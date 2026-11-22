#!/usr/bin/env python3
"""vorbauten_bauplan.py - Vorbauten (Erker, Galerie, Vordach, Balkon) aus dem Ebenen-Sweep in eine BAULISTE uebersetzen (20.11.2026).

Bisher endete der Sweep (tools/fassade_tiefe.py -> vorbauten_fNN.json + tiefe_fNN.npz) als 'Vorschlag' - kein Generator las ihn,
der Schwabentor-Erker existierte nur im Hand-Generator schwab_v3 (Nutzer 20.11.: "Wir haben hier manuell alles gebastelt ... und jetzt
haben wir diese Faehigkeit verloren"). Dieses Werkzeug schliesst die Luecke; bauteile.vorbauten_aus_json baut die Liste.

Regeln (generisch, keine Objektwerte):
  KOERPER  = Kandidat 'Vorbau' mit ebener Front: w_median >= --w_min, Streuung w_p90 - w_p10 <= --streuung, Flaeche >= --min_m2,
             Front nicht am Rand des Suchbereichs (w_p90 <= Grenze - 0,25 m).
             (Durchblick durch eine Tordurchfahrt streut ueber > 1 m - faellt hier heraus; die Oeffnung ist Sache von oeffnungen_wandbild.)
  DACH     = Kandidat 'Vorbau' direkt ueber einem Koerper (Unterkante bis --dach_abstand ueber dessen Oberkante, u-Ueberlappung >= 50 %),
             darf streuen (schraege Dachflaeche).
  GESTALT  = Hoehenfeld je Zelle (--raster, Standard 0,2 m) aus der Sweep-Tiefe (nur 'gut'-Zellen, Median), im Rechteck Koerper..Dach;
             Zellen ohne sichere Tiefe = Median ihrer Zeile, sonst Wand (0). 3x3-Median gegen Einzelausreisser. Kein Spiegeln, kein Erfinden:
             was die Fotos nicht sicher sehen, steht nicht vor der Wand.
Aufruf:  vorbauten_bauplan.py <objekt.json> <fassaden-ordner> [--aus audit/vorbauten_auto.json]
Ausgabe: JSON {fassaden: [{id, o, d, n, w_wand, gruppen: [{koerper, dach, u0, z1, raster, w: [[...]] }]}]} + Bild audit/vorbauten_auto.jpg
rc 0 = mindestens ein Vorbau, rc 3 = keiner (kein Fehler).
"""
import sys, os, json, argparse, numpy as np
from scipy import ndimage as ndi


def wand_ebene_w(we, u, z):
    """Wandtiefe der geneigten Wandebene (fassade_tiefe 'wand_ebene') an (u, z); ohne Ebene 0."""
    if not we: return 0.0 * np.asarray(u, float)
    return we["a"] + we["b_u"] * (np.asarray(u, float) - we["u_ref"]) + we["c_z"] * (np.asarray(z, float) - we["z_ref"])


