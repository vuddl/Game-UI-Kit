#!/usr/bin/env python3
"""Turn UI sheets and loose sprites into a named kit with 9-slice data and checks.

Commands: slice, import, nineslice, states, compare, wireframe, mockup, choose, flow, export, info, qa.
Run any of them with --help.
Exit codes: 0 ok, 1 usage or input error, 2 result needs a fix (see output).
"""
from __future__ import annotations

import argparse
import base64
import fnmatch
import html
import io
import json
import re
import shutil
import struct
import sys
import unicodedata
from pathlib import Path

try:
    import numpy as np
    from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageFont
except ImportError as exc:
    sys.exit(f"Missing dependency: {exc.name}. Install with: py -3 -m pip install pillow numpy")

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
    if not refs:
        die("NO_REFERENCES", "add style/style_anchor.png, style/references/ or --ref.", 1)

    palette_sets, ref_pixels = [], []
    for ref in refs:
        pixels = visible_pixels(ref)
        if len(pixels):
            ref_pixels.append(pixels)
            palette_sets.append(palette_of(pixels))
    if not ref_pixels:
        die("NO_REFERENCES", "the references have no visible pixels.", 1)
    palette_rgb = np.concatenate(palette_sets)
    palette_lab = rgb_to_lab(palette_rgb)
    ref_lab = rgb_to_lab(np.concatenate(ref_pixels))
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
    summary = {"references": [p.name for p in refs][:20], "reference_count": len(refs),
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


def render_nine_slice(img: Image.Image, border: dict, width: int, height: int,
                      border_scale: float | None = None) -> Image.Image:
    w, h = img.size
    xs = [0, border["left"], w - border["right"], w]
    ys = [0, border["top"], h - border["bottom"], h]
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
    scale = min(scale, width / across if across else scale, height / down if down else scale)
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
    names = [n for n in selected(manifest, args.match) if n.endswith("_normal")]
    if not names:
        die("NO_MATCH", f"no *_normal elements match {args.match}", 1)
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
        base = name[: -len("_normal")]
        for state, pixels in variants.items():
            derived = f"{base}_{state}"
            target = kit / "elements" / f"{derived}.png"
            if target.exists() and not args.force:
                skipped += 1
                continue
            Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8), "RGBA").save(target)
            manifest["elements"][derived] = {**entry, "file": target.relative_to(kit).as_posix(),
                                             "derived_from": name}
            written += 1
    save_manifest(kit, manifest)
    print(f"Wrote {written} derived states, kept {skipped} existing files.")
    return 0


LAYOUT_KEYS = {"size", "title", "background", "reference", "font", "items"}
ITEM_KEYS = {"element", "text", "x", "y", "w", "h", "anchor", "mode", "border_scale", "opacity",
             "text_color", "text_size", "text_stroke", "fill", "group", "goto", "label"}
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
    paths = [p for p in (kit / "mockups").glob("*.json") if p.stem != "chosen"]
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
        if "element" not in item and "text" not in item:
            bad(f'{where}: needs "element" or "text"')
        if not is_number(item.get("x")) or not is_number(item.get("y")):
            bad(f'{where}: needs numeric "x" and "y"')
        for key in ("w", "h", "text_size", "text_stroke", "border_scale", "opacity", "fill"):
            if key in item and (not is_number(item[key]) or item[key] < 0 or (key in ("w", "h") and item[key] == 0)):
                bad(f'{where}: "{key}" must be a positive number')
        if "fill" in item and (item["fill"] > 1 or "w" not in item or "h" not in item):
            bad(f'{where}: "fill" must be from 0 to 1 and needs "w" and "h"')
        if item.get("anchor", "top_left") not in ANCHORS:
            bad(f'{where}: anchor must be one of {sorted(ANCHORS)}')
        if item.get("mode", "auto") not in ("auto", "nine", "fit", "stretch"):
            bad(f'{where}: mode must be auto, nine, fit or stretch')
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


def build_layers(kit: Path, layout: dict, manifest: dict):
    """Turn a layout into ordered layers. PNG mockups and PSD exports both draw from this."""
    size = tuple(layout["size"])
    width, height = size
    warnings, missing, used, boxes, layers = [], [], [], [], []
    warn = warnings.append
    font_path = layout.get("font")

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
        label = name or str(item.get("text"))
        boxes.append({"name": label, "box": box, "sprite": bool(sprite),
                      "touch": "goto" in item or bool(name and "_normal" in name)})
        if sprite is not None:
            if item.get("opacity", 1) < 1:
                sprite = sprite.copy()
                sprite.putalpha(sprite.getchannel("A").point(lambda a: round(a * item["opacity"])))
            layer = Image.new("RGBA", size, (0, 0, 0, 0))
            layer.paste(sprite, (x0 + offset_x, y0 + offset_y))
            add(layer, name.split("/")[-1], group)
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


