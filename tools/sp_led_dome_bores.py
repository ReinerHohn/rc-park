#!/usr/bin/env python3
"""sp_led_dome_bores.py — Petersdom-KUPPEL mit ECHTEN Ø3,5-DURCHBOHRUNGEN statt
flacher Mini-Schlitze. Jedes Loch bricht komplett in den Hohlraum durch →
im Druck klar sichtbares rundes Loch, 0805-LED wird von INNEN reingesteckt.

Jede Lochposition wird per Raycast von der Mittelachse nach außen auf die
ECHTE Oberfläche gesnappt (robust gegen Maß-Abschätzungen).

Exporte:
  - sp-dome-led-bored.stl   volle Kuppel, 25 Löcher
  - sp-dome-top-test.stl    nur Oberteil (z>150): 8 Laternen + Spitze = schneller Test
"""
import sys, numpy as np, trimesh
sys.path.insert(0, "tools")
import light_prep as L

SRC  = "modelle/3d_druck/sp-dome.stl"
FULL = "modelle/3d_druck/sp-dome-led-bored.stl"
TOP  = "modelle/3d_druck/sp-dome-top-test.stl"
SCALE = 1.6
BORE_D = 3.3          # Ø für 3-mm-RUNDE LED (3,0 + 0,3 Klebespiel) → selbst-zentrierend
Z_TOP_CUT = 150.0     # Oberteil-Schnitt (Laterne + Spitze)
SEAT = False          # False = rundes selbst-zentrierendes Loch (runde LED klemmt/zentriert
                      #         sich an der Wand); True = eckige 0805-SMD-Sitztasche


def hole(p, d, through):
    """Ein Loch als Dict: entweder Sitztasche (SEAT) oder gerade Bohrung."""
    if SEAT:
        return {"type": "seat", "pos": list(p), "dir": list(d),
                "led": [2.0, 1.25], "tol": 0.5, "seat_depth": 1.0,
                "bore_d": 1.8, "through": max(through, 5.0), "overshoot": 1.0}
    return {"type": "bore", "pos": list(p), "dir": list(d),
            "d": BORE_D, "through": through, "overshoot": 1.5}


def snap_radial(m, cx, cy, z, a):
    """Radialer Strahl von der Achse nach außen → äußerster Trefferpunkt = Oberflächenmund."""
    o = np.array([cx, cy, z])
    d = np.array([np.cos(a), np.sin(a), 0.0])
    locs, _, _ = m.ray.intersects_location([o], [d])
    if len(locs) == 0:
        return None, d
    far = locs[np.argmax(np.linalg.norm(locs - o, axis=1))]
    return far, d


def snap_top(m, cx, cy):
    """Senkrechter Strahl von oben nach unten → höchster Treffer = Spitzen-Oberfläche."""
    o = np.array([cx, cy, 400.0]); d = np.array([0, 0, -1.0])
    locs, _, _ = m.ray.intersects_location([o], [d])
    if len(locs) == 0:
        return None
    return locs[np.argmax(locs[:, 2])]


def tilted_up(a, elev_deg):
    """LED-Licht-/Einsteckrichtung = Außennormale (radial) um elev_deg nach OBEN
    gekippt. elev_deg=0 → gerade raus, =35 → 35° nach oben Richtung Rippen.
    Das Loch bleibt bohrbar (Gegenrichtung zeigt in die Wand/Hohlraum)."""
    e = np.radians(elev_deg)
    radial = np.array([np.cos(a), np.sin(a), 0.0])
    d = radial * np.cos(e) + np.array([0, 0, 1.0]) * np.sin(e)
    return d / (np.linalg.norm(d) + 1e-9)


# Kippwinkel je Ring (Grad nach OBEN gegen die Kuppel). Zum Experimentieren anpassen.
TILT_BALKON = 35.0    # Balkon: nach oben an die Rippen
TILT_FUSS   = 30.0    # Laternenfuß
TILT_KRANZ  = 25.0    # Laternen-Kranz
FINIAL_LED  = False   # Spitzen-LED: aus → massive stabile Spitze (kein Empty-Layer/Bruch)
N_LWL       = 8       # kleine LWL/Glasfaser-Löcher oben in der Kuppe
LWL_D       = 1.5     # Ø LWL-Loch (fein → für saubere Kante eig. 0,4-Düse)


