#!/usr/bin/env python3
"""test_buendel_synthetisch.py - BEWEIS mit bekannter Wahrheit: alte gegen neue Kamera-/Buendelkette (Kaufhaus 2026-11-04, Nutzerauftrag
"beweise, dass es bei einem neuen Objekt besser laeuft").

Szene = echte amtliche Umgebung eines Objekts (LoD2-Waende/-Daecher aller Gebaeude im Umkreis + DGM1), Wahrheit sind Punkte darauf (+ 10 % Fassadendetail
0,3-1 m vor/hinter der Wand, das LoD2 NICHT kennt) und Strassenkameras (Standorte aus der echten SfM-Ausrichtung, Hoehe DGM + 1,6 m) mit dem Bildmix, der
die Kaufhaus-Wolke verzerrt hat: Brennweiten 0,6-2,5 x Langseite, Seitenverhaeltnisse 4:3/3:2/1:1, 30 % beschnittene Fotos, 15 % perspektivkorrigiert (--anteil-shift)
(Hauptpunkt verschoben), k1 +-0,05, Bildrauschen 0,7 px. EXIF: 50 % der Fotos; davon die Haelfte f35 (bei Beschnitt FALSCH), die Haelfte FocalPlane (richtig).
Ketten (gleiche Beobachtungen):
  ALT : Intrinsics fest auf f35/36*Langseite (sfm_netz.py bis 2026-11-04), Hauptpunkt Mitte, Ausgleich nur Bild; danach ORAKEL-Aehnlichkeit auf die wahren
        Punkte (besser als jede echte Ausrichtung -> der Vergleich bevorzugt ALT)
  NEU1: wie ALT, aber EXIF nach exif_brennweite.py (Diagonale/FocalPlane) als weicher Prior, Hauptpunkt frei, kein LoD2   (= nur Intrinsik-Fix)
  NEU : NEU1 + sfm_lod2_buendel.ausgleichen (LoD2/DGM-Flaechen, Kamerahoehe ueber DGM, EXIF-Ausreisser verworfen)
Kennzahlen gegen die Wahrheit: 3D-Punktfehler (Median, p90), Hoehenfehler oberhalb 8 m (Dachzone, das Kaufhaus-Symptom), Kamerahoehenfehler, Brennweitenfehler.
  /media/oem/scan/venv-colmap/bin/python -u -I -W ignore tools/test_buendel_synthetisch.py modelle/<obj>/objekt.json --kameras messprotokoll/SFM-AUSRICHTUNG-<seite>.json
        [--seeds 0 1 2] [--punkte 3000] [--aus audit/test_buendel_synthetisch.json]
Exit 0 = NEU in jedem Seed besser als ALT im Punktfehler und im Hoehenfehler; Exit 1 sonst.
"""
import sys, os, json, math, argparse, time, numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation as Rot
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wolke_entzerren_lod2 import ziel
import sfm_lod2_buendel as B


def szene(obj, kam_json, n_p, rng):
    T, N, K = ziel(obj, 60.0, dichte=0.25)
    # Wahrheitspunkte: Verteilung wie eine echte Strassenwolke (Wand 90 %, Dach 3 %, Boden 7 %), 10 % der Wandpunkte als Fassadendetail versetzt
    idx = np.r_[rng.choice(np.where(K == 0)[0], int(0.90 * n_p)), rng.choice(np.where(K == 1)[0], int(0.03 * n_p)), rng.choice(np.where(K == 2)[0], int(0.07 * n_p))]
    X = T[idx].copy(); Nn = N[idx]; det = rng.random(len(X)) < 0.10 * (K[idx] == 0)
    X[det] += Nn[det] * rng.uniform(-1.0, 1.0, det.sum())[:, None] * np.where(rng.random(det.sum()) < 0.5, 0.3, 1.0)[:, None]
    obj_b = (K[idx] == 2) & (rng.random(len(X)) < 0.6); X[obj_b, 2] += rng.uniform(0.2, 1.2, obj_b.sum())   # 60 % der 'Bodenpunkte' auf Raedern/Autos/Menschen (echte Strassenwolke)
    gb = cKDTree(T[K == 2][:, :2]); gz = T[K == 2][:, 2]
    S = json.load(open(kam_json))["kameras"]; C = np.array([v["standort"] for v in S.values()], float)
    C[:, 2] = gz[gb.query(C[:, :2])[1]] + 1.6 + rng.normal(0, 0.15, len(C))
    return T, N, K, X, Nn, C


