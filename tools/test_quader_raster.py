#!/usr/bin/env python3
"""Test tools/quader_raster.py (21.11.2026, Schwabentor Stadtseite: Quader 'geschmolzen', Eckquader 'Rauschen'). Synthetisch, numpy/scipy/PIL, < 30 s.
A) Wandbild-Raster 1 cm, 4 x 4 m Quaderwerk, Lagen 30-45 cm, Fugen 2 cm dunkel, drei Einzelfotos (eines mit Verkehrsschild = nur in EINEM Foto).
   Tiefe wie im Mischrelief w01: Steinfronten +-3 cm + grosse Beule +-8 cm + 1-cm-Rauschen, Fugen nur 1 cm tief (= 0,1 mm H0).
   Erwartet: Lagerfugen >= 80 % auf 3 cm, jeder Stein eben mit Front = Median der Tiefe im Stein, Rillen >= 0,8 mm x 87 breit / >= 0,4 mm x 87 tief,
   Eckquader lang/kurz mit gemessener Laenge und Zahnung, Relief ohne Steine unveraendert.
B) Ende-zu-Ende quader_auf_relief mit einem synthetischen fassade_fein-Ordner (fassaden.json + ortho_f00_einzeln/*.png): unten Quaderwerk, darueber 1,6 m glatter
   Putz, oben ein Wandgemaelde (weiche Farbverlaeufe). Wand ohne Quader-Tor (zone_unten): Steine nur unten, keine im Gemaelde (Probe f00 w02: Vordach-Ziegel/Gemaelde
   bekamen Steine); nur_in begrenzt auf die belegte Flaeche.
Aufruf: ~/.venvs/rcpark/bin/python -I tools/test_quader_raster.py (rc 0 = ok)"""
import sys, os, numpy as np
from scipy import ndimage as ndi
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pfade import temp_ordner                                         # 22.11.2026: Temp nicht auf Root, beim Ende aufgeraeumt (auch nach assert)
import quader_raster as Q


def wand(rng, c=0.01, B=4.0, Hm=4.0):
    nz, nu = int(Hm / c), int(B / c); lab = np.zeros((nz, nu), np.int32); fuge = np.zeros((nz, nu), bool); lager = []; z = 0.0; k = 0
    while z < Hm - 0.05:
        h = rng.uniform(0.30, 0.45); r1 = nz - int(z / c); r0 = max(nz - int((z + h) / c), 0); lager.append(r0); x = 0.0
        while x < B:
            L = (0.60 if k % 2 == 0 else 0.30) if x == 0.0 else rng.uniform(0.45, 0.85)      # Eckstein am Wandanfang: lang/kurz je Lage im Wechsel
            c0, c1 = max(int(x / c), 0), min(int((x + L) / c), nu)
            if c1 > c0: lab[r0:r1, c0:c1] = lab.max() + 1; fuge[r0:r1, max(c1 - 2, 0):c1] = True
            x += L
        fuge[r0:min(r0 + 2, nz), :] = True; z += h; k += 1
    lab[fuge] = 0; return lab, fuge, lager


