#!/usr/bin/env python3
"""video_frames_waehlen.py - aus einem Handyvideo die brauchbaren Einzelbilder waehlen (Schaerfe + Verdeckung), CPU, ohne GPU.

  /media/oem/scan/venv-seg/bin/python -I tools/video_frames_waehlen.py <video.mp4> <ausgabeordner> [--fenster 8] [--rel 0.6] [--verdeck 0.05] [--probe]
Pass 1: ffmpeg liefert jedes Bild verkleinert (Breite 360, Grau, Rotation angewandt) -> je Bild Laplace-Varianz (Schaerfe) und Verdeckungsmass.
Auswahl: je Fenster von --fenster Bildern das schaerfste; es entfaellt, wenn Schaerfe < --rel x Median ALLER Bilder oder Verdeckungsanteil > --verdeck.
Verdeckungsmass = Anteil Pixel in grossen (>= 40x40 px bei Breite 360) flachen Bloecken (Gradient ~ 0), die zudem hell oder gross zusammenhaengen (weisse Transporter,
Waende ohne Struktur): Block-Standardabweichung < 8 Graustufen. Gemessen 6.11. am Kaufhaus-Video (Sichtkontrolle): Transporter 0,06-0,39, Fassadenbilder 0,00-0,11 (hoher bewoelkter Himmel im unteren Bilddrittel gibt Fehlalarm, kostet Bilder, kein Fehlbild). ANNAHME: Gebaeudefassaden haben Struktur > 8; Himmel zaehlt mit (Himmel ist kein Verdecker, daher
nur Bloecke ausserhalb des oberen Bilddrittels mit Helligkeit > 150 und Std < 4).
Pass 2: ausgewaehlte Bilder in voller Aufloesung als JPEG (q 2) nach <ausgabe>/bilder/vid_<nnnn>.jpg; <ausgabe>/auswahl.json mit Schaerfe, Verdeckung, Grund je Bild.
Nichts Objektspezifisches. Keine Rotationsannahme: ffmpeg wendet die Container-Rotation selbst an.
"""
import os, sys, json, argparse, subprocess, numpy as np, cv2


def info(video):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate,nb_frames:stream_side_data=rotation", "-of", "json", video], capture_output=True, text=True, check=True)
    s = json.loads(r.stdout)["streams"][0]; w, h = int(s["width"]), int(s["height"]); rot = 0
    for sd in s.get("side_data_list", []):
        if "rotation" in sd: rot = int(sd["rotation"])
    if abs(rot) == 90: w, h = h, w
    return w, h, s["r_frame_rate"], int(s.get("nb_frames", 0) or 0)


def verdeckung(g):
    """Anteil Pixel in flachen hellen Bloecken (unteres 2/3 des Bildes); g = Graubild uint8."""
    H, W = g.shape; b = 40; y0 = H // 3; n = tot = 0
    for y in range(y0, H - b + 1, b):
        for x in range(0, W - b + 1, b):
            blk = g[y:y + b, x:x + b]; tot += 1
            if blk.std() < 8.0 and blk.mean() > 150: n += 1
    return n / max(tot, 1)


def pass1(video, w, h, breite=360):
    hh = int(round(h * breite / w / 2)) * 2
    cmd = ["ffmpeg", "-v", "error", "-threads", "4", "-i", video, "-vf", f"scale={breite}:{hh}", "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    p = subprocess.Popen(["nice", "-n", "10"] + cmd, stdout=subprocess.PIPE); S = []; V = []; n = 0
    while True:
        buf = p.stdout.read(breite * hh)
        if len(buf) < breite * hh: break
        g = np.frombuffer(buf, np.uint8).reshape(hh, breite); S.append(float(cv2.Laplacian(g, cv2.CV_64F).var())); V.append(verdeckung(g)); n += 1
    p.wait(); return np.array(S), np.array(V)


def waehlen(S, V, fenster, rel, verd):
    med = float(np.median(S)); sel = []; grund = {}
    for a in range(0, len(S), fenster):
        idx = np.arange(a, min(a + fenster, len(S))); ok = [i for i in idx if V[i] <= verd]
        if not ok: grund[a] = "verdeckt"; continue
        i = max(ok, key=lambda j: S[j])
        if S[i] < rel * med: grund[a] = "unscharf"; continue
        sel.append(int(i))
    return sel, med, grund


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video"); ap.add_argument("aus"); ap.add_argument("--fenster", type=int, default=8); ap.add_argument("--rel", type=float, default=0.6)
    ap.add_argument("--verdeck", type=float, default=0.05); ap.add_argument("--probe", action="store_true", help="nur Auswahl berechnen, keine Bilder schreiben")
    a = ap.parse_args(); w, h, fps, nb = info(a.video); print(f"Video {w}x{h} (nach Rotation), {fps}, {nb} Bilder", flush=True)
    S, V = pass1(a.video, w, h); sel, med, grund = waehlen(S, V, a.fenster, a.rel, a.verdeck)
    print(f"Bilder {len(S)}, Schaerfe-Median {med:.0f}; gewaehlt {len(sel)}, verworfen verdeckt {sum(v == 'verdeckt' for v in grund.values())}, unscharf {sum(v == 'unscharf' for v in grund.values())} (von {len(grund) + len(sel)} Fenstern)", flush=True)
    os.makedirs(a.aus, exist_ok=True)
    json.dump(dict(video=os.path.abspath(a.video), breite=w, hoehe=h, fenster=a.fenster, rel=a.rel, verdeck=a.verdeck, schaerfe_median=med, gewaehlt=sel,
                   schaerfe=[round(float(S[i]), 1) for i in sel], verdeckung=[round(float(V[i]), 3) for i in sel], verworfen={str(k): v for k, v in grund.items()},
                   alle_schaerfe=[round(float(x), 1) for x in S], alle_verdeckung=[round(float(x), 3) for x in V]), open(os.path.join(a.aus, "auswahl.json"), "w"))
    if a.probe: return
    bd = os.path.join(a.aus, "bilder"); os.makedirs(bd, exist_ok=True)
    expr = "+".join(f"eq(n\\,{i})" for i in sel)
    # ffmpeg-Ausdruecke sind laenglich begrenzt: in Gruppen zu 60 Bildern
    for g0 in range(0, len(sel), 60):
        grp = sel[g0:g0 + 60]; expr = "+".join(f"eq(n\\,{i})" for i in grp)
        subprocess.run(["nice", "-n", "10", "ffmpeg", "-v", "error", "-y", "-threads", "4", "-i", a.video, "-vf", f"select='{expr}'", "-vsync", "0", "-q:v", "2", "-start_number", "0", os.path.join(bd, f"tmp_{g0:04d}_%03d.jpg")], check=True)
        for k, i in enumerate(grp): os.replace(os.path.join(bd, f"tmp_{g0:04d}_{k:03d}.jpg"), os.path.join(bd, f"vid_{i:04d}.jpg"))
    print("geschrieben:", bd, len(os.listdir(bd)), "Bilder")


if __name__ == "__main__":
    main()
