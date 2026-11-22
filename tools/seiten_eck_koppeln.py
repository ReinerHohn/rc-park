#!/usr/bin/env python3
"""seiten_eck_koppeln.py <modell_a> <modell_b> <db_mapper> <seiten.json> <fotos> --aus <ordner>

TEILE UEBER EIN ECKMODELL KOPPELN (22.11.2026, schwabentor-1122, Nutzer: "Ich habe doch Fotos von ueberall her gemacht. Muesst ihr das nicht zusammenfinden?").
Befund: die Stufe Durchblick (seiten_erkennen --durchblick) findet echte Brueckenpaare um eine Turmecke (Gruppe 1 -> 27 -> 12), aber nur wenige. Der GLOBALE Mapper ueber
alle Bilder knickte Teil B an EINEM Bild um 25 Grad (Drehungsmittelung ueberstimmte die Eckpaare; Suedwand -16 Grad gegen LoD2); ein Anbau an Teil A (--input_path)
registrierte 0 Bilder. Hier stattdessen:
  1. BRUECKE: Paare aus seiten.json 'durchblick' (urteil 'durchblick', inkl. 'Bruecke erweitern'), die NICHT ganz in A oder ganz in B liegen. Keine -> rc 2.
  2. ECKBILDER: deren Bilder + direkte Nachbarn (Paare >= NACHBAR_MIN Inlier in der Mapper-DB) - ein kleines lokales Netz um die Bruecke.
  3. ECKMODELL: schrittweiser COLMAP-Mapper nur ueber die Eckbilder (Kopie der Mapper-DB wird NICHT veraendert, nur gelesen). abs_pose_min_num_inliers ABS_POSE_MIN.
     ANNAHME 12 (COLMAP-Standard 30): 1122 zerfiel mit 30 und 15 in zwei Eckmodelle (Ecke G27 sieht die G12-Seite nur ueber 2 Bilder); Start am Brueckenpaar selbst lehnt
     COLMAP ab (Basislinie zu kurz). Die Lockerung betrifft NUR das kleine Eckmodell; ob es stimmt, entscheiden die Kopplungs-Pruefungen unten (nicht die Schwelle).
  4. KOPPLUNG je Seite ueber GEMEINSAME 3D-PUNKTE (gleicher Bildpunkt eines gemeinsamen Bildes, in beiden Modellen trianguliert), robuste Sim3 (sim3_robust.sim3_meter,
     Schwelle relativ zur Ausdehnung des Eckmodells). Annahme nur, wenn BEIDE Kopplungen stimmig sind: >= MIN_PUNKTE stimmige Punkte, Anteil >= MIN_ANTEIL,
     Rest-Median <= REST_REL x Ausdehnung, Massstab Haelften-Probe <= MASS_REL (sonst 'Massstab nicht belegt').
     Begruendung an 1122 (Meter): Ecke->A 7828/7960 stimmig, Rest 0,024 m; B->Ecke 1501/1525, Rest 0,015 m; Ausdehnung Eckmodell ~15 m -> 0,16 % / 0,10 %.
     Negativfall (Test): Punkte eines anderen Gebaeudeteils / Zufall -> Anteil < 10 % -> abgelehnt.
  5. Ausgabe <aus>/eck.json: ok, urteil, B_nach_A (Sim3 B -> A, 4x4), pruefung{...}. rc 0 gekoppelt, 3 abgelehnt, 2 keine Bruecke/kein Eckmodell.
Danach (sfm_seiten_modelle): Blick-Tor + GPS-Seiten-Tor (Veto) wie beim GPS-Weg; wand_dicke/Grundriss laufen als Tore der Kette nach der Ausrichtung."""
import os, sys, json, argparse, sqlite3, subprocess, shutil, numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
from sim3_robust import sim3_meter, umeyama, anwenden

MAXID = 2147483647
NACHBAR_MIN = 200        # wie DURCH_MIN_INLIER: nur starke Nachbarpaare ziehen Bilder ins Eckmodell
NACHBARN_JE_BILD = 10    # ANNAHME: je Brueckenbild die 10 staerksten Nachbarn (1122: alle Nachbarn >= 200 = 196 Bilder, schrittweiser Mapper > 10 min; Handliste 44 Bilder reichte)
ABS_POSE_MIN = 12        # ANNAHME, siehe Kopf (3)
MIN_PUNKTE = 100
MIN_ANTEIL = 0.8
REST_REL = 0.005         # ANNAHME: 0,5 % der Eckmodell-Ausdehnung (1122: 0,10-0,16 %)
SCHWELLE_REL = 0.02      # Inlier-Schwelle der Sim3: 2 % der Ausdehnung
MASS_REL = 0.02          # Massstab-Unsicherheit (Haelften-Probe / Bootstrap) hoechstens 2 %
COLMAP = os.environ.get("RCPARK_COLMAP", "/media/oem/scan/colmap-build/prefix/bin/colmap")


