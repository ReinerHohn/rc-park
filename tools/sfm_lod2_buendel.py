#!/usr/bin/env python3
"""sfm_lod2_buendel.py - GENERISCH: Buendelausgleich eines SfM-Netzes MIT den amtlichen Flaechen (LoD2-Waende/-Daecher aller Gebaeude im Umkreis + DGM1)
als Bedingung, ohne Handpicks (Kaufhaus 2026-11-04).

Warum: Ein Netz aus Einzelfotos (Wikimedia, je Foto eigene Brennweite/Verzeichnung, Kaufhaus 76 Kameras, 8900 Punkte) ist in sich verzerrt
(Kaufhaus: Wolkendach ~3 m unter DOM1, Hoehe ~16 % gestaucht), obwohl die Aehnlichkeitstransformation (sfm_lod2_ausrichten.py) die Fassaden trifft.
Eine nachtraegliche Wolkentransformation (wolke_entzerren_lod2.py) kann das nicht heilen, weil die Verzerrung in Brennweiten/Posen steckt.
Hier werden Kameras (Drehung, Lage, Brennweite, k1), alle 3D-Punkte und die Flaechenbedingung GEMEINSAM ausgeglichen:
  Bild:    Rueckprojektionsfehler jeder Spurbeobachtung (sigma 1 px)
  Flaeche: Punkt-zu-Ebene-Abstand zur besten von 8 benachbarten LoD2-Ebenen; DGM interpoliert als Band (bis 2 sigma darueber beidseitig, hoeher = Objekt, ignoriert) (sigma --sigma-flaeche, Klassen Wand/Dach/Boden gleich gewichtet;
           Zuordnung je Durchgang neu, Fang 2,0 -> 1,0 -> 0,6 m: Arkadenruecksprung, Erker und Aufbauten fallen heraus)
  Hauptpunkt: frei je Kamera (Prior Bildmitte, sigma 25 % der Langseite) - Wikimedia-Architekturfotos sind oft perspektivkorrigiert (Shift),
           ihr Hauptpunkt liegt dann weit ausserhalb der Mitte; fest in der Mitte zwang das Netz in Brennweite/Lage auszuweichen (Kameras unter Strassenniveau)
  Prior:   log f um die EXIF-Brennweite (tools/exif_brennweite.py, sigma 5 %, hart; verworfen bei > 25 % Abstand zum SfM-Wert), ohne EXIF um den SfM-Startwert (sigma 0,5), k1 -> 0 (sigma 0,2; Einzelfotos mit |k1| 0,6 sind Fehlbestimmungen), Kamerahoehe UEBER DGM1 1,6 +- 0,3 m (ANNAHME Strassenfotos; absolut im Rahmen war falsch: Kameras sanken unter das Gelaende); Ausreisser per IRLS-Huber-Gewicht
Unabhaengige Kontrolle (nicht im Ausgleich): DOM1-Dachzellen des eigenen Gebaeudes gegen die neu gerechnete dichte Wolke (Pruefung im Nachgang).
  /media/oem/scan/venv-colmap/bin/python -I -W ignore tools/sfm_lod2_buendel.py modelle/<obj>/objekt.json <seite> [--name buendel] [--radius 60] [--schreiben]
liest sfm/sparse_modell_<seite> (Modellsystem, Meter; von sfm_lod2_ausrichten.py), schreibt sfm/sparse_<name>/0 (Modellsystem), sfm/sparse_<name>_bilder (Link),
messprotokoll/SFM-AUSRICHTUNG-<name>.json (Einheitstransformation + Kameras, Format wie sfm_lod2_ausrichten), sfm/punkte_modell_<name>.npy/_farben,
audit/buendel_<name>.json. Danach: sfm_dicht.py <obj> <name>.
"""
import sys, os, json, math, argparse, time, numpy as np
from scipy.optimize import least_squares
from scipy.sparse import lil_matrix
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation as Rot
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pycolmap
from wolke_entzerren_lod2 import ziel



NPAR = 10                                                                      # je Kamera: rvec3 t3 log f k1 cx cy


AUS_PX = float(os.environ.get("BUENDEL_AUS_PX", "50"))    # Bildbeobachtungen mit groesserem Residuum (oder hinter der Kamera) zaehlen in der IRLS-Runde nicht (Huber-Rest unbeschraenkt)


def proj(cam, X, ii):
    """SIMPLE_RADIAL-Projektion (identisch mit COLMAP img_from_cam, geprueft 2026-11-04)."""
    R = Rot.from_rotvec(cam[ii, :3]); x = R.apply(X) + cam[ii, 3:6]
    u = x[:, :2] / x[:, 2:3]; r2 = (u ** 2).sum(1); d = 1 + cam[ii, 7] * r2
    return np.exp(cam[ii, 6])[:, None] * d[:, None] * u + cam[ii, 8:10], x[:, 2]


