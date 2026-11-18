#!/usr/bin/env python3
"""Builds the static layers for a Vice City Clips vertical video (1080x1920).

Outputs three PNGs into --outdir:
  overlay.png  header, single caption (+ emoji), footage frame glow, credit line
  tint.png     Vice City sunset tint laid over the blurred background
  mask.png     rounded-corner alpha mask for the foreground footage
"""
import argparse
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
FG_Y, FG_H = 660, 840          # foreground footage band
FG_X, FG_W = 0, 1080
RADIUS = 36

# Vice City / Miami Vice palette
PINK = (255, 46, 147)
ORANGE = (255, 150, 60)
PURPLE = (120, 44, 210)
TEAL = (24, 226, 214)
NAVY = (24, 10, 48)
WHITE = (255, 255, 255)

FONT_DIR = "/usr/share/fonts/truetype"
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_FONT = os.path.join(HERE, "..", "fonts", "Anton-Regular.ttf")
EMOJI_FONT = os.path.join(HERE, "..", "fonts", "NotoColorEmoji.ttf")


def vgrad(w, h, stops):
    """Vertical gradient image from a list of (pos 0..1, (r,g,b[,a])) stops."""
    img = Image.new("RGBA", (w, h))
    px = img.load()
    stops = [(p, c if len(c) == 4 else (*c, 255)) for p, c in stops]
    for y in range(h):
        t = y / max(h - 1, 1)
        for i in range(len(stops) - 1):
            p0, c0 = stops[i]
            p1, c1 = stops[i + 1]
            if p0 <= t <= p1:
                k = (t - p0) / max(p1 - p0, 1e-6)
                col = tuple(int(c0[j] + (c1[j] - c0[j]) * k) for j in range(4))
                break
        for x in range(w):
            px[x, y] = col
    return img


def styled_text(text, font, fill_stops, stroke, stroke_col, glow_col, glow_blur):
    """Text with gradient fill, solid outline and soft neon glow, as RGBA."""
    pad = stroke + glow_blur * 3
    l, t, r, b = font.getbbox(text, stroke_width=stroke)
    w, h = r - l + pad * 2, b - t + pad * 2
    origin = (pad - l, pad - t)

    m_stroke = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m_stroke).text(origin, text, font=font, fill=255,
                                  stroke_width=stroke, stroke_fill=255)
    m_fill = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m_fill).text(origin, text, font=font, fill=255)

    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if glow_col:
        glow = Image.new("RGBA", (w, h), (*glow_col, 0))
        glow.putalpha(m_stroke.filter(ImageFilter.GaussianBlur(glow_blur)))
        out = Image.alpha_composite(out, glow)
        out = Image.alpha_composite(out, glow)  # double pass = stronger neon
    solid = Image.new("RGBA", (w, h), (*stroke_col, 255))
    solid.putalpha(m_stroke)
    out = Image.alpha_composite(out, solid)
    # gradient spans the glyph box only (not the padding)
    gl, gt, gr, gb = m_fill.getbbox() or (0, 0, w, h)
    grad = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    grad.paste(vgrad(w, gb - gt, fill_stops), (0, gt))
    fill_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    fill_layer.paste(grad, (0, 0), m_fill)
    out = Image.alpha_composite(out, fill_layer)
    return out, pad


def emoji_image(ch, height):
    font = ImageFont.truetype(EMOJI_FONT, 109)
    tmp = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text((10, 10), ch, font=font, embedded_color=True)
    tmp = tmp.crop(tmp.getbbox())
    ratio = height / tmp.height
    return tmp.resize((int(tmp.width * ratio), height), Image.LANCZOS)


def wrap(text, font, max_w, stroke):
    words, lines, cur = text.split(), [], ""
    for wd in words:
        trial = (cur + " " + wd).strip()
        l, _, r, _ = font.getbbox(trial, stroke_width=stroke)
        if r - l <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    lines.append(cur)
    return lines


