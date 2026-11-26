#!/usr/bin/env python3
"""Fester Test (~2 s) fuer tools/abdeckung_meldung.py - Abdeckungsmeldung nach der Registrierung (Spec Vollautomatik 1b-1d, Abnahmekriterium 2, Nutzer 26.11.2026).
Datensatz: tools/testdata/abdeckung_handy_20261126_mini.json = echte Kameras/Punkte/Registriereintraege der Handyfotos Schwabentor 26.11. (Modellrahmen), 'kameras_wand'
sehen den Treppenturm nicht (dort fehlt die Einordnung), 'kameras_treppenturm' sehen ihn.
  1 Einordnung fehlt  nur Wandkameras -> Fotoauftrag nennt Bruecke, Treppe, Unterdurchgang UND Treppenturm (ROT, wenn eine fehlt); Treppenturm mit Standpunkten ausserhalb
                      des Baukoerpers, Blick zur Turmmitte, Kompass + GPS; Stellen ohne Lage mit Anschlussweg, im Modell 'nicht belegt'.
  2 Gegenprobe        Nord/Sued/Ost sind belegt und stehen NICHT im Auftrag (sonst waere 1 trivial); West haengt an den Treppenturm-Kameras (siehe 3).
  3 Tauschtest        + Treppenturm-Kameras -> Treppenturm verschwindet aus dem Auftrag (gemessen, nicht gelistet); Stellen ohne Lage bleiben.
  4 Gruende           je nicht eingeordnetem Foto genau ein Grund nach n_korr/min_inlier; Foto ohne Registriereintrag -> 'nicht versucht'; Summen stimmen.
  5 Konfiguration     modelle/schwabentor-1122/abdeckung_zonen.json fuehrt die vier Sonderstellen; Markdown nennt jede Auftragsstelle.
Python: /media/oem/scan/venv-seg/bin/python -I tools/test_abdeckung_meldung.py (cv2 nur fuer das Bild; ohne cv2 wird es uebersprungen)."""
import os, sys, json, math, copy
import numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import abdeckung_meldung as AM

D = json.load(open(os.path.join(T, "testdata", "abdeckung_handy_20261126_mini.json")))
VIER = ("Bruecke", "Treppe", "Unterdurchgang", "Treppenturm")
kam = lambda L: [dict(k, C=np.array(k["C"]), R=np.array(k["R"])) for k in L]
P = np.array(D["punkte"]); reg = D["registrierung"]; neu = [n for n, v in reg["bilder"].items() if v["status"] == "registriert"]
fehler = []


def pruef(bed, text):
    if not bed: fehler.append(text); print("FEHLER:", text)


# ---------- 1 Einordnung fehlt am Treppenturm (und Bruecke/Treppe/Unterdurchgang ohne Lage)
m, zonen = AM.melden(D["objekt"], D["zonen"], kam(D["kameras_wand"]), neu, reg, P)
auf = {a["stelle"]: a for a in m["fotoauftrag"]}; zs = {e["name"]: e for e in m["zonen"]}
for s in VIER: pruef(s in auf, f"Fotoauftrag nennt {s} nicht, obwohl dort die Einordnung fehlt (Auftrag: {sorted(auf)})")
for s in VIER:
    if s in auf: pruef(auf[s]["im_modell"] == "nicht belegt" and auf[s]["anweisung"] and auf[s]["grund"], f"{s}: Auftrag ohne Grund/Anweisung/'nicht belegt'")
for s in ("Bruecke", "Treppe", "Unterdurchgang"):
    if s in auf: pruef("Lage unbekannt" in auf[s]["anweisung"] and zs[s]["status"] == "nicht belegt", f"{s}: ohne Lage muss 'Lage unbekannt' + Anschlussweg stehen")
if "Treppenturm" in auf:
    a = auf["Treppenturm"]; tt = next(z for z in zonen if z["name"] == "Treppenturm"); u0, u1, v0, v1, _ = tt["koerper"]; c = np.array(tt["mitte"][:2])
    pruef(len(a["standpunkte"]) >= 3, f"Treppenturm: {len(a['standpunkte'])} Standpunkte < 3 (Faecher)")
    for s in a["standpunkte"]:
        p = np.array([s["x"], s["y"]]); pruef(not (u0 < p[0] < u1 and v0 < p[1] < v1), f"Treppenturm-Standpunkt {s['nr']} im Baukoerper")
        b = math.radians(s["blick_modell_grad"]); pruef(np.dot([math.cos(b), math.sin(b)], (c - p) / np.linalg.norm(c - p)) > 0.99, f"Standpunkt {s['nr']} blickt nicht zum Treppenturm")
        pruef(s["blick_kompass_grad"] is not None and s["abstand_m"] >= AM.MIN_ABSTAND_M, f"Standpunkt {s['nr']}: Kompass/Abstand fehlt")
    pruef(all(s.get("gps") for s in a["standpunkte"]), "Treppenturm-Standpunkte ohne GPS")
    pruef(zs["Treppenturm"]["fotos"] == 0, f"Treppenturm: {zs['Treppenturm']['fotos']} Fotos gezaehlt, Datensatz hat dort keine Einordnung")
