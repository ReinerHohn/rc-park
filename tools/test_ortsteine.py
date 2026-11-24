#!/usr/bin/env python3
"""test_ortsteine.py - Rot-Probe Ortsteine/Eckverzahnung aus dem Wandbild (tools/ortsteine.py, 24.11.2026).
Anlass: Schwabentor-1122 (Lauf 1122u/v) - Foto Sued/Nord zeigt an allen Turmkanten versetzte rote Sandstein-Eckquader, Modell: Kanten glatt.
Runde 2 (Befund 1122w): Nord links viele duenne gleich lange Streifen (Splitter aus Steintextur, kein Stossfugen), Uhrzone leer (Mosaik endet unter der Uhr;
Ziffernring im Innenband), keine eigene Kettenstufe / kein Tor.
Synthetische Wand 12 x 18 m (Wandbild 1 cm): weisser Putz, an beiden Kanten Ortsteine abwechselnd 1,0 / 0,6 m lang, Lagen 0,5 m (z 3..15), lange Steine mit
Stossfuge bei 0,55 m, darunter volles Quadermauerwerk (darf KEINE Ortsteinzone sein), LoD2-Kante 0,2 m neben der Fotokante, Einzelbilder: 3 deckungsgleich +
1 um 0,7 m versetztes (wird ausgerichtet und stimmt mit) + 1 fremde Putzwand (stimmt nicht mit).
  1. Erkennung: beide Kanten, Zone z 3..15 (+-0,3), Lagen 24 +-3, lang 1,0 / kurz 0,6 (+-0,12), Zahnung >= 0,8, Fotokante erkannt, 4 Fotos bestaetigen.
  2. Vorsprung aus dem Ebenen-Sweep (Stein +5 cm) gemessen; ohne Sweep -> None (ANNAHME im Bau).
  3. Bau: Bloecke vor der echten Flaeche, Vorsprung im Modell, ein Koerper, lang/kurz im Modell; Druckmass (Lage, Breite >= MINMM).
  4. Gegenproben: Putzwand ohne Steine -> nichts; nur 2 bestaetigende Fotos -> nicht gebaut; fassaden_kette.anbauen ruft ortsteine_anbauen (Generator ruft nur auf).
  5. Runde 2: Mosaik ohne Daten ueber z 11 -> aus >= 3 ausgerichteten Einzelfotos ergaenzt, Zone bis z 15; mit nur 2 Einzelfotos nicht ergaenzt.
  6. Runde 2: Uhr (rote Scheibe) im Innenband -> Zone bleibt eine durchgehende Zone (Putz direkt hinter dem Stein zaehlt).
  7. Runde 2: Lagen nie Splitter (>= 0,4 m bei 0,5-m-Lagen); Pfeiler gleicher Breite an Lagerfugen in Lagen der Fugenhoehe geteilt, ohne Fugen keine Splitter.
  8. Runde 2: Stossfugen - lange Steine 2 Teilsteine, kurze 1; im Modell Fuge sichtbar.
  9. Runde 2: Tor - zu breite Lagen fallen durch und werden nicht gebaut; Kettenstufe bauplan_ortsteine in gesamtkette (Beleg-JSON + Bild), main rc 0 mit Tor-Block.
"""
import os, sys, json, subprocess, numpy as np
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from pfade import temp_ordner
from PIL import Image
import ortsteine as O
n_ok = 0


def ok(b, t):
    global n_ok
    if not b: print("FEHLER:", t); sys.exit(1)
    n_ok += 1; print("    ok", t)


C = 0.01; UW, ZW = 12.0, 18.0; MARGE = 0.5; LOD2_VERSATZ = 0.2; Z_A, Z_E, LAGE, LANG, KURZ = 3.0, 15.0, 0.5, 1.0, 0.6; STOSS = 0.55
rng = np.random.default_rng(3)