def build(args):
    os.makedirs(args.outdir, exist_ok=True)
    over = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # Header: page name, Miami Vice teal with pink glow
    hfont = ImageFont.truetype(args.font, args.header_size)
    head, hpad = styled_text(args.header, hfont, [(0, WHITE), (1, TEAL)],
                             5, NAVY, PINK, 10)
    over.alpha_composite(head, ((W - head.width) // 2, args.header_y - head.height // 2))

    # Single caption, sized to fit in at most two lines, emoji on the last line
    size = args.caption_size
    emoji_gap = 18
    while True:
        cfont = ImageFont.truetype(args.font, size)
        stroke = max(6, size // 10)
        reserve = int(size * 1.05) + emoji_gap if args.emoji else 0
        lines = wrap(args.caption.upper(), cfont, 960 - reserve, stroke)
        if len(lines) <= 2 or size <= 64:
            break
        size -= 6
    rendered = [styled_text(ln, cfont, [(0, (255, 120, 200)), (0.55, PINK), (1, ORANGE)],
                            stroke, NAVY, PINK, 14) for ln in lines]
    line_gap = int(size * 0.04)
    heights = [img.height - 2 * pad for img, pad in rendered]
    block_h = sum(heights) + line_gap * (len(lines) - 1)
    y = FG_Y - 44 - block_h
    for i, (img, pad) in enumerate(rendered):
        extra = None
        if args.emoji and i == len(rendered) - 1:
            extra = emoji_image(args.emoji, int(heights[i] * 0.92))
        total_w = img.width - 2 * pad + (extra.width + emoji_gap if extra else 0)
        x = (W - total_w) // 2
        over.alpha_composite(img, (x - pad, y - pad))
        if extra:
            ex = x + img.width - 2 * pad + emoji_gap
            over.alpha_composite(extra, (ex, y + (heights[i] - extra.height) // 2))
        y += heights[i] + line_gap

    # Neon frame around the footage: pink -> orange, soft glow
    frame_mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(frame_mask).rounded_rectangle(
        (FG_X + 4, FG_Y - 4, FG_X + FG_W - 5, FG_Y + FG_H + 3), RADIUS + 4, outline=255, width=6)
    ring = vgrad(W, H, [(0, PINK), (FG_Y / H, PINK), ((FG_Y + FG_H) / H, ORANGE), (1, ORANGE)])
    glow = ring.copy()
    glow.putalpha(frame_mask.filter(ImageFilter.GaussianBlur(14)))
    ring.putalpha(frame_mask)
    over = Image.alpha_composite(over, glow)
    over = Image.alpha_composite(over, ring)

    # Credit under the footage
    if args.credit:
        crfont = ImageFont.truetype(args.font, 40)
        cr, crpad = styled_text(args.credit.upper(), crfont, [(0, WHITE), (1, WHITE)],
                                3, NAVY, None, 1)
        over.alpha_composite(cr, ((W - cr.width) // 2, FG_Y + FG_H + 34 - crpad))

    over.save(os.path.join(args.outdir, "overlay.png"))

    tint = vgrad(W, H, [(0, (*PURPLE, 130)), (0.45, (*PINK, 60)),
                        (0.8, (*ORANGE, 70)), (1, (*NAVY, 150))])
    tint.save(os.path.join(args.outdir, "tint.png"))

    mask = Image.new("L", (FG_W, FG_H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, FG_W - 1, FG_H - 1), RADIUS, fill=255)
    mask.save(os.path.join(args.outdir, "mask.png"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--caption", required=True)
    ap.add_argument("--emoji", default="")
    ap.add_argument("--credit", default="Footage: @RockstarGames")
    ap.add_argument("--header", default="VICE CITY CLIPS")
    ap.add_argument("--font", default=DEFAULT_FONT)
    ap.add_argument("--header-size", type=int, default=84)
    ap.add_argument("--header-y", type=int, default=210)
    ap.add_argument("--caption-size", type=int, default=128)
    ap.add_argument("--outdir", default="layers")
    build(ap.parse_args())
