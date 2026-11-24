#!/usr/bin/env python3
"""test_bogen_fugen.py - fester synthetischer Test: GEMESSENE Fugen zwischen den Bogensteinen der Tore (24.11.2026), < 60 s, nur CPU.

Befund (Nutzer 24.11.: "Fugen zwischen den Bogensteinen sehen"; Regel 15.11.: Bogensteine NIE generieren): tools/bogen_gewaende.py misst je Einzelfoto-Ortho radiale
Fugenlinien im Gewaende-Band, eine Fuge gilt erst mit Mehrfoto-Beleg; bauteile.bogen_gewaende_spaet baut nur diese als Rillen. Teile:
  1 MESSEN     Spitzbogen-Tor, Bogensteine mit UNREGELMAESSIGEN Fugen (Liste unten, keine Teilung), 5 Einzelfotos mit Versatz, Helligkeit, Rauschen; in EINEM Foto
               zusaetzlich ein dunkler Fahrdraht quer durchs Band -> jede echte Fuge +- 3 cm gefunden, keine weitere (Draht nur 1 Foto = kein Beleg), Zahl gleich.
  2 ROT        a) glattes Band ohne Fugen -> keine Fugen, keine Rillen; b) Bruchstein bis ans Loch (kein Band) -> nichts; c) nur 2 Fotos (eins doppelt) -> kein Beleg.
  3 BAUEN      Rillen an den gemessenen Stellen (Oberflaeche dort um die Rillentiefe tiefer), zwischen zwei Fugen glatt, ein Koerper, Breite >= Druckmindestmass,
               Tiefe als ANNAHME vermerkt; zwei Fugen naeher als Rille + Steg -> die schwaecher belegte entfaellt (Vermerk).
"""
import sys, os, json, numpy as np
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(HIER), "tools"))
from pfade import temp_ordner
import bogen_gewaende as BG

U0, U1, Z0, Z1, C = -4.5, 4.5, -0.2, 8.0, 0.01
TOR = dict(art="bogen", form="spitz", u=0.0, breite=4.0, kaempfer=3.5, scheitel=6.2, unten=0.0, tiefe_m=0.6, gebaut=True)
BAND = 0.45
F = 0


def pruef(ok, text):
    global F
    print(("  ok     " if ok else "  FEHLER ") + text)
    if not ok: F += 1


def fugen_soll():
    """Unregelmaessige Fugenlagen (Weg s entlang des Umrisses) im Bogen ueber dem Kaempfer: Abstaende 0,22-0,48 m, fest gewuerfelt (keine Teilung)."""
    Q, N, teil = BG.umriss_pfad(TOR); s_weg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(Q, axis=0), axis=1))]
    ob = np.where(teil == "oben")[0]; s0, s1 = s_weg[ob[0]] + 0.25, s_weg[ob[-1]] - 0.25
    rng = np.random.default_rng(11); s = [s0]
    while s[-1] < s1 - 0.5: s.append(s[-1] + rng.uniform(0.22, 0.48))
    return np.array(s), Q, N, s_weg


