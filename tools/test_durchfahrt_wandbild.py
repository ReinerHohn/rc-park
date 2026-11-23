#!/usr/bin/env python3
"""test_durchfahrt_wandbild.py - Tordurchfahrt, deren Sweep-Form verworfen wurde, kommt ueber die Fotokanten doch ins Modell (23.11.2026). Ohne Dateien, < 30 s.

Anlass Kette 1122q (Schwabentor, Bild audit/neben_eigen__IMG_20261106_113231.jpg): das Stadttor fehlte ganz - im Modell nur eine Bogenlinie im Relief.
Ursache: oeffnungen_bogen.py verwarf f00 NUR wegen 'Bogenrand nur zu 33 % von Wand begrenzt' (Schwelle 40 %; 1120: 49 %), obwohl der Durchblick belegt war
(innen 98 %, Wand daneben 5 % offen). Damit liefen durchfahrt_pruefen (nur gebaute) und oeffnungen_aus_kanten --uebernehmen (nur gebaute) ins Leere, obwohl das
Wandbild einen SICHEREN Spitzbogen aus 41 Fotos mass. Fix: form_offen -> uebernehmen baut aus den Fotokanten, gesamtkette wiederholt danach durchfahrt_pruefen.

Vorgespielt: Turm 11 x 10 m, Torseite f00 (+x), Gegenseite f01 (-x).
 1. form_offen: Feld / aus 'grund' abgeleitet (alte Dateien) / Durchblick-Grund -> nein.
 2. uebernehmen: gerettet mit Spitzbogen aus dem Wandbild; NICHT gerettet: Wandbild unsicher, < 3 Einzelfotos, kein Durchblick, Wandbild-Bogen 10 m hoeher.
 3. durchfahrt_pruefen.main (Wolke mit durchgehendem Torweg) -> durchfahrt, tiefe = Dicke + 0,6.
 4. bauteile.oeffnungen_aus_json: Loch geht durch BEIDE Seiten und die Mitte; ueber dem Scheitel bleibt Mauer."""
import sys, os, json, copy, tempfile, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oeffnungen_bogen as OB, oeffnungen_aus_kanten as OK, durchfahrt_pruefen as DP, bauteile as BT
from manifold3d import Manifold as M

fehler = []
def pruef(ok, text):
    print(("    ok   " if ok else "FEHLER  ") + text)
    if not ok: fehler.append(text)

DICKE = 11.0
DB = dict(offen_innen=0.983, offen_flaeche_innen=0.808, bekannt_innen=0.822, offen_wand=0.051)
KAND = dict(art="bogen", kasten=[-2.44, 1.89, 0.03, 7.17], stimmen=9, gesehen=8, unten=0.0, gebaut=False, form="rund", u=-0.12, breite=4.41, kaempfer=4.17, scheitel=6.37,
            rest=dict(wand_innen=0.022, rand_wand=0.334), durchblick=DB, grund="Bogenrand nur zu 33 % von Wand begrenzt - Form nicht belegt", form_offen=True)
AUTO = {"f00": dict(o=[0.0, 0.0], d=[0.0, 1.0], n=[1.0, 0.0], oeffnungen=[KAND], fotos=["a", "b", "c"]),
        "f01": dict(o=[-DICKE, 0.0], d=[0.0, -1.0], n=[-1.0, 0.0], oeffnungen=[], fotos=[])}
WB = dict(id="f00_wand_o0", form="spitzbogen", sicher=True, form_quelle="wandbild", zone=[-2.1, 2.4, 1.5, 6.9], mitte_u=0.15, breite=dict(wert=4.5, hinweis="lichte Weite (Innenkante)", quelle="Kantenzug"),
          kaempfer=dict(wert=3.9), scheitel=dict(wert=6.9), aussenmass=dict(breite=5.1), gewaende=dict(links=0.3, rechts=0.3, scheitel=0.3))
def ber(wb=WB, nfo=41): return dict(ebenen={"f00_wand": dict(oeffnungen=[wb], wandbild=dict(einzelfotos=nfo))})

# ---- 1: form_offen ----
alt = {k: v for k, v in KAND.items() if k != "form_offen"}
pruef(OB.form_offen(KAND) and OB.form_offen(alt), "form_offen: Feld gesetzt und aus 'grund' abgeleitet (Datei vor 23.11.)")
pruef(not OB.form_offen(dict(alt, grund=alt["grund"] + "; kein Durchblick im Inneren (offen 0.2, Flaeche 0.1)")), "form_offen: Durchblick-Grund -> nicht offen")
pruef(not OB.form_offen(dict(alt, gebaut=True, grund="")) and not OB.form_offen(dict(art="bogen", gebaut=False, grund="kein Durchblick im Kasten")), "form_offen: gebaut / ohne Form -> nicht offen")

