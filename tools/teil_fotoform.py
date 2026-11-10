#!/usr/bin/env python3
"""teil_fotoform.py - FORMPRUEFUNG JE BAUTEIL GEGEN DIE EINZELFOTOS (Regel 9d b, L-KR24).

Warum (Nutzer-Sichtfunde 10.11.): Gauben (Dachueberstand, fehlende Wangenfenster) und Balkon (laeuft bis an Erker 2, in echt Ende + Ruecksprung)
waren falsch, ohne dass der Kreis es merkte: das Kantengitter hat an den Gauben 0 Punkte -> Guete = nur Wolkenbeleg; die Wolke sieht steile
Wangen nicht; Fehlteile kommen nur aus dem Gitter. Hier dagegen direkt am Foto, je Teil:

  1. foto_diff.py (Raster, GPU) je kalibriertem Foto mit Bewertungsmaske = ganzes Bild -> Kostenkarte: Modellkanten mkp, Fotokanten fkp und je Pixel
     der Abstand zur jeweils anderen Kantenart (dF, dM; Einheit = Kappe tol 0,35 m).
  2. Jedes Teil allein EXAKT gerastert (render_kern, GPU) und mit der Tiefe des ganzen Modells verglichen -> sichtbare Pixel des Teils (verdeckt = nicht).
  3. Im sichtbaren Teilbereich: Praezision = Anteil Modellkantenpixel mit Fotokante naeher als --schwelle x Kappe (rot = erfundene Form),
     Recall = Anteil Fotokantenpixel mit Modellkante naeher als --schwelle x Kappe (gelb = fehlende Form, z. B. Fenster in einer Wange).
  4. Brennpunkte: zusammenhaengende rote/gelbe Flecken im Teilbereich, mit Weltpunkt (Rasterposition) -> wo genau.

Aufruf: /media/oem/scan/venv-seg/bin/python -W ignore -I tools/teil_fotoform.py <objekt> [--teile_dir D] [--fotos 6120,6161] [--aus bericht.json] [--bilder]
Ohne --teile_dir werden die Teile mit dem Generator (BAUTEILE_AUS) in einen Zeitordner exportiert.
"""
import sys, os, json, glob, argparse, tempfile, subprocess, numpy as np, cv2, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import foto_diff as FD, fehlteile_finden as FF, render_kern as RK

R0 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def rahmen(stl, obj, kk):
    """Gleiche Verschiebung wie foto_diff._netz_raster (aus dem GANZEN Modell), damit Teile im Kamerarahmen liegen."""
    m = trimesh.load(stl, force="mesh"); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0)
    c = m.bounds.mean(0) if obj.get("zentrierung", "huelle") == "huelle" else np.zeros(3)
    return np.asarray(kk["rahmen_verschiebung"] if "rahmen_verschiebung" in kk else [-c[0], -c[1], -m.bounds[0, 2]], float)


