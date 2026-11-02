#!/usr/bin/env python3
"""massstab_quelle_lod2.py - Massstabsquelle 'LoD2-Nachbargebaeude als Hoehenschwarm' (vertikal).

Idee: Jedes Gebaeude der Umgebung hat amtliche Traufhoehen (LoD2, ca. +-0,5 m). Die Traufkanten (obere Waagerechte der LoD2-Waende) werden mit der
Kamera des Fotos ins Bild projiziert, an die staerkste Bildkante in der Naehe angedockt (Gradient senkrecht zur Kante, Median ueber Stuetzpunkte,
Konsistenzpruefung) und die gemessene Pixelkante als Strahl mit der Wandebene geschnitten -> gemessene Traufhoehe im Modell. s = h_LoD2 / h_gemessen
(h = Hoehe ueber dem Gebaeudefuss laut LoD2; 1.0 = Modellmeter sind wahre Meter). Aggregation Median + MAD ueber alle Kanten/Fotos.

Kameras: SfM-Posen aus messprotokoll/SFM-AUSRICHTUNG-<seite>.json['kameras'] (X_cam = R X + t, f = f_px_original * fak, Bild verkleinert um fak).
ABHAENGIGKEIT (ehrlich): Die Posen sind ueber Bodenanker ins Modell gebracht; die Quelle prueft die vertikale Metrik an Gebaeuden in 8-25 m Hoehe
(nicht den Turm), ist aber NICHT unabhaengig von den Bodenankern (gleicher Massstab fuer die Kamerahoehe). Sie ist unabhaengig von DOM1, Fotohoehen am Turm,
Dokumenten und Normmassen.

  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/massstab_quelle_lod2.py modelle/martinstor_null/objekt.json [--gml-dir /media/oem/scan/tmp/mt_lod2] [--radius 120]
Ausgabe: <objekt>/audit/massstab_lod2.json, Kurztabelle auf stdout, Kontrollbilder <objekt>/audit/massstab_lod2_<foto>.jpg
"""
import sys, os, json, glob, argparse, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--gml-dir", default="/media/oem/scan/tmp/mt_lod2"); ap.add_argument("--radius", type=float, default=120.0)
    ap.add_argument("--seite", default="nord"); ap.add_argument("--suchband", type=int, default=40, help="Suchband +-px senkrecht zur Kante (Originalbild)")
    ap.add_argument("--min-laenge", type=float, default=4.0, help="Mindestlaenge Traufkante (m)"); ap.add_argument("--min-px", type=float, default=80.0, help="Mindestlaenge im Bild (px, Original)")
    ap.add_argument("--konsistenz", type=float, default=0.6); ap.add_argument("--bilder", type=int, default=3)
    a = ap.parse_args(); import cv2; import lod2_gebaeude as LG
    obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); repo = os.path.dirname(os.path.dirname(od)); os.makedirs(os.path.join(od, "audit"), exist_ok=True)
    A = json.load(open(os.path.join(od, "anker3d.json"))); mitte = np.array(A["mitte_utm"]); xh = np.array(A["xhat_utm"]); yh = np.array(A["yhat_utm"]); gel = float(A["gelaende"])
    AL = json.load(open(os.path.join(od, "messprotokoll", f"SFM-AUSRICHTUNG-{a.seite}.json"))); cams = AL["kameras"]
    def modell(P): d = P[:, :2] - mitte; return np.c_[d @ xh, d @ yh, P[:, 2] - gel]
    geb = []
    for g in sorted(glob.glob(os.path.join(a.gml_dir, "**", "*.gml"), recursive=True)):
        for meta, polys in LG.extract(g, center=tuple(mitte), radius=a.radius):
            if meta["id"] in {x["id"] for x in geb}: continue
            gz = meta.get("ground_z"); walls = []
            for typ, P in polys:
                if typ != "WallSurface": continue
                V = modell(P); zt = V[:, 2].max(); top = V[V[:, 2] > zt - 0.05]
                if len(top) < 2: continue
                # die zwei am weitesten entfernten Punkte der Oberkante
                D = np.linalg.norm(top[:, None, :2] - top[None, :, :2], axis=2); i, j = np.unravel_index(np.argmax(D), D.shape); p0, p1 = top[i], top[j]
                L = float(np.linalg.norm(p1[:2] - p0[:2]))
                if L < a.min_laenge: continue
                n = np.cross(V[1] - V[0], V[2] - V[0]) if len(V) >= 3 else np.zeros(3)
                if np.linalg.norm(n) < 1e-6 or abs(n[2]) / np.linalg.norm(n) > 0.3: continue            # nur (fast) senkrechte Waende
                walls.append(dict(p0=p0, p1=p1, laenge=L, n=n / np.linalg.norm(n), ztop=float(zt), zfuss=float(V[:, 2].min())))
            ist_turm = bool(walls) and min(float(np.linalg.norm(((w_['p0'] + w_['p1']) / 2)[:2])) for w_ in walls) < 8.0         # Wand nahe der Turmmitte = das Objekt selbst
            if walls: geb.append(dict(id=meta["id"], name=meta.get("name") or "", walls=walls, turm=ist_turm, ground=float(gz - gel) if gz is not None else None))
    print(f"{len(geb)} LoD2-Gebaeude mit {sum(len(g['walls']) for g in geb)} Traufwaenden im Umkreis {a.radius:.0f} m", flush=True)
    schaetz = []; verworfen = {}; bilder = 0
    def verwirf(grund): verworfen[grund] = verworfen.get(grund, 0) + 1
    for fid, k in sorted(cams.items()):
        fn = glob.glob(os.path.join(repo, obj["fotos_dir"], fid + "_*"))
        if not fn: continue
        im = cv2.imread(fn[0], cv2.IMREAD_GRAYSCALE)
        if im is None: continue
        H, Wd = im.shape; fak = k["fak"]; R = np.array(k["R"]); t = np.array(k["t"]); f = k["f_px_original"] * fak; cx, cy = k["cx"], k["cy"]; cen = -R.T @ t
        sc = 1.0 / fak                                                                   # Pixel verkleinertes Bild -> Original
        gb = cv2.GaussianBlur(im, (0, 0), 2.0); gy = cv2.Sobel(gb.astype(np.float32), cv2.CV_32F, 0, 1, ksize=3)
        def proj(X): Xc = X @ R.T + t; return np.c_[(f * Xc[:, 0] / Xc[:, 2] + cx) * sc, (f * Xc[:, 1] / Xc[:, 2] + cy) * sc], Xc[:, 2]
        vis = cv2.cvtColor(im, cv2.COLOR_GRAY2BGR) if bilder < a.bilder else None; n_f = 0
        for g in geb:
            for w in g["walls"]:
                nn = w["n"]; mid3 = (w["p0"] + w["p1"]) / 2
                if abs(np.dot(nn, cen - mid3)) < 1.0: continue                                  # Kamera in der Wandebene: Schnitt unbestimmt
                P = np.array([w["p0"], w["p1"]]); uv, z = proj(P)
                if (z <= 3).any(): verwirf("hinter_kamera"); continue
                if np.linalg.norm(cen[:2] - mid3[:2]) > a.radius * 1.2: continue
                # Sichtbarkeit grob: Kante ganz im Bild, Mindestlaenge
                if (uv[:, 0] < 5).any() or (uv[:, 0] > Wd - 5).any() or (uv[:, 1] < a.suchband + 5).any() or (uv[:, 1] > H - a.suchband - 5).any(): verwirf("nicht_im_bild"); continue
                if np.linalg.norm(uv[1] - uv[0]) < a.min_px: verwirf("zu_kurz_im_bild"); continue
                # Verdeckung grob: ein anderer Wandabschnitt (anderes Gebaeude) schneidet den Sehstrahl zur Kantenmitte vor der Kante
                verd = False
                for g2 in geb:
                    for w2 in g2["walls"]:
                        if w2 is w: continue
                        n2 = w2["n"]; dn = np.dot(n2, mid3 - cen)
                        if abs(dn) < 1e-6: continue
                        s_ = np.dot(n2, w2["p0"] - cen) / dn
                        if not (0.02 < s_ < 0.97): continue
                        Q = cen + s_ * (mid3 - cen); e = w2["p1"] - w2["p0"]; Le = np.linalg.norm(e[:2])
                        tpar = np.dot(Q[:2] - w2["p0"][:2], e[:2]) / (Le ** 2)
                        if 0 <= tpar <= 1 and w2["zfuss"] - 0.5 <= Q[2] <= w2["ztop"] + 0.2: verd = True; break
                    if verd: break
                if verd: verwirf("verdeckt"); continue
                # Andocken: Stuetzpunkte entlang der Kante, Suchprofil senkrecht (vertikal im Bild; Kanten nahezu waagerecht)
                d = uv[1] - uv[0]; ang = np.degrees(np.arctan2(d[1], d[0]))
                if abs(abs(ang) - 180) > 35 and abs(ang) > 35: verwirf("kante_zu_steil_im_bild"); continue
                ns = max(8, int(np.linalg.norm(d) / 15)); ts = np.linspace(0.05, 0.95, ns); offs = []
                for tt in ts:
                    u, v = uv[0] + tt * d; ui = int(round(u)); vi = int(round(v))
                    if not (0 <= ui < Wd) or vi - a.suchband < 0 or vi + a.suchband >= H: continue
                    prof = np.abs(gy[vi - a.suchband:vi + a.suchband + 1, ui]); j = int(np.argmax(prof))
                    if prof[j] < 8.0 or j in (0, len(prof) - 1): continue
                    offs.append(j - a.suchband)
                if len(offs) < max(5, 0.5 * ns): verwirf("kein_gradient"); continue
                offs = np.array(offs, float); md = float(np.median(offs)); kons = float(np.mean(np.abs(offs - md) <= 3.0))
                if kons < a.konsistenz: verwirf("inkonsistent"); continue
                # gemessene Kante: Mittelpunkt + vertikaler Versatz md -> Strahl -> Schnitt mit Wandebene
                um, vm = (uv[0] + uv[1]) / 2; vm_m = vm + md
                ray_c = np.array([(um / sc - cx) / f, (vm_m / sc - cy) / f, 1.0]); ray_w = R.T @ ray_c; ray_w /= np.linalg.norm(ray_w)
                den = np.dot(nn, ray_w)
                if abs(den) < 0.1: verwirf("streifender_schnitt"); continue
                lam = np.dot(nn, w["p0"] - cen) / den
                if lam <= 0: verwirf("schnitt_hinter_kamera"); continue
                Xm = cen + lam * ray_w
                if np.linalg.norm(Xm[:2] - mid3[:2]) > w["laenge"] + 2: verwirf("schnitt_ausserhalb"); continue
                fuss = g["ground"] if g["ground"] is not None else w["zfuss"]
                h_lod = w["ztop"] - fuss; h_mes = Xm[2] - fuss
                if h_mes < 2.0: verwirf("gemessene_hoehe_unplausibel"); continue
                s = h_lod / h_mes
                # Pixelabweichung als Hoehenfehler: dz/dv ~ Entfernung / f / cos
                dz_px = float(np.linalg.norm(Xm - cen)) / (f * sc) * 2.0                         # 2 px Andockunsicherheit
                sig = float(np.sqrt(0.5 ** 2 + dz_px ** 2) / h_lod * s)
                schaetz.append(dict(id=f"{fid}:{g['id'][-8:]}:{len(schaetz)}", foto=fid, ist_turm=g["turm"], gebaeude=g["id"], wert_s=round(float(s), 4), sigma=round(sig, 4), h_lod_m=round(h_lod, 2), h_gemessen_m=round(float(h_mes), 2),
                                    versatz_px=round(md, 1), konsistenz=round(kons, 2), entfernung_m=round(float(np.linalg.norm(Xm - cen)), 1),
                                    beleg=f"LoD2 Traufkante {g['id']} (Wand {w['laenge']:.1f} m, z {w['ztop']:.2f} m), Foto {fid}, Andocken Gradient (Versatz {md:+.0f} px, Konsistenz {kons:.0%})"))
                n_f += 1
                if vis is not None:
                    cv2.line(vis, tuple(int(x) for x in uv[0]), tuple(int(x) for x in uv[1]), (0, 0, 255), 3)
                    cv2.line(vis, (int(uv[0][0]), int(uv[0][1] + md)), (int(uv[1][0]), int(uv[1][1] + md)), (0, 255, 0), 3)
                    cv2.putText(vis, f"s {s:.2f}", (int(um), int(vm + md) - 10), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 255, 255), 3)
        if vis is not None and n_f:
            sc2 = 1400.0 / max(vis.shape); cv2.imwrite(os.path.join(od, "audit", f"massstab_lod2_{fid}.jpg"), cv2.resize(vis, None, fx=sc2, fy=sc2), [cv2.IMWRITE_JPEG_QUALITY, 85]); bilder += 1
        print(f"  Foto {fid}: {n_f} Traufkanten angedockt", flush=True)
    nb = [x for x in schaetz if not x["ist_turm"]]; tm = [x for x in schaetz if x["ist_turm"]]
    def stat(l): v = np.array([x["wert_s"] for x in l]); m = float(np.median(v)) if len(v) else None; return m, (float(np.median(np.abs(v - m))) if len(v) else None), v
    md, mad, s_ = stat(nb); md_t, mad_t, s_t = stat(tm)       # Kennzahl = NUR Nachbarn; der Turm selbst ist das Objekt (Wandoberkante = generalisierter Anker ecke_wandoben), nur zum Vergleich
    out = dict(quelle="LoD2-Nachbargebaeude Traufkanten (LGL LoD2) + SfM-Kameras + Bildkanten-Andocken", richtung="vertikal",
               unabhaengig_von=["DOM1", "Fotohoehen am Turm", "Dokumente (60/65 m)", "Normmasse"], abhaengig_von=["Bodenanker (Kameraposen/Kamerahoehe ueber Massstab der Ausrichtung)", "LoD2-Hoehen der Nachbarn (+-0,5 m, generalisiert)"],
               s_definition="wahre Meter / Modellmeter, 1.0 = konsistent (h_LoD2 / h_gemessen ueber Gebaeudefuss)", schaetzungen=schaetz, n=len(nb), median=md, mad=mad, turm_selbst=dict(n=len(tm), median=md_t, mad=mad_t, hinweis="Turm-Wandoberkante LoD2 37,0 m ist generalisiert/mehrdeutig (Galeriegesims, Register AR); nicht in der Kennzahl"),
               n_fotos=len({x["foto"] for x in nb}), n_gebaeude=len({x["gebaeude"] for x in nb}), verworfen=verworfen,
               annahmen=["ANNAHME: LoD2-Traufkante (obere Waagerechte der LoD2-Wand) = sichtbare Dachkante im Foto (Dachueberstand und Generalisierung bis ca. 0,5 m)",
                         "ANNAHME: Gebaeudefuss = LoD2-GroundSurface-Minimum, Gelaendemodell der Nachbarn bis ca. 0,5 m genau",
                         "ANNAHME: Andockunsicherheit 2 px im Originalbild; staerkste Vertikalgradienten im Suchband sind die Dachkante (nicht Fenster/Baum/Schatten)"],
               blind=["Ergebnis haengt an den SfM-Kameraposen (Bodenanker): ein gemeinsamer Massstabsfehler der Ausrichtung erscheint hier NICHT als Widerspruch, nur Hoehenverzerrung ueber die Gebaeudehoehe",
                      "nur Gebaeude bis ca. 25 m; keine Aussage ueber den Turm (ab 30 m)", "Verdeckung nur grob (LoD2-Waende), Baeume/Aufbauten/Dachueberstaende nicht modelliert"])
    json.dump(out, open(os.path.join(od, "audit", "massstab_lod2.json"), "w"), indent=1, ensure_ascii=False)
    print(f"\nNachbarn: n = {len(nb)} Traufkanten aus {out['n_fotos']} Fotos / {out['n_gebaeude']} Gebaeuden; verworfen: {verworfen}")
    if len(s_): print(f"s (wahr/Modell) Nachbarn Median {md:.3f}  MAD {mad:.3f}  Spanne {s_.min():.3f}..{s_.max():.3f}")
    else: print("keine verwertbare Nachbarkante")
    if len(s_t): print(f"(Turm selbst, nicht in der Kennzahl: n = {len(tm)}, Median {md_t:.3f}, MAD {mad_t:.3f})")

if __name__ == "__main__":
    main()
