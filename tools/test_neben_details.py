#!/usr/bin/env python3
"""test_neben_details.py - synthetische Pruefung von tools/neben_details.py (Detailansicht je Bauteil, 22.11.2026). Kein echtes Objekt, Sekunden.
1. Kamerawahl front: von vier Kameras gewinnt die, die das Bauteil gross, mittig und senkrecht zeigt (nicht die ferne, nicht die schraeg
   abgeschnittene, nicht der Steilblick von unten, nicht die von hinten).
2. Kamerawahl seite (Profil-Bauteil): gewinnt die seitliche Kamera, die frontale ist dafuer unbrauchbar.
3. Rundteil: waagrechter Blick schlaegt Steilblick.
4. Render + Sicht: ein fremder Verdecker vor dem Bauteil senkt den Sicht-Anteil deutlich, ohne ~ 100 %; Beleg: Fotokanten am Umriss hoch, leerer Himmel ~ 0.
5. Bauteile aus einem kuenstlichen audit-Ordner (vorbauten_auto.json + dach_profil.json): Fassadenzone mit Ausladung aus dem Modell -> Profil, Rundteil erkannt.
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

print("ALLE OK" if F == 0 else f"{F} FEHLER")
sys.exit(1 if F else 0)