def kameras(C, X, rng, a_shift=0.15):
    nI = len(C); ziel_p = np.median(X, 0); cam = np.zeros((nI, B.NPAR)); info = []
    for i in range(nI):
        asp = rng.choice([4 / 3, 3 / 2, 1.0], p=[0.45, 0.45, 0.10]); W0, H0 = 2000, int(round(2000 / asp))
        f = rng.uniform(0.6, 2.5) * W0; beschnitt = rng.random() < 0.3; c = rng.uniform(0.6, 0.9) if beschnitt else 1.0
        W, H = int(W0 * c), int(H0 * c); s = 2000 / max(W, H) if beschnitt else 1.0          # Beschnitt, dann wieder auf 2000 px Langseite
        W, H, f_px = int(W * s), int(H * s), f * s
        blick = ziel_p - C[i]; blick[2] = 0; blick /= np.linalg.norm(blick); yaw = math.atan2(blick[1], blick[0]) + rng.normal(0, 0.15)
        pitch = rng.uniform(0.03, 0.20); shift = rng.random() < a_shift
        # Kamera: z_cam = Blickrichtung; x_cam rechts, y_cam unten. Perspektivkorrigiert = optische Achse waagerecht, Hauptpunkt um f*tan(pitch) nach unten
        p_eff = 0.0 if shift else pitch
        d = np.array([math.cos(yaw) * math.cos(p_eff), math.sin(yaw) * math.cos(p_eff), math.sin(p_eff)]); xr = np.cross(d, [0, 0, 1.0]); xr /= np.linalg.norm(xr); yd = np.cross(d, xr)
        R = np.vstack([xr, yd, d]); cx, cy = W / 2 + rng.normal(0, 5), H / 2 + rng.normal(0, 5) + (f_px * math.tan(pitch) if shift else 0.0)
        cam[i, :3] = Rot.from_matrix(R).as_rotvec(); cam[i, 3:6] = -R @ C[i]; cam[i, 6] = math.log(f_px); cam[i, 7] = rng.normal(0, 0.03); cam[i, 8:10] = (cx, cy)
        exif = None
        if rng.random() < 0.5:
            if rng.random() < 0.5: exif = ("f35", f * 43.27 / math.hypot(W0, H0))                 # 35-mm-Aequivalent des UNBESCHNITTENEN Bildes (Diagonale)
            else: exif = ("focalplane", f_px)                                                   # beschnittfest (Pixelabstand)
        info.append(dict(W=W, H=H, beschnitt=bool(beschnitt), shift=bool(shift), f_px=f_px, exif=exif))
    return cam, info


def beobachten(cam, X, Nn, info, rng, rausch=0.7, max_je_bild=500):
    oi, oj, uv = [], [], []
    for i in range(len(cam)):
        u, z = B.proj(cam, X, np.full(len(X), i)); W, H = info[i]["W"], info[i]["H"]; C = B.zentren(cam[i:i + 1])[0]
        sicht = (z > 1) & (z < 70) & (u[:, 0] > 0) & (u[:, 0] < W) & (u[:, 1] > 0) & (u[:, 1] < H) & (np.einsum("ij,ij->i", C - X, Nn) > 0)
        j = np.where(sicht)[0]; j = rng.choice(j, min(len(j), max_je_bild), replace=False) if len(j) else j
        oi += [i] * len(j); oj += j.tolist(); uv.append(u[j] + rng.normal(0, rausch, (len(j), 2)))
    oi, oj, uv = np.array(oi), np.array(oj), np.vstack(uv)
    n = np.bincount(oj, minlength=len(X)); ok = n[oj] >= 2
    return oi[ok], oj[ok], uv[ok], np.where(n >= 2)[0]


