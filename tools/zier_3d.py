#!/usr/bin/env python3
"""zier_3d.py - Bild-zu-3D fuer Zierteile (Figuren ...) aus zier_ausschnitt.py (2026-11-05).

Je Ausschnitt (ausschnitte.json) ein Netz mit TripoSR (MIT, stabilityai/TripoSR, lokal /media/oem/scan/TripoSR, venv-tsr; RTX 4060 ca. 5 s je Figur).
Form = TripoSR (Rueckseite geraten - Figuren stehen an der Wand), MASSE = Element-Box (Buendelkameras), nicht das Netz. Schreibt "netz" in ausschnitte.json.
Lizenz: TripoSR-Code und -Gewichte MIT; rembg (MIT) mit u2net (Apache-2.0).

  /media/oem/scan/venv-seg/bin/python -I tools/zier_3d.py <ausschnitte.json> [--mc 256]
"""
import os, sys, json, argparse, subprocess

TSR = "/media/oem/scan/TripoSR"; PY = "/media/oem/scan/venv-tsr/bin/python"


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("ausschnitte"); ap.add_argument("--mc", type=int, default=256); a = ap.parse_args(argv)
    A = json.load(open(a.ausschnitte)); aus = os.path.join(os.path.dirname(os.path.abspath(a.ausschnitte)), "tsr"); L = A["ausschnitte"]
    if not L: print("keine Ausschnitte"); return
    env = dict(os.environ, HF_HOME=os.environ.get("HF_HOME", "/media/oem/scan/hf_cache"), U2NET_HOME="/media/oem/scan/hf_cache/u2net", TMPDIR="/media/oem/scan/tmp")
    rr = subprocess.run([PY, "run.py"] + [e["datei"] for e in L] + ["--output-dir", aus, "--model-save-format", "obj", "--mc-resolution", str(a.mc)], cwd=TSR, env=env, capture_output=True, text=True)
    if rr.returncode != 0: raise SystemExit("TripoSR fehlgeschlagen: " + (rr.stderr or rr.stdout)[-800:])
    for i, e in enumerate(L):
        p = os.path.join(aus, str(i), "mesh.obj")
        if os.path.exists(p): e["netz"] = p; e["netz_quelle"] = "TripoSR (MIT), mc %d, Achsen: z hoch, Front +x, Bild-rechts +y" % a.mc
        print(f"  {os.path.basename(e['datei'])} -> {p if os.path.exists(p) else 'FEHLT'}")
    json.dump(A, open(a.ausschnitte, "w"), indent=1)


if __name__ == "__main__":
    main()
