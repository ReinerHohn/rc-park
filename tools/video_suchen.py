#!/usr/bin/env python3
"""video_suchen.py - Videoclips (Drohne/Rundgang) fuer ein Objekt AUTOMATISCH finden und pruefen (5.11.: Martinstor-Clips waren noch von Hand gesucht;
Nutzerregel "alles vollautomatisch"). Schritt vor tools/video_frames.py / nullstart --videos.

1. Suche: yt-dlp "ytsearchN:<Anfrage>" fuer alle Anfragen aus objekt.json (name, ort, bildquellen.commons.suchen) x Zusaetze (Drohne, drone, aerial, 4K, walk).
2. Vorpruefung je Clip (Laenge <= --max-s): Vorschau in niedriger Aufloesung (<= 480p) laden, je --abstand s ein Bild.
3. Beweis, dass das Objekt zu sehen ist (nicht Titel/Bildbeschreibung): SIFT-Merkmale (OpenCV, Apache 2) jedes Bildes gegen die Objektfotos
   (objekt.json fotos_dir, --ref beste N); Treffer = >= --min-inlier RANSAC-Inlier (Fundamentalmatrix) zu mindestens einem Objektfoto.
4. Ergebnis je Clip: Treffer-Bilder, Zeitabschnitte (Treffer zusammengefasst), Bildwinkel-Neuheit grob (Treffer zu verschiedenen Objektfotos).
Ausgabe --aus/video_kandidaten.json (sortiert nach Trefferzahl) + Kontaktabzug je Clip (Treffer gruen). LIZENZ: YouTube = nur private Messvorlage
(modelle/LIZENZ_WERKZEUGE.md); Vorschauen werden nach der Pruefung geloescht (nur Kandidatenliste bleibt).
  python3 tools/video_suchen.py modelle/<objekt>/objekt.json --aus <ordner> [--suchen 12] [--abstand 2] [--ref 12]
"""
import os, sys, json, glob, argparse, subprocess, time, shutil
import numpy as np, cv2

ZUSAETZE = ["drohne", "drone 4k", "aerial", "walk 4k", ""]


def sift_ref(pfade, kante=1000):
    s = cv2.SIFT_create(4000); R = []
    for p in pfade:
        im = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
        if im is None: continue
        f = kante / max(im.shape); im = cv2.resize(im, None, fx=min(1, f), fy=min(1, f), interpolation=cv2.INTER_AREA)
        k, d = s.detectAndCompute(im, None)
        if d is not None and len(k) > 50: R.append((os.path.basename(p), np.float32([x.pt for x in k]), d))
    return R


