#!/usr/bin/env python3
"""test_bruecke_messen.py - rote Pruefungen der Kettenstufe BRUECKE (27.11.2026, RECHERCHE_BRUECKE_UND_PUTZ_2026-11-27.md A4, SPEC_SCHWABENTOR Anf. 4). CPU, ~1-2 min.

  1 SYNTHETIK   bekannte Bruecke (bauteile.ueberdachter_gang) -> 14 kuenstliche Kameras -> schattierte Fotos mit Stoerlinien/Rauschen -> bruecke_render.abgleich
                (seit 27.11. abends Render-Abgleich statt Profilspitzen; Teile 1+2 dauern ~10 min GPU, nicht im Schnelltest)
                -> Parameter gegen Wahrheit (Toleranzen TOL unten). Fehler 'kamera': alle Kameras 1,2 m verschoben -> muss ROT werden.
  2 TAUSCHTEST  Zone (Suchraum) +-30 % -> dieselben Parameter (tausch_pruefen). Fehler 'zirkulaer': Messung klebt an der Zone -> ROT.
  3 OBERWELLE   14 Stufen, Rauschen auf jeder zweiten Kante, Luecken, Doppelfunde -> 14 (nicht 7/28). Fehler 'autokorr': reiner Autokorrelationsschaetzer -> ROT.
  4 SAEGEZAHN   Treppe und Rampe mit Kerben getrennt. Fehler 'saege': Schaetzer, der nur Hoehen-Spruenge zaehlt -> ROT.
  5 KEIN STILLER FALLBACK  leere Kantenbilder -> 'nicht belegt'; Gang ohne Treppe/mit Ersatzform -> bruecke_tor ROT. Fehler 'still': altes Tor (nur art) -> ROT.
  6 QUELLEN NICHT MITTELN  Spannweite gegen DOM1-Laenge > Toleranz -> Widerspruch (ROT). Fehler 'mitteln': Mittelwert statt Meldung -> ROT.
  8 STRASSENKANTEN  Hoehenkandidaten unter der untersten dichten Wolkenschicht (Strasse/Autos) verworfen, Zone +-30 %. Fehler 'strasse': ohne Veto -> ROT.
  7 DRUCK       Teilung: jedes Teil ein wasserdichter Koerper, <= Bett, Wand >= 0,8 mm. Fehler 'druck': Mindestmass 0,3 mm -> ROT.
Aufruf: test_bruecke_messen.py [--fehler kamera|zirkulaer|autokorr|saege|still|mitteln|druck|strasse] [--nur 1,3,...]  (rc 0 = alle bestanden)
"""
import sys, os, math, copy, json
import numpy as np, cv2
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(HIER), "tools"))
import bauteile as BT
import bruecke_messen as BM
import bruecke_bauen as BB
import bruecke_render as BR

FEHLER = sys.argv[sys.argv.index("--fehler") + 1] if "--fehler" in sys.argv else ""
NUR = set(sys.argv[sys.argv.index("--nur") + 1].split(",")) if "--nur" in sys.argv else None
F = 0


def pruef(name, ok, info=""):
    global F
    print(("  ok     " if ok else "  FEHLER ") + name + (f"  [{info}]" if info else ""), flush=True)
    if not ok: F += 1


# Wahrheit (frei gewaehlte Testzahlen, keine Objektwerte)
P0 = dict(achse=dict(a=[0.0, -12.0], b=[0.0, 12.0]), breite=3.0, z_boden=6.0, hoehe=2.6, boden_dicke=0.6, wand_dicke=0.12, einbinden=0.0,
          dach=dict(form="sattel", neigung_grad=40.0, ueberstand=0.3, dicke=0.12),
          seiten=dict(art="offen", pfosten=9, pfosten_breite=0.16, bruestung=1.0, riegel=0.4))
LAGE = dict(steg=dict(mitte_modell_xy=[0.3, 0.2], achse_modell_xy=[0.0, 1.0], laenge_dach_m=26.0, breite_dach_m=3.6, dach_first_z_m=10.1,
                      deck_unterkante_z_m=5.4, neigung_grad={"a": 0.0}))
TOL = dict(breite=0.2, unterkante=0.15, laufebene=0.15, holm=0.15, traufe=0.4, first=0.2, spannweite=1.2)


