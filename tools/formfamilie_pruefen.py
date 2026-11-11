#!/usr/bin/env python3
"""formfamilie_pruefen.py - FORMFAMILIEN-SICHTPRUEFUNG JE BAUTEIL (Spec modelle/SPEC_FORMFAMILIE_SICHTPRUEFUNG.md, Nutzerauftrag 11.11.).

Warum: Die Kantenmessung (Foto-F1) misst Kantendichte, keine Formfamilie (Lehren L46/L47): Saegezahn statt Treppe, spitz statt rund, Rechteck statt Bogen,
zu niedriger Sockel, fehlende Aufsaetze/Gelaender blieben im Kreis unbemerkt. Hier tut das Werkzeug, was der Nutzer tut: Foto und Modell-Render
nebeneinander ansehen und NUR die Formfamilie vergleichen.

Ablauf je Teil:
  1. 3-4 Fotos mit grosser sichtbarer Teilflaeche (sicht_px der Formliste), verschiedene Blickrichtungen (>= 25 Grad), moeglichst ein schraeges.
  2. Bildpaar je Foto: links Fotoausschnitt (entzerrt, Teilbox + 30 % Rand), rechts normalen-schattierter Render des GANZEN Modells aus derselben Kamera,
     gleicher Ausschnitt, Zielteil orange, Rest grau, Kanten an Flaechen-/Tiefensprung dunkel.
  3. Bildpruefer `claude -p --model opus` liest die Paare (Read-Werkzeug) und liefert JSON. Fehler/kein JSON = "ungeprueft", nie "passt".
Ausgabe: <arbeit>/formfamilie.json, <arbeit>/bilder/. Schreibt NICHT in masstabelle.json, haengt nichts in den Kreis ein.

Aufruf: /media/oem/scan/venv-seg/bin/python -I tools/formfamilie_pruefen.py <objekt> --teile_dir D --formliste F.json [--teile a,b] [--arbeit A] [--nur_bilder]
Der Prompt kennt KEINE Sollbefunde (Selbstbezug-Verbot); er nennt nur die Formfamilien-Kategorien und den Teilnamen.
"""
import sys, os, json, glob, re, argparse, time, math, subprocess, threading, numpy as np, cv2, trimesh
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import foto_diff as FD, fehlteile_finden as FF, render_kern as RK, teil_fotoform as TF

R0 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARBEIT_STD = "/media/oem/scan/rc-park_tmp/formfamilie"
PANEL = 880           # lange Seite je Bildhaelfte (Paar <= ~1800 px breit)
RAND = 0.30           # Rand um die projizierte Teilbox
MIN_WINKEL = 25.0     # Grad Unterschied der Blickrichtungen
KACHEL_MIN_PX = 1500   # Mindestzahl sichtbarer Teilpixel je Detailkachel
MIN_SICHT = 2500      # sichtbare Teilpixel, darunter kein Kandidat

