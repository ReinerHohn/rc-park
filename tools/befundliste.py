#!/usr/bin/env python3
"""befundliste.py <objekt.json> [--daten DIR] [--bericht B.json --ab-schritt N] [--log L --ab-zeile N] [--neben BILD ...] [--aus audit/befunde.json] [--kachel 30]
BEFUNDLISTE (22.11.2026, Agenten-Schleife automatisch, 0_DURCHBRUCH_AGENTEN_SCHLEIFE.md): maschinenlesbare Liste der SICHTBAREN Fehler nach einem Kettenlauf.

Anlass: die Fehler der Nacht 21./22.11. ("Vordach flache Platte statt geschweift", "Mauerwerk unten klumpig", "Rundbogenfenster flach", "Laterne runde Saeule")
fand nur das Auge am Nebeneinander-Bild audit/neben_*.jpg (Foto | Modell aus derselben SfM-Kamera); hand_vergleich 11/11, foto_diff und ebenen_abweichung schwiegen.
Hier wird aus VORHANDENEN Ergebnissen (kein Render, keine GPU, Sekunden) je Befund festgehalten:
  ort       Fassade (fNN + Himmelsseite), u-/z-Bereich in m (Strahl der Fotokamera K-<foto>.json gegen die Fassadenebenen aus fassade/fassaden.json), Bauteil
            (Zonen aus audit/*_auto.json, vordach_profil.json), Bildausschnitt in Pixeln
  art       fehlt/zu flach | zu grob/verrauscht | Form falsch | Lage/Mass | Umriss | Codefehler | Stufe rot | Beleg ungueltig | keine Fotos
  beleg     Quelle (Tor-JSON, Bild, Log) + Zahl; staerke 0..1; stufe FEHLER/HINWEIS/KEINE FOTOS
  vorschlag zustaendiges Werkzeug (tools/...) + warum; ausschnitt audit/befunde/<id>.jpg (Foto | Modell, Rahmen um den Befund)

Bausteine (Wiederverwendung statt Neubau): die Tore selbst liefern ihre Urteile (hand_vergleich.json, fenster_form_tor.json, umriss_tor.json,
ebenen_abweichung.json, seiten_luecken.json, fototor_vergleich.json), Logwarnungen ueber tools/log_warnungen.sammeln, Stufen aus gesamtkette_bericht.json.
NEU ist nur der Bildvergleich je Kachel (30 px) der Nebeneinander-Bilder (beide Haelften aus derselben Kamera, ohne Neurendern), Zone = 3x3 Kacheln:
  KANTEN     lange Fotokanten (Canny, Zuege >= 25 px) gegen lange Modell-Renderkanten: Anzahl, Recall, Praezision (6 px Toleranz) je Zone
  FEHLT      Foto strukturiert (Energie bei 3 px Glaettung > 1,15 x Median der Modellflaeche) und Modell glatt (Render rauschfrei), ODER Fotokanten
             ohne Modellkanten (Modell < 0,3 x, Recall < 0,3) -> fehlt/zu flach (Rundbogenfenster, Gesims, Eckquader)
  KLUMPEN    Modell hat > 1,6 x so viele lange Kanten wie das Foto, meist ohne Fotokante (Praezision < 0,5) oder richtungslos (Anteil in den zwei
             Hauptrichtungen des FOTOS klein) -> zu grob/verrauscht (Beulen statt Quader)
  FORM       beide haben Kanten in aehnlicher Menge, aber an anderer Stelle (Kanten-F1 < 0,45) -> Form falsch (Kastenvordach gegen geschweifte Traufe)
  BELEG      Modellumriss gegen Fotokanten: Abstand an der Stelle / Median desselben Umrisses verschoben; ~1 = Foto zeigt das Objekt dort nicht
             (Kamera falsch / falsches Bild) -> Beleg ungueltig, keine Flaechenbefunde aus diesem Bild.
  FREMDES    Fotokantenzuege, die zu > 30 % ausserhalb der Modellflaeche laufen (Oberleitungen), zaehlen nicht; Kacheln hinter LoD2-Nachbarn
             (fassade_ortho.nachbarn_netz, Strahl der Fotokamera) zaehlen nicht.
Kacheln verbinden sich nur innerhalb derselben Fassade + Bauteilzone (bzw. 6-m-Hoehenband), damit Vordach, Erker und Mauerwerk getrennte Befunde werden.
ANNAHME: Fotostruktur = Geometrie. Wandmalerei (Schwabentor-Erker), Vordergrund ohne LoD2 (Tram, Schilder) machen Fehlalarme - deshalb
Staerke aus Flaeche x Abstand zur Schwelle, und Befunde auf Fassaden ohne Fotos (seiten_luecken 'ungesehen') werden zu "keine Fotos" herabgestuft.
Abgefangene Codefehler im zustaendigen Werkzeug werden als 'moegliche_ursache' an den Sichtbefund gehaengt.
Kein Tor: rc 0 immer (rc 3 = gar nichts zu pruefen). Test: tools/test_befundliste.py. Kettenstufe 'befundliste' am Ende von tools/gesamtkette.py.
"""
import sys, os, re, json, glob, math, time, argparse
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

# ---------------------------------------------------------------- Schwellen (an Schwabentor 1121m/1122a kalibriert, siehe Test)
GLATT_EM = 4.0          # Modell-Kachel glatt: mittlere Gradientenenergie des Renders (Sobel, 1 px Glaettung) darunter
STRUKTUR_SF = 1.15      # Foto-Kachel strukturiert: Energie (3 px Glaettung) / Median der Modellflaeche darueber
KLUMPEN_EM = 14.0       # Modell-Kachel stark strukturiert (1 px)
KLUMPEN_ACHSE = 0.12    # Fotoanteil in den Fotohauptrichtungen minus Modellanteil darin (richtungslose Beulen) - verstaerkt Klumpen
UEBERSCHUSS = 1.6       # Klumpen: lange Modellkanten > 1,6 x lange Fotokanten in der Zone (Schwabentor unten 3,3x, Vordach-Kasten 1,5x, Uhr 0,6-1,1x)
KANTEN_MIN = 60         # Kantenpixel (Zone 3x3 Kacheln) fuer Kantenurteile
FORM_F1 = 0.45          # Kanten-F1 Foto/Modell in der Zone darunter -> Form falsch (Vordach-Kasten 0,41 / 0,28; Uhr 0,78 / 0,95; Mauer unten 0,5)
BELEG_QUOTE = 0.9       # Umrissabstand an der Stelle / Median verschoben darueber -> Foto zeigt das Modell nicht
MIN_KACHELN = 3         # zusammenhaengende Kacheln je Bildbefund
ARTEN = {"fehlt": "fehlt/zu flach", "klumpen": "zu grob/verrauscht", "form": "Form falsch"}


def _cv():
    import cv2
    return cv2


# ---------------------------------------------------------------- Bild
def haelften(pfad_oder_bild):
    """neben_*.jpg -> (Foto, Modell) als BGR; beide Haelften gleich gross (modell_neben_foto.py: hstack, gemeinsam skaliert)."""
    cv2 = _cv(); im = cv2.imread(pfad_oder_bild) if isinstance(pfad_oder_bild, str) else pfad_oder_bild
    if im is None: raise FileNotFoundError(pfad_oder_bild)
    w = im.shape[1] // 2
    return im[:, :w], im[:, w:2 * w]


def modellmaske(modell, hinter=235, tol=4):
    """Modellpixel = alles, was nicht zum randverbundenen Hintergrund (Grau 235 aus modell_neben_foto) gehoert."""
    from scipy import ndimage as ndi
    cv2 = _cv(); g = cv2.cvtColor(modell, cv2.COLOR_BGR2GRAY).astype(int)
    lab, _ = ndi.label(np.abs(g - hinter) <= tol)
    rand = set(np.unique(np.r_[lab[0], lab[-1], lab[:, 0], lab[:, -1]]).tolist()) - {0}
    m = ~np.isin(lab, list(rand))
    return ndi.binary_opening(m, iterations=2)


