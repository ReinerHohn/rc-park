#!/usr/bin/env python3
"""abdeckung_meldung.py - ABDECKUNGSMELDUNG NACH DER REGISTRIERUNG je Wand, Dach und Sonderstelle + Fotoauftrag + Grund je nicht eingeordnetem Foto
Verwandt: tools/abdeckung_quellen.py (Richtungen/Abstaende je Quelle), tools/seiten_luecken.py (Luecken je Seite), tools/foto_auftrag_lage.py (Fotoauftrag zur Stelle).
Vorlaeufer: keiner je Zone/Sonderstelle - Lage kommt aus Lagedatei, Fotos je Teil gemessen (27.11.).
(Spec modelle/SPEC_VOLLAUTOMATIK_FOTOS_ZU_3D.md Anforderung 1b-1d, 26.11.2026; Handyfotos Schwabentor: 97 von 241 eingeordnet, Bruecke/Treppe/Unterdurchgang/
Treppenturm fehlten im Netz und wurden nirgends gemeldet).

WAS SCHON DA WAR (nicht ersetzt): abdeckung_quellen.py (Kameras je Seite/Quelle, nur Zaehlung), abdeckung.py (Sektoren je Seitennetz), kamera_abdeckung.py
(30-Grad-Sektoren, Luecke), foto_auftrag.py (Fassadenbild-Loecher -> HTML), foto_auftrag_skizze.py (LoD2-Waende + Wolke + Standpunkte, nur Waende, keine
Sonderstellen, keine Registrierungsgruende). Hier NEU: Sonderstellen als ZONENLISTE (Konfiguration, nichts im Code), je Zone Fotos/Faecher/Tiefe, Fotoauftrag je
unbelegter Zone, Grund je nicht eingeordnetem Foto aus registrierung.json (zusatzfotos_registrieren.py).

ZONEN (Datei --zonen, JSON):  {"wand_unten_m": 0.5, "wand_oben_m": 36, "dach_oben_m": 50, "waende": "auto" | [ {name, a:[x,y], b:[x,y], normal:[x,y]} ],
  "dach": true, "sonderstellen": [ {name, form: "zylinder"|"kasten"|"unbekannt", mitte:[x,y] | null, radius_m, groesse_m:[dx,dy], z:[z0,z1], seite, hinweis, quelle} ]}
  'waende: auto' = Rechteck objekt.json rahmen_wand (u = x, v = y im Modellrahmen) mit Seitennamen aus objekt.json seiten_konvention (+x/-x/+y/-y).
  Sonderstelle ohne 'mitte' = Lage im Netz unbekannt (nie eingeordnet) -> immer 'nicht belegt' + Fotoauftrag mit Anschlussweg (kein Raten einer Lage) -
  AUSSER es gibt eine LAGEDATEI (27.11.2026, Review: Bruecke stand fest auf 'mitte: null' = Zirkelschluss): 'lage' (Pfad relativ zur Zonenliste) oder automatisch
  <Ordner der Zonenliste>/messprotokoll/*/<NAME>-LAGE*.json (lage_lesen: mitte*, achse*, laenge*, breite*, *unterkante_z*, *first_z* im Modellrahmen). Dann wird die
  Stelle als laenglicher Kasten GEMESSEN, je Teil eine Zone '<Name> <Teil>' (Seite <Himmelsrichtung> x2, Dach, Unterseite, Deck innen = nur Kameras im Kasten,
  Ende nah/fern = Zonenliste 'enden'). Eine einpassung.json neben der Lagedatei (teilmodell_spuren_einpassen.py: 'teil' + spuren.M_teil_modell) bringt die
  eingepassten Teilmodell-Kameras + Punkte automatisch dazu (auch --einpassung). Harte Regel: Zone mit 0 Fotos ist nie belegt.
JE ZONE: Zellen (ZELLE_M) mit Aussennormale; Kamera sieht eine Zelle, wenn sie vor der Kamera im Bild liegt, <= MAX_ABSTAND_M und Blick zur Normale <= BLICK_MAX_GRAD.
  fotos (neu/referenz), faecher_grad = 360 - groesste Azimutluecke der sehenden Kameras um die Zonenmitte, zellen_gesehen = Anteil Zellen mit >= MIN_FOTOS Kameras,
  tiefe = Anteil Zellen mit >= MIN_PUNKTE Punkten (Wolke/Sparse im Modellrahmen), tiefe_rel = tiefe / beste Wand.
  belegt  <=> fotos >= MIN_FOTOS und faecher >= MIN_FAECHER_GRAD und zellen_gesehen >= MIN_ZELLEN und tiefe_rel >= MIN_TIEFE_REL; 0 Fotos = 'nicht belegt', sonst 'duenn'.
SCHWELLEN (Herkunft):  MIN_FOTOS 3 = Regel "Formfamilie aus >= 3 Fotos" (CLAUDE.md); BLICK_MAX_GRAD 70 wie foto_auftrag.py; MAX_SCHRITT_GRAD 15 und MIN_TIEFE_REL 0,25 wie
  foto_auftrag_skizze.py (dort ANNAHME bzw. 1122-Wolke Sued 0,6 % / Ost 20 %); MIN_FAECHER_GRAD = 2 x MAX_SCHRITT_GRAD (ANNAHME: drei Standpunkte je Stelle);
  ANNAHME: MAX_ABSTAND_M 150 (Register BI: Nordnetz 27-150 m brauchbar), ZELLE_M 2, MIN_PUNKTE 3, MIN_ZELLEN 0,5.
VERDECKUNG: Hauptbaukoerper als Kasten (Strahltest verdeckt()); Nachbarhaeuser per SPURBELEG (seit 26.11.2026): eine Kamera zaehlt fuer eine Zone nur mit
  >= MIN_PUNKTE eigenen Sparse-Spurpunkten <= ZELLE_M an ihren gesehenen Zellen (bei Sonderstellen ohne Punkte am Hauptbaukoerper). Befund: Treppenturm 320 geometrisch,
  davon zeigten Altstadt-Strassenblicke die Hauszeile davor (Kontaktbogen). Versucht und verworfen: Voxel-Verdeckung durch Sparse-Masse (1-m-Voxel) - nahm 13 Kameras
  mit >= 10 Turmspurpunkten weg und liess die Strassenblicke stehen (Nachbarhaeuser im Sparse zu duenn). JSON 'fotos_geometrisch' = Zaehlung ohne Spurbeleg.
NICHT EINGEORDNET (Grund, Schwelle min_inlier aus registrierung.json): n_korr = 0 -> 'keine Korrespondenz'; n_korr < min_inlier -> 'zu wenige Matches';
  sonst (genug 2D-3D-Paare, PnP ohne konsistente Pose) -> 'Lage nicht berechenbar'; Foto im --bilder-Ordner ohne Eintrag -> 'nicht versucht'.
  Mit --teilmodelle (handy_teilmodell.py-Ordner + ausrichtung.json) steht je Foto zusaetzlich sein Teilmodell und ob es eingepasst ist.
FOTOAUFTRAG je nicht belegter Zone: Stelle, Grund (welche Schwelle), Standpunkte (Modell-x/y, GPS aus objekt.json rahmen, Abstand, Kompass-Blickrichtung, Neigung),
  Faecher -MIN_FAECHER/2..+MIN_FAECHER/2 um die Normale in MAX_SCHRITT_GRAD-Schritten; Abstand: Zone passt ins Bild (Bildwinkel der eigenen Kameras), >= MIN_ABSTAND_M.
  Zone ohne Lage: Anschlussweg (Startstandpunkt nur vor der konfigurierten Wand 'seite', sonst ohne Standpunkt - nie geraten; Schritte <= MAX_SCHRITT_GRAD,
  angrenzende Wand im Bild). Im Modell gilt dort "nicht belegt".
  Draufsicht im Bild: +x nach oben, +y nach links (Modellrahmen von oben).
AUFRUF: tools/py tools/abdeckung_meldung.py --objekt modelle/<obj>/objekt.json --zonen <zonen.json> --registrierung <Z>/registrierung.json --sparse <Z>/sparse_handy/0
          [--ausrichtung messprotokoll/SFM-AUSRICHTUNG-<obj>.json] [--punkte wolke.npy] [--teilmodelle <Z>/teilmodell] [--bilder <Z>/bilder] --aus <ordner>
  Ohne --punkte: Punkte des --sparse. Ausgabe <aus>/abdeckung_meldung.json, .md, .png (Draufsicht, wenn cv2 da). Nur CPU, Sekunden.
TEST: tools/test_abdeckung_meldung.py (fester Mini-Datensatz tools/testdata/abdeckung_handy_20261126_mini.json), tools/test_abdeckung_echt.py (echte Kameras +
  Spurpunkte, echte Zonenliste + Lagedatei, Treppenturm 186/320). Fotoauftrag mit Karte fuer eine Stelle mit Lagedatei: tools/foto_auftrag_lage.py.
"""
import os, sys, json, math, argparse, collections
import numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
from abdeckung_quellen import seiten_aus_konvention

