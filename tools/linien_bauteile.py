#!/usr/bin/env python3
"""linien_bauteile.py - WAAGERECHTE LINIEN-BAUTEILE (Gesims, Band, Verdachung, Balkenkopf-Reihe) aus Mehrfoto-Kanten (Kettenstufe 'bauplan_linien', 24.11.2026).
Synonyme: Gesims, Kranzgesims, Gurtgesims, Fries, Band, Steinband, Leiste, Verdachung, Fensterverdachung, Vordaechlein, Balkenkopf, Balkenkoepfe, Konsole,
Kragstein, waagerechte Kante, fehlende Kanten, fehlende_kanten_haufen, Linien-Feature.
Verwandt/Vorlaeufer: tools/kanten_features.py + tools/features_in_objekt.py (Skill linien-features, nur Hand); tools/sohlbank_aus_fotos.py (Auskragung gegen
die Blickschraege kappa, gerade() wird hier wiederverwendet); tools/hoehen_angleich.py (gleicht nur VORHANDENE waagerechte Linien an); tools/kantenstufe.py:178
(fehlende_kanten_haufen = Arbeitsliste, hier erstmals gelesen); Handstand modelle/schwab_v3_gen.py:230-232/267 (Gesims, Verdachung, Balkenkoepfe per foto_mass).

ANLASS (modelle/WEG_HAND_ZU_KETTE.md Punkt 5, verlorene_gewinner Punkte 7+8): Gesims Sued/West, Verdachung Sued und Balkenkoepfe fehlten in der Kette - keine
Stufe las die waagerechten Kantenhaufen. NUTZERENTSCHEID 24.11.: alle Masse aus Fotos (Hoehe, Ausladung, Stueckzahl, Teilung); fehlt ein Mass, erst weitere
Fotos messen, dann foto-abgeleiteter Wert als ANNAHME mit Herleitung - nie feste Zahl, nie Handwert. Linienhafte Bauteile NIE per Farbschwelle/Wolke.

VERFAHREN je Wand (art 'wand' aus <ebenen>/ebenen.json, tools/ebenen_bauplan.py):
 1. KANTEN: triangulierte Fotokanten der Wandebene (<ebene>/sweep.npz, Mehrfoto-Sweep mit Stabilkarten) in Wandkoordinaten u, z, w_rel (w_rel = Abstand vor der
    geneigten Wandebene a + b_u (u - u_ref) + c_z (z - z_ref)). Waagerechte Linie = z-Zeile (Z_BIN), deren belegte u-Zellen (U_ZELLE, >= 2 Punkte) einen Lauf
    >= RUN_MIN_M mit Luecken <= LUECKE_M bilden (senkrechte Kanten fuellen nie einen Lauf). Benachbarte Zeilen -> eine Kante. Form belegt: >= MIN_FOTOS Referenzfotos.
 2. AUSGESCHLOSSEN (andere Stufen bauen dort): Uhr (uhren_auto.json), Vorbauten (vorbauten_auto.json), Fenster-Ober/Unterkanten (Sohlbank, Sturz), Tor-/Bogenkasten
    (oeffnungen_auto.json), Traufe/Umgang (umgang_auto.json z0 bzw. Wandoberkante), Wandraender (Eckquader, Ortsteine).
 3. AUSLADUNG je Kante, zwei unabhaengige Fotomessungen:
    (a) KAPPA (wie sohlbank_aus_fotos): in jedem Einzelfoto-Ortho der Wand (<fein>/ortho_<fid>_einzeln, 1 cm) staerkster waagerechter Helligkeitssprung nahe der
        Kante (Zeilenprofil = Median ueber die Spalten der Kante, Teilpixel) -> z_obs; kappa = (z_obs - C_z) / (C_w - s); Y = C_z + kappa C_w = z + kappa d.
        Ausgleichsgerade ueber >= MIN_FOTOS Fotos mit Blickspanne >= K_SPANNE: Achsabschnitt = wahre Hoehe, Steigung = Ausladung d (Streuung per Bootstrap).
        Gilt, wenn Streuung <= 50 % |d| oder |d| < Druckmindestmass bei kleiner Streuung (= gemessen flach).
    (b) SWEEP: Median w_rel der Kantenpunkte (Dreieckspunkte aus >= 3 Fotos). Waagerechte Kanten sind bei waagerechter Basis tiefenschwach -> nur Ersatz.
    Ausladung = (a), sonst (b) wenn deutlich (q25 > 0 und Median >= Druckmindestmass). Gemessen flach (Farbkante: Putz/Stein, Bildrand) -> KEIN Bauteil.
 4. BAUTEIL: vorstehende Kanten, die <= PAAR_MAX_M uebereinander liegen und sich in u ueberlappen, bilden EIN Profil (z, Ausladung je Kante); die naechste flache
    Kante darunter/darueber innerhalb 2 x Ausladung ist der Wandanschluss (Ausladung 0). Ohne Partnerkante: Hoehe = gemessene Ausladung (ANNAHME 45-Grad-Schraege,
    Herleitung im JSON). Typ: 'gesims' (Lauf >= GESIMS_ANTEIL der Wandbreite), 'verdachung' (kuerzer, Erkennerelement darunter), sonst 'band'.
    Ausladung unbestimmt, aber Form belegt -> Ausladung derselben Hoehe von einer ANDEREN Wand (gleiche Hoehe +- 0,3 m, dort gemessen) als ANNAHME mit Herleitung;
    sonst nicht gebaut + Eintrag 'foto_auftrag' (nie erfinden).
 5. BALKENKOEPFE: kompakte vorstehende Kantenhaufen (w_rel > 2 x Druckmindestmass, Breite <= KOPF_MAX_B, Hoehe <= KOPF_MAX_H, >= MIN_FOTOS) ausserhalb der
    Ausschlusszonen; REIHE = >= 2 gleich hohe, aehnlich grosse Haufen. Stueckzahl = Haufen, Teilung = Abstaende der u-Mitten, Groesse = Haufenausdehnung,
    Ausladung = (a) an Ober-/Unterkante, sonst (b).
 6. FEHLENDE_KANTEN_HAUFEN (kantenstufe.py, kanten_bericht.json): je Bauteil die Haufen in seiner Zone -> 'haufen' (Beleg, dass das Modell die Kante nicht hat).
Ausgabe: audit/linien_auto.json {fassaden: {fid: {o, d, n, bauteile: [...], balkenkoepfe: [...], verworfen: [...]}}} -> bauteile.linien_aus_json (Generator);
 Bild audit/linien_auto.jpg (Wandbild mit Kanten: gruen gebaut, orange flach/Farbkante, grau ausgeschlossen, rot Balkenkoepfe; rechts w_rel ueber z).
Aufruf: linien_bauteile.py <objekt.json> <ebenen-ordner> <fassade-ordner> [--fein <fassade_fein>] [--kanten <kanten_bericht.json>] [--aus J] [--bild B] [--nur f01]
rc 0 = mindestens ein Bauteil, 3 = nichts zu bauen (Bericht geschrieben), 1 = Eingaben fehlen.
Umgebung: /media/oem/scan/venv-seg/bin/python -I (numpy, scipy, cv2, matplotlib), CPU, < 1 GB RAM.
"""
import sys, os, json, glob, argparse, time
import numpy as np

HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)

MIN_PUNKTE = 40; KOPF_Z_MIN = 2.5; Z_BIN = 0.05; U_ZELLE = 0.25; LUECKE_M = 0.5; RUN_MIN_M = 1.0; MIN_FOTOS = 3; MIN_PKT_ZELLE = 2
K_SPANNE = 0.1; MAX_AUSLADUNG = 1.0; PAAR_MAX_M = 0.8; GESIMS_ANTEIL = 0.7; RAND_M = 0.5
VORBAU_UNTEN_M = 1.5; KOPF_MAX_B = 1.0; KOPF_MAX_H = 1.2; KOPF_DZ = 0.3; FENSTER_DZ = 0.25; MAX_KANTEN = 30


def druck_min():
    """Druckmindestmass in Gebaeude-Metern (MINMM x SCALE, wie bauteile.sohlbank) - kleinere Ausladung ist im Modell nicht darstellbar."""
    return float(os.environ.get("MINMM", "0.8")) * float(os.environ.get("SCALE", "87")) / 1000.0


# ------------------------------------------------------------------ Wandkoordinaten
def wand_rel(P, e):
    """Punkte P (N x 3, Modellrahmen) -> u, z, w_rel (Abstand vor der geneigten Wandebene der Ebene e aus ebenen.json)."""
    o, d, n = (np.asarray(e[k], float) for k in ("o", "d", "n"))
    u = (P[:, :2] - o) @ d; w = (P[:, :2] - o) @ n; z = P[:, 2]
    ne = e.get("neigung") or {}
    if "a" in ne: w0 = ne["a"] + ne.get("b_u", 0.0) * (u - ne.get("u_ref", 0.0)) + ne.get("c_z", 0.0) * (z - ne.get("z_ref", 0.0))
    else: w0 = float(e.get("w", 0.0))
    return u, z, w - w0


def ebene_w(e, u, z):
    """Lage der (geneigten) Wandebene bei (u, z), w ab o entlang n."""
    ne = e.get("neigung") or {}
    if "a" in ne: return float(ne["a"] + ne.get("b_u", 0.0) * (u - ne.get("u_ref", 0.0)) + ne.get("c_z", 0.0) * (z - ne.get("z_ref", 0.0)))
    return float(e.get("w", 0.0))


def in_wand(u, z, polys, rand=0.3):
    """Maske: (u, z) innerhalb eines Wandpolygons (fassaden.json polys_uz, um rand erweitert); ohne Polygone alles."""
    if not polys: return np.ones(len(u), bool)
    if isinstance(polys, str):
        try: polys = json.loads(polys)
        except Exception: return np.ones(len(u), bool)
    from matplotlib.path import Path
    m = np.zeros(len(u), bool); Q = np.column_stack([u, z])
    for pg in polys:
        if len(pg) >= 3: m |= Path(np.asarray(pg, float)).contains_points(Q, radius=rand) | Path(np.asarray(pg, float)[::-1]).contains_points(Q, radius=rand)
    return m


# ------------------------------------------------------------------ 1. waagerechte Kanten
def fotos_belegt(r, min_pkt=3):
    """Anzahl Referenzfotos, die eine Kante mit >= min_pkt Punkten tragen (kreuzende Fugenkanten liefern je Foto nur Einzelpunkte - Test 24.11.: eine Kante
    aus 2 Fotos zaehlte sonst 10 Fotos)."""
    _, c = np.unique(r, return_counts=True); return int((c >= min_pkt).sum())


def laeufe(zellen, luecke):
    """Sortierte belegte Zellindizes -> Liste (i0, i1) zusammenhaengender Laeufe (Luecke <= luecke Zellen)."""
    if len(zellen) == 0: return []
    L = []; a = b = zellen[0]
    for c in zellen[1:]:
        if c - b <= luecke + 1: b = c
        else: L.append((a, b)); a = b = c
    L.append((a, b)); return L


def kanten_finden(u, z, w, ref, zone, dw_max=0.07):
    """Waagerechte Kanten (Schritt 1). zone = (u0, u1, z0, z1) der Wand; Nachbarzeilen werden nur bei Tiefenunterschied <= dw_max (Druckmindestmass) vereint. Liefert Liste dict(z, u0, u1, punkte, fotos, w_med, w_q25, w_q75, idx)."""
    u0z, u1z = zone[0], zone[1]
    m = (u >= u0z - RAND_M) & (u <= u1z + RAND_M)
    iu = np.floor((u - u0z + RAND_M) / U_ZELLE).astype(int); iz = np.floor(z / Z_BIN).astype(int)
    zeilen = {}
    for b in np.unique(iz[m]):
        mb = m & (iz == b); zc, cnt = np.unique(iu[mb], return_counts=True); zc = zc[cnt >= MIN_PKT_ZELLE]
        best = None
        for a_, b_ in laeufe(list(zc), int(round(LUECKE_M / U_ZELLE))):
            lang = (b_ - a_ + 1) * U_ZELLE
            if lang >= RUN_MIN_M and (best is None or lang > best[2]): best = (a_, b_, lang)
        if best:
            ub_ = u0z - RAND_M + np.array([best[0], best[1] + 1]) * U_ZELLE; mm_ = mb & (u >= ub_[0]) & (u <= ub_[1])
            zeilen[int(b)] = best + (float(np.median(w[mm_])),)
    roh = []; frei = sorted(zeilen); dw = dw_max
    while frei:                                                          # benachbarte Zeilen mit ueberlappendem Lauf UND gleicher Tiefe -> eine Kante
        g = [frei.pop(0)]                                                # (Lauf 1122 f01: Verdachung = Wandanschluss 18,85 flach + Vorderkante 19,0-19,1 +0,08 m; zusammengelegt war sie 'unbestimmt')
        while (frei and frei[0] - g[-1] <= 2 and min(zeilen[frei[0]][1], zeilen[g[-1]][1]) >= max(zeilen[frei[0]][0], zeilen[g[-1]][0])
               and abs(zeilen[frei[0]][3] - zeilen[g[-1]][3]) <= dw): g.append(frei.pop(0))
        a_ = min(zeilen[b][0] for b in g); b_ = max(zeilen[b][1] for b in g)
        ua, ub = u0z - RAND_M + a_ * U_ZELLE, u0z - RAND_M + (b_ + 1) * U_ZELLE
        idx = np.flatnonzero(m & np.isin(iz, g) & (u >= ua) & (u <= ub))
        if len(idx) < MIN_PUNKTE: continue
        ww = w[idx]
        roh.append(dict(z=round(float(np.mean(z[idx])), 3), u0=round(float(max(ua, u0z)), 2), u1=round(float(min(ub, u1z)), 2), punkte=int(len(idx)),
                        fotos=fotos_belegt(ref[idx]), w_med=round(float(np.median(ww)), 3), w_q25=round(float(np.percentile(ww, 25)), 3),
                        w_q75=round(float(np.percentile(ww, 75)), 3), idx=idx))
    return roh


