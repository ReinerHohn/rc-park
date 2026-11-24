#!/usr/bin/env python3
"""test_formsitz_durchblick.py - synthetische Pruefung des Durchblick-Schutzes in tools/formsitz.py (tiefe_vorn / durchblick_fuellen, 24.11.2026).

Befund: Formsitz Ost (1122zb) median |Modell-Wolke| 3,57 m, weil die Ostwand der dichten Wolke 10-50 x duenner belegt ist (250-1300 Punkte/m2
statt 2 500-17 000) - im 8-cm-Pixel keine 3 Stuetzpunkte -> die Tiefe kam von der dichten Westwand 12 m dahinter.
Nachgebaut: Kasten 8 x 8 x 15 m, Kamera 30 m vor der Vorderwand (Pixel ~8 cm).
  A  Vorderwand der Wolke duenn (80 Punkte/m2), Rueckwand dicht -> ohne Schutz: Durchblick (tiefe < 0,3); mit Schutz: tiefe > 0,7
  B  Nullprobe bleibt trennscharf: Modell 1,3 m nach hinten -> tiefe < 0,3 auch mit Schutz
  C  dichte Wand mit 0,5 m tiefer Fensterlaibung: Laibung bleibt fein (Schutz greift nur bei duenner Belegung)
  D  Silhouette waechst nicht (dichtes Modell: belegte Pixel mit/ohne Schutz < 2 % verschieden)
  E  verstreute Einzelpunkte vor der Wand erzeugen keine Flaeche
Nur CPU, wenige Sekunden.
"""
import sys, os
os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import formsitz as FS

F = 0


def pruef(ok, text):
    global F
    print(("    ok    " if ok else "    FEHLER ") + text)
    if not ok: F += 1


def wand(rng, dichte, x, y, z, ach):
    """Rechteckflaeche: ach = Normalenachse (0/1), x/y/z = (lo, hi) oder fester Wert auf der Normalenachse."""
    lo = [x[0], y[0], z[0]]; hi = [x[1], y[1], z[1]]
    fl = np.prod([hi[i] - lo[i] for i in range(3) if i != ach]); n = int(dichte * fl)
    P = rng.uniform(lo, hi, (n, 3)).astype(np.float32); return P


def kasten(rng, d_vorn, d_rest, laibung=False):
    T = [wand(rng, d_vorn, (-4, 4), (0, 0), (0, 15), 1), wand(rng, d_rest, (-4, 4), (8, 8), (0, 15), 1),
         wand(rng, d_rest, (-4, -4), (0, 8), (0, 15), 0), wand(rng, d_rest, (4, 4), (0, 8), (0, 15), 0)]
    P = np.vstack(T)
    if laibung:                                                    # Fenster 1,2 x 1,6 m, 0,5 m tief, in der Vorderwand
        f = (np.abs(P[:, 0]) < 0.6) & (np.abs(P[:, 2] - 7) < 0.8) & (P[:, 1] < 0.01); P = P[~f]
        P = np.vstack([P, wand(rng, d_vorn, (-0.6, 0.6), (0.5, 0.5), (6.2, 7.8), 1)])
    return P


def kamera():
    C = np.array([0.0, -30.0, 7.5]); R = np.array([[1.0, 0, 0], [0, 0, -1.0], [0, 1.0, 0]])     # Blick +y, Bild-y nach unten
    return dict(R=R, t=-R @ C, C=C, f=375.0, cx=200.0, cy=150.0, W=400, H=300, k1=0.0)