def wandbild(ortsteine=True, uhr=False):
    """RGB-Wandbild im fassade_fein-Raster (Zeile 0 = z1 = ZW + MARGE). Wand u 0..UW (Fotokante = LoD2 + LOD2_VERSATZ)."""
    nu, nz = int((UW + 2 * MARGE) / C), int((ZW + 2 * MARGE) / C)
    uu = -MARGE + (np.arange(nu) + 0.5) * C; zz = ZW + MARGE - (np.arange(nz) + 0.5) * C; U, Z = np.meshgrid(uu, zz)
    img = np.zeros((nz, nu, 3), np.float32); wand = (U >= LOD2_VERSATZ) & (U <= UW - LOD2_VERSATZ) & (Z >= 0) & (Z <= ZW)
    img[wand] = (232, 230, 226)
    stein = np.zeros(U.shape, bool); fuge = np.zeros(U.shape, bool)
    if ortsteine:
        k = np.floor((Z - Z_A) / LAGE).astype(int); lang = (k % 2 == 0); b = np.where(lang, LANG, KURZ)
        zone = (Z >= Z_A) & (Z < Z_E)
        links = zone & (U >= LOD2_VERSATZ) & (U < LOD2_VERSATZ + b); rechts = zone & (U <= UW - LOD2_VERSATZ) & (U > UW - LOD2_VERSATZ - np.where(lang, KURZ, LANG))
        stein |= links | rechts
        fuge |= links & lang & (np.abs(U - (LOD2_VERSATZ + STOSS)) < 0.015)                         # Stossfuge in den langen Steinen (links)
        fuge |= rechts & ~lang & (np.abs(U - (UW - LOD2_VERSATZ - STOSS)) < 0.015)                  # rechts sind die ungeraden Lagen lang
        stein |= (Z < Z_A) & wand                                             # volles Quadermauerwerk unten
    stein &= wand
    fuge = (fuge | (stein & ((((Z - Z_A) % LAGE) < 0.02) | (((Z % 0.4) < 0.02) & (Z < Z_A))))) & stein
    img[stein] = (150, 80, 60); img[fuge] = (70, 60, 55)
    if uhr: img[(U - 3.2) ** 2 + (Z - 9.0) ** 2 < 1.0] = (160, 70, 50)  # rote Uhr im Innenband der linken Kante
    img[wand] += rng.normal(0, 6, (int(wand.sum()), 3))
    return np.clip(img, 0, 255).astype(np.uint8), stein


def ordner(ortsteine=True, n_gut=3, sweep=True, versetzt=True, fremd=True, mosaik_bis=None, uhr=False):
    d = temp_ordner("test_ortsteine_"); fein = os.path.join(d, "fassade_fein"); fa = os.path.join(d, "fassade"); os.makedirs(os.path.join(fein, "ortho_f00_einzeln")); os.makedirs(fa)
    img, stein = wandbild(ortsteine, uhr)
    F = dict(id="f00", o=[0.0, 0.0], d=[1.0, 0.0], n=[0.0, -1.0], u=[0.0, UW], z=[0.0, ZW], raster=dict(u0=-MARGE, z1=ZW + MARGE, nu=img.shape[1], nz=img.shape[0], zelle=C))
    json.dump(dict(fassaden=[F]), open(os.path.join(fein, "fassaden.json"), "w"))
    json.dump(dict(f00=dict(fotos=[dict(foto="a", rolle="bezug")] + [dict(foto=f"b{i}", rolle="ausgerichtet") for i in range(n_gut - 1)])), open(os.path.join(fein, "fein.json"), "w"))
    mos = img.copy()
    if mosaik_bis is not None: mos[:int((ZW + MARGE - mosaik_bis) / C)] = 0                   # Mosaik sieht oben nichts (Schwabentor Nord: Uhrzone)
    Image.fromarray(mos).save(os.path.join(fein, "ortho_f00_fein.png"))
    for i in range(n_gut): Image.fromarray(img).save(os.path.join(fein, "ortho_f00_einzeln", f"gut{i}.png"))
    if versetzt: Image.fromarray(np.roll(img, 70, axis=1)).save(os.path.join(fein, "ortho_f00_einzeln", "versetzt.png"))     # 0,7 m seitlich versetzt: wird ausgerichtet
    if fremd: Image.fromarray(wandbild(False)[0]).save(os.path.join(fein, "ortho_f00_einzeln", "fremd.png"))              # fremde Putzwand: darf nicht mitstimmen
    if sweep:
        c4 = 0.04; nu4, nz4 = int(UW / c4), int(ZW / c4); jj = ((np.arange(nu4) + 0.5) * c4 + MARGE) / C; ii = (MARGE + (np.arange(nz4) + 0.5) * c4) / C
        st4 = stein[np.ix_(ii.astype(int), jj.astype(int))]; w = np.where(st4, 0.05, 0.0) + rng.normal(0, 0.005, st4.shape)
        np.savez(os.path.join(fa, "tiefe_f00.npz"), w=w.astype(np.float32), gut=np.ones_like(st4), sicher=np.ones(st4.shape, np.float32), u0=0.0, z1=ZW, zelle=c4)
    return fein


