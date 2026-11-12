"""Selection and execution checks; these never launch an installed Photoshop."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
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

        with patch.object(photoshop, 'prepare_script_preferences', return_value={'ok': True}), \
                patch.object(photoshop.subprocess, 'Popen', side_effect=fake_launch) as launch:
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

    def test_script_config_uses_selected_version_before_first_launch(self):
        with patch.dict(os.environ, {'APPDATA': str(self.kit)}):
            config = photoshop.script_config_path({'path': 'X:/Custom/Photoshop.exe', 'version': '27.11'})
        self.assertEqual(config, self.kit / 'Adobe/Adobe Photoshop 2026/Adobe Photoshop 2026 Settings/PSUserConfig.txt')
        self.assertFalse(config.exists())
        self.assertTrue(photoshop.disable_script_warning(config))
        self.assertEqual(config.read_text(), 'WarnRunningScripts 0\n')
        stamp = config.stat().st_mtime_ns
        self.assertFalse(photoshop.disable_script_warning(config))
        self.assertEqual(config.stat().st_mtime_ns, stamp)

    def test_script_flag_preserves_encoding_other_settings_and_backup(self):
        for encoding, bom in [('utf-8', b'\xef\xbb\xbf'), ('utf-16-le', b'\xff\xfe'), ('utf-16-be', b'\xfe\xff')]:
            with self.subTest(encoding=encoding):
                config = self.kit / encoding / 'PSUserConfig.txt'
                config.parent.mkdir()
                original = bom + '# Ghi chú\r\nOtherFlag 1\r\nWarnRunningScripts 1\r\nWarnRunningScripts 1 # keep\r\n'.encode(encoding)
                config.write_bytes(original)
                self.assertTrue(photoshop.disable_script_warning(config))
                expected = original.decode(encoding).replace('WarnRunningScripts 1', 'WarnRunningScripts 0')
                self.assertEqual(config.read_bytes(), expected.encode(encoding))
                self.assertEqual(config.with_name(config.name + '.game-ui-kit.bak').read_bytes(), original)

    def test_runner_configures_before_launch_without_showing_a_script_dialog(self):
        exe = self.kit / 'Photoshop.exe'
        exe.touch()
        selected = {'path': str(exe), 'version': '27.11'}
        with patch.dict(os.environ, {'APPDATA': str(self.kit)}), \
                patch.object(photoshop, 'selected_process_starts', return_value=[]), \
                patch.object(photoshop.subprocess, 'Popen') as launch:
            def verify_launch(*args, **kwargs):
                self.assertIn('WarnRunningScripts 0', photoshop.script_config_path(selected).read_text())
                raise OSError('Test stops before launching Photoshop')
            launch.side_effect = verify_launch
            result = photoshop.run_photoshop(self.kit / 'test.jsx', 1, selected)
        self.assertEqual(launch.call_count, 1)
        self.assertFalse(result['ok'])

    def test_running_photoshop_requires_restart_before_any_jsx_is_sent(self):
        exe = self.kit / 'Photoshop.exe'
        exe.touch()
        with patch.dict(os.environ, {'APPDATA': str(self.kit)}), \
                patch.object(photoshop, 'selected_process_starts', return_value=[1]), \
                patch.object(photoshop.subprocess, 'Popen') as launch:
            result = photoshop.run_photoshop(self.kit / 'test.jsx', 1, {'path': str(exe), 'version': '27.11'})
        self.assertEqual(result['code'], 'PHOTOSHOP_RESTART_REQUIRED')
        launch.assert_not_called()

    def test_restarted_app_with_current_config_is_ready(self):
        selected = {'path': str(self.kit / 'Photoshop.exe'), 'version': '27.11'}
        with patch.dict(os.environ, {'APPDATA': str(self.kit)}), \
                patch.object(photoshop, 'selected_process_starts', return_value=[time.time() + 10]):
            config = photoshop.script_config_path(selected)
            photoshop.disable_script_warning(config)
            result = photoshop.prepare_script_preferences(selected)
        self.assertTrue(result['ok'])
        self.assertFalse(result['changed'])

    def test_config_failure_does_not_launch_photoshop(self):
        exe = self.kit / 'Photoshop.exe'
        exe.touch()
        with patch.object(photoshop, 'disable_script_warning', side_effect=PermissionError('Read only')), \
                patch.dict(os.environ, {'APPDATA': str(self.kit)}), \
                patch.object(photoshop.subprocess, 'Popen') as launch:
            result = photoshop.run_photoshop(self.kit / 'test.jsx', 1, {'path': str(exe), 'version': '27.11'})
        self.assertEqual(result['code'], 'PHOTOSHOP_SCRIPT_CONFIG_FAILED')
        launch.assert_not_called()

    @unittest.skipUnless(uikit.find_browser(), 'Requires Edge or Chrome')
    def test_export_form_configures_selected_app_and_rechecks_after_restart(self):
        with patch.object(ask, 'discover_photoshop', return_value=self.installs):
            form = ask.load_form('export', self.kit)
        prefill = self.answers()
        driver = r'''<script>
        (async () => {
          const result = document.createElement('pre'); document.body.append(result);
          window.close = () => {};
          const waitFor = async fn => {
            for (let i = 0; i < 300; i++) {
              if (fn()) return;
              await new Promise(r => setTimeout(r, 20));
            }
            throw Error('Preflight did not finish');
          };
          try {
            await waitFor(() => document.querySelector('#q_photoshop input'));
            document.querySelector('#q_photoshop input').click();
            if (!sendBtn.disabled) throw Error('Submit was not disabled during preflight');
            await waitFor(() => PREFLIGHTS === 0);
            const path = photoshopPath(VALUES.photoshop.value);
            if (photoshopChecks.get(path).result.code !== 'PHOTOSHOP_RESTART_REQUIRED') throw Error('Restart was not reported');
            await submit();
            if (document.querySelector('.done')) throw Error('Form submitted before Photoshop was ready');
            document.querySelector('#q_photoshop button.add').click();
            await waitFor(() => PREFLIGHTS === 0);
            if (!photoshopChecks.get(path).result.ok) throw Error('Retry did not mark Photoshop ready');
            await submit();
            if (!document.querySelector('.done')) throw Error('Ready form could not submit');
            result.textContent = 'PS_CONFIG_PASSED';
          } catch (error) { result.textContent = 'PS_CONFIG_FAILED: ' + error.stack; }
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
            with patch.object(ask, 'inspect_photoshop', return_value=self.installs[0]), \
                    patch.object(ask, 'prepare_script_preferences', side_effect=[
                        {'ok': False, 'code': 'PHOTOSHOP_RESTART_REQUIRED', 'error': 'Restart Photoshop'},
                        {'ok': True, 'changed': False}]) as configure:
                run = subprocess.run([uikit.find_browser(), '--headless=new', '--disable-gpu', '--no-first-run',
                                      '--no-default-browser-check', '--disable-extensions',
                                      '--user-data-dir=' + str(self.kit / 'browser'), '--dump-dom',
                                      '--virtual-time-budget=12000', f'http://127.0.0.1:{server.server_port}/'],
                                     capture_output=True, timeout=45,
                                     creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                output = run.stdout.decode('utf-8', errors='replace')
                self.assertTrue('<pre>PS_CONFIG_PASSED</pre>' in output, output[-1800:])
                self.assertEqual(configure.call_count, 2)
                self.assertTrue(all(call.args[0] == self.installs[0] for call in configure.call_args_list))
            self.assertEqual(ask.read_json(out)['photoshop'], self.installs[0])
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)


if __name__ == '__main__':
    unittest.main()