def main():
    print("test_formsitz_durchblick:")
    rng = np.random.default_rng(0); cam = kamera()
    M = kasten(rng, 20000, 20000)                                  # Modell dicht
    Wd = kasten(rng, 80, 15000)                                    # Wolke: Vorderwand duenn (wie Ost 1122zb), Rest dicht
    vorn = lambda P, durchblick=True: FS.tiefe_vorn(P, cam, durchblick=durchblick)     # Grobstufen-Fuellung (Standard aus) hier ausdruecklich an
    Dm, Dw0, Dw1 = vorn(M), vorn(Wd, durchblick=False), vorn(Wd)
    e0, e1 = FS.vergleich(Dm, Dw0, None, cam), FS.vergleich(Dm, Dw1, None, cam)
    pruef(e0["tiefe"] < 0.3 and e0["med_dz"] > 5, f"A ohne Schutz Durchblick auf die Rueckwand (tiefe {e0['tiefe']:.2f}, med|dz| {e0['med_dz']:.1f} m)")
    pruef(e1["tiefe"] > 0.7 and e1["med_dz"] < 0.1, f"A mit Schutz duenne Wand gefunden (tiefe {e1['tiefe']:.2f}, med|dz| {e1['med_dz']:.2f} m)")
    Mn = M + np.float32([0, 1.3, 0]); en = FS.vergleich(vorn(Mn), Dw1, None, cam)
    pruef(en["tiefe"] < 0.3, f"B Nullprobe 1,3 m bleibt schlecht (tiefe {en['tiefe']:.2f})")
    ML = kasten(np.random.default_rng(1), 20000, 20000, laibung=True); DL0, DL1 = vorn(ML, durchblick=False), vorn(ML)
    v = 150 + int(round(0.5 * 375 / 30.5))                         # Fenstermitte z 7 (Kamera z 7,5), Bildmitte in u
    fe = DL1[v - 4:v + 5, 196:205]; fe0 = DL0[v - 4:v + 5, 196:205]
    pruef(np.all(np.abs(fe - 30.5) < 0.1) and np.all(np.abs(fe - fe0) < 0.05),
          f"C Laibung 0,5 m bleibt fein (Tiefe {np.median(fe):.2f}, ohne Schutz {np.median(fe0):.2f})")
    n0, n1 = np.isfinite(vorn(M, durchblick=False)).sum(), np.isfinite(Dm).sum()
    pruef(abs(n1 - n0) / n0 < 0.02, f"D Silhouette waechst nicht ({n0} -> {n1} Pixel)")
    G = np.vstack([Wd, rng.uniform([-4, -15, 0], [4, -10, 15], (25, 3)).astype(np.float32)])
    DG = vorn(G); vor = np.isfinite(DG) & (DG < 25)
    pruef(vor.sum() == 0, f"E 25 verstreute Einzelpunkte 10-15 m vor der Wand -> keine Flaeche ({vor.sum()} Pixel)")
    # --- Verdeckung: Fremdbau (Anbau) 6 m vor der unteren Haelfte der Vorderwand, ausserhalb des Vergleichsbereichs
    rng = np.random.default_rng(3)
    Wv = kasten(rng, 15000, 15000); Wv = Wv[~((Wv[:, 1] < 0.01) & (Wv[:, 2] < 8))]          # verdeckter Wandteil fehlt in der Wolke (kein Foto sieht ihn)
    PV = wand(rng, 15000, (-6, 6), (-6, -6), (0, 8), 1)                                    # Anbau-Stirnwand
    Dw, Dv = vorn(Wv, durchblick=False), vorn(PV, durchblick=False); Dm0 = vorn(M, durchblick=False)
    vm = FS.verdeckt_maske(Dv, Dw)
    g0, g1 = FS.vergleich(Dm0, Dw, None, cam), FS.vergleich(Dm0, Dw, None, cam, maske=vm)
    pruef(g0["tiefe"] < 0.6 and g0["a25"] < 0.7, f"V ohne Sichtschutz: unsichtbare Wand verglichen (tiefe {g0['tiefe']:.2f}, a25 {g0['a25']:.2f})")
    pruef(g1["tiefe"] > 0.85 and g1["med_dz"] < 0.1, f"V mit Sichtschutz: nur Sichtbares verglichen (tiefe {g1['tiefe']:.2f}, med|dz| {g1['med_dz']:.2f} m)")
    gn = FS.vergleich(vorn(M + np.float32([0, 1.3, 0]), durchblick=False), Dw, None, cam, maske=vm)
    pruef(gn["tiefe"] < 0.3, f"V Nullprobe 1,3 m bleibt schlecht mit Sichtschutz (tiefe {gn['tiefe']:.2f})")
    ant = vm[np.isfinite(Dm0)].mean()
    pruef(0.3 < ant < 0.7, f"V Anteil verdeckter Modellpixel plausibel ({ant:.2f}, Anbau deckt 8 von 15 m)")
    PH = wand(rng, 15000, (-6, 6), (14, 14), (0, 20), 1)                                    # Haus HINTER dem Objekt verdeckt nichts
    pruef(not FS.verdeckt_maske(vorn(PH, durchblick=False), Dw)[np.isfinite(Dw)].any(), "V Fremdbau hinter dem Objekt verdeckt nichts")
    # --- Durchsicht (Standard): Wolke ohne Vorderwand (wie Ost 1122zb: Anbau und Turmwand nicht rekonstruiert) -> Rueckwand ist Vorderpunkt
    Wn = kasten(np.random.default_rng(4), 15000, 15000); Wn = Wn[Wn[:, 1] > 0.01]
    Dw, Dh = vorn(Wn, durchblick=False), FS.tiefe_hinten(M, cam)
    ds = FS.durchsicht_maske(Dm0, Dh, Dw); ant = ds[np.isfinite(Dm0)].mean()
    pruef(ant > 0.5, f"S Wolke ohne Vorderwand: Durchsicht erkannt ({ant:.2f} der Modellpixel; Rest: Strahl ueber die Rueckwand hinaus = leer, Seitenwaende)")
    pruef(ant > FS.DURCHSICHT_MAX, "S Anteil ueber DURCHSICHT_MAX -> Seite urteilt nicht")
    Dw_ok = vorn(kasten(np.random.default_rng(5), 15000, 15000), durchblick=False)
    a_ok = FS.durchsicht_maske(Dm0, Dh, Dw_ok)[np.isfinite(Dm0)].mean()
    pruef(a_ok < 0.02, f"S vollstaendige Wolke: keine Durchsicht ({a_ok:.3f})")
    for d in (1.3, 3.0):                                            # Modell zu weit AUSSEN (Richtung Kamera) ist ein Modellfehler, keine Durchsicht
        Ma = M + np.float32([0, -d, 0]); Dma = vorn(Ma, durchblick=False)
        aa = FS.durchsicht_maske(Dma, FS.tiefe_hinten(Ma, cam), Dw_ok)[np.isfinite(Dma)].mean()
        pruef(aa < 0.05, f"S Modell {d} m zu weit aussen bleibt Fehler, nicht Durchsicht ({aa:.3f})")
    S0 = dict(seiten={"-y": dict(name="Ost", fotos=["a", "b", "c"])})
    q = dict(formsitz=0.1, formsitz_null=0.05, guete=0.05, tiefe=0.1, deckung=0.9, trennschaerfe=0.6, decke=0.7, decke_null=0.1, relativ=0.1, durchsicht=0.5)
    es = FS.seiten_auswerten(S0, {k: dict(q) for k in "abc"})["-y"]
    pruef(not es["trennt"] and es["status"] == FS.BEZUG_DURCHSICHTIG, f"S Seite mit Durchsicht 0,5 -> '{es['status']}', trennt nicht")
    eu = FS.seiten_auswerten(S0, {k: dict(q, durchsicht=0.2, unbeobachtet=0.6) for k in "abc"})["-y"]
    pruef(not eu["trennt"], f"S verdeckt + durchsichtig 0,6 > UNBEOBACHTET_MAX -> '{eu['status']}'")
    eg = FS.seiten_auswerten(S0, {k: dict(q, durchsicht=0.03, unbeobachtet=0.05) for k in "abc"})["-y"]
    pruef(eg["trennt"], "S kleine Anteile (0,03/0,05 wie Nord/Sued/West 1122zb) -> urteilt weiter")
    print(f"test_formsitz_durchblick: {F} Fehler"); return 1 if F else 0


if __name__ == "__main__":
    sys.exit(main())
