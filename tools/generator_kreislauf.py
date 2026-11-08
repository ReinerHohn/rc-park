#!/usr/bin/env python3
"""generator_kreislauf.py - BS55: selbstverbessernder Kreislauf, Teil-Tor per FOTO-DIFF (nicht nur Wolkenabstand).
Schritt 1 'bauen':   aus teile/g_*.stl (globale Lage) und teile/f_*.stl (eingepasst) je GRUPPE eine Kandidaten-STL: Basis A0 = alles global, Kandidat = Gruppe eingepasst.
Schritt 2 'start':   Foto-Diff aller Kandidaten parallel (tools/diff_parallel.py, B = A0, Z = Referenz d03_fix).
Schritt 3 'tor':     Gruppe wird uebernommen, wenn bei BEIDEN Glaettungen Mittel-Diff besser (< -0.002) UND nicht mehr Fotos schlechter als besser UND kein Foto > +0.03 schlechter.
Schritt 4 'final':   A1 = A0 + uebernommene Gruppen -> Diff gegen A0 und Z. (Wiederholung: A1 wird neue Basis, Fit startet von dort - spaeter.)
  venv-seg/bin/python -I tools/generator_kreislauf.py bauen|start|tor|final NAME [--teile-dir ...]"""
import sys, os, json, glob, argparse, subprocess, numpy as np, trimesh
R = "/media/oem/scan/rc-park_null"; REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRUPPEN = {"fassade": ["fassade", "waende", "balken", "cornice", "konsolen", "dachkante_gold"], "arkaden": ["boegen", "piers", "pierbase", "laube", "arkadenglas", "arkadenkreuz"],
           "fenster": ["fenster", "rahmen", "sprossen", "seitenglas", "seitenrahmen"], "erker": ["erker", "balkon", "gitter", "galerie", "baldachin"],
           "figuren": ["statuen", "konsole", "nische"], "dach": ["dach", "giebel", "giebelglas", "giebelrahmen", "first", "krabben", "dachmuster", "dachrauten", "dachziegel"],
           "gauben": ["gauben", "gauben_dach", "gauben_rahmen"], "helme": ["helm", "helm_rot", "helm_hell", "helm_gruen"]}
ap = argparse.ArgumentParser(); ap.add_argument("schritt"); ap.add_argument("name"); ap.add_argument("--teile-dir", default=R + "/generator_alt/teile"); ap.add_argument("--liste", default="000,004,010,016,022,026,032,043,049,054,059,065,082,095,114,120,209,214,218,222,227,247")
a = ap.parse_args(); D = f"{R}/kreislauf/{a.name}"; os.makedirs(D, exist_ok=True)
namen = sorted({os.path.basename(f)[2:-4] for f in glob.glob(a.teile_dir + "/g_*.stl")}); zu = {n: g for g, ns in GRUPPEN.items() for n in ns}; rest = [n for n in namen if n not in zu]
def teil(n, fit): return trimesh.load(os.path.join(a.teile_dir, ("f_" if fit else "g_") + n + ".stl"), force="mesh")
def bau(fit_gruppen, aus): trimesh.util.concatenate([teil(n, zu.get(n) in fit_gruppen) for n in namen]).export(aus)
if a.schritt == "bauen":
    bau(set(), D + "/A0.stl"); print("A0", len(namen), "Teile; ohne Gruppe:", rest)
    for g in GRUPPEN: bau({g}, f"{D}/G_{g}.stl")
elif a.schritt == "start":
    k = [f"--kandidat {g[:3].upper()}_{g}:{D}/G_{g}.stl" for g in GRUPPEN]; k = " ".join(k).split(" ")
    cmd = ["python3", f"{REPO}/tools/diff_parallel.py", "start", "kr_" + a.name, "--basis", f"B:{D}/A0.stl", "--liste", a.liste, "--g", "0.18,0.05"]
    for g in GRUPPEN: cmd += ["--kandidat", f"G{list(GRUPPEN).index(g)}:{D}/G_{g}.stl"]
    cmd += ["--kandidat", f"Z:{R}/wettbewerb_kh/netze5/mvs_d03_fix.stl"]; print(subprocess.run(cmd, capture_output=True, text=True).stdout)
elif a.schritt in ("tor", "final"):
    P = f"{R}/diffpar/kr_{a.name}"; ok = {}; 
    for g in ("0.18", "0.05"):
        r = json.load(open(f"{P}/global_{g}/ergebnis.json")); ph = sorted({k.split("|")[1] for k in r}); B = np.array([r[f"B|{x}"]["lr"] for x in ph])
        for i, gr in enumerate(GRUPPEN):
            v = np.array([r[f"G{i}|{x}"]["lr"] for x in ph]); dl = v - B; ok.setdefault(gr, []).append((dl.mean() < -0.002) and ((dl < -1e-4).sum() > (dl > 1e-4).sum()) and (dl.max() < 0.03))
            print(f"{gr:8s} g{g}: Mittel {dl.mean():+.4f} besser {(dl < -1e-4).sum()} schlechter {(dl > 1e-4).sum()} max {dl.max():+.3f}")
    gut = [g for g, o in ok.items() if all(o)]; print("UEBERNOMMEN:", gut); json.dump(gut, open(D + "/uebernommen.json", "w"))
    if a.schritt == "final":
        bau(set(gut), D + "/A1.stl"); cmd = ["python3", f"{REPO}/tools/diff_parallel.py", "start", "krf_" + a.name, "--basis", f"B:{D}/A0.stl", "--kandidat", f"A1:{D}/A1.stl", "--kandidat", f"Z:{R}/wettbewerb_kh/netze5/mvs_d03_fix.stl", "--liste", a.liste, "--g", "0.18,0.05"]
        print(subprocess.run(cmd, capture_output=True, text=True).stdout)
