"""Render smooth parametric UI surfaces at delivery resolution, with separate effects.

This rebuilds simple native UI geometry. It is not an image upscaler or a substitute
for detailed icons/illustrations. Specs live in the kit, not in this renderer.
"""
from __future__ import annotations

import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageColor, ImageChops
from sprite_quality import color_layer, effect_layer, erode
from psd_recipe import blur as float_blur


def _curve(start, c1, c2, end, steps=60):
    return [tuple((1-t)**3*start[j]+3*(1-t)**2*t*c1[j]+3*(1-t)*t*t*c2[j]+t**3*end[j]
                  for j in (0,1)) for t in np.linspace(0,1,steps)]


def silhouette(kind, size, box, radius=.2):
    w,h=size;x0,y0,x1,y1=box;bw,bh=x1-x0,y1-y0
    im=Image.new('L',size);d=ImageDraw.Draw(im)
    if kind in ('pill','roundrect','ellipse'):
        if kind=='ellipse':d.ellipse(box,fill=255)
        else:d.rounded_rectangle(box,radius=(bh/2 if kind=='pill' else min(bw,bh)*radius),fill=255)
        return im
    if kind=='chevron':
        pts=[(x0+.12*bw,y0+.84*bh),(x0+.5*bw,y0+.18*bh),(x0+.88*bw,y0+.84*bh)]
        line=max(1,round(bh*.22));d.line(pts,fill=255,width=line,joint='curve')
        for x,y in pts:d.ellipse((x-line/2,y-line/2,x+line/2,y+line/2),fill=255)
        return im
    # Smooth cubic contours, never tracing pixel-level wiggles from the screenshot.
    if kind in ('title','cart'):
        shoulder=.25 if kind=='title' else .30
        pts=[(.09,shoulder),(.34,shoulder)]
        pts+=_curve((.34,shoulder),(.40,shoulder),(.39,.025),(.50,.025))
        pts+=_curve((.50,.025),(.61,.025),(.60,shoulder),(.66,shoulder))
        pts +=[(.91,shoulder)]
        pts+=_curve((.91,shoulder),(.99,shoulder),(1,.55),(.96,.78))
        pts+=_curve((.96,.78),(.95,.97),(.91,.98),(.85,.98))
        pts +=[(.15,.98)]
        pts+=_curve((.15,.98),(.09,.98),(.05,.97),(.04,.78))
        pts+=_curve((.04,.78),(0,.55),(.01,shoulder),(.09,shoulder))
    elif kind=='sign':
        pts=[(.12,.22)]
        pts+=_curve((.12,.22),(.12,.08),(.32,.08),(.36,.12))
        pts+=_curve((.36,.12),(.40,-.025),(.60,-.025),(.64,.12))
        pts+=_curve((.64,.12),(.68,.08),(.88,.08),(.88,.22))
        pts+=_curve((.88,.22),(1,.28),(1,.72),(.88,.78))
        pts+=_curve((.88,.78),(.88,.92),(.68,.92),(.64,.88))
        pts+=_curve((.64,.88),(.60,1.025),(.40,1.025),(.36,.88))
        pts+=_curve((.36,.88),(.32,.92),(.12,.92),(.12,.78))
        pts+=_curve((.12,.78),(0,.72),(0,.28),(.12,.22))
    else:raise ValueError(f'Unsupported native contour: {kind}')
    d.polygon([(x0+x*bw,y0+y*bh) for x,y in pts],fill=255)
    return im


def gradient(size, stops):
    w,h=size;t=np.linspace(0,1,h,dtype=np.float32)
    positions=[p for p,c in stops];colors=[ImageColor.getrgb(c) for p,c in stops]
    row=np.stack([np.interp(t,positions,[c[j] for c in colors]) for j in range(3)],axis=-1)
    rgba=np.empty((h,w,4),dtype=np.uint8);rgba[:,:,:3]=np.rint(row[:,None,:]);rgba[:,:,3]=255
    return Image.fromarray(rgba)


def paint(body, mask, stops):
    layer=gradient(body.size,stops);layer.putalpha(mask);body.alpha_composite(layer)