# ------------------------------------------------------------------ 2. Ausschlusszonen
def ausschluss(fid, F_aud, zone, uhr_marge=0.3):
    """Rechtecke (u0, u1, z0, z1, grund) anderer Stufen auf Wand fid und z-Grenzen (z_min, z_max) fuer Linien-Bauteile.
    F_aud = dict(uhren, vorbauten, fenster, oeffnungen, umgang) (geladene Audit-JSON oder None)."""
    R = []
    U = (F_aud.get("uhren") or {}).get(fid) or {}
    for x in U.get("uhren", []):
        r = 0.5 * float(x["d_aussen"]) + uhr_marge; R.append((x["u"] - r, x["u"] + r, x["z"] - r, x["z"] + r, "Uhr (uhren_auto)"))
    for Fv in (F_aud.get("vorbauten") or {}).get("fassaden", []):
        if Fv.get("id") != fid: continue
        for g in Fv.get("gruppen", []):
            if not g.get("verworfen"): R.append((g["u0"], g["u1"], g["z0"] - VORBAU_UNTEN_M, g["z1"] + 0.5, "Vorbau mit Konsolen darunter (vorbauten_auto)"))
    for q in ((F_aud.get("fenster") or {}).get(fid) or {}).get("fenster", []):
        R.append((q["u0"] - 0.3, q["u1"] + 0.3, q["z0"] - FENSTER_DZ, q["z1"] + FENSTER_DZ, "Fenster mit Sohlbank/Sturz (fenster_auto, sohlbank_aus_fotos)"))
    for Fo in (F_aud.get("ortsteine") or {}).get("fassaden", []):
        if Fo.get("id") != fid: continue
        for k in Fo.get("kanten", []):
            try: a_, b_ = sorted((float(k["u_kante"]), float(k["u_kante"]) + float(k.get("richtung", 1)) * float(k.get("lang_m") or 0.0)))
            except Exception: continue
            R.append((a_, b_, float(k["z0"]), float(k["z1"]), "Ortsteine (ortsteine_auto: Lagerfugen)"))
    for q in ((F_aud.get("oeffnungen") or {}).get(fid) or {}).get("oeffnungen", []):
        k = q.get("kasten")
        if k: R.append((k[0], k[1], k[2], k[3] + 0.3, "Tor/Bogen (oeffnungen_auto)"))
    z_max = float(zone[3]) - 0.3
    ug = F_aud.get("umgang") or {}
    if ug.get("gefunden") and ug.get("z0") is not None: z_max = min(z_max, float(ug["z0"]) - 0.2)
    return R, 0.3, z_max


def in_zone(u0, u1, z, R):
    """Grund, falls die Kante (u0..u1 bei z) zu >= 50 % in einem Ausschlussrechteck liegt, sonst None."""
    for a, b, c, d_, g in R:
        if c <= z <= d_:
            ov = max(0.0, min(u1, b) - max(u0, a))
            if ov >= 0.5 * max(u1 - u0, 1e-6): return g
    return None


# ------------------------------------------------------------------ 3a. Ausladung gegen die Blickschraege (Einzelfoto-Orthos)
def kamera_zentren(objekt, namen):
    """Kamerazentren (Modellrahmen) aus messprotokoll/K-<name>.json (wie sohlbank_aus_fotos)."""
    from sohlbank_aus_fotos import kamera_zentrum
    mp = os.path.join(os.path.dirname(os.path.abspath(objekt)), "messprotokoll"); C = {}
    for nm in namen:
        kf = os.path.join(mp, f"K-{nm}.json")
        if not os.path.exists(kf): continue
        try: K = json.load(open(kf)).get("kamera")
        except Exception: continue
        if isinstance(K, dict) and "rvec" in K: C[nm] = kamera_zentrum(K)
    return C


