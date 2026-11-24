#!/usr/bin/env python3
"""test_traufe_aus_fotos.py - Traufe des Hauptdachs aus Fotokanten (tools/traufe_aus_fotos.py, bauteile.traufkasten/traufe_einbauen, hand_vergleich), 21.11.2026.
Anlass Schwabentor-1120 (Nutzer "noch nicht gut"): Foto dicke dunkle Traufe, Modell duenne 2-cm-Scheibe; Ueberstand nur "aus der Wolke (vorlaeufig)".
Synthetisch: Turmseite +n (Wandebene 0,3 m hinter wand_halb), dunkle Untersicht vom Wandanschluss (z 29,5) zur Stirn (a 0,7, z 30,4..31,0), Dach 52 Grad, Himmel;
Kameras 1,6 m hoch in 8..80 m Abstand (Hoehenwinkel ~19..74 Grad), Bilder per Strahlschnitt gerendert, Rauschen.
  T1 Wandanschluss / Aussenkante auf +-0,1 m, Ueberstand 1,0 +-0,12; Stirn heller als Untersicht -> Unterkante gemessen (+-0,12)
  T2 Stirn so dunkel wie die Untersicht -> Unterkante NICHT erfunden (None), Seite trotzdem gueltig, Bau mit Druckmindestmass
  T3 alle Kameras gleicher Hoehenwinkel -> ungueltig (keine Triangulation); T4 5 Fotos -> ungueltig (Formfamilie)
  T5 Generator: Koerper steht in Stirnhoehe bis zur gemessenen Aussenkante, ungemessene Seite bleibt bei der Wolkenscheibe, Belege nennen beides
  T6 hand_vergleich wertet zeltdach_ueberstand "aus Fotos" (Quelle foto), ohne gueltigen Block weiter "wolke".
  T8 (24.11.2026) Stirn-Unterkante aus den 3D-Kanten der Kantenstufe (Traufzone): gefunden, ersetzt die ANNAHME; Guards Formfamilie/Linie/Rauschen/ohne Datei."""
import os, sys, json, math, tempfile, subprocess, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cv2, flaeche_ortho as FO, traufe_aus_fotos as T

fehler = []
def pruef(ok, text):
    print(("  ok    " if ok else "  FEHLER ") + text)
    if not ok: fehler.append(text)

H, A_W, Z_W, A_O, Z_U, Z_O, NEIG = 5.0, -0.3, 29.5, 0.7, 30.4, 31.0, math.radians(52)
D = dict(o=[0.0, 0.0], d=[1.0, 0.0], n=[0.0, 1.0], wand_halb=[H, H], z0=30.0, schritt=0.5)
YW, YO = H + A_W, H + A_O
POLY = [(YW, 0.0), (YW, Z_W), (YO, Z_U), (YO, Z_O), (0.0, Z_O + YO * math.tan(NEIG)), (-20.0, Z_O + YO * math.tan(NEIG))]   # Querschnitt (y, z), in x unendlich


def kamera(dist, x, hoehe=1.6, W=640, Hb=480):
    C = np.array([x, H + dist, hoehe]); ziel = np.array([0.0, H, 30.2]); zv = ziel - C; zv /= np.linalg.norm(zv)
    xv = np.cross(zv, [0, 0, 1.0]); xv /= np.linalg.norm(xv); yv = np.cross(zv, xv); Rm = np.stack([xv, yv, zv]); f = 420.0 * np.linalg.norm(ziel - C) / 30.0
    return dict(rvec=cv2.Rodrigues(Rm)[0].ravel().tolist(), t=(-Rm @ C).tolist(), f_px=f, cx=W / 2, cy=Hb / 2, k1=0.0, bild=[W, Hb]), C, Rm


