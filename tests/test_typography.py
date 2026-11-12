"""Observable typography placement: ink bounds, content regions and explicit effects."""
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'game-ui-kit/scripts'))
import uikit


class TypographyTests(unittest.TestCase):
    def render(self,text,box=(40,30,360,130),**options):
        warnings=[]
        image=uikit.text_layer((420,220),{'text':text,'text_size':64,**options},box,None,warnings.append)
        return image,warnings

    def test_visible_glyphs_center_for_caps_descenders_and_accents(self):
        for text in ['OPEN','gyp','Épée','jazz']:
            with self.subTest(text=text):
                image,warnings=self.render(text)
                left,top,right,bottom=image.getchannel('A').getbbox()
                self.assertAlmostEqual((left+right)/2,200,delta=1)
                self.assertAlmostEqual((top+bottom)/2,80,delta=1)
                self.assertFalse(warnings)

    def test_empty_advance_does_not_displace_visible_label(self):
        a,_=self.render('Play');b,_=self.render('   Play   ')
        self.assertEqual(a.getchannel('A').getbbox(),b.getchannel('A').getbbox())

    def test_tall_text_fits_content_height_as_well_as_width(self):
        image,warnings=self.render('gyp',box=(30,80,390,110),text_size=120)
        left,top,right,bottom=image.getchannel('A').getbbox()
        self.assertLessEqual(bottom-top,28)
        self.assertGreaterEqual(top,80)
        self.assertLessEqual(bottom,110)
        self.assertFalse(warnings)

    def test_label_uses_lower_main_band_not_parent_canvas_center(self):
        image,_=self.render('Delivery',box=(40,120,360,180))
        left,top,right,bottom=image.getchannel('A').getbbox()
        self.assertAlmostEqual((top+bottom)/2,150,delta=1)
        self.assertGreater(top,110)

    def test_plain_label_has_no_implicit_outline_or_shadow(self):
        image,_=self.render('Shop',text_color='#ae3456')
        rgba=np.asarray(image);visible=rgba[:,:,3]>0
        self.assertTrue(np.all(rgba[:,:,:3][visible]==[174,52,86]))

    def test_outline_only_appears_when_requested(self):
        plain,_=self.render('Shop')
        outlined,_=self.render('Shop',text_stroke=3)
        a=plain.getchannel('A').getbbox();b=outlined.getchannel('A').getbbox()
        self.assertGreater(b[2]-b[0],a[2]-a[0])
        self.assertGreater(b[3]-b[1],a[3]-a[1])


if __name__=='__main__':unittest.main()