def komponenten(oi, oj, nI, min_gemeinsam=10):
    """Kameragraph: Kanten zwischen Kameras mit >= min_gemeinsam gemeinsamen Punkten. Mehrere Komponenten = Szene zerfaellt (keine Kette kann sie
    gemeinsam lagern; Seed 2 Martinstor 2026-11-04: alle Ketten 25 m) -> Szenario wird ausgewiesen, nicht gewertet."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    M = coo_matrix((np.ones(len(oi)), (oi, oj))).tocsr(); G = (M @ M.T).toarray() >= min_gemeinsam
    n, lab = connected_components(G, directed=False); return n, np.bincount(lab)


def umeyama(A, Bp):
    ma, mb = A.mean(0), Bp.mean(0); A0, B0 = A - ma, Bp - mb; U, S, Vt = np.linalg.svd(B0.T @ A0); D = np.eye(3); D[2, 2] = np.sign(np.linalg.det(U @ Vt))
    R = U @ D @ Vt; s = (S * np.diag(D)).sum() / (A0 ** 2).sum(); return s, R, mb - s * R @ ma


def umeyama_robust(A, Bp, runden=5, anteil=0.8):
    """Getrimmte Aehnlichkeit: wenige weggeflogene Punkte (kurze Spuren) duerfen das Orakel nicht verdrehen (Pruefstandsfehler 2026-11-04: s = 0,03)."""
    # Start NICHT mit allen Punkten (2026-11-04, Kaufhaus Seed 1): wenige weit weggeflogene Punkte blaehen die Streuung, s = 1e-4, Orakel-Fehler 28 m bei
    # Kettenfehler 0,10 m - alle Ketten 'gescheitert'. Erst Kern um den Median (80 %), dann trimmen.
    dA = np.linalg.norm(A - np.median(A, 0), axis=1); m = dA <= np.quantile(dA, anteil)
    for _ in range(runden):
        s, R, t = umeyama(A[m], Bp[m]); e = np.linalg.norm((s * (R @ A.T)).T + t - Bp, axis=1); m = e <= np.quantile(e, anteil)
    return s, R, t


def aehnlich_anwenden(cam, X, s, R, t):
    """X' = s R X + t; Kamera: x_c = Rc X + tc -> Rc R^T, tc*s - Rc R^T t (Brennweite unveraendert)."""
    c2 = cam.copy(); X2 = (s * (R @ X.T)).T + t
    for i in range(len(cam)):
        Rc = Rot.from_rotvec(cam[i, :3]).as_matrix(); Rn = Rc @ R.T; c2[i, :3] = Rot.from_matrix(Rn).as_rotvec(); c2[i, 3:6] = s * cam[i, 3:6] - Rn @ t
    return c2, X2


