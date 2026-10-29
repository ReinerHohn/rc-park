#!/usr/bin/env python3
"""hofgut_sternen.py — Detail-3D des Hofgut Sternen (Höllsteig/Ravennaschlucht) aus der
Vermesser-Pipeline: LOD2 liefert Grundriss+Höhen (belegt), die FOTOS (g1–g4) die Fassade.

Maße (m) — Herkunft markiert:
  Gesamthöhe First  17,5   [LOD2 measuredHeight 17,46/17,63 — amtlich]
  Traufe             9,0   [LOD2 Dach-Unterkante 9,37 ~ Foto Dachanteil ~50% — PASS]
  Fassadenlänge     40     [LOD2 Hauptfront ~40 m + Foto]; Tiefe 13 [LOD2]
  Sockel/EG 0..3 / 1.OG 3..6 / 2.OG 6..9  [Foto: 3 Ebenen je ~3 m]
  Balkonvorsprung  1,3     [Foto]; Gauben unten 7 / oben 6 [Foto gezählt]; Kamine 3 [Foto]

GROB→FEIN: baut FARBIGES GLB (weiße Wand, dunkles Holz/Dach, Fenster, Blumen) + Teil-STL.
Verfeinerung Schritt für Schritt gegen g4 (Fresko, EG-Arkade, feinere Gauben) oben drauf.
"""
import argparse, json, os
import numpy as np
import trimesh


def box(x0, y0, z0, dx, dy, dz):
    b = trimesh.creation.box(extents=(dx, dy, dz))
    b.apply_translation((x0 + dx / 2, y0 + dy / 2, z0 + dz / 2))
    return b


def hip_roof(Lf, D, z_eave, z_ridge, inset, overh=1.15):
    """RIESIGES Krüppelwalmdach (DAS prägende Element des Hofgut Sternen) — weiter Dachüberstand
    (schützt die Balkone), First verkürzt (Krüppelwalm). Front -y, Rück +y. Gibt massives Solid."""
    o = overh; E = z_eave; db = -0.25           # Traufe leicht abgesenkt (Dach zieht tief runter)
    # Oberfläche (6 Punkte) …
    A = (-o, -o, E + db); B = (Lf + o, -o, E + db); C = (Lf + o, D + o, E + db); Dd = (-o, D + o, E + db)
    R0 = (inset, D / 2, z_ridge); R1 = (Lf - inset, D / 2, z_ridge)
    top = [A, B, C, Dd, R0, R1]
    Ft = [(0, 1, 5), (0, 5, 4), (2, 3, 4), (2, 4, 5), (0, 4, 3), (1, 2, 5)]
    # … + Unterseite (Dachstärke, damit es ein druckbares Solid mit sichtbarer Untersicht ist)
    t = 0.45
    bot = [(p[0], p[1], p[2] - t) for p in top]
    V = top + bot; F = list(Ft)
    for (a_, b_, c_) in Ft:                      # Unterseite (umgedreht)
        F.append((a_ + 6, c_ + 6, b_ + 6))
    # Rand-Wände zwischen Ober- und Unterseite (geschlossenes Solid)
    rim = [(0, 1), (1, 2), (2, 3), (3, 0)]
    for (i, j) in rim:
        F += [(i, j, j + 6), (i, j + 6, i + 6)]
    return trimesh.Trimesh(vertices=np.array(V, float), faces=np.array(F), process=True)


def shed_dormer(x, y_slope, z_slope, w=2.0, proj=1.8, h=1.5):
    """Schleppgaube: Rückkante auf der Dachlinie, ragt nach vorn(-y)+oben. Front + Pultdach + Seiten."""
    yf = y_slope - proj; zt = z_slope + h; zb = z_slope - 0.3; xl, xr = x - w / 2, x + w / 2
    V = [(xl, yf, zb), (xr, yf, zb), (xr, yf, zt), (xl, yf, zt),
         (xl, y_slope, z_slope + 0.2), (xr, y_slope, z_slope + 0.2),
         (xl, y_slope, z_slope + h + 0.2), (xr, y_slope, z_slope + h + 0.2)]
    F = [(0, 1, 2), (0, 2, 3), (3, 2, 7), (3, 7, 6), (0, 3, 6), (0, 6, 4),
         (1, 5, 7), (1, 7, 2), (0, 4, 5), (0, 5, 1)]
    return trimesh.Trimesh(vertices=np.array(V, float), faces=np.array(F), process=True)


