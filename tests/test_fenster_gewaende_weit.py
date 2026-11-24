#!/usr/bin/env python3
"""test_fenster_gewaende_weit.py - Befund 1122w Sued-Fenster f01 (24.11.2026), synthetisch, < 20 s, nur CPU.

Foto: vergittertes Stichbogenfenster in einem BREITEN Sandstein-Gewaende (Keilsteinfaecher 0,8 m hoch, Seiten 0,7 m) in weissem Putz.
Kette: Gewaende fehlte, Beulen daneben. Ursache: loch_gewaende nahm die Wandfarbe als Median des Rings 0,15-0,45 m um die Zone - den fuellt hier der
Sandstein -> Sandstein = 'Wand', Gewaende leer; zusaetzlich nur 10 cm um die Zone erlaubt.
  1 Gewaende: Wandfarbe aus dem aeusseren Band (wandfarbe, 2-Mittel) -> Gewaende gefunden, Umriss reicht bis an den Faecher/die Seiten.
    ROT-PROBE: alte Wandfarbe (Ring-Median) -> kein Gewaende (= Befund).
  2 Bogen: Eintrag ohne Bogen -> Stichbogen aus der Oberkante des Lochs (Pfeil 0,11 m); Eintrag mit Bogen aus nischen_fenster (rund) bleibt rund.
    Rundbogenloch -> 'rund'. Rechteckloch -> kein Bogen.
  3 Guard Normalfall: schmales Gewaende (8 cm) in Putz -> Wandfarbe wie bisher (wand_weit fehlt), Gewaende nur am Loch.
  4 Bau: Gewaende-Relief + Loch (Stichbogen) senkrecht zur Wandebene; eine Netz-Beule VOR dem Gewaende wird von loch_gewaende_spaet abgetragen,
    das Loch bleibt offen, die Wand daneben unveraendert, ein Koerper.
"""
import os, sys, json, copy
import numpy as np
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(HIER), "tools"))
from pfade import temp_ordner
import loch_gewaende as LG

U0, U1, Z0, Z1, C = -3.0, 3.0, 20.0, 28.0, 0.01
PUTZ, SAND, DUNKEL, STAB = (225, 228, 230), (120, 135, 190), (25, 25, 30), (70, 70, 75)
F = 0


def pruef(ok, text):
    global F
    print(("  ok     " if ok else "  FEHLER ") + text)
    if not ok: F += 1


def nahe(a, b, tol): return a is not None and abs(a - b) <= tol


def gitter():
    H, W = int((Z1 - Z0) / C), int((U1 - U0) / C); uu = U0 + C * (np.arange(W) + 0.5); zz = Z1 - C * (np.arange(H) + 0.5)
    return np.meshgrid(uu, zz)


def bild(loch, gewaende, bogen_pfeil, rng_seed=1):
    """Putzwand; gewaende = Liste von Rechtecken (Sandstein); loch = (u0, u1, z0, kaempfer) mit Bogen (Pfeil) darueber, Gitterstaebe."""
    rng = np.random.default_rng(rng_seed); UU, ZZ = gitter()
    im = np.zeros(UU.shape + (3,)) + np.array(PUTZ) + rng.normal(0, 3.0, UU.shape + (1,))
    for u0, u1, z0, z1 in gewaende: im[(UU >= u0) & (UU <= u1) & (ZZ >= z0) & (ZZ <= z1)] = np.array(SAND) + rng.normal(0, 4.0, 3)
    u0, u1, z0, k = loch; a = (u1 - u0) / 2; m = (u0 + u1) / 2; h = bogen_pfeil
    if h > 0:
        R = (a * a + h * h) / (2 * h); top = k - R + h + np.sqrt(np.maximum(R * R - (UU - m) ** 2, 0.0)) if h < a else k + np.sqrt(np.maximum(a * a - (UU - m) ** 2, 0.0))
    else: top = np.full(UU.shape, k)
    hole = (UU >= u0) & (UU <= u1) & (ZZ >= z0) & (ZZ <= np.maximum(top, k))
    im[hole] = DUNKEL
    for s in np.arange(u0 + 0.12, u1, 0.15): im[hole & (np.abs(UU - s) < 0.012)] = STAB
    return np.clip(im, 0, 255).astype(np.uint8)


# Sued-Fenster wie 1122w f01: Loch u -0.44..0.44, z 23.30..24.55 (Kaempfer), Stich 0,11 m -> Scheitel 24.66
LOCH = (-0.44, 0.44, 23.30, 24.55); PFEIL = 0.11
GEW = [(-0.95, 0.95, 23.15, 24.95), (-1.20, -0.95, 23.75, 24.25), (0.95, 1.20, 23.55, 24.10),       # Seitenstuecke (verzahnt)
       (-0.55, 0.55, 24.95, 25.30), (-0.20, 0.20, 25.30, 25.45)]                                    # Keilsteinfaecher (vereinfacht)
