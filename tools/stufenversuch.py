#!/usr/bin/env python3
"""stufenversuch.py - Stufenmodell grob -> fein: gleiches Netz (Nullstart ab 'dicht'), nur die dichte Stufe variiert (Register BK).

  python3 -I tools/stufenversuch.py modelle/martinstor/objekt.json --ziel martinstor_null --varianten "basis:" "n11_1600:--fotos A" "n11_1200:--max-size 1200 --fotos A"
'--fotos @N' im Text wird durch die N besten Fotos der Abdeckungs-Auswahl (foto_auswahl.py --waehle N) ersetzt, z. B. "n11_1200:--max-size 1200 --fotos @11".
Je Variante: nullstart.py --ab dicht --dicht-extra ...; gesichert werden Pruefbericht, Masse, Bericht, STL; Zusammenfassung stufen_<datum>/ZUSAMMENFASSUNG.md
Vergleich ist sauber, weil Netz und Ausrichtung gleich bleiben (kein Netz-Rauschen); PatchMatch selbst ist zufallsbehaftet -> 'basis' zweimal laufen lassen zeigt das Rauschen.
"""
import sys, os, json, shutil, subprocess, argparse, time, re

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--ziel", default="martinstor_null"); ap.add_argument("--varianten", nargs="+", required=True); ap.add_argument("--streng", action="store_true", default=True)
    a = ap.parse_args(); repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); zd = os.path.realpath(os.path.join(repo, "modelle", a.ziel))
    base = os.path.join(os.path.dirname(zd), f"stufen_{time.strftime('%Y%m%d_%H%M')}"); os.makedirs(base, exist_ok=True); rows = []
    for v in a.varianten:
        name, extra = v.split(":", 1)
        m = re.search(r"@(s?)(\d+)", extra)
        if m:
            r = subprocess.run(["/media/oem/scan/venv-colmap/bin/python", "-I", "tools/foto_auswahl.py", f"modelle/{a.ziel}/objekt.json", "--waehle", m.group(2)] + (["--schicht"] if m.group(1) else []), cwd=repo, capture_output=True, text=True).stdout
            lst = re.search(r"--fotos (\S+)", r).group(1); extra = extra.replace(m.group(0), lst)
        cmd = [sys.executable, "-I", "tools/nullstart.py", a.objekt, "--ziel", a.ziel, "--ab", "dicht", "--mapper", "global", "--dicht-extra", extra] + (["--streng"] if a.streng else [])
        for fn in ("pruefbericht.json", "nullstart_bericht.json"):                      # nie Ergebnisse einer frueheren Variante wiederverwenden (Fehler 2026-11-02: Fehlschlaege zeigten den Basiswert)
            if os.path.exists(os.path.join(zd, fn)): os.remove(os.path.join(zd, fn))
        t0 = time.time(); print(f"== {name}: {extra}", flush=True)
        with open(os.path.join(base, f"{name}.log"), "w") as f: rc = subprocess.run(cmd, cwd=repo, stdout=f, stderr=subprocess.STDOUT).returncode
        wall = time.time() - t0; d = os.path.join(base, name); os.makedirs(d, exist_ok=True)
        for fn in ("pruefbericht.json", "masse.json", "nullstart_bericht.json"):
            if os.path.exists(os.path.join(zd, fn)): shutil.copy2(os.path.join(zd, fn), d)
        for s in ("martinstor_null_v4_1-87.stl",):
            p = os.path.join(repo, "modelle", "stl", s)
            if os.path.exists(p): shutil.copy2(p, d)
        if rc != 0: rows.append((name, extra, rc, round(wall), None, "FEHLGESCHLAGEN")); print(f"   FEHLGESCHLAGEN rc {rc} nach {wall:.0f} s", flush=True); continue
        try:
            pb = json.load(open(os.path.join(d, "pruefbericht.json"))); ok = sum(x["ok"] for x in pb["pruefungen"]); n = len(pb["pruefungen"])
            nb = json.load(open(os.path.join(d, "nullstart_bericht.json"))); dicht = [s["sekunden"] for s in nb["schritte"] if s.get("schritt") == "dicht_nord"][-1]   # LETZTER Eintrag (der Bericht kann mehrere enthalten)
        except Exception as e: ok = n = dicht = None
        rows.append((name, extra, rc, round(wall), dicht, f"{ok}/{n}")); print(f"   rc {rc}, Wanduhr {wall:.0f} s, PatchMatch+Fusion {dicht} s, bestanden {ok}/{n}", flush=True)
    M = ["# Stufenversuch (automatisch)", "", "| Variante | Argumente | rc | Wanduhr s | dicht_nord s | bestanden |", "|---|---|---|---|---|---|"] + [f"| {r[0]} | `{r[1]}` | {r[2]} | {r[3]} | {r[4]} | {r[5]} |" for r in rows]
    open(os.path.join(base, "ZUSAMMENFASSUNG.md"), "w").write("\n".join(M) + "\n"); print("\n".join(M)); print("fertig:", base)

if __name__ == "__main__":
    main()
