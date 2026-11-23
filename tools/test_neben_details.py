#!/usr/bin/env python3
"""test_neben_details.py - synthetische Pruefung von tools/neben_details.py (Detailansicht je Bauteil, 22.11.2026). Kein echtes Objekt, Sekunden.
1. Kamerawahl front: von vier Kameras gewinnt die, die das Bauteil gross, mittig und senkrecht zeigt (nicht die ferne, nicht die schraeg
   abgeschnittene, nicht der Steilblick von unten, nicht die von hinten).
2. Kamerawahl seite (Profil-Bauteil): gewinnt die seitliche Kamera, die frontale ist dafuer unbrauchbar.
3. Rundteil: waagrechter Blick schlaegt Steilblick.
4. Render + Sicht: ein fremder Verdecker vor dem Bauteil senkt den Sicht-Anteil deutlich, ohne ~ 100 %; Beleg: Fotokanten am Umriss hoch, leerer Himmel ~ 0.
5. Bauteile aus einem kuenstlichen audit-Ordner (vorbauten_auto.json + dach_profil.json): Fassadenzone mit Ausladung aus dem Modell -> Profil, Rundteil erkannt.
6. Uhr (Befund 1122q, 23.11.): Wand-Faecher mit Mitte im Uhrkasten sind NICHT Bauteil (alle Ecken im Kasten + Kreis-Kontur aus uhren_auto.json).
"""
import os, sys, json, math, tempfile
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import neben_details as ND

F = 0


def pruefe(ok, text):
    global F
    print(("  ok    " if ok else "  FEHLER ") + text)
    if not ok: F += 1


def kamera(C, ziel, f=1000.0, W=1000, H=800):
    C = np.asarray(C, float); z = np.asarray(ziel, float) - C; z /= np.linalg.norm(z)
    x = np.cross(z, [0, 0, 1.0]); x /= np.linalg.norm(x); y = np.cross(z, x)           # Bild-y nach unten
    R = np.stack([x, y, z]); t = -R @ C
    return dict(rvec=cv2.Rodrigues(R)[0].ravel().tolist(), t=t.tolist(), f_px=f, cx=W / 2, cy=H / 2, bild=[W, H])


def quader(c, h):
    c = np.asarray(c, float); h = np.asarray(h, float)
    V = np.array([[sx, sy, sz] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]) * h + c
    Fl = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)]
    T = V[np.array(Fl)]
    N = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); m = T.mean(1) - c
    flip = np.einsum("ij,ij->i", N, m) < 0; T[flip] = T[flip][:, [0, 2, 1]]                # Normalen nach aussen
    return T


def normalen(T):
    N = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); return N / np.linalg.norm(N, axis=1, keepdims=True)


# Bauteil: Fassade in der Ebene x = 0, Aussennormale +x, Bauteil u (= y) -1..1, z 9..11, w (= x) 0..0,5
B = dict(name="vorbau_f00", art="fassade", o=[0.0, 0.0], d=[0.0, 1.0], n=[1.0, 0.0], u0=-1.0, u1=1.0, z0=9.0, z1=11.0, w0=-0.3, w1=0.5, profil=True)
E, M = ND.ecken(B)
kams = {"eigen__gut": kamera([8, 0, 10], M), "eigen__fern": kamera([60, 0, 10], M), "eigen__schraeg_rand": kamera([8, 3, 10], [0, -1.5, 10]),
        "eigen__steil": kamera([2.5, 0, 0], M), "eigen__hinten": kamera([-8, 0, 10], M), "eigen__seite": kamera([2.0, 9.0, 10], M)}
w = {nm: ND.kamera_wertung(K, E, M, B["n"], "front", nm) for nm, K in kams.items()}
gueltig = {k: v["wert"] for k, v in w.items() if v}
pruefe(max(gueltig, key=gueltig.get) == "eigen__gut", f"front: grosse/mittige/senkrechte Kamera gewinnt ({ {k: round(v, 3) for k, v in gueltig.items()} })")
pruefe(w["eigen__hinten"] is None, "front: Kamera hinter der Wand unbrauchbar")
pruefe(not w["eigen__steil"] or w["eigen__steil"]["wert"] < 0.5 * w["eigen__gut"]["wert"], "front: Steilblick von unten deutlich schlechter")
ws = {nm: ND.kamera_wertung(K, E, M, B["n"], "seite", nm) for nm, K in kams.items()}
gs = {k: v["wert"] for k, v in ws.items() if v}
pruefe(bool(gs) and max(gs, key=gs.get) == "eigen__seite" and ws["eigen__gut"] is None, f"seite: seitliche Kamera gewinnt, frontale unbrauchbar ({ {k: round(v, 3) for k, v in gs.items()} })")