def rendern(c, C, Rm, stirn=120.0, rng=None):
    W, Hb = c["bild"]; u, v = np.meshgrid(np.arange(W) + 0.5, np.arange(Hb) + 0.5); r = np.stack([(u - c["cx"]) / c["f_px"], (v - c["cy"]) / c["f_px"], np.ones_like(u)], -1) @ Rm
    ry, rz = r[..., 1], r[..., 2]; best = np.full(u.shape, np.inf); wer = np.full(u.shape, -1)
    for k, ((y0, z0), (y1, z1)) in enumerate(zip(POLY[:-1], POLY[1:])):        # Strahl (C_y + l ry, C_z + l rz) gegen Strecke
        ey, ez = y1 - y0, z1 - z0; den = ry * (-ez) - rz * (-ey)
        with np.errstate(divide="ignore", invalid="ignore"):
            l = ((y0 - C[1]) * (-ez) - (z0 - C[2]) * (-ey)) / den; s = (ry * (z0 - C[2]) - rz * (y0 - C[1])) / den
        hit = (np.abs(den) > 1e-12) & (l > 0) & (s >= 0) & (s <= 1) & (l < best); best[hit] = l[hit]; wer[hit] = k
    farbe = np.array([190.0, 45.0, stirn, 80.0, 80.0]); im = np.where(wer >= 0, farbe[np.clip(wer, 0, 4)], np.where(rz > 0, 235.0, 110.0))
    if rng is not None: im = im + rng.normal(0, 4, im.shape)
    return cv2.GaussianBlur(np.clip(im, 0, 255).astype(np.uint8), (0, 0), 0.8)


def messen(kams, stirn=120.0, min_fotos=10):          # synthetisch rauschfrei genug fuer 10 Fotos; die echte Schwelle (MIN_FOTOS) prueft T4b
    rng = np.random.default_rng(1); o = np.array(D["o"]); e, t, h, hl = T.rahmen(D, "+n"); A, Z = T.gitter(D["z0"]); Ms, SGs, EL = [], [], []
    for dist, x in kams:
        c, C, Rm = kamera(dist, x); im = rendern(c, C, Rm, stirn, rng)
        r = T.foto_karte(im, lambda X, c=c: FO.projektion(X, c)[:2], o, e, t, h, hl, A, Z)
        if r is None: continue
        Ms.append(r[0]); SGs.append(r[1]); EL.append(math.degrees(math.atan2(D["z0"] - C[2], dist)))
    if os.environ.get("TRAUFE_DUMP") and Ms: np.savez(os.environ["TRAUFE_DUMP"] + f"_{len(Ms)}_{int(stirn)}.npz", A=A, Z=Z, M=np.array(Ms), SG=np.array(SGs), EL=np.array(EL), S=T._summe(np.array(Ms, float), np.ones(len(Ms), bool)))   # Diagnose
    return T.auswerten(A, Z, np.array(Ms), np.array(SGs), np.array(EL), min_fotos=min_fotos) if Ms else dict(gueltig=False, grund="keine Deckung")


KAMS = [(dd, x) for dd, x in zip((8, 10, 12, 15, 18, 22, 27, 33, 40, 50, 62, 80), (-2, 1, 3, -1, 2, -3, 0, 2, -2, 1, -1, 3))]
E = messen(KAMS)
print("  T1:", {k: E.get(k) for k in ("gueltig", "a_wand", "z_wand", "a_aussen", "z_oben", "z_unten", "ueberstand", "untersicht_grad", "grund", "kandidaten", "stirn_suche")})
pruef(E.get("gueltig") is True, f"T1 Seite gueltig ({E.get('grund')})")
pruef(E.get("a_wand") is not None and abs(E["a_wand"] - A_W) <= 0.1 and abs(E["z_wand"] - Z_W) <= 0.1, f"T1 Wandanschluss a {E.get('a_wand')} z {E.get('z_wand')} (Soll {A_W} / {Z_W} +- 0,1)")
pruef(E.get("a_aussen") is not None and abs(E["a_aussen"] - A_O) <= 0.1 and abs(E["z_oben"] - Z_O) <= 0.1, f"T1 Aussenkante a {E.get('a_aussen')} z {E.get('z_oben')} (Soll {A_O} / {Z_O} +- 0,1)")
pruef(E.get("ueberstand") is not None and abs(E["ueberstand"] - (A_O - A_W)) <= 0.12, f"T1 Ueberstand {E.get('ueberstand')} (Soll {A_O - A_W:.2f} +- 0,12)")
pruef(E.get("z_unten") is not None and abs(E["z_unten"] - Z_U) <= 0.12, f"T1 Stirn-Unterkante {E.get('z_unten')} (Soll {Z_U} +- 0,12, Stirn heller als Untersicht)")
E2 = messen(KAMS, stirn=45.0)
pruef(E2.get("gueltig") is True and E2.get("z_unten") is None and abs(E2.get("z_unten_bau", 0) - (E2.get("z_oben", 0) - T.STIRN_MIN_M)) < 1e-6,
      f"T2 Stirn wie Untersicht: Unterkante nicht erfunden (z_unten {E2.get('z_unten')}, Bau {E2.get('z_unten_bau')}), gueltig {E2.get('gueltig')}")
