#!/usr/bin/env python3
"""kamera_bruecke_pruefen.py - TOR je Kamera (generisch, 2026-11-04): Ist die K-Kamera (K-<foto>.json 'kamera') so gut wie das Buendel, aus dem sie stammt?

Warum nicht gegen LoD2: LoD2 ist ungenauer als die Buendelkameras (Kaufhaus: LoD2-First = Hoehe der Stufengiebelspitzen, 40-50 px ueber dem echten First in 004;
Nachbardach 30-40 px; die rechte Nachbartraufe und die Bodenanker passen). Ein Kanten-Tor gegen LoD2 verwarf gute Kameras und nahm auf Strassenfoto-Unordnung
falsche an (kamera_lod2_nachfuehren: 2/96, davon 1 falsch; Kantenmass an der Buendelkamera nicht besser als bei 2 Grad Verstellung, Versuchslog).
Die Buendelkameras sind je Foto durch ihre eigenen SfM-Beobachtungen bestimmt; das Buendel als Ganzes ist gegen LoD2/DGM1 verankert und durch sein eigenes Tor
(sfm_lod2_buendel Exit 3) und den Sichtbeweis (beweis_anker.py) geprueft. Dieses Werkzeug prueft die KETTE dazwischen exakt:
  Punkte des ausgerichteten Netzes (A['sparse'], Transformation A['transformation'] -> Modellsystem) -> Werkzeugrahmen (+ rahmen_verschiebung T_) ->
  Projektion mit der K-Kamera (f, cx, cy, k1 radial wie SIMPLE_RADIAL) -> Abstand zu den beobachteten Bildpunkten dieses Fotos (SfM-Pixel x s).
Tor je Kamera: >= --min-beob Beobachtungen, Median <= --median-proz, p90 <= --p90-proz der langen Bildseite. Schreibt K['kamera']['buendel_tor'] (--schreiben),
audit/kamera_bruecke.json. Exit 0 = Kette in Ordnung (Median ueber alle Kameras im Tor), 1 = Kette gebrochen (Umrechnungsfehler), 3 = keine Kameras.
  /media/oem/scan/venv-colmap/bin/python -I tools/kamera_bruecke_pruefen.py modelle/<objekt>/objekt.json --ausrichtung messprotokoll/SFM-AUSRICHTUNG-buendel.json [--schreiben] [--selbsttest]
--selbsttest: BEWEIS mit bekannter Wahrheit - jede Kamera zusaetzlich verstellt (0,2 Grad Drehung, 1 % Brennweite, 0,3 m Lage, 0,1 m Rahmen): die echte muss bestehen,
jede verstellte, deren Bildwirkung (Median-Verschiebung der Punkte) ueber 1,5 x Grenze liegt, muss durchfallen (kleinere Verstellungen liegen innerhalb der Toleranz, die das Tor zusichert); Ergebnis audit/kamera_bruecke_selbsttest.json, Exit 1 wenn nicht.
GRENZEN: prueft Kamera relativ zum Buendel, nicht das Buendel gegen die Wirklichkeit (dafuer Buendel-Tor + beweis_anker + foto_overlay ansehen).
"""
import sys, os, json, glob, argparse, numpy as np


def rot(rv):
    from scipy.spatial.transform import Rotation as Rot
    return Rot.from_rotvec(np.asarray(rv, float)).as_matrix()


def projiziere(X, K):
    R = rot(K["rvec"]); Xc = X @ R.T + np.asarray(K["t"], float); z = Xc[:, 2]; zz = np.where(z > 1e-6, z, 1e-6)
    xn = Xc[:, :2] / zz[:, None]; d = 1 + float(K.get("k1", 0.0)) * (xn ** 2).sum(1)
    return np.c_[K["f_px"] * d * xn[:, 0] + K["cx"], K["f_px"] * d * xn[:, 1] + K["cy"]], z


def beobachtungen(A):
    import pycolmap
    r = pycolmap.Reconstruction(A["sparse"]); T = A.get("transformation") or {}; s_ = float(T.get("s", 1.0)); Rt = rot(T.get("rvec", [0, 0, 0])); tt = np.asarray(T.get("t", [0, 0, 0]), float)
    B = {}
    for pid, pt in r.points3D.items():
        Xm = s_ * Rt @ np.asarray(pt.xyz, float) + tt
        for el in pt.track.elements:
            im = r.images[el.image_id]; nr = os.path.splitext(im.name)[0]; B.setdefault(nr, ([], [], im.camera_id))
            B[nr][0].append(Xm); B[nr][1].append(np.asarray(im.points2D[el.point2D_idx].xy, float))
    breite = {c_id: c.width for c_id, c in r.cameras.items()}
    return {nr: (np.array(x), np.array(u), breite[c]) for nr, (x, u, c) in B.items()}


def pruefe(K, X, u_sfm, b_sfm, a):
    W, H = K["bild"]; s = W / float(b_sfm); L = max(W, H); T_ = np.asarray(K.get("rahmen_verschiebung", [0, 0, 0]), float)
    uv, z = projiziere(X + T_, K); d = np.linalg.norm(uv - u_sfm * s, axis=1); d[z <= 0] = 1e9
    med, p90 = float(np.median(d)), float(np.percentile(d, 90))
    ok = len(d) >= a.min_beob and med <= a.median_proz / 100 * L and p90 <= a.p90_proz / 100 * L
    return dict(ok=bool(ok), beob=int(len(d)), median_px=round(med, 2), p90_px=round(p90, 2), grenze_median_px=round(a.median_proz / 100 * L, 1), grenze_p90_px=round(a.p90_proz / 100 * L, 1))


