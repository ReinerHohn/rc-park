#!/usr/bin/env python3
"""test_malplan.py - fester synthetischer Test fuer tools/malplan.py (24.11.2026), < 15 s, nur CPU.

Synthetisches 1-cm-Wandbild 4 m x 8 m mit drei Zonen (wie ein fassade_fein-Ordner der Kette):
  links Putz (hell, leicht verrauscht), rechts Sandstein-Quader (rotbraun, dunklere Fugen 1,5 cm im Verband),
  im Putz ein Fenster 1,0 x 1,5 m (dunkel), dazu ein 5-cm-Fleck (unter der H0-Mindestzone (2 mm)^2 -> muss verschwinden)
  und ein oberer Streifen ohne Abdeckung (darf nicht gezaehlt werden).
Erwartet: genau Putz / Sandstein-Quader / Fenster dunkel mit den richtigen Anteilen, Putzfarbe nahe am Soll, Reihenfolge Putz zuerst / Fenster
zuletzt, 5 Malschritte in fester Reihenfolge, keine OBI-Farbe als Grundton, keine Zone unter der Mindestflaeche, Ausgaben da.
Rot-Probe: ohne Fenster -> keine Fenster-Zone (Fugen/Quader werden NICHT zur Oeffnung).
"""
import sys, os, json, numpy as np
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(HIER), "tools"))
from PIL import Image
from scipy import ndimage as ndi
from pfade import temp_ordner
import malplan as MP

F = 0


def pruef(ok, text):
    global F
    print(("  ok     " if ok else "  FEHLER ") + text)
    if not ok: F += 1


def wand(mit_fenster=True, seed=3):
    rng = np.random.default_rng(seed); H, W = 800, 400                      # 1 cm je Pixel
    img = np.zeros((H, W, 3), float)
    img[:, :200] = MP.hex_zu_rgb("#e6e2d8")                                    # Putz
    img[:, 200:] = MP.hex_zu_rgb("#8a5545")                                    # Sandstein
    yy, xx = np.mgrid[:H, :W]
    lage = yy // 30; fuge = (yy % 30 < 2) | (((xx + 30 * (lage % 2)) % 60) < 2)
    img[(xx >= 200) & fuge] = MP.hex_zu_rgb("#5a3a30")                        # Fugen im Quaderverband
    stein = (xx >= 200) & ~fuge
    img[stein] += rng.normal(0, 6, (stein.sum(), 1))                           # Steine leicht unterschiedlich hell
    if mit_fenster: img[300:450, 50:150] = MP.hex_zu_rgb("#1e1e22")           # Fenster 1,0 x 1,5 m
    img[600:605, 100:105] = MP.hex_zu_rgb("#202020")                           # 5-cm-Fleck
    img += rng.normal(0, 3, img.shape)
    ab = np.full((H, W), 255, np.uint8); ab[:50] = 0                           # oben keine Abdeckung
    img[:50] = 0
    return np.clip(img, 0, 255).astype(np.uint8), ab


def schatten(rgb, faktor=(0.30, 0.36, 0.50)):
    """Schattenseite mit Blaustich: linear je Kanal abdunkeln (Himmelslicht statt Sonne)."""
    return MP.linear_zu_srgb(MP.srgb_zu_linear(rgb) * np.array(faktor)[None, None, :]).round().astype(np.uint8)


def ordner_bauen(d, mit_fenster, objekt=None, zweite_wand=False):
    rgb, ab = wand(mit_fenster)
    Image.fromarray(rgb).save(os.path.join(d, "ortho_f00_fein.png")); Image.fromarray(ab).save(os.path.join(d, "abdeckung_f00_fein.png"))
    fa = [dict(id="f00", n=[0.99, 0.05], raster=dict(zelle=0.01, u0=0, z1=8, nu=400, nz=800))]
    if zweite_wand:                                                              # Gegenseite: gleiche Materialien, im Schatten + Farbstich
        rgb2, ab2 = wand(mit_fenster, seed=7); rgb2 = schatten(rgb2); rgb2[ab2 == 0] = 0
        Image.fromarray(rgb2).save(os.path.join(d, "ortho_f01_fein.png")); Image.fromarray(ab2).save(os.path.join(d, "abdeckung_f01_fein.png"))
        fa.append(dict(id="f01", n=[-0.99, -0.05], raster=dict(zelle=0.01, u0=0, z1=8, nu=400, nz=800)))
    json.dump(dict(objekt=objekt, fassaden=fa), open(os.path.join(d, "fassaden.json"), "w"))