E3 = messen([(20, x) for x in (-3, -2, -1, 0, 1, 2, 3, -2.5, 2.5, 0.5)])
pruef(E3.get("gueltig") is False, f"T3 gleicher Hoehenwinkel -> ungueltig ({E3.get('grund')})")
E4 = messen(KAMS[::3][:5] if len(KAMS[::3]) >= 5 else KAMS[:5])
pruef(E4.get("gueltig") is False, f"T4 nur 5 Fotos -> ungueltig ({E4.get('grund')})")
E4b = messen(KAMS, min_fotos=T.MIN_FOTOS)
pruef(E4b.get("gueltig") is False and T.MIN_FOTOS >= 20, f"T4b 12 Fotos unter der echten Schwelle MIN_FOTOS {T.MIN_FOTOS} -> ungueltig ({E4b.get('grund')})")

# ---- T5 Generator --------------------------------------------------------------------------------------------------------------------------
if not E.get("gueltig"): print(f"FEHLER: {len(fehler)} (T5/T6 ohne gueltige Messung uebersprungen)"); sys.exit(1)
import bauteile as BT
from manifold3d import Manifold as M
sch = [[round(z, 2), -(H + 0.5) + 1.28 ** -1 * 0 - (z - 30.0) / math.tan(NEIG), (H + 0.5) - (z - 30.0) / math.tan(NEIG), -(H + 0.5) + (z - 30.0) / math.tan(NEIG), (H + 0.5) - (z - 30.0) / math.tan(NEIG), 500, []]
       for z in np.arange(30.0, 34.01, 0.5)]
