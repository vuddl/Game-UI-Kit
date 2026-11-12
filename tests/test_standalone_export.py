"""Standalone command, form and packaging behavior with synthetic source art."""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image, PngImagePlugin

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'game-ui-kit/scripts'))
import ask
import background
import delivery
import state
import uikit


class StandaloneExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.kit = self.root / 'kit'

    def save(self, relative, value):
        delivery.write(self.kit / relative, value)

    def mockups(self, formats=('ui_kit',)):
        entries = {}
        specs = [('controls/btn_blue', 'blue', (40, 20)), ('alias/same_button', 'blue', (40, 20)),
                 ('symbols/home_only', 'red', (20, 20)), ('rewards/shop_only', 'green', (20, 20))]
        for name, color, size in specs:
            path = self.kit / f'elements/{name}.png'
            path.parent.mkdir(parents=True, exist_ok=True)
            metadata = PngImagePlugin.PngInfo()
            metadata.add_text('original', name)
            Image.new('RGBA', size, color).save(path, pnginfo=metadata)
            entries[name] = {'file': path.relative_to(self.kit).as_posix(), 'width': size[0], 'height': size[1]}
        self.save('manifest.json', {'elements': entries})
        for screen, button, symbol in [('home', 'controls/btn_blue', 'symbols/home_only'),
                                       ('shop', 'alias/same_button', 'rewards/shop_only')]:
            self.save(f'mockups/{screen}__v1.json', {'size': [160, 90], 'background': '#203040',
                       'items': [{'element': button, 'x': 10, 'y': 10}, {'element': symbol, 'x': 70, 'y': 10}]})
        self.save('briefs/export.json', {'source': 'existing', 'formats': list(formats), 'layouts': ['home__v1', 'shop__v1']})
        self.save('briefs/export_folders.json', {'screens': {'home': 'Main', 'shop': 'Shop'},
                                               'families': {'controls': 'Controls'}})

    def test_command_starts_without_setup_even_in_new_folder(self):
        script = Path(state.__file__)
        done = subprocess.run([sys.executable, str(script), str(self.kit), 'begin', 'export'], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)['status'], 'START')
        self.assertFalse((self.kit / 'briefs/setup.json').exists())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(state.cmd_begin(self.kit, 'mockup'), 3)
        self.assertEqual(state.load(self.kit)['current'], 'export')

    def test_export_reset_removes_generated_work_and_preserves_original(self):
        self.root.joinpath('original.png').write_bytes(b'original')
        with contextlib.redirect_stdout(io.StringIO()):
            state.cmd_begin(self.kit, 'export')
            self.kit.joinpath('generated.txt').write_text('working')
            state.cmd_reset(self.kit)
        self.assertFalse(self.kit.joinpath('generated.txt').exists())
        self.assertEqual(self.root.joinpath('original.png').read_bytes(), b'original')
        self.assertEqual(state.load(self.kit)['current'], 'export')

    def test_export_switching_and_resume_without_setup(self):
        with contextlib.redirect_stdout(io.StringIO()):
            state.cmd_begin(self.kit, 'export')
            state.cmd_step(self.kit, 'reconstructing home')
            state.cmd_begin(self.kit, 'setup')
            state.cmd_begin(self.kit, 'export')
        data = state.load(self.kit)
        self.assertEqual(data['runs']['export']['step'], 'reconstructing home')
        self.assertEqual(data['runs']['export']['status'], 'active')
        self.assertFalse((self.kit / 'briefs/setup.json').exists())

    def test_fresh_export_form_has_five_multi_select_choices_and_upload_source(self):
        with patch.object(ask, 'discover_photoshop', return_value=[]):
            form = ask.load_form('export', self.kit)
        formats = next(q for q in form['questions'] if q['id'] == 'format')
        self.assertEqual(formats['type'], 'multi')
        self.assertEqual({o['value'] for o in formats['options']}, delivery.FORMATS)
        self.assertTrue(all(o['label'] and o['hint'] for o in formats['options']))
        self.assertEqual([o['value'] for o in form['questions'][0]['options']], ['provided'])
        self.assertTrue(form['questions'][0]['hidden'])
        self.assertEqual(form['questions'][0]['fixed_value']['choice'], 'provided')

    def test_export_offers_source_choice_when_kit_screens_exist(self):
        self.save('mockups/home__v1.json', {})
        with patch.object(ask, 'discover_photoshop', return_value=[]):
            source = ask.load_form('export', self.kit)['questions'][0]
        self.assertEqual({o['value'] for o in source['options']}, {'provided', 'existing'})
        self.assertFalse(source.get('hidden', False))
        self.assertNotIn('fixed_value', source)

    @unittest.skipUnless(uikit.find_browser(), 'Requires Edge or Chrome')
    def test_browser_hides_fixed_source_and_submits_uploaded_images(self):
        self.save('briefs/export.json', {})
        image = self.kit / 'inputs/home.png'
        image.parent.mkdir()
        Image.new('RGB', (32, 32), 'blue').save(image)
        with patch.object(ask, 'discover_photoshop', return_value=[]):
            form = ask.load_form('export', self.kit)
        prefill = {'source': {'value': {'choice': 'existing'}},
                   'screens': {'value': [{'path': 'inputs/home.png', 'screen': 'Home'}]},
                   'format': {'value': [{'choice': 'ui_kit'}]}}
        driver = r'''<script>
        (async () => {
          const result = document.createElement('pre'); document.body.append(result);
          window.close = () => {};
          try {
            while (!document.querySelector('#q_source')) await new Promise(r => setTimeout(r, 20));
            const source = document.querySelector('#q_source');
            if (!source.hidden || getComputedStyle(source).display !== 'none') throw Error('Source question still visible');
            if (VALUES.source.value.choice !== 'provided') throw Error('Stale source was not replaced');
            if (!document.querySelector('#q_screens') || document.querySelector('#q_layouts')) throw Error('Wrong dependent fields');
            await submit();
            if (!document.querySelector('.done')) throw Error('Hidden source prevented submission');
            result.textContent = 'EXPORT_SOURCE_PASSED';
          } catch (error) { result.textContent = 'EXPORT_SOURCE_FAILED: ' + error.stack; }
        })();</script>'''
        html = (ask.FORMS / 'form.html').read_text(encoding='utf-8').replace('</body>', driver + '</body>')

        class TestHandler(ask.Handler):
            def do_GET(self):
                if self.path == '/':
                    self.send(200, html.encode('utf-8'), 'text/html; charset=utf-8')
                else:
                    super().do_GET()

        out = self.kit / 'briefs/export.json'
        server = ask.FormServer(self.kit, form, out, prefill)
        server.RequestHandlerClass = TestHandler
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            run = subprocess.run([uikit.find_browser(), '--headless=new', '--disable-gpu', '--no-first-run',
                                  '--no-default-browser-check', '--disable-extensions',
                                  '--user-data-dir=' + str(self.kit / 'browser'), '--dump-dom',
                                  '--virtual-time-budget=10000', f'http://127.0.0.1:{server.server_port}/'],
                                 capture_output=True, timeout=45,
                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            output = run.stdout.decode('utf-8', errors='replace')
            self.assertTrue('<pre>EXPORT_SOURCE_PASSED</pre>' in output, output[-1500:])
            self.assertEqual(ask.read_json(out)['source'], 'provided')
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)

    def test_zip_alone_and_missing_input_are_rejected(self):
        for formats in [['zip'], ['ui_kit']]:
            answers = {'source': {'value': {'choice': 'provided'}},
                       'format': {'value': [{'choice': value} for value in formats]}}
            with self.assertRaises(ValueError):
                ask.apply_answers('export', self.kit, answers)

    def test_prefilled_sources_keep_dimensions_and_prepare_is_resumable(self):
        first, second = self.root / 'portrait.png', self.root / 'landscape.png'
        Image.new('RGB', (90, 160), 'pink').save(first)
        Image.new('RGB', (160, 90), 'blue').save(second)
        original = first.read_bytes()
        delivery.add_source(self.kit, first, 'home')
        delivery.add_source(self.kit, second, 'shop')
        draft = delivery.read(self.kit / 'briefs/export.json')
        with self.assertRaises(ValueError):
            delivery.prepare_sources(self.kit)
        answers = draft['answers']
        answers['format'] = {'value': [{'choice': 'ui_kit'}, {'choice': 'unity'}]}
        record = ask.apply_answers('export', self.kit, answers)
        self.save('briefs/export.json', record)
        prepared = delivery.prepare_sources(self.kit)
        self.assertEqual([s['size'] for s in prepared['screens']], [[90, 160], [160, 90]])
        stems = [s['layout'] for s in prepared['screens']]
        self.assertEqual(stems, [s['layout'] for s in delivery.prepare_sources(self.kit)['screens']])
        self.assertFalse((self.kit / 'briefs/setup.json').exists())
        self.assertFalse((self.kit / 'mockups').exists())
        self.assertEqual(first.read_bytes(), original)

    def test_shared_pixels_export_once_in_dynamic_base_with_screen_demos(self):
        self.mockups()
        report = delivery.build(self.kit)
        root = self.kit / 'export/delivery/UI'
        self.assertTrue((root / 'Base/Controls/btn_blue.png').is_file())
        self.assertTrue((root / 'Main/home_only.png').is_file())
        self.assertTrue((root / 'Shop/shop_only.png').is_file())
        self.assertTrue((root / 'Main/demo/home__v1.png').is_file())
        self.assertTrue((root / 'Shop/demo/shop__v1.png').is_file())
        self.assertFalse((root / 'Base/Popup').exists())
        self.assertEqual(len(list(root.rglob('*.png'))), 5)
        shared = next(r for r in report['resources'].values() if len(r['aliases']) == 2)
        self.assertEqual(shared['screens'], ['home', 'shop'])
        with Image.open(root / 'Main/demo/home__v1.png') as rendered:
            self.assertEqual(rendered.size, (160, 90))
            self.assertEqual(rendered.getpixel((12, 12))[:3], (0, 0, 255))
        self.assertFalse((self.kit / 'export/delivery/PSD').exists())
        self.assertFalse((self.kit / 'export/delivery/Unity').exists())

    def test_only_actual_families_are_created_for_reusable_assets(self):
        self.mockups()
        self.save('briefs/export_folders.json', {'base': ['symbols/*'], 'families': {'symbols': 'GameSymbols'}})
        delivery.build(self.kit)
        base = self.kit / 'export/delivery/UI/Base'
        self.assertTrue((base / 'GameSymbols/home_only.png').is_file())
        self.assertEqual({p.name for p in base.iterdir()}, {'controls', 'GameSymbols'})

    def test_available_native_font_is_a_single_base_resource(self):
        self.mockups()
        font = self.kit / 'fonts/game_font.otf'
        font.parent.mkdir()
        # No text is rendered in this fixture; verify native-file packaging and deduplication.
        font.write_bytes(b'font fixture bytes')
        report = delivery.build(self.kit)
        copied = self.kit / 'export/delivery/UI/Base/Font/game_font.otf'
        self.assertEqual(copied.read_bytes(), font.read_bytes())
        self.assertEqual(len([r for r in report['resources'].values() if r['kind'] == 'font']), 1)

    def test_unity_only_contains_its_required_assets_without_ui_demos(self):
        self.mockups(('unity',))
        args = SimpleNamespace(kit=str(self.kit), layout=['home__v1', 'shop__v1'], force=True)
        with contextlib.redirect_stdout(io.StringIO()):
            uikit.cmd_unity(args)
        delivery.build(self.kit)
        root = self.kit / 'export/delivery'
        self.assertFalse((root / 'UI').exists())
        mapping = delivery.read(root / 'Unity/home__v1.json')
        for node in mapping['nodes']:
            self.assertTrue((root / node['sprite']).is_file())
        self.assertEqual(len(list((root / 'Unity/Assets').rglob('*.png'))), 3)

    def test_combined_unity_and_ui_kit_reuse_the_same_files(self):
        self.mockups(('ui_kit', 'unity'))
        with contextlib.redirect_stdout(io.StringIO()):
            uikit.cmd_unity(SimpleNamespace(kit=str(self.kit), layout=['home__v1', 'shop__v1'], force=True))
        delivery.build(self.kit)
        root = self.kit / 'export/delivery'
        self.assertFalse((root / 'Unity/Assets').exists())
        mapping = delivery.read(root / 'Unity/shop__v1.json')
        self.assertEqual(mapping['nodes'][0]['sprite'], 'UI/Base/Controls/btn_blue.png')

    def test_zip_includes_only_selected_deliverables_and_report(self):
        self.mockups(('ui_kit', 'zip'))
        old = self.kit / 'export/psd/old.psd'
        old.parent.mkdir(parents=True)
        old.write_bytes(b'not selected')
        report = delivery.build(self.kit)
        with zipfile.ZipFile(self.kit / 'export/delivery/UI_export.zip') as archive:
            self.assertIn('UI/Main/demo/home__v1.png', archive.namelist())
            self.assertIn('report.json', archive.namelist())
            self.assertFalse(any(name.endswith('.psd') for name in archive.namelist()))
            self.assertNotIn('UI_export.zip', archive.namelist())
            self.assertTrue(json.loads(archive.read('report.json'))['files'])
        with contextlib.redirect_stdout(io.StringIO()) as output:
            state.cmd_summary(self.kit)
        summary = json.loads(output.getvalue())
        self.assertIsNone(summary['setup'])
        self.assertEqual(summary['export']['files'], report['files'])

    def test_failed_packaging_preserves_previous_delivery(self):
        self.mockups(('ui_kit', 'screen_psd'))
        prior = self.kit / 'export/delivery/prior.txt'
        prior.parent.mkdir(parents=True)
        prior.write_text('previous export')
        with self.assertRaises(ValueError):
            delivery.build(self.kit, force=True)
        self.assertEqual(prior.read_text(), 'previous export')
        self.assertFalse(list((self.kit / 'export').glob('.delivery-stage-*')))

    def test_stale_unity_mapping_is_rejected(self):
        self.mockups(('unity',))
        self.save('export/unity/home__v1.json', {'source_layout_sha256': 'old'})
        with self.assertRaises(ValueError):
            delivery.build(self.kit)

    def test_screen_specific_subgroups_can_follow_the_game(self):
        self.mockups()
        self.save('briefs/export_folders.json', {'screen_groups': {'shop': {'rewards': 'Reward_pack'}}})
        delivery.build(self.kit)
        self.assertTrue((self.kit / 'export/delivery/UI/shop/Reward_pack/shop_only.png').is_file())

    def test_component_master_requires_current_resource_proof(self):
        self.mockups(('components_psd',))
        brief = delivery.read(self.kit / 'briefs/export.json')
        brief['photoshop'] = {'path': r'C:\Example\Photoshop.exe', 'label': 'Selected Photoshop', 'version': 'test'}
        self.save('briefs/export.json', brief)
        master = self.kit / 'export/psd/components.psd'
        master.parent.mkdir(parents=True)
        master.write_bytes(b'synthetic bytes for packaging proof checks only')
        proof = {'verified': True, 'photoshop': brief['photoshop'], 'psd_sha256': background.digest(master)}
        self.save('export/components_report.json', proof)
        with self.assertRaises(ValueError):
            delivery.build(self.kit)
        assets = delivery.collect(self.kit, brief['layouts'])[1]
        proof['resources'] = {alias: asset['sha256'] for asset in assets.values() for alias in asset['aliases']}
        self.save('export/components_report.json', proof)
        delivery.build(self.kit)
        self.assertTrue((self.kit / 'export/delivery/PSD/components.psd').is_file())
        self.assertFalse((self.kit / 'export/delivery/UI').exists())

    def test_local_installer_includes_the_new_command_and_delivery_helper(self):
        repo = Path(__file__).resolve().parents[1]
        archive = self.root / 'install.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            for folder in ['game-ui-kit', 'commands']:
                for path in (repo / folder).rglob('*'):
                    if path.is_file() and '__pycache__' not in path.parts:
                        z.write(path, 'package/' + path.relative_to(repo).as_posix())
        codex = self.root / 'test-codex'
        done = subprocess.run([sys.executable, str(repo / 'game-ui-kit/scripts/update.py'), '--zip', str(archive)],
                              capture_output=True, text=True, env={**os.environ, 'CODEX_HOME': str(codex)})
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue((codex / 'skills/export/SKILL.md').is_file())
        self.assertTrue((codex / 'skills/game-ui-kit/scripts/delivery.py').is_file())
        self.assertIn('export', json.loads((codex / 'skills/.game-ui-kit.json').read_text()))


if __name__ == '__main__':
    unittest.main()