def _grad(g, s):
    cv2 = _cv(); g = cv2.GaussianBlur(g.astype(np.float32), (0, 0), s)
    return cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1)


def beleg_quote(foto, maske):
    """Mittlerer Abstand (px, gekappt 10) des Modellumrisses zur naechsten starken Fotokante, geteilt durch den Median desselben Abstands fuer den
    VERSCHOBENEN Umriss (48 Verschiebungen bis +-12 % der Bildbreite = Nullverteilung). Passt die Kamera, liegt der Umriss an seiner Stelle besser
    auf Fotokanten als verschoben (Schwabentor 113231: 0,65 / 0,78); zeigt das Foto dort etwas anderes, ist er nicht besser als Zufall (vf_023_3: 1,01).
    (Erster Ansatz 'Abstand am Umriss / Abstand in der Flaeche' trennte nur 0,90 gegen 1,08 - ein Fachwerk-Verdecker am Umriss reichte fuer Fehlalarm.)"""
    from scipy import ndimage as ndi
    cv2 = _cv(); gx, gy = _grad(cv2.cvtColor(foto, cv2.COLOR_BGR2GRAY), 1.5); e = np.hypot(gx, gy)
    if maske.sum() < 500: return None
    k = e > np.percentile(e, 85); dt = np.minimum(ndi.distance_transform_edt(~k), 10.0)
    rand = maske ^ ndi.binary_erosion(maske, iterations=1)
    rand[[0, -1], :] = False; rand[:, [0, -1]] = False                    # Bildrand ist kein Umriss
    if rand.sum() < 50: return None
    ys, xs = np.nonzero(rand); H, W = maske.shape

    def d(dx, dy):
        y2, x2 = ys + dy, xs + dx; ok = (y2 >= 0) & (y2 < H) & (x2 >= 0) & (x2 < W)
        return float(dt[y2[ok], x2[ok]].mean()) if ok.mean() > 0.6 else np.nan
    s = max(2, int(0.04 * W)); v = np.array([d(dx, dy) for dx in range(-3 * s, 3 * s + 1, s) for dy in range(-3 * s, 3 * s + 1, s) if (dx, dy) != (0, 0)])
    v = v[np.isfinite(v)]
    if len(v) < 8: return None
    return float(d(0, 0) / max(np.median(v), 1e-6))


def _ohist(gx, gy, sel, nb=18):
    a = np.arctan2(gy, gx)[sel] % np.pi; w = np.hypot(gx, gy)[sel]
    h = np.bincount(np.minimum((a / np.pi * nb).astype(int), nb - 1), weights=w, minlength=nb)
    return h / (h.sum() + 1e-9)


def _achsanteil(hf, hm):
    """Anteil von Foto und Modell in den zwei Hauptrichtungen des Fotos (je +-1 Bin, kreisfoermig)."""
    nb = len(hf); hs = hf + np.roll(hf, 1) + np.roll(hf, -1); i1 = int(np.argmax(hs))
    hs2 = hs.copy(); hs2[[(i1 + d) % nb for d in range(-2, 3)]] = -1; i2 = int(np.argmax(hs2))
    sel = np.zeros(nb, bool)
    for i in (i1, i2):
        for d in (-1, 0, 1): sel[(i + d) % nb] = True
    return float(hf[sel].sum()), float(hm[sel].sum())


def lange_kanten(g, s, lo, hi, min_px=25):
    """Canny nach Glaettung s, nur zusammenhaengende Kantenzuege >= min_px (kurze Textur-/Rauschkanten weg)."""
    from scipy import ndimage as ndi
    cv2 = _cv(); k = cv2.Canny(cv2.GaussianBlur(g, (0, 0), s), lo, hi) > 0
    lab, _ = ndi.label(k, structure=np.ones((3, 3))); sz = np.bincount(lab.ravel()); keep = sz >= min_px; keep[0] = False
    return keep[lab]


def kacheln(foto, modell, maske, T=30, min_anteil=0.7, tol_px=6):
    """Kennzahlen je Kachel TxT (nur Kacheln mit >= min_anteil Modellflaeche). Rueckgabe dict von Arrays (ny, nx), NaN = nicht bewertet.
    Struktur: ef3 (Foto, 3 px Glaettung), em1 (Modell, 1 px), Richtungen (achse_f/achse_m, schnitt);
    KANTENABGLEICH je Zone (3x3 Kacheln): lange Fotokanten (Canny nach 2 px Glaettung) gegen lange Modell-Renderkanten derselben Kamera,
    nf/nm Anzahl, recall = Anteil Fotokanten mit Modellkante in tol_px, praez = Anteil Modellkanten mit Fotokante in tol_px."""
    from scipy import ndimage as ndi
    cv2 = _cv(); fg = cv2.cvtColor(foto, cv2.COLOR_BGR2GRAY); rg = cv2.cvtColor(modell, cv2.COLOR_BGR2GRAY)
    f3x, f3y = _grad(fg, 3.0); m1x, m1y = _grad(rg, 1.0); f1x, f1y = _grad(fg, 1.5); ef3 = np.hypot(f3x, f3y); em1 = np.hypot(m1x, m1y)
    innen = ndi.binary_erosion(maske, iterations=3)                         # Modellumriss selbst ist Sache des Umriss-Tors
    kf_alle = lange_kanten(fg, 2.0, 40, 100); km = lange_kanten(rg, 1.5, 20, 50) & innen
    # LEITUNGEN/FREMDES: Fotokantenzuege, die zu > 30 % ausserhalb der Modellflaeche laufen (Oberleitung, Nachbarhaus-Kante), zaehlen nicht -
    # weder als Kante noch als Struktur (Schwabentor 113231: zwei Leitungen ueber dem Putz machten 'fehlt' zwischen den Rundbogenfenstern)
    lab, n = ndi.label(kf_alle, structure=np.ones((3, 3))); fremd = np.zeros(maske.shape, bool)
    if n:
        ges = np.bincount(lab.ravel(), minlength=n + 1); drin = np.bincount(lab.ravel(), weights=maske.ravel().astype(float), minlength=n + 1)
        aus = (ges - drin) > 0.3 * ges; aus[0] = False; fremd = ndi.binary_dilation(aus[lab], iterations=7)
    kf = kf_alle & innen & ~fremd; gueltig = maske & ~fremd
    mf = kf & (ndi.distance_transform_edt(~km) <= tol_px); mm_ = km & (ndi.distance_transform_edt(~kf) <= tol_px)
    ny, nx = maske.shape[0] // T, maske.shape[1] // T
    K = {k: np.full((ny, nx), np.nan) for k in ("anteil", "ef3", "em1", "achse_f", "achse_m", "schnitt")}
    C = {k: np.zeros((ny, nx)) for k in ("nf", "nm", "mf", "mm")}
    for i in range(ny):
        for j in range(nx):
            s = (slice(i * T, (i + 1) * T), slice(j * T, (j + 1) * T)); mm = maske[s]; K["anteil"][i, j] = mm.mean()
            C["nf"][i, j] = kf[s].sum(); C["nm"][i, j] = km[s].sum(); C["mf"][i, j] = mf[s].sum(); C["mm"][i, j] = mm_[s].sum()
            if mm.mean() < min_anteil: continue
            gg = gueltig[s]
            K["ef3"][i, j] = ef3[s][gg].mean() if gg.mean() > 0.3 else np.nan; K["em1"][i, j] = em1[s][mm].mean()
            hf = _ohist(f1x[s], f1y[s], mm); hm = _ohist(m1x[s], m1y[s], mm)
            K["achse_f"][i, j], K["achse_m"][i, j] = _achsanteil(hf, hm); K["schnitt"][i, j] = float(np.minimum(hf, hm).sum())
    for k in C: C[k] = ndi.uniform_filter(C[k], size=3, mode="constant") * 9     # Zone = 3x3 Kacheln
    with np.errstate(invalid="ignore", divide="ignore"):
        K["nf"], K["nm"] = C["nf"], C["nm"]; K["recall"] = np.where(C["nf"] > 0, C["mf"] / C["nf"], np.nan); K["praez"] = np.where(C["nm"] > 0, C["mm"] / C["nm"], np.nan)
        K["kanten_f1"] = np.where((K["recall"] + K["praez"]) > 0, 2 * K["recall"] * K["praez"] / (K["recall"] + K["praez"]), 0.0)
    med = np.nanmedian(K["ef3"]) if np.isfinite(K["ef3"]).any() else 1.0
    K["sf"] = K["ef3"] / max(med, 1e-6)
    return K