def render_wireframe(kit: Path, path: Path, manifest: dict) -> Path:
    layout = read_layout(path)
    size = tuple(layout["size"])
    image = Image.new("RGB", size, (236, 238, 242))
    draw = ImageDraw.Draw(image)
    scale = min(size) / 500
    label_font = load_font(max(11, round(13 * scale)), layout.get("font"))
    for item in layout["items"]:
        name = item.get("element")
        entry = manifest["elements"].get(name) if name else None
        native = (entry["width"], entry["height"]) if entry and entry.get("width") else None
        x0, y0, x1, y1 = item_box(item, native, size)
        label = item.get("label") or item.get("text") or (name.split("/")[-1] if name else "")
        if name:
            link = "goto" in item
            draw.rectangle([x0, y0, x1, y1], fill=(214, 218, 226), outline=(40, 90, 220) if link else (110, 116, 130),
                           width=max(2, round(2 * scale)) if link else 1)
            if "text" not in item and x1 - x0 > 30 and y1 - y0 > 30:
                draw.line([x0, y0, x1, y1], fill=(186, 190, 200))
                draw.line([x0, y1, x1, y0], fill=(186, 190, 200))
        if link_target := item.get("goto"):
            label = f"{label} > {link_target}"
        if label:
            draw.text(((x0 + x1) / 2, (y0 + y1) / 2), str(label), font=label_font, fill=(30, 34, 44), anchor="mm")
    out = kit / "preview" / "wireframes" / f"{path.stem}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out)
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
    picked = selected_layouts(kit, args.screen)
    built = {}
    for screen, path in picked.items():
        layout = read_layout(path)
        layers, warnings, missing, _ = build_layers(kit, layout, manifest)
        if missing:
            die("MISSING_ELEMENT", f"{screen} uses missing elements {missing}. Fix the layout before exporting.")
        built[screen] = (layout, layers, warnings)

    psd_dir, png_dir = kit / "export" / "psd", kit / "export" / "png"
    targets = [psd_dir / f"{s}.psd" for s in built] + [png_dir / f"{s}.png" for s in built]
    existing = [t.name for t in targets if t.exists()]
    if existing and not args.force:
        die("EXISTS", f"{existing} already exist. Pass --force only if replacing them was requested.", 1)
    psd_dir.mkdir(parents=True, exist_ok=True)
    png_dir.mkdir(parents=True, exist_ok=True)

    report = {}
    for screen, (layout, layers, warnings) in built.items():
        size = tuple(layout["size"])
        merged = flatten(layers, size)
        merged.save(png_dir / f"{screen}.png")
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
    print(f"Exported {len(report)} screens. Text layers are pixels, not editable type.")
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
    exports = sorted(p.stem for p in (kit / "export" / "psd").glob("*.psd"))

    if not elements:
        step = "Create or import the art."
    elif not screens:
        step = "Propose layouts: /wireframe, then /mockup."
    elif undecided:
        step = f"Choose a variant for {undecided} with /choose, then /export."
    elif qa is None or qa["errors"]:
        step = "Run QA and fix any errors."
    elif len(exports) < len(screens):
        step = "When the screens are approved, run /export."
    else:
        step = "Everything is exported."
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
        "flow_demo": (kit / "demo" / "index.html").exists(),
        "exported_psd": exports,
        "next_step": step,
    }
    print(json.dumps(info, indent=2, ensure_ascii=True))
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

    p = commands.add_parser("states", help="Derive pressed and disabled from *_normal elements")
    p.add_argument("kit")
    p.add_argument("--match", action="append", required=True)
    p.add_argument("--force", action="store_true", help="Replace existing derived files")
    p.set_defaults(func=cmd_states)

    p = commands.add_parser("wireframe", help="Draw layouts as gray boxes, before or without art")
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

    p = commands.add_parser("flow", help="Draw the screen flow and build a clickable HTML demo")
    p.add_argument("kit")
    p.add_argument("--start", help="First screen of the demo")
    p.add_argument("--wireframe", action="store_true", help="Use wireframes instead of mockups")
    p.set_defaults(func=cmd_flow)

    p = commands.add_parser("export", help="Write layered PSD and flat PNG files for approved screens")
    p.add_argument("kit")
    p.add_argument("--screen", help="One screen; defaults to all")
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
