#!/usr/bin/env python3
"""foto_verhaeltnis.py - massstabsfreie HOEHENVERHAELTNISSE aus einem WEIT ENTFERNTEN Foto.

Wozu: ein Foto aus 1 km Entfernung ist nahezu orthografisch. Dann ist das Verhaeltnis zweier senkrechter Strecken
im Bild gleich dem Verhaeltnis in der Wirklichkeit - ohne Kamera, ohne Brennweite, ohne Massstab, ohne Modell.
Das ist genau die Luecke zwischen "Foto sieht nur Verhaeltnisse" (foto_verhaeltnis, +-5-10 %) und
"Kamera gegen amtliche Anker" (foto_kalibriert, braucht Anker IN der Hoehenzone - siehe Ankerzone in
METHODE_MASSTABELLE Abschnitt 8). Fuer den Oberbau eines Turms, wo unten keine Anker sichtbar sind, ist es oft
die einzige saubere Messung.

Die Unsicherheit kommt aus dem Foto selbst, nicht aus einer Annahme: mehrere Punkte, die in Wirklichkeit GLEICH HOCH
sind (die vier Tuermchenspitzen), muessen in einem orthografischen Bild in derselben Zeile liegen. Ihre Streuung IST
die Abweichung von der Orthografie plus der Pickfehler. Streut sie mehr als ein Zehntel der Messstrecke, ist das Foto
fuer dieses Verfahren zu nah dran und das Werkzeug bricht ab.

Protokoll je Foto: modelle/<objekt>/messprotokoll/V-<foto>.json
  {"unten": {"anker": "tuermchen_NW", "picks": {"NW": [u, v], "NE": [u, v], "SW": [u, v]}},   # gleich hohe Punkte
   "oben":  {"anker": "spitze_dokument", "pick": [u, v]},                                      # zweiter Bezugspunkt
   "punkte": {"knauf": [u, v], "dachansatz": [u, v]},                                          # was gemessen wird
   "notiz": "..."}
Die Namen unter "anker" zeigen auf modelle/<objekt>/anker3d.json; nur daraus kommen die Meter (und nur, wenn beide
Bezugshoehen aus einer Quelle stammen, die absolute Hoehen sehen darf).

  foto_verhaeltnis.py modelle/<objekt>/objekt.json 060,061
Ausgabe: je Merkmal das Verhaeltnis je Foto, die Pruefung ueber alle Fotos (messung_pruefen.pruefe) und - wenn gueltig -
der Vorschlag fuer die Tabellenzeile. Je Foto wird ein Messprotokoll M-<foto>-V<n>.json geschrieben.
"""
import sys, os, json, numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from messung_pruefen import pruefe, plausibel

MAX_STREUUNG = 0.10          # Streuung der Gleichhoch-Punkte, bezogen auf die Messstrecke: darueber ist das Foto zu nah
PICK_PX = 3.0                # Pickgenauigkeit von Hand; die Unsicherheit darf nie kleiner sein, auch wenn die
                             # Gleichhoch-Punkte zufaellig genau in einer Zeile liegen (sonst sperrt pruefe() alles)


def eine_datei(od, nr):
    p = os.path.join(od, "messprotokoll", f"V-{nr}.json")
    if not os.path.exists(p): raise SystemExit(f"fehlt: {p} (Vorlage steht im Kopf von tools/foto_verhaeltnis.py)")
    return p, json.load(open(p))


def messen(V, nr):
    """Verhaeltnisse eines Fotos: r = (v_unten - v_punkt) / (v_unten - v_oben). 0 = auf Hoehe der unteren Bezugsebene,
    1 = auf Hoehe des oberen Bezugspunkts. Negativ = darunter."""
    vs = np.array([p[1] for p in V["unten"]["picks"].values()], float)
    v_unten = float(vs.mean()); streu = max(float(vs.max() - vs.min()), 2 * PICK_PX)
    v_oben = float(V["oben"]["pick"][1]); strecke = v_unten - v_oben
    if strecke <= 0: raise SystemExit(f"V-{nr}: der obere Bezugspunkt liegt im Bild nicht ueber den unteren")
    anteil = streu / strecke
    if anteil > MAX_STREUUNG:
        raise SystemExit(f"V-{nr}: die {len(vs)} gleich hohen Punkte streuen {streu:.0f} px = {anteil * 100:.1f} % der "
                         f"Messstrecke ({strecke:.0f} px). Dieses Foto ist zu nah/zu schraeg fuer ein massstabsfreies "
                         f"Verhaeltnis - entweder eine Kamera loesen (foto_kalibrieren.py) oder ein ferneres Foto nehmen.")
    r = {n: (v_unten - float(p[1])) / strecke for n, p in V["punkte"].items()}
    return r, anteil, strecke, streu, v_unten, v_oben