def ausdehnung(X):
    X = np.asarray(X, float); return float(np.percentile(np.linalg.norm(X - np.median(X, 0), axis=1), 90)) if len(X) else 0.0


def punkte(rE, rZ):
    """Gemeinsame 3D-Punkte (Bildname + Keypoint-Index gemeinsamer Bilder, in beiden Modellen trianguliert) -> (X_eck, X_ziel, gemeinsame Bilder)."""
    E = {im.name: im for im in rE.images.values() if im.has_pose}; Z = {im.name: im for im in rZ.images.values() if im.has_pose}; pe, pz, ges = [], [], set(); ns = sorted(set(E) & set(Z))
    for n in ns:
        a_, b_ = E[n].points2D, Z[n].points2D
        for k in range(min(len(a_), len(b_))):
            if a_[k].has_point3D() and b_[k].has_point3D() and (a_[k].point3D_id, b_[k].point3D_id) not in ges:
                ges.add((a_[k].point3D_id, b_[k].point3D_id)); pe.append(rE.points3D[a_[k].point3D_id].xyz); pz.append(rZ.points3D[b_[k].point3D_id].xyz)
    return np.array(pe).reshape(-1, 3), np.array(pz).reshape(-1, 3), ns


def kopplung_pruefen(X, Y, ausd):
    """Sim3 X -> Y (X im Eckmodell, Y im Zielmodell; ausd = Ausdehnung des Eckmodells). -> (M, pruefung, ok, grund)."""
    if len(X) < MIN_PUNKTE: return None, dict(punkte=len(X)), False, f"nur {len(X)} gemeinsame Punkte (< {MIN_PUNKTE})"
    f = sim3_meter(X, Y, schwelle_m=float("inf"), min_anteil=0.0)                   # grobe Lage fuer den Massstab der Schwelle im Zielrahmen
    s_ = float(np.cbrt(abs(np.linalg.det(f["M"][:3, :3])))) if f else 1.0
    f = sim3_meter(X, Y, schwelle_m=SCHWELLE_REL * ausd * s_, min_anteil=0.0)
    if f is None: return None, dict(punkte=len(X)), False, "keine Sim3"
    rest_rel = f["rest_median_m"] / max(ausd * s_, 1e-12); ant = f["n_inlier"] / len(X); i_ = np.flatnonzero(f["inlier"])
    Q = X[i_]; _, _, Vt = np.linalg.svd(Q - Q.mean(0)); u = (Q - Q.mean(0)) @ Vt[0]
    hs = [umeyama(X[i_][w], Y[i_][w])[0] for w in (u < np.median(u), u >= np.median(u)) if w.sum() >= 3]
    hael = float(abs(hs[0] - hs[1]) / np.mean(hs)) if len(hs) == 2 else 1.0
    pr = dict(punkte=len(X), stimmig=f["n_inlier"], anteil=round(ant, 3), rest_rel=round(rest_rel, 5), massstab_haelften_rel=round(hael, 4))
    gr = [x for x, schlecht in ((f"Anteil stimmig {ant:.0%} < {MIN_ANTEIL:.0%}", ant < MIN_ANTEIL), (f"stimmig {f['n_inlier']} < {MIN_PUNKTE}", f["n_inlier"] < MIN_PUNKTE),
                                (f"Rest {rest_rel:.2%} der Ausdehnung > {REST_REL:.1%}", rest_rel > REST_REL), (f"Massstab nicht belegt (Haelften {hael:.1%} > {MASS_REL:.0%})", hael > MASS_REL)) if schlecht]
    return f["M"], pr, not gr, "; ".join(gr) or "stimmig"