def zentren(cam): return -Rot.from_rotvec(cam[:, :3]).inv().apply(cam[:, 3:6])


def hauptpunkt_test(cam, X, oi, oj, ouv, cxy0, lang, f0, fs, sh_eng, sh_frei, min_beob=30, gewinn=0.8, gewinn_px=0.1, min_versatz=0.02):
    """Hauptpunkt je Kamera nur FREIGEBEN, wenn die eigenen Bildbeobachtungen es verlangen (2026-11-04).
    Befund: global frei (sigma 0,25) schluckte beim Martinstor (Nordnetz fast ohne Boden-/Dachpunkte) die Hoehenbindung - Goldkugeln 0,9-1,1 m tiefer als die
    Pick-Kette; fast fest (0,01) traf die Pick-Kette auf 0,0-0,4 m. Das Kaufhaus (Wikimedia-Shiftfotos) braucht ihn aber frei.
    Test: Rueckwaertsschnitt der Kamera bei FESTEN Punkten, einmal eng, einmal frei. Eine gemeinsame Datumsverschiebung ist bei festen Punkten nicht verfuegbar,
    nur ein echter Versatz (Shift, Beschnitt aus der Mitte) senkt den Fehler. Freigabe bei Median-Fehler < gewinn * eng UND > gewinn_px besser UND Versatz > min_versatz."""
    frei = np.zeros(len(cam), bool); info = {}
    for i in range(len(cam)):
        m = oi == i
        if m.sum() < min_beob: continue
        Xi, u, ii = X[oj[m]], ouv[m], np.zeros(int(m.sum()), int)
        e0 = np.linalg.norm(proj(cam[i:i + 1], Xi, ii)[0] - u, axis=1); w = np.sqrt(np.minimum(1.0, 2.0 / np.maximum(e0, 1e-9)))[:, None]
        def r(p, s):
            uv, _ = proj(p[None], Xi, ii)
            return np.r_[((uv - u) * w).ravel(), (p[6] - f0[i]) / fs[i], p[7] / 0.2, (p[8:10] - cxy0[i]) / (s * lang[i])]
        e = {}
        for nm, s in (("eng", sh_eng), ("frei", sh_frei)):
            sol = least_squares(lambda p: r(p, s), cam[i], x_scale="jac", max_nfev=60); e[nm] = (float(np.median(np.linalg.norm(proj(sol.x[None], Xi, ii)[0] - u, axis=1))), sol.x)
        vs = float(np.linalg.norm(e["frei"][1][8:10] - cxy0[i]) / lang[i])
        frei[i] = e["frei"][0] < gewinn * e["eng"][0] and e["eng"][0] - e["frei"][0] > gewinn_px and vs > min_versatz
        info[int(i)] = dict(eng_px=round(e["eng"][0], 3), frei_px=round(e["frei"][0], 3), versatz_anteil=round(vs, 4), frei=bool(frei[i]))
    return frei, info


