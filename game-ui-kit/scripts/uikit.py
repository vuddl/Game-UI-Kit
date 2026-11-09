#!/usr/bin/env python3
"""Turn UI sheets and loose sprites into a named kit with 9-slice data and checks.

Commands: slice, import, backdrop, shapes, nineslice, states, palette, fonts, compare, wireframe, mockup, choose, confirm, flow,
export, psd, vectorize, unity, resize-layout, device, spec, info, qa.
Run any of them with --help.
Exit codes: 0 ok, 1 usage or input error, 2 result needs a fix (see output).
"""
from __future__ import annotations

import argparse
import base64
import fnmatch
import hashlib
import html
import io
import json
import re
import shutil
import struct
import subprocess
import sys
import unicodedata
import urllib.request
from pathlib import Path

try:
    import numpy as np
    from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageFilter, ImageFont
except ImportError as exc:
    sys.exit(f"Missing dependency: {exc.name}. Install with: py -3 -m pip install pillow numpy")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import psd_recipe as recipes  # noqa: E402

NAME_RE = re.compile(r"^[a-z0-9_]+(/[a-z0-9_]+)*$")
STATE_RE = re.compile(r"_(normal|hover|pressed|selected|disabled|locked)$")
ALPHA_FLOOR = 8
PAD = 2


def die(code: str, message: str, status: int = 2):
    print(f"{code}: {message}", file=sys.stderr)
    raise SystemExit(status)


def load_manifest(kit: Path) -> dict:
    path = kit / "manifest.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"elements": {}}