# ---- 2: uebernehmen ----
def lauf(auto, b):
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "oa.json"); json.dump(auto, open(p, "w")); n = OK.uebernehmen(b, p, log=lambda *_: None); return n, json.load(open(p))
n, A = lauf(AUTO, ber()); x = A["f00"]["oeffnungen"][0]
pruef(n == 1 and x["gebaut"] and x["form"] == "spitz" and abs(x["breite"] - 4.5) < 1e-6 and abs(x["scheitel"] - 6.9) < 1e-6 and x["tiefe_m"] == OB.NISCHE_M and not x["durchfahrt"],
      f"gerettet: {x.get('form')} b {x.get('breite')} s {x.get('scheitel')} tiefe {x.get('tiefe_m')} ({x.get('gebaut_durch', '')[:60]})")
pruef(x.get("grund") == "" and "Bogenrand" in (x.get("grund_sweep") or ""), "Sweep-Grund aufbewahrt (grund_sweep), grund leer")
n, A = lauf({"f00": dict(AUTO["f00"], oeffnungen=[alt]), "f01": AUTO["f01"]}, ber()); pruef(n == 1 and A["f00"]["oeffnungen"][0]["gebaut"], "alte Datei ohne form_offen-Feld: gerettet")
for nm, b in (("Wandbild unsicher", ber(dict(WB, sicher=False))), ("nur 2 Einzelfotos", ber(nfo=2)), ("Wandbild-Bogen 10 m hoeher", ber(dict(WB, zone=[-2.1, 2.4, 11.5, 16.9], kaempfer=dict(wert=13.9), scheitel=dict(wert=16.9)))),
              ("Wandbild Sturz statt Bogen", ber(dict(WB, form="sturz")))):
    n, A = lauf(AUTO, b); pruef(n == 0 and not A["f00"]["oeffnungen"][0]["gebaut"], f"NICHT gerettet: {nm}")
kd = dict(KAND, form_offen=False, grund=KAND["grund"] + "; kein Durchblick im Inneren (offen 0.2, Flaeche 0.1)")
n, A = lauf({"f00": dict(AUTO["f00"], oeffnungen=[kd]), "f01": AUTO["f01"]}, ber()); pruef(n == 0 and not A["f00"]["oeffnungen"][0]["gebaut"], "NICHT gerettet: Durchblick nicht belegt")
n, A = lauf(AUTO, ber(dict(WB, gewaende={}, aussenmass=dict(breite=4.5)))); pruef(any("Aussenkante" in s for s in A["f00"]["oeffnungen"][0]["annahmen"]), "ohne Innenkante: ANNAHME Aussenkante vermerkt")

# ---- 3: durchfahrt_pruefen nach der Uebernahme ----
_, A = lauf(AUTO, ber())
rng = np.random.default_rng(5); n_ = 8000
stoer = np.c_[-rng.uniform(0, DICKE, 4000), rng.uniform(-5, 5, 4000), rng.uniform(0, 8, 4000)]
w = rng.uniform(0, DICKE, n_); s = rng.choice([-1, 1], n_); laib = np.c_[-w, 0.15 + s * 2.25 + rng.normal(0, 0.05, n_), rng.uniform(0.3, 3.8, n_)]
with tempfile.TemporaryDirectory() as td:
    fj, oj, wj = (os.path.join(td, f) for f in ("fassaden.json", "oa.json", "w.npy"))
    json.dump(dict(fassaden=[dict(id="f00", o=[0, 0], d=[0, 1], n=[1, 0]), dict(id="f01", o=[-DICKE, 0], d=[0, -1], n=[-1, 0])]), open(fj, "w")); json.dump(A, open(oj, "w")); np.save(wj, np.vstack([stoer, laib]))
    rc = DP.main([fj, oj, "--wolke", wj]); A = json.load(open(oj))
x = A["f00"]["oeffnungen"][0]
pruef(rc == 0 and x.get("durchfahrt") and abs(x["tiefe_m"] - (DICKE + 0.6)) < 1e-6, f"durchfahrt_pruefen: Durchfahrt {x.get('durchfahrt')}, tiefe {x.get('tiefe_m')} (rc {rc})")

# ---- 4: Generator: Loch durch den ganzen Baukoerper ----
turm = M.cube((DICKE, 10.0, 20.0)).translate((-DICKE, -5.0, 0.0))
with tempfile.TemporaryDirectory() as td:
    oj = os.path.join(td, "oa.json"); json.dump(A, open(oj, "w")); k, bel, zm = BT.oeffnungen_aus_json(turm, oj)
def voll(px, py, pz, a=0.2): return (k ^ M.cube((a, a, a)).translate((px - a / 2, py - a / 2, pz - a / 2))).volume() > 1e-6
pruef(not voll(-0.3, 0.15, 2.0) and not voll(-DICKE / 2, 0.15, 2.0) and not voll(-DICKE + 0.3, 0.15, 2.0), "Loch an Torseite, in der Mitte UND an der Gegenseite (beidseitig offen)")
pruef(voll(-DICKE / 2, 0.15, 8.0) and voll(-0.3, 3.5, 2.0), "ueber dem Scheitel und neben dem Tor bleibt Mauer")
pruef(len(bel) == 1 and "Tordurchfahrt" in bel[0]["element"] and zm is not None and abs(zm - (6.9 + 0.5)) < 1e-6, f"Beleg Tordurchfahrt, z_massiv {zm}")

print(f"{'FEHLER: ' + str(len(fehler)) if fehler else 'alle Tests bestanden'}")
sys.exit(1 if fehler else 0)
