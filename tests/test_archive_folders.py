"""Real ZIP/RAR unpacking and browser folder ingestion with preserved screen paths."""
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'game-ui-kit/scripts'))
import ask
from uikit import find_browser
import test_form_attachments as browser_tests


FOLDER_DRIVER = r'''
<script>
(async () => {
  const result = document.createElement('pre'); document.body.append(result);
  const check = (ok, message) => { if (!ok) throw new Error(message); };
  const wait = async fn => { for(let n=0;n<300;n++){ if(fn()) return; await new Promise(r=>setTimeout(r,20)); } throw Error('timeout'); };
  window.close = () => {};
  try {
    await wait(() => document.querySelector('#q_function textarea'));
    const box = document.querySelector('#q_function .description-box');
    const picker = box.querySelector('input[webkitdirectory]');
    check(picker, 'Folder picker absent');
    const canvas = document.createElement('canvas'); canvas.width=8; canvas.height=8;
    const png = Uint8Array.from(atob(canvas.toDataURL('image/png').split(',')[1]),c=>c.charCodeAt(0));
    const a=new File([png],'same.png',{type:'image/png'}), b=new File([png],'same.png',{type:'image/png'});
    Object.defineProperty(a,'webkitRelativePath',{value:'Demo/Lobby/same.png'});
    Object.defineProperty(b,'webkitRelativePath',{value:'Demo/Shop/same.png'});
    const ignored = new File(['ignore'],'notes.exe');
    Object.defineProperty(ignored,'webkitRelativePath',{value:'Demo/notes.exe'});
    const transfer = new DataTransfer(); [a,b,ignored].forEach(f=>transfer.items.add(f));
    picker.files=transfer.files; picker.dispatchEvent(new Event('change'));
    await wait(()=>UPLOADS===0);
    check(VALUES.function.files.length===2,'Same filenames from different subfolders collided');
    check(VALUES.function.files[0].path!==VALUES.function.files[1].path,'Folder structure lost');
    check(box.textContent.includes('notes.exe'),'Skipped file was not reported');
    // Emulate a directory drop with two readEntries chunks, a browser behavior seen with large folders.
    const entry = file => ({isFile:true,name:file.name,file:resolve=>resolve(file)});
    const folder = {isDirectory:true,name:'Dropped',createReader(){let n=0; return {readEntries(resolve){resolve(n++===0?[entry(new File([png],'one.png'))]:n===2?[entry(new File([png],'two.png'))]:[])}}}};
    const drop=new Event('drop',{bubbles:true,cancelable:true});
    Object.defineProperty(drop,'dataTransfer',{value:{types:['Files'],files:[],items:[{webkitGetAsEntry:()=>folder}]}});
    box.dispatchEvent(drop); await wait(()=>UPLOADS===0);
    check(VALUES.function.files.length===4,'Directory drop did not read every chunk');
    await submit(); check(document.querySelector('.done'),'Submission failed');
    result.textContent='ATTACHMENT_TEST_PASSED';
  }catch(error){ result.textContent='ATTACHMENT_TEST_FAILED: '+error.stack; }
})();
</script>
'''


class ArchiveFolderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.kit = self.root / 'kit'

    def png(self):
        data = io.BytesIO()
        Image.new('RGBA', (10, 10), 'red').save(data, format='PNG')
        return data.getvalue()

    def test_nested_upload_paths_keep_same_names_separate(self):
        first = ask.store_upload(self.kit, 'mockup', 'sources', 'Demo/Lobby/same.png', self.png())[0]
        second = ask.store_upload(self.kit, 'mockup', 'sources', 'Demo/Shop/same.png', self.png())[0]
        self.assertNotEqual(first['path'], second['path'])
        self.assertEqual(first['name'], 'Demo/Lobby/same.png')

    def test_zip_path_escape_and_name_collisions(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as archive:
            archive.writestr('../escape.png', self.png())
        with self.assertRaises(ValueError):
            ask.store_upload(self.kit, 'export', 'screens', 'bad.zip', data.getvalue())
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as archive:
            archive.writestr('Home A/a-b.png', self.png())
            archive.writestr('Home-A/a b.png', self.png())
            archive.writestr('notes.txt', 'not artwork')
        files = ask.store_upload(self.kit, 'export', 'screens', 'good.zip', data.getvalue())
        self.assertEqual(len(files), 2)
        self.assertNotEqual(files[0]['path'], files[1]['path'])
        self.assertEqual(files[0]['archive_skipped'], ['notes.txt'])

    @unittest.skipUnless(Path('C:/Program Files/WinRAR/Rar.exe').is_file(), 'Real RAR fixture generation needs WinRAR CLI')
    def test_actual_rar_archive_unpacks_without_modifying_png(self):
        source = self.root / 'Screens/Lobby'
        source.mkdir(parents=True)
        (source / 'ui.png').write_bytes(self.png())
        archive = self.root / 'screens.rar'
        subprocess.run(['C:/Program Files/WinRAR/Rar.exe','a','-idq','-ma5',str(archive),'Screens'],
                       cwd=self.root, check=True, capture_output=True)
        files = ask.store_upload(self.kit, 'mockup', 'wireframe', 'screens.rar', archive.read_bytes())
        self.assertEqual(len(files), 1)
        self.assertIn('Lobby', files[0]['name'])
        self.assertEqual((self.kit / files[0]['path']).read_bytes(), self.png())

    @unittest.skipUnless(find_browser(), 'Browser required')
    def test_folder_picker_and_drop_keep_nested_groups_in_existing_form(self):
        self.kit.mkdir()
        (self.kit / 'briefs').mkdir()
        (self.kit / 'briefs/setup.json').write_text(json.dumps({'size':[1920,1080],'orientation':'landscape'}))
        form = ask.load_form('wireframe', self.kit)
        prefill = {'screen':{'value':{'choice':'home','label':'Home'}}, 'options':{'value':1},
                   'prototype':{'value':{'choice':'no'}}}
        tester = browser_tests.ClipboardAttachmentTests('runTest')
        saved = tester.submit_in_browser(self.kit, form, prefill, self.kit/'briefs/wireframe/home.json', FOLDER_DRIVER)
        self.assertEqual(len(saved['answers']['function']['files']), 4)


if __name__ == '__main__':
    unittest.main()