PROMPT = """Du bist Bildpruefer fuer ein 3D-Modell (H0 1:87, 3D-Druck) des Gebaeudes "{objekt}". Pruefe das Bauteil "{teil}".
Jede der folgenden Bilddateien ist ein Paar: LINKS ein Foto (Ausschnitt um das Bauteil), RECHTS ein schattierter Render des Modells aus DERSELBEN Kamera mit
demselben Ausschnitt. Im Render ist das zu pruefende Bauteil ORANGE, alle anderen Bauteile grau; dunkle Linien = Kanten/Sprunge. Nur das orange Bauteil beurteilen.
Oben im Bild steht das Foto-Kuerzel; Dateien mit Zusatz in eckigen Klammern (Fuss, Kopf, Ende A, Ende B) sind DETAILKACHELN (unteres Drittel, oberes Drittel, aeussere Fuenftel an den beiden Enden der Hauptachse) - pruefe dort gezielt die Stationen Fuss, Abschluss und Enden. Dateien mit [Kontur] sind FRONTAL-PARALLELE Ansichten ohne Perspektive: links das Foto per Homographie auf die Frontebene des Teils entzerrt, rechts das Modell orthografisch in derselben Ebene und demselben Ausschnitt. Bei Boegen (rund/spitz) und Stufen/Zacken/Treppen die [Kontur]-Kachel zur Entscheidung heranziehen (entzerrt wirken nur Dinge in der Teilebene richtig, Tiefenversatz verzerrt). Die [Fuss]-Kachel reicht bis unter die Teilunterkante. Die Dateinamen tragen das Etikett. Sieh dir jede Datei mit dem Read-Werkzeug an (Bilder werden angezeigt):
{pfade}

Vorgehen: Beschreibe ERST die Form des Bauteils im Foto, DANN die Form im Modell (Mehrzahl der Bilder beachten, ein Foto allein kann verdeckt oder schief sein).
Gehe dafuer bei jedem Bauteil einen Pflicht-Rundgang durch und vergleiche je Station Foto gegen Modell (auch wenn alles gleich aussieht, notiere kurz in "form_*"):
 (1) Fuss/Sockel/Auflager: Grundrissform (rund, achteckig ...), Hoehe im Verhaeltnis zur Schaftdicke bzw. Elementbreite - schaetze das Verhaeltnis in Foto und Modell als Zahl;
 (2) Schaft/Koerper: Querschnitt, Gliederung (glatt, gerillt, gedreht, Rippen), Proportion Hoehe zu Breite als Zahl;
 (3) Oeffnungen (Bogen, Fenster, Tor, Durchgang, auch an den Enden/Seitenflaechen des Bauteils): Umriss jeder Oeffnung - Halbkreis, Spitzbogen, Segmentbogen oder Rechteck;
 (4) Obere Kontur/Abschluss: bei Treppen/Zacken/Daechern fuer jede Stufe die Oberseite (waagerecht oder schraeg) und die Vorderkante (senkrecht oder schraeg), Abdeckungen, Aufsaetze, Bekroenungen;
 (5) Enden und Seiten: ist das Bauteil an den Enden offen, zugemauert, mit Seitenteilen/Gelaender abgeschlossen oder stumpf abgeschnitten;
 (6) Anzahl und Anordnung gleicher Elemente: zaehle in Foto und Modell.
Nenne dann NUR Abweichungen der FORMFAMILIE, naemlich:
- Bogenart (rund, spitz, gerade/Rechteck, Segmentbogen, Kleeblatt ...)
- Stufen: Treppe (waagerechte Stufen) oder Zacke/Saegezahn oder Dach/Schraege
- Anzahl gleicher Elemente (Bogen, Fenster, Saeulen, Stufen ...)
- fehlende oder erfundene Elemente (Sockel, Aufsatz, Gelaender, Stirn/Seitenteil, Rippen, Masswerk, Pfosten ...)
- Proportion: wenn deine geschaetzten Verhaeltniszahlen aus dem Rundgang (Foto gegen Modell) um mehr als etwa 15 % abweichen, melde sie (bei 15-30 % hoechstens "mittel", darueber "hoch", wenn in 2 Bildern gleich)
NICHT melden: Farbe, Textur, Feinlage (wenige cm), Schmutz, Verdeckungen im Foto (Baeume, Personen, Schilder, Geruest, Nachbarhaeuser),
Teile, die im Foto gar nicht zu sehen sind, Details unter ca. 0,3 m Modellgroesse. Gib "sicher" nur mit "hoch", wenn die Abweichung in mindestens 2 Bildern
klar zu sehen ist; ein einziges Bild oder unklare Sicht = hoechstens "mittel"; Vermutung = "niedrig". Wenn Foto und Modell in der Formfamilie passen,
ist die Liste der Abweichungen LEER - erfinde nichts. Wenn das Bauteil im Foto nicht erkennbar ist, melde das in "form_foto" und lasse die Liste leer.

Letzte Zeile deiner Antwort GENAU (eine Zeile, gueltiges JSON, deutsche Texte):
ERGEBNIS {{"teil": "{teil}", "fotos": [{fotos}], "form_foto": "...", "form_modell": "...", "abweichungen": [{{"merkmal": "...", "foto": "...", "modell": "...", "fotos_belegt": ["..."], "sicher": "hoch|mittel|niedrig"}}]}}
"""


def winkel_diff(a, b):
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def fotowahl(teil, je_foto, kam, mesh_w, n=4, nur_fotos=None):
    """je_foto: {foto: {sicht_px,...}} aus der Formliste; kam: {foto: (Zentrum xyz im Modellrahmen)}; mesh_w: Teilnetz im Modellrahmen.
    Greedy: bestes sicht_px, dann jeweils das beste mit >= MIN_WINKEL Abstand zu allen gewaehlten; ein schraeges Foto wird bevorzugt eingetauscht, falls keins gewaehlt."""
    kand = [(v["sicht_px"], f) for f, v in je_foto.items() if isinstance(v, dict) and v.get("sicht_px", 0) >= MIN_SICHT and f in kam and (not nur_fotos or f in nur_fotos)]
    kand.sort(reverse=True)
    if not kand: return []
    ctr = mesh_w.bounds.mean(0)
    v = mesh_w.vertices[:, :2] - mesh_w.vertices[:, :2].mean(0); w, V = np.linalg.eigh(np.cov(v.T) + 1e-9 * np.eye(2))
    ax = V[:, 1]; nrm = np.array([-ax[1], ax[0]]); naz = math.degrees(math.atan2(nrm[1], nrm[0]))   # Teilflaechennormale (waagerecht), Vorzeichen egal
    az = {f: math.degrees(math.atan2(kam[f][1] - ctr[1], kam[f][0] - ctr[0])) for _, f in kand}
    def schraeg(f):
        d = min(winkel_diff(az[f], naz), winkel_diff(az[f], naz + 180)); return 25.0 <= d <= 75.0
    kand = kand[:14]; wahl = []
    for s, f in kand:
        if all(winkel_diff(az[f], az[g]) >= MIN_WINKEL for g in wahl): wahl.append(f)
        if len(wahl) == n: break
    if not any(schraeg(f) for f in wahl):
        for s, f in kand:
            if f not in wahl and schraeg(f) and all(winkel_diff(az[f], az[g]) >= MIN_WINKEL for g in wahl[:-1]):
                wahl = wahl[:-1] + [f] if len(wahl) >= n else wahl + [f]; break
    # STIRN (Runde 2): mindestens ein Foto mit Blickrichtung eher ENTLANG der Hauptachse (Stirnseite), falls sicht_px >= 5 % des Maximums
    def stirn(f):
        d = min(winkel_diff(az[f], naz + 90), winkel_diff(az[f], naz - 90)); return d <= 35.0
    if not any(stirn(f) for f in wahl):
        smax = kand[0][0]
        for s_, f in kand:
            if stirn(f) and s_ >= 0.05 * smax: wahl.append(f); break
    return wahl


