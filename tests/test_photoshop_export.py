"""Selection and execution checks; these never launch an installed Photoshop."""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'game-ui-kit' / 'scripts'))
import ask
import photoshop
import uikit


class PhotoshopExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.kit = Path(self.temp.name)
        (self.kit / 'mockups').mkdir()
        (self.kit / 'mockups/home__v1.json').write_text('{}')
        self.installs = [
            {'path': 'C:\\Adobe\\Photoshop 2021\\Photoshop.exe', 'label': 'Photoshop 2021', 'version': '22.0'},
            {'path': 'D:\\Adobe\\Photoshop 2026\\Photoshop.exe', 'label': 'Photoshop 2026', 'version': '27.11'},
        ]

    def answers(self, formats=('screen_psd',), choice=None):
        result = {'format': {'value': [{'choice': item} for item in formats]},
                  'source': {'value': {'choice': 'existing'}},
                  'background': {'value': {'choice': 'image'}},
                  'layouts': {'value': [{'choice': 'home__v1'}]}}
        if choice:
            result['photoshop'] = {'value': choice}
        return result

    def test_form_lists_each_install_with_path_and_version(self):
        with patch.object(ask, 'discover_photoshop', return_value=self.installs):
            form = ask.load_form('export', self.kit)
        question = next(q for q in form['questions'] if q['id'] == 'photoshop')
        self.assertTrue(question['required'])
        self.assertEqual(question['show_if'], {'question': 'format', 'in': ['components_psd', 'screen_psd']})
        self.assertEqual([item['value'] for item in question['options']], [i['path'] for i in self.installs])
        self.assertIn('27.11', question['options'][1]['label'])
        self.assertEqual(question['options'][1]['hint'], self.installs[1]['path'])

    def test_no_installs_or_failed_discovery_still_offer_manual_path_and_png(self):
        for behavior in ({'return_value': []}, {'side_effect': OSError('registry unavailable')}):
            with self.subTest(behavior=behavior), patch.object(ask, 'discover_photoshop', **behavior):
                form = ask.load_form('export', self.kit)
                question = next(q for q in form['questions'] if q['id'] == 'photoshop')
                self.assertEqual(question['options'], [])
                self.assertIn('PNG', question['hint'])
                self.assertTrue(question['other'])

    def test_psd_requires_explicit_choice(self):
        with self.assertRaises(ValueError):
            ask.apply_answers('export', self.kit, self.answers())

    def test_psd_saves_verified_selection_for_both_formats(self):
        selected = self.installs[1]
        with patch.object(ask, 'inspect_photoshop', return_value=selected) as inspect:
            record = ask.apply_answers('export', self.kit, self.answers(('screen_psd', 'ui_kit'), {'choice': selected['path']}))
        inspect.assert_called_once_with(selected['path'])
        self.assertEqual(record['photoshop'], selected)

    def test_manual_path_is_verified(self):
        selected = self.installs[1]
        with patch.object(ask, 'inspect_photoshop', return_value=selected) as inspect:
            record = ask.apply_answers('export', self.kit, self.answers(choice={'choice': 'other', 'label': '"' + selected['path'] + '"'}))
        inspect.assert_called_once_with(selected['path'])
        self.assertEqual(record['photoshop'], selected)

    def test_png_ignores_hidden_stale_photoshop_choice(self):
        with patch.object(ask, 'inspect_photoshop') as inspect:
            record = ask.apply_answers('export', self.kit, self.answers(('ui_kit',), {'choice': 'missing.exe'}))
        inspect.assert_not_called()
        self.assertNotIn('photoshop', record)

    def test_invalid_install_blocks_submission(self):
        with patch.object(ask, 'inspect_photoshop', side_effect=ValueError('removed')), self.assertRaises(ValueError):
            ask.apply_answers('export', self.kit, self.answers(choice={'choice': self.installs[0]['path']}))

    def test_cli_blocks_missing_or_removed_choice_before_writing(self):
        args = SimpleNamespace(kit=str(self.kit), no_run=False)
        for selected in (None, self.installs[0]):
            if selected:
                (self.kit / 'briefs').mkdir()
                (self.kit / 'briefs' / 'export.json').write_text(json.dumps({'photoshop': selected}))
            with patch.object(uikit, 'inspect_photoshop', side_effect=ValueError('removed')), \
                    patch.object(uikit, 'load_manifest') as load, self.assertRaises(SystemExit) as stopped:
                uikit.cmd_psd(args)
            self.assertEqual(stopped.exception.code, 3)
            load.assert_not_called()
            self.assertFalse((self.kit / 'export').exists())

    def capture_wrapper(self):
        exe = self.kit / "User's Photoshop bản thử" / 'Photoshop.exe'
        exe.parent.mkdir()
        exe.touch()
        script = self.kit / 'document.jsx'
        script.write_text('"{\\"ok\\":true}";')
        captured = {}

        def fake_launch(command, **kwargs):
            captured['command'] = command
            captured['source'] = Path(command[2]).read_text(encoding='utf-8')
            output_path = json.loads(re.search(r'var report = new File\((.+)\);', captured['source']).group(1))
            Path(output_path).write_text('{"ok":true}', encoding='utf-8')

        with patch.object(photoshop.subprocess, 'Popen', side_effect=fake_launch) as launch:
            result = photoshop.run_photoshop(script, 5, {'path': str(exe)})
        self.assertTrue(result['ok'])
        self.assertEqual(launch.call_count, 1)
        self.assertEqual(captured['command'][:2], [str(exe.resolve()), '-r'])
        return captured['source']

    def test_runner_launches_only_selected_executable(self):
        self.capture_wrapper()

    @unittest.skipUnless(shutil.which('node'), 'Node is needed to evaluate the JSX guard')
    def test_wrong_application_is_rejected_before_document_script_runs(self):
        source = self.capture_wrapper()
        harness = r'''
const vm = require('vm');
let evaluated = false, output;
const context = {
  Folder: function(path) { this.fsName = path; },
  File: function() { this.open = () => {}; this.write = s => output = s; this.close = () => {}; },
  app: {path: {fsName: 'C:/another Photoshop'}},
  $: {evalFile: () => { evaluated = true; return '{"ok":true}'; }}
};
vm.runInNewContext(SOURCE, context);
if (evaluated || JSON.parse(output).ok !== false) process.exit(1);
'''
        done = subprocess.run(['node', '-e', 'const SOURCE = ' + json.dumps(source) + ';' + harness], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_missing_executable_never_launches_another_version(self):
        with patch.object(photoshop.subprocess, 'Popen') as launch:
            result = photoshop.run_photoshop(self.kit / 'x.jsx', 5, {'path': str(self.kit / 'missing.exe')})
        self.assertFalse(result['ok'])
        launch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