def kamera(C, ziel, f=1400.0, W=2000, H=1500):
    C = np.asarray(C, float); z = np.asarray(ziel, float) - C; z /= np.linalg.norm(z); x = np.cross(z, [0, 0, 1.0]); x /= np.linalg.norm(x); y = np.cross(z, x)
    R = np.stack([x, y, z]); return dict(Rn=R.tolist(), tn=(-R @ C).tolist(), C=C.tolist(), f=f, cx=W / 2, cy=H / 2, W=W, H=H, modell="SIMPLE_RADIAL", params=[f, W / 2, H / 2, 0.0])


def kameras(versatz=0.0):
    K = []
    for s in (-10, -5, 0, 5, 10):
        for q in (-18, 18): K.append(kamera([q, s, 1.6], [0, s * 0.5, 7.5]))
    K.append(kamera([8, -26, 3.0], [0, 0, 7.5])); K.append(kamera([-8, 26, 3.0], [0, 0, 7.5]))
    K.append(kamera([-8, -26, 3.0], [0, 0, 7.5])); K.append(kamera([8, 26, 3.0], [0, 0, 7.5]))   # 4 Schraegblicke auf die Giebel (Dachneigung >= 3 Fotos)
    if versatz:                                               # Fehler: Posen 1,2 m daneben (Bild bleibt, Kamera falsch)
        for k in K: C = np.array(k["C"]) + [versatz, 0, versatz * 0.5]; R = np.array(k["Rn"]); k["C"] = C.tolist(); k["tn"] = (-R @ C).tolist()
    return K


def rendern(t, K, seed=0):
    rng = np.random.default_rng(seed); out = []
    for c in K:
        im = np.full((c["H"], c["W"]), 200, np.uint8)
        for _ in range(60):                                   # Stoerkanten (Hintergrund)
            p = rng.uniform([0, 0], [c["W"], c["H"]], (2, 2)).astype(int); cv2.line(im, tuple(p[0]), tuple(p[1]), int(rng.integers(60, 160)), 2)
        C = np.asarray(c["C"]); ks = BB.kanten3d(t, schritt=0.03); P = np.concatenate(ks); d = P - C; dist = np.linalg.norm(d, axis=1); d /= dist[:, None]
        loc, idx, _ = t.ray.intersects_location(np.repeat(C[None], len(P), 0), d, multiple_hits=False)
        first = np.full(len(P), np.inf); first[idx] = np.linalg.norm(loc - C, axis=1); sicht = first >= dist - 0.05
        uv, z = BM.projizieren(c, P); j = 0
        for k in ks:
            n = len(k); u = uv[j:j + n]; s_ = sicht[j:j + n] & (z[j:j + n] > 0.3); j += n
            for i in range(n - 1):
                if s_[i] and s_[i + 1]: cv2.line(im, tuple(np.round(u[i]).astype(int)), tuple(np.round(u[i + 1]).astype(int)), 20, 2)
        out.append(im)
    return out


def rendern_flaechen(t, K, seed=0, n_hinten=60, n_vorne=8, rauschen=4.0):
    """Synthetisches FOTO (nicht Kantenzeichnung): Netz exakt gerastert (render_kern, GPU), Flaechen nach Lichtrichtung schattiert, Stoerlinien hinter
    (Hintergrund) und einige VOR der Bruecke (Aeste/Leitungen), Rauschen. Die Kanten entstehen erst durch die Fotokantensuche (LSD) aus Grauwertspruengen -
    unabhaengig von der Sichtbarkeitsrechnung des Messwerkzeugs (Test 1 vorher: Kantenzeichnung per Strahltest liess Silhouetten an Streifkanten weg)."""
    import render_kern as RK
    rng = np.random.default_rng(seed); out = []; L_ = np.array([0.35, -0.5, 0.8]); L_ /= np.linalg.norm(L_)
    hell = 70 + 150 * np.abs(t.face_normals @ L_)
    for c in K:
        im = np.full((c["H"], c["W"]), 185, np.float32)
        for _ in range(n_hinten):
            p = rng.uniform([0, 0], [c["W"], c["H"]], (2, 2)).astype(int); cv2.line(im, tuple(p[0]), tuple(p[1]), float(rng.integers(60, 160)), 2)
        _, fid, _ = RK.dreiecke_rastern(t, np.array(c["Rn"]), np.array(c["tn"]), c["f"], c["cx"], c["cy"], c["W"], c["H"])
        m = fid >= 0; im[m] = hell[fid[m]]
        for _ in range(n_vorne):
            p = rng.uniform([0, 0], [c["W"], c["H"]], (2, 2)).astype(int); cv2.line(im, tuple(p[0]), tuple(p[1]), float(rng.integers(30, 90)), 3)
        im += rng.normal(0, rauschen, im.shape).astype(np.float32); out.append(np.clip(im, 0, 255).astype(np.uint8))
    return out


