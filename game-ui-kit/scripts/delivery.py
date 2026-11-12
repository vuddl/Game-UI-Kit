"""Prepare standalone sources and package selected, reconstructed UI exports. Never paints or traces art."""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import shutil
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path

from PIL import Image

import background
import uikit
import sprite_quality

FORMATS = {'ui_kit', 'components_psd', 'screen_psd', 'unity', 'zip'}


def read(path: Path, default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')


def leaf(value: str) -> str:
    """Keep readable game-specific names while avoiding invalid Windows path components."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', str(value)).strip(' .')
    if not name or name in ('.', '..') or re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', name):
        raise ValueError(f'Invalid folder or resource name: {value!r}')
    return name


def brief_for(kit: Path) -> dict:
    brief = read(kit / 'briefs/export.json', {})
    selected = set(brief.get('formats') or [])
    if not selected or selected - FORMATS or selected == {'zip'}:
        raise ValueError('Submit the export form with at least one output type; ZIP is an additional selection.')
    if brief.get('draft'):
        raise ValueError('The export form has not been submitted yet.')
    return brief


def add_source(kit: Path, file: Path, screen: str = '') -> dict:
    from ask import store_upload
    entries = store_upload(kit, 'export', 'screens', file.name, file.read_bytes())
    record = read(kit / 'briefs/export.json', {})
    answers = record.setdefault('answers', {})
    answers['source'] = {'value': {'choice': 'provided'}}
    current = answers.setdefault('screens', {'value': []})['value']
    seen = {e['path'] for e in current}
    for entry in entries:
        if entry['path'] not in seen:
            current.append({**entry, 'screen': screen, 'note': ''})
            seen.add(entry['path'])
    record['draft'] = True
    write(kit / 'briefs/export.json', record)
    return {'files_added': len(entries), 'status': 'FORM_PREFILL', 'source_files_unchanged': True}


def prepare_sources(kit: Path) -> dict:
    brief = brief_for(kit)
    if brief.get('source') != 'provided' or not brief.get('sources'):
        raise ValueError('Choose supplied mockups and submit at least one source image first.')
    existing = {p.stem for p in uikit.layout_paths(kit)}
    counts = defaultdict(int)
    sources = []
    prior = read(kit / 'briefs/export_sources.json', {})
    known = {(s['file'], s.get('screen')): s for s in prior.get('screens', [])}
    for source in brief['sources']:
        path = background.kit_file(kit, source['file'])
        screen = uikit.slug(source.get('screen') or Path(source.get('name') or path.name).stem)
        with Image.open(path) as image:
            size = list(image.size)
        if max(size) > 8192:
            raise ValueError(f'{path.name}: source exceeds layout limit 8192; agree a uniform working size first.')
        old = known.get((source['file'], screen), {})
        source_hash = background.digest(path)
        stem = old.get('layout') if old.get('sha256') == source_hash else None
        if not stem:
            counts[screen] += 1
            stem = f'{screen}__v{counts[screen]}'
            while stem in existing:
                counts[screen] += 1
                stem = f'{screen}__v{counts[screen]}'
        existing.add(stem)
        sources.append({**source, 'screen': screen, 'layout': stem, 'size': size, 'sha256': source_hash,
                        'orientation': 'portrait' if size[1] > size[0] else 'landscape'})
    result = {'status': 'NEEDS_RECONSTRUCTION', 'screens': sources,
              'note': 'Inspect each source, separate real assets and build layouts before exporting. No setup was created.'}
    write(kit / 'briefs/export_sources.json', result)
    brief.update(layouts=[s['layout'] for s in sources], sources=sources)
    write(kit / 'briefs/export.json', brief)
    return result


def pixel_hash(path: Path) -> str:
    with Image.open(path) as opened:
        image = opened.convert('RGBA')
    return hashlib.sha256(str(image.size).encode() + image.tobytes()).hexdigest()


def collect(kit: Path, names: list[str]):
    manifest = uikit.load_manifest(kit)
    available = {p.stem: p for p in uikit.layout_paths(kit)}
    if not names or set(names) - set(available):
        raise ValueError('Reconstruct all selected source screens into layouts before packaging.')
    layouts, resources, hashes, warnings = {}, {}, {}, []
    for name in names:
        layout = uikit.read_layout(available[name])
        uikit.validate_background_export(kit, layout, name)
        layouts[name] = layout
        screen = uikit.screen_of(name)
        ids = {item['element'] for item in layout['items'] if item.get('element')}
        bg = layout.get('background')
        if bg and not bg.startswith('#'):
            ids.add(bg)
        for identifier in sorted(ids):
            entry = manifest['elements'].get(identifier)
            relative = entry['file'] if entry else identifier
            path = background.kit_file(kit, relative)
            if not path.is_file():
                raise ValueError(f'Missing component: {identifier}')
            signature = pixel_hash(path)
            key = hashes.setdefault(signature, identifier)
            if key not in resources:
                family = identifier.split('/')[0] if entry and '/' in identifier else 'Artwork'
                filename = Path((entry or {}).get('imported_from') or path.name).stem + '.png'
                resources[key] = {'source': relative, 'filename': leaf(filename), 'family': family,
                                  'aliases': [], 'screens': set(), 'sha256': signature, 'kind': 'image',
                                  'nine_slice': (entry or {}).get('nine_slice')}
            if identifier not in resources[key]['aliases']:
                resources[key]['aliases'].append(identifier)
            resources[key]['screens'].add(screen)
        font, origin = uikit.resolve_font(kit, layout)
        if font and Path(font).resolve().is_relative_to(kit.resolve()):
            path = Path(font).resolve()
            key = 'font:' + background.digest(path)
            if key not in resources:
                resources[key] = {'source': path.relative_to(kit.resolve()).as_posix(), 'filename': leaf(path.name),
                                  'family': 'Font', 'aliases': [], 'screens': set(), 'sha256': key[5:], 'kind': 'font'}
            resources[key]['screens'].add(screen)
        elif any('text' in item for item in layout['items']):
            warnings.append(f'{name}: font is external or a system fallback; no font file bundled')
    return layouts, resources, manifest, sorted(set(warnings))


def verify_psd(kit: Path, brief: dict, path: Path, report: dict, layout: str | None = None):
    selected = brief.get('photoshop') or {}
    if not selected.get('path'):
        raise ValueError('Choose Photoshop in the export form before creating or delivering PSDs.')
    recorded = report.get('photoshop') or {}
    if os.path.normcase(recorded.get('path', '')) != os.path.normcase(selected['path']):
        raise ValueError(f'{path.name}: verification does not match the chosen Photoshop installation.')
    if not path.is_file() or report.get('psd_sha256') != background.digest(path):
        raise ValueError(f'{path.name}: missing PSD or stale Photoshop verification.')
    if layout and report.get('layout_sha256') != background.digest(kit / f'mockups/{layout}.json'):
        raise ValueError(f'{path.name}: layout changed after Photoshop export.')
    if not layout and not report.get('verified'):
        raise ValueError('Verify the component master in Photoshop before packaging.')


def build(kit: Path, force: bool = False) -> dict:
    brief = brief_for(kit)
    selected = set(brief['formats'])
    layouts, assets, manifest, warnings = collect(kit, brief.get('layouts') or [])
    if brief.get('quality_required'):
        sprite_quality.validate_delivery(kit, [alias for v in assets.values() for alias in v['aliases']])
    folders = read(kit / 'briefs/export_folders.json', {})
    screen_folders = {uikit.screen_of(n): leaf(folders.get('screens', {}).get(uikit.screen_of(n), uikit.screen_of(n))) for n in layouts}
    if len({n.casefold() for n in screen_folders.values()}) != len(screen_folders) or any(n.casefold() == 'base' for n in screen_folders.values()):
        raise ValueError('Screen folder names must be unique and cannot be Base.')
    export = (kit / 'export').resolve()
    destination = export / 'delivery'
    if destination.exists() and not force:
        raise ValueError('Delivery exists. Use --force only when replacing it was requested.')
    if destination.is_symlink() or getattr(destination, 'is_junction', lambda: False)():
        raise ValueError('Refusing to replace a linked delivery directory.')
    export.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.delivery-stage-', dir=export))
    report = {'version': 1, 'formats': brief['formats'], 'layouts': list(layouts), 'resources': {}, 'warnings': warnings}
    try:
        occupied, alias_paths, source_paths = {}, {}, {}
        for key, asset in sorted(assets.items()):
            group = leaf(folders.get('assets', {}).get(key, folders.get('families', {}).get(asset['family'], asset['family'])))
            is_base = asset['kind'] == 'font' or len(asset['screens']) > 1 or any(
                fnmatch.fnmatch(alias, pattern) for pattern in folders.get('base', []) for alias in asset['aliases'])
            if 'ui_kit' in selected:
                if is_base:
                    parent = Path('UI/Base') / group
                else:
                    screen = next(iter(asset['screens']))
                    parent = Path('UI') / screen_folders[screen]
                    subgroup = folders.get('screen_groups', {}).get(screen, {}).get(asset['family'])
                    if subgroup:
                        parent /= leaf(subgroup)
            elif 'unity' in selected:
                parent = Path('Unity/Assets') / group
            elif asset['kind'] == 'font' and selected & {'components_psd', 'screen_psd'}:
                parent = Path('Fonts')
            else:
                parent = None
            target = parent / asset['filename'] if parent else None
            if target:
                lookup = target.as_posix().casefold()
                if lookup in occupied:
                    target = parent / f'{Path(asset["filename"]).stem}_{asset["sha256"][:8]}{Path(asset["filename"]).suffix}'
                occupied[target.as_posix().casefold()] = key
                path = stage / target
                path.parent.mkdir(parents=True, exist_ok=True)
                source = background.kit_file(kit, asset['source'])
                if asset['kind'] == 'image':
                    with Image.open(source) as image:
                        image.convert('RGBA').save(path)
                else:
                    shutil.copy2(source, path)
            entry = {**asset, 'screens': sorted(asset['screens']), 'file': target.as_posix() if target else None}
            report['resources'][key] = entry
            for alias in asset['aliases']:
                alias_paths[alias] = entry['file']
                relative = manifest['elements'].get(alias, {}).get('file', alias)
                source_paths[relative] = entry['file']
        for name, layout in layouts.items():
            if 'ui_kit' in selected:
                layers, notes, missing, _ = uikit.build_layers(kit, layout, manifest)
                if missing:
                    raise ValueError(f'{name}: missing {missing}')
                path = stage / 'UI' / screen_folders[uikit.screen_of(name)] / 'demo' / f'{name}.png'
                path.parent.mkdir(parents=True, exist_ok=True)
                uikit.flatten(layers, tuple(layout['size'])).save(path)
                warnings.extend(f'{name}: {note}' for note in notes)
            if 'screen_psd' in selected:
                source = kit / f'export/psd/{name}.psd'
                proof = read(kit / 'export/psd_report.json', {}).get(name, {})
                verify_psd(kit, brief, source, proof, name)
                path = stage / 'PSD' / source.name
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, path)
            if 'unity' in selected:
                mapping = read(kit / f'export/unity/{name}.json')
                if not mapping or mapping.get('source_layout_sha256') != background.digest(kit / f'mockups/{name}.json'):
                    raise ValueError(f'{name}: generate current Unity JSON before packaging.')
                def remap(node):
                    for field, value in list(node.items()):
                        if field in ('sprite', 'file') and isinstance(value, str) and value in source_paths:
                            node[field] = source_paths[value]
                        elif isinstance(value, dict):
                            remap(value)
                        elif isinstance(value, list):
                            for item in value:
                                if isinstance(item, dict):
                                    remap(item)
                remap(mapping)
                mapping.update(spritesRoot='..', resourceRoot='..')
                mapping['fontFiles'] = [entry['file'] for entry in report['resources'].values()
                                        if entry['kind'] == 'font' and uikit.screen_of(name) in entry['screens']]
                write(stage / 'Unity' / f'{name}.json', mapping)
        if 'components_psd' in selected:
            source = kit / 'export/psd/components.psd'
            proof = read(kit / 'export/components_report.json', {})
            verify_psd(kit, brief, source, proof)
            expected = {alias: asset['sha256'] for asset in assets.values() for alias in asset['aliases']}
            if proof.get('resources') != expected:
                raise ValueError('Component master verification does not cover the current selected resources.')
            (stage / 'PSD').mkdir(exist_ok=True)
            shutil.copy2(source, stage / 'PSD/components.psd')
        report['warnings'] = sorted(set(warnings))
        if 'zip' in selected:
            report['files'] = sorted('export/delivery/' + name for name in
                                     [p.relative_to(stage).as_posix() for p in stage.rglob('*') if p.is_file()] +
                                     ['report.json', 'UI_export.zip'])
            write(stage / 'report.json', report)
            with zipfile.ZipFile(stage / 'UI_export.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(stage.rglob('*')):
                    if path.is_file() and path.name != 'UI_export.zip':
                        archive.write(path, path.relative_to(stage).as_posix())
        relative_files = sorted(p.relative_to(stage).as_posix() for p in stage.rglob('*') if p.is_file())
        report['files'] = ['export/delivery/' + name for name in relative_files]
        # All selected outputs are built before replacing this generated, bounded destination.
        if destination.exists():
            if destination.resolve().parent != export:
                raise ValueError('Delivery destination escaped its export directory.')
            shutil.rmtree(destination)
        os.replace(stage, destination)
        write(export / 'delivery_report.json', report)
        return report
    finally:
        if stage.exists() and stage.resolve().parent == export and stage.name.startswith('.delivery-stage-'):
            shutil.rmtree(stage)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    add = sub.add_parser('add-source')
    add.add_argument('kit', type=Path)
    add.add_argument('file', type=Path)
    add.add_argument('--screen', default='')
    prepare = sub.add_parser('prepare')
    prepare.add_argument('kit', type=Path)
    package = sub.add_parser('build')
    package.add_argument('kit', type=Path)
    package.add_argument('--force', action='store_true')
    args = parser.parse_args()
    try:
        result = add_source(args.kit, args.file, args.screen) if args.command == 'add-source' else \
            prepare_sources(args.kit) if args.command == 'prepare' else build(args.kit, args.force)
        print(json.dumps(result, indent=2, ensure_ascii=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f'EXPORT_ERROR: {exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
