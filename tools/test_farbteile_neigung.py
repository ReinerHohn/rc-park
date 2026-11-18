#!/usr/bin/env python3
"""test_farbteile_neigung.py - Schnelltest fuer tools/druck_farbteile.py: Plattentiefe folgt der OERTLICHEN Wand (18.11.2026).
Synthetisch: Quader 12 x 8 x 10 m, um 2 Grad gegen die Maskenebene gedreht (Wandflaeche +-21 cm vor/hinter der Ebene = +-2,4 mm im Druck bei 1:87).
Erwartung: eine Ebene je Wand -> Tasche bricht auf einem grossen Teil durch die 2,4-mm-Wand; neue Bauart -> Ebene geneigt erkannt, EINE Platte (keine Streifen),
Restwand ueberall >= 0,6 mm (bis auf Randpixel), rc 0, Platte liegt eben (Drucklage-Dicke klein)."""
import sys, os, json, shutil, subprocess, re, numpy as np, trimesh
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); NAME = "_test_farbteile_neigung"
od = os.path.join(ROOT, "modelle", NAME); ad = os.path.join(ROOT, "modelle", "stl", NAME + "_farbteile"); gross = os.path.join("/media/oem/scan/rc-park_stl", NAME + "_farbteile")


def lauf(*opt):
    r = subprocess.run([sys.executable, "-W", "ignore", "-I", os.path.join(ROOT, "tools", "druck_farbteile.py"), NAME, "--stl", os.path.join(od, "m.stl"), "--masken", "relief/sued_putz.npz",
                        "--wand_mm", "2.4", "--spiel_mm", "0.3", "--ohne_luft", "--min_m2", "1.0", *opt], capture_output=True, text=True, timeout=300)
    return r.returncode, r.stdout + r.stderr


def main():
    for d in (od, ad, gross): shutil.rmtree(d, ignore_errors=True) if not os.path.islink(d) else os.remove(d)
    try:
        os.makedirs(os.path.join(od, "relief")); json.dump(dict(name=NAME, stl="m.stl", stl_massstab=87), open(os.path.join(od, "objekt.json"), "w"))
        b = trimesh.creation.box((12.0, 8.0, 10.0)); b.apply_translation((0, 0, 5.0)); b.apply_transform(trimesh.transformations.rotation_matrix(np.radians(2.0), (0, 0, 1))); b.apply_scale(1000.0 / 87); b.export(os.path.join(od, "m.stl"))
        px = 0.05; H, W = int(9.0 / px), int(10.0 / px); putz = np.zeros((H, W), bool)      # alles Stein, Maskenebene = Suedseite y = -4 (ungedreht), Normale -y
        np.savez(os.path.join(od, "relief", "sued_putz.npz"), putz=putz, px=px, u0=-5.0, z0=0.5, a=np.array([0.0, -4.0]), t=np.array([1.0, 0.0]), n=np.array([0.0, -1.0]))
        rc1, o1 = lauf("--eine_ebene"); rc2, o2 = lauf()
        f = []
        m = re.search(r"mit EINER Ebene waeren es (-?[\d.]+) mm / ([\d.]+) %", o2); s_ = re.search(r"mit Stufen min (-?[\d.]+) mm, < 0,6 mm auf ([\d.]+) %", o2)
        if not (m and s_): f.append("Restwand-Zeile fehlt: " + o2[-600:])
        else:
            if float(m.group(2)) < 30: f.append(f"eine Ebene sollte durchbrechen (>= 30 %), war {m.group(2)} %")
            if float(s_.group(2)) > 3: f.append(f"neue Bauart: Restwand < 0,6 mm auf {s_.group(2)} % (soll <= 3 %)")
        if "geneigt" not in o2: f.append("Neigung nicht erkannt")
        if rc2 != 0: f.append(f"rc {rc2}: " + o2[-500:])
        pl = re.findall(r"platte_sued_\d+: .*Drucklage (\d+) x (\d+) x ([\d.]+) mm", o2)
        if len(pl) != 1: f.append(f"{len(pl)} Platten statt 1: {pl}")
        elif float(pl[0][2]) > 4.0: f.append(f"Platte liegt schief (Dicke in Drucklage {pl[0][2]} mm)")
        print("FARBTEILE_NEIGUNG: " + ("ok" if not f else "FEHLER " + " | ".join(f)))
        return 1 if f else 0
    finally:
        for d in (od, ad, gross): shutil.rmtree(d, ignore_errors=True) if not os.path.islink(d) else os.remove(d)


if __name__ == "__main__":
    sys.exit(main())