def column_angles(m, cx, cy, z=183.0, n=720):
    """Kolonnaden-Säulen am Kranz finden → Säulen-Winkel + Lücken-Mittelwinkel."""
    angs = np.linspace(0, 2*np.pi, n, endpoint=False)
    R = np.full(n, np.nan)
    for i, a in enumerate(angs):
        o = np.array([cx, cy, z]); d = np.array([np.cos(a), np.sin(a), 0.0])
        locs, _, _ = m.ray.intersects_location([o], [d])
        if len(locs):
            R[i] = np.linalg.norm(locs - o, axis=1).max()
    above = R > np.nanmean(R) + 0.25
    cols, i = [], 0
    arr = np.concatenate([above, above[:1]])
    while i < n:
        if arr[i]:
            j = i
            while j < i + n and arr[j % n]:
                j += 1
            cols.append(float(angs[(i + j - 1) // 2 % n])); i = j
        else:
            i += 1
    cols = np.sort(cols)
    gaps = [((cols[k] + (cols[(k+1) % len(cols)] + (2*np.pi if k == len(cols)-1 else 0))) / 2) % (2*np.pi)
            for k in range(len(cols))] if len(cols) else []
    return cols, np.array(gaps)


def build_bores(m, cx, cy):
    bores = []
    cols, gaps = column_angles(m, cx, cy)
    # --- 16 BALKON-UPLIGHTER: senkrechtes Loch durch den waagrechten Galerie-
    #     Boden (z≈92, r≈42). LED wird von INNEN hochgesteckt, strahlt SENKRECHT
    #     nach oben an die Kuppel-RIPPEN → DAS beleuchtet die Kuppel. -----------
    Z_LEDGE, R_LEDGE = 92.0, 42.0
    for i in range(16):
        a = 2 * np.pi * i / 16
        x, y = cx + R_LEDGE * np.cos(a), cy + R_LEDGE * np.sin(a)
        d = np.array([-0.15 * np.cos(a), -0.15 * np.sin(a), 1.0])  # hoch + leicht nach innen
        d /= np.linalg.norm(d)
        bores.append(hole([x, y, Z_LEDGE], d, through=8.0))
    # --- Laternenfuß (8): weiterhin radial gekippt ------------------------
    for i in range(8):
        a = 2 * np.pi * i / 8
        p, _ = snap_radial(m, cx, cy, 164.8, a)
        if p is None:
            continue
        bores.append(hole(p, tilted_up(a, TILT_FUSS), through=5.0))
    # --- Laternen-KRANZ (z≈185): LED-Löcher in die LÜCKEN zwischen den Säulen ---
    gap_pick = gaps[np.linspace(0, len(gaps)-1, 6).round().astype(int)] if len(gaps) >= 6 else gaps
    for a in gap_pick:
        p, _ = snap_radial(m, cx, cy, 185.0, a)
        if p is None:
            continue
        bores.append(hole(p, tilted_up(a, TILT_KRANZ), through=6.0))
    # --- Kleine LWL/Glasfaser-Löcher ÜBER den Säulen (Kuppe z≈193), radial -----
    col_pick = cols[np.linspace(0, len(cols)-1, N_LWL).round().astype(int)] if len(cols) >= N_LWL else cols
    for a in col_pick:
        p, _ = snap_radial(m, cx, cy, 193.0, a)
        if p is None:
            continue
        d = np.array([np.cos(a), np.sin(a), 0.0])
        bores.append({"type": "bore", "pos": list(p), "dir": list(d),
                      "d": LWL_D, "through": 4.0, "overshoot": 1.0})
    # Spitze: vertikale Bohrung/Tasche — NUR wenn FINIAL_LED (sonst hohlt sie die
    # Spitze aus → Empty-Layer/Bruch; Kranz beleuchtet den oberen Bereich eh).
    if FINIAL_LED:
        p = snap_top(m, cx, cy)
        if p is not None:
            bores.append(hole(p, [0, 0, 1.0], through=6.0))
    return bores


def verify(m, bores):
    """Jede Bohrung muss durch Material gehen (sonst kein sichtbares Loch)."""
    good = 0
    for b in bores:
        p = np.array(b["pos"]); d = np.array(b["dir"], float); d /= np.linalg.norm(d)
        hit = m.ray.intersects_any([p + d * 0.5], [-d])  # von außen nach innen
        good += bool(hit[0])
    return good


def main():
    m = trimesh.load(SRC, force="mesh")
    m.apply_scale(SCALE)
    cx, cy = m.vertices[:, 0].mean(), m.vertices[:, 1].mean()

    bores = build_bores(m, cx, cy)
    print(f"Bohrungen: {len(bores)}  durch Material: {verify(m, bores)}")

    # Kabel-Austritt (Port) senkrecht durch den Sockel nach unten raus -------
    base_z = float(m.bounds[0][2])
    bores.append({"type": "port", "pos": [cx, cy, base_z + 2.0], "d": 6.0, "up": 10})

    # --- volle Kuppel -----------------------------------------------------
    full = L.prep(m, bores)
    full.export(FULL)
    print(f"FULL watertight={full.is_watertight} faces={len(full.faces):,} "
          f"vol={full.volume/1000:.1f}cm3 -> {FULL}")

    # --- Test-Oberteil: fertige Kuppel oben abschneiden (Löcher schon drin) --
    top_bores = [b for b in bores if b["pos"][2] > Z_TOP_CUT]
    top = full.slice_plane([0, 0, Z_TOP_CUT], [0, 0, 1], cap=True)
    # auf z=0 absetzen fürs Drucken
    top.apply_translation([0, 0, -top.bounds[0][2]])
    top.export(TOP)
    print(f"TOP  Löcher={len(top_bores)} watertight={top.is_watertight} "
          f"faces={len(top.faces):,} vol={top.volume/1000:.1f}cm3 "
          f"h={top.bounds[1][2]-top.bounds[0][2]:.0f}mm -> {TOP}")


if __name__ == "__main__":
    main()