def main():
    t = temp_ordner("test_malplan_"); ein = os.path.join(t, "fassade_fein"); aus = os.path.join(t, "aus"); os.makedirs(ein)
    oj = os.path.join(t, "objekt.json"); json.dump(dict(seiten_konvention={"+x": "Nord", "-x": "Sued", "+y": "West", "-y": "Ost"}), open(oj, "w"))
    ordner_bauen(ein, True, objekt=oj)
    rc = MP.main([os.path.dirname(ein), "--aus", aus, "--objekt", "test"])      # Datenordner: fassade_fein darunter wird gefunden; objekt.json aus fassaden.json
    pruef(rc == 0, f"rc 0 (ist {rc})")
    for f_ in ("malplan.json", "malplan.md", "malplan_Nord_f00.jpg"): pruef(os.path.exists(os.path.join(aus, f_)), f"Ausgabe {f_} da (Seite aus objekt.json seiten_konvention: Normale +x = Nord)")
    plan = json.load(open(os.path.join(aus, "malplan.json"))); w = plan["waende"][0]; z = {z_["material"]: z_ for z_ in w["zonen"]}
    pruef(set(z) == {"Putz", "Sandstein-Quader", "Fenster dunkel"}, f"genau drei Zonen Putz/Sandstein/Fenster (ist {sorted(z)})")
    soll = {"Putz": (200 * 750 - 100 * 150) / (400 * 750), "Sandstein-Quader": 0.5, "Fenster dunkel": 100 * 150 / (400 * 750)}
    for m, s in soll.items():
        if m in z: pruef(abs(z[m]["anteil"] - s) < 0.03, f"Anteil {m} {z[m]['anteil']:.3f} ~ {s:.3f} (+-0,03; Fleck + unbedeckter Streifen zaehlen nicht)")
    if "Putz" in z:
        de = MP.delta_e(MP.rgb_zu_lab(MP.hex_zu_rgb(z["Putz"]["hex"])), MP.rgb_zu_lab(MP.hex_zu_rgb("#e6e2d8")))
        pruef(de < 6, f"Putzfarbe {z['Putz']['hex']} nahe #e6e2d8 (dE {de:.1f} < 6)")
    if "Sandstein-Quader" in z:
        L = [t_["L"] for t_ in z["Sandstein-Quader"]["toene"]]
        pruef(MP.rgb_zu_lab(MP.hex_zu_rgb(z["Sandstein-Quader"]["ton_dunkel"]))[0] <= MP.rgb_zu_lab(MP.hex_zu_rgb(z["Sandstein-Quader"]["ton_hell"]))[0] + 1e-6,
              f"Sandstein: dunkler Ton (Lasur) <= heller Ton (Trockenbuersten), Toene L {L}")
    reih = [z_["material"] for z_ in sorted(w["zonen"], key=lambda z_: z_.get("reihenfolge", 999))]
    pruef(reih[0] == "Putz" and reih[-1] == "Fenster dunkel", f"Reihenfolge grosse Grundflaeche zuerst, Fenster zuletzt ({reih})")
    ok_s = all([s_["schritt"] for s_ in z_["schritte"]] == ["Grundierung", "Grundton", "Lasur", "Trockenbuersten", "Mattlack"] for z_ in w["zonen"])
    pruef(ok_s, "je Zone 5 Malschritte Grundierung -> Grundton -> Lasur -> Trockenbuersten -> Mattlack")
    pruef(not any("OBI" in z_["mischung"]["text"] or "OBI" in z_["palette"]["name"] for z_ in w["zonen"]), "OBI-Farben nie als Grundton (nur Lasur)")
    # Mindestflaeche: Labelbild neu rechnen und Zusammenhangsteile pruefen
    rgb, ab = wand(True); g = (ab > 0) & (rgb.max(2) > 3)
    zonen, voll, info = MP.malplan_wand(rgb, g, 0.01)
    klein = min((int(np.bincount(ndi.label(voll == zl)[0].ravel())[1:].min()) for zl in np.unique(voll[voll >= 0])), default=0)
    min_voll = info["min_zone_px"] * (info["arbeit_zelle_m"] / 0.01) ** 2
    pruef(klein >= min_voll * 0.99, f"kleinstes Zusammenhangsteil {klein} px >= Mindestzone {min_voll:.0f} px ((2 mm H0)^2)")
    pruef((voll[~g] == -1).all(), "ungueltige Flaeche (keine Abdeckung) bleibt ohne Zone")
    # Rot-Probe: ohne Fenster keine Oeffnung (Fugen/Quader duerfen nicht zum Fenster werden)
    ein2 = os.path.join(t, "ohne", "fassade_fein"); os.makedirs(ein2); ordner_bauen(ein2, False)
    MP.main([ein2, "--aus", os.path.join(t, "aus2")])
    m2 = {z_["material"] for z_ in json.load(open(os.path.join(t, "aus2", "malplan.json")))["waende"][0]["zonen"]}
    pruef(m2 == {"Putz", "Sandstein-Quader"}, f"Rot-Probe ohne Fenster: nur Putz + Sandstein (ist {sorted(m2)})")
    pruef(os.path.exists(os.path.join(t, "aus2", "malplan_f00.jpg")), "ohne objekt.json-Konvention: nur Wand-ID, keine eigene Kompassrechnung (malplan_f00.jpg)")
    # Weissabgleich: Sonnenwand + Schattenwand mit Blaustich -> gleiche Materialfarbe je Material, Gebaeudefarbe je Material
    ein3 = os.path.join(t, "wb", "fassade_fein"); os.makedirs(ein3); ordner_bauen(ein3, True, objekt=oj, zweite_wand=True)
    rc3 = MP.main([ein3, "--aus", os.path.join(t, "aus3")]); p3 = json.load(open(os.path.join(t, "aus3", "malplan.json")))
    w3 = {w_["wand"]: {z_["material"]: z_ for z_ in w_["zonen"]} for w_ in p3["waende"]}
    pruef(rc3 == 0 and set(w3) == {"Nord_f00", "Sued_f01"}, f"zwei Waende Nord_f00 + Sued_f01 (ist {sorted(w3)})")
    lab = lambda h_: MP.rgb_zu_lab(MP.hex_zu_rgb(h_))
    for m in ("Putz", "Sandstein-Quader"):
        if all(m in v for v in w3.values()):
            de = MP.delta_e(lab(w3["Nord_f00"][m]["hex"]), lab(w3["Sued_f01"][m]["hex"]))
            pruef(de < 5, f"{m}: Sonne {w3['Nord_f00'][m]['hex']} ~ Schatten {w3['Sued_f01'][m]['hex']} nach Abgleich (dE {de:.1f} < 5)")
        else: pruef(False, f"{m} fehlt auf einer Wand ({ {k: sorted(v) for k, v in w3.items()} })")
    roh_s = MP.rgb_zu_hex(MP.linear_zu_srgb(MP.srgb_zu_linear(MP.hex_zu_rgb("#8a5545")) * np.array((0.30, 0.36, 0.50))))
    pruef(MP.delta_e(lab(roh_s), lab("#8a5545")) > 20, f"Probe ist hart: Schatten-Sandstein roh {roh_s} weicht stark ab (dE > 20)")
    pruef(w3["Sued_f01"].get("Sandstein-Quader", {}).get("lab", [0])[0] > 30, "Schattenseite-Sandstein nach Abgleich nicht schwarz (L* > 30)")
    g3 = p3.get("gebaeude") or {}
    pruef({"Putz", "Sandstein-Quader"} <= set(g3) and len(g3["Sandstein-Quader"]["waende"]) == 2, f"Gebaeude: eine Farbe je Material ueber beide Waende ({ {k: v['hex'] for k, v in g3.items()} })")
    if "Putz" in g3: pruef(np.hypot(*lab(g3["Putz"]["hex"])[1:]) < 3, f"Gebaeude-Putz neutral ({g3['Putz']['hex']})")
    gn = [w_["weissabgleich"]["gain"] for w_ in p3["waende"]]
    pruef(gn[1][0] > gn[1][2] > 1.5, f"Schattenwand: Verstaerkung {gn[1]} hebt an und gleicht den Blaustich aus (Rot > Blau > 1,5)")
    print(f"test_malplan: {'BESTANDEN' if F == 0 else f'{F} FEHLER'}")
    return 1 if F else 0


if __name__ == "__main__":
    sys.exit(main())
