"""Persistent project workflow, exact approved images, sprite masters and Figma work queue.

This helper never drives the engine or calls Figma. A connector must perform and
verify remote writes before mark-synced is used. See references/prototype.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from datetime import datetime, timezone
from urllib.parse import urlparse

from PIL import Image


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=".workflow-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def local_file(kit, relative):
    path = (kit / relative).resolve()
    if not path.is_relative_to(kit.resolve()):
        raise ValueError("Đường dẫn phải nằm trong kit.")
    return path


def identifier(value):
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", value):
        raise ValueError("Mã màn/component dùng chữ thường, số, _ hoặc -.")
    return value


def figma_key(url):
    parsed = urlparse(url)
    parts = parsed.path.strip("/").split("/")
    if (parsed.scheme != "https" or parsed.hostname not in ("figma.com", "www.figma.com")
            or parsed.username or parsed.password or len(parts) < 2
            or parts[0] not in ("design", "file", "board") or not parts[1]):
        raise ValueError("Cung cấp link file Figma của dự án: https://www.figma.com/design/…")
    return parts[1]


def configuration(kit):
    return (read(kit / "briefs/setup.json", {}) or {}).get("project_workflow") or {}


def registry_path():
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "game-ui-kit/projects.json"


def project_key(project):
    value = str(Path(project).resolve())
    return os.path.normcase(value)


def remember_project(kit):
    project = configuration(kit).get("project_path")
    if project:
        path = registry_path()
        records = read(path, {}) or {}
        records[project_key(project)] = {"project": str(Path(project).resolve()),
                                         "kit": str(kit.resolve()), "updated": now()}
        write(path, records)


def resolve_project(project):
    entry = (read(registry_path(), {}) or {}).get(project_key(project))
    if entry and (Path(entry["kit"]) / "briefs/setup.json").is_file():
        return entry
    return None


def project_screens(kit):
    """Actual project inventory wins over generic screen suggestions."""
    catalog = read(kit / "briefs/project_screens.json", {}) or {}
    rows = catalog if isinstance(catalog, list) else catalog.get("screens", []) if isinstance(catalog, dict) else []
    demos = read(kit / "briefs/mockup/demos.json", {}) or {}
    if not isinstance(demos, dict):
        demos = {}
    by_demo = {r["screen"]: r for r in demos.get("screens", []) if r.get("screen")}
    combined = list(rows)
    for folder in ("wireframe", "mockup"):
        for path in sorted((kit / "briefs" / folder).glob("*.json")):
            record = read(path, {}) or {}
            if not isinstance(record, dict):
                continue
            if path.stem not in ("full", "demos", "_new") and record.get("screen"):
                combined.append({"screen": record["screen"], "label": record.get("screen_label")})
            combined.extend(record.get("screens") or [])
    combined.extend(demos.get("screens") or [])
    for path in sorted((kit / "mockups").glob("*.json")):
        if path.stem not in ("chosen", "confirmed"):
            screen = re.sub(r"__v\d+$", "", path.stem)
            combined.append({"screen": screen, "label": screen.replace("_", " ").title()})
    result, seen = [], set()
    for row in combined:
        if not isinstance(row, dict):
            continue
        screen = row.get("screen") or row.get("id")
        if not screen or screen in seen:
            continue
        seen.add(screen)
        demo = by_demo.get(screen, {})
        status = "đã chốt" if demo.get("approved_demo") else (
            "đang sửa" if demo.get("drafts") or demo.get("current_draft") else "chưa làm")
        result.append({"value": screen, "label": row.get("label") or row.get("name") or screen,
                       "group": row.get("group") or row.get("flow") or "Màn của dự án",
                       "hint": f"{status} · {row.get('function') or row.get('note') or ''}".rstrip(" ·"),
                       "status": status})
    return result


def catalog(kit, source):
    record = read(source)
    rows = record if isinstance(record, list) else (record or {}).get("screens", [])
    if not rows:
        raise ValueError("Danh mục phải chứa danh sách screens có mã và tên màn thực tế.")
    seen = set()
    for row in rows:
        key = identifier(row.get("screen") or row.get("id") or "")
        if key in seen:
            raise ValueError(f"Trùng mã màn: {key}")
        row["screen"] = key
        seen.add(key)
    write(kit / "briefs/project_screens.json", {"screens": rows, "updated": now()})
    return {"screens": project_screens(kit)}


def exact_copy(source, target):
    """Copy bytes without resampling/re-encoding, verify before atomic replacement."""
    source, target = Path(source), Path(target)
    expected = digest(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=".image-", suffix=target.suffix, dir=target.parent)
    os.close(handle)
    try:
        shutil.copyfile(source, temporary)
        if digest(temporary) != expected:
            raise ValueError("Ảnh nguồn thay đổi trong khi copy.")
        os.replace(temporary, target)
        if digest(target) != expected:
            raise ValueError("Hash ảnh lưu không khớp nguồn.")
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return expected


def queue(kit):
    return read(kit / "briefs/project_sync.json", {"version": 1, "approved": {}, "exported": {}})


def approve(kit, screen, image, label, group, evidence, filename=None):
    identifier(screen)
    if not evidence.strip():
        raise ValueError("Cần ghi lời xác nhận chốt đúng ảnh của người dùng.")
    source = Path(image).resolve()
    with Image.open(source) as img:
        if img.format != "PNG":
            raise ValueError("Ảnh chốt phải là PNG; không tự chuyển đổi ảnh đã duyệt.")
        img.verify()
    sha = digest(source)
    snapshot = kit / "style/approvals" / screen / f"{sha}.png"
    exact_copy(source, snapshot)
    canonical = kit / "style/concepts" / f"{screen}__approved.png"
    exact_copy(snapshot, canonical)
    relative = canonical.relative_to(kit).as_posix()
    register_path = kit / "briefs/mockup/demos.json"
    demos = read(register_path, {"screens": [], "sprite_production": {"requested": False}})
    entry = next((r for r in demos["screens"] if r.get("screen") == screen), None)
    if entry is None:
        entry = {"screen": screen, "label": label or screen, "drafts": []}
        demos["screens"].append(entry)
    if entry.get("approved_sha256") and entry["approved_sha256"] != sha:
        entry.setdefault("approval_history", []).append({"sha256": entry["approved_sha256"],
                                                        "image": entry.get("approval_snapshot")})
    entry.update(approved_demo=relative, approved_sha256=sha,
                 approval_snapshot=snapshot.relative_to(kit).as_posix(), evidence=evidence, group=group)
    if not demos.get("style_anchor"):
        exact_copy(snapshot, kit / "style/style_anchor.png")
        demos["style_anchor"] = "style/style_anchor.png"
    demos["internal_sprites"] = {"enabled": True, "registry": "style/reusable_components.json"}
    write(register_path, demos)
    brief_path = kit / "briefs/mockup" / f"{screen}.json"
    brief = read(brief_path, {"screen": screen, "screen_label": label or screen})
    brief.update(approved_concept=relative, approved_sha256=sha)
    write(brief_path, brief)
    components_path = kit / "style/reusable_components.json"
    components = read(components_path, {"components": {}, "approved_sources": {}})
    old_source = components.get("approved_sources", {}).get(screen)
    if old_source and old_source.get("sha256") != sha:
        components.setdefault("source_history", []).append(old_source)
    components.setdefault("approved_sources", {})[screen] = {
        "image": snapshot.relative_to(kit).as_posix(), "sha256": sha, "status": "inspect-and-extract"}
    write(components_path, components)

    config = configuration(kit)
    work = queue(kit)
    previous = work["approved"].get(screen, {})
    name = filename or previous.get("filename") or f"{screen}.png"
    if Path(name).name != name or not name.lower().endswith(".png") or "/" in name or "\\" in name:
        raise ValueError("Tên file lưu phải là tên PNG, không chứa đường dẫn.")
    target = Path(config["approved_demo_folder"]) / name if config.get("approved_demo_folder") else None
    same_remote = (previous.get("sha256") == sha and previous.get("figma_url") == config.get("figma_url")
                   and previous.get("group") == group and previous.get("label") == (label or screen))
    item = {**previous, "screen": screen, "label": label or screen, "group": group, "filename": name,
            "source": str(snapshot.resolve()), "sha256": sha, "figma_url": config.get("figma_url"),
            "remote_status": previous.get("remote_status", "pending") if same_remote else "pending",
            "folder_status": "pending" if target else "not-configured"}
    if previous.get("figma_url") != config.get("figma_url"):
        item.pop("node_id", None)
        item.pop("node_url", None)
    work["approved"][screen] = item
    write(kit / "briefs/project_sync.json", work)  # retain approval if a destination is unavailable
    if target:
        try:
            if target.exists() and digest(target) != sha:
                owned = previous.get("folder_path") == str(target.resolve())
                if not owned or digest(target) != previous.get("folder_sha256"):
                    raise ValueError("File đích chưa được ánh xạ hoặc đã sửa bên ngoài; cần đối chiếu trước khi thay.")
            exact_copy(snapshot, target)
            item.update(folder_status="verified", folder_path=str(target.resolve()), folder_sha256=sha)
            item.pop("folder_error", None)
        except (OSError, ValueError) as error:
            item.update(folder_status="error", folder_error=str(error))
    write(kit / "briefs/project_sync.json", work)
    checkpoint(kit)
    return item


def sync_plan(kit, namespace="approved"):
    work = queue(kit)
    config = configuration(kit)
    if namespace == "exported" and config.get("exported_demo_folder"):
        root = Path(config["exported_demo_folder"])
        if not root.is_dir():
            raise ValueError("Folder demo xuất file chưa tồn tại hoặc chưa truy cập được.")
        for source in sorted(root.rglob("*")):
            if not source.is_file() or source.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
                continue
            relative = source.relative_to(root).as_posix()
            key = relative.casefold()
            old = work[namespace].get(key, {})
            sha = digest(source)
            same = old.get("sha256") == sha and old.get("figma_url") == config.get("figma_url")
            work[namespace][key] = {**old, "source": str(source.resolve()), "relative": relative,
                "sha256": sha, "group": source.parent.parent.name if source.parent.name == "demo" else source.parent.name,
                "figma_url": config.get("figma_url"),
                "remote_status": old.get("remote_status", "pending") if same else "pending"}
    # Refresh a changed destination even when the approved pixels are unchanged.
    for item in work[namespace].values():
        if item.get("figma_url") != config.get("figma_url"):
            item.update(figma_url=config.get("figma_url"), remote_status="pending")
            item.pop("node_id", None)
    write(kit / "briefs/project_sync.json", work)
    return {"figma_url": config.get("figma_url"), "namespace": namespace,
            "section": "Demo chốt trong phiên" if namespace == "approved" else "Demo bản cuối sau Export",
            "items": [{"key": key, **item} for key, item in work[namespace].items()
                      if item.get("remote_status") != "verified"],
            "note": "Dùng connector để cập nhật và xem lại Figma. Đây chỉ là hàng đợi, chưa ghi remote."}


def mark_synced(kit, namespace, key, sha256, node_id, url):
    work = queue(kit)
    item = work[namespace][key]
    target = configuration(kit).get("figma_url")
    if not target or item.get("figma_url") != target or figma_key(url) != figma_key(target):
        raise ValueError("Node phải thuộc đúng file Figma được cấu hình.")
    if item["sha256"] != sha256 or digest(item["source"]) != sha256:
        raise ValueError("Ảnh đã thay đổi; không đánh dấu đồng bộ bằng hash cũ.")
    if not re.fullmatch(r"\d+:\d+", node_id):
        raise ValueError("Cần node ID đã xác minh trên Figma.")
    item.update(remote_status="verified", node_id=node_id, node_url=url, verified_at=now())
    write(kit / "briefs/project_sync.json", work)
    return item


def archive_exported(kit, files):
    config = configuration(kit)
    if not config.get("exported_demo_folder"):
        return {"status": "not-configured"}
    root = Path(config["exported_demo_folder"])
    records = read(kit / ".gui/export_copies.json", {})
    errors = []
    for relative in files:
        source = local_file(kit, relative)
        parts = Path(relative).parts
        if source.suffix.lower() != ".png" or "demo" not in parts:
            continue
        # Delivery's screen/demo path is retained; variants stay distinct.
        index = parts.index("demo")
        target = root / Path(*parts[index - 1:])
        key = target.relative_to(root).as_posix().casefold()
        try:
            expected = digest(source)
            if target.exists() and digest(target) not in (expected, records.get(key)):
                raise ValueError("File đích đã thay đổi ngoài lần xuất được ghi nhận.")
            exact_copy(source, target)
            records[key] = expected
        except (OSError, ValueError) as error:
            errors.append({"file": relative, "error": str(error)})
    write(kit / ".gui/export_copies.json", records)
    plan = sync_plan(kit, "exported")
    return {"status": "pending" if errors else "copied", "errors": errors,
            "figma_pending": len(plan["items"])}


def component(kit, name, source, box=None, replace=False):
    """Capture pixels once from the approved master; never regenerate or upscale."""
    identifier(name)
    source = local_file(kit, source)
    records_path = kit / "style/reusable_components.json"
    records = read(records_path, {"components": {}, "approved_sources": {}})
    master = kit / "style/components" / f"{name}.png"
    if name in records["components"] and not replace:
        raise ValueError("Component đã có master; dùng lại hoặc yêu cầu thay thiết kế rõ ràng.")
    source_hash = digest(source)
    approved_hashes = {row.get("sha256") for row in records.get("approved_sources", {}).values()}
    approved_hashes.update(row.get("sha256") for row in records.get("source_history", []))
    if source_hash not in approved_hashes:
        raise ValueError("Nguồn component phải là ảnh đã chốt được ghi nhận trong kit.")
    with Image.open(source) as image:
        image.load()
        if box:
            left, top, right, bottom = box
            if not (0 <= left < right <= image.width and 0 <= top < bottom <= image.height):
                raise ValueError("Vùng cắt nằm ngoài ảnh gốc.")
            image = image.crop(tuple(box))
        master.parent.mkdir(parents=True, exist_ok=True)
        if replace and master.exists():
            exact_copy(master, kit / "style/component_history" / name / f"{digest(master)}.png")
        image.save(master, format="PNG")
        size = list(image.size)
    records["components"][name] = {"master": master.relative_to(kit).as_posix(), "size": size,
        "sha256": digest(master), "source": source.relative_to(kit).as_posix(),
        "source_sha256": source_hash, "box": box, "alpha_note": "Pixels retained; no inferred transparency."}
    write(records_path, records)
    return records["components"][name]


def compose(kit, layout, output):
    spec = read(layout)
    records = read(kit / "style/reusable_components.json", {}).get("components", {})
    canvas = Image.new("RGBA", tuple(spec["size"]), tuple(spec.get("color", [0, 0, 0, 0])))
    if spec.get("background"):
        with Image.open(local_file(kit, spec["background"])) as background:
            if background.size != canvas.size:
                raise ValueError("Background phải đúng kích thước canvas; không tự kéo giãn.")
            canvas.alpha_composite(background.convert("RGBA"))
    for item in spec.get("components", []):
        master = records[item["id"]]
        path = local_file(kit, master["master"])
        if digest(path) != master["sha256"]:
            raise ValueError(f"Master {item['id']} đã đổi ngoài bản ghi; dừng để tránh trôi chi tiết.")
        with Image.open(path) as image:
            image = image.convert("RGBA")
            size = (item.get("width", image.width), item.get("height", image.height))
            if size != image.size:
                if not item.get("allow_scale") or abs(size[0] / image.width - size[1] / image.height) > .001:
                    raise ValueError("Giữ nguyên sprite; chỉ scale đồng dạng từ master khi đã cho phép.")
                image = image.resize(size, Image.Resampling.NEAREST if item.get("pixel_art") else Image.Resampling.LANCZOS)
            x, y = int(item["x"]), int(item["y"])
            if x < 0 or y < 0 or x + image.width > canvas.width or y + image.height > canvas.height:
                raise ValueError("Component bị cắt khỏi canvas.")
            canvas.alpha_composite(image, (x, y))
    path = local_file(kit, output)
    if path.is_relative_to((kit / "style/components").resolve()):
        raise ValueError("Không ghi demo đè lên sprite master.")
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path)
    return {"output": str(path), "components_reused": len(spec.get("components", []))}


def pending_question(kit):
    question = read(kit / ".gui/question.json", {})
    return question if question.get("status") == "waiting" else None


def question(kit, text=None, options=None, answer=None, evidence=None):
    path = kit / ".gui/question.json"
    entry = read(path, {})
    if answer is not None:
        if not pending_question(kit) or not evidence or answer not in entry.get("options", []):
            raise ValueError("Chỉ nhận lựa chọn đã được người dùng gửi; Skip/đóng bảng vẫn là chờ.")
        entry.update(status="answered", answer=answer, evidence=evidence, answered_at=now())
    elif text:
        if pending_question(kit):
            raise ValueError("Câu hỏi trước vẫn chờ trả lời; không thay bằng câu hỏi/form khác.")
        if not options:
            raise ValueError("Cần danh sách lựa chọn.")
        entry = {"text": text, "options": options, "status": "waiting", "created": now()}
    write(path, entry)
    checkpoint(kit)
    return entry


def cancel_question(kit, evidence):
    if not evidence or not pending_question(kit):
        raise ValueError("Cần yêu cầu đổi/hủy tác vụ rõ ràng từ người dùng để hủy câu đang chờ.")
    entry = read(kit / ".gui/question.json", {})
    entry.update(status="superseded", evidence=evidence, updated=now())
    write(kit / ".gui/question.json", entry)
    checkpoint(kit)
    return entry


def checkpoint(kit):
    commands = read(kit / ".gui/state.json", {})
    snapshot = {"updated": now(), "kit": str(kit.resolve()), "project_workflow": configuration(kit),
        "current": commands.get("current"),
        "runs": {k: {n: v for n, v in row.items() if n not in ("baseline", "created")}
                 for k, row in commands.get("runs", {}).items()},
        "pending_question": pending_question(kit), "form": read(kit / ".gui/ask.json"),
        "screens": project_screens(kit), "demo_register": "briefs/mockup/demos.json",
        "sprite_masters": "style/reusable_components.json", "sync_queue": "briefs/project_sync.json"}
    write(kit / ".gui/handoff.json", snapshot)
    return snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["resolve", "catalog", "approve", "sync-plan", "mark-synced",
                                            "component", "compose", "checkpoint", "question", "answer", "cancel-question"])
    parser.add_argument("kit", type=Path, help="Kit path; resolve takes the project path instead")
    parser.add_argument("--file", type=Path)
    parser.add_argument("--image", type=Path)
    parser.add_argument("--screen")
    parser.add_argument("--label", default="")
    parser.add_argument("--group", default="")
    parser.add_argument("--evidence", default="")
    parser.add_argument("--filename")
    parser.add_argument("--namespace", choices=["approved", "exported"], default="approved")
    parser.add_argument("--key")
    parser.add_argument("--sha256")
    parser.add_argument("--node-id")
    parser.add_argument("--url")
    parser.add_argument("--id")
    parser.add_argument("--source")
    parser.add_argument("--box", type=int, nargs=4)
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--output")
    parser.add_argument("--text")
    parser.add_argument("--options", nargs="+")
    parser.add_argument("--choice")
    args = parser.parse_args()
    if hasattr(__import__("sys").stdout, "reconfigure"):
        __import__("sys").stdout.reconfigure(encoding="utf-8")
    try:
        kit = args.kit.resolve()
        if args.command == "resolve": result = resolve_project(kit) or {"status": "NOT_REGISTERED"}
        elif args.command == "catalog": result = catalog(kit, args.file)
        elif args.command == "approve": result = approve(kit, args.screen, args.image, args.label, args.group, args.evidence, args.filename)
        elif args.command == "sync-plan": result = sync_plan(kit, args.namespace)
        elif args.command == "mark-synced": result = mark_synced(kit, args.namespace, args.key, args.sha256, args.node_id, args.url)
        elif args.command == "component": result = component(kit, args.id, args.source, args.box, args.replace)
        elif args.command == "compose": result = compose(kit, args.file, args.output)
        elif args.command == "checkpoint": result = checkpoint(kit)
        elif args.command == "question": result = question(kit, args.text, args.options)
        elif args.command == "cancel-question": result = cancel_question(kit, args.evidence)
        else: result = question(kit, answer=args.choice, evidence=args.evidence)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"status": "ERROR", "message": str(error)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
