#!/usr/bin/env python3
"""wolke_draehte.py - duenne linienhafte Strukturen FREI IM RAUM aus der dichten Wolke nehmen (Draehte, Oberleitung, Spann-/Tragseile) - nur fuer die ANZEIGE.

Anlass 24.11.2026 (Nutzer am 3D-Artifact schwabentor-1122, Ebene "Dichte Wolke (Fotofarben)"): neben der Nordseite eine Fehlerwolke aus diagonalen
duennen Linien (Strassenbahn-Oberleitung + Spanndraehte vor dem Turm, y-z-Schnitt schraeg (y10,z15)->(y20,z8), x-z-Strich (x3,z10)->(x6,z25)) und ein
schraeger Strich oben an der Spitze (z 40-50). Die Wolke ist nur Lage-Veto; die Anzeige (tools/modell_3d_html.py) soll sie aber nicht als Gebaeude zeigen.
Vorher gab es keinen Draht-Filter fuer die WOLKE (grep draht/kabel/oberleitung: nur Bildmasken - dach_aus_fotos Schliessung 9 px, drehkoerper_aus_fotos
Himmelslauf, befundliste Kantenzuege ausserhalb der Modellflaeche, haufen_klaeren Wandblatt-Merkmal fuer das Grundriss-Tor).

BEFUND AM ECHTEN AUSSCHNITT (Nordturm 1122, 1 Punkt je 10-cm-Voxel): die Oberleitung steht in der dichten Wolke NUR selten als duenne Linie
(z. B. 5-m-Draht schraeg ueber der Wand, Fahrdraht im Tor z ~6,5); meist als schmales schraeges BLATT ("Fahne", 0,7-0,8 m breit, 4 m lang): die
Tiefe eines Drahts ist quer zur Blickrichtung unsicher, MVS verschmiert ihn laengs der Sichtstrahlen. Darum zwei Stufen:
VERFAHREN (dichte-unabhaengig, weil auf belegten Voxeln statt Punkten gezaehlt wird):
  1. Voxel (Kante v = 0,10 m), belegt ab 1 Punkt; Mittelpunkte = Analyseeinheiten.
  2. LINIEN: lokale PCA je Voxel im Radius r = 0,5 m: Linearitaet 1 - l2/l1 >= 0,7 und hoechstens 4,5 x Linienwert (2r/v+1) belegte Nachbarn;
     Gegenprobe im weiten Radius R = 1,2 m: Anteil der Nachbarn auf der lokalen Linie (<= 0,25 m) >= 0,45 - Gesims, Dachkante, Sturz haengen an
     Wand/Dach -> viele Nachbarn neben der Linie -> bleibt. Zusammenhang (<= 2,5 v); Zug >= 1,5 m lang und mehr als 20 Grad von der Lotrechten.
     LOTRECHTE Zuege bleiben immer (Wetterstange, Turmspitze, Blitzableiter, Mast). Saum (Drahtenden) mit halber Schwelle.
  3. FAHNEN: Blatt-Voxel (l3/l2 <= 0,2) mit aehnlicher Normale (cos >= 0,9) verbunden -> Segmente; Fahne = >= 2,5 m lang, <= 1,5 m breit, 2,5x so
     lang wie breit, SCHRAEG (Blattnormale |n_z| 0,25..0,95: lotrechte Wandstreifen zwischen Gesimsen und waagrechte Gesimsoberseiten bleiben) und
     NICHT GETRAGEN: liegen die Nachbarn ausserhalb der Blattebene (<= 0,7 m) auf EINEM grossen Blatt (l3/l2 <= 0,2, >= 2 m breit im 2-m-Umkreis
     = Wand/Dach), bleibt der Streifen (angebundenes Vordach, Gesims). Bis zu 3 Durchgaenge (eine Fahne, die nur eine andere Fahne beruehrte).
GRENZEN: Draht/Fahne naeher als ~0,7-1,2 m an Wand oder Vordach bleibt (lieber stehen lassen als Gebaeude fressen); lotrechte Fahnen (Draht aus
  waagrechter Blickrichtung) bleiben; das dichte Gewirr direkt an der Turmwand ist so nicht trennbar (braucht Sichtbarkeit: Punkt verdeckt die Wand
  in Fotos, die die Wand sehen). Der "Strich an der Spitze" (x-z schraeg z 39-48) ist die nach +x geneigte DACHFLAECHE (Draufsicht Dreieck, Basis an
  der Traufe x 3,3, y 10-20) von der Kante gesehen - echt, bleibt (kein Streifen).
ORIGINAL BLEIBT: geschrieben wird eine gefilterte Kopie (gleiche Dateinamen in --aus), Bericht-JSON und Kontrollbild.

Aufruf: tools/py tools/wolke_draehte.py WOLKE.npy [--farben F.npy] --aus ORDNER [--bericht B.json] [--bild K.jpg]
"""
import argparse, json, os, sys, time
import numpy as np

