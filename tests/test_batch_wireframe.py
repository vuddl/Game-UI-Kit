"""Batch wireframes start from setup and save their own rendering choices."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'game-ui-kit/scripts'))
import ask
import state
from uikit import find_browser


DRIVER = r"""
<script>
(async () => {
  const check = (ok, message) => { if (!ok) throw new Error(message); };
  const result = document.createElement('pre');
  document.body.append(result);
  window.close = () => {};
  try {
    while (!document.querySelector('#q_screens')) await new Promise(r => setTimeout(r, 20));
    for (const name of ['Home', 'Shop']) {
      const label = [...document.querySelectorAll('#q_screens .opt > label')].find(e => e.textContent === name);
      check(label, 'Catalog screen missing');
      label.querySelector('input').click();
    }
    if (CTX.command === 'wireframe') {
      check(document.querySelector('#q_prototype') && document.querySelector('#q_options'), 'Batch controls missing');
      check(problem(SPEC.questions.find(q => q.id === 'prototype')), 'Prototype selection must be explicit');
      const count = document.querySelector('#q_options input');
      check(count.value === '1', 'Default count must be one per screen');
      count.value = '4'; count.dispatchEvent(new Event('input'));
      document.querySelector('#q_prototype input').click();
      check(document.querySelector('#q_options input').value === '4', 'Rerender lost count');
    } else {
      check(!document.querySelector('#q_prototype') && !document.querySelector('#q_options'), 'Wireframe controls leaked into mockup');
    }
    await submit();
    check(document.querySelector('.done'), 'Submission failed');
    result.textContent = 'BATCH_TEST_PASSED';
  } catch (error) { result.textContent = 'BATCH_TEST_FAILED: ' + error.stack; }
})();
</script>
"""


class BatchWireframeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.kit = Path(self.temp.name)
        self.save('briefs/setup.json', {'size': [1920, 1080], 'orientation': 'landscape'})

    def save(self, relative, data):
        path = self.kit / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding='utf-8')

    def begin(self, command):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(state.cmd_begin(self.kit, command), 0)

    def answers(self, count=3, prototype='yes'):
        return {'screens': {'value': [{'choice': 'home', 'label': 'Home', 'note': 'Main modes'},
                                      {'choice': 'shop', 'label': 'Shop', 'note': 'IAP'}]},
                'options': {'value': count}, 'prototype': {'value': {'choice': prototype}}}

    def test_fresh_batch_requires_no_first_wireframe(self):
        self.begin('wireframe')
        self.assertFalse((self.kit / 'mockups').exists())
        self.assertEqual(ask.build_context(self.kit)['command'], 'wireframe')
        form = ask.load_form('full', self.kit)
        self.assertTrue(any(o['value'] == 'home' for o in form['questions'][0]['options']))
        for choice in ('yes', 'no'):
            result = ask.apply_answers('full', self.kit, self.answers(prototype=choice))
            self.assertEqual(result['options'], 3)
            self.assertEqual(result['prototype'], choice == 'yes')
            self.assertEqual([s['screen'] for s in result['screens']], ['home', 'shop'])

    def test_invalid_or_missing_batch_choices_are_rejected(self):
        self.begin('wireframe')
        for count in (0, 6, 1.5, True, None):
            with self.subTest(count=count), self.assertRaises(ValueError):
                ask.apply_answers('full', self.kit, self.answers(count=count))
        for prototype in ('', None, 'maybe'):
            with self.subTest(prototype=prototype), self.assertRaises(ValueError):
                ask.apply_answers('full', self.kit, self.answers(prototype=prototype))
        for missing in ('options', 'prototype'):
            answers = self.answers()
            del answers[missing]
            with self.subTest(missing=missing), self.assertRaises(ValueError):
                ask.apply_answers('full', self.kit, answers)

    def test_mockup_keeps_inherited_settings_and_summary_reports_batch_choices(self):
        self.begin('wireframe')
        result = ask.apply_answers('full', self.kit, self.answers())
        self.save('briefs/wireframe/full.json', result)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            state.cmd_summary(self.kit)
        summary = json.loads(output.getvalue())['wireframe']
        self.assertEqual(summary['full_options'], 3)
        self.assertTrue(summary['full_prototype'])
        self.begin('mockup')
        mockup = ask.apply_answers('full', self.kit, {'screens': self.answers()['screens']})
        self.assertNotIn('options', mockup)
        self.assertNotIn('prototype', mockup)

    @unittest.skipUnless(find_browser(), 'Requires Edge or Chrome')
    def test_browser_displays_and_saves_controls_only_for_wireframe(self):
        for command in ('wireframe', 'mockup'):
            with self.subTest(command=command):
                self.begin(command)
                form = ask.load_form('full', self.kit)
                html = (ask.FORMS / 'form.html').read_text(encoding='utf-8').replace('</body>', DRIVER + '</body>')

                class TestHandler(ask.Handler):
                    def do_GET(self):
                        if self.path == '/':
                            self.send(200, html.encode('utf-8'), 'text/html; charset=utf-8')
                        else:
                            super().do_GET()

                out = self.kit / f'briefs/{command}/full.json'
                server = ask.FormServer(self.kit, form, out, {})
                server.RequestHandlerClass = TestHandler
                worker = threading.Thread(target=server.serve_forever, daemon=True)
                worker.start()
                try:
                    with patch.object(ask, 'remember_kit'):
                        run = subprocess.run([find_browser(), '--headless=new', '--disable-gpu', '--no-first-run',
                                              '--no-default-browser-check', '--disable-extensions',
                                              '--user-data-dir=' + str(self.kit / ('browser_' + command)),
                                              '--dump-dom', '--virtual-time-budget=10000',
                                              f'http://127.0.0.1:{server.server_port}/'],
                                             capture_output=True, timeout=45,
                                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                    output = run.stdout.decode('utf-8', errors='replace')
                    self.assertTrue('<pre>BATCH_TEST_PASSED</pre>' in output, output[-1500:])
                    saved = ask.read_json(out)
                    self.assertEqual(len(saved['screens']), 2)
                    if command == 'wireframe':
                        self.assertEqual(saved['options'], 4)
                        self.assertTrue(saved['prototype'])
                    else:
                        self.assertNotIn('options', saved['answers'])
                        self.assertNotIn('prototype', saved['answers'])
                finally:
                    server.shutdown()
                    server.server_close()
                    worker.join(timeout=5)


if __name__ == '__main__':
    unittest.main()
