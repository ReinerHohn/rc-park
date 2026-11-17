#!/usr/bin/env python3
"""video_suchen.py - Videoclips (Drohne/Rundgang) fuer ein Objekt AUTOMATISCH finden und pruefen (5.11.: Martinstor-Clips waren noch von Hand gesucht;
Nutzerregel "alles vollautomatisch"). Schritt vor tools/video_frames.py / nullstart --videos.

1. Suche: yt-dlp "ytsearchN:<Anfrage>" fuer alle Anfragen aus objekt.json (name, ort, bildquellen.commons.suchen) x Zusaetze (Drohne, drone, aerial, 4K, walk).
2. Vorpruefung je Clip (Laenge <= --max-s): Vorschau in niedriger Aufloesung (<= 480p) laden, je --abstand s ein Bild.
3. Beweis, dass das Objekt zu sehen ist (nicht Titel/Bildbeschreibung): ALIKED+LightGlue-Zuordnungen (GPU, BSD-3/Apache 2) jedes Bildes gegen die Objektfotos
   (objekt.json fotos_dir, --ref beste N); Treffer = >= --min-inlier RANSAC-Inlier (Fundamentalmatrix) zu mindestens einem Objektfoto.
4. Ergebnis je Clip: Treffer-Bilder, Zeitabschnitte (Treffer zusammengefasst), Bildwinkel-Neuheit grob (Treffer zu verschiedenen Objektfotos).
Ausgabe --aus/video_kandidaten.json (sortiert nach Trefferzahl) + Kontaktabzug je Clip (Treffer gruen). LIZENZ: YouTube = nur private Messvorlage
(modelle/LIZENZ_WERKZEUGE.md); Vorschauen werden nach der Pruefung geloescht (nur Kandidatenliste bleibt).
  python3 tools/video_suchen.py modelle/<objekt>/objekt.json --aus <ordner> [--suchen 12] [--abstand 2] [--ref 12]
"""
import os, sys, json, glob, argparse, subprocess, time, shutil
import numpy as np, cv2

ZUSAETZE = ["drohne", "drone 4k", "aerial", "walk 4k", ""]
BILD_ENDUNGEN = (".jpg", ".jpeg", ".png")


def referenzfotos(obj, root):
    """EIGENE Objektfotos als Referenz (auch fuer tools/bilder_vorpruefen.py). Rueckgabe (sortierte Pfade, Ordner, Hinweis).
    17.11.2026 (Durchsicht), zwei stille Fehler: (1) `glob("*.jpg")` unterscheidet Gross-/Kleinschreibung - Kameras schreiben .JPG: 0 Referenzfotos, jede Pruefung
    'kein Treffer', rc 0 (kaufhaus_gk: 8 von 363 Bildern fehlten, martinstor_gk 7 von 243). (2) Nach dem ersten Kettenlauf zeigt objekt.json fotos_dir auf den SAMMELORDNER
    (eigene + Fremdbilder, tools/gesamtkette.py): die Referenz wurde quer durch alle Quellen gezogen (schwab_auto: 15 von 24 Referenzfotos waren Commons-/Videobilder) -
    Fremdbilder bestaetigten sich selbst. Jetzt: fotos_dir_quelle, wenn gesetzt und nicht leer; im Sammelordner nur die Bilder 'eigen__*', wenn es welche gibt."""
    def bilder(d): return sorted(os.path.join(d, f) for f in os.listdir(d) if f.lower().endswith(BILD_ENDUNGEN)) if os.path.isdir(d) else []
    absolut = lambda d: d if os.path.isabs(d) else os.path.join(root, d)
    fq = obj.get("fotos_dir_quelle")
    if fq and bilder(absolut(fq)): return bilder(absolut(fq)), absolut(fq), "fotos_dir_quelle (eigene Fotos vor dem Sammeln)"
    fd = absolut(obj.get("fotos_dir") or ""); alle = bilder(fd); eig = [p for p in alle if os.path.basename(p).startswith("eigen__")]
    if eig and len(eig) < len(alle): return eig, fd, f"nur eigen__* ({len(eig)} von {len(alle)} Bildern im Sammelordner)"
    return alle, fd, "fotos_dir"


DEV = None
_LG = {}


def _sift(n):
    """GPU-Merkmale ALIKED + LightGlue (BSD-3 / Apache-2.0, modelle/LIZENZ_WERKZEUGE.md). Lehre 2026-11-14: OpenCV-SIFT + BFMatcher lief auf
    18 CPU-Kernen bei GPU 0 % (Nutzerfrage); Kornia-SIFT auf GPU verlor Treffer (Positivkontrolle 113604: CPU 67 Inlier, Kornia 0)."""
    global DEV
    import torch
    from lightglue import LightGlue, ALIKED
    DEV = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if DEV.type != "cuda": print("WARNUNG: keine GPU - Merkmale laufen auf CPU", flush=True)
    if "m" not in _LG: _LG["m"] = LightGlue(features="aliked").eval().to(DEV)
    return ALIKED(max_num_keypoints=n).eval().to(DEV)