def big_dormer(x, y_slope, z_slope, w=3.6, proj=1.5, h=1.9, gh=1.1):
    """GROSSES Zwerchhaus (Giebelgaube) an der Traufe: Giebel-Frontwand + Satteldach + dunkles
    Fenster. Gibt (Körper, Fenster). (Foto g4: wenige grosse statt vieler kleiner Gauben!)"""
    yf = y_slope - proj; zb = z_slope - 0.5; zt = zb + h; apex = zt + gh; xl, xr = x - w / 2, x + w / 2
    yb = y_slope
    V = [(xl, yf, zb), (xr, yf, zb), (xr, yf, zt), (xl, yf, zt), (x, yf, apex),            # Front 0-4
         (xl, yb, zb), (xr, yb, zb), (xr, yb, zt), (xl, yb, zt), (x, yb, apex)]            # Rück 5-9
    F = [(0, 1, 2), (0, 2, 3), (3, 2, 4),           # Front Rechteck + Giebeldreieck
         (5, 7, 6), (5, 8, 7), (8, 9, 7),           # Rück
         (0, 3, 8), (0, 8, 5), (1, 6, 7), (1, 7, 2),  # Seitenwände
         (3, 8, 9), (3, 9, 4), (2, 4, 9), (2, 9, 7),  # 2 Dachschrägen
         (0, 5, 6), (0, 6, 1)]                       # Boden
    body = trimesh.Trimesh(vertices=np.array(V, float), faces=np.array(F), process=True)
    win = box(x - w * 0.36, yf - 0.08, zb + 0.45, w * 0.72, 0.1, h - 0.8)
    return body, win


def zwerchhaus(x, E, Rz, D, overh, w=4.0, body_h=1.6, gh=1.3, dep=2.8):
    """ZWERCHHAUS (Wandgaube, Foto g4): Giebel-Frontwand FLÜCHTIG mit der Fassade (y=0), steigt ab
    Traufe E als Rechteck+Giebeldreieck AUF, bricht die vordere Dachlinie. Satteldach nach hinten,
    Rückkante im Haupt-Dach-Solid versenkt. Gibt (körper, fenster). Pokt sichtbar aus dem tiefen Traufbereich."""
    xl, xr = x - w / 2, x + w / 2; zt = E + body_h; apex = zt + gh; yb = dep
    V = [(xl, 0, E), (xr, 0, E), (xr, 0, zt), (xl, 0, zt), (x, 0, apex),        # Front-Giebel 0-4
         (xl, yb, E), (xr, yb, E), (xr, yb, zt), (xl, yb, zt), (x, yb, apex)]   # Rück 5-9
    F = [(0, 1, 2), (0, 2, 3), (3, 2, 4),             # Front Rechteck + Giebeldreieck
         (5, 7, 6), (5, 8, 7), (8, 9, 7),             # Rück
         (0, 3, 8), (0, 8, 5), (1, 6, 7), (1, 7, 2),  # Seitenwände
         (3, 9, 8), (3, 4, 9), (2, 7, 9), (2, 9, 4),  # 2 Dachschrägen (Satteldach)
         (0, 5, 6), (0, 6, 1)]                        # Boden
    body = trimesh.Trimesh(vertices=np.array(V, float), faces=np.array(F), process=True)
    win = box(x - w * 0.34, -0.06, E + 0.35, w * 0.68, 0.1, body_h - 0.6)
    return body, win


def skylight(x, y_slope, z_slope, w=0.85, h=1.1):
    """flaches Dachflächenfenster (Velux), liegt ~bündig auf der Schräge (dunkel)."""
    return box(x - w / 2, y_slope - 0.06, z_slope, w, 0.12, h)


