#!/usr/bin/env python3
"""test_wand_neigung_vorbau.py - synthetisch, CPU, < 5 s (22.11.2026, Befund 1122n: Bilderker der Stadtseite fehlte).

URSACHE 1122n: Die Wand f00 stand im Kamerarahmen geneigt gegen die LoD2-Ebene (Lotfehler ~2,6 Grad: 0 m am Fuss, -1,4 m bei z 33). fassade_tiefe nahm einen
konstanten Wandversatz an -> Wandtiefe verschmiert, Tor 31 % < 35 % -> 'nicht belastbar' -> kein Vorbau; das Fenster-Tor zaehlte die geneigte Wand als 'Nische'.
Geprueft:
  1. wand_ebene_schaetzen findet die geneigte Wand (Neigung auf < 0,5 cm/m), der Erker davor zieht die Ebene nicht.
  2. Guard: lotrechte Wand (nur konstanter Versatz) -> None (Verhalten wie bisher); reines Rauschen -> None; Neigung ueber max_neigung -> None.
  3. ebenen_masse misst die Ausladung gegen die OERTLICHE (geneigte) Wand: 1,30 m statt 1,30 - Neigung x Hoehe.
  4. fenster_tiefe_tor: Kasten zwischen Erker-Streben (unter dem Kasten, ueber dem Strebenfuss aus kanten_mass) wird verworfen; ein Fenster weit weg bleibt.
"""
import os, sys, json, subprocess, tempfile, numpy as np
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from vorbauten_bauplan import wand_ebene_schaetzen, wand_ebene_w

F = []
def pruef(b, t):
    print(("ok     " if b else "FEHLER ") + t)
    if not b: F.append(t)


rng = np.random.default_rng(1)
c = 0.04; u0, u1, z0, z1 = -6.0, 6.0, 0.0, 36.0
U, Z = np.meshgrid(np.arange(u0, u1, c) + c / 2, np.arange(z1, z0, -c) - c / 2)
u_ref, z_ref = 0.0, 0.0
wand = 0.05 - 0.045 * (Z - z_ref) + 0.01 * (U - u_ref)            # Lotfehler: 4,5 cm/m nach hinten, 1 cm/m entlang u
erker = (U > -4) & (U < 4.5) & (Z > 9) & (Z < 16)
W = wand + rng.normal(0, 0.03, U.shape); W[erker] = (wand + 1.3)[erker] + rng.normal(0, 0.05, erker.sum())
gut = rng.random(U.shape) < 0.5
we = wand_ebene_schaetzen(U, Z, W, gut, u_ref, z_ref)
pruef(we is not None and abs(we["c_z"] + 0.045) < 0.005 and abs(we["b_u"] - 0.01) < 0.005 and abs(we["a"] - 0.05) < 0.05,
      f"geneigte Wand gefunden: {we and (we['a'], we['b_u'], we['c_z'], we['neigung_grad'])}")
if we:
    r = W - wand_ebene_w(we, U, Z)
    pruef(abs(np.median(r[erker & gut]) - 1.3) < 0.05, f"Erker relativ zur geneigten Wand {np.median(r[erker & gut]):.2f} m (soll 1,30)")

W2 = -0.12 + rng.normal(0, 0.03, U.shape); W2[erker] = 1.2
pruef(wand_ebene_schaetzen(U, Z, W2, gut, u_ref, z_ref) is None, "Guard: lotrechte Wand -> keine Neigung (konstanter Versatz wie bisher)")
W3 = rng.uniform(-0.8, 2.5, U.shape)
pruef(wand_ebene_schaetzen(U, Z, W3, gut, u_ref, z_ref) is None, "Guard: Rauschen -> keine Ebene")
W4 = 0.25 * (Z - 18) + rng.normal(0, 0.02, U.shape)
pruef(wand_ebene_schaetzen(U, Z, W4, gut, u_ref, z_ref) is None, "Guard: Neigung 0,25 m/m (> max_neigung 0,10) -> keine Ebene")

