"""Geometry, rendering and export checks using synthetic art; no AI calls or Unity edits."""
import contextlib
import io
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'game-ui-kit' / 'scripts'))
import background
import uikit


class GeometryTests(unittest.TestCase):
    def test_default_targets_follow_the_base_orientation(self):
        self.assertIn([1080, 2400], background.default_targets([900, 1600]))
        self.assertIn([2400, 1080], background.default_targets([1600, 900]))
        self.assertTrue(all(w >= h for w, h in background.default_targets([1600, 900])))

    def test_cover_preserves_scale_and_fills_the_viewport(self):
        for source, target in [([400, 300], [1080, 2400]), ([300, 400], [2400, 1080])]:
            geometry = background.cover_geometry(source, target, [.2, .8])
            x, y, right, bottom = geometry['box']
            self.assertLessEqual(x, 0)
            self.assertLessEqual(y, 0)
            self.assertGreaterEqual(right + 1e-8, target[0])
            self.assertGreaterEqual(bottom + 1e-8, target[1])
            self.assertAlmostEqual((right - x) / source[0], (bottom - y) / source[1])

    def test_rendered_round_marker_stays_round(self):
        image = Image.new('RGB', (100, 100), 'black')
        ImageDraw.Draw(image).ellipse((40, 40, 60, 60), fill='white')
        result = background.render_cover(image, [200, 100]).convert('L').point(lambda value: 255 if value > 128 else 0)
        left, top, right, bottom = result.getbbox()
        self.assertLessEqual(abs((right - left) - (bottom - top)), 1)
        self.assertEqual(result.size, (200, 100))

    def test_expansion_protects_original_frame_across_intermediate_ratios(self):
        rng = random.Random(12)
        for _ in range(60):
            original = [rng.randint(100, 1500), rng.randint(100, 1500)]
            targets = [[900, 2000], [1200, 1600], [2100, 900]]
            plan = background.expansion_plan(original, targets)
            for target in targets + [[rng.randint(450, 2333), 1000] for _ in range(6)]:
                crop = background.cover_geometry(plan['canvasSize'], target)['crop']
                self.assertAlmostEqual(background.visible_fraction(plan['originalFrame'], crop), 1)
            self.assertTrue(all(n % 4 == 0 for n in plan['canvasSize']))

    def test_invalid_alignment_is_rejected(self):
        with self.assertRaises(ValueError):
            background.cover_geometry([100, 200], [100, 100], [float('nan'), .5])


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.kit = Path(self.temp.name)
        for folder in ('elements/backgrounds', 'briefs/backgrounds', 'mockups'):
            (self.kit / folder).mkdir(parents=True)
        self.image_path = self.kit / 'elements/backgrounds/bg_home.png'
        image = Image.new('RGB', (160, 240), '#26364a')
        ImageDraw.Draw(image).ellipse((60, 60, 100, 140), fill='#66ccaa')
        image.save(self.image_path)
        self.profile_path = 'briefs/backgrounds/home.json'
        self.profile = {'image': 'elements/backgrounds/bg_home.png', 'targets': [[90, 160], [120, 160], [72, 160]],
                        'alignment': [.5, .5], 'protected': [{'name': 'Landmark', 'rect': [60, 60, 40, 80]}]}
        self.write_profile()
        self.layout = {'size': [90, 160], 'background': 'backgrounds/bg_home',
                       'background_profile': self.profile_path,
                       'items': [{'text': 'Play', 'x': 15, 'y': 140, 'w': 60, 'h': 15, 'text_size': 10}]}
        self.write_layout('home__v1')
        (self.kit / 'manifest.json').write_text(json.dumps({'elements': {
            'backgrounds/bg_home': {'file': self.profile['image'], 'width': 160, 'height': 240}}}))

    def write_profile(self):
        (self.kit / self.profile_path).write_text(json.dumps(self.profile), encoding='utf-8')

    def write_layout(self, stem):
        (self.kit / f'mockups/{stem}.json').write_text(json.dumps(self.layout), encoding='utf-8')

    def test_clean_and_overlay_checks_keep_separate_previews(self):
        clean = background.check_profile(self.kit, self.profile_path)
        overlay = background.check_profile(self.kit, self.profile_path, 'home__v1')
        self.assertTrue(overlay['geometry_ok'])
        self.assertNotEqual(clean['preview'], overlay['preview'])
        self.assertTrue((self.kit / clean['preview']).is_file())
        self.assertTrue((self.kit / overlay['preview']).is_file())
        self.assertTrue(overlay['visual_review_required'])
        background.current_report(self.kit, self.profile_path, 'home__v1')

    def test_changed_image_or_profile_invalidates_checks(self):
        background.check_profile(self.kit, self.profile_path)
        self.profile['alignment'] = [.4, .5]
        self.write_profile()
        with self.assertRaises(ValueError):
            background.current_report(self.kit, self.profile_path)
        background.check_profile(self.kit, self.profile_path)
        Image.new('RGB', (160, 240), 'blue').save(self.image_path)
        with self.assertRaises(ValueError):
            background.current_report(self.kit, self.profile_path)

    def test_cropped_important_subject_blocks_export(self):
        self.profile['protected'] = [{'name': 'Edge landmark', 'rect': [0, 0, 35, 240]}]
        self.write_profile()
        report = background.check_profile(self.kit, self.profile_path)
        self.assertFalse(report['geometry_ok'])
        with self.assertRaises(ValueError):
            background.current_report(self.kit, self.profile_path)

    def test_transparent_gaps_are_not_ready(self):
        image = Image.open(self.image_path).convert('RGBA')
        image.putpixel((80, 120), (0, 0, 0, 0))
        image.save(self.image_path)
        report = background.check_profile(self.kit, self.profile_path)
        self.assertFalse(report['geometry_ok'])
        self.assertFalse(report['opaque'])

    def test_each_exported_variant_needs_its_own_current_overlay_check(self):
        self.write_layout('home__v2')
        background.check_profile(self.kit, self.profile_path, 'home__v1')
        with self.assertRaises(ValueError):
            background.current_report(self.kit, self.profile_path, 'home__v2')
        report = background.check_profile(self.kit, self.profile_path, 'home__v2')
        self.assertEqual(set(report['overlays']), {'home__v1', 'home__v2'})
        self.layout['items'][0]['text'] = 'Start'
        self.write_layout('home__v1')
        with self.assertRaises(ValueError):
            background.current_report(self.kit, self.profile_path, 'home__v1')
        background.current_report(self.kit, self.profile_path, 'home__v2')

    def test_png_psd_plan_and_unity_use_the_same_uniform_placement(self):
        background.check_profile(self.kit, self.profile_path, 'home__v1')
        args = SimpleNamespace(kit=str(self.kit), layout=['home__v1'], screen=None, force=True,
                               png_only=True, no_run=True, background='image', art='image', timeout=10)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(uikit.cmd_export(args), 0)
            self.assertEqual(uikit.cmd_psd(args), 0)
            self.assertEqual(uikit.cmd_unity(args), 0)
        with Image.open(self.kit / 'export/png/home__v1.png') as exported:
            self.assertEqual(exported.size, (90, 160))
        mapping = json.loads((self.kit / 'export/unity/home__v1.json').read_text())
        geometry = background.cover_geometry([160, 240], self.layout['size'])
        self.assertEqual(mapping['backgroundRendering']['referencePlacement'], geometry)
        self.assertEqual(mapping['backgroundRendering']['mode'], 'uniformCover')
        jsx = (self.kit / 'export/psd/home__v1.jsx').read_text()
        plan_line = next(line for line in jsx.splitlines() if line.startswith('var PLAN = '))
        plan = json.loads(plan_line[len('var PLAN = '):].rstrip(';'))
        self.assertEqual(plan['ops'][0]['box'], geometry['box'])
        self.assertEqual(plan['ops'][0]['op'], 'smart')

    def test_unchecked_profile_blocks_png_before_output_is_created(self):
        args = SimpleNamespace(kit=str(self.kit), layout=['home__v1'], force=True, png_only=True)
        with self.assertRaises(SystemExit):
            uikit.cmd_export(args)
        self.assertFalse((self.kit / 'export/png').exists())

    def test_profile_cannot_reference_another_background(self):
        background.check_profile(self.kit, self.profile_path, 'home__v1')
        wrong = self.kit / 'elements/backgrounds/other.png'
        Image.new('RGB', (160, 240)).save(wrong)
        with self.assertRaises(SystemExit):
            uikit.background_geometry(self.kit, self.layout, wrong)


if __name__ == '__main__':
    unittest.main()