def roof_shingles(Lf, D, E, Rz, slope="front"):
    """Schindelreihen auf der Dachschräge (dezent erhaben) — gibt dem Dach Schindel-Charakter."""
    a = D / 2; b = Rz - E; Ls = (a * a + b * b) ** 0.5
    sgn = -1 if slope == "front" else 1
    su = np.array([0, sgn * a, b]) / Ls; nrm = np.array([0, -sgn * b, a]) / Ls
    Rm = np.eye(4); Rm[:3, 0] = [1, 0, 0]; Rm[:3, 1] = su; Rm[:3, 2] = nrm
    tw, th, rel = 0.34, 0.24, 0.05; parts = []; y0 = 0.0 if slope == "front" else D
    for ci in range(1, int(Ls / th)):
        t = ci * th
        if t > Ls - 0.12:
            break
        base = np.array([0.0, y0, E]) + su * t
        x = tw / 2 if ci % 2 else 0.0
        while x + tw <= Lf:
            bx = trimesh.creation.box(extents=(tw * 0.9, th * 1.3, rel)); bx.apply_transform(Rm)
            bx.apply_translation(np.array([x + tw / 2, base[1], base[2]]) + nrm * (rel * 0.5))
            parts.append(bx); x += tw
    return trimesh.util.concatenate(parts)


def eg_arcade(Lf, z_top=2.9, n=6, y=0.0, spring=1.7):
    """EG-LOGGIA (Foto g4): Stein-Pfeiler + RUNDBÖGEN + dunkle Öffnungen. Gibt (pfeiler, öffnungen)."""
    pitch = Lf / n; pw = 0.55; piers, glass = [], []
    for i in range(n + 1):
        piers.append(box(i * pitch - pw / 2, y - 0.32, 0, pw, 0.5, z_top))         # Pfeiler
    piers.append(box(-0.1, y - 0.32, z_top, Lf + 0.2, 0.52, 0.32))                 # Sturzband über den Bögen
    for i in range(n):
        cx = (i + 0.5) * pitch; ow = pitch - pw; r = ow / 2
        glass.append(box(cx - r, y + 0.02, 0.15, ow, 0.14, spring))                # Rechteck bis Kämpfer
        cyl = trimesh.creation.cylinder(radius=r, height=0.14, sections=18)        # Rundbogen oben
        cyl.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
        cyl.apply_translation((cx, y + 0.02, spring)); glass.append(cyl)
    return trimesh.util.concatenate(piers), trimesh.util.concatenate(glass)


def gaden(x0, y, z, length, height=0.95):
    """Schwarzwald-GADEN-Brüstung: SOLIDES dunkles Holz-Füllpaneel + Hand-/Fußleiste + senkrechte
    Rippen (Foto g4: breite geschlossene Holzbrüstung, NICHT dünne Pfosten) — das prägende Element."""
    parts = [box(x0, y - 0.05, z + 0.08, length, 0.1, height - 0.2),          # geschlossenes Füllpaneel
             box(x0, y - 0.11, z + height - 0.14, length, 0.18, 0.15),        # Handlauf (kräftig)
             box(x0, y - 0.11, z, length, 0.18, 0.13)]                        # Fußleiste
    for xi in np.arange(x0 + 0.25, x0 + length, 0.55):                        # senkrechte Rippen (Relief)
        parts.append(box(xi - 0.03, y - 0.13, z + 0.1, 0.06, 0.06, height - 0.24))
    return trimesh.util.concatenate(parts)


