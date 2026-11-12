"""Exercise clipboard uploads in a real browser and check the saved brief."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'game-ui-kit' / 'scripts'))
import ask
from uikit import find_browser


DRIVER = r"""
<script>
(async () => {
  const check = (ok, message) => { if (!ok) throw new Error(message); };
  const waitFor = async fn => {
    for (let i = 0; i < 300; i++) {
      if (fn()) return;
      await new Promise(resolve => setTimeout(resolve, 20));
    }
    throw new Error('Timed out waiting for form');
  };
  const result = document.createElement('pre');
  document.body.append(result);
  window.close = () => {};
  try {
    await waitFor(() => document.querySelector('#q_function textarea'));
    const canvas = document.createElement('canvas');
    canvas.width = 900; canvas.height = 600;
    canvas.getContext('2d').fillRect(0, 0, 900, 600);
    const png = Uint8Array.from(atob(canvas.toDataURL('image/png').split(',')[1]), c => c.charCodeAt(0));
    const paste = target => {
      const data = new DataTransfer();
      data.items.add(new File([png], 'screenshot.png', {type: 'image/png'}));
      const event = new ClipboardEvent('paste', {clipboardData: data, bubbles: true, cancelable: true});
      target.dispatchEvent(event);
      check(event.defaultPrevented, 'Image paste was not handled');
      check(sendBtn.disabled, 'Submit must wait for the image upload');
    };
    const general = document.querySelector('#q_function textarea');
    check(problem(SPEC.questions.find(q => q.id === 'function')), 'Empty required description was accepted');
    const text = new DataTransfer();
    text.setData('text/plain', 'Keep normal text paste');
    const textEvent = new ClipboardEvent('paste', {clipboardData: text, bubbles: true, cancelable: true});
    general.dispatchEvent(textEvent);
    check(!textEvent.defaultPrevented, 'Normal text paste was intercepted');
    const originalFetch = window.fetch;
    const originalAlert = window.alert;
    let uploadError = '';
    window.alert = message => { uploadError = message; };
    window.fetch = (...args) => String(args[0]).startsWith('/upload') ? Promise.reject(new Error('Upload failed')) : originalFetch(...args);
    paste(general);
    await waitFor(() => UPLOADS === 0);
    check(uploadError.includes('Upload failed') && VALUES.function.files.length === 0, 'Failed upload created a ghost image');
    check(!sendBtn.disabled, 'Failed upload left submit disabled');
    window.fetch = originalFetch;
    window.alert = originalAlert;
    paste(general);
    await waitFor(() => UPLOADS === 0);
    check(VALUES.function.files.length === 1, 'General image was lost or uploaded twice');
    check(!problem(SPEC.questions.find(q => q.id === 'function')), 'Image-only description was rejected');
    check(document.querySelectorAll('#q_function .file img').length === 1, 'General preview missing');

    const fields = SPEC.questions.find(q => q.id === 'areas').fields_by[CTX.orientation];
    for (const field of fields) {
      const block = [...document.querySelectorAll('#q_areas .fields > div')].find(node => node.firstChild.textContent === field.label);
      const input = block.querySelector('textarea');
      input.value = 'Describe ' + field.id;
      input.dispatchEvent(new Event('input'));
      paste(input);
      await waitFor(() => UPLOADS === 0);
      check(VALUES.areas.field_files[field.id].length === 1, 'Region image missing or duplicated: ' + field.id);
      check(block.querySelectorAll('.file img').length === 1, 'Region preview missing');
    }
    const top = document.querySelector('#q_areas .fields > div');
    top.querySelector('.file .x').click();
    check(VALUES.areas.field_files.top.length === 0, 'Remove did not clear region image');
    const picked = new DataTransfer();
    picked.items.add(new File([png], 'picked.png', {type: 'image/png'}));
    const picker = top.querySelector('input[type=file]');
    picker.files = picked.files;
    picker.dispatchEvent(new Event('change'));
    await waitFor(() => UPLOADS === 0);
    check(VALUES.areas.field_files.top.length === 1, 'File picker upload failed');
    top.querySelector('.file .x').click();
    paste(top.querySelector('.drop'));
    await waitFor(() => UPLOADS === 0);
    rerender();
    check(document.querySelectorAll('#q_areas .file img').length === fields.length, 'Rerender lost images');
    check(document.querySelector('#q_areas textarea').value === 'Describe top', 'Rerender lost text');
    const note = document.querySelector('#q_areas .file input');
    note.value = 'Reference note';
    note.dispatchEvent(new Event('input'));
    const snapshot = JSON.stringify(VALUES);
    const thumb = document.querySelector('#q_areas .image-thumb');
    thumb.focus();
    const scrollBefore = window.scrollY;
    const overflowBefore = document.body.style.overflow;
    for (const method of ['button', 'background', 'escape']) {
      thumb.click();
      const viewer = document.querySelector('dialog.image-viewer');
      check(viewer?.open && viewer.matches(':modal'), 'Image did not open as a modal overlay');
      check(document.body.style.overflow === 'hidden', 'Background scrolling was not locked');
      const image = viewer.querySelector('img');
      await waitFor(() => image.complete && image.naturalWidth === 900);
      check(image.src === thumb.querySelector('img').src, 'Viewer did not use the original image');
      const bounds = image.getBoundingClientRect();
      check(bounds.width > thumb.offsetWidth && bounds.width <= window.innerWidth && bounds.height <= window.innerHeight,
        'Large image was clipped or remained thumbnail size');
      if (method === 'button') viewer.querySelector('.viewer-close').click();
      else if (method === 'background') viewer.querySelector('.viewer-stage').click();
      else viewer.requestClose(); // Native cancel/close path used by Escape.
      await waitFor(() => !document.querySelector('dialog.image-viewer'));
      check(JSON.stringify(VALUES) === snapshot, 'Viewing an image changed form data');
      check(document.body.style.overflow === overflowBefore, 'Closing did not restore scrolling');
      check(document.activeElement === thumb, 'Closing did not restore thumbnail focus');
      check(window.scrollY === scrollBefore, 'Closing changed the form scroll position');
    }
    await submit();
    check(document.querySelector('.done'), 'Form did not submit');
    result.textContent = 'ATTACHMENT_TEST_PASSED';
  } catch (error) {
    result.textContent = 'ATTACHMENT_TEST_FAILED: ' + error.stack;
  }
})();
</script>
"""


class ClipboardAttachmentTests(unittest.TestCase):
    @unittest.skipUnless(find_browser(), 'Requires Edge or Chrome')
    def test_paste_preview_remove_submit_and_rerender(self):
        for orientation in ('portrait', 'landscape'):
            with self.subTest(orientation=orientation), tempfile.TemporaryDirectory() as folder:
                kit = Path(folder)
                (kit / 'briefs').mkdir()
                (kit / 'briefs/setup.json').write_text(json.dumps({'orientation': orientation}), encoding='utf-8')
                form = ask.load_form('wireframe', kit)
                prefill = {'screen': {'value': {'choice': 'home', 'label': 'Home'}},
                           'prototype': {'value': {'choice': 'no'}}, 'options': {'value': 1}}
                html = (ask.FORMS / 'form.html').read_text(encoding='utf-8').replace('</body>', DRIVER + '</body>')

                class TestHandler(ask.Handler):
                    def do_GET(self):
                        if self.path == '/':
                            self.send(200, html.encode('utf-8'), 'text/html; charset=utf-8')
                        else:
                            super().do_GET()

                out = kit / 'briefs/wireframe/home.json'
                server = ask.FormServer(kit, form, out, prefill)
                server.RequestHandlerClass = TestHandler
                worker = threading.Thread(target=server.serve_forever, daemon=True)
                worker.start()
                try:
                    with patch.object(ask, 'remember_kit'):
                        run = subprocess.run([find_browser(), '--headless=new', '--disable-gpu', '--no-first-run',
                                              '--no-default-browser-check', '--disable-extensions',
                                              '--user-data-dir=' + str(kit / 'browser'), '--dump-dom',
                                              '--virtual-time-budget=15000', f'http://127.0.0.1:{server.server_port}/'],
                                             capture_output=True, timeout=45,
                                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                    output = run.stdout.decode('utf-8', errors='replace')
                    self.assertTrue('<pre>ATTACHMENT_TEST_PASSED</pre>' in output, output[-1800:])
                    saved = ask.read_json(out)['answers']
                    self.assertEqual(saved['function']['value'], '')
                    self.assertEqual(len(saved['function']['files']), 1)
                    fields = form['questions'][2]['fields_by'][orientation]
                    self.assertEqual(set(saved['areas']['field_files']), {f['id'] for f in fields})
                    refs = set()
                    ask.referenced_files(saved, refs)
                    self.assertEqual(len(refs), len(fields) + 1)
                    self.assertTrue(all((kit / path).is_file() for path in refs))
                    self.assertEqual(ask.clean_inputs(kit), 0)
                finally:
                    server.shutdown()
                    server.server_close()
                    worker.join(timeout=5)


if __name__ == '__main__':
    unittest.main()