ZONE = [LOCH[0] - 0.05, LOCH[1] + 0.05, LOCH[2] - 0.05, LOCH[3] + PFEIL]


def main():
    R = LG.Raster(U0, Z1, C, int((Z1 - Z0) / C), int((U1 - U0) / C))
    bgr = bild(LOCH, GEW, PFEIL)
    # 1 Gewaende
    erg = LG.loch_messen(bgr, R, ZONE); G = erg.get("gewaende") or {}
    pruef("fehler" not in erg, f"1: Loch gefunden ({erg.get('fehler', erg.get('loch'))})")
    pruef(bool(erg.get("wand_weit")), "1: Wandfarbe aus dem aeusseren Band (Ring voller Sandstein erkannt)")
    pruef(nahe((erg.get("loch") or {}).get("wand_L"), 90.0, 5.0), f"1: Wand-Helligkeit = Putz (L {(erg.get('loch') or {}).get('wand_L')}, Sandstein waere ~60)")
    um = np.array(G.get("umriss") or [[0, 0]], float)
    pruef(len(G.get("umriss") or []) >= 4, f"1: Gewaende-Umriss {len(G.get('umriss') or [])} Ecken, {G.get('flaeche_m2')} m2")
    soll = sum((b - a) * (d - c) for a, b, c, d in GEW) - (LOCH[1] - LOCH[0]) * (LOCH[3] + PFEIL * 0.7 - LOCH[2])
    pruef(nahe(G.get("flaeche_m2"), soll, 0.35 * soll), f"1: Gewaende-Flaeche {G.get('flaeche_m2')} m2 (soll ~{soll:.2f}, ohne Loch)")
    pruef(um[:, 0].min() < -1.1 and um[:, 0].max() > 1.1 and um[:, 1].max() > 25.35, f"1: Umriss reicht an Seitenstuecke und Faecher (u {um[:, 0].min():.2f}..{um[:, 0].max():.2f}, z bis {um[:, 1].max():.2f})")
    # ROT-PROBE: alte Wandfarbe = Ring-Median
    alt = LG.wandfarbe
    def ring_median(lab, d, bel, **k):
        nah = (d >= LG.RING[0]) & (d <= LG.RING[1]) & bel; w0 = np.median(lab[nah], axis=0)
        return w0, 2.0 * float(np.percentile(np.linalg.norm(lab[nah] - w0, axis=1), 50)), False
    LG.wandfarbe = ring_median
    try: erg_alt = LG.loch_messen(bgr, R, ZONE)
    finally: LG.wandfarbe = alt
    pruef(not erg_alt.get("gewaende") or erg_alt["gewaende"]["flaeche_m2"] < 0.5 * soll,
          f"1 ROT-PROBE: mit dem Ring-Median fehlt das Gewaende (Befund 1122w): {(erg_alt.get('gewaende') or {}).get('flaeche_m2')} m2")

    # 2 Bogen
    e = dict(u0=ZONE[0], u1=ZONE[1], z0=ZONE[2], z1=ZONE[3], teiler=[], scheiben=1, stimmen_min=5, sprossen=[])
    LG.eintrag_anpassen(e, copy.deepcopy(erg), None)
    b = e.get("bogen") or {}
    pruef(b.get("form") == "stich" and nahe(b.get("scheitel", 0) - b.get("kaempfer", 0), PFEIL, 0.03) and nahe(b.get("scheitel"), LOCH[3] + PFEIL, 0.03),
          f"2: Eintrag ohne Bogen -> Stich aus der Lochoberkante {b} (Pfeil soll {PFEIL})")
    pruef(nahe(e["u0"], LOCH[0], 0.03) and nahe(e["u1"], LOCH[1], 0.03), f"2: Seiten aus dem Loch {e['u0']:.2f}..{e['u1']:.2f}")
    e2 = dict(u0=ZONE[0], u1=ZONE[1], z0=ZONE[2], z1=ZONE[3], teiler=[], scheiben=1, stimmen_min=5, sprossen=[], bogen=dict(form="rund", kaempfer=24.2, scheitel=24.66))
    LG.eintrag_anpassen(e2, copy.deepcopy(erg), None)
    pruef((e2.get("bogen") or {}).get("form") == "rund", f"2: Bogen aus nischen_fenster (rund) bleibt ({e2.get('bogen')})")
    lr = (-0.4, 0.4, 23.3, 24.4); bgr_r = bild(lr, [], 0.4); er = LG.loch_messen(bgr_r, R, [lr[0] - 0.05, lr[1] + 0.05, lr[2] - 0.05, lr[3] + 0.45])
    pruef(((er.get("loch") or {}).get("bogen") or {}).get("form") == "rund", f"2: Rundbogenloch -> rund ({(er.get('loch') or {}).get('bogen')})")
    lq = (-0.4, 0.4, 23.3, 24.6); bgr_q = bild(lq, [], 0.0); eq = LG.loch_messen(bgr_q, R, [lq[0] - 0.05, lq[1] + 0.05, lq[2] - 0.05, lq[3] + 0.05])
    pruef("loch" in eq and not eq["loch"].get("bogen"), f"2: Rechteckloch -> kein Bogen ({(eq.get('loch') or {}).get('bogen')})")

    # 3 Guard Normalfall: schmales Gewaende
    gs = [(LOCH[0] - 0.08, LOCH[1] + 0.08, LOCH[2] - 0.08, LOCH[3] + PFEIL + 0.08)]
    en = LG.loch_messen(bild(LOCH, gs, PFEIL), R, ZONE)
    um3 = np.array((en.get("gewaende") or {}).get("umriss") or [[0, 0]], float)
    pruef(not en.get("wand_weit") and en.get("gewaende") is not None and um3[:, 0].min() > LOCH[0] - 0.15,
          f"3: schmales Gewaende -> Wandfarbe wie bisher, Umriss nur am Loch ({en.get('wand_weit')}, u ab {um3[:, 0].min():.2f})")

    # 4 Bau
    from bauteile import fenster_aus_json, loch_gewaende_spaet, _oberflaeche_w, Wand
    from manifold3d import Manifold as M
    d = temp_ordner("test_fgw_"); fa = os.path.join(d, "fenster_auto.json")
    e["gewaende"] = dict(umriss=G["umriss"], flaeche_m2=G["flaeche_m2"], hoehe=None, hoehe_quelle="ANNAHME Druckmindestmass")
    e["tiefe"] = 0.12
    json.dump({"f01": dict(o=[0.0, 0.0], d=[1.0, 0.0], n=[0.0, 1.0], fenster=[e])}, open(fa, "w"))
    k = M.cube((6.0, 3.0, 8.0)).translate((-3.0, -3.0, 20.0)); k1, _ = fenster_aus_json(k, fa)
    beule = M.cube((0.3, 0.25, 0.3)).translate((-0.85, 0.0, 24.0))        # Netz-Beule vor dem linken Gewaendestueck (w 0 .. 0,25)
    beule2 = M.cube((0.2, 0.2, 0.2)).translate((2.2, 0.0, 22.0))          # Beule weit neben dem Gewaende (nicht Sache dieses Bauteils)
    k1 = k1 + beule + beule2
    W = Wand((0.0, 0.0), (1.0, 0.0), aussen=(0.0, 1.0))
    v = _oberflaeche_w(k1, W, [(-0.7, 24.15)])[0]; pruef(nahe(v, 0.25, 0.01), f"4: Beule steht vor dem Gewaende (w {v})")
    k2, bel = loch_gewaende_spaet(k1, fa)
    dm = float(os.environ.get("MINMM", "0.8")) * float(os.environ.get("SCALE", "87")) / 1000.0
    s = _oberflaeche_w(k2, W, [(-0.7, 24.15), (0.0, 23.8), (0.0, 24.62), (-0.42, 24.62), (-0.7, 23.5), (-2.5, 22.0), (2.3, 22.1), (0.0, 25.4)])
    pruef(nahe(s[0], dm, 0.01), f"4: Beule vor dem Gewaende abgetragen -> Gewaende-Hoehe (w {s[0]}, soll {dm:.3f})")
    pruef(nahe(s[1], -0.12, 0.02), f"4: Loch senkrecht zur Wand, Laibung 0,12 (w {s[1]})")
    pruef(nahe(s[2], -0.12, 0.02), f"4: Stichbogen offen unter dem Scheitel (w {s[2]})")
    pruef(s[3] is not None and s[3] > -0.01, f"4: Bogenzwickel neben dem Scheitel zu (w {s[3]}) - Bogen, kein Rechteck")
    pruef(nahe(s[4], dm, 0.01), f"4: Gewaende neben dem Loch (w {s[4]})")
    pruef(nahe(s[5], 0.0, 0.005), f"4: Wand neben dem Gewaende unveraendert (w {s[5]})")
    pruef(nahe(s[6], 0.2, 0.01), f"4: Beule ausserhalb des Gewaendes bleibt (Kantenbeleg-Sache, w {s[6]})")
    pruef(nahe(s[7], dm, 0.01), f"4: Keilsteinfaecher als Relief (w {s[7]})")
    pruef(len(k2.decompose()) == 1, f"4: ein Koerper ({len(k2.decompose())} Teile)")
    print(f"test_fenster_gewaende_weit: {F} Fehler"); return 1 if F else 0


if __name__ == "__main__": sys.exit(main())
