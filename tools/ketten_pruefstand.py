#!/usr/bin/env python3
"""ketten_pruefstand.py ZIEL:QUELLE [ZIEL:QUELLE ...] [--ab fototor] [--bis html] [--nur-lesen] [--aus DATEI.md] - die Gesamtkette an MEHREREN Gebaeuden laufen lassen und vergleichen.

Anlass 17.11.2026 (Nutzer: "beweise, dass die Kette stabil ist und aus jedem Gebaeude Details holt"): bisher lief die Kette je Objekt von Hand, das Ergebnis stand in
verstreuten Logs - niemand sah auf einen Blick, an welchem Gebaeude welche Stufe scheitert und wie viel Detail herauskommt.
Ablauf: je Paar `tools/gesamtkette.py QUELLE --ziel ZIEL --ab .. --bis ..` NACHEINANDER (nie zwei Laeufe gleichzeitig: Grafikspeicher), danach je Objekt die Kennzahlen lesen:
  Kette:    Stufen, Stufen nicht in Ordnung (Namen), Dauer
  Fotos:    Messkameras, Fassaden, mittlere Abdeckung der Fassadenbilder (flaechengewichtet), Flaeche ohne Bilddaten
  Detail:   Waende mit Relief, erkannte Fenster, Dreiecke im STL
  Modell:   Pruefstand bestanden, wasserdicht, ein Koerper, Umriss-Tor (Befunde)
  Druck:    Anteil Ueberhang > 60 Grad, Anteil duenner als 0,4 mm (tools/druck_vorcheck.py)
Ausgabe: Zeilen je Objekt + JSON /media/oem/scan/rc-park_daten/ketten_pruefstand.json (+ Markdown mit --aus). rc 3, wenn ein Lauf Stufen nicht in Ordnung hat.
--nur-lesen: keine Kette starten, nur Kennzahlen des letzten Laufs. Grenze: Kennzahlen sagen nicht, ob das Modell STIMMT - dafuer audit/seiten.jpg und neben_<foto>.jpg ansehen.
"""
import sys, os, json, glob, subprocess, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); PY = "/media/oem/scan/venv-seg/bin/python"


def kennzahlen(ziel):
    D = f"/media/oem/scan/rc-park_daten/{ziel}"; Z = os.path.join(ROOT, "modelle", ziel); k = dict(ziel=ziel)
    def js(p):
        try: return json.load(open(p))
        except Exception: return None
    B = js(os.path.join(D, "gesamtkette_bericht.json")) or {}; S = B.get("schritte", []); st = max([i for i, e in enumerate(S) if e.get("stufe") == "LAUF_START"] or [0]); L = S[st:]
    k["stufen"] = len(L); k["rot"] = [e["stufe"] for e in L if e.get("ok") is False]; k["dauer_min"] = round(sum(e.get("sekunden", 0) for e in L) / 60, 1)
    k["kameras"] = len(glob.glob(os.path.join(Z, "messprotokoll", "K-*.json")))
    F = js(os.path.join(D, "fassade", "fassaden.json")); fl = (F.get("fassaden", F) if isinstance(F, dict) else F) or []; fl = fl if isinstance(fl, list) else list(fl.values())
    fl = [f for f in fl if isinstance(f, dict) and "flaeche_m2" in f]; A = sum(f["flaeche_m2"] for f in fl)
    k["fassaden"] = len(fl); k["abdeckung"] = round(sum(f["flaeche_m2"] * f.get("abdeckung_anteil", 0) for f in fl) / A, 2) if A else None; k["ohne_bild_m2"] = round(sum(f["flaeche_m2"] * (1 - f.get("abdeckung_anteil", 0)) for f in fl)) if A else None
    FK = js(os.path.join(Z, "audit", "fassaden_kette.json")) or {}; k["relief_waende"] = len(glob.glob(os.path.join(Z, "relief", "w*_putz.npz")) or FK.get("waende", []))
    FE = js(os.path.join(Z, "audit", "fenster_auto.json")) or {}; k["fenster"] = sum(len(v.get("fenster", v) if isinstance(v, dict) else v) for v in FE.values()) if isinstance(FE, dict) else None
    PB = js(os.path.join(Z, "pruefbericht.json")) or {}; pr = PB.get("pruefungen", []); k["pruefstand"] = PB.get("bestanden"); k["pruefungen"] = len(pr); k["hoehe_m"] = round(PB.get("werte", {}).get("hoehe", 0), 1) or None
    U = js(os.path.join(Z, "audit", "umriss_tor.json")); k["umriss_befunde"] = len(U["befunde"]) if U else None
    V = js(os.path.join(Z, "audit", "druck_vorcheck.json")) or {}; k["dreiecke"] = V.get("netz", {}).get("dreiecke"); k["wasserdicht"] = V.get("netz", {}).get("wasserdicht"); k["teilnetze"] = V.get("netz", {}).get("teilnetze")
    k["ueberhang"] = V.get("ueberhang", {}).get("anteil"); k["duenn"] = V.get("duenn", {}).get("anteil_unter")
    return k