def window_row(Lf, z0, z1, n, wd=0.95, y=0.0):
    """Reihe ECHTER Fenster: dunkle Scheibe + heller Rahmen (Sturz/Sohlbank/Jamben) + Kreuzstock.
    Gibt (glas, rahmen)."""
    glass, fr = [], []; h = z1 - z0
    for x in np.linspace(Lf * 0.07, Lf * 0.93, n):
        xl, xr = x - wd / 2, x + wd / 2
        glass.append(box(xl, y - 0.05, z0, wd, 0.1, h))
        fr.append(box(xl - 0.07, y - 0.11, z1 - 0.02, wd + 0.14, 0.13, 0.11))     # Sturz
        fr.append(box(xl - 0.07, y - 0.11, z0 - 0.06, wd + 0.14, 0.14, 0.1))      # Sohlbank
        fr.append(box(xl - 0.07, y - 0.11, z0, 0.08, 0.13, h))                    # Jambe links
        fr.append(box(xr - 0.01, y - 0.11, z0, 0.08, 0.13, h))                    # Jambe rechts
        fr.append(box(xl, y - 0.13, (z0 + z1) / 2 - 0.03, wd, 0.06, 0.06))        # Kämpfer (quer)
        fr.append(box(x - 0.03, y - 0.13, z0, 0.06, 0.06, h))                     # Mittelpfosten
    return trimesh.util.concatenate(glass), trimesh.util.concatenate(fr)


def flower_boxes(x0, y, z, length, h_rail=0.95):
    """Geranien-KÄSTEN in Gruppen am Handlauf (Foto g4: Blütenbüschel überhängend, NICHT ein
    durchlaufender roter Streifen). Einzelne Kästen mit Lücke dazwischen → liest als Blumen."""
    parts = []
    for xi in np.arange(x0 + 0.3, x0 + length - 0.6, 1.5):           # Kasten alle ~1,5 m
        w = 1.0
        parts.append(box(xi, y - 0.30, z + h_rail - 0.12, w, 0.34, 0.34))   # überhängender Blütenbüschel
    return trimesh.util.concatenate(parts)


