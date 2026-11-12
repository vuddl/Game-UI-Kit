"""Regression cases for solid alpha, real translucency, clean effects and delivery proofs."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image,ImageDraw

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'game-ui-kit/scripts'))
import native_ui
import sprite_quality as quality
import uikit


class SpriteQualityTests(unittest.TestCase):
    def test_solid_core_252_is_detected_and_fixed_without_changing_rgb(self):
        image=Image.new('RGBA',(40,40));ImageDraw.Draw(image).rectangle((5,5,34,34),fill=(18,44,73,252))
        self.assertTrue(quality.audit(image,'opaque')['issues'])
        fixed=quality.repair_alpha(image,'opaque')
        self.assertFalse(quality.audit(fixed,'opaque')['issues'])
        self.assertEqual(fixed.getpixel((20,20)),(18,44,73,255))
        self.assertEqual(fixed.getpixel((0,0)),(0,0,0,0))

    def test_real_translucency_is_not_made_opaque(self):
        image=Image.new('RGBA',(30,30),(42,159,185,84))
        self.assertEqual(quality.repair_alpha(image,'translucent').tobytes(),image.tobytes())
        self.assertEqual(quality.repair_alpha(image,'mixed').tobytes(),image.tobytes())

    def test_mixed_cleanup_keeps_clear_pane_and_real_hole_but_discards_outer_matte(self):
        image=Image.new('RGBA',(44,44),(100,220,80,60));d=ImageDraw.Draw(image)
        d.rectangle((6,6,37,37),fill=(210,175,65,253));d.rectangle((12,12,31,31),fill=(180,220,230,70));d.rectangle((19,19,24,24),fill=(0,0,0,0))
        fixed,mask=quality.repair_mixed(image)
        self.assertEqual(fixed.getpixel((1,1))[3],0)
        self.assertEqual(fixed.getpixel((16,16))[3],70)
        self.assertEqual(fixed.getpixel((21,21))[3],0)
        self.assertFalse(quality.audit(fixed,'mixed',mask)['issues'])

    def test_explicit_solid_region_inside_mixed_asset_is_checked(self):
        image=Image.new('RGBA',(30,30),(42,159,185,84));mask=Image.new('L',image.size)
        ImageDraw.Draw(mask).rectangle((2,2,10,27),fill=255)
        self.assertTrue(quality.audit(image,'mixed',mask)['issues'])
        fixed=quality.repair_alpha(image,'mixed',mask)
        self.assertFalse(quality.audit(fixed,'mixed',mask)['issues'])
        self.assertEqual(fixed.getpixel((22,15))[3],84)

    def test_shadow_is_one_rgb_hue_with_smooth_alpha_not_background_rgb(self):
        mask=Image.new('L',(80,80));ImageDraw.Draw(mask).rectangle((25,25,54,54),fill=255)
        shadow=np.array(quality.effect_layer(mask,'#392616',.35,4,(0,7)))
        visible=shadow[:,:,3]>0
        np.testing.assert_array_equal(np.unique(shadow[:,:,:3][visible],axis=0),[[57,38,22]])
        self.assertEqual(shadow[0,0,3],0)
        self.assertGreater(len(np.unique(shadow[:,:,3])),20)
        self.assertGreater(shadow[61,40,3],shadow[18,40,3])

    def test_preserve_policy_repairs_interior_without_changing_good_edge_coverage(self):
        coverage=Image.new('L',(240,160))
        ImageDraw.Draw(coverage).rounded_rectangle((32,32,207,127),radius=36,fill=255)
        coverage=coverage.resize((60,40),Image.Resampling.LANCZOS)
        source=np.empty((40,60,4),dtype=np.uint8);source[:,:,:3]=[42,159,85]
        source[:,:,3]=np.rint(np.array(coverage)*.988).astype(np.uint8)
        source[18:22,28:32,3]=236
        fixed,mask=quality.repair_body(Image.fromarray(source),'opaque',coverage)
        result=np.array(fixed);core=quality.erode(np.array(coverage)>=128)
        np.testing.assert_array_equal(result[:,:,3][~core],source[:,:,3][~core])
        np.testing.assert_array_equal(result[:,:,:3][source[:,:,3]>0],source[:,:,:3][source[:,:,3]>0])
        self.assertTrue(np.all(result[:,:,3][core]==255))
        self.assertFalse(quality.audit(fixed,'opaque',mask)['issues'])

    def test_preserve_mixed_material_requires_mask_and_keeps_glass_coverage(self):
        image=Image.new('RGBA',(40,40),(190,225,235,65));mask=Image.new('L',image.size)
        ImageDraw.Draw(mask).rectangle((2,2,10,37),fill=255)
        with self.assertRaisesRegex(ValueError,'explicit solid-region'):
            quality.repair_body(image,'mixed')
        body,_=quality.repair_body(image,'mixed',mask)
        self.assertEqual(body.getpixel((6,20))[3],255)
        self.assertEqual(body.getpixel((20,20))[3],65)
        with self.assertRaisesRegex(ValueError,'edge_policy'):
            quality.repair_body(image,'mixed',mask,'automatic')

    def test_effect_opacity_and_blur_are_independently_controlled(self):
        mask=Image.new('L',(160,80));ImageDraw.Draw(mask).rectangle((40,20,119,59),fill=255)
        weak=quality.effect_alpha(mask,.18,4)
        strong=quality.effect_alpha(mask,.72,4)
        np.testing.assert_allclose(strong,weak*4,atol=1e-14)
        self.assertAlmostEqual(strong[40,80],.72,places=12)
        self.assertTrue(np.all(np.diff(strong[60:,80])<=0))
        broad=quality.effect_alpha(mask,.72,10)
        self.assertGreater(broad[70,80],strong[70,80])
        # Preserve useful low-opacity precision until the PNG conversion.
        very_weak=quality.effect_alpha(mask,.001,4)
        self.assertGreater(very_weak[40,80],0)
        self.assertLess(very_weak[40,80],1/255)

    def test_fractional_effect_offset_keeps_subpixel_coverage_without_wrapping(self):
        mask=Image.new('L',(32,32));ImageDraw.Draw(mask).rectangle((5,8,8,23),fill=255)
        field=quality.effect_alpha(mask,1,0,(.5,0))
        self.assertAlmostEqual(field[16,5],.5)
        self.assertAlmostEqual(field[16,6],1)
        self.assertEqual(field[16,0],0)
        self.assertEqual(field[16,31],0)

    def test_unmix_recomposites_consistently_on_two_backdrops(self):
        foreground=np.array([.12,.28,.36],dtype=np.float32);a=np.array(.32,dtype=np.float32)
        for bg in [np.array([1.,1.,1.]),np.array([.04,.08,.12])]:
            composite=foreground*a+bg*(1-a)
            np.testing.assert_allclose(quality.unmix(composite,bg,a),foreground,atol=1e-6)

    def test_opaque_isolation_discards_colored_matte_preserves_cutout_hole(self):
        image=Image.new('RGBA',(40,40),(40,255,30,110));d=ImageDraw.Draw(image)
        d.rectangle((7,7,32,32),fill=(15,40,80,253));d.rectangle((16,16,23,23),fill=(0,0,0,0))
        body,mask=quality.isolate_opaque(image)
        self.assertEqual(body.getpixel((1,1))[3],0)
        self.assertEqual(body.getpixel((20,20))[3],0)
        self.assertEqual(body.getpixel((10,10)),(15,40,80,255))
        self.assertFalse(quality.audit(body,'opaque',mask)['issues'])

    def test_native_large_surface_has_opaque_core_and_separate_effect_hue(self):
        spec={'kind':'pill','size':[480,160],'colored':True,'palette':['#fff674','#ffe83b','#ffd21a','#dca000']}
        image,body,mask,shadow,glow=native_ui.render(spec)
        self.assertFalse(quality.audit(image,'opaque',mask)['issues'])
        self.assertEqual(body.getpixel((240,80))[3],255)
        a=np.array(shadow);colors=np.unique(a[:,:,:3][a[:,:,3]>0],axis=0)
        self.assertEqual(len(colors),1)

    def test_minimum_key_feather_accepts_zero_and_keeps_antialiasing(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'key.png';im=Image.new('RGB',(40,40),'#00ff00');d=ImageDraw.Draw(im)
            d.rectangle((10,10,29,29),fill='#122844');d.line((9,11,9,28),fill=(9,148,34));im.save(p)
            rgba,key=uikit.extract_alpha(p,24,0)
            self.assertEqual(rgba[20,20,3],255)
            self.assertEqual(rgba[0,0,3],0)
            self.assertGreater(rgba[20,9,3],0)
            self.assertLess(rgba[20,9,3],255)

    def test_delivery_rejects_a_stale_visual_alpha_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            k=Path(tmp);(k/'elements').mkdir();(k/'style').mkdir();(k/'export').mkdir()
            im=Image.new('RGBA',(16,16),(10,40,70,255));im.save(k/'elements/body.png')
            (k/'manifest.json').write_text(json.dumps({'elements':{'ui/body':{'file':'elements/body.png'}}}))
            (k/'style/sprite_quality.json').write_text(json.dumps({'elements':{'ui/body':{'alpha_mode':'opaque'}}}))
            proof=quality.audit(im,'opaque');proof['visual_reviewed']=True
            (k/'export/sprite_quality_report.json').write_text(json.dumps({'elements':{'ui/body':proof}}))
            quality.validate_delivery(k,['ui/body'])
            (k/'style/sprite_quality.json').write_text(json.dumps({'elements':{'ui/body':{'alpha_mode':'translucent'}}}))
            with self.assertRaisesRegex(ValueError,'stale'):quality.validate_delivery(k,['ui/body'])
            (k/'style/sprite_quality.json').write_text(json.dumps({'elements':{'ui/body':{'alpha_mode':'opaque'}}}))
            im.putpixel((8,8),(11,40,70,255));im.save(k/'elements/body.png')
            with self.assertRaisesRegex(ValueError,'stale'):quality.validate_delivery(k,['ui/body'])

    def test_thin_keyed_image_does_not_sample_across_or_outside_canvas(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'thin.png';im=Image.new('RGB',(2,8),'#00ff00')
            im.putpixel((1,3),(18,40,68));im.save(p)
            rgba,_=uikit.extract_alpha(p,24,0)
            self.assertEqual(rgba[3,1,3],255)
            self.assertEqual(rgba[0,0,3],0)


if __name__=='__main__':unittest.main()