def save_manifest(kit: Path, manifest: dict) -> None:
    manifest["elements"] = dict(sorted(manifest["elements"].items()))
    (kit / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def to_hex(color) -> str:
    return "#%02X%02X%02X" % tuple(int(c) for c in color)


def from_hex(value: str) -> np.ndarray:
    return np.array([int(value[i:i + 2], 16) for i in (1, 3, 5)], dtype=float)


def checker(w: int, h: int, size: int = 10) -> Image.Image:
    y, x = np.indices((h, w))
    tile = ((x // size + y // size) % 2) * 28 + 212
    return Image.fromarray(np.dstack([tile] * 3).astype(np.uint8), "RGB").convert("RGBA")


def on_checker(img: Image.Image) -> Image.Image:
    bg = checker(*img.size)
    bg.alpha_composite(img)
    return bg


def extract_alpha(path: Path, tolerance: int, ramp: int):
    """Return (RGBA float array, key color or None), using real alpha or a flat key."""
    rgba = np.asarray(Image.open(path).convert("RGBA")).astype(float)
    if (rgba[..., 3] < 16).mean() > 0.02:
        rgba[rgba[..., 3] < ALPHA_FLOOR] = 0
        return rgba, None

    rgb = rgba[..., :3]
    edge = np.concatenate([rgb[:4].reshape(-1, 3), rgb[-4:].reshape(-1, 3),
                           rgb[:, :4].reshape(-1, 3), rgb[:, -4:].reshape(-1, 3)])
    # Use the most common color, since a median falls between the two tones of a fake checkerboard.
    bins, counts = np.unique((edge // 16).astype(int), axis=0, return_counts=True)
    dominant = bins[counts.argmax()] * 16 + 8
    key = np.median(edge[np.abs(edge - dominant).max(axis=1) <= 24], axis=0)
    flat_share = (np.abs(edge - key).max(axis=1) <= 20).mean()
    if flat_share < 0.9:
        die("BACKGROUND_NOT_FLAT",
            f"{path.name}: no transparency and only {flat_share:.0%} of the border matches one "
            "color. Regenerate on a flat key color.")

    dist = np.abs(rgb - key).max(axis=2)
    alpha = np.clip((dist - tolerance) / ramp, 0, 1)
    # Remove the key color mixed into soft edge pixels.
    soft = (alpha > 0.03) & (alpha < 1)
    source = rgb.copy()
    rgb[soft] = np.clip((rgb[soft] - (1 - alpha[soft, None]) * key) / alpha[soft, None], 0, 255)
    clean_edges(source, rgb, alpha, dist, key)
    rgba[..., 3] = alpha * 255
    rgba[alpha <= 0.03] = 0
    return rgba, key


def clean_edges(source: np.ndarray, rgb: np.ndarray, alpha: np.ndarray, dist: np.ndarray,
                key: np.ndarray, radius: int = 2) -> None:
    """Unmix pixels next to the background against their purest neighbor, in place.

    A dark outline blended with a bright key is far from the key color, so distance alone
    leaves it opaque and tinted. The neighbor furthest from the key is the unblended color,
    which also keeps outlines only a pixel or two wide, unlike sampling the solid interior.
    """
    background = Image.fromarray(((alpha <= 0.03) * 255).astype(np.uint8))
    near = background.filter(ImageFilter.MaxFilter(radius * 2 + 1))
    edge = (np.asarray(near) > 0) & (alpha > 0.03)

    best, pure = dist.copy(), source.copy()
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dy or dx:
                shifted = np.roll(dist, (dy, dx), axis=(0, 1))
                better = shifted > best
                best[better] = shifted[better]
                pure[better] = np.roll(source, (dy, dx), axis=(0, 1))[better]

    direction = pure - key
    length = (direction ** 2).sum(axis=2)
    amount = ((source - key) * direction).sum(axis=2) / np.maximum(length, 1)
    usable = edge & (length > 1600)
    alpha[usable] = np.clip(amount[usable], 0, 1)
    mixed = usable & (alpha < 0.98)
    rgb[mixed] = pure[mixed]
    opaque = usable & ~mixed
    rgb[opaque] = source[opaque]


def label_regions(mask: np.ndarray, gap: int):
    """Label 8-connected regions on a grid of gap-sized cells, so near parts stay together."""
    h, w = mask.shape
    rows, cols = np.arange(0, h, gap), np.arange(0, w, gap)
    grid = np.logical_or.reduceat(np.logical_or.reduceat(mask, rows, axis=0), cols, axis=1)
    labels = np.zeros(grid.shape, dtype=np.int32)
    count = 0
    gh, gw = grid.shape
    for sy, sx in zip(*np.nonzero(grid)):
        if labels[sy, sx]:
            continue
        count += 1
        labels[sy, sx] = count
        stack = [(sy, sx)]
        while stack:
            y, x = stack.pop()
            for ny in range(max(y - 1, 0), min(y + 2, gh)):
                for nx in range(max(x - 1, 0), min(x + 2, gw)):
                    if grid[ny, nx] and not labels[ny, nx]:
                        labels[ny, nx] = count
                        stack.append((ny, nx))
    full = np.repeat(np.repeat(labels, gap, axis=0), gap, axis=1)[:h, :w]
    return full, count


def reading_order(boxes: list[dict]) -> list[dict]:
    """Sort boxes into rows by vertical overlap, then left to right."""
    ordered, row, band = [], [], None
    for box in sorted(boxes, key=lambda b: (b["y0"] + b["y1"]) / 2):
        center = (box["y0"] + box["y1"]) / 2
        if band and not band[0] <= center <= band[1]:
            ordered += sorted(row, key=lambda b: b["x0"])
            row, band = [], None
        if band is None:
            band = (box["y0"], box["y1"])
        row.append(box)
    return ordered + sorted(row, key=lambda b: b["x0"])


def read_names(path: Path) -> list[str] | None:
    if not path.exists():
        return None
    lines = (line.strip() for line in path.read_text(encoding="utf-8").splitlines())
    names = [line for line in lines if line and not line.startswith("#")]
    bad = [n for n in names if not NAME_RE.match(n)]
    if bad:
        die("BAD_NAME", f"{path.name}: use lowercase letters, digits, _ and /: {bad}", 1)
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        die("DUPLICATE_NAME", f"{path.name}: {dupes}", 1)
    return names


def write_labeled(kit: Path, sheet: Path, rgba: np.ndarray, boxes: list[dict]) -> Path:
    img = on_checker(Image.fromarray(rgba.astype(np.uint8), "RGBA"))
    draw = ImageDraw.Draw(img)
    for number, box in enumerate(boxes, 1):
        draw.rectangle([box["x0"], box["y0"], box["x1"], box["y1"]], outline=(255, 0, 0, 255), width=2)
        draw.text((box["x0"] + 4, box["y0"] + 4), str(number), fill=(255, 0, 0, 255), stroke_width=2,
                  stroke_fill=(255, 255, 255, 255), font_size=20)
    out = kit / "preview" / f"{sheet.stem}_labeled.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out)
    return out


def cmd_slice(args) -> int:
    kit, sheet = Path(args.kit), Path(args.sheet)
    if not sheet.is_absolute() and not sheet.exists():
        sheet = kit / sheet
    if not sheet.exists():
        die("NOT_FOUND", str(sheet), 1)

    rgba, key = extract_alpha(sheet, args.tolerance, args.ramp)
    mask = rgba[..., 3] >= ALPHA_FLOOR
    if not mask.any():
        die("EMPTY_SHEET", f"{sheet.name}: nothing left after removing the background.")
    labels, count = label_regions(mask, args.gap)

    boxes, dropped = [], 0
    for index in range(1, count + 1):
        region = mask & (labels == index)
        area = int(region.sum())
        if area < args.min_area:
            dropped += 1
            continue
        ys, xs = np.nonzero(region)
        boxes.append({"index": index, "area": area, "x0": int(xs.min()), "y0": int(ys.min()),
                      "x1": int(xs.max()), "y1": int(ys.max())})
    boxes = reading_order(boxes)
    labeled = write_labeled(kit, sheet, rgba, boxes)

    names_file = Path(args.names) if args.names else sheet.with_suffix(".txt")
    names = read_names(names_file)
    if names is None:
        die("NO_NAMES", f"found {len(boxes)} elements. Write {names_file} using {labeled}.")
    if len(names) != len(boxes):
        die("COUNT_MISMATCH", f"{sheet.name}: found {len(boxes)} elements but {len(names)} names. "
            f"See {labeled}.")

    targets = [kit / "elements" / f"{name}.png" for name in names]
    existing = [str(t) for t in targets if t.exists()]
    if existing and not args.force:
        die("EXISTS", f"{existing} already exist. Pass --force only if replacing them was requested.", 1)

    manifest = load_manifest(kit)
    h, w = mask.shape
    for name, box, target in zip(names, boxes, targets):
        x0, y0, x1, y1 = box["x0"], box["y0"], box["x1"], box["y1"]
        crop = rgba[y0:y1 + 1, x0:x1 + 1].copy()
        crop[labels[y0:y1 + 1, x0:x1 + 1] != box["index"]] = 0
        padded = np.zeros((crop.shape[0] + PAD * 2, crop.shape[1] + PAD * 2, 4))
        padded[PAD:-PAD, PAD:-PAD] = crop
        target.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(padded.astype(np.uint8), "RGBA").save(target)
        manifest["elements"][name] = {
            "file": target.relative_to(kit).as_posix(),
            "width": padded.shape[1], "height": padded.shape[0],
            "sheet": sheet.name, "sheet_box": [x0, y0, x1, y1],
            "key_color": None if key is None else to_hex(key),
            "touches_sheet_edge": x0 == 0 or y0 == 0 or x1 == w - 1 or y1 == h - 1,
            "nine_slice": None,
        }
    save_manifest(kit, manifest)
    source = "real alpha" if key is None else f"key {to_hex(key)}"
    print(f"{sheet.name}: wrote {len(names)} elements ({source}), ignored {dropped} specks.")
    return 0


def normalize_name(relative: Path) -> str:
    """Turn a relative file path into a valid element name, keeping folders."""
    parts = []
    for part in relative.with_suffix("").parts:
        text = unicodedata.normalize("NFKD", part.replace("đ", "d").replace("Đ", "D"))
        text = "".join(c for c in text if not unicodedata.combining(c)).lower()
        text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
        if text:
            parts.append(text)
    return "/".join(parts)


def read_import_map(path: Path, source: Path) -> list[tuple[Path, str]]:
    pairs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            die("BAD_MAP", f"expected 'file = element/name', got: {line}", 1)
        rel, name = (part.strip() for part in line.split("=", 1))
        if not NAME_RE.match(name):
            die("BAD_NAME", f"use lowercase letters, digits, _ and /: {name}", 1)
        pairs.append((source / rel, name))
    return pairs


def cmd_import(args) -> int:
    kit, source = Path(args.kit), Path(args.source)
    if not source.exists():
        die("NOT_FOUND", str(source), 1)
    root = source if source.is_dir() else source.parent
    other = 0
    if args.map:
        pairs = read_import_map(Path(args.map), root)
    else:
        files = sorted(p for p in (source.rglob("*") if source.is_dir() else [source]) if p.is_file())
        kit_root = kit.resolve()
        files = [p for p in files if not p.resolve().is_relative_to(kit_root)]
        images = [p for p in files if p.suffix.lower() in (".png", ".webp")]
        other = len([p for p in files if p.suffix.lower() in (".jpg", ".jpeg", ".psd", ".tga", ".bmp")])
        prefix = f"{args.prefix.strip('/')}/" if args.prefix else ""
        pairs = [(p, prefix + normalize_name(p.relative_to(root))) for p in images]
    if not pairs:
        die("NO_IMAGES", f"no PNG or WebP files in {source}", 1)

    bad = [n for _, n in pairs if not NAME_RE.match(n)]
    if bad:
        die("BAD_NAME", f"cannot build valid names for {bad}. Use --map.", 1)
    seen: dict[str, Path] = {}
    for path, name in pairs:
        if name in seen:
            die("NAME_COLLISION", f"{seen[name].name} and {path.name} both become {name}. Use --map.", 1)
        seen[name] = path

    manifest = load_manifest(kit)
    loaded = []
    for path, name in pairs:
        target = kit / "elements" / f"{name}.png"
        if (target.exists() or name in manifest["elements"]) and not args.force:
            die("EXISTS", f"{name} already exists. Pass --force only if replacing it was requested.", 1)
        try:
            with Image.open(path) as img:
                img.load()
                loaded.append((path, name, target, img.size, img.convert("RGBA").getextrema()[3][0] < 250))
        except OSError as exc:
            die("BAD_IMAGE", f"{path}: {exc}", 1)

    for path, name, target, size, transparent in loaded:
        target.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() == ".png":
            shutil.copyfile(path, target)
        else:
            Image.open(path).convert("RGBA").save(target)
        manifest["elements"][name] = {
            "file": target.relative_to(kit).as_posix(), "width": size[0], "height": size[1],
            "imported_from": path.name, "has_transparency": transparent,
            "key_color": None, "touches_sheet_edge": False, "nine_slice": None,
        }
    save_manifest(kit, manifest)
    opaque = sum(1 for item in loaded if not item[4])
    print(f"Imported {len(loaded)} elements, {opaque} without transparency, "
          f"skipped {other} files in other image formats.")
    return 0


def rgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """Convert sRGB values from 0 to 255 into CIE Lab, so distances follow perceived color."""
    c = rgb / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    xyz = c @ np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]]).T
    t = xyz / np.array([0.9505, 1.0, 1.089])
    f = np.where(t > 0.008856, np.cbrt(t), 7.787 * t + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], axis=-1)


def visible_pixels(path: Path, limit: int = 256) -> np.ndarray:
    img = Image.open(path).convert("RGBA")
    img.thumbnail((limit, limit), Image.BILINEAR)
    pixels = np.asarray(img).reshape(-1, 4)
    return pixels[pixels[:, 3] > 128][:, :3].astype(float)


def palette_of(pixels: np.ndarray, colors: int = 8) -> np.ndarray:
    """Return the main RGB colors, ignoring any under 1 percent of the pixels."""
    strip = Image.fromarray(pixels.reshape(-1, 1, 3).astype(np.uint8), "RGB")
    quantized = strip.quantize(colors=colors, method=Image.MEDIANCUT)
    table = quantized.getpalette()
    counts = quantized.getcolors() or []
    keep = [(count, table[i * 3:i * 3 + 3]) for count, i in counts if count / len(pixels) >= 0.01]
    return np.array([color for _, color in sorted(keep, key=lambda item: -item[0])], dtype=float)


def reference_files(kit: Path, extra: list[str], manifest: dict) -> list[Path]:
    found = [Path(p) for p in extra]
    style = kit / "style"
    if (style / "style_anchor.png").exists():
        found.append(style / "style_anchor.png")
    if (style / "references").is_dir():
        found += sorted(p for p in (style / "references").iterdir()
                        if p.suffix.lower() in (".png", ".webp", ".jpg", ".jpeg"))
    found += [kit / e["file"] for e in manifest["elements"].values()
              if e.get("imported_from") and not e.get("derived_from")]
    return found


def cmd_compare(args) -> int:
    kit = Path(args.kit)
    manifest = load_manifest(kit)
    refs = reference_files(kit, args.ref or [], manifest)
    missing = [str(p) for p in refs if not p.exists()]
    if missing:
        die("NOT_FOUND", f"{missing}", 1)
    locked = read_palette(kit)
    if not refs and not locked:
        die("NO_REFERENCES", "add style/palette.json, style/style_anchor.png, style/references/ or --ref.", 1)

    palette_sets, ref_pixels = [], []
    for ref in refs:
        pixels = visible_pixels(ref)
        if len(pixels):
            ref_pixels.append(pixels)
            palette_sets.append(palette_of(pixels))
    if not ref_pixels and not locked:
        die("NO_REFERENCES", "the references have no visible pixels.", 1)
    # A recorded palette is the tone decision, so it replaces whatever the references contain.
    palette_rgb = np.array([from_hex(c) for c in locked["colors"]]) if locked else np.concatenate(palette_sets)
    palette_lab = rgb_to_lab(palette_rgb)
    ref_lab = rgb_to_lab(palette_rgb if locked else np.concatenate(ref_pixels))
    light = np.percentile(ref_lab[:, 0], [5, 95])
    chroma = np.percentile(np.hypot(ref_lab[:, 1], ref_lab[:, 2]), [5, 95])

    names = [n for n, e in manifest["elements"].items()
             if not e.get("imported_from") and not e.get("derived_from") and not n.endswith("_disabled")]
    if args.match:
        names = [n for n in names if any(fnmatch.fnmatch(n, p) for p in args.match)]

    report = {}
    for name in names:
        pixels = visible_pixels(kit / manifest["elements"][name]["file"])
        if len(pixels) < 16:
            report[name] = {"status": "review", "reasons": ["almost no visible pixels"]}
            continue
        lab = rgb_to_lab(pixels)
        nearest = np.sqrt(((lab[:, None, :] - palette_lab[None, ...]) ** 2).sum(axis=2)).min(axis=1)
        match = float((nearest <= args.color_distance).mean())
        med_light = float(np.median(lab[:, 0]))
        med_chroma = float(np.median(np.hypot(lab[:, 1], lab[:, 2])))
        reasons = []
        if match < args.min_palette:
            reasons.append(f"only {match:.0%} of pixels fit the reference palette")
        if not light[0] - 10 <= med_light <= light[1] + 10:
            reasons.append(f"lightness {med_light:.0f} is outside the reference range {light[0]:.0f}-{light[1]:.0f}")
        if not chroma[0] - 10 <= med_chroma <= chroma[1] + 10:
            reasons.append(f"saturation {med_chroma:.0f} is outside the reference range {chroma[0]:.0f}-{chroma[1]:.0f}")
        report[name] = {"status": "review" if reasons else "ok", "palette_match": round(match, 3),
                        "lightness": round(med_light, 1), "saturation": round(med_chroma, 1), "reasons": reasons}

    board = compare_board(kit, manifest, refs, palette_rgb, report)
    review = [n for n, r in report.items() if r["status"] == "review"]
    summary = {"tone_source": locked["source"] if locked else "references",
               "references": [p.name for p in refs][:20], "reference_count": len(refs),
               "compared": len(report), "review": review, "board": board.relative_to(kit).as_posix(),
               "elements": report}
    (kit / "compare_report.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    for name in review:
        print(f"{name}: review - {'; '.join(report[name]['reasons'])}")
    print(f"Compared {len(report)} elements against {len(refs)} references: "
          f"{len(report) - len(review)} ok, {len(review)} to review. Board: {summary['board']}")
    return 0


def compare_board(kit: Path, manifest: dict, refs: list[Path], palette: np.ndarray, report: dict,
                  cell: int = 130, ref_size: int = 260, columns: int = 6) -> Path:
    """Draw references and palette beside the compared elements, with flagged ones in red."""
    shown = refs[:4]
    rows = max(1, (len(report) + columns - 1) // columns)
    height = max(len(shown) * (ref_size + 8) + 44, rows * (cell + 22) + 44)
    board = Image.new("RGB", (ref_size + 20 + columns * cell, height), (245, 245, 245))
    draw = ImageDraw.Draw(board)
    width = (ref_size - 8) / max(1, len(palette))
    for i, color in enumerate(palette):
        draw.rectangle([4 + i * width, 4, 4 + (i + 1) * width, 30], fill=tuple(int(c) for c in color))
    for i, ref in enumerate(shown):
        thumb = Image.open(ref).convert("RGBA")
        thumb.thumbnail((ref_size - 8, ref_size - 8))
        tile = checker(ref_size - 8, ref_size - 8)
        tile.alpha_composite(thumb, ((tile.width - thumb.width) // 2, (tile.height - thumb.height) // 2))
        board.paste(tile.convert("RGB"), (4, 38 + i * (ref_size + 8)))
    left = ref_size + 12
    draw.line([left - 4, 0, left - 4, height], fill=(170, 170, 170))
    for i, (name, result) in enumerate(report.items()):
        x, y = left + (i % columns) * cell, 8 + (i // columns) * (cell + 22)
        thumb = Image.open(kit / manifest["elements"][name]["file"]).convert("RGBA")
        thumb.thumbnail((cell - 12, cell - 12))
        tile = checker(cell - 4, cell - 4)
        tile.alpha_composite(thumb, ((tile.width - thumb.width) // 2, (tile.height - thumb.height) // 2))
        board.paste(tile.convert("RGB"), (x + 2, y + 2))
        flagged = result["status"] == "review"
        if flagged:
            draw.rectangle([x, y, x + cell - 1, y + cell - 1], outline=(220, 0, 0), width=3)
        short = name.split("/")[-1]
        draw.text((x + 3, y + cell + 2), short if len(short) <= 20 else short[:19] + "~",
                  fill=(200, 0, 0) if flagged else (30, 30, 30))
    out = kit / "preview" / "compare.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    board.save(out)
    return out


def read_palette(kit: Path) -> dict | None:
    path = kit / "style" / "palette.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def parse_region(text: str, size: tuple[int, int]) -> tuple[int, int, int, int]:
    try:
        x0, y0, x1, y1 = (int(v) for v in text.split(","))
    except ValueError:
        die("BAD_REGION", f"{text}: use x0,y0,x1,y1 in pixels", 1)
    if not (0 <= x0 < x1 <= size[0] and 0 <= y0 < y1 <= size[1]):
        die("BAD_REGION", f"{text} is outside the {size[0]}x{size[1]} image", 1)
    return x0, y0, x1, y1


def cmd_palette(args) -> int:
    kit = Path(args.kit)
    target = kit / "style" / "palette.json"
    if bool(args.image) == bool(args.hex):
        die("BAD_INPUT", "give either a reference image or --hex", 1)
    if target.exists() and not args.force:
        die("EXISTS", f"{target} already records the tone. Pass --force only when deliberately changing it.", 1)
    if args.hex:
        colors = [c.strip().upper() for c in args.hex.split(",") if c.strip()]
        bad = [c for c in colors if not re.fullmatch(r"#[0-9A-F]{6}", c)]
        if bad or not colors:
            die("BAD_INPUT", f"use #RRGGBB values: {bad}", 1)
        source = "chosen colors"
    else:
        path = Path(args.image)
        if not path.exists():
            die("NOT_FOUND", str(path), 1)
        img = Image.open(path).convert("RGBA")
        boxes = [parse_region(r, img.size) for r in args.region or []] or [(0, 0, *img.size)]
        chunks = [np.asarray(img.crop(b)).reshape(-1, 4) for b in boxes]
        pixels = np.concatenate(chunks)
        pixels = pixels[pixels[:, 3] > 128][:, :3].astype(float)
        if not len(pixels):
            die("NO_PIXELS", "the image or regions have no visible pixels", 1)
        colors = [to_hex(c) for c in palette_of(pixels, args.colors)]
        source = f"{path.name}, {len(boxes)} region(s)" if args.region else path.name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"source": source, "colors": colors}, indent=2), encoding="utf-8")
    swatch = Image.new("RGB", (max(1, len(colors)) * 110, 110), (255, 255, 255))
    draw = ImageDraw.Draw(swatch)
    for i, color in enumerate(colors):
        draw.rectangle([i * 110, 0, i * 110 + 109, 80], fill=color)
        draw.text((i * 110 + 6, 88), color, fill=(20, 20, 20))
    out = kit / "preview" / "palette.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    swatch.save(out)
    print(f"Recorded {len(colors)} colors from {source}: {' '.join(colors)}. Swatch: preview/palette.png")
    return 0


FONT_ROOT = "https://raw.githubusercontent.com/google/fonts/main/"
FONT_CATALOG = {
    "lilita one": ("ofl/lilitaone", "LilitaOne-Regular.ttf"), "titan one": ("ofl/titanone", "TitanOne-Regular.ttf"),
    "luckiest guy": ("apache/luckiestguy", "LuckiestGuy-Regular.ttf"), "bungee": ("ofl/bungee", "Bungee-Regular.ttf"),
    "russo one": ("ofl/russoone", "RussoOne-Regular.ttf"), "passion one": ("ofl/passionone", "PassionOne-Bold.ttf"),
    "changa one": ("ofl/changaone", "ChangaOne-Regular.ttf"),
    "press start 2p": ("ofl/pressstart2p", "PressStart2P-Regular.ttf"),
    "silkscreen": ("ofl/silkscreen", "Silkscreen-Regular.ttf"), "vt323": ("ofl/vt323", "VT323-Regular.ttf"),
    "medievalsharp": ("ofl/medievalsharp", "MedievalSharp.ttf"),
    "cinzel decorative": ("ofl/cinzeldecorative", "CinzelDecorative-Bold.ttf"),
    "black ops one": ("ofl/blackopsone", "BlackOpsOne-Regular.ttf"), "audiowide": ("ofl/audiowide", "Audiowide-Regular.ttf"),
    "creepster": ("ofl/creepster", "Creepster-Regular.ttf"),
}


def kit_fonts(kit: Path) -> list[Path]:
    folder = kit / "fonts"
    return sorted(p for p in folder.glob("*") if p.suffix.lower() in (".ttf", ".otf")) if folder.is_dir() else []


def resolve_font(kit: Path, layout: dict) -> tuple[str | None, str]:
    """Return the font path and where it came from: the layout, then the kit, then the system."""
    named = layout.get("font")
    if named:
        for candidate in (kit / named, Path(named)):
            if candidate.is_file():
                return str(candidate), "layout"
    fonts = kit_fonts(kit)
    return (str(fonts[0]), "kit") if fonts else (None, "system")


def missing_glyphs(text: str, font) -> list[str]:
    """List characters that would draw as an empty box, by comparing with a missing glyph."""
    box = bytes(font.getmask("\U0010FFFF"))
    return sorted({c for c in text if not c.isspace() and bytes(font.getmask(c)) == box})


def cmd_fonts(args) -> int:
    kit = Path(args.kit)
    if args.add:
        entry = FONT_CATALOG.get(args.add.strip().lower())
        if not entry:
            die("NOT_IN_CATALOG", f"{args.add} is not in the catalog: {sorted(FONT_CATALOG)}", 1)
        folder, file = entry
        target = kit / "fonts" / file
        if target.exists():
            print(f"Already in the kit: fonts/{file}")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            license_name = "LICENSE.txt" if folder.startswith("apache") else "OFL.txt"
            try:
                for url, path in ((FONT_ROOT + f"{folder}/{file}", target),
                                  (FONT_ROOT + f"{folder}/{license_name}", target.with_name(f"{target.stem}_{license_name}"))):
                    request = urllib.request.Request(url, headers={"User-Agent": "game-ui-kit"})
                    with urllib.request.urlopen(request, timeout=30) as response:
                        path.write_bytes(response.read())
                ImageFont.truetype(str(target), 20)
            except (OSError, ValueError) as exc:
                target.unlink(missing_ok=True)
                die("DOWNLOAD_FAILED", f"{args.add}: {exc}. Allow network access or ask the user for a font file.")
            print(f"Added fonts/{file} with its license.")
    fonts = kit_fonts(kit)
    print(f"Kit fonts: {[p.name for p in fonts] or 'none'}")
    problems = 0
    for path in layout_paths(kit):
        layout = read_layout(path)
        font_path, source = resolve_font(kit, layout)
        font = load_font(32, font_path)
        texts = [str(i["text"]) for i in layout["items"] if "text" in i]
        lacking = sorted({c for t in texts for c in missing_glyphs(t, font)})
        print(f"{path.stem}: font from {source}, {len(texts)} texts" + (f", missing glyphs: {lacking}".encode("ascii", "backslashreplace").decode() if lacking else ""))
        problems += bool(lacking)
    return 2 if problems else 0


def stretch_band(image: np.ndarray, axis: int, tolerance: float, min_share: float):
    """Find the longest run of near-identical lines along axis. Return (start, end) or None."""
    alpha = image[..., 3:] / 255
    premultiplied = np.concatenate([image[..., :3] * alpha, image[..., 3:]], axis=2)
    other = 1 - axis
    # Average along each line first, so image noise does not read as detail between lines.
    kernel = np.ones(9) / 9
    smoothed = np.apply_along_axis(lambda line: np.convolve(line, kernel, mode="same"), other, premultiplied)
    diff = np.abs(np.diff(smoothed, axis=axis)).max(axis=2)
    profile = np.percentile(diff, 99, axis=other)
    size = image.shape[axis]
    best, start = None, None
    for i, value in enumerate(list(profile) + [tolerance + 1]):
        if value <= tolerance:
            start = i if start is None else start
        elif start is not None:
            run = (start, i - 1)
            length = i - start
            distance = abs((start + i - 1) / 2 - size / 2)
            if best is None or (length, -distance) > best[0]:
                best = ((length, -distance), run)
            start = None
    if best is None or best[0][0] < max(4, size * min_share):
        return None
    return best[1]


def nine_scale(border: dict, w: int, h: int, width: int, height: int, border_scale: float | None) -> float:
    across = border["left"] + border["right"]
    down = border["top"] + border["bottom"]
    # A sprite cut on one axis scales normally on the other, so its end caps must follow that
    # scale. Otherwise a bar squeezed to a third of its height keeps full-width, pointed caps.
    if not down:
        scale = height / h
    elif not across:
        scale = width / w
    else:
        scale = min(1.0, width / w, height / h)
    if border_scale is not None:
        scale = scale * border_scale if not (across and down) else border_scale
    # Shrink corners rather than let them overlap when the target is smaller than the borders.
    return min(scale, width / across if across else scale, height / down if down else scale)


def render_nine_slice(img: Image.Image, border: dict, width: int, height: int,
                      border_scale: float | None = None) -> Image.Image:
    w, h = img.size
    xs = [0, border["left"], w - border["right"], w]
    ys = [0, border["top"], h - border["bottom"], h]
    scale = nine_scale(border, w, h, width, height, border_scale)
    left, right = round(border["left"] * scale), round(border["right"] * scale)
    top, bottom = round(border["top"] * scale), round(border["bottom"] * scale)
    tx = [0, left, width - right, width]
    ty = [0, top, height - bottom, height]
    out = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    for row in range(3):
        for col in range(3):
            source = (xs[col], ys[row], xs[col + 1], ys[row + 1])
            size = (tx[col + 1] - tx[col], ty[row + 1] - ty[row])
            if min(size) <= 0 or source[0] >= source[2] or source[1] >= source[3]:
                continue
            out.paste(img.crop(source).resize(size, Image.BILINEAR), (tx[col], ty[row]))
    return out


def selected(manifest: dict, patterns: list[str]) -> list[str]:
    return [n for n in manifest["elements"] if any(fnmatch.fnmatch(n, p) for p in patterns)]


def cmd_nineslice(args) -> int:
    kit = Path(args.kit)
    manifest = load_manifest(kit)
    names = selected(manifest, args.match)
    if not names:
        die("NO_MATCH", f"no elements match {args.match}", 1)
    review = 0
    for name in names:
        entry = manifest["elements"][name]
        img = Image.open(kit / entry["file"]).convert("RGBA")
        image = np.asarray(img).astype(float)
        w, h = img.size
        h_band = stretch_band(image, 1, args.tolerance, args.min_share) if args.axis != "vertical" else None
        v_band = stretch_band(image, 0, args.tolerance, args.min_share) if args.axis != "horizontal" else None
        missing = (args.axis != "vertical" and h_band is None) or (args.axis != "horizontal" and v_band is None)
        if missing:
            entry["nine_slice"] = {"status": "needs_review"}
            review += 1
            print(f"{name}: needs_review (no stretchable band)")
            continue
        border = {"left": 0, "bottom": 0, "right": 0, "top": 0}
        if h_band:
            border["left"], border["right"] = h_band[0] + 1, w - h_band[1] - 1
        if v_band:
            border["top"], border["bottom"] = v_band[0] + 1, h - v_band[1] - 1
        entry["nine_slice"] = {"status": "suggested", **border}
        large = [side for side, used, total in (("width", border["left"] + border["right"], w),
                                                ("height", border["top"] + border["bottom"], h))
                 if used > total * 0.6]
        entry["nine_slice"]["large_borders"] = large
        target_w = w * 2 if h_band else w
        target_h = h * 2 if v_band else h
        preview = on_checker(render_nine_slice(img, border, target_w, target_h))
        out = kit / "preview" / "nineslice" / f"{name.replace('/', '__')}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        preview.convert("RGB").save(out)
        print(f"{name}: L{border['left']} B{border['bottom']} R{border['right']} T{border['top']}")
    save_manifest(kit, manifest)
    print(f"{len(names) - review} suggested, {review} need review.")
    return 0


def cmd_states(args) -> int:
    kit = Path(args.kit)
    manifest = load_manifest(kit)
    # The normal state is the bare name (btn_yellow) or, in older kits, ends in _normal.
    names = [n for n in selected(manifest, args.match)
             if (n.endswith("_normal") or not STATE_RE.search(n)) and not manifest["elements"][n].get("derived_from")]
    if not names:
        die("NO_MATCH", f"no normal-state elements match {args.match}", 1)
    written = skipped = 0
    for name in names:
        entry = manifest["elements"][name]
        source = np.asarray(Image.open(kit / entry["file"]).convert("RGBA")).astype(float)
        rgb, alpha = source[..., :3], source[..., 3:]
        gray = (rgb * [0.299, 0.587, 0.114]).sum(axis=2, keepdims=True)
        variants = {
            "pressed": np.concatenate([rgb * 0.8, alpha], axis=2),
            "disabled": np.concatenate([rgb * 0.2 + gray * 0.8, alpha], axis=2),
        }
        base = name[: -len("_normal")] if name.endswith("_normal") else name
        for state, pixels in variants.items():
            derived = f"{base}_{state}"
            target = kit / "elements" / f"{derived}.png"
            if target.exists() and not args.force:
                skipped += 1
                continue
            Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8), "RGBA").save(target)
            # A derived state is new art, so it takes the kit's naming rule, not the source file's name.
            fields = {k: v for k, v in entry.items() if k != "imported_from"}
            manifest["elements"][derived] = {**fields, "file": target.relative_to(kit).as_posix(),
                                             "derived_from": name}
            written += 1
    save_manifest(kit, manifest)
    print(f"Wrote {written} derived states, kept {skipped} existing files.")
    return 0


LAYOUT_KEYS = {"size", "title", "background", "reference", "font", "items"}
ITEM_KEYS = {"element", "text", "x", "y", "w", "h", "anchor", "mode", "border_scale", "opacity",
             "text_color", "text_size", "text_stroke", "fill", "group", "goto", "label", "name", "role",
             "wf", "icon", "sub", "badge", "selected", "align"}
WF_KINDS = {"panel", "card", "button", "button_primary", "icon_button", "pill", "progress", "title", "text", "label",
            "image", "avatar", "tab", "bar", "badge", "slot", "divider"}
ANCHORS = {"top_left": (0, 0), "top": (0.5, 0), "top_right": (1, 0), "left": (0, 0.5), "center": (0.5, 0.5),
           "right": (1, 0.5), "bottom_left": (0, 1), "bottom": (0.5, 1), "bottom_right": (1, 1)}
VARIANT_RE = re.compile(r"^(.+)__v(\d+)$")
DEFAULT_SCREENS = ("home", "main_menu", "menu", "lobby", "hud")


def screen_of(stem: str) -> str:
    match = VARIANT_RE.match(stem)
    return match.group(1) if match else stem


def layout_sort_key(path: Path):
    match = VARIANT_RE.match(path.stem)
    return (screen_of(path.stem), int(match.group(2)) if match else 0)


def layout_paths(kit: Path, screen: str | None = None) -> list[Path]:
    paths = [p for p in (kit / "mockups").glob("*.json") if p.stem not in ("chosen", "confirmed")]
    if screen:
        paths = [p for p in paths if p.stem == screen or screen_of(p.stem) == screen]
    return sorted(paths, key=layout_sort_key)


def read_chosen(kit: Path) -> dict:
    path = kit / "mockups" / "chosen.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def selected_layouts(kit: Path, screen: str | None = None, strict: bool = True) -> dict[str, Path]:
    """Pick one layout per screen: the only one, or the chosen variant."""
    grouped: dict[str, list[Path]] = {}
    for path in layout_paths(kit, screen):
        grouped.setdefault(screen_of(path.stem), []).append(path)
    if not grouped:
        die("NO_LAYOUT", f"no layouts for {screen or 'this kit'} in {kit / 'mockups'}", 1)
    chosen, picked, undecided = read_chosen(kit), {}, {}
    for name, paths in grouped.items():
        match = [p for p in paths if p.stem == chosen.get(name)]
        if match:
            picked[name] = match[0]
        elif len(paths) == 1:
            picked[name] = paths[0]
        elif strict:
            undecided[name] = [p.stem for p in paths]
        else:
            picked[name] = paths[0]
    if undecided:
        die("NOT_CHOSEN", f"pick a variant first with the choose command: {undecided}")
    return picked


def load_font(size: int, path: str | None):
    for candidate in ([path] if path else []) + ["arial.ttf", "Arial.ttf", "segoeui.ttf", "DejaVuSans.ttf"]:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def read_layout(path: Path) -> dict:
    def bad(message: str):
        die("BAD_LAYOUT", f"{path.name}: {message}", 1)

    try:
        layout = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        bad(str(exc))
    if not isinstance(layout, dict):
        bad("the file must contain one JSON object")
    unknown = set(layout) - LAYOUT_KEYS
    if unknown:
        bad(f"unknown keys {sorted(unknown)}")
    size = layout.get("size")
    if not (isinstance(size, list) and len(size) == 2 and all(isinstance(v, int) and 0 < v <= 8192 for v in size)):
        bad('"size" must be [width, height] in pixels, at most 8192')
    if not isinstance(layout.get("items"), list) or not layout["items"]:
        bad('"items" must be a non-empty list')
    for index, item in enumerate(layout["items"]):
        where = f"item {index}"
        if not isinstance(item, dict):
            bad(f"{where} must be an object")
        unknown = set(item) - ITEM_KEYS
        if unknown:
            bad(f"{where}: unknown keys {sorted(unknown)}")
        if "element" not in item and "text" not in item and "wf" not in item:
            bad(f'{where}: needs "element", "text" or "wf"')
        if not is_number(item.get("x")) or not is_number(item.get("y")):
            bad(f'{where}: needs numeric "x" and "y"')
        for key in ("w", "h", "text_size", "text_stroke", "border_scale", "opacity", "fill"):
            if key in item and (not is_number(item[key]) or item[key] < 0 or (key in ("w", "h") and item[key] == 0)):
                bad(f'{where}: "{key}" must be a positive number')
        if "fill" in item and (item["fill"] > 1 or "w" not in item or "h" not in item):
            bad(f'{where}: "fill" must be from 0 to 1 and needs "w" and "h"')
        if item.get("anchor", "top_left") not in ANCHORS:
            bad(f'{where}: anchor must be one of {sorted(ANCHORS)}')
        if item.get("role", "ui") not in ("ui", "art"):
            bad(f'{where}: role must be ui or art')
        if item.get("mode", "auto") not in ("auto", "nine", "fit", "stretch"):
            bad(f'{where}: mode must be auto, nine, fit or stretch')
        if "wf" in item and item["wf"] not in WF_KINDS:
            bad(f'{where}: wf must be one of {sorted(WF_KINDS)}')
        if item.get("align", "center") not in ("left", "center", "right"):
            bad(f'{where}: align must be left, center or right')
        if "text_color" in item:
            try:
                ImageColor.getrgb(item["text_color"])
            except (ValueError, AttributeError):
                bad(f'{where}: "text_color" is not a color')
    return layout


def fit_sprite(img: Image.Image, entry: dict, item: dict, warn) -> tuple[Image.Image, int, int]:
    """Size one sprite for its item. Return the image and its offset inside the item's box."""
    ew, eh = img.size
    w, h = item.get("w"), item.get("h")
    label = item["element"]
    if w is None and h is None:
        return img, 0, 0
    if w is None or h is None:
        scale = (w / ew) if w is not None else (h / eh)
        if scale > 1.5:
            warn(f"{label}: enlarged {scale:.1f}x, may look soft")
        return img.resize((max(1, round(ew * scale)), max(1, round(eh * scale))), Image.LANCZOS), 0, 0
    w, h = max(1, round(w)), max(1, round(h))
    mode = item.get("mode", "auto")
    nine = entry.get("nine_slice") or {}
    ready = nine.get("status") == "suggested"
    if mode == "nine" and not ready:
        warn(f"{label}: asked for 9-slice but it has no usable borders, drawn with fit instead")
    if mode in ("auto", "nine") and ready:
        return render_nine_slice(img, nine, w, h, item.get("border_scale")), 0, 0
    if mode == "stretch":
        return img.resize((w, h), Image.LANCZOS), 0, 0
    scale = min(w / ew, h / eh)
    if scale > 1.5:
        warn(f"{label}: enlarged {scale:.1f}x, may look soft")
    size = (max(1, round(ew * scale)), max(1, round(eh * scale)))
    return img.resize(size, Image.LANCZOS), (w - size[0]) // 2, (h - size[1]) // 2


def text_layer(size: tuple[int, int], item: dict, box, font_path, warn) -> Image.Image:
    """Render sample text centered in box on its own transparent layer, shrinking it to fit."""
    x0, y0, x1, y1 = box
    color = ImageColor.getrgb(item.get("text_color", "#FFFFFF"))[:3]
    stroke = round(item.get("text_stroke", 0))
    text_size = round(item.get("text_size", max(12, (y1 - y0) * 0.45)))
    text = str(item["text"])
    limit = (x1 - x0) * 0.9
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    font = load_font(text_size, font_path)
    lacking = missing_glyphs(text, font)
    if lacking:
        warn(f'text "{text}": the font has no glyph for {lacking}')
    while probe.textlength(text, font=font) + stroke * 2 > limit and text_size > 8:
        text_size -= 1
        font = load_font(text_size, font_path)
    if probe.textlength(text, font=font) + stroke * 2 > limit:
        warn(f'text "{text}" does not fit its {round(x1 - x0)} px box')
    center = ((x0 + x1) / 2, (y0 + y1) / 2)
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    if stroke:
        # Masks keep soft edges clean; drawing color straight onto transparency darkens them.
        luminance = 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]
        outline = (20, 20, 20) if luminance > 128 else (245, 245, 245)
        mask = Image.new("L", size, 0)
        ImageDraw.Draw(mask).text(center, text, font=font, fill=255, anchor="mm", stroke_width=stroke, stroke_fill=255)
        layer = Image.merge("RGBA", [Image.new("L", size, c) for c in outline] + [mask])
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).text(center, text, font=font, fill=255, anchor="mm")
    layer.alpha_composite(Image.merge("RGBA", [Image.new("L", size, c) for c in color] + [mask]))
    return layer


def prepare_fill(item: dict, entry: dict, warn) -> dict:
    """Shorten a progress bar to its value, never below the width of its end caps."""
    if "fill" not in item:
        return item
    nine = entry.get("nine_slice") or {}
    if nine.get("status") != "suggested":
        warn(f"{item['element']}: fill needs horizontal 9-slice, so the ends are stretched")
        return {**item, "w": max(1, item["w"] * item["fill"]), "mode": "stretch"}
    caps = (nine["left"] + nine["right"]) * item["h"] / entry["height"]
    return {**item, "w": max(caps + 1, item["w"] * item["fill"])}


def item_box(item: dict, native: tuple[int, int] | None, canvas: tuple[int, int]) -> tuple[int, int, int, int]:
    width, height = item.get("w"), item.get("h")
    if native and width is None and height is None:
        width, height = native
    elif native and width is None:
        width = height * native[0] / native[1]
    elif native and height is None:
        height = width * native[1] / native[0]
    if width is None:
        width = 240 if item.get("element") else canvas[0]
    if height is None:
        height = width if item.get("element") and "w" in item else 80
    width, height = max(1, round(width)), max(1, round(height))
    ax, ay = ANCHORS[item.get("anchor", "top_left")]
    x0, y0 = round(item["x"] - width * ax), round(item["y"] - height * ay)
    return x0, y0, x0 + width, y0 + height


def lint_layout(boxes: list[dict], size: tuple[int, int], warn) -> None:
    """Flag layout problems a person would notice: small targets, cut-off items, near misses."""
    width, height = size
    short = min(size)
    margin = round(short * 0.02)
    for box in boxes:
        x0, y0, x1, y1 = box["box"]
        if x1 <= 0 or y1 <= 0 or x0 >= width or y0 >= height:
            warn(f"{box['name']}: entirely outside the {width}x{height} screen")
        elif x0 < 0 or y0 < 0 or x1 > width or y1 > height:
            warn(f"{box['name']}: extends outside the {width}x{height} screen")
        elif box["touch"] and (x0 < margin or y0 < margin or x1 > width - margin or y1 > height - margin):
            warn(f"{box['name']}: tappable item is within {margin} px of the screen edge")
        if box["touch"] and min(x1 - x0, y1 - y0) < short * 0.07:
            warn(f"{box['name']}: tappable item is small ({x1 - x0}x{y1 - y0})")
    sprites = [b for b in boxes if b["sprite"]]
    for i, a in enumerate(sprites):
        for b in sprites[i + 1:]:
            for edge, label in ((0, "left"), (1, "top"), (2, "right"), (3, "bottom")):
                gap = abs(a["box"][edge] - b["box"][edge])
                size_match = a["box"][2] - a["box"][0] == b["box"][2] - b["box"][0] or \
                    a["box"][3] - a["box"][1] == b["box"][3] - b["box"][1]
                if 1 <= gap <= 3 and size_match:
                    warn(f"{a['name']} and {b['name']}: {label} edges are {gap} px apart, almost aligned")


def cmd_backdrop(args) -> int:
    """Blur and dim a rendered screen into a background element for the popups opened from it."""
    kit = Path(args.kit)
    manifest = load_manifest(kit)
    picked = selected_layouts(kit, args.screen, strict=False)
    if args.screen not in picked:
        die("NOT_FOUND", f"no layout for screen {args.screen}", 1)
    result = render_mockup(kit, picked[args.screen], manifest)
    image = Image.open(kit / result["image"]).convert("RGB")
    image = image.filter(ImageFilter.GaussianBlur(args.blur))
    image = Image.blend(image, Image.new("RGB", image.size, ImageColor.getrgb(args.color)[:3]), args.dim)
    name = args.name or f"backgrounds/bg_blur_{slug(args.screen)}"
    if not NAME_RE.match(name):
        die("BAD_NAME", f"use lowercase letters, digits, _ and /: {name}", 1)
    target = kit / "elements" / f"{name}.png"
    if name in manifest["elements"] and not args.force:
        die("EXISTS", f"{name} already exists. Pass --force to rebuild it after the screen changed.", 1)
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target)
    manifest["elements"][name] = {
        "file": target.relative_to(kit).as_posix(), "width": image.width, "height": image.height,
        "derived_from": f"screen:{args.screen}", "has_transparency": False,
        "key_color": None, "touches_sheet_edge": False, "nine_slice": None,
    }
    save_manifest(kit, manifest)
    print(f"Wrote {name} from {args.screen}, blur {args.blur}, dim {args.dim}. "
          f'Set "background": "{name}" in the popup layouts. Rebuild with --force when {args.screen} changes.')
    return 0