def szene(fugen_s, mit_band=True, seed=5, linie=True):
    """Wandbild der Szene (BGR, 1 cm): Bruchstein in Lagen, Spitzbogen-Tor dunkel, Bogensteine (je Stein eine Farbe, Fugen hell an fugen_s) im Band."""
    import cv2
    from bauteile import bogen_querschnitt
    rng = np.random.default_rng(seed); H, W = int(round((Z1 - Z0) / C)), int(round((U1 - U0) / C))
    im = np.zeros((H, W, 3), np.float64) + np.array([150, 160, 170])
    z = Z0
    while z < Z1:
        h = rng.uniform(0.25, 0.40); u = U0 - rng.uniform(0, 0.5)
        while u < U1:
            l = rng.uniform(0.3, 0.8); f = np.array([70, 85, 120]) + rng.normal(0, 18, 3)
            i0, i1 = int((Z1 - (z + h - 0.015)) / C), int((Z1 - z) / C); j0, j1 = int((u - U0) / C), int((u + l - 0.015 - U0) / C)
            im[max(0, i0):max(0, i1), max(0, j0):max(0, j1)] = f; u += l
        z += h
    P = np.array(bogen_querschnitt(TOR["form"], TOR["breite"], TOR["kaempfer"], TOR["scheitel"], TOR["unten"]).to_polygons()[0])
    pts = np.stack([(TOR["u"] + P[:, 0] - U0) / C, (Z1 - P[:, 1]) / C], 1).round().astype(np.int32)
    loch = np.zeros((H, W), np.uint8); cv2.fillPoly(loch, [pts], 1)
    if mit_band:
        Q, N, teil = BG.umriss_pfad(TOR); s_weg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(Q, axis=0), axis=1))]
        rand = np.ones((H, W), np.uint8); idx = np.zeros((H, W), np.int32)
        for k, q in enumerate(Q):
            i, j = int(round((Z1 - q[1]) / C)), int(round((TOR["u"] + q[0] - U0) / C))
            if 0 <= i < H and 0 <= j < W: rand[i, j] = 0; idx[i, j] = k
        dist, lab = cv2.distanceTransformWithLabels(rand, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
        nl = np.zeros(lab.max() + 1, np.int32); nl[lab[rand == 0]] = idx[rand == 0]; s = s_weg[nl[lab]]; d = dist * C
        im_b = (d <= BAND) & (loch == 0)
        fl = np.zeros((H, W), np.uint8)                                             # Fuge = Gerade vom Umrisspunkt entlang der Normalen ueber das Band, 2 cm breit
        for fs in (fugen_s if fugen_s is not None else []):
            i = int(np.argmin(np.abs(s_weg - fs))); a_, b_ = Q[i] - 0.05 * N[i], Q[i] + (BAND + 0.05) * N[i]
            cv2.line(fl, (int(round((TOR["u"] + a_[0] - U0) / C)), int(round((Z1 - a_[1]) / C))), (int(round((TOR["u"] + b_[0] - U0) / C)), int(round((Z1 - b_[1]) / C))), 1, 2)
        _, stein = cv2.connectedComponents((im_b & (fl == 0)).astype(np.uint8), connectivity=4)   # Steine = Bandstuecke zwischen den Fugenlinien
        if not linie:                                                                # ohne Fugenlinie: Linienpixel gehoeren zum naechsten Stein (reine Stufenkante)
            _, nl_ = cv2.distanceTransformWithLabels((fl > 0).astype(np.uint8), cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
            st_ = np.zeros(nl_.max() + 1, np.int32); st_[nl_[fl == 0]] = stein[fl == 0]; stein = st_[nl_]
        farben = np.array([95, 110, 165]) + rng.normal(0, 14, (stein.max() + 1, 3))
        im[im_b] = farben[stein[im_b]] + rng.normal(0, 4, (int(im_b.sum()), 3))
        im[im_b & (d > BAND - 0.015)] = [150, 160, 170]
        if linie: im[im_b & (fl > 0)] = [160, 170, 180]
    im[loch > 0] = [25, 25, 30]
    return np.clip(im, 0, 255)


def foto(szene_bgr, di, dj, gain, seed, draht=False):
    """Einzelfoto-Ortho: Szene um (di, dj) Zellen versetzt (wie fassade_ortho ohne Feinausrichtung), Helligkeit, Rauschen; optional ein Fahrdraht (nur dieses Foto)."""
    import cv2
    rng = np.random.default_rng(seed)
    M_ = np.float32([[1, 0, -dj], [0, 1, -di]]); im = cv2.warpAffine(szene_bgr.astype(np.float32), M_, (szene_bgr.shape[1], szene_bgr.shape[0]), borderMode=cv2.BORDER_REPLICATE)
    im = cv2.GaussianBlur(im, (0, 0), float(rng.uniform(0.8, 1.6)))                 # je Foto andere Schaerfe/Aufloesung (echte Fotos 1122: r 0,5-0,8 untereinander)
    im = im * gain + rng.normal(0, 12, im.shape)
    if draht: cv2.line(im, (0, int((Z1 - 6.4) / C)), (im.shape[1], int((Z1 - 4.6) / C)), (20, 20, 20), 2)
    return np.clip(im, 1, 255).astype(np.uint8)


def ordner(fugen_s, mit_band=True, n_fotos=5, doppel=False):
    import cv2
    d = temp_ordner("test_bogen_fugen_"); fo, ff, au = (os.path.join(d, n) for n in ("fassade", "fassade_fein", "audit"))
    for p in (fo, ff, au, os.path.join(ff, "ortho_f00_einzeln")): os.makedirs(p, exist_ok=True)
    rast = dict(u0=U0, z1=Z1, zelle=C, nu=int((U1 - U0) / C), nz=int((Z1 - Z0) / C))
    json.dump(dict(fassaden=[dict(id="f00", o=[0.0, 0.0], d=[1.0, 0.0], n=[0.0, -1.0], raster=rast)]), open(os.path.join(ff, "fassaden.json"), "w"))
    S = szene(fugen_s, mit_band)
    cv2.imwrite(os.path.join(ff, "ortho_f00_fein.png"), np.clip(S, 1, 255).astype(np.uint8))
    vers = [(0, 0, 1.0), (4, -3, 0.85), (-3, 5, 1.15), (6, 2, 0.95), (-5, -4, 1.05)][:n_fotos]
    for k, (di, dj, g) in enumerate(vers):
        im = foto(S, di, dj, g, 100 + k, draht=(k == 2))
        cv2.imwrite(os.path.join(ff, "ortho_f00_einzeln", f"foto{k}.png"), im)
        if doppel and k == 0: cv2.imwrite(os.path.join(ff, "ortho_f00_einzeln", "foto0_kopie.png"), im)
    oa = os.path.join(au, "oeffnungen_auto.json")
    json.dump({"f00": dict(o=[0.0, 0.0], d=[1.0, 0.0], n=[0.0, -1.0], oeffnungen=[dict(TOR, gewaende_fugen=dict(fugen=[dict(s=1, q=[0, 6], n=[0, 1], fotos=9)]))])}, open(oa, "w"))
    return oa, ff, fo, au


def lauf(oa, ff, au):
    rc = BG.main([oa, ff, "--aus", au]); x = json.load(open(oa))["f00"]["oeffnungen"][0]
    return rc, x, json.load(open(os.path.join(au, "bogen_gewaende.json")))["f00"][0]


def teil_messen():
    print("1 Messen: unregelmaessige Fugen, 5 Einzelfotos, Fahrdraht in einem Foto")
    soll, Q, N, s_weg = fugen_soll()
    oa, ff, fo, au = ordner(soll)
    rc, x, ber = lauf(oa, ff, au)
    G = x.get("gewaende_band"); FG = (x.get("gewaende_fugen") or {}).get("fugen", [])
    pruef(rc == 0 and G is not None, f"Band erkannt (rc {rc})")
    ist = np.array([f["s"] for f in FG])
    treffer = [float(np.min(np.abs(ist - s))) if len(ist) else 9 for s in soll]
    pruef(len(FG) == len(soll), f"Zahl: gemessen {len(FG)} = Foto/Soll {len(soll)}")
    pruef(max(treffer) <= 0.03, f"jede Soll-Fuge +- 3 cm gefunden (groesste Abweichung {max(treffer) * 100:.1f} cm)")
    falsch = [float(s) for s in ist if np.min(np.abs(soll - s)) > 0.03]
    pruef(not falsch, f"keine erfundene Fuge (Draht in 1 Foto kein Beleg) {falsch}")
    pruef(all(f["fotos"] >= BG.FUGE_FOTOS_MIN for f in FG) and all("winkel_grad" in f and "q" in f and "n" in f for f in FG), "je Fuge Winkel, Lage, Normale, Beleg >= 3 Fotos")
    d_ = np.diff(ist) if len(ist) > 2 else np.array([0.0])
    pruef(len(ist) < 3 or np.std(d_) > 0.03, f"Abstaende ungleich wie gemessen (Streuung {np.std(d_):.3f} m) - keine Teilung")
    pruef(x["gewaende_fugen"]["fugen"][0].get("s") != 1, "alte Fugen eines frueheren Laufs ersetzt")
    pruef(os.path.exists(os.path.join(au, "bogen_gewaende_f00.jpg")), "Kontrollbild mit Fugen geschrieben")
    return oa, soll


def teil_rot():
    print("2 Rot-Probe")
    import cv2, bauteile as B
    G = dict(innen=0.03, aussen=BAND)                                              # Band vorgegeben (die Bandmessung selbst braucht Fugen-Kohaerenz)
    for name, stufen in (("a) glattes Band ohne Fugen", False), ("a2) Steine verschiedener Farbe, KEINE Fugenlinie (nur Stufenkanten)", True)):
        oa, ff, fo, au = ordner(np.array([]))
        if stufen:                                                                 # Steinfarben wechseln an den Soll-Stellen, die helle Fugenlinie fehlt
            soll, *_ = fugen_soll(); S = szene(soll, linie=False)
            for k, (di, dj) in enumerate([(0, 0), (4, -3), (-3, 5), (6, 2), (-5, -4)]): cv2.imwrite(os.path.join(ff, "ortho_f00_einzeln", f"foto{k}.png"), foto(S, di, dj, 1.0, 200 + k))
            cv2.imwrite(os.path.join(ff, "ortho_f00_fein.png"), np.clip(S, 1, 255).astype(np.uint8))
        bgr = cv2.imread(os.path.join(ff, "ortho_f00_fein.png")); rs = json.load(open(os.path.join(ff, "fassaden.json")))["fassaden"][0]["raster"]
        fu, fb = BG.fugen_messen(bgr, BG.einzelbilder(ff, "f00"), rs, dict(TOR), G)
        _, geb, _ = B.bogen_fugen_rillen(fu, G["innen"], G["aussen"], 0.07)
        pruef(not fu and not geb, f"{name}: keine Fugen, keine Rillen ({len(fu)} Fugen, {len(fb.get('fotos_benutzt', []))} Fotos)")
    oa, ff, fo, au = ordner(None, mit_band=False)
    rc, x, ber = lauf(oa, ff, au)
    pruef(rc == 3 and "gewaende_band" not in x and "gewaende_fugen" not in x, f"b) Bruchstein bis ans Loch: nichts (rc {rc})")
    soll, *_ = fugen_soll()
    oa, ff, fo, au = ordner(soll, n_fotos=2, doppel=True)
    rc, x, ber = lauf(oa, ff, au)
    pruef("gewaende_fugen" not in x, f"c) 2 Fotos + Kopie: kein Mehrfoto-Beleg ({ber.get('fugen', {}).get('fehler', '')[:60]})")
    pruef(len(ber.get("fugen", {}).get("doppel", [])) == 1, "Kopie als Doppel erkannt, zaehlt nicht")


def teil_bauen(oa, soll):
    print("3 Bauen: Rillen nur an gemessenen Fugen")
    import bauteile as B
    J = json.load(open(oa)); F0 = J["f00"]; o = np.array(F0["o"]); W = B.Wand(o, o + np.array(F0["d"]), aussen=o + np.array(F0["n"]))
    x = F0["oeffnungen"][0]; G = x["gewaende_band"]; FG = x["gewaende_fugen"]["fugen"]
    k = W.kasten(-4.5, 4.5, 0, 8, -2.0, 0.0)
    d = temp_ordner("test_bogen_fugen_bau_"); p = os.path.join(d, "oa.json"); json.dump(J, open(p, "w"))
    k, _, _ = B.oeffnungen_aus_json(k, p)
    J0 = json.loads(json.dumps(J)); J0["f00"]["oeffnungen"][0].pop("gewaende_fugen"); p0 = os.path.join(d, "oa0.json"); json.dump(J0, open(p0, "w"))
    k0, _ = B.bogen_gewaende_spaet(k, p0); k1, bel = B.bogen_gewaende_spaet(k, p)
    m = bel[0]["masse"][0]; dm = float(os.environ.get("MINMM", "0.8")) * float(os.environ.get("SCALE", "87")) / 1000.0
    h = max(G["vorsprung"], dm); tf = m.get("fugen_tiefe", 0)
    pruef(len(k1.decompose()) == len(k0.decompose()) == 1 and k1.volume() < k0.volume(), f"Rillen abgetragen, ein Koerper (-{k0.volume() - k1.volume():.4f} m3)")
    pruef(m.get("fugen_breite", 0) >= dm - 1e-9 and "ANNAHME" in m.get("fugen_tiefe_quelle", ""), f"Breite {m.get('fugen_breite')} >= Druckmindestmass, Tiefe {tf} als ANNAHME")
    mitte = 0.5 * (G["innen"] + G["aussen"])
    an = [(f["q"][0] + mitte * f["n"][0], f["q"][1] + mitte * f["n"][1]) for f in FG[1:-1]]
    zw = []
    for a_, b_ in zip(FG[1:-2], FG[2:-1]):                           # Mitte zwischen zwei Fugen (nur wo der Stein > Rille + 2 cm)
        if b_["s"] - a_["s"] < dm + 0.04: continue
        q = 0.5 * (np.array(a_["q"]) + np.array(b_["q"])); n = 0.5 * (np.array(a_["n"]) + np.array(b_["n"])); n /= np.linalg.norm(n); zw.append((q[0] + mitte * n[0], q[1] + mitte * n[1]))
    w_an = [w for w in B._oberflaeche_w(k1, W, an) if w is not None]; w_zw = [w for w in B._oberflaeche_w(k1, W, zw) if w is not None]
    pruef(w_an and all(abs(w - (h - tf)) < 0.01 for w in w_an), f"an jeder Fuge Rille (w {np.round(w_an[:4], 3)} soll {h - tf:.3f})")
    pruef(w_zw and all(abs(w - h) < 0.01 for w in w_zw), f"zwischen den Fugen glatte Bandflaeche (w {np.round(w_zw[:4], 3)} soll {h:.3f})")
    pruef(m.get("fugen_gebaut") == len(FG), f"gebaut {m.get('fugen_gebaut')} = gemessen {len(FG)}")
    eng = [dict(FG[3], fotos=2, s=FG[3]["s"] + 0.04)] + FG                        # kuenstlich zu nah an einer echten Fuge, schwaecher belegt
    _, geb, weg = B.bogen_fugen_rillen(eng, G["innen"], G["aussen"], dm)
    pruef(len(geb) == len(FG) and len(weg) == 1 and "nicht druckbar" in weg[0], "zu nahe Fuge (Steg < Mindestmass) entfaellt mit Vermerk")
    _, geb0, _ = B.bogen_fugen_rillen([], G["innen"], G["aussen"], dm)
    pruef(not geb0, "ohne Fugen keine Rille")


def main():
    os.environ.setdefault("MINMM", "0.8"); os.environ.setdefault("SCALE", "87")
    oa, soll = teil_messen(); teil_rot(); teil_bauen(oa, soll)
    print("FEHLER gesamt:", F)
    return 1 if F else 0


if __name__ == "__main__": sys.exit(main())