def kante_im_foto(g, rast, u0, u1, z, such=0.3):
    """Waagerechter Helligkeitssprung im Graubild g (Wandraster rast = (u0, z1, zelle), 0 = kein Foto) nahe Hoehe z ueber die Spalten u0..u1.
    Zeilenprofil = Median ueber die (je Spalte >= 90 % belegten) Spalten, >= 40 % der Spalten noetig. Unter den Spruengen >= 50 % des staerksten gilt der z
    naechste (zwei Kanten eines Gesimses liegen im Suchfenster). Teilpixel per Parabel. Liefert (z_obs, staerke, vorzeichen) oder None."""
    from scipy import ndimage as ndi
    ur, zr, c = rast; i0, i1 = int((zr - (z + such)) / c), int((zr - (z - such)) / c)
    j0, j1 = int((u0 - ur) / c), int((u1 - ur) / c); b = j1 - j0; j0, j1 = j0 + b // 10, j1 - b // 10
    i0, j0 = max(i0, 0), max(j0, 0); i1, j1 = min(i1, g.shape[0]), min(j1, g.shape[1])
    if i1 - i0 < 6 or j1 - j0 < 5: return None
    A = g[i0:i1, j0:j1].astype(np.float32); D = A > 0; sp = D.mean(0) >= 0.9
    if sp.mean() < 0.4: return None
    A = A[:, sp]; D = D[:, sp]
    A = ndi.gaussian_filter(np.where(D, A, np.median(A[D])), 1.0)
    p = np.median(A, axis=1)[::-1]; zz = (zr - (i0 + np.arange(i1 - i0) + 0.5) * c)[::-1]      # Index waechst mit z
    gr = np.abs(np.gradient(p)); ref = float(np.median(gr))
    pk = [i for i in range(1, len(gr) - 1) if gr[i] >= gr[i - 1] and gr[i] >= gr[i + 1] and gr[i] >= 0.5 * gr.max()]
    if not pk or gr.max() < 3.0 * max(ref, 0.5): return None             # kein deutlicher Sprung (Rauschen)
    i = min(pk, key=lambda k: abs(zz[k] - z)); s_ = float(np.sign(np.gradient(p)[i]))
    a_, b_, c_ = gr[i - 1], gr[i], gr[i + 1]; den = a_ - 2 * b_ + c_; di = 0.5 * (a_ - c_) / den if abs(den) > 1e-9 else 0.0
    return float(np.interp(i + np.clip(di, -0.5, 0.5), np.arange(len(zz)), zz)), float(gr[i]), s_


def flaeche_s(rel, rast, u0, u1, z, ersatz):
    """Lage der Ortho-Flaeche (relief_<fid>.png: (s + 10 m) in mm, 0 = keine) an der Kante - die Einzelfoto-Orthos liegen auf ihr (wie sohlbank_aus_fotos)."""
    if rel is None: return ersatz
    ur, zr, c = rast; i = int(round((zr - z) / c)); j0, j1 = max(0, int((u0 - ur) / c)), int((u1 - ur) / c)
    if not 0 <= i < rel.shape[0]: return ersatz
    R_ = rel[max(0, i - 3):i + 4, j0:j1]; R_ = R_[R_ > 0]
    return float(np.median(R_)) / 1000.0 - 10.0 if R_.size else ersatz


def ausladung_kappa(fotos, rast, kanten, F, versatz, rel=None):
    """(a) je Kante: Gerade Y = z + kappa d ueber die Einzelfotos (sohlbank_aus_fotos.gerade). fotos = [(name, g, C)].
    Ergebnis wird in die Kanten geschrieben: kappa = dict(d, streuung, z, fotos, spanne) oder dict(fehler)."""
    from sohlbank_aus_fotos import gerade
    o, d, n = (np.asarray(F[k], float) for k in ("o", "d", "n"))
    for K in kanten:
        X, Y = [], []; s_ = flaeche_s(rel, rast, K["u0"], K["u1"], K["z"], versatz); K["ortho_s"] = round(s_, 3)
        for nm, g, C in fotos:
            Cu, Cw, Cz = float((C[:2] - o) @ d), float((C[:2] - o) @ n) - s_, float(C[2])
            if Cw < 2.0: continue
            r = kante_im_foto(g, rast, K["u0"], K["u1"], K["z"])
            if r is None: continue
            ka = (r[0] - Cz) / Cw; X.append(ka); Y.append(Cz + ka * Cw)
        sp = float(np.ptp(X)) if X else 0.0
        if len(X) < MIN_FOTOS or sp < K_SPANNE:
            K["kappa"] = dict(fehler=f"{len(X)} Fotos mit Kante, Blickspanne {sp:.2f} (noetig >= {MIN_FOTOS} / {K_SPANNE})"); continue
        f = gerade(X, Y, MIN_FOTOS)
        if f is None or f["streuung_d"] is None: K["kappa"] = dict(fehler="Ausgleich nicht bestimmt", fotos=len(X)); continue
        K["kappa"] = dict(d=round(f["d"], 3), streuung=round(f["streuung_d"], 3), z=round(f["a"], 3), fotos=int(f["n"]), spanne=round(sp, 3))


def ausladung_entscheiden(K, dmin):
    """Schritt 3: setzt K['ausladung'] (m, 0 = flach), K['ausladung_aus'] und K['zustand'] ('vor', 'flach', 'unbestimmt').
    Reihenfolge (Lauf 1122 an der Kopie 24.11.: kappa-d flacher Farbkanten streute -0,32..+0,05 m - Registrierfehler der Einzelorthos wie in sohlbank_aus_fotos
    beschrieben): (1) Sweep eindeutig (Median >= Druckmindestmass, q25 >= 0; flach: |Median| < Druckmindestmass und IQR < 2x), (2) kappa nur als Beleg FUER eine Ausladung (Streuung <= 50 %), (3) sonst unbestimmt."""
    if K["fotos"] >= MIN_FOTOS and K["w_q25"] >= 0 and K["w_med"] >= dmin:
        K.update(ausladung=round(min(K["w_med"], MAX_AUSLADUNG), 3), ausladung_aus=f"Sweep-Median ({K['fotos']} Fotos, q25 {K['w_q25']:+.2f})", zustand="vor"); return
    if abs(K["w_med"]) < dmin and K["w_q75"] - K["w_q25"] < 2 * dmin:
        K.update(ausladung=0.0, ausladung_aus=f"Sweep flach (Median {K['w_med']:+.3f}, IQR {K['w_q75'] - K['w_q25']:.3f})", zustand="flach"); return
    kp = K.get("kappa") or {}
    if "d" in kp:
        d_, s_ = kp.get("d_wand", kp["d"]), kp["streuung"]
        if dmin <= d_ <= MAX_AUSLADUNG and s_ <= 0.5 * d_: K.update(ausladung=round(d_, 3), ausladung_aus=f"kappa ({kp['fotos']} Fotos, +-{s_:.3f})", zustand="vor"); return
        # kappa 'flach' entscheidet NICHT (Bias der Einzelorthos, s. o.) - Kante bleibt unbestimmt -> Uebertragung/Fotoauftrag
    K.update(ausladung=None, ausladung_aus="weder Sweep noch kappa eindeutig", zustand="unbestimmt")


# ------------------------------------------------------------------ 4. Profile
def ueberlapp(a, b): return max(0.0, min(a["u1"], b["u1"]) - max(a["u0"], b["u0"])) >= 0.5 * min(a["u1"] - a["u0"], b["u1"] - b["u0"])