def wand_ebene_schaetzen(U, Z, w, gut, u_ref, z_ref, tol=0.08, max_neigung=0.10, min_gewinn=1.2, min_hub=0.2, min_anteil=0.2, n_iter=600, seed=0):
    """22.11.2026 (Schwabentor-1122 f00, Lotfehler ~2,6 Grad: Wand 0 m am Fuss, -1,4 m bei z 33): Wand als GENEIGTE Ebene w = a + b_u*(u-u_ref) + c_z*(z-z_ref)
    aus den sicheren Sweep-Zellen (RANSAC + kleinste Quadrate auf den Treffern, Treffer = |Rest| < tol). GUARD - nur wenn alle gelten, sonst None (konstanter Versatz wie bisher):
      Neigung |b_u|, |c_z| <= max_neigung; Hub der Ebene ueber die Fassade >= min_hub (sonst reicht konstant); Treffer >= min_gewinn x Treffer der besten Konstanten;
      Treffer >= min_anteil der sicheren Zellen. Vorbauten/Nischen liegen ausserhalb tol und ziehen die Ebene nicht (die Wand ist die groesste Flaeche)."""
    U = np.asarray(U, float); Z = np.asarray(Z, float); w = np.asarray(w, float); g = np.asarray(gut, bool)
    u, z, ww = U[g], Z[g], w[g]
    if len(ww) < 200: return None
    rng = np.random.default_rng(seed)
    if len(ww) > 30000: s = rng.choice(len(ww), 30000, replace=False); u, z, ww = u[s], z[s], ww[s]
    du, dz = u - u_ref, z - z_ref
    ks = np.arange(ww.min(), ww.max() + tol, tol / 2); konst = max(int((np.abs(ww - k) < tol).sum()) for k in ks)
    A = np.c_[np.ones_like(du), du, dz]; best = (0, None)
    for _ in range(n_iter):
        i = rng.choice(len(ww), 3, replace=False)
        try: p = np.linalg.solve(A[i], ww[i])
        except np.linalg.LinAlgError: continue
        if abs(p[1]) > max_neigung or abs(p[2]) > max_neigung: continue
        k = int((np.abs(A @ p - ww) < tol).sum())
        if k > best[0]: best = (k, p)
    if best[1] is None: return None
    p = best[1]
    for _ in range(3):
        m = np.abs(A @ p - ww) < tol
        if m.sum() < 3: return None
        p = np.linalg.lstsq(A[m], ww[m], rcond=None)[0]
    k = int((np.abs(A @ p - ww) < tol).sum()); hub = abs(p[1]) * (U.max() - U.min()) + abs(p[2]) * (Z.max() - Z.min())
    if abs(p[1]) > max_neigung or abs(p[2]) > max_neigung or hub < min_hub or k < min_gewinn * konst or k < min_anteil * len(ww): return None
    return dict(a=round(float(p[0]), 3), b_u=round(float(p[1]), 4), c_z=round(float(p[2]), 4), u_ref=round(float(u_ref), 3), z_ref=round(float(z_ref), 3), inlier=k, inlier_konst=konst,
                hub_m=round(float(hub), 2), neigung_grad=round(float(np.degrees(np.arctan(np.hypot(p[1], p[2])))), 2),
                quelle="fassade_tiefe: RANSAC-Ebene der sicheren Sweep-Zellen (Lot-/Lagefehler oder echter Anzug - die Ebene sagt nicht, welches)")


def gruppen_bilden(kand, w_min, streuung, min_m2, dach_abstand, w_grenze=9.0):
    vb = [k for k in kand if k.get("art") == "Vorbau"]
    # w_grenze: Front bis 0,25 m an den Rand des Suchbereichs = kein echtes Kostenminimum (Himmel, Dachkante, Bildrand; Schwabentor f03 20.11.: zwei Scheinkoerper bei +2,2 m)
    koerper = [k for k in vb if k["w_median"] >= w_min and (k["w_p90"] - k["w_p10"]) <= streuung and k["flaeche_m2"] >= min_m2 and k["w_p90"] <= w_grenze - 0.25]
    out = []
    for k in sorted(koerper, key=lambda k: -k["flaeche_m2"]):
        if any(not (k["u1"] <= g["u0"] or k["u0"] >= g["u1"] or k["z1"] <= g["z0"] or k["z0"] >= g["z1"]) for g in out): continue   # liegt in einer groesseren Gruppe
        daecher = [d for d in vb if d is not k and k["z1"] - 0.5 <= d["z0"] <= k["z1"] + dach_abstand and d["w_median"] >= w_min
                   and (min(k["u1"], d["u1"]) - max(k["u0"], d["u0"])) >= 0.5 * (d["u1"] - d["u0"])]
        dach = max(daecher, key=lambda d: d["flaeche_m2"]) if daecher else None
        g = dict(koerper=k, dach=dach, u0=min(k["u0"], dach["u0"]) if dach else k["u0"], u1=max(k["u1"], dach["u1"]) if dach else k["u1"],
                 z0=k["z0"], z1=dach["z1"] if dach else k["z1"])
        out.append(g)
    return out


