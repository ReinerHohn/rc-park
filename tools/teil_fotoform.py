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
import sys, os, json, glob, argparse, tempfile, subprocess, time, numpy as np, cv2, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import foto_diff as FD, fehlteile_finden as FF, render_kern as RK

R0 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def rahmen(stl, obj, kk):
    """Gleiche Verschiebung wie foto_diff._netz_raster (aus dem GANZEN Modell), damit Teile im Kamerarahmen liegen."""
    m = trimesh.load(stl, force="mesh"); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0)
    c = m.bounds.mean(0) if obj.get("zentrierung", "huelle") == "huelle" else np.zeros(3)
    return np.asarray(kk["rahmen_verschiebung"] if "rahmen_verschiebung" in kk else [-c[0], -c[1], -m.bounds[0, 2]], float)


def waagerecht(maske, winkel=30.0):
    """Kantenpixel, deren Kantenrichtung im Bild hoechstens `winkel` Grad von waagerecht abweicht (Strukturtensor der geglaetteten Kantenmaske).
    HOEHEN-WERT (Nutzer 10.11. abends, Positivtest Helm O: 0,3 m nach oben -> Foto-F1 nur -0,010, seitlich -0,093): steile Kanten gleiten bei
    Hoehenfehlern an sich selbst entlang und bleiben 'Treffer'; nur waagerechte Kanten verraten die Hoehe - getrennt zaehlen, sonst gehen sie unter.
    ANNAHME: Bild-waagerecht ~ Welt-waagerecht (Fotos kaum gerollt, Rahmen lot2)."""
    m = cv2.GaussianBlur(maske.astype(np.float32), (0, 0), 2)
    gx = cv2.Sobel(m, cv2.CV_32F, 1, 0, ksize=3); gy = cv2.Sobel(m, cv2.CV_32F, 0, 1, ksize=3)
    jxx = cv2.GaussianBlur(gx * gx, (0, 0), 3); jyy = cv2.GaussianBlur(gy * gy, (0, 0), 3); jxy = cv2.GaussianBlur(gx * gy, (0, 0), 3)
    th = 0.5 * np.arctan2(2 * jxy, jxx - jyy)          # Gradientenrichtung; waagerechte Kante = senkrechter Gradient
    return maske & (np.abs(np.cos(th)) < np.sin(np.radians(winkel)))


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
    import hashlib, time
    erg = {"objekt": a.objekt, "stl_sha": hashlib.sha256(open(stl, "rb").read()).hexdigest()[:16], "bilder_dir": bd, "schwelle_m": round(a.schwelle * 0.35, 3), "fotos": {}, "teile": {}}
    _td = "/media/oem/scan/rc-park_tmp" if os.path.isdir("/media/oem/scan") else None   # nie Root-Platte (10.11.: 76 Reste = 4,1 GB in /tmp, Root 5 GB)
    if _td: os.makedirs(_td, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="tff_k_", dir=_td)
    import atexit, shutil as _sh; atexit.register(_sh.rmtree, tmp, True)   # auch bei Abbruch per Ausnahme aufraeumen
    TM = {}
    def foto_bewerten(nr):
            kp = FF.k_datei(objp, obj, R0, nr)
            if not kp: return
            K = json.load(open(kp)); kk = K["kamera"]
            bild = glob.glob(os.path.join(R0, obj["fotos_dir"], nr + "_*"))
            if not bild: return
            im0 = cv2.imread(bild[0]); H, W = im0.shape[:2]
            voll = os.path.join(tmp, f"voll_{W}x{H}.png"); cv2.imwrite(voll, np.full((H, W), 255, np.uint8)) if not os.path.exists(voll) else None
            npz = os.path.join(tmp, f"k_{nr}.npz")
            # SCHNELLWEG (10.11. abends, bitgleich geprueft - TFF_LANGSAM=1 = alter Weg, TFF_PRUEF=1 = beide Wege vergleichen): foto_diff gibt Raster und
            # Kostenkarte im Speicher zurueck und hoert nach der Kostenkarte auf (Bericht/Bilder/zweites Vollraster/npz entfallen).
            schnell = os.environ.get("TFF_LANGSAM") != "1"
            FD._RUECK = {"nur_kosten": os.environ.get("TFF_PRUEF") != "1"} if schnell else None
            try:
                FD.main([objp, nr, "--stl", stl, "--bewertung-maske", voll, "--kostenkarte", npz, "--aus", tmp])
            except BaseException as ex:
                if 'out of memory' in str(ex).lower(): raise
                erg["fotos"][nr] = f"foto_diff fehlgeschlagen: {str(ex)[:120]}"; return
            finally:
                rueck, FD._RUECK = FD._RUECK, None
            if schnell and rueck and "kosten" in rueck:
                Z = rueck["kosten"]
            elif os.path.exists(npz): Z = np.load(npz)
            else: erg["fotos"][nr] = "keine Kostenkarte (zu wenig Kanten)"; return
            mkp, fkp, dF, dM = Z["mkp"], Z["fkp"], Z["dF"].astype(np.float32), Z["dM"].astype(np.float32)
            # Hoehen-Wert: Abstaende nur zwischen WAAGERECHTEN Kanten, gleiche Einheit wie dF (Kappe in Pixeln aus dF zurueckgerechnet)
            _dtF = cv2.distanceTransform((~fkp).astype(np.uint8), cv2.DIST_L2, 5); _s = (dF > 0.05) & (dF < 0.95) & mkp
            kap = float(np.median(_dtF[_s] / dF[_s])) if _s.sum() > 20 else None
            if kap:
                mkh, fkh = waagerecht(mkp), waagerecht(fkp)
                dFh = np.minimum(cv2.distanceTransform((~fkh).astype(np.uint8), cv2.DIST_L2, 5), kap) / kap
                dMh = np.minimum(cv2.distanceTransform((~mkh).astype(np.uint8), cv2.DIST_L2, 5), kap) / kap
            R, t, f, _, _ = FF.kamera_laden(K, obj, nr, R0, W, H); cx, cy = float(kk.get("cx", W / 2)), float(kk.get("cy", H / 2))
            tr = rahmen(stl, obj, kk)
            if schnell and rueck and "depth" in rueck and os.environ.get("TFF_PRUEF") != "1":
                dv, pos = rueck["depth"], rueck["pos"].cpu().numpy()   # Vollraster aus foto_diff (gleiches Netz, gleiche Kamera) statt zweitem Raster
            else:
                mv = trimesh.load(stl, force="mesh"); mv.apply_scale(obj.get("stl_massstab", 87) / 1000.0); mv.apply_translation(tr)
                dv, _, pos = RK.dreiecke_rastern(mv, R, t, f, cx, cy, W, H)
                if schnell and rueck and "depth" in rueck:   # TFF_PRUEF: Schnellweg muss bitgleich sein
                    print(f"PRUEF {nr}: depth gleich {np.array_equal(dv, rueck['depth'], equal_nan=True)}, pos gleich {np.array_equal(pos, rueck['pos'].cpu().numpy(), equal_nan=True)}", flush=True)
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
                if kap:
                    mh_t, fh_t = mkh & ms, fkh & ms
                    hw = {"praez_h": round(float((dFh[mh_t] < a.schwelle).mean()), 3), "recall_h": round(float((dMh[fh_t] < a.schwelle).mean()), 3),
                          "mkh_px": int(mh_t.sum()), "fkh_px": int(fh_t.sum())} if (mh_t.sum() >= 50 and fh_t.sum() >= 50) else {}
                else: hw = {}
                e = {**hw, "praez": round(float(ok_m.mean()), 3), "recall": round(float(ok_f.mean()), 3), "mk_px": int(mk_t.sum()), "fk_px": int(fk_t.sum()),
                     "rot": flecken(rot, pos), "gelb": flecken(gelb, pos)}
                erg["teile"].setdefault(name, {})[nr] = e
                if a.bilder:
                    ys, xs = np.where(ms); y0, y1, x0, x1 = max(0, ys.min() - 40), min(H, ys.max() + 40), max(0, xs.min() - 40), min(W, xs.max() + 40)
                    ov = (im0 // 2).copy(); ov[ms & ~(mk_t | fk_t)] = (ov[ms & ~(mk_t | fk_t)] * 1.6).clip(0, 255).astype(np.uint8)
                    ov[mk_t & ~rot] = (0, 200, 0); ov[fk_t & ~gelb & ~mk_t] = (200, 120, 0); ov[rot] = (0, 0, 255); ov[gelb] = (0, 255, 255)
                    cv2.imwrite(os.path.join(bd, f"{name}_{nr}{('_' + a.etikett) if a.etikett else ''}.jpg"), ov[y0:y1, x0:x1], [cv2.IMWRITE_JPEG_QUALITY, 85])
    TEIL = (a.aus + ".teil") if a.aus else None
    if TEIL and os.path.exists(TEIL):   # Wiederaufnahme: abgebrochener Lauf zum selben STL
        try:
            alt = json.load(open(TEIL))
            if alt.get("stl_sha") == erg["stl_sha"]: erg["fotos"], erg["teile"] = alt["fotos"], alt["teile"]; print("Wiederaufnahme:", sum(isinstance(v, dict) for v in alt["fotos"].values()), "Fotos fertig", flush=True)
        except Exception: pass
    import torch
    for nr in fotos:
        if isinstance(erg["fotos"].get(nr), dict): continue
        for versuch in range(12):   # 10.11.: GPU-Speicher voll durch 8 Kreis-Spuren -> Abbruch nach 38 min; jetzt warten und Foto wiederholen
            try: foto_bewerten(nr); break
            except (torch.OutOfMemoryError, RuntimeError) as ex:
                if "out of memory" not in str(ex).lower(): raise
                for v in erg["teile"].values(): v.pop(nr, None)
                erg["fotos"].pop(nr, None); torch.cuda.empty_cache(); print(f"Foto {nr}: GPU-Speicher voll, Versuch {versuch + 1}, warte 60 s", flush=True); time.sleep(60)
        else: erg["fotos"][nr] = "GPU-Speicher dauerhaft voll"
        print(f"Foto {nr}: {sum(1 for v in erg['teile'].values() if nr in v)} Teile beurteilt", flush=True)
        if TEIL: json.dump(erg, open(TEIL, "w"), ensure_ascii=False)   # Zwischenstand je Foto (11:56 brach ein 38-min-Lauf am Ende ab, alles verloren)
    for name, je in erg["teile"].items():   # Mittel ueber Fotos, gewichtet mit Pixelzahl
        je = {k: v for k, v in je.items() if isinstance(v, dict) and "mk_px" in v}; erg["teile"][name] = je
        mk = sum(v["mk_px"] for v in je.values()); fk = sum(v["fk_px"] for v in je.values())
        if not mk or not fk: continue
        p = sum(v["praez"] * v["mk_px"] for v in je.values()) / mk; r = sum(v["recall"] * v["fk_px"] for v in je.values()) / fk
        je["_gesamt"] = {"praez": round(p, 3), "recall": round(r, 3), "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0, "fotos": len(je)}
        hh = [v for v in je.values() if isinstance(v, dict) and "mkh_px" in v]   # Hoehen-Wert (waagerechte Kanten), gleiche Gewichtung
        mh = sum(v["mkh_px"] for v in hh); fh = sum(v["fkh_px"] for v in hh)
        if mh and fh:
            ph = sum(v["praez_h"] * v["mkh_px"] for v in hh) / mh; rh = sum(v["recall_h"] * v["fkh_px"] for v in hh) / fh
            je["_gesamt"].update({"praez_h": round(ph, 3), "recall_h": round(rh, 3), "f1_h": round(2 * ph * rh / (ph + rh), 3) if ph + rh else 0.0, "fotos_h": len(hh)})
    if a.aus: json.dump(erg, open(a.aus, "w"), ensure_ascii=False, indent=1)
    print(f"{'Teil':30s} {'Fotos':>5s} {'Praez':>6s} {'Recall':>6s} {'F1':>6s}")
    for name, je in sorted(((k, v) for k, v in erg["teile"].items() if "_gesamt" in v), key=lambda kv: kv[1]["_gesamt"]["f1"]):
        g = je["_gesamt"]; print(f"{name:30s} {g['fotos']:5d} {g['praez']:6.3f} {g['recall']:6.3f} {g['f1']:6.3f}")
    return erg


if __name__ == "__main__":
    import gpu_slot; gpu_slot.belegen("teil_fotoform")   # gemeinsame GPU-Schlange (10.11.: >2-3 gleichzeitige GPU-Pruefungen = Einbruch)
    main()