def wahrheit(P):
    """Erwartete Messgroessen aus der Wahrheit (dieselben Kanten, die die Messung sucht)."""
    return dict(breite=P["breite"], unterkante=P["z_boden"] - P["boden_dicke"], laufebene=P["z_boden"], holm=P["z_boden"] + P["seiten"]["bruestung"],
                traufe=P["z_boden"] + P["hoehe"], first=None, spannweite=float(np.linalg.norm(np.subtract(P["achse"]["b"], P["achse"]["a"]))))


UNSICHTBAR = ("laufebene",)   # Synthetik hat keine Kamera AUF dem Steg: Bodenoberkante ist von der Strasse nicht zu sehen -> 'fehlt' ist dort richtig, ein Wert muss stimmen


def vergleich(ml, W, name):
    fehl = []
    for k, tol in TOL.items():
        e = ml["parameter"].get(k, {}); v = e.get("wert"); w = W.get(k)
        if w is None: continue
        if e.get("status") == "fehlt" and k in UNSICHTBAR: continue
        if e.get("status") == "fehlt": fehl.append(f"{k} nicht belegt ({e.get('grund', '')[:60]})"); continue
        if v is None or abs(v - w) > tol: fehl.append(f"{k} {v if v is None else round(v, 2)} statt {w:.2f}")
    n = ml["parameter"].get("pfosten", {}).get("wert")
    if n != W["pfosten"]: fehl.append(f"pfosten {n} statt {W['pfosten']}")
    pruef(name, not fehl, "; ".join(fehl) if fehl else ", ".join(f"{k} {ml['parameter'][k]['wert']:.2f}" for k in TOL if ml["parameter"].get(k, {}).get("wert") is not None))
    return not fehl


