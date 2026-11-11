"""Plan outpainting and check uniform background coverage. Does not generate or separate artwork."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def kit_file(kit: Path, relative: str) -> Path:
    path = (kit / relative).resolve()
    if not path.is_relative_to(kit.resolve()):
        raise ValueError('Background paths must stay inside the kit.')
    return path


def size_pair(value) -> tuple[int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 2 or any(
            isinstance(n, bool) or not isinstance(n, int) or n <= 0 for n in value):
        raise ValueError('Sizes must be positive integer [width, height] pairs.')
    return tuple(value)


def parse_size(value: str) -> tuple[int, int]:
    return size_pair([int(n) for n in value.lower().split('x')])


def default_targets(base) -> list[list[int]]:
    w, h = size_pair(base)
    sizes = [(1080, 1920), (1080, 2400), (1536, 2048)]
    if w > h:
        sizes = [(height, width) for width, height in sizes]
    return [list(s) for s in dict.fromkeys([(w, h), *sizes])]


def cover_geometry(source, target, alignment=(0.5, 0.5)) -> dict:
    sw, sh = size_pair(source)
    tw, th = size_pair(target)
    if len(alignment) != 2 or any(isinstance(n, bool) or not isinstance(n, (int, float)) or
                                  not math.isfinite(n) or not 0 <= n <= 1 for n in alignment):
        raise ValueError('Alignment must contain two numbers from 0 to 1, measured from top left.')
    scale = max(tw / sw, th / sh)
    cw, ch = tw / scale, th / scale
    left, top = (sw - cw) * alignment[0], (sh - ch) * alignment[1]
    x, y = -left * scale, -top * scale
    return {'scale': scale, 'box': [x, y, x + sw * scale, y + sh * scale],
            'crop': [left, top, left + cw, top + ch]}


def expansion_plan(source, targets) -> dict:
    """Center the entire original frame inside every target's visible crop, without stretching."""
    w, h = size_pair(source)
    targets = [list(size_pair(t)) for t in targets]
    if not targets:
        raise ValueError('At least one target size is required.')
    ratios = [tw / th for tw, th in targets]
    # Two source pixels guard the integer placement of odd-sized original frames.
    mw = math.ceil((max(w, h * max(ratios)) + 2) / 4) * 4
    mh = math.ceil((max(h, w / min(ratios)) + 2) / 4) * 4
    left, top = (mw - w) // 2, (mh - h) // 2
    return {'sourceSize': [w, h], 'canvasSize': [mw, mh],
            'originalFrame': [left, top, w, h],
            'expandPixels': {'left': left, 'top': top, 'right': mw - w - left, 'bottom': mh - h - top},
            'targets': targets, 'alignment': [0.5, 0.5],
            'scope': 'Centered uniform cover for the listed aspect range; remeasure the actual generated image.'}


def load_profile(kit: Path, relative: str) -> dict:
    profile = json.loads(kit_file(kit, relative).read_text(encoding='utf-8'))
    if not isinstance(profile, dict):
        raise ValueError('Background profile must be an object.')
    image = kit_file(kit, profile['image'])
    with Image.open(image) as opened:
        source = opened.size
    targets = [size_pair(t) for t in profile['targets']]
    if not targets:
        raise ValueError('Background profile needs target sizes.')
    cover_geometry(source, targets[0], profile.get('alignment', [0.5, 0.5]))
    if not isinstance(profile.get('protected'), list):
        raise ValueError('List protected subjects; use [] explicitly for an abstract background.')
    for subject in profile['protected']:
        rect = subject['rect']
        if len(rect) != 4 or any(isinstance(n, bool) or not isinstance(n, (int, float)) or not math.isfinite(n) for n in rect):
            raise ValueError('Protected rect must be [x, y, width, height] in actual master pixels.')
        x, y, w, h = rect
        if min(x, y) < 0 or min(w, h) <= 0 or x + w > source[0] or y + h > source[1]:
            raise ValueError('Protected rect lies outside the actual master.')
        tolerance = subject.get('max_crop', 0)
        if not isinstance(tolerance, (int, float)) or not math.isfinite(tolerance) or not 0 <= tolerance < 1:
            raise ValueError('max_crop must be an area fraction from 0 up to, but excluding, 1.')
    return profile


def visible_fraction(rect, crop) -> float:
    x, y, w, h = rect
    left, top, right, bottom = crop
    return max(0, min(x + w, right) - max(x, left)) * max(0, min(y + h, bottom) - max(y, top)) / (w * h)


def render_cover(image: Image.Image, target, alignment=(0.5, 0.5)) -> Image.Image:
    geometry = cover_geometry(image.size, target, alignment)
    # A single source crop transformed to target size uses one scale on both axes.
    return image.convert('RGBA').resize(tuple(target), Image.Resampling.LANCZOS, box=geometry['crop'])