def ausgleichen(cam0, cxy0, lang, X0, oi, oj, ouv, T, N, K, f0, fs, sigma_flaeche=0.10, kamerahoehe=(1.6, 0.3), sigma_hauptpunkt=0.01,
                flaeche=True, intrinsik_fest=False, faenge=(2.0, 1.0, 0.6), runden=3, max_nfev=40, laut=True, t0=None, boden_einseitig=True, exif_pruefen=True, exif_toleranz=0.15,
                hauptpunkt_freigabe=True, sigma_hauptpunkt_frei=0.25):
    """Kern (testbar, tools/test_buendel_synthetisch.py): Buendel mit Bild-, Flaechen- und Prior-Termen. flaeche=False + intrinsik_fest=True emuliert den
    alten Weg (COLMAP-Ausgleich mit festen EXIF-Intrinsics, keine amtlichen Flaechen). Rueckgabe cam, X, vorher, stufen.
    Hauptpunkt: eng (sigma_hauptpunkt, Anteil der Langseite) und je Kamera per hauptpunkt_test() freigegeben (sigma_hauptpunkt_frei); sigma_hauptpunkt darf
    auch ein Vektor je Kamera sein."""
    t0 = t0 or time.time(); nI, nP, nO = len(cam0), len(X0), len(oi); h0, hs = kamerahoehe; baum = cKDTree(T)
    # EXIF-Pruefdurchgang (2026-11-04): beschnittene Fotos tragen ein f35 des UNBESCHNITTENEN Bildes (bis Faktor 1,6 falsch); hart (5 %) gesetzt riss das die
    # Simulation auseinander (28 m). Erst weich (sigma >= 0,3) aus den Bildern schaetzen, dann EXIF mit > exif_toleranz Abweichung verwerfen, erst danach hart.
    verworfen = []
    if exif_pruefen and not intrinsik_fest and np.any(fs < 0.5):
        # Pruefdurchgang mit FREIEM Hauptpunkt: ein Shiftfoto darf seinen Versatz nicht ueber eine falsche Brennweite ausgleichen und so seine EXIF verlieren
        cp, Xp, _, _ = ausgleichen(cam0, cxy0, lang, X0, oi, oj, ouv, T, N, K, f0, np.maximum(fs, 0.3), sigma_flaeche, kamerahoehe, sigma_hauptpunkt_frei, flaeche, False,
                                   faenge[:1], 2, max_nfev, False, t0, boden_einseitig, exif_pruefen=False, hauptpunkt_freigabe=False)
        schlecht = (fs < 0.5) & (np.abs(cp[:, 6] - f0) > exif_toleranz); f0 = f0.copy(); fs = fs.copy(); f0[schlecht] = cp[schlecht, 6]; fs[schlecht] = 0.5
        # NUR Test: Start bleibt der Eingang. Mit uebernommenem Zustand (freier Hauptpunkt) lagen die Martinstor-Goldkugeln 0,5 m tiefer als bei engem Hauptpunkt
        verworfen = [int(i) for i in np.where(schlecht)[0]]
        if laut: print(f"EXIF-Pruefdurchgang: {int(np.sum(fs < 0.5))} EXIF-Brennweiten bestaetigt, {len(verworfen)} verworfen (> {exif_toleranz:.0%} gegen die Bilder): {verworfen}", flush=True)
    hp_info = None
    if hauptpunkt_freigabe and not intrinsik_fest:
        kw = dict(sigma_flaeche=sigma_flaeche, kamerahoehe=kamerahoehe, flaeche=flaeche, faenge=faenge, runden=runden, max_nfev=max_nfev, laut=laut, t0=t0, boden_einseitig=boden_einseitig)
        cT, XT, vT, sT = ausgleichen(cam0, cxy0, lang, X0, oi, oj, ouv, T, N, K, f0, fs, sigma_hauptpunkt=sigma_hauptpunkt, exif_pruefen=False, hauptpunkt_freigabe=False, **kw)
        frei, hp_info = hauptpunkt_test(cT, XT, oi, oj, ouv, cxy0, lang, f0, fs, sigma_hauptpunkt, sigma_hauptpunkt_frei)
        if laut: print(f"Hauptpunkt-Test: {int(frei.sum())} von {nI} Kameras freigegeben {[int(i) for i in np.where(frei)[0]]}", flush=True)
        vT["exif_verworfen"] = verworfen; vT["hauptpunkt"] = dict(eng=sigma_hauptpunkt, frei=sigma_hauptpunkt_frei, kameras=hp_info, freigegeben=[int(i) for i in np.where(frei)[0]])
        if not frei.any(): return cT, XT, vT, sT
        shv = np.where(frei, sigma_hauptpunkt_frei, sigma_hauptpunkt); kw["faenge"] = faenge[-1:]
        c2, X2, _, s2 = ausgleichen(cT, cxy0, lang, XT, oi, oj, ouv, T, N, K, f0, fs, sigma_hauptpunkt=shv, exif_pruefen=False, hauptpunkt_freigabe=False, **kw)
        return c2, X2, vT, sT + s2
    # Gelaendehoehe INTERPOLIERT an der Lage (2026-11-04): mit dem naechsten 1-m-Rasterpunkt lag im geneigten Gelaende die Haelfte der Punkte scheinbar
    # 'unter' dem DGM; einseitig gedrueckt hob das die ganze Szene um 0,2 m (Simulation, aus der Wahrheit gestartet). Ausserhalb der Huelle: naechster Punkt.
    from scipy.interpolate import LinearNDInterpolator
    Gp = T[K == 2]; gb = cKDTree(Gp[:, :2]); gz = Gp[:, 2]; gi = LinearNDInterpolator(Gp[:, :2], gz)
    def dgm(xy):
        z = gi(xy); n = ~np.isfinite(z)
        if n.any(): z[n] = gz[gb.query(xy[n])[1]]
        return z
    def ueber_dgm(C): return C[:, 2] - dgm(C[:, :2])                         # Kamerahoehe ueber dem Gelaende (DGM1) unter der Kamera
    def zuordnen(X, fang=np.inf):
        """Flaechenzuordnung: unter den 8 naechsten Abtastpunkten die EBENE mit dem kleinsten Punkt-Ebene-Abstand (2026-11-04). 'Naechster Abtastpunkt'
        gab Wandpunkten unter der Traufe die Dachebene -> einseitiger Druck nach oben, Szene +0,2 m (Simulation aus der Wahrheit)."""
        d, jj = baum.query(X, k=8, distance_upper_bound=fang if np.isfinite(fang) else np.inf)
        ok = np.isfinite(d); jj = np.where(ok, jj, 0)
        r = np.abs(np.einsum("ikj,ikj->ik", X[:, None, :] - T[jj], N[jj])); r[~ok] = np.inf
        b = np.argmin(r, 1); return d[np.arange(len(X)), b], jj[np.arange(len(X)), b]
    sh = np.maximum(np.broadcast_to(np.asarray(sigma_hauptpunkt, float), (nI,)), 1e-6); fs = np.full(nI, 1e-6) if intrinsik_fest else fs; f0 = cam0[:, 6].copy() if intrinsik_fest else f0
    sk = 1e-6 if intrinsik_fest else 0.2; sh = np.full(nI, 1e-6) if intrinsik_fest else sh
    def bericht(cam, X, tag):
        uv, z = proj(cam, X[oj], oi); e = np.linalg.norm(uv - ouv, axis=1); d, j = zuordnen(X); r = np.abs(np.einsum("ij,ij->i", X - T[j], N[j]))
        out = dict(reproj_median_px=float(np.median(e)), reproj_p90_px=float(np.percentile(e, 90)), hinter_kamera=int(np.sum(z <= 0)))
        for k, nm in enumerate(("wand", "dach", "boden")):
            m = (K[j] == k) & (d < 1.0); out[nm] = dict(n=int(m.sum()), median_abs_m=float(np.median(r[m])) if m.any() else None)
        C = zentren(cam); hd = ueber_dgm(C); out["kamera_ueber_dgm_m"] = dict(p10=float(np.percentile(hd, 10)), median=float(np.median(hd)), p90=float(np.percentile(hd, 90)))
        if laut: print(f"  {tag}: Rueckprojektion Median {out['reproj_median_px']:.2f} px (p90 {out['reproj_p90_px']:.1f}), " + ", ".join(f"{nm} n={out[nm]['n']} |d| {out[nm]['median_abs_m']:.2f} m" for nm in ("wand", "dach", "boden") if out[nm]["median_abs_m"] is not None) + f", Kamera ueber DGM p10/Median/p90 {out['kamera_ueber_dgm_m']['p10']:.2f}/{out['kamera_ueber_dgm_m']['median']:.2f}/{out['kamera_ueber_dgm_m']['p90']:.2f} m", flush=True)
        return out
    cam, X = cam0.copy(), X0.copy(); vor = bericht(cam, X, "vorher"); vor["exif_verworfen"] = verworfen; stufen = []
    for fang in (faenge if flaeche else (0.0,)):
        if flaeche:
            d, j = zuordnen(X, fang); sel = np.where(d < fang)[0]; Tj, Nj, Kj = T[j[sel]], N[j[sel]], K[j[sel]]
        else: sel = np.zeros(0, int); Tj = Nj = np.zeros((0, 3)); Kj = np.zeros(0, int)
        w = np.ones(len(sel)); nS = len(sel)
        for k in range(3):                                                    # Klassenausgleich, aber gedeckelt (Faktor <= 4): 150 Dachpunkte duerfen nicht wie 2300 zaehlen
            m = Kj == k
            if m.any(): w[m] = min(4.0, math.sqrt(nS / (3 * m.sum())))
        w /= sigma_flaeche
        # Boden EINSEITIG (Kaufhaus 2026-11-04): Gelaende ist eine Untergrenze. Strassenwolken haben 'Bodenpunkte' auf Raedern, Autos, Menschen (0,3-1 m darueber);
        # zweiseitig zog die Bedingung sie aufs DGM und die ganze Szene samt Kameras sank unter das Gelaende (Median -0,6 m). Nur Punkte UNTER dem DGM werden bestraft.
        boden = (Kj == 2) if boden_einseitig else np.zeros(len(sel), bool)
        nres = 2 * nO + nS + 5 * nI
        J = lil_matrix((nres, NPAR * nI + 3 * nP), dtype=np.int8); ro = np.arange(nO)
        for c in range(NPAR): J[2 * ro, NPAR * oi + c] = 1; J[2 * ro + 1, NPAR * oi + c] = 1
        for c in range(3): J[2 * ro, NPAR * nI + 3 * oj + c] = 1; J[2 * ro + 1, NPAR * nI + 3 * oj + c] = 1
        for c in range(3): J[2 * nO + np.arange(nS), NPAR * nI + 3 * sel + c] = 1
        ri = 2 * nO + nS + np.arange(nI)
        J[ri, NPAR * np.arange(nI) + 6] = 1; J[ri + nI, NPAR * np.arange(nI) + 7] = 1
        for c in range(6): J[ri + 2 * nI, NPAR * np.arange(nI) + c] = 1
        J[ri + 3 * nI, NPAR * np.arange(nI) + 8] = 1; J[ri + 4 * nI, NPAR * np.arange(nI) + 9] = 1
        # IRLS statt robuster Verlustfunktion: Huber-Gewichte je Beobachtung (Bild 2 px, Flaeche 2 sigma, Kamerahoehe 1 sigma) aus dem letzten Stand,
        # die Priors (Brennweite, k1) bleiben dadurch HART quadratisch - mit loss=soft_l1 wurden sie bei grossem Residuum linear und die Brennweiten liefen weg
        Js = J.tocsr()
        for runde in range(runden):
            uv, zb = proj(cam, X[oj], oi); e = np.linalg.norm(uv - ouv, axis=1)
            # Grobe Fehlbeobachtungen (2026-11-04, kaufhaus_null2): Punkte hinter/nahe der Kamera (z <= 0) und e > AUS_PX bekamen mit Huber noch sqrt(2e) -
            # nahe z = 0 unbeschraenkt (Kosten 3e24), der Ausgleich lief weg. Jetzt Gewicht 0 in dieser Runde (absteigend), ab Runde 2 neu bewertet.
            grob = (zb <= 1e-3) | ~np.isfinite(e) | (e > AUS_PX); e = np.where(grob, 1.0, e)
            wb = np.repeat(np.sqrt(np.minimum(1.0, 2.0 / np.maximum(e, 1e-9))) * ~grob, 2)
            df = np.einsum("ij,ij->i", X[sel] - Tj, Nj)
            # Boden als BAND (2026-11-04): einseitig (nur 'darunter' bestraft) wirkte bei verrauschten Punkten wie ein Gleichrichter und hob die Szene starr
            # um 0,13 m (Simulation aus der Wahrheit; steile Daecher halten z nicht, sie weichen seitlich aus). Jetzt: Punkte bis tau ueber dem DGM beidseitig,
            # darunter immer, deutlich darueber (Raeder/Autos/Menschen) gar nicht. Die Bandzugehoerigkeit wird je IRLS-Runde festgelegt (stetig in der Runde).
            boden_band = np.zeros(int(boden.sum()), bool)
            if boden.any(): hb_ = X[sel[boden], 2] - dgm(X[sel[boden], :2]); boden_band = hb_ < 2 * sigma_flaeche; df[boden] = np.where(boden_band, hb_, 0.0)
            df = np.abs(df); wf = np.sqrt(np.minimum(1.0, 2 * sigma_flaeche / np.maximum(df, 1e-9)))
            # Ausreisser der Kamerahoehe RELATIV ZUM MEDIAN (2026-11-04): absolut gewichtet schaltete sich der Prior bei einer gemeinsamen Verschiebung aller
            # Kameras selbst ab (alle 'Ausreisser') -> Martinstor-Kameras sanken auf -0,5 m. Einzelne Fenster-/Turmfotos bleiben Ausreisser.
            hc = ueber_dgm(zentren(cam)); hz = np.abs(hc - np.median(hc)) / hs; wh = np.sqrt(np.minimum(1.0, 2.0 / np.maximum(hz, 1e-9))) * (1.0 if flaeche else 0.0)
            def res(q):
                cm = q[:NPAR * nI].reshape(nI, NPAR); Xq = q[NPAR * nI:].reshape(nP, 3)
                uv, _ = proj(cm, Xq[oj], oi); rb = (uv - ouv).ravel() * wb
                rf = np.einsum("ij,ij->i", Xq[sel] - Tj, Nj)
                if boden.any(): rb_ = Xq[sel[boden], 2] - dgm(Xq[sel[boden], :2]); rf[boden] = np.where(boden_band, rb_, 0.0)
                rf = rf * w * wf
                C = zentren(cm)
                return np.r_[rb, rf, (cm[:, 6] - f0) / fs, (cm[:, 7] - (cam0[:, 7] if intrinsik_fest else 0)) / sk, (ueber_dgm(C) - h0) / hs * wh, (cm[:, 8:10] - cxy0).T.ravel() / np.r_[sh * lang, sh * lang]]
            q0 = np.r_[cam.ravel(), X.ravel()]
            sol = least_squares(res, q0, jac_sparsity=Js, loss="linear", x_scale="jac", method="trf", tr_solver="lsmr", max_nfev=max_nfev, verbose=0)
            cam = sol.x[:NPAR * nI].reshape(nI, NPAR); X = sol.x[NPAR * nI:].reshape(nP, 3)
        if laut: print(f"Fang {fang} m: {nS} Flaechenbedingungen, Kosten {sol.cost:.0f}, {sol.nfev} Auswertungen, {time.time() - t0:.0f} s", flush=True)
        stufen.append(dict(fang_m=fang, flaechenbedingungen=int(nS), kosten=float(sol.cost), auswertungen=int(sol.nfev), **bericht(cam, X, f"Fang {fang}")))
    return cam, X, vor, stufen