def schattieren(Mw, fid, dv, R, hell=None):
    """Graustufen-Schattierung (Float 0..1) aus Dreiecksnormalen: Scheinwerfer + Seitenlicht; dunkle Linien an Dreiecks-Gruppen-/Tiefensprung."""
    Nc = np.asarray(Mw.face_normals) @ R.T                        # Normalen im Kamerarahmen (z = Blickrichtung, y nach unten)
    ok = fid >= 0; n = np.zeros(fid.shape + (3,), np.float32); n[ok] = Nc[fid[ok]]
    flip = n[..., 2] > 0; n[flip] *= -1                          # zur Kamera drehen
    kopf = np.clip(-n[..., 2], 0, 1)
    L = np.array([-0.45, -0.65, -0.62]); L /= np.linalg.norm(L); seite = np.clip(n @ (-L), 0, 1)
    g = 0.18 + 0.42 * kopf + 0.40 * seite
    img = np.where(ok, g, 0.93).astype(np.float32)
    # Kanten: Normalensprung (> ~25 Grad) und Tiefensprung (> 4 %)
    nn = n.copy(); dx = np.linalg.norm(nn[:, 1:] - nn[:, :-1], axis=2); dy = np.linalg.norm(nn[1:] - nn[:-1], axis=2)
    kante = np.zeros(fid.shape, bool); kante[:, 1:] |= dx > 0.42; kante[1:] |= dy > 0.42
    dd = np.where(np.isfinite(dv), dv, 0.0)
    rx = np.abs(dd[:, 1:] - dd[:, :-1]) > 0.04 * np.maximum(dd[:, 1:], 0.5); ry = np.abs(dd[1:] - dd[:-1]) > 0.04 * np.maximum(dd[1:], 0.5)
    kante[:, 1:] |= rx; kante[1:] |= ry
    return img, kante


def box_aus_maske(m, W, H, rand=RAND):
    ys, xs = np.where(m)
    if len(xs) == 0: return None
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    bw, bh = x1 - x0 + 1, y1 - y0 + 1; s = max(bw, bh)
    bw2, bh2 = max(bw, 0.25 * s) * (1 + 2 * rand), max(bh, 0.25 * s) * (1 + 2 * rand)
    cx_, cy_ = (x0 + x1) / 2, (y0 + y1) / 2
    return (int(max(0, cx_ - bw2 / 2)), int(max(0, cy_ - bh2 / 2)), int(min(W, cx_ + bw2 / 2)), int(min(H, cy_ + bh2 / 2)))