def hoehenfeld(npz, w_wand, g, raster, w_max):
    w = npz["w"] - w_wand; gut = npz["gut"]; c = float(npz["zelle"]); u0n = float(npz["u0"]); z1n = float(npz["z1"])
    H, W = w.shape; nu = max(1, int(round((g["u1"] - g["u0"]) / raster))); nz = max(1, int(round((g["z1"] - g["z0"]) / raster)))
    feld = np.full((nz, nu), np.nan)
    for r in range(nz):
        za, zb = g["z1"] - (r + 1) * raster, g["z1"] - r * raster; i0, i1 = int((z1n - zb) / c), int(np.ceil((z1n - za) / c))
        for s in range(nu):
            ua, ub = g["u0"] + s * raster, g["u0"] + (s + 1) * raster; j0, j1 = int((ua - u0n) / c), int(np.ceil((ub - u0n) / c))
            i0_, i1_, j0_, j1_ = max(i0, 0), min(i1, H), max(j0, 0), min(j1, W)
            if i1_ <= i0_ or j1_ <= j0_: continue
            m = gut[i0_:i1_, j0_:j1_]
            if m.mean() >= 0.25: feld[r, s] = float(np.median(w[i0_:i1_, j0_:j1_][m]))
    for r in range(nz):                                         # Luecken: Median der Zeile (eine Erkerfront ist zeilenweise eben), sonst Wand
        z_ = feld[r]; ok = np.isfinite(z_)
        if ok.sum() >= max(2, 0.3 * nu): z_[~ok] = np.median(z_[ok])
    feld = np.nan_to_num(feld, nan=0.0)
    feld = ndi.median_filter(feld, 3, mode="nearest")
    return np.clip(feld, 0.0, w_max)


def stufe_je_spalte(B, gueltig, m_min):
    """GENERISCHER Stufen-Detektor (21.11.2026): je Spalte von B (Zeilen x Spalten x Kanaele, Zeile 0 = oben) die beste Zwei-Niveau-Zerlegung
    (Stueckweise konstant, kleinste Fehlerquadratsumme; Segmente >= m_min Zeilen). Keine Schwelle relativ zur Spitze - gesucht ist der WECHSEL des Niveaus.
    gueltig: (Zeilen x Spalten) bool, Spalte zaehlt nur bei >= 90 % gueltigen Zeilen. Liefert je Spalte (k, gewinn, kontrast) oder None;
    k = erste Zeile des unteren Segments, gewinn = 1 - SSE_2 / SSE_1 (Anteil der Streuung, den die Stufe erklaert), kontrast = |Mittel oben - Mittel unten|."""
    N = B.shape[0]; out = []
    if N < 2 * m_min + 1: return [None] * B.shape[1]
    k = np.arange(m_min, N - m_min + 1)
    for j in range(B.shape[1]):
        if gueltig[:, j].mean() < 0.9: out.append(None); continue
        x = B[:, j].reshape(N, -1).astype(float); cs = np.cumsum(x, 0); q = np.cumsum((x ** 2).sum(1))
        m1 = cs[k - 1] / k[:, None]; m2 = (cs[-1] - cs[k - 1]) / (N - k)[:, None]
        sse = q[-1] - k * (m1 ** 2).sum(1) - (N - k) * (m2 ** 2).sum(1); sse0 = q[-1] - N * ((cs[-1] / N) ** 2).sum()
        if sse0 <= 1e-9: out.append(None); continue
        i = int(np.argmin(sse)); out.append((int(k[i]), float(1 - sse[i] / sse0), float(np.linalg.norm(m1[i] - m2[i]))))
    return out


def stufenkante(z_spalten, gewinn, kontrast=None, gewinn_min=0.5, kontrast_min=30.0, band=0.5, lauf_min=0.5):
    """Gueltigkeits-Guard fuer eine durchgehende waagrechte Stufe: groesster ZUSAMMENHAENGENDER Spaltenlauf, dessen Stufen-z alle in einem Band
    der Hoehe `band` liegen, Gewinn >= gewinn_min und Kontrast >= kontrast_min (Lab 0-255; Schatten-/Lichtgrenze auf hellem Putz bleibt darunter).
    Spalten ohne Bild (nan) unterbrechen den Lauf nicht, zaehlen aber nicht. Gilt nur, wenn der Lauf >= lauf_min der Spalten MIT Bild deckt
    (ein Fenster, ein Schatten, eine Leitung deckt nur Teile). Liefert (z_median, anteil, (j0, j1)) oder (None, anteil_bester, None)."""
    z = np.asarray(z_spalten, float); g = np.asarray(gewinn, float); n = len(z); da = np.isfinite(z)
    k_ = np.full(n, np.inf) if kontrast is None else np.asarray(kontrast, float)
    ok = da & (g >= gewinn_min) & (k_ >= kontrast_min); best = (0, None)
    for j0 in range(n):
        if not ok[j0]: continue
        lo = hi = z[j0]; j1 = j0; j = j0 + 1; zahl = 1
        while j < n:
            if not da[j]: j += 1; continue
            if not ok[j] or max(hi, z[j]) - min(lo, z[j]) > band: break
            lo, hi = min(lo, z[j]), max(hi, z[j]); j1 = j; zahl += 1; j += 1
        if zahl > best[0]: best = (zahl, (j0, j1))
    anteil = best[0] / max(int(da.sum()), 1)
    if best[1] is None or anteil < lauf_min: return None, anteil, None
    j0, j1 = best[1]; zz = z[j0:j1 + 1]; return float(np.median(zz[np.isfinite(zz)])), anteil, best[1]