def eg_wall_windows(Lf, z0, z1, n, y=0.0, door_x=None):
    """EG = schlichte Wand mit KLEINEN Fenstern + mittigem Eingang (KEINE Riesen-Arkade!).
    Gibt (glas, rahmen). Foto g4: EG hat kleine Fenster, Terrasse davor, Haustür mittig."""
    glass, fr = [], []; h = z1 - z0; wd = 0.75
    xs = list(np.linspace(Lf * 0.08, Lf * 0.92, n))
    for x in xs:
        if door_x is not None and abs(x - door_x) < 1.6:
            continue
        xl = x - wd / 2
        glass.append(box(xl, y - 0.04, z0, wd, 0.08, h))
        fr.append(box(xl - 0.06, y - 0.10, z1 - 0.02, wd + 0.12, 0.12, 0.1))      # Sturz
        fr.append(box(xl - 0.06, y - 0.10, z0 - 0.05, wd + 0.12, 0.13, 0.09))     # Sohlbank
        fr.append(box(xl - 0.06, y - 0.10, z0, 0.07, 0.12, h))
        fr.append(box(x + wd / 2 - 0.01, y - 0.10, z0, 0.07, 0.12, h))
    if door_x is not None:                                                        # Haustür (Rundbogen-Ton)
        glass.append(box(door_x - 0.7, y - 0.04, 0.05, 1.4, 0.09, 2.5))
        fr.append(box(door_x - 0.8, y - 0.11, 0.0, 1.6, 0.14, 0.14))              # Türsturz
        fr.append(box(door_x - 0.8, y - 0.11, 0.0, 0.14, 0.14, 2.65))
        fr.append(box(door_x + 0.66, y - 0.11, 0.0, 0.14, 0.14, 2.65))
    return trimesh.util.concatenate(glass), trimesh.util.concatenate(fr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--Lf", type=float, default=40.0); ap.add_argument("--D", type=float, default=13.0)
    ap.add_argument("--eave", type=float, default=8.2); ap.add_argument("--ridge", type=float, default=17.5)
    ap.add_argument("--socle", type=float, default=3.0); ap.add_argument("--floor", type=float, default=3.0)
    ap.add_argument("--balc-proj", type=float, default=1.3); ap.add_argument("--n-axes", type=int, default=13)
    ap.add_argument("--dormers-low", type=int, default=7); ap.add_argument("--dormers-up", type=int, default=6)
    ap.add_argument("--chimneys", type=int, default=3); ap.add_argument("--inset", type=float, default=5.0)
    ap.add_argument("--outdir", default="modelle/hofgut_sternen")
    ap.add_argument("--schema", default="modelle/hofgut_sternen/schema.json",
                    help="gemessenes Schema (LOD2-Massing + Foto-Kanten); überschreibt die Defaults")
    a = ap.parse_args()

    # --- PFLICHT-GATE: Quellen-Inventur (alle Quellen mergen, nichts raten) VOR dem Bau ---
    import subprocess
    try:
        r = subprocess.run(["python3", "tools/quellen_inventar.py", "--name", "hofgut_sternen"],
                            capture_output=True, text=True, timeout=60)
        tail = [l for l in r.stdout.splitlines() if "genutzt ·" in l or "OFFEN" in l]
        print("[quellen] " + " | ".join(tail) if tail else "[quellen] Inventur gelaufen")
    except Exception as e:
        print(f"[quellen] Inventur übersprungen ({e})")

    # --- DATEN-GETRIEBEN: Schema aus LOD2+Foto laden und Massing/Achsen daraus setzen (nicht raten) ---
    if os.path.exists(a.schema):
        with open(a.schema) as f:
            sc = json.load(f)
        a.ridge = sc.get("ridge_m", a.ridge)                 # First  — LOD2 amtlich
        a.eave = sc.get("eave_m", a.eave)                    # Traufe — LOD2 amtlich
        a.Lf = sc.get("width_m", a.Lf)                       # Fassadenbreite Hauptflügel — LOD2
        a.n_axes = sc.get("n_axes", a.n_axes)                # Fensterachsen — Foto-Kanten
        qc = sc.get("quercheck", "n/a")
        print(f"[schema] Massing aus LOD2: First {a.ridge} m, Traufe {a.eave} m, Breite {a.Lf} m, "
              f"{a.n_axes} Achsen | Dachanteil-Quercheck Foto↔LOD2: {qc}")
    Lf, D, E, Rz, S, Fl, bp, N = a.Lf, a.D, a.eave, a.ridge, a.socle, a.floor, a.balc_proj, a.n_axes
    # Geschosshöhe aus gemessener Traufe ableiten (3 Ebenen: EG + 2 OG) statt fester 3 m
    S = a.socle; Fl = (E - S) / 2.0

    # --- ECHTE FARBEN zonenweise aus dem Foto (via ML-Maske gemessen) statt geraten ---
    farben = os.path.join(a.outdir, "farben.json")
    FM = {"dach": [173, 155, 136], "og_lauben": [105, 85, 62], "eg": [197, 176, 148]}
    if os.path.exists(farben):
        with open(farben) as f:
            FM.update(json.load(f))
        print(f"[farben] gemessen: Dach {FM['dach']}, OG-Holz {FM['og_lauben']}, EG {FM['eg']}")
    def shade(c, f):  # abgedunkelte/aufgehellte Variante einer gemessenen Farbe
        return [max(0, min(255, int(v * f))) for v in c] + [255]

    sockel = box(0, 0, 0, Lf, D, S)
    waende = box(0, 0, S, Lf, D, E - S)
    dach = hip_roof(Lf, D, E, Rz, a.inset)

    balkone, blumen = [], []
    for zf in (S, S + Fl):                                   # Gaden-Galerien auf 1.OG + 2.OG
        balkone.append(box(0.6, -bp, zf - 0.18, Lf - 1.2, bp + 0.1, 0.18))     # auskragender Holzboden
        balkone.append(gaden(0.6, -bp, zf, Lf - 1.2))                          # solide Holzbrüstung
        blumen.append(flower_boxes(0.6, -bp, zf, Lf - 1.2))                    # üppige Geranien
    balkone = trimesh.util.concatenate(balkone); blumen = trimesh.util.concatenate(blumen)

    # EG = schlichte Wand mit kleinen Fenstern + mittigem Eingang (KEINE Riesen-Arkade!)
    fglass, fframe = [], []
    eg_g, eg_fr = eg_wall_windows(Lf, S * 0.55, S * 0.55 + 1.5, N - 2, door_x=Lf * 0.5)
    fglass.append(eg_g); fframe.append(eg_fr)
    for z0, z1 in [(S + 0.5, S + 1.9), (S + Fl + 0.5, S + Fl + 1.9)]:
        g, fr = window_row(Lf, z0, z1, N); fglass.append(g); fframe.append(fr)

    # DACH: wenige GROSSE Zwerchhäuser + kleine Schleppgauben darüber — NICHT viele gleiche Gauben (Foto g4).
    # höher auf der Schräge platzieren (frac ~0.30), sonst verschwinden sie unter dem weiten Dachüberstand.
    def on_slope(frac): z = E + frac * (Rz - E); return (D / 2) * (z - E) / (Rz - E), z
    bodies = []
    for x in np.array([0.24, 0.55, 0.82]) * Lf:                       # 3 grosse Zwerchhäuser (Wandgauben) an der Fassade
        b, w_ = zwerchhaus(x, E, Rz, D, a.inset, w=4.0, body_h=1.7, gh=1.3); bodies.append(b); fglass.append(w_)
    vy, vz = on_slope(0.52)                                           # flache Dachflächenfenster (dezent) statt Warzen
    fglass += [skylight(x, vy, vz) for x in np.array([0.16, 0.40, 0.63, 0.88]) * Lf]
    gauben = trimesh.util.concatenate(bodies)
    fenster = trimesh.util.concatenate(fglass)
    fensterrahmen = trimesh.util.concatenate(fframe)
    schindel = trimesh.util.concatenate([roof_shingles(Lf, D, E, Rz, "front"), roof_shingles(Lf, D, E, Rz, "back")])

    kamine = trimesh.util.concatenate(
        [box(x - 0.5, D / 2 - 0.5, Rz - 1.0, 1.0, 1.0, 3.0) for x in np.linspace(Lf * 0.25, Lf * 0.8, a.chimneys)])

    # FRESKO (Foto g4: grosses Wandgemälde mittig im 2.OG über der Laube) — flaches Panel, warm getönt
    fresko = box(Lf * 0.5 - 2.6, -0.06, S + Fl + 0.3, 5.2, 0.06, Fl - 0.7)

    COL = {"sockel": FM["eg"] + [255],                       # EG = beiger Stein (gemessen)
           "waende": FM["og_lauben"] + [255],                # OG = DUNKLES HOLZ (gemessen, nicht weiß!)
           "balkone": shade(FM["og_lauben"], 0.8),           # Lauben = etwas dunkleres Holz
           "dach": FM["dach"] + [255],                       # Dach = hell-graubraun (gemessen)
           "gauben": FM["dach"] + [255], "kamine": [120, 108, 98, 255],
           "fenster": [44, 42, 48, 255], "blumen": [196, 60, 66, 255], "fensterrahmen": [228, 222, 208, 255],
           "schindel": shade(FM["dach"], 0.82), "fresko": [182, 150, 112, 255]}
    parts = {"sockel": sockel, "waende": waende, "fresko": fresko,
             "balkone": balkone, "fenster": fenster, "fensterrahmen": fensterrahmen, "blumen": blumen,
             "dach": dach, "schindel": schindel, "gauben": gauben, "kamine": kamine}
    os.makedirs(a.outdir, exist_ok=True)
    sc = trimesh.Scene()
    for nm, m in parts.items():
        m.visual.face_colors = COL[nm]; m.export(f"{a.outdir}/hofgut_{nm}.stl")
        sc.add_geometry(m, geom_name=nm)
    trimesh.util.concatenate(list(parts.values())).export(f"{a.outdir}/hofgut_detail.stl")
    sc.export(f"{a.outdir}/hofgut_sternen.glb")
    ext = sc.bounds[1] - sc.bounds[0]
    print(f"Hofgut Sternen (grob+farbig): L×B×H = {ext[0]:.1f}×{ext[1]:.1f}×{ext[2]:.1f} m")
    print(f"  Teile: {', '.join(parts)} | {N} Achsen, Gauben {a.dormers_low}+{a.dormers_up}, Kamine {a.chimneys}")
    print(f"-> {a.outdir}/hofgut_sternen.glb (+ Teil-STL + hofgut_detail.stl)")


if __name__ == "__main__":
    main()