def _merkmale(s, grau):
    import torch
    t = torch.from_numpy(grau).to(DEV, torch.float32)[None, None].expand(1, 3, -1, -1) / 255.0
    with torch.inference_mode():
        f = s.extract(t)
    return f["keypoints"][0].cpu().numpy().astype(np.float32), f


def sift_ref(pfade, kante=1000):
    s = _sift(2048); R = []
    for p in pfade:
        im = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
        if im is None: continue
        f = kante / max(im.shape); im = cv2.resize(im, None, fx=min(1, f), fy=min(1, f), interpolation=cv2.INTER_AREA)
        P, d = _merkmale(s, im)
        if len(P) > 50: R.append((os.path.basename(p), P, d))
    return R


def treffer(bild, R, bf, s, min_inlier):
    """bf ungenutzt (Signatur gleich). LightGlue-Zuordnung auf der GPU, RANSAC (Fundamentalmatrix, 3 px) auf der CPU wie vorher."""
    import torch
    P, d = _merkmale(s, bild); best = (0, None)
    if len(P) < 50: return best
    for nm, Q, dq in R:
        with torch.inference_mode():
            m = _LG["m"]({"image0": d, "image1": dq})["matches"][0].cpu().numpy()
        if len(m) < min_inlier: continue
        F, msk = cv2.findFundamentalMat(P[m[:, 0]], Q[m[:, 1]], cv2.FM_RANSAC, 3.0, 0.999)
        n = int(msk.sum()) if msk is not None else 0
        if n > best[0]: best = (n, nm)
    return best


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--aus", required=True); ap.add_argument("--suchen", type=int, default=12)
    ap.add_argument("--abstand", type=float, default=2.0); ap.add_argument("--ref", type=int, default=12); ap.add_argument("--min-inlier", type=int, default=60)
    ap.add_argument("--max-s", type=int, default=1500); ap.add_argument("--anfragen", nargs="*"); ap.add_argument("--nur", nargs="*", help="nur diese Clip-IDs pruefen")
    a = ap.parse_args(argv); t0 = time.time(); os.makedirs(a.aus, exist_ok=True); op = os.path.abspath(a.objekt); obj = json.load(open(op))
    root = os.path.dirname(os.path.dirname(os.path.dirname(op)))
    name = obj.get("name", "").split("(")[0].strip(); ort = obj.get("ort", "").split(",")[0].strip()
    basis = a.anfragen or sorted({x for x in [name, f"{name} {ort}".strip()] + list((obj.get("bildquellen", {}).get("commons", {}) or {}).get("suchen", [])) if x})
    fotos, fd, woher = referenzfotos(obj, root)
    if obj.get("fotos"): fotos = [p for p in fotos if os.path.splitext(os.path.basename(p))[0] in obj["fotos"]] or fotos
    if not fotos: print(f"FEHLER: kein Objektfoto (.jpg/.jpeg/.png) in {fd} - ohne Referenz ist jede Clip-Pruefung 'kein Treffer'; nichts gesucht"); return 2      # 17.11.2026: lief mit 0 Referenzfotos durch (rc 0, alle Clips 0 Treffer)
    step = max(1, len(fotos) // a.ref); R = sift_ref(fotos[::step][:a.ref]); print(f"{len(R)} Objektfotos als Referenz aus {fd} [{woher}] ({time.time() - t0:.0f} s)", flush=True)
    if not R: print(f"FEHLER: keines der {len(fotos[::step][:a.ref])} Referenzfotos lesbar/mit Merkmalen - nichts gesucht"); return 2
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
        if not kand: print(f"FEHLER: Videosuche lieferte KEINEN Kandidaten (kein Netz? yt-dlp veraltet?) - letzte Meldung: {(r.stderr or '').strip()[-200:] if basis else 'keine Anfrage (objekt.json name/ort leer)'}"); return 3      # 17.11.2026: rc 0 mit leerer Kandidatenliste
    s = _sift(2048); bf = None; erg = []
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
    n_gepr = sum(1 for c in erg if c.get("status") == "geprueft" and c.get("bilder")); n_dl = sum(1 for c in erg if str(c.get("status", "")).startswith("Download fehlgeschlagen"))
    if erg and n_gepr == 0 and n_dl: print(f"FEHLER: KEIN Clip geprueft - {n_dl} von {len(erg)} Vorschau-Downloads fehlgeschlagen (video_kandidaten.json 'status')"); return 3      # 17.11.2026: alle Downloads gescheitert = rc 0, Liste ohne Treffer
    return 0


if __name__ == "__main__":
    sys.exit(main())
