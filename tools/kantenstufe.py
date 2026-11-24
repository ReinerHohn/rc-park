#!/usr/bin/env python3
"""kantenstufe.py - KANTENSTUFE der Gesamtkette (KERNMETHODE, Nutzer 15.11.2026): Fotokanten + SfM-Kameras -> 3D-Kanten um die Modellflaeche -> Bewertung.
Allgemein fuer jedes Objekt (keine Kaufhaus-Pfade). Die dichte Wolke wird NICHT benutzt.

  /media/oem/scan/venv-seg/bin/python -I tools/kantenstufe.py modelle/<obj>/objekt.json --ausrichtung <SFM-AUSRICHTUNG.json> --bilder <ORDNER> --aus <DIR>
        [--max_fotos 80] [--refs 30] [--band 0.5] [--vorn 2.0] [--tol 0.15] [--nur_bewerten] [--suchraum messkoerper|modell] [--messkoerper STL] [--wolke W.npy] [--geraet cuda]
Schritte:
  1. Kameras aus der Ausrichtung (X_sfm = ..., je Kamera R, t im Modellrahmen = STL-Meter) -> DIR/kam.json (kam_lot2-Format: Rn, tn, C, f, cx, cy, W, H, modell, params).
     Auswahl: Kameras, die den Messkoerper sehen (Anteil projizierter Modellpunkte im Bild, Abstand < 80 m), gleichmaessig ueber 12 Blickrichtungen -> DIR/kam_wahl.json.
  2. tools/stabil_alle.py (GPU) -> DIR/stabil/<foto>.png
  3. tools/kanten_tiefe_sweep_flaeche.py --flaeche MESSKOERPER --flaeche_skala --band --vorn --huelle --ziel_auto (Blickziel je Referenz aus der Flaeche) -> DIR/sweep.npz
  4. Bewertung in 3D (gpu_knn): Modellkanten (Knick > 30 Grad + Rand, alle 5 cm) gegen Sweep-Kantenpunkte:
       Praezision = Anteil Modellkanten-Proben (im von Kanten belegten Bereich) mit Fotokante < tol  (rot = erfundene Kante)
       Recall     = Anteil Sweep-Punkte mit Modellkante < tol                                        (gelb = Fotokante ohne Modell = fehlendes Feature)
     Fehlende Kanten als Haufen (Raster 0,5 m, >= 30 Punkte) mit Seite/Hoehe -> Arbeitsliste fuer Generator-Features (kanten_features.py --sweep).
Ausgabe: DIR/kanten_bericht.json, modelle/<obj>/audit/kanten3d.png (Seitenansichten). Exit 0; rc 4 = zu wenig Kantenpunkte (Kameras/Stabilkarten pruefen).
22.11.2026 KREISFALL (0_DURCHBRUCH_AGENTEN_SCHLEIFE.md "Zirkulaere Messung"): bisher suchte der Sweep nur +-0,5 m um das STL des VORMODELLS und die Kameras wurden gegen
das Vormodell gewaehlt - Kanten > 0,5 m vor dem Vormodell (Vordach, Erker, Traufe) fand die Kette nie, Strahlen durch gebaute Oeffnungen suchten an der Rueckwand,
und ohne Vorlauf gab es keinen Suchraum. Jetzt (--suchraum messkoerper, Standard): Suchraum, Blickziel, Kameraauswahl und Box nur aus dem MODELLFREIEN Messkoerper
(tools/fassade_ortho.py --nur-messkoerper: LoD2 flach + Wandversatz aus Fotokanten, geschlossen), Band asymmetrisch --vorn 2,0 m vor bis --band 0,5 m hinter der Flaeche
(senkrecht, je Strahl umgerechnet), Strahlen am Messkoerper vorbei ueber die Huelle (--huelle); Tiefe = Triangulation ueber die Nachbarfotos (unveraendert);
dichte Wolke nur als Lage-Veto (--wolke, Punkte weiter als --veto_m von jeder Wolkenstelle fallen weg). Das gebaute Modell wird NUR noch bewertet (Schritt 4).
Waechter: tools/test_kantenstufe_kreis.py (zwei Vormodelle -> bitgleiche Kanten, Vordachkante 1,2 m vor der Wand gefunden). --suchraum modell = alter Weg (nur Vergleich).
Grenze: Teile weiter als --vorn vor der Messflaeche fehlen weiterhin (dafuer Foto-Tor teil_fotoform/foto_diff).
24.11.2026 TRAUFZONE (Befund Hoehen-Angleich 1122, modelle/FEATURE_FORMSITZ.md): ueber der LoD2-Wandoberkante fand der Sweep keine Kanten (Traufstrahlen treffen den
Messkoerper erst auf dem Dach dahinter -> Fenster verfehlt die Traufe). Jetzt zweiter Sweep um eine senkrechte Traufschuerze je Wandoberkante (traufzone():
Hoehe = Wolken-Dachfuss bzw. LoD2-Traufe + --traufzone_rand, kein Objektwert), Punkte nur in der Zone an sweep.npz angehaengt; --traufzone_rand 0 = alter Weg.
Waechter: tools/test_kantenstufe_traufzone.py (Traufkasten 1 m vor der Wand ueber der Oberkante: alt nicht gefunden, neu gefunden).
"""
import sys, os, json, glob, argparse, subprocess, time, numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); PY = "/media/oem/scan/venv-seg/bin/python"
sys.path.insert(0, os.path.join(ROOT, "tools"))


