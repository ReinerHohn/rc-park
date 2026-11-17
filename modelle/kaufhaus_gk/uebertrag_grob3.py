#!/usr/bin/env python3
"""uebertrag_grob3.py - Figuren und Baldachine des Handmodells kaufhaus_grob3 (dort am Foto trianguliert, M-6120-0xx / M-6161-0xx) in den kaufhaus_gk-Rahmen uebertragen
(17.11.2026 Runde 3). grob3 liegt in einem 1,30x zu grossen Rahmen: Similaritaet grob3 -> gk (s 0,767, R, t) aus der Umriss-/Kantenausrichtung des Koordinators
(sim_g3_gk.json, Kopie in /media/oem/scan/rc-park_daten/kaufhaus_gk/feinteil/sim_g3_gk.json). Lagen werden transformiert, Formmasse mit s skaliert.
Gegenprobe Lage: die 4 Figurenachsen fallen in gk auf u 5,58 / 8,64 / 11,61 / 14,71 = Mitten der Pfeiler zwischen den 5 Vorhangbogenfenstern (5,62 / 8,61 / 11,64 / 14,63,
unabhaengig in Runde 2 aus gk-Fotos gemessen) -> Uebertrag stimmt auf <= 0,08 m.
Schreibt objekt.json bauteile_foto.figuren / .baldachine.  python3 modelle/kaufhaus_gk/uebertrag_grob3.py
"""
import json, os, numpy as np
H = os.path.dirname(os.path.abspath(__file__)); R0 = os.path.dirname(os.path.dirname(H))
SIM = "/media/oem/scan/rc-park_daten/kaufhaus_gk/feinteil/sim_g3_gk.json"
S = json.load(open(SIM)); s = S["s"]; R = np.array(S["R"]); t = np.array(S["t"])
O = os.path.join(H, "objekt.json"); o = json.load(open(O)); BF = o["bauteile_foto"]; T = BF["traufwand"]
a = np.array(T["a"]); b = np.array(T["b"]); et = (b - a) / np.linalg.norm(b - a); en = np.array([et[1], -et[0]])
if (np.array(T["aussen"]) - a) @ en < 0: en = -en
g = {x["typ"]: x for x in json.load(open(os.path.join(R0, "modelle", "kaufhaus_grob3", "objekt.json")))["bauteile"]}
F = g["figurenreihe:figuren"]; B = g["baldachinreihe:baldachine"]
nn = np.array(F["achse_n"], float); nn /= np.linalg.norm(nn); uu = np.array([nn[1], -nn[0]])
def tr(u, sn, z):
    X = np.array([*(u * uu + sn * nn), z]); Y = s * R @ X + t; d = Y[:2] - a; return float(d @ et), float(d @ en), float(Y[2])
W_PUTZ = 0.115     # Putzebene der Traufwand in gk (w vor der LoD2-Ebene): Wandniveau relief/w04_voll.npz bei den Figuren 0,109-0,124 (fassaden_kette.wandniveau)
fig = []
for f in F["figuren"]:
    u, _, zs = tr(f["u"], f["s"], f["z_scheitel"]); fig.append(dict(u=round(u, 3), z_scheitel=round(zs, 3), quelle="grob3: " + f["quelle"]))
ztop = max(z for z, _, _ in F["koerper"])
BF["figuren"] = dict(liste=fig, w_achse=round(W_PUTZ + (F["figuren"][0]["s"] - F["wand_n"]) * s, 3),
                     konsole=[[round((z - ztop) * s, 3), round(r * s, 3)] for z, r in F["konsole"]], koerper=[[round((z - ztop) * s, 3), round(bb * s, 3), round(d * s, 3)] for z, bb, d in F["koerper"]],
                     quelle="UEBERTRAGEN aus kaufhaus_grob3 figurenreihe (Masse dort am Foto trianguliert: " + F["konsole_quelle"][:160] + " ...; Zaehlung " + ", ".join(F["zaehlung"]) + ") per Similaritaet s %.3f (modelle/kaufhaus_gk/uebertrag_grob3.py)" % s,
                     annahmen=["Profile relativ zum Kronenscheitel, ganze Figur auf z_scheitel geschoben (grob3 schob nur den Kopf)", "Huellkoerper ohne Arme/Attribute (wie grob3)", "Achse %.3f m vor der Putzebene w %.3f" % ((F["figuren"][0]["s"] - F["wand_n"]) * s, W_PUTZ)],
                     klipsteil=True)
bal = []
for x in B["baldachine"]:
    u, _, zs = tr(x["u"], B["wand_n"], x["z_spitze"]); bal.append(dict(u=round(u, 3), z_spitze=round(zs, 3), ds=round(x.get("ds", 0.0) * s, 3), quelle="grob3: " + x["quelle"]))
BF["baldachine"] = dict(liste=bal, w_wand=W_PUTZ, einbindung=round(B["einbindung"] * s, 3), kegel_h=round(B["kegel_h"] * s, 3),
                        stufen=[[round(v * s, 3) for v in st] for st in B["stufen"]], fialen=[[round(v * s, 3) for v in fi] for fi in B["fialen"]],
                        quelle="UEBERTRAGEN aus kaufhaus_grob3 baldachinreihe (" + B["quelle"][:200] + ") per Similaritaet s %.3f (uebertrag_grob3.py); Zaehlung " % s + ", ".join(B["zaehlung"]),
                        annahmen=["Form aller 4 wie gemessener Baldachin 2 (grob3)", "Seitenfialen symmetrisch (grob3 ANNAHME)", "Masswerk/Blattwerk nicht einzeln"], klipsteil=True)
json.dump(o, open(O, "w"), indent=1, ensure_ascii=False)
print("Figuren u", [f["u"] for f in fig], "Baldachine u", [x["u"] for x in bal])
