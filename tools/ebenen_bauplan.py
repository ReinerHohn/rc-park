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


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("fassade"); ap.add_argument("kanten"); ap.add_argument("aus")
    ap.add_argument("--min_m2", type=float, default=40.0); ap.add_argument("--maxpx", type=int, default=150000); ap.add_argument("--refs", type=int, default=80); ap.add_argument("--nur", default="")
    ap.add_argument("--bild", type=int, default=1); ap.add_argument("--stapel", nargs=3, type=float, help="w0 w1 schritt (m gegen die Wandebene): Schichtstapel je Wand"); ap.add_argument("--seiten", type=int, default=1, help="1 = je Vorbau auch die zwei Seitenebenen (senkrecht zur Wand)"); a = ap.parse_args()
    import trimesh
    od = os.path.dirname(os.path.abspath(a.objekt)); FA = json.load(open(os.path.join(a.fassade, "fassaden.json")))["fassaden"]; os.makedirs(a.aus, exist_ok=True)
    KW, SD = os.path.join(a.kanten, "kam_wahl.json"), os.path.join(a.kanten, "stabil")
    if not (os.path.exists(KW) and os.path.isdir(SD)): print("Kantenstufe fehlt (kam_wahl.json / stabil) - erst Stufe 'kanten'"); return 3
    E = []
    for i, F in enumerate(FA):
        vj = os.path.join(a.fassade, f"vorbauten_f{i:02d}.json"); ww = float(json.load(open(vj)).get("wand_versatz_m", 0.0)) if os.path.exists(vj) and json.load(open(vj)).get("belastbar") else 0.0
        if F.get("flaeche_m2", 0) >= a.min_m2 and len(F.get("fotos") or {}) >= 6:
            E.append(dict(id=f"f{i:02d}_wand", art="wand", fassade=F.get("id", f"f{i:02d}"), o=F["o"], d=F["d"], n=F["n"], w=round(ww, 3), zone=[F["u"][0], F["u"][1], F["z"][0], F["z"][1]], band=0.5))
    vp = os.path.join(od, "audit", "vorbauten_auto.json")
    if os.path.exists(vp):
        for F in json.load(open(vp)).get("fassaden", []):
            for k, g in enumerate(F["gruppen"]):
                E.append(dict(id=f"f{F['nr']:02d}_vb{k}", art="vorbau", fassade=F["id"], o=F["o"], d=F["d"], n=F["n"], w=round(float(F.get("w_wand", 0.0)) + float(g["koerper"]["w_median"]), 3),
                              w_wand=round(float(F.get("w_wand", 0.0)), 3), zone=[g["u0"] - 0.6, g["u1"] + 0.6, g["z0"] - 1.6, g["z1"] + 1.0], band=0.8))
    # 21.11.2026 (Nutzer: "Ebenen in alle Richtungen, nicht nur in der Frontansicht, sondern von der Seite auch"): je Vorbau zwei SEITENEBENEN (senkrecht zur Wand, an den Enden des
    # Vorbaus). In-Ebenen-Achse u' = Tiefe ab der Fassadenebene (Richtung n), Normale = -d (links) / +d (rechts). Dort stehen Ausladung, Strebenschraege und Dachprofil als Kanten.
    if os.path.exists(vp) and a.seiten:
        for F in json.load(open(vp)).get("fassaden", []):
            o_ = np.array(F["o"], float); d_ = np.array(F["d"], float); n_ = np.array(F["n"], float); ww_ = float(F.get("w_wand", 0.0))
            for k, g in enumerate(F["gruppen"]):
                Kb = (g.get("kanten_mass") or {}).get("kasten") or g["koerper"]; aus_ = float((g.get("kanten_mass") or {}).get("ausladung") or g["koerper"]["w_median"])
                for nm, ue, vz in (("li", Kb["u0"], -1.0), ("re", Kb["u1"], 1.0)):
                    E.append(dict(id=f"f{F['nr']:02d}_vb{k}_{nm}", art="seite", fassade=F["id"], o=[float(x) for x in (o_ + ue * d_)], d=[float(x) for x in n_], n=[float(x) for x in (vz * d_)], w=0.0, w_wand=round(ww_, 3),
                                  zone=[ww_ - 0.4, ww_ + aus_ + 1.6, g["z0"] - 2.2, g["z1"] + 1.5], band=0.5, u_kante=round(float(ue), 2)))
    # 21.11.2026 (Nutzer: "geht auf der GPU sehr schnell ... auf ganz vielen, aus allen Winkeln machen"): SCHICHTSTAPEL je Wand - parallele duenne Ebenen (--stapel w0 w1 schritt,
    # Band = halber Schritt). Im duennen Band ist die Tiefe je Kantenpixel eindeutig (der breite Sweep verwirft mehrdeutige Pixel) -> mehr Punkte; Gegenprobe der Scheintreffer mit der Wolke.
    if a.stapel:
        w0s, w1s, ds = a.stapel
        for e_ in [e_ for e_ in E if e_["art"] == "wand"]:
            for j, wj in enumerate(np.arange(w0s, w1s + 1e-6, ds)):
                E.append(dict(id=f"{e_['id'][:3]}_s{j:02d}", art="schicht", fassade=e_["fassade"], o=e_["o"], d=e_["d"], n=e_["n"], w=round(e_["w"] + float(wj), 3), w_wand=e_["w"], zone=e_["zone"], band=round(ds / 2, 3)))
    if a.nur: E = [e for e in E if e["id"] in a.nur.split(",") or (a.nur.endswith("*") and e["id"].startswith(a.nur[:-1]))]
    PY = sys.executable; n_ok = 0
    for e in E:
        t0 = time.time(); ed = os.path.join(a.aus, e["id"]); os.makedirs(ed, exist_ok=True); o = np.array(e["o"]); d = np.array(e["d"]); n = np.array(e["n"]); u0, u1, z0, z1 = e["zone"]; z0 = max(z0, 0.0)
        P = lambda u, z: [o[0] + u * d[0] + e["w"] * n[0], o[1] + u * d[1] + e["w"] * n[1], z]
        V = np.array([P(u0, z0), P(u1, z0), P(u1, z1), P(u0, z1)]); stl = os.path.join(ed, "ebene.stl"); trimesh.Trimesh(V, [[0, 1, 2], [0, 2, 3]]).export(stl)
        box = ",".join(f"{x:.2f}" for x in np.r_[V.min(0) - e["band"] - 1.0, V.max(0) + e["band"] + 1.0]); sw = os.path.join(ed, "sweep.npz")
        if os.path.exists(sw): os.remove(sw)
        r = subprocess.run([PY, "-I", os.path.join(HIER, "kanten_tiefe_sweep_flaeche.py"), KW, SD, sw, "--flaeche", stl, "--flaeche_skala", "1.0", "--box3", box, "--band", str(e["band"]), "--ziel_auto",
                            "--nbdist", "80", "--refs", str(a.refs), "--nb", "12", "--maxpx", str(a.maxpx)], capture_output=True, text=True)
        e["punkte"] = int(len(np.load(sw)["P"])) if os.path.exists(sw) else 0; e["sweep"] = sw if e["punkte"] else None; e["sekunden"] = round(time.time() - t0)
        if r.returncode != 0 or not e["punkte"]: e["fehler"] = (r.stderr.strip().splitlines() or r.stdout.strip().splitlines() or ["?"])[-1][:200]
        if e["punkte"]:
            n_ok += 1; Pp = np.load(sw)["P"].astype(float); w_ = (Pp[:, :2] - o) @ n - e["w"]; e["auf_ebene_anteil"] = round(float((np.abs(w_) < 0.15).mean()), 3)
        if e["art"] == "vorbau" and a.bild and e["punkte"]:
            try:
                import cv2
                from form_aus_wandbild import wandbild_fotos, _ebene
                A_, T_, N_ = _ebene(o, o + d, o + n); img, _, _ = wandbild_fotos(a.objekt, A_, T_, N_, (u0, u1, z0, z1), 0.01, w=e["w"], k=5)
                if img is not None: e["bild"] = os.path.join(ed, "bild.png"); cv2.imwrite(e["bild"], img)
            except Exception as x_: e["bild_fehler"] = str(x_)[:160]
        print(f"{e['id']}: Ebene w {e['w']:+.2f} m, Zone u {u0:.1f}..{u1:.1f} z {z0:.1f}..{z1:.1f}, Band {e['band']} m -> {e['punkte']} Kantenpunkte"
              + (f", {e.get('auf_ebene_anteil', 0) * 100:.0f} % auf der Ebene (+-15 cm)" if e["punkte"] else f"  FEHLER: {e.get('fehler')}") + f" ({e['sekunden']} s)", flush=True)
    json.dump(dict(quelle="tools/ebenen_bauplan.py", ebenen=E), open(os.path.join(a.aus, "ebenen.json"), "w"), indent=1)
    print(f"-> {os.path.join(a.aus, 'ebenen.json')}: {n_ok} von {len(E)} Ebenen mit Kantenpunkten"); return 0 if n_ok else 3


if __name__ == "__main__": sys.exit(main())
