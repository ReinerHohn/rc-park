#!/usr/bin/env python3
"""video_seite_pruefen.py - UNABHAENGIGE Pruefung, ob die Seitenzuordnung (Spiegelung Nord/Sued bzw. Ost/West) der Video-/Wolken-Ausrichtung stimmt (Plan M8, Register AH).

Problem: Ein Turm mit zwei fast gleichen Seiten (Martinstor: Uhr Nord/Sued) laesst sich vom SfM nicht unterscheiden; die Ausrichtung ans Nordnetz kann gespiegelt sein.
Idee: Ein ASYMMETRISCHES Nachbargebaeude (objekt.json["nebengebaeude"][*]["stl_m"], amtlich LoD2, Modellrahmen in Metern, liegt NICHT symmetrisch zum Turm) dient als Merkmal. Fuer jede Spiegelung
(x -> -x: vertauscht Sued/Nord; y -> -y: vertauscht Ost/West) wird gezaehlt, wie viele Punkte der Wolke nahe der ECHTEN und nahe der GESPIEGELTEN Flaeche liegen, jeweils nur dort, wo
sich beide unterscheiden (A = nah an echt, nicht an gespiegelt; B = umgekehrt). A >> B: Zuordnung konsistent. B >> A: gespiegelt. Sonst: nicht entscheidbar (ehrlich so melden).
  /media/oem/scan/venv-seg/bin/python -I tools/video_seite_pruefen.py modelle/<objekt>/objekt.json [--wolke <npy> ...] [--abstand 1.0] [--verhaeltnis 2.0] [--min-punkte 200]
Wolken (ohne --wolke): sfm/dicht_*_entzerrt.npy bzw. sfm/dicht_*_modell.npy des Objekts und <video_stufe.ordner>/*/dicht_modell.npy (Modellrahmen).
Ausgabe: modelle/<objekt>/audit/video_seite_pruefung.json. Exit 0 = alle entscheidbaren Wolken konsistent, 1 = mindestens eine gespiegelt, 2 = nichts entscheidbar.
ANNAHMEN (Argumente, keine Messwerte): Abstand 1,0 m (LoD2 ist generalisiert, Fassadenversatz bis ~1 m); Verhaeltnis 2,0; mind. 200 Punkte in A+B; Spiegelachsen = Turmachsen x und y durch den Ursprung.
GRENZEN: Setzt voraus, dass die Wolke das Nachbargebaeude ueberhaupt sieht (Strassenfotos der Nordseite sehen den Torbau kaum); ein verdecktes Merkmal ergibt 'nicht entscheidbar', nicht 'konsistent'.
Ein Gebaeude, das selbst fast spiegelsymmetrisch ist (Anteil Unterschied < 10 % der Flaeche), wird als Merkmal verworfen.
"""
import sys, os, json, glob, argparse, numpy as np

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--wolke", nargs="*"); ap.add_argument("--abstand", type=float, default=1.0)
    ap.add_argument("--verhaeltnis", type=float, default=2.0); ap.add_argument("--min-punkte", type=int, default=200); ap.add_argument("--flaechenpunkte", type=int, default=400000); a = ap.parse_args()
    import trimesh; from scipy.spatial import cKDTree
    objp = os.path.abspath(a.objekt); obj = json.load(open(objp)); od = os.path.dirname(objp); root = os.path.dirname(os.path.dirname(od))
    aud = os.path.join(root, obj.get("audit", os.path.join(os.path.dirname(obj["masstabelle"]), "audit"))); os.makedirs(aud, exist_ok=True)
    wolken = a.wolke or sorted(glob.glob(os.path.join(od, "sfm", "dicht_*_entzerrt.npy")) + glob.glob(os.path.join(od, "sfm", "dicht_*_modell.npy")) + glob.glob(os.path.join(obj.get("video_stufe", {}).get("ordner", "/nicht/da"), "*", "dicht_modell.npy")))
    merkmale = {}
    for nm, nb in (obj.get("nebengebaeude") or {}).items():
        p = os.path.join(root, nb.get("stl_m", "")) if nb.get("stl_m") else None
        if not p or not os.path.exists(p): continue
        m = trimesh.load(p); P, _ = trimesh.sample.sample_surface(m, a.flaechenpunkte, seed=0); P = np.asarray(P); T = cKDTree(P); merkmale[nm] = (m, P, T)
    erg = dict(parameter=dict(abstand_m=a.abstand, verhaeltnis=a.verhaeltnis, min_punkte=a.min_punkte), merkmale={}, wolken={}, hinweis="ANNAHMEN siehe Kopf von tools/video_seite_pruefen.py")
    if not merkmale: erg["fehler"] = "kein Nebengebaeude mit stl_m in objekt.json - keine unabhaengige Seitenpruefung moeglich"
    for spiegel, achse in (("x->-x (Sued/Nord)", 0), ("y->-y (Ost/West)", 1)):
        for nm, (m, P, T) in merkmale.items():
            Pm = P.copy(); Pm[:, achse] *= -1; Tm = cKDTree(Pm)
            d_re, _ = T.query(Pm[::40]); unterschied = float((d_re > a.abstand).mean())      # Anteil der gespiegelten Flaeche, der NICHT auf der echten liegt
            erg["merkmale"][f"{nm} | {spiegel}"] = dict(unterschied_anteil=round(unterschied, 3), taugt=unterschied >= 0.10)
    for w in wolken:
        try: X = np.load(w, mmap_mode="r"); X = np.asarray(X[:: max(1, len(X) // 3000000)], dtype=np.float64)
        except Exception as e: erg["wolken"][w] = dict(fehler=str(e)); continue
        r = dict(punkte=int(len(X)), pruefungen={})
        for spiegel, achse in (("x->-x (Sued/Nord)", 0), ("y->-y (Ost/West)", 1)):
            for nm, (m, P, T) in merkmale.items():
                if not erg["merkmale"][f"{nm} | {spiegel}"]["taugt"]: continue
                Pm = P.copy(); Pm[:, achse] *= -1; Tm = cKDTree(Pm); lo = np.minimum(m.bounds[0], m.bounds[0] * np.where(np.arange(3) == achse, -1, 1)); hi = np.maximum(m.bounds[1], m.bounds[1] * np.where(np.arange(3) == achse, -1, 1))
                lo2 = lo - a.abstand; hi2 = hi + a.abstand; Xs = X[np.all((X >= lo2) & (X <= hi2), axis=1)]
                if len(Xs) == 0: r["pruefungen"][f"{nm} | {spiegel}"] = dict(A=0, B=0, urteil="nicht entscheidbar (keine Punkte im Bereich des Nachbargebaeudes)"); continue
                d1, _ = T.query(Xs); d2, _ = Tm.query(Xs); nah1 = d1 <= a.abstand; nah2 = d2 <= a.abstand; A = int((nah1 & ~nah2).sum()); B = int((nah2 & ~nah1).sum())
                if A + B < a.min_punkte: u = f"nicht entscheidbar (nur {A + B} Punkte in den unterscheidenden Zonen, mind. {a.min_punkte})"
                elif A >= a.verhaeltnis * max(B, 1): u = "konsistent (echte Lage)"
                elif B >= a.verhaeltnis * max(A, 1): u = "GESPIEGELT (Punkte liegen an der gespiegelten Flaeche)"
                else: u = "nicht entscheidbar (A/B zu nah beieinander)"
                r["pruefungen"][f"{nm} | {spiegel}"] = dict(A=A, B=B, punkte_im_bereich=int(len(Xs)), urteil=u)
        erg["wolken"][w] = r
    json.dump(erg, open(os.path.join(aud, "video_seite_pruefung.json"), "w"), indent=1, ensure_ascii=False)
    gesp = False; ent = False
    for nm, mm in erg["merkmale"].items(): print(f"Merkmal {nm}: Unterschied zur Spiegelung {100 * mm['unterschied_anteil']:.0f} % der Flaeche -> {'taugt' if mm['taugt'] else 'verworfen (zu symmetrisch)'}")
    for w, r in erg["wolken"].items():
        print(f"== {os.path.relpath(w, root) if w.startswith(root) else w}  ({r.get('punkte', '?')} Punkte)")
        for k, v in r.get("pruefungen", {}).items():
            print(f"   {k}: A {v['A']} B {v['B']} -> {v['urteil']}"); gesp |= v["urteil"].startswith("GESPIEGELT"); ent |= v["urteil"].startswith("konsistent")
    print("->", os.path.join(aud, "video_seite_pruefung.json")); sys.exit(1 if gesp else (0 if ent else 2))

if __name__ == "__main__":
    main()