def render(spec: dict, supersample=2):
    """Return assembled PNG, opaque body, body mask, shadow, glow at final size."""
    width,height=spec['size'];size=(width*supersample,height*supersample);w,h=size
    native=spec.get('kind','roundrect');kind=native if native not in ('toggle','slider','dial') else 'roundrect'
    pad=spec.get('padding',.045)*min(w,h);box=(pad,pad,w-pad,h-pad*1.7)
    radius=spec.get('radius',.18)
    if native in ('toggle','slider'):kind='pill'
    if native=='dial':kind='ellipse'
    if native=='chevron':kind='chevron'
    mask=silhouette(kind,size,box,radius);body=Image.new('RGBA',size)
    palette=spec.get('palette',['#fffdf0','#fff7e6','#faecd5','#f5dfbe'])
    colored=spec.get('colored',False)
    rings=[(0,[(0,'#fff7cc'),(.13,'#fffef2'),(.6,'#f3d0a3'),(1,'#cc9564')]),
           (.012,[(0,'#ffffff'),(.45,'#fff9de'),(1,'#efd0aa')]),
           (.033,[(0,'#efd0a0'),(.3,'#fff7db'),(1,'#bc8249')]),
           (.052 if colored else .035,list(zip([0,.22,.65,1],palette)))]
    if native=='chevron':rings=[(0,list(zip([0,.22,.65,1],palette)))]
    if spec.get('rim_palette'):
        rp=spec['rim_palette'];rings[:3]=[(i, list(zip([0,.22,.65,1],rp))) for i,_ in rings[:3]]
    for inset,stops in rings:
        delta=inset*min(w,h);b=(box[0]+delta,box[1]+delta,box[2]-delta,box[3]-delta)
        face=silhouette(kind,size,b,radius)
        paint(body,face,stops)
    # Smooth bevel normals from a continuous height field. The fill remains fully opaque;
    # highlight/shade are independent color layers clipped to its silhouette.
    bevel=spec.get('bevel',.045 if colored else .018)*min(w,h)
    field=float_blur(np.asarray(face,dtype=np.float32)/255,bevel*.55)
    gy,gx=np.gradient(field);light=np.clip((gx*.45+gy*.9)*bevel*3,-1,1)
    clip=np.asarray(face,dtype=np.float32)/255
    body.alpha_composite(color_layer(Image.fromarray(np.rint(np.maximum(light,0)*clip*255*spec.get('bevel_highlight',.5)).astype(np.uint8)),'#ffffff'))
    body.alpha_composite(color_layer(Image.fromarray(np.rint(np.maximum(-light,0)*clip*110).astype(np.uint8)),spec.get('bevel_shadow',palette[-1])))
    if colored and native not in ('chevron','dial'):
        # Soft reflections affect RGB only: the structural surface beneath stays opaque.
        gloss=Image.new('L',size);d=ImageDraw.Draw(gloss)
        d.ellipse((w*.09,h*.075,w*.86,h*.40),fill=25)
        a=np.asarray(gloss,dtype=np.float32)*np.asarray(mask,dtype=np.float32)/255
        gloss=Image.fromarray(a.astype(np.uint8)).filter(ImageFilter.GaussianBlur(.018*h))
        body.alpha_composite(color_layer(ImageChops.multiply(gloss,mask),'#ffffff'))
        small=Image.new('L',size);ImageDraw.Draw(small).ellipse((w*.105,h*.115,w*.255,h*.20),fill=190)
        # Smooth white highlight follows the top-left bevel.
        a=np.asarray(small,dtype=np.float32)*np.asarray(mask,dtype=np.float32)/255
        gloss=Image.fromarray(a.astype(np.uint8)).filter(ImageFilter.GaussianBlur(.002*h))
        body.alpha_composite(color_layer(ImageChops.multiply(gloss,mask),'#ffffff'))
    if native in ('toggle','slider'):
        if native=='slider':
            fill=silhouette('pill',size,(box[0]+.025*h,box[1]+.04*h,w*.62,box[3]-.04*h))
            paint(body,fill,[(0,'#d1ff66'),(.4,'#99e214'),(1,'#4a9c00')])
        cx=w*(.75 if native=='toggle' else .56);cy=h*.47;rr=h*.37
        knob=silhouette('ellipse',size,(cx-rr,cy-rr,cx+rr,cy+rr))
        body.alpha_composite(effect_layer(knob,'#493b2d',.24,h*.018,(h*.01,h*.025)))
        paint(body,knob,[(0,'#ffffff'),(.4,'#fffef8'),(1,'#d9d6ce')])
    elif native=='dial':
        cx=w*.5;cy=h*.47
        rr=min(w,h)*.34;knob=silhouette('ellipse',size,(cx-rr,cy-rr,cx+rr,cy+rr))
        # Brushed-metal radial lighting, kept inside one opaque knob silhouette.
        yy,xx=np.mgrid[:h,:w];angles=np.arctan2(yy-cy,xx-cx)
        light=.5+.5*np.cos(angles*2-.6);base=np.array([235,165,37]);high=np.array([255,237,157])
        rgb=base+(high-base)*light[...,None];layer=np.empty((h,w,4),dtype=np.uint8);layer[:,:,:3]=rgb;layer[:,:,3]=np.asarray(knob)
        body.alpha_composite(Image.fromarray(layer))
        pointer=Image.new('L',size);ImageDraw.Draw(pointer).rounded_rectangle((cx-.02*w,cy-.30*h,cx+.02*w,cy-.08*h),radius=.02*w,fill=255)
        body.alpha_composite(color_layer(pointer,'#65421c'))
    if native=='sign' and spec.get('chef_hat'):
        # Separate native chef emblem, complete opaque white face and gold edge.
        hat=Image.new('L',size);d=ImageDraw.Draw(hat)
        for cx,cy,rx,ry in [(.44,.13,.07,.09),(.50,.095,.08,.095),(.56,.13,.07,.09)]:d.ellipse(((cx-rx)*w,(cy-ry)*h,(cx+rx)*w,(cy+ry)*h),fill=255)
        d.rounded_rectangle((.43*w,.12*h,.57*w,.25*h),radius=.012*h,fill=255)
        body.alpha_composite(color_layer(hat.filter(ImageFilter.MaxFilter(2*supersample+1)),'#cf8b38'))
        paint(body,hat,[(0,'#fffef7'),(.2,'#fff9de'),(1,'#efd0a4')])
        mask=ImageChops.lighter(mask,hat.filter(ImageFilter.MaxFilter(2*supersample+1)))
    fx=spec.get('shadow',{'color':'#634328','opacity':.23,'blur':.018,'dy':.026})
    shadow=effect_layer(mask,fx['color'],fx['opacity'],fx['blur']*h,(fx.get('dx',0)*w,fx.get('dy',0)*h))
    glow=Image.new('RGBA',size)
    if spec.get('glow'):
        g=spec['glow'];glow=effect_layer(mask,g['color'],g['opacity'],g['blur']*h)
    assembled=Image.alpha_composite(Image.alpha_composite(shadow,glow),body)
    outputs=[]
    for im in (assembled,body,mask,shadow,glow):
        im=im.resize((width,height),Image.Resampling.LANCZOS)
        if im.mode=='RGBA':
            a=np.array(im);a[:,:,3][a[:,:,3]>=254]=255;a[a[:,:,3]==0]=0;im=Image.fromarray(a)
        outputs.append(im)
    core=erode(np.asarray(outputs[2])>=128)
    a=np.array(outputs[1]);a[:,:,3][core]=255;outputs[1]=Image.fromarray(a)
    # Resizing associated RGBA and converting back can quantize hue at alpha 1/255.
    # Effects have one straight RGB color: resample only A, then reapply that color.
    outputs[3]=color_layer(outputs[3].getchannel('A'),fx['color'])
    outputs[4]=color_layer(outputs[4].getchannel('A'),spec.get('glow',{}).get('color','#ffffff'))
    outputs[0]=Image.alpha_composite(Image.alpha_composite(outputs[3],outputs[4]),outputs[1])
    return tuple(outputs)