def check_profile(kit: Path, relative: str, layout_name: str | None = None) -> dict:
    profile = load_profile(kit, relative)
    image_path = kit_file(kit, profile['image'])
    with Image.open(image_path) as opened:
        image = opened.convert('RGBA')
    opaque = image.getextrema()[3][0] == 255
    results, thumbs = [], []
    layout = manifest = None
    if layout_name:
        import uikit
        layout = uikit.read_layout(kit_file(kit, f'mockups/{layout_name}.json'))
        manifest = uikit.load_manifest(kit)
        if layout.get('background_profile') != relative:
            raise ValueError('Overlay layout must reference this background_profile.')
    for target in profile['targets']:
        geometry = cover_geometry(image.size, target, profile.get('alignment', [0.5, 0.5]))
        subjects = [{'name': s['name'], 'visibleFraction': visible_fraction(s['rect'], geometry['crop']),
                     'maxCrop': s.get('max_crop', 0)} for s in profile['protected']]
        ok = opaque and all(s['visibleFraction'] + 1e-8 >= 1 - s['maxCrop'] for s in subjects)
        results.append({'size': target, **geometry, 'subjects': subjects, 'geometry_ok': ok})
        preview = render_cover(image, target, profile.get('alignment', [0.5, 0.5]))
        if layout:
            preview = uikit.flatten(uikit.build_layers(kit, uikit.device_layout(layout, *target), manifest)[0], tuple(target))
        preview.thumbnail((420, 420))
        thumbs.append((f'{target[0]}x{target[1]}  ' + ('PASS' if ok else 'REVIEW'), preview))
    columns = min(3, len(thumbs))
    board = Image.new('RGB', (columns * 444, math.ceil(len(thumbs) / columns) * 464), '#20242b')
    draw = ImageDraw.Draw(board)
    for index, (label, preview) in enumerate(thumbs):
        x, y = index % columns * 444 + 12, index // columns * 464 + 10
        draw.text((x, y), label, fill='white')
        board.paste(preview.convert('RGB'), (x, y + 24))
    name = Path(relative).stem
    suffix = layout_name or 'clean'
    out = kit / 'preview' / 'backgrounds' / f'{name}__{suffix}.png'
    out.parent.mkdir(parents=True, exist_ok=True)
    board.save(out)
    report = {'version': 1, 'profile': relative, 'image': profile['image'], 'sourceSize': list(image.size),
              'image_sha256': digest(image_path), 'profile_sha256': digest(kit_file(kit, relative)),
              'geometry_ok': all(r['geometry_ok'] for r in results), 'opaque': opaque,
              'visual_review_required': True, 'preview': out.relative_to(kit).as_posix(), 'targets': results}
    destination = kit / 'export' / 'backgrounds' / f'{name}.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    prior = {}
    if destination.exists():
        try:
            prior = json.loads(destination.read_text(encoding='utf-8'))
        except ValueError:
            pass
    report['overlays'], report['previews'] = {}, {}
    if all(prior.get(key) == report[key] for key in ('image_sha256', 'profile_sha256')):
        report['previews'] = prior.get('previews', {})
        for stem, proof in prior.get('overlays', {}).items():
            path = kit_file(kit, f'mockups/{stem}.json')
            if path.is_file() and proof.get('layout_sha256') == digest(path):
                report['overlays'][stem] = proof
    report['previews'][suffix] = out.relative_to(kit).as_posix()
    if layout_name:
        report['overlays'][layout_name] = {'layout_sha256': digest(kit_file(kit, f'mockups/{layout_name}.json')),
                                         'preview': out.relative_to(kit).as_posix()}
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    return report


def current_report(kit: Path, relative: str, layout_name: str | None = None) -> dict:
    profile = load_profile(kit, relative)
    report = json.loads((kit / 'export' / 'backgrounds' / f'{Path(relative).stem}.json').read_text(encoding='utf-8'))
    if report.get('profile') != relative or report.get('image_sha256') != digest(kit_file(kit, profile['image'])) or \
            report.get('profile_sha256') != digest(kit_file(kit, relative)):
        raise ValueError('Background QA is stale. Run background.py check again.')
    if layout_name:
        proof = report.get('overlays', {}).get(layout_name, {})
        if proof.get('layout_sha256') != digest(kit_file(kit, f'mockups/{layout_name}.json')):
            raise ValueError('This UI overlay is missing or changed. Run background.py check with --layout again.')
    if not report.get('geometry_ok'):
        raise ValueError('Background has transparent gaps or cropped protected subjects. Fix it before export.')
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    plan = sub.add_parser('plan')
    plan.add_argument('kit', type=Path)
    plan.add_argument('--source', required=True, help='Demo or clean background, relative to kit')
    plan.add_argument('--target', action='append', required=True, help='WIDTHxHEIGHT; repeat for each target')
    plan.add_argument('--out', required=True, help='Plan JSON path, relative to kit')
    check = sub.add_parser('check')
    check.add_argument('kit', type=Path)
    check.add_argument('--profile', required=True, help='Profile JSON path, relative to kit')
    check.add_argument('--layout', help='Optional mockup stem to preview the UI over the background')
    args = parser.parse_args()
    try:
        if args.command == 'plan':
            source = kit_file(args.kit, args.source)
            with Image.open(source) as image:
                report = expansion_plan(image.size, [parse_size(t) for t in args.target])
            report.update(source=args.source, source_sha256=digest(source))
            out = kit_file(args.kit, args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(report, indent=2), encoding='utf-8')
        else:
            report = check_profile(args.kit, args.profile, args.layout)
        print(json.dumps(report, indent=2, ensure_ascii=True))
        return 0 if report.get('geometry_ok', True) else 2
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f'BACKGROUND_ERROR: {exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