blk = dict(gueltig=True, seiten={"+n": E, "-n": dict(gueltig=False, grund="keine Kamera sieht die Traufe dieser Seite")}, gueltige_seiten=["+n"])
with tempfile.TemporaryDirectory() as td:
    pj = os.path.join(td, "dach_profil.json"); json.dump(dict(D, scheiben=sch, traufe_foto=blk), open(pj, "w"))
    k, bel = BT.dach_aus_profil(M.cube((2 * H, 2 * H, 32)).translate((-H, -H, 0)), pj)
    def ausdehnung(z): b = k.slice(z).bounds(); return b
    b = ausdehnung((E["z_unten_bau"] + E["z_oben"]) / 2)
    pruef(abs(b[3] - (H + E["a_aussen"])) <= 0.03, f"T5 Koerper in Stirnhoehe bis y {b[3]:.2f} (Soll Aussenkante {H + E['a_aussen']:.2f})")
    pruef(abs(-b[1] - (H + 0.5 - (((E['z_unten_bau'] + E['z_oben']) / 2) - 30.0) / math.tan(NEIG))) <= 0.35, f"T5 ungemessene Seite -n bleibt bei der Wolkenscheibe (y {b[1]:.2f})")
    bz = ausdehnung(E["z_wand"] + 0.05)
    pruef(bz[3] <= H + 0.02, f"T5 knapp ueber dem Wandanschluss keine Platte vor der Wand (y {bz[3]:.2f}, Untersicht steigt nach aussen)")
    pruef(any("Traufkasten +n aus Fotos" in x["element"] for x in bel) and any("NICHT aus Fotos" in x["element"] and "-n" in x["element"] for x in bel), "T5 Belege: +n aus Fotos, -n ehrlich nicht")
    pruef(k.genus() >= 0 and k.num_vert() > 0 and k.status().name == "NoError", "T5 Koerper gueltig")
    # ---- T6 hand_vergleich --------------------------------------------------------------------------------------------------------------
    os.makedirs(os.path.join(td, "obj", "audit")); ob = os.path.join(td, "obj", "objekt.json"); json.dump({}, open(ob, "w"))
    json.dump(dict(quelle="test", bauteile=[dict(bauteil="zeltdach_ueberstand", masse=dict(ueberstand=1.0), toleranz_m=0.3)]), open(os.path.join(td, "obj", "referenz_hand.json"), "w"))
    def hv(block):
        json.dump(dict(D, scheiben=sch, **({"traufe_foto": block} if block else {})), open(os.path.join(td, "obj", "audit", "dach_profil.json"), "w"))
        r_ = subprocess.run([sys.executable, "-I", os.path.join(os.path.dirname(os.path.abspath(__file__)), "hand_vergleich.py"), ob], capture_output=True, text=True)
        if r_.returncode != 0: print(r_.stdout[-500:], r_.stderr[-1500:])
        return next(b for b in json.load(open(os.path.join(td, "obj", "audit", "hand_vergleich.json")))["bauteile"] if b["bauteil"] == "zeltdach_ueberstand")
    h1 = hv(blk); h0 = hv(dict(blk, gueltig=False))
    pruef(h1.get("quelle") == "foto" and abs(h1["masse"]["ueberstand"]["ist"] - E["ueberstand"]) < 1e-6, f"T6 hand_vergleich: Ueberstand {h1['masse']['ueberstand']['ist']} aus {h1.get('quelle')}")
    pruef(h0.get("quelle") == "wolke", f"T6 ohne gueltigen Fotoblock bleibt die Quelle 'wolke' ({h0.get('quelle')})")

# ---- T7 offener Umgang unter der Traufe (Schwabentor: helle->dunkle Kante z 36,18 = Unterkante des Umgangs 35,92..36,97): Kasten erst ueber dem Raehm ---------------
U = dict(gefunden=True, z0=Z_W - 0.2, z1=30.3)
E7 = T.umgang_anpassen(dict(E2), U)
pruef(E7.get("z_wand_bau") == 30.3 and E7.get("z_unten_bau") == 30.3 and E7.get("untersicht_grad") == 0.0 and "ANNAHME" in E7.get("unterkante_quelle", ""),
      f"T7 Umgang: Kasten ab Raehm z {E7.get('z_wand_bau')}, Untersicht waagrecht ({E7.get('untersicht_grad')} Grad), als ANNAHME markiert")
pruef(T.umgang_anpassen(dict(E2), dict(U, z1=20.0)) == E2 and T.umgang_anpassen(dict(E2), None) == E2 and T.umgang_anpassen(dict(E), U).get("z_unten") == E.get("z_unten"),
      "T7 Umgang weit unter der Traufe / ohne Umgang: unveraendert; gemessene Stirn-Unterkante bleibt")
with tempfile.TemporaryDirectory() as td:
    pj = os.path.join(td, "dach_profil.json"); json.dump(dict(D, scheiben=sch, traufe_foto=dict(blk, seiten={"+n": E7})), open(pj, "w"))
    k7, bel7 = BT.dach_aus_profil(M.cube((2 * H, 2 * H, 32)).translate((-H, -H, 0)), pj)
    b_lauf = k7.slice((Z_W + 30.3) / 2).bounds(); b_stirn = k7.slice((30.3 + E7["z_oben"]) / 2).bounds()
    pruef(b_lauf[3] <= H + 0.02 and abs(b_stirn[3] - (H + E7["a_aussen"])) <= 0.03, f"T7 Generator: im Umgang kein Kasten (y {b_lauf[3]:.2f}), darueber Stirn bis y {b_stirn[3]:.2f}")
    pruef(any("Laufgang bleibt offen" in x.get("hinweis", "") for x in bel7), "T7 Beleg nennt den Umgang")

