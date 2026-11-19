#!/usr/bin/env python3
"""Finds the newest GTA 6 money spot / glitch / tips videos on YouTube.

Writes discover/youtube.json, newest-and-most-viewed first. For each video it
also suggests the best window to clip: YouTube's "most replayed" peak when the
video has one, otherwise its first chapter after the intro.
"""
import json
import subprocess
import time
import urllib.parse

QUERIES = json.load(open("discover/yt_queries.json"))
seen, cands = set(), []
for q in QUERIES:
    url = ("https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(q)
           + "&sp=EgIIAw%253D%253D")  # filter: uploaded this week
    r = subprocess.run(["yt-dlp", "--flat-playlist", "-J", "--playlist-end", "25", url],
                       capture_output=True, text=True, timeout=180)
    try:
        entries = json.loads(r.stdout).get("entries") or []
    except Exception:
        print("search failed:", q, r.stderr[-300:])
        continue
    for e in entries:
        if e.get("id") and e["id"] not in seen:
            seen.add(e["id"])
            cands.append({"id": e["id"], "query": q, "title": e.get("title"),
                          "views": e.get("view_count"), "duration": e.get("duration"),
                          "channel": e.get("channel") or e.get("uploader")})
    print(q, len(entries))

# keep the most-viewed candidates, then fetch full details (upload time, heatmap)
cands.sort(key=lambda c: c["views"] or 0, reverse=True)
out = []
for c in cands[:30]:
    url = f"https://www.youtube.com/watch?v={c['id']}"
    r = subprocess.run(["yt-dlp", "-J", "--skip-download", url],
                       capture_output=True, text=True, timeout=120)
    try:
        info = json.loads(r.stdout)
    except Exception:
        print("info failed:", c["id"], r.stderr[-200:])
        continue
    dur = info.get("duration") or 0
    start = 0.0
    hm = info.get("heatmap") or []
    if hm and dur > 60:
        peak = max(hm[1:] if len(hm) > 1 else hm, key=lambda h: h.get("value", 0))
        start = max(0.0, peak["start_time"] - 8)
    elif info.get("chapters") and dur > 60:
        ch = info["chapters"]
        start = ch[1]["start_time"] if len(ch) > 1 else 0.0
    out.append({
        "url": url, "title": info.get("title"), "channel": info.get("channel"),
        "views": info.get("view_count"), "duration": dur,
        "uploaded": info.get("timestamp"), "is_short": dur <= 60,
        "suggest_trim": round(start, 1), "has_heatmap": bool(hm), "query": c["query"],
    })

out.sort(key=lambda v: ((v["uploaded"] or 0) > time.time() - 86400 * 2, v["views"] or 0), reverse=True)
json.dump({"updated": int(time.time()), "videos": out}, open("discover/youtube.json", "w"), indent=1)
print("videos", len(out))
