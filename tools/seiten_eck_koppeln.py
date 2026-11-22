#!/usr/bin/env python3
"""seiten_eck_koppeln.py <db_mapper> <seiten.json> <fotos> --teil N=<modell> [--teil M=<modell> ...] --aus <ordner>   (erster --teil = Teil A, Bezugsrahmen)

TEILE UEBER BRUECKEN-ZWISCHENMODELLE KOPPELN (22.11.2026, erst schwabentor-1122, dann verallgemeinert; Nutzer: "Ich will es jetzt generalisiert geloest.").
WANN: nur wenn die Bilder NICHT von selbst ein Modell ergeben. Reihenfolge in der Kette: (1) normaler Weg - ein Modell aus allen Bildern; (2) zerfaellt es in Teile
(seiten_erkennen/sfm_seiten_modelle), sucht seiten_erkennen --durchblick bestaetigte Brueckenpaare zwischen den Gruppen; (3) erst wenn die Klappung (seiten_vereinen)
einen Teil NICHT anbindet, koppelt diese Stufe ueber die Brueckenpaare; (4) sonst GPS-Weg / Fotoluecke. Ein zusammenhaengendes Modell (ein Teil) wird nie veraendert
(rc 2, kein Ergebnis; Test). Befund 1122: der GLOBALE Mapper ueber alle Bilder knickte Teil 1 an der Bruecke um 25 Grad, ein Anbau mit --input_path registrierte 0 Bilder.
ABLAUF (beliebig viele Teile, Bruecken jeder Art):
  1. KNOTEN = alle Teilmodelle. BRUECKEN = Durchblick-Paare (seiten.json 'durchblick', urteil 'durchblick', inkl. 'Bruecke erweitern'), die nicht ganz in einem Teil liegen.
     Zusammenhangsstuecke der Brueckenpaare (ueber gemeinsame Bilder), die >= 2 Teile beruehren, sind KANDIDATEN; Stuecke an nur einem Teil zaehlen nicht (1122: Paare
     zwischen Videobildern ausserhalb aller Teile zogen sonst 124 Bilder in 3 getrennte Modelle).
  2. ZWISCHENMODELL je Kandidat: Brueckenbilder + NACHBAR_TIEFE Schritte starker Nachbarn (je NACHBARN_JE_BILD, >= NACHBAR_MIN Inlier), schrittweiser COLMAP-Mapper.
     SCHWELLE abs_pose_min_num_inliers NICHT frei gewaehlt: der Reihe nach SCHWELLEN (30 = COLMAP-Standard, 20, 15, 12, 10); genommen wird die STRENGSTE, bei der ein Modell
     >= MIN_BILDER_TEIL Bilder aus >= 2 beruehrten Teilen enthaelt. Die naechst lockerere Schwelle wird zur SENSITIVITAET mitgerechnet: Kopplung (Drehung, Massstab,
     Versatz) bei beiden Schwellen im Stufen-JSON ('sensitivitaet'). 1122: 30 und 15 zerfallen, 12 verbindet. Untergrenze 10: ANNAHME (P3P braucht 4; < 10 Inlier je
     Bild ist im Mapper-Log nicht mehr von Fehlregistrierung zu trennen).
  3. KOPPLUNG Zwischenmodell -> jeder beruehrte Teil ueber GEMEINSAME 3D-PUNKTE (gleicher Bildpunkt gemeinsamer Bilder), robuste Sim3 (sim3_robust.sim3_meter, Schwelle
     SCHWELLE_REL x Ausdehnung). Stimmig nur bei >= MIN_PUNKTE stimmigen Punkten, Anteil >= MIN_ANTEIL, Rest <= REST_REL x Ausdehnung, Massstab Haelften-Probe <= MASS_REL
     (sonst 'Massstab nicht belegt'); Hebel = Ausdehnung der gemeinsamen Punkte / Ausdehnung des Teils. Begruendung 1122: Ecke->A 96 % stimmig, Rest 0,34 %, Ecke->B
     96 %, 0,21 %; Zufall / andere Flaeche -> keine Sim3; 8 % Verformung -> Anteil 53 % (Test).
     KANTE i-j = zwei stimmige Kopplungen desselben Zwischenmodells; Guete = min(stimmig x Hebel).
  4. STAERKSTER SPANNBAUM ab Teil A (Prim, groesste Guete zuerst) -> Lage jedes erreichten Teils im Rahmen von A. Jede weitere Kante schliesst einen KREIS = unabhaengige
     Pruefung: Kreisschlussfehler (Drehung Grad, Massstab, Versatz relativ zur Ausdehnung) gegen 3 x sigma, sigma = Wurzel der Quadratsumme der Kopplungsreste und
     Haelften-Proben aller Kanten im Kreis (ANNAHME: Rest = 1 sigma). Widerspruch -> alle Teile des Kreises (ausser A) und was nur durch sie erreicht wird: NICHT gekoppelt.
  5. Ausgabe <aus>/eck.json: teile{N: ok, M_nach_A (4x4), weg, massstab_unsicher}, kanten, kreise, zwischenmodelle, fotoluecken (Teil + gewuenschte Verbindung).
     rc 0 = mindestens ein Teil gekoppelt, 2 = nichts zu koppeln (ein Teil / keine Bruecke / kein Zwischenmodell), 3 = Kandidaten, aber keine stimmige Kopplung.
Danach (sfm_seiten_modelle): Blick-Tor + GPS-Seiten-Tor (Veto); wand_dicke/Grundriss als Tore der Kette nach der Ausrichtung."""
import os, sys, json, argparse, sqlite3, subprocess, shutil, numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
from sim3_robust import sim3_meter, umeyama