def draw_shape(kind: str, corner: int, outline: int, size: int = 256, scale: int = 4) -> Image.Image:
    """One white shape on a transparent square frame, drawn large and reduced for smooth edges."""
    big, r, w = size * scale, corner * scale, outline * scale
    mask = Image.new("L", (big, big), 0)
    draw = ImageDraw.Draw(mask)

    def solid(inset: int, value: int):
        if kind == "circle":
            draw.ellipse([inset, inset, big - 1 - inset, big - 1 - inset], fill=value)
            return
        if kind == "rectangle":
            draw.rounded_rectangle([inset, inset, big - 1 - inset, big - 1 - inset], radius=max(0, r - inset), fill=value)
            return
        # Equilateral triangle filling the frame width, centered vertically; an inset of d moves
        # each side in by d, which moves each vertex 2d from the centroid.
        side = big - 1
        height = side * 3 ** 0.5 / 2
        top = (big - height) / 2
        cx, cy = big / 2, top + height * 2 / 3
        base = [(cx, top), (cx + side / 2, top + height), (cx - side / 2, top + height)]

        def toward_center(points, distance):
            out = []
            for x, y in points:
                length = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
                k = max(0.0, (length - distance) / length)
                out.append((cx + (x - cx) * k, cy + (y - cy) * k))
            return out

        radius = max(0, r - inset)
        inner = toward_center(base, 2 * inset)
        if radius:
            core = toward_center(inner, 2 * radius)
            draw.polygon(core, fill=value)
            draw.line(core + [core[0]], fill=value, width=round(radius * 2), joint="curve")
            for x, y in core:
                draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=value)
        else:
            draw.polygon(inner, fill=value)

    solid(0, 255)
    if w:
        solid(w, 0)
    mask = mask.resize((size, size), Image.LANCZOS)
    image = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    image.putalpha(mask)
    return image


def cmd_shapes(args) -> int:
    """Draw the standard's common shapes: square, circle and triangle, plain, outlined and with round corners."""
    kit = Path(args.kit)
    manifest = load_manifest(kit)
    written = skipped = 0
    for kind in ("rectangle", "circle", "poly"):
        corners = (0,) if kind == "circle" else (0, 8, 12)
        for corner in corners:
            for outline in (0, 4):
                name = "shapes/shape_" + kind + (f"_{corner}px" if corner else "") + ("_outline" if outline else "")
                target = kit / "elements" / f"{name}.png"
                if name in manifest["elements"] and not args.force:
                    skipped += 1
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                draw_shape(kind, corner, outline).save(target)
                manifest["elements"][name] = {
                    "file": target.relative_to(kit).as_posix(), "width": 256, "height": 256,
                    "has_transparency": True, "key_color": None, "touches_sheet_edge": False, "nine_slice": None,
                    "drawn_by": "shapes",
                }
                written += 1
    save_manifest(kit, manifest)
    print(f"Wrote {written} shapes, kept {skipped} existing. All solid white on transparent 256 px frames.")
    return 0


