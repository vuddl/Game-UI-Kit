"""Shape recipes: how to rebuild one sprite in Photoshop from editable shapes and layer effects.

A recipe lives at <kit>/style/recipes/<element>.json and lists layers bottom to top:

    {"element": "frames/frame_activity", "size": [240, 240],
     "effects": {...},                       # optional, on the element's own group
     "layers": [
       {"name": "fill_rectangle", "shape": "rect", "box": [0, 0, 240, 240], "radius": 40,
        "fill": {"gradient": [["#f2d9a6", 0], ["#fff6de", 100]], "angle": 90},
        "effects": {"bevel": {"size": 10, "depth": 120}}},
       {"group": "stroke", "effects": {"bevel": {"size": 4}}, "layers": [
         {"name": "stroke_rectangle", "shape": "rect", "box": [0, 0, 240, 240], "radius": 40,
          "fill": "#ffffff", "fill_opacity": 0, "effects": {"stroke": {"size": 8, "color": "#2ec4d6"}}}]},
       {"name": "highlight_top_left", "shape": "ellipse", "box": [20, 14, 90, 40], "fill":
        {"gradient": [["#ffffff", 0, 0], ["#ffffff", 100, 90]], "angle": 90}, "clip": true}
     ]}

Coordinates are pixels of the sprite at its native size. The renderer here approximates Photoshop
closely enough to compare with the source; Photoshop itself draws the final file.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageFilter

SHAPES = {"rect", "ellipse", "path"}
EFFECTS = {"stroke", "bevel", "drop_shadow", "inner_shadow", "outer_glow", "inner_glow", "gradient_overlay", "color_overlay"}
BLENDS = {"normal", "multiply", "screen", "overlay", "soft_light", "hard_light", "color_dodge", "color_burn",
          "darken", "lighten", "linear_dodge", "linear_burn"}
LAYER_KEYS = {"name", "shape", "box", "radius", "points", "subpaths", "fill", "fill_opacity", "opacity", "blend",
              "clip", "effects", "hidden"}
GROUP_KEYS = {"group", "layers", "effects", "opacity", "blend", "hidden"}
SS = 2  # supersampling for the preview render


# ---------- validation ----------

def check_recipe(recipe: dict) -> list[str]:
    """Return problems with a recipe, empty when it is valid."""
    problems = []
    if not isinstance(recipe.get("size"), list) or len(recipe["size"]) != 2:
        problems.append('"size" must be [width, height] of the sprite')
    if not isinstance(recipe.get("layers"), list) or not recipe["layers"]:
        problems.append('"layers" must be a non-empty list')
        return problems
    problems += check_effects(recipe.get("effects"), "recipe")

    def walk(layers, where):
        for i, layer in enumerate(layers):
            at = f"{where}[{i}]"
            if "group" in layer:
                extra = set(layer) - GROUP_KEYS
                if extra:
                    problems.append(f"{at}: unknown group keys {sorted(extra)}")
                problems.extend(check_effects(layer.get("effects"), at))
                walk(layer.get("layers") or [], f"{at}.{layer['group']}")
                continue
            extra = set(layer) - LAYER_KEYS
            if extra:
                problems.append(f"{at}: unknown keys {sorted(extra)}")
            if layer.get("shape") not in SHAPES:
                problems.append(f"{at}: shape must be one of {sorted(SHAPES)}")
            elif layer["shape"] in ("rect", "ellipse") and not (isinstance(layer.get("box"), list) and len(layer["box"]) == 4):
                problems.append(f"{at}: {layer['shape']} needs box [x0, y0, x1, y1]")
            elif layer["shape"] == "path" and not (layer.get("points") or layer.get("subpaths")):
                problems.append(f"{at}: path needs points or subpaths")
            if layer.get("blend", "normal") not in BLENDS:
                problems.append(f"{at}: blend must be one of {sorted(BLENDS)}")
            try:
                parse_fill(layer.get("fill"))
            except ValueError as exc:
                problems.append(f"{at}: {exc}")
            problems.extend(check_effects(layer.get("effects"), at))
    walk(recipe["layers"], "layers")
    return problems


def check_effects(effects, where) -> list[str]:
    if not effects:
        return []
    if not isinstance(effects, dict):
        return [f"{where}: effects must be an object"]
    unknown = set(effects) - EFFECTS
    return [f"{where}: unknown effects {sorted(unknown)}, use {sorted(EFFECTS)}"] if unknown else []


# ---------- colors and fills ----------

def rgb(value, default="#ffffff") -> tuple[int, int, int]:
    return tuple(ImageColor.getrgb(value or default)[:3])


def parse_fill(fill):
    """Return ('solid', rgb) or ('gradient', [(rgb, position, opacity)], angle)."""
    if fill is None:
        return ("solid", (255, 255, 255))
    if isinstance(fill, str):
        try:
            return ("solid", rgb(fill))
        except ValueError:
            raise ValueError(f"fill {fill!r} is not a color")
    if isinstance(fill, dict) and isinstance(fill.get("gradient"), list) and len(fill["gradient"]) >= 2:
        stops = []
        for stop in fill["gradient"]:
            if not isinstance(stop, list) or len(stop) < 2:
                raise ValueError("gradient stops are [color, position 0-100] or [color, position, opacity]")
            stops.append((rgb(stop[0]), float(stop[1]), float(stop[2]) if len(stop) > 2 else 100.0))
        return ("gradient", sorted(stops, key=lambda s: s[1]), float(fill.get("angle", 90)))
    raise ValueError('fill must be "#rrggbb" or {"gradient": [[color, position], ...], "angle": 90}')


def gradient_image(stops, angle: float, size: tuple[int, int], box=None) -> np.ndarray:
    """Linear gradient as float RGBA (0-1). Angle as in Photoshop: 90 runs from the bottom (first stop) to the top."""
    w, h = size
    x0, y0, x1, y1 = box or (0, 0, w, h)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    rad = math.radians(angle)
    dx, dy = math.cos(rad), -math.sin(rad)
    half = abs((x1 - x0) / 2 * dx) + abs((y1 - y0) / 2 * dy) or 1
    ys, xs = np.mgrid[0:h, 0:w].astype(float) + 0.5
    t = np.clip((((xs - cx) * dx + (ys - cy) * dy) / half + 1) / 2 * 100, 0, 100)
    positions = [s[1] for s in stops]
    out = np.zeros((h, w, 4))
    for channel in range(3):
        out[..., channel] = np.interp(t, positions, [s[0][channel] / 255 for s in stops])
    out[..., 3] = np.interp(t, positions, [s[2] / 100 for s in stops])
    return out


def fill_image(fill, size, box) -> np.ndarray:
    kind = parse_fill(fill)
    if kind[0] == "solid":
        out = np.zeros((size[1], size[0], 4))
        out[..., :3] = np.array(kind[1]) / 255
        out[..., 3] = 1
        return out
    return gradient_image(kind[1], kind[2], size, box)


# ---------- masks ----------

def shape_mask(layer: dict, size: tuple[int, int], scale: float = SS) -> np.ndarray:
    """The layer's shape as a float mask (0-1) at size, with geometry multiplied by scale."""
    w, h = size
    image = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(image)
    kind = layer["shape"]
    if kind in ("rect", "ellipse"):
        x0, y0, x1, y1 = [v * scale for v in layer["box"]]
        if kind == "ellipse":
            draw.ellipse([x0, y0, x1 - 1, y1 - 1], fill=255)
        else:
            radius = layer.get("radius", 0)
            radius = max(radius) if isinstance(radius, list) else radius
            radius = min(radius * scale, (x1 - x0) / 2, (y1 - y0) / 2)
            draw.rounded_rectangle([x0, y0, x1 - 1, y1 - 1], radius=radius, fill=255)
    else:
        loops = layer.get("subpaths") or [layer["points"]]
        mask = Image.new("1", (w, h), 0)
        for loop in loops:
            piece = Image.new("1", (w, h), 0)
            ImageDraw.Draw(piece).polygon([(x * scale, y * scale) for x, y in loop], fill=1)
            mask = ImageChops.logical_xor(mask, piece)
        image = mask.convert("L")
    return np.asarray(image).astype(float) / 255


