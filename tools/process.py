#!/usr/bin/env python3
"""Downloads and renders every job in jobs/*.json that has no output yet.

Job file: a list of {"id", "url", "caption", "emoji", "credit", "trim", "dur", "fit", "crop"}.
Output: out/<id>.mp4
"""
import glob
import json
import os
import subprocess

os.makedirs("src", exist_ok=True)
os.makedirs("out", exist_ok=True)
for jf in sorted(glob.glob("jobs/*.json")):
    for j in json.load(open(jf)):
        out = f"out/{j['id']}.mp4"
        if os.path.exists(out):
            continue
        src = f"src/{j['id']}.mp4"
        try:
            dl = ["yt-dlp", "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/best[ext=mp4]/best",
                  "--merge-output-format", "mp4", "-o", src, "--force-overwrites"]
            trim = float(j.get("trim", 0))
            if trim > 0:  # long video: only download the window we need
                dl += ["--download-sections", f"*{trim}-{trim + float(j.get('dur', 30)) + 1}",
                       "--force-keyframes-at-cuts"]
                j = dict(j, trim=0)
            subprocess.run(dl + [j["url"]], check=True, timeout=600)
            layers = f"src/layers_{j['id']}"
            subprocess.run(["python3", "tools/make_overlay.py", "--caption", j["caption"],
                            "--emoji", j.get("emoji", ""), "--credit", j.get("credit", ""),
                            "--outdir", layers], check=True)
            cmd = ["python3", "tools/render.py", src, out, "--layers", layers,
                   "--trim", str(j.get("trim", 0)), "--dur", str(j.get("dur", 30))]
            if j.get("fit", True):
                cmd.append("--fit")
            if j.get("crop"):
                cmd += ["--crop", j["crop"]]
            subprocess.run(cmd, check=True, timeout=900)
            print("OK", out)
        except Exception as e:
            print("FAIL", j["id"], e)
            open(f"out/{j['id']}.error.txt", "w").write(str(e))