def profile_bilden(kanten, dmin):
    """Vorstehende Kanten -> Profile (Liste von Kantengruppen). Wandanschluss = naechste flache Kante darunter (<= PAAR_MAX_M, gleich lang: >= 70 %% Ueberlappung,
    Unterseite/Unterkante des Bandes) bzw. darueber (<= min(PAAR_MAX_M, 2 x Ausladung), Abdeckung)."""
    vor = sorted([k for k in kanten if k["zustand"] == "vor"], key=lambda k: k["z"]); gr = []
    for k in vor:
        for g in gr:
            if any(abs(k["z"] - x["z"]) <= PAAR_MAX_M and ueberlapp(k, x) for x in g): g.append(k); break
        else: gr.append([k])
    out = []
    for g in gr:
        amax = max(x["ausladung"] for x in g); flach = [k for k in kanten if k["zustand"] == "flach" and any(ueberlapp(k, x) for x in g)]
        zlo, zhi = min(x["z"] for x in g), max(x["z"] for x in g); anschl = []
        gl = lambda k: min(k["u1"], max(x["u1"] for x in g)) - max(k["u0"], min(x["u0"] for x in g)) >= 0.7 * min(k["u1"] - k["u0"], max(x["u1"] for x in g) - min(x["u0"] for x in g))
        unten = [k for k in flach if zlo - PAAR_MAX_M <= k["z"] < zlo and gl(k)]; oben = [k for k in flach if zhi < k["z"] <= zhi + min(PAAR_MAX_M, 2 * amax) and gl(k)]
        if unten: anschl.append(max(unten, key=lambda k: k["z"]))
        if oben: anschl.append(min(oben, key=lambda k: k["z"]))
        out.append(dict(vor=g, anschluss=anschl))
    return out


def bauteil_aus_profil(P, breite, elemente, dmin):
    """Profil -> Bauteil-Eintrag (typ, u0, u1, z0, z1, profil [[z, a], ...], annahmen)."""
    g = P["vor"]; an = P["anschluss"]; ann = []
    pts = sorted([(x["z"], x["ausladung"]) for x in g] + [(x["z"], 0.0) for x in an])
    u0 = float(np.median([x["u0"] for x in g])); u1 = float(np.median([x["u1"] for x in g]))
    if len(g) == 1 and not an:                                         # nur eine Kante: Hoehe nicht gemessen -> aus der gemessenen Ausladung (45 Grad), ANNAHME
        z, a = pts[0]; pts = [(round(z - a, 3), 0.0), (z, a)]
        ann.append(f"Hoehe nicht als Kantenpaar gemessen: Unterseite als 45-Grad-Schraege = gemessene Ausladung {a:.2f} m (Herleitung: einzige Kante z {z:.2f}, Ausladung {g[0]['ausladung_aus']})")
    if pts[-1][1] > 0:                                                 # Oberseite: Abdeckung mindestens Druckmindestmass dick
        pts.append((round(pts[-1][0] + dmin, 3), pts[-1][1])); ann.append(f"Abdeckplatte ueber der obersten Kante {dmin:.3f} m = Druckmindestmass (keine Kante darueber gemessen)") if not an or max(x['z'] for x in an) < pts[-2][0] else None
    lang = u1 - u0
    if lang >= GESIMS_ANTEIL * breite: typ = "gesims"
    elif any(e_["u0"] < u1 and u0 < e_["u1"] and 0 <= min(p[0] for p in pts) - e_["z1"] <= 3.0 for e_ in elemente): typ = "verdachung"
    else: typ = "band"
    fotos = max(x["fotos"] for x in g)
    return dict(typ=typ, art=typ, u0=round(u0, 3), u1=round(u1, 3), z0=round(min(p[0] for p in pts), 3), z1=round(max(p[0] for p in pts), 3),
                profil=[[round(z_, 3), round(a_, 3)] for z_, a_ in pts], ausladung=round(max(p[1] for p in pts), 3), fotos=fotos,
                kanten=[dict(z=x["z"], u0=x["u0"], u1=x["u1"], ausladung=x["ausladung"], aus=x["ausladung_aus"], fotos=x["fotos"], punkte=x["punkte"], kappa=x.get("kappa")) for x in g + an],
                annahmen=[x for x in ann if x])


