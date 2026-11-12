#!/usr/bin/env python3
"""Track which command ($setup, $wireframe, $mockup, $export) a kit is in, and undo one with reset.

    state.py <kit> begin <setup|wireframe|mockup|export>
    state.py <kit> step "<what was just done>"
    state.py <kit> done
    state.py <kit> reset
    state.py <kit> show
    state.py <kit> summary      everything saved so far, for $info; changes nothing

begin prints one of:
  NEEDS_SETUP   $wireframe and $mockup need a saved setup; $export does not
  START         a new run of the command
  RESUME        back to a command left unfinished for another one; its step is printed
  CONTINUE      the same command is still running; carry on from its step
reset deletes every file the current command created, restores the text files it changed
(when no other command ran in between), and starts that command again. Resetting setup
also deletes the setup, so $wireframe and $mockup are blocked until $setup runs again.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ask import clean_inputs  # noqa: E402

COMMANDS = ("setup", "wireframe", "mockup", "export")
HIDDEN = ".gui"
BACKUP_TYPES = {".json", ".md", ".txt"}
BACKUP_MAX = 5 * 1024 * 1024


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def state_path(kit: Path) -> Path:
    return kit / HIDDEN / "state.json"


def load(kit: Path) -> dict:
    try:
        return json.loads(state_path(kit).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"current": None, "runs": {}}


def save(kit: Path, data: dict) -> None:
    path = state_path(kit)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def snapshot(kit: Path) -> dict[str, list]:
    files = {}
    if kit.exists():
        for path in kit.rglob("*"):
            rel = path.relative_to(kit)
            if rel.parts[0] == HIDDEN or not path.is_file():
                continue
            stat = path.stat()
            files[rel.as_posix()] = [stat.st_size, stat.st_mtime_ns]
    return files


def backup(kit: Path, command: str, files: dict) -> None:
    folder = kit / HIDDEN / "backup" / command
    if folder.exists():
        shutil.rmtree(folder)
    for rel, (size, _) in files.items():
        if Path(rel).suffix.lower() in BACKUP_TYPES and size <= BACKUP_MAX:
            target = folder / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(kit / rel, target)


def new_run(kit: Path, command: str) -> dict:
    files = snapshot(kit)
    backup(kit, command, files)
    return {"status": "active", "step": "", "started": now(), "baseline": files, "created": [], "periods": 1}


def created_since(kit: Path, run: dict) -> list[str]:
    current = snapshot(kit)
    return sorted(set(current) - set(run["baseline"]))


def pause(kit: Path, run: dict) -> None:
    run["created"] = sorted(set(run["created"]) | set(created_since(kit, run)))
    run["status"] = "paused"


def needs_setup(kit: Path) -> bool:
    return not (kit / "briefs" / "setup.json").exists()


def cmd_begin(kit: Path, command: str) -> int:
    data = load(kit)
    if command in ("wireframe", "mockup") and needs_setup(kit):
        print(json.dumps({"status": "NEEDS_SETUP", "message": "Run $setup before $wireframe or $mockup. $export can run independently."}))
        return 3
    kit.mkdir(parents=True, exist_ok=True)
    runs, current = data["runs"], data.get("current")
    run = runs.get(command)
    if current == command and run and run["status"] == "active":
        print(json.dumps({"status": "CONTINUE", "command": command, "step": run["step"]}, ensure_ascii=False))
        return 0
    if current and current != command and runs.get(current, {}).get("status") == "active":
        pause(kit, runs[current])
    if run and run["status"] == "paused":
        run["baseline"] = snapshot(kit)
        run["status"], run["periods"] = "active", run["periods"] + 1
        status = "RESUME"
    else:
        run = runs[command] = new_run(kit, command)
        status = "START"
    data["current"] = command
    save(kit, data)
    print(json.dumps({"status": status, "command": command, "step": run["step"],
                      "left": current if current and current != command else None}, ensure_ascii=False))
    return 0


def cmd_step(kit: Path, text: str) -> int:
    data = load(kit)
    current = data.get("current")
    if not current:
        print(json.dumps({"status": "NO_COMMAND"}))
        return 1
    data["runs"][current]["step"] = text
    save(kit, data)
    print(json.dumps({"status": "OK", "command": current, "step": text}, ensure_ascii=False))
    return 0


def cmd_done(kit: Path) -> int:
    data = load(kit)
    current = data.get("current")
    if not current:
        print(json.dumps({"status": "NO_COMMAND"}))
        return 1
    run = data["runs"][current]
    pause(kit, run)
    run["status"], run["finished"] = "done", now()
    data["current"] = None
    save(kit, data)
    print(json.dumps({"status": "DONE", "command": current}))
    return 0


def cmd_reset(kit: Path) -> int:
    data = load(kit)
    current = data.get("current")
    if not current:
        print(json.dumps({"status": "NOTHING", "message": "No command is running, so nothing was reset."}))
        return 0
    run = data["runs"][current]
    created = sorted(set(run["created"]) | set(created_since(kit, run)))
    if current == "setup" and (kit / "briefs" / "setup.json").exists():
        created = sorted(set(created) | {"briefs/setup.json"})
    deleted = 0
    for rel in created:
        path = kit / rel
        if path.is_file():
            path.unlink()
            deleted += 1
    restored, kept = [], []
    now_files = snapshot(kit)
    backups = kit / HIDDEN / "backup" / current
    for rel, stamp in run["baseline"].items():
        if rel in now_files and now_files[rel] != stamp:
            source = backups / rel
            if run["periods"] == 1 and source.exists():
                shutil.copy2(source, kit / rel)
                restored.append(rel)
            else:
                kept.append(rel)
    for folder in sorted((p for p in kit.rglob("*") if p.is_dir() and p.relative_to(kit).parts[0] != HIDDEN),
                         key=lambda p: len(p.parts), reverse=True):
        if not any(folder.iterdir()):
            folder.rmdir()
    removed_inputs = clean_inputs(kit)
    data["runs"][current] = new_run(kit, current)
    save(kit, data)
    print(json.dumps({"status": "RESET", "command": current, "deleted_files": deleted + removed_inputs,
                      "restored_files": restored, "changed_but_kept": kept,
                      "setup_deleted": current == "setup"}, ensure_ascii=False))
    return 0


def cmd_show(kit: Path) -> int:
    data = load(kit)
    runs = {name: {k: v for k, v in run.items() if k not in ("baseline", "created")} | {"files_created": len(run["created"])}
            for name, run in data["runs"].items()}
    print(json.dumps({"kit": str(kit), "setup": not needs_setup(kit), "current": data.get("current"), "runs": runs},
                     indent=2, ensure_ascii=False))
    return 0


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def value(answers: dict, key: str):
    return (answers.get(key) or {}).get("value")


def files_of(entry) -> list[str]:
    return [f.get("path") for f in (entry or {}).get("files") or [] if isinstance(f, dict)]


def list_images(kit: Path, folder: str) -> list[str]:
    path = kit / folder
    return sorted(p.relative_to(kit).as_posix() for p in path.glob("*.png")) if path.exists() else []


def screen_briefs(kit: Path, command: str) -> list[dict]:
    folder = kit / "briefs" / command
    if not folder.exists():
        return []
    return [(p.stem, read_json(p) or {}) for p in sorted(folder.glob("*.json")) if p.stem not in ("_new", "full", "demos")]


def cmd_summary(kit: Path) -> int:
    data = load(kit)
    setup = read_json(kit / "briefs" / "setup.json")
    summary = {"kit": kit.resolve().name, "path": str(kit)}
    if setup:
        summary["setup"] = {"size": setup.get("size"), "orientation": setup.get("orientation"),
                            "game_type": setup.get("game_type"),
                            "game_type_description": setup.get("game_type_description"), "gameplay": setup.get("gameplay"),
                            "saved": setup.get("submitted")}
    else:
        summary["setup"] = None
    current = data.get("current")
    summary["current"] = {"command": current, "step": data["runs"][current]["step"]} if current else None
    summary["commands"] = {name: {"status": run["status"], "step": run["step"]} for name, run in data["runs"].items()}

    wireframes = []
    for stem, record in screen_briefs(kit, "wireframe"):
        answers = record.get("answers") or {}
        wireframes.append({"screen": record.get("screen_label") or stem, "function": value(answers, "function"),
                           "areas": {k: v for k, v in (value(answers, "areas") or {}).items() if v},
                           "options": record.get("options"), "prototype": record.get("prototype")})
    full = read_json(kit / "briefs" / "wireframe" / "full.json")
    summary["wireframe"] = {
        "screens": wireframes,
        "full": [{"screen": e.get("label"), "note": e.get("note"), "files": len(e.get("files") or [])}
                 for e in (full or {}).get("screens", [])],
        "full_options": (full or {}).get("options"),
        "full_prototype": (full or {}).get("prototype"),
        "images": list_images(kit, "preview/wireframes"),
        "prototype": "demo/index.html" if (kit / "demo" / "index.html").exists() else None,
    }

    mockups = []
    for stem, record in screen_briefs(kit, "mockup"):
        answers = record.get("answers") or {}
        kit_answer, start, background = value(answers, "kit") or {}, value(answers, "start") or {}, value(answers, "background") or {}
        if kit_answer.get("choice") == "yes":
            source = {"type": "ui_kit", "files": len(files_of(kit_answer)), "note": kit_answer.get("note")}
        else:
            source = {"type": "reference", "files": len(files_of(start)), "note": start.get("note")} \
                if start.get("choice") == "reference" else {"type": "description"}
            style = {"colors": value(answers, "colors"), "theme": (value(answers, "theme") or {}).get("label"),
                     "ui_style": (value(answers, "ui_style") or {}).get("label"),
                     "ui_style_description": record.get("ui_style_description"), "note": value(answers, "style_note")}
            source.update({k: v for k, v in style.items() if v})
        names = [s.get("label") or s.get("screen") or "(Codex đoán)" for s in record.get("screens") or []]
        mockups.append({"screen": ", ".join(names) or record.get("screen_label") or stem,
                        "wireframe_files": len(value(answers, "wireframe") or []),
                        "source": source, "background": background.get("label"),
                        "background_note": (answers.get("background") or {}).get("note"), "options": record.get("options"),
                        "approved_concept": record.get("approved_concept")})
    full = read_json(kit / "briefs" / "mockup" / "full.json")
    demos = read_json(kit / "briefs" / "mockup" / "demos.json") or {}
    summary["mockup"] = {
        "screens": mockups,
        "style_anchor": demos.get("style_anchor"),
        "demos": demos.get("screens") or [],
        "sprite_production": demos.get("sprite_production") or {"requested": False},
        "full": [{"screen": e.get("label"), "note": e.get("note"), "files": len(e.get("files") or [])}
                 for e in (full or {}).get("screens", [])],
        "images": [p for p in list_images(kit, "preview/mockups") if "_variants" not in p and "_vs_reference" not in p],
    }
    export = read_json(kit / "briefs" / "export.json")
    delivery = read_json(kit / "export" / "delivery_report.json") or {}
    files = delivery.get("files") or []
    if not files and (kit / "export").exists():
        files = sorted(p.relative_to(kit).as_posix() for p in (kit / "export").rglob("*")
                       if p.is_file() and p.parent.name in ("psd", "png", "unity"))
    summary["export"] = {"formats": (export or {}).get("formats"), "layouts": (export or {}).get("layouts"),
                         "source": (export or {}).get("source"), "sources": (export or {}).get("sources"),
                         "photoshop": (export or {}).get("photoshop"), "files": files,
                         "resource_map": delivery.get("resources"), "warnings": delivery.get("warnings")}
    inputs = kit / "inputs"
    summary["attached_files"] = sum(1 for p in inputs.rglob("*") if p.is_file()) if inputs.exists() else 0
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("kit")
    parser.add_argument("action", choices=["begin", "step", "done", "reset", "show", "summary"])
    parser.add_argument("value", nargs="?")
    args = parser.parse_args()
    kit = Path(args.kit)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.action == "begin":
        if args.value not in COMMANDS:
            parser.error(f"begin needs one of {COMMANDS}")
        if args.value in ("setup", "export"):
            kit.mkdir(parents=True, exist_ok=True)
        elif not kit.exists():
            print(json.dumps({"status": "NEEDS_SETUP", "message": "Run $setup before $wireframe or $mockup. $export can run independently."}))
            return 3
        return cmd_begin(kit, args.value)
    if args.action == "step":
        return cmd_step(kit, args.value or "")
    if args.action == "done":
        return cmd_done(kit)
    if args.action == "reset":
        return cmd_reset(kit)
    if args.action == "summary":
        if not kit.exists():
            print(json.dumps({"kit": None, "setup": None, "message": "No kit yet. Run $setup or $export."}))
            return 0
        return cmd_summary(kit)
    return cmd_show(kit)


if __name__ == "__main__":
    raise SystemExit(main())