def main():
    objp = sys.argv[1]; nrs = sys.argv[2].split(",")
    obj = json.load(open(objp)); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(objp))))
    od = os.path.join(root, os.path.dirname(obj["masstabelle"])); A = json.load(open(os.path.join(od, "anker3d.json")))["anker"]
    alle, sig, info = {}, 0.0, {}
    for nr in nrs:
        p, V = eine_datei(od, nr)
        r, anteil, strecke, streu, vu, vo = messen(V, nr)
        sig = max(sig, anteil)                                   # Unsicherheit des Verhaeltnisses = relative Streuung
        info[nr] = (V, strecke, streu, anteil, vu, vo)
        print(f"Foto {nr}: Messstrecke {V['unten']['anker']} -> {V['oben']['anker']} = {strecke:.0f} px; "
              f"{len(V['unten']['picks'])} gleich hohe Punkte streuen {streu:.0f} px = {anteil * 100:.1f} % "
              f"(Grenze {MAX_STREUUNG * 100:.0f} % - so weit ist das Bild von der Orthografie entfernt)")
        for n, x in r.items(): print(f"   {n:<16} Verhaeltnis {x:+.3f}")
        alle.setdefault("__fotos__", []).append(nr)
        for n, x in r.items(): alle.setdefault(n, {})[nr] = x

    z_u = A[list(info.values())[0][0]["unten"]["anker"]]["xyz"][2]
    z_o = A[list(info.values())[0][0]["oben"]["anker"]]["xyz"][2]
    print(f"\nBezugshoehen aus anker3d.json: unten {z_u} m, oben {z_o} m -> Meter = {z_u} + Verhaeltnis * {z_o - z_u:.1f}")
    print("ACHTUNG: die Meter sind nur so gut wie diese beiden Ankerhoehen; das VERHAELTNIS selbst ist von ihnen unabhaengig.\n")
    for n, werte in alle.items():
        if n == "__fotos__": continue
        ok, text = pruefe(werte, sig, f"Verhaeltnis '{n}'")
        print(("  " if ok else "  ") + text)
        if ok and len(werte) > 1:
            m = float(np.mean(list(werte.values()))); z = z_u + m * (z_o - z_u)
            spanne = sig * abs(z_o - z_u)
            print(f"     -> Soll-Vorschlag Verhaeltnis [{m - 2 * sig:.3f}, {m + 2 * sig:.3f}]  "
                  f"entspricht z = {z:.1f} m +- {2 * spanne:.1f} (quelltyp foto_vollbild, merkmal verhaeltnis)")

    for nr, (V, strecke, streu, anteil, vu, vo) in info.items():
        mp = os.path.join(od, "messprotokoll", f"M-{nr}-V1.json")
        json.dump({"foto": nr, "verfahren": "massstabsfreies Hoehenverhaeltnis (fernes Foto, nahezu orthografisch)",
                   "unten": V["unten"], "oben": V["oben"], "v_unten_mittel": round(vu, 1), "v_oben": vo,
                   "messstrecke_px": round(strecke, 1), "streuung_gleichhoch_px": round(streu, 1),
                   "orthografie_abweichung": round(anteil, 4),
                   "verhaeltnisse": {n: round(alle[n][nr], 4) for n in alle if n != "__fotos__" and nr in alle[n]},
                   "notiz": V.get("notiz", "")}, open(mp, "w"), indent=1, ensure_ascii=False)
        print(f"  Protokoll: {mp}")


if __name__ == "__main__":
    main()