def flecken(maske, pos, n=3, min_px=40):
    """Groesste zusammenhaengende Flecken (nach 5-px-Schliessen) mit Pixelzahl und Weltpunkt (Median der Rasterpositionen)."""
    if maske.sum() < min_px: return []
    mm = cv2.dilate(maske.astype(np.uint8), np.ones((5, 5), np.uint8))
    k, lab, st, _ = cv2.connectedComponentsWithStats(mm, 8)
    out = []
    for i in np.argsort(-st[1:, cv2.CC_STAT_AREA])[:n] + 1:
        sel = (lab == i) & maske
        if sel.sum() < min_px: continue
        p = pos[sel]; p = p[np.isfinite(p).all(1)]
        out.append({"px": int(sel.sum()), "xyz": np.round(np.median(p, 0), 2).tolist() if len(p) else None,
                    "bbox_px": [int(st[i, 0]), int(st[i, 1]), int(st[i, 2]), int(st[i, 3])]})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--teile_dir"); ap.add_argument("--fotos")
    ap.add_argument("--stl"); ap.add_argument("--schwelle", type=float, default=0.4, help="Anteil der Kappe (0,35 m): 0,4 = 0,14 m")
    ap.add_argument("--min_px", type=int, default=150, help="Mindestzahl Kantenpixel je Teil und Foto, sonst nicht beurteilbar")
    ap.add_argument("--aus"); ap.add_argument("--bilder", action="store_true", help="je Teil+Foto Ausschnitt mit gruen/rot/gelb nach audit/teil_fotoform/")
    ap.add_argument("--nur", help="nur diese Teile (Komma), z. B. das Kreis-Ziel"); ap.add_argument("--etikett", default="", help="Zusatz im Bildnamen (vorher/nachher)")
    ap.add_argument("--bilder_dir", help="Bilder hierhin statt modelle/<objekt>/audit/teil_fotoform (Kreis: Datenplatte, nicht ins Repo)")
    a = ap.parse_args(argv)
    objp = os.path.join(R0, "modelle", a.objekt, "objekt.json"); obj = json.load(open(objp))
    stl = a.stl or os.path.join(R0, obj["stl"])
    td = a.teile_dir
    if not td:
        td = tempfile.mkdtemp(prefix="tff_")
        subprocess.run(obj["generator"], shell=True, cwd=R0, env=dict(os.environ, BAUTEILE_AUS=td), check=True, capture_output=True)
    teile = sorted(glob.glob(os.path.join(td, "*.stl")))
    if a.nur: teile = [p for p in teile if os.path.basename(p)[:-4] in a.nur.split(",")]   # Kreis-Tor: nur das Ziel-Teil (Verdeckung trotzdem gegen das ganze Modell)
    fotos = a.fotos.split(",") if a.fotos else sorted(os.path.basename(p)[2:-5] for p in glob.glob(os.path.join(os.path.dirname(objp), "messprotokoll", "K-*.json")))
    bd = a.bilder_dir or os.path.join(os.path.dirname(objp), "audit", "teil_fotoform"); os.makedirs(bd, exist_ok=True)
    import hashlib
    erg = {"objekt": a.objekt, "stl_sha": hashlib.sha256(open(stl, "rb").read()).hexdigest()[:16], "bilder_dir": bd, "schwelle_m": round(a.schwelle * 0.35, 3), "fotos": {}, "teile": {}}
    tmp = tempfile.mkdtemp(prefix="tff_k_")
    TM = {}
    for nr in fotos:
        kp = FF.k_datei(objp, obj, R0, nr)
        if not kp: continue
        K = json.load(open(kp)); kk = K["kamera"]
        bild = glob.glob(os.path.join(R0, obj["fotos_dir"], nr + "_*"))
        if not bild: continue
        im0 = cv2.imread(bild[0]); H, W = im0.shape[:2]
        voll = os.path.join(tmp, f"voll_{W}x{H}.png"); cv2.imwrite(voll, np.full((H, W), 255, np.uint8)) if not os.path.exists(voll) else None
        npz = os.path.join(tmp, f"k_{nr}.npz")
        try:
            FD.main([objp, nr, "--stl", stl, "--bewertung-maske", voll, "--kostenkarte", npz, "--aus", tmp])
        except BaseException as ex:
            erg["fotos"][nr] = f"foto_diff fehlgeschlagen: {str(ex)[:120]}"; continue
        if not os.path.exists(npz): erg["fotos"][nr] = "keine Kostenkarte (zu wenig Kanten)"; continue
        Z = np.load(npz); mkp, fkp, dF, dM = Z["mkp"], Z["fkp"], Z["dF"].astype(np.float32), Z["dM"].astype(np.float32)
        R, t, f, _, _ = FF.kamera_laden(K, obj, nr, R0, W, H); cx, cy = float(kk.get("cx", W / 2)), float(kk.get("cy", H / 2))
        tr = rahmen(stl, obj, kk)
        mv = trimesh.load(stl, force="mesh"); mv.apply_scale(obj.get("stl_massstab", 87) / 1000.0); mv.apply_translation(tr)
        dv, _, pos = RK.dreiecke_rastern(mv, R, t, f, cx, cy, W, H)
        erg["fotos"][nr] = {"mk_px": int(mkp.sum()), "fk_px": int(fkp.sum())}
        for tp in teile:
            name = os.path.basename(tp)[:-4]
            if name not in TM:
                m = trimesh.load(tp, force="mesh")
                if not isinstance(m, trimesh.Trimesh) or len(m.faces) == 0: TM[name] = None; continue
                m.apply_scale(obj.get("stl_massstab", 87) / 1000.0); TM[name] = m
            if TM[name] is None: continue
            m = TM[name].copy(); m.apply_translation(tr)
            dp, _, _ = RK.dreiecke_rastern(m, R, t, f, cx, cy, W, H)
            vis = np.isfinite(dp) & (dp <= dv * 1.003 + 0.03)
            if vis.sum() < 200: continue
            ms = cv2.dilate(vis.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
            mk_t, fk_t = mkp & ms, fkp & ms
            if mk_t.sum() < a.min_px or fk_t.sum() < a.min_px: continue
            ok_m, ok_f = dF[mk_t] < a.schwelle, dM[fk_t] < a.schwelle
            rot = mk_t & (dF >= a.schwelle); gelb = fk_t & (dM >= a.schwelle)
            e = {"praez": round(float(ok_m.mean()), 3), "recall": round(float(ok_f.mean()), 3), "mk_px": int(mk_t.sum()), "fk_px": int(fk_t.sum()),
                 "rot": flecken(rot, pos), "gelb": flecken(gelb, pos)}
            erg["teile"].setdefault(name, {})[nr] = e
            if a.bilder:
                ys, xs = np.where(ms); y0, y1, x0, x1 = max(0, ys.min() - 40), min(H, ys.max() + 40), max(0, xs.min() - 40), min(W, xs.max() + 40)
                ov = (im0 // 2).copy(); ov[ms & ~(mk_t | fk_t)] = (ov[ms & ~(mk_t | fk_t)] * 1.6).clip(0, 255).astype(np.uint8)
                ov[mk_t & ~rot] = (0, 200, 0); ov[fk_t & ~gelb & ~mk_t] = (200, 120, 0); ov[rot] = (0, 0, 255); ov[gelb] = (0, 255, 255)
                cv2.imwrite(os.path.join(bd, f"{name}_{nr}{('_' + a.etikett) if a.etikett else ''}.jpg"), ov[y0:y1, x0:x1], [cv2.IMWRITE_JPEG_QUALITY, 85])
        print(f"Foto {nr}: {sum(1 for v in erg['teile'].values() if nr in v)} Teile beurteilt", flush=True)
    for name, je in erg["teile"].items():   # Mittel ueber Fotos, gewichtet mit Pixelzahl
        mk = sum(v["mk_px"] for v in je.values()); fk = sum(v["fk_px"] for v in je.values())
        p = sum(v["praez"] * v["mk_px"] for v in je.values()) / mk; r = sum(v["recall"] * v["fk_px"] for v in je.values()) / fk
        je["_gesamt"] = {"praez": round(p, 3), "recall": round(r, 3), "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0, "fotos": len(je)}
    if a.aus: json.dump(erg, open(a.aus, "w"), ensure_ascii=False, indent=1)
    print(f"{'Teil':30s} {'Fotos':>5s} {'Praez':>6s} {'Recall':>6s} {'F1':>6s}")
    for name, je in sorted(erg["teile"].items(), key=lambda kv: kv[1]["_gesamt"]["f1"]):
        g = je["_gesamt"]; print(f"{name:30s} {g['fotos']:5d} {g['praez']:6.3f} {g['recall']:6.3f} {g['f1']:6.3f}")
    return erg


if __name__ == "__main__":
    main()