def anschluss_aus_uneinig(fein, fid, z_traufe, u0, u1, hoch=5.0, streifen=0.2, bild=None):
    """Wandanschluss eines Vordachs = OBERKANTE der Dachflaeche an der Wand, gemessen als waagrechte Fotokante im verschmolzenen Wandbild ortho_<fid>.png
    (Dachdeckung vor der Wand -> Wandputz darueber: Wechsel des Farb-NIVEAUS), bestaetigt durch die Uneinigkeitskarte uneinig_<fid>.png (die Anschlusslinie
    selbst macht die Fotos uneinig: Kante in leicht verschiedener Projektion). Suchfenster z_traufe+0,5 .. z_traufe+hoch, Spaltenstreifen `streifen` m.
    Liefert (z, quelle) oder (None, grund) -> Aufrufer behaelt die ANNAHME.
    21.11.2026 URSACHE ANNAHME 16,74 statt ~19,4 (Schwabentor-1120 f00): die alte Regel (Profil der Uneinigkeit ueber u gemittelt, 'letzte Stufe ueber 40 % der
    Spitze') setzte voraus, dass die Dachflaeche uneinig und die Wand darueber einig ist. Die Karte zeigt aber das Gegenteil: Dachflaeche und Wand liegen
    beide bei 25-36, nur die Anschlusslinie selbst ist ein heller Balken (43-45); 40 % der Spitze (~18) unterschreitet das Profil nie -> 'keine Stufe'.
    Dazu zog ein senkrechter Fremdbalken (Stange/Leitung, Wert 255) den u-Mittelwert hoch. Neu: Niveauwechsel je Spalte (stufe_je_spalte) + Guard
    zusammenhaengender Spaltenlauf (stufenkante) + Gegenprobe Uneinigkeit (Median ueber die Laufspalten, Gipfel +-0,4 m um die Kante >= 1,15 x Fenstermedian).
    MESSFEHLER 21.11.: Karte mit dem schon gebauten Vordach als Verdecker -> zirkulaer; verworfen, wenn fassaden.json verdecker_selbstbau.zustand = 'im_modell'."""
    import cv2
    FJ = json.load(open(os.path.join(fein, "fassaden.json")))
    if (FJ.get("verdecker_selbstbau") or {}).get("zustand") == "im_modell":
        return None, f"Wandbild {fid} mit gebauten Vorbauten als Verdecker gerechnet - zirkulaer, nicht verwendet"
    R_ = {f["id"]: f for f in FJ["fassaden"]}[fid]["raster"]; im = cv2.imread(os.path.join(fein, f"ortho_{fid}.png"))
    if im is None: return None, f"ortho_{fid}.png fehlt"
    c = float(R_["zelle"]) * float(R_["nz"]) / im.shape[0]; py = lambda z: int(round((R_["z1"] - z) / c)); px = lambda u: int(round((u - R_["u0"]) / c))
    ya, yb = max(0, py(z_traufe + hoch)), min(im.shape[0], py(z_traufe + 0.5)); xa, xb = max(0, px(u0)), min(im.shape[1], px(u1))
    w = max(1, int(round(streifen / c))); ns = (xb - xa) // w
    if yb - ya < int(1.0 / c) or ns < 3: return None, f"Wandbild {fid}: Suchfenster zu klein"
    lab = cv2.cvtColor(cv2.GaussianBlur(im, (0, 0), max(0.5, 0.03 / c)), cv2.COLOR_BGR2LAB).astype(float)[ya:yb, xa:xa + ns * w]
    gl = (im[ya:yb, xa:xa + ns * w].sum(2) > 0)
    B = lab.reshape(yb - ya, ns, w, 3).mean(2); G = gl.reshape(yb - ya, ns, w).all(2)
    st = stufe_je_spalte(B, G, max(2, int(0.3 / c)))
    zj = [R_["z1"] - (ya + s[0]) * c if s else np.nan for s in st]; gj = [s[1] if s else 0.0 for s in st]; kj = [s[2] if s else 0.0 for s in st]
    z_k, anteil, lauf = stufenkante(zj, gj, kj)
    if bild is not None: bild.update(z_spalten=zj, gewinn=gj, kontrast=kj, lauf=lauf, u_spalten=[R_["u0"] + (xa + (j + 0.5) * w) * c for j in range(ns)])
    if z_k is None: return None, f"Wandbild {fid}: keine durchgehende waagrechte Stufe (bester Spaltenlauf {anteil:.0%} < 50 %)"
    un = cv2.imread(os.path.join(fein, f"uneinig_{fid}.png"), 0); bestaetigt = "ohne Uneinigkeitskarte"
    if un is not None:
        cu = float(R_["zelle"]) * float(R_["nz"]) / un.shape[0]; ua, ub = xa + lauf[0] * w, xa + (lauf[1] + 1) * w
        U = un[int(ya * c / cu):int(yb * c / cu), int(ua * c / cu):int(ub * c / cu)].astype(float)
        pr = np.median(U, 1); zu = R_["z1"] - (int(ya * c / cu) + np.arange(len(pr)) + 0.5) * cu; nah = np.abs(zu - z_k) <= 0.4
        unten, oben = (zu < z_k - 0.1) & (zu > z_k - 1.0), (zu > z_k + 0.1) & (zu < z_k + 1.0)
        gipfel = pr[nah].max() if nah.any() else 0.0; med = max(float(np.median(pr)), 1.0)
        mu, mo = (float(np.median(pr[unten])) if unten.any() else 0.0), (float(np.median(pr[oben])) if oben.any() else 0.0)
        if gipfel >= 1.15 * med: bestaetigt = f"Uneinigkeit Gipfel {gipfel:.0f} vs. Median {med:.0f}"      # die Anschlusslinie selbst (Schwabentor f00)
        elif abs(mu - mo) >= 0.15 * max(mu, mo, 1.0) and unten.any() and oben.any(): bestaetigt = f"Uneinigkeit wechselt {mu:.0f} -> {mo:.0f}"   # Dachflaeche uneinig, Wand einig
        else: return None, f"Wandbild {fid}: Fotokante z {z_k:.2f} ohne Gegenprobe in der Uneinigkeitskarte (Gipfel {gipfel:.0f} < 1,15 x {med:.0f}, kein Niveauwechsel {mu:.0f}/{mo:.0f})"
    z_an = round(z_k, 2)
    return z_an, f"Wandbild {fid}: Fotokante Dach->Wand bei z {z_an} (Niveauwechsel je {streifen:.1f}-m-Spalte, Lauf {anteil:.0%} der Spalten, {bestaetigt})"