# ------------------------------------------------------------------ 5. Balkenkoepfe
def balkenkoepfe(u, z, w, ref, zone, R, zmin, zmax, linien_z, dmin):
    """Kompakte vorstehende Haufen -> Reihen (Liste dict(z0, z1, b, u [...], teilung, ausladung, fotos, aus))."""
    from scipy import ndimage as ndi
    thr = 2 * dmin; m = (w > thr) & (u > zone[0] + RAND_M) & (u < zone[1] - RAND_M) & (z > max(zmin, KOPF_Z_MIN)) & (z < zmax)      # unter KOPF_Z_MIN: Strassenmobiliar/Personen vor der Wand
    if m.sum() < 20: return [], []
    g = 0.2; u0, z0 = zone[0], 0.0
    iu = ((u[m] - u0) / g).astype(int); iz = ((z[m] - z0) / g).astype(int)
    A = np.zeros((iu.max() + 2, iz.max() + 2)); np.add.at(A, (iu, iz), 1)
    lab, nl = ndi.label(A >= 3); H = []; um, zm, wm, rm = u[m], z[m], w[m], ref[m]
    for i, sl in enumerate(ndi.find_objects(lab)):
        ua, ub = u0 + sl[0].start * g, u0 + sl[0].stop * g; za, zb = z0 + sl[1].start * g, z0 + sl[1].stop * g
        mm = (um >= ua) & (um < ub) & (zm >= za) & (zm < zb); nf = fotos_belegt(rm[mm])
        if ub - ua > KOPF_MAX_B or zb - za > KOPF_MAX_H or nf < MIN_FOTOS or mm.sum() < 15: continue
        zc = 0.5 * (za + zb)
        if in_zone(ua, ub, zc, R) or any(abs(zc - lz) <= 0.5 * (zb - za) + 0.1 for lz in linien_z): continue
        H.append(dict(u0=ua, u1=ub, z0=za, z1=zb, u=0.5 * (ua + ub), z=zc, fotos=nf, punkte=int(mm.sum()), w_med=float(np.median(wm[mm]))))
    reihen = []; frei = sorted(H, key=lambda h: h["z"])
    while frei:
        h = frei.pop(0); r = [h]
        for x in list(frei):
            if abs(x["z"] - h["z"]) <= KOPF_DZ: r.append(x); frei.remove(x)
        r.sort(key=lambda x: x["u"]); vb = [r[0]]                       # Haufen mit Luecke < eigener Breite = EIN Koerper (zwei Kantenhaelften eines Kopfes)
        for x in r[1:]:
            y = vb[-1]
            if x["u0"] - y["u1"] <= min(x["u1"] - x["u0"], y["u1"] - y["u0"]) + 1e-6:
                vb[-1] = dict(y, u0=y["u0"], u1=max(y["u1"], x["u1"]), z0=min(y["z0"], x["z0"]), z1=max(y["z1"], x["z1"]), fotos=max(y["fotos"], x["fotos"]),
                              punkte=y["punkte"] + x["punkte"], w_med=0.5 * (y["w_med"] + x["w_med"])); vb[-1]["u"] = 0.5 * (vb[-1]["u0"] + vb[-1]["u1"])
            else: vb.append(x)
        b_med = float(np.median([x["u1"] - x["u0"] for x in vb]))
        r = [x for x in vb if 0.5 <= (x["u1"] - x["u0"]) / b_med <= 2.0 and x["u1"] - x["u0"] <= KOPF_MAX_B]
        if len(r) >= 2:
            r.sort(key=lambda x: x["u"]); us = [round(x["u"], 2) for x in r]
            reihen.append(dict(typ="balkenkopf_reihe", n=len(r), u=us, teilung=[round(b - a, 2) for a, b in zip(us, us[1:])],
                               b=round(float(np.median([x["u1"] - x["u0"] for x in r])), 2), z0=round(float(np.median([x["z0"] for x in r])), 2),
                               z1=round(float(np.median([x["z1"] for x in r])), 2), ausladung=round(float(np.median([x["w_med"] for x in r])), 3),
                               ausladung_aus="Sweep-Median der Haufen (Kantenpunkte aus >= 3 Fotos)", fotos=min(x["fotos"] for x in r), haufen=r))
    return reihen, H


# ------------------------------------------------------------------ 6. fehlende Kanten
def haufen_zuordnen(haufen, F, u0, u1, z0, z1, rand=0.5):
    o, d, n = (np.asarray(F[k], float) for k in ("o", "d", "n")); out = []
    for h in haufen or []:
        c = np.asarray(h["mitte"], float); hu = float((c[:2] - o) @ d); hw = float((c[:2] - o) @ n)
        if abs(hw) <= 2.5 and u0 - rand <= hu <= u1 + rand and z0 - rand <= c[2] <= z1 + rand: out.append(dict(h, u=round(hu, 2)))
    return out


# ------------------------------------------------------------------ Bild
def bild(pfad, tafeln):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    if not tafeln: return
    fig, ax = plt.subplots(1, 2 * len(tafeln), figsize=(7 * len(tafeln), 14), gridspec_kw=dict(width_ratios=[3, 1.4] * len(tafeln)))
    ax = np.atleast_1d(ax)
    for k, T in enumerate(tafeln):
        a = ax[2 * k]; b = ax[2 * k + 1]
        if T.get("bild") is not None:
            ur, zr, c = T["rast"]; a.imshow(T["bild"], cmap="gray", extent=[ur, ur + T["bild"].shape[1] * c, zr - T["bild"].shape[0] * c, zr])
        for K in T["kanten"]:
            col = {"vor": "lime", "flach": "orange", "unbestimmt": "magenta"}.get(K.get("zustand"), "gray") if not K.get("aus") else "gray"
            a.plot([K["u0"], K["u1"]], [K["z"], K["z"]], color=col, lw=1.5 if col != "gray" else 0.8)
        for B in T["bauteile"]:
            a.add_patch(plt.Rectangle((B["u0"], B["z0"]), B["u1"] - B["u0"], max(B["z1"] - B["z0"], 0.05), fill=False, ec="cyan", lw=2))
            a.text(B["u0"], B["z1"] + 0.15, f"{B['typ']} {B['z0']:.2f}-{B['z1']:.2f} a {B['ausladung']:.2f}", color="cyan", fontsize=8, backgroundcolor="black")
        for Rr in T["koepfe"]:
            for x in Rr["haufen"]: a.add_patch(plt.Rectangle((x["u0"], x["z0"]), x["u1"] - x["u0"], x["z1"] - x["z0"], fill=False, ec="red", lw=2))
        a.set_title(f"{T['fid']}: Wandbild + Kanten (gruen vor, orange flach, grau ausgeschl.), cyan Bauteil, rot Balkenkopf", fontsize=8); a.set_xlabel("u (m)"); a.set_ylabel("z (m)")
        b.scatter(T["w"], T["z"], s=0.2, c="k", alpha=0.15); b.axvline(0, color="b", lw=0.8)
        for B in T["bauteile"]: b.plot([p[1] for p in B["profil"]], [p[0] for p in B["profil"]], "c-o", ms=3)
        b.set_xlim(-0.6, 1.0); b.set_ylim(a.get_ylim()); b.set_title("w_rel ueber z (Sweep) + Profil", fontsize=8); b.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(pfad, dpi=60); plt.close(fig)


# ------------------------------------------------------------------ Hauptablauf
def lade(p):
    try: return json.load(open(p)) if p and os.path.exists(p) else None
    except Exception: return None