VOXEL = 0.10; R_LOKAL = 0.5; R_WEIT = 1.2; MIN_LIN = 0.7; N_LINIE_FAKTOR = 4.5; AUF_TOL = 0.25; MIN_AUF = 0.45; MIN_LAENGE = 1.5; LOT_GRAD = 20.0
# Fahnen (Draht als schmales Blatt verschmiert, 24.11.: Strich an der Spitze 1,1 m x 0,45 m x 0,1 m)
MAX_DUENN = 0.2; NORMAL_COS = 0.9; FAHNE_MIN_LAENGE = 2.5; FAHNE_MAX_BREITE = 1.5; FAHNE_SCHLANK = 2.5; FAHNE_ANBINDUNG_M = 0.7; FAHNE_TRAEGER_DUENN = 0.2; FAHNE_TRAEGER_M = 2.0; FAHNE_NZ = (0.25, 0.95)   # Blattnormale: |n_z| < 0,25 = lotrechtes Blatt (Wandstreifen), > 0,95 = waagrecht (Gesimsoberseite, Flachdach) -> bleibt


def _pca(P, nb, gueltig):
    """P (m,3) Voxelmitten, nb (k,K) Nachbarindizes, gueltig (k,K) Maske -> n, Eigenwerte (k,3) aufsteigend, Eigenvektoren (k,3,3) Spalten, Schwerpunkt."""
    w = gueltig.astype(np.float64); n = w.sum(1); nn = np.maximum(n, 1)[:, None]
    Q = P[np.where(gueltig, nb, 0)]                                                     # (k,K,3)
    mu = (Q * w[..., None]).sum(1) / nn
    d = (Q - mu[:, None, :]) * w[..., None]
    C = np.einsum("kia,kib->kab", d, d) / nn[..., None]
    l, e = np.linalg.eigh(C)
    return n, np.maximum(l, 0), e, mu