def box_blur(a: np.ndarray, width: int, axis: int) -> np.ndarray:
    """Mean over a window of this odd width along one axis, treating outside as empty."""
    half = width // 2
    pad = [(0, 0), (0, 0)]
    pad[axis] = (half + 1, half)
    c = np.cumsum(np.pad(a, pad), axis=axis)
    n = a.shape[axis]
    hi = np.take(c, np.arange(width, width + n), axis=axis)
    lo = np.take(c, np.arange(0, n), axis=axis)
    return (hi - lo) / width


def blur(mask: np.ndarray, sigma: float) -> np.ndarray:
    """Gaussian-like blur in floating point: three box passes per axis."""
    if sigma <= 0.3:
        return mask
    width = max(3, int(round(math.sqrt(4 * sigma * sigma + 1))) | 1)
    out = mask.astype(float)
    for axis in (0, 1):
        for _ in range(3):
            out = box_blur(out, width, axis)
    return out


def grow(mask: np.ndarray, pixels: float) -> np.ndarray:
    """Dilate (positive) or erode (negative) a mask by about this many pixels, with round corners like Photoshop."""
    if abs(pixels) < 0.5:
        return mask
    sigma = abs(pixels) / 2
    soft = blur(mask, sigma)
    # A blurred straight edge reaches 2.3% two sigmas outside it and 97.7% two sigmas inside.
    threshold = 0.023 if pixels > 0 else 0.977
    slope = 0.054 / sigma  # how fast the blurred edge changes per pixel at that point
    return np.clip((soft - threshold) / slope + 0.5, 0, 1)