def main():
    a = sys.argv[1:]; opt = lambda n, d: a[a.index(n) + 1] if n in a else d; ab, bis, aus = opt("--ab", "fototor"), opt("--bis", "html"), opt("--aus", "")
    paare = [x.split(":") for x in a if ":" in x and not x.startswith("--")]
    if not paare: sys.exit(__doc__)
    erg = []; schlecht = False
    for ziel, quelle in paare:
        if "--nur-lesen" not in a:
            t0 = time.time(); print(f"=== {ziel} (Quelle {quelle}) ab {ab} bis {bis}  [{time.strftime('%H:%M')}]", flush=True)
            r = subprocess.run(["python3", "tools/gesamtkette.py", quelle, "--ziel", ziel, "--ab", ab, "--bis", bis], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
            open(f"/media/oem/scan/rc-park_daten/{ziel}/ketten_pruefstand.log", "w").write(r.stdout); print("\n".join(z for z in r.stdout.splitlines() if z.startswith(("ERGEBNIS DES LAUFS", "    FEHLER", "PLATZ"))), flush=True)
            subprocess.run([PY, "-W", "ignore", "-I", "tools/druck_vorcheck.py", ziel], cwd=ROOT, capture_output=True)
            print(f"    Kette rc {r.returncode}, {(time.time() - t0) / 60:.0f} min", flush=True)
        k = kennzahlen(ziel); erg.append(k); schlecht |= bool(k["rot"])
        print(f"{ziel}: {k['stufen']} Stufen, {len(k['rot'])} nicht in Ordnung {k['rot'][:6]}, {k['dauer_min']} min | {k['kameras']} Kameras, {k['fassaden']} Fassaden, Abdeckung {k['abdeckung']}, {k['ohne_bild_m2']} m2 ohne Bild | "
              f"Relief an {k['relief_waende']} Waenden, {k['fenster']} Fenster, {k['dreiecke']} Dreiecke | Pruefstand {k['pruefstand']} ({k['pruefungen']}), wasserdicht {k['wasserdicht']}, Teilnetze {k['teilnetze']}, Umriss-Befunde {k['umriss_befunde']} | Ueberhang {k['ueberhang']}, duenn {k['duenn']}", flush=True)
    sys.path.insert(0, os.path.join(ROOT, "tools")); import json_sicher
    json_sicher.schreiben("/media/oem/scan/rc-park_daten/ketten_pruefstand.json", dict(zeit=time.strftime("%Y-%m-%d %H:%M"), ab=ab, bis=bis, objekte=erg))
    if aus:
        with open(aus, "w") as f:
            f.write(f"# Kettenpruefstand {time.strftime('%Y-%m-%d %H:%M')} (ab {ab} bis {bis})\n\n")
            for k in erg: f.write(f"## {k['ziel']}\n" + "".join(f"- {n}: {v}\n" for n, v in k.items() if n != "ziel") + "\n")
    return 3 if schlecht else 0


if __name__ == "__main__":
    sys.exit(main())
