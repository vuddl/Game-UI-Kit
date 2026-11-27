"""Project routing, approval durability, exact sprite reuse and pending choice/form state."""
import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'game-ui-kit/scripts'))
import ask
import state
import workflow


class ProjectWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.kit = self.root / 'external-kit'
        self.project = self.root / 'prototype'
        self.project.mkdir()
        self.config = dict(input_mode='prototype', project_path=str(self.project),
            figma_url='https://www.figma.com/design/TEST/Game',
            approved_demo_folder=str(self.root / 'approved'), exported_demo_folder=str(self.root / 'final'))
        self.save('briefs/setup.json', {'size': [1920, 1080], 'orientation': 'landscape', 'project_workflow': self.config})
        self.a = self.root / 'a.png'
        self.b = self.root / 'b.png'
        Image.new('RGBA', (40, 30), (31, 71, 121, 255)).save(self.a)
        Image.new('RGBA', (40, 30), (52, 92, 142, 255)).save(self.b)

    def save(self, relative, value):
        workflow.write(self.kit / relative, value)

    def approve(self, image=None, screen='lobby'):
        return workflow.approve(self.kit, screen, image or self.a, screen.title(), 'Startup', 'Synthetic test approval')

    def test_one_file_two_folders_and_optional_layout_round_trip(self):
        answers = {'input_mode': {'value': {'choice': 'prototype'}},
                   'orientation': {'value': {'choice': 'landscape'}}}
        for key in ('project_path', 'figma_url', 'approved_demo_folder', 'exported_demo_folder'):
            answers[key] = {'value': self.config[key]}
        result = ask.apply_answers('setup', self.kit, answers)
        self.assertEqual(result['project_workflow']['layout_workflow'], 'during_mockup')
        answers['exported_demo_folder']['value'] = self.config['approved_demo_folder']
        with self.assertRaises(ValueError):
            ask.apply_answers('setup', self.kit, answers)
        del answers['figma_url']
        with self.assertRaises(ValueError):
            ask.apply_answers('setup', self.kit, answers)

    def test_external_kit_is_resolved_in_new_chat(self):
        with patch.dict(os.environ, {'CODEX_HOME': str(self.root / 'codex')}):
            workflow.remember_project(self.kit)
            result = workflow.resolve_project(self.project)
        self.assertEqual(result['kit'], str(self.kit.resolve()))
        self.assertEqual(list(self.project.iterdir()), [])

    def test_real_screen_inventory_replaces_generic_suggestions(self):
        self.save('briefs/project_screens.json', {'screens': [
            {'screen': 'core_choice', 'label': 'Choose a Core', 'group': 'Defense'},
            {'screen': 'run_over', 'label': 'Run Over', 'group': 'Defense'}]})
        self.approve(screen='core_choice')
        options = ask.options_for('kit:screens+catalog:screens', self.kit)
        self.assertEqual([s['value'] for s in options], ['core_choice', 'run_over'])
        self.assertEqual(options[0]['status'], 'đã chốt')
        self.assertEqual(options[1]['status'], 'chưa làm')
        self.assertEqual(options[0]['group'], 'Defense')

    def test_prototype_can_select_actual_screen_without_wireframe(self):
        self.save('briefs/project_screens.json', {'screens': [{'screen': 'core', 'label': 'Core'}]})
        result = ask.apply_answers('mockup', self.kit, {'wireframe': {'value': []},
            'prototype_screens': {'value': [{'choice': 'core', 'label': 'Core'}]}, 'options': {'value': 2}})
        self.assertEqual([s['screen'] for s in result['screens']], ['core'])
        self.assertEqual(result['screens'][0]['reference_role'], 'function')
        with self.assertRaises(ValueError):
            ask.apply_answers('mockup', self.kit, {'wireframe': {'value': []}})

    def test_prefilled_capture_retains_reference_when_label_differs_from_screen_id(self):
        target = self.kit / 'captures/defense_core/default.png'
        workflow.exact_copy(self.a, target)
        self.save('briefs/project_screens.json', {'screens': [{'screen': 'defense_core', 'label': 'Choose a Core',
            'cases': [{'path': 'captures/defense_core/default.png', 'status': 'captured'}]}]})
        sources = ask.defaults_for('kit:wireframes', self.kit)
        result = ask.apply_answers('mockup', self.kit, {'wireframe': {'value': sources},
            'prototype_screens': {'value': [{'choice': 'defense_core', 'label': 'Choose a Core'}]}})
        self.assertEqual(result['screens'][0]['function_references'][0]['file'], 'captures/defense_core/default.png')

    def test_approval_copies_exact_bytes_and_replaces_only_owned_file(self):
        first = self.approve()
        target = Path(first['folder_path'])
        self.assertEqual(target.read_bytes(), self.a.read_bytes())
        self.assertEqual(first['remote_status'], 'pending')
        second = self.approve(self.b)
        self.assertEqual(target.read_bytes(), self.b.read_bytes())
        self.assertEqual(len(list(target.parent.glob('*.png'))), 1)
        self.assertEqual(len(list((self.kit / 'style/approvals/lobby').glob('*.png'))), 2)
        target.write_bytes(self.a.read_bytes())  # A real edit made outside the managed archive.
        result = self.approve(self.b)
        self.assertEqual(result['folder_status'], 'error')
        self.assertEqual(target.read_bytes(), self.a.read_bytes())
        self.assertEqual(workflow.read(self.kit / 'briefs/mockup/demos.json')['screens'][0]['approved_sha256'], second['sha256'])

    def test_copy_failure_retains_approval_and_can_retry(self):
        self.approve()
        original_copy = workflow.exact_copy
        def unavailable(source, target):
            if Path(target).parent == self.root / 'approved':
                raise OSError('Simulated unavailable archive')
            return original_copy(source, target)
        with patch.object(workflow, 'exact_copy', side_effect=unavailable):
            failed = self.approve(self.b)
        self.assertEqual(failed['folder_status'], 'error')
        self.assertTrue((self.kit / 'style/concepts/lobby__approved.png').is_file())
        self.assertEqual(self.approve(self.b)['folder_status'], 'verified')

    def test_stale_hash_or_other_figma_file_cannot_be_marked_synced(self):
        item = self.approve()
        with self.assertRaises(ValueError):
            workflow.mark_synced(self.kit, 'approved', 'lobby', item['sha256'], '1:2', 'https://www.figma.com/design/OTHER/Game')
        workflow.mark_synced(self.kit, 'approved', 'lobby', item['sha256'], '1:2', self.config['figma_url'])
        self.assertEqual(workflow.sync_plan(self.kit)['items'], [])
        self.approve(self.b)
        with self.assertRaises(ValueError):
            workflow.mark_synced(self.kit, 'approved', 'lobby', item['sha256'], '1:2', self.config['figma_url'])
        self.assertEqual(workflow.sync_plan(self.kit)['items'][0]['node_id'], '1:2')

    def test_export_folder_queue_updates_changed_keeps_missing_and_separates_approval(self):
        self.approve()
        demo = self.kit / 'export/delivery/UI/Lobby/demo/lobby__v1.png'
        workflow.exact_copy(self.a, demo)
        result = workflow.archive_exported(self.kit, [demo.relative_to(self.kit).as_posix()])
        self.assertEqual(result['status'], 'copied')
        target = self.root / 'final/Lobby/demo/lobby__v1.png'
        self.assertEqual(target.read_bytes(), self.a.read_bytes())
        plan = workflow.sync_plan(self.kit, 'exported')
        self.assertEqual(plan['items'][0]['key'], 'lobby/demo/lobby__v1.png')
        item = plan['items'][0]
        workflow.mark_synced(self.kit, 'exported', item['key'], item['sha256'], '2:3', self.config['figma_url'])
        self.assertEqual(workflow.sync_plan(self.kit, 'exported')['items'], [])
        target.write_bytes(self.b.read_bytes())
        self.assertEqual(workflow.sync_plan(self.kit, 'exported')['items'][0]['node_id'], '2:3')
        target.unlink()
        self.assertEqual(len(workflow.queue(self.kit)['exported']), 1)
        self.assertEqual(len(workflow.queue(self.kit)['approved']), 1)

    def test_component_pixels_stay_identical_across_composites(self):
        self.approve()
        master = workflow.component(self.kit, 'avatar', 'style/concepts/lobby__approved.png', [2, 3, 15, 20])
        source_hash = workflow.digest(self.kit / master['master'])
        layout = self.kit / 'mockups/demo.json'
        workflow.write(layout, {'size': [100, 80], 'components': [{'id': 'avatar', 'x': 20, 'y': 10}]})
        for index in range(5):
            output = f'style/concepts/demo_{index}.png'
            workflow.compose(self.kit, layout, output)
            with Image.open(self.kit / output) as image, Image.open(self.kit / master['master']) as original:
                self.assertEqual(image.crop((20, 10, 33, 27)).tobytes(), original.convert('RGBA').tobytes())
        self.assertEqual(workflow.digest(self.kit / master['master']), source_hash)
        with self.assertRaises(ValueError):
            workflow.component(self.kit, 'avatar', 'style/concepts/lobby__approved.png', [2, 3, 15, 20])
        workflow.write(layout, {'size': [100, 80], 'components': [{'id': 'avatar', 'x': 0, 'y': 0, 'width': 26, 'height': 34}]})
        with self.assertRaises(ValueError):
            workflow.compose(self.kit, layout, 'style/concepts/invalid.png')

    def test_earliest_approved_source_survives_later_approvals(self):
        self.approve()
        earliest = workflow.read(self.kit / 'style/reusable_components.json')['approved_sources']['lobby']['image']
        self.approve(self.b)
        component = workflow.component(self.kit, 'original_avatar', earliest, [0, 0, 10, 10])
        with Image.open(self.kit / component['master']) as image:
            self.assertEqual(image.getpixel((0, 0)), (31, 71, 121, 255))

    def test_layout_only_inventory_is_real_and_non_record_json_is_ignored(self):
        self.save('mockups/actual_screen__v1.json', {'size': [100, 100]})
        self.save('briefs/mockup/non_record.json', ['Legacy list data'])
        options = ask.options_for('kit:screens+catalog:screens', self.kit)
        self.assertEqual([item['value'] for item in options], ['actual_screen'])

    def test_existing_batch_concept_revision_is_preserved(self):
        folder = self.kit / 'style/concepts'
        folder.mkdir(parents=True)
        for name in ('lobby__concept_1', 'shop__concept_1'):
            Image.new('RGBA', (10, 10), 'red').save(folder / (name + '.png'))
        with patch.dict(ask.PREVIEW, kind='concepts', screens=['lobby__concept_1', 'shop__concept_1']):
            form = ask.load_form('revise', self.kit)
            self.assertEqual(len(form['questions'][0]['options']), 2)
            result = ask.apply_answers('revise', self.kit, {
                'versions': {'value': [{'choice': 'lobby__concept_1'}, {'choice': 'shop__concept_1'}]},
                'common': {'value': 'Synthetic common revision request'}})
        self.assertEqual(len(result['versions']), 2)

    def test_question_waits_and_blocks_done_and_form_spawn(self):
        with contextlib.redirect_stdout(io.StringIO()):
            state.cmd_begin(self.kit, 'mockup')
        workflow.question(self.kit, 'Một hay nhiều màn?', ['Một màn', 'Nhiều màn'])
        with contextlib.redirect_stdout(io.StringIO()), patch.object(ask.subprocess, 'Popen') as spawn:
            self.assertEqual(state.cmd_done(self.kit), 4)
            self.assertEqual(ask.start_detached(argparse.Namespace(), self.kit), 4)
            spawn.assert_not_called()
        with self.assertRaises(ValueError):
            workflow.question(self.kit, answer='Skip', evidence='Skipped')
        self.assertIsNotNone(workflow.pending_question(self.kit))
        workflow.question(self.kit, answer='Một màn', evidence='Synthetic test reply')
        self.assertIsNone(workflow.pending_question(self.kit))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(state.cmd_done(self.kit), 0)
        checkpoint = workflow.read(self.kit / '.gui/handoff.json')
        self.assertEqual(checkpoint['project_workflow']['figma_url'], self.config['figma_url'])

    def test_live_form_is_reused_and_not_killed_for_another_form(self):
        server = ask.FormServer(self.kit, ask.load_form('full', self.kit), self.kit / 'briefs/mockup/full.json', {})
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f'http://127.0.0.1:{server.server_port}/'
            self.save('.gui/ask.json', dict(url=url, pid=os.getpid(), form='full', out='briefs/mockup/full.json', kind='mockups', screens=''))
            args = argparse.Namespace(form='full', out='briefs/mockup/full.json', kind='mockups', screens='')
            with contextlib.redirect_stdout(io.StringIO()), patch.object(ask.os, 'kill') as kill:
                self.assertEqual(ask.start_detached(args, self.kit), 0)
                args.form = 'revise'
                self.assertEqual(ask.start_detached(args, self.kit), 4)
                kill.assert_not_called()
            with urlopen(url + 'spec') as response:
                self.assertEqual(response.status, 200)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(5)

    def test_draft_uploads_survive_cleanup_and_invalid_submission(self):
        server = ask.FormServer(self.kit, ask.load_form('setup', self.kit), self.kit / 'briefs/setup.json', {})
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f'http://127.0.0.1:{server.server_port}'
            file = ask.store_upload(self.kit, 'setup', 'gameplay', 'ref.png', self.a.read_bytes())[0]
            answers = {'input_mode': {'value': {'choice': 'prototype'}}, 'gameplay': {'value': 'Draft kept', 'files': [file]}}
            def post(endpoint):
                request = Request(url + endpoint, data=json.dumps({'answers': answers}).encode(), headers={'Content-Type': 'application/json'})
                return urlopen(request)
            with post('/draft') as response:
                self.assertEqual(response.status, 200)
            with self.assertRaises(HTTPError):
                post('/submit')
            self.assertFalse(server.done.is_set())
            self.assertEqual(ask.clean_inputs(self.kit), 0)
            with urlopen(url + '/spec') as response:
                self.assertEqual(json.load(response)['prefill']['gameplay']['value'], 'Draft kept')
            answers['input_mode']['value']['choice'] = 'idea'
            with patch.object(ask, 'remember_kit'), post('/submit') as response:
                self.assertEqual(response.status, 200)
            self.assertTrue(server.done.is_set())
            self.assertFalse(ask.draft_path(self.kit, server.out).exists())
        finally:
            server.shutdown()
            server.server_close()
            thread.join(5)


if __name__ == '__main__':
    unittest.main()