def shift(mask: np.ndarray, dx: float, dy: float) -> np.ndarray:
    """Move a mask by (dx, dy) pixels; what moves in from outside is empty."""
    image = Image.fromarray((np.clip(mask, 0, 1) * 255).astype(np.uint8))
    moved = image.transform(image.size, Image.AFFINE, (1, 0, -dx, 0, 1, -dy), resample=Image.BILINEAR)
    return np.asarray(moved).astype(float) / 255


def light_vector(angle: float) -> tuple[float, float]:
    rad = math.radians(angle)
    return math.cos(rad), -math.sin(rad)


# ---------- compositing ----------

def over(dst: np.ndarray, src: np.ndarray) -> np.ndarray:
    """Source-over in straight alpha, float RGBA."""
    sa, da = src[..., 3:4], dst[..., 3:4]
    out_a = sa + da * (1 - sa)
    safe = np.where(out_a > 1e-6, out_a, 1)
    rgb_ = (src[..., :3] * sa + dst[..., :3] * da * (1 - sa)) / safe
    return np.concatenate([rgb_, out_a], axis=-1)


def blend_rgb(base: np.ndarray, top: np.ndarray, mode: str) -> np.ndarray:
    if mode == "multiply":
        return base * top
    if mode == "screen":
        return 1 - (1 - base) * (1 - top)
    if mode == "overlay":
        return np.where(base < 0.5, 2 * base * top, 1 - 2 * (1 - base) * (1 - top))
    if mode == "soft_light":
        return (1 - 2 * top) * base ** 2 + 2 * top * base
    if mode == "hard_light":
        return np.where(top < 0.5, 2 * base * top, 1 - 2 * (1 - base) * (1 - top))
    if mode == "darken":
        return np.minimum(base, top)
    if mode == "lighten":
        return np.maximum(base, top)
    if mode == "linear_dodge":
        return np.clip(base + top, 0, 1)
    if mode == "linear_burn":
        return np.clip(base + top - 1, 0, 1)
    if mode == "color_dodge":
        return np.clip(base / np.maximum(1e-3, 1 - top), 0, 1)
    if mode == "color_burn":
        return 1 - np.clip((1 - base) / np.maximum(1e-3, top), 0, 1)
    return top


def blend_over(dst: np.ndarray, src: np.ndarray, mode: str) -> np.ndarray:
    if mode == "normal":
        return over(dst, src)
    mixed = src.copy()
    mixed[..., :3] = np.where(dst[..., 3:4] > 0, blend_rgb(dst[..., :3], src[..., :3], mode), src[..., :3])
    return over(dst, mixed)


def solid(color, alpha: np.ndarray) -> np.ndarray:
    out = np.zeros(alpha.shape + (4,))
    out[..., :3] = np.array(rgb(color)) / 255
    out[..., 3] = np.clip(alpha, 0, 1)
    return out


# ---------- effects ----------