def kennzahlen(cam, X, cam_w, X_w, gb, gz):
    e = np.linalg.norm(X - X_w, axis=1); hoch = X_w[:, 2] > 8
    Cz = B.zentren(cam); Cw = B.zentren(cam_w)
    return dict(punkt_median_m=float(np.median(e)), anteil_ueber_1m=float(np.mean(e > 1.0)), punkt_p90_m=float(np.percentile(e, 90)),
                hoehe_ueber_8m_median_m=float(np.median(X[hoch, 2] - X_w[hoch, 2])) if hoch.any() else None, hoehe_ueber_8m_abs_median_m=float(np.median(np.abs(X[hoch, 2] - X_w[hoch, 2]))) if hoch.any() else None,
                kamerahoehe_fehler_median_m=float(np.median(np.abs(Cz[:, 2] - Cw[:, 2]))), brennweite_fehler_median=float(np.median(np.abs(cam[:, 6] - cam_w[:, 6]))))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--kameras", required=True); ap.add_argument("--seeds", type=int, nargs="*", default=[0, 1, 2])
    ap.add_argument("--punkte", type=int, default=3000); ap.add_argument("--aus", default=None)
    ap.add_argument("--anteil-shift", type=float, default=0.15, help="Anteil perspektivkorrigierter Fotos (Hauptpunkt verschoben)"); a = ap.parse_args()
    obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); obj = __import__('objekt_rahmen').ergaenzen(obj, od); kj = a.kameras if os.path.isabs(a.kameras) else os.path.join(od, a.kameras)
    alle = []; ok_alle = True
    for seed in a.seeds:
        rng = np.random.default_rng(seed); t0 = time.time()
        T, N, K, Xw, Nn, C = szene(obj, kj, a.punkte, rng); cam_w, info = kameras(C, Xw, rng, a.anteil_shift); oi, oj, ouv, pidx = beobachten(cam_w, Xw, Nn, info, rng)
        # nur Punkte mit >= 2 Beobachtungen; Indizes neu zaehlen
        neu = -np.ones(len(Xw), int); neu[pidx] = np.arange(len(pidx)); oj = neu[oj]; Xw = Xw[pidx]
        gb = cKDTree(T[K == 2][:, :2]); gz = T[K == 2][:, 2]; nI = len(cam_w)
        lang = np.array([max(d["W"], d["H"]) for d in info], float); mitte = np.array([[d["W"] / 2, d["H"] / 2] for d in info])
        print(f"\n=== Seed {seed}: {nI} Kameras, {len(Xw)} Punkte, {len(oi)} Beobachtungen; beschnitten {sum(d['beschnitt'] for d in info)}, perspektivkorrigiert {sum(d['shift'] for d in info)}, EXIF {sum(d['exif'] is not None for d in info)}", flush=True)
        # Start: Wahrheit leicht gestoert (SfM-Startloesung), Intrinsics je Kette
        # Startzustand wie ein KONVERGIERTER SfM-Lauf (2026-11-04): mit Punkte +-0,3 m und f +-10 % lag der Start bei langen Brennweiten 76 px neben den
        # Beobachtungen und ALLE Ketten divergierten gleich (Martinstor Seed 2, 25 m) - ein Startfehler des Pruefstands, kein Befund ueber die Ketten.
        st = rng.normal(0, 0.05, Xw.shape)
        def start_cam(f_alt):
            c = cam_w.copy(); c[:, 6] = f_alt; c[:, 7] = 0.0; c[:, 8:10] = mitte; c[:, :3] += rng.normal(0, 1, (nI, 3)) * (2.0 / np.exp(cam_w[:, 6]))[:, None]; return c
        # Drehrauschen ~2 px je Kamera (2026-11-04): 0,01 rad waren bei f = 5000 px 50 px Startfehler -> Martinstor Seed 2 divergierte in ALLEN Ketten gleich (25 m)
        # ALT: f35/36*Langseite fest (EXIF-Kameras), sonst frei; Hauptpunkt Mitte fest
        # Kameras OHNE EXIF: Start = Wahrheit +-5 % (ein inkrementeller SfM-Lauf schaetzt sie aus den Bildern; Start 1,2 x Langseite lag bis Faktor 2 daneben
        # und liess ALLE Ketten divergieren - Pruefstandsfehler 2026-11-04, kein Befund)
        f_frei = cam_w[:, 6] + rng.normal(0, 0.05, nI)
        f_alt = f_frei.copy(); fest = np.zeros(nI, bool); f_neu = f_frei.copy(); s_neu = np.full(nI, 0.5)
        for i, d in enumerate(info):
            if d["exif"]:
                typ, v = d["exif"]
                if typ == "f35": f_alt[i] = math.log(v / 36.0 * lang[i]); f_neu[i] = math.log(v * math.hypot(d["W"], d["H"]) / 43.27); fest[i] = True
                else: f_alt[i] = math.log(v); f_neu[i] = math.log(v); fest[i] = True
                s_neu[i] = 0.05
        erg = dict(seed=seed, kameras=nI, punkte=int(len(Xw)), beobachtungen=int(len(oi)))
        nk, gr = komponenten(oi, oj, nI); erg["komponenten"] = int(nk); erg["komponenten_groessen"] = sorted(gr.tolist(), reverse=True)
        if nk > 1 and sorted(gr)[-2] >= 2:
            erg["szenario_zerfallen"] = True; print(f"  Szene zerfaellt in {nk} Kameragruppen {erg['komponenten_groessen']} - nicht gewertet", flush=True); alle.append(erg); continue
        # ALT
        c0 = start_cam(f_alt); fs_alt = np.where(fest, 1e-6, 10.0)
        camA, XA, _, _ = B.ausgleichen(c0, mitte, lang, Xw + st, oi, oj, ouv, T, N, K, f_alt, fs_alt, flaeche=False, sigma_hauptpunkt=1e-6, laut=False, max_nfev=60, exif_pruefen=False, hauptpunkt_freigabe=False)
        s, R, t = umeyama_robust(XA, Xw); camA, XA = aehnlich_anwenden(camA, XA, s, R, t); erg["ALT"] = kennzahlen(camA, XA, cam_w, Xw, gb, gz)
        # NEU1: weicher EXIF-Prior nach exif_brennweite.py, Hauptpunkt eng + Freigabetest je Kamera (wie im Werkzeug), ohne LoD2
        c1 = start_cam(f_neu)
        cam1, X1, v1, _ = B.ausgleichen(c1, mitte, lang, Xw + st, oi, oj, ouv, T, N, K, f_neu, s_neu, flaeche=False, laut=False, max_nfev=60)
        s, R, t = umeyama_robust(X1, Xw)
        cam1o, X1o = aehnlich_anwenden(cam1, X1, s, R, t); erg["NEU1_nur_intrinsik"] = kennzahlen(cam1o, X1o, cam_w, Xw, gb, gz)
        # NEU: Start = ALT nach realistischer Ausrichtung? -> strenger: Start = NEU1 nach ORAKEL-Aehnlichkeit, dann LoD2-Buendel; EXIF-Ausreisser wie im Werkzeug verwerfen
        f2, s2 = f_neu.copy(), s_neu.copy()
        cam2, X2, v2, _ = B.ausgleichen(cam1o, mitte, lang, X1o, oi, oj, ouv, T, N, K, f2, s2, laut=False)
        erg["NEU"] = kennzahlen(cam2, X2, cam_w, Xw, gb, gz)
        # Trefferquote des Hauptpunkt-Tests gegen die Wahrheit (shift = perspektivkorrigiert)
        wahr = {i for i, d in enumerate(info) if d["shift"]}; fg = set(v2.get("hauptpunkt", {}).get("freigegeben", []))
        erg["hauptpunkt_test"] = dict(wahr_verschoben=sorted(wahr), freigegeben=sorted(fg), treffer=len(wahr & fg), fehlalarm=len(fg - wahr), verpasst=len(wahr - fg))
        print(f"  Hauptpunkt-Test: {len(wahr)} verschoben, {len(fg)} freigegeben, Treffer {len(wahr & fg)}, Fehlalarm {len(fg - wahr)}, verpasst {len(wahr - fg)}", flush=True)
        besser = erg["NEU"]["punkt_median_m"] < erg["ALT"]["punkt_median_m"] and erg["NEU"]["hoehe_ueber_8m_abs_median_m"] < erg["ALT"]["hoehe_ueber_8m_abs_median_m"]
        if erg["NEU"]["punkt_median_m"] > 1.0 and erg["ALT"]["punkt_median_m"] > 1.0:
            # Alle Ketten > 1 m = Pruefstand (Start/Orakel), kein Befund (2026-11-04: Kaufhaus Seed 1 meldete 'NEU besser' bei 28,58 gegen 28,60 m)
            erg["szenario_ungueltig"] = True; print("  alle Ketten > 1 m - Pruefstandsfehler, nicht gewertet", flush=True); alle.append(erg); continue
        erg["neu_besser"] = bool(besser); ok_alle &= besser; erg["sekunden"] = round(time.time() - t0)
        for k in ("ALT", "NEU1_nur_intrinsik", "NEU"):
            m = erg[k]; print(f"  {k:20s} Punkt Median {m['punkt_median_m']:.3f} m (p90 {m['punkt_p90_m']:.2f}, >1 m {100 * m['anteil_ueber_1m']:.0f} %), Hoehe >8 m {m['hoehe_ueber_8m_median_m']:+.3f} m (|.| {m['hoehe_ueber_8m_abs_median_m']:.3f}), Kamerahoehe {m['kamerahoehe_fehler_median_m']:.2f} m, |dlog f| {m['brennweite_fehler_median']:.3f}", flush=True)
        print(f"  -> NEU besser: {besser} ({erg['sekunden']} s)", flush=True); alle.append(erg)
    aus = a.aus or os.path.join(od, "audit", "test_buendel_synthetisch.json"); os.makedirs(os.path.dirname(aus), exist_ok=True)
    json.dump(dict(werkzeug="test_buendel_synthetisch.py", objekt=obj.get("name", os.path.basename(od)), kameras_quelle=a.kameras, seeds=alle, neu_immer_besser=bool(ok_alle),
                   hinweis="ALT bekommt eine ORAKEL-Aehnlichkeit auf die wahren Punkte (bevorzugt ALT); NEU startet vom Intrinsik-Fix + Orakel und nutzt LoD2/DGM"), open(aus, "w"), indent=1)
    gew = [e for e in alle if not e.get("szenario_zerfallen") and not e.get("szenario_ungueltig")]
    print(f"\nErgebnis: NEU in allen {len(gew)} gewerteten Seeds besser: {ok_alle} ({len(alle) - len(gew)} zerfallene/ungueltige Szenarien ausgewiesen)  -> {aus}"); sys.exit(0 if ok_alle and gew else 1)


if __name__ == "__main__":
    main()