# Rundteil (Laterne) Achse (20, 0), r 1, z 30..34
L = dict(name="laterne", art="rund", achse=[20.0, 0.0], r=1.0, z0=30.0, z1=34.0)
EL, ML = ND.ecken(L)
kr = {"eigen__waagrecht": kamera([32, 0, 32], ML), "eigen__steil": kamera([23, 0, 2], ML)}
wr = {nm: ND.kamera_wertung(K, EL, ML, None, "rund", nm) for nm, K in kr.items()}
pruefe(wr["eigen__waagrecht"] and (not wr["eigen__steil"] or wr["eigen__waagrecht"]["wert"] > wr["eigen__steil"]["wert"]), "rund: waagrechter Blick schlaegt Steilblick")

# Render + Sicht: Bauteilquader allein vs. mit Verdecker davor
T0 = np.concatenate([quader([-1, 0, 10], [1, 4, 6]), quader([0.25, 0, 10], [0.25, 1, 1])])        # Wand + Bauteil
sel0 = ND.auswahl(T0, B)
pruefe(sel0.sum() == 12, f"auswahl: genau die 12 Bauteil-Dreiecke ({int(sel0.sum())})")
K = kams["eigen__gut"]; ka = ND.ausschnitt(ND.kamera_wertung(K, E, M, B["n"], "front", "eigen__gut")["px"], 1000, 800)
s_frei, _, _ = ND.sicht_anteil(T0, normalen(T0), K, ka, sel0)
TV = quader([4, 0, 10], [0.2, 0.9, 0.9])
s_verd, _, _ = ND.sicht_anteil(T0, normalen(T0), K, ka, sel0, extra=(TV, normalen(TV)))
pruefe(s_frei > 0.9 and s_verd < 0.5, f"sicht: frei {s_frei:.2f} > 0,9, mit fremdem Verdecker {s_verd:.2f} < 0,5")
# Beleg: Foto = Render selbst (Kanten passen) gegen leeres Himmelsfoto (Kamera falsch)
voll, _ = ND.rendern(T0, normalen(T0), K, [0, 0, 1000, 800], 1.0, (1000, 800), hervor=sel0)       # Bauteil getoent = Kante zur Wand
_, b_gut, p_gut = ND.sicht_anteil(T0, normalen(T0), K, ka, sel0, foto=voll)
_, b_leer, _ = ND.sicht_anteil(T0, normalen(T0), K, ka, sel0, foto=np.full((800, 1000, 3), 200, np.uint8))
pruefe(b_gut is not None and b_gut > 0.6 and b_leer is not None and b_leer < 0.1, f"beleg: passendes Foto {b_gut}, leerer Himmel {b_leer}")
_, _, p_vers = ND.sicht_anteil(T0, normalen(T0), K, ka, sel0, foto=np.roll(voll, 30, axis=1))          # Kamerapose 30 px daneben
pruefe(p_gut is not None and p_gut > 0.9 and p_vers is not None and p_vers < 0.6, f"passung: passende Pose {p_gut}, 30 px daneben {p_vers}")
img, fid = ND.rendern(T0, normalen(T0), K, [int(v) for v in ka], 1.0, (int(ka[2] - ka[0]), int(ka[3] - ka[1])), hervor=sel0)
mf = fid[fid >= 0]
pruefe(img.shape[2] == 3 and sel0[mf].mean() > 0.3, f"render: Bauteil sichtbar und getoent ({sel0[mf].mean():.2f} der Modellpixel)")

