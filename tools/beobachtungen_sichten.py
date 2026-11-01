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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
            elif len(fotos) >= 2:
                # JE FOTO mitteln und verlangen, dass JEDES fuer sich deutlich abweicht. Ein Mittelwert ueber Fotos
                # verdeckt Uneinigkeit: 030 mit +1,60 und 031 mit +0,00 ergeben +0,80 und saehen bestaetigt aus
                # (2026-11-01, Befund 36-41 m). Dieselbe Falle wie beim Zonenmittel gegen Einzelhoehe.
                je = {f: float(np.mean([x["abweichung"] for x in g["b"] if x["foto"] == f])) for f in fotos}
                paare = ", ".join(f"{f}{v:+.2f}" for f, v in je.items())
                # Zuerst: ist die MESSUNG ueberhaupt gueltig (messen die Fotos dasselbe)? Erst dann die Frage nach dem Befund.
                import messung_pruefen as MP
                gueltig, text = MP.pruefe(je, 0.3, "Streuung")
                if not gueltig: status, grund = "MESSUNG UNGUELTIG", text.split(") ")[1] if ") " in text else text
                elif min(abs(v) for v in je.values()) >= 0.4: status, grund = "BESTAETIGT", f"je Foto: {paare}"
                else: status, grund = "SCHWACH", f"je Foto: {paare} - mindestens ein Foto unter 0,4 m, nicht belastbar"
            else: status, grund = "EINZELN", ""
        print(f"  {status:10s} z {zv:5.1f}-{zb:5.1f} m  {g['art']:9s}  Fotos {','.join(fotos):12s}  Abweichung {mw:+.2f} m  {grund[:70]}")
        if status in ("UNEINS", "TEXTUR", "SCHWACH", "MESSUNG UNGUELTIG"):
            for b in g["b"]: erledigt.append(dict(b, status=status, begruendung=grund))
        else:
            offen += g["b"]
            if status == "BESTAETIGT": bestaetigt.append((zv, zb, g["art"], fotos, mw))
    print(f"\n{len(bestaetigt)} BESTAETIGT (Ursache isolieren + Pruefzeile), {len([b for b in offen if b.get('art')])} EINZELN (zweites Foto noetig), {len(erledigt)} geschlossen")
    print("Regel: BESTAETIGT nur, wenn JEDES beteiligte Foto fuer sich >= 0,4 m abweicht und alle dasselbe Vorzeichen haben.")
    for zv, zb, art, fotos, mw in bestaetigt: print(f"  -> z {zv:.1f}-{zb:.1f} m ({art}, Fotos {','.join(fotos)}, {mw:+.2f} m)")
    # NACHPRUEFEN: fuer jeden EINZELN-Befund die anderen Kameras an genau dieser Hoehe befragen - auch wenn sie dort
    # keine eigene Zone gemeldet haben (eine Abweichung unter der Meldeschwelle ist trotzdem eine Aussage).
    # Diese Mechanik fehlte: Einzelbefunde blieben liegen, darunter die Tuermchen-Gliederung, die der Nutzer fand.
    if "--nachpruefen" in sys.argv:
        import subprocess, glob as _g
        einzel = [b for b in offen if b.get("art") == "breite"]
        alle = sorted({os.path.basename(x)[2:-5] for x in _g.glob(os.path.join(root, os.path.dirname(obj["masstabelle"]), "messprotokoll", "K-*.json"))})
        print(f"\nNachpruefung von {len(einzel)} Einzelbefund(en) an den uebrigen Kameras {alle}:")
        for b in einzel:
            andere = [f for f in alle if f != b["foto"]]; werte = {b["foto"]: b["abweichung"]}
            for f in andere:
                r = subprocess.run([sys.executable, "-W", "ignore", "-I", os.path.join(root, "tools", "foto_breitenprofil.py"), objp, f,
                                    "--von", str(b["z_von"]), "--bis", str(b["z_bis"]), "--schritt", "0.5"],
                                   capture_output=True, text=True, env=dict(os.environ, OBJEKT=os.path.abspath(objp)))
                zs = [l.split("|") for l in r.stdout.split("\n") if l.strip().startswith(("3", "4", "2")) and "|" in l]
                d = [float(z[-1].split()[0]) for z in zs if z[-1].split() and z[-1].split()[0].replace("+", "").replace("-", "").replace(".", "").isdigit()]
                if d: werte[f] = round(float(np.mean(d)), 2)
            einig = [v for v in werte.values() if abs(v) >= 0.4 and np.sign(v) == np.sign(b["abweichung"])]
            urteil = "BESTAETIGT durch Nachpruefung" if len(einig) >= 2 else ("widerlegt" if len(werte) > 1 else "keine zweite Kamera sieht die Stelle")
            print(f"  z {b['z_von']:.1f}-{b['z_bis']:.1f} m: " + ", ".join(f"{f}{v:+.2f}" for f, v in werte.items()) + f"  -> {urteil}")
            if urteil == "widerlegt" and anwenden:
                offen.remove(b); erledigt.append(dict(b, status="WIDERLEGT", begruendung="Nachpruefung an den anderen Kameras: " + ", ".join(f"{f}{v:+.2f}" for f, v in werte.items())))
    if anwenden:
        tab["beobachtungen_offen"] = offen; tab.setdefault("beobachtungen_erledigt", []).extend(erledigt)
        json.dump(tab, open(tp, "w"), indent=1, ensure_ascii=False); print(f"\nangewendet: {len(erledigt)} geschlossen, {len(offen)} bleiben offen")

if __name__ == "__main__":
    main()