# ---------- 2 Gegenprobe Waende (West nicht: im echten Bestand sieht jede Kamera, die mehr als 36 % der Westwand zeigt, auch den Treppenturm -> ohne
#            Treppenturm-Einordnung ist West ehrlich 'duenn'; geprueft wird West im Tauschtest)
for w in ("Nord", "Sued", "Ost"):
    pruef(zs[w]["status"] == "belegt" and w not in auf, f"Wand {w}: {zs[w]['status']} {zs[w]['fehlt']} - Gegenprobe verlangt belegt")
    pruef(zs[w]["fotos"] >= AM.MIN_FOTOS and zs[w]["faecher_grad"] >= AM.MIN_FAECHER_GRAD, f"Wand {w}: Fotos/Faecher unter Schwelle")
# ---------- 3 Tauschtest: Treppenturm-Kameras dazu
m2, _ = AM.melden(D["objekt"], D["zonen"], kam(D["kameras_wand"] + D["kameras_treppenturm"]), neu, reg, P)
auf2 = {a["stelle"] for a in m2["fotoauftrag"]}; z2 = {e["name"]: e for e in m2["zonen"]}
pruef("Treppenturm" not in auf2, f"Treppenturm trotz {z2['Treppenturm']['fotos']} sehender Kameras im Auftrag ({z2['Treppenturm']['fehlt']})")
pruef({"Bruecke", "Treppe", "Unterdurchgang"} <= auf2, "Stellen ohne Lage duerfen durch mehr Wandkameras nicht verschwinden")
pruef(z2["West"]["zellen_gesehen"] > zs["West"]["zellen_gesehen"], "Westwand: Treppenturm-Kameras muessten auch die Westwand mehr zeigen")
# ---------- 4 Gruende je nicht eingeordnetem Foto
mi = reg["min_inlier"]; nie = {x["foto"]: x for x in m["nicht_eingeordnete_fotos"]}
for n, v in reg["bilder"].items():
    if v["status"] == "registriert": pruef(n not in nie, f"{n} ist eingeordnet, steht aber in der Liste"); continue
    soll = "keine Korrespondenz" if v["n_korr"] == 0 else ("zu wenige Matches" if v["n_korr"] < mi else "Lage nicht berechenbar")
    pruef(nie.get(n, {}).get("grund") == soll, f"{n}: Grund {nie.get(n, {}).get('grund')} statt {soll} (n_korr {v['n_korr']})")
for g in ("keine Korrespondenz", "zu wenige Matches", "Lage nicht berechenbar"): pruef(m["gruende"][g] == 4, f"Grund {g}: {m['gruende'][g]} statt 4")
m3, _ = AM.melden(D["objekt"], D["zonen"], kam(D["kameras_wand"]), neu, reg, P, bilder=list(reg["bilder"]) + ["IMG_ohne_eintrag.jpg"])
pruef(m3["gruende"]["nicht versucht"] == 1 and m3["nicht_eingeordnet"] == m["nicht_eingeordnet"] + 1, "Foto ohne Registriereintrag nicht als 'nicht versucht' gemeldet")
pruef(m["eingeordnet"] + m["nicht_eingeordnet"] == m["fotos"] == len(reg["bilder"]), "Summen eingeordnet/nicht eingeordnet stimmen nicht")
# ---------- 5 Konfiguration im Objektordner + Ausgabe
live = json.load(open(os.path.join(T, "..", "modelle", "schwabentor-1122", "abdeckung_zonen.json")))
pruef(set(VIER) - {"Treppenturm"} <= {s["name"] for s in live["sonderstellen"]} and "Treppenturm" in {s["name"] for s in live["sonderstellen"]},
      "modelle/schwabentor-1122/abdeckung_zonen.json fehlt eine der vier Sonderstellen")
md = AM.markdown(m)
for s in auf: pruef(f"**{s}**" in md, f"Markdown nennt {s} nicht")
tmp = __import__("pfade").temp_ordner("test_abdeckung_meldung_"); b = AM.bild(os.path.join(tmp, "a.png"), m, zonen, kam(D["kameras_wand"]), set(neu))
pruef(b is None or os.path.getsize(b) > 1000, "Bild leer")
print("Auftrag:", ", ".join(sorted(auf)), "| Waende:", {w: zs[w]["status"] for w in ("Nord", "Sued", "West", "Ost")}, "| Gruende:", m["gruende"])
if fehler: print(f"ROT: {len(fehler)} Fehler"); sys.exit(1)
print("ok test_abdeckung_meldung")