def main():
    g, _, ms = BT.ueberdachter_gang(P0); t = BT.als_trimesh(g); W = wahrheit(P0); W["pfosten"] = P0["seiten"]["pfosten"]
    W["first"] = P0["z_boden"] + P0["hoehe"] + math.tan(math.radians(40)) * (P0["breite"] / 2 - P0["wand_dicke"]) + ms["dach_dicke"] / math.cos(math.radians(40))
    TOL["first"] = 0.3
    still = lambda *a, **k: None
    if NUR is None or "1" in NUR or "2" in NUR:
        K = kameras(); bilder = rendern_flaechen(t, K)
        print("1 SYNTHETIK schattierte Fotos -> Render-Abgleich (bruecke_render) -> Parameter")
        K1 = kameras(1.2) if FEHLER == "kamera" else K
        zone = BM.zone_aus_lage(LAGE); ml = BR.abgleich(K1, bilder, zone, log=still)
        if ml["status"] != "gemessen": pruef("Synthetik gemessen", False, ml.get("grund", ""))
        else: vergleich(ml, W, "Synthetik: Parameter innerhalb Toleranz" + (" (Fehler kamera eingebaut)" if FEHLER == "kamera" else ""))
        if NUR is None or "2" in NUR:
            print("2 TAUSCHTEST Zone +-30 %")
            if FEHLER == "zirkulaer":                         # Fehler: Messung uebernimmt Zonenwerte (klebt am Vormodell)
                def zirk(zz):
                    m = copy.deepcopy(ml); m["parameter"]["traufe"]["wert"] = zz["z1"] - 1.0; m["parameter"]["breite"]["wert"] = 2 * zz["qmax"] - 2.0; return m
                ml_ = zirk(zone); andere = [zirk(BM.zone_aus_lage(LAGE, f)) for f in (0.7, 1.3)]
            else:
                ml_ = ml; andere = [BR.abgleich(K, bilder, BM.zone_aus_lage(LAGE, f), log=still) for f in (0.7, 1.3)]
            pflicht = [k for k in ("breite", "unterkante", "traufe", "spannweite", "pfosten") if ml_["parameter"].get(k, {}).get("wert") is None]
            pruef("Tauschtest nicht leer (Pflichtmasse gemessen)", not pflicht, "fehlen: " + ", ".join(pflicht))
            BM.tausch_pruefen(ml_, andere); inst = [k for k, v in ml_["parameter"].items() if v.get("status") == "instabil"]
            pruef("Tauschtest: kein Parameter instabil", not inst, ", ".join(f"{k} {ml_['parameter'][k]['wert']:.2f}->{ml_['parameter'][k]['tausch_werte']}" for k in inst))
    if NUR is None or "3" in NUR:
        print("3 TREPPE OBERWELLE")
        rng = np.random.default_rng(3); s = 0.17; z = np.arange(15) * s + 2.0; z[1::2] += rng.uniform(-0.035, 0.035, 7)
        z2 = np.r_[np.delete(z, [4, 9]), z[[2, 7]] + 0.004]
        def autokorr(h, **k):                                  # Fehler: Periode = staerkstes Autokorrelationsmaximum eines Hoehen-Histogramms
            hb = np.histogram(h, bins=np.arange(h.min() - 0.01, h.max() + 0.02, 0.01))[0].astype(float); hb -= hb.mean(); ac = np.correlate(hb, hb, "full")[len(hb):]
            lag = 5 + int(np.argmax(ac[5:])); n = int(round((h.max() - h.min()) / (lag * 0.01))); return dict(stufen=n)
        zaehl = autokorr if FEHLER == "autokorr" else BM.treppe_zaehlen
        for name, zz in (("14 Stufen, jede zweite Kante verrauscht", z), ("dto. mit 2 Luecken + 2 Doppelfunden", z2)):
            n = zaehl(zz)["stufen"]; pruef(f"Oberwelle: {name} -> 14", n == 14, f"gezaehlt {n}")
    if NUR is None or "4" in NUR:
        print("4 SAEGEZAHN gegen TREPPE")
        x = np.linspace(0, 4.2, 2000); a = 0.3; s = 0.18; k = np.floor(x / a)
        treppe = (k + 1) * s; saege = s * (x / a) * 1.0 + 0.0; saege = np.where((x % a) > 0.8 * a, (k + 0.8) * s * 1.0 - (x % a - 0.8 * a) / (0.2 * a) * 0.5 * s, s * (k + (x % a) / a))
        def naiv(xx, zz): return ("treppe", {}) if np.abs(np.diff(zz)).max() > 0.05 else ("rampe", {})
        f = naiv if FEHLER == "saege" else BM.saegezahn_oder_treppe
        art_t = f(x, treppe)[0]; art_s = f(x, saege)[0]
        pruef("Treppe als 'treppe'", art_t == "treppe", art_t); pruef("Rampe mit Kerben als 'saegezahn'", art_s == "saegezahn", art_s)
    if NUR is None or "5" in NUR:
        print("5 KEIN STILLER FALLBACK")
        K = kameras()[:6]; leer = [BM.kantenbild(np.full((1500, 2000), 200, np.uint8)) for _ in K]
        ml, _ = BM.messen(K, leer, BM.zone_aus_lage(LAGE), z_strasse=0.9, log=still)
        pruef("leere Zone -> 'nicht belegt' (kein Kasten)", ml["status"] == "nicht belegt", ml["status"])
        tor = BT.bruecke_tor
        if FEHLER == "still": tor = lambda m, **k: dict(status="ROT" if m.get("art") == "nicht gebaut" else "GRUEN", rot=[])   # altes Verhalten: nur 'nicht gebaut' zaehlt
        _, _, m1 = BT.ueberdachter_gang(P0); r1 = tor(m1)
        pruef("Gang ohne Treppenblock -> ROT 'treppe'", r1["status"] == "ROT" and any(r["bauteil"] == "treppe" for r in r1["rot"]), str([r["bauteil"] for r in r1["rot"]]))
        P2 = copy.deepcopy(P0); P2["dach"]["neigung_grad"] = 90; _, _, m2 = BT.ueberdachter_gang(P2); r2 = tor(m2)
        pruef("ungueltige Dachneigung (Flachdach-Ersatz) -> ROT 'dach'", any(r["bauteil"] == "dach" for r in r2["rot"]), str([r["bauteil"] for r in r2["rot"]]))
        P3 = copy.deepcopy(P0); P3["breite"] = 0.2; _, _, m3 = BT.ueberdachter_gang(P3); r3 = tor(m3)
        pruef("zu schmal (massiver Steg) -> ROT 'gang'", any(r["bauteil"] == "gang" for r in r3["rot"]), str([r["bauteil"] for r in r3["rot"]]))
        P4 = copy.deepcopy(P0); P4["fehlt"] = [dict(bauteil="holm", grund="nicht gemessen")]; _, _, m4 = BT.ueberdachter_gang(P4); r4 = tor(m4)
        pruef("Massliste 'fehlt: holm' -> ROT 'holm'", any(r["bauteil"] == "holm" for r in r4["rot"]), str([r["bauteil"] for r in r4["rot"]]))
    if NUR is None or "6" in NUR:
        print("6 QUELLEN NICHT MITTELN")
        import tempfile
        d = tempfile.mkdtemp(); lp = os.path.join(d, "lage.json"); json.dump(LAGE, open(lp, "w"))
        ml = dict(lage=lp, parameter=dict(spannweite=dict(wert=24.0)))
        gp = BB.gegenprobe_lage(ml, toleranz=1.0)
        if FEHLER == "mitteln": gp = dict(widerspruch=False, wert=0.5 * (24.0 + 26.0))
        pruef("Spannweite 24 gegen DOM1 26 -> Widerspruch gemeldet (kein Mittelwert)", gp and gp.get("widerspruch") and "wert" not in gp, str(gp)[:120])
        ml["parameter"]["spannweite"]["wert"] = 25.6; gp = BB.gegenprobe_lage(ml, toleranz=1.0)
        pruef("Spannweite 25,6 gegen 26 -> kein Widerspruch", gp and not gp["widerspruch"], str(gp)[:80])
    if NUR is None or "7" in NUR:
        print("7 DRUCK (Teilung, wasserdicht, Mindestmass)")
        mm = 0.3 if FEHLER == "druck" else 0.8
        P5 = copy.deepcopy(P0); P5["wand_dicke"] = 0.01; P5["dach"]["dicke"] = 0.01
        Q = BB.lokal_param(P5); gl, _, msl = BT.ueberdachter_gang(Q, min_mm=mm)
        tei, teile = BB.teilen(gl, Q, msl, bett=250.0, rand=10.0)
        pruef(f"{tei['teile_n']} Teile, jedes ein wasserdichter Koerper <= Bett", all(t_["ok"] for t_ in teile), str([(t_["mass_mm"], t_["wasserdicht"], t_["koerper"]) for t_ in teile]))
        wd = msl["wand_dicke"] * 1000 / 87.0
        pruef("Wand-/Pfostendicke >= 0,8 mm (H0)", wd >= 0.8 - 1e-9, f"{wd:.2f} mm")
    if NUR is None or "8" in NUR:
        print("8 STRASSENKANTEN (Lichtraum-Veto aus der Wolke)")
        rng = np.random.default_rng(8); R = BM.zone_aus_lage(LAGE)["rahmen"]
        def wolke(n, s0, s1, q, z0, z1): return R.welt(rng.uniform(s0, s1, n), rng.uniform(-q, q, n), rng.uniform(z0, z1, n))
        X = np.concatenate([wolke(300, -12, 12, 6, 0.8, 1.0), wolke(400, -12, 12, 6, 1.0, 2.3), wolke(200, -12, 12, 6, 2.3, 4.5),   # Strasse, Autos, Streu
                            wolke(20000, -12, 12, 1.5, 5.4, 6.0), wolke(8000, -12, 12, 1.5, 6.0, 9.9)])                              # Deck, Waende/Dach
        kand = [1.78, 1.98, 2.16, 5.40, 7.00, 8.60]
        for f in (0.7, 1.0, 1.3):
            lr = None if FEHLER == "strasse" else BR.lichtraum_unterkante(X, BM.zone_aus_lage(LAGE, f))
            bleib = [h for h in kand if lr is None or h >= lr["deck_unten"] - 0.3]
            pruef(f"Zone x{f}: Strassenkanten verworfen, Deck-Unterkante 5,40 bleibt", bleib == [5.40, 7.00, 8.60], f"{lr} -> {bleib}")
    print("ERGEBNIS:", "alle Pruefungen bestanden" if F == 0 else f"{F} FEHLER" + (f" (eingebauter Fehler '{FEHLER}')" if FEHLER else ""))
    return 0 if F == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