MAXID = 2147483647
NACHBAR_MIN = 200        # wie DURCH_MIN_INLIER: nur starke Nachbarpaare ziehen Bilder ins Zwischenmodell
NACHBARN_JE_BILD = 5     # ANNAHME: je Bild die 5 staerksten Nachbarn, zwei Schritte weit; alle Nachbarn >= 200 = 196 Bilder (1122, > 10 min), ein Schritt = 14 Bilder (nur 2 Teil-0-Bilder)
NACHBAR_TIEFE = 2
SCHWELLEN = (30, 20, 15, 12, 10)   # abs_pose_min_num_inliers: strengste verbindende gewinnt (Kopf 2)
MIN_BILDER_TEIL = 3
MIN_PUNKTE = 100
MIN_ANTEIL = 0.8
REST_REL = 0.005         # ANNAHME: 0,5 % der Zwischenmodell-Ausdehnung (1122: 0,21-0,34 %)
SCHWELLE_REL = 0.02      # Inlier-Schwelle der Sim3: 2 % der Ausdehnung
MASS_REL = 0.02          # Massstab-Unsicherheit (Haelften-Probe) hoechstens 2 %
KREIS_SIGMA = 3.0
COLMAP = os.environ.get("RCPARK_COLMAP", "/media/oem/scan/colmap-build/prefix/bin/colmap")
NAMEN = {}               # Teil -> registrierte Bildnamen (main)


def ausdehnung(X):
    X = np.asarray(X, float); return float(np.percentile(np.linalg.norm(X - np.median(X, 0), axis=1), 90)) if len(X) else 0.0


def winkel(R): return float(np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1))))


def zerlegen(M):
    """4x4 Sim3 -> (s, R, t)."""
    M = np.asarray(M, float); s = float(np.cbrt(np.linalg.det(M[:3, :3]))); return s, M[:3, :3] / s, M[:3, 3]


def punkte(rE, rZ):
    """Gemeinsame 3D-Punkte (Bildname + Keypoint-Index gemeinsamer Bilder, in beiden Modellen trianguliert) -> (X_eck, X_ziel, gemeinsame Bilder)."""
    E = {im.name: im for im in rE.images.values() if im.has_pose}; Z = {im.name: im for im in rZ.images.values() if im.has_pose}; pe, pz, ges = [], [], set(); ns = sorted(set(E) & set(Z))
    for n in ns:
        a_, b_ = E[n].points2D, Z[n].points2D
        for k in range(min(len(a_), len(b_))):
            if a_[k].has_point3D() and b_[k].has_point3D() and (a_[k].point3D_id, b_[k].point3D_id) not in ges:
                ges.add((a_[k].point3D_id, b_[k].point3D_id)); pe.append(rE.points3D[a_[k].point3D_id].xyz); pz.append(rZ.points3D[b_[k].point3D_id].xyz)
    return np.array(pe).reshape(-1, 3), np.array(pz).reshape(-1, 3), ns