def main():
    import argparse,json
    from pathlib import Path
    from types import SimpleNamespace
    import uikit
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kit',type=Path);parser.add_argument('--spec',required=True,type=Path)
    parser.add_argument('--force',action='store_true',help='Replace approved component versions')
    args=parser.parse_args();kit=args.kit
    data=json.loads(args.spec.read_text(encoding='utf-8'));out=kit/'style/native_ui/renders';out.mkdir(parents=True,exist_ok=True)
    config_path=kit/'style/sprite_quality.json'
    config=json.loads(config_path.read_text(encoding='utf-8')) if config_path.exists() else {'elements':{}}
    mapping=[]
    for name,spec in data['elements'].items():
        if not uikit.NAME_RE.fullmatch(name):raise ValueError(f'Invalid element name: {name}')
        image,body,mask,shadow,glow=render(spec,supersample=data.get('supersample',2))
        paths={suffix:out/f'{name}__{suffix}.png' for suffix in ['sprite','body','mask','shadow','glow']}
        for suffix,im in zip(paths,[image,body,mask,shadow,glow]):
            paths[suffix].parent.mkdir(parents=True,exist_ok=True);im.save(paths[suffix])
        mapping.append(f"{paths['sprite'].relative_to(out).as_posix()} = {name}")
        config['elements'][name]={'alpha_mode':'opaque','body_mask':paths['mask'].relative_to(kit).as_posix(),
                                  'source':'native_ui','effect_layers':{s:paths[s].relative_to(kit).as_posix() for s in ['shadow','glow']}}
        print('Rendered',name,image.size,flush=True)
    mapping_path=out/'import.txt';mapping_path.write_text('\n'.join(mapping)+'\n',encoding='utf-8')
    uikit.cmd_import(SimpleNamespace(kit=str(kit),source=str(out),map=str(mapping_path),prefix=None,force=args.force))
    config_path.write_text(json.dumps(config,indent=2),encoding='utf-8')
    manifest=uikit.load_manifest(kit)
    for name,spec in data['elements'].items():
        manifest['elements'][name]['quality_source']='native_ui'
        manifest['elements'][name]['native_ui_spec']=str(args.spec.resolve().relative_to(kit.resolve())).replace('\\','/')
        # Working layer suffixes must not rename the delivered public component.
        manifest['elements'][name]['imported_from']=name+'.png'
    uikit.save_manifest(kit,manifest)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
