#!/usr/bin/env python3
"""videobilder_ausduennen.py <video_frames_ordner> [fenster=3]
Je Clip aus jeweils <fenster> aufeinanderfolgenden Bildern das schaerfste behalten (manifest.json von videos_zu_bildern.py).
Schreibt ausgewaehlt.txt (Dateinamen) und verlinkt sie in <ordner>/gewaehlt/."""
import sys, os, json, collections
d = sys.argv[1]; w = int(sys.argv[2]) if len(sys.argv) > 2 else 3
m = json.load(open(os.path.join(d, "manifest.json")))["frames"]; clips = collections.defaultdict(list)
for f in m: clips[f["clip"]].append(f)
keep = []
for c, fs in clips.items():
    fs.sort(key=lambda f: f["file"])
    for i in range(0, len(fs), w): keep.append(max(fs[i:i + w], key=lambda f: f["schaerfe"])["file"])
g = os.path.join(d, "gewaehlt"); os.makedirs(g, exist_ok=True)
for f in keep:
    p = os.path.join(g, f)
    if not os.path.lexists(p): os.symlink(os.path.join("..", f), p)
open(os.path.join(d, "ausgewaehlt.txt"), "w").write("\n".join(keep) + "\n")
print(f"{len(keep)} von {len(m)} Bildern -> {g}")