def effect_layers(effects: dict, mask: np.ndarray, body: np.ndarray, scale: float):
    """Return (below, body, above) after applying layer effects to a layer with this shape mask."""
    effects = effects or {}
    h, w = mask.shape
    below = np.zeros((h, w, 4))
    for key in ("outer_glow", "drop_shadow"):
        fx = effects.get(key)
        if not fx or fx.get("enabled") is False:
            continue
        size = fx.get("size", 10 if key == "outer_glow" else 6) * scale
        spread = fx.get("spread", 0) / 100
        source = grow(mask, size * spread)
        if key == "drop_shadow":
            lx, ly = light_vector(fx.get("angle", 120))
            distance = fx.get("distance", 4) * scale
            source = shift(source, -lx * distance, -ly * distance)
        alpha = blur(source, size / 2) * fx.get("opacity", 75 if key == "drop_shadow" else 60) / 100
        default = "#000000" if key == "drop_shadow" else "#ffffbe"
        layer = solid(fx.get("color", default), alpha)
        below = blend_over(below, layer, fx.get("blend", "multiply" if key == "drop_shadow" else "screen"))

    for key in ("gradient_overlay", "color_overlay"):
        fx = effects.get(key)
        if not fx or fx.get("enabled") is False:
            continue
        if key == "color_overlay":
            paint = solid(fx.get("color", "#ff0000"), mask)
        else:
            stops = parse_fill({"gradient": fx.get("gradient", [["#000000", 0], ["#ffffff", 100]]), "angle": fx.get("angle", 90)})
            paint = gradient_image(stops[1], stops[2], (w, h), bbox_of(mask))
            paint[..., 3] *= mask
        paint[..., 3] *= fx.get("opacity", 100) / 100
        body = blend_over(body, paint, fx.get("blend", "normal"))

    fx = effects.get("inner_glow")
    if fx and fx.get("enabled") is not False:
        size = fx.get("size", 10) * scale
        edge = np.clip((1 - blur(mask, size / 2)) * 2, 0, 1) * mask
        layer = solid(fx.get("color", "#ffffbe"), edge * fx.get("opacity", 75) / 100)
        body = blend_over(body, layer, fx.get("blend", "screen"))

    fx = effects.get("inner_shadow")
    if fx and fx.get("enabled") is not False:
        size = fx.get("size", 6) * scale
        lx, ly = light_vector(fx.get("angle", 120))
        distance = fx.get("distance", 4) * scale
        outside = shift(1 - mask, -lx * distance, -ly * distance)
        alpha = blur(outside, size / 2) * mask * fx.get("opacity", 75) / 100
        body = blend_over(body, solid(fx.get("color", "#000000"), alpha), fx.get("blend", "multiply"))

    fx = effects.get("bevel")
    if fx and fx.get("enabled") is not False:
        body, extra_below = bevel(fx, mask, body, scale)
        below = over(below, extra_below)

    above = np.zeros((h, w, 4))
    fx = effects.get("stroke")
    if fx and fx.get("enabled") is not False:
        size = fx.get("size", 3) * scale
        position = fx.get("position", "outside")
        if position == "inside":
            ring = np.clip(mask - grow(mask, -size), 0, 1)
        elif position == "center":
            ring = np.clip(grow(mask, size / 2) - grow(mask, -size / 2), 0, 1)
        else:
            ring = np.clip(grow(mask, size) - mask, 0, 1)
        if isinstance(fx.get("gradient"), list):
            stops = parse_fill({"gradient": fx["gradient"], "angle": fx.get("angle", 90)})
            paint = gradient_image(stops[1], stops[2], (w, h), bbox_of(mask))
            paint[..., 3] *= ring
        else:
            paint = solid(fx.get("color", "#000000"), ring)
        paint[..., 3] *= fx.get("opacity", 100) / 100
        above = paint
    return below, body, above


