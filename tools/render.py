#!/usr/bin/env python3
"""Renders a source clip into a 1080x1920 Vice City Clips video.

  python3 render.py SRC OUT --layers layers [--speed 2] [--trim 1.5] [--dur 14]

--speed 2 undoes a half-speed browser capture (video and audio, exact inverse).
--trim/--dur pick the window, in real-time seconds after the speed fix.
Background = the same footage, zoomed to fill, blurred and sunset-tinted.
Foreground = the footage with letterbox bars removed, rounded corners.
"""
import argparse
import re
import subprocess

FG_Y, FG_W, FG_H = 660, 1080, 840


def detect_crop(src):
    cmd = ["ffmpeg", "-hide_banner", "-t", "10", "-i", src,
           "-vf", "cropdetect=24:2:0", "-f", "null", "-"]
    err = subprocess.run(cmd, capture_output=True, text=True).stderr
    crops = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", err)
    if not crops:
        return None
    w, h, x, y = map(int, crops[-1])
    # only trust it for real letterboxing (keeps full width, trims >4% height)
    if w < 1800 or h > 1035:
        return None
    return f"{w}:{h}:{x}:{y}"


def render(a):
    crop = a.crop or (None if a.nocrop else detect_crop(a.src))
    pre = f"crop={crop}," if crop else ""
    sp = a.speed
    fc = (
        f"[0:v]setpts=(PTS-STARTPTS)/{sp},trim=start={a.trim}:duration={a.dur},"
        f"setpts=PTS-STARTPTS,{pre}setsar=1,fps=30,split[a][b];"
        f"[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
        f"gblur=sigma=26,eq=brightness=-0.10:saturation=1.3[bg0];"
        f"[bg0][2:v]overlay=0:0[bg];"
        + (
            # fit: keep the whole frame (facecams in corners stay visible)
            f"[b]scale={FG_W}:-2,eq=saturation=1.12:contrast=1.04,format=rgba[fg];"
            f"[bg][fg]overlay=0:{FG_Y}+({FG_H}-overlay_h)/2[v1];"
            if a.fit else
            f"[b]scale={FG_W}:{FG_H}:force_original_aspect_ratio=increase,crop={FG_W}:{FG_H},"
            f"eq=saturation=1.12:contrast=1.04,format=rgba[fg0];"
            f"[3:v]format=gray[m];[fg0][m]alphamerge[fg];"
            f"[bg][fg]overlay=0:{FG_Y}[v1];"
        ) +
        f"[v1][1:v]overlay=0:0,format=yuv420p[v];"
        f"[0:a]asetpts=PTS-STARTPTS,asetrate={int(48000 * sp)},aresample=48000,"
        f"atrim=start={a.trim}:duration={a.dur},asetpts=PTS-STARTPTS,"
        f"afade=t=out:st={max(a.dur - 0.4, 0)}:d=0.4[aout]"
    )
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", a.src,
           "-loop", "1", "-i", f"{a.layers}/overlay.png",
           "-loop", "1", "-i", f"{a.layers}/tint.png",
           "-loop", "1", "-i", f"{a.layers}/mask.png",
           "-filter_complex", fc, "-map", "[v]", "-map", "[aout]",
           "-t", str(a.dur), "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
           "-profile:v", "high", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-movflags", "+faststart", a.out]
    subprocess.run(cmd, check=True)
    print(f"crop={crop} -> {a.out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--layers", default="layers")
    ap.add_argument("--speed", type=float, default=1)
    ap.add_argument("--trim", type=float, default=0)
    ap.add_argument("--dur", type=float, default=14)
    ap.add_argument("--nocrop", action="store_true")
    ap.add_argument("--crop", help="manual crop w:h:x:y applied before layout")
    ap.add_argument("--fit", action="store_true", help="show the full frame instead of filling the band")
    render(ap.parse_args())