def klassen(K):
    """Je Kachel: 'fehlt' | 'klumpen' | 'form' | '' mit Staerke 0..1 (Abstand zur Schwelle)."""
    ny, nx = K["anteil"].shape; L = np.full((ny, nx), "", dtype=object); S = np.zeros((ny, nx))
    nf, nm = K.get("nf", np.zeros((ny, nx))), K.get("nm", np.zeros((ny, nx))); rec = K.get("recall", np.full((ny, nx), np.nan)); pre = K.get("praez", np.full((ny, nx), np.nan))
    f1 = K.get("kanten_f1", np.full((ny, nx), np.nan)); nfx = np.maximum(nf, KANTEN_MIN / 2)
    with np.errstate(invalid="ignore", divide="ignore"):
        ok = np.isfinite(K["em1"])
        fehlt_s = ok & (K["em1"] < GLATT_EM) & (K["sf"] > STRUKTUR_SF)                                   # Foto strukturiert, Modell glatt
        fehlt_k = ok & (nf >= KANTEN_MIN) & (nm < 0.3 * nf) & (np.nan_to_num(rec) < 0.3)                  # Fotokanten ohne Modellkanten
        fehlt = fehlt_s | fehlt_k
        dach = K["achse_f"] - K["achse_m"]
        klumpen = ok & ~fehlt & (K["em1"] > KLUMPEN_EM) & (nm > UEBERSCHUSS * nfx) & ((np.nan_to_num(pre) < 0.5) | (dach > KLUMPEN_ACHSE))
        form = ok & ~fehlt & ~klumpen & (nf >= KANTEN_MIN) & (nm >= 0.4 * nf) & (np.nan_to_num(f1) < FORM_F1)
    L[fehlt] = "fehlt"
    S[fehlt] = np.maximum(np.where(fehlt_s, np.clip((K["sf"] - STRUKTUR_SF) / 1.5, 0.05, 1) * np.clip(1 - K["em1"] / GLATT_EM, 0.2, 1), 0),
                          np.where(fehlt_k, (1 - np.nan_to_num(rec)) * np.clip(nf / (3 * KANTEN_MIN), 0.2, 1), 0))[fehlt]
    L[klumpen] = "klumpen"; S[klumpen] = (np.clip((nm / nfx - UEBERSCHUSS) / 2.0 + 0.2, 0.05, 1) * np.clip(1 - np.nan_to_num(pre) + np.clip(dach, 0, 0.5), 0.1, 1))[klumpen]
    L[form] = "form"; S[form] = np.clip((FORM_F1 - np.nan_to_num(f1)) / FORM_F1 + 0.1, 0.05, 1)[form]
    return L, S


def regionen(L, S, T, min_k=MIN_KACHELN, schluessel=None):
    """Zusammenhaengende Kacheln gleicher Klasse (8er-Nachbarschaft) -> Bildbefunde (Pixelrahmen x0 y0 x1 y1, Kachelzahl, Staerke).
    schluessel (ny, nx, Objekt-Array, optional): Kacheln nur innerhalb desselben Schluessels verbinden (Fassade + Bauteil bzw. 6-m-Hoehenband) -
    sonst wird aus Vordach, Erker und Mauerwerk EIN Riesenbefund."""
    from scipy import ndimage as ndi
    out = []
    keys = [None] if schluessel is None else sorted(set(schluessel[L != ""].tolist()), key=str)
    for art in ARTEN:
        for key in keys:
            sel = (L == art) if key is None else (L == art) & (schluessel == key)
            lab, n = ndi.label(sel, structure=np.ones((3, 3)))
            out += _regionen_aus(lab, n, art, S, T, min_k)
    return sorted(out, key=lambda b: -b["staerke"] * b["kacheln"])


def _regionen_aus(lab, n, art, S, T, min_k):
    out = []
    for r in range(1, n + 1):
        ii, jj = np.nonzero(lab == r)
        if len(ii) < min_k: continue
        st = float(np.clip(S[ii, jj].mean() * min(1.0, len(ii) / 12.0) ** 0.5, 0, 1))
        out.append(dict(art=art, kacheln=int(len(ii)), staerke=round(st, 2), px=[int(jj.min() * T), int(ii.min() * T), int((jj.max() + 1) * T), int((ii.max() + 1) * T)]))
    return out


# ---------------------------------------------------------------- Ort (Strahl der Fotokamera gegen die Fassadenebenen)
def kamera_laden(od, foto):
    p = os.path.join(od, "messprotokoll", "K-" + foto + ".json")
    if not os.path.exists(p): return None
    try: return json.load(open(p))["kamera"]
    except Exception: return None


def _rot(rvec):
    r = np.asarray(rvec, float); th = np.linalg.norm(r)
    if th < 1e-12: return np.eye(3)
    k = r / th; Kx = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + math.sin(th) * Kx + (1 - math.cos(th)) * Kx @ Kx


def strahl_treffer(K, px, py, skala, fassaden):
    """Bildpunkt (Nebeneinander-Pixel; Original = px*skala, Foto schon entzerrt) -> naechste Fassade (id, u, z, Abstand) oder None."""
    R = _rot(K["rvec"]); t = np.asarray(K["t"], float); C = -R.T @ t
    d = R.T @ np.array([(px * skala - K["cx"]) / K["f_px"], (py * skala - K["cy"]) / K["f_px"], 1.0]); best = None
    for fa in fassaden:
        n = np.asarray(fa["n"], float); o = np.asarray(fa["o"], float); dn = float(n @ d[:2])
        if abs(dn) < 1e-9: continue
        lam = float(n @ (o - C[:2])) / dn
        if lam <= 0: continue
        P = C + lam * d; u = float(np.asarray(fa["d"], float) @ (P[:2] - o)); z = float(P[2])
        if fa["u"][0] - 0.3 <= u <= fa["u"][1] + 0.3 and fa["z"][0] - 0.5 <= z <= fa["z"][1] + 0.5 and (best is None or lam < best[3]):
            best = (fa["id"], u, z, lam)
    return best


def projizieren(K, xyz, skala):
    R = _rot(K["rvec"]); p = R @ np.asarray(xyz, float) + np.asarray(K["t"], float)
    if p[2] <= 0.1: return None
    return ((K["f_px"] * p[0] / p[2] + K["cx"]) / skala, (K["f_px"] * p[1] / p[2] + K["cy"]) / skala)


def fassaden_punkt(fa, u, z):
    o = np.asarray(fa["o"], float); dd = np.asarray(fa["d"], float); q = o + u * dd
    return [float(q[0]), float(q[1]), float(z)]


def seite_name(fa, konv):
    if not konv or "n" not in fa: return ""
    n = fa["n"]; ach = {"+x": (1, 0), "-x": (-1, 0), "+y": (0, 1), "-y": (0, -1)}
    k = max(ach, key=lambda a: ach[a][0] * n[0] + ach[a][1] * n[1])
    return konv.get(k, "")