MIN_FOTOS = 3; BLICK_MAX_GRAD = 70.0; MAX_SCHRITT_GRAD = 15.0; MIN_TIEFE_REL = 0.25; MIN_FAECHER_GRAD = 2 * MAX_SCHRITT_GRAD
MAX_ABSTAND_M = 150.0; ZELLE_M = 2.0; MIN_PUNKTE = 3; MIN_ZELLEN = 0.5; MIN_ABSTAND_M = 5.0; AUGE_M = 1.6; HFOV_ANNAHME = 60.0; MAX_PUNKTE = 600_000
GRUENDE = ("keine Korrespondenz", "zu wenige Matches", "Lage nicht berechenbar", "nicht versucht")


# ---------------------------------------------------------------- Zonen
def _wand_zellen(a, b, n, z0, z1):
    a, b = np.asarray(a, float), np.asarray(b, float); L = float(np.linalg.norm(b - a)); nu = max(1, int(round(L / ZELLE_M))); nz = max(1, int(round((z1 - z0) / ZELLE_M)))
    us = (np.arange(nu) + 0.5) / nu; zs = z0 + (np.arange(nz) + 0.5) * (z1 - z0) / nz
    X = np.array([[*(a + u * (b - a)), z] for u in us for z in zs]); N = np.tile([n[0], n[1], 0.0], (len(X), 1)); return X, N


def lage_finden(s, basis):
    """Lagedatei einer Sonderstelle: 'lage' (Pfad relativ zum Ordner der Zonenliste) oder automatisch <basis>/messprotokoll/*/<NAME>-LAGE*.json (NAME = Zonenname
    gross, z. B. Bruecke -> BRUECKE-LAGE.json). Kein Fund -> None (Lage bleibt unbekannt, nie geraten)."""
    if not basis: return None
    if s.get("lage"):
        p = s["lage"] if os.path.isabs(s["lage"]) else os.path.join(basis, s["lage"]); return p if os.path.isfile(p) else None
    import glob
    k = sorted(glob.glob(os.path.join(basis, "messprotokoll", "*", s["name"].upper() + "-LAGE*.json"))); return k[-1] if k else None


def _feld(d, praefixe, n=None, ohne=("utm", "quelle")):
    for k, v in d.items():
        if any(k.startswith(p) for p in praefixe) and not any(o in k for o in ohne):
            if n is None and isinstance(v, (int, float)) and not isinstance(v, bool): return float(v)
            if n and isinstance(v, list) and len(v) >= n and all(isinstance(x, (int, float)) for x in v[:n]): return [float(x) for x in v[:n]]
    return None


def rel(p):
    """Pfad relativ zur Repo-Wurzel, wenn darin (Meldungen ohne Worktree-Pfade)."""
    r = os.path.relpath(p, os.path.dirname(T)); return p if r.startswith("..") else r


def lage_lesen(pfad):
    """Lagedatei (z. B. messprotokoll/bruecke_lage_1127/BRUECKE-LAGE.json) -> dict mitte(2), achse(2, Einheitsvektor), laenge, breite, z_unten, z_oben, z_lauf|None
    im Modellrahmen. Felder per Namensanfang (mitte*, achse*, laenge*, breite*, *unterkante_z*/unten_z*, *first_z*/oben_z*/dach_z*, laufebene_z*) in der Datei selbst
    oder einem Unterobjekt; fehlt eins -> ValueError (dann Lage unbekannt). Keine Objektwerte im Code."""
    d = json.load(open(pfad)); kand = [d] + [v for v in d.values() if isinstance(v, dict)]
    for c in kand:
        m, a = _feld(c, ("mitte",), 2), _feld(c, ("achse",), 2)
        if m is None or a is None: continue
        L, B = _feld(c, ("laenge",)), _feld(c, ("breite",))
        zo = next((_feld(c, (p,)) for p in ("dach_first_z", "first_z", "oben_z", "dach_z") if _feld(c, (p,)) is not None), None)
        zu = next((_feld(c, (p,)) for p in ("deck_unterkante_z", "unterkante_z", "unten_z") if _feld(c, (p,)) is not None), None); zl = _feld(c, ("laufebene_z",))
        if zu is None: zu = zl
        fehlt = [n for n, v in (("laenge", L), ("breite", B), ("oben_z", zo), ("unten_z", zu)) if v is None]
        if fehlt: raise ValueError("fehlt " + ", ".join(fehlt))
        if not (L > 0 and B > 0 and zo > zu): raise ValueError(f"ungueltig: laenge {L}, breite {B}, z {zu}..{zo}")
        a = np.asarray(a); a = a / np.linalg.norm(a)
        return dict(mitte=m, achse=[float(a[0]), float(a[1])], laenge=L, breite=B, z_unten=zu, z_oben=zo, z_lauf=zl)
    raise ValueError("keine Felder mitte*/achse* (Modellrahmen)")