# 1 Erkennung
fein = ordner()
J = O.ortsteine_erkennen(fein); Fa = J["fassaden"][0]; K = {k["ende"]: k for k in Fa["kanten"]}
print("   ", [(k["ende"], k["z0"], k["z1"], k["lagen"], k["lang_m"], k["kurz_m"], k["zahnung"], k["vorsprung_m"], k["fotos_bestaetigt"], k["u_stein"], k["stossfugen"], k["tor"]) for k in Fa["kanten"]])
ok(set(K) == {"anfang", "ende"} and len(Fa["kanten"]) == 2, f"beide Kanten je eine Zone ({len(Fa['kanten'])} Zonen)")
ok(all(abs(k["z0"] - Z_A) <= 0.3 and abs(k["z1"] - Z_E) <= 0.3 for k in K.values()), "Zone z 3..15 (volles Mauerwerk darunter ist keine Ortsteinzone)")
ok(all(abs(k["lagen"] - (Z_E - Z_A) / LAGE) <= 3 for k in K.values()), f"Lagen {[k['lagen'] for k in K.values()]} ~ 24")
ok(all(abs(k["lang_m"] - LANG) <= 0.12 and abs(k["kurz_m"] - KURZ) <= 0.12 for k in K.values()), f"lang/kurz {[(k['lang_m'], k['kurz_m']) for k in K.values()]} ~ 1,0/0,6")
ok(all(k["zahnung"] >= 0.8 for k in K.values()), "Zahnung lang/kurz im Wechsel")
ok(abs(K["anfang"]["u_stein"] - LOD2_VERSATZ) <= 0.06 and abs(K["ende"]["u_stein"] - (UW - LOD2_VERSATZ)) <= 0.06, "Fotokante neben der LoD2-Kante erkannt")
al = {e["foto"]: e for e in Fa["einzeln_ausgerichtet"]}
ok("versetzt.png" in al and abs(al["versetzt.png"]["du_m"] + 0.70) <= 0.03 and "fremd.png" not in al, f"Mehrfoto: versetztes Foto um {al.get('versetzt.png', {}).get('du_m')} m ausgerichtet, fremde Putzwand nicht")
ok(all(k["fotos_bestaetigt"] == 4 for k in K.values()), f"Formfamilie aus 4 ausgerichteten Fotos bestaetigt ({[k['fotos_bestaetigt'] for k in K.values()]}), fremde Wand stimmt nicht mit")
# 2 Vorsprung
ok(all(k["vorsprung_m"] is not None and abs(k["vorsprung_m"] - 0.05) <= 0.015 for k in K.values()), "Vorsprung aus dem Ebenen-Sweep 5 cm")
J2 = O.ortsteine_erkennen(ordner(sweep=False)); ok(all(k["vorsprung_m"] is None for k in J2["fassaden"][0]["kanten"]), "ohne Sweep: Vorsprung None (Bau: ANNAHME Druckmass)")
# 3 Bau
from manifold3d import Manifold as M
koerper = M.cube((UW, 8.0, 20.0)).translate((0.0, 0.0, 0.0))                 # Wand bei y = 0, aussen = -y (n)
k2, bel = O.ortsteine_bauen(koerper, J)
me = k2.to_mesh(); V = np.asarray(me.vert_properties)[:, :3]
ok(k2.volume() > koerper.volume() + 0.5 and len(k2.decompose()) == 1, f"Bloecke angebaut, ein Koerper (+{k2.volume() - koerper.volume():.2f} m3)")
ok(abs(-V[:, 1].min() - 0.05) <= 0.01, f"Vorsprung im Modell {-V[:, 1].min():.3f} m")
gb = [g for b in bel if "ortsteine" in b for g in b["ortsteine"]]
ok(len(gb) >= 40 and min(g["z1"] - g["z0"] for g in gb) >= O.druck_m(1.0) - 1e-6 and min(g["b"] for g in gb) >= O.druck_m(1.0) - 1e-6, f"{len(gb)} Lagen, Lage/Breite >= Druckmass")
sl = k2.slice(9.25); sl2 = k2.slice(9.75)                                    # zwei Nachbarlagen: links lang/kurz wechselt
def vorn(s, links=True):
    P = np.vstack([np.asarray(p) for p in s.to_polygons()]); v = P[P[:, 1] < -0.02]; x = v[:, 0][(v[:, 0] < UW / 2) == links]; return x