def wand_messen(e, F, fid, F_aud, fein, objekt, haufen, elemente, dmin, ohne_kappa=False):
    """Eine Wand: Kanten, Ausladung, Bauteile, Balkenkoepfe. Liefert (ergebnis-dict, tafel)."""
    Z = np.load(e["sweep"]); P = Z["P"].astype(float); ref = Z["ref"]; u, z, w = wand_rel(P, e)
    im = in_wand(u, z, F.get("polys_uz"))                                # nur Punkte auf DIESER Wand (Treppenturm/Anbau davor = andere Flaeche)
    P, ref, u, z, w = P[im], ref[im], u[im], z[im], w[im]
    zone = e["zone"]; breite = zone[1] - zone[0]
    R, zmin, zmax = ausschluss(fid, F_aud, zone)
    roh = kanten_finden(u, z, w, ref, zone, dmin)
    for K in roh:
        if K["fotos"] < MIN_FOTOS: K["aus"] = f"nur {K['fotos']} Fotos"
        elif not zmin <= K["z"] <= zmax: K["aus"] = f"ausserhalb z {zmin:.1f}..{zmax:.1f} (Sockel/Traufe/Umgang: eigene Stufen)"
        elif K["u1"] - K["u0"] < RUN_MIN_M: K["aus"] = "zu kurz nach Zuschnitt"
        elif K["u1"] - K["u0"] < 2 * RUN_MIN_M and (K["u0"] <= zone[0] + RAND_M or K["u1"] >= zone[1] - RAND_M): K["aus"] = "kurz am Wandrand (Eckquader/Ortsteine, Lagerfuge)"
        else: K["aus"] = in_zone(K["u0"], K["u1"], K["z"], R)
    kand = sorted([K for K in roh if not K.get("aus")], key=lambda k: -k["punkte"])[:MAX_KANTEN]
    for K in roh:
        if not K.get("aus") and K not in kand: K["aus"] = f"nicht unter den {MAX_KANTEN} staerksten"
    # (a) Einzelfoto-Orthos dieser Wand
    rast = None; fotos = []; versatz = 0.0
    FFj = lade(os.path.join(fein, "fassaden.json")) if fein else None
    FF = {x["id"]: x for x in (FFj or {}).get("fassaden", [])}
    ed = os.path.join(fein, f"ortho_{fid}_einzeln") if fein else ""
    if not ohne_kappa and fid in FF and os.path.isdir(ed) and kand:
        import cv2
        rs = FF[fid]["raster"]; rast = (rs["u0"], rs["z1"], rs["zelle"]); versatz = float((FF[fid].get("messflaeche") or {}).get("versatz", 0.0))
        namen = [os.path.basename(p)[:-4] for p in sorted(glob.glob(os.path.join(ed, "*.png")))]; C = kamera_zentren(objekt, namen)
        zlo = min(K["z"] for K in kand) - 0.5; zhi = max(K["z"] for K in kand) + 0.5
        i0, i1 = max(0, int((rast[1] - zhi) / rast[2])), int((rast[1] - zlo) / rast[2])
        for nm in namen:
            if nm not in C: continue
            g = cv2.imread(os.path.join(ed, nm + ".png"), cv2.IMREAD_GRAYSCALE)
            if g is None: continue
            G = np.zeros_like(g); G[i0:i1] = g[i0:i1]; fotos.append((nm, G, C[nm]))
        rp = os.path.join(fein, f"relief_{fid}.png"); rel = cv2.imread(rp, cv2.IMREAD_UNCHANGED) if os.path.exists(rp) else None
        ausladung_kappa(fotos, rast, kand, F, versatz, rel)
        for K in kand:                                                     # Ortho-Flaeche s gegen die geneigte Wandebene: kappa-d gilt ab s, Ausladung ab der Wand
            if "d" in (K.get("kappa") or {}): K["kappa"]["d_wand"] = round(K["kappa"]["d"] + K["ortho_s"] - ebene_w(e, 0.5 * (K["u0"] + K["u1"]), K["z"]), 3)
    for K in kand: ausladung_entscheiden(K, dmin)
    PR = profile_bilden(kand, dmin)
    bauteile = []
    for Pp in PR:
        B = bauteil_aus_profil(Pp, breite, elemente, dmin)
        B["haufen"] = haufen_zuordnen(haufen, F, B["u0"], B["u1"], B["z0"], B["z1"])
        B["wand_w"] = round(ebene_w(e, 0.5 * (B["u0"] + B["u1"]), B["z0"]), 3)
        bauteile.append(B)
    unbest = [K for K in kand if K["zustand"] == "unbestimmt"]
    linien_z = [K["z"] for K in roh if not K.get("aus") and K.get("zustand") == "vor" and K["u1"] - K["u0"] >= 2 * RUN_MIN_M]   # nur lange Linien sperren Koepfe
    koepfe, H = balkenkoepfe(u, z, w, ref, zone, R, zmin, zmax, linien_z, dmin)
    kopf_h = [h for r in koepfe for h in r["haufen"]]                    # kurze 'Baender' auf einem Kopf = dessen Ober-/Unterkante (Test 24.11.), kein eigenes Bauteil
    bauteile = [B for B in bauteile if B["typ"] == "gesims" or not any(B["u0"] < h["u1"] and h["u0"] < B["u1"] and B["z0"] - 0.1 <= h["z1"] and h["z0"] <= B["z1"] + 0.1 for h in kopf_h)]
    for r in koepfe:
        r["wand_w"] = round(ebene_w(e, float(np.median(r["u"])), r["z0"]), 3); r["haufen_fehlend"] = haufen_zuordnen(haufen, F, min(r["u"]) - r["b"], max(r["u"]) + r["b"], r["z0"], r["z1"])
    tafel = dict(fid=fid, kanten=roh, bauteile=bauteile, koepfe=koepfe, w=w[::max(1, len(w) // 40000)], z=z[::max(1, len(w) // 40000)])
    og = os.path.join(os.path.dirname(fein) if fein else "", "fassade", f"ortho_{fid}.png")
    if FF.get(fid) and os.path.exists(og):
        import cv2
        gb = cv2.imread(og, cv2.IMREAD_GRAYSCALE); FG = {x["id"]: x for x in (lade(os.path.join(os.path.dirname(og), "fassaden.json")) or {}).get("fassaden", [])}
        if gb is not None and fid in FG: rr = FG[fid]["raster"]; tafel.update(bild=gb, rast=(rr["u0"], rr["z1"], rr["zelle"]))
    ohne = lambda K: {k: v for k, v in K.items() if k != "idx"}
    erg = dict(o=F["o"], d=F["d"], n=F["n"], zone=zone, ebene=e["id"], sweep_punkte=int(len(P)), einzelfotos=len(fotos), bauteile=bauteile, balkenkoepfe=koepfe,
               kanten=[ohne(K) for K in roh], unbestimmt=[ohne(K) for K in unbest], ausschluss=[list(r) for r in R], z_grenzen=[zmin, zmax])
    return erg, tafel


def ausladung_uebertragen(waende, dmin):
    """Schritt 4 Ende: unbestimmte, aber belegte Kanten ohne Bauteil -> Ausladung einer anderen Wand auf gleicher Hoehe (+- 0,3 m), dort gemessen = ANNAHME mit Herleitung."""
    gemessen = [(fid, B) for fid, W in waende.items() for B in W["bauteile"] if not B.get("uebertragen")]
    for fid, W in waende.items():
        W["foto_auftrag"] = []
        for K in W["unbestimmt"]:
            if any(B["z0"] - 0.1 <= K["z"] <= B["z1"] + 0.1 and B["u0"] < K["u1"] and K["u0"] < B["u1"] for B in W["bauteile"]): continue
            q = [(f2, B) for f2, B in gemessen if f2 != fid and abs(0.5 * (B["z0"] + B["z1"]) - K["z"]) <= 0.3 + 0.5 * (B["z1"] - B["z0"])]
            if not q: W["foto_auftrag"].append(f"Kante z {K['z']:.2f} u {K['u0']:.2f}..{K['u1']:.2f}: Form belegt ({K['fotos']} Fotos), Ausladung nicht messbar - Fotos von schraeg unten/oben noetig"); continue
            f2, B = min(q, key=lambda x: abs(0.5 * (x[1]["z0"] + x[1]["z1"]) - K["z"]))
            dz = K["z"] - B["profil"][-2][0] if len(B["profil"]) >= 2 else 0.0
            prof = [[round(p[0] + dz, 3), p[1]] for p in B["profil"]]
            W["bauteile"].append(dict(typ=B["typ"], art=B["typ"], u0=K["u0"], u1=K["u1"], z0=min(p[0] for p in prof), z1=max(p[0] for p in prof), profil=prof, ausladung=B["ausladung"],
                                      fotos=K["fotos"], uebertragen=f2, wand_w=None, kanten=[{k: v for k, v in K.items() if k != "idx"}], haufen=[],
                                      annahmen=[f"ANNAHME Profil/Ausladung von Wand {f2} (gleiche Hoehe, dort {B['kanten'][0]['aus']}); hier nur Lage z {K['z']:.2f} aus {K['fotos']} Fotos"]))


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("ebenen"); ap.add_argument("fassade")
    ap.add_argument("--fein", default=""); ap.add_argument("--kanten", default=""); ap.add_argument("--aus", default=""); ap.add_argument("--bild", default="")
    ap.add_argument("--nur", nargs="*"); ap.add_argument("--ohne_kappa", action="store_true", help="nur Sweep-Ausladung (Test)")
    a = ap.parse_args(argv)
    objp = os.path.abspath(a.objekt); od = os.path.dirname(objp); au = os.path.join(od, "audit")
    EJ = lade(os.path.join(a.ebenen, "ebenen.json")); FJ = lade(os.path.join(a.fassade, "fassaden.json"))
    if not EJ or not FJ: print("ebenen.json oder fassaden.json fehlt"); return 1
    FF = {x["id"]: x for x in FJ["fassaden"]}
    F_aud = {k: lade(os.path.join(au, f)) for k, f in (("uhren", "uhren_auto.json"), ("vorbauten", "vorbauten_auto.json"), ("fenster", "fenster_auto.json"),
                                                        ("oeffnungen", "oeffnungen_auto.json"), ("umgang", "umgang_auto.json"), ("ortsteine", "ortsteine_auto.json"))}
    KB = lade(a.kanten) or {}; haufen = KB.get("fehlende_kanten_haufen") or []
    EL = (lade(os.path.join(a.fassade, "elemente.json")) or {}).get("fassaden", {})
    dmin = druck_min(); waende = {}; tafeln = []
    for e in EJ.get("ebenen", []):
        fid = e.get("fassade")
        if e.get("art") != "wand" or fid not in FF or (a.nur and fid not in a.nur) or not os.path.exists(e.get("sweep", "")): continue
        elem = list((EL.get(fid) or {}).get("elemente", [])) + list(((F_aud.get("fenster") or {}).get(fid) or {}).get("fenster", []))
        erg, taf = wand_messen(e, FF[fid], fid, F_aud, a.fein, objp, haufen, elem, dmin, a.ohne_kappa)
        waende[fid] = erg; tafeln.append(taf)
        print(f"{fid}: {len(erg['kanten'])} Kanten, {sum(1 for k in erg['kanten'] if k.get('zustand') == 'vor')} vorstehend, "
              f"{sum(1 for k in erg['kanten'] if k.get('zustand') == 'flach')} flach, {len(erg['unbestimmt'])} unbestimmt; Bauteile "
              + ", ".join(f"{B['typ']} z {B['z0']:.2f}-{B['z1']:.2f} u {B['u0']:.1f}..{B['u1']:.1f} a {B['ausladung']:.2f}" for B in erg["bauteile"])
              + "; Balkenkoepfe " + ", ".join(f"{r['n']} x b {r['b']:.2f} z {r['z0']:.2f}-{r['z1']:.2f}" for r in erg["balkenkoepfe"]), flush=True)
    ausladung_uebertragen(waende, dmin)
    n_b = sum(len(W["bauteile"]) + len(W["balkenkoepfe"]) for W in waende.values())
    J = dict(quelle="tools/linien_bauteile.py: waagerechte Fotokanten der Wandebenen (ebenen_bauplan sweep.npz) + Ausladung gegen die Blickschraege (Einzelfoto-Orthos) bzw. Sweep-Tiefe",
             zeit=time.strftime("%Y-%m-%d %H:%M"), druck_min_m=round(dmin, 4), kanten_bericht=a.kanten or None, fehlende_kanten_haufen=len(haufen),
             schwellen=dict(Z_BIN=Z_BIN, U_ZELLE=U_ZELLE, RUN_MIN_M=RUN_MIN_M, MIN_FOTOS=MIN_FOTOS, K_SPANNE=K_SPANNE, PAAR_MAX_M=PAAR_MAX_M, GESIMS_ANTEIL=GESIMS_ANTEIL),
             fassaden=waende, n_bauteile=n_b)
    aus = a.aus or os.path.join(au, "linien_auto.json"); os.makedirs(os.path.dirname(os.path.abspath(aus)), exist_ok=True)
    json.dump(J, open(aus, "w"), indent=1, ensure_ascii=False, default=lambda x: x.tolist() if hasattr(x, "tolist") else str(x))
    if a.bild: bild(a.bild, tafeln)
    print(f"-> {aus}: {n_b} Linien-Bauteile" + (f"; Bild {a.bild}" if a.bild else ""))
    return 0 if n_b else 3


if __name__ == "__main__":
    sys.exit(main())