def daecher_gegen_dom1(obj, T, N, K, tol=1.0):
    """LoD2-Dachflaechen nur als Bedingung, wo DOM1 sie bestaetigt (2026-11-04): Martinstor-LoD2-First 45,3 m, echter Turm ~54,8 m (DOM1) - das Buendel zog
    die Dachpunkte 2 m hinunter. DOM1 sieht flache/maessig steile Dachflaechen von oben; Abtastpunkte mit |z_LoD2 - z_DOM1| > tol fallen weg.
    Steile Flaechen (|n_z| < 0,26, > 75 Grad) prueft DOM1 nicht verlaesslich (Register AR) -> fallen ebenfalls weg. Waende bleiben (DOM1 blind)."""
    from dom1_kachel import dom1_hoehe
    R = obj["rahmen"]; c0 = np.array(R["mitte_utm"], float); xh, yh = np.array(R["xhat_utm"]), np.array(R["yhat_utm"])
    d = K == 1
    if not d.any(): return T, N, K, "Dachpruefung: keine Dachflaechen"
    P = T[d]; E = c0[0] + P[:, 0] * xh[0] + P[:, 1] * yh[0]; Nn = c0[1] + P[:, 0] * xh[1] + P[:, 1] * yh[1]
    zd = dom1_hoehe(E, Nn) - R["gelaende"]
    if np.all(~np.isfinite(zd)): return T, N, K, "Dachpruefung: keine DOM1-Kachel - Daecher ungeprueft"
    gut = np.isfinite(zd) & (np.abs(P[:, 2] - zd) < tol) & (np.abs(N[d][:, 2]) >= 0.26)
    keep = np.ones(len(T), bool); keep[np.where(d)[0][~gut]] = False
    return T[keep], N[keep], K[keep], f"Dachpruefung gegen DOM1 (+-{tol} m): {int(gut.sum())} von {int(d.sum())} Dach-Abtastpunkten bestaetigt, {int((~gut).sum())} verworfen (LoD2 weicht ab oder > 75 Grad)"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("seite"); ap.add_argument("--name", default="buendel")
    ap.add_argument("--radius", type=float, default=60.0); ap.add_argument("--sigma-flaeche", type=float, default=0.10)
    ap.add_argument("--kamerahoehe", nargs=2, type=float, default=(1.6, 0.3)); ap.add_argument("--schreiben", action="store_true")
    ap.add_argument("--sigma-exif", type=float, default=0.05, help="Prior-Streuung log f fuer Kameras mit EXIF-Brennweite (0,05 = 5 %%)"); ap.add_argument("--ohne-exif", action="store_true")
    ap.add_argument("--sigma-hauptpunkt", type=float, default=0.01, help="Prior-Streuung des Hauptpunkts (Anteil der Bild-Langseite), eng; je Kamera per Test freigegeben (--sigma-hauptpunkt-frei)")
    ap.add_argument("--sigma-hauptpunkt-frei", type=float, default=0.25, help="Streuung fuer Kameras, deren Bilder einen Versatz belegen (Shift-/Architekturfotos)")
    ap.add_argument("--ohne-hauptpunkt-test", action="store_true", help="alle Kameras mit --sigma-hauptpunkt (kein Freigabetest)")
    ap.add_argument("--ohne-dom-pruefung", action="store_true"); ap.add_argument("--dom-toleranz", type=float, default=1.0, help="LoD2-Dach gilt nur, wo DOM1 innerhalb dieser Toleranz liegt (m)")
    ap.add_argument("--exif-max", type=float, default=0.25, help="EXIF-Brennweite verwerfen, wenn |log(f_sfm/f_exif)| groesser (Beschnitt/Digitalzoom)"); a = ap.parse_args()
    obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); obj = __import__('objekt_rahmen').ergaenzen(obj, od); sd = os.path.join(od, "sfm")
    rec = pycolmap.Reconstruction(os.path.join(sd, f"sparse_modell_{a.seite}")); t0 = time.time()
    ims = sorted(rec.images.values(), key=lambda im: im.name); pids = sorted(rec.points3D.keys()); pj = {p: j for j, p in enumerate(pids)}
    nI, nP = len(ims), len(pids)
    cam0 = np.zeros((nI, NPAR)); cxy0 = np.zeros((nI, 2)); lang = np.zeros(nI)
    for i, im in enumerate(ims):
        cw = im.cam_from_world(); c = rec.cameras[im.camera_id]; pr = list(c.params)
        if c.model.name != "SIMPLE_RADIAL": sys.exit(f"Kameramodell {c.model.name} nicht unterstuetzt (SIMPLE_RADIAL erwartet)")
        cam0[i, :3] = Rot.from_matrix(cw.rotation.matrix()).as_rotvec(); cam0[i, 3:6] = np.array(cw.translation); cam0[i, 6] = math.log(pr[0]); cam0[i, 7] = pr[3]; cxy0[i] = pr[1:3]; cam0[i, 8:10] = pr[1:3]; lang[i] = max(c.width, c.height)
    X0 = np.array([rec.points3D[p].xyz for p in pids]); farben = np.array([rec.points3D[p].color for p in pids], dtype=np.uint8)
    oi, oj, ouv = [], [], []
    for i, im in enumerate(ims):
        for p2 in im.points2D:
            if p2.has_point3D() and p2.point3D_id in pj: oi.append(i); oj.append(pj[p2.point3D_id]); ouv.append(p2.xy)
    oi, oj, ouv = np.array(oi), np.array(oj), np.array(ouv, float); nO = len(oi)
    T, N, K = ziel(obj, a.radius, dichte=0.25)
    if not a.ohne_dom_pruefung: T, N, K, dp = daecher_gegen_dom1(obj, T, N, K, a.dom_toleranz); print(dp, flush=True)
    baum = cKDTree(T)
    print(f"{nI} Kameras, {nP} Punkte, {nO} Beobachtungen; Ziel {len(T)} Flaechenpunkte (Wand {np.sum(K == 0)}, Dach {np.sum(K == 1)}, Boden {np.sum(K == 2)})", flush=True)
    # Brennweiten-Prior: EXIF (tools/exif_brennweite.py, sigma --sigma-exif in log f, robust) wo vorhanden, sonst schwach um den SfM-Startwert
    from exif_brennweite import brennweite_px
    f0 = cam0[:, 6].copy(); fs = np.full(nI, 0.5); fquelle = {}
    bdir = os.path.join(sd, f"sparse_{a.seite}_bilder")
    for i, im in enumerate(ims):
        c = rec.cameras[im.camera_id]; fe, q = brennweite_px(os.path.join(bdir, im.name), c.width, c.height) if not a.ohne_exif else (None, "abgeschaltet")
        fquelle[im.name] = dict(quelle=q, f_exif_px=fe, f_sfm_px=float(np.exp(cam0[i, 6])))
        if fe and abs(math.log(fe) - cam0[i, 6]) > a.exif_max:            # EXIF passt nicht zum Bild (Beschnitt, Digitalzoom, falsche Kamera): Prior aus, protokollieren
            fquelle[im.name]["verworfen"] = f"|log(f_sfm/f_exif)| {abs(math.log(fe) - cam0[i, 6]):.2f} > {a.exif_max}"; fe = None
        if fe: f0[i] = math.log(fe); fs[i] = a.sigma_exif
    ne = int(np.sum(fs < 0.5)); rq = [np.exp(cam0[i, 6] - f0[i]) for i in range(nI) if fs[i] < 0.5]
    print(f"EXIF-Brennweite fuer {ne} von {nI} Kameras; SfM/EXIF vorher Median {np.median(rq) if rq else float('nan'):.3f} (p10 {np.percentile(rq, 10) if rq else float('nan'):.3f}, p90 {np.percentile(rq, 90) if rq else float('nan'):.3f})", flush=True)
    h0, hs = a.kamerahoehe
    cam, X, vor, stufen = ausgleichen(cam0, cxy0, lang, X0, oi, oj, ouv, T, N, K, f0, fs, sigma_flaeche=a.sigma_flaeche, kamerahoehe=a.kamerahoehe,
                                      sigma_hauptpunkt=a.sigma_hauptpunkt, sigma_hauptpunkt_frei=a.sigma_hauptpunkt_frei,
                                      hauptpunkt_freigabe=not a.ohne_hauptpunkt_test, t0=t0)
    fr = np.exp(cam[:, 6] - cam0[:, 6])
    for i, im in enumerate(ims): fquelle[im.name]["f_buendel_px"] = float(np.exp(cam[i, 6]))
    rn = [np.exp(cam[i, 6] - f0[i]) for i in range(nI) if fs[i] < 0.5]
    if rn: print(f"Buendel/EXIF nachher Median {np.median(rn):.3f} (p10 {np.percentile(rn, 10):.3f}, p90 {np.percentile(rn, 90):.3f}); Kameras mit > 15 % Abweichung (Beschnitt?): {[ims[i].name for i in range(nI) if fs[i] < 0.5 and abs(math.log(np.exp(cam[i, 6] - f0[i]))) > 0.14]}")
    print(f"Brennweitenaenderung: Median {np.median(fr):.3f}, p10 {np.percentile(fr, 10):.3f}, p90 {np.percentile(fr, 90):.3f}; |k1| Median vorher {np.median(np.abs(cam0[:, 7])):.3f} nachher {np.median(np.abs(cam[:, 7])):.3f}")
    C = zentren(cam)
    # TOR (2026-11-04, kaufhaus_null2): divergierter Ausgleich (Rueckprojektion 4e6 px, 19738 Punkte hinter Kameras) wurde geschrieben und die Kette
    # rechnete die Dichtwolke darauf. Jetzt: Abbruch mit Exit 3, nichts schreiben, wenn das Ergebnis schlechter ist als der Eingang.
    nb = stufen[-1] if stufen else vor; n_beob = max(len(oi), 1)
    tor = dict(reproj_median=(nb["reproj_median_px"], max(3.0, 2.0 * vor["reproj_median_px"])), hinter_kamera_anteil=(nb["hinter_kamera"] / n_beob, max(0.01, 2.0 * vor["hinter_kamera"] / n_beob)))
    durch = {k: v for k, v in tor.items() if not v[0] <= v[1]}
    if durch:
        print(f"TOR: Ausgleich divergiert/verschlechtert - {', '.join(f'{k} {v[0]:.3g} > {v[1]:.3g}' for k, v in durch.items())}; NICHT geschrieben (Eingangsnetz pruefen: Brennweiten-Priors, sfm_netz Prior-Pruefung)", flush=True)
        sys.exit(3)
    if not a.schreiben: return
    # COLMAP-Netz schreiben (Modellsystem, Meter)
    for i, im in enumerate(ims):
        c = rec.cameras[im.camera_id]; c.params = [float(np.exp(cam[i, 6])), float(cam[i, 8]), float(cam[i, 9]), float(cam[i, 7])]
        rig = pycolmap.Rigid3d(pycolmap.Rotation3d(Rot.from_rotvec(cam[i, :3]).as_matrix()), cam[i, 3:6]); rec.frames[im.frame_id].rig_from_world = rig
    for j, p in enumerate(pids): rec.points3D[p].xyz = X[j]
    ziel_d = os.path.join(sd, f"sparse_{a.name}", "0"); os.makedirs(ziel_d, exist_ok=True); rec.write(ziel_d)
    lnk = os.path.join(sd, f"sparse_{a.name}_bilder"); src = f"sparse_{a.seite}_bilder"
    if not os.path.exists(lnk): os.symlink(src, lnk)
    kam = {}
    for i, im in enumerate(ims):
        nr = os.path.splitext(im.name)[0]; c = rec.cameras[im.camera_id]
        kam[nr] = dict(standort=C[i].round(2).tolist(), f_px_original=float(np.exp(cam[i, 6])), fak=1.0, off=[0.0, 0.0], R=Rot.from_rotvec(cam[i, :3]).as_matrix().tolist(), t=cam[i, 3:6].tolist(),
                       cx=float(cam[i, 8]), cy=float(cam[i, 9]), k=[float(cam[i, 7])], bild_b=c.width, bild_h=c.height, hinweis="f/cx/cy in SfM-Bildpixeln; Buendel mit LoD2-Flaechen")
    out = dict(verfahren="sfm_lod2_buendel.py (Buendelausgleich mit LoD2/DGM1-Flaechenbedingung, Start sparse_modell_" + a.seite + ")", sparse=ziel_d, fotos_sfm=sorted(kam), fotos_mit_picks=[],
               transformation=dict(beschreibung="Einheit: das Netz ist bereits im Modellsystem (X_sfm = X_modell)", s=1.0, s_sigma_prozent=0.0, rvec=[0.0, 0.0, 0.0], t=[0.0, 0.0, 0.0]),
               kameras=kam, vorher=vor, stufen=stufen, sigma_flaeche_m=a.sigma_flaeche, brennweiten=fquelle, sigma_exif=a.sigma_exif,
               annahmen=dict(kamerahoehe=dict(h0=h0, sigma=hs, hinweis="ANNAHME Strassenfotos, Huber"), prior_f="log f sigma 0,5 um Startwert", prior_k1="k1 -> 0 sigma 0,2"))
    os.makedirs(os.path.join(od, "messprotokoll"), exist_ok=True); json.dump(out, open(os.path.join(od, "messprotokoll", f"SFM-AUSRICHTUNG-{a.name}.json"), "w"), indent=1, ensure_ascii=False)
    np.save(os.path.join(sd, f"punkte_modell_{a.name}.npy"), X); np.save(os.path.join(sd, f"punkte_farben_{a.name}.npy"), farben)
    os.makedirs(os.path.join(od, "audit"), exist_ok=True)
    json.dump(dict(werkzeug="sfm_lod2_buendel.py", vorher=vor, stufen=stufen, brennweiten=fquelle, f_aenderung=dict(median=float(np.median(fr)), p10=float(np.percentile(fr, 10)), p90=float(np.percentile(fr, 90)))),
              open(os.path.join(od, "audit", f"buendel_{a.name}.json"), "w"), indent=1)
    print("geschrieben:", ziel_d, f"messprotokoll/SFM-AUSRICHTUNG-{a.name}.json", f"sfm/punkte_modell_{a.name}.npy")


if __name__ == "__main__":
    main()
