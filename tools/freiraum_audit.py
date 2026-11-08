#!/usr/bin/env python3
"""freiraum_audit.py - Freiraumkette fuer das aktuelle Objekt-STL (von tools/bauen_abnehmen.sh vor dem Pruefstand aufgerufen; Pruefstand-Messer freiraum_offen liest das Ergebnis).
objekt.json "freiraum": {"dicht": <COLMAP-Arbeitsordner mit fused.ply(.vis) + kameras_unverzerrt.json>, "ausrichtung": <SFM-AUSRICHTUNG-*.json, mit der sfm_dicht rechnete>,
                         "fassaden": <fassade_ortho fassaden.json>, "elemente": <fassade_parsing elemente.json>, "aus": "audit/freiraum"}  (Pfade relativ zum Objektordner oder absolut)
Ohne Eintrag: nichts tun (Exit 0). Laeuft mit Speichergrenze (trimesh signed_distance ist speicherhungrig, 5.11.).
  /media/oem/scan/venv-seg/bin/python -I tools/freiraum_audit.py modelle/<objekt>/objekt.json [--stl X.stl]
"""
import os, sys, json, subprocess, argparse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); PY = sys.executable


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--stl"); a = ap.parse_args(argv)
    op = os.path.abspath(a.objekt); od = os.path.dirname(op); obj = json.load(open(op)); c = obj.get("freiraum")
    if not c: print("freiraum_audit: kein 'freiraum' in objekt.json - uebersprungen"); return 0
    P = lambda x: x if os.path.isabs(x) else os.path.join(od, x)
    stl = a.stl or os.path.join(ROOT, obj["stl"]); aus = P(c.get("aus", "audit/freiraum")); os.makedirs(aus, exist_ok=True)
    T = os.path.join(ROOT, "tools"); sc = ["systemd-run", "--user", "--scope", "-q", "-p", f"MemoryMax={c.get('speicher', '6G')}"]
    schritte = [sc + [PY, "-W", "ignore", "-I", os.path.join(T, "freiraum_pruefen.py"), op, "--stl", stl, "--dicht", P(c["dicht"]), "--ausrichtung", P(c["ausrichtung"]), "--aus", aus],
                [PY, "-W", "ignore", "-I", os.path.join(T, "freiraum_fassaden.py"), os.path.join(aus, "strahlen.npz"), P(c["fassaden"]), aus, "--stl", stl],
                [PY, "-W", "ignore", "-I", os.path.join(T, "freiraum_oeffnungen.py"), os.path.join(aus, "freiraum_fassaden.json"), P(c["elemente"]), os.path.join(aus, "elemente_freiraum.json"), "--fassaden", P(c["fassaden"])]]
    for cmd in schritte:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True); print("\n".join((r.stdout or "").strip().splitlines()[-3:]))
        if r.returncode != 0: print(f"freiraum_audit: {os.path.basename(cmd[cmd.index('-I') + 1])} rc {r.returncode}: {(r.stderr or '')[-400:]}"); return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