def _flaeche(p0, e1, e2, n1, n2, nrm):
    """Zellen einer Rechteckflaeche p0 + s e1 + t e2 (s,t in -1/2..1/2, Laengen n1/n2 m) mit Normale nrm."""
    a, b = max(1, int(round(n1 / ZELLE_M))), max(1, int(round(n2 / ZELLE_M))); s = (np.arange(a) + 0.5) / a - 0.5; t = (np.arange(b) + 0.5) / b - 0.5
    X = np.array([p0 + si * n1 * e1 + ti * n2 * e2 for si in s for ti in t]); return X, np.tile(nrm, (len(X), 1))


def himmel(obj, d):
    k = kompass(obj, d)
    return None if k is None else ("Nord", "Nordost", "Ost", "Suedost", "Sued", "Suedwest", "West", "Nordwest")[int(((k + 22.5) % 360) // 45)]


def lage_zonen(s, L, pfad, koerper, obj=None):
    """Sonderstelle mit Lagedatei = laenglicher Kasten (Mitte, Achse, Laenge, Breite, z_unten..z_oben) -> je TEIL eine Zone: zwei Seiten (Normale quer), Dach (+z),
    Unterseite (-z), Deck innen (Laufebene, nur von Kameras IM Kasten), zwei Enden (Ende nah = naeher am Hauptbaukoerper; Namen aus der Zonenliste 'enden')."""
    c = np.asarray(L["mitte"]); u = np.asarray(L["achse"]); q = np.array([-u[1], u[0]]); Ln, B, zu, zo = L["laenge"], L["breite"], L["z_unten"], L["z_oben"]
    zm, H = (zu + zo) / 2, zo - zu; u3, q3, z3 = np.r_[u, 0], np.r_[q, 0], np.array([0, 0, 1.0]); c3 = np.r_[c, zm]
    km = np.array([(koerper[0] + koerper[1]) / 2, (koerper[2] + koerper[3]) / 2]); nah = 1.0 if np.linalg.norm(c + u * Ln / 2 - km) < np.linalg.norm(c - u * Ln / 2 - km) else -1.0
    en = s.get("enden") or {}; n_nah, n_fern = en.get("nah", "Ende am Hauptbau"), en.get("fern", "Ende fern")
    box = dict(c=c.tolist(), u=u.tolist(), laenge=Ln, breite=B, z=[zu, zo])
    teile = [("Seite +q", c3 + q3 * B / 2, u3, z3, Ln, H, q3, q.tolist()), ("Seite -q", c3 - q3 * B / 2, u3, z3, Ln, H, -q3, (-q).tolist()),
             ("Dach", np.r_[c, zo], u3, q3, Ln, B, z3, None), ("Unterseite", np.r_[c, zu], u3, q3, Ln, B, -z3, None),
             (n_nah, c3 + nah * u3 * Ln / 2, q3, z3, B, H, nah * u3, (nah * u).tolist()), (n_fern, c3 - nah * u3 * Ln / 2, q3, z3, B, H, -nah * u3, (-nah * u).tolist())]
    if L.get("z_lauf") is not None and zu <= L["z_lauf"] < zo: teile.append(("Deck innen", np.r_[c, L["z_lauf"]], u3, q3, Ln, B, z3, None))
    out = []; u0, u1, v0, v1, _ = koerper
    for nm, p0, e1, e2, n1, n2, nrm, n2d in teile:
        if nm.startswith("Seite"): nm = "Seite " + (himmel(obj or {}, n2d) or nm[-2:])
        X, N = _flaeche(p0, e1, e2, n1, n2, nrm); innen = (X[:, 0] > u0) & (X[:, 0] < u1) & (X[:, 1] > v0) & (X[:, 1] < v1); X, N = X[~innen], N[~innen]
        out.append(dict(name=f"{s['name']} {nm}", art="sonder", gruppe=s["name"], seite=s.get("seite"), hinweis=s.get("hinweis", ""), mitte=[*p0[:2], p0[2]] if len(X) else None,
                        X=X, N=N, normal2=n2d, breite=max(n1, 2 * ZELLE_M) if n2d else max(n1, n2), hoehe=n2 if n2d else 0.0, koerper=koerper,
                        innen_box=box if nm == "Deck innen" else None, lage_datei=rel(pfad),
                        quelle=f"Lagedatei {rel(pfad)}: Mitte {L['mitte']}, Achse {L['achse']}, Laenge {Ln}, Breite {B}, z {zu}..{zo}"))
    return out


def im_kasten(C, box):
    """bool (K,): Kamera im laenglichen Kasten (Deck innen nur von dort sichtbar; Dach verdeckt von aussen)."""
    d = C[:, :2] - np.asarray(box["c"]); u = np.asarray(box["u"]); q = np.array([-u[1], u[0]])
    return (np.abs(d @ u) <= box["laenge"] / 2) & (np.abs(d @ q) <= box["breite"] / 2) & (C[:, 2] >= box["z"][0]) & (C[:, 2] <= box["z"][1])


def zonen_bauen(cfg, obj, basis=None):
    """Zonenliste [{name, art, mitte(3)|None, X(M,3), N(M,3)|None, breite, normal2|None, seite, ...}] aus Konfiguration + objekt.json (nichts objektspezifisch im Code).
    basis = Ordner der Zonenliste (Lagedateien relativ dazu / automatisch in <basis>/messprotokoll/*/)."""
    z0, z1 = float(cfg.get("wand_unten_m", 0.5)), float(cfg.get("wand_oben_m", obj.get("hoehe_m", 20.0)))
    waende = cfg.get("waende", "auto"); out = []; box = None
    if waende == "auto":
        rw = obj.get("rahmen_wand") or {}; konv = seiten_aus_konvention(obj)
        if not rw or len(konv) < 4: raise ValueError("waende 'auto' braucht objekt.json rahmen_wand und seiten_konvention (+x/-x/+y/-y)")
        u0, u1, v0, v1 = (float(rw[k]) for k in ("u0", "u1", "v0", "v1")); box = (u0, u1, v0, v1)
        waende = [dict(name=konv["+x"], a=[u1, v0], b=[u1, v1], normal=[1, 0]), dict(name=konv["-x"], a=[u0, v0], b=[u0, v1], normal=[-1, 0]),
                  dict(name=konv["+y"], a=[u0, v1], b=[u1, v1], normal=[0, 1]), dict(name=konv["-y"], a=[u0, v0], b=[u1, v0], normal=[0, -1])]
    for w in waende:
        X, N = _wand_zellen(w["a"], w["b"], w["normal"], z0, z1); m = (np.asarray(w["a"], float) + np.asarray(w["b"], float)) / 2
        out.append(dict(name=w["name"], art="wand", seite=w["name"], mitte=[*m, (z0 + z1) / 2], X=X, N=N, normal2=list(map(float, w["normal"])),
                        breite=float(np.linalg.norm(np.subtract(w["b"], w["a"]))), hoehe=z1 - z0, quelle=w.get("quelle", "objekt.json rahmen_wand")))
    if box is None:
        A = np.array([p for w in waende for p in (w["a"], w["b"])], float); box = (A[:, 0].min(), A[:, 0].max(), A[:, 1].min(), A[:, 1].max())
    if cfg.get("dach", True):
        zo = float(cfg.get("dach_oben_m", obj.get("hoehe_m", z1 + 5))); u0, u1, v0, v1 = box; cx, cy, hx, hy, H = (u0 + u1) / 2, (v0 + v1) / 2, (u1 - u0) / 2, (v1 - v0) / 2, zo - z1
        xs = np.linspace(u0, u1, max(2, int((u1 - u0) / ZELLE_M) + 1)); ys = np.linspace(v0, v1, max(2, int((v1 - v0) / ZELLE_M) + 1)); X, N = [], []
        for x in xs:
            for y in ys:
                if cfg.get("dach_form", "zelt") == "flach": X.append([x, y, z1]); N.append([0, 0, 1.0]); continue
                rx, ry = (x - cx) / hx, (y - cy) / hy; r = max(abs(rx), abs(ry))          # Zeltdach: vier Dreiecke von der Traufe (r = 1) zur Spitze (r = 0)
                n = np.array([math.copysign(H / hx, rx), 0, 1.0]) if abs(rx) >= abs(ry) else np.array([0, math.copysign(H / hy, ry), 1.0])
                X.append([x, y, z1 + H * (1 - r)]); N.append(n / np.linalg.norm(n))
        out.append(dict(name="Dach", art="dach", seite=None, mitte=[cx, cy, z1 + H / 3], X=np.array(X), N=np.array(N), normal2=None, breite=max(u1 - u0, v1 - v0), hoehe=H,
                        quelle=f"Rechteck der Waende, {cfg.get('dach_form', 'zelt')}dach wand_oben_m..dach_oben_m (Form = ANNAHME aus der Konfiguration)"))
    for z in out: z["koerper"] = (*box, z1)
    for s in cfg.get("sonderstellen", []):
        if s.get("mitte") is None:
            pf = lage_finden(s, basis); L = None
            if pf:
                try: L = lage_lesen(pf)
                except ValueError as ex: s = dict(s, quelle=f"{s.get('quelle', '')}; Lagedatei {pf} unbrauchbar: {ex}")
            if L:
                out += lage_zonen(s, L, pf, (*box, z1), obj); continue
        e = dict(name=s["name"], art="sonder", seite=s.get("seite"), hinweis=s.get("hinweis", ""), quelle=s.get("quelle", ""), mitte=None, X=np.zeros((0, 3)), N=None, normal2=None)
        zz = s.get("z", [z0, z1])
        if s.get("mitte") is not None and s.get("form", "kasten") != "unbekannt":
            c = np.asarray(s["mitte"][:2], float); e["mitte"] = [*c, (zz[0] + zz[1]) / 2]; e["hoehe"] = zz[1] - zz[0]
            zs = np.arange(zz[0] + ZELLE_M / 2, zz[1], ZELLE_M) if zz[1] - zz[0] > ZELLE_M else np.array([(zz[0] + zz[1]) / 2])
            if s.get("form") == "zylinder":
                r = float(s["radius_m"]); na = max(8, int(round(2 * math.pi * r / ZELLE_M))); ang = 2 * math.pi * (np.arange(na) + 0.5) / na; e["breite"] = 2 * r
                X = np.array([[c[0] + r * math.cos(t), c[1] + r * math.sin(t), z] for t in ang for z in zs]); N = np.array([[math.cos(t), math.sin(t), 0.0] for t in ang for z in zs])
            else:
                dx, dy = (float(v) for v in s.get("groesse_m", [ZELLE_M, ZELLE_M])); e["breite"] = max(dx, dy); X, N = [], []
                for (nx, ny, hx, hy) in ((1, 0, 0, dy), (-1, 0, 0, dy), (0, 1, dx, 0), (0, -1, dx, 0)):
                    p = c + np.array([nx * dx / 2, ny * dy / 2]); a = p - np.array([hx, hy]) / 2; b = p + np.array([hx, hy]) / 2; Xi, Ni = _wand_zellen(a, b, (nx, ny), zz[0], zz[1])
                    X.append(Xi); N.append(Ni)
                X, N = np.vstack(X), np.vstack(N)
            # Zellen IM Hauptbaukoerper sind verdeckt (z. B. Turmseite des Treppenturms) - nur freie Zellen zaehlen
            u0, u1, v0, v1 = box; e["koerper"] = (*box, z1); innen = (X[:, 0] > u0) & (X[:, 0] < u1) & (X[:, 1] > v0) & (X[:, 1] < v1); e["X"], e["N"] = X[~innen], N[~innen]
            if s.get("seite"):
                w = next((z for z in out if z["art"] == "wand" and z["name"] == s["seite"]), None); e["normal2"] = w["normal2"] if w else None
        out.append(e)
    return out


# ---------------------------------------------------------------- Messung
def sicht(kams, X, N, koerper=None):
    """bool (K, M): Kamera k sieht Zelle m (vor der Kamera, im Bild, Abstand, Blick zur Normale)."""
    if not len(kams) or not len(X): return np.zeros((len(kams), len(X)), bool)
    C = np.array([k["C"] for k in kams]); R = np.array([k["R"] for k in kams]); f = np.array([k["f"] for k in kams]); w = np.array([k["w"] for k in kams]); h = np.array([k["h"] for k in kams])
    D = X[None, :, :] - C[:, None, :]; v = np.einsum("kij,kmj->kmi", R, D); z = v[..., 2]; zs = np.where(z > 0.1, z, 1.0)
    u = f[:, None] * v[..., 0] / zs + w[:, None] / 2; q = f[:, None] * v[..., 1] / zs + h[:, None] / 2; dist = np.linalg.norm(D, axis=2)
    ok = (z > 0.1) & (u >= 0) & (u <= w[:, None]) & (q >= 0) & (q <= h[:, None]) & (dist <= MAX_ABSTAND_M)
    if N is not None: ok &= np.einsum("mj,kmj->km", N, -D) / np.maximum(dist, 1e-6) >= math.cos(math.radians(BLICK_MAX_GRAD))
    if koerper is not None: ok &= ~verdeckt(C, X, koerper)
    return ok


def verdeckt(C, X, koerper, rand=0.3):
    """bool (K, M): Strecke Kamera -> Zelle (endet rand m vor der Zelle) schneidet den Hauptbaukoerper (Kasten u0..u1, v0..v1, 0..z_oben). Nur dieser Kasten verdeckt (ANNAHME)."""
    u0, u1, v0, v1, zt = koerper; lo = np.array([u0, v0, -1e3]); hi = np.array([u1, v1, zt])
    D = X[None, :, :] - C[:, None, :]; L = np.linalg.norm(D, axis=2); tmax = np.clip(1 - rand / np.maximum(L, 1e-6), 0, 1)
    with np.errstate(divide="ignore", invalid="ignore"):
        inv = 1.0 / np.where(np.abs(D) < 1e-12, 1e-12, D); t1 = (lo - C[:, None, :]) * inv; t2 = (hi - C[:, None, :]) * inv
    tn = np.minimum(t1, t2).max(axis=2); tf = np.maximum(t1, t2).min(axis=2); return (tn <= tf) & (tf >= 0) & (tn <= tmax)


def spurbeleg(kams, S, X, art, koerper=None, kante=0.5):
    """bool (K, M): S nur fuer Kameras behalten, die auf den gesehenen Zellen der Zone >= MIN_PUNKTE eigene Sparse-Beobachtungen haben (kam['beob'] = Weltpunkte
    ihrer Spuren im Modellrahmen; Punkt <= ZELLE_M von einer gesehenen Zelle). Grund (26.11.2026, Kontaktbogen): Strassenblicke der Altstadt 'sahen' den Treppenturm
    geometrisch, obwohl die Hauszeile davor steht; Nachbarhaeuser sind nicht als Koerper bekannt, die Spuren der Kamera aber schon. Bei Sonderstellen zaehlen
    Punkte am Hauptbaukoerper (Kasten + kante m) nicht (Westwandpunkte direkt neben dem Turm). Kamera ohne 'beob' bleibt ungefiltert."""
    S = S.copy()
    for k in np.nonzero(S.any(axis=1))[0]:
        B = kams[k].get("beob")
        if B is None: continue
        B = np.asarray(B, float).reshape(-1, 3)
        if art == "sonder" and koerper is not None and len(B):
            u0, u1, v0, v1, zt = koerper; B = B[~((B[:, 0] > u0 - kante) & (B[:, 0] < u1 + kante) & (B[:, 1] > v0 - kante) & (B[:, 1] < v1 + kante) & (B[:, 2] < zt + kante))]
        Xs = X[S[k]]; lo, hi = Xs.min(0) - ZELLE_M, Xs.max(0) + ZELLE_M; B = B[np.all((B >= lo) & (B <= hi), axis=1)]; n = 0
        for a in range(0, len(B), 4000): n += int((np.linalg.norm(B[a:a + 4000, None, :] - Xs[None], axis=2).min(axis=1) <= ZELLE_M).sum())
        if n < MIN_PUNKTE: S[k] = False
    return S


def faecher(C, mitte):
    if len(C) < 2: return 0.0
    az = np.sort(np.degrees(np.arctan2(C[:, 1] - mitte[1], C[:, 0] - mitte[0])) % 360); gaps = np.diff(np.r_[az, az[0] + 360]); return float(360 - gaps.max())


def tiefe(P, X):
    if not len(X) or P is None or not len(P): return 0.0
    P = P[np.all((P >= X.min(0) - ZELLE_M) & (P <= X.max(0) + ZELLE_M), axis=1)]; n = 0      # Vorfilter Huelle (Geschwindigkeit, gleiches Ergebnis)
    for x in X: n += int(np.count_nonzero(np.all(np.abs(P - x) <= ZELLE_M / 2, axis=1)) >= MIN_PUNKTE)
    return n / len(X)


def grund(e, min_inlier):
    if e is None: return "nicht versucht"
    nk = int(e.get("n_korr") or 0)
    if nk == 0: return "keine Korrespondenz"
    if nk < min_inlier: return "zu wenige Matches"
    return "Lage nicht berechenbar"


# ---------------------------------------------------------------- Rahmen / Fotoauftrag
def kompass(obj, d):
    r = obj.get("rahmen") or {}
    if "xhat_utm" not in r: return None
    E, Nn = d[0] * np.array(r["xhat_utm"]) + d[1] * np.array(r["yhat_utm"]); return round(float(math.degrees(math.atan2(E, Nn)) % 360), 0)


def gps(obj, p):
    r = obj.get("rahmen") or {}
    if "mitte_utm" not in r: return None
    e, n = np.array(r["mitte_utm"]) + p[0] * np.array(r["xhat_utm"]) + p[1] * np.array(r["yhat_utm"])
    try:
        from seiten_luecken import utm32_nach_geo
        la, lo = utm32_nach_geo(float(e), float(n)); return [round(la, 6), round(lo, 6)]
    except Exception: return None


def standpunkte(z, obj, hfov):
    """Faecher um die Zonennormale; Abstand: Breite und Hoehe der Zone im Bild (Hochformat kurze Seite ~ 0,75 x hfov, ANNAHME 4:3)."""
    m = np.asarray(z["mitte"], float); g = max(z.get("breite", ZELLE_M) / 2 / math.tan(math.radians(hfov) / 2), z.get("hoehe", ZELLE_M) / 2 / math.tan(math.radians(0.75 * hfov) / 2))
    d = max(MIN_ABSTAND_M, g); n2 = z.get("normal2"); out = []
    if n2 is None: richt = [0.0, 90.0, 180.0, 270.0]; basis = 0.0; d = max(d, (m[2] - AUGE_M) / math.tan(math.radians(45)))   # Dach / ohne Normale: rundum, Neigung <= 45 Grad
    else: basis = math.degrees(math.atan2(n2[1], n2[0])); k = int(MIN_FAECHER_GRAD / MAX_SCHRITT_GRAD); richt = [basis + MAX_SCHRITT_GRAD * (i - k / 2) for i in range(k + 1)]
    for i, a in enumerate(richt):
        p = m[:2] + d * np.array([math.cos(math.radians(a)), math.sin(math.radians(a))]); blick = m[:2] - p
        out.append(dict(nr=i + 1, x=round(float(p[0]), 1), y=round(float(p[1]), 1), abstand_m=round(d, 1), gps=gps(obj, p), blick_kompass_grad=kompass(obj, blick),
                        blick_modell_grad=round(float(math.degrees(math.atan2(blick[1], blick[0])) % 360), 0),
                        neigung_grad=round(float(math.degrees(math.atan2(m[2] - AUGE_M, d))), 0)))
    return out


def melden(obj, cfg, kams, neu, reg, P=None, teil=None, bilder=None, spur=True, basis=None, eingepasst=()):
    """kams: [{name, C(3), R(3x3) Welt->Kamera im Modellrahmen, f, w, h}] aller eingeordneten Kameras (Referenz + neu); neu: Namen der neuen eingeordneten Fotos;
    reg: registrierung.json (dict); P: Punkte (n,3) Modellrahmen; teil: {foto: (teilmodell, status)}; bilder: Fotonamen des Satzes (None = reg['bilder'])."""
    zonen = zonen_bauen(cfg, obj, basis); neu = set(neu); min_inl = int(reg.get("min_inlier", 30))
    if P is not None and len(P) > MAX_PUNKTE: P = P[np.random.default_rng(0).choice(len(P), MAX_PUNKTE, replace=False)]
    hf = [math.degrees(2 * math.atan(k["w"] / 2 / k["f"])) for k in kams if k["name"] in neu]; hfov = float(np.median(hf)) if hf else HFOV_ANNAHME
    erg = []
    for z in zonen:
        S = sicht(kams, z["X"], z["N"], z.get("koerper"))
        if z.get("innen_box") and len(kams): S &= im_kasten(np.array([k["C"] for k in kams]), z["innen_box"])[:, None]
        geo = int(S.any(axis=1).sum())
        if spur: S = spurbeleg(kams, S, z["X"], z["art"], z.get("koerper"))
        seh = S.any(axis=1); Cs = np.array([k["C"] for k, s in zip(kams, seh) if s]).reshape(-1, 3)
        nn = sum(1 for k, s in zip(kams, seh) if s and k["name"] in neu); e = dict(name=z["name"], art=z["art"], seite=z.get("seite"), lage_bekannt=z["mitte"] is not None,
            fotos=int(seh.sum()), fotos_neu=nn, fotos_referenz=int(seh.sum()) - nn, fotos_geometrisch=geo, zellen=len(z["X"]),
            faecher_grad=round(faecher(Cs, z["mitte"]), 0) if z["mitte"] is not None else 0.0,
            zellen_gesehen=round(float((S.sum(axis=0) >= MIN_FOTOS).mean()), 3) if len(z["X"]) else 0.0, tiefe=round(tiefe(P, z["X"]), 3), quelle=z.get("quelle", ""))
        if len(z["X"]):        # Luecke: Zellen mit < MIN_FOTOS Kameras (Ort fuer gezielte Standpunkte)
            lu = z["X"][S.sum(axis=0) < MIN_FOTOS]; e["zellen_luecke"] = np.round(lu, 1).tolist()[:400]
        if len(Cs): dd = np.linalg.norm(Cs[:, :2] - np.asarray(z["mitte"][:2]), axis=1); e["abstand_median_m"] = round(float(np.median(dd)), 1)
        if z.get("hinweis"): e["hinweis"] = z["hinweis"]
        if z.get("gruppe") and z.get("normal2") is not None: e["normal2"] = [round(float(v), 4) for v in z["normal2"]]
        for k_ in ("gruppe", "lage_datei"):
            if z.get(k_): e[k_] = z[k_]
        erg.append((z, e))
    tmax = max([e["tiefe"] for z, e in erg if z["art"] == "wand"] + [1e-9])
    auftraege = []
    for z, e in erg:
        e["tiefe_rel"] = round(e["tiefe"] / tmax, 3); fehlt = []
        if not e["lage_bekannt"]: fehlt.append("Lage im Netz unbekannt (kein eingeordnetes Foto zeigt die Stelle)")
        if e["fotos"] == 0: fehlt.append("0 Fotos")                                     # harte Regel: ohne Foto nie belegt (unabhaengig von Schwellen)
        elif e["fotos"] < MIN_FOTOS: fehlt.append(f"{e['fotos']} Fotos < {MIN_FOTOS}")
        if e["lage_bekannt"] and e["faecher_grad"] < MIN_FAECHER_GRAD: fehlt.append(f"Blickwinkelfaecher {e['faecher_grad']:.0f} < {MIN_FAECHER_GRAD:.0f} Grad")
        if e["lage_bekannt"] and e["zellen_gesehen"] < MIN_ZELLEN: fehlt.append(f"nur {100 * e['zellen_gesehen']:.0f} % der Flaeche von >= {MIN_FOTOS} Fotos gesehen (< {100 * MIN_ZELLEN:.0f} %)")
        if e["tiefe_rel"] < MIN_TIEFE_REL: fehlt.append(f"Tiefe {e['tiefe_rel']:.2f} der besten Wand < {MIN_TIEFE_REL}")
        e["status"] = "belegt" if not fehlt else ("nicht belegt" if e["fotos"] == 0 or not e["lage_bekannt"] else "duenn"); e["fehlt"] = fehlt
        if not fehlt: continue
        a = dict(stelle=z["name"], art=z["art"], status=e["status"], grund="; ".join(fehlt), im_modell="nicht belegt")
        if e["lage_bekannt"]: a["standpunkte"] = standpunkte(z, obj, hfov); a["anweisung"] = (f"je Standpunkt 1 Foto quer + 1 hoch, feste Linse, kein Zoom; Stelle formatfuellend, "
                                                                                       f"Blickwinkel zwischen Nachbarstandpunkten <= {MAX_SCHRITT_GRAD:.0f} Grad")
        else:
            w = next((zz for zz, ee in erg if zz["art"] == "wand" and zz["name"] == z.get("seite")), None)     # Anschlusswand nur aus der Konfiguration, nie geraten
            a["standpunkte"] = standpunkte(w, obj, hfov)[1:2] if w else []
            a["anweisung"] = ((f"Lage unbekannt - Anschlussweg: vor der Wand {w['name']} beginnen (Standpunkt unten), " if w else
                               "Lage unbekannt, Anschlusswand nicht konfiguriert - Anschlussweg: an der naechsten eingeordneten Wand beginnen (Foto mit Wand UND Weg zur Stelle), ")
                              + f"dann in Schritten <= {MAX_SCHRITT_GRAD:.0f} Grad Blickwinkel / ~2 m zur Stelle '{z['name']}' gehen, dort >= {MIN_FOTOS} Fotos aus "
                              f"{MIN_FAECHER_GRAD:.0f} Grad Faecher; jedes Foto ueberlappt das vorige um >= 2/3. {z.get('hinweis', '')}").strip()
        auftraege.append(a)
    # ---- nicht eingeordnete Fotos mit Grund
    rb = reg.get("bilder", {}); namen = sorted(set(bilder) if bilder is not None else set(rb)); nicht = []; n_ein = 0; eingepasst = set(eingepasst)
    for n in namen:
        r = rb.get(n)
        if r is not None and r.get("status") == "registriert": continue
        if n in eingepasst: n_ein += 1; continue                                       # ueber ein eingepasstes Teilmodell im Modellrahmen
        g = grund(r, min_inl); x = dict(foto=n, grund=g, status_registrierung=(r or {}).get("status"), n_korr=(r or {}).get("n_korr"), inlier=(r or {}).get("inlier"),
                                         referenzbilder=(r or {}).get("referenzbilder"))
        if teil and n in teil: x["teilmodell"], x["teilmodell_status"] = teil[n]
        nicht.append(x)
    zaehl = collections.Counter(x["grund"] for x in nicht)
    return dict(fotos=len(namen), eingeordnet=len(namen) - len(nicht), davon_ueber_einpassung=n_ein, nicht_eingeordnet=len(nicht), gruende={g: zaehl.get(g, 0) for g in GRUENDE},
                min_inlier=min_inl, bildwinkel_grad=round(hfov, 1), zonen=[e for z, e in erg], fotoauftrag=auftraege, nicht_eingeordnete_fotos=nicht,
                schwellen=dict(MIN_FOTOS=MIN_FOTOS, MIN_FAECHER_GRAD=MIN_FAECHER_GRAD, MIN_ZELLEN=MIN_ZELLEN, MIN_TIEFE_REL=MIN_TIEFE_REL, BLICK_MAX_GRAD=BLICK_MAX_GRAD,
                               MAX_ABSTAND_M=MAX_ABSTAND_M, ZELLE_M=ZELLE_M, MIN_PUNKTE=MIN_PUNKTE, herkunft="siehe Kopf abdeckung_meldung.py (ANNAHME gekennzeichnet)")), zonen


# ---------------------------------------------------------------- Ausgabe
def markdown(m):
    L = [f"# Abdeckungsmeldung", "", f"{m['eingeordnet']} von {m['fotos']} Fotos eingeordnet; nicht eingeordnet {m['nicht_eingeordnet']}: " +
         ", ".join(f"{g} {n}" for g, n in m["gruende"].items() if n), "", "## Zonen"]
    for e in m["zonen"]:
        L.append(f"- **{e['name']}** ({e['art']}): {e['status']} - {e['fotos']} Fotos (neu {e['fotos_neu']}), Faecher {e['faecher_grad']:.0f} Grad, "
                 f"gesehen {100 * e['zellen_gesehen']:.0f} %, Tiefe {100 * e['tiefe']:.0f} % (rel {e['tiefe_rel']:.2f})" + (f"; fehlt: {'; '.join(e['fehlt'])}" if e["fehlt"] else ""))
    L += ["", "## Fotoauftrag (statt Erfinden; im Modell dort 'nicht belegt')"]
    for i, a in enumerate(m["fotoauftrag"], 1):
        L.append(f"{i}. **{a['stelle']}** - {a['grund']}"); L.append(f"   {a['anweisung']}")
        for s in a["standpunkte"]:
            L.append(f"   - Standpunkt {s['nr']}: x {s['x']} / y {s['y']} m, {s['abstand_m']} m entfernt, Blick Kompass {s['blick_kompass_grad']} Grad, Handy {s['neigung_grad']} Grad nach oben"
                     + (f", GPS {s['gps'][0]}, {s['gps'][1]}" if s.get("gps") else ""))
    L += ["", "## Nicht eingeordnete Fotos (Grund)"]
    for x in m["nicht_eingeordnete_fotos"]:
        L.append(f"- {x['foto']}: {x['grund']} (n_korr {x['n_korr']}, inlier {x['inlier']})" + (f", Teilmodell {x['teilmodell']} {x['teilmodell_status']}" if x.get("teilmodell") is not None else ""))
    return "\n".join(L) + "\n"


def bild(pfad, m, zonen, kams, neu):
    try: import cv2
    except Exception: return None
    A = np.vstack([z["X"][:, :2] for z in zonen if len(z["X"])] + [np.array([[s["x"], s["y"]] for a in m["fotoauftrag"] for s in a["standpunkte"]]).reshape(-1, 2)])
    lo, hi = A.min(0) - 25, A.max(0) + 25      # Ausschnitt Zonen + Standpunkte + 25 m, ferne Kameras fallen heraus
    S = 900 / max(hi - lo); W, H = int((hi - lo)[1] * S) + 20, int((hi - lo)[0] * S) + 20
    img = np.full((H + 30 * (len(m["fotoauftrag"]) + 2), max(W, 700), 3), 255, np.uint8)
    px = lambda p: (int((hi[1] - p[1]) * S) + 10, int((hi[0] - p[0]) * S) + 10)      # Draufsicht: +x nach oben, +y nach links (Rahmen rechtshaendig)
    farbe = {"belegt": (60, 140, 46), "duenn": (0, 168, 224), "nicht belegt": (28, 40, 208)}; st = {e["name"]: e["status"] for e in m["zonen"]}
    for k in kams: cv2.circle(img, px(k["C"]), 2, (200, 80, 0) if k["name"] in neu else (180, 180, 180), -1)
    for z in zonen:
        for x in z["X"]: cv2.circle(img, px(x), 3, farbe[st[z["name"]]], -1)
        if z["mitte"] is not None: cv2.putText(img, z["name"], px(z["mitte"]), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)
    for i, a in enumerate(m["fotoauftrag"], 1):
        for s in a["standpunkte"]:
            p = px((s["x"], s["y"])); cv2.circle(img, p, 7, (28, 40, 208), 2); cv2.putText(img, f"{i}.{s['nr']}", (p[0] + 8, p[1]), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (28, 40, 208), 1)
        cv2.putText(img, f"{i}. {a['stelle']}: {a['grund']}"[:110], (10, H + 30 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)
    cv2.putText(img, f"gruen belegt / gelb duenn / rot nicht belegt; blau = neue Fotos; {m['eingeordnet']}/{m['fotos']} eingeordnet", (10, H + 30 * (len(m["fotoauftrag"]) + 1)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)
    cv2.imwrite(pfad, img); return pfad


def rodrigues(r):
    r = np.asarray(r, float); th = np.linalg.norm(r)
    if th < 1e-12: return np.eye(3)
    k = r / th; K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]]); return np.eye(3) + math.sin(th) * K + (1 - math.cos(th)) * K @ K


def laden_sparse(sparse, ausrichtung=None, M=None):
    """pycolmap-Rekonstruktion -> Kameras + Punkte im Modellrahmen (X_sfm = s R X_modell + t laut SFM-AUSRICHTUNG; ohne Datei: Sparse = Modellrahmen).
    M (4x4, X_modell = M X_teil, z. B. einpassung.json spuren.M_teil_modell von teilmodell_spuren_einpassen.py) statt ausrichtung."""
    import pycolmap
    rec = pycolmap.Reconstruction(sparse); s, Ra, t = 1.0, np.eye(3), np.zeros(3)
    if ausrichtung:
        tr = json.load(open(ausrichtung))["transformation"]; s, Ra, t = float(tr["s"]), rodrigues(tr["rvec"]), np.asarray(tr["t"], float)
    if M is not None:      # X_m = sm Rm X_t + tm  <=>  X_t = (1/sm) Rm^T (X_m - tm): gleiche Form wie oben mit s = 1/sm, Ra = Rm^T, t = -(1/sm) Rm^T tm
        M = np.asarray(M, float); sm = float(np.cbrt(np.linalg.det(M[:3, :3]))); Rm = M[:3, :3] / sm; s, Ra, t = 1 / sm, Rm.T, -(Rm.T @ M[:3, 3]) / sm
    kams = []
    for im in rec.images.values():
        if not im.has_pose: continue
        cam = rec.cameras[im.camera_id]; Rc = np.asarray(im.cam_from_world().rotation.matrix()); Cs = np.asarray(im.projection_center())
        ids = [p.point3D_id for p in im.points2D if p.has_point3D()]
        kams.append(dict(name=im.name, C=Ra.T @ (Cs - t) / s, R=Rc @ Ra, f=float(cam.params[0]), w=float(cam.width), h=float(cam.height), beob=ids))
    pid = list(rec.points3D.keys()); P = np.array([rec.points3D[i].xyz for i in pid]).reshape(-1, 3); P = (Ra.T @ (P - t).T).T / s; idx = {i: j for j, i in enumerate(pid)}
    for k in kams: k["beob"] = P[[idx[i] for i in k["beob"] if i in idx]].astype(np.float32)     # Spurpunkte je Kamera fuer spurbeleg()
    return kams, P


def laden_einpassung(pfad):
    """einpassung.json (tools/teilmodell_spuren_einpassen.py): 'teil' = Rekonstruktion im Teilrahmen, spuren.M_teil_modell = Sim3 in Modellmeter -> (kams, P)."""
    e = json.load(open(pfad)); M = (e.get("spuren") or {}).get("M_teil_modell") or e.get("M_teil_modell")
    if M is None or not os.path.isfile(os.path.join(e.get("teil", ""), "images.bin")): raise ValueError(f"{pfad}: 'teil' oder M_teil_modell fehlt")
    return laden_sparse(e["teil"], M=M)


def punkte_laden(p):
    """Punkte (n,3) aus .npy oder binaerem PLY (x,y,z float zuerst), auf MAX_PUNKTE ausgeduennt."""
    if p.endswith(".npy"): P = np.load(p, mmap_mode="r"); return np.asarray(P[:: max(1, len(P) // MAX_PUNKTE)])[:, :3]
    with open(p, "rb") as f:
        kopf = b""
        while not kopf.endswith(b"end_header\n"): kopf += f.readline()
        k = kopf.decode("latin1").split("\n"); n = int(next(x for x in k if x.startswith("element vertex")).split()[2]); typ = {"float": "f4", "double": "f8", "uchar": "u1", "int": "i4", "uint": "u4", "short": "i2", "ushort": "u2"}
        dt = np.dtype([(x.split()[2], "<" + typ[x.split()[1]]) for x in k if x.startswith("property")]); off = f.tell()
    A = np.memmap(p, dt, "r", off, (n,)); A = A[:: max(1, n // MAX_PUNKTE)]; return np.stack([A["x"], A["y"], A["z"]], 1).astype(np.float64)


def laden_teilmodelle(d):
    import pycolmap
    st = json.load(open(os.path.join(d, "ausrichtung.json"))) if os.path.isfile(os.path.join(d, "ausrichtung.json")) else {}; out = {}
    for n in sorted(os.listdir(d)):
        p = os.path.join(d, n)
        if not n.isdigit() or not os.path.isfile(os.path.join(p, "images.bin")): continue
        for im in pycolmap.Reconstruction(p).images.values(): out[im.name] = (int(n), (st.get(n) or {}).get("status", "ohne Ausrichtung"))
    return out


def einpassungen_finden(cfg, basis, explizit=()):
    """einpassung.json neben jeder gefundenen Lagedatei (gleicher messprotokoll-Ordner) + explizite --einpassung; nur existierende, ohne Doppel."""
    out = list(explizit)
    for s in cfg.get("sonderstellen", []):
        pf = lage_finden(s, basis) if s.get("mitte") is None else None
        if pf and os.path.isfile(os.path.join(os.path.dirname(pf), "einpassung.json")): out.append(os.path.join(os.path.dirname(pf), "einpassung.json"))
    return list(dict.fromkeys(os.path.abspath(x) for x in out if os.path.isfile(x)))


def kameras_vereinen(haupt, zusatz):
    """Kameras nach Name vereinen; eingepasste Teilmodell-Kameras ersetzen gleichnamige (je Foto genau eine Pose)."""
    d = {k["name"]: k for k in haupt}
    for k in zusatz: d[k["name"]] = k
    return list(d.values())


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0]); ap.add_argument("--objekt", required=True); ap.add_argument("--zonen", required=True)
    ap.add_argument("--registrierung", required=True); ap.add_argument("--sparse", required=True); ap.add_argument("--ausrichtung"); ap.add_argument("--punkte", action="append", default=[])
    ap.add_argument("--einpassung", action="append", default=[], help="einpassung.json eines eingepassten Teilmodells (zusaetzliche Kameras); neben Lagedateien automatisch")
    ap.add_argument("--teilmodelle"); ap.add_argument("--bilder"); ap.add_argument("--aus", required=True); a = ap.parse_args(argv)
    obj = json.load(open(a.objekt)); cfg = json.load(open(a.zonen)); reg = json.load(open(a.registrierung)); kams, P = laden_sparse(a.sparse, a.ausrichtung)
    ein_namen = set(); basis = os.path.dirname(os.path.abspath(a.zonen)); neu = [n for n, v in reg.get("bilder", {}).items() if v.get("status") == "registriert"]; Ps = [P]; quellen = []
    for ep in einpassungen_finden(cfg, basis, a.einpassung):
        try: kz, Pz = laden_einpassung(ep)
        except Exception as ex: print(f"WARNUNG Einpassung {ep} nicht geladen: {ex}"); quellen.append(dict(einpassung=ep, fehler=str(ex))); continue
        kams = kameras_vereinen(kams, kz); ein_namen |= {k["name"] for k in kz}; neu += [k["name"] for k in kz]; Ps.append(Pz); quellen.append(dict(einpassung=rel(ep), kameras=len(kz), punkte=len(Pz)))
    if a.punkte: Ps = [punkte_laden(p) for p in a.punkte]
    P = np.vstack([np.asarray(x, float).reshape(-1, 3) for x in Ps])
    bilder = sorted(f for f in os.listdir(a.bilder) if f.lower().endswith((".jpg", ".jpeg", ".png"))) if a.bilder else None
    m, zonen = melden(obj, cfg, kams, sorted(set(neu)), reg, P, laden_teilmodelle(a.teilmodelle) if a.teilmodelle else None, bilder, basis=basis, eingepasst=ein_namen)
    m["kamera_quellen"] = [dict(sparse=a.sparse, ausrichtung=a.ausrichtung)] + quellen; m["punkte_quellen"] = a.punkte or "Sparse (Haupt + Einpassungen)"
    os.makedirs(a.aus, exist_ok=True); j = os.path.join(a.aus, "abdeckung_meldung.json"); json.dump(m, open(j, "w"), indent=1, ensure_ascii=False)
    open(os.path.join(a.aus, "abdeckung_meldung.md"), "w").write(markdown(m)); b = bild(os.path.join(a.aus, "abdeckung_meldung.png"), m, zonen, kams, set(neu))
    print(f"{m['eingeordnet']}/{m['fotos']} eingeordnet; Gruende {m['gruende']}; Kameras {len(kams)} ({len(quellen)} Einpassungen)")
    for e in m["zonen"]: print(f"  {e['name']:24s} {e['status']:12s} Fotos {e['fotos']:4d} (neu {e['fotos_neu']:3d}, geo {e['fotos_geometrisch']:4d}) Faecher {e['faecher_grad']:5.0f} gesehen {e['zellen_gesehen']:.2f} Tiefe_rel {e['tiefe_rel']:.2f}")
    print("FOTOAUFTRAG: " + ", ".join(x["stelle"] for x in m["fotoauftrag"])); print(f"-> {j}" + (f", {b}" if b else "")); return 0


if __name__ == "__main__": sys.exit(main())