# 3. ebenen_masse gegen die oertliche Wand
with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as T:
    od = os.path.join(T, "obj"); os.makedirs(os.path.join(od, "audit")); eb = os.path.join(T, "ebenen"); os.makedirs(eb)
    o, d, n = np.array([10.0, 0.0]), np.array([0.0, 1.0]), np.array([1.0, 0.0])
    ne = dict(a=0.05, b_u=0.0, c_z=-0.045, u_ref=0.0, z_ref=0.0)
    pts = []
    for zl in (10.2, 11.5):                                           # Unter-/Oberkante der Bruestung, Front 1,30 vor der oertlichen Wand
        for uu in np.arange(-3.9, 4.4, 0.01): pts.append((uu, zl + rng.normal(0, 0.005), 1.3 + rng.normal(0, 0.03)))
    for k in range(6):                                                  # Konsolen 0,4 m breit unter der Unterkante
        for uu in np.arange(-3.6 + 1.5 * k, -3.2 + 1.5 * k, 0.01): pts.append((uu, 9.95, 1.3 + rng.normal(0, 0.03)))
    pts = np.array(pts); wl = 0.05 - 0.045 * pts[:, 1] + pts[:, 2]
    P3 = np.c_[o[0] + pts[:, 0] * d[0] + wl * n[0], o[1] + pts[:, 0] * d[1] + wl * n[1], pts[:, 1]]
    np.savez(os.path.join(eb, "sweep.npz"), P=P3.astype(np.float32))
    ww = 0.05; front = 1.3
    g = dict(u0=-4.0, u1=4.5, z0=9.5, z1=12.0, koerper=dict(u0=-4.0, u1=4.5, z0=9.5, z1=12.0, w_median=front, w_p10=1.1, w_p90=1.5, flaeche_m2=20))
    for mit in (True, False):
        json.dump(dict(fassaden=[dict(id="f00", nr=0, o=o.tolist(), d=d.tolist(), n=n.tolist(), w_wand=ww, wand_ebene=ne if mit else None, gruppen=[g])]), open(os.path.join(od, "audit", "vorbauten_auto.json"), "w"))
        json.dump(dict(ebenen=[dict(id="f00_vb0", art="vorbau", o=o.tolist(), d=d.tolist(), n=n.tolist(), w=ww + front, w_wand=ww, neigung=ne if mit else None, zone=[-4.6, 5.1, 7.9, 13.0], sweep=os.path.join(eb, "sweep.npz"))]),
                  open(os.path.join(eb, "ebenen.json"), "w"))
        r = subprocess.run([sys.executable, "-I", os.path.join(HIER, "ebenen_masse.py"), os.path.join(od, "objekt.json"), eb], capture_output=True, text=True)
        km = json.load(open(os.path.join(od, "audit", "vorbauten_auto.json")))["fassaden"][0]["gruppen"][0].get("kanten_mass") or {}
        if mit: pruef(abs(km.get("ausladung", 0) - 1.3) < 0.06 and "kasten" in km, f"ebenen_masse mit Neigung: Ausladung {km.get('ausladung')} (soll 1,30), Kasten {km.get('kasten')} {r.stderr[-200:]}")
        else: pruef(km.get("ausladung", 9) < 1.0, f"Gegenprobe ohne Neigung: Ausladung {km.get('ausladung')} (zu klein - so sah die Kette 1122 den Erker)")

