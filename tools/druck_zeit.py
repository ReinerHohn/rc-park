#!/usr/bin/env python3
"""druck_zeit.py <ordner mit STL-Teilen> [--schicht 0.16] [--fuellung 15] [--stuetzen] [--parallel 4] - Druckzeit und Material je Teil mit dem Slicer MESSEN.

Anlass 17.11.2026 (Nutzer: "es geht auch um gute Druckzeit"): Teilungen wurden nur nach Ueberhang bewertet; ob ein Bausatz 20 oder 60 Stunden druckt, stand nirgends.
Je teil_*.stl / platte_*.stl / koerper.stl im Ordner (Drucklage, mm): prusa-slicer --export-gcode, aus dem G-Code 'estimated printing time' und 'filament used [cm3]'.
Ausgabe: Zeilen je Teil, Summe; <ordner>/druckzeit.json. G-Code wird nicht aufgehoben.
Grenzen: PrusaSlicer-Standardprofil (0,4-mm-Duese, Standardgeschwindigkeiten) - ein Bambu P1S druckt schneller; die Zahlen taugen zum VERGLEICH zweier Teilungen,
nicht als Zusage. Teile, die der Slicer ablehnt (nicht druckbar), werden als FEHLER gemeldet (rc 3).
"""
import sys, os, re, glob, json, subprocess, tempfile
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, "tools"))


def sek(t):
    return sum(int(v) * dict(d=86400, h=3600, m=60, s=1)[e] for v, e in re.findall(r"(\d+)([dhms])", t))


def main():
    a = sys.argv[1:]; opt = lambda n, d: a[a.index(n) + 1] if n in a else d
    if not a or a[0].startswith("--"): sys.exit(__doc__)
    od = a[0]; fl = sorted(f for f in glob.glob(os.path.join(od, "*.stl")) if os.path.basename(f) != "stifte.stl")
    if not fl: print("keine STL in", od); return 2
    tmp = tempfile.mkdtemp(dir="/media/oem/scan/tmp" if os.path.isdir("/media/oem/scan/tmp") else None)
    def eins(f):
        g = os.path.join(tmp, os.path.basename(f)[:-4] + ".gcode")
        cmd = ["prusa-slicer", "--export-gcode", "--layer-height", opt("--schicht", "0.16"), "--fill-density", opt("--fuellung", "15") + "%", "--output", g, f] + (["--support-material"] if "--stuetzen" in a else [])
        try: r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        except subprocess.TimeoutExpired: return dict(teil=os.path.basename(f), fehler="Slicer-Zeitlimit 60 min")
        if r.returncode or not os.path.exists(g): return dict(teil=os.path.basename(f), fehler=(r.stdout + r.stderr).strip().splitlines()[-1][:160] if (r.stdout + r.stderr).strip() else "kein G-Code")
        t = v = None
        for z in open(g, errors="replace"):
            if "estimated printing time (normal mode)" in z: t = z.split("=")[1].strip()
            elif "filament used [cm3]" in z: v = float(z.split("=")[1])
        os.remove(g); return dict(teil=os.path.basename(f), zeit=t, sekunden=sek(t or ""), filament_cm3=v)
    with ThreadPoolExecutor(int(opt("--parallel", "4"))) as ex: erg = list(ex.map(eins, fl))
    rot = [e for e in erg if e.get("fehler")]; gut = [e for e in erg if not e.get("fehler")]
    for e in erg: print(f"  {e['teil']:28s} " + (f"FEHLER {e['fehler']}" if e.get("fehler") else f"{e['zeit']:>12s}  {e['filament_cm3']:7.1f} cm3"))
    S = sum(e["sekunden"] for e in gut); V = sum(e["filament_cm3"] or 0 for e in gut)
    print(f"SUMME {len(gut)} Teile: {S // 3600} h {S % 3600 // 60} min, {V:.0f} cm3 Filament (~{V * 1.24:.0f} g PLA)" + (f"; {len(rot)} Teil(e) NICHT geslict" if rot else ""))
    import json_sicher; json_sicher.schreiben(os.path.join(od, "druckzeit.json"), dict(schicht_mm=float(opt("--schicht", "0.16")), fuellung_prozent=float(opt("--fuellung", "15")), stuetzen="--stuetzen" in a, slicer="PrusaSlicer Standardprofil", teile=erg, summe_sekunden=S, summe_cm3=round(V, 1)))
    return 3 if rot else 0


if __name__ == "__main__":
    sys.exit(main())
