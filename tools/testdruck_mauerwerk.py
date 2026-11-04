#!/usr/bin/env python3
"""testdruck_mauerwerk.py - GENERISCH: Mauerwerks-Musterplatte eines Objekts im Massstab (Standard H0 1:87) fuer den Bambu P1S.

Liest die Mauerwerksmasse aus modelle/<objekt>/masse.json (Schichthoehen/Steinlaenge = Daten mit Quelle, keine Zahlen hier) und baut sie nach
DENSELBEN Regeln wie der Generator (martinstor_v4_gen.quoins3, bauteile.bruchstein):
  Fuge = min(0,09 m, 0,2 x Schicht), Relief = 0,2-0,4 x Schicht (ANNAHME wie im Generator), Blocklaengen +-15 %;
  Bruchstein: Hoehe 0,48-0,78 m, Breite 0,7-1,7 m, Relief 0,05-0,22 m, Fuge 0,06 m (bauteile.bruchstein).
Flach gedruckt, Wandansicht nach oben. Felder (Kerben 1..n am Rand) aus --felder, je Feld:
  quader:<SCHICHT>[:<LANG>]            durchgehendes Quadermauerwerk (halber Versatz)
  eck:<SCHICHT>[:<LANG>[:<KURZ>]]      Eckquaderverband (lang/kurz im Wechsel) an der linken Feldkante, daneben glatter Putz
  Werte: Schluessel aus masse.json ODER @M-<foto>-<nr> (Foto-Messprotokoll, Feld 'abstand'); fehlt LANG/KURZ -> QUADER_LAENGE / KURZ_FAKTOR
  bruch                       Bruchsteinsockel
  ...*2                       gleiches Feld, Relief und Fuge x2 (Lesbarkeitsvergleich)
  ~/.venvs/rcpark/bin/python tools/testdruck_mauerwerk.py modelle/martinstor/objekt.json modelle/export/h0/mauerwerk_test.stl
"""
import os, sys, json, struct, argparse, numpy as np
from manifold3d import Manifold as M, OpType
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bauteile import lade_masse


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("aus"); ap.add_argument("--massstab", type=float, default=87.0)
    ap.add_argument("--felder", nargs="+", default=["bruch", "eck:QUADER_SCHAFT_UNTEN", "quader:QUADER_GLOCKENSTOCK", "quader:QUADER_SCHAFT_UNTEN*2"])
    ap.add_argument("--laenge_key", default="QUADER_LAENGE"); ap.add_argument("--feld", nargs=2, type=float, default=[30.0, 24.0])
    ap.add_argument("--basis", type=float, default=1.2); ap.add_argument("--min_relief", type=float, default=0.16, help="mm: unter 2 Schichten a 0,08 nicht druckbar")
    ap.add_argument("--seed", type=int, default=7); a = ap.parse_args()
    od = os.path.dirname(os.path.abspath(a.objekt)); m = lade_masse(os.path.join(od, "masse.json"))
    k = 1000.0 / a.massstab; FX, FY = a.feld; B = a.basis; RAND = 2.0; rng = np.random.default_rng(a.seed)
    rel = lambda r_m: max(a.min_relief, r_m * k)                                                   # Relief m -> mm, mindestens druckbar
    adds, cuts, info = [], [], []
    def blk(x0, x1, y0, y1, h):
        if x1 - x0 > 0.2 and y1 - y0 > 0.2: adds.append(M.cube((x1 - x0, y1 - y0, h)).translate((x0, y0, B - 0.01)))
    def wert(t):
        if t.startswith("@"): return float(json.load(open(os.path.join(od, "messprotokoll", t[1:] + ".json")))["abstand"])
        return float(m[t])
    def quader(x0, y0, kurs_m, f, lang=None):
        c = kurs_m * k; L = (lang or m[a.laenge_key]) * k; j = min(0.09, 0.2 * kurs_m) * k * f
        for i, y in enumerate(np.arange(y0, y0 + FY - 0.3, c)):
            x = x0 - (L / 2 if i % 2 else 0.0)
            while x < x0 + FX:
                l = L * rng.uniform(0.85, 1.15)
                blk(max(x, x0), min(x + l - j, x0 + FX), y, min(y + c - j, y0 + FY), rel(rng.uniform(0.2, 0.4) * kurs_m) * f)
                x += l
        return f"Quader Schicht {kurs_m} m = {c:.2f} mm, Laenge {L/k:.2f} m = {L:.2f} mm, Fuge {j:.2f} mm"
    def eck(x0, y0, kurs_m, f, lang=None, kurz=None):
        c = kurs_m * k; L = (lang or m[a.laenge_key]) * k; Kz = (kurz * k) if kurz else m.get("QUADER_KURZ_FAKTOR", 1.0) * L; j = min(0.09, 0.2 * kurs_m) * k * f
        for i, y in enumerate(np.arange(y0, y0 + FY - 0.3, c)):
            l = (L if i % 2 == 0 else Kz) * rng.uniform(0.85, 1.15)
            blk(x0, x0 + l, y, min(y + c - j, y0 + FY), rel(rng.uniform(0.2, 0.4) * kurs_m) * f)
        adds.append(M.cube((FX, FY, 0.08)).translate((x0, y0, B - 0.01)))                               # Putzflaeche 1 Schicht
        return f"Eckverband Schicht {kurs_m} m = {c:.2f} mm, lang/kurz {L:.2f}/{Kz:.2f} mm, Fuge {j:.2f} mm"
    def bruch(x0, y0, f):
        y = y0
        while y < y0 + FY - 0.3:
            h = rng.uniform(0.48, 0.78) * k; y1 = min(y + h, y0 + FY); x = x0
            while x < x0 + FX - 0.3:
                w = rng.uniform(0.7, 1.7) * k; x1 = min(x + w, x0 + FX)
                g = 0.03 * k * f; blk(x + g, x1 - g, y + g, y1 - g, rel(rng.uniform(0.05, 0.22)) * f); x = x1
            y = y1
        return f"Bruchstein H 0,48-0,78 m = {0.48*k:.1f}-{0.78*k:.1f} mm, B 0,7-1,7 m, Relief {rel(0.05):.2f}-{rel(0.22):.2f} mm, Fuge {0.06*k*f:.2f} mm"
    n = len(a.felder); spalten = 2; zeilen = (n + 1) // 2
    adds.append(M.cube((spalten * FX + RAND, zeilen * FY + (zeilen - 1) * RAND, B)))
    for i, spec in enumerate(a.felder):
        x0 = (i % spalten) * (FX + RAND); y0 = (i // spalten) * (FY + RAND)
        f = 2.0 if spec.endswith("*2") else 1.0; s = spec[:-2] if f == 2.0 else spec
        art, *keys = s.split(":"); key = ":".join(keys)
        txt = bruch(x0, y0, f) if art == "bruch" else (quader if art == "quader" else eck)(x0, y0, wert(keys[0]), f, *[wert(t) for t in keys[1:]])
        info.append(f"  Feld {i+1} ({spec}{', Quelle ' + key if key else ''}): {txt}")
        for jn in range(i + 1):                                                                   # Kerben am Aussenrand
            yk = -0.01 if y0 == 0 else y0 + FY - 1.49
            cuts.append(M.cube((0.8, 1.5, B + 5)).translate((x0 + 1.0 + jn * 1.6, yk, -0.5)))
    body = M.batch_boolean(adds, OpType.Add) - M.batch_boolean(cuts, OpType.Add)
    mesh = body.to_mesh(); V = np.asarray(mesh.vert_properties)[:, :3]; F = np.asarray(mesh.tri_verts)
    with open(a.aus, "wb") as fo:
        fo.write(b"mauerwerk_test rc-park".ljust(80, b" ")); fo.write(struct.pack("<I", len(F)))
        for t in F:
            p = V[t]; nrm = np.cross(p[1] - p[0], p[2] - p[0]); nrm = nrm / (np.linalg.norm(nrm) + 1e-12)
            fo.write(struct.pack("<12fH", *nrm, *p[0], *p[1], *p[2], 0))
    lo, hi = V.min(0), V.max(0)
    print(f"{a.aus}: {hi[0]-lo[0]:.1f} x {hi[1]-lo[1]:.1f} x {hi[2]-lo[2]:.2f} mm, {len(F)} Dreiecke, Volumen {body.volume():.0f} mm3, Genus {body.genus()}")
    print("\n".join(info))


if __name__ == "__main__":
    main()