def eckbilder(sj, A, B, db):
    """Brueckenpaare (nicht ganz in A, nicht ganz in B) + starke direkte Nachbarn ihrer Bilder."""
    br = [d for d in (sj.get("durchblick") or []) if d.get("urteil") == "durchblick" and not (d["a"] in A and d["b"] in A) and not (d["a"] in B and d["b"] in B)]
    kern = {d["a"] for d in br} | {d["b"] for d in br}
    if not kern: return br, []
    c = sqlite3.connect(f"file:{db}?immutable=1", uri=True); nm = {i: n for i, n in c.execute("select image_id, name from images")}; aus = set(kern); nb = {k: [] for k in kern}
    for pid, r in c.execute("select pair_id, rows from two_view_geometries where rows >= ?", (NACHBAR_MIN,)):
        a, b = nm.get(pid // MAXID), nm.get(pid % MAXID)
        if a in kern and b: nb[a].append((r, b))
        if b in kern and a: nb[b].append((r, a))
    for k, L in nb.items(): aus |= {x for _, x in sorted(L, reverse=True)[:NACHBARN_JE_BILD]}
    return br, sorted(aus)


def eckmodell(liste, db, fotos, aus, faeden):
    os.makedirs(aus, exist_ok=True); lp = os.path.join(aus, "eckbilder.txt"); open(lp, "w").write("\n".join(liste) + "\n"); sp = os.path.join(aus, "sparse")
    if os.path.isdir(sp): shutil.move(sp, sp + ".alt_" + str(int(os.path.getmtime(sp))))
    os.makedirs(sp); cmd = [COLMAP, "mapper", "--database_path", db, "--image_path", fotos, "--output_path", sp, "--Mapper.image_list_path", lp, "--Mapper.num_threads", str(faeden),
                            "--Mapper.ba_use_gpu", "0", "--Mapper.abs_pose_min_num_inliers", str(ABS_POSE_MIN), "--Mapper.abs_pose_min_inlier_ratio", "0.1"]
    with open(os.path.join(aus, "mapper.log"), "w") as lg: rc = subprocess.call(cmd, stdout=lg, stderr=subprocess.STDOUT)
    return rc, sorted(os.path.join(sp, d) for d in os.listdir(sp) if os.path.isfile(os.path.join(sp, d, "images.bin")))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0]); [ap.add_argument(k) for k in ("a", "b", "db", "seiten", "fotos")]; ap.add_argument("--aus", required=True)
    ap.add_argument("--faeden", type=int, default=max(1, (os.cpu_count() or 2) // 2)); a = ap.parse_args(argv); os.makedirs(a.aus, exist_ok=True); import pycolmap
    def ende(rc, urteil, **kw):
        d = dict(rc=rc, ok=rc == 0, urteil=urteil, **kw); json.dump(d, open(os.path.join(a.aus, "eck.json"), "w"), indent=1, ensure_ascii=False); print(("ECK-KOPPLUNG: " if rc == 0 else "ECK-KOPPLUNG NICHT: ") + urteil); return rc
    rA, rB = pycolmap.Reconstruction(a.a), pycolmap.Reconstruction(a.b)
    A = {im.name for im in rA.images.values() if im.has_pose}; B = {im.name for im in rB.images.values() if im.has_pose}
    br, liste = eckbilder(json.load(open(a.seiten)), A, B, a.db)
    if not br: return ende(2, "keine bestaetigten Brueckenpaare zwischen den Teilen (seiten.json 'durchblick')")
    rc, mods = eckmodell(liste, a.db, a.fotos, a.aus, a.faeden)
    if not mods: return ende(2, f"kein Eckmodell (Mapper rc {rc}, {len(liste)} Eckbilder)", brueckenpaare=len(br), eckbilder=len(liste))
    best = None
    for m in mods:
        rE = pycolmap.Reconstruction(m); E = {im.name for im in rE.images.values() if im.has_pose}; na, nb = len(E & A), len(E & B)
        if na >= 3 and nb >= 3 and (best is None or na + nb > best[1]): best = (m, na + nb, rE, na, nb)
    if best is None: return ende(2, f"kein Eckmodell mit >= 3 Bildern aus BEIDEN Teilen ({len(mods)} Modelle, {len(liste)} Eckbilder) - die Bruecke traegt nicht", brueckenpaare=len(br))
    m, _, rE, na, nb = best; Pe = np.array([p.xyz for p in rE.points3D.values()]); ausd = ausdehnung(Pe)
    Xe, Xa, _ = punkte(rE, rA); Ma, pa, oka, ga = kopplung_pruefen(Xe, Xa, ausd)
    Ye, Yb, _ = punkte(rE, rB); Mb, pb, okb, gb = kopplung_pruefen(Ye, Yb, ausd)
    pr = dict(eckmodell=m, bilder_a=na, bilder_b=nb, ausdehnung=round(ausd, 4), eck_nach_a=pa, eck_nach_b=pb, brueckenpaare=len(br), eckbilder=len(liste))
    if not (oka and okb): return ende(3, f"Kopplung nicht stimmig - Ecke->A: {ga}; Ecke->B: {gb}", pruefung=pr)
    B_nach_A = Ma @ np.linalg.inv(Mb)
    return ende(0, f"Teil B ueber das Eckmodell gekoppelt ({na} + {nb} gemeinsame Bilder; Ecke->A {pa['stimmig']}/{pa['punkte']}, Ecke->B {pb['stimmig']}/{pb['punkte']} Punkte stimmig)",
                pruefung=pr, B_nach_A=B_nach_A.tolist())


if __name__ == "__main__": sys.exit(main())
