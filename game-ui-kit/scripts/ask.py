#!/usr/bin/env python3
"""Ask the user a form in their browser, served from localhost, and save the answers in the kit.

    ask.py <form> <kit> --out briefs/<name>.json     open the form and wait for the answer
    ask.py <kit> --wait                              wait again, or collect an answer already given

The form server runs on its own, so it survives the calling command being cut off or the
turn ending, and keeps the answer until --wait collects it.

<form> is a file in the skill's forms/ folder: setup, wireframe, full, mockup, revise or export.
The revise form offers the images in preview/<--kind>/ of the --screens given.
For --kind concepts, pass one draft image stem in --screens to revise that concept.
Prints a JSON line with the answers when the user submits. Attached files go to <kit>/inputs/.
Nothing else is written: no copy of the form, no logs. Files in inputs/ that no answer file
under <kit>/briefs/ refers to any more are deleted after every form.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
import unicodedata
import webbrowser
import zipfile
from collections import defaultdict
from contextlib import closing
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from photoshop import discover_photoshop, inspect_photoshop

SKILL = Path(__file__).resolve().parent.parent
FORMS = SKILL / "forms"
CATALOG = SKILL / "references" / "catalog.md"
FORM_SUGGESTIONS = SKILL / "references" / "form_suggestions.json"
FORM_HISTORY = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "game-ui-kit" / "form-history.sqlite3"
ALLOWED = {".png", ".jpg", ".jpeg", ".webp", ".psd", ".zip"}
FROM_ZIP = {".png", ".jpg", ".jpeg", ".webp", ".psd"}
MAX_FILE = 300 * 1024 * 1024
MAX_UNZIPPED = 1024 * 1024 * 1024
MAX_MEMBERS = 3000
SERVE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif"}


def slug(text: str) -> str:
    text = unicodedata.normalize("NFD", text or "").replace("đ", "d").replace("Đ", "D")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_") or "item"


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


# ---------- option lists ----------

def catalog_rows(heading: str) -> list[dict]:
    """Rows of a catalog table. The form shows the Vietnamese "Mô tả trên form" column and the reference games."""
    text = CATALOG.read_text(encoding="utf-8")
    part = text.split(f"## {heading}", 1)[1].split("\n## ", 1)[0]
    rows, header = [], []
    for line in part.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and cells[0] == "#":
            header = cells
        elif len(cells) >= 3 and cells[0].isdigit():
            row = dict(zip(header, cells))
            hint = row.get("Mô tả trên form") or cells[2]
            games = row.get("Reference games")
            rows.append({"value": slug(cells[1]), "label": cells[1], "hint": f"{hint} Ví dụ: {games}." if games else hint})
    return rows


def catalog_screens() -> list[dict]:
    text = CATALOG.read_text(encoding="utf-8").split("## Screens", 1)[1]
    options = []
    for line in text.splitlines():
        match = re.match(r"\s*-\s*\*\*(.+?):\*\*\s*(.+)", line)
        if match:
            for name in match.group(2).split(","):
                name = name.strip()
                if name:
                    options.append({"value": slug(name), "label": name, "group": match.group(1)})
    return options


VARIANT = re.compile(r"^(.*)__v(\d+)$")


def kit_layouts(kit: Path) -> list[str]:
    folder = kit / "mockups"
    if not folder.exists():
        return []
    return sorted(p.stem for p in folder.glob("*.json") if p.stem not in ("chosen", "confirmed"))


def screen_of(stem: str) -> str:
    match = VARIANT.match(stem)
    return match.group(1) if match else stem


def kit_screens(kit: Path) -> list[dict]:
    seen, options = set(), []
    for stem in kit_layouts(kit):
        screen = screen_of(stem)
        if screen not in seen:
            seen.add(screen)
            options.append({"value": screen, "label": screen.replace("_", " ").title(), "group": "Đã có trong kit"})
    return options


def screen_label(kit: Path, screen: str) -> str:
    """The name the user gave a screen in a form, else one made from its id."""
    for folder in ("wireframe", "mockup"):
        briefs = kit / "briefs" / folder
        for path in sorted(briefs.glob("*.json")) if briefs.exists() else []:
            record = read_json(path) or {}
            if record.get("screen") == screen and record.get("screen_label"):
                return record["screen_label"]
            for entry in record.get("screens") or []:
                if entry.get("screen") == screen and entry.get("label"):
                    return entry["label"]
    return screen.replace("_", " ").title()


def kit_previews(kit: Path, kind: str, screens: list[str]) -> list[dict]:
    """The rendered versions of the given screens, for the revise form, each with its image."""
    if kind == "concepts":
        folder = kit / "style" / "concepts"
        return [{"value": image.stem, "label": "Concept đang chỉnh", "image": image.relative_to(kit).as_posix()}
                for image in folder.glob("*.png") if image.stem in screens and image.is_file()]
    folder = kit / "preview" / kind
    options = []
    for stem in kit_layouts(kit):
        if screens and screen_of(stem) not in screens:
            continue
        image = folder / f"{stem}.png"
        if not image.exists():
            continue
        match = VARIANT.match(stem)
        label = f"{screen_label(kit, screen_of(stem))}, bản {match.group(2) if match else 1}"
        options.append({"value": stem, "label": label, "image": image.relative_to(kit).as_posix()})
    return options


def kit_mockups(kit: Path) -> list[dict]:
    options = []
    for stem in kit_layouts(kit):
        match = VARIANT.match(stem)
        label = f"{screen_of(stem).replace('_', ' ').title()}, option {match.group(2) if match else 1}"
        image = f"preview/mockups/{stem}.png"
        options.append({"value": stem, "label": label, "image": image if (kit / image).exists() else None})
    return options


PREVIEW = {"kind": "mockups", "screens": []}  # set from --kind and --screens, for kit:previews


def options_for(source: str, kit: Path) -> list[dict]:
    options, seen = [], set()
    for part in source.split("+"):
        if part == "catalog:game_types":
            found = catalog_rows("Game types")
        elif part == "catalog:art_styles":
            found = catalog_rows("Art styles")
        elif part == "catalog:screens":
            found = catalog_screens()
        elif part == "kit:screens":
            found = kit_screens(kit)
        elif part == "kit:mockups":
            found = kit_mockups(kit)
        elif part == "kit:previews":
            found = kit_previews(kit, PREVIEW["kind"], PREVIEW["screens"])
        elif part == "host:photoshop":
            found = [{"value": item["path"], "label": f'{item["label"]} · {item["version"]}',
                      "hint": item["path"]} for item in discover_photoshop()]
        else:
            raise SystemExit(f"Unknown options_from: {part}")
        for option in found:
            if option["value"] not in seen:
                seen.add(option["value"])
                options.append(option)
    return options


def setup_size(kit: Path):
    setup = read_json(kit / "briefs" / "setup.json") or {}
    return setup.get("size"), setup.get("orientation")


def build_context(kit: Path) -> dict:
    size, orientation = setup_size(kit)
    context = {"kit": kit.resolve().name, "has_layouts": bool(kit_layouts(kit))}
    if orientation:
        context["orientation"] = orientation
        context["summary"] = f"Setup: {orientation}, {size[0]} × {size[1]}" if size else f"Setup: {orientation}"
    return context


def defaults_for(source: str, kit: Path):
    if source == "kit:wireframes":
        folder = kit / "preview" / "wireframes"
        files = sorted(folder.glob("*.png")) if folder.exists() else []
        return [{"path": p.relative_to(kit).as_posix(), "name": p.name, "screen": screen_label(kit, screen_of(p.stem)),
                 "note": ""} for p in files]
    raise SystemExit(f"Unknown default_from: {source}")


def load_form(name: str, kit: Path) -> dict:
    path = FORMS / f"{name}.json"
    if not path.exists():
        raise SystemExit(f"No form {name}. Forms: {sorted(p.stem for p in FORMS.glob('*.json'))}")
    form = read_json(path)
    if name in ("setup", "wireframe", "mockup", "full"):
        form["description_suggestions"] = read_json(FORM_SUGGESTIONS, {})
        form["personal_suggestions"] = personal_suggestions(name, kit, form["description_suggestions"])
    for question in form["questions"]:
        if "options_from" in question:
            source = question.pop("options_from")
            try:
                question["options"] = question.get("options", []) + options_for(source, kit)
            except (OSError, ValueError, subprocess.TimeoutExpired):
                if source != "host:photoshop":
                    raise
                question["options"] = []
                question["hint"] = "Không đọc được danh sách Photoshop. Nhập đường dẫn Photoshop.exe ở lựa chọn bên dưới."
            if source == "host:photoshop" and not question["options"]:
                question["hint"] += " Chưa tìm thấy bản Photoshop nào; nếu chưa cài, bỏ các mục PSD và chọn Bộ UI kit và ảnh demo (PNG) hoặc JSON Unity."
        for field in question.get("file_fields") or []:
            if "suggestions_from" in field:
                field["suggestions"] = [o["label"] for o in options_for(field.pop("suggestions_from"), kit)]
    if name == "revise" and PREVIEW["kind"] == "concepts":
        versions = next(q for q in form["questions"] if q["id"] == "versions")
        versions.update(title="Bạn muốn chỉnh gì ở concept này?", hint="Ghi rõ phần cần đổi. Có thể đính kèm ảnh minh họa.")
        form.update(title="Sửa concept", intro="Bấm Hoàn thành để tạo bản chỉnh sửa và xem lại trước khi chốt.",
                    questions=[versions])
    if name == "export" and not kit_layouts(kit):
        source = next(q for q in form["questions"] if q["id"] == "source")
        source["options"] = [o for o in source["options"] if o["value"] != "existing"]
    return form


# ---------- answers ----------

def answer_paths(kit: Path) -> list[Path]:
    briefs = kit / "briefs"
    return sorted(briefs.rglob("*.json")) if briefs.exists() else []


def remember_kit(kit: Path) -> None:
    """Index a kit after submission. The descriptions stay in its briefs."""
    try:
        FORM_HISTORY.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(FORM_HISTORY, timeout=0.5)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS kits (path TEXT PRIMARY KEY, used_at INTEGER NOT NULL)")
            db.execute("INSERT INTO kits VALUES (?, ?) ON CONFLICT(path) DO UPDATE SET used_at = excluded.used_at",
                       (str(kit.resolve()), time.time_ns()))
    except (OSError, sqlite3.Error):
        return


def history_kits(kit: Path) -> list[Path]:
    previous = []
    if FORM_HISTORY.is_file():
        try:
            with closing(sqlite3.connect(FORM_HISTORY, timeout=0.5)) as db:
                previous = [Path(path) for path, in db.execute("SELECT path FROM kits ORDER BY used_at DESC LIMIT 30")]
        except sqlite3.Error:
            pass
    return list(dict.fromkeys([kit.resolve(), *previous]))


def brief_descriptions(brief: dict):
    """Yield a suggestion source, context, area and text from a submitted brief."""
    answers = brief.get("answers") or {}
    kind = brief.get("form")
    if kind == "setup" and brief.get("game_type"):
        for text in (brief.get("gameplay"), brief.get("game_type_description")):
            yield "game_types", slug(brief["game_type"]), "", text
    if kind == "wireframe" and brief.get("screen"):
        screen = brief["screen"]
        yield "screens", screen, "", (answers.get("function") or {}).get("value")
        areas = (answers.get("areas") or {}).get("value") or {}
        for area, text in areas.items():
            yield "screens", screen, area, text
    if kind in ("mockup", "full"):
        for screen in brief.get("screens") or []:
            if screen.get("screen"):
                yield "screens", screen["screen"], "", screen.get("note")
    if kind == "mockup":
        style = (answers.get("ui_style") or {}).get("value") or {}
        style_name = style.get("label") if style.get("choice") == "other" else style.get("choice")
        context = slug(style_name) if style_name else ""
        for text in ((answers.get("style_note") or {}).get("value"), brief.get("ui_style_description")):
            yield "art_styles", context, "", text


def normalized_note(text: str) -> str:
    return " ".join(text.casefold().split())


def personal_suggestions(form: str, kit: Path, catalog: dict) -> dict:
    setup_path = Path("briefs/setup.json")
    current_genre = (read_json(kit / setup_path) or {}).get("game_type")
    if form != "setup" and not current_genre:
        return {}
    stock = {normalized_note(item["text"]) for group in ("game_types", "art_styles") for item in catalog.get(group, [])}
    for screen in catalog.get("screens", []):
        for region in screen["regions"]:
            stock.update((normalized_note(region["text"]), normalized_note(f"{region['label']}: {region['text']}")))

    groups = defaultdict(dict)
    for previous in history_kits(kit):
        setup = read_json(previous / setup_path) or {}
        genre = setup.get("game_type")
        if not genre or (form != "setup" and slug(genre) != slug(current_genre)):
            continue
        if form == "setup":
            briefs = [setup]
        else:
            briefs = [read_json(path) or {} for folder in ("wireframe", "mockup")
                      for path in (previous / "briefs" / folder).glob("*.json")]
        for brief in briefs:
            if not brief.get("submitted"):
                continue
            for source, context, area, value in brief_descriptions(brief):
                if not isinstance(value, str):
                    continue
                text = re.sub(r"https?://\S+", "", value).strip()
                key = normalized_note(text)
                if not key or key in stock or all(normalized_note(line) in stock for line in text.splitlines() if line.strip()):
                    continue
                examples = groups[source, context, area]
                entry = examples.setdefault(key, {"text": text, "kits": set(), "latest": ""})
                entry["kits"].add(previous)
                entry["latest"] = max(entry["latest"], brief["submitted"])

    result = {}
    for (source, context, area), examples in groups.items():
        ranked = sorted(examples.values(), key=lambda item: (len(item["kits"]), item["latest"]), reverse=True)
        result.setdefault(source, {}).setdefault(context, {})[area] = [
            {"label": f"Mẫu bạn đã dùng · {len(item['kits'])} bộ UI", "text": item["text"]}
            for item in ranked[:4]
        ]
    return result


def referenced_files(value, found: set[str]) -> None:
    if isinstance(value, dict):
        path = value.get("path")
        if isinstance(path, str):
            found.add(path.replace("\\", "/"))
        for item in value.values():
            referenced_files(item, found)
    elif isinstance(value, list):
        for item in value:
            referenced_files(item, found)


def clean_inputs(kit: Path) -> int:
    """Delete files in inputs/ that no answer file refers to, and empty folders."""
    inputs = kit / "inputs"
    if not inputs.exists():
        return 0
    used: set[str] = set()
    for path in answer_paths(kit):
        referenced_files(read_json(path, {}), used)
    removed = 0
    for path in sorted(inputs.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        rel = path.relative_to(kit).as_posix()
        if path.is_file() and rel not in used:
            path.unlink()
            removed += 1
        elif path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    if inputs.exists() and not any(inputs.iterdir()):
        inputs.rmdir()
    return removed


def apply_answers(form_id: str, kit: Path, answers: dict) -> dict:
    """Derive the fields the skill needs from the raw answers."""
    record = {"form": form_id, "submitted": datetime.now(timezone.utc).isoformat(timespec="seconds"), "answers": answers}
    if form_id == "setup":
        choice = (answers.get("orientation") or {}).get("value") or {}
        if choice.get("choice") == "custom":
            fields = choice.get("fields") or {}
            width, height = int(fields.get("width") or 0), int(fields.get("height") or 0)
            if width < 64 or height < 64:
                raise ValueError("Kích thước phải từ 64 px trở lên.")
            orientation = "portrait" if height > width else "landscape"
        elif choice.get("choice") == "landscape":
            width, height, orientation = 1920, 1080, "landscape"
        else:
            width, height, orientation = 1080, 1920, "portrait"
        record["size"], record["orientation"] = [width, height], orientation
        game = (answers.get("game_type") or {}).get("value") or {}
        record["game_type"] = game.get("label")
        if game.get("choice") == "other" and (game.get("note") or "").strip():
            record["game_type_description"] = game["note"].strip()
        record["gameplay"] = (answers.get("gameplay") or {}).get("value")
    if form_id == "wireframe":
        screen = (answers.get("screen") or {}).get("value") or {}
        record["screen"] = screen.get("choice") if screen.get("choice") != "other" else slug(screen.get("label"))
        record["screen_label"] = screen.get("label")
    if form_id in ("wireframe", "mockup"):
        record["options"] = int((answers.get("options") or {}).get("value") or 1)
    if form_id == "mockup":
        kit_choice = (answers.get("kit") or {}).get("value") or {}
        if kit_choice.get("choice") == "no":
            concept = (answers.get("concept_count") or {}).get("value") or {}
            count = concept.get("choice")
            if count not in ("1", "2", "3"):
                raise ValueError("Chọn từ 1 đến 3 lượt tạo ảnh concept.")
            record["concept_count"] = int(count)
        # One screen per wireframe file. A blank name is for Codex to guess from the image.
        record["screens"] = [{"screen": slug(f.get("screen")) if (f.get("screen") or "").strip() else "",
                              "label": (f.get("screen") or "").strip(), "note": (f.get("note") or "").strip(),
                              "file": f.get("path")}
                             for f in (answers.get("wireframe") or {}).get("value") or []]
        style = (answers.get("ui_style") or {}).get("value") or {}
        if style.get("choice") == "other" and (style.get("note") or "").strip():
            record["ui_style_description"] = style["note"].strip()
    if form_id == "revise":
        record["kind"] = PREVIEW["kind"]
        versions = [{"layout": e["choice"], "label": e.get("label"), "change": (e.get("note") or "").strip(),
                     "files": e.get("files", [])} for e in (answers.get("versions") or {}).get("value") or []]
        if record["kind"] == "concepts":
            if len(versions) != 1 or versions[0]["layout"] not in PREVIEW["screens"] or not versions[0]["change"]:
                raise ValueError("Ghi rõ phần cần sửa ở concept đang xem.")
        record["versions"] = versions
    if form_id == "wireframe":
        record["prototype"] = ((answers.get("prototype") or {}).get("value") or {}).get("choice") == "yes"
    if form_id == "full":
        record["screens"] = [{"screen": e["choice"] if e["choice"] != "other" else slug(e.get("label")),
                              "label": e.get("label"), "note": e.get("note", ""), "files": e.get("files", [])}
                             for e in (answers.get("screens") or {}).get("value") or []]
    if form_id == "export":
        record["formats"] = [e["choice"] for e in (answers.get("format") or {}).get("value") or []]
        formats = set(record["formats"])
        if not formats or formats - {"ui_kit", "components_psd", "screen_psd", "unity", "zip"}:
            raise ValueError("Chọn ít nhất một loại file trong danh sách export.")
        if formats == {"zip"}:
            raise ValueError("Chọn thêm ít nhất một loại file để đóng gói ZIP.")
        source = ((answers.get("source") or {}).get("value") or {}).get("choice")
        record["source"] = source
        if source == "existing":
            record["layouts"] = [e["choice"] for e in (answers.get("layouts") or {}).get("value") or []]
            if not record["layouts"] or set(record["layouts"]) - set(kit_layouts(kit)):
                raise ValueError("Chọn màn có trong kit, hoặc dùng ảnh mockup có sẵn.")
        elif source == "provided":
            files = (answers.get("screens") or {}).get("value") or []
            if not files:
                raise ValueError("Thêm ít nhất một ảnh mockup để export.")
            sources = []
            for file in files:
                path = (kit / file["path"]).resolve()
                if not path.is_relative_to(kit.resolve()) or not path.is_file() or path.suffix.lower() not in FROM_ZIP:
                    raise ValueError("Ảnh mockup phải là file PNG, JPG, WebP hoặc PSD đã thêm vào kit.")
                sources.append({"file": file["path"], "name": file.get("name", path.name),
                                "screen": slug(file["screen"]) if (file.get("screen") or "").strip() else "",
                                "label": (file.get("screen") or "").strip(), "note": file.get("note", "")})
            record.update(sources=sources, layouts=[])
        else:
            raise ValueError("Chọn nguồn ảnh mockup hoặc các màn đã làm trong kit.")
        if formats & {"components_psd", "screen_psd"}:
            choice = (answers.get("photoshop") or {}).get("value") or {}
            path = choice.get("label") if choice.get("choice") == "other" else choice.get("choice")
            if not path:
                raise ValueError("Chọn một bản Photoshop để tạo PSD trước khi hoàn thành.")
            record["photoshop"] = inspect_photoshop(path.strip().strip('"'))
        background = ((answers.get("background") or {}).get("value") or {}).get("choice")
        if formats & {"components_psd", "screen_psd"}:
            if background not in ("image", "redraw"):
                raise ValueError("Chọn cách xử lý background trong PSD.")
            record["background"] = background
    return record


# ---------- uploads ----------

def store_upload(kit: Path, form_id: str, where: str, name: str, data: bytes) -> list[dict]:
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED:
        raise ValueError(f"Chỉ nhận {', '.join(sorted(ALLOWED))}")
    parts = [slug(p) for p in where.split("/") if p.strip()] or ["files"]
    folder = kit / "inputs" / slug(form_id) / Path(*parts)
    digest = hashlib.sha256(data).hexdigest()[:10]
    stem = slug(Path(name).stem)
    folder.mkdir(parents=True, exist_ok=True)
    if ext != ".zip":
        same = sorted(folder.glob(f"{digest}_*{ext}"))
        target = same[0] if same else folder / f"{digest}_{stem}{ext}"
        if not target.exists():
            target.write_bytes(data)
        return [{"path": target.relative_to(kit).as_posix(), "name": name}]
    out = folder / f"{digest}_{stem}"
    files = []
    import io
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        members = [m for m in archive.infolist() if not m.is_dir() and Path(m.filename).suffix.lower() in FROM_ZIP
                   and not Path(m.filename).name.startswith(".") and "__MACOSX" not in m.filename]
        if len(members) > MAX_MEMBERS or sum(m.file_size for m in members) > MAX_UNZIPPED:
            raise ValueError("File ZIP quá lớn.")
        for member in members:
            rel = [slug(Path(p).stem) if i == len(Path(member.filename).parts) - 1 else slug(p)
                   for i, p in enumerate(Path(member.filename).parts)]
            target = out.joinpath(*rel[:-1], rel[-1] + Path(member.filename).suffix.lower())
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                target.write_bytes(archive.read(member))
            files.append({"path": target.relative_to(kit).as_posix(), "name": member.filename})
    if not files:
        raise ValueError("File ZIP không có ảnh hoặc PSD nào.")
    return files


# ---------- server ----------

class FormServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, kit: Path, form: dict, out: Path, prefill: dict):
        super().__init__(("127.0.0.1", 0), Handler)
        self.kit, self.form, self.out, self.prefill = kit, form, out, prefill
        self.result = None
        self.done = threading.Event()


class Handler(BaseHTTPRequestHandler):
    server: FormServer

    def log_message(self, *args):
        pass

    def send(self, code: int, body: bytes, kind: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, code: int, data) -> None:
        self.send(code, json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        url = urlparse(self.path)
        if url.path in ("/", "/index.html"):
            self.send(200, (FORMS / "form.html").read_bytes(), "text/html; charset=utf-8")
        elif url.path == "/spec":
            self.send_json(200, {"form": self.server.form, "context": build_context(self.server.kit),
                                 "prefill": self.server.prefill})
        elif url.path == "/kitfile":
            rel = (parse_qs(url.query).get("p") or [""])[0]
            kit = self.server.kit.resolve()
            path = (kit / rel).resolve()
            if kit not in path.parents or path.suffix.lower() not in SERVE_TYPES or not path.is_file():
                self.send_json(404, {"error": "not found"})
                return
            self.send(200, path.read_bytes(), SERVE_TYPES[path.suffix.lower()])
        else:
            self.send_json(404, {"error": "not found"})

    def do_POST(self):
        url = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_FILE:
            self.send_json(413, {"error": "File quá lớn (tối đa 300 MB)."})
            return
        data = self.rfile.read(length)
        try:
            if url.path == "/upload":
                query = parse_qs(url.query)
                files = store_upload(self.server.kit, self.server.form["id"], (query.get("where") or ["files"])[0],
                                     (query.get("name") or ["file"])[0], data)
                self.send_json(200, {"files": files})
            elif url.path == "/submit":
                if self.server.done.is_set():
                    self.send_json(409, {"error": "Form này đã được gửi."})
                    return
                answers = json.loads(data.decode("utf-8"))["answers"]
                record = apply_answers(self.server.form["id"], self.server.kit, answers)
                self.server.out.parent.mkdir(parents=True, exist_ok=True)
                self.server.out.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
                if "description_suggestions" in self.server.form:
                    remember_kit(self.server.kit)
                self.server.result = record
                self.send_json(200, {"ok": True})
                self.server.done.set()
            else:
                self.send_json(404, {"error": "not found"})
        except (ValueError, KeyError, zipfile.BadZipFile) as exc:
            self.send_json(400, {"error": str(exc)})


def wait_file(kit: Path) -> Path:
    return kit / ".gui" / "ask.json"


def serve(args, kit: Path) -> int:
    form = load_form(args.form, kit)
    out = kit / args.out
    old = read_json(out, {}) or {}
    prefill = old.get("answers") or {}
    if args.form == "export":
        prefill.pop("photoshop", None)  # require an explicit choice on every export, even for one install
        source = "existing" if kit_layouts(kit) else "provided"
        prefill.setdefault("source", {"value": {"choice": source}})
        if not kit_layouts(kit):
            prefill["source"] = {"value": {"choice": "provided"}}
        # Old saved choices are migrated into the new, reviewable multi-select form.
        aliases = {"psd": "screen_psd", "png": "ui_kit"}
        choices = next(q for q in form["questions"] if q["id"] == "format")["options"]
        labels = {o["value"]: o["label"] for o in choices}
        for entry in (prefill.get("format") or {}).get("value") or []:
            entry["choice"] = aliases.get(entry.get("choice"), entry.get("choice"))
            if entry["choice"] in labels:
                entry["label"] = labels[entry["choice"]]
    if args.form == "revise" and args.kind == "concepts":
        draft = form["questions"][0]["options"][0]
        prefill.setdefault("versions", {"value": [{"choice": draft["value"], "label": draft["label"]}]})
    for question in form["questions"]:
        if question.get("default_from") and question["id"] not in prefill:
            files = defaults_for(question["default_from"], kit)
            if files:
                prefill[question["id"]] = {"value": files}
    server = FormServer(kit, form, out, prefill)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    state = wait_file(kit)
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps({"url": url, "out": args.out, "pid": os.getpid(), "started": time.time()}), encoding="utf-8")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"FORM_URL {url}", flush=True)
    if not args.no_browser:
        try:
            webbrowser.open_new_tab(url)
        except Exception:
            pass
    try:
        finished = server.done.wait(args.timeout)
        time.sleep(0.3)
    except KeyboardInterrupt:
        finished = False
    server.shutdown()
    removed = clean_inputs(kit)
    if args.child:
        info = read_json(state, {}) or {}
        if info.get("pid") != os.getpid():  # a newer form owns the state now
            return 0
        info.update({"finished": True, "submitted": bool(finished), "removed_unused_files": removed})
        state.write_text(json.dumps(info), encoding="utf-8")
    else:
        try:
            state.unlink()
        except OSError:
            pass
    if not finished:
        print(json.dumps({"status": "TIMEOUT", "message": "No answer before the timeout. Nothing was saved.",
                          "removed_unused_files": removed}, ensure_ascii=False), flush=True)
        return 4
    print(json.dumps({"status": "SUBMITTED", "out": args.out, "removed_unused_files": removed,
                      "record": server.result}, ensure_ascii=False), flush=True)
    return 0


def start_detached(args, kit: Path) -> int:
    """Start the form server in the background and return once its URL is known."""
    state = wait_file(kit)
    old = read_json(state)
    if old and not old.get("finished") and old.get("pid"):
        try:  # close a form left open, so it cannot overwrite this one's state
            os.kill(int(old["pid"]), 15)
        except (OSError, ValueError):
            pass
    if state.exists():
        state.unlink()
    command = [sys.executable, str(Path(__file__).resolve()), args.form, str(kit), "--out", args.out,
               "--timeout", str(args.keep), "--child", "--kind", args.kind] + (["--no-browser"] if args.no_browser else [])
    if args.screens:
        command += ["--screens", args.screens]
    options = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.name == "nt":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        try:
            subprocess.Popen(command, creationflags=flags | 0x01000000, **options)  # CREATE_BREAKAWAY_FROM_JOB
        except OSError:
            subprocess.Popen(command, creationflags=flags, **options)
    else:
        subprocess.Popen(command, start_new_session=True, **options)
    for _ in range(150):
        info = read_json(state)
        if info:
            print(f"FORM_URL {info['url']}", flush=True)
            return 0
        time.sleep(0.1)
    print("The form server did not start.", file=sys.stderr)
    return 1


def wait_answers(args, kit: Path) -> int:
    state = wait_file(kit)
    info = read_json(state)
    if not info:
        print(json.dumps({"status": "NO_FORM", "message": "No form is open for this kit."}))
        return 1
    out = kit / info["out"]
    deadline = time.time() + args.timeout
    next_note = time.time() + 60
    while not info.get("finished") and time.time() < deadline:
        time.sleep(1)
        info = read_json(state, info) or info
        if time.time() >= next_note:
            print("still waiting for the form", flush=True)
            next_note = time.time() + 60
    if not info.get("finished"):
        print(json.dumps({"status": "WAITING", "url": info.get("url"),
                          "message": "The form is still open. Run ask.py <kit> --wait again; do not end the turn."}))
        return 4
    state.unlink()
    if not info.get("submitted"):
        print(json.dumps({"status": "TIMEOUT", "message": "The form closed without an answer. Nothing was saved."}))
        return 4
    print(json.dumps({"status": "SUBMITTED", "out": info["out"], "removed_unused_files": info.get("removed_unused_files", 0),
                      "record": read_json(out)}, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("form", nargs="?", help="setup, wireframe, full, mockup, revise or export")
    parser.add_argument("kit", help="Kit folder, such as ui_art/<kit>")
    parser.add_argument("--out", help="Answer file, relative to the kit, under briefs/")
    parser.add_argument("--timeout", type=int, default=1800, help="Seconds this command waits for the answer")
    parser.add_argument("--keep", type=int, default=86400, help="Seconds the form stays open")
    parser.add_argument("--no-browser", action="store_true", help="Only print the URL")
    parser.add_argument("--kind", choices=["wireframes", "mockups", "concepts"], default="mockups",
                        help="revise form: which images to offer")
    parser.add_argument("--screens", default="", help="Comma-separated screens to offer, or one concept image stem")
    parser.add_argument("--detach", action="store_true", help="Open the form and return at once, without waiting")
    parser.add_argument("--foreground", action="store_true", help="Serve in this process, for testing")
    parser.add_argument("--wait", action="store_true", help="Wait for the form started with --detach")
    parser.add_argument("--clean", action="store_true", help="Only delete unused files in inputs/")
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    kit = Path(args.kit)
    PREVIEW.update(kind=args.kind, screens=[s.strip() for s in args.screens.split(",") if s.strip()])
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.clean:
        print(json.dumps({"removed_unused_files": clean_inputs(kit)}))
        return 0
    if args.wait:
        return wait_answers(args, kit)
    if not args.form or not args.out:
        parser.error("form and --out are required")
    if not args.out.replace("\\", "/").startswith("briefs/"):
        parser.error("--out must be under briefs/")
    if args.kind == "concepts" and (args.form != "revise" or len(PREVIEW["screens"]) != 1
                                   or not kit_previews(kit, args.kind, PREVIEW["screens"])):
        parser.error("--kind concepts requires the revise form and one existing concept image stem in --screens")
    kit.mkdir(parents=True, exist_ok=True)
    if args.foreground or args.child:
        return serve(args, kit)
    started = start_detached(args, kit)
    if started or args.detach:
        return started
    return wait_answers(args, kit)


if __name__ == "__main__":
    raise SystemExit(main())
