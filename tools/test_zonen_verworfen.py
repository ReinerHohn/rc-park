#!/usr/bin/env python3
"""Test: verworfene Erkennungen sind keine Bauteil-Zonen (befundliste.bauteil_zonen -> neben_details, befundliste).

Befund 24.11.2026 (Kette 1122zb, Schwabentor f01): neben_details zeigte 'uhr_f01_2' auf dem Wandgemaelde (Goldnimbus der Heiligen) und 'uhr_f01_3' als
Zackenrechteck im Ziffernring. Beide stammen aus der Liste 'verworfen' in audit/uhren_auto.json (uhren_wandbild: kein 12er-Zifferblatt), gebaut wurden sie nie -
bauteil_zonen lief aber rekursiv auch in 'verworfen' hinein und machte aus jedem verworfenen Kasten eine "Uhr".
Synthetisch: eine angenommene Uhr + zwei verworfene Kandidaten, eine verworfene Vorbau-Gruppe ('verworfen': Grund) und eine gebaute Gruppe mit verworfenen
FOTOS (Liste von Namen, kein Kasten) -> nur angenommene Uhr + gebaute Gruppe sind Zonen, die Uhr mit Kreis-Kontur.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pfade
import befundliste as BL

d = pfade.temp_ordner("zonen_verworfen_")
uhren = {"f01": {"o": [0, 0], "d": [1, 0], "n": [0, 1],
                  "uhren": [{"u": 0.0, "z": 31.8, "d_aussen": 4.8, "kasten": [-2.6, 2.4, 29.4, 34.4]}],
                  "verworfen": [{"kasten": [0.7, 2.4, 16.2, 17.8], "grund": "kein Zifferblatt: 12er-Teilung 1.01"},
                                {"kasten": [-1.8, 1.6, 30.2, 33.6], "grund": "kein Zifferblatt: 12er-Teilung 0.43"}]}}
vorbauten = {"f02": {"gruppen": [{"u0": 1.0, "u1": 3.0, "z0": 2.0, "z1": 5.0, "verworfen": "Beleg-Tor: Phantom"},
                                 {"u0": 5.0, "u1": 7.0, "z0": 2.0, "z1": 5.0, "verworfen": ["foto_a", "foto_b"]},
                                 {"u0": 8.0, "u1": 9.0, "z0": 2.0, "z1": 5.0, "status": "verworfen"}]}}
json.dump(uhren, open(os.path.join(d, "uhren_auto.json"), "w"))
json.dump(vorbauten, open(os.path.join(d, "vorbauten_auto.json"), "w"))

Z = BL.bauteil_zonen(d)
uz = [z for z in Z if z["name"].startswith("uhren")]
vz = [z for z in Z if z["name"].startswith("vorbau")]
fehler = []
if len(uz) != 1: fehler.append(f"FEHLER: {len(uz)} Uhr-Zonen statt 1 (verworfene Kandidaten zaehlen mit): {[(z['u0'], z['z0']) for z in uz]}")
elif not uz[0].get("kreis") or abs(uz[0]["kreis"][2] - 2.4) > 1e-6: fehler.append(f"FEHLER: angenommene Uhr ohne Kreis-Kontur: {uz[0]}")
if len(vz) != 1 or abs(vz[0]["u0"] - 5.0) > 1e-6: fehler.append(f"FEHLER: Vorbau-Zonen {[(z['u0'], z['u1']) for z in vz]} statt nur der gebauten Gruppe u0=5 (Grund-Text/status verworfen = kein Bauteil, Fotoliste schon)")
if not hasattr(BL, "verworfen_eintrag"): fehler.append("FEHLER: befundliste.verworfen_eintrag fehlt")
elif not BL.verworfen_eintrag({"verworfen": True}) or BL.verworfen_eintrag({"verworfen": []}) or BL.verworfen_eintrag({}): fehler.append("FEHLER: verworfen_eintrag falsch")
print("\n".join(fehler) if fehler else f"OK: {len(Z)} Zonen, verworfene Uhr-Kandidaten und Vorbau-Gruppen ausgeschlossen, Uhr mit Kreis")
sys.exit(1 if fehler else 0)
