#!/usr/bin/env python3
"""sp_lantern_leds.py — druckfertiges LATERNENTEIL (alles oberhalb der Kuppel) mit
SENKRECHTEN Löchern nach oben für 3-mm-LEDs, platziert in den LÜCKEN zwischen den
Kolonnaden-Säulen. LED wird von oben reingesteckt, zeigt nach oben.

Ablauf (Boolean nur am wasserdichten Vollmodell!):
  Säulen per Raycast finden → Lücken = Mittelwinkel → vertikale Bohrungen am
  wasserdichten Vollmodell → oberhalb z=Z_CUT abschneiden → vergrößern → export.
"""
import sys, numpy as np, trimesh
sys.path.insert(0, "tools")

SRC = "modelle/3d_druck/sp-dome.stl"
OUT = "modelle/3d_druck/sp-lantern-leds.stl"

SCALE   = 1.6
Z_CUT   = 174.0        # Sockelring MIT dabei (fuer LED-Sitz zum direkt Reinstecken)
Z_COL   = 183.0        # Höhe zum Säulen-Detektieren
PART_SCALE = 1.5       # Laternenteil vergrößern → 3-mm bequem
LED_FINAL  = 3.3       # Ziel-Ø nach dem Vergrößern (3-mm-LED + Spiel)
N_LEDS  = 8            # LEDs (in jede 2. Lücke bei ~16 Säulen)
UPPER_Z = 193.0        # Höhe der oberen Löcher (Kuppe über den Säulen)
UPPER_D_FINAL = 1.8    # Ziel-Ø oben (LWL/Glasfaser oder kleine LED)
N_UPPER = 8            # Anzahl obere Löcher (über den Säulen)


def column_angles(m, cx, cy, z, n=720):
    angs = np.linspace(0, 2*np.pi, n, endpoint=False)
    R = np.full(n, np.nan)
    for i, a in enumerate(angs):
        o = np.array([cx, cy, z]); d = np.array([np.cos(a), np.sin(a), 0.0])
        locs, _, _ = m.ray.intersects_location([o], [d])
        if len(locs):
            R[i] = np.linalg.norm(locs - o, axis=1).max()
    Rm = np.nanmean(R)
    above = R > Rm + 0.25
    # Säulen = zusammenhängende "oben"-Segmente → Mittelwinkel
    cols = []
    i = 0
    arr = np.concatenate([above, above[:1]])
    while i < n:
        if arr[i]:
            j = i
            while arr[j % n] and j < i + n:
                j += 1
            cols.append(angs[(i + (j-1)) // 2 % n])
            i = j
        else:
            i += 1
    return np.array(cols), np.nanmean(R)


def main():
    m = trimesh.load(SRC, force="mesh"); m.apply_scale(SCALE)
    cx, cy = m.vertices[:, 0].mean(), m.vertices[:, 1].mean()
    cols, r_col = column_angles(m, cx, cy, Z_COL)
    print(f"Säulen erkannt: {len(cols)}  r_kolonnade≈{r_col:.1f} mm")
    # Lücken = Mittelwinkel zwischen benachbarten Säulen
    gaps = []
    cs = np.sort(cols)
    for i in range(len(cs)):
        a0 = cs[i]; a1 = cs[(i+1) % len(cs)] + (2*np.pi if i == len(cs)-1 else 0)
        gaps.append(((a0 + a1) / 2.0) % (2*np.pi))
    gaps = np.array(gaps)
    # N_LEDS gleichmäßig aus den Lücken wählen
    pick = gaps[np.linspace(0, len(gaps)-1, N_LEDS).round().astype(int)] if len(gaps) >= N_LEDS else gaps
    print(f"Lücken gesamt {len(gaps)} → {len(pick)} LEDs gesetzt")

    # SENKRECHTE Aussparungen MITTIG in die LÜCKEN zwischen den Säulen (r=Ringmitte,
    # nicht am Säulenrand). LED von UNTEN rein, strahlt senkrecht nach oben zwischen
    # den Säulen durch.
    hole_pre = LED_FINAL / PART_SCALE
    R_LED = 9.0                             # im Sockelring-Material UND an der Saeulen-Luecke
    POCKET_TOP, POCKET_BOT = 184.0, 172.0   # durch den Sockelring, unten offen -> LED von unten
    cutters = []
    for a in pick:
        x, y = cx + R_LED*np.cos(a), cy + R_LED*np.sin(a)
        cyl = trimesh.creation.cylinder(radius=hole_pre/2,
              segment=np.array([[x, y, POCKET_TOP], [x, y, POCKET_BOT]]), sections=24)
        cutters.append(cyl)

    # --- OBERER Ring: kleine RADIALE Löcher ÜBER den Säulen (Kuppe) für
    #     LWL/Glasfaser oder kleine LEDs. Ø vor dem Vergrößern. ---------------
    up_cols = cols[np.linspace(0, len(cols)-1, N_UPPER).round().astype(int)] if len(cols) >= N_UPPER else cols
    up_pre = UPPER_D_FINAL / PART_SCALE
    for a in up_cols:
        rad = np.array([np.cos(a), np.sin(a), 0.0])
        p_out = np.array([cx, cy, UPPER_Z]) + rad * 9.0    # außen
        p_in  = np.array([cx, cy, UPPER_Z]) + rad * 2.0    # kurz nach innen (nicht durch Gegenwand)
        cutters.append(trimesh.creation.cylinder(radius=up_pre/2,
              segment=np.array([p_out, p_in]), sections=16))
    print(f"Obere LWL/Klein-Löcher: {len(up_cols)} @ z={UPPER_Z} Ø≈{up_pre*PART_SCALE:.1f}mm")

    # --- ZENTRALER LICHT-SCHACHT: verbindet den Kolonnaden-Hohlraum mit der
    #     oberen Krone (Kuppe/Kugel), damit das Licht hoch in die Krone steigt. --
    cutters.append(trimesh.creation.cylinder(radius=2.0,
          segment=np.array([[cx, cy, 188.0], [cx, cy, 213.0]]), sections=24))
    print("Zentraler Licht-Schacht: z188..213 Ø4 (pre) -> Licht in die obere Krone")

    cut = trimesh.util.concatenate(cutters)
    bored = m.difference(cut)
    print(f"Vollmodell gebohrt: watertight={bored.is_watertight}")

    # Laterne abschneiden (OFFENER Boden, cap=False → kein innerer Boden) + vergrößern
    lant = bored.slice_plane([0, 0, Z_CUT], [0, 0, 1], cap=False)
    lant.apply_scale(PART_SCALE)
    lant.apply_translation([0, 0, -lant.bounds[0][2]])
    lant.export(OUT)
    print(f"Laterne: h={lant.bounds[1][2]-lant.bounds[0][2]:.0f}mm "
          f"Ø_fuß≈{lant.bounds[1][0]-lant.bounds[0][0]:.0f}mm "
          f"Loch-Ø≈{hole_pre*PART_SCALE:.1f}mm -> {OUT}")


if __name__ == "__main__":
    main()