# Bauteile aus kuenstlichem audit-Ordner
with tempfile.TemporaryDirectory() as d:
    json.dump(dict(fassaden=[dict(id="f00", o=[0, 0], d=[0, 1], n=[1, 0], gruppen=[dict(u0=-1, u1=1, z0=9, z1=11)])]), open(os.path.join(d, "vorbauten_auto.json"), "w"))
    json.dump(dict(laterne_foto=dict(achse=[-1, 0], profil=[[12, 0.5, 8], [13, 0.4, 8], [14, 0.2, 8]], nadel_z=15.0)), open(os.path.join(d, "dach_profil.json"), "w"))
    T2 = np.concatenate([T0, quader([0.9, 0, 10], [0.9, 0.9, 0.9])])                                # Ausladung 1,8 m
    bs = {b["name"]: b for b in ND.bauteile_sammeln(d, T2)}
    pruefe("vorbau_f00" in bs and bs["vorbau_f00"]["profil"] and 1.5 < bs["vorbau_f00"]["w1"] < 2.0, f"bauteile: Vorbau erkannt, Ausladung aus dem Modell ({bs.get('vorbau_f00', {}).get('w1')})")
    pruefe("laterne" in bs and bs["laterne"]["z1"] == 15.0 and bs["laterne"]["r"] == 0.5, f"bauteile: Laterne aus dach_profil (z bis Nadel, r max) {sorted(bs)}")

# 6. Befund Uhr f00 (Lauf 1122q, 23.11.2026): flache Wand um die Uhr als Faecher trianguliert -> lange Splitter, deren MITTE im Uhrkasten liegt, wurden
#    als 'Uhr' blau gemalt ('Keile bis zur Traufe'). Erwartet: nur Dreiecke innerhalb des Kastens UND der belegten Kreis-Kontur (Mitte + d_aussen).
def fp(u, w, z): return [w, u, z]                                                             # Fassade wie B: o (0,0), d = +y (u), n = +x (w)
ph = np.linspace(0, 2 * np.pi, 33)
scheibe = np.array([[fp(0, 0.1, 10), fp(np.sin(a), 0.1, 10 + np.cos(a)), fp(np.sin(b_), 0.1, 10 + np.cos(b_))] for a, b_ in zip(ph[:-1], ph[1:])])   # Uhr r 1, u 0, z 10
splitter = np.array([[fp(-0.95, 0, 5.0), fp(-0.97, 0, 11.5), fp(-0.93, 0, 11.5)],          # Wand-Faecher: Mitte z 9,33 im Kasten, Ecken 5 / 11,5 m
                     [fp(-3.0, 0, 10.0), fp(0.98, 0, 10.4), fp(0.98, 0, 10.5)]])            # quer: Ecke 2 m links neben dem Kasten
ecke = np.array([[fp(0.9, 0, 10.9), fp(1.05, 0, 10.9), fp(1.05, 0, 11.05)]])                 # Wand in der Kastenecke, ausserhalb des Kreises
TU = np.concatenate([scheibe, splitter, ecke]); nS = len(scheibe)
with tempfile.TemporaryDirectory() as d:
    json.dump(dict(f00=dict(o=[0.0, 0.0], d=[0.0, 1.0], n=[1.0, 0.0], uhren=[dict(u=0.0, z=10.0, d_aussen=2.0, d_innen=1.3, kasten=[-1.1, 1.1, 8.9, 11.1])])),
              open(os.path.join(d, "uhren_auto.json"), "w"))
    bu = {b["name"]: b for b in ND.bauteile_sammeln(d, TU)}.get("uhr_f00")
    pruefe(bool(bu) and bu.get("kreis") == [0.0, 10.0, 1.0], f"uhr: belegte Kontur (Kreis) aus uhren_auto.json mitgefuehrt ({(bu or {}).get('kreis')})")
    if bu:
        u_, w_, z_ = ND.lokal(TU, bu)
        alt = (u_ >= bu["u0"] - 0.1) & (u_ <= bu["u1"] + 0.1) & (w_ >= bu["w0"]) & (w_ <= bu["w1"]) & (z_ >= bu["z0"] - 0.1) & (z_ <= bu["z1"] + 0.1)
        pruefe(alt[nS:nS + 2].all(), "Vorbedingung: alte Mitten-Auswahl haette die Splitter genommen")
        su, fr = ND.auswahl(TU, bu, fremd=True)
        pruefe(su[:nS].all() and not su[nS:].any() and fr == 3, f"uhr: alle {nS} Scheibendreiecke, keine Wand-Splitter, keine Kastenecke (Auswahl {int(su.sum())}, fremd {fr})")
        b2 = dict(bu); b2.pop("kreis")
        s2 = ND.auswahl(TU, b2); pruefe(s2[:nS].all() and not s2[nS:nS + 2].any() and s2[-1], "ohne Kreis: Splitter raus (Ecken weit ausserhalb), Kastenecke bleibt")

print("ALLE OK" if F == 0 else f"{F} FEHLER")
sys.exit(1 if F else 0)