def ort_aus_rahmen(K, px_rahmen, skala, fassaden, raster=5):
    """Ort eines Bildbefunds: Strahlen auf einem raster x raster-Gitter im Rahmen -> Mehrheitsfassade, u-/z-Spanne."""
    if not K or not fassaden: return {}
    x0, y0, x1, y1 = px_rahmen; tr = []
    for x in np.linspace(x0 + 2, x1 - 2, raster):
        for y in np.linspace(y0 + 2, y1 - 2, raster):
            h = strahl_treffer(K, x, y, skala, fassaden)
            if h: tr.append(h)
    if not tr: return dict(fassade=None, hinweis="kein Fassadentreffer (Dach, Aufsatz oder Anbau)")
    ids = [h[0] for h in tr]; fid = max(set(ids), key=ids.count); hs = [h for h in tr if h[0] == fid]
    u = [h[1] for h in hs]; z = [h[2] for h in hs]
    return dict(fassade=fid, u=[round(min(u), 2), round(max(u), 2)], z=[round(min(z), 2), round(max(z), 2)], treffer=len(hs), von=len(tr))


# ---------------------------------------------------------------- Bauteil-Zonen aus den Kettenergebnissen
VERWERF_SCHLUESSEL = ("verworfen", "abgelehnt", "ausreisser")


def verworfen_eintrag(x):
    """True, wenn ein Erkennungseintrag (dict) als verworfen markiert ist: 'verworfen' = Grund-Text/True, oder status/urteil == 'verworfen'/'abgelehnt'.
    Eine LISTE unter 'verworfen' (z. B. verworfene Fotos eines gebauten Teils) markiert den Eintrag selbst nicht."""
    v = x.get("verworfen")
    if v is True or (isinstance(v, str) and v.strip()): return True
    return any(str(x.get(k, "")).lower() in ("verworfen", "abgelehnt") for k in ("status", "urteil"))


def bauteil_zonen(audit):
    """Alle Zonen (fassade, u0, u1, z0, z1, name) aus audit/*_auto.json und vordach_profil.json - generisch: jedes Objekt mit u0/u1/z0/z1, 'kasten' [u0,u1,z0,z1]
    oder Vordach (u0/u1 + z_t/z_a); Fassade = naechster Schluessel/Eintrag 'fNN'."""
    Z = []

    def geh(x, fid, name, tiefe=0):
        if tiefe > 6: return
        if isinstance(x, dict):
            f2 = x.get("id") if isinstance(x.get("id"), str) and re.fullmatch(r"f\d\d", x.get("id", "")) else fid
            # 23.11.2026 (1122o: neben_details zeigte den Treppenturm als 'oeffnung_bogen_f03' und das Turmstueck vor der Tuer als 'oeffnung_bogen_f04' - beide
            # Eintraege hatten gebaut=false): verworfene/nicht gebaute Erkennungen und Koerper vor der Wand sind KEIN Bauteil des Modells
            if x.get("gebaut") is False or x.get("koerper_vor_wand"): return
            # 24.11.2026 (1122zb, neben_detail uhr_f01_2/_3): Erkennungen, die die messende Stufe VERWORFEN hat, sind kein Bauteil - weder als Eintrag mit
            # 'verworfen': "<Grund>"/True bzw. status/urteil 'verworfen' (vorbau_fototor) noch als Liste unter einem Verwerf-Schluessel (uhren_wandbild:
            # 'verworfen': [{kasten, grund}]). Vorher wurden die zwei verworfenen Uhr-Kandidaten auf f01 (Goldnimbus im Wandgemaelde, Innenkreis der echten Uhr)
            # als 'uhr_f01_2'/'uhr_f01_3' mit Rechteck-Kasten ausgeschnitten -> Wandstueck bzw. Zackenrechteck als "Uhr" im Detailbild.
            if verworfen_eintrag(x): return
            k = None
            if all(isinstance(x.get(a), (int, float)) for a in ("u0", "u1", "z0", "z1")): k = (x["u0"], x["u1"], x["z0"], x["z1"])
            elif isinstance(x.get("kasten"), list) and len(x["kasten"]) == 4: k = tuple(x["kasten"])
            elif all(isinstance(x.get(a), (int, float)) for a in ("u0", "u1", "z_t", "z_a")): k = (x["u0"], x["u1"], x["z_t"] - 0.5, x["z_a"])
            if k and f2 and k[1] - k[0] < 30 and k[3] - k[2] < 40:
                Z.append(dict(fassade=f2, u0=float(k[0]), u1=float(k[1]), z0=float(k[2]), z1=float(k[3]), name=name + (("/" + x["art"]) if isinstance(x.get("art"), str) else "")))
                # 23.11.2026 (Uhr f00, 1122q): runde Bauteile (Mitte u/z + gemessener d_aussen, z. B. uhren_auto.json) tragen ihre BELEGTE Kontur mit - der Kasten
                # ist der Erkennerkasten (OWLv2), die Ecken ausserhalb des Kreises sind Wand
                if all(isinstance(x.get(a), (int, float)) for a in ("u", "z", "d_aussen")) and x["d_aussen"] > 0:
                    Z[-1]["kreis"] = [float(x["u"]), float(x["z"]), 0.5 * float(x["d_aussen"])]
                return
            for a, v in x.items():
                if str(a) in VERWERF_SCHLUESSEL and isinstance(v, list): continue      # Liste verworfener Kandidaten (nicht: Fotonamen eines gebauten Teils, die haben keinen Kasten)
                geh(v, a if re.fullmatch(r"f\d\d", str(a)) else f2, name, tiefe + 1)
        elif isinstance(x, list):
            for v in x: geh(v, fid, name, tiefe + 1)
    for p in sorted(glob.glob(os.path.join(audit, "*_auto.json"))) + [os.path.join(audit, "vordach_profil.json")]:
        if not os.path.exists(p): continue
        try: j = json.load(open(p))
        except Exception: continue
        nm = os.path.basename(p).replace("_auto.json", "").replace(".json", "")
        if nm in ("vorbauten",): nm = "vorbau"
        geh(j, None, nm)
    return Z


def bauteil_von(ort, zonen):
    if not ort or not ort.get("fassade") or "u" not in ort: return ""
    u0, u1 = ort["u"]; z0, z1 = ort["z"]; kand = []
    if u1 - u0 < 0.05: u0, u1 = u0 - 0.1, u1 + 0.1
    if z1 - z0 < 0.05: z0, z1 = z0 - 0.1, z1 + 0.1
    for zz in zonen:
        if zz["fassade"] != ort["fassade"]: continue
        du = min(u1, zz["u1"]) - max(u0, zz["u0"]); dz = min(z1, zz["z1"]) - max(z0, zz["z0"])
        if du <= 0 or dz <= 0: continue
        a = du * dz / max((u1 - u0) * (z1 - z0), 1e-6)            # Anteil des Befunds in der Zone
        if a >= 0.4: kand.append(((zz["u1"] - zz["u0"]) * (zz["z1"] - zz["z0"]), zz["name"]))
    return min(kand)[1] if kand else ""                             # kleinste passende Zone (Fenster vor Vorbau vor Wand)