def merkmale(V, voxel=VOXEL, r=R_LOKAL, R=R_WEIT, min_lin=MIN_LIN, n_faktor=N_LINIE_FAKTOR, auf_tol=AUF_TOL, workers=2, block=50000):
    """Je Voxelmitte: n (belegte Nachbarvoxel in r), lin = 1 - l2/l1 (Linie ~1, Flaeche/Koerper klein), achse; fuer lokale Linienkandidaten
    (lin >= min_lin, n <= n_faktor x Linienwert 2r/v+1) zusaetzlich auf = Anteil der Nachbarn in R, die auf der Linie liegen (Abstand <= auf_tol).
    Dazu duenn = l3/l2 (Blatt ~0, Linie/Koerper ~1) und normale (lokale Blattnormale) fuer die Fahnen-Stufe.
    Rueckgabe n, lin, auf (nicht geprueft = 0), n_max, duenn, normale, Baum."""
    from scipy.spatial import cKDTree
    tree = cKDTree(V); M = len(V)
    n_max = int(round(n_faktor * (2 * r / voxel + 1)))                                  # mehr belegte Nachbarn = mehr als ein dicker Draht -> keine Linie
    K = int(np.ceil(1.6 * np.pi * r * r / voxel ** 2)) + 1                               # volle Flaeche + Rauschen
    n_r = np.zeros(M, np.int32); lin = np.zeros(M, np.float32); ach = np.zeros((M, 3), np.float64); mu = np.zeros((M, 3), np.float64)
    duenn = np.ones(M, np.float32); nrm = np.zeros((M, 3), np.float32)
    for s in range(0, M, block):
        sl = slice(s, s + block); dd, ii = tree.query(V[sl], k=K, distance_upper_bound=r, workers=workers); g = np.isfinite(dd)
        n_, l_, e_, m_ = _pca(V, ii, g); n_r[sl] = n_; lin[sl] = 1 - l_[:, 1] / np.maximum(l_[:, 2], 1e-12); ach[sl] = e_[:, :, 2]; mu[sl] = m_
        duenn[sl] = l_[:, 0] / np.maximum(l_[:, 1], 1e-12); nrm[sl] = e_[:, :, 0]
    lin[(n_r < 5) | (n_r > n_max)] = 0
    kand = np.flatnonzero(lin >= min_lin); auf = np.zeros(M, np.float32)
    Kw = int(round(n_faktor * 2 * (2 * R / voxel + 1))) + 1                             # weite Kappe: doppelter dicker Draht; erreicht -> Struktur ringsum
    for s in range(0, len(kand), block):
        ki = kand[s:s + block]; dd, ii = tree.query(V[ki], k=Kw, distance_upper_bound=R, workers=workers); g = np.isfinite(dd)
        Q = V[np.where(g, ii, 0)] - mu[ki][:, None, :]; a_ = ach[ki]
        quer = np.linalg.norm(Q - (Q * a_[:, None, :]).sum(2)[..., None] * a_[:, None, :], axis=2)
        auf[ki] = np.where(g[:, -1], 0.0, ((quer <= auf_tol) & g).sum(1) / np.maximum(g.sum(1), 1))
    return n_r, lin, auf, n_max, duenn, nrm, tree


