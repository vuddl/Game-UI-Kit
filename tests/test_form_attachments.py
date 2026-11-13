"""Exercise uploads in a real browser and check the saved briefs."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
import zipfile
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
    const generalBox = general.closest('.description-box');
    const generalPreview = generalBox.querySelector('.description-attachment img');
    const generalAdd = generalBox.querySelector('.attachment-add');
    check(generalPreview.compareDocumentPosition(general) & Node.DOCUMENT_POSITION_FOLLOWING,
      'Preview belongs above the description');
    check(general.compareDocumentPosition(generalAdd) & Node.DOCUMENT_POSITION_FOLLOWING,
      'The add button belongs below the description');

    const fields = SPEC.questions.find(q => q.id === 'areas').fields_by[CTX.orientation];
    for (const field of fields) {
      const block = [...document.querySelectorAll('#q_areas .fields > div')].find(node => node.firstChild.textContent === field.label);
      const input = block.querySelector('textarea');
      input.value = 'Describe ' + field.id;
      input.dispatchEvent(new Event('input'));
      paste(input);
      await waitFor(() => UPLOADS === 0);
      check(VALUES.areas.field_files[field.id].length === 1, 'Region image missing or duplicated: ' + field.id);
      check(input.closest('.description-box').querySelectorAll('.description-attachment img').length === 1, 'Region preview missing');
    }
    const top = document.querySelector('#q_areas .fields > div');
    top.querySelector('.description-attachment .x').click();
    check(VALUES.areas.field_files.top.length === 0, 'Remove did not clear region image');
    const picked = new DataTransfer();
    picked.items.add(new File([png], 'picked.png', {type: 'image/png'}));
    const picker = top.querySelector('input[type=file]');
    picker.files = picked.files;
    picker.dispatchEvent(new Event('change'));
    await waitFor(() => UPLOADS === 0);
    check(VALUES.areas.field_files.top.length === 1, 'File picker upload failed');
    top.querySelector('.description-attachment .x').click();
    paste(top.querySelector('.drop'));
    await waitFor(() => UPLOADS === 0);
    rerender();
    check(document.querySelectorAll('#q_areas .description-attachment img').length === fields.length, 'Rerender lost images');
    check(document.querySelector('#q_areas textarea').value === 'Describe top', 'Rerender lost text');
    const thumb = document.querySelector('#q_areas .image-thumb');
    thumb.click();
    const note = document.querySelector('.viewer-details .description-box textarea');
    note.value = 'Reference note';
    note.dispatchEvent(new Event('input'));
    document.querySelector('.viewer-close').click();
    const snapshot = JSON.stringify(VALUES);
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

FIELD_DRIVER = r"""
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
  function data(name) {
    const transfer = new DataTransfer();
    if (name.endsWith('.png')) {
      const canvas = document.createElement('canvas');
      canvas.width = name.length;
      canvas.height = 1;
      const png = Uint8Array.from(atob(canvas.toDataURL().split(',')[1]), char => char.charCodeAt(0));
      transfer.items.add(new File([png], name, {type: 'image/png'}));
    } else {
      transfer.items.add(new File(['test ' + name], name));
    }
    return transfer;
  }
  function paste(input, name) {
    const event = new ClipboardEvent('paste', {clipboardData: data(name), bubbles: true, cancelable: true});
    input.dispatchEvent(event);
    check(event.defaultPrevented && sendBtn.disabled, 'Paste did not start uploading: ' + name);
  }
  function pick(input, name) {
    check(!input.hasAttribute('accept'), 'Reference picker restricts file types');
    input.files = data(name).files;
    input.dispatchEvent(new Event('change'));
  }
  function drop(input, name) {
    const event = new DragEvent('drop', {dataTransfer: data(name), bubbles: true, cancelable: true});
    input.dispatchEvent(event);
    check(event.defaultPrevented && sendBtn.disabled, 'Drop did not start uploading: ' + name);
  }
  try {
    await waitFor(() => document.querySelector('#questions'));
    if (SPEC.id === 'setup') {
      const orientation = SPEC.questions.find(q => q.id === 'orientation');
      const custom = document.querySelector('#q_orientation .opt:last-child input[type=radio]');
      custom.click();
      const [width, height] = document.querySelectorAll('#q_orientation input[type=number]');
      paste(width, 'width.pdf');
      await waitFor(() => !UPLOADS);
      check(problem(orientation), 'Reference file replaced a required size');
      for (const [input, value] of [[width, 1080], [height, 1920]]) {
        input.value = value;
        input.dispatchEvent(new Event('input'));
      }
      const game = document.querySelector('#q_game_type .opt:last-child input[type=radio]');
      game.click();
      const name = document.querySelector('#q_game_type input[type=text]');
      name.value = 'Puzzle RPG';
      name.dispatchEvent(new Event('input'));
      paste(name, 'name.pdf');
      await waitFor(() => !UPLOADS);
      const note = document.querySelector('#q_game_type .extra > .description-box textarea');
      drop(note, 'rules.docx');
      await waitFor(() => !UPLOADS);
      const picker = document.querySelector('#q_gameplay input[type=file]');
      pick(picker, 'gameplay.zip');
      await waitFor(() => !UPLOADS);
      check(problem(SPEC.questions.find(q => q.id === 'gameplay')), 'Reference file replaced required gameplay text');
      const gameplay = document.querySelector('#q_gameplay textarea');
      gameplay.value = 'Match tiles and battle monsters';
      gameplay.dispatchEvent(new Event('input'));
      rerender();
      check(document.querySelector('#q_game_type .file .nm')?.textContent === 'name.pdf', 'Name attachment was lost');
      check(document.querySelector('#q_game_type .extra > .description-box .description-attachment button')?.title === 'rules.docx',
        'Custom description attachment was lost');
    } else {
      const wireframe = document.querySelector('#q_wireframe');
      check(wireframe.querySelector('input[type=file][accept]')?.accept.includes('.psd'), 'Artwork picker lost format restriction');
      const count = VALUES.wireframe.value.length;
      if (count) {
        const name = wireframe.querySelector('.file input[type=text]');
        const note = wireframe.querySelector('.file textarea');
        paste(name, 'screen.pdf');
        await waitFor(() => !UPLOADS);
        paste(note, 'layout.txt');
        await waitFor(() => !UPLOADS);
      }
      check(VALUES.wireframe.value.length === count, 'Reference file became a source wireframe');
      const question = SPEC.questions.find(q => q.id === 'wireframe');
      const addLink = wireframe.querySelector('button.add');
      check(problem(question) === !count, 'Missing source requirement is wrong');
      addLink.click();
      const linkInput = wireframe.querySelector('input[type=url]');
      check(document.activeElement === linkInput, 'New link did not receive focus');
      const enter = (input, value) => {
        input.value = value;
        input.dispatchEvent(new Event('input'));
      };
      enter(linkInput, 'javascript:alert(1)');
      check(problem(question), 'An invalid link was accepted');
      enter(linkInput, 'https://www.figma.com/design/example?node-id=12%3A3#frame');
      const linkRow = linkInput.closest('.link-source');
      const description = linkRow.querySelector('textarea');
      const composer = description.closest('.description-box');
      check(linkRow.querySelectorAll('input:not([type=file]),textarea').length === 2, 'Link row has extra fields');
      check(wireframe.querySelector('.drop').compareDocumentPosition(addLink) & Node.DOCUMENT_POSITION_FOLLOWING,
        'Add link is above the upload area');
      check(addLink.compareDocumentPosition(linkRow) & Node.DOCUMENT_POSITION_FOLLOWING,
        'Link row is above the add link button');
      enter(description, 'Use the item grid in the selected frame.');
      const picker = composer.querySelector('input[type=file]');
      check(composer.querySelector('button.attachment-add').textContent === '+', 'Description lacks the compact image control');
      picker.files = data('picked.png').files;
      picker.dispatchEvent(new Event('change'));
      await waitFor(() => !UPLOADS);
      check(composer.querySelectorAll('.description-attachment img').length === 1, 'Picked image is missing from the description');
      composer.querySelector('.description-attachment .x').click();
      check(!composer.querySelector('.description-attachment'), 'Removed image is still visible');
      paste(description, 'reference.png');
      await waitFor(() => !UPLOADS);
      drop(composer, 'extra.png');
      await waitFor(() => !UPLOADS);
      const thumbnails = composer.querySelectorAll('.description-attachment img');
      await waitFor(() => [...thumbnails].every(img => img.naturalWidth > 0));
      check(thumbnails.length === 2, 'Pasted and dropped images are missing from the description');
      check(VALUES.wireframe.value.length === count + 1, 'Description image became a source wireframe');
      addLink.click();
      check(problem(question), 'An empty link was accepted');
      wireframe.querySelector('.link-source:last-child .x').click();
      check(!problem(question), 'A valid link did not satisfy the source requirement');
      rerender();
      check(document.querySelector('#q_wireframe input[type=url]').value === 'https://www.figma.com/design/example?node-id=12%3A3#frame',
        'Link was lost after rerendering');
      check(document.querySelectorAll('#q_wireframe .link-source .description-attachment img').length === 2,
        'Link description images were lost on rerender');
      paste(document.querySelector('#q_background .description-box textarea'), 'background.pdf');
      await waitFor(() => !UPLOADS);
      paste(document.querySelector('#q_options input[type=number]'), 'options.txt');
      await waitFor(() => !UPLOADS);
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
    def submit_in_browser(self, kit, form, prefill, out, driver):
        html = (ask.FORMS / 'form.html').read_text(encoding='utf-8').replace('</body>', driver + '</body>')

        class TestHandler(ask.Handler):
            def do_GET(self):
                if self.path == '/':
                    self.send(200, html.encode('utf-8'), 'text/html; charset=utf-8')
                else:
                    super().do_GET()

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
            self.assertTrue('<pre>ATTACHMENT_TEST_PASSED</pre>' in output, output[-1000:])
            return ask.read_json(out)
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)

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
                out = kit / 'briefs/wireframe/home.json'
                saved = self.submit_in_browser(kit, form, prefill, out, DRIVER)['answers']
                self.assertEqual(saved['function']['value'], '')
                self.assertEqual(len(saved['function']['files']), 1)
                fields = form['questions'][2]['fields_by'][orientation]
                self.assertEqual(set(saved['areas']['field_files']), {f['id'] for f in fields})
                self.assertEqual(saved['areas']['field_files']['top'][0]['note'], 'Reference note')
                refs = set()
                ask.referenced_files(saved, refs)
                self.assertEqual(len(refs), len(fields) + 1)
                self.assertTrue(all((kit / path).is_file() for path in refs))
                self.assertEqual(ask.clean_inputs(kit), 0)

    @unittest.skipUnless(find_browser(), 'Requires Edge or Chrome')
    def test_setup_custom_fields_keep_separate_reference_files(self):
        with tempfile.TemporaryDirectory() as folder:
            kit = Path(folder)
            form = ask.load_form('setup', kit)
            saved = self.submit_in_browser(kit, form, {}, kit / 'briefs/setup.json', FIELD_DRIVER)
            self.assertEqual(saved['size'], [1080, 1920])
            answers = saved['answers']
            self.assertEqual(answers['game_type']['value']['label'], 'Puzzle RPG')
            for files, name in [
                (answers['orientation']['value']['field_files']['width'], 'width.pdf'),
                (answers['game_type']['value']['field_files']['label'], 'name.pdf'),
                (answers['game_type']['value']['files'], 'rules.docx'),
                (answers['gameplay']['files'], 'gameplay.zip'),
            ]:
                self.assertEqual([entry['name'] for entry in files], [name])
                self.assertEqual((kit / files[0]['path']).read_bytes(), f'test {name}'.encode())
            self.assertEqual(ask.clean_inputs(kit), 0)

    @unittest.skipUnless(find_browser(), 'Requires Edge or Chrome')
    def test_mockup_accepts_wireframe_links_with_or_without_uploads(self):
        for with_upload in (False, True):
            with self.subTest(with_upload=with_upload), tempfile.TemporaryDirectory() as folder:
                kit = Path(folder)
                source = ask.store_upload(kit, 'mockup', 'wireframe', 'screen.png', b'example')[0]
                prefill = {'wireframe': {'value': [source] if with_upload else []}, 'kit': {'value': {'choice': 'no'}},
                           'start': {'value': {'choice': 'reference', 'files': [source]}},
                           'background': {'value': {'choice': 'generate'}}}
                form = ask.load_form('mockup', kit)
                saved = self.submit_in_browser(kit, form, prefill, kit / 'briefs/mockup/test.json', FIELD_DRIVER)
                answers = saved['answers']
                self.assertEqual([s['file'] for s in saved['screens'] if 'file' in s], [source['path']] if with_upload else [])
                self.assertEqual(saved['screens'][-1], {
                    'screen': '', 'label': '', 'note': 'Use the item grid in the selected frame.',
                    'url': 'https://www.figma.com/design/example?node-id=12%3A3#frame',
                })
                self.assertEqual(answers['wireframe']['value'][-1]['url'], saved['screens'][-1]['url'])
                refs = answers['wireframe']['value'][-1]['field_files']['note']
                self.assertEqual([ref['name'] for ref in refs], ['reference.png', 'extra.png'])
                if with_upload:
                    fields = answers['wireframe']['value'][0]['field_files']
                    self.assertEqual(fields['screen'][0]['name'], 'screen.pdf')
                    self.assertEqual(fields['note'][0]['name'], 'layout.txt')
                self.assertEqual(answers['background']['field_files']['note'][0]['name'], 'background.pdf')
                self.assertEqual(answers['options']['files'][0]['name'], 'options.txt')
                self.assertEqual(saved['options'], 1)
                self.assertEqual(ask.clean_inputs(kit), 1)
                self.assertTrue(all((kit / ref['path']).is_file() for ref in refs))

    def test_artwork_upload_retains_zip_import_and_type_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            kit = Path(folder)
            archive = io.BytesIO()
            with zipfile.ZipFile(archive, 'w') as output:
                output.writestr('screen.png', b'example')
                output.writestr('notes.txt', b'notes')
            files = ask.store_upload(kit, 'export', 'screens', 'artwork.zip', archive.getvalue())
            self.assertEqual([entry['name'] for entry in files], ['screen.png'])
            with self.assertRaises(ValueError):
                ask.store_upload(kit, 'export', 'screens', 'notes.txt', b'notes')
            mixed = ask.store_upload(kit, 'wireframe', 'function', 'mixed.zip', archive.getvalue(),
                                     reference=True, unpack=True)
            self.assertEqual([entry['name'] for entry in mixed], ['mixed.zip'])
            self.assertEqual((kit / mixed[0]['path']).read_bytes(), archive.getvalue())
            artwork = io.BytesIO()
            with zipfile.ZipFile(artwork, 'w') as output:
                output.writestr('screen.png', b'example')
            files = ask.store_upload(kit, 'wireframe', 'function', 'artwork.zip', artwork.getvalue(),
                                     reference=True, unpack=True)
            self.assertEqual([entry['name'] for entry in files], ['screen.png'])


if __name__ == '__main__':
    unittest.main()
