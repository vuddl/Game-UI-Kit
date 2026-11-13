"""Demo approvals and a separate sprite request remain visible across resumes."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'game-ui-kit/scripts'))
import state
import ask


class MockupDemoProgressTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.kit = Path(self.temp.name)

    def save(self, relative, value):
        path = self.kit / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding='utf-8')

    def summary(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            state.cmd_summary(self.kit)
        return json.loads(output.getvalue())['mockup']

    def test_legacy_demo_approval_does_not_imply_sprite_request(self):
        self.save('briefs/mockup/home.json', {'screens': [{'screen': 'home', 'label': 'Home'}],
                                             'approved_concept': 'style/concepts/home_approved.png'})
        result = self.summary()
        self.assertEqual(result['screens'][0]['approved_concept'], 'style/concepts/home_approved.png')
        self.assertEqual(result['sprite_production'], {'requested': False})

    def test_register_reports_each_demo_without_a_phantom_screen_brief(self):
        demos = [{'screen': 'home', 'label': 'Home', 'drafts': ['style/concepts/home_v1.png'],
                  'approved_demo': 'style/concepts/home_v1.png'},
                 {'screen': 'shop', 'label': 'Shop', 'drafts': ['style/concepts/shop_v1.png'],
                  'approved_demo': None}]
        self.save('briefs/mockup/demos.json', {'style_anchor': 'style/concepts/home_v1.png', 'screens': demos,
                                              'sprite_production': {'requested': False}})
        result = self.summary()
        self.assertEqual(result['screens'], [])
        self.assertEqual(result['demos'], demos)
        self.assertEqual(result['style_anchor'], 'style/concepts/home_v1.png')
        self.assertFalse(result['sprite_production']['requested'])

    def test_sprite_request_preserves_exact_screen_and_demo_scope(self):
        request = {'requested': True, 'screens': ['home'],
                   'approved_demos': {'home': 'style/concepts/home_v1.png'}}
        self.save('briefs/mockup/demos.json', {'screens': [{'screen': 'home'}, {'screen': 'shop'}],
                                              'sprite_production': request})
        self.assertEqual(self.summary()['sprite_production'], request)

    def test_one_demo_count_works_with_or_without_an_existing_kit(self):
        for kit_choice in ('yes', 'no'):
            answers = {'kit': {'value': {'choice': kit_choice}}, 'options': {'value': 4}}
            result = ask.apply_answers('mockup', self.kit, answers)
            self.assertEqual(result['options'], 4)
            self.assertNotIn('concept_count', result)
            # Stale data from an older open form does not override the single count.
            answers['concept_count'] = {'value': {'choice': '2'}}
            self.assertEqual(ask.apply_answers('mockup', self.kit, answers)['options'], 4)

    def test_demo_count_rejects_invalid_values(self):
        for count in (0, 6, 2.5, True, None):
            with self.subTest(count=count), self.assertRaises(ValueError):
                ask.apply_answers('mockup', self.kit, {'options': {'value': count}})

    def test_wireframe_link_rejects_invalid_urls_on_submit(self):
        for url in ('', 'www.figma.com/design/example', 'javascript:alert(1)', 'https:///example.org',
                    'https://user:password@example.org', 'https://example.org:99999'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                ask.apply_answers('mockup', self.kit, {'wireframe': {'value': [{'url': url}]}})

    def test_summary_counts_wireframe_uploads_and_links(self):
        answers = {'wireframe': {'value': [
            {'path': 'preview/wireframes/home.png', 'screen': 'Home'},
            {'url': 'https://www.figma.com/design/example?node-id=12%3A3', 'screen': 'Shop'},
        ]}}
        self.save('briefs/mockup/home.json', ask.apply_answers('mockup', self.kit, answers))
        screen = self.summary()['screens'][0]
        self.assertEqual(screen['wireframe_files'], 1)
        self.assertEqual(screen['wireframe_links'], 1)


if __name__ == '__main__':
    unittest.main()