def vorn_bis(s): return float(vorn(s).max())
ok(abs(abs(vorn_bis(sl) - vorn_bis(sl2)) - (LANG - KURZ)) <= 0.12, f"lang/kurz im Modell (Kante links {vorn_bis(sl):.2f} / {vorn_bis(sl2):.2f} m)")
ok(V[:, 0].min() < -0.03, "Block um die Ecke gefuehrt (Vorsprung auch an der Nachbarseite)")
# 4 Gegenproben
J3 = O.ortsteine_erkennen(ordner(ortsteine=False)); ok(not J3["fassaden"][0]["kanten"], "Putzwand ohne Steine: keine Ortsteine")
J4 = O.ortsteine_erkennen(ordner(n_gut=2, versetzt=False)); k4, b4 = O.ortsteine_bauen(koerper, J4)
ok(not J4["fassaden"][0]["kanten"] and abs(k4.volume() - koerper.volume()) < 1e-6, "nur 2 bestaetigende Fotos: Formfamilie nicht belegt, nichts gebaut")
src = open(os.path.join(HIER, "fassaden_kette.py")).read(); ok("ortsteine_anbauen(koerper, objekt_json)" in src, "fassaden_kette.anbauen ruft ortsteine_anbauen (Generator ruft nur auf)")
# 5 Mosaikluecke aus Einzelfotos (Uhrzone Nord)
J5 = O.ortsteine_erkennen(ordner(mosaik_bis=11.0)); F5 = J5["fassaden"][0]; K5 = {k["ende"]: k for k in F5["kanten"]}
ok(F5.get("ergaenzt") and F5["ergaenzt"]["z1"] >= 17.5 and set(K5) == {"anfang", "ende"} and all(abs(k["z1"] - Z_E) <= 0.3 and k["aus_ergaenzung"] for k in K5.values()),
   f"Mosaik endet bei z 11: aus ausgerichteten Einzelfotos ergaenzt, Zone bis z {[k['z1'] for k in K5.values()]}")
J5b = O.ortsteine_erkennen(ordner(mosaik_bis=11.0, n_gut=1, fremd=False)); F5b = J5b["fassaden"][0]
ok(not F5b.get("ergaenzt") and all(k["z1"] <= 11.3 for k in F5b["kanten"]), "nur 2 Einzelfotos: Luecke NICHT ergaenzt (>= 3 noetig)")
# 6 Uhr im Innenband
J6 = O.ortsteine_erkennen(ordner(uhr=True)); K6 = [k for k in J6["fassaden"][0]["kanten"] if k["ende"] == "anfang"]
ok(len(K6) == 1 and K6[0]["z0"] <= Z_A + 0.3 and K6[0]["z1"] >= Z_E - 0.3, f"Uhr im Innenband: linke Kante bleibt eine Zone ({[(k['z0'], k['z1']) for k in K6]})")
# 7 Lagen ohne Splitter
hs = [s["z1"] - s["z0"] for k in K.values() for s in k["steine"]]
ok(min(hs) >= 0.4, f"keine Splitter: kleinste Lage {min(hs):.2f} m (Soll 0,5)")
c2 = 0.02; n2 = int(3.0 / c2); fu = rng.uniform(0, 0.4, n2); pos = np.arange(int(0.35 / c2), n2, int(0.35 / c2)); fu[pos] = 0.9
lg = O.steinlagen(np.full(n2, 1.5), fu, c2); hl = [(e - a) * c2 for a, e, _ in lg]
ok(len(lg) >= 7 and all(0.25 <= h <= 0.5 for h in hl), f"Pfeiler ohne Verzahnung an Lagerfugen geteilt: {len(lg)} Lagen {[round(h, 2) for h in hl]}")
lg0 = O.steinlagen(np.full(n2, 1.5), rng.uniform(0, 0.4, n2), c2); ok(len(lg0) == 1, f"ohne Lagerfugen (nur Textur) keine Splitter ({len(lg0)} Lage)")
# 8 Stossfugen
for e_, k in K.items():
    st_ = k["steine"]; tl = [len(s["teile"]) for s in st_]; lang_ = [s["b"] > 0.8 for s in st_]
    ok(sum(t == 2 for t, l in zip(tl, lang_) if l) >= 0.8 * sum(lang_) and all(t == 1 for t, l in zip(tl, lang_) if not l),
       f"Stossfugen {e_}: lange Steine 2 Teile ({sum(t == 2 for t, l in zip(tl, lang_) if l)}/{sum(lang_)}), kurze 1")