BILD_ENDUNGEN = (".jpg", ".jpeg", ".png")


def bild_finden(bd, name):
    """Bilddatei zur Kamera `name` (Kennung ohne Endung, wie in der Ausrichtung). 17.11.2026 (Durchsicht): der Ersatzweg `glob(name + "*")` nahm die erste Datei mit diesem ANFANG -
    fuer IMG_1 ohne eigene Datei (oder mit .JPEG, das nicht in der Liste stand) war das IMG_10.jpg: Kamera von Bild 1 mit dem Inhalt von Bild 10, die Kantenstufe rechnete still damit.
    Jetzt: (1) genau diese Datei, (2) Datei mit genau diesem Namen vor der Endung (Endung in beliebiger Schreibweise), (3) `name_<zusatz>` (Kaufhaus: 122 -> 122_<quelle>.jpg) NUR wenn eindeutig."""
    if os.path.isfile(os.path.join(bd, name)): return name
    try: alle = sorted(f for f in os.listdir(bd) if f.lower().endswith(BILD_ENDUNGEN))
    except OSError: return None
    g = [f for f in alle if os.path.splitext(f)[0] == name]
    if not g: g = [f for f in alle if f.startswith(name + "_")]; g = g if len(g) == 1 else []
    return g[0] if g else None


def kameras(A, bd):
    K = {}
    for nm, k in A["kameras"].items():
        f = bild_finden(bd, nm)
        if not f or "R" not in k: continue
        R = np.array(k["R"], float); t = np.array(k["t"], float); fp = float(k["f_px_original"]); k1 = float((k.get("k") or [0.0])[0])
        K[f] = dict(Rn=R.tolist(), tn=t.tolist(), C=(-R.T @ t).tolist(), f=fp, cx=float(k["cx"]), cy=float(k["cy"]), W=int(float(k.get("bild_b", 2 * float(k["cx"])))),
                    H=int(float(k.get("bild_h", 2 * float(k["cy"])))), modell="SIMPLE_RADIAL", params=[fp, float(k["cx"]), float(k["cy"]), k1])
    return K