# 4. fenster_tiefe_tor: Kasten zwischen Streben
with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as T:
    au = os.path.join(T, "audit"); fo = os.path.join(T, "fassade"); os.makedirs(au); os.makedirs(fo)
    H_, W_ = 300, 300; cz = 0.04; npz_u0, npz_z1 = -6.0, 12.0
    w = np.full((H_, W_), 0.05, np.float32); w[225:275, 225:262] = -0.25     # Kasten 2 = echte Nische (0,3 m hinter der Wand)
    gutm = np.ones((H_, W_), bool)
    np.savez(os.path.join(fo, "tiefe_f00.npz"), w=w, gut=gutm, zelle=cz, u0=npz_u0, z1=npz_z1)
    json.dump(dict(wand_versatz_m=0.05), open(os.path.join(fo, "vorbauten_f00.json"), "w"))
    json.dump(dict(fassaden={"f00": dict(elemente=[])}), open(os.path.join(fo, "elemente.json"), "w"))
    k1 = dict(u0=-3.46, u1=-1.87, z0=7.9, z1=9.75)                     # zwischen den Streben (Strebenfuss 8,4, Konsolen 9,95, Kasten 10,2)
    k2 = dict(u0=3.0, u1=4.5, z0=1.0, z1=3.0)                          # weit weg, gewoehnliche Wand -> darf nicht wegen des Vorbaus fallen
    json.dump({"f00": dict(fenster=[k1, k2])}, open(os.path.join(au, "fenster_auto.json"), "w"))
    km = dict(kasten=dict(z_unten=10.2, z_oben=11.5, u0=-3.9, u1=4.4), konsolen=dict(z_unten=9.95, anzahl=6), streben=dict(z_fuss=8.4))
    json.dump(dict(fassaden=[dict(id="f00", gruppen=[dict(u0=-4.0, u1=4.5, z0=10.0, z1=16.0, kanten_mass=km)])]), open(os.path.join(au, "vorbauten_auto.json"), "w"))
    w[int((npz_z1 - 9.75) / cz):int((npz_z1 - 7.9) / cz), int((-3.46 - npz_u0) / cz):int((-1.87 - npz_u0) / cz)][:9] = -0.3   # etwas 'hinten' (19 %)
    np.savez(os.path.join(fo, "tiefe_f00.npz"), w=w, gut=gutm, zelle=cz, u0=npz_u0, z1=npz_z1)
    r = subprocess.run([sys.executable, "-I", os.path.join(HIER, "fenster_tiefe_tor.py"), os.path.join(au, "fenster_auto.json"), fo], capture_output=True, text=True)
    FE = json.load(open(os.path.join(au, "fenster_auto.json")))["f00"]["fenster"]
    pruef(not any(abs(q["u0"] + 3.46) < 1e-6 for q in FE), f"Kasten zwischen den Streben verworfen (Vorbau-Raum bis Strebenfuss aus kanten_mass) {r.stdout[-200:]} {r.stderr[-200:]}")
    pruef(any(abs(q["u0"] - 3.0) < 1e-6 for q in FE), "Fenster ausserhalb des Vorbau-Raums bleibt")

# 5. vorbau_fototor: Export je Gruppe (Generator-Umgebung) + Urteil
import vorbau_fototor as VF
pruef(VF.urteil({"_gesamt": dict(praez=0.62, recall=0.4, f1=0.48, fotos=5)})[0] == "BELEGT" and VF.urteil({"_gesamt": dict(praez=0.3, recall=0.4, f1=0.34, fotos=5)})[0] == "NICHT BELEGT"
      and VF.urteil({"_gesamt": dict(praez=0.9, recall=0.9, f1=0.9, fotos=2)})[0] == "KEIN URTEIL", "vorbau_fototor.urteil: belegt / nicht belegt / zu wenige Fotos")
try:
    import manifold3d  # noqa: F401
    with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as T:
        g = dict(u0=-1.0, u1=1.0, z0=5.0, z1=6.0, raster=0.5, w=[[1.0] * 4, [1.0] * 4], koerper=dict(u0=-1.0, u1=1.0, z0=5.0, z1=6.0, w_median=1.0), dach=None)      # 24.11.: Grobkoerper vollstaendig - ohne Kantenkasten baut der Ersatz-Kasten daraus (nie Hoehenfeld)
        vj = os.path.join(T, "vorbauten_auto.json"); json.dump(dict(fassaden=[dict(id="f00", nr=0, o=[0, 0], d=[0, 1], n=[1, 0], w_wand=0.0, gruppen=[g, dict(g, u0=3.0, u1=4.0, w=[[0.8] * 2] * 2, koerper=dict(u0=3.0, u1=4.0, z0=5.0, z1=6.0, w_median=0.8))])]), open(vj, "w"))
        aus = VF.exportieren(vj, os.path.join(T, "teile"), 87.0)
        import trimesh
        m0 = trimesh.load(os.path.join(T, "teile", "vorbau_f00_0.stl")); m1 = trimesh.load(os.path.join(T, "teile", "vorbau_f00_1.stl"))
        pruef([x[0] for x in aus] == ["vorbau_f00_0", "vorbau_f00_1"] and abs(m0.bounds[1][0] * 87 / 1000 - 1.0) < 0.02 and m1.bounds[0][1] * 87 / 1000 > 2.9,
              f"Export je Gruppe getrennt, Massstab 1:87 (Front {m0.bounds[1][0] * 87 / 1000:.2f} m, Gruppe 2 ab u {m1.bounds[0][1] * 87 / 1000:.2f})")
except ImportError:
    print("hinweis: manifold3d fehlt in dieser Umgebung - Export nicht geprueft")

print("FEHLER: %d" % len(F) if F else "alle Pruefungen bestanden"); sys.exit(1 if F else 0)