def bevel(fx: dict, mask: np.ndarray, body: np.ndarray, scale: float):
    """Approximate Photoshop's smooth bevel: light and shade from the slope of a softened mask."""
    size = max(1.0, fx.get("size", 5) * scale)
    soften = fx.get("soften", 0) * scale
    style = fx.get("style", "inner")
    softened = blur(mask, size / 2)
    if style == "inner":
        height = np.clip((softened - 0.5) * 2, 0, 1)
        region = mask
    elif style == "outer":
        height = np.clip(softened * 2, 0, 1)
        region = np.clip(grow(mask, size) - mask, 0, 1)
    else:  # emboss and pillow
        height = softened
        region = np.clip(grow(mask, size / 2), 0, 1)
    if soften:
        height = blur(height, soften / 2)
    gy, gx = np.gradient(height)
    lx, ly = light_vector(fx.get("angle", 120))
    altitude = math.radians(fx.get("altitude", 30))
    depth = fx.get("depth", 100) / 100
    shade = -(gx * lx + gy * ly) * size * depth * math.cos(altitude) * 1.6
    if fx.get("direction", "up") == "down":
        shade = -shade
    if style == "pillow":
        shade = np.where(mask > 0.5, shade, -shade)
    light = np.clip(shade, 0, 1) * region
    dark = np.clip(-shade, 0, 1) * region
    hl = solid(fx.get("highlight", "#ffffff"), light * fx.get("highlight_opacity", 75) / 100)
    sh = solid(fx.get("shadow", "#000000"), dark * fx.get("shadow_opacity", 75) / 100)
    if style == "inner":
        body = blend_over(body, hl, fx.get("highlight_blend", "screen"))
        body = blend_over(body, sh, fx.get("shadow_blend", "multiply"))
        return body, np.zeros(body.shape)
    outside = np.zeros(body.shape)
    inside_hl, inside_sh = hl.copy(), sh.copy()
    inside_hl[..., 3] *= mask
    inside_sh[..., 3] *= mask
    hl[..., 3] *= 1 - mask
    sh[..., 3] *= 1 - mask
    outside = over(over(outside, hl), sh)
    body = blend_over(blend_over(body, inside_hl, "screen"), inside_sh, "multiply")
    return body, outside


def bbox_of(mask: np.ndarray):
    ys, xs = np.nonzero(mask > 0.5)
    if not len(xs):
        return (0, 0, mask.shape[1], mask.shape[0])
    return (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)


# ---------- rendering ----------

def render_layers(layers: list[dict], size: tuple[int, int], scale: float):
    """Render a list of layers bottom to top. Return (image, union mask)."""
    w, h = size
    canvas = np.zeros((h, w, 4))
    union = np.zeros((h, w))
    clip_base = None
    for layer in layers:
        if layer.get("hidden"):
            continue
        if "group" in layer:
            image, mask = render_layers(layer.get("layers") or [], size, scale)
            image = apply_effects(image, mask, layer.get("effects"), scale)
            image[..., 3] *= layer.get("opacity", 100) / 100
            canvas = blend_over(canvas, image, layer.get("blend", "normal"))
            union = np.maximum(union, mask)
            clip_base = None
            continue
        mask = shape_mask(layer, size, scale)
        content = fill_image(layer.get("fill"), size, [v * scale for v in layer["box"]] if "box" in layer else None)
        content[..., 3] *= mask * layer.get("fill_opacity", 100) / 100
        below, body, above = effect_layers(layer.get("effects"), mask, content, scale)
        image = over(over(below, body), above)
        if layer.get("clip") and clip_base is not None:
            image[..., 3] *= clip_base
        else:
            clip_base = mask
        image[..., 3] *= layer.get("opacity", 100) / 100
        canvas = blend_over(canvas, image, layer.get("blend", "normal"))
        union = np.maximum(union, mask)
    return canvas, union


def apply_effects(image: np.ndarray, mask: np.ndarray, effects, scale: float) -> np.ndarray:
    """Effects on a group work on the group's combined pixels."""
    if not effects:
        return image
    alpha = image[..., 3]
    below, body, above = effect_layers(effects, alpha, image.copy(), scale)
    return over(over(below, body), above)


def render_recipe(recipe: dict) -> Image.Image:
    """Render a recipe at the sprite's native size, as RGBA."""
    w, h = recipe["size"]
    size = (int(w * SS), int(h * SS))
    image, mask = render_layers(recipe["layers"], size, SS)
    image = apply_effects(image, mask, recipe.get("effects"), SS)
    out = Image.fromarray((np.clip(image, 0, 1) * 255).astype(np.uint8), "RGBA")
    return out.resize((int(w), int(h)), Image.LANCZOS)


# ---------- automatic first guess ----------

def color_distance(a, b) -> float:
    return float(np.sqrt(((np.asarray(a, float) - np.asarray(b, float)) ** 2).sum()))


def hexcolor(c) -> str:
    return "#%02x%02x%02x" % tuple(int(round(v)) for v in c[:3])