def beschriften(im, text):
    cv2.rectangle(im, (0, 0), (im.shape[1], 26), (0, 0, 0), -1)
    cv2.putText(im, text, (6, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA); return im


def bildpaar(foto_bgr, render_gr, kante, ziel, box, titel, pfad):
    x0, y0, x1, y1 = box
    f = foto_bgr[y0:y1, x0:x1].copy()
    g = (np.clip(render_gr, 0, 1) * 255).astype(np.uint8)
    rgb = np.stack([g, g, g], 2).astype(np.float32)
    tint = np.array([40, 140, 255], np.float32)                  # BGR orange
    rgb[ziel] = rgb[ziel] * 0.35 + (0.65 * tint) * (0.35 + 0.9 * g[ziel, None].astype(np.float32) / 255.0)
    rgb[kante] = rgb[kante] * 0.25
    r = np.clip(rgb, 0, 255).astype(np.uint8)[y0:y1, x0:x1]
    s = PANEL / max(f.shape[:2]); sz = (max(2, int(f.shape[1] * s)), max(2, int(f.shape[0] * s)))
    f = cv2.resize(f, sz, interpolation=cv2.INTER_AREA); r = cv2.resize(r, sz, interpolation=cv2.INTER_NEAREST if s > 1 else cv2.INTER_AREA)
    paar = np.hstack([beschriften(f, f"FOTO {titel}"), np.full((f.shape[0], 6, 3), 255, np.uint8), beschriften(r, f"MODELL (Teil orange) {titel}")])
    cv2.imwrite(pfad, paar, [cv2.IMWRITE_JPEG_QUALITY, 90]); return pfad


def unterkante_px(m, R, t, f, cx, cy):
    """Bildzeile der Teilunterkante (tiefste Ecken des Teilnetzes, projiziert) und Bildhoehe des Teils in px; (None, 0) wenn nicht projizierbar."""
    V = m.vertices; X = V @ np.asarray(R, float).T + np.asarray(t, float).ravel(); ok = X[:, 2] > 1
    if ok.sum() < 3: return None, 0.0
    v = f * X[ok, 1] / X[ok, 2] + cy; z = V[ok, 2]; low = z <= z.min() + 0.03
    return float(v[low].max()), float(v.max() - v.min())


def fuss_box(kb, ybot, hpx, H, rand=0.15):
    """Fuss-Kachelbox nach unten bis Teilunterkante + 15 % Teilhoehe verlaengern; None, wenn die Unterkante samt Rand nicht im Bild liegt."""
    if ybot is None: return None
    y1 = ybot + rand * hpx
    if y1 > H - 1 or ybot < kb[1]: return None
    return (kb[0], kb[1], kb[2], int(max(kb[3], y1)))


def ortho_kontur(m, achse, nrm, seite, mitte, ue, ze, breite_px=PANEL, rand=0.12):
    """Orthografische Frontansicht des Teils m auf die Ebene (Mitte mitte, Normale nrm): Rueckgabe (Bild BGR, Projektionsfunktion Weltpunkt -> Pixel).
    Betrachter steht auf der Seite 'seite' (+1/-1) der Normale. Ortho = perspektivische Kamera in 400 m Abstand mit grosser Brennweite.
    ue = (u0,u1) Ausdehnung entlang achse, ze = (z0,z1) Hoehe; Rand relativ."""
    d = -seite * np.array([nrm[0], nrm[1], 0.0]); d /= np.linalg.norm(d)
    zc = d; yc = np.array([0.0, 0.0, -1.0]); xc = np.cross(yc, zc); R = np.stack([xc, yc, zc])
    Wm = (ue[1] - ue[0]) * (1 + 2 * rand); Hm = (ze[1] - ze[0]) * (1 + 2 * rand); Wm, Hm = max(Wm, 0.3 * Hm), max(Hm, 0.3 * Wm); s = breite_px / max(Wm, Hm)   # flache/duenne Teile: Mindestseitenverhaeltnis 0,3 (lesbar)
    W, H = int(Wm * s) + 1, int(Hm * s) + 1; D = 400.0; C = mitte - D * d; t = -R @ C; f = s * D
    proj = lambda P: np.stack([f * ((R @ (np.asarray(P, float) - C))[0]) / D + W / 2, f * ((R @ (np.asarray(P, float) - C))[1]) / D + H / 2])
    dp, fid, _ = RK.dreiecke_rastern(m, R, t, f, W / 2, H / 2, W, H)
    ok = fid >= 0; Nc = np.asarray(m.face_normals) @ R.T; n = np.zeros(fid.shape + (3,), np.float32); n[ok] = Nc[fid[ok]]
    n[n[..., 2] > 0] *= -1; kopf = np.clip(-n[..., 2], 0, 1)
    L = np.array([-0.45, -0.65, -0.62]); L /= np.linalg.norm(L); g = 0.25 + 0.45 * kopf + 0.30 * np.clip(n @ (-L), 0, 1)
    img = np.where(ok, g, 0.93).astype(np.float32)
    dd = np.where(np.isfinite(dp), dp, 0.0); kante = np.zeros(fid.shape, bool)
    dx = np.linalg.norm(n[:, 1:] - n[:, :-1], axis=2); dy = np.linalg.norm(n[1:] - n[:-1], axis=2)
    kante[:, 1:] |= dx > 0.42; kante[1:] |= dy > 0.42
    kante[:, 1:] |= np.abs(dd[:, 1:] - dd[:, :-1]) > 0.10; kante[1:] |= np.abs(dd[1:] - dd[:-1]) > 0.10
    g8 = (img * 255).astype(np.uint8); rgb = np.stack([g8, g8, g8], 2).astype(np.float32)
    tint = np.array([40, 140, 255], np.float32); rgb[ok] = rgb[ok] * 0.35 + 0.65 * tint * (0.35 + 0.9 * g8[ok, None] / 255.0)
    rgb[kante] *= 0.25
    return np.clip(rgb, 0, 255).astype(np.uint8), proj, (Wm, Hm)


def kontur_kachel(tn, m, ctx_foto, nr, pfad):
    """[Kontur]-Kachel: links Foto nr entzerrt auf die Frontebene des Teils (Homographie der 4 Ecken der Teilbox-Frontflaeche), rechts orthografisches Modell.
    ctx_foto = (im0, R, t, f, cx, cy, W, H) des Fotos (entzerrt, im Modellrahmen m). Rueckgabe Pfad oder None."""
    im0, R, t, f, cx, cy, W, H = ctx_foto
    v2 = m.vertices[:, :2] - m.vertices[:, :2].mean(0); w_, V_ = np.linalg.eigh(np.cov(v2.T) + 1e-9 * np.eye(2))
    ax = V_[:, 1]; nrm = np.array([-ax[1], ax[0]]); b = m.bounds; mitte = m.vertices.mean(0) * 0 + (b[0] + b[1]) / 2
    uv = (m.vertices[:, :2] - mitte[:2]) @ ax; ue = (float(uv.min()), float(uv.max())); ze = (float(b[0, 2]), float(b[1, 2]))
    C = -np.asarray(R, float).T @ np.asarray(t, float).ravel(); n3 = np.array([nrm[0], nrm[1], 0.0])
    seite = 1.0 if float((C - mitte) @ n3) >= 0 else -1.0
    modell, proj, (Wm, Hm) = ortho_kontur(m, ax, nrm, seite, mitte, ue, ze)
    h_, w_ = modell.shape[:2]
    # Ecken auch mit dem Rand der Ortho-Ansicht (Rand 12 %), damit Foto und Modell denselben Ausschnitt zeigen
    uc, zc = (ue[0] + ue[1]) / 2, (ze[0] + ze[1]) / 2; ue2 = (uc - Wm / 2, uc + Wm / 2); ze2 = (zc - Hm / 2, zc + Hm / 2)   # ganzer Ortho-Ausschnitt
    welt = [mitte + np.array([ax[0], ax[1], 0.0]) * u + np.array([0, 0, 1.0]) * (z - mitte[2]) for u, z in ((ue2[0], ze2[0]), (ue2[1], ze2[0]), (ue2[1], ze2[1]), (ue2[0], ze2[1]))]
    # Homographie aus einem Gitter ueber die Frontebene (Ecken + Innenpunkte); nur Punkte VOR der Kamera und im Bild zaehlen -> auch bei nahen Kameras (Ecke hinter dem Kamerazentrum) loesbar
    gs = np.linspace(0, 1, 7); G = [(u, z) for u in ue2[0] + gs * (ue2[1] - ue2[0]) for z in ze2[0] + gs * (ze2[1] - ze2[0])]
    P3 = [mitte + np.array([ax[0], ax[1], 0.0]) * u + np.array([0, 0, 1.0]) * (z - mitte[2]) for u, z in G]
    Xc = [np.asarray(R, float) @ P + np.asarray(t, float).ravel() for P in P3]; sel = [i for i, x in enumerate(Xc) if x[2] > 1 and -0.1 * W <= f * x[0] / x[2] + cx < 1.1 * W and -0.1 * H <= f * x[1] / x[2] + cy < 1.1 * H]
    if len(sel) < 8: print(f'  Kontur {nr} {tn}: nur {len(sel)} Ebenenpunkte im Bild', flush=True); return None
    src = np.float32([[f * Xc[i][0] / Xc[i][2] + cx, f * Xc[i][1] / Xc[i][2] + cy] for i in sel]); dst = np.float32([proj(P3[i]) for i in sel])
    Hm, _ = cv2.findHomography(src, dst, 0)
    if Hm is None: return None
    foto = cv2.warpPerspective(im0, Hm, (w_, h_), flags=cv2.INTER_LINEAR, borderValue=(40, 40, 40))
    paar = np.hstack([beschriften(foto, f"FOTO {nr} [Kontur] frontal entzerrt"), np.full((h_, 6, 3), 255, np.uint8), beschriften(modell.copy(), f"MODELL [Kontur] orthografisch (Teil orange)")])
    cv2.imwrite(pfad, paar, [cv2.IMWRITE_JPEG_QUALITY, 90]); return pfad


def bilder_erzeugen(a, obj, objp, teile_pfade, wahl, formliste_teile, bilder_dir):
    """wahl: {teil: [fotos]}. Rastert je Foto das ganze Modell einmal, dann je Teil. Rueckgabe {teil: {foto: pfad}}."""
    stl = a.stl or os.path.join(R0, obj["stl"]); sk = obj.get("stl_massstab", 87) / 1000.0
    ganz = trimesh.load(stl, force="mesh"); ganz.apply_scale(sk)
    TM = {}
    def teilnetz(t):
        if t not in TM:
            m = trimesh.load(teile_pfade[t], force="mesh"); m.apply_scale(sk); TM[t] = m
        return TM[t]
    je_foto = {}
    for t, fl in wahl.items():
        for f in fl: je_foto.setdefault(f, []).append(t)
    out = {t: {} for t in wahl}; kand_k = {}
    sc = os.path.join(bilder_dir, "_kacheln.json")
    if a.bilder_neu and os.path.exists(sc): os.remove(sc)   # Zwischenstand der Detailkacheln gehoert zu den neu gerenderten Bildern
    for nr, ts in je_foto.items():
        vorh = {tn: os.path.join(bilder_dir, f"{tn}_{nr}.jpg") for tn in ts}
        if not a.bilder_neu and all(os.path.exists(v) for v in vorh.values()):   # Bilder dieses Fotos schon da (Wiederaufnahme)
            for tn, v in vorh.items(): out[tn][nr] = v
            continue
        kp = FF.k_datei(objp, obj, R0, nr); K = json.load(open(kp))
        bild = glob.glob(os.path.join(R0, obj["fotos_dir"], nr + "_*"))
        if not bild: continue
        im0 = cv2.imread(bild[0]); im0, K = FD.foto_skalieren(im0, K); kk = K["kamera"]
        im0, _ = FF.foto_entzerren(im0, kk); H, W = im0.shape[:2]
        R, t, f, _, _ = FF.kamera_laden(K, obj, nr, R0, W, H); cx, cy = float(kk.get("cx", W / 2)), float(kk.get("cy", H / 2))
        tr = TF.rahmen(stl, obj, kk)
        Mw = ganz.copy(); Mw.apply_translation(tr)
        dv, fid, _ = RK.dreiecke_rastern(Mw, R, t, f, cx, cy, W, H)
        img, kante = schattieren(Mw, fid, dv, R)
        for tn in ts:
            m = teilnetz(tn).copy(); m.apply_translation(tr)
            dp, _, pos = RK.dreiecke_rastern(m, R, t, f, cx, cy, W, H)
            ziel = np.isfinite(dp) & (dp <= dv * 1.003 + 0.03)
            if ziel.sum() < 200: continue
            box = box_aus_maske(ziel, W, H)
            pf = os.path.join(bilder_dir, f"{tn}_{nr}.jpg")
            out[tn][nr] = bildpaar(im0, img, kante, ziel, box, nr, pf)
            # DETAILKACHELN: Fuss/Kopf = unteres/oberes Drittel der Teilbox (Hoehe), Enden = aeussere Fuenftel entlang der waagerechten Hauptachse
            b = m.bounds; z0, z1 = b[0, 2], b[1, 2]; v2 = m.vertices[:, :2] - m.vertices[:, :2].mean(0)
            ax = np.linalg.eigh(np.cov(v2.T) + 1e-9 * np.eye(2))[1][:, 1]; u = (pos[..., :2] - m.vertices[:, :2].mean(0)) @ ax
            uv = v2 @ ax; u0, u1 = uv.min(), uv.max(); zz = pos[..., 2]
            regionen = {"Fuss": zz <= z0 + (z1 - z0) / 3, "Kopf": zz >= z1 - (z1 - z0) / 3,
                        "Ende A": u <= u0 + (u1 - u0) / 5, "Ende B": u >= u1 - (u1 - u0) / 5}
            ybot, hpx = unterkante_px(m, R, t, f, cx, cy)
            for lab, reg in regionen.items():
                zk = ziel & reg
                if zk.sum() < KACHEL_MIN_PX: continue
                kb = box_aus_maske(zk, W, H, rand=0.5)
                if lab == "Fuss":    # Runde 3: Kachel muss Teilunterkante + 15 % Rand nach unten enthalten, sonst kein Fuss-Kandidat dieses Fotos
                    kb = fuss_box(kb, ybot, hpx, H)
                    if kb is None: continue
                kp = os.path.join(bilder_dir, f"{tn}_{lab.replace(' ', '')}_{nr}.jpg")
                bildpaar(im0, img, kante, ziel, kb, f"{nr} [{lab}]", kp)
                kand_k.setdefault(tn, {}).setdefault(lab, []).append((int(zk.sum()), nr, kp))
        print(f"Foto {nr}: {len(ts)} Teile gerendert", flush=True)
    # je Kachel das Foto mit den meisten sichtbaren Kachelpixeln behalten, die Etikette stehen als Schluessel '@Fuss' usw. im Paare-Dict
    if kand_k:
        bestk = {tn: {lab: max(c) for lab, c in d.items()} for tn, d in kand_k.items()}
        try: alt = json.load(open(sc))
        except Exception: alt = {}
        alt.update(bestk); json.dump(alt, open(sc, "w"))
        for tn, d in bestk.items():
            for lab, (px, nr, kp) in d.items(): out[tn]["@" + lab + " (" + nr + ")"] = kp
            for lab, c in kand_k[tn].items():
                for px, nr, kp in c:
                    if kp != d[lab][2]:
                        try: os.remove(kp)
                        except OSError: pass
    if os.path.exists(sc):
        for tn, d in json.load(open(sc)).items():
            if tn in out and not any(k.startswith("@") for k in out[tn]):
                for lab, (px, nr, kp) in d.items():
                    if os.path.exists(kp): out[tn]["@" + lab + " (" + nr + ")"] = kp
    # ---- Runde 3: Kontext-Helfer, Fuss-Nachsuche (Unterkante im Bild), [Kontur]-Kachel ----
    kam = getattr(a, "kam", {}); kctx = {}
    def kontext(nr, voll):
        if (nr, voll) in kctx: return kctx[(nr, voll)]
        kp_ = FF.k_datei(objp, obj, R0, nr); K_ = json.load(open(kp_)); bild_ = glob.glob(os.path.join(R0, obj["fotos_dir"], nr + "_*"))
        if not bild_: return None
        i0 = cv2.imread(bild_[0]); i0, K_ = FD.foto_skalieren(i0, K_); kk_ = K_["kamera"]; i0, _ = FF.foto_entzerren(i0, kk_); H_, W_ = i0.shape[:2]
        R_, t_, f_, _, _ = FF.kamera_laden(K_, obj, nr, R0, W_, H_); cx_, cy_ = float(kk_.get("cx", W_ / 2)), float(kk_.get("cy", H_ / 2)); tr_ = TF.rahmen(stl, obj, kk_)
        c = {"im0": i0, "R": R_, "t": t_, "f": f_, "cx": cx_, "cy": cy_, "W": W_, "H": H_, "tr": tr_}
        if voll:
            Mw_ = ganz.copy(); Mw_.apply_translation(tr_); dv_, fid_, _ = RK.dreiecke_rastern(Mw_, R_, t_, f_, cx_, cy_, W_, H_)
            c["dv"] = dv_; c["img"], c["kante"] = schattieren(Mw_, fid_, dv_, R_)
        if len(kctx) > 5: kctx.pop(next(iter(kctx)))
        kctx[(nr, voll)] = c; return c
    def kandidaten(tn, nmax=14, smin=MIN_SICHT):
        return sorted(((v["sicht_px"], f) for f, v in formliste_teile.get(tn, {}).items() if isinstance(v, dict) and v.get("sicht_px", 0) >= max(MIN_SICHT, smin)), reverse=True)[:nmax]
    for tn in list(wahl):
        if any(k.startswith("@Fuss") for k in out.get(tn, {})): continue
        for sp, nr in kandidaten(tn, 40, 0):
            if nr in wahl[tn]: continue
            c = kontext(nr, True)
            if not c: continue
            m = teilnetz(tn).copy(); m.apply_translation(c["tr"])
            dp, _, pos = RK.dreiecke_rastern(m, c["R"], c["t"], c["f"], c["cx"], c["cy"], c["W"], c["H"])
            ziel = np.isfinite(dp) & (dp <= c["dv"] * 1.003 + 0.03); zk = ziel & (pos[..., 2] <= m.bounds[0, 2] + (m.bounds[1, 2] - m.bounds[0, 2]) / 3)
            if zk.sum() < KACHEL_MIN_PX: continue
            ybot, hpx = unterkante_px(m, c["R"], c["t"], c["f"], c["cx"], c["cy"]); kb = fuss_box(box_aus_maske(zk, c["W"], c["H"], rand=0.5), ybot, hpx, c["H"])
            if kb is None: continue
            kp = os.path.join(bilder_dir, f"{tn}_Fuss_{nr}.jpg"); bildpaar(c["im0"], c["img"], c["kante"], ziel, kb, f"{nr} [Fuss]", kp)
            out[tn]["@Fuss (" + nr + ")"] = kp; print(f"{tn}: Fuss-Nachsuche Foto {nr} ({int(zk.sum())} px)", flush=True); break
        else: print(f"{tn}: KEIN Foto mit Teilunterkante im Bild fuer die Fuss-Kachel", flush=True)
    for tn in wahl:
        kp_alt = [os.path.join(bilder_dir, x) for x in os.listdir(bilder_dir) if x.startswith(tn + "_Kontur_")]
        if kp_alt and not a.bilder_neu:
            out[tn]["@Kontur (" + os.path.basename(kp_alt[0])[:-4].split("_")[-1] + ")"] = kp_alt[0]; continue
        m0 = teilnetz(tn); v2 = m0.vertices[:, :2] - m0.vertices[:, :2].mean(0); ax = np.linalg.eigh(np.cov(v2.T) + 1e-9 * np.eye(2))[1][:, 1]
        nrm = np.array([-ax[1], ax[0]]); ctr = m0.bounds.mean(0); fr = []
        smax = max([v.get('sicht_px', 0) for v in formliste_teile.get(tn, {}).values() if isinstance(v, dict)] + [1])
        for sp, nr in kandidaten(tn, 60, 0.08 * smax):
            if nr not in kam: continue
            d = kam[nr][:2] - ctr[:2]; ang = math.degrees(math.acos(min(1.0, abs(float(d @ nrm)) / (np.linalg.norm(d) + 1e-9)))); fr.append((ang, nr))
        for ang, nr in sorted(fr)[:8]:
            c = kontext(nr, False)
            if not c: continue
            m = m0.copy(); m.apply_translation(c["tr"]); kp = os.path.join(bilder_dir, f"{tn}_Kontur_{nr}.jpg")
            r_ = kontur_kachel(tn, m, (c["im0"], c["R"], c["t"], c["f"], c["cx"], c["cy"], c["W"], c["H"]), nr, kp)
            if r_: out[tn]["@Kontur (" + nr + ")"] = r_; print(f"{tn}: Kontur Foto {nr} (Winkel zur Frontnormale {ang:.0f} Grad)", flush=True); break
    return out


OBJ_NAME = "Gebaeude"   # aus objekt.json["name"] (main), kein Objektname im Code


def pruefer(teil, paare, arbeit, modell, timeout):
    """Ein claude-Aufruf je Teil. Rueckgabe dict mit 'status' ok|ungeprueft."""
    pf = "\n".join(f"- {p}" for p in paare.values()); fotos = ", ".join(f'"{k}"' for k in paare)
    p = PROMPT.format(teil=teil, pfade=pf, fotos=fotos, objekt=OBJ_NAME)
    logp = os.path.join(arbeit, "pruefer", f"{teil}.log"); os.makedirs(os.path.dirname(logp), exist_ok=True)
    t0 = time.time()
    try:
        r = subprocess.run(["claude", "-p", p, "--model", modell, "--permission-mode", "plan"], cwd=arbeit, capture_output=True, text=True, timeout=timeout)
        out = r.stdout + ("\n[stderr]\n" + r.stderr if r.stderr else "")
    except subprocess.TimeoutExpired:
        open(logp, "w").write("ZEITLIMIT"); return {"teil": teil, "status": "ungeprueft", "grund": "Zeitlimit"}
    open(logp, "w").write(out)
    erg = None
    for m in re.finditer(r"ERGEBNIS\s*(\{)", out):
        try: erg = json.JSONDecoder().raw_decode(out[m.start(1):])[0]
        except Exception: pass
    if not isinstance(erg, dict) or "abweichungen" not in erg:
        return {"teil": teil, "status": "ungeprueft", "grund": "kein lesbares JSON (rc %s)" % r.returncode, "log": logp}
    erg["status"] = "ok"; erg["sek"] = round(time.time() - t0); erg["log"] = logp; erg["paare"] = paare
    return erg


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--teile_dir", required=True); ap.add_argument("--formliste", required=True)
    ap.add_argument("--teile", help="Komma; ohne Angabe alle Teile der Formliste"); ap.add_argument("--arbeit", default=ARBEIT_STD)
    ap.add_argument("--stl"); ap.add_argument("--fotos_je_teil", type=int, default=4); ap.add_argument("--nur_bilder", action="store_true")
    ap.add_argument("--modell", default="opus"); ap.add_argument("--parallel", type=int, default=11); ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--neu", action="store_true", help="Pruefer-Ergebnisse im Arbeitsordner nicht wiederverwenden")
    ap.add_argument("--bilder_neu", action="store_true", help="vorhandene Bildpaare neu rendern")
    ap.add_argument("--fotos", help="Foto-Kuerzel erzwingen/einschraenken (Komma)")
    a = ap.parse_args(argv)
    objp = os.path.join(R0, "modelle", a.objekt, "objekt.json"); obj = json.load(open(objp)); global OBJ_NAME; OBJ_NAME = str(obj.get("name") or a.objekt).split(" - ")[0]
    FL = json.load(open(a.formliste))
    stl = a.stl or os.path.join(R0, obj["stl"]); sk = obj.get("stl_massstab", 87) / 1000.0
    import hashlib
    sha = hashlib.sha256(open(stl, "rb").read()).hexdigest()[:16]
    if FL.get("stl_sha") != sha: print(f"WARNUNG: Formliste stl_sha {FL.get('stl_sha')} != {sha} (aktuelles Modell)", flush=True)
    os.makedirs(os.path.join(a.arbeit, "bilder"), exist_ok=True); bilder_dir = os.path.join(a.arbeit, "bilder")
    teile_pfade = {os.path.basename(p)[:-4]: p for p in glob.glob(os.path.join(a.teile_dir, "*.stl"))}
    namen = a.teile.split(",") if a.teile else sorted(FL["teile"])
    namen = [n for n in namen if n in teile_pfade and n in FL["teile"]]
    # Kamerazentren im Modellrahmen: C = -R^T t - Rahmenverschiebung (Teilnetze liegen ohne Verschiebung vor)
    kam = {}
    for nr in FL["fotos"]:
        try:
            kp = FF.k_datei(objp, obj, R0, nr); K = json.load(open(kp)); kk = K["kamera"]
            R, _ = cv2.Rodrigues(np.array(kk["rvec"])); C = -R.T @ np.array(kk["t"], float)
            kam[nr] = C - TF.rahmen(stl, obj, kk)
        except Exception: continue
    wahl = {}
    for n in namen:
        m = trimesh.load(teile_pfade[n], force="mesh"); m.apply_scale(sk)
        wahl[n] = fotowahl(n, FL["teile"][n], kam, m, a.fotos_je_teil, a.fotos.split(",") if a.fotos else None)
        print(f"{n}: Fotos {wahl[n]}", flush=True)
    t0 = time.time()
    import gpu_slot; gpu_slot.belegen("formfamilie_pruefen")
    a.kam = kam
    paare = bilder_erzeugen(a, obj, objp, teile_pfade, {n: w for n, w in wahl.items() if w}, FL["teile"], bilder_dir)
    t_bild = time.time() - t0
    erg = {"objekt": a.objekt, "stl_sha": sha, "formliste": a.formliste, "teile": {}, "sek_bilder": round(t_bild)}
    for n in namen: erg["teile"][n] = {"status": "ungeprueft", "grund": "keine Bilder"} if not paare.get(n) else {"status": "offen", "paare": paare[n]}
    if not a.nur_bilder:
        pdir = os.path.join(a.arbeit, "pruefer"); os.makedirs(pdir, exist_ok=True)
        def lauf(n):
            cache = os.path.join(pdir, n + ".json")
            if os.path.exists(cache) and not a.neu:
                try:
                    c = json.load(open(cache))
                    if c.get("paare") == paare[n] and c.get("status") == "ok" and c.get("stl_sha") == sha: return n, c, 0
                except Exception: pass
            r = pruefer(n, paare[n], a.arbeit, a.modell, a.timeout); r["stl_sha"] = sha
            if r.get("status") == "ok": json.dump(r, open(cache, "w"), ensure_ascii=False, indent=1)
            return n, r, 1
        todo = [n for n in namen if paare.get(n)]
        aufrufe = 0
        with ThreadPoolExecutor(a.parallel) as ex:
            for n, r, k in ex.map(lauf, todo):
                erg["teile"][n] = r; aufrufe += k
                print(f"{n}: {r['status']}, {len(r.get('abweichungen', []))} Abweichungen", flush=True)
        erg["claude_aufrufe"] = aufrufe
    erg["sek_gesamt"] = round(time.time() - t0)
    json.dump(erg, open(os.path.join(a.arbeit, "formfamilie.json"), "w"), ensure_ascii=False, indent=1)
    return erg


if __name__ == "__main__":
    main()