def build_layers(kit: Path, layout: dict, manifest: dict):
    """Turn a layout into ordered layers. PNG mockups and PSD exports both draw from this."""
    size = tuple(layout["size"])
    width, height = size
    warnings, missing, used, boxes, layers = [], [], [], [], []
    warn = warnings.append
    font_path, font_source = resolve_font(kit, layout)
    if size != DEFAULT_CANVAS:
        warn(f"canvas is {width}x{height}, the default is {DEFAULT_CANVAS[0]}x{DEFAULT_CANVAS[1]}")
    if font_source == "system" and any("text" in i for i in layout["items"]):
        warn("no font in the kit, so a system font was used")

    def add(image: Image.Image, name: str, group=None):
        bbox = image.getbbox()
        if bbox:
            layers.append({"name": name, "group": group, "image": image.crop(bbox), "x": bbox[0], "y": bbox[1]})

    background = layout.get("background")
    if background is None:
        background = "#282C34"
    if isinstance(background, str) and background.startswith("#"):
        try:
            add(Image.new("RGBA", size, ImageColor.getrgb(background)[:3] + (255,)), "Background")
        except ValueError:
            die("BAD_LAYOUT", "background is not a color", 1)
    else:
        file = None
        if background in manifest["elements"]:
            used.append(background)
            file = kit / manifest["elements"][background]["file"]
        elif (kit / str(background)).is_file():
            file = kit / str(background)
        if file:
            add(Image.open(file).convert("RGBA").resize(size, Image.LANCZOS), "Background")
        else:
            missing.append(str(background))
            add(Image.new("RGBA", size, (40, 44, 52, 255)), "Background")

    for item in layout["items"]:
        name, group = item.get("element"), item.get("group")
        entry = manifest["elements"].get(name) if name else None
        sprite, offset_x, offset_y = None, 0, 0
        if entry:
            used.append(name)
            item = prepare_fill(item, entry, warn)
            source = Image.open(kit / entry["file"]).convert("RGBA")
            sprite, offset_x, offset_y = fit_sprite(source, entry, item, warn)
            if "w" in item and "h" in item:
                native = None
            else:
                native = sprite.size
            box = item_box({**item, "w": sprite.width, "h": sprite.height} if native else item, None, size)
        else:
            if name:
                missing.append(name)
            box = item_box(item, None, size)
        x0, y0, x1, y1 = box
        label = name or str(item.get("text") or item.get("wf"))
        boxes.append({"name": label, "box": box, "sprite": bool(sprite),
                      "touch": "goto" in item or bool(name and ("_normal" in name or name.split("/")[-1].startswith("btn_")))})
        if sprite is not None:
            if item.get("opacity", 1) < 1:
                sprite = sprite.copy()
                sprite.putalpha(sprite.getchannel("A").point(lambda a: round(a * item["opacity"])))
            layer = Image.new("RGBA", size, (0, 0, 0, 0))
            layer.paste(sprite, (x0 + offset_x, y0 + offset_y))
            add(layer, kit_layer_name(entry) or name.split("/")[-1], group)
        elif name:
            layer = Image.new("RGBA", size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(layer)
            draw.rectangle([x0, y0, x1, y1], fill=(255, 0, 80, 70), outline=(255, 0, 80, 255), width=3)
            draw.text((x0 + 6, y0 + 6), f"MISSING {name}", fill=(255, 255, 255, 255), font=load_font(16, font_path))
            add(layer, f"MISSING {name}", group)
        if "text" in item:
            add(text_layer(size, item, box, font_path, warn), f"Text: {item['text']}", group)
    lint_layout(boxes, size, warn)
    return layers, warnings, sorted(set(missing)), sorted(set(used))


def flatten(layers: list[dict], size: tuple[int, int]) -> Image.Image:
    canvas = Image.new("RGBA", size, (0, 0, 0, 255))
    for layer in layers:
        canvas.alpha_composite(layer["image"], (layer["x"], layer["y"]))
    return canvas.convert("RGB")


def render_mockup(kit: Path, path: Path, manifest: dict) -> dict:
    layout = read_layout(path)
    width, height = layout["size"]
    layers, warnings, missing, used = build_layers(kit, layout, manifest)
    image = flatten(layers, (width, height))
    out_dir = kit / "preview" / "mockups"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{path.stem}.png"
    image.save(out)

    compared = None
    if layout.get("reference"):
        reference = kit / layout["reference"]
        if reference.exists():
            ref = Image.open(reference).convert("RGB")
            ref = ref.resize((max(1, round(ref.width * height / ref.height)), height), Image.LANCZOS)
            pair = Image.new("RGB", (ref.width + 24 + width, height), (245, 245, 245))
            pair.paste(ref, (0, 0))
            pair.paste(image, (ref.width + 24, 0))
            compared = out_dir / f"{path.stem}_vs_reference.png"
            pair.save(compared)
            mine, theirs = detail_score(image), detail_score(ref)
            if theirs > 0 and mine / theirs < DETAIL_RATIO:
                warnings.append(f"DETAIL_GAP: about {mine / theirs:.0%} of its reference's detail; "
                                "add the parts and decoration the reference shows")
        else:
            warnings.append(f"reference not found: {layout['reference']}")

    return {"image": out.relative_to(kit).as_posix(),
            "versus_reference": compared.relative_to(kit).as_posix() if compared else None,
            "items": len(layout["items"]), "layers": len(layers), "missing": missing,
            "warnings": warnings, "used": used}


def variants_board(kit: Path, screen: str, stems: list[str]) -> Path:
    """Place a screen's variants side by side, labeled for choosing."""
    thumbs = []
    for stem in stems:
        image = Image.open(kit / "preview" / "mockups" / f"{stem}.png").convert("RGB")
        image.thumbnail((640, 640))
        thumbs.append((stem, image))
    width = sum(t.width for _, t in thumbs) + 16 * (len(thumbs) + 1)
    height = max(t.height for _, t in thumbs) + 56
    board = Image.new("RGB", (width, height), (245, 245, 245))
    draw = ImageDraw.Draw(board)
    x = 16
    for stem, thumb in thumbs:
        match = VARIANT_RE.match(stem)
        draw.text((x, 12), f"v{match.group(2)}" if match else stem, fill=(20, 20, 20), font=load_font(24, None))
        board.paste(thumb, (x, 44))
        x += thumb.width + 16
    out = kit / "preview" / "mockups" / f"{screen}_variants.png"
    board.save(out)
    return out


def plan_text(paths: list[Path]) -> str:
    counts: dict[str, int] = {}
    for path in paths:
        counts[screen_of(path.stem)] = counts.get(screen_of(path.stem), 0) + 1
    detail = ", ".join(f"{name} x{count}" for name, count in counts.items())
    return f"{len(paths)} mockups across {len(counts)} screens: {detail}"


BACKGROUND_FAMILIES = {"backgrounds", "backdrops"}
MIN_OWN_ELEMENTS = 3
DETAIL_RATIO = 0.6


def detail_score(image: Image.Image) -> float:
    """Mean edge strength at a fixed width, so a plain panel scores low and a decorated screen high."""
    small = image.convert("L").resize((480, max(1, round(image.height * 480 / image.width))), Image.LANCZOS)
    return float(np.asarray(small.filter(ImageFilter.FIND_EDGES), dtype=float).mean())


def richness_warnings(kit: Path) -> dict[str, list[str]]:
    """Flag screens with no element of their own, or more text than art, per screen across its variants."""
    used: dict[str, set[str]] = {}
    texts: dict[str, int] = {}
    arts: dict[str, int] = {}
    for path in layout_paths(kit):
        try:
            items = json.loads(path.read_text(encoding="utf-8")).get("items", [])
        except (OSError, ValueError, AttributeError):
            continue
        screen = screen_of(path.stem)
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            element = item.get("element")
            if element and element.split("/")[0] not in BACKGROUND_FAMILIES:
                used.setdefault(screen, set()).add(STATE_RE.sub("", element))
                arts[screen] = arts.get(screen, 0) + 1
            elif "text" in item:
                texts[screen] = texts.get(screen, 0) + 1
    screens = set(used) | set(texts)
    result: dict[str, list[str]] = {}
    for screen in sorted(screens):
        notes = []
        mine = used.get(screen, set())
        others = set().union(*(used.get(o, set()) for o in screens if o != screen))
        own = mine - others
        if len(screens) > 1 and len(own) < MIN_OWN_ELEMENTS:
            notes.append(f"has {len(own)} element(s) of its own, fewer than {MIN_OWN_ELEMENTS}; "
                         "add this screen's specific parts from its concept")
        if texts.get(screen, 0) > arts.get(screen, 0):
            notes.append(f"shows more text-only items ({texts.get(screen, 0)}) than art ({arts.get(screen, 0)}); "
                         "replace labels with icons or art where they would do")
        if notes:
            result[screen] = notes
    return result


def cmd_mockup(args) -> int:
    kit = Path(args.kit)
    manifest = load_manifest(kit)
    paths = layout_paths(kit, args.screen)
    if not paths:
        die("NO_LAYOUT", f"write a layout in {kit / 'mockups'} first", 1)
    # Validate everything first, so one bad layout does not leave a partial set of images.
    for path in paths:
        read_layout(path)
    print(f"Planned: {plan_text(paths)}. No image generation is used.")
    if args.plan:
        return 0
    screens = {path.stem: render_mockup(kit, path, manifest) for path in paths}
    boards = {}
    grouped: dict[str, list[str]] = {}
    for path in paths:
        grouped.setdefault(screen_of(path.stem), []).append(path.stem)
    for screen, stems in grouped.items():
        if len(stems) > 1:
            boards[screen] = variants_board(kit, screen, stems).relative_to(kit).as_posix()
    used = {name for screen in screens.values() for name in screen["used"]}
    unused = [n for n, e in manifest["elements"].items() if n not in used and not e.get("derived_from")]
    report = {"count": len(screens), "screens": screens, "variant_boards": boards, "unused_elements": unused}
    (kit / "mockup_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    for name, screen in screens.items():
        print(f"{name}: {screen['image']}, {screen['items']} items, {len(screen['missing'])} missing, "
              f"{len(screen['warnings'])} warnings")
        for element in screen["missing"]:
            print(f"  MISSING_ELEMENT: {element}")
        for warning in screen["warnings"]:
            print(f"  warning: {warning}".encode("ascii", "replace").decode())
    richness = richness_warnings(kit)
    report["richness"] = richness
    (kit / "mockup_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    for screen, notes in richness.items():
        if screen in {screen_of(n) for n in screens}:
            for note in notes:
                print(f"  PLAIN_SCREEN {screen}: {note}")
    for screen, board in boards.items():
        print(f"Variants of {screen}: {board}")
    print(f"Rendered {len(screens)} mockups. {len(unused)} elements not used in any mockup.")
    return 2 if any(screen["missing"] for screen in screens.values()) else 0


def cmd_choose(args) -> int:
    kit = Path(args.kit)
    variant = args.variant if args.variant.startswith(args.screen) else f"{args.screen}__{args.variant}"
    options = [p.stem for p in layout_paths(kit, args.screen)]
    if variant not in options:
        die("NOT_FOUND", f"{variant} is not one of {options}", 1)
    chosen = read_chosen(kit)
    chosen[args.screen] = variant
    (kit / "mockups" / "chosen.json").write_text(json.dumps(chosen, indent=2), encoding="utf-8")
    print(f"{args.screen}: chose {variant}")
    return 0


WIRE_ICONS: dict | None = None
WIRE_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:__W__px;height:__H__px;overflow:hidden}
body{--u:__U__px;--accent:#c8f03c;--accent-ink:#17210a;--ink:#eef2fa;--soft:#aab4c8;--muted:#7a869c;
  --surface:rgba(255,255,255,.055);--surface2:rgba(255,255,255,.09);--line:rgba(255,255,255,.10);
  font-family:"Segoe UI","Be Vietnam Pro","Inter",system-ui,-apple-system,"Noto Sans",sans-serif;color:var(--ink);
  background:__BG__;position:relative;-webkit-font-smoothing:antialiased}
.i{position:absolute;display:flex;align-items:center;justify-content:center;gap:calc(var(--u)*5);
  text-align:center;line-height:1.15;overflow:visible}
.i.al-left{justify-content:flex-start;text-align:left}.i.al-right{justify-content:flex-end;text-align:right}
.t{overflow:hidden;text-overflow:ellipsis;max-width:100%}
.stack{display:flex;flex-direction:column;align-items:inherit;gap:calc(var(--u)*2);min-width:0}
.i.al-left .stack{align-items:flex-start}.i.al-center .stack{align-items:center}
.sub{color:var(--soft);font-weight:500;font-size:.62em}
svg.ic{flex:none;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.k-panel{background:var(--surface);border:calc(var(--u)*.8) solid var(--line);border-radius:calc(var(--u)*14)}
.k-card{background:linear-gradient(160deg,rgba(255,255,255,.10),rgba(255,255,255,.04));border:calc(var(--u)*.8) solid var(--line);
  border-radius:calc(var(--u)*12);padding:calc(var(--u)*8);flex-direction:column;font-weight:600}
.k-card.wide{flex-direction:row;justify-content:flex-start;text-align:left;gap:calc(var(--u)*8);padding:0 calc(var(--u)*12)}
.k-card.wide .stack{align-items:flex-start}
.k-card.wide svg.ic{color:var(--accent)}
.k-button{background:#26324a;border:calc(var(--u)*.8) solid rgba(255,255,255,.12);border-radius:calc(var(--u)*12);font-weight:700;padding:0 calc(var(--u)*8)}
.k-button_primary{background:linear-gradient(180deg,#d6fb55,var(--accent));color:var(--accent-ink);border-radius:calc(var(--u)*14);
  font-weight:800;box-shadow:0 calc(var(--u)*4) 0 #7d9a1c,0 calc(var(--u)*8) calc(var(--u)*18) rgba(200,240,60,.25);letter-spacing:.02em;padding:0 calc(var(--u)*8)}
.k-icon_button{background:#1d2840;border:calc(var(--u)*.8) solid var(--line);border-radius:calc(var(--u)*12);flex-direction:column;
  gap:calc(var(--u)*3);font-weight:600;color:var(--ink)}
.k-icon_button .t{font-size:.9em;color:var(--soft)}
.k-pill{background:rgba(0,0,0,.28);border:calc(var(--u)*.8) solid var(--line);font-weight:700;padding:0 calc(var(--u)*3);justify-content:flex-start;gap:calc(var(--u)*3)}
.k-pill .t{flex:1;text-align:center;text-overflow:clip}
.k-pill .plus{width:calc(var(--u)*13);height:calc(var(--u)*13);border-radius:50%;background:var(--accent);color:var(--accent-ink);
  display:flex;align-items:center;justify-content:center;flex:none}
.k-progress{background:#1a2438;border:calc(var(--u)*.8) solid var(--line);overflow:hidden;font-weight:700}
.k-progress .fill{position:absolute;left:0;top:0;bottom:0;background:linear-gradient(90deg,#9fd12b,var(--accent));border-radius:inherit}
.k-progress .t{position:relative;color:#fff;text-shadow:0 1px 2px rgba(0,0,0,.6)}
.k-title{font-weight:800;letter-spacing:.01em}
.k-text{color:var(--soft);font-weight:500}
.k-label{color:var(--muted);font-weight:700;text-transform:uppercase;letter-spacing:.08em}
.k-image{background:repeating-linear-gradient(135deg,rgba(255,255,255,.035) 0 calc(var(--u)*6),rgba(255,255,255,.065) calc(var(--u)*6) calc(var(--u)*12));
  border:calc(var(--u)*.8) dashed rgba(255,255,255,.18);border-radius:calc(var(--u)*12);color:rgba(255,255,255,.35);flex-direction:column;font-weight:600}
.k-image .t{color:var(--soft)}
.k-avatar{background:linear-gradient(160deg,#3a4a6b,#25314a);border:calc(var(--u)*1.2) solid var(--accent);border-radius:50%;color:var(--soft)}
.k-tab{flex-direction:column;gap:calc(var(--u)*3);color:var(--muted);font-weight:600;border-radius:calc(var(--u)*10)}
.k-tab.sel{color:var(--accent);background:rgba(200,240,60,.10)}
.k-tab.sel::after{content:"";position:absolute;bottom:calc(var(--u)*-1);left:30%;right:30%;height:calc(var(--u)*2);background:var(--accent);border-radius:9px}
.k-bar{background:rgba(10,16,30,.85);border-top:calc(var(--u)*.8) solid var(--line);border-bottom:calc(var(--u)*.8) solid var(--line)}
.k-badge{background:#ff4d5e;color:#fff;border-radius:999px;font-weight:800;box-shadow:0 0 0 calc(var(--u)*1.2) #0d1526}
.k-slot{border:calc(var(--u)*.9) dashed rgba(255,255,255,.22);border-radius:calc(var(--u)*10);background:rgba(255,255,255,.03);color:rgba(255,255,255,.35)}
.k-divider{background:var(--line)}
.dot{position:absolute;top:calc(var(--u)*-3);right:calc(var(--u)*-3);min-width:calc(var(--u)*11);height:calc(var(--u)*11);padding:0 calc(var(--u)*3);
  border-radius:999px;background:#ff4d5e;color:#fff;font-size:calc(var(--u)*7);font-weight:800;display:flex;align-items:center;justify-content:center;
  box-shadow:0 0 0 calc(var(--u)*1.2) #0d1526}
.ic-coins{color:#ffc93c}.ic-gem{color:#4fd8ff}.ic-zap{color:#ffe14d}.ic-heart{color:#ff5d73}.ic-star{color:#ffd54a}.ic-ticket{color:#c79bff}
"""
ICON_TINT = {"coins", "gem", "zap", "heart", "star", "ticket"}


def wire_icon(name: str | None, size: float) -> str:
    """Inline SVG for an icon name or alias from assets/wire_icons.json, or '' when unknown."""
    global WIRE_ICONS
    if not name:
        return ""
    if WIRE_ICONS is None:
        path = Path(__file__).resolve().parent.parent / "assets" / "wire_icons.json"
        WIRE_ICONS = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"alias": {}, "icons": {}}
    key = str(name).lower().replace(" ", "-")
    key = WIRE_ICONS["alias"].get(key.replace("-", "_"), key)
    body = WIRE_ICONS["icons"].get(key)
    if not body:
        return ""
    tint = f" ic-{key}" if key in ICON_TINT else ""
    return (f'<svg class="ic{tint}" viewBox="0 0 24 24" width="{size:.0f}" height="{size:.0f}" '
            f'aria-hidden="true">{body}</svg>')


def wire_kind(item: dict) -> str:
    """The wireframe kind of an item: its "wf", else a guess from its element and keys."""
    if item.get("wf"):
        return item["wf"]
    name = (item.get("element") or "").lower()
    base = name.split("/")[-1]
    if "fill" in item or name.startswith("bars/") or "bar" in base and "progress" in base:
        return "progress"
    if name.startswith("buttons/") or base.startswith("btn_"):
        return "button_primary" if any(k in base for k in ("play", "start", "battle", "primary", "buy", "claim", "green")) else "button"
    if name.startswith("icons/") or base.startswith("icon_"):
        return "icon_button"
    if name.startswith(("panels/", "popups/", "frames/", "cards/")):
        return "panel"
    if name.startswith(("characters/", "items/", "art/", "backgrounds/")) or item.get("role") == "art":
        return "image"
    if name:
        return "card"
    size = item.get("text_size") or 0
    return "title" if size >= 56 else "text"


def wire_icon_name(item: dict) -> str | None:
    if item.get("icon"):
        return item["icon"]
    base = (item.get("element") or "").split("/")[-1]
    base = re.sub(r"^(icon|icn|btn|button|ic)_", "", base)
    base = re.sub(r"_(normal|pressed|disabled|selected|\d+)$", "", base)
    return base or None


def wireframe_html(layout: dict, manifest: dict) -> str:
    width, height = layout["size"]
    u = min(width, height) / 360
    background = layout.get("background")
    bg = background if isinstance(background, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", background) else \
        "radial-gradient(120% 70% at 50% 0%,#1d2b4a 0%,#111a2e 55%,#0b1222 100%)"
    parts = []
    for item in layout["items"]:
        name = item.get("element")
        entry = manifest["elements"].get(name) if name else None
        native = (entry["width"], entry["height"]) if entry and entry.get("width") else None
        x0, y0, x1, y1 = item_box(item, native, (width, height))
        w, h = x1 - x0, y1 - y0
        kind = wire_kind(item)
        text = item.get("text")
        text = text if text is not None else (item.get("label") if kind in ("card", "image", "button", "button_primary", "tab", "slot") else None)
        wide = kind == "card" and w > 2.2 * h
        icon_px = {"icon_button": min(w, h) * (0.42 if text else 0.5), "tab": min(w, h) * 0.36, "pill": h * 0.52,
                   "image": min(w, h) * 0.3, "avatar": min(w, h) * 0.5, "slot": min(w, h) * 0.38,
                   "card": h * 0.45 if wide else min(w, h) * 0.32}.get(kind, h * 0.5)
        icon_name = wire_icon_name(item) if kind not in ("text", "title", "label", "progress", "bar", "divider", "badge", "panel") \
            or item.get("icon") else None
        if kind == "image" and not icon_name:
            icon_name = "image"
        if kind == "avatar" and not icon_name:
            icon_name = "user"
        if kind == "pill" and not item.get("icon"):
            icon_name = wire_icon_name(item)
        svg = wire_icon(icon_name, icon_px)
        if not svg and kind in ("image", "avatar"):
            svg = wire_icon("image" if kind == "image" else "user", icon_px)
        if kind in ("icon_button", "slot") and not svg and not text:
            text = item.get("label") or (name.split("/")[-1] if name else "")
        size = item.get("text_size") or {
            "title": h * 0.62, "text": h * 0.5, "label": h * 0.55, "button_primary": min(h * 0.38, w * 0.16),
            "button": min(h * 0.36, w * 0.14), "pill": h * 0.4, "progress": h * 0.5, "tab": min(w, h) * 0.17,
            "icon_button": min(w, h) * 0.15, "badge": h * 0.6, "card": h * 0.28 if wide else min(w, h) * 0.12,
            "image": min(w, h) * 0.06,
            "slot": min(w, h) * 0.14}.get(kind, h * 0.4)
        align = item.get("align") or ("left" if kind in ("title", "text", "label") and item.get("anchor", "top_left").endswith("left")
                                       else "center")
        style = [f"left:{x0}px", f"top:{y0}px", f"width:{w}px", f"height:{h}px", f"font-size:{size:.1f}px"]
        if kind in ("pill", "progress", "badge"):
            style.append(f"border-radius:{h / 2:.0f}px")
        if item.get("text_color"):
            style.append(f"color:{item['text_color']}")
        if item.get("opacity") is not None:
            style.append(f"opacity:{item['opacity']}")
        classes = f"i k-{kind} al-{align}" + (" sel" if item.get("selected") else "") + (" wide" if wide else "")
        inner = []
        if kind == "progress":
            inner.append(f'<div class="fill" style="width:{max(0.0, min(1.0, item.get("fill", 0.6))) * 100:.1f}%"></div>')
        if svg:
            inner.append(svg)
        if text not in (None, ""):
            label = html.escape(str(text))
            sub = f'<span class="sub">{html.escape(str(item["sub"]))}</span>' if item.get("sub") else ""
            inner.append(f'<span class="stack"><span class="t">{label}</span>{sub}</span>' if sub else f'<span class="t">{label}</span>')
        if kind == "pill" and item.get("goto") is not None or kind == "pill" and item.get("badge") == "+":
            inner.append(f'<span class="plus" style="width:{h * 0.6:.0f}px;height:{h * 0.6:.0f}px">{wire_icon("plus", h * 0.4)}</span>')
        elif item.get("badge") not in (None, "", False):
            badge = "" if item["badge"] is True else html.escape(str(item["badge"]))
            inner.append(f'<span class="dot">{badge}</span>')
        parts.append(f'<div class="{classes}" style="{";".join(style)}">{"".join(inner)}</div>')
    css = WIRE_CSS.replace("__W__", str(width)).replace("__H__", str(height)).replace("__U__", f"{u:.3f}").replace("__BG__", bg)
    return (f'<!doctype html><html lang="vi"><head><meta charset="utf-8"><style>{css}</style></head>'
            f'<body>{"".join(parts)}</body></html>')


def find_browser() -> str | None:
    """A Chromium-based browser that can take headless screenshots: Edge, Chrome or Chromium."""
    import os
    candidates = [os.environ.get("UIKIT_BROWSER")]
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")):
        if base:
            candidates += [f"{base}/Microsoft/Edge/Application/msedge.exe", f"{base}/Google/Chrome/Application/chrome.exe"]
    candidates += ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                   "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                   "/Applications/Chromium.app/Contents/MacOS/Chromium"]
    candidates += [shutil.which(n) for n in ("msedge", "microsoft-edge", "google-chrome", "chromium", "chromium-browser", "chrome")]
    return next((c for c in candidates if c and Path(c).exists()), None)


def screenshot_html(page: str, size: tuple[int, int], out: Path) -> bool:
    """Render an HTML page to a PNG of exactly this size with a headless browser. False when none works."""
    import tempfile
    browser = find_browser()
    if not browser:
        return False
    with tempfile.TemporaryDirectory(prefix="uikit_wire_") as tmp:
        page_path = Path(tmp) / "page.html"
        page_path.write_text(page, encoding="utf-8")
        shot = Path(tmp) / "shot.png"
        command = [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                   "--no-default-browser-check", "--disable-extensions", "--force-device-scale-factor=1",
                   f"--user-data-dir={Path(tmp) / 'profile'}", f"--window-size={size[0]},{size[1]}",
                   f"--screenshot={shot}", "--virtual-time-budget=2000", page_path.as_uri()]
        try:
            subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
        except (OSError, subprocess.TimeoutExpired):
            return False
        if not shot.exists():
            return False
        image = Image.open(shot).convert("RGB")
        if image.size != tuple(size):
            image = image.crop((0, 0, min(image.width, size[0]), min(image.height, size[1])))
            if image.size != tuple(size):
                return False
        out.parent.mkdir(parents=True, exist_ok=True)
        image.save(out)
    return True


def render_wireframe_basic(layout: dict, manifest: dict, kit: Path, out: Path) -> None:
    """Plain fallback when no browser is available: rounded boxes with labels, no flow text."""
    size = tuple(layout["size"])
    image = Image.new("RGB", size, (17, 26, 46))
    draw = ImageDraw.Draw(image)
    scale = min(size) / 360
    for item in layout["items"]:
        name = item.get("element")
        entry = manifest["elements"].get(name) if name else None
        native = (entry["width"], entry["height"]) if entry and entry.get("width") else None
        x0, y0, x1, y1 = item_box(item, native, size)
        kind = wire_kind(item)
        if kind not in ("text", "title", "label"):
            fill = (200, 240, 60) if kind == "button_primary" else (38, 50, 74)
            draw.rounded_rectangle([x0, y0, x1, y1], radius=round(10 * scale), fill=fill, outline=(70, 84, 110))
            if kind == "progress":
                draw.rounded_rectangle([x0, y0, x0 + (x1 - x0) * item.get("fill", 0.6), y1], radius=round(10 * scale), fill=(170, 220, 50))
        label = item.get("text") or item.get("label") or ""
        if label:
            font = load_font(max(10, round(min((y1 - y0) * 0.4, 18 * scale))), resolve_font(kit, layout)[0])
            draw.text(((x0 + x1) / 2, (y0 + y1) / 2), str(label), font=font, anchor="mm",
                      fill=(23, 33, 10) if kind == "button_primary" else (235, 240, 250))
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out)


WIRE_WARNINGS: list[str] = []


def render_wireframe(kit: Path, path: Path, manifest: dict) -> Path:
    layout = read_layout(path)
    out = kit / "preview" / "wireframes" / f"{path.stem}.png"
    if not screenshot_html(wireframe_html(layout, manifest), tuple(layout["size"]), out):
        WIRE_WARNINGS.append("NO_BROWSER: Edge or Chrome was not found or failed, so a plain wireframe was drawn")
        render_wireframe_basic(layout, manifest, kit, out)
    return out


def cmd_wireframe(args) -> int:
    kit = Path(args.kit)
    manifest = load_manifest(kit)
    paths = layout_paths(kit, args.screen)
    if not paths:
        die("NO_LAYOUT", f"write a layout in {kit / 'mockups'} first", 1)
    for path in paths:
        read_layout(path)
    print(f"Planned: {plan_text(paths)} as wireframes. No image generation is used.")
    for path in paths:
        print(render_wireframe(kit, path, manifest).relative_to(kit).as_posix())
    for warning in sorted(set(WIRE_WARNINGS)):
        print(f"WARNING {warning}")
    return 0


DEMO_HTML = """<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{color-scheme:dark}*{box-sizing:border-box}
body{margin:0;background:#14161b;color:#eceef2;font:15px/1.4 system-ui,sans-serif;display:flex;flex-direction:column;height:100vh}
header{display:flex;gap:8px;align-items:center;padding:8px 12px;flex-wrap:wrap}
#name{font-weight:600;margin-right:auto}
button{background:#2a2e37;color:inherit;border:1px solid #454b58;border-radius:6px;padding:6px 10px;font:inherit;cursor:pointer}
button:disabled{opacity:.45;cursor:default}
main{flex:1;min-height:0;display:flex;align-items:center;justify-content:center;padding:0 12px 12px}
#stage{position:relative;max-width:100%;max-height:100%}
#stage img{display:block;max-width:100%;max-height:calc(100vh - 70px)}
.hot{position:absolute;background:transparent;border:0;border-radius:4px;padding:0}
.show .hot{outline:2px solid #4c8dff;background:#4c8dff33}
</style></head><body>
<header><span id="name"></span><button id="back">Quay lại</button><button id="restart">Từ đầu</button><button id="hints">Hiện vùng bấm</button></header>
<main><div id="stage"><img id="shot" alt=""></div></main>
<script>
const DATA=__DATA__;
const stage=document.getElementById("stage"),shot=document.getElementById("shot"),nameBox=document.getElementById("name"),backBtn=document.getElementById("back");
let trail=[];
function show(id,remember){
  const s=DATA.screens[id];if(!s)return;
  if(remember&&DATA.current)trail.push(DATA.current);
  DATA.current=id;shot.src=s.image;shot.alt=s.title;nameBox.textContent=s.title;backBtn.disabled=!trail.length;
  stage.querySelectorAll(".hot").forEach(e=>e.remove());
  for(const h of s.links){
    const b=document.createElement("button");b.className="hot";b.title=h.label;b.setAttribute("aria-label",h.label);
    b.style.left=h.x+"%";b.style.top=h.y+"%";b.style.width=h.w+"%";b.style.height=h.h+"%";
    b.onclick=()=>h.to==="back"?goBack():show(h.to,true);stage.appendChild(b);
  }
}
function goBack(){if(trail.length){const id=trail.pop();show(id,false);backBtn.disabled=!trail.length;}}
backBtn.onclick=goBack;
document.getElementById("restart").onclick=()=>{trail=[];show(DATA.start,false);};
document.getElementById("hints").onclick=()=>stage.classList.toggle("show");
show(DATA.start,false);
</script></body></html>
"""


def flow_graph(layouts: dict[str, dict], manifest: dict) -> list[dict]:
    edges = []
    for screen, layout in layouts.items():
        size = tuple(layout["size"])
        for item in layout["items"]:
            if "goto" not in item:
                continue
            name = item.get("element")
            entry = manifest["elements"].get(name) if name else None
            native = (entry["width"], entry["height"]) if entry and entry.get("width") else None
            box = item_box(item, native, size)
            label = item.get("label") or item.get("text") or (name.split("/")[-1] if name else item["goto"])
            edges.append({"from": screen, "to": item["goto"], "label": str(label), "box": box})
    return edges


def flow_board(images: dict[str, Image.Image], levels: dict[str, int], edges: list[dict], titles: dict[str, str],
               cell=(320, 240)) -> Image.Image:
    columns: dict[int, list[str]] = {}
    for name in images:
        columns.setdefault(levels.get(name, max(levels.values(), default=0) + 1), []).append(name)
    order = sorted(columns)
    rows = max(len(names) for names in columns.values())
    gap_x, gap_y, top = 110, 56, 20
    board = Image.new("RGB", (len(order) * (cell[0] + gap_x) + 30, rows * (cell[1] + gap_y) + top + 20), (245, 246, 248))
    draw = ImageDraw.Draw(board)
    font = load_font(16, None)
    small = load_font(13, None)
    spots = {}
    for c, level in enumerate(order):
        for r, name in enumerate(columns[level]):
            x, y = 20 + c * (cell[0] + gap_x), top + r * (cell[1] + gap_y)
            thumb = images[name].copy()
            thumb.thumbnail(cell)
            board.paste(thumb, (x, y + 24))
            draw.text((x, y), titles.get(name, name), fill=(20, 20, 20), font=font)
            spots[name] = (x, y + 24, x + thumb.width, y + 24 + thumb.height)
    for edge in edges:
        if edge["to"] not in spots or edge["to"] == edge["from"]:
            continue
        a, b = spots[edge["from"]], spots[edge["to"]]
        forward = a[2] <= b[0]
        start = (a[2], (a[1] + a[3]) // 2) if forward else (a[0], (a[1] + a[3]) // 2 + 14)
        end = (b[0], (b[1] + b[3]) // 2) if forward else (b[2], (b[1] + b[3]) // 2 + 14)
        color = (40, 90, 220) if forward else (150, 90, 200)
        draw.line([start, end], fill=color, width=2)
        vector = np.array(end, dtype=float) - np.array(start, dtype=float)
        length = max(1.0, float(np.hypot(*vector)))
        unit = vector / length
        side = np.array([-unit[1], unit[0]])
        tip = np.array(end, dtype=float)
        draw.polygon([tuple(tip), tuple(tip - unit * 10 + side * 5), tuple(tip - unit * 10 - side * 5)], fill=color)
        middle = ((start[0] + end[0]) // 2, (start[1] + end[1]) // 2 - 10)
        draw.text(middle, edge["label"][:22], fill=color, font=small, anchor="mm", stroke_width=2, stroke_fill=(245, 246, 248))
    return board


def cmd_flow(args) -> int:
    kit = Path(args.kit)
    manifest = load_manifest(kit)
    picked = selected_layouts(kit, strict=False)
    layouts = {name: read_layout(path) for name, path in picked.items()}
    start = args.start or next((n for n in DEFAULT_SCREENS if n in layouts), next(iter(layouts)))
    if start not in layouts:
        die("NOT_FOUND", f"start screen {start} is not one of {sorted(layouts)}", 1)
    edges = flow_graph(layouts, manifest)

    levels, queue = {start: 0}, [start]
    while queue:
        current = queue.pop(0)
        for edge in edges:
            if edge["from"] == current and edge["to"] in layouts and edge["to"] not in levels:
                levels[edge["to"]] = levels[current] + 1
                queue.append(edge["to"])
    broken = [f"{e['from']} > {e['to']} ({e['label']})" for e in edges if e["to"] != "back" and e["to"] not in layouts]
    unreachable = [n for n in layouts if n not in levels]
    dead_ends = [n for n in layouts if not any(e["from"] == n for e in edges)]

    images, screens = {}, {}
    missing = set()
    for name, path in picked.items():
        if args.wireframe:
            image = Image.open(render_wireframe(kit, path, manifest)).convert("RGB")
        else:
            result = render_mockup(kit, path, manifest)
            missing |= set(result["missing"])
            image = Image.open(kit / result["image"]).convert("RGB")
        images[name] = image
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=90)
        width, height = image.size
        links = [{"x": round(e["box"][0] / width * 100, 3), "y": round(e["box"][1] / height * 100, 3),
                  "w": round((e["box"][2] - e["box"][0]) / width * 100, 3),
                  "h": round((e["box"][3] - e["box"][1]) / height * 100, 3),
                  "to": e["to"], "label": e["label"]}
                 for e in edges if e["from"] == name and (e["to"] in layouts or e["to"] == "back")]
        screens[name] = {"title": layouts[name].get("title", name), "links": links,
                         "image": "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")}

    titles = {n: layouts[n].get("title", n) for n in layouts}
    board = flow_board(images, levels, edges, titles)
    flow_out = kit / "preview" / "flow.png"
    flow_out.parent.mkdir(parents=True, exist_ok=True)
    board.save(flow_out)

    data = json.dumps({"start": start, "screens": screens}, ensure_ascii=False).replace("</", "<\\/")
    demo = kit / "demo" / "index.html"
    demo.parent.mkdir(parents=True, exist_ok=True)
    title = html.escape(kit.resolve().name)
    demo.write_text(DEMO_HTML.replace("__TITLE__", title).replace("__DATA__", data), encoding="utf-8")

    report = {"start": start, "screens": sorted(layouts), "links": len(edges), "broken_links": broken,
              "unreachable": unreachable, "dead_ends": dead_ends, "missing_elements": sorted(missing),
              "uses_first_variant": [n for n in picked if len(layout_paths(kit, n)) > 1 and n not in read_chosen(kit)],
              "board": "preview/flow.png", "demo": "demo/index.html"}
    (kit / "flow_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 2 if broken else 0


def psd_block(key: bytes, data: bytes) -> bytes:
    data += b"\0" * (-len(data) % 4)
    return b"8BIM" + key + struct.pack(">I", len(data)) + data


def psd_record(name: str, layer: dict | None, section: int | None = None, hidden: bool = False):
    """Build one PSD layer record and its channel data."""
    encoded = name.encode("ascii", "replace")[:31]
    pascal = bytes([len(encoded)]) + encoded
    pascal += b"\0" * (-len(pascal) % 4)
    unicode_name = struct.pack(">I", len(name)) + name.encode("utf-16-be")
    blocks = psd_block(b"luni", unicode_name)
    if section is not None:
        blocks += psd_block(b"lsct", struct.pack(">I", section) + b"8BIM" + (b"pass" if section == 1 else b"norm"))
    extra = struct.pack(">II", 0, 0) + pascal + blocks

    if layer is None:
        top = left = bottom = right = 0
        channels = [b"", b"", b"", b""]
    else:
        pixels = np.asarray(layer["image"].convert("RGBA"))
        top, left = layer["y"], layer["x"]
        bottom, right = top + pixels.shape[0], left + pixels.shape[1]
        channels = [pixels[..., 3].tobytes(), pixels[..., 0].tobytes(), pixels[..., 1].tobytes(), pixels[..., 2].tobytes()]
    record = struct.pack(">iiiiH", top, left, bottom, right, 4)
    for channel_id, channel in zip((-1, 0, 1, 2), channels):
        record += struct.pack(">hI", channel_id, len(channel) + 2)
    flags = 0x08 | (0x10 if section is not None else 0) | (0x02 if hidden else 0)
    record += b"8BIM" + b"norm" + struct.pack(">BBBB", 255, 0, flags, 0)
    record += struct.pack(">I", len(extra)) + extra
    data = b"".join(struct.pack(">H", 0) + channel for channel in channels)
    return record, data


def write_psd(path: Path, size: tuple[int, int], layers: list[dict], merged: Image.Image) -> int:
    """Write an 8-bit RGB PSD with named layers and groups. Layer order is bottom to top."""
    records = []
    current = None
    for layer in layers + [None]:
        group = layer.get("group") if layer else None
        if current and group != current:
            records.append(psd_record(current, None, section=1))
        if group and group != current:
            records.append(psd_record("</Layer group>", None, section=3))
        current = group
        if layer:
            records.append(psd_record(layer["name"], layer, hidden=layer.get("hidden", False)))
    body = struct.pack(">h", len(records)) + b"".join(r for r, _ in records) + b"".join(d for _, d in records)
    body += b"\0" * (len(body) % 2)
    layer_info = struct.pack(">I", len(body)) + body
    layer_mask = layer_info + struct.pack(">I", 0)
    width, height = size
    planes = np.asarray(merged.convert("RGB"))
    with open(path, "wb") as out:
        out.write(b"8BPS" + struct.pack(">H", 1) + b"\0" * 6 + struct.pack(">HIIHH", 3, height, width, 8, 3))
        out.write(struct.pack(">I", 0) + struct.pack(">I", 0))
        out.write(struct.pack(">I", len(layer_mask)) + layer_mask)
        out.write(struct.pack(">H", 0))
        for channel in range(3):
            out.write(planes[..., channel].tobytes())
    return len(records)


def cmd_export(args) -> int:
    kit = Path(args.kit)
    manifest = load_manifest(kit)
    picked = export_targets(kit, args)
    built = {}
    for screen, path in picked.items():
        layout = read_layout(path)
        layers, warnings, missing, _ = build_layers(kit, layout, manifest)
        if missing:
            die("MISSING_ELEMENT", f"{screen} uses missing elements {missing}. Fix the layout before exporting.")
        built[screen] = (layout, layers, warnings)

    psd_dir, png_dir = kit / "export" / "psd", kit / "export" / "png"
    png_only = getattr(args, "png_only", False)
    targets = ([] if png_only else [psd_dir / f"{s}.psd" for s in built]) + [png_dir / f"{s}.png" for s in built]
    existing = [t.name for t in targets if t.exists()]
    if existing and not args.force:
        die("EXISTS", f"{existing} already exist. Pass --force only if replacing them was requested.", 1)
    if not png_only:
        psd_dir.mkdir(parents=True, exist_ok=True)
    png_dir.mkdir(parents=True, exist_ok=True)

    report = {}
    for screen, (layout, layers, warnings) in built.items():
        size = tuple(layout["size"])
        merged = flatten(layers, size)
        merged.save(png_dir / f"{screen}.png")
        if png_only:
            report[screen] = {"png": f"export/png/{screen}.png", "layout": picked[screen].stem, "warnings": warnings}
            print(f"{screen}: export/png/{screen}.png from {picked[screen].stem}")
            continue
        full = list(layers)
        reference = kit / layout["reference"] if layout.get("reference") else None
        if reference and reference.exists():
            image = Image.open(reference).convert("RGBA").resize(size, Image.LANCZOS)
            full.insert(0, {"name": "Reference (hidden)", "image": image, "x": 0, "y": 0, "hidden": True, "group": None})
        count = write_psd(psd_dir / f"{screen}.psd", size, full, merged)
        texts = sum(1 for layer in layers if layer["name"].startswith("Text: "))
        report[screen] = {"psd": f"export/psd/{screen}.psd", "png": f"export/png/{screen}.png",
                          "layout": picked[screen].stem, "layers": count, "text_layers_as_pixels": texts,
                          "warnings": warnings}
        print(f"{screen}: export/psd/{screen}.psd from {picked[screen].stem}, {count} layers, "
              f"{texts} text layers as pixels, {len(warnings)} warnings")
    (kit / "export" / "export_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Exported {len(report)} screens." + ("" if png_only else " Text layers are pixels, not editable type."))
    return 0


def cmd_info(args) -> int:
    kit = Path(args.kit)
    if not (kit / "manifest.json").exists() and not (kit / "mockups").exists():
        die("NOT_FOUND", f"{kit} is not a kit yet", 1)
    manifest = load_manifest(kit)
    elements = manifest["elements"]
    families: dict[str, int] = {}
    for name in elements:
        family = name.split("/")[0] if "/" in name else "(root)"
        families[family] = families.get(family, 0) + 1
    nine = {"suggested": 0, "needs_review": 0}
    for entry in elements.values():
        status = (entry.get("nine_slice") or {}).get("status")
        if status in nine:
            nine[status] += 1
    def read(name):
        path = kit / name
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    qa, compare = read("qa_report.json"), read("compare_report.json")
    chosen = read_chosen(kit)
    screens: dict[str, list[str]] = {}
    for path in layout_paths(kit):
        screens.setdefault(screen_of(path.stem), []).append(path.stem)
    undecided = [s for s, stems in screens.items() if len(stems) > 1 and s not in chosen]
    good, stale = confirmed_screens(kit)
    wire_ok, wire_changed = wireframe_confirmed(kit) if screens else (False, [])
    exports = sorted(p.stem for p in (kit / "export" / "psd").glob("*.psd"))
    brief = read("briefs/setup.json")
    has_demo = (kit / "demo" / "index.html").exists()
    exported = sorted(p.stem for p in (kit / "export").rglob("*") if p.suffix in (".psd", ".png", ".json")
                      and p.parent.name in ("psd", "png", "unity"))
    mocked = [p.stem for p in (kit / "preview" / "mockups").glob("*.png")] if (kit / "preview" / "mockups").exists() else []
    if not brief:
        step = "Run $setup."
    elif not screens:
        step = "Run $wireframe, or $mockup with your own wireframe files."
    elif not mocked:
        step = "Run $mockup."
    elif not exported:
        step = "Run $mockup and answer Có to Export."
    else:
        step = "Exported. Run $mockup again to change or add screens."
    info = {
        "kit": kit.resolve().name,
        "elements": {"total": len(elements), "families": dict(sorted(families.items())),
                     "generated": sum(1 for e in elements.values() if not e.get("imported_from") and not e.get("derived_from")),
                     "imported": sum(1 for e in elements.values() if e.get("imported_from") and not e.get("derived_from")),
                     "derived_states": sum(1 for e in elements.values() if e.get("derived_from"))},
        "nine_slice": nine,
        "screens": {s: {"mockups": len(stems), "chosen": chosen.get(s) or (stems[0] if len(stems) == 1 else None)}
                    for s, stems in screens.items()},
        "total_mockups": sum(len(stems) for stems in screens.values()),
        "qa": {"errors": len(qa["errors"]), "warnings": len(qa["warnings"])} if qa else "not run",
        "compare": {"review": len(compare["review"])} if compare else "not run",
        "tone": read_palette(kit) or "not locked",
        "fonts": [p.name for p in kit_fonts(kit)] or "none, system font in use",
        "wireframe_confirmed": wire_ok, "wireframe_changed": wire_changed,
        "confirmed_screens": sorted(good), "changed_since_confirmed": sorted(stale),
        "setup": {"game_type": brief.get("game_type"), "size": brief.get("size")} if brief else "not done",
        "flow_demo": has_demo,
        "exported_psd": exports,
        "next_step": step,
    }
    print(json.dumps(info, indent=2, ensure_ascii=True))
    return 0


FAMILY_FUNCTION = {"buttons": "btn", "icons": "icon", "hud": "icon", "menu": "icon", "navigation": "icon",
                   "currency": "set", "shop": "icon", "controls": "btn", "panels": "popup", "popups": "popup",
                   "titles": "title", "bars": "bar", "frames": "frame", "rewards": "reward", "shapes": "shape",
                   "tabs": "tab", "slots": "slot", "badges": "badge", "patterns": "pattern",
                   "backdrops": "bg", "backgrounds": "bg", "characters": "char", "items": "item"}
NAME_PREFIXES = ("btn", "popup", "title", "bg", "pattern", "icon", "set", "shape", "reward", "loading_bar",
                 "frame", "tab", "bar", "slot", "badge", "char", "item")
PSD_NAME_RE = re.compile(r"^[a-z]+(_[a-z0-9]+)+$")
DEFAULT_CANVAS = (1920, 1080)
ART_NAME_RE = re.compile(r"(^|[/_])(characters?|char|avatars?|heroes|hero|npcs?|enem(y|ies)|monsters?|pets?|mounts?|"
                         r"bg|backgrounds?|backdrops?|env|environments?|worlds?|scenes?|terrain|props?|illustrations?)($|[/_])")


def is_art(name: str, item: dict) -> bool:
    """UI is redrawn by default. Characters, backgrounds and environments need the user's approval."""
    role = item.get("role")
    return role == "art" if role else bool(ART_NAME_RE.search(name))


def slug(text: str) -> str:
    return normalize_name(Path(str(text))).replace("/", "_") or "item"


def kit_layer_name(entry: dict | None) -> str | None:
    """The original file name of a sprite imported from the user's kit, without its extension."""
    if not entry or not entry.get("imported_from"):
        return None
    return Path(entry["imported_from"]).stem


def element_layer_name(name: str) -> str:
    """Build a (function)_(description) name from an element path."""
    family, _, leaf = name.rpartition("/")
    function = FAMILY_FUNCTION.get(family.split("/")[-1], family.split("/")[-1].rstrip("s") or "item")
    leaf = slug(leaf)
    if any(leaf == prefix or leaf.startswith(f"{prefix}_") for prefix in NAME_PREFIXES):
        return leaf
    return f"{function}_{leaf}"


def trace_contours(mask: np.ndarray) -> list[list[tuple[int, int]]]:
    """Follow pixel-edge boundaries of a mask into closed loops, in image coordinates."""
    padded = np.pad(mask, 1)
    h, w = mask.shape
    links: dict[tuple[int, int], list[tuple[int, int]]] = {}

    def add(ys, xs, a, b):
        for y, x in zip(ys.tolist(), xs.tolist()):
            links.setdefault((x + a[0], y + a[1]), []).append((x + b[0], y + b[1]))

    core = padded[1:-1, 1:-1]
    add(*np.nonzero(core & ~padded[:-2, 1:-1]), (0, 0), (1, 0))
    add(*np.nonzero(core & ~padded[1:-1, 2:]), (1, 0), (1, 1))
    add(*np.nonzero(core & ~padded[2:, 1:-1]), (1, 1), (0, 1))
    add(*np.nonzero(core & ~padded[1:-1, :-2]), (0, 1), (0, 0))
    loops = []
    while links:
        start = next(iter(links))
        loop, point = [start], links[start].pop()
        if not links[start]:
            del links[start]
        while point != start:
            loop.append(point)
            options = links[point]
            following = options.pop()
            if not options:
                del links[point]
            point = following
        loops.append(loop)
    return loops


def simplify(points: list[tuple[float, float]], epsilon: float) -> list[tuple[float, float]]:
    """Ramer-Douglas-Peucker on a closed loop, keeping two far-apart anchors."""
    if len(points) < 8:
        return points
    array = np.array(points, dtype=float)
    far = int(((array - array[0]) ** 2).sum(axis=1).argmax())

    def reduce(section: np.ndarray) -> list[int]:
        keep, stack = [0, len(section) - 1], [(0, len(section) - 1)]
        while stack:
            a, b = stack.pop()
            if b <= a + 1:
                continue
            line = section[b] - section[a]
            length = max(1e-9, float(np.hypot(*line)))
            middle = section[a + 1:b] - section[a]
            distance = np.abs(line[0] * middle[:, 1] - line[1] * middle[:, 0]) / length
            index = int(distance.argmax())
            if distance[index] > epsilon:
                index += a + 1
                keep.append(index)
                stack += [(a, index), (index, b)]
        return sorted(set(keep))

    first = array[: far + 1]
    second = np.concatenate([array[far:], array[:1]])
    return [tuple(first[i]) for i in reduce(first)[:-1]] + [tuple(second[i]) for i in reduce(second)[:-1]]


def polygon_area(points) -> float:
    array = np.array(points, dtype=float)
    return abs(float(np.dot(array[:, 0], np.roll(array[:, 1], 1)) - np.dot(array[:, 1], np.roll(array[:, 0], 1)))) / 2


def raster_shapes(shapes: list[dict], size: tuple[int, int], factor: int = 3) -> np.ndarray:
    """Draw traced shapes with even-odd fill, to score them against the source sprite."""
    w, h = size
    canvas = Image.new("RGBA", (w * factor, h * factor), (0, 0, 0, 0))
    for shape in shapes:
        mask = Image.new("1", canvas.size, 0)
        for subpath in shape["subpaths"]:
            piece = Image.new("1", canvas.size, 0)
            ImageDraw.Draw(piece).polygon([(x * factor, y * factor) for x, y in subpath], fill=1)
            mask = ImageChops.logical_xor(mask, piece)
        canvas.paste(tuple(shape["color"]) + (255,), (0, 0), mask)
    return np.asarray(canvas.resize((w, h), Image.BOX)).astype(float)


def score_shapes(source: np.ndarray, drawn: np.ndarray) -> float:
    """Mean perceptual difference over visible pixels. Below about 6 is hard to notice."""
    visible = (source[..., 3] > 16) | (drawn[..., 3] > 16)
    if not visible.any():
        return 0.0
    def on_gray(p):
        return p[..., :3] * (p[..., 3:] / 255) + 128 * (1 - p[..., 3:] / 255)
    a = rgb_to_lab(on_gray(source)[visible])
    b = rgb_to_lab(on_gray(drawn)[visible])
    return float(np.sqrt(((a - b) ** 2).sum(axis=1)).mean())


def trace_sprite(path: Path, max_layers: int, max_points: int, limit: int = 384) -> tuple[list[dict], tuple[int, int], float, tuple[int, int]]:
    """Trace a sprite into stacked flat-color shapes, with more colors until it scores well."""
    img = Image.open(path).convert("RGBA")
    native = img.size
    if max(img.size) > limit:
        img.thumbnail((limit, limit), Image.LANCZOS)
    size = img.size
    source = np.asarray(img).astype(float)
    solid = source[..., 3] >= 128
    if not solid.any():
        return [], size, 0.0, native
    scale = native[0] / size[0]
    best = None
    for colors in (6, 10, 16, 24):
        colors = min(colors, max_layers)
        strip = Image.fromarray(source[..., :3].astype(np.uint8), "RGB")
        quantized = strip.quantize(colors=colors, method=Image.FASTOCTREE)
        table = np.array(quantized.getpalette()[: colors * 3]).reshape(-1, 3)
        index = np.asarray(quantized)
        counts = np.bincount(index[solid], minlength=len(table))
        order = [int(i) for i in np.argsort(-counts) if counts[i] > 0]
        rank = np.full(len(table), len(order), dtype=int)
        for r, i in enumerate(order):
            rank[i] = r
        ranks = rank[index]
        shapes, points = [], 0
        for r, color_index in enumerate(order):
            mask = solid & (ranks >= r)
            loops = [simplify(loop, 0.8) for loop in trace_contours(mask)]
            loops = [loop for loop in loops if len(loop) >= 3 and polygon_area(loop) >= 3]
            if loops:
                shapes.append({"color": [int(c) for c in table[color_index]], "subpaths": loops})
                points += sum(len(loop) for loop in loops)
        score = score_shapes(source, raster_shapes(shapes, size))
        candidate = (shapes, score, points)
        if points <= max_points and (best is None or score < best[1]):
            best = candidate
        if colors == max_layers or (best and score <= 5):
            break
    if best is None:
        return [], size, 99.0, native
    shapes = [{"color": s["color"], "subpaths": [[[round(x * scale, 2), round(y * scale, 2)] for x, y in loop] for loop in s["subpaths"]]} for s in best[0]]
    return shapes, native, best[1], native


def vector_path(kit: Path, name: str) -> Path:
    return kit / "style" / "vector" / f"{name}.json"


def vectorize_element(kit: Path, name: str, entry: dict, args) -> dict:
    out = vector_path(kit, name)
    if out.exists() and not args.force:
        return json.loads(out.read_text(encoding="utf-8"))
    shapes, size, score, native = trace_sprite(kit / entry["file"], args.max_layers, args.max_points)
    kind = "vector" if shapes and score <= args.max_difference else "raster"
    spec = {"element": name, "kind": kind, "score": round(score, 2), "size": list(native), "shapes": shapes if kind == "vector" else []}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(spec), encoding="utf-8")
    return spec


def recipe_board(source: Image.Image, drawn: Image.Image, score: float, name: str) -> Image.Image:
    """Source, shape rebuild and difference side by side, for judging a recipe by eye."""
    height = 300
    scale = height / max(1, source.height)
    size = (max(1, round(source.width * scale)), height)
    a = on_checker(source.resize(size, Image.LANCZOS)).convert("RGB")
    b = on_checker(drawn.resize(size, Image.LANCZOS)).convert("RGB")
    diff = np.abs(np.asarray(a).astype(int) - np.asarray(b).astype(int)).sum(axis=2)
    heat = Image.fromarray(np.clip(diff * 2, 0, 255).astype(np.uint8)).convert("RGB")
    gap, top = 16, 34
    board = Image.new("RGB", (size[0] * 3 + gap * 4, height + top + gap), (245, 246, 248))
    draw = ImageDraw.Draw(board)
    font = load_font(15, None)
    for i, (image, label) in enumerate(((a, "Ảnh gốc"), (b, "Shape + effect"), (heat, f"Khác biệt: {score:.1f}"))):
        x = gap + i * (size[0] + gap)
        board.paste(image, (x, top))
        draw.text((x, 9), label, fill=(20, 20, 20), font=font)
    draw.text((board.width - gap, 9), name, fill=(110, 110, 120), font=font, anchor="ra")
    return board


def cmd_recipe(args) -> int:
    """Write, check and preview shape recipes, the editable rebuild of each sprite for the PSD."""
    kit = Path(args.kit)
    manifest = load_manifest(kit)
    names = selected(manifest, args.match) if args.match else list(manifest["elements"])
    if not names:
        die("NO_MATCH", "no elements matched", 1)
    report_path = kit / "recipes_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
    tally = {"good": 0, "check": 0, "none": 0}
    for name in names:
        entry = manifest["elements"][name]
        path = recipes.recipe_path(kit, name)
        if args.auto and (not path.exists() or args.force):
            guess = recipes.auto_recipe(kit / entry["file"], name)
            if guess.get("status") == "AUTO":
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(guess, indent=1, ensure_ascii=False), encoding="utf-8")
            elif not path.exists():
                report[name] = {"status": guess.get("status"), "fit": guess.get("fit")}
                print(f"{name}: {guess.get('status')}, not a simple shape; write its recipe by hand or it stays traced or an image")
                tally["none"] += 1
                continue
        if not path.exists():
            print(f"{name}: no recipe")
            tally["none"] += 1
            continue
        try:
            recipe = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            print(f"{name}: BAD_RECIPE {exc}")
            tally["none"] += 1
            continue
        problems = recipes.check_recipe(recipe)
        if problems:
            print(f"{name}: BAD_RECIPE " + "; ".join(problems))
            report[name] = {"status": "BAD_RECIPE", "problems": problems}
            tally["none"] += 1
            continue
        source = Image.open(kit / entry["file"]).convert("RGBA")
        if list(source.size) != list(recipe["size"]):
            print(f"{name}: recipe size {recipe['size']} differs from the sprite {list(source.size)}")
        drawn = recipes.render_recipe(recipe).resize(source.size, Image.LANCZOS)
        score = score_shapes(np.asarray(source).astype(float), np.asarray(drawn).astype(float))
        board = kit / "preview" / "recipes" / f"{name}.png"
        board.parent.mkdir(parents=True, exist_ok=True)
        recipe_board(source, drawn, score, name).save(board)
        verdict = "good" if score <= args.max_difference else "check"
        tally[verdict] += 1
        count = sum(1 for _ in walk_recipe_layers(recipe["layers"]))
        report[name] = {"status": verdict.upper(), "difference": round(score, 2), "layers": count,
                        "board": board.relative_to(kit).as_posix()}
        print(f"{name}: {verdict.upper()}, difference {score:.1f}, {count} shape layers, view {board.relative_to(kit).as_posix()}")
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{tally['good']} close to the source, {tally['check']} to improve, {tally['none']} without a recipe.")
    return 0


def walk_recipe_layers(layers):
    for layer in layers:
        if "group" in layer:
            yield from walk_recipe_layers(layer.get("layers") or [])
        else:
            yield layer


def cmd_vectorize(args) -> int:
    kit = Path(args.kit)
    manifest = load_manifest(kit)
    names = selected(manifest, args.match) if args.match else list(manifest["elements"])
    if not names:
        die("NO_MATCH", "no elements to vectorize", 1)
    tally = {"vector": 0, "raster": 0}
    for name in names:
        spec = vectorize_element(kit, name, manifest["elements"][name], args)
        tally[spec["kind"]] += 1
        print(f"{name}: {spec['kind']}, difference {spec['score']}, {len(spec['shapes'])} shapes")
    print(f"{tally['vector']} redrawn as shapes, {tally['raster']} kept as images.")
    return 0


def nine_mapper(border: dict, native: tuple[int, int], box: tuple[int, int, int, int], border_scale):
    x0, y0, x1, y1 = box
    width, height = x1 - x0, y1 - y0
    w, h = native
    scale = nine_scale(border, w, h, width, height, border_scale)
    left, right, top, bottom = (border[k] * scale for k in ("left", "right", "top", "bottom"))

    def axis(value, size, low, high, target_low, target_high, target):
        if value <= low:
            return value * (target_low / low) if low else 0.0
        if value >= size - high:
            return target - (size - value) * (target_high / high) if high else float(target)
        middle = size - low - high
        return target_low + (value - low) * ((target - target_low - target_high) / middle)

    return lambda px, py: (x0 + axis(px, w, border["left"], border["right"], left, right, width),
                           y0 + axis(py, h, border["top"], border["bottom"], top, bottom, height))


def item_mapper(item: dict, entry: dict, box, native):
    """Map sprite coordinates to the screen, the same way the mockup draws that sprite."""
    x0, y0, x1, y1 = box
    width, height = x1 - x0, y1 - y0
    nine = entry.get("nine_slice") or {}
    has_box = "w" in item and "h" in item
    mode = item.get("mode", "auto")
    if has_box and mode in ("auto", "nine") and nine.get("status") == "suggested":
        return nine_mapper(nine, native, box, item.get("border_scale")), "nine"
    if has_box and mode != "stretch":
        scale = min(width / native[0], height / native[1])
        ox = x0 + (width - native[0] * scale) / 2
        oy = y0 + (height - native[1] * scale) / 2
        return (lambda px, py: (ox + px * scale, oy + py * scale)), "fit"
    sx, sy = width / native[0], height / native[1]
    return (lambda px, py: (x0 + px * sx, y0 + py * sy)), "stretch"


def find_container(node: dict, group: str | None, placed: list[tuple[dict, str | None]]) -> dict | None:
    """Find the smallest earlier sprite that visually holds this node, which becomes its parent."""
    x0, y0, x1, y1 = node["box"]
    area = max(1, (x1 - x0) * (y1 - y0))
    best, best_area = None, None
    for other, other_group in placed:
        if not other["entry"] or other_group != group:
            continue
        a0, b0, a1, b1 = other["box"]
        other_area = (a1 - a0) * (b1 - b0)
        overlap = max(0, min(x1, a1) - max(x0, a0)) * max(0, min(y1, b1) - max(y0, b0))
        if overlap >= area * 0.9 and other_area > area * 1.1 and (best is None or other_area < best_area):
            best, best_area = other, other_area
    return best


def build_tree(kit: Path, layout: dict, manifest: dict, screen: str, background: str | None, args=None, assets: Path | None = None):
    """Turn a layout into a tree of named nodes for the PSD and Unity exports."""
    size = tuple(layout["size"])
    used: dict[str, int] = {}
    nodes, notes = [], []

    def unique(name: str) -> str:
        used[name] = used.get(name, 0) + 1
        return name if used[name] == 1 else f"{name}_{used[name]}"

    folders: dict[str, dict] = {}
    placed: list[tuple[dict, str | None]] = []
    current = None
    for item in layout["items"]:
        name = item.get("element")
        if not name and "text" not in item:
            continue  # a wireframe-only item, such as a "wf": "bar"
        entry = manifest["elements"].get(name) if name else None
        if entry:
            item = prepare_fill(item, entry, notes.append)
            native = (entry["width"], entry["height"])
            box = item_box(item, native, size) if not ("w" in item and "h" in item) else item_box(item, None, size)
        else:
            box = item_box(item, None, size)
        original = kit_layer_name(entry)
        if original and not item.get("name"):
            # A kit sprite keeps the user's own file name on every use, so exporting
            # layers from the PSD maps back to one resource instead of name_2, name_3.
            label, file_id = original, unique(original)
        else:
            label = item.get("name") or (element_layer_name(name) if name else f"text_{slug(item.get('text', ''))}")
            if not PSD_NAME_RE.match(label):
                notes.append(f"{label}: does not follow function_description_color_screen")
            label = file_id = unique(label)
        node = {"name": label, "file_id": file_id, "kit": bool(original and not item.get("name")),
                "box": list(box), "item": item, "element": name if entry else None,
                "entry": entry, "children": []}
        group = item.get("group")
        container = find_container(node, group, placed)
        placed.append((node, group))
        if container:
            container["children"].append(node)
            current = group
            continue
        if group:
            if group != current or group not in folders:
                folder = {"name": unique(group), "folder": True, "children": []}
                folders[group] = folder
                nodes.append(folder)
            folders[group]["children"].append(node)
        else:
            nodes.append(node)
        current = group
    return nodes, notes


def psd_font(font_path: str | None) -> str:
    """Read a font's PostScript name, which is what Photoshop asks for."""
    if not font_path:
        return "ArialMT"
    try:
        data = Path(font_path).read_bytes()
        tables = struct.unpack(">H", data[4:6])[0]
        for i in range(tables):
            tag, _, offset, _ = struct.unpack(">4sIII", data[12 + i * 16:28 + i * 16])
            if tag == b"name":
                _, count, start = struct.unpack(">HHH", data[offset:offset + 6])
                for j in range(count):
                    platform, _, _, name_id, length, where = struct.unpack(">6H", data[offset + 6 + j * 12:offset + 18 + j * 12])
                    if name_id == 6:
                        raw = data[offset + start + where:offset + start + where + length]
                        return raw.decode("utf-16-be" if platform in (0, 3) else "latin-1")
    except (OSError, struct.error, UnicodeDecodeError):
        pass
    return "ArialMT"


def psd_ops(kit: Path, node: dict, layout: dict, font: str, args, stats: dict, assets: Path) -> list[dict]:
    """Describe one node as Photoshop drawing steps, in bottom-to-top order."""
    if node.get("folder"):
        children = []
        for child in node["children"]:
            children += psd_ops(kit, child, layout, font, args, stats, assets)
        return [{"op": "group", "name": node["name"], "children": children}]
    item, entry = node["item"], node["entry"]
    box = node["box"]
    children = []
    group_effects = None
    opacity = round(item.get("opacity", 1) * 100, 1)
    if entry:
        native = (entry["width"], entry["height"])
        mapper, mode = item_mapper(item, entry, box, native)
        from_kit = node.get("kit") and not getattr(args, "redraw_kit", False)
        keep_image = from_kit or (is_art(node["element"], item) and args.art != "redraw")
        # A recipe means the sprite was rebuilt from shapes on purpose, so it wins even for kit sprites,
        # whose group still carries the user's own file name.
        keep_art = is_art(node["element"], item) and args.art != "redraw"
        recipe = None if keep_art else recipes.load_recipe(kit, node["element"])
        if recipe:
            from_kit, keep_image = False, False
        spec = {"kind": "recipe"} if recipe else {"kind": "raster"} if keep_image else vectorize_element(kit, node["element"], entry, args)
        if from_kit:
            stats.setdefault("kit_images", []).append(node["name"])
        elif keep_image:
            stats["art_as_images"].append(node["name"])
        if recipe:
            stats.setdefault("recipe", []).append(node["name"])
            built = recipes.to_photoshop(recipe, node["name"], mapper, opacity)
            children += built["children"]
            group_effects = built.get("effects")
        elif spec["kind"] == "vector":
            stats["vector"].append(node["name"])
            for i, shape in enumerate(spec["shapes"]):
                subpaths = [[[round(v, 2) for v in mapper(*point)] for point in loop] for loop in shape["subpaths"]]
                children.append({"op": "path", "name": f"{node['name']}_shape{i + 1}", "color": shape["color"],
                                 "subpaths": subpaths, "opacity": opacity})
        else:
            stats["image"].append(node["name"])
            source = kit / entry["file"]
            if mode == "nine":
                # A smart object cannot 9-slice, so the stretched result is embedded at final size.
                image = Image.open(source).convert("RGBA")
                rendered = render_nine_slice(image, entry["nine_slice"], box[2] - box[0], box[3] - box[1], item.get("border_scale"))
                source = assets / f"{node.get('file_id', node['name'])}.png"
                rendered.save(source)
                place = list(box)
            else:
                x0, y0, x1, y1 = box
                if mode == "fit":
                    scale = min((x1 - x0) / native[0], (y1 - y0) / native[1])
                    w, h = native[0] * scale, native[1] * scale
                    place = [x0 + ((x1 - x0) - w) / 2, y0 + ((y1 - y0) - h) / 2, x0 + ((x1 - x0) + w) / 2, y0 + ((y1 - y0) + h) / 2]
                else:
                    scale = (x1 - x0) / native[0]
                    place = list(box)
                if scale > 1.02:
                    stats["upscaled"].append(f"{node['name']}: source enlarged {scale:.1f}x, will look soft")
            layer = node["name"] if node.get("kit") else f"{node['name']}_image"
            children.append({"op": "smart", "name": layer, "file": source.resolve().as_posix(),
                             "box": [round(v, 2) for v in place], "opacity": opacity})
    if "text" in item:
        center = [(box[0] + box[2]) / 2, (box[1] + box[3]) / 2]
        color = list(ImageColor.getrgb(item.get("text_color", "#FFFFFF"))[:3])
        size = round(item.get("text_size", max(12, (box[3] - box[1]) * 0.45)))
        children.append({"op": "text", "name": f"text_{slug(item['text'])}", "text": str(item["text"]), "font": font,
                         "size": size, "color": color, "center": center, "max_width": (box[2] - box[0]) * 0.9,
                         "stroke": round(item.get("text_stroke", 0))})
        stats["text"] += 1
    for child in node.get("children", []):
        children += psd_ops(kit, child, layout, font, args, stats, assets)
    if len(children) == 1 and not entry:
        children[0]["name"] = node["name"]
        return children
    return [{"op": "group", "name": node["name"], "children": children, "effects": group_effects}]


PSD_JSX = r"""#target photoshop
var PLAN = __PLAN__;
function s(n) { return stringIDToTypeID(n); }
function rgb(c) { var d = new ActionDescriptor(); d.putDouble(s("red"), c[0]); d.putDouble(s("green"), c[1]); d.putDouble(s("blue"), c[2]); return d; }
var missingFonts = {}, placed = {}, doc, kinds = {shape: 0, text: 0, smart: 0, group: 0, live: 0, effects: 0, effects_failed: 0};
function hasFont(n) { try { app.fonts.getByName(n); return true; } catch (e) { return false; } }
function solidLayer(color) {
  var make = new ActionDescriptor(), ref = new ActionReference();
  ref.putClass(s("contentLayer")); make.putReference(s("null"), ref);
  var content = new ActionDescriptor(), fill = new ActionDescriptor();
  fill.putObject(s("color"), s("RGBColor"), rgb(color));
  content.putObject(s("type"), s("solidColorLayer"), fill);
  make.putObject(s("using"), s("contentLayer"), content);
  executeAction(s("make"), make, DialogModes.NO);
}
function drawPath(op, parent) {
  var infos = [];
  for (var i = 0; i < op.subpaths.length; i++) {
    var points = [], loop = op.subpaths[i];
    for (var j = 0; j < loop.length; j++) {
      var p = new PathPointInfo(); p.kind = PointKind.CORNERPOINT;
      p.anchor = loop[j]; p.leftDirection = loop[j]; p.rightDirection = loop[j];
      points.push(p);
    }
    var sub = new SubPathInfo(); sub.closed = true; sub.operation = ShapeOperation.SHAPEXOR; sub.entireSubPath = points;
    infos.push(sub);
  }
  var path = doc.pathItems.add("tmp_path", infos);
  path.select();
  solidLayer(op.color);
  path.remove();
  var layer = doc.activeLayer; layer.name = op.name;
  if (op.opacity < 100) layer.opacity = op.opacity;
  kinds.shape++;
}
function hex(v) { if (!v) return null; if (v.length) { if (typeof v === "string") { var n = parseInt(v.replace("#", ""), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; } return v; } return null; }
var BLEND = {normal: "normal", multiply: "multiply", screen: "screen", overlay: "overlay", soft_light: "softLight",
  hard_light: "hardLight", color_dodge: "colorDodge", color_burn: "colorBurn", darken: "darken", lighten: "lighten",
  linear_dodge: "linearDodge", linear_burn: "linearBurn"};
var DOM_BLEND = {multiply: "MULTIPLY", screen: "SCREEN", overlay: "OVERLAY", soft_light: "SOFTLIGHT", hard_light: "HARDLIGHT",
  color_dodge: "COLORDODGE", color_burn: "COLORBURN", darken: "DARKEN", lighten: "LIGHTEN", linear_dodge: "LINEARDODGE",
  linear_burn: "LINEARBURN", normal: "NORMAL"};
function val(v, d) { return (v === undefined || v === null) ? d : v; }
function gradientDesc(stops) {
  var g = new ActionDescriptor(), colors = new ActionList(), alphas = new ActionList();
  g.putString(s("name"), "Custom");
  g.putEnumerated(s("gradientForm"), s("gradientForm"), s("customStops"));
  g.putDouble(s("interfaceIconFrameDimmed"), 4096);
  for (var i = 0; i < stops.length; i++) {
    var c = new ActionDescriptor(), a = new ActionDescriptor(), at = Math.round(stops[i][1] / 100 * 4096);
    c.putObject(s("color"), s("RGBColor"), rgb(hex(stops[i][0])));
    c.putEnumerated(s("type"), s("colorStopType"), s("userStop"));
    c.putInteger(s("location"), at); c.putInteger(s("midpoint"), 50);
    colors.putObject(s("colorStop"), c);
    a.putUnitDouble(s("opacity"), s("percentUnit"), val(stops[i][2], 100));
    a.putInteger(s("location"), at); a.putInteger(s("midpoint"), 50);
    alphas.putObject(s("transferSpec"), a);
  }
  g.putList(s("colors"), colors); g.putList(s("transparency"), alphas);
  return g;
}
function contentType(fill) {
  var d = new ActionDescriptor();
  if (fill.gradient) {
    d.putEnumerated(s("type"), s("gradientType"), s("linear"));
    d.putUnitDouble(s("angle"), s("angleUnit"), val(fill.angle, 90));
    d.putObject(s("gradient"), s("gradientClassEvent"), gradientDesc(fill.gradient));
    return [s("gradientLayer"), d];
  }
  d.putObject(s("color"), s("RGBColor"), rgb(hex(fill.color)));
  return [s("solidColorLayer"), d];
}
function makeContent(fill, shape) {
  var make = new ActionDescriptor(), ref = new ActionReference(), layer = new ActionDescriptor(), type = contentType(fill);
  ref.putClass(s("contentLayer")); make.putReference(s("null"), ref);
  layer.putObject(s("type"), type[0], type[1]);
  if (shape) layer.putObject(s("shape"), shape[0], shape[1]);
  make.putObject(s("using"), s("contentLayer"), layer);
  executeAction(s("make"), make, DialogModes.NO);
}
function roundedLoop(b, r) {
  var pts = [], k = 8, corners = [[b[2] - r[1], b[1] + r[1], -90, r[1]], [b[2] - r[2], b[3] - r[2], 0, r[2]],
                                   [b[0] + r[3], b[3] - r[3], 90, r[3]], [b[0] + r[0], b[1] + r[0], 180, r[0]]];
  for (var c = 0; c < 4; c++) {
    var cx = corners[c][0], cy = corners[c][1], a0 = corners[c][2], rad = corners[c][3];
    for (var i = 0; i <= k; i++) {
      var a = (a0 + 90 * i / k) * Math.PI / 180;
      pts.push([cx + rad * Math.cos(a), cy + rad * Math.sin(a)]);
      if (rad <= 0) break;
    }
  }
  return pts;
}
function ellipseLoop(b) {
  var pts = [], cx = (b[0] + b[2]) / 2, cy = (b[1] + b[3]) / 2, rx = (b[2] - b[0]) / 2, ry = (b[3] - b[1]) / 2;
  for (var i = 0; i < 48; i++) { var a = i / 48 * 2 * Math.PI; pts.push([cx + rx * Math.cos(a), cy + ry * Math.sin(a)]); }
  return pts;
}
function pathFromLoops(loops) {
  var infos = [];
  for (var i = 0; i < loops.length; i++) {
    var points = [], loop = loops[i];
    for (var j = 0; j < loop.length; j++) {
      var p = new PathPointInfo(); p.kind = PointKind.CORNERPOINT;
      p.anchor = loop[j]; p.leftDirection = loop[j]; p.rightDirection = loop[j];
      points.push(p);
    }
    var sub = new SubPathInfo(); sub.closed = true; sub.operation = ShapeOperation.SHAPEXOR; sub.entireSubPath = points;
    infos.push(sub);
  }
  return doc.pathItems.add("tmp_path", infos);
}
function drawShape(op, parent) {
  var b = op.box, made = false;
  if (op.shape === "rect" || op.shape === "ellipse") {
    try {
      var shape = new ActionDescriptor();
      shape.putInteger(s("unitValueQuadVersion"), 1);
      shape.putUnitDouble(s("top"), s("pixelsUnit"), b[1]); shape.putUnitDouble(s("left"), s("pixelsUnit"), b[0]);
      shape.putUnitDouble(s("bottom"), s("pixelsUnit"), b[3]); shape.putUnitDouble(s("right"), s("pixelsUnit"), b[2]);
      if (op.shape === "rect") {
        var r = op.radius || [0, 0, 0, 0], lim = Math.min(b[2] - b[0], b[3] - b[1]) / 2;
        shape.putUnitDouble(s("topLeft"), s("pixelsUnit"), Math.min(r[0], lim));
        shape.putUnitDouble(s("topRight"), s("pixelsUnit"), Math.min(r[1], lim));
        shape.putUnitDouble(s("bottomRight"), s("pixelsUnit"), Math.min(r[2], lim));
        shape.putUnitDouble(s("bottomLeft"), s("pixelsUnit"), Math.min(r[3], lim));
      }
      makeContent(op.fill, [s(op.shape === "rect" ? "rectangle" : "ellipse"), shape]);
      made = true; kinds.live = (kinds.live || 0) + 1;
    } catch (liveFailed) { made = false; }
  }
  if (!made) {
    var loops = op.subpaths;
    if (op.shape === "rect") { var lim2 = Math.min(b[2] - b[0], b[3] - b[1]) / 2, rr = op.radius || [0, 0, 0, 0];
      loops = [roundedLoop(b, [Math.min(rr[0], lim2), Math.min(rr[1], lim2), Math.min(rr[2], lim2), Math.min(rr[3], lim2)])]; }
    if (op.shape === "ellipse") loops = [ellipseLoop(b)];
    var path = pathFromLoops(loops);
    path.select();
    makeContent(op.fill, null);
    path.remove();
  }
  var layer = doc.activeLayer;
  if (parent !== doc && layer.parent !== parent) layer.move(parent, ElementPlacement.PLACEATBEGINNING);
  layer.name = op.name;
  setEffects(op.effects);
  if (op.fill_opacity !== undefined && op.fill_opacity < 100) layer.fillOpacity = op.fill_opacity;
  if (op.opacity !== undefined && op.opacity < 100) layer.opacity = op.opacity;
  if (op.blend && op.blend !== "normal") layer.blendMode = BlendMode[DOM_BLEND[op.blend]];
  if (op.clip) { try { layer.grouped = true; } catch (noBase) {} }
  kinds.shape++;
}
function shadowDesc(fx, mode, color, opacity, angle) {
  var d = new ActionDescriptor();
  d.putBoolean(s("enabled"), true);
  d.putEnumerated(s("mode"), s("blendMode"), s(BLEND[val(fx.blend, mode)]));
  d.putObject(s("color"), s("RGBColor"), rgb(hex(val(fx.color, color))));
  d.putUnitDouble(s("opacity"), s("percentUnit"), val(fx.opacity, opacity));
  d.putBoolean(s("useGlobalAngle"), false);
  d.putUnitDouble(s("localLightingAngle"), s("angleUnit"), val(fx.angle, angle));
  d.putUnitDouble(s("distance"), s("pixelsUnit"), val(fx.distance, 4));
  d.putUnitDouble(s("chokeMatte"), s("pixelsUnit"), val(fx.spread, 0));
  d.putUnitDouble(s("blur"), s("pixelsUnit"), val(fx.size, 6));
  d.putUnitDouble(s("noise"), s("percentUnit"), 0);
  d.putBoolean(s("antiAlias"), false);
  return d;
}
function glowDesc(fx, inner) {
  var d = new ActionDescriptor();
  d.putBoolean(s("enabled"), true);
  d.putEnumerated(s("mode"), s("blendMode"), s(BLEND[val(fx.blend, "screen")]));
  d.putObject(s("color"), s("RGBColor"), rgb(hex(val(fx.color, "#ffffbe"))));
  d.putUnitDouble(s("opacity"), s("percentUnit"), val(fx.opacity, 75));
  d.putEnumerated(s("glowTechnique"), s("matteTechnique"), s("softMatte"));
  d.putUnitDouble(s("chokeMatte"), s("pixelsUnit"), val(fx.spread, 0));
  d.putUnitDouble(s("blur"), s("pixelsUnit"), val(fx.size, 10));
  d.putUnitDouble(s("noise"), s("percentUnit"), 0);
  d.putUnitDouble(s("shadingNoise"), s("percentUnit"), 0);
  d.putBoolean(s("antiAlias"), false);
  d.putUnitDouble(s("inputRange"), s("percentUnit"), 50);
  if (inner) d.putEnumerated(s("innerGlowSource"), s("innerGlowSourceType"), s("edgeGlow"));
  return d;
}
function bevelDesc(fx) {
  var d = new ActionDescriptor();
  var tech = {smooth: "softMatte", chisel_hard: "preciseMatte", chisel_soft: "slopeLimitMatte"}[val(fx.technique, "smooth")] || "softMatte";
  var style = {inner: "innerBevel", outer: "outerBevel", emboss: "emboss", pillow: "pillowEmboss", stroke: "strokeEmboss"}[val(fx.style, "inner")] || "innerBevel";
  d.putBoolean(s("enabled"), true);
  d.putEnumerated(s("highlightMode"), s("blendMode"), s(BLEND[val(fx.highlight_blend, "screen")]));
  d.putObject(s("highlightColor"), s("RGBColor"), rgb(hex(val(fx.highlight, "#ffffff"))));
  d.putUnitDouble(s("highlightOpacity"), s("percentUnit"), val(fx.highlight_opacity, 75));
  d.putEnumerated(s("shadowMode"), s("blendMode"), s(BLEND[val(fx.shadow_blend, "multiply")]));
  d.putObject(s("shadowColor"), s("RGBColor"), rgb(hex(val(fx.shadow, "#000000"))));
  d.putUnitDouble(s("shadowOpacity"), s("percentUnit"), val(fx.shadow_opacity, 75));
  d.putEnumerated(s("bevelTechnique"), s("bevelTechnique"), s(tech));
  d.putEnumerated(s("bevelStyle"), s("bevelEmbossStyle"), s(style));
  d.putBoolean(s("useGlobalAngle"), false);
  d.putUnitDouble(s("localLightingAngle"), s("angleUnit"), val(fx.angle, 120));
  d.putUnitDouble(s("localLightingAltitude"), s("angleUnit"), val(fx.altitude, 30));
  d.putUnitDouble(s("strengthRatio"), s("percentUnit"), val(fx.depth, 100));
  d.putUnitDouble(s("blur"), s("pixelsUnit"), val(fx.size, 5));
  d.putEnumerated(s("bevelDirection"), s("bevelEmbossStampStyle"), s(val(fx.direction, "up") === "down" ? "stampOut" : "stampIn"));
  d.putUnitDouble(s("softness"), s("pixelsUnit"), val(fx.soften, 0));
  d.putBoolean(s("useShape"), false); d.putBoolean(s("useTexture"), false);
  return d;
}
function strokeDesc(fx) {
  var d = new ActionDescriptor();
  d.putBoolean(s("enabled"), true);
  d.putEnumerated(s("style"), s("frameStyle"), s({inside: "insetFrame", center: "centeredFrame"}[fx.position] || "outsetFrame"));
  d.putEnumerated(s("mode"), s("blendMode"), s(BLEND[val(fx.blend, "normal")]));
  d.putUnitDouble(s("opacity"), s("percentUnit"), val(fx.opacity, 100));
  d.putUnitDouble(s("size"), s("pixelsUnit"), val(fx.size, 3));
  if (fx.gradient) {
    d.putEnumerated(s("paintType"), s("frameFill"), s("gradientFill"));
    d.putObject(s("gradient"), s("gradientClassEvent"), gradientDesc(fx.gradient));
    d.putUnitDouble(s("angle"), s("angleUnit"), val(fx.angle, 90));
    d.putEnumerated(s("type"), s("gradientType"), s("linear"));
  } else {
    d.putEnumerated(s("paintType"), s("frameFill"), s("solidColor"));
    d.putObject(s("color"), s("RGBColor"), rgb(hex(val(fx.color, "#000000"))));
  }
  return d;
}
function setEffects(fx) {
  if (!fx) return;
  var any = false;
  for (var k in fx) { if (fx[k] && fx[k].enabled !== false) any = true; }
  if (!any) return;
  var set = new ActionDescriptor(), ref = new ActionReference(), all = new ActionDescriptor();
  ref.putProperty(s("property"), s("layerEffects")); ref.putEnumerated(s("layer"), s("ordinal"), s("targetEnum"));
  set.putReference(s("null"), ref);
  all.putUnitDouble(s("scale"), s("percentUnit"), 100);
  if (fx.drop_shadow) all.putObject(s("dropShadow"), s("dropShadow"), shadowDesc(fx.drop_shadow, "multiply", "#000000", 75, 120));
  if (fx.inner_shadow) all.putObject(s("innerShadow"), s("innerShadow"), shadowDesc(fx.inner_shadow, "multiply", "#000000", 75, 120));
  if (fx.outer_glow) all.putObject(s("outerGlow"), s("outerGlow"), glowDesc(fx.outer_glow, false));
  if (fx.inner_glow) all.putObject(s("innerGlow"), s("innerGlow"), glowDesc(fx.inner_glow, true));
  if (fx.bevel) all.putObject(s("bevelEmboss"), s("bevelEmboss"), bevelDesc(fx.bevel));
  if (fx.color_overlay) {
    var co = new ActionDescriptor(), c = fx.color_overlay;
    co.putBoolean(s("enabled"), true); co.putEnumerated(s("mode"), s("blendMode"), s(BLEND[val(c.blend, "normal")]));
    co.putUnitDouble(s("opacity"), s("percentUnit"), val(c.opacity, 100));
    co.putObject(s("color"), s("RGBColor"), rgb(hex(val(c.color, "#ff0000"))));
    all.putObject(s("solidFill"), s("solidFill"), co);
  }
  if (fx.gradient_overlay) {
    var go = new ActionDescriptor(), g = fx.gradient_overlay;
    go.putBoolean(s("enabled"), true); go.putEnumerated(s("mode"), s("blendMode"), s(BLEND[val(g.blend, "normal")]));
    go.putUnitDouble(s("opacity"), s("percentUnit"), val(g.opacity, 100));
    go.putObject(s("gradient"), s("gradientClassEvent"), gradientDesc(val(g.gradient, [["#000000", 0], ["#ffffff", 100]])));
    go.putUnitDouble(s("angle"), s("angleUnit"), val(g.angle, 90));
    go.putEnumerated(s("type"), s("gradientType"), s("linear"));
    go.putBoolean(s("reverse"), false); go.putBoolean(s("dither"), false); go.putBoolean(s("align"), true);
    go.putUnitDouble(s("scale"), s("percentUnit"), 100);
    all.putObject(s("gradientFill"), s("gradientFill"), go);
  }
  if (fx.stroke) all.putObject(s("frameFX"), s("frameFX"), strokeDesc(fx.stroke));
  set.putObject(s("to"), s("layerEffects"), all);
  try { executeAction(s("set"), set, DialogModes.NO); kinds.effects = (kinds.effects || 0) + 1; }
  catch (fxFailed) { kinds.effects_failed = (kinds.effects_failed || 0) + 1; }
}
function drawSmart(op) {
  var layer;
  if (placed[op.file]) {
    doc.activeLayer = placed[op.file];
    var d = new ActionDescriptor(), ref = new ActionReference();
    ref.putEnumerated(s("layer"), s("ordinal"), s("targetEnum")); d.putReference(s("null"), ref);
    executeAction(s("copyToLayer"), undefined, DialogModes.NO);
    layer = doc.activeLayer;
    layer.move(current, ElementPlacement.PLACEATBEGINNING);
  } else {
    var place = new ActionDescriptor();
    place.putPath(s("null"), new File(op.file));
    executeAction(s("placeEvent"), place, DialogModes.NO);
    layer = doc.activeLayer;
    placed[op.file] = layer; if (current !== doc && layer.parent !== current) layer.move(current, ElementPlacement.PLACEATBEGINNING);
  }
  layer.name = op.name;
  var b = layer.bounds, w = b[2].as("px") - b[0].as("px"), h = b[3].as("px") - b[1].as("px");
  var tw = op.box[2] - op.box[0], th = op.box[3] - op.box[1];
  layer.resize(tw / w * 100, th / h * 100, AnchorPosition.TOPLEFT);
  b = layer.bounds;
  layer.translate(new UnitValue(op.box[0] - b[0].as("px"), "px"), new UnitValue(op.box[1] - b[1].as("px"), "px"));
  if (op.opacity < 100) layer.opacity = op.opacity;
  kinds.smart++;
}
function drawText(op, parent) {
  var font = op.font;
  if (!hasFont(font)) { missingFonts[font] = true; font = "ArialMT"; }
  var layer = parent.artLayers.add(); layer.kind = LayerKind.TEXT; layer.name = op.name;
  var t = layer.textItem;
  t.contents = op.text; t.font = font; t.size = new UnitValue(op.size, "px");
  t.justification = Justification.CENTER;
  var c = new SolidColor(); c.rgb.red = op.color[0]; c.rgb.green = op.color[1]; c.rgb.blue = op.color[2]; t.color = c;
  t.position = [new UnitValue(op.center[0], "px"), new UnitValue(op.center[1], "px")];
  var size = op.size, b = layer.bounds;
  while (b[2].as("px") - b[0].as("px") > op.max_width && size > 8) {
    size -= 1; t.size = new UnitValue(size, "px"); b = layer.bounds;
  }
  layer.translate(new UnitValue(op.center[0] - (b[0].as("px") + b[2].as("px")) / 2, "px"),
                  new UnitValue(op.center[1] - (b[1].as("px") + b[3].as("px")) / 2, "px"));
  if (op.stroke > 0) {
    var set = new ActionDescriptor(), ref = new ActionReference();
    ref.putProperty(s("property"), s("layerEffects")); ref.putEnumerated(s("layer"), s("ordinal"), s("targetEnum"));
    set.putReference(s("null"), ref);
    var fx = new ActionDescriptor(), f = new ActionDescriptor();
    fx.putUnitDouble(s("scale"), s("percentUnit"), 100);
    f.putBoolean(s("enabled"), true);
    f.putEnumerated(s("style"), s("frameStyle"), s("outsetFrame"));
    f.putEnumerated(s("paintType"), s("frameFill"), s("solidColor"));
    f.putEnumerated(s("mode"), s("blendMode"), s("normal"));
    f.putUnitDouble(s("opacity"), s("percentUnit"), 100);
    f.putUnitDouble(s("size"), s("pixelsUnit"), op.stroke);
    var lum = 0.299 * op.color[0] + 0.587 * op.color[1] + 0.114 * op.color[2];
    f.putObject(s("color"), s("RGBColor"), rgb(lum > 128 ? [20, 20, 20] : [245, 245, 245]));
    fx.putObject(s("frameFX"), s("frameFX"), f);
    set.putObject(s("to"), s("layerEffects"), fx);
    doc.activeLayer = layer;
    executeAction(s("set"), set, DialogModes.NO);
  }
  kinds.text++;
}
var current;
function buildOps(ops, parent) {
  for (var i = 0; i < ops.length; i++) {
    var op = ops[i];
    current = parent;
    if (parent !== doc && parent.layers.length) { doc.activeLayer = parent.layers[0]; }
    else if (parent !== doc) { doc.activeLayer = parent; }
    else if (doc.layers.length) { doc.activeLayer = doc.layers[0]; }
    if (op.op === "group") {
      var g = parent.layerSets.add(); g.name = op.name; kinds.group++;
      doc.activeLayer = g;
      buildOps(op.children, g);
      current = parent;
      if (op.effects) { doc.activeLayer = g; setEffects(op.effects); }
      if (op.opacity !== undefined && op.opacity < 100) g.opacity = op.opacity;
      if (op.blend && op.blend !== "normal") g.blendMode = BlendMode[DOM_BLEND[op.blend]];
    } else if (op.op === "path") drawPath(op, parent);
    else if (op.op === "shape") drawShape(op, parent);
    else if (op.op === "smart") drawSmart(op);
    else if (op.op === "text") drawText(op, parent);
  }
}
var savedUnits = app.preferences.rulerUnits, savedDialogs = app.displayDialogs, result = {};
app.preferences.rulerUnits = Units.PIXELS; app.displayDialogs = DialogModes.NO;
try {
  doc = app.documents.add(PLAN.size[0], PLAN.size[1], 72, PLAN.title, NewDocumentMode.RGB, DocumentFill.TRANSPARENT);
  var base = doc.artLayers[0]; base.name = "tmp_base";
  buildOps(PLAN.ops, doc);
  try {
    var bottom = doc.layers[doc.layers.length - 1];
    if (bottom.name !== "tmp_base") throw new Error("already gone");
    doc.activeLayer = bottom;
    var del = new ActionDescriptor(), delRef = new ActionReference();
    delRef.putEnumerated(s("layer"), s("ordinal"), s("targetEnum"));
    del.putReference(s("null"), delRef);
    executeAction(s("delete"), del, DialogModes.NO);
  } catch (ignoredBase) { result.base_left = true; }
  var options = new PhotoshopSaveOptions(); options.layers = true; options.embedColorProfile = true; options.maximizeCompatibility = true;
  doc.saveAs(new File(PLAN.psd), options, true);
  doc.saveAs(new File(PLAN.check), new PNGSaveOptions(), true);
  doc.close(SaveOptions.DONOTSAVECHANGES);
  result.ok = true;
} catch (error) {
  result.ok = false; result.error = String(error) + " line " + error.line;
  try { if (doc) doc.close(SaveOptions.DONOTSAVECHANGES); } catch (ignored) {}
}
app.preferences.rulerUnits = savedUnits; app.displayDialogs = savedDialogs;
var names = []; for (var key in missingFonts) names.push('"' + key + '"');
'{"ok":' + (result.ok ? "true" : "false") + ',"error":"' + String(result.error || "").replace(/[\r\n"\\]/g, " ") + '","shape":' + kinds.shape + ',"live_shapes":' + kinds.live + ',"effects":' + kinds.effects + ',"effects_failed":' + kinds.effects_failed + ',"text":' + kinds.text + ',"smart":' + kinds.smart + ',"group":' + kinds.group + ',"missing_fonts":[' + names.join(",") + "]}";
"""


def run_photoshop(jsx: Path, timeout: int) -> dict | None:
    """Run a script in Photoshop on Windows. Return None when Photoshop cannot be reached."""
    if sys.platform != "win32":
        return None
    command = ("$ErrorActionPreference='Stop';$running=[bool](Get-Process Photoshop -ErrorAction SilentlyContinue);"
               "$ps=New-Object -ComObject Photoshop.Application;"
               f"$out=$ps.DoJavaScriptFile('{jsx.resolve()}');"
               "if(-not $running){$ps.Quit()};[Console]::OutputEncoding=[Text.Encoding]::UTF8;Write-Output $out")
    try:
        done = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    start, end = done.stdout.find("{"), done.stdout.rfind("}")
    if start < 0 or end < start:
        return None
    try:
        return json.loads(done.stdout[start:end + 1])
    except ValueError:
        return {"ok": False, "error": done.stdout[start:end + 1][:300]}


def layout_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_confirmed(kit: Path) -> dict:
    path = kit / "mockups" / "confirmed.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"wireframe": {}, "screens": {}}


def write_confirmed(kit: Path, data: dict) -> None:
    (kit / "mockups").mkdir(parents=True, exist_ok=True)
    (kit / "mockups" / "confirmed.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def confirmed_screens(kit: Path) -> tuple[list[str], list[str]]:
    """Return confirmed screens, and those whose layout changed after being confirmed."""
    data = read_confirmed(kit)
    good, stale = [], []
    for screen, record in data["screens"].items():
        path = kit / "mockups" / f"{record['layout']}.json"
        if path.exists() and layout_hash(path) == record["hash"]:
            good.append(screen)
        else:
            stale.append(screen)
    return good, stale


def wireframe_confirmed(kit: Path) -> tuple[bool, list[str]]:
    data = read_confirmed(kit)["wireframe"]
    if not data:
        return False, []
    picked = selected_layouts(kit, strict=False)
    changed = [s for s in data if s not in picked or layout_hash(picked[s]) != data[s]["hash"]]
    added = [s for s in picked if s not in data]
    return not changed and not added, changed + added


def cmd_confirm(args) -> int:
    kit = Path(args.kit)
    data = read_confirmed(kit)
    if args.target == "wireframe":
        picked = selected_layouts(kit, args.variant)
        for screen, path in picked.items():
            data["wireframe"][screen] = {"layout": path.stem, "hash": layout_hash(path)}
        write_confirmed(kit, data)
        print(f"Confirmed the wireframe of {len(picked)} screens: {sorted(picked)}")
        return 0
    screen = args.target
    if args.variant:
        variant = args.variant if args.variant.startswith(screen) else f"{screen}__{args.variant}"
        options = [p.stem for p in layout_paths(kit, screen)]
        if variant not in options:
            die("NOT_FOUND", f"{variant} is not one of {options}", 1)
        chosen = read_chosen(kit)
        chosen[screen] = variant
        (kit / "mockups" / "chosen.json").write_text(json.dumps(chosen, indent=2), encoding="utf-8")
    picked = selected_layouts(kit, screen)
    path = picked[screen]
    data["screens"][screen] = {"layout": path.stem, "hash": layout_hash(path)}
    write_confirmed(kit, data)
    print(f"{screen}: confirmed {path.stem}")
    return 0


def export_targets(kit: Path, args) -> dict[str, Path]:
    """Pick screens to export: confirmed ones only, unless --unconfirmed is given.

    With --layout, export exactly those layouts, such as home__v2, each under its own name."""
    if getattr(args, "layout", None):
        available = {p.stem: p for p in layout_paths(kit)}
        missing = [name for name in args.layout if name not in available]
        if missing:
            die("NOT_FOUND", f"no layouts {missing}. Layouts: {sorted(available)}", 1)
        return {name: available[name] for name in args.layout}
    picked = selected_layouts(kit, args.screen)
    if args.unconfirmed:
        return picked
    good, stale = confirmed_screens(kit)
    if stale:
        print(f"Changed since being confirmed, so skipped: {sorted(stale)}")
    allowed = {s: p for s, p in picked.items() if s in good}
    if not allowed:
        die("NOT_CONFIRMED", f"confirm a screen first. Screens: {sorted(picked)}")
    skipped = sorted(set(picked) - set(allowed) - set(stale))
    if skipped:
        print(f"Not confirmed, so skipped: {skipped}")
    return allowed


def cmd_psd(args) -> int:
    kit = Path(args.kit)
    manifest = load_manifest(kit)
    targets = export_targets(kit, args)
    layouts = {s: read_layout(p) for s, p in targets.items()}
    with_image = [s for s, l in layouts.items() if isinstance(l.get("background"), str) and not l["background"].startswith("#")]
    if with_image and not args.background:
        die("NEEDS_BACKGROUND_CHOICE", f"ask the user: redraw or keep the background as one image layer? Screens: {with_image}. "
            "Then pass --background redraw|image.", 3)
    art = sorted({i["element"] for l in layouts.values() for i in l["items"]
                  if i.get("element") in manifest["elements"] and is_art(i["element"], i)})
    if art and not args.art:
        die("NEEDS_ART_CHOICE", f"ask the user: redraw these characters, environments and other art, or keep them as images? {art}. "
            "Then pass --art redraw|image.", 3)
    psd_dir = kit / "export" / "psd"
    assets = psd_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    existing = [s for s in targets if (psd_dir / f"{s}.psd").exists()]
    if existing and not args.force:
        die("EXISTS", f"{existing} already exported. Pass --force only if replacing them was requested.", 1)

    report = {}
    status = 0
    for screen, layout in layouts.items():
        size = tuple(layout["size"])
        font_path, font_source = resolve_font(kit, layout)
        font = psd_font(font_path)
        nodes, notes = build_tree(kit, layout, manifest, screen, args.background)
        stats = {"vector": [], "image": [], "kit_images": [], "art_as_images": [], "upscaled": [], "text": 0, "recipe": []}
        ops = []
        background = layout.get("background")
        if isinstance(background, str) and background.startswith("#"):
            color = list(ImageColor.getrgb(background)[:3])
            ops.append({"op": "path", "name": f"bg_{slug(screen)}", "color": color, "opacity": 100,
                        "subpaths": [[[0, 0], [size[0], 0], [size[0], size[1]], [0, size[1]]]]})
        elif background:
            file = kit / manifest["elements"][background]["file"] if background in manifest["elements"] else kit / background
            bg_name = f"bg_{slug(Path(str(background)).stem)}"
            if args.background == "redraw" and background in manifest["elements"]:
                bg_node = {"name": bg_name, "box": [0, 0, size[0], size[1]], "item": {"element": background, "w": size[0], "h": size[1], "mode": "stretch"},
                           "element": background, "entry": manifest["elements"][background]}
                ops += psd_ops(kit, bg_node, layout, font, args, stats, assets)
                if bg_name in stats["image"]:
                    notes.append(f"{bg_name}: too detailed to redraw accurately, so it stayed an image layer")
            else:
                ops.append({"op": "smart", "name": bg_name, "file": file.resolve().as_posix(), "box": [0, 0, size[0], size[1]], "opacity": 100})
        for node in nodes:
            ops += psd_ops(kit, node, layout, font, args, stats, assets)
        psd = psd_dir / f"{screen}.psd"
        check = psd_dir / "assets" / f"{screen}_check.png"
        plan = {"size": list(size), "title": screen, "ops": ops, "psd": psd.resolve().as_posix(), "check": check.resolve().as_posix()}
        jsx = psd_dir / f"{screen}.jsx"
        jsx.write_text(PSD_JSX.replace("__PLAN__", json.dumps(plan, ensure_ascii=True)), encoding="utf-8")
        result = None if args.no_run else run_photoshop(jsx, args.timeout)
        entry = {"psd": psd.relative_to(kit).as_posix() if result and result.get("ok") else None,
                 "script": jsx.relative_to(kit).as_posix(), "rebuilt_from_recipes": stats["recipe"],
                 "redrawn_as_shapes": stats["vector"],
                 "kept_as_images": stats["image"], "kit_sprites_as_images": stats["kit_images"], "art_kept_as_images": stats["art_as_images"], "live_text": stats["text"], "font": font, "font_source": font_source,
                 "warnings": notes + stats["upscaled"]}
        if result is None:
            entry["status"] = "script only: open the .jsx with Photoshop, File > Scripts > Browse"
            status = max(status, 2 if not args.no_run else 0)
        elif not result.get("ok"):
            entry["status"] = f"failed: {result.get('error')}"
            status = 2
        else:
            entry["status"] = "built in Photoshop"
            entry["layers"] = {k: result.get(k) for k in ("shape", "live_shapes", "effects", "effects_failed", "text", "smart", "group")}
            entry["fonts_not_installed"] = result.get("missing_fonts", [])
            if check.exists():
                flat = flatten(build_layers(kit, layout, manifest)[0], size)
                entry["difference_from_mockup"] = round(score_shapes(np.asarray(flat.convert("RGBA")).astype(float),
                                                                       np.asarray(Image.open(check).convert("RGBA")).astype(float)), 2)
        report[screen] = entry
        print(json.dumps({"screen": screen, **{k: (len(v) if isinstance(v, list) and k in ("rebuilt_from_recipes", "redrawn_as_shapes", "kept_as_images", "art_kept_as_images") else v) for k, v in entry.items()}}, indent=1, ensure_ascii=True))
    (kit / "export" / "psd_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return status


def anchor_of(center: float, size: float) -> float:
    position = center / size
    return 0.0 if position < 1 / 3 else (1.0 if position > 2 / 3 else 0.5)


def unity_node(node: dict, size: tuple[int, int], font_name: str, origin: tuple[float, float] = (0, 0)) -> dict:
    """Describe a node relative to its parent. size and origin are the parent's rectangle."""
    if node.get("folder"):
        return {"name": node["name"], "type": "group", "stretch": True,
                "children": [unity_node(child, size, font_name, origin) for child in node["children"]]}
    item, entry = node["item"], node["entry"]
    x0, y0, x1, y1 = node["box"]
    cx, cy = (x0 + x1) / 2 - origin[0], (y0 + y1) / 2 - origin[1]
    ax, ay = anchor_of(cx, size[0]), anchor_of(cy, size[1])
    result = {"name": node["name"], "type": "image" if entry else "text",
              "anchor": [ax, 1 - ay], "pivot": [0.5, 0.5],
              "position": [round(cx - ax * size[0], 2), round(ay * size[1] - cy, 2)],
              "size": [x1 - x0, y1 - y0]}
    text = None
    if "text" in item:
        text = {"text": str(item["text"]), "font": font_name, "fontSize": round(item.get("text_size", max(12, (y1 - y0) * 0.45))),
                "color": item.get("text_color", "#FFFFFF"), "outline": round(item.get("text_stroke", 0)), "alignment": "center"}
    if entry:
        nine = entry.get("nine_slice") or {}
        sliced = nine.get("status") == "suggested" and "w" in item and "h" in item and item.get("mode", "auto") in ("auto", "nine")
        result.update({"sprite": entry["file"], "spriteSize": [entry["width"], entry["height"]],
                       "imageType": "sliced" if sliced else "simple", "preserveAspect": not sliced and item.get("mode") != "stretch"})
        if nine.get("status") == "suggested":
            result["border"] = {k: nine[k] for k in ("left", "bottom", "right", "top")}
        if "fill" in item:
            result["fillValue"] = item["fill"]
    if item.get("opacity", 1) < 1:
        result["alpha"] = item["opacity"]
    if "goto" in item:
        result["onClick"] = {"goto": item["goto"]}
    children = []
    if text:
        if entry:
            children.append({"name": f"text_{slug(item['text'])}", "type": "text", "anchor": [0.5, 0.5], "pivot": [0.5, 0.5],
                             "stretch": True, **text})
        else:
            result.update(text)
    children += [unity_node(child, (x1 - x0, y1 - y0), font_name, (x0, y0)) for child in node.get("children", [])]
    if children:
        result["children"] = children
    return result


def cmd_unity(args) -> int:
    kit = Path(args.kit)
    manifest = load_manifest(kit)
    targets = export_targets(kit, args)
    out_dir = kit / "export" / "unity"
    existing = [s for s in targets if (out_dir / f"{s}.json").exists()]
    if existing and not args.force:
        die("EXISTS", f"{existing} already exported. Pass --force only if replacing them was requested.", 1)
    out_dir.mkdir(parents=True, exist_ok=True)
    for screen, path in targets.items():
        layout = read_layout(path)
        size = tuple(layout["size"])
        nodes, notes = build_tree(kit, layout, manifest, screen, None)
        font_path, source = resolve_font(kit, layout)
        font_name = Path(font_path).stem if font_path else "default"
        background = layout.get("background")
        mapping = {"version": 1, "screen": screen, "layout": path.stem, "referenceResolution": list(size),
                   "canvasScaler": {"mode": "ScaleWithScreenSize", "matchWidthOrHeight": 1}, "font": font_name,
                   "spritesRoot": "elements" , "background": background,
                   "nodes": [unity_node(node, size, font_name) for node in nodes]}
        (out_dir / f"{screen}.json").write_text(json.dumps(mapping, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"{screen}: export/unity/{screen}.json, {len(nodes)} top-level nodes, {len(notes)} naming notes")
    return 0


def cmd_resize_layout(args) -> int:
    """Rescale a layout to a new canvas, uniformly, centered, without distorting anything."""
    kit = Path(args.kit)
    width, height = (int(v) for v in args.size.lower().split("x"))
    paths = layout_paths(kit, args.screen)
    if not paths:
        die("NO_LAYOUT", "no layouts to resize", 1)
    for path in paths:
        layout = read_layout(path)
        old_w, old_h = layout["size"]
        scale = min(width / old_w, height / old_h)
        ox, oy = (width - old_w * scale) / 2, (height - old_h * scale) / 2
        for item in layout["items"]:
            item["x"] = round(item["x"] * scale + ox, 2)
            item["y"] = round(item["y"] * scale + oy, 2)
            for key in ("w", "h", "text_size", "text_stroke"):
                if key in item:
                    item[key] = round(item[key] * scale, 2)
        layout["size"] = [width, height]
        path.write_text(json.dumps(layout, indent=2, ensure_ascii=False), encoding="utf-8")
        note = "" if abs(old_w / old_h - width / height) < 0.005 else f", ratio differs so {round(ox)} px sides and {round(oy)} px top and bottom are empty"
        print(f"{path.stem}: {old_w}x{old_h} to {width}x{height}, scale {scale:.3f}{note}")
    return 0


def device_layout(layout: dict, width: int, height: int) -> dict:
    """Simulate another screen: keep height scale, keep items near their nearest screen edge."""
    old_w, old_h = layout["size"]
    scale = height / old_h
    moved = {**layout, "size": [width, height], "items": []}
    for item in layout["items"]:
        ax = anchor_of(item["x"], old_w)
        new = dict(item)
        new["x"] = round(ax * width + (item["x"] - ax * old_w) * scale, 2)
        new["y"] = round(item["y"] * scale, 2)
        for key in ("w", "h", "text_size", "text_stroke"):
            if key in new:
                new[key] = round(new[key] * scale, 2)
        moved["items"].append(new)
    return moved


def cmd_device(args) -> int:
    kit = Path(args.kit)
    manifest = load_manifest(kit)
    picked = selected_layouts(kit, args.screen, strict=False)
    devices = {"16x9": (1920, 1080), "20x9": (2400, 1080), "16x10": (1728, 1080), "4x3": (1440, 1080)}
    out_dir = kit / "preview" / "devices"
    out_dir.mkdir(parents=True, exist_ok=True)
    problems = 0
    for screen, path in picked.items():
        layout = read_layout(path)
        thumbs = []
        for label, (width, height) in devices.items():
            layers, warnings, _, _ = build_layers(kit, device_layout(layout, width, height), manifest)
            image = flatten(layers, (width, height))
            image.thumbnail((640, 360))
            thumbs.append((label, image))
            serious = [w for w in warnings if "outside" in w or "does not fit" in w]
            problems += len(serious)
            print(f"{screen} {label}: {len(serious)} problems")
            for warning in serious:
                print(f"  {warning}".encode("ascii", "replace").decode())
        board = Image.new("RGB", (sum(t.width for _, t in thumbs) + 16 * 5, 400), (245, 245, 245))
        draw = ImageDraw.Draw(board)
        x = 16
        for label, thumb in thumbs:
            draw.text((x, 8), label, fill=(20, 20, 20), font=load_font(20, None))
            board.paste(thumb, (x, 36))
            x += thumb.width + 16
        board.save(out_dir / f"{screen}.png")
    print(f"Boards are in preview/devices/. {problems} problems.")
    return 0


def cmd_spec(args) -> int:
    kit = Path(args.kit)
    manifest = load_manifest(kit)
    picked = selected_layouts(kit, args.screen, strict=False)
    out_dir = kit / "export" / "spec"
    out_dir.mkdir(parents=True, exist_ok=True)
    palette = read_palette(kit)
    for screen, path in picked.items():
        layout = read_layout(path)
        size = tuple(layout["size"])
        nodes, _ = build_tree(kit, layout, manifest, screen, None)
        font_path, _ = resolve_font(kit, layout)
        lines = [f"# {layout.get('title', screen)}", "", f"- Canvas: {size[0]} x {size[1]}",
                 f"- Font: {Path(font_path).name if font_path else 'not chosen'}",
                 f"- Palette: {', '.join(palette['colors']) if palette else 'not recorded'}", "",
                 "| Name | Type | X | Y | W | H | 9-slice (L B R T) | Text | Opens |", "|---|---|---|---|---|---|---|---|---|"]
        flat = []

        def collect(items, depth):
            for node in items:
                if not node.get("folder"):
                    flat.append((node, depth))
                collect(node.get("children", []), depth + (0 if node.get("folder") else 1))

        collect(nodes, 0)
        for node, depth in flat:
            item, entry = node["item"], node["entry"]
            x0, y0, x1, y1 = node["box"]
            nine = (entry or {}).get("nine_slice") or {}
            border = " ".join(str(nine[k]) for k in ("left", "bottom", "right", "top")) if nine.get("status") == "suggested" else ""
            text = str(item.get("text", "")).replace("|", "/")
            lines.append(f"| {'-- ' * depth}{node['name']} | {'sprite' if entry else 'text'} | {x0} | {y0} | {x1 - x0} | {y1 - y0} | {border} | {text} | {item.get('goto', '')} |")
        (out_dir / f"{screen}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"{screen}: export/spec/{screen}.md, {len(flat)} items")
    return 0


def contact_sheet(kit: Path, manifest: dict, cell: int = 170, columns: int = 6) -> Path:
    names = list(manifest["elements"])
    rows = max(1, (len(names) + columns - 1) // columns)
    sheet = Image.new("RGB", (columns * cell, rows * (cell + 24)), (250, 250, 250))
    draw = ImageDraw.Draw(sheet)
    for i, name in enumerate(names):
        x, y = (i % columns) * cell, (i // columns) * (cell + 24)
        path = kit / manifest["elements"][name]["file"]
        if path.exists():
            thumb = Image.open(path).convert("RGBA")
            thumb.thumbnail((cell - 12, cell - 12))
            tile = checker(cell - 4, cell - 4)
            tile.alpha_composite(thumb, ((cell - 4 - thumb.width) // 2, (cell - 4 - thumb.height) // 2))
            sheet.paste(tile.convert("RGB"), (x + 2, y + 2))
        short = name.split("/")[-1]
        draw.text((x + 4, y + cell + 2), short if len(short) <= 26 else short[:25] + "~", fill=(30, 30, 30))
    out = kit / "preview" / "contact_sheet.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return out


def cmd_qa(args) -> int:
    kit = Path(args.kit)
    manifest = load_manifest(kit)
    errors, warnings = [], []

    expected = set()
    for names_file in sorted((kit / "sheets").glob("*.txt")):
        expected |= set(read_names(names_file) or [])
    errors += [f"{n}: planned but not produced" for n in sorted(expected - set(manifest["elements"]))]

    groups: dict[str, list[tuple[str, tuple[int, int]]]] = {}
    for name, entry in manifest["elements"].items():
        path = kit / entry["file"]
        if not path.exists():
            errors.append(f"{name}: file missing")
            continue
        img = Image.open(path).convert("RGBA")
        pixels = np.asarray(img).astype(float)
        if min(img.size) < args.min_size:
            warnings.append(f"{name}: small ({img.width}x{img.height}), under {args.min_size} px")
        if entry.get("touches_sheet_edge"):
            warnings.append(f"{name}: touches the sheet edge, may be clipped")
        if entry.get("key_color"):
            visible = pixels[..., 3] > 128
            near = np.abs(pixels[..., :3] - from_hex(entry["key_color"])).max(axis=2) < 120
            share = (near & visible).sum() / max(1, visible.sum())
            if share > 0.01:
                warnings.append(f"{name}: {share:.1%} of pixels are close to the key color, check for fringe")
        nine = entry.get("nine_slice")
        if nine and nine.get("status") == "needs_review":
            warnings.append(f"{name}: 9-slice needs review")
        if nine and nine.get("large_borders") and not entry.get("derived_from"):
            warnings.append(f"{name}: 9-slice corners take most of its {' and '.join(nine['large_borders'])}, "
                            "so it only suits sizes near the original")
        if entry.get("has_transparency") is False:
            warnings.append(f"{name}: imported without transparency")
        if STATE_RE.search(name):
            groups.setdefault(STATE_RE.sub("", name), []).append((name, img.size))

    for group, members in groups.items():
        if len({size for _, size in members}) > 1:
            warnings.append(f"{group}: state sizes differ {dict(members)}")

    comparable = [n for n, e in manifest["elements"].items()
                  if not e.get("imported_from") and not e.get("derived_from") and not n.endswith("_disabled")]
    compare_path = kit / "compare_report.json"
    if compare_path.exists():
        compared = json.loads(compare_path.read_text(encoding="utf-8"))["elements"]
        warnings += [f"{n}: differs from references: {'; '.join(compared[n]['reasons'])}"
                     for n in comparable if compared.get(n, {}).get("status") == "review"]
        unchecked = [n for n in comparable if n not in compared]
        if unchecked:
            warnings.append(f"not compared with references yet: {unchecked}")
    elif comparable and reference_files(kit, [], manifest):
        warnings.append("references exist but compare has not been run")

    for layout_path in sorted((kit / "mockups").glob("*.json")):
        try:
            layout = json.loads(layout_path.read_text(encoding="utf-8"))
            planned = [i["element"] for i in layout.get("items", []) if isinstance(i, dict) and "element" in i]
        except (ValueError, AttributeError):
            warnings.append(f"mockup {layout_path.stem}: layout cannot be read")
            continue
        for name in sorted(set(planned) - set(manifest["elements"])):
            warnings.append(f"mockup {layout_path.stem}: uses missing element {name}")

    for screen, notes in richness_warnings(kit).items():
        warnings += [f"screen {screen}: {note}" for note in notes]

    sheet = contact_sheet(kit, manifest)
    report = {"elements": len(manifest["elements"]), "errors": errors, "warnings": warnings,
              "contact_sheet": sheet.relative_to(kit).as_posix()}
    (kit / "qa_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 2 if errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    p = commands.add_parser("slice", help="Cut one sheet into named element PNGs")
    p.add_argument("kit")
    p.add_argument("sheet", help="Sheet image, absolute or relative to the kit")
    p.add_argument("--names", help="Names file; defaults to the sheet path with .txt")
    p.add_argument("--gap", type=int, default=6, help="Parts closer than about this many px stay together")
    p.add_argument("--min-area", type=int, default=64, help="Ignore specks smaller than this many px")
    p.add_argument("--tolerance", type=int, default=24, help="Distance from key color treated as background")
    p.add_argument("--ramp", type=int, default=60, help="Distance over which edges fade to opaque")
    p.add_argument("--force", action="store_true", help="Replace existing elements")
    p.set_defaults(func=cmd_slice)

    p = commands.add_parser("import", help="Add existing loose PNG or WebP sprites to the kit, unchanged")
    p.add_argument("kit")
    p.add_argument("source", help="Folder or single image")
    p.add_argument("--prefix", help="Folder to put elements under, such as buttons")
    p.add_argument("--map", help="File with lines of: relative/file.png = element/name. Imports only these")
    p.add_argument("--force", action="store_true", help="Replace existing elements")
    p.set_defaults(func=cmd_import)

    p = commands.add_parser("backdrop", help="Blur and dim a screen into a background element for its popups")
    p.add_argument("kit")
    p.add_argument("screen", help="Parent screen, as named in mockups/")
    p.add_argument("--name", help="Element name, default backgrounds/bg_blur_<screen>")
    p.add_argument("--blur", type=float, default=14)
    p.add_argument("--dim", type=float, default=0.45, help="0 to 1, how much the dim color covers")
    p.add_argument("--color", default="#000000", help="Dim color")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_backdrop)

    p = commands.add_parser("shapes", help="Draw the standard common shapes in white, without image generation")
    p.add_argument("kit")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_shapes)

    p = commands.add_parser("palette", help="Record the kit's tone from an image or chosen colors")
    p.add_argument("kit")
    p.add_argument("image", nargs="?", help="Reference image")
    p.add_argument("--region", action="append", help="x0,y0,x1,y1 to sample only the UI, repeatable")
    p.add_argument("--hex", help="Comma-separated chosen colors, instead of an image")
    p.add_argument("--colors", type=int, default=8)
    p.add_argument("--force", action="store_true", help="Replace the recorded palette")
    p.set_defaults(func=cmd_palette)

    p = commands.add_parser("fonts", help="List kit fonts, check glyphs, or add a font from the catalog")
    p.add_argument("kit")
    p.add_argument("--add", help="Open-license font name from the catalog")
    p.set_defaults(func=cmd_fonts)

    p = commands.add_parser("compare", help="Compare elements with references and draw a side-by-side board")
    p.add_argument("kit")
    p.add_argument("--ref", action="append", help="Extra reference image, repeatable")
    p.add_argument("--match", action="append", help="Compare only these element patterns, repeatable")
    p.add_argument("--min-palette", type=float, default=0.55, help="Minimum share of pixels fitting the palette")
    p.add_argument("--color-distance", type=float, default=22, help="Lab distance that counts as fitting")
    p.set_defaults(func=cmd_compare)

    p = commands.add_parser("nineslice", help="Suggest 9-slice borders and render stretch previews")
    p.add_argument("kit")
    p.add_argument("--match", action="append", required=True, help="Element name pattern, repeatable")
    p.add_argument("--axis", choices=["both", "horizontal", "vertical"], default="both")
    p.add_argument("--tolerance", type=float, default=8, help="Allowed difference between adjacent lines")
    p.add_argument("--min-share", type=float, default=0.08, help="Minimum stretch band as a share of size")
    p.set_defaults(func=cmd_nineslice)

    p = commands.add_parser("states", help="Derive pressed and disabled from normal-state elements")
    p.add_argument("kit")
    p.add_argument("--match", action="append", required=True)
    p.add_argument("--force", action="store_true", help="Replace existing derived files")
    p.set_defaults(func=cmd_states)

    p = commands.add_parser("wireframe", help="Draw layouts as clean wireframes in a headless browser, before or without art")
    p.add_argument("kit")
    p.add_argument("--screen", help="One screen or variant; defaults to all layouts")
    p.set_defaults(func=cmd_wireframe)

    p = commands.add_parser("mockup", help="Assemble preview screens from the kit's sprites using layout files")
    p.add_argument("kit")
    p.add_argument("--screen", help="One screen or variant; defaults to all layouts")
    p.add_argument("--plan", action="store_true", help="Only report how many mockups would be made")
    p.set_defaults(func=cmd_mockup)

    p = commands.add_parser("choose", help="Record the approved variant of a screen")
    p.add_argument("kit")
    p.add_argument("screen")
    p.add_argument("variant", help="For example v2")
    p.set_defaults(func=cmd_choose)

    p = commands.add_parser("confirm", help="Confirm the wireframe or a screen; a later layout edit undoes it")
    p.add_argument("kit")
    p.add_argument("target", help="wireframe, or a screen name")
    p.add_argument("variant", nargs="?", help="For a screen: v2. For wireframe: one screen")
    p.set_defaults(func=cmd_confirm)

    p = commands.add_parser("vectorize", help="Redraw sprites as flat shapes and score them against the source")
    p.add_argument("kit")
    p.add_argument("--match", action="append")
    p.add_argument("--max-layers", type=int, default=24)
    p.add_argument("--max-points", type=int, default=6000)
    p.add_argument("--max-difference", type=float, default=6.0, help="Worse than this stays an image")
    p.add_argument("--force", action="store_true", help="Trace again")
    p.set_defaults(func=cmd_vectorize)

    p = commands.add_parser("recipe", help="Rebuild sprites as named shapes with layer effects, and compare with the source")
    p.add_argument("kit")
    p.add_argument("--match", action="append")
    p.add_argument("--auto", action="store_true", help="Write a first guess for sprites without a recipe")
    p.add_argument("--force", action="store_true", help="With --auto, replace existing recipes")
    p.add_argument("--max-difference", type=float, default=6.0, help="Above this the recipe needs work")
    p.set_defaults(func=cmd_recipe)

    p = commands.add_parser("psd", help="Build an editable PSD in Photoshop: shapes, live text, smart objects, groups")
    p.add_argument("kit")
    p.add_argument("--screen")
    p.add_argument("--background", choices=["redraw", "image"], help="Required when a screen has an image background")
    p.add_argument("--art", choices=["redraw", "image"], help="Required when a screen uses characters or environment art")
    p.add_argument("--redraw-kit", action="store_true",
                   help="Also redraw the user's kit sprites as shapes; by default they stay images under their own file names")
    p.add_argument("--unconfirmed", action="store_true", help="Also export screens not yet confirmed")
    p.add_argument("--layout", action="append", help="Export exactly this layout, such as home__v2; repeatable")
    p.add_argument("--no-run", action="store_true", help="Only write the Photoshop script")
    p.add_argument("--timeout", type=int, default=900)
    p.add_argument("--max-layers", type=int, default=24)
    p.add_argument("--max-points", type=int, default=6000)
    p.add_argument("--max-difference", type=float, default=6.0)
    p.add_argument("--force", action="store_true", help="Replace existing exports")
    p.set_defaults(func=cmd_psd)

    p = commands.add_parser("unity", help="Write a JSON mapping per screen for assembling in Unity")
    p.add_argument("kit")
    p.add_argument("--screen")
    p.add_argument("--unconfirmed", action="store_true")
    p.add_argument("--layout", action="append", help="Export exactly this layout, such as home__v2; repeatable")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_unity)

    p = commands.add_parser("resize-layout", help="Rescale layouts to a new canvas without distortion")
    p.add_argument("kit")
    p.add_argument("--size", default="1920x1080")
    p.add_argument("--screen")
    p.set_defaults(func=cmd_resize_layout)

    p = commands.add_parser("device", help="Preview screens at other aspect ratios")
    p.add_argument("kit")
    p.add_argument("--screen")
    p.set_defaults(func=cmd_device)

    p = commands.add_parser("spec", help="Write a handoff table per screen")
    p.add_argument("kit")
    p.add_argument("--screen")
    p.set_defaults(func=cmd_spec)

    p = commands.add_parser("flow", help="Draw the screen flow and build a clickable HTML demo")
    p.add_argument("kit")
    p.add_argument("--start", help="First screen of the demo")
    p.add_argument("--wireframe", action="store_true", help="Use wireframes instead of mockups")
    p.set_defaults(func=cmd_flow)

    p = commands.add_parser("export", help="Write layered PSD and flat PNG files for approved screens")
    p.add_argument("kit")
    p.add_argument("--screen", help="One screen; defaults to all")
    p.add_argument("--unconfirmed", action="store_true", help="Also export screens not yet confirmed")
    p.add_argument("--layout", action="append", help="Export exactly this layout, such as home__v2; repeatable")
    p.add_argument("--png-only", action="store_true", help="Write only export/png/, no flat PSD")
    p.add_argument("--force", action="store_true", help="Replace existing exports")
    p.set_defaults(func=cmd_export)

    p = commands.add_parser("info", help="Show the kit's status and the next step")
    p.add_argument("kit")
    p.set_defaults(func=cmd_info)

    p = commands.add_parser("qa", help="Check the kit and build the contact sheet")
    p.add_argument("kit")
    p.add_argument("--min-size", type=int, default=48)
    p.set_defaults(func=cmd_qa)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