def corner_radius(alpha: np.ndarray, box) -> float:
    """Estimate a rounded corner radius from how far the shape starts along each corner's diagonal."""
    x0, y0, x1, y1 = box
    limit = min(x1 - x0, y1 - y0) // 2
    found = []
    for cx, cy, sx, sy in ((x0, y0, 1, 1), (x1 - 1, y0, -1, 1), (x0, y1 - 1, 1, -1), (x1 - 1, y1 - 1, -1, -1)):
        for d in range(limit):
            if alpha[cy + sy * d, cx + sx * d] >= 128:
                # d steps along the diagonal are d*sqrt(2) pixels; a corner of radius r starts r*(sqrt(2)-1) in.
                found.append(d * math.sqrt(2) / (math.sqrt(2) - 1) if d else 0)
                break
    return float(np.median(found)) if found else 0.0


def iou(a: np.ndarray, b: np.ndarray) -> float:
    inter = np.logical_and(a, b).sum()
    union = np.logical_or(a, b).sum()
    return float(inter / union) if union else 0.0


def auto_recipe(path: Path, element: str) -> dict:
    """First guess for simple UI shapes: a rounded rectangle or ellipse with fill, gradient and border."""
    img = Image.open(path).convert("RGBA")
    pixels = np.asarray(img).astype(float)
    alpha = pixels[..., 3]
    solid_mask = alpha >= 128
    w, h = img.size
    recipe = {"element": element, "size": [w, h], "layers": []}
    if not solid_mask.any():
        recipe["status"] = "EMPTY"
        return recipe
    ys, xs = np.nonzero(solid_mask)
    box = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]
    bw, bh = box[2] - box[0], box[3] - box[1]
    radius = min(corner_radius(alpha, box), bw / 2, bh / 2)
    candidates = []
    for kind in ("rect", "ellipse"):
        layer = {"shape": kind, "box": box, "radius": round(radius, 1)}
        candidates.append((iou(shape_mask(layer, (w, h), 1) > 0.5, solid_mask), kind))
    fit, kind = max(candidates)
    if fit < 0.93:
        recipe["status"] = "NO_SIMPLE_SHAPE"
        recipe["fit"] = round(fit, 3)
        return recipe

    # The fill color: the middle of the shape.
    cx0, cy0 = box[0] + bw * 0.3, box[1] + bh * 0.3
    cx1, cy1 = box[0] + bw * 0.7, box[1] + bh * 0.7
    core = pixels[int(cy0):int(cy1) + 1, int(cx0):int(cx1) + 1]
    core = core[core[..., 3] >= 200][..., :3]
    fill = np.median(core, axis=0) if len(core) else np.array([200, 200, 200])

    # The border: walk in from each side's middle until the color reaches the fill's.
    widths, ring = [], []
    mid_x, mid_y = (box[0] + box[2]) // 2, (box[1] + box[3]) // 2
    for sx, sy, x, y, steps in ((1, 0, box[0], mid_y, bw // 2), (-1, 0, box[2] - 1, mid_y, bw // 2),
                                (0, 1, mid_x, box[1], bh // 2), (0, -1, mid_x, box[3] - 1, bh // 2)):
        run = []
        for d in range(int(steps * 0.45)):
            px = pixels[y + sy * d, x + sx * d]
            if px[3] < 128:
                continue
            if color_distance(px[:3], fill) < 38:
                break
            run.append(px[:3])
        if 0 < len(run) < min(bw, bh) * 0.25:
            widths.append(len(run))
            # Skip the soft outer pixel and the blend into the fill, keep the border's own color.
            core_run = run[1:max(2, int(len(run) * 0.6))] if len(run) > 2 else run
            ring += core_run
    stroke = None
    if len(widths) >= 3:
        stroke = {"size": int(round(float(np.median(widths)))), "color": hexcolor(np.median(np.array(ring), axis=0)),
                  "position": "inside"}

    # A vertical gradient inside the border.
    inset = stroke["size"] if stroke else 0
    column = []
    for t in (0.08, 0.3, 0.5, 0.7, 0.92):
        y = int(box[1] + inset + (bh - 2 * inset) * t)
        patch = pixels[max(0, y - 1):y + 2, mid_x - 2:mid_x + 3]
        patch = patch[patch[..., 3] >= 200][..., :3]
        column.append(np.median(patch, axis=0) if len(patch) else fill)
    fill_spec = hexcolor(fill)
    if color_distance(column[0], column[-1]) > 16:
        fill_spec = {"gradient": [[hexcolor(column[-1]), 0], [hexcolor(column[2]), 50], [hexcolor(column[0]), 100]], "angle": 90}

    round_ends = kind == "rect" and radius >= min(bw, bh) * 0.48
    if kind == "ellipse" or round_ends:
        shape_name = "circle" if abs(bw - bh) <= max(2, 0.04 * max(bw, bh)) else ("ellipse" if kind == "ellipse" else "pill")
    else:
        shape_name = "rectangle" if radius < 2 else "rounded_rectangle"
    base = {"shape": kind, "box": box}
    if kind == "rect":
        base["radius"] = round(radius, 1)
    recipe["layers"].append({"name": f"fill_{shape_name}", **base, "fill": fill_spec})
    if stroke:
        recipe["layers"].append({"group": "stroke", "layers": [
            {"name": f"stroke_{shape_name}", **base, "fill": "#ffffff", "fill_opacity": 0, "effects": {"stroke": stroke}}]})
    recipe["status"] = "AUTO"
    recipe["fit"] = round(fit, 3)
    return recipe


# ---------- Photoshop operations ----------

def to_photoshop(recipe: dict, name: str, mapper, opacity: float) -> dict:
    """Turn a recipe into a group of Photoshop operations, mapped from sprite pixels to the screen."""
    ox, oy = mapper(0, 0)
    ax, _ = mapper(1, 0)
    _, by = mapper(0, 1)
    unit = max(0.01, min(abs(ax - ox), abs(by - oy)))  # how many screen pixels one sprite pixel becomes, at the corners

    def scaled_effects(effects):
        if not effects:
            return None
        out = {}
        for key, fx in effects.items():
            fx = dict(fx)
            for k in ("size", "distance", "soften"):
                if k in fx:
                    fx[k] = round(fx[k] * unit, 2)
            out[key] = fx
        return out

    def convert(layers):
        ops = []
        for layer in layers:
            if layer.get("hidden"):
                continue
            if "group" in layer:
                ops.append({"op": "group", "name": layer["group"], "children": convert(layer.get("layers") or []),
                            "effects": scaled_effects(layer.get("effects")), "opacity": layer.get("opacity", 100),
                            "blend": layer.get("blend", "normal")})
                continue
            op = {"op": "shape", "name": layer.get("name") or f"{layer['shape']}_layer", "shape": layer["shape"],
                  "fill": fill_for_photoshop(layer.get("fill")), "fill_opacity": layer.get("fill_opacity", 100),
                  "opacity": layer.get("opacity", 100) * opacity / 100, "blend": layer.get("blend", "normal"),
                  "clip": bool(layer.get("clip")), "effects": scaled_effects(layer.get("effects"))}
            if layer["shape"] in ("rect", "ellipse"):
                x0, y0 = mapper(layer["box"][0], layer["box"][1])
                x1, y1 = mapper(layer["box"][2], layer["box"][3])
                op["box"] = [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)]
                radius = layer.get("radius", 0)
                radii = radius if isinstance(radius, list) else [radius] * 4
                op["radius"] = [round(r * unit, 2) for r in radii]
            else:
                loops = layer.get("subpaths") or [layer["points"]]
                op["subpaths"] = [[[round(v, 2) for v in mapper(x, y)] for x, y in loop] for loop in loops]
            ops.append(op)
        return ops

    return {"op": "group", "name": name, "children": convert(recipe["layers"]),
            "effects": scaled_effects(recipe.get("effects")), "opacity": 100, "blend": "normal"}


def fill_for_photoshop(fill):
    kind = parse_fill(fill)
    if kind[0] == "solid":
        return {"color": list(kind[1])}
    return {"gradient": [[list(c), p, o] for c, p, o in kind[1]], "angle": kind[2]}


def recipe_path(kit: Path, element: str) -> Path:
    return kit / "style" / "recipes" / f"{element}.json"


def load_recipe(kit: Path, element: str) -> dict | None:
    path = recipe_path(kit, element)
    if not path.exists():
        return None
    try:
        recipe = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None
    return recipe if recipe.get("layers") and not check_recipe(recipe) else None
