#!/usr/bin/env python3
"""ebenen_bauplan.py - BAUPLAN JE EBENE: dichte triangulierte Fotokanten (+ feines Bild) fuer jede Wand und jede Sweep-Ebene (21.11.2026, Kettenstufe 'bauplan').

Leitbild Nutzer 21.11.: "die Tiefen sweepen und mehrere Bauplaene auf mehrere Ebenen machen und dort die Abweichungen mit diesen Bauplaenen abgleichen."
Schritt 1 der Schleife (LOGBUCH_SCHWABENTOR_KETTE_2026-11-21.md, METHODE): je Ebene
  - WAND   : jede Fassade aus fassaden.json mit >= --min_m2 Flaeche und >= 6 Fotos; Ebene = Fassadenebene + gemessener Wandversatz (vorbauten_fNN.json), Band +-0,5 m.
  - VORBAU : jede Gruppe aus audit/vorbauten_auto.json; Ebene = Wandversatz + Frontausladung, Zone + 0,6 m Rand, Band +-0,8 m (schraege Streben laufen zur Wand zurueck).
  Kanten: tools/kanten_tiefe_sweep_flaeche.py auf ein Rechteck der Ebene (--flaeche, --band), Kameras + Stabilitaetskarten der Kantenstufe (kanten/kam_wahl.json, kanten/stabil).
  Probe Erker Schwabentor: 54 463 Punkte statt 13 041 aus dem Gesamtlauf; Bruestungskanten auf wenige cm am Handstand, 6 Konsolen gezaehlt.
  Bild (nur VORBAU, --bild 1): form_aus_wandbild.wandbild_fotos auf der Ebene (1 cm); fuer WAND gilt das feine Fassadenbild der Stufe 'fenster'.
Ausgabe: <daten>/ebenen/ebenen.json (je Ebene id, fassade, o, d, n, w, zone, band, sweep.npz, punkte, bild) - Eingang fuer tools/ebenen_abweichung.py.
Aufruf: ebenen_bauplan.py <objekt.json> <fassade-ordner> <kanten-ordner> <aus-ordner> [--nur f00_wand,f00_vb0] [--maxpx 150000]
rc 0 = mindestens eine Ebene mit Punkten, rc 3 = keine.
"""
import sys, os, json, argparse, subprocess, time, numpy as np

HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)


def kipp(ne, u, z):
    """22.11.2026: Neigung der Wandebene im Kamerarahmen (fassade_tiefe 'wand_ebene', ohne Fusswert a) an (u, z); ohne Neigung 0."""
    if not ne: return 0.0 * np.asarray(u, float)
    return ne["b_u"] * (np.asarray(u, float) - ne["u_ref"]) + ne["c_z"] * (np.asarray(z, float) - ne["z_ref"])


def nur_passt(i, nur):
    """--nur: Komma-Liste aus Ids, jedes Glied darf auf '*' enden (27.11.2026, Stapel aller Waende in einem Lauf: 'f00_s*,f01_s*'; vorher nur EIN Muster fuer die ganze Liste)."""
    return any(i == p or (p.endswith("*") and i.startswith(p[:-1])) for p in nur.split(",") if p)


