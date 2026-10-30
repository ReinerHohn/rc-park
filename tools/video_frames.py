#!/usr/bin/env python3
"""video_frames.py — Fotos AUS VIDEOS für Photogrammetrie/Fassadenmessung.
Ein Touristen-Video, das um ein Wahrzeichen schwenkt, liefert dutzende Blickwinkel
in Sekunden — ideal für SfM (die vielen überlappenden Ansichten, die COLMAP/OpenSfM
brauchen) ODER um einen scharfen Frontal-Frame zu fischen.

Pipeline: yt-dlp (Download bester Qualität) → ffmpeg (N Frames/s) → Schärfefilter
(Laplace-Varianz; Bewegungsunschärfe raus) → scharfe, verschiedene Frames + manifest.

  python3 tools/video_frames.py --url "https://youtu.be/XXXX" \
      --out daten/martinstor/fotos/video --fps 1.5 --min-sharp 80 --max 60
  python3 tools/video_frames.py --file lokal.mp4 --out ... --fps 2

RECHTLICH (ehrlich, wichtig fürs Geschäftsmodell): YouTube-Videos sind urheberrechtlich
geschützt (Uploader). Als PRIVATE Modellier-Referenz Graubereich; für ein VERKAUFTES
Produkt brauchst du Rechte — oder bleib bei CC/PD-Quellen (Commons, commons_harvest.py).
"""
import argparse, os, sys, glob, json, subprocess
import numpy as np, cv2


def download(url, workdir):
    out = os.path.join(workdir, "video.%(ext)s")
    # bestes mp4 bis 1080p (mehr bringt für Frames selten was)
    cmd = ["yt-dlp", "-f", "bestvideo[height<=1080][ext=mp4]/best[height<=1080]",
           "-o", out, url]
    print(f"  yt-dlp lädt {url} ...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"yt-dlp-Fehler: {r.stderr.strip()[-200:]}")
    vids = glob.glob(os.path.join(workdir, "video.*"))
    return vids[0] if vids else sys.exit("Kein Video geladen.")


def extract(video, raw_dir, fps):
    os.makedirs(raw_dir, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-i", video, "-vf", f"fps={fps}", "-qscale:v", "2",
           os.path.join(raw_dir, "f_%04d.jpg")]
    print(f"  ffmpeg extrahiert {fps} Frames/s ...")
    subprocess.run(cmd, capture_output=True, text=True)
    return sorted(glob.glob(os.path.join(raw_dir, "f_*.jpg")))


def sharpness(path):
    im = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if im is None: return 0.0
    if max(im.shape) > 1000:
        s = 1000 / max(im.shape); im = cv2.resize(im, None, fx=s, fy=s)
    return float(cv2.Laplacian(im, cv2.CV_64F).var())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="Video-URL (YouTube etc., via yt-dlp)")
    ap.add_argument("--file", help="lokale Videodatei (statt --url)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=float, default=1.5, help="Frames pro Sekunde extrahieren")
    ap.add_argument("--min-sharp", type=float, default=60, help="min. Laplace-Varianz (Unschärfe-Filter)")
    ap.add_argument("--max", type=int, default=60, help="max. behaltene Frames")
    a = ap.parse_args()
    if not a.url and not a.file:
        sys.exit("--url oder --file nötig.")
    os.makedirs(a.out, exist_ok=True)
    raw = os.path.join(a.out, "_raw")

    video = a.file if a.file else download(a.url, a.out)
    frames = extract(video, raw, a.fps)
    print(f"  {len(frames)} Rohframes → Schärfe prüfen ...")
    scored = [(f, sharpness(f)) for f in frames]
    sharp = [(f, s) for f, s in scored if s >= a.min_sharp]
    sharp.sort(key=lambda x: -x[1])
    keep = sharp[:a.max]

    manifest = []
    for i, (f, s) in enumerate(sorted(keep, key=lambda x: x[0])):
        dst = os.path.join(a.out, f"vf_{i:03d}.jpg")
        os.replace(f, dst)
        manifest.append({"file": os.path.basename(dst), "sharpness": round(s, 1)})
    # Rohordner + Video aufräumen
    for f in glob.glob(os.path.join(raw, "*")): os.remove(f)
    try: os.rmdir(raw)
    except OSError: pass
    json.dump({"source": a.url or a.file, "fps": a.fps, "frames": manifest},
              open(os.path.join(a.out, "manifest.json"), "w"), indent=2)
    print(f"\n{len(manifest)} scharfe Frames (von {len(frames)}) → {a.out}")
    print(f"Schärfe behalten: {round(keep[-1][1],0) if keep else 0}..{round(keep[0][1],0) if keep else 0}")
    print("Nächster Schritt: opensfm_run.py / COLMAP (Photogrammetrie) ODER besten Frontal-Frame nehmen.")


if __name__ == "__main__":
    main()