# ---------------------------------------------------------------- zustaendiges Werkzeug
def vorschlag(art, bauteil="", z=None, hoch=None):
    b = (bauteil or "").lower(); oben = z is not None and hoch is not None and z > 0.9 * hoch
    if art == "Beleg ungueltig": return dict(werkzeug="tools/kameras_aus_buendel.py, tools/neben_fotos_waehlen.py", warum="Foto zeigt das Modell an der Kamerastelle nicht - Kamera/Bildwahl pruefen, erst dann Flaechenbefunde")
    if art == "keine Fotos": return dict(werkzeug="tools/seiten_luecken.py, tools/foto_auftrag.py", warum="Wand ohne Fotobeleg - Fotos suchen/holen, nicht spiegeln oder erfinden")
    if art == "Codefehler": return dict(werkzeug="(Werkzeug aus der Logzeile)", warum="abgefangener Programmfehler - Teilschritt lief nicht, Ergebnis unveraendert")
    if "fenster" in b or "nische" in b:
        return dict(werkzeug="tools/nischen_fenster.py, tools/laibung_aus_fotos.py, tools/fenster_form_tor.py", warum="Fensterform/-tiefe aus Fotokanten (Laibung, Nische, Formfamilie >= 3 Fotos)")
    if "vordach" in b or "vorbau" in b:
        return dict(werkzeug="tools/vordach_profil.py, tools/vorbauten_bauplan.py", warum="Vorbau/Vordach: Profil und Ausladung aus Foto-Silhouetten")
    if "uhr" in b: return dict(werkzeug="tools/uhren_wandbild.py", warum="Uhr/Zifferblatt aus dem Wandbild")
    if "oeffnung" in b or "tor" in b: return dict(werkzeug="tools/oeffnungen_aus_kanten.py", warum="Bogen/Durchfahrt aus Fotokanten")
    if "umgang" in b: return dict(werkzeug="tools/umgang_aus_fotos.py", warum="Umgang unter der Traufe")
    if oben or b in ("dach", "laterne", "spitze"):
        return dict(werkzeug="tools/dachflaeche_aus_umriss.py, tools/spitze_aus_umriss.py, tools/laterne_aus_fotos.py, tools/traufe_aus_fotos.py", warum="Dach/Aufsatz aus der Himmelskante (Umriss) der Fotos")
    if art == ARTEN["klumpen"]:
        return dict(werkzeug="tools/quader_raster.py, tools/putz_wandbild.py (tiefe_belegt), tools/relief_einsatz.py", warum="Relief baut Beulen statt Fugen/Quader - Raster aus dem Wandbild, Tiefe nur mit Beleg")
    if art == ARTEN["fehlt"]:
        return dict(werkzeug="tools/fassaden_kette.py (fassade_fein, relief), tools/ebenen_bauplan.py", warum="Fotostruktur ohne Modellgeometrie - Wandbild/Ebene fehlt dort (ANNAHME: keine Wandmalerei)")
    if art == ARTEN["form"]:
        return dict(werkzeug="tools/ebenen_bauplan.py, tools/bauteile.py (generisches Bauteil)", warum="Modellkanten in anderer Richtung als die Fotokanten - Form aus Fotokanten neu")
    if art.startswith("Umriss"):
        return dict(werkzeug="tools/rund_aus_umriss.py, tools/vorbauten_bauplan.py, tools/umriss_tor.py", warum="Silhouette weicht von der Himmelskante ab - Koerper/Vorbau an dieser Stelle aus Foto-Umrissen")
    if art == "Lage/Mass":
        return dict(werkzeug="tools/ebenen_masse.py, tools/hand_vergleich.py (Soll)", warum="Mass/Lage aus Kanten je Ebene neu messen (nie Handstand-Werte einsetzen)")
    if art == "Stufe rot": return dict(werkzeug="(Stufe im Bericht)", warum="Kettenstufe fehlgeschlagen - Log der Stufe lesen")
    return dict(werkzeug="", warum="")


# ---------------------------------------------------------------- Ausschnitt
def ausschnitt(foto, modell, px, aus, rand=40, farbe=(0, 0, 255)):
    cv2 = _cv(); H, W = foto.shape[:2]; x0, y0, x1, y1 = px
    a0, b0, a1, b1 = max(0, x0 - rand), max(0, y0 - rand), min(W, x1 + rand), min(H, y1 + rand)
    if a1 - a0 < 8 or b1 - b0 < 8: return None
    t = []
    for im in (foto, modell):
        c = im[b0:b1, a0:a1].copy(); cv2.rectangle(c, (x0 - a0, y0 - b0), (x1 - a0 - 1, y1 - b0 - 1), farbe, 2); t.append(c)
    sp = np.full((t[0].shape[0], 6, 3), 255, np.uint8); o = np.hstack([t[0], sp, t[1]])
    s = min(1.0, 900.0 / o.shape[1]) if o.shape[1] > 900 else max(1.0, min(3.0, 400.0 / o.shape[1]))
    if s != 1.0: o = cv2.resize(o, None, fx=s, fy=s, interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_NEAREST)
    os.makedirs(os.path.dirname(aus), exist_ok=True); cv2.imwrite(aus, o, [cv2.IMWRITE_JPEG_QUALITY, 85]); return aus


# ---------------------------------------------------------------- Bildbefunde je Nebeneinander-Bild
def kachel_orte(K, skala, fassaden, shape, T, zonen=None, verdecker=None):
    """Je Kachelmitte: Schluessel 'fNN|bauteil' bzw. 'fNN|zB' (6-m-Band) und Verdeckt-Flag (Nachbarnetz VOR der Fassade, Strahl der Fotokamera)."""
    ny, nx = shape[0] // T, shape[1] // T; key = np.full((ny, nx), "ohne", dtype=object); verd = np.zeros((ny, nx), bool)
    if not K or not fassaden: return key, verd
    R = _rot(K["rvec"]); C = -R.T @ np.asarray(K["t"], float); orte = {}
    for i in range(ny):
        for j in range(nx):
            h = strahl_treffer(K, (j + 0.5) * T, (i + 0.5) * T, skala, fassaden)
            if not h: continue
            orte[(i, j)] = h; bt = ""
            for zz in sorted(zonen or [], key=lambda z_: (z_["u1"] - z_["u0"]) * (z_["z1"] - z_["z0"])):
                if zz["fassade"] == h[0] and zz["u0"] <= h[1] <= zz["u1"] and zz["z0"] <= h[2] <= zz["z1"]: bt = zz["name"]; break
            key[i, j] = f"{h[0]}|{bt}" if bt else f"{h[0]}|z{int(h[2] // 6)}"
    if verdecker is not None and orte:
        try:
            ij = list(orte); D = np.array([R.T @ np.array([((j + 0.5) * T * skala - K["cx"]) / K["f_px"], ((i + 0.5) * T * skala - K["cy"]) / K["f_px"], 1.0]) for i, j in ij])
            nd = np.linalg.norm(D, axis=1); lam = np.array([orte[k][3] for k in ij]) * nd; D /= nd[:, None]      # Abstand Kamera -> Fassade in m
            loc, ri, _ = verdecker.ray.intersects_location(np.repeat(C[None], len(ij), 0), D, multiple_hits=True)
            if len(ri):
                dist = np.linalg.norm(loc - C, axis=1); best = np.full(len(ij), np.inf); np.minimum.at(best, ri, dist)
                for n_, (i, j) in enumerate(ij):
                    if best[n_] < lam[n_] - 0.5: verd[i, j] = True
        except Exception as e: print("Verdecker nicht geprueft:", type(e).__name__, str(e)[:120])
    return key, verd


_VERDECKER = {}


def verdecker_netz(obj):
    """LoD2-Nachbarn als Dreiecksnetz im Modellrahmen (fassade_ortho.nachbarn_netz, wiederverwendet); None, wenn nicht ladbar."""
    k = json.dumps(obj.get("lod2", {}).get("gml", "")) + json.dumps(obj.get("rahmen", {}))
    if k not in _VERDECKER:
        try:
            import fassade_ortho as FO
            _VERDECKER[k] = FO.nachbarn_netz(obj)[0]
        except Exception as e:
            print("Nachbarnetz nicht geladen (Verdecker ungeprueft):", type(e).__name__, str(e)[:160]); _VERDECKER[k] = None
    return _VERDECKER[k]