def waehlen(K, V, n):
    """Kameras, die das Modell sehen; je 30-Grad-Sektor (Blick um die Modellmitte) die besten zuerst (Rundlauf)."""
    mid = V.mean(0); sek = {}
    for f, k in K.items():
        R = np.array(k["Rn"]); t = np.array(k["tn"]); X = V @ R.T + t; z = X[:, 2]; ok = z > 0.5
        u = k["f"] * X[ok, 0] / z[ok] + k["cx"]; v = k["f"] * X[ok, 1] / z[ok] + k["cy"]
        sicht = float(((u >= 0) & (u < k["W"]) & (v >= 0) & (v < k["H"])).sum()) / len(V); d = float(np.linalg.norm(np.array(k["C"]) - mid))
        if sicht < 0.2 or d > 80: continue
        az = int((np.degrees(np.arctan2(*(np.array(k["C"])[:2] - mid[:2])[::-1])) % 360) // 30); sek.setdefault(az, []).append((-sicht / max(d, 3) ** 0.5, f))
    for s in sek.values(): s.sort()
    out = []; i = 0
    while len(out) < n and any(i < len(s) for s in sek.values()):
        for s in sek.values():
            if i < len(s) and len(out) < n: out.append(s[i][1])
        i += 1
    return out, {str(a * 30): len(s) for a, s in sorted(sek.items())}


def messkoerper_laden(a, obj, objp, skala):
    """Suchraum der Kantenstufe (22.11.2026 Kreisfall): (Netz in Meter/Modellrahmen oder None, STL-Pfad, Quelle). Nie das gebaute Modell (ausser --suchraum modell)."""
    import trimesh
    if a.suchraum == "modell":
        p = os.path.join(ROOT, obj["stl"]); m = trimesh.load(p); m.apply_scale(skala); return m, p, "modell (ALTER WEG, zirkulaer: Suchraum = Vormodell)"
    mk = os.path.abspath(a.messkoerper) if a.messkoerper else os.path.join(os.path.abspath(a.aus), "messkoerper.stl")
    if not a.messkoerper:
        r = subprocess.run([PY, "-W", "ignore", "-I", os.path.join(ROOT, "tools/fassade_ortho.py"), objp, "--nur-messkoerper", mk], capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(mk):
            return None, mk, "kein Messkoerper: " + ((r.stdout + r.stderr).strip().splitlines() or ["?"])[-1][:200]
    m = trimesh.load(mk); m.apply_scale(skala)
    return (m, mk, "messkoerper (modellfrei: LoD2 flach + Wandversatz aus Fotokanten)") if len(m.faces) else (None, mk, "Messkoerper leer")


def traufkanten(S, winkel_lot=0.1, min_l=0.3, neigung=0.1):
    """Waagrechte WANDOBERKANTEN des Messkoerpers (Traufe/Dachfuss im LoD2): je senkrechter Flaeche die waagrechte Oberkante, wenn darueber keine senkrechte
    Flaeche derselben Ebene weitergeht (gestapelte Wandstuecke). Aussenrichtung per Strahlzaehlung (gerade Trefferzahl = aussen), sonst weg von der Mitte.
    Oberkante = die zwei hoechsten Ecken eines Dreiecks, Steigung <= neigung (LoD2-Wandoberkanten sind nicht genau waagrecht, 1122: 36,47/36,70 auf 5 m).
    Liefert Liste dict(a, b (Endpunkte), z (hoeher), z_lo (tiefer), n (aussen, waagrecht), L)."""
    V = np.asarray(S.vertices, float); Fc = np.asarray(S.faces); N = np.asarray(S.face_normals, float); A = np.asarray(S.area_faces, float)
    vert = np.flatnonzero((np.abs(N[:, 2]) < winkel_lot) & (A > 0.02)); mitte = V.mean(0); out = []
    def bedeckt(p, nh, f0):                                                        # liegt p in einer anderen senkrechten Flaeche derselben Ebene?
        for f in vert:
            if f == f0 or abs(float(N[f, :2] @ nh)) < 0.98: continue
            T = V[Fc[f]]
            if abs(float((p - T[0]) @ N[f])) > 0.05: continue
            v0, v1, v2 = T[1] - T[0], T[2] - T[0], p - T[0]; d00, d01, d11, d20, d21 = v0 @ v0, v0 @ v1, v1 @ v1, v2 @ v0, v2 @ v1; den = d00 * d11 - d01 * d01
            if abs(den) < 1e-12: continue
            b1 = (d11 * d20 - d01 * d21) / den; b2 = (d00 * d21 - d01 * d20) / den
            if b1 >= -1e-3 and b2 >= -1e-3 and b1 + b2 <= 1 + 1e-3: return True
        return False
    for f in vert:
        P = V[Fc[f]]; o_ = np.argsort(-P[:, 2]); a_, b_ = P[o_[0]].copy(), P[o_[1]].copy(); L = float(np.linalg.norm((b_ - a_)[:2]))
        if L < min_l or abs(a_[2] - b_[2]) > neigung * L or float(P[o_[2], 2]) > min(a_[2], b_[2]) - 0.3: continue   # waagrecht (LoD2-Rauschen bis neigung) + Wand darunter
        zmax = float(max(a_[2], b_[2])); zmin_ = float(min(a_[2], b_[2]))
        nh = N[f, :2] / max(np.linalg.norm(N[f, :2]), 1e-9); m = 0.5 * (a_ + b_)
        if bedeckt(m + np.array([0, 0, 0.2]), nh, f): continue                     # Wand geht darueber weiter: keine Oberkante
        zahl = []
        for s in (1.0, -1.0):
            o_ = m + np.array([0, 0, -0.3]) + np.r_[0.02 * s * nh, 0.0]
            try: loc, _, _ = S.ray.intersects_location(o_[None], np.r_[s * nh, 0.0][None], multiple_hits=True)
            except Exception: loc = np.zeros((0, 3))
            zahl.append(len(np.unique(np.round(np.linalg.norm(loc - o_, axis=1), 3))) if len(loc) else 0)
        if zahl[0] % 2 == 0 and zahl[1] % 2 == 1: s_ = 1.0
        elif zahl[1] % 2 == 0 and zahl[0] % 2 == 1: s_ = -1.0
        else: s_ = 1.0 if float((m[:2] - mitte[:2]) @ nh) >= 0 else -1.0
        out.append(dict(a=a_, b=b_, z=zmax, z_lo=zmin_, n=s_ * nh, L=L))
    return out


def traufzone(S, vorn, band, rand, wolke=None, z_max=None):
    """SUCHRAUM UEBER DER WANDOBERKANTE (24.11.2026, Befund Hoehen-Angleich 1122: ueber 36,5 m keine triangulierten Fotokanten, Traufkasten/Galerie/Dachfuss ohne
    zweite Quelle). Ursache: Strahlen zur Traufe (vor der Wand, ueber der Oberkante) treffen den Messkoerper erst auf dem DACH weit dahinter oder auf der
    Gegenseite - das Fenster -vorn..+band um diesen Treffer (je Strahl hoechstens 2 x vorn) erreicht die Traufe nicht (1122: 0-4 % der Traufstrahlen im Fenster).
    Genauer (1122, Kameras vor der Seite): 95 % der Traufstrahlen verfehlen den Messkoerper; ueber die Huelle beginnt das Fenster an der Huellbox-Wand, entlang
    des Strahls 2,7-25 m vor der Traufe (steile Nahaufnahmen aus der Gasse/dem Tor).
    Fix: je Wandoberkante (traufkanten) eine senkrechte SCHUERZE in der Wandebene von der Oberkante z_e bis z_oben + vorn (flachere Strahlen treffen sie hoeher)
    und eine waagrechte DECKE in z_oben von der Wand bis vorn davor (steile Strahlen von unten), seitlich um min(vorn, L/2) verlaengert (Eckueberstand). Hoehe aus Daten: z_oben = z_e + rand + max(0, Wolken-Dachfuss - z_e), Wolken-Dachfuss = 95. Perzentil
    der Wolkenpunkte VOR der Wand (0,05..vorn) ueber z_e (>= 30 Punkte, nur die zusammenhaengende Belegung ab z_e), gedeckelt auf die oertliche Dachhoehe des Messkoerpers ueber der Kante und auf die Unterkante ANDERER
    Messkoerper-WAENDE in diesem Quader (Guard: Anbau vor dem Hauptturm); ohne Wolke LoD2-Traufe + rand.
    Liefert (Schuerze trimesh oder None, Zonen-Liste fuer den Punktfilter, Text)."""
    import trimesh
    K = traufkanten(S)
    if not K: return None, [], "keine waagrechte Wandoberkante im Messkoerper"
    zmx = float(S.bounds[1][2]) if z_max is None else float(z_max); W = None
    if wolke is not None and len(wolke): W = np.asarray(wolke, float)
    import trimesh as _tm
    lot = np.flatnonzero(np.abs(np.asarray(S.face_normals)[:, 2]) < 0.1)            # nur WAENDE als fremde Flaechen (das eigene LoD2-Dach steht oft 0,2-0,3 m ueber)
    MP = np.asarray(_tm.Trimesh(S.vertices, np.asarray(S.faces)[lot], process=False).sample(40000, seed=0), float) if len(lot) else np.zeros((0, 3))
    schr = np.setdiff1d(np.arange(len(S.faces)), lot)                               # Dach/Boden: oertliche Dachhoehe ueber der Kante (Rundturm 13,7 statt Hauptdach 45,9)
    RP = np.asarray(_tm.Trimesh(S.vertices, np.asarray(S.faces)[schr], process=False).sample(40000, seed=0), float) if len(schr) else np.zeros((0, 3))
    V, F, Z = [], [], []
    for k in K:
        a_, b_, n, z_e, z_lo, L = k["a"], k["b"], k["n"], k["z"], k["z_lo"], k["L"]; t = (b_ - a_)[:2] / L; hd = max(zmx - z_e, 0.0); dw = None
        q = RP[:, :2] - a_[:2]; tt = q @ t; ww = q @ n; s = (tt >= 0) & (tt <= L) & (ww <= 0.5)
        if s.any(): hd = min(hd, max(float(RP[s, 2].max()) - z_e, 0.0))
        q = MP[:, :2] - a_[:2]; tt = q @ t; ww = q @ n                           # Guard: steht vor der Wand ueber z_e ANDERER Messkoerper (Nachbarwand, Hauptturm
        s = (tt >= 0) & (tt <= L) & (ww >= 0.15) & (ww <= vorn) & (MP[:, 2] > z_e + 0.05)   # hinter einem Anbau), gehoert die Wolke dort nicht zur Traufe -> Deckel
        if s.any(): hd = min(hd, max(float(MP[s, 2].min()) - z_e, 0.0))
        if W is not None:
            q = W[:, :2] - a_[:2]; tt = q @ t; ww = q @ n; zz = W[:, 2]
            s = (tt >= 0) & (tt <= L) & (ww >= 0.05) & (ww <= vorn) & (zz > z_e) & (zz <= z_e + hd)
            if s.sum() >= 30:                                                    # zusammenhaengende Belegung ab z_e (0,1-m-Scheiben; eine Luecke >= vorn beendet sie -
                zs = np.sort(zz[s]); h_, _ = np.histogram(zs, bins=np.arange(z_e, z_e + hd + 0.1, 0.1))   # unter einer Untersicht ist Luft, eine fremde Traufe/Baum weit darueber zaehlt nicht)
                ng = max(1, int(round(vorn / 0.1))); leer = np.flatnonzero(np.convolve((h_ < 3).astype(int), np.ones(ng, int), "valid") == ng) if len(h_) >= ng else np.zeros(0, int)
                ende = z_e + 0.1 * (int(leer[0]) if len(leer) else len(h_))
                zs = zs[zs <= ende]
                if len(zs) >= 30: dw = float(np.percentile(zs, 95)) - z_e
        zo = z_e + rand + max(0.0, min(dw or 0.0, hd)); ext = min(vorn, 0.5 * L)
        p0 = np.r_[a_[:2] - ext * t, z_lo]; p1 = np.r_[b_[:2] + ext * t, z_lo]; h_ = zo + vorn
        i = len(V); V += [p0, p1, np.r_[p1[:2], h_], np.r_[p0[:2], h_]]; F += [[i, i + 1, i + 2], [i, i + 2, i + 3]]
        i = len(V); V += [np.r_[p0[:2], zo], np.r_[p1[:2], zo], np.r_[p1[:2] + vorn * n, zo], np.r_[p0[:2] + vorn * n, zo]]; F += [[i, i + 1, i + 2], [i, i + 2, i + 3]]   # DECKE
        Z.append(dict(a=a_[:2].tolist(), t=t.tolist(), n=n.tolist(), L=L, ext=ext, z_e=round(z_lo, 3), z_oben=round(zo, 3), wolke_dachfuss=None if dw is None else round(z_e + dw, 3)))
    m = trimesh.Trimesh(np.array(V), np.array(F), process=False)
    nw = sum(z["wolke_dachfuss"] is not None for z in Z)
    return m, Z, f"{len(Z)} Wandoberkanten z {min(z['z_e'] for z in Z):.2f}..{max(z['z_e'] for z in Z):.2f}, Zone bis z {max(z['z_oben'] for z in Z):.2f} (Rand {rand} m, Wolken-Dachfuss an {nw})"


def suchfenster_trifft(netz, C, Q, vorn, band, huelle=True):
    """Liegt der Punkt Q (N x 3) im Suchfenster des Kanten-Sweeps (kanten_tiefe_sweep_flaeche.py --flaeche netz --vorn --band [--huelle]) fuer Strahlen von C aus?
    Gleiche Rechnung wie der Sweep: erster Treffer t0, Fenster t0 - vorn*sk .. t0 + band*sk mit sk = 1/max(|cos|, 0,5); ohne Treffer (huelle) Eintritt in die um vorn
    vergroesserte Huellbox, Fenster tin .. tin + vorn + band. Fuer Diagnose und den Waechter (1122: 0-4 % der Traufpunkte im alten Fenster)."""
    C = np.asarray(C, float); d = np.asarray(Q, float) - C; L = np.linalg.norm(d, axis=1); d = d / L[:, None]
    loc, ir, it = netz.ray.intersects_location(np.repeat(C[None], len(d), 0), d, multiple_hits=False)
    tz = np.full(len(d), np.nan); tz[ir] = np.linalg.norm(loc - C, axis=1); sk = np.ones(len(d)); sk[ir] = 1.0 / np.maximum(np.abs(np.einsum("ij,ij->i", d[ir], np.asarray(netz.face_normals)[it])), 0.5)
    h = ~np.isnan(tz); ok = h & (L >= tz - vorn * sk) & (L <= tz + band * sk)
    if huelle and (~h).any():
        lo3, hi3 = netz.bounds[0] - vorn, netz.bounds[1] + vorn; dd = np.where(np.abs(d) < 1e-9, 1e-9, d); t1 = (lo3 - C) / dd; t2 = (hi3 - C) / dd
        tin = np.minimum(t1, t2).max(1); tout = np.maximum(t1, t2).min(1); ok |= (~h) & (tout > tin) & (tin > 0.5) & (L >= tin) & (L <= tin + vorn + band)
    return ok


def in_traufzone(P, Z, vorn, band):
    """Punkte P (N x 3) im Quader einer Traufzone: entlang -ext..L+ext, vor der Wand -band..vorn, z_e - 0,05 .. z_oben."""
    ok = np.zeros(len(P), bool)
    for z in Z:
        q = P[:, :2] - np.asarray(z["a"]); tt = q @ np.asarray(z["t"]); ww = q @ np.asarray(z["n"])
        ok |= (tt >= -z["ext"]) & (tt <= z["L"] + z["ext"]) & (ww >= -band - 0.05) & (ww <= vorn + 0.05) & (P[:, 2] >= z["z_e"] - 0.05) & (P[:, 2] <= z["z_oben"])
    return ok


def traufzone_lauf(a, S, sq, skala, vorn, KW, SD, SW):
    """Zweiter Sweep um die Traufschuerze (gleiche Kameras/Stabilkarten, Blickziel aus dem Messkoerper), Punkte nur in der Traufzone -> an sweep.npz
    angehaengt (Rohlauf DIR/sweep_traufe.npz). ALLE gewaehlten Fotos als Referenz (nur Pixel auf der Schuerze, 1122 CPU 8 s fuer 80): mit 30 sah an 1122 +n nur
    1-2 Referenzen die Stirn-Unterkante (Formfamilie verlangt 3). Jeder Ausfall laesst sweep.npz unveraendert (Fallback = alter Suchraum)."""
    import trimesh
    W = None
    if a.wolke and os.path.exists(a.wolke):
        try:
            lo, hi = S.bounds; W = np.load(a.wolke, mmap_mode="r"); st = max(1, len(W) // 2_000_000); W = np.asarray(W[::st, :3], np.float32)
            W = W[np.all((W >= lo - vorn - 1.0) & (W <= hi + vorn + 1.0), 1)]
        except Exception: W = None
    m, Z, txt = traufzone(S, vorn, a.band, a.traufzone_rand, W)
    info = dict(text=txt, rand_m=a.traufzone_rand, zonen=Z[:60], zonen_anzahl=len(Z))
    if m is None: return info
    v2 = min(max([vorn] + [z["z_oben"] - z["z_e"] for z in Z]), 2.0 * vorn); info["vorn_m"] = round(v2, 2)   # Fenster vor Schuerze/Decke deckt die Zonenhoehe (Decke: steile
    # Strahlen), hoechstens 2 x vorn (= Strahlkappung des Sweeps; 1122: eine Rundturm-Zone 8,5 m hoch haette das Fenster fuer alle auf 8,5 m gezogen)
    sp = os.path.join(a.aus, "traufschuerze.stl"); m.export(sp); ST = os.path.join(a.aus, "sweep_traufe.npz"); lo, hi = m.bounds
    box = ",".join(f"{x:.2f}" for x in np.r_[lo - 1.0, hi + 1.0])
    r = subprocess.run([PY, "-I", os.path.join(ROOT, "tools/kanten_tiefe_sweep_flaeche.py"), KW, SD, ST, "--flaeche", sp, "--flaeche_skala", "1.0", "--box3", box,
                        "--band", str(a.band), "--ziel_auto", "--ziel_flaeche", sq, "--ziel_skala", str(skala), "--nbdist", "80", "--refs", str(max(a.refs, a.max_fotos)), "--nb", "12",
                        "--maxpx", "40000", "--geraet", a.geraet, "--vorn", f"{v2:.2f}"], capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(ST):
        info["text"] += f"; Sweep ausgefallen (rc {r.returncode}: {((r.stdout + r.stderr).strip().splitlines() or ['?'])[-1][:160]}) - sweep.npz ohne Traufzone"; return info
    try:
        Z1 = dict(np.load(SW)); Z2 = dict(np.load(ST)); ok = in_traufzone(Z2["P"].astype(float), Z, vorn, a.band)
        f1 = [str(x) for x in Z1["fotos"]]; f2 = [str(x) for x in Z2["fotos"]]; ref2 = np.array([f1.index(f2[i]) if f2[i] in f1 else -1 for i in Z2["ref"]], int) if len(Z2["ref"]) else np.zeros(0, int)
        ok &= ref2 >= 0
        Z1.update(P=np.vstack([Z1["P"], Z2["P"][ok].astype(Z1["P"].dtype)]), s=np.concatenate([Z1["s"], Z2["s"][ok].astype(Z1["s"].dtype)]), ref=np.concatenate([Z1["ref"], ref2[ok].astype(Z1["ref"].dtype)]))
        np.savez(SW, **Z1); info.update(punkte=int(ok.sum()), roh=int(len(ok)))
        info["text"] += f"; {int(ok.sum())} Kantenpunkte in der Traufzone angehaengt (von {len(ok)})"
    except Exception as e_: info["text"] += f"; Zusammenfuehren ausgefallen ({type(e_).__name__}: {str(e_)[:120]}) - sweep.npz ohne Traufzone"
    return info


def abstand(A, B, geraet):
    """Abstand jedes Punkts aus A zum naechsten aus B (GPU gpu_knn; cpu = cKDTree fuer den Waechter-Test)."""
    if geraet == "cpu":
        from scipy.spatial import cKDTree
        return cKDTree(np.asarray(B, float)).query(np.asarray(A, float))[0]
    from gpu_knn import min_abstand
    return np.asarray(min_abstand(A, B))


def wolke_veto(P, wolke, veto_m, lo, hi, geraet):
    """Lage-Veto aus der dichten Wolke (nur grobe Ausreisser weg, nie Form): Kantenpunkte weiter als veto_m von jeder Wolkenstelle (Raster 0,1 m in der Box) fallen weg."""
    W = np.load(wolke, mmap_mode="r"); st = max(1, len(W) // 2_000_000); W = np.asarray(W[::st, :3], np.float32)
    W = W[np.all((W >= lo) & (W <= hi), 1)]
    if len(W) < 1000: return np.ones(len(P), bool), f"zu wenig Wolkenpunkte in der Box ({len(W)}) - kein Veto"
    W = np.unique(np.floor(W / 0.1).astype(np.int32), axis=0).astype(np.float32) * 0.1 + 0.05
    ok = abstand(P, W, geraet) <= veto_m
    return ok, f"{int((~ok).sum())} von {len(P)} Kantenpunkten weiter als {veto_m} m von der Wolke (verworfen)"


def modellkanten(m, winkel=30.0, schritt=0.05):
    import trimesh
    adj = m.face_adjacency; ang = m.face_adjacency_angles; E = m.face_adjacency_edges[ang > np.radians(winkel)]
    rand = trimesh.grouping.group_rows(m.edges_sorted, require_count=1); E = np.vstack([E, m.edges_sorted[rand]]) if len(rand) else E
    if not len(E): return np.zeros((0, 3))
    # 21.11.2026 (Tempo: ebenen_abweichung 150 s, davon 79 s hier - Python-Schleife mit 1,26 Mio. linspace): vektorisiert, gleiche Rechenschritte wie
    # A + (B - A) * np.linspace(0, 1, k) je Kante (t_i = i * (1/(k-1)), letzter Punkt genau 1) -> bitgleich (tools/test_kette_tempo.py)
    E = np.asarray(E); V = np.asarray(m.vertices, float); A = V[E[:, 0]]; D = V[E[:, 1]] - A
    L = np.sqrt(np.einsum("ij,ij->i", D, D)); k = np.maximum(2, (L / schritt).astype(int) + 1); kante = np.repeat(np.arange(len(E)), k)
    i = np.arange(int(k.sum())) - np.repeat(np.cumsum(k) - k, k); t = i * (1.0 / (k[kante] - 1)); t[np.cumsum(k) - 1] = 1.0
    return A[kante] + D[kante] * t[:, None]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--ausrichtung", required=True); ap.add_argument("--bilder", required=True)
    ap.add_argument("--aus", required=True); ap.add_argument("--max_fotos", type=int, default=80); ap.add_argument("--refs", type=int, default=30)
    ap.add_argument("--suchraum", choices=("messkoerper", "modell"), default="messkoerper", help="messkoerper = modellfrei (Standard, Kreisfall 22.11.2026); modell = alter, zirkulaerer Weg um das Vormodell")
    ap.add_argument("--messkoerper", default="", help="fertiger Messkoerper-STL (mm wie das Objekt-STL); Standard: tools/fassade_ortho.py --nur-messkoerper DIR/messkoerper.stl")
    ap.add_argument("--vorn", type=float, default=2.0, help="Suchraum vor der Messflaeche (m, senkrecht): Vordach/Erker/Traufe; nur --suchraum messkoerper")
    ap.add_argument("--traufzone_rand", type=float, default=1.0, help="Suchraum ueber der Wandoberkante bis Dachfuss (Wolke) bzw. LoD2-Traufe + RAND m (zweiter Sweep um die Traufschuerze); 0 = aus (alter Suchraum)")
    ap.add_argument("--wolke", default="", help="dichte Wolke (npy N x 3, Modellrahmen) nur als LAGE-VETO und fuer die Hoehe der Traufzone"); ap.add_argument("--veto_m", type=float, default=1.5)
    ap.add_argument("--geraet", default="cuda", help="cpu nur fuer den Waechter-Test"); ap.add_argument("--stabil_vorhanden", action="store_true", help="Stabilkarten liegen schon in DIR/stabil (Test)")
    ap.add_argument("--band", type=float, default=0.5); ap.add_argument("--tol", type=float, default=0.15); ap.add_argument("--nur_bewerten", action="store_true"); ap.add_argument("--name", default="", help="Zusatz fuer Bericht/Bild (z.B. _fertig: Bewertung des fertigen Modells nach Fassaden/Bauplan mit dem Sweep der Kantenstufe)")
    a = ap.parse_args(); import trimesh
    objp = os.path.abspath(a.objekt); obj = json.load(open(objp)); od = os.path.dirname(objp); os.makedirs(a.aus, exist_ok=True)
    A = json.load(open(a.ausrichtung if os.path.isabs(a.ausrichtung) else os.path.join(ROOT, a.ausrichtung)))
    skala = float(obj.get("stl_massstab", 87)) / 1000.0; stl = os.path.join(ROOT, obj["stl"])   # Modellrahmen = STL-Meter (kameras_aus_buendel)
    bericht = dict(objekt=os.path.relpath(objp, ROOT), stl=obj["stl"], ausrichtung=a.ausrichtung, start=time.strftime("%Y-%m-%d %H:%M"))
    KJ, KW, SD, SW = (os.path.join(a.aus, n) for n in ("kam.json", "kam_wahl.json", "stabil", "sweep.npz"))
    def ende(fehler):
        bericht["fehler"] = fehler; json.dump(bericht, open(os.path.join(a.aus, f"kanten_bericht{a.name}.json"), "w"), indent=1, ensure_ascii=False); print(fehler, flush=True); return 4
    if not a.nur_bewerten:
        S, sq, squelle = messkoerper_laden(a, obj, objp, skala); bericht.update(suchraum=a.suchraum, suchraum_quelle=squelle, suchraum_stl=os.path.relpath(sq, ROOT))
        print(f"Suchraum: {squelle}", flush=True)
        if S is None: return ende(f"KEIN modellfreier Suchraum ({squelle}) - LoD2/rahmen im Objekt pruefen; --suchraum modell waere der zirkulaere alte Weg")
        vorn = a.vorn if a.suchraum == "messkoerper" else 0.0; slo, shi = S.bounds; box = ",".join(f"{x:.2f}" for x in np.r_[slo - vorn - 1.0, shi + vorn + 1.0])
        K = kameras(A, a.bilder); json.dump(K, open(KJ, "w"))
        V = S.sample(4000, seed=0) if len(S.faces) else S.vertices; wahl, sek = waehlen(K, np.asarray(V), a.max_fotos)      # Kameraauswahl gegen den Messkoerper (nicht das Vormodell)
        json.dump({f: K[f] for f in wahl}, open(KW, "w")); bericht.update(kameras=len(K), gewaehlt=len(wahl), sektoren=sek, vorn_m=vorn)
        print(f"Kameras {len(K)}, gewaehlt {len(wahl)} (Sektoren {sek})", flush=True)
        if len(wahl) < 6: return ende("weniger als 6 Kameras sehen den Messkoerper")
        if not a.stabil_vorhanden: subprocess.run([PY, "-I", os.path.join(ROOT, "tools/stabil_alle.py"), KW, a.bilder, SD], check=True)
        subprocess.run([PY, "-I", os.path.join(ROOT, "tools/kanten_tiefe_sweep_flaeche.py"), KW, SD, SW, "--flaeche", sq, "--flaeche_skala", str(skala), "--box3", box,
                        "--band", str(a.band), "--ziel_auto", "--nbdist", "80", "--refs", str(a.refs), "--nb", "12", "--maxpx", "40000", "--geraet", a.geraet]
                       + (["--vorn", str(vorn), "--huelle"] if vorn > 0 else []), check=True)
        if a.traufzone_rand > 0 and vorn > 0:                                   # 24.11.2026: zweiter Lauf um die Traufschuerze (Traufe/Dachfuss ueber der Wandoberkante)
            bericht["traufzone"] = traufzone_lauf(a, S, sq, skala, vorn, KW, SD, SW)
            print("Traufzone:", bericht["traufzone"].get("text"), flush=True)
        if a.wolke and os.path.exists(a.wolke):                                 # Lage-Veto (KERNMETHODE: Wolke nie Form, nur Lage)
            try:
                Z = dict(np.load(SW)); ok, txt = wolke_veto(Z["P"].astype(float), a.wolke, a.veto_m, slo - vorn - 1.0, shi + vorn + 1.0, a.geraet)
                if not ok.all(): np.savez(SW, **{k: (v[ok] if k in ("P", "s", "ref") else v) for k, v in Z.items()})
                bericht["wolke_veto"] = txt
            except Exception as e_: bericht["wolke_veto"] = f"ausgefallen ({type(e_).__name__}: {str(e_)[:150]}) - Kanten ohne Veto"
            print("Wolke-Veto:", bericht["wolke_veto"], flush=True)
    Z = np.load(SW); P = Z["P"].astype(float); bericht["sweep_punkte"] = int(len(P))
    if len(P) < 2000: return ende(f"nur {len(P)} Kantenpunkte")
    if not os.path.exists(stl): return ende(f"Kanten gefunden ({len(P)} Punkte), aber kein Modell {obj['stl']} zum Bewerten")
    m = trimesh.load(stl); m.apply_scale(skala); lo, hi = m.bounds                # das gebaute Modell wird nur BEWERTET, es bestimmt keine Kante
    E = modellkanten(m); dP = abstand(P, E, a.geraet); dE = abstand(E, P, a.geraet)
    belegt = dE < 1.0                                                          # nur Modellkanten, in deren Naehe ueberhaupt Fotokanten gefunden wurden (sonst ungesehen)
    prae = float((dE[belegt] < a.tol).mean()) if belegt.any() else 0.0; rec = float((dP < a.tol).mean()); f1 = 2 * prae * rec / max(prae + rec, 1e-9)
    from dach_bauen import seiten_aus_rahmen
    try: sn = seiten_aus_rahmen(obj)
    except Exception: sn = {"+x": "+x", "-x": "-x", "+y": "+y", "-y": "-y"}
    F = P[dP >= a.tol]; mid = (lo + hi) / 2; hauf = []
    if len(F):
        z = np.floor(F / 0.5).astype(int); u, inv, cnt = np.unique(z, axis=0, return_inverse=True, return_counts=True)
        for i in np.argsort(-cnt)[:40]:
            if cnt[i] < 30: break
            c = F[inv.ravel() == i].mean(0); d = c[:2] - mid[:2]; s = ("+x" if d[0] > 0 else "-x") if abs(d[0]) / max(hi[0] - lo[0], 1) > abs(d[1]) / max(hi[1] - lo[1], 1) else ("+y" if d[1] > 0 else "-y")
            hauf.append(dict(mitte=[round(float(x), 2) for x in c], punkte=int(cnt[i]), seite=sn.get(s, s), hoehe_m=round(float(c[2] - lo[2]), 2)))
    bericht.update(modellkanten_proben=int(len(E)), modellkanten_belegt=round(float(belegt.mean()), 3), praezision=round(prae, 3), recall=round(rec, 3), f1=round(f1, 3), tol_m=a.tol,
                   band_m=a.band, fehlende_kanten_haufen=hauf[:20], hinweis="Recall niedrig = Fotokanten ohne Modellkante (fehlende Features: Fenster, Gesimse, Lisenen ...); Praezision niedrig = Modellkanten ohne Fotokante (erfundene/falsch liegende Form)")
    json.dump(bericht, open(os.path.join(a.aus, f"kanten_bericht{a.name}.json"), "w"), indent=1, ensure_ascii=False)
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 3, figsize=(18, 7)); ok = dP < a.tol; rng = np.random.default_rng(0); sel = rng.choice(len(P), min(len(P), 120000), replace=False)
    for k, (i, j, t) in enumerate([(0, 2, f"Ansicht entlang y ({sn.get('-y', '-y')})"), (1, 2, f"Ansicht entlang x ({sn.get('-x', '-x')})"), (0, 1, "Draufsicht")]):
        x = ax[k]; s = sel[~ok[sel]]; x.scatter(P[s, i], P[s, j], s=0.3, c="orange", label="Fotokante ohne Modellkante"); s = sel[ok[sel]]; x.scatter(P[s, i], P[s, j], s=0.3, c="green", label="Fotokante = Modellkante")
        r = dE >= a.tol; x.scatter(E[r & belegt, i], E[r & belegt, j], s=0.5, c="red", label="Modellkante ohne Fotokante"); x.scatter(E[~belegt, i], E[~belegt, j], s=0.3, c="lightgray", label="Modellkante ungesehen")
        x.set_aspect("equal"); x.set_title(t)
    ax[0].legend(loc="upper left", markerscale=12, fontsize=8)
    fig.suptitle(f"{obj.get('name', '')} Kantenstufe: Praezision {prae:.2f}  Recall {rec:.2f}  F1 {f1:.2f}  (tol {a.tol} m, {len(P)} Sweep-Punkte)"); fig.tight_layout()
    os.makedirs(os.path.join(od, "audit"), exist_ok=True); fig.savefig(os.path.join(od, "audit", f"kanten3d{a.name}.png"), dpi=90)
    print(f"KANTEN: Praezision {prae:.3f} Recall {rec:.3f} F1 {f1:.3f}; fehlende Haufen {len(hauf)}; Bild {os.path.join(od, 'audit', f'kanten3d{a.name}.png')}", flush=True); return 0


if __name__ == "__main__":
    sys.exit(main())