seg = M.cube((UW / 2, 0.2, 20.0)).translate((0.0, -0.1, 0.0)) ^ k2           # nur der Vorsprung links (y < 0) bis zur Wandmitte
lag = [z for z in (9.25, 9.75) if abs(vorn_bis(k2.slice(z)) - (LOD2_VERSATZ + LANG)) < 0.12][0]
xs = sorted(set(np.round(np.vstack([np.asarray(p) for p in seg.slice(lag).to_polygons()])[:, 0], 3)))
ok(any(LOD2_VERSATZ + STOSS - 0.1 < x < LOD2_VERSATZ + STOSS + 0.1 for x in xs), f"Stossfuge im Modell bei u ~ {LOD2_VERSATZ + STOSS:.2f} (Kanten {xs[:8]})")
# 9 Tor + Kettenstufe
ok(J["tor"]["kanten"] == 2 and J["tor"]["bestanden"] == 2 and all(k["tor"]["iou"] >= 0.8 for k in K.values()), f"Tor bestanden (IoU {[k['tor']['iou'] for k in K.values()]})")
kl_, hell_, rgb_, dat_, _ = O.mosaik_karte(fein, "f00"); c_ = 0.02; Rr = dict(u0=-MARGE, z1=ZW + MARGE)
jk_ = int(round((LOD2_VERSATZ + MARGE) / c_)); i0_, i1_ = int((ZW + MARGE - Z_E) / c_), int((ZW + MARGE - Z_A) / c_)
br_ = np.full(kl_.shape[0], np.nan); br_[i0_:i1_] = 0.8
t_gut = O.tor_kante(kl_, c_, jk_, 1, i0_, i1_, br_, [(a, min(a + 25, i1_ - i0_), LANG if (a // 25) % 2 == 1 else KURZ) for a in range(0, i1_ - i0_, 25)])
t_bad = O.tor_kante(kl_, c_, jk_, 1, i0_, i1_, br_, [(a, min(a + 25, i1_ - i0_), 2.4) for a in range(0, i1_ - i0_, 25)])
ok(t_gut["bestanden"] and t_gut["iou"] >= 0.85 and not t_bad["bestanden"], f"Tor: richtige Lagen IoU {t_gut['iou']} bestanden, 2,4-m-Balken IoU {t_bad['iou']} durchgefallen")
Jx = json.loads(json.dumps(J)); Jx["fassaden"][0]["kanten"][0]["tor"] = dict(t_bad); kx, bx = O.ortsteine_bauen(koerper, Jx)
ok(any("NICHT gebaut (Tor)" in b["element"] for b in bx) and sum(1 for b in bx if "ortsteine" in b) == 1, "Kante mit durchgefallenem Tor wird nicht gebaut")
gk = open(os.path.join(HIER, "gesamtkette.py")).read()
ok('"bauplan_ortsteine"' in gk and "tools/ortsteine.py" in gk and "ortsteine_auto.json" in gk and "ortsteine_auto.jpg" in gk, "Kettenstufe bauplan_ortsteine in gesamtkette (Beleg-JSON + Bild)")
d9 = os.path.dirname(fein); aus9 = os.path.join(d9, "ortsteine_auto.json")
r9 = subprocess.run([sys.executable, "-W", "ignore", os.path.join(HIER, "ortsteine.py"), os.path.join(d9, "objekt.json"), "--fein", fein, "--aus", aus9, "--bild", os.path.join(d9, "o.jpg")], capture_output=True, text=True)
J9 = json.load(open(aus9)) if os.path.exists(aus9) else {}
ok(r9.returncode == 0 and J9.get("tor", {}).get("bestanden") == 2 and os.path.exists(os.path.join(d9, "o.jpg")), f"main: rc {r9.returncode}, Tor-Block, Bild ({r9.stderr[-200:]})")
print(f"alle {n_ok} Ortstein-Pruefungen bestanden")