def bild_befunde(pfad, K=None, fassaden=None, T=30, debug=None, zonen=None, verdecker=None):
    """Ein neben_*.jpg -> (Befundliste, Info). K: Kamera (dict aus K-<foto>.json) fuer den Ort, fassaden: Liste aus fassaden.json,
    zonen: bauteil_zonen(), verdecker: Nachbarnetz (trimesh) - verdeckte Kacheln zaehlen nicht."""
    foto, modell = haelften(pfad); m = modellmaske(modell); info = dict(bild=pfad, modellflaeche=round(float(m.mean()), 3))
    if m.mean() < 0.01: return [dict(art="Beleg ungueltig", px=[0, 0, foto.shape[1], foto.shape[0]], staerke=0.5, beleg=dict(zahl="Modell im Bild nicht sichtbar (Flaeche < 1 %)"))], info
    q = beleg_quote(foto, m); info["umriss_quote"] = None if q is None else round(q, 3)
    if q is not None and q > BELEG_QUOTE:
        ys, xs = np.nonzero(m)
        return [dict(art="Beleg ungueltig", px=[int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1], staerke=round(float(np.clip((q - BELEG_QUOTE) / 0.2 + 0.3, 0, 1)), 2),
                     beleg=dict(zahl=f"Umrissabstand / Erwartung {q:.2f} (> {BELEG_QUOTE}: Modellumriss liegt nicht auf Fotokanten)"))], info
    Kz = kacheln(foto, modell, m, T); skala = (K["bild"][0] / foto.shape[1]) if K and K.get("bild") else None
    key, verd = kachel_orte(K, skala, fassaden, m.shape, T, zonen, verdecker) if skala else (None, None)
    if verd is not None and verd.any():
        for a in Kz: Kz[a][verd] = np.nan
        info["kacheln_verdeckt"] = int(verd.sum())
    L, S = klassen(Kz); R = regionen(L, S, T, schluessel=key)
    if debug: _debug_bild(foto, modell, m, L, T, debug, verd)
    out = []
    for r in R:
        ii = slice(r["px"][1] // T, r["px"][3] // T); jj = slice(r["px"][0] // T, r["px"][2] // T); sel = L[ii, jj] == r["art"]
        zahl = dict(kacheln=r["kacheln"], foto_struktur=round(float(np.nanmean(Kz["sf"][ii, jj][sel])), 2), modell_energie=round(float(np.nanmean(Kz["em1"][ii, jj][sel])), 1),
                    achse_foto=round(float(np.nanmean(Kz["achse_f"][ii, jj][sel])), 2), achse_modell=round(float(np.nanmean(Kz["achse_m"][ii, jj][sel])), 2),
                    richtung_schnitt=round(float(np.nanmean(Kz["schnitt"][ii, jj][sel])), 2),
                    kanten_foto=int(np.nansum(Kz["nf"][ii, jj][sel]) / 9), kanten_modell=int(np.nansum(Kz["nm"][ii, jj][sel]) / 9),
                    kanten_recall=round(float(np.nanmean(Kz["recall"][ii, jj][sel])), 2) if np.isfinite(Kz["recall"][ii, jj][sel]).any() else None,
                    kanten_praez=round(float(np.nanmean(Kz["praez"][ii, jj][sel])), 2) if np.isfinite(Kz["praez"][ii, jj][sel]).any() else None)
        b = dict(art=ARTEN[r["art"]], px=r["px"], staerke=r["staerke"], beleg=dict(zahl=zahl))
        if skala: b["ort"] = ort_aus_rahmen(K, r["px"], skala, fassaden or [])
        out.append(b)
    info["kacheln_bewertet"] = int(np.isfinite(Kz["em1"]).sum())
    return out, info


def _debug_bild(foto, modell, m, L, T, aus, verd=None):
    cv2 = _cv(); fa = {"fehlt": (255, 0, 0), "klumpen": (0, 0, 255), "form": (0, 200, 255), "verdeckt": (0, 160, 0)}; o = [foto.copy(), modell.copy()]
    L = L.copy()
    if verd is not None: L[verd] = "verdeckt"
    for (i, j), v in np.ndenumerate(L):
        if v in fa:
            for im in o: cv2.rectangle(im, (j * T + 1, i * T + 1), ((j + 1) * T - 2, (i + 1) * T - 2), fa[v], 2)
    cv2.imwrite(aus, np.hstack(o))


# ---------------------------------------------------------------- Tore / Bericht / Log zusammenfuehren
def _lade(p):
    try: return json.load(open(p)) if os.path.exists(p) else None
    except Exception: return None


def tor_befunde(audit, fassaden_by_id=None):
    B = []; quellen = {}
    hv = _lade(os.path.join(audit, "hand_vergleich.json")); quellen["hand_vergleich"] = hv is not None
    for e in (hv or {}).get("bauteile", []):
        u = e.get("urteil", "")
        if u in ("PASST",) or not u: continue
        falsch = {k: v for k, v in (e.get("masse") or {}).items() if isinstance(v, dict) and v.get("ok") is False}
        B.append(dict(art="fehlt/zu flach" if u == "FEHLT" else "Lage/Mass", ort=dict(bauteil=e.get("bauteil")), staerke=0.8 if u == "FEHLT" else 0.6,
                      beleg=dict(tor="audit/hand_vergleich.json", zahl=dict(urteil=u, masse=falsch, form=e.get("form")))))
    ff = _lade(os.path.join(audit, "fenster_form_tor.json")); quellen["fenster_form_tor"] = ff is not None
    for fid, L in ((ff or {}).get("fassaden") or {}).items():
        for e in L:
            for teil in ("fenster", "nische"):
                t = e.get(teil) or {}
                if t.get("urteil") == "FALSCH":
                    k = e.get("kasten") or [None] * 4
                    B.append(dict(art="Form falsch", ort=dict(fassade=fid, u=k[:2], z=k[2:], bauteil="fenster" if teil == "fenster" else "fenster/nische"), staerke=0.7,
                                  beleg=dict(tor="audit/fenster_form_tor.json", zahl=dict(gebaut=t.get("gebaut"), fotos_sagen=t.get("fotos_sagen"), stimmen=t.get("stimmen")))))
    ut = _lade(os.path.join(audit, "umriss_tor.json")); quellen["umriss_tor"] = ut is not None
    for e in (ut or {}).get("befunde", []):
        a = abs(float(e.get("abweichung_m", 0))); fehlt = "Foto hoeher" in e.get("art", "")
        B.append(dict(art="Umriss " + ("fehlt (Foto hoeher)" if fehlt else "zu hoch/erfunden (Modell hoeher)"), ort=dict(xyz=e.get("xyz"), z=[e["xyz"][2]] * 2 if e.get("xyz") else None, foto=e.get("foto")),
                      staerke=round(float(np.clip(a / 2.0, 0.1, 1)) * float(np.clip(e.get("breite_m", 1) / 1.5, 0.3, 1)), 2),
                      beleg=dict(tor="audit/umriss_tor.json", zahl=dict(abweichung_m=e.get("abweichung_m"), breite_m=e.get("breite_m")))))
    ea = _lade(os.path.join(audit, "ebenen_abweichung.json")); quellen["ebenen_abweichung"] = ea is not None
    for e in (ea or {}).get("ebenen", []):
        if (e.get("erfunden") or 0) > 0.5 and (e.get("modellkanten") or 0) > 2 * (e.get("fotokanten") or 0):
            B.append(dict(art="zu grob/verrauscht", ort=dict(fassade=e.get("fassade"), ebene=e.get("id")), staerke=round(float(np.clip((e["erfunden"] - 0.5) * 2, 0.1, 0.8)), 2),
                          beleg=dict(tor="audit/ebenen_abweichung.json", zahl=dict(erfunden=e.get("erfunden"), modellkanten=e.get("modellkanten"), fotokanten=e.get("fotokanten")),
                                     hinweis="Modell behauptet viele Kanten ohne Fotokante (Beulen/Rauschen im Relief)")))
        if (e.get("form_fehlt") or 0) > 0.1:
            B.append(dict(art="fehlt/zu flach", ort=dict(fassade=e.get("fassade"), ebene=e.get("id")), staerke=round(float(np.clip(e["form_fehlt"] * 2, 0.1, 0.9)), 2),
                          beleg=dict(tor="audit/ebenen_abweichung.json", zahl=dict(form_fehlt=e.get("form_fehlt"), fotokanten=e.get("fotokanten")))))
        for f in (e.get("liste_form") or [])[:3]:
            if (f.get("punkte") or 0) >= 150 and (e.get("form_fehlt") or 0) > 0.02:
                B.append(dict(art="fehlt/zu flach", ort=dict(fassade=e.get("fassade"), ebene=e.get("id"), u=[f["u0"], f["u1"]], z=[f["z0"], f["z1"]]), staerke=round(float(np.clip(f["punkte"] / 1500, 0.1, 0.6)), 2),
                              beleg=dict(tor="audit/ebenen_abweichung.json (liste_form)", zahl=dict(punkte=f["punkte"], tiefe=f.get("tiefe")))))
    fv = _lade(os.path.join(audit, "fototor_vergleich.json")); quellen["fototor_vergleich"] = fv is not None
    for foto, e in ((fv or {}).get("fotos") or {}).items():
        if isinstance(e, dict) and "schlechter" in str(e.get("urteil", "")):
            B.append(dict(art="Form falsch", ort=dict(foto=foto), staerke=0.5, beleg=dict(tor="audit/fototor_vergleich.json", zahl={k: e[k] for k in e if k != "sekunden"})))
    return B, quellen


def seiten_ohne_fotos(audit, fassaden):
    sl = _lade(os.path.join(audit, "seiten_luecken.json")); ids = []; B = []
    for w in (sl or {}).get("waende", []):
        if w.get("ungesehen"):
            fid = fassaden[w["nr"]]["id"] if fassaden and w.get("nr") is not None and w["nr"] < len(fassaden) else f"f{w.get('nr', 0):02d}"
            ids.append(fid)
            B.append(dict(art="keine Fotos", ort=dict(fassade=fid), staerke=0.0, stufe="KEINE FOTOS",
                          beleg=dict(tor="audit/seiten_luecken.json", zahl=dict(abdeckung=w.get("abdeckung"), fotos=w.get("fotos"), ohne_daten_m2=w.get("ohne_daten_m2")))))
    return B, ids, sl is not None


_TOOLS = None


def _werkzeug_in(text):
    global _TOOLS
    if _TOOLS is None: _TOOLS = sorted((os.path.basename(p)[:-3] for p in glob.glob(os.path.join(ROOT, "tools", "*.py"))), key=len, reverse=True)
    m = re.search(r"tools/([\w]+)\.(py|sh)", text)
    if m: return "tools/" + m.group(1) + "." + m.group(2)
    for t in _TOOLS:
        if len(t) > 5 and re.search(r"(?<![\w])" + re.escape(t) + r"(?![\w])", text): return "tools/" + t + ".py"
    return ""


CODEFEHLER = re.compile(r"\b(\w*Error|Traceback|Exception|NameError|KeyError|IndexError)\b")


def log_befunde(log=None, ab_zeile=0, bericht=None, ab_schritt=0):
    """Abgefangene Codefehler aus dem Kettenlog (log_warnungen.sammeln) + rote Stufen aus gesamtkette_bericht.json (ab dem Start dieses Laufs)."""
    B = []; ws = []
    if log and os.path.exists(log):
        try:
            import log_warnungen as LW
            ws = [dict(n=e["n"], text=e["text"], datei=os.path.basename(e["datei"]), zeile=e["zeile"]) for e in LW.sammeln([log], ab_zeile={log: ab_zeile})]
        except Exception as e: print("Log nicht gelesen:", type(e).__name__, e)
    elif bericht and os.path.exists(bericht):
        ws = (_lade(bericht) or {}).get("warnungen", [])
    for w in ws:
        t = w.get("text", "")
        if CODEFEHLER.search(t) and "Warning" not in t.split(":")[0][-12:] and "RuntimeWarning" not in t and "UserWarning" not in t:
            wz = _werkzeug_in(t)
            B.append(dict(art="Codefehler", ort=dict(werkzeug=wz), staerke=0.9, beleg=dict(tor="Log " + str(w.get("datei")), zahl=dict(n=w.get("n"), zeile=w.get("zeile")), text=t[:240]),
                          vorschlag=dict(werkzeug=wz or "(aus der Logzeile)", warum="abgefangener Programmfehler - der Teilschritt lief nicht, sein Ergebnis fehlt im Modell")))
    j = _lade(bericht) if bericht else None
    for e in ((j or {}).get("schritte") or [])[ab_schritt:]:
        if e.get("ok") is False:
            tx = str(e.get("fehler") or " | ".join(e.get("ende") or []))[:240]; wz = _werkzeug_in(str(e.get("stufe")) + " " + tx)
            B.append(dict(art="Stufe rot", ort=dict(stufe=e.get("stufe")), staerke=0.7, beleg=dict(tor="gesamtkette_bericht.json", zahl=dict(rc=e.get("rc")), text=tx),
                          vorschlag=dict(werkzeug=wz or "(Stufe im Bericht/Log)", warum="Kettenstufe fehlgeschlagen - ihr Log lesen, Ursache benennen")))
    return B


# ---------------------------------------------------------------- Hauptablauf
def erstellen(objekt, daten=None, neben=None, bericht=None, ab_schritt=0, log=None, ab_zeile=0, aus=None, T=30, debug_dir=None, verdecker=True):
    objp = os.path.abspath(objekt); od = os.path.dirname(objp); obj = json.load(open(objp)); ziel = os.path.basename(od); audit = os.path.join(od, "audit")
    daten = daten or f"/media/oem/scan/rc-park_daten/{ziel}"
    fj = _lade(os.path.join(daten, "fassade", "fassaden.json")); fassaden = (fj or {}).get("fassaden") or []
    konv = obj.get("seiten_konvention") or {}; hoch = max((f["z"][1] for f in fassaden), default=None)
    zonen = bauteil_zonen(audit); bild_dir = os.path.join(audit, "befunde")
    if os.path.isdir(bild_dir):
        for p in glob.glob(os.path.join(bild_dir, "b*.jpg")): os.remove(p)        # nur eigene Ausschnitte des vorigen Laufs
    neben = neben if neben is not None else sorted(p_ for p_ in glob.glob(os.path.join(audit, "neben_*.jpg")) if not os.path.basename(p_).startswith(("neben_detail_", "neben_details")))   # Detailansichten (neben_details.py) sind Ausschnitte ohne eigene K-Datei
    befunde = []; bilder = []; ungesehen_B, ungesehen, sl_da = seiten_ohne_fotos(audit, fassaden)
    for p in neben:
        foto = re.sub(r"^neben_", "", os.path.splitext(os.path.basename(p))[0]); K = kamera_laden(od, foto)
        try:
            vd = verdecker_netz(obj) if (K and fassaden and verdecker) else None
            bb, info = bild_befunde(p, K, fassaden, T, debug=os.path.join(debug_dir, "debug_" + os.path.basename(p)) if debug_dir else None, zonen=zonen, verdecker=vd)
        except Exception as e:
            bilder.append(dict(bild=os.path.relpath(p, od), fehler=f"{type(e).__name__}: {e}"[:200])); continue
        info["bild"] = os.path.relpath(p, od); info["kamera"] = bool(K); bilder.append(info)
        fo, mo = haelften(p)
        for b in bb:
            b["beleg"]["bild"] = os.path.relpath(p, od); b.setdefault("ort", {}); b["ort"]["bild_px"] = b.pop("px"); b["ort"]["foto"] = foto
            b["ort"]["bauteil"] = bauteil_von(b["ort"], zonen)
            if b["ort"].get("fassade") and fassaden:
                fa = next((f for f in fassaden if f["id"] == b["ort"]["fassade"]), None); b["ort"]["seite"] = seite_name(fa, konv) if fa else ""
            b["_bild"] = (fo, mo); befunde.append(b)
    tb, quellen = tor_befunde(audit); befunde += tb
    lb = log_befunde(log, ab_zeile, bericht, ab_schritt); befunde += lb
    # Tor-Befunde mit Ort in ein Nebeneinander-Bild projizieren (Ausschnitt), wenn eine Kamera da ist
    kams = {}
    for p in neben:
        foto = re.sub(r"^neben_", "", os.path.splitext(os.path.basename(p))[0]); K = kamera_laden(od, foto)
        if K and K.get("bild"):
            fo, mo = haelften(p); kams[foto] = (K, fo, mo, K["bild"][0] / fo.shape[1], os.path.relpath(p, od))
    for b in tb:
        o = b.get("ort") or {}; pts = []
        if o.get("xyz"): pts = [o["xyz"]]
        elif o.get("fassade") and o.get("u") and o.get("z") and None not in o["u"] + o["z"]:
            fa = next((f for f in fassaden if f["id"] == o["fassade"]), None)
            if fa: pts = [fassaden_punkt(fa, u, z) for u in o["u"] for z in o["z"]]
        if not pts: continue
        for foto, (K, fo, mo, sk, rel) in sorted(kams.items(), key=lambda kv: kv[0] != o.get("foto")):
            pp = [projizieren(K, q, sk) for q in pts]
            if any(q is None for q in pp): continue
            xs = [q[0] for q in pp]; ys = [q[1] for q in pp]; r_ = 12 if len(pp) == 1 else 0
            x0, y0, x1, y1 = int(min(xs)) - r_, int(min(ys)) - r_, int(max(xs)) + r_ + 1, int(max(ys)) + r_ + 1
            if x1 <= 0 or y1 <= 0 or x0 >= fo.shape[1] or y0 >= fo.shape[0]: continue
            o["bild_px"] = [max(0, x0), max(0, y0), min(fo.shape[1], x1), min(fo.shape[0], y1)]; o.setdefault("foto", foto); b["_bild"] = (fo, mo); b["beleg"]["bild"] = rel; break
        if o.get("fassade") and o.get("u") and o.get("z") and not o.get("bauteil"): o["bauteil"] = bauteil_von(o, zonen)
    # Seiten ohne Fotos: Bildbefunde dort herabstufen, Seiten selbst als Hinweis
    for b in befunde:
        fid = (b.get("ort") or {}).get("fassade")
        if fid and fid in ungesehen and b["art"] in ARTEN.values(): b["stufe"] = "KEINE FOTOS"; b["staerke"] = 0.0; b["beleg"]["hinweis"] = "Fassade ohne Fotobeleg (seiten_luecken 'ungesehen') - kein Fehlerbeweis"
        b.setdefault("stufe", "FEHLER" if b["staerke"] >= 0.3 else "HINWEIS")
        if "vorschlag" not in b:
            o = b.get("ort") or {}; zm = (sum(o["z"]) / 2) if o.get("z") and None not in o["z"] else None
            b["vorschlag"] = vorschlag(b["art"], o.get("bauteil", ""), zm, hoch)
    for b in ungesehen_B:
        fa = next((f for f in fassaden if f["id"] == b["ort"]["fassade"]), None); b["ort"]["seite"] = seite_name(fa, konv) if fa else ""; b["vorschlag"] = vorschlag("keine Fotos")
    befunde += ungesehen_B
    reihen = {"FEHLER": 0, "HINWEIS": 1, "KEINE FOTOS": 2}
    befunde.sort(key=lambda b: (reihen.get(b["stufe"], 3), -b["staerke"]))
    for i, b in enumerate(befunde):
        b["id"] = f"b{i + 1:02d}"; fb = b.pop("_bild", None); o = b.get("ort") or {}
        if fb and o.get("bild_px"):
            a = ausschnitt(fb[0], fb[1], o["bild_px"], os.path.join(bild_dir, f"{b['id']}.jpg"))
            if a: b["ausschnitt"] = os.path.relpath(a, od)
    # Ursache verknuepfen: ein abgefangener Codefehler im zustaendigen Werkzeug erklaert den Sichtbefund (1122a: quader_raster UnboundLocalError -> Mauerwerk wieder klumpig)
    cf = [(b["id"], b["vorschlag"]["werkzeug"]) for b in befunde if b["art"] in ("Codefehler", "Stufe rot") and (b.get("vorschlag") or {}).get("werkzeug", "").startswith("tools/")]
    for b in befunde:
        if b["art"] in ("Codefehler", "Stufe rot"): continue
        u = [i for i, w in cf if w in (b.get("vorschlag") or {}).get("werkzeug", "")]
        if u: b["beleg"]["moegliche_ursache"] = u
    zus = {}
    for b in befunde: zus[b["stufe"]] = zus.get(b["stufe"], 0) + 1
    quellen.update(neben_bilder=len(neben), fassaden=bool(fassaden), seiten_luecken=sl_da, log=bool(log and os.path.exists(log)), bericht=bool(bericht and os.path.exists(bericht)))
    E = dict(werkzeug="tools/befundliste.py", zeit=time.strftime("%Y-%m-%d %H:%M"), objekt=os.path.relpath(objp, ROOT) if objp.startswith(ROOT) else objp,
             schwellen=dict(GLATT_EM=GLATT_EM, STRUKTUR_SF=STRUKTUR_SF, KLUMPEN_EM=KLUMPEN_EM, KLUMPEN_ACHSE=KLUMPEN_ACHSE, UEBERSCHUSS=UEBERSCHUSS, KANTEN_MIN=KANTEN_MIN,
                            FORM_F1=FORM_F1, BELEG_QUOTE=BELEG_QUOTE, kachel_px=T),
             quellen=quellen, bilder=bilder, zusammenfassung=zus, ohne_fotos=ungesehen, befunde=befunde,
             hinweis="Bild schlaegt Zahl: Ausschnitte audit/befunde/bNN.jpg ANSEHEN. ANNAHME: Fotostruktur = Geometrie (Wandmalerei/Vordergrund = Fehlalarm moeglich).")
    aus = aus or os.path.join(audit, "befunde.json")
    try: __import__("json_sicher").schreiben(aus, E)
    except Exception:
        os.makedirs(os.path.dirname(aus), exist_ok=True); json.dump(E, open(aus, "w"), indent=1, ensure_ascii=False)
    return E


def zeile(b):
    o = b.get("ort") or {}; w = []
    if o.get("fassade"): w.append(o["fassade"] + (f" {o['seite']}" if o.get("seite") else ""))
    if o.get("z") and None not in o["z"]: w.append(f"z {o['z'][0]:.1f}-{o['z'][1]:.1f} m")
    if o.get("bauteil"): w.append(o["bauteil"])
    for k in ("stufe", "werkzeug", "ebene"):
        if o.get(k): w.append(str(o[k]))
    return f"{b['id']} {b['stufe']:<11} {b['art']:<22} {b['staerke']:.2f}  {', '.join(w)}  -> {(b.get('vorschlag') or {}).get('werkzeug', '')[:70]}"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0]); ap.add_argument("objekt")
    ap.add_argument("--daten", default=None); ap.add_argument("--neben", nargs="*", default=None); ap.add_argument("--bericht", default=None); ap.add_argument("--ab-schritt", type=int, default=0)
    ap.add_argument("--log", default=None); ap.add_argument("--ab-zeile", type=int, default=0); ap.add_argument("--aus", default=None); ap.add_argument("--kachel", type=int, default=30)
    ap.add_argument("--debug", default=None, help="Ordner fuer Kachel-Overlays (blau fehlt, rot Klumpen, gelb Form)")
    ap.add_argument("--ohne-verdecker", action="store_true", help="LoD2-Nachbarn nicht als Verdecker laden (schneller, mehr Fehlalarme 'fehlt')")
    a = ap.parse_args(argv)
    E = erstellen(a.objekt, a.daten, a.neben, a.bericht, a.ab_schritt, a.log, a.ab_zeile, a.aus, a.kachel, a.debug, verdecker=not a.ohne_verdecker)
    for b in E["befunde"][:25]: print(zeile(b))
    print(f"BEFUNDLISTE: {len(E['befunde'])} Befunde ({', '.join(f'{v} {k}' for k, v in E['zusammenfassung'].items())}); Bilder {len(E['bilder'])}; -> {a.aus or 'audit/befunde.json'}")
    return 0 if (E["bilder"] or E["befunde"] or any(E["quellen"].values())) else 3


if __name__ == "__main__":
    sys.exit(main())