def teil_b(rng, basis_mauer, lab_mauer, c=0.01):
    """Ende-zu-Ende mit synthetischem Wandbild-Ordner; liefert Fehlerliste."""
    import json, tempfile, shutil
    from PIL import Image
    nz, nu = 600, 400; mauer = int(1.4 / c); putz_bis = int(3.0 / c)          # z 0-1,4 Quader, 1,4-3,0 Putz, 3,0-6,0 Gemaelde
    bild = np.empty((nz, nu)); bild[nz - mauer:] = basis_mauer[basis_mauer.shape[0] - mauer:]; bild[nz - putz_bis:nz - mauer] = 205.0
    farbe = ndi.gaussian_filter(rng.normal(0, 1, (nz, nu)), 8.0); pin = ndi.gaussian_filter(rng.normal(0, 1, (nz, nu)), 1.5); bild[:nz - putz_bis] = (135 + farbe / farbe.std() * 45 + pin / pin.std() * 18)[:nz - putz_bis]      # Gemaelde: Verlaeufe + Pinselstruktur (Wandbild liest es als 'rau')
    d = temp_ordner("quader_raster_"); ffn = os.path.join(d, "fassade_fein"); os.makedirs(os.path.join(ffn, "ortho_f00_einzeln")); fe = []
    try:
        json.dump(dict(fassaden=[dict(id="f00", n=[0.0, -1.0], d=[1.0, 0.0], o=[0.0, 0.0], raster=dict(u0=0.0, z1=6.0, nu=nu, nz=nz, zelle=c))]), open(os.path.join(ffn, "fassaden.json"), "w"))
        for k in range(4):
            Image.fromarray(np.clip(bild + rng.normal(0, 6, bild.shape), 1, 255).astype(np.uint8)).save(os.path.join(ffn, "ortho_f00_einzeln", f"f{k}.png"))
        H, W = 300, 200; Z = dict(rel=rng.normal(0, 0.03, (H, W)).astype(np.float32), a=np.array([0.0, 0.0]), t=np.array([1.0, 0.0]), n=np.array([0.0, -1.0]), u0=0.0, z0=0.0, px=0.02,
                                  oeffnung=np.zeros((H, W), bool), wand=np.ones((H, W), bool))
        h, info = Q.quader_auf_relief(Z, ffn, zone_unten=os.environ.get("TEST_OHNE_ZONE") != "1")
        if h is None: return [f"Teil B: kein Ergebnis ({info})"]
        lab = info["lab"]; zz = (H - 1 - np.arange(H) + 0.5) * 0.02; oben = zz > 1.6
        print(f"    Teil B: {info.get('relief_steine')} Steine, Steinzone z {info.get('steinzone_z')}, weg (Zone) {info.get('weg_zone')}, Steine oberhalb 1,6 m: {(lab[oben] > 0).mean() * 100:.1f} %, unten belegt {(lab[~oben] > 0).mean() * 100:.0f} %")
        if (lab[oben] > 0).mean() > 0.01: fe.append(f"Teil B: Putz/Gemaelde zu {(lab[oben] > 0).mean() * 100:.0f} % mit Steinen")
        if (lab[zz < 1.3] > 0).mean() < 0.5: fe.append(f"Teil B: Quaderwerk unten nur zu {(lab[zz < 1.3] > 0).mean() * 100:.0f} % mit Steinen")
        links = np.zeros((H, W), bool); links[:, : W // 2] = True
        h2, info2 = Q.quader_auf_relief(Z, ffn, zone_unten=True, nur_in=links)
        if h2 is not None and (info2["lab"][:, W // 2 + 10:] > 0).any(): fe.append("Teil B: nur_in nicht beachtet (Steine rechts)")
        if h is not None and np.allclose(h[oben], Z["rel"][oben]) is False: fe.append("Teil B: Relief ausserhalb der Steine veraendert")
        # Zone von unten: oben (z 3-4 m) ECHTES Quaderwerk ueber 1,6 m Putz (wie w02: Quader unten, Putz/Vordach, darueber Ziegel/Gemaelde mit 'Raster').
        # Ohne zone_unten muss es oben Steine geben (Gegenprobe), mit zone_unten nicht.
        bild[:nz - putz_bis] = basis_mauer[: nz - putz_bis]
        for k in range(4): Image.fromarray(np.clip(bild + rng.normal(0, 6, bild.shape), 1, 255).astype(np.uint8)).save(os.path.join(ffn, "ortho_f00_einzeln", f"f{k}.png"))
        Q.PW._CACHE.clear() if hasattr(Q, "PW") else None
        import putz_wandbild; putz_wandbild._CACHE.clear()
        _, i_aus = Q.quader_auf_relief(Z, ffn, zone_unten=False); _, i_an = Q.quader_auf_relief(Z, ffn, zone_unten=True)
        ob_aus = (i_aus["lab"][zz > 3.0] > 0).mean() if "lab" in i_aus else 0.0; ob_an = (i_an["lab"][zz > 3.0] > 0).mean() if "lab" in i_an else 0.0
        print(f"    Teil B Zone: Quaderwerk oben belegt ohne zone_unten {ob_aus * 100:.0f} %, mit {ob_an * 100:.0f} %")
        if ob_aus < 0.3: fe.append(f"Teil B Gegenprobe: oberes Quaderwerk ohne zone_unten nur {ob_aus * 100:.0f} % (Test zeigt nichts)")
        if ob_an > 0.01: fe.append(f"Teil B: zone_unten laesst oberhalb der Putzluecke {ob_an * 100:.0f} % Steine")
    finally: shutil.rmtree(d, ignore_errors=True)
    return fe


def main():
    rng = np.random.default_rng(3); c = 0.01; lab_w, fuge_w, lager = wand(rng); nz, nu = lab_w.shape; fe = []
    basis = np.where(lab_w > 0, 120.0, 55.0) + ndi.gaussian_filter(rng.normal(0, 1, lab_w.shape), 1.5) * 25
    bilder = []
    for k in range(3):
        b = np.clip(basis + rng.normal(0, 6, basis.shape), 1, 255)
        if k == 1: yy, xx = np.mgrid[0:nz, 0:nu]; b[(yy - 260) ** 2 + (xx - 120) ** 2 < 30 ** 2] = 250.0      # Schild nur in diesem Foto
        b[:, : int(0.02 / c)] = 0.0 if k == 2 else b[:, : int(0.02 / c)]                                  # schwarzer Rand = nicht gesehen
        bilder.append(b.astype(np.float32))
    ant, n = Q.fugen_antwort(bilder, c)
    stein = np.ones(lab_w.shape, bool)
    lab, fuge, info = Q.raster_segmentieren(ant, stein, c)
    print(f"    Raster: {info['steine']} Steine, Polaritaet {info['polaritaet']}, Lagen {len(info['lagen_m'])}, verworfen {info['verworfen']}")
    if info["polaritaet"] != "dunkel": fe.append(f"Polaritaet {info['polaritaet']} statt dunkel")
    gef = np.flatnonzero(fuge[:, : int(2.5 / c)].mean(1) > 0.5); innen = [r for r in lager if 5 < r < nz - 5]
    treff = np.mean([np.abs(gef - (r + 0.5)).min() * c <= 0.03 if len(gef) else False for r in innen]); print(f"    Lagerfugen getroffen {treff * 100:.0f} % von {len(innen)}")
    if treff < 0.8: fe.append(f"Lagerfugen nur {treff * 100:.0f} % getroffen")
    # Tiefe wie im Mischrelief: Front je Stein +-3 cm, Beule +-8 cm (Massstab 1,2 m), Rauschen 1 cm, Fugen 1 cm tief
    front = np.r_[0.0, rng.uniform(-0.03, 0.03, lab_w.max())]; yy, xx = np.mgrid[0:nz, 0:nu] * c
    tiefe = front[lab_w] + 0.08 * np.sin(xx / 1.2 * np.pi) * np.cos(yy / 1.5 * np.pi) + rng.normal(0, 0.01, lab_w.shape) - 0.01 * fuge_w
    h, qi = Q.quader_relief(tiefe, lab, c)
    print(f"    Relief: Rillen {qi['rille_mm']} mm H0 (Breite, Tiefe), Fronten p5-p95 {qi['front_p5_p95_m']} m, Rillenanteil {qi['rillen_anteil']}")
    br, ti = Q.druckmass()
    if qi["rille_breite_m"] < br - 1e-9 or qi["rille_tiefe_m"] < ti - 1e-9: fe.append(f"Rille unter Druckmass: {qi['rille_breite_m']} / {qi['rille_tiefe_m']} m")
    idx = np.arange(1, lab.max() + 1); fr = np.asarray(ndi.maximum(h, lab, idx)); kern = (lab > 0) & (h >= np.r_[0.0, fr][lab] - 1e-7)      # Stirnflaeche = hoechste Ebene je Stein, Rille darunter
    anteil_kern = np.asarray(ndi.mean(kern.astype(float), lab, idx)); med = np.asarray(ndi.median(tiefe, lab, idx))
    if np.median(anteil_kern) < 0.4: fe.append(f"Steine nicht eben: Stirnflaeche nur {np.median(anteil_kern) * 100:.0f} % des Steins")
    if np.abs(fr - med).max() > 1e-5: fe.append(f"Stirnflaeche ist nicht der Median der Tiefe im Stein (bis {np.abs(fr - med).max() * 100:.2f} cm daneben)")
    # Rillentiefe: Zellen mitten auf einer Lagerfuge im Mauerwerk
    r_ = [r for r in innen][2]; zeile = h[r_, int(0.2 / c): int(2.3 / c)]; nb = np.minimum(h[r_ - 6, int(0.2 / c): int(2.3 / c)], h[r_ + 6, int(0.2 / c): int(2.3 / c)])
    if np.median(nb - zeile) < ti - 0.002: fe.append(f"Rille auf der Lagerfuge nur {np.median(nb - zeile) * 100:.1f} cm tief (Soll >= {ti * 100:.1f})")
    # Eckquader: Wandanfang, Steine lang 0,60 / kurz 0,30 abwechselnd (wand(): erster Stein je Lage)
    E = Q.eckquader_bloecke(lab, c, 0.0, True, False).get("anfang", {}); print(f"    Eckquader: lang {E.get('lang_m')} kurz {E.get('kurz_m')} Zahnung {E.get('zahnung')} ({len(E.get('bloecke', []))} Bloecke)")
    if not E or abs((E.get("lang_m") or 0) - 0.6) > 0.08 or abs((E.get("kurz_m") or 0) - 0.3) > 0.08 or (E.get("zahnung") or 0) < 0.6: fe.append(f"Eckquader nicht gemessen: {dict((k, E.get(k)) for k in ('lang_m', 'kurz_m', 'zahnung'))}")
    # quader_relief ohne Steine laesst das Relief unveraendert
    h0, _ = Q.quader_relief(tiefe, np.zeros_like(lab), c)
    if not np.allclose(h0, tiefe.astype(np.float32)): fe.append("Relief ohne Steine veraendert")
    fe += teil_b(rng, basis, lab_w)
    for x in fe: print("FEHLER", x)
    if not fe:
        for t in ("Lagerfugen aus Mehrfoto-Antwort (Schild in einem Foto stoert nicht)", "Gemaelde/Putz ohne erfundene Steine (zone_unten), nur_in", "Steine eben = Median", "Rillen druckbar", "Eckquader lang/kurz gemessen", "ohne Steine unveraendert"): print("    ok", t)
    return 1 if fe else 0


if __name__ == "__main__":
    sys.exit(main())