def verstellen(K, art, rng):
    K = dict(K)
    if art == "drehung":
        ax = rng.normal(size=3); ax /= np.linalg.norm(ax); R = rot(np.radians(0.2) * ax) @ rot(K["rvec"]); C = -rot(K["rvec"]).T @ np.asarray(K["t"])
        from scipy.spatial.transform import Rotation as Rot
        K["rvec"] = Rot.from_matrix(R).as_rotvec().tolist(); K["t"] = (-R @ C).tolist()
    elif art == "brennweite": K["f_px"] = K["f_px"] * 1.01
    elif art == "lage":
        R = rot(K["rvec"]); C = -R.T @ np.asarray(K["t"]); d = rng.normal(size=3); d /= np.linalg.norm(d); K["t"] = (-R @ (C + 0.3 * d)).tolist()
    elif art == "rahmen": K["rahmen_verschiebung"] = (np.asarray(K.get("rahmen_verschiebung", [0, 0, 0]), float) + [0, 0, 0.1]).tolist()
    return K


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--ausrichtung", required=True); ap.add_argument("--schreiben", action="store_true"); ap.add_argument("--selbsttest", action="store_true")
    ap.add_argument("--min-beob", type=int, default=30); ap.add_argument("--median-proz", type=float, default=0.15, help="Median-Grenze in %% der langen Bildseite (4000 px -> 6 px)")
    ap.add_argument("--p90-proz", type=float, default=0.5); a = ap.parse_args()
    objp = os.path.abspath(a.objekt); od = os.path.dirname(objp); root = os.path.dirname(os.path.dirname(od))
    ap_ = a.ausrichtung if os.path.isabs(a.ausrichtung) else (os.path.join(od, a.ausrichtung) if os.path.exists(os.path.join(od, a.ausrichtung)) else os.path.join(root, a.ausrichtung))
    A = json.load(open(ap_)); B = beobachtungen(A); erg = {}; selbst = []; rng = np.random.default_rng(0)
    for kp in sorted(glob.glob(os.path.join(od, "messprotokoll", "K-*.json"))):
        nr = os.path.basename(kp)[2:-5]; KK = json.load(open(kp)); K = KK.get("kamera")
        if not K or nr not in B: continue
        X, u, b = B[nr]; r = pruefe(K, X, u, b, a); erg[nr] = r
        if a.selbsttest:
            for art in ("drehung", "brennweite", "lage", "rahmen"):
                Kv = verstellen(K, art, rng); rv = pruefe(Kv, X, u, b, a)
                T0 = np.asarray(K.get("rahmen_verschiebung", [0, 0, 0]), float); T1 = np.asarray(Kv.get("rahmen_verschiebung", [0, 0, 0]), float)
                wirk = float(np.median(np.linalg.norm(projiziere(X + T1, Kv)[0] - projiziere(X + T0, K)[0], axis=1)))   # Bildwirkung der Verstellung allein
                selbst.append(dict(foto=nr, art=art, wahr_ok=r["ok"], verstellt_ok=rv["ok"], median_verstellt_px=rv["median_px"], wirkung_px=round(wirk, 2), grenze_px=r["grenze_median_px"],
                                   muss_durchfallen=bool(wirk > 1.5 * r["grenze_median_px"])))
        if a.schreiben: K["buendel_tor"] = dict(r, werkzeug="kamera_bruecke_pruefen.py", ausrichtung=os.path.relpath(ap_, root)); json.dump(KK, open(kp, "w"), indent=1, ensure_ascii=False)
    if not erg: print("keine K-Kamera mit Buendelbeobachtungen"); sys.exit(3)
    med_alle = float(np.median([r["median_px"] for r in erg.values()])); n_ok = sum(r["ok"] for r in erg.values())
    kette_ok = med_alle <= np.median([r["grenze_median_px"] for r in erg.values()])
    json.dump(dict(kette_ok=bool(kette_ok), median_alle_px=round(med_alle, 2), bestanden=n_ok, geprueft=len(erg), kameras=erg, annahmen=vars(a)), open(os.path.join(od, "audit", "kamera_bruecke.json"), "w"), indent=1)
    print(f"Bruecke Buendel -> K: {n_ok} von {len(erg)} Kameras im Tor, Median aller Kameras {med_alle:.2f} px -> Kette {'IN ORDNUNG' if kette_ok else 'GEBROCHEN'}")
    for nr, r in sorted(erg.items(), key=lambda x: -x[1]["median_px"])[:5]: print(f"  schlechteste K-{nr}: {r}")
    rc = 0 if kette_ok else 1
    if a.selbsttest:
        wahr = [e for e in selbst if e["wahr_ok"]]; falsch_an = [e for e in wahr if e["verstellt_ok"] and e["muss_durchfallen"]]   # Tor verspricht Median <= Grenze: Verstellung mit Wirkung > 1,5 x Grenze darf nie durch
        bestanden = bool(wahr) and not falsch_an
        json.dump(dict(bestanden=bestanden, faelle=selbst, falsch_angenommen=falsch_an), open(os.path.join(od, "audit", "kamera_bruecke_selbsttest.json"), "w"), indent=1)
        arten = {}
        for e in wahr: arten.setdefault(e["art"], []).append(e["median_verstellt_px"])
        print(f"SELBSTTEST: {len(wahr)} Faelle mit bestandener echter Kamera, verstellt angenommen: {len(falsch_an)} -> {'BESTANDEN' if bestanden else 'NICHT BESTANDEN'}; "
              + ", ".join(f"{k}: Median verstellt {np.median(v):.1f} px" for k, v in arten.items()))
        rc = rc or (0 if bestanden else 1)
    sys.exit(rc)


if __name__ == "__main__":
    main()