def treffer(bild, R, bf, s, min_inlier):
    k, d = s.detectAndCompute(bild, None); best = (0, None)
    if d is None or len(k) < 50: return best
    P = np.float32([x.pt for x in k])
    for nm, Q, dq in R:
        mm = bf.knnMatch(d, dq, k=2); g = [m for m, n in (x for x in mm if len(x) == 2) if m.distance < 0.75 * n.distance]
        if len(g) < min_inlier: continue
        A = P[[m.queryIdx for m in g]]; B = Q[[m.trainIdx for m in g]]; F, msk = cv2.findFundamentalMat(A, B, cv2.FM_RANSAC, 3.0, 0.999)
        n = int(msk.sum()) if msk is not None else 0
        if n > best[0]: best = (n, nm)
    return best


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--aus", required=True); ap.add_argument("--suchen", type=int, default=12)
    ap.add_argument("--abstand", type=float, default=2.0); ap.add_argument("--ref", type=int, default=12); ap.add_argument("--min-inlier", type=int, default=40)
    ap.add_argument("--max-s", type=int, default=1500); ap.add_argument("--anfragen", nargs="*"); ap.add_argument("--nur", nargs="*", help="nur diese Clip-IDs pruefen")
    a = ap.parse_args(argv); t0 = time.time(); os.makedirs(a.aus, exist_ok=True); op = os.path.abspath(a.objekt); obj = json.load(open(op))
    root = os.path.dirname(os.path.dirname(os.path.dirname(op)))
    name = obj.get("name", "").split("(")[0].strip(); ort = obj.get("ort", "").split(",")[0].strip()
    basis = a.anfragen or sorted({x for x in [name, f"{name} {ort}".strip()] + list((obj.get("bildquellen", {}).get("commons", {}) or {}).get("suchen", [])) if x})
    fd = obj.get("fotos_dir"); fd = fd if os.path.isabs(fd) else os.path.join(root, fd)
    fotos = sorted(glob.glob(os.path.join(fd, "*.jpg")) + glob.glob(os.path.join(fd, "*.png")) + glob.glob(os.path.join(fd, "*.jpeg")))
    if obj.get("fotos"): fotos = [p for p in fotos if os.path.splitext(os.path.basename(p))[0] in obj["fotos"]] or fotos
    step = max(1, len(fotos) // a.ref); R = sift_ref(fotos[::step][:a.ref]); print(f"{len(R)} Objektfotos als Referenz ({time.time() - t0:.0f} s)", flush=True)
    kand = {}
    if a.nur: kand = {c: dict(id=c, dauer=None, titel="", anfrage="--nur") for c in a.nur}
    else:
        for b in basis:
            for z in ZUSAETZE:
                q = f"{b} {z}".strip(); r = subprocess.run(["yt-dlp", "--flat-playlist", "--print", "%(id)s|%(duration)s|%(title)s", f"ytsearch{a.suchen}:{q}"], capture_output=True, text=True, timeout=300)
                for ln in r.stdout.splitlines():
                    p = ln.split("|", 2)
                    if len(p) == 3 and p[0] not in kand:
                        try: du = float(p[1])
                        except ValueError: du = None
                        kand[p[0]] = dict(id=p[0], dauer=du, titel=p[2], anfrage=q)
        print(f"{len(kand)} Kandidaten aus {len(basis)} Anfragen ({time.time() - t0:.0f} s)", flush=True)
    s = cv2.SIFT_create(2000); bf = cv2.BFMatcher(); erg = []
    for c in kand.values():
        if c["dauer"] and c["dauer"] > a.max_s: c["status"] = "zu lang"; erg.append(c); continue
        vd = os.path.join(a.aus, "vorschau", c["id"]); os.makedirs(vd, exist_ok=True)
        r = subprocess.run(["yt-dlp", "-f", "bv*[height<=480][vcodec^=avc1]/b[height<=480][vcodec^=avc1]/bv*[height<=480][vcodec^=vp9]/wv*", "-o", os.path.join(vd, "v.%(ext)s"), "--no-playlist", f"https://youtu.be/{c['id']}"], capture_output=True, text=True, timeout=900)
        vv = [p for p in glob.glob(os.path.join(vd, "v.*")) if not p.endswith(".part")]
        if not vv: c["status"] = "Download fehlgeschlagen: " + (r.stderr or "")[-200:]; erg.append(c); shutil.rmtree(vd, ignore_errors=True); continue
        cap = cv2.VideoCapture(vv[0]); fps = cap.get(cv2.CAP_PROP_FPS) or 25; n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); hits = []; bilder = []
        for t in np.arange(0, n / fps, a.abstand):
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000); ok, im = cap.read()
            if not ok: continue
            g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY); ni, ref = treffer(g, R, bf, s, a.min_inlier)
            if ni: hits.append(dict(t=round(float(t), 1), inlier=ni, foto=ref))
            bilder.append((im, ni > 0))
        abschn = []
        for h in hits:
            if abschn and h["t"] - abschn[-1][1] <= 2.5 * a.abstand: abschn[-1][1] = h["t"]
            else: abschn.append([h["t"], h["t"]])
        c.update(status="geprueft", bilder=len(bilder), treffer=len(hits), fotos_getroffen=len({h["foto"] for h in hits}), abschnitte=abschn, hits=hits)
        if bilder:                                                                                   # Kontaktabzug (Treffer gruen umrandet)
            th = [cv2.copyMakeBorder(cv2.resize(im, (160, 90)), 3, 3, 3, 3, cv2.BORDER_CONSTANT, value=(0, 200, 0) if hit else (60, 60, 60)) for im, hit in bilder[:120]]
            th += [np.zeros_like(th[0])] * (-len(th) % 10); cv2.imwrite(os.path.join(a.aus, f"kontakt_{c['id']}.jpg"), cv2.vconcat([cv2.hconcat(th[i:i + 10]) for i in range(0, len(th), 10)]))
        shutil.rmtree(vd, ignore_errors=True); erg.append(c)
        print(f"  {c['id']} ({c['dauer']} s) {c['titel'][:50]!r}: {len(hits)}/{len(bilder)} Bilder zeigen das Objekt, {c['fotos_getroffen']} Objektfotos  ({time.time() - t0:.0f} s)", flush=True)
        json.dump(dict(objekt=op, referenz=[x[0] for x in R], parameter=vars(a), clips=sorted(erg, key=lambda x: -x.get("treffer", 0))), open(os.path.join(a.aus, "video_kandidaten.json"), "w"), indent=1, ensure_ascii=False)
    json.dump(dict(objekt=op, referenz=[x[0] for x in R], parameter=vars(a), clips=sorted(erg, key=lambda x: -x.get("treffer", 0)), sekunden=round(time.time() - t0)),
              open(os.path.join(a.aus, "video_kandidaten.json"), "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
