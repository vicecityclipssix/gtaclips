#!/usr/bin/env python3
"""Lists each streamer's top Twitch clips from the last 24h into discover/latest.json."""
import json
import subprocess
import sys
import time

CHANNELS = json.load(open("discover/channels.json"))
out = []
for ch in CHANNELS:
    url = f"https://www.twitch.tv/{ch}/clips?filter=clips&range=24hr"
    try:
        r = subprocess.run(["yt-dlp", "--flat-playlist", "-J", "--playlist-end", "40", url],
                           capture_output=True, text=True, timeout=180)
        data = json.loads(r.stdout or "{}")
    except Exception as e:  # keep going for the other channels
        print(ch, "failed:", e, file=sys.stderr)
        continue
    for e in data.get("entries") or []:
        out.append({
            "channel": ch,
            "title": e.get("title"),
            "views": e.get("view_count"),
            "duration": e.get("duration"),
            "url": e.get("url") or e.get("webpage_url"),
            "created": e.get("timestamp"),
        })
    print(ch, len(data.get("entries") or []), file=sys.stderr)

out.sort(key=lambda x: x["views"] or 0, reverse=True)
json.dump({"updated": int(time.time()), "clips": out}, open("discover/latest.json", "w"), indent=1)
print("total", len(out))
