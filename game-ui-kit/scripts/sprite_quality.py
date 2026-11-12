"""Material-aware alpha checks and deterministic RGBA cleanup; no invented image detail."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageDraw


def pixel_hash(image: Image.Image) -> str:
    image = image.convert('RGBA')
    return hashlib.sha256(str(image.size).encode() + image.tobytes()).hexdigest()


def erode(mask: np.ndarray, radius: int = 2) -> np.ndarray:
    """Outside the canvas is transparent, including when the object touches its edge."""
    if radius <= 0:
        return mask.copy()
    source = Image.fromarray((mask.astype(np.uint8) * 255))
    padded = Image.new('L', (source.width + 2 * radius, source.height + 2 * radius))
    padded.paste(source, (radius, radius))
    inner = padded.filter(ImageFilter.MinFilter(2 * radius + 1))
    return np.asarray(inner.crop((radius, radius, radius + source.width, radius + source.height))) == 255


def audit(image: Image.Image, mode: str = 'unknown', body_mask: Image.Image | None = None) -> dict:
    if mode not in ('unknown', 'opaque', 'mixed', 'translucent', 'background'):
        raise ValueError(f'Unknown alpha intent: {mode}')
    rgba = np.asarray(image.convert('RGBA'))
    alpha = rgba[..., 3]
    support = np.asarray(body_mask.convert('L')) >= 128 if body_mask is not None else alpha >= 128
    if support.shape != alpha.shape:
        raise ValueError('Body mask and image must have the same dimensions')
    core = erode(support)
    count = int(core.sum())
    weak = int((core & (alpha < 255)).sum())
    problems = []
    if (mode == 'opaque' or (mode == 'mixed' and body_mask is not None)) and weak:
        problems.append(f'ACCIDENTAL_TRANSLUCENCY: {weak}/{count} interior pixels are not opaque')
    if mode == 'background' and np.any(alpha != 255):
        problems.append('BACKGROUND_ALPHA: clean scenery must be opaque')
    # Unknown materials are a classification task, never permission to flatten glass/VFX.
    return {'mode': mode, 'size': list(image.size), 'pixel_sha256': pixel_hash(image),
            'interior_pixels': count, 'nonopaque_interior_pixels': weak,
            'max_alpha': int(alpha.max()), 'issues': problems,
            'classification_required': mode == 'unknown'}


def repair_alpha(image: Image.Image, mode: str, body_mask: Image.Image | None = None,
                 near_opaque: int = 256) -> Image.Image:
    """Repair declared solid regions; preserve AA, holes and intentional optical alpha.

    RGB is straight/unassociated. Do not multiply RGB by the new opacity, which would
    darken a later source-over composite. This cannot reconstruct missing RGB detail.
    """
    if mode not in ('opaque', 'mixed', 'translucent', 'background'):
        raise ValueError('Classify the material before repairing alpha')
    rgba = np.array(image.convert('RGBA'))
    if mode == 'background':
        if np.any(rgba[..., 3] != 255):
            raise ValueError('A scenery hole needs reconstruction, not opacity flattening')
        return image.convert('RGBA')
    if mode == 'opaque':
        support = np.asarray(body_mask.convert('L')) >= 128 if body_mask is not None else rgba[..., 3] >= 128
        core = erode(support)
        rgba[..., 3][core] = 255
        # Global normalization is opt-in; the default preserves measured edge AA.
        rgba[..., 3][rgba[..., 3] >= near_opaque] = 255
    elif mode == 'mixed':
        # Mixed glass/metal needs an explicit opaque-region mask; clear glass is left alone.
        if body_mask is not None:
            solid = erode(np.asarray(body_mask.convert('L')) >= 128)
            rgba[..., 3][solid] = 255
    # Translucent materials are never globally normalized. Rebuild them from a color/alpha
    # model or an optical mask when a composite reference exposes contamination.
    rgba[rgba[..., 3] == 0] = 0
    return Image.fromarray(rgba)


def unmix(composite: np.ndarray, backdrop: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    """F=(C-(1-a)B)/a in the reference's compositing space; zero-alpha is unknowable.

    Inputs use the same numeric color space (0..1). Linearize first when that is the
    renderer's compositing space. One flattened reference alone cannot solve F and a.
    """
    a = np.asarray(alpha, dtype=np.float32)
    if a.ndim == np.asarray(composite).ndim - 1:
        a = a[..., None]
    return np.clip(np.divide(composite - (1 - a) * backdrop, a,
                            out=np.zeros_like(composite, dtype=np.float32), where=a > 1e-6), 0, 1)


def color_layer(mask: Image.Image, color: str, opacity: float = 1) -> Image.Image:
    if not 0 <= opacity <= 1:
        raise ValueError('Opacity must be between 0 and 1')
    layer = Image.new('RGBA', mask.size, color)
    layer.putalpha(mask.point(lambda v: round(v * opacity)))
    return layer


def isolate_opaque(image: Image.Image, cutoff: int = 220) -> tuple[Image.Image, Image.Image]:
    """Rebuild an opaque silhouette without keeping the source's noisy outer effects.

    Use only on a visually classified opaque body. Glass/VFX require a separate optical
    mask. RGB at antialiased boundary pixels comes from adjacent solid foreground,
    never from the old matte/shadow. No added feather is applied to the body.
    """
    rgba=np.array(image.convert('RGBA'));a=rgba[:,:,3]
    support=a>=cutoff
    mask=Image.fromarray(support.astype(np.uint8)*255)
    # A median removes isolated one-pixel islands without spreading a blur over the edge.
    mask=mask.filter(ImageFilter.MedianFilter(3))
    # Coverage at a single-pixel contour: preserve measured AA above the solid/matte cutoff.
    solid=np.asarray(mask)>0
    interior=erode(solid,1)
    boundary=solid & ~interior
    alpha=np.zeros(a.shape,dtype=np.uint8);alpha[solid]=255
    # The thresholded contour is reconstructed by 2x coverage sampling, not a feather blur.
    large=mask.resize((mask.width*2,mask.height*2),Image.Resampling.BICUBIC)
    large=large.point(lambda v:255 if v>=128 else 0)
    coverage=np.asarray(large.resize(mask.size,Image.Resampling.LANCZOS))
    alpha[:]=coverage;alpha[erode(solid,2)]=255;alpha[alpha>=254]=255
    # Replace only the edge's contaminated colors with the nearest trusted foreground.
    known=interior & (a>=245);pending=(alpha>0) & ~known
    rgb=rgba[:,:,:3].copy();filled=~pending
    h,w=a.shape
    offsets=sorted([(dy,dx) for dy in range(-4,5) for dx in range(-4,5) if dy or dx],key=lambda z:z[0]**2+z[1]**2)
    for dy,dx in offsets:
        ys=slice(max(0,dy),min(h,h+dy));xs=slice(max(0,dx),min(w,w+dx))
        sy=slice(max(0,-dy),min(h,h-dy));sx=slice(max(0,-dx),min(w,w-dx))
        use=pending[ys,xs] & ~filled[ys,xs] & known[sy,sx]
        rgb[ys,xs][use]=rgba[sy,sx,:3][use];filled[ys,xs][use]=True
    out=np.dstack((rgb,alpha));out[alpha==0]=0
    return Image.fromarray(out),Image.fromarray(alpha)


def optical_fill(image: Image.Image, region: Image.Image, color: str, opacity: float,
                 reflection: float = .18) -> Image.Image:
    """Replace an identified optical pane with a clean tint plus a white reflection layer."""
    if image.size!=region.size:raise ValueError('Optical region must match the image')
    base=np.array(image.convert('RGBA'));coverage=np.asarray(region,dtype=np.float32)/255
    # This region is a separate physical material; erase the flattened old pane first.
    base[:,:,3]=np.rint(base[:,:,3]*(1-coverage)).astype(np.uint8)
    out=Image.fromarray(base)
    out.alpha_composite(color_layer(region,color,opacity))
    y,x=np.mgrid[:image.height,:image.width]
    stripe=np.maximum(0,1-np.abs((x/image.width+y/image.height*.65)-.68)/.10)
    mask=Image.fromarray(np.rint(255*coverage*stripe*reflection).astype(np.uint8))
    out.alpha_composite(color_layer(mask,'#ffffff'))
    return out


def envelope_mask(support: np.ndarray) -> np.ndarray:
    """Fill enclosed regions for exterior-matte clipping, never overwrite their true alpha."""
    solid=np.pad(support,1);outside=np.zeros(solid.shape,dtype=bool);h,w=solid.shape;stack=[(0,0)]
    while stack:
        y,x=stack.pop()
        if solid[y,x] or outside[y,x]:continue
        left=x;right=x
        while left>0 and not (solid[y,left-1] or outside[y,left-1]):left-=1
        while right+1<w and not (solid[y,right+1] or outside[y,right+1]):right+=1
        outside[y,left:right+1]=True
        for ny in (y-1,y+1):
            if not 0<=ny<h:continue
            xs=np.flatnonzero(~solid[ny,left:right+1] & ~outside[ny,left:right+1])+left
            if len(xs):
                first=np.r_[True,np.diff(xs)>1]
                stack.extend((ny,int(v)) for v in xs[first])
    return (~outside)[1:-1,1:-1]


def repair_mixed(image: Image.Image) -> tuple[Image.Image,Image.Image]:
    """Remove exterior matte; retain enclosed glass/holes and declare high-confidence solids."""
    a=np.array(image.convert('RGBA'));alpha=a[:,:,3]
    envelope=envelope_mask(alpha>=220)
    clip=Image.fromarray(envelope.astype(np.uint8)*255).filter(ImageFilter.MaxFilter(3))
    a[:,:,3][np.asarray(clip)==0]=0
    solid=erode(alpha>=245,1);mask=Image.fromarray(solid.astype(np.uint8)*255)
    out=repair_alpha(Image.fromarray(a),'mixed',mask)
    return out,mask


def repair_body(image: Image.Image, mode: str, body_mask: Image.Image | None = None,
                edge_policy: str = 'preserve') -> tuple[Image.Image, Image.Image]:
    """Keep a good cut by default; contour/matte reconstruction is explicitly opt-in.

    Preserve mode expects a clean body-only source before new effects are added.
    Its fallback opaque mask follows the existing silhouette; use an explicit
    material mask when there are accidental holes or mixed optical regions.
    """
    if edge_policy not in ('preserve', 'rebuild'):
        raise ValueError('edge_policy must be preserve or rebuild')
    if mode not in ('opaque', 'mixed', 'translucent'):
        raise ValueError('Body repair requires opaque, mixed or translucent material intent')
    image = image.convert('RGBA')
    if edge_policy == 'rebuild':
        if mode == 'opaque':
            return isolate_opaque(image)
        if mode == 'mixed':
            return repair_mixed(image)
    if mode == 'translucent':
        return image.convert('RGBA'), Image.new('L', image.size)
    if body_mask is None:
        if mode == 'mixed':
            raise ValueError('Preserving mixed material requires an explicit solid-region body_mask')
        body_mask = image.getchannel('A').point(lambda v: 255 if v >= 128 else 0)
    if body_mask.size != image.size:
        raise ValueError('Body mask and repair source must have the same dimensions')
    return repair_alpha(image, mode, body_mask), body_mask.convert('L')


def main():
    import argparse
    from types import SimpleNamespace
    import uikit
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kit',type=Path);parser.add_argument('--repair',action='store_true')
    args=parser.parse_args();kit=args.kit
    config_path=kit/'style/sprite_quality.json'
    config=json.loads(config_path.read_text(encoding='utf-8')) if config_path.exists() else {'elements':{}}
    manifest=uikit.load_manifest(kit)
    if args.repair:
        out=kit/'style/quality_repair/clean';out.mkdir(parents=True,exist_ok=True);mapping=[]
        for name,rule in config['elements'].items():
            if rule.get('source')=='native_ui' or not rule.get('repair'):continue
            source=kit/rule.get('repair_source',manifest['elements'][name]['file']);image=Image.open(source).convert('RGBA')
            mode=rule['alpha_mode']
            if mode not in ('opaque','mixed','translucent'):continue
            mask_path=rule.get('body_mask')
            input_mask=Image.open(kit/mask_path).convert('L') if mask_path else None
            body,mask=repair_body(image,mode,input_mask,rule.get('edge_policy','preserve'))
            for glass in rule.get('optical_regions',[]):
                region=Image.new('L',body.size);draw=ImageDraw.Draw(region)
                pts=[(round(x*body.width),round(y*body.height)) for x,y in glass['polygon']]
                draw.polygon(pts,fill=255)
                # Hardware can contain neutral highlights too; color alone cannot
                # distinguish white metal reflections from a transparent pane.
                for polygon in glass.get('exclude_polygons', []):
                    draw.polygon([(round(x*body.width),round(y*body.height)) for x,y in polygon],fill=0)
                if glass.get('select_neutral'):
                    pixels=np.array(body);rgb=pixels[:,:,:3].astype(float);hi=rgb.max(axis=2)
                    saturation=(hi-rgb.min(axis=2))/np.maximum(hi,1)
                    optical=(saturation<.35)&(rgb[:,:,2]>=rgb[:,:,0]*.9)&(rgb[:,:,1]>=rgb[:,:,0]*.9)&(pixels[:,:,3]>0)
                    region=Image.fromarray(np.where(optical,np.asarray(region),0).astype(np.uint8))
                body=optical_fill(body,region,glass['color'],glass['opacity'],glass.get('reflection',.18))
                solid=np.array(mask);solid[np.asarray(region)>0]=0;mask=Image.fromarray(solid)
            assembled=body.copy();shadow=Image.new('RGBA',body.size)
            if rule.get('shadow'):
                fx=rule['shadow'];silhouette=body.getchannel('A').point(lambda v:255 if v>=128 else 0)
                shadow=effect_layer(silhouette,fx['color'],fx['opacity'],fx['blur']*image.height,(0,fx.get('dy',0)*image.height))
                assembled=Image.alpha_composite(shadow,body)
            bounds=assembled.getchannel('A').getbbox()
            if bounds is None:raise ValueError(f'{name}: cleanup removed the whole asset')
            x0,y0,x1,y1=bounds;cw=(x1-x0+3)//4*4;ch=(y1-y0+3)//4*4
            images=[]
            for im in (assembled,body,mask,shadow):
                canvas=Image.new(im.mode,(cw,ch));canvas.paste(im.crop(bounds),(0,0));images.append(canvas)
            dest=out/f'{name}.png';dest.parent.mkdir(parents=True,exist_ok=True);images[0].save(dest)
            layer_root=kit/'style/quality_repair/layers'
            for suffix,im in zip(['body','mask','shadow'],images[1:]):
                p=layer_root/f'{name}__{suffix}.png';p.parent.mkdir(parents=True,exist_ok=True);im.save(p)
            rule['body_mask']=(layer_root/f'{name}__mask.png').relative_to(kit).as_posix()
            rule['effect_layers']={'shadow':(layer_root/f'{name}__shadow.png').relative_to(kit).as_posix()}
            rule['repair']=False;rule['source']='material_cleanup'
            mapping.append(f'{name}.png = {name}');print('Repaired',name,images[0].size,flush=True)
        if mapping:
            mp=out/'import.txt';mp.write_text('\n'.join(mapping)+'\n',encoding='utf-8')
            uikit.cmd_import(SimpleNamespace(kit=str(kit),source=str(out),map=str(mp),prefix=None,force=True))
        config_path.write_text(json.dumps(config,indent=2),encoding='utf-8')
    result=check_kit(kit);(kit/'export').mkdir(exist_ok=True)
    (kit/'export/sprite_quality_numeric.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'checked':len(result['elements']),'issues':result['issues']}))
    return 2 if result['issues'] else 0


def effect_alpha(mask: Image.Image, opacity: float, blur: float,
                 offset: tuple[float, float] = (0, 0)) -> np.ndarray:
    """Normalized Gaussian alpha, before export quantization. Sizes are in pixels.

    Strength, blur and offset are supplied by the caller from its reference. This
    helper deliberately has no generic 'subtle shadow' preset or peak rescaling.
    """
    if not np.isfinite(opacity) or not 0 <= opacity <= 1:
        raise ValueError('Opacity must be between 0 and 1')
    if not np.isfinite(blur) or blur < 0:
        raise ValueError('Blur must be finite and nonnegative')
    if len(offset) != 2 or not np.all(np.isfinite(offset)):
        raise ValueError('Offset must contain two finite pixel distances')
    field = np.asarray(mask.convert('L'), dtype=np.float32) / 255
    # F-mode translation retains fractional coverage; outside pixels are zero,
    # never samples wrapped from the opposite canvas edge.
    moved = Image.fromarray(field).transform(mask.size, Image.Transform.AFFINE,
                (1, 0, -offset[0], 0, 1, -offset[1]), Image.Resampling.BILINEAR, fillcolor=0)
    field = np.asarray(moved, dtype=np.float64)
    if blur > 0:
        radius = int(np.ceil(4 * blur))
        x = np.arange(-radius, radius + 1, dtype=np.float64)
        kernel = np.exp(-.5 * (x / blur) ** 2)
        kernel /= kernel.sum()
        for axis in (0, 1):
            padding = [(0, 0), (0, 0)]
            padding[axis] = (radius, radius)
            field = np.apply_along_axis(lambda row: np.convolve(row, kernel, mode='valid'),
                                       axis, np.pad(field, padding))
    return np.clip(field * opacity, 0, 1)


def effect_layer(mask: Image.Image, color: str, opacity: float, blur: float,
                 offset: tuple[float, float] = (0, 0)) -> Image.Image:
    """One straight RGB hue, with alpha quantized only after floating-point fade."""
    alpha = Image.fromarray(np.rint(effect_alpha(mask, opacity, blur, offset) * 255).astype(np.uint8))
    return color_layer(alpha, color)


def proof_board(before: Image.Image, after: Image.Image, limit: tuple[int, int] = (620, 340)) -> Image.Image:
    """Composites on actual flat backgrounds, not a baked checkerboard screenshot."""
    samples = []
    for img in (before, after):
        view = img.convert('RGBA').copy()
        scale=min(limit[0]/view.width,limit[1]/view.height)
        view=view.resize((max(1,round(view.width*scale)),max(1,round(view.height*scale))),Image.Resampling.LANCZOS)
        samples.append(view)
    w, h = limit
    board = Image.new('RGB', (2 * (w + 20), 4 * (h + 34)), '#646464')
    draw = ImageDraw.Draw(board)
    for row, color in enumerate(['#ffffff', '#111111', '#808080', '#ff00b0']):
        for col, view in enumerate(samples):
            bg = Image.new('RGBA', (w, h), color)
            bg.alpha_composite(view, ((w-view.width)//2, (h-view.height)//2))
            x, y = col*(w+20)+10, row*(h+34)+24
            board.paste(bg.convert('RGB'), (x, y))
            draw.text((x, y-18), ('BEFORE' if col == 0 else 'AFTER')+' '+color, fill='white')
    return board


def check_kit(kit: Path, identifiers: list[str] | None = None) -> dict:
    config_path = kit / 'style/sprite_quality.json'
    config = json.loads(config_path.read_text(encoding='utf-8')) if config_path.exists() else {}
    manifest = json.loads((kit/'manifest.json').read_text(encoding='utf-8'))
    result = {}
    for name in identifiers or list(manifest['elements']):
        entry = manifest['elements'][name]
        rule = config.get('elements', {}).get(name, {})
        mask_path = rule.get('body_mask')
        mask = Image.open(kit/mask_path).convert('L') if mask_path else None
        result[name] = audit(Image.open(kit/entry['file']), rule.get('alpha_mode', 'unknown'), mask)
        result[name]['body_mask_sha256'] = pixel_hash(mask.convert('RGBA')) if mask is not None else None
    return {'elements': result, 'issues': [f'{n}: {s}' for n,v in result.items() for s in v['issues']]}


def validate_delivery(kit: Path, identifiers: list[str]) -> None:
    config = kit/'style/sprite_quality.json'
    if not config.exists():
        raise ValueError('Classify sprite materials and run the quality review before delivery')
    report = check_kit(kit, identifiers)
    unknown = [n for n,v in report['elements'].items() if v['classification_required']]
    if report['issues'] or unknown:
        raise ValueError('Sprite alpha review failed: '+ '; '.join(report['issues'] + unknown))
    proof = kit/'export/sprite_quality_report.json'
    if not proof.exists():
        raise ValueError('Inspect the alpha/backdrop boards before marking quality reviewed')
    saved = json.loads(proof.read_text(encoding='utf-8'))
    for name, actual in report['elements'].items():
        old = saved.get('elements', {}).get(name, {})
        if (old.get('pixel_sha256') != actual['pixel_sha256'] or old.get('mode') != actual['mode']
                or old.get('body_mask_sha256') != actual['body_mask_sha256'] or not old.get('visual_reviewed')):
            raise ValueError(f'{name}: missing or stale visual alpha review')


if __name__=='__main__':
    raise SystemExit(main())