def frontal_kameras(K, e, wahl, n_max=24, winkel=45.0, min_sicht=0.5, max_gsd=0.03, n_proben=600):
    """24.11.2026 (Befund 1122z f02/Ost: 1316 Fotokantenpunkte statt 13 501 an f00): die Kantenstufe waehlt 80 Kameras GLOBAL (12 Azimut-Sektoren um die Modellmitte,
    Abstand <= 80 m, Rang Sicht/sqrt(Abstand)). Fuer f02 lagen 49 SfM-Kameras frontal (< winkel Grad), sehen >= 50 % der Wand und hatten 1,2-6,6 cm/px - KEINE davon in
    kam_wahl; dort sahen die 17 'frontalen' die Wand nur schraeg/nah (je Ref 0-265 Punkte). Jetzt je WAND: Kameras aus kam.json (alle SfM-Kameras) vor der Wand, Blick auf die
    Wand (Winkel zur Normale < winkel), >= min_sicht der Wandflaeche im Bildfeld, Bodenaufloesung Abstand/f <= max_gsd m/px; die besten n_max (Aufloesung) zusaetzlich zu kam_wahl.
    Reine Kameraauswahl - Sweep, Tore und Guards bleiben unveraendert. Der Sweep zieht seine Referenzen ZUFAELLIG (--refs aus dem Kamerasatz): --refs waechst um die
    Zahl der ergaenzten Kameras, sonst fielen alte Referenzen heraus (Probe f02: 80 aus 90 -> 816 statt 1316 Punkte). -> Liste Dateinamen (ohne die schon gewaehlten)."""
    o = np.array(e["o"], float); d = np.array(e["d"], float); n = np.array(e["n"], float); u0, u1, z0, z1 = e["zone"]; z0 = max(z0, 0.0)
    rg = np.random.default_rng(0); uu = rg.uniform(u0, u1, n_proben); zz = rg.uniform(z0, z1, n_proben); ww = float(e.get("w", 0.0))
    VF = np.c_[o[0] + uu * d[0] + ww * n[0], o[1] + uu * d[1] + ww * n[1], zz]; c = np.cos(np.radians(winkel)); out = []
    for f, k in K.items():
        if f in wahl or "C" not in k or "Rn" not in k: continue
        C = np.array(k["C"], float); R = np.array(k["Rn"], float); ab = float((C[:2] - o) @ n)
        bl = R[2, :2]; nb_ = float(np.linalg.norm(bl))
        if ab <= 1.0 or nb_ < 1e-6 or -(bl @ n) / nb_ < c: continue
        X = VF @ R.T + np.array(k["tn"], float); z = X[:, 2]; ok = z > 0.5
        if ok.sum() < min_sicht * n_proben: continue
        uc = k["f"] * X[ok, 0] / z[ok] + k["cx"]; vc = k["f"] * X[ok, 1] / z[ok] + k["cy"]
        sicht = float(((uc >= 0) & (uc < k["W"]) & (vc >= 0) & (vc < k["H"])).sum()) / n_proben; gsd = float(np.median(z[ok])) / float(k["f"])
        if sicht >= min_sicht and gsd <= max_gsd: out.append((gsd, f))
    out.sort(); return [f for _, f in out[:n_max]]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("fassade"); ap.add_argument("kanten"); ap.add_argument("aus")
    ap.add_argument("--min_m2", type=float, default=40.0); ap.add_argument("--maxpx", type=int, default=150000); ap.add_argument("--refs", type=int, default=80); ap.add_argument("--nur", default="")
    ap.add_argument("--bild", type=int, default=1); ap.add_argument("--stapel", nargs=3, type=float, help="w0 w1 schritt (m gegen die Wandebene): Schichtstapel je Wand"); ap.add_argument("--seiten", type=int, default=1, help="1 = je Vorbau auch die zwei Seitenebenen (senkrecht zur Wand)")
    ap.add_argument("--kam_ergaenzen", type=int, default=24, help="24.11.2026: je WAND bis zu N frontale SfM-Kameras aus kanten/kam.json zu kam_wahl (frontal_kameras); 0 = alter Weg")
    ap.add_argument("--bilder", default="", help="Fotoordner der Kantenstufe (Stabilkarten fuer ergaenzte Kameras); Standard <kanten>/../fotos"); a = ap.parse_args()
    import trimesh
    od = os.path.dirname(os.path.abspath(a.objekt)); FA = json.load(open(os.path.join(a.fassade, "fassaden.json")))["fassaden"]; os.makedirs(a.aus, exist_ok=True)
    KW, SD = os.path.join(a.kanten, "kam_wahl.json"), os.path.join(a.kanten, "stabil")
    if not (os.path.exists(KW) and os.path.isdir(SD)): print("Kantenstufe fehlt (kam_wahl.json / stabil) - erst Stufe 'kanten'"); return 3
    KWAHL = json.load(open(KW)); KJ_ = os.path.join(a.kanten, "kam.json"); KALLE = json.load(open(KJ_)) if a.kam_ergaenzen > 0 and os.path.exists(KJ_) else {}
    BILDER = a.bilder or os.path.join(os.path.dirname(os.path.abspath(a.kanten)), "fotos")
    if not os.path.isdir(BILDER): KALLE = {}
    E = []
    for i, F in enumerate(FA):
        vj = os.path.join(a.fassade, f"vorbauten_f{i:02d}.json"); vj_ = json.load(open(vj)) if os.path.exists(vj) else {}
        ww = float(vj_.get("wand_versatz_m", 0.0)) if vj_.get("belastbar") else 0.0; ne = vj_.get("wand_ebene") if vj_.get("belastbar") else None
        if F.get("flaeche_m2", 0) >= a.min_m2 and len(F.get("fotos") or {}) >= 6:
            E.append(dict(id=f"f{i:02d}_wand", art="wand", fassade=F.get("id", f"f{i:02d}"), o=F["o"], d=F["d"], n=F["n"], w=round(ww, 3), neigung=ne, zone=[F["u"][0], F["u"][1], F["z"][0], F["z"][1]], band=0.5))
    vp = os.path.join(od, "audit", "vorbauten_auto.json")
    if os.path.exists(vp):
        for F in json.load(open(vp)).get("fassaden", []):
            for k, g in enumerate(F["gruppen"]):
                E.append(dict(id=f"f{F['nr']:02d}_vb{k}", art="vorbau", fassade=F["id"], o=F["o"], d=F["d"], n=F["n"], w=round(float(F.get("w_wand", 0.0)) + float(g["koerper"]["w_median"]), 3),
                              w_wand=round(float(F.get("w_wand", 0.0)), 3), neigung=F.get("wand_ebene"), zone=[g["u0"] - 0.6, g["u1"] + 0.6, g["z0"] - 1.6, g["z1"] + 1.0], band=0.8))
    # 21.11.2026 (Nutzer: "Ebenen in alle Richtungen, nicht nur in der Frontansicht, sondern von der Seite auch"): je Vorbau zwei SEITENEBENEN (senkrecht zur Wand, an den Enden des
    # Vorbaus). In-Ebenen-Achse u' = Tiefe ab der Fassadenebene (Richtung n), Normale = -d (links) / +d (rechts). Dort stehen Ausladung, Strebenschraege und Dachprofil als Kanten.
    if os.path.exists(vp) and a.seiten:
        for F in json.load(open(vp)).get("fassaden", []):
            o_ = np.array(F["o"], float); d_ = np.array(F["d"], float); n_ = np.array(F["n"], float); ww_ = float(F.get("w_wand", 0.0))
            for k, g in enumerate(F["gruppen"]):
                Kb = (g.get("kanten_mass") or {}).get("kasten") or g["koerper"]; aus_ = float((g.get("kanten_mass") or {}).get("ausladung") or g["koerper"]["w_median"])
                ww_ = float(F.get("w_wand", 0.0)) + float(kipp(F.get("wand_ebene"), 0.5 * (g["u0"] + g["u1"]), 0.5 * (g["z0"] + g["z1"])))      # oertliche Wand bei geneigter Wandebene
                for nm, ue, vz in (("li", Kb["u0"], -1.0), ("re", Kb["u1"], 1.0)):
                    E.append(dict(id=f"f{F['nr']:02d}_vb{k}_{nm}", art="seite", fassade=F["id"], o=[float(x) for x in (o_ + ue * d_)], d=[float(x) for x in n_], n=[float(x) for x in (vz * d_)], w=0.0, w_wand=round(ww_, 3),
                                  zone=[ww_ - 0.4, ww_ + aus_ + 1.6, g["z0"] - 2.2, g["z1"] + 1.5], band=0.5, u_kante=round(float(ue), 2)))
    # 21.11.2026 (Nutzer: "geht auf der GPU sehr schnell ... auf ganz vielen, aus allen Winkeln machen"): SCHICHTSTAPEL je Wand - parallele duenne Ebenen (--stapel w0 w1 schritt,
    # Band = halber Schritt). Im duennen Band ist die Tiefe je Kantenpixel eindeutig (der breite Sweep verwirft mehrdeutige Pixel) -> mehr Punkte; Gegenprobe der Scheintreffer mit der Wolke.
    if a.stapel:
        w0s, w1s, ds = a.stapel
        for e_ in [e_ for e_ in E if e_["art"] == "wand"]:
            for j, wj in enumerate(np.arange(w0s, w1s + 1e-6, ds)):
                E.append(dict(id=f"{e_['id'][:3]}_s{j:02d}", art="schicht", fassade=e_["fassade"], o=e_["o"], d=e_["d"], n=e_["n"], w=round(e_["w"] + float(wj), 3), w_wand=e_["w"], neigung=e_.get("neigung"), zone=e_["zone"], band=round(ds / 2, 3)))
    if a.nur: E = [e for e in E if nur_passt(e["id"], a.nur)]
    PY = sys.executable; n_ok = 0
    for e in E:
        t0 = time.time(); ed = os.path.join(a.aus, e["id"]); os.makedirs(ed, exist_ok=True); o = np.array(e["o"]); d = np.array(e["d"]); n = np.array(e["n"]); u0, u1, z0, z1 = e["zone"]; z0 = max(z0, 0.0)
        ne = e.get("neigung"); P = lambda u, z: [o[0] + u * d[0] + (e["w"] + kipp(ne, u, z)) * n[0], o[1] + u * d[1] + (e["w"] + kipp(ne, u, z)) * n[1], z]      # geneigte Ebene: 4 Ecken bleiben eben
        V = np.array([P(u0, z0), P(u1, z0), P(u1, z1), P(u0, z1)]); stl = os.path.join(ed, "ebene.stl"); trimesh.Trimesh(V, [[0, 1, 2], [0, 2, 3]]).export(stl)
        box = ",".join(f"{x:.2f}" for x in np.r_[V.min(0) - e["band"] - 1.0, V.max(0) + e["band"] + 1.0]); sw = os.path.join(ed, "sweep.npz")
        if os.path.exists(sw): os.remove(sw)
        kw_e = KW
        # 24.11.2026 (Rueckfall Treppenkloetze 1122z-zc): auch die VORBAU-Ebene bekommt frontale Zusatzkameras - f00_vb0 hatte 3375 statt 13 116 Kantenpunkte,
        # die Galerie-Fotos (IMG_..._1131xx, frontal, nah) standen nicht in kam_wahl -> Holm/Unterkante luechig, kein Kantenkasten. OHNE_VORBAU_KAM=1 = alter Weg.
        # 27.11.2026 (K7): Schichten des Stapels bekommen dieselben frontalen Kameras wie ihre Wand (sonst f02-Befund 24.11.: Schichten fast leer -> keine Spitze)
        if (e["art"] in ("wand", "schicht") or (e["art"] == "vorbau" and os.environ.get("OHNE_VORBAU_KAM") != "1")) and a.kam_ergaenzen > 0 and KALLE:
            plus = frontal_kameras(KALLE, e, KWAHL, n_max=a.kam_ergaenzen)
            if plus:
                kw_e = os.path.join(ed, "kam_wand.json"); json.dump({**KWAHL, **{f: KALLE[f] for f in plus}}, open(kw_e, "w")); kp = os.path.join(ed, "kam_plus.json"); json.dump({f: KALLE[f] for f in plus}, open(kp, "w"))
                rs = subprocess.run([PY, "-I", os.path.join(HIER, "stabil_alle.py"), kp, BILDER, SD], capture_output=True, text=True)      # nur fehlende Karten (vorhandene bleiben)
                e["kameras_ergaenzt"] = sum(os.path.exists(os.path.join(SD, os.path.splitext(f)[0] + ".png")) for f in plus)
                if rs.returncode != 0: e["stabil_fehler"] = (rs.stderr.strip().splitlines() or ["?"])[-1][:200]
        r = subprocess.run([PY, "-I", os.path.join(HIER, "kanten_tiefe_sweep_flaeche.py"), kw_e, SD, sw, "--flaeche", stl, "--flaeche_skala", "1.0", "--box3", box, "--band", str(e["band"]), "--ziel_auto",
                            "--nbdist", "80", "--refs", str(a.refs if kw_e == KW else a.refs + len(plus))] + (["--nb_rel", "1.3"] if kw_e != KW else []) + ["--nb", "12", "--maxpx", str(a.maxpx)], capture_output=True, text=True)
        e["punkte"] = int(len(np.load(sw)["P"])) if os.path.exists(sw) else 0; e["sweep"] = sw if e["punkte"] else None; e["sekunden"] = round(time.time() - t0)
        if r.returncode != 0 or not e["punkte"]: e["fehler"] = (r.stderr.strip().splitlines() or r.stdout.strip().splitlines() or ["?"])[-1][:200]
        if e["punkte"]:
            n_ok += 1; Pp = np.load(sw)["P"].astype(float); w_ = (Pp[:, :2] - o) @ n - e["w"] - kipp(ne, (Pp[:, :2] - o) @ d, Pp[:, 2]); e["auf_ebene_anteil"] = round(float((np.abs(w_) < 0.15).mean()), 3)
        if e["art"] == "vorbau" and a.bild and e["punkte"]:
            try:
                import cv2
                from form_aus_wandbild import wandbild_fotos, _ebene
                A_, T_, N_ = _ebene(o, o + d, o + n); img, _, _ = wandbild_fotos(a.objekt, A_, T_, N_, (u0, u1, z0, z1), 0.01, w=e["w"] + float(kipp(ne, 0.5 * (u0 + u1), 0.5 * (z0 + z1))), k=5)
                if img is not None: e["bild"] = os.path.join(ed, "bild.png"); cv2.imwrite(e["bild"], img)
            except Exception as x_: e["bild_fehler"] = str(x_)[:160]
        print(f"{e['id']}: Ebene w {e['w']:+.2f} m, Zone u {u0:.1f}..{u1:.1f} z {z0:.1f}..{z1:.1f}, Band {e['band']} m -> {e['punkte']} Kantenpunkte"
              + (f", {e.get('auf_ebene_anteil', 0) * 100:.0f} % auf der Ebene (+-15 cm)" if e["punkte"] else f"  FEHLER: {e.get('fehler')}")
              + (f", +{e['kameras_ergaenzt']} frontale Kameras" if e.get("kameras_ergaenzt") else "") + f" ({e['sekunden']} s)", flush=True)
    json.dump(dict(quelle="tools/ebenen_bauplan.py", ebenen=E), open(os.path.join(a.aus, "ebenen.json"), "w"), indent=1)
    print(f"-> {os.path.join(a.aus, 'ebenen.json')}: {n_ok} von {len(E)} Ebenen mit Kantenpunkten"); return 0 if n_ok else 3


if __name__ == "__main__": sys.exit(main())
