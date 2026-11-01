#!/usr/bin/env python3
"""beobachtungen_sichten.py - automatische Beobachtungen BEWERTEN, statt sie einzeln von Hand durchzugehen.

Die Foto-Werkzeuge melden pro Foto, was ihnen auffaellt. Einzelne Meldungen sind schwach (Kamerafehler, Verdeckung, Rauschen).
Dieses Werkzeug gruppiert sie nach Hoehe und entscheidet nach einer festen Regel:
  BESTAETIGT   >= 2 Fotos, gleiches Vorzeichen, Mittel >= 0,5 m   -> Ursache isolieren, Pruefzeile anlegen
  UNEINS       >= 2 Fotos, aber gegensaetzlich                     -> Kamerafehler/Verdeckung, verwerfen (mit Begruendung)
  EINZELN      nur ein Foto                                        -> bleibt offen, braucht ein zweites Foto
  TEXTUR       Fehlteil-Treffer an der Fassadenkante ueber viele Hoehen -> Steinfugen/Quader, kein Bauteil
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/beobachtungen_sichten.py modelle/<objekt>/objekt.json [--anwenden]
Ohne --anwenden wird nur berichtet. Mit --anwenden werden UNEINS und TEXTUR mit Begruendung geschlossen (in 'beobachtungen_erledigt').
"""
import sys, os, json, numpy as np

def main():
    objp = sys.argv[1]; anwenden = "--anwenden" in sys.argv
    obj = json.load(open(objp)); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(objp))))
    tp = os.path.join(root, obj["masstabelle"]); tab = json.load(open(tp)); beob = tab.get("beobachtungen_offen", [])
    auto = [b for b in beob if b.get("art")]; hand = [b for b in beob if not b.get("art")]
    # Gruppieren nach UEBERLAPPUNG der Hoehenzonen (nicht nach Zonenanfang - sonst trennt man 29,0-31,5 von 31,0-33,5,
    # obwohl beide dieselbe Stelle meinen; genau das verdeckte 2026-11-01 einen von zwei Fotos bestaetigten Befund).
    gruppen = []
    for b in sorted(auto, key=lambda x: x.get("z_von", 0)):
        # echte Ueberlappung (keine Toleranz) UND Gruppe hoechstens 5 m hoch - sonst kettet sich eine Gruppe
        # ueber den halben Turm (27-35 m) und mischt verschiedene Stellen zu einem Schein-Widerspruch.
        passt = next((g for g in gruppen if g["art"] == b["art"]
                      and b["z_von"] <= max(x["z_bis"] for x in g["b"])
                      and b["z_bis"] >= min(x["z_von"] for x in g["b"])
                      and max(b["z_bis"], max(x["z_bis"] for x in g["b"])) - min(b["z_von"], min(x["z_von"] for x in g["b"])) <= 5.0), None)
        if passt: passt["b"].append(b)
        else: gruppen.append({"art": b["art"], "b": [b]})
    print(f"{len(auto)} automatische Beobachtungen -> {len(gruppen)} Hoehengruppen ({len(hand)} von Hand bleiben unberuehrt)\n")
    erledigt, offen = [], list(hand); bestaetigt = []
    for g in sorted(gruppen, key=lambda g: -abs(np.mean([x["abweichung"] for x in g["b"]]))):
        fotos = sorted({x["foto"] for x in g["b"]}); w = [x["abweichung"] for x in g["b"]]
        zv, zb = min(x["z_von"] for x in g["b"]), max(x["z_bis"] for x in g["b"]); mw = float(np.mean(w))
        if g["art"] == "fehlteil":
            y = [abs(x["xyz"][1]) for x in g["b"] if "xyz" in x]
            kante = bool(y) and np.mean(y) > 4.5
            status = "TEXTUR" if kante else ("BESTAETIGT" if len(fotos) >= 2 else "EINZELN")
            grund = "Treffer an der Fassadenkante (|y| > 4,5 m) ueber mehrere Hoehen = Steinfugen/Eckquader, kein fehlendes Bauteil" if kante else ""
        else:
            if len(fotos) >= 2 and min(w) * max(w) < 0:
                paare = ", ".join(f"{b['foto']}{b['abweichung']:+.2f}" for b in g["b"])
                status, grund = "UNEINS", f"Fotos gegensaetzlich ({paare}) - Kamerafehler oder Verdeckung"
            elif len(fotos) >= 2 and abs(mw) >= 0.5: status, grund = "BESTAETIGT", ""
            elif len(fotos) >= 2: status, grund = "UNEINS", f"beide Fotos unter 0,5 m Abweichung (Mittel {mw:+.2f}) - im Rauschen"
            else: status, grund = "EINZELN", ""
        print(f"  {status:10s} z {zv:5.1f}-{zb:5.1f} m  {g['art']:9s}  Fotos {','.join(fotos):12s}  Abweichung {mw:+.2f} m  {grund[:70]}")
        if status in ("UNEINS", "TEXTUR"):
            for b in g["b"]: erledigt.append(dict(b, status=status, begruendung=grund))
        else:
            offen += g["b"]
            if status == "BESTAETIGT": bestaetigt.append((zv, zb, g["art"], fotos, mw))
    print(f"\n{len(bestaetigt)} BESTAETIGT (Ursache isolieren + Pruefzeile), {len([b for b in offen if b.get('art')])} EINZELN (zweites Foto noetig), {len(erledigt)} geschlossen")
    for zv, zb, art, fotos, mw in bestaetigt: print(f"  -> z {zv:.1f}-{zb:.1f} m ({art}, Fotos {','.join(fotos)}, {mw:+.2f} m)")
    if anwenden:
        tab["beobachtungen_offen"] = offen; tab.setdefault("beobachtungen_erledigt", []).extend(erledigt)
        json.dump(tab, open(tp, "w"), indent=1, ensure_ascii=False); print(f"\nangewendet: {len(erledigt)} geschlossen, {len(offen)} bleiben offen")

if __name__ == "__main__":
    main()