def _fahnen(V, n_r, duenn, nrm, tree, frei, voxel, lot_grad, info, workers=2):
    """Fahnen = schmale, lange, freie Blaetter (Draht in der dichten Wolke als Band verschmiert). Blatt-Voxel (duenn) mit aehnlicher Normale
    verbunden -> Segmente; Fahne, wenn lang (>= FAHNE_MIN_LAENGE), schmal (<= FAHNE_MAX_BREITE), schlank und FREI: Nachbarvoxel neben dem Blatt
    und nicht getragen: liegen die Nachbarn ausserhalb der Ebene (<= 0,7 m) auf EINEM grossen Blatt (Wand/Dach, >= 2 m breit), bleibt der Streifen
    (Vordach, Gesims, Sturz). Lotrechte (Wandstreifen zwischen Gesimsen) und waagrechte Blaetter bleiben immer. Bis zu 3 Durchgaenge: eine Fahne,
    die nur von einer schon entfernten Fahne "getragen" war, faellt im naechsten Durchgang.
    Rueckgabe Voxelmaske."""
    from scipy.spatial import cKDTree
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    M = len(V); raus = np.zeros(M, bool); info["fahnen"] = []; info["fahnen_geschuetzt"] = {"lotrecht": 0, "wand_oder_waagrecht": 0, "angebunden": 0}
    kb = np.flatnonzero(frei & (n_r >= 8) & (duenn <= MAX_DUENN))
    if len(kb) < 2: return raus
    pr = cKDTree(V[kb]).query_pairs(1.75 * voxel + 1e-9, output_type="ndarray")
    if len(pr): pr = pr[np.abs((nrm[kb[pr[:, 0]]] * nrm[kb[pr[:, 1]]]).sum(1)) >= NORMAL_COS]
    nc, lab = connected_components(coo_matrix((np.ones(len(pr)), (pr[:, 0], pr[:, 1])), shape=(len(kb), len(kb))), directed=False)
    gr = np.bincount(lab); seg = np.flatnonzero(gr >= 40); o = np.argsort(lab); st = np.r_[0, np.cumsum(gr)]
    streifen = []
    for c in seg:
        j = kb[o[st[c]:st[c + 1]]]; Q = V[j]; m_ = Q.mean(0); _, _, vt = np.linalg.svd(Q - m_, full_matrices=False)
        t1 = (Q - m_) @ vt[0]; t2 = (Q - m_) @ vt[1]
        L = float(np.percentile(t1, 98) - np.percentile(t1, 2)); W = float(np.percentile(t2, 95) - np.percentile(t2, 5))
        if L < FAHNE_MIN_LAENGE or W > FAHNE_MAX_BREITE or L < FAHNE_SCHLANK * W: continue
        neig = float(np.degrees(np.arccos(min(1.0, abs(vt[0][2]))))); nz = abs(float(vt[2][2]))
        if neig < lot_grad: info["fahnen_geschuetzt"]["lotrecht"] += 1; continue
        if not FAHNE_NZ[0] <= nz <= FAHNE_NZ[1]: info["fahnen_geschuetzt"]["wand_oder_waagrecht"] += 1; continue
        streifen.append((j, Q, m_, vt, L, W, neig))
    weg = ~frei                                                                             # schon entfernt (Draehte) zaehlt nicht als Nachbar
    for durchgang in range(3):                                                              # Fahnen-Gewirr: eine Fahne ist oft nur von einer anderen Fahne "getragen"
        neu_ = []; geschuetzt = []
        for (j, Q, m_, vt, L, W, neig) in streifen:
            nb = tree.query_ball_point(Q, FAHNE_ANBINDUNG_M, workers=workers); u = np.unique(np.concatenate([np.asarray(x, np.int64) for x in nb]))
            ims = weg.copy(); ims[j] = True; u = u[~ims[u]]
            aus_ebene = np.abs((V[u] - m_) @ vt[2]) > 0.15
            fremd = int(aus_ebene.sum())                                                    # Nachbarn ausserhalb der Blattebene (Wand, Dach, Koerper, andere Fahnen)
            # ANBINDUNG: liegen die Nachbarn ausserhalb der Ebene selbst auf EINEM Blatt (f_duenn klein), das gross ist (Breite >= FAHNE_TRAEGER_M im
            # 2-m-Umkreis) -> Wand/Dach traegt den Streifen (Vordach, Gesims) -> bleibt. Ein Gewirr anderer Fahnen ist kein grosses Blatt.
            Fq = V[u[aus_ebene]]; f_duenn = 1.0; f_breite = 0.0
            if len(Fq) >= 10:
                fm = Fq.mean(0); fl, fe = np.linalg.eigh(np.cov((Fq - fm).T)); f_duenn = float(fl[0] / max(fl[1], 1e-12))
                if f_duenn <= FAHNE_TRAEGER_DUENN:
                    ww = tree.query_ball_point(Q[::max(1, len(Q) // 200)], 2.0, workers=workers); w_ = np.unique(np.concatenate([np.asarray(x, np.int64) for x in ww]))
                    w_ = w_[~ims[w_]]; w_ = w_[np.abs((V[w_] - fm) @ fe[:, 0]) <= 0.15]
                    if len(w_) >= 10: f_breite = float(np.sqrt(12 * np.linalg.eigvalsh(np.cov((V[w_] - V[w_].mean(0)).T))[1]))
            d_ = dict(voxel=int(len(j)), laenge_m=round(L, 2), breite_m=round(W, 2), fremd_anteil=round(fremd / len(j), 2), traeger_duenn=round(f_duenn, 3),
                      traeger_breite_m=round(f_breite, 2), mitte=m_.round(2).tolist(), neigung_zur_lotrechten_grad=round(neig, 1), normale_z=round(abs(float(vt[2][2])), 2), durchgang=durchgang)
            if f_duenn <= FAHNE_TRAEGER_DUENN and f_breite >= FAHNE_TRAEGER_M: geschuetzt.append(((j, Q, m_, vt, L, W, neig), d_)); continue
            saum = u[~aus_ebene]; saum = saum[np.min(np.linalg.norm(V[saum][:, None, :] - Q[None, ::max(1, len(Q) // 400)], axis=2), axis=1) <= 0.3] if len(saum) else saum
            neu_.append((j, saum)); info["fahnen"].append(d_)
        for j, saum in neu_: raus[j] = True; raus[saum] = True; weg[j] = True; weg[saum] = True   # Rauschsaum in der Ebene (<= 0,3 m) mit
        streifen = [g[0] for g in geschuetzt]
        if not neu_ or not streifen: break
    info["fahnen_geschuetzt"]["angebunden"] = len(streifen); info["angebunden"] = [g[1] for g in geschuetzt][:50]
    info["fahnen"].sort(key=lambda z: -z["voxel"])
    return raus


def draht_maske(X, voxel=VOXEL, r=R_LOKAL, R=R_WEIT, min_lin=MIN_LIN, min_auf=MIN_AUF, min_laenge=MIN_LAENGE, lot_grad=LOT_GRAD, fahnen=True, workers=2):
    """X (N,3) Meter -> (entfernen (N,) bool, info dict mit Zuegen). Rein, kein Schreiben."""
    from scipy.spatial import cKDTree
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    X = np.asarray(X); t0 = time.time()
    k = np.floor(X / voxel).astype(np.int64); k0 = k.min(0); k -= k0
    sp = k.max(0) + 1; key = (k[:, 0] * sp[1] + k[:, 1]) * sp[2] + k[:, 2]; del k
    uk, inv = np.unique(key, return_inverse=True); del key
    V = np.c_[uk // (sp[1] * sp[2]), (uk // sp[2]) % sp[1], uk % sp[2]].astype(np.float64)
    V = (V + k0 + 0.5) * voxel; M = len(V)
    n_r, lin, auf, n_max, duenn, nrm, tree = merkmale(V, voxel, r, R, min_lin, workers=workers)
    kand = np.flatnonzero((lin >= min_lin) & (auf >= min_auf))
    info = dict(voxel_m=voxel, r_lokal_m=r, r_weit_m=R, min_linearitaet=min_lin, max_nachbarn=n_max, min_anteil_auf_linie=min_auf, min_laenge_m=min_laenge, lot_grad=lot_grad,
                punkte=int(len(X)), voxel=int(M), kandidaten_voxel=int(len(kand)), zuege=[], lotrecht_geschuetzt=0)
    vrm = np.zeros(M, bool)
    if len(kand):
        Pk = V[kand]; pr = cKDTree(Pk).query_pairs(2.5 * voxel + 1e-9, output_type="ndarray")
        A = coo_matrix((np.ones(len(pr)), (pr[:, 0], pr[:, 1])), shape=(len(kand), len(kand))) if len(pr) else coo_matrix((len(kand), len(kand)))
        nc, lab = connected_components(A, directed=False)
        for c in range(nc):
            j = np.flatnonzero(lab == c)
            if len(j) < 8: continue
            Q = Pk[j]; m_ = Q.mean(0); _, _, vt = np.linalg.svd(Q - m_, full_matrices=False); e1 = vt[0]
            t = (Q - m_) @ e1; L = float(t.max() - t.min())
            if L < min_laenge: continue
            neig = float(np.degrees(np.arccos(min(1.0, abs(e1[2])))))                 # Winkel zur Lotrechten
            if neig < lot_grad: info["lotrecht_geschuetzt"] += 1; continue
            vrm[kand[j]] = True
            info["zuege"].append(dict(voxel=int(len(j)), laenge_m=round(L, 2), neigung_zur_lotrechten_grad=round(neig, 1), von=(m_ + t.min() * e1).round(2).tolist(), bis=(m_ + t.max() * e1).round(2).tolist()))
        # Saum: duenne Nachbarvoxel ohne Flaeche an den Zuegen (Drahtenden, Rauschsaum)
        if vrm.any():
            nb = tree.query_ball_point(V[vrm], 2.5 * voxel + 1e-9, workers=workers)
            s_ = np.unique(np.concatenate([np.asarray(x, np.int64) for x in nb])) if len(nb) else np.zeros(0, np.int64)
            s_ = s_[~vrm[s_] & (lin[s_] >= 0.5 * min_lin) & (auf[s_] >= 0.5 * min_auf)]
            info["saum_voxel"] = int(len(s_)); vrm[s_] = True
    if fahnen:
        f_ = _fahnen(V, n_r, duenn, nrm, tree, ~vrm, voxel, lot_grad, info, workers); info["fahnen_voxel"] = int((f_ & ~vrm).sum()); vrm |= f_
    entf = vrm[inv]
    info.update(entfernt_voxel=int(vrm.sum()), entfernt_punkte=int(entf.sum()), anteil_entfernt=round(float(entf.mean()) if len(entf) else 0.0, 5), sekunden=round(time.time() - t0, 1))
    info["zuege"].sort(key=lambda z: -z["voxel"])
    return entf, info


def kontrollbild(X, C, entf, pfad, n_max=300000, titel=""):
    """Vorher (entfernte Punkte rot) / Nachher, Blick x-z, y-z, x-y."""
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    rng = np.random.default_rng(0); i = rng.choice(len(X), min(n_max, len(X)), replace=False)
    ie = np.flatnonzero(entf); ie = ie if len(ie) <= 60000 else rng.choice(ie, 60000, replace=False)
    i = i[~entf[i]]; col = (np.asarray(C[i], float) / 255.0) if C is not None else "0.4"
    f, ax = plt.subplots(2, 3, figsize=(24, 15))
    for c_, (a0, a1, nm) in enumerate([(0, 2, "x-z"), (1, 2, "y-z"), (0, 1, "x-y")]):
        for r_ in range(2):
            A = ax[r_, c_]; A.scatter(X[i, a0], X[i, a1], s=0.3, c=col, linewidths=0)
            if r_ == 0 and len(ie): A.scatter(X[ie, a0], X[ie, a1], s=1.2, c="red", linewidths=0)
            A.set_aspect("equal"); A.grid(alpha=0.3); A.set_title(f"{'VORHER (rot = entfernt)' if r_ == 0 else 'NACHHER'} {nm}")
    f.suptitle(titel); f.tight_layout(); f.savefig(pfad, dpi=70); plt.close(f)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("wolke"); ap.add_argument("--farben", default=""); ap.add_argument("--aus", required=True, help="Ordner fuer die gefilterte Kopie (gleiche Dateinamen)")
    ap.add_argument("--bericht", default=""); ap.add_argument("--bild", default=""); ap.add_argument("--voxel", type=float, default=VOXEL)
    ap.add_argument("--r", type=float, default=R_LOKAL); ap.add_argument("--R", type=float, default=R_WEIT); ap.add_argument("--min_laenge", type=float, default=MIN_LAENGE)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    X = np.load(a.wolke, mmap_mode="r"); C = np.load(a.farben, mmap_mode="r") if a.farben and os.path.exists(a.farben) else None
    if C is not None and len(C) != len(X): sys.exit(f"FEHLER: Farben {len(C)} != Punkte {len(X)}")
    entf, info = draht_maske(np.asarray(X), voxel=a.voxel, r=a.r, R=a.R, min_laenge=a.min_laenge, workers=a.workers)
    os.makedirs(a.aus, exist_ok=True); bleib = ~entf
    np.save(os.path.join(a.aus, os.path.basename(a.wolke)), np.asarray(X)[bleib])
    if C is not None: np.save(os.path.join(a.aus, os.path.basename(a.farben)), np.asarray(C)[bleib])
    info.update(wolke=os.path.abspath(a.wolke), kopie=os.path.join(os.path.abspath(a.aus), os.path.basename(a.wolke)), hinweis="Original unveraendert; Kopie nur fuer die Anzeige")
    if a.bild:
        kontrollbild(np.asarray(X), C, entf, a.bild, titel=f"wolke_draehte: {info['entfernt_punkte']} von {info['punkte']} Punkten entfernt, {len(info['zuege'])} Zuege")
        info["bild"] = os.path.abspath(a.bild)
    bp = a.bericht or os.path.join(a.aus, "wolke_draehte.json")
    json.dump(info, open(bp, "w"), indent=1, ensure_ascii=False)
    print(f"wolke_draehte: {info['entfernt_punkte']} von {info['punkte']} Punkten entfernt ({100 * info['anteil_entfernt']:.2f} %), {len(info['zuege'])} Drahtzuege, "
          f"{info['lotrecht_geschuetzt']} lotrecht geschuetzt, {info['sekunden']} s -> {bp}")


if __name__ == "__main__":
    main()