def kopplung_pruefen(X, Y, ausd, ausd_ziel=None):
    """Sim3 X -> Y (X im Zwischenmodell, Y im Teilmodell; ausd = Ausdehnung des Zwischenmodells, ausd_ziel = des Teils fuer den Hebel). -> (M, pruefung, ok, grund)."""
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
    if ausd_ziel: pr["hebel"] = round(ausdehnung(Y[i_]) / max(ausd_ziel, 1e-12), 3)
    gr = [x for x, schlecht in ((f"Anteil stimmig {ant:.0%} < {MIN_ANTEIL:.0%}", ant < MIN_ANTEIL), (f"stimmig {f['n_inlier']} < {MIN_PUNKTE}", f["n_inlier"] < MIN_PUNKTE),
                                (f"Rest {rest_rel:.2%} der Ausdehnung > {REST_REL:.1%}", rest_rel > REST_REL), (f"Massstab nicht belegt (Haelften {hael:.1%} > {MASS_REL:.0%})", hael > MASS_REL)) if schlecht]
    return f["M"], pr, not gr, "; ".join(gr) or "stimmig"


def nachbarn(db):
    c = sqlite3.connect(f"file:{db}?immutable=1", uri=True); nm = {i: n for i, n in c.execute("select image_id, name from images")}; nb = {}
    for pid, r in c.execute("select pair_id, rows from two_view_geometries where rows >= ?", (NACHBAR_MIN,)):
        a, b = nm.get(pid // MAXID), nm.get(pid % MAXID)
        if a and b: nb.setdefault(a, []).append((r, b)); nb.setdefault(b, []).append((r, a))
    return nb


def kandidaten(sj, teil_von, db):
    """Bruecken-Zusammenhangsstuecke, die >= 2 Teile beruehren. teil_von: Bildname -> Teil. -> [dict(paare, teile, bilder)] (bilder = Bruecke + Nachbarn)."""
    br = [d for d in (sj.get("durchblick") or []) if d.get("urteil") == "durchblick" and not (d["a"] in teil_von and teil_von.get(d["a"]) == teil_von.get(d["b"]))]
    eltern = {}
    def wurzel(x):
        while eltern.setdefault(x, x) != x: x = eltern[x]
        return x
    for d in br: eltern[wurzel(d["a"])] = wurzel(d["b"])
    stuecke = {}
    for d in br: stuecke.setdefault(wurzel(d["a"]), []).append(d)
    aus = []; nb = None
    for paare in stuecke.values():
        kern = {d["a"] for d in paare} | {d["b"] for d in paare}; teile = sorted({teil_von[x] for x in kern if x in teil_von})
        if len(teile) < 2: continue
        if nb is None: nb = nachbarn(db)
        bil = set(kern); rand = set(kern)
        for _ in range(NACHBAR_TIEFE):                                                 # Nachbarn der Nachbarn: das Zwischenmodell braucht >= 3 Bilder je Teil mit vielen Punkten
            neu = {x for k in rand for _, x in sorted(nb.get(k, []), reverse=True)[:NACHBARN_JE_BILD]} - bil; bil |= neu; rand = neu
        aus.append(dict(paare=paare, teile=teile, bilder=sorted(bil)))
    return aus


def eckbilder(sj, A, B, db):
    """Kompatibel (zwei Teile): -> (Brueckenpaare, Bilder) der Stuecke zwischen A und B."""
    tv = {**{n: 0 for n in A}, **{n: 1 for n in B}}; ks = kandidaten(sj, tv, db)
    return [d for k in ks for d in k["paare"]], sorted({x for k in ks for x in k["bilder"]})


def mapper(liste, db, fotos, aus, faeden, schwelle):
    os.makedirs(aus, exist_ok=True); lp = os.path.join(aus, "bilder.txt"); open(lp, "w").write("\n".join(liste) + "\n"); sp = os.path.join(aus, "sparse")
    if os.path.isdir(sp): shutil.move(sp, sp + ".alt_" + str(int(os.path.getmtime(sp))))
    os.makedirs(sp); cmd = [COLMAP, "mapper", "--database_path", db, "--image_path", fotos, "--output_path", sp, "--Mapper.image_list_path", lp, "--Mapper.num_threads", str(faeden),
                            "--Mapper.ba_use_gpu", "0", "--Mapper.abs_pose_min_num_inliers", str(schwelle), "--Mapper.abs_pose_min_inlier_ratio", "0.1"]
    from sfm_seiten_modelle import CUDA_LIBS                                            # die COLMAP-Binaerdatei braucht die CUDA-Bibliotheken (auch ausserhalb der Kette)
    env = dict(os.environ, LD_LIBRARY_PATH=":".join(CUDA_LIBS + [x for x in [os.environ.get("LD_LIBRARY_PATH", "")] if x]))
    with open(os.path.join(aus, "mapper.log"), "w") as lg: rc = subprocess.call(cmd, stdout=lg, stderr=subprocess.STDOUT, env=env)
    return rc, sorted(os.path.join(sp, d) for d in os.listdir(sp) if os.path.isfile(os.path.join(sp, d, "images.bin")))


def koppeln(m, teile, R, P, ausd_teil):
    """Zwischenmodell m an alle Teile koppeln. -> (info, {teil: (M_teil_von_E, pruefung)} nur stimmige, alle pruefungen)."""
    import pycolmap
    rE = pycolmap.Reconstruction(m); ausd = ausdehnung([p.xyz for p in rE.points3D.values()]); gut, alle = {}, {}
    for t in teile:
        X, Y, ns = punkte(rE, R[t])
        if len(ns) < MIN_BILDER_TEIL: alle[t] = dict(bilder=len(ns), grund=f"nur {len(ns)} gemeinsame Bilder"); continue
        M, pr, ok, g = kopplung_pruefen(X, Y, ausd, ausd_teil[t]); pr.update(bilder=len(ns), grund=g); alle[t] = pr
        if ok: gut[t] = (M, pr)
    return dict(modell=m, ausdehnung=round(ausd, 4)), gut, alle


def zwischenmodell(k, i, db, fotos, aus, faeden, R, ausd_teil):
    """Strengste verbindende Schwelle + Sensitivitaet an der naechst lockereren. -> dict"""
    import pycolmap
    erg = dict(teile=k["teile"], brueckenpaare=len(k["paare"]), bilder=len(k["bilder"]), versuche=[]); treffer = []
    for s in SCHWELLEN:
        rc, mods = mapper(k["bilder"], db, fotos, os.path.join(aus, f"zwischen{i}_s{s}"), faeden, s); best = None
        for m in mods:
            E = {im.name for im in pycolmap.Reconstruction(m).images.values() if im.has_pose}; je = {t: len(E & NAMEN[t]) for t in k["teile"]}
            n2 = sum(v >= MIN_BILDER_TEIL for v in je.values())
            if n2 >= 2 and (best is None or (n2, sum(je.values())) > best[0]): best = ((n2, sum(je.values())), m, je)
        erg["versuche"].append(dict(schwelle=s, modelle=len(mods), bilder_je_teil=best[2] if best else None))
        if best: treffer.append((s, best[1]))
        if len(treffer) == 2: break
    if not treffer: erg["grund"] = f"kein Zwischenmodell mit >= {MIN_BILDER_TEIL} Bildern aus >= 2 Teilen (Schwellen {list(SCHWELLEN)})"; return erg
    s0, m0 = treffer[0]; info, gut, alle = koppeln(m0, k["teile"], R, None, ausd_teil); erg.update(schwelle=s0, kopplungen={str(t): v for t, v in alle.items()}, **info); erg["_gut"] = gut
    if len(treffer) > 1:
        _, gut1, _ = koppeln(treffer[1][1], k["teile"], R, None, ausd_teil); sens = []
        ts = sorted(set(gut) & set(gut1))
        for x in ts[1:]:
            D = (gut[ts[0]][0] @ np.linalg.inv(gut[x][0])) @ np.linalg.inv(gut1[ts[0]][0] @ np.linalg.inv(gut1[x][0])); s, Rr, t = zerlegen(D)
            sens.append(dict(kante=[ts[0], x], drehung_grad=round(winkel(Rr), 3), massstab_rel=round(abs(s - 1), 4), versatz_rel=round(float(np.linalg.norm(t)) / max(ausd_teil[ts[0]], 1e-12), 4)))
        erg["sensitivitaet"] = dict(schwelle=treffer[1][0], vergleich=sens or "zu wenige stimmige Kopplungen bei der lockereren Schwelle")
    else: erg["sensitivitaet"] = dict(schwelle=None, vergleich="keine lockerere Schwelle verbindet")
    return erg


def spannbaum(teile, kanten, a):
    """Prim ab a ueber die groesste Guete. kanten: [dict(i, j, M_i_von_j, guete, sigma)]. -> (lage {teil: M_a_von_teil}, weg {teil: [kantenindex]}, Baumkanten-Indizes)."""
    lage = {a: np.eye(4)}; weg = {a: []}; baum = set()
    while True:
        best = None
        for n, k in enumerate(kanten):
            for x, y, M in ((k["i"], k["j"], k["M"]), (k["j"], k["i"], np.linalg.inv(k["M"]))):   # M: j -> i
                if x in lage and y not in lage and (best is None or k["guete"] > best[0]): best = (k["guete"], n, x, y, M)
        if best is None: return lage, weg, baum
        _, n, x, y, M = best; lage[y] = lage[x] @ M; weg[y] = weg[x] + [n]; baum.add(n)


def kreise_pruefen(kanten, lage, weg, baum, ausd_teil):
    """Jede Nicht-Baumkante zwischen zwei erreichten Teilen = Kreis. -> [dict(kante, teile, drehung_grad, massstab_rel, versatz_rel, grenze, ok)]"""
    aus = []
    for n, k in enumerate(kanten):
        if n in baum or k["i"] not in lage or k["j"] not in lage: continue
        D = np.linalg.inv(lage[k["i"]] @ k["M"]) @ lage[k["j"]]; s, R, t = zerlegen(D)          # j -> j um den Kreis
        im_kreis = sorted(set(weg[k["i"]]) ^ set(weg[k["j"]]) | {n}); sig = float(np.sqrt(sum(kanten[m]["sigma"] ** 2 for m in im_kreis))); g = KREIS_SIGMA * sig
        f = dict(drehung_grad=round(winkel(R), 3), massstab_rel=round(abs(s - 1), 4), versatz_rel=round(float(np.linalg.norm(t)) / max(ausd_teil[k["j"]], 1e-12), 4))
        ok = np.radians(f["drehung_grad"]) <= g and f["massstab_rel"] <= g and f["versatz_rel"] <= g
        teile = sorted({kanten[m]["i"] for m in im_kreis} | {kanten[m]["j"] for m in im_kreis})
        aus.append(dict(kante=n, kanten=im_kreis, teile=teile, grenze=round(g, 4), ok=bool(ok), **f))
    return aus


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0]); [ap.add_argument(k) for k in ("db", "seiten", "fotos")]; ap.add_argument("--aus", required=True)
    ap.add_argument("--teil", action="append", required=True, help="N=<modell>, erster = Teil A"); ap.add_argument("--faeden", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    a = ap.parse_args(argv); os.makedirs(a.aus, exist_ok=True)
    tl = [(int(x.split("=", 1)[0]), x.split("=", 1)[1]) for x in a.teil]; A = tl[0][0]
    def ende(rc, urteil, **kw):
        d = dict(rc=rc, ok=rc == 0, urteil=urteil, teil_a=A, **kw); json.dump(d, open(os.path.join(a.aus, "eck.json"), "w"), indent=1, ensure_ascii=False)
        print(("ECK-KOPPLUNG: " if rc == 0 else "ECK-KOPPLUNG NICHT: ") + urteil); return rc
    if len(tl) < 2: return ende(2, "nur ein Teil - nichts zu koppeln (zusammenhaengendes Modell bleibt unveraendert)")
    import pycolmap
    R, teil_von, ausd_teil = {}, {}, {}
    for t, p in tl:
        r = pycolmap.Reconstruction(p); ns = {im.name for im in r.images.values() if im.has_pose}; R[t] = r; NAMEN[t] = ns
        for n in ns: teil_von.setdefault(n, t)
        ausd_teil[t] = ausdehnung([q.xyz for q in r.points3D.values()])
    ks = kandidaten(json.load(open(a.seiten)), teil_von, a.db)
    luecke = lambda erreicht, extra={}: [dict(teil=t, verbindung=extra.get(t) or f"Fotos, die Teil {t} und einen gekoppelten Teil gemeinsam zeigen (Uebergang um die Ecke, Schritte <= 30 Grad)")
                                         for t, _ in tl if t not in erreicht]
    if not ks: return ende(2, "keine bestaetigten Brueckenpaare zwischen den Teilen (seiten.json 'durchblick')", fotoluecken=luecke({A}))
    zw, kanten = [], []
    for i, k in enumerate(ks):
        z = zwischenmodell(k, i, a.db, a.fotos, a.aus, a.faeden, R, ausd_teil); gut = z.pop("_gut", {}); zw.append(z); ts = sorted(gut)
        for x in range(len(ts)):
            for y in range(x + 1, len(ts)):
                (Mi, pi), (Mj, pj) = gut[ts[x]], gut[ts[y]]
                sig = float(np.sqrt(sum(p_["rest_rel"] ** 2 + p_["massstab_haelften_rel"] ** 2 for p_ in (pi, pj))))
                kanten.append(dict(i=ts[x], j=ts[y], M=Mi @ np.linalg.inv(Mj), zwischenmodell=i, sigma=sig,
                                   guete=float(min(pi["stimmig"] * pi.get("hebel", 1), pj["stimmig"] * pj.get("hebel", 1)))))
    lage, weg, baum = spannbaum([t for t, _ in tl], kanten, A); kr = kreise_pruefen(kanten, lage, weg, baum, ausd_teil)
    raus = set()
    for c in kr:
        if not c["ok"]: raus |= {t for t in lage if t != A and set(weg[t]) & set(c["kanten"])}
    teile = {}
    for t, _ in tl:
        if t == A: continue
        if t in lage and t not in raus:
            teile[str(t)] = dict(ok=True, M_nach_A=lage[t].tolist(), weg=[[kanten[n]["i"], kanten[n]["j"]] for n in weg[t]], massstab_unsicher=round(float(np.sqrt(sum(kanten[n]["sigma"] ** 2 for n in weg[t]))), 4))
        else: teile[str(t)] = dict(ok=False, grund="Kreisschluss-Widerspruch" if t in raus else "keine stimmige Kopplung")
    kj = [dict(i=k["i"], j=k["j"], zwischenmodell=k["zwischenmodell"], guete=round(k["guete"], 1), sigma=round(k["sigma"], 5), im_baum=n in baum) for n, k in enumerate(kanten)]
    erreicht = {A} | {int(t) for t, v in teile.items() if v["ok"]}
    fl = luecke(erreicht, {t: f"Bruecke zu Teil(en) {[x for x in z['teile'] if x != t]} vorhanden, Kopplung nicht stimmig ({z.get('grund') or '; '.join(f'Teil {tk}: ' + str(v.get('grund')) for tk, v in (z.get('kopplungen') or {}).items() if v.get('grund') != 'stimmig')}) - mehr Fotos dieses Uebergangs"
                           for z in zw for t in z["teile"]})
    rc = 0 if len(erreicht) > 1 else (3 if kanten or any(z.get("kopplungen") for z in zw) else 2)
    txt = (f"Teile {sorted(erreicht - {A})} an Teil {A} gekoppelt ({len(kanten)} Kanten, {len(kr)} Kreise{', Widerspruch' if raus else ''})" if rc == 0 else
           "keine stimmige Kopplung" if rc == 3 else "kein Zwischenmodell aus >= 2 Teilen - die Bruecke traegt nicht")
    return ende(rc, txt, teile=teile, kanten=kj, kreise=kr, zwischenmodelle=zw, fotoluecken=fl)


if __name__ == "__main__": sys.exit(main())