def galerie_messen(feld, g, raster, w_wand, fein=None, fid=None):
    """21.11.2026 (Nutzer: "der Erker ist doch generiert beim guten Fall ... hier voelliger Wurstelschrott"): wie im Hand-Generator schwab_v3 nur MASSE messen und das
    bewaehrte Bauteil bauteile.Wand.galerie bauen lassen. Aus dem Hoehenfeld (Zeile 0 = oben): Bruestungsband = unterstes zusammenhaengendes Zeilenband, in dem >= 50 % der
    Spalten >= halbe Frontausladung haben (z_boden, z_holm); Pfosten = Spaltenhaufen zwischen Holm und Dach mit Ausladung in >= 25 % der Zeilen (Enden zaehlen immer);
    Dach = Gruppe 'dach' (Traufe = Unterkante, Ausladung = Median). Streben aus dem feinen Wandbild: dunkle senkrechte Linien im 1-m-Band unter der Bruestung, regelmaessiger
    Abstand (Median der starken Spitzen), Fussende = tiefster Punkt, bis zu dem die Linie dunkel bleibt. Kein Ergebnis -> None (dann Hoehenfeld)."""
    k = g["koerper"]; front = k["w_median"]; nz, nu = feld.shape; zr = lambda i: g["z1"] - (i + 0.5) * raster
    voll = (feld >= 0.5 * front).mean(1); band = [i for i in range(nz) if voll[i] >= 0.5 and k["z0"] - 0.3 <= zr(i) <= k["z1"] + 0.3]
    if len(band) < 3: return None
    i_unten = max(band); i_oben = i_unten
    while i_oben - 1 in band: i_oben -= 1
    z_boden, z_holm = zr(i_unten) - raster / 2, zr(i_oben) + raster / 2
    if z_holm - z_boden < 0.6: return None
    # 21.11.2026 (hand_vergleich gegen schwab_v3: 'Dach' bei z 18,2-19,2 / +2,3 m lag 2 m zu hoch = Oberleitung vor dem Turm): TRAUFE = erstes Band ueber dem Holm,
    # in dem >= 40 % der Spalten Frontausladung haben (Traufkante/Raehm vor der Wand); das 'dach'-Kandidatenfeld zaehlt nur, wenn es direkt (<= 1 m) an dieses Band anschliesst.
    trauf = [i for i in range(nz) if voll[i] >= 0.4 and zr(i) > z_holm + 1.0]; d_ = g.get("dach")
    if trauf:
        i_t = max(trauf); i_to = i_t
        while i_to - 1 in trauf: i_to -= 1
        z_tu, z_to = zr(i_t) - raster / 2, zr(i_to) + raster / 2
        w_tr = float(np.median(feld[i_to:i_t + 1][feld[i_to:i_t + 1] >= 0.5 * front]))
        if d_ and d_["z0"] > z_to + 1.0: d_ = None
        if not d_: d_ = dict(z0=z_to, z1=z_to, w_median=w_tr, u0=g["koerper"]["u0"], u1=g["koerper"]["u1"], aus_traufband=True)
    z_dach = d_["z0"] if d_ else min(g["z1"], z_holm + 3.0)
    if d_ and d_.get("aus_traufband"): z_dach = z_tu
    oben = [i for i in range(nz) if z_holm + 0.3 < zr(i) < z_dach - 0.1]; spalten = []
    if oben:
        anteil = (feld[oben] >= 0.5 * front).mean(0); j = 0
        while j < nu:
            if anteil[j] >= 0.25:
                e = j
                while e + 1 < nu and anteil[e + 1] >= 0.25: e += 1
                spalten.append(g["u0"] + (0.5 * (j + e) + 0.5) * raster); j = e + 1
            else: j += 1
    u0, u1 = g["koerper"]["u0"], g["koerper"]["u1"]; pf = sorted(set([u0 + 0.11, u1 - 0.11] + [u for u in spalten if u0 + 0.6 < u < u1 - 0.6]))
    erg = dict(u0=u0, u1=u1, z_boden=round(z_boden, 2), z_holm=round(z_holm, 2), z_dach=round(z_dach, 2), w=round(w_wand + front, 2), w_wand=round(w_wand - 0.05, 2),
               pfosten=[round(u, 2) for u in pf], streben=0, z_fuss=None, quelle="Hoehenfeld Ebenen-Sweep (Bruestungsband, Pfostenspalten), Dach aus Gruppe 'dach'")
    if fein and fid:
        try:
            import cv2
            from scipy.signal import find_peaks
            R_ = {f["id"]: f for f in json.load(open(os.path.join(fein, "fassaden.json")))["fassaden"]}[fid]["raster"]; c = float(R_["zelle"])
            im = cv2.imread(os.path.join(fein, f"ortho_{fid}_fein.png"), 0); gr_ = cv2.imread(os.path.join(fein, f"ortho_{fid}.png"), 0)
            if gr_ is not None: im = np.where(im > 0, im, cv2.resize(gr_, (im.shape[1], im.shape[0])))
            px = lambda u: int((u - R_["u0"]) / c); py = lambda z: int((R_["z1"] - z) / c)
            B = im[py(z_boden):py(z_boden - 1.0), px(u0):px(u1)].astype(float); p = np.convolve(B.mean(0), np.ones(9) / 9, "same"); d = np.convolve(p, np.ones(81) / 81, "same") - p
            pk, pr = find_peaks(d, height=0.5 * d.max(), distance=int(0.5 / c))
            if len(pk) >= 3:
                ab = float(np.median(np.diff(pk))) * c; us = u0 + pk[0] * c; st = [us + i * ab for i in range(int((u1 - us) / ab) + 1)]
                fuss = []
                for u in st:
                    sp = im[py(z_boden):py(z_boden - 3.0), max(0, px(u) - 4):px(u) + 5].astype(float).mean(1); hell = np.median(im[py(z_boden):py(z_boden - 3.0), px(u0):px(u1)])
                    dunkel = sp < 0.75 * hell; n_ = 0
                    while n_ < len(dunkel) and dunkel[n_]: n_ += 1
                    if n_ > 10: fuss.append(z_boden - n_ * c)
                erg.update(streben=len(st), streben_u=[round(u, 2) for u in st], streben_abstand=round(ab, 2), z_fuss=round(float(np.median(fuss)), 2) if fuss else round(z_boden - 1.0, 2),
                           streben_quelle=f"feines Wandbild {fid}: {len(pk)} starke dunkle Linien unter der Bruestung, Abstand {ab:.2f} m" + ("" if fuss else "; Fussende ANNAHME 1,0 m"))
        except Exception as e_: erg["streben_fehler"] = str(e_)[:120]
    if d_:
        wt = w_wand + d_["w_median"]; z_an = round(d_["z1"] + 0.6 * d_["w_median"], 2); an_q = "ANNAHME: Oberkante Dachband + 0,6 x Ausladung (Neigung ~31 Grad)"
        if fein and fid:      # Anschluss an der Wand aus der Uneinigkeitskarte des feinen Wandbilds: die Dachflaeche vor der Wand macht die Fotos uneinig, die Wand darueber nicht
            try:
                z_m, an_m = anschluss_aus_uneinig(fein, fid, d_["z0"], g["koerper"]["u0"], g["koerper"]["u1"])
                if z_m is not None: z_an, an_q = z_m, an_m
                elif an_m: an_q += f" ({an_m})"
            except Exception as e_: an_q += f" (Karte nicht lesbar: {str(e_)[:60]})"
        erg["vordach"] = dict(z_traufe=round(d_["z0"], 2), w_traufe=round(wt, 2), z_anschluss=z_an, u0=d_["u0"], u1=d_["u1"], quelle="Traufband im Ebenen-Sweep" if d_.get("aus_traufband") else "Dachkandidat im Ebenen-Sweep",
                              annahme="Anschluss: " + an_q + "; Breite = Galerie + 0,1 m")
    return erg


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("ordner"); ap.add_argument("--aus")
    ap.add_argument("--w_min", type=float, default=0.5, help="Mindest-Ausladung eines Vorbaus (m)")
    ap.add_argument("--streuung", type=float, default=0.8, help="max. w_p90 - w_p10 einer Koerperfront (m); 21.11.: Erker 0,5-0,6 (zweiter Lauf genau 0,60 -> fiel bei 0,6 heraus), Durchblick Torbogen 1,5")
    ap.add_argument("--min_m2", type=float, default=3.0); ap.add_argument("--dach_abstand", type=float, default=6.0)
    ap.add_argument("--raster", type=float, default=0.2, help="Bauraster (m); 0,2 m = 2,3 mm in H0"); ap.add_argument("--fein", help="fassade_fein-Ordner (Streben zaehlen im 1-cm-Wandbild)")
    a = ap.parse_args()
    od = os.path.dirname(os.path.abspath(a.objekt)); aus = a.aus or os.path.join(od, "audit", "vorbauten_auto.json")
    F = json.load(open(os.path.join(a.ordner, "fassaden.json")))["fassaden"]; erg = []; bilder = []
    for i, f in enumerate(F):
        vj, nz = os.path.join(a.ordner, f"vorbauten_f{i:02d}.json"), os.path.join(a.ordner, f"tiefe_f{i:02d}.npz")
        if not (os.path.exists(vj) and os.path.exists(nz)): print(f"f{i:02d}: kein Sweep"); continue
        v = json.load(open(vj))
        if not v.get("belastbar"): print(f"f{i:02d}: Sweep nicht belastbar - kein Vorbau"); continue
        npz = np.load(nz); gr = gruppen_bilden(v["kandidaten"], a.w_min, a.streuung, a.min_m2, a.dach_abstand, w_grenze=v["w_bereich"][1] - v["wand_versatz_m"]); fg = []
        for g in gr:
            w_max = max(g["koerper"]["w_p90"], g["dach"]["w_p90"] if g["dach"] else 0.0)
            feld = hoehenfeld(npz, v["wand_versatz_m"], g, a.raster, w_max)
            if (feld > a.w_min * 0.5).mean() < 0.2: print(f"f{i:02d}: Gruppe u {g['u0']:.2f}..{g['u1']:.2f} - Hoehenfeld fast leer, verworfen"); continue
            fg.append(dict(u0=g["u0"], u1=g["u1"], z0=g["z0"], z1=g["z1"], raster=a.raster, w=np.round(feld, 2).tolist(),
                           koerper={k: g["koerper"][k] for k in ("u0", "u1", "z0", "z1", "w_median", "w_p10", "w_p90", "flaeche_m2")},
                           dach={k: g["dach"][k] for k in ("u0", "u1", "z0", "z1", "w_median", "w_p10", "w_p90", "flaeche_m2")} if g["dach"] else None))
            ga = galerie_messen(feld, g, a.raster, v["wand_versatz_m"], fein=a.fein, fid=f.get("id", f"f{i:02d}"))
            if ga: fg[-1]["galerie"] = ga; print(f"f{i:02d}: GALERIE u {ga['u0']:.2f}..{ga['u1']:.2f}, Boden {ga['z_boden']:.2f}, Holm {ga['z_holm']:.2f}, Dach {ga['z_dach']:.2f}, Ausladung {ga['w']:.2f} m, {len(ga['pfosten'])} Pfosten, {ga['streben']} Streben (Fuss {ga['z_fuss']})")
            print(f"f{i:02d}: VORBAU u {g['u0']:.2f}..{g['u1']:.2f}  z {g['z0']:.2f}..{g['z1']:.2f}  Front w {g['koerper']['w_median']:+.2f} m"
                  + (f"  Dach z {g['dach']['z0']:.2f}..{g['dach']['z1']:.2f} w {g['dach']['w_median']:+.2f}" if g["dach"] else "  (ohne Dach)")
                  + f"  max {feld.max():.2f} m")
            bilder.append((f"f{i:02d}", feld))
        if fg: erg.append(dict(id=f.get("id", f"f{i:02d}"), nr=i, o=f["o"], d=f["d"], n=f["n"], w_wand=v["wand_versatz_m"], wand_ebene=v.get("wand_ebene"), gruppen=fg))   # wand_ebene: Kamerarahmen (Kanten-Stufen), w_wand: Bau (LoD2-Wand)
    os.makedirs(os.path.dirname(aus), exist_ok=True)
    json.dump(dict(quelle="tools/vorbauten_bauplan.py aus fassade_tiefe (Ebenen-Sweep) - Hoehenfeld je Zelle", fassaden=erg), open(aus, "w"), indent=0)
    if bilder:
        import cv2
        kach = []
        for nm, fe in bilder:
            im = cv2.applyColorMap(np.clip(fe / max(fe.max(), 0.1) * 255, 0, 255).astype(np.uint8), cv2.COLORMAP_TURBO)
            im = cv2.resize(im, (im.shape[1] * 12, im.shape[0] * 12), interpolation=cv2.INTER_NEAREST); cv2.putText(im, nm, (5, 20), 0, 0.6, (255, 255, 255), 2); kach.append(im)
        hm = max(k.shape[0] for k in kach); cv2.imwrite(aus[:-5] + ".jpg", np.hstack([np.pad(k, ((0, hm - k.shape[0]), (0, 8), (0, 0))) for k in kach]))
    n = sum(len(e["gruppen"]) for e in erg); print(f"-> {aus}: {n} Vorbau-Gruppen"); return 0 if n else 3


if __name__ == "__main__": sys.exit(main())