# ---- T8 Stirn-Unterkante aus den 3D-Kanten der Kantenstufe (24.11.2026, Befund 1122 Nord: ANNAHME 'Untersicht in Raehmhoehe' statt Messung) -------------------
def linie(z, refs, n_=240, x0=-0.6 * H, x1=0.6 * H, rng=np.random.default_rng(3)):
    x = rng.uniform(x0, x1, n_); return np.c_[x, np.full(n_, H + A_O) + rng.normal(0, 0.03, n_), np.full(n_, z) + rng.normal(0, 0.012, n_)], np.resize(np.asarray(list(refs)), n_)
rng8 = np.random.default_rng(8)
Pu, Ru = linie(Z_U, range(5)); Po, Ro = linie(Z_O, range(5)); Pn = np.c_[rng8.uniform(-3, 3, 150), H + A_O + rng8.uniform(-0.2, 0.2, 150), rng8.uniform(Z_W, Z_O, 150)]
P8 = np.vstack([Pu, Po, Pn]); R8 = np.concatenate([Ru, Ro, rng8.integers(0, 9, 150)])
E8 = dict(E2); z8, b8 = T.stirn_aus_kanten(P8, R8, D, "+n", E8)
pruef(z8 is not None and abs(z8 - Z_U) <= 0.05, f"T8 Stirn-Unterkante aus Kantenpunkten z {z8} (Soll {Z_U} +- 0,05; {b8})")
E8b = T.umgang_anpassen(T.stirn_einsetzen(E8, z8, b8), dict(gefunden=True, z0=Z_W - 0.2, z1=30.3))
pruef(E8b.get("z_unten") is not None and abs(E8b["z_unten"] - Z_U) <= 0.05 and E8b.get("stirn_gemessen") is True, f"T8 eingesetzt: z_unten {E8b.get('z_unten')}, Stirn {E8b.get('stirn_m')} m")
pruef("ANNAHME" not in str(E8b.get("unterkante_quelle")) and "Fotokanten" in str(E8b.get("unterkante_quelle")),
      f"T8 rote Probe: mit Umgang KEINE ANNAHME mehr (alter Weg: umgang_anpassen setzt 'Untersicht in Raehmhoehe') - Quelle {E8b.get('unterkante_quelle')}")
pruef(T.stirn_einsetzen(dict(E), Z_U + 0.2, b8).get("z_unten") == E.get("z_unten"), "T8 gemessene 2D-Unterkante wird nicht ueberschrieben")
z_, b_ = T.stirn_aus_kanten(P8, np.concatenate([np.resize([0, 1], len(Pu)), Ro, rng8.integers(0, 9, 150)]), D, "+n", E8)
pruef(z_ is None and "Referenzfotos" in b_.get("grund", ""), f"T8 Guard Formfamilie: Unterkante aus nur 2 Fotos verworfen ({b_.get('grund')})")
Pk, Rk = linie(Z_U, range(5), x0=0.0, x1=0.4); z_, b_ = T.stirn_aus_kanten(np.vstack([Pk, Po, Pn]), np.concatenate([Rk, Ro, rng8.integers(0, 9, 150)]), D, "+n", E8)
pruef(z_ is None and "Linie" in b_.get("grund", ""), f"T8 Guard Linie: Haufen an einer Stelle verworfen ({b_.get('grund')})")
z_, b_ = T.stirn_aus_kanten(np.vstack([Po, Pn]), np.concatenate([Ro, rng8.integers(0, 9, 150)]), D, "+n", E8)
pruef(z_ is None, f"T8 Guard nur Rauschen + Oberkante: keine Unterkante erfunden ({b_.get('grund')})")
pruef(T.stirn_aus_kanten(None, None, D, "+n", E8)[0] is None, "T8 ohne sweep.npz: Fallback (None)")

print(f"{'FEHLER: ' + str(len(fehler)) if fehler else 'alle Tests bestanden'}")
sys.exit(1 if fehler else 0)
