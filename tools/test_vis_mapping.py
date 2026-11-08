#!/usr/bin/env python3
"""test_vis_mapping.py - Beweis und Dauerwaechter fuer die Zuordnung vis-Index -> Bild (Register CV/CW).

FEHLER (6.11.): Index in dicht/fused.ply.vis = aufsteigende Bild-ID aus sparse/images.bin, NICHT sorted(K, key=int). Bei Kaufhaus waren 14 von 94 Bildern falsch.
Tests (Exit 0 = alle bestanden):
  A Tiefenkarten  : je dichte Arbeitsumgebung (alle vorhandenen mit images.bin + depth_maps): Beobachtung (Punkt, vis-Kamera) wird in die Kamera projiziert, Tiefe z gegen die
                    geometrische Tiefenkarte DIESER Kamera (|D-z| < 3 %). Die Punkte stammen aus genau diesen Tiefenkarten -> richtige Zuordnung >= 85 % Treffer,
                    falsche (Namensreihenfolge) deutlich weniger. Pflicht: vis_ids >= 85 % UND >= Namensreihenfolge; mindestens ein Objekt, bei dem beide Ordnungen
                    verschieden sind und die Namensreihenfolge bei mindestens einer Kamera < 50 % faellt (sonst waere der Test blind).
  B Fallback      : ohne images.bin KEIN stilles Raten (FileNotFoundError); mit ausdruecklichem fallback_ids nur mit Warnung.
  C Synthetik     : gebaute images.bin mit nicht aufsteigenden Namen -> Reihenfolge nach Bild-ID; Bildmengen-Abweichung zu K bricht ab.
  D Quelltext     : jedes tools/*.py, das fused.ply.vis/vis_lesen nutzt, MUSS vis_ids/vis_namen verwenden und darf kein sorted(K...) fuer Kameraindizes haben
                    (faengt kuenftige Werkzeuge mit dem Namensreihenfolge-Fehler).
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_vis_mapping.py [dicht_ordner ...]
"""
import os, sys, re, json, glob, struct, tempfile, io, contextlib
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import freiraum_pruefen as FP

STANDARD = ["/media/oem/scan/rc-park_null/kaufhaus_null4/sfm/dicht_alle", "/media/oem/scan/rc-park_null/martinstor_lod2/sfm/dicht_nord",
            "/media/oem/scan/rc-park_null/martinstor_null/sfm/dicht_nord", "/media/oem/scan/rc-park_daten/martinstor/sfm/dicht_nord",
            "/media/oem/scan/rc-park_daten/kaufhaus/video_sfm/d_kaufhaus_null5_cnplZ_/dicht", "/media/oem/scan/rc-park_daten/martinstor/video_sfm/d1/dicht"]
fehler = []


def check(ok, text):
    print(("  ok   " if ok else "  FEHLER ") + text); (None if ok else fehler.append(text))


def depth_lesen(p):
    raw = open(p, "rb").read(); i = 0; hd = []
    while len(hd) < 3:
        j = raw.index(b"&", i); hd.append(int(raw[i:j])); i = j + 1
    w, h, c = hd; return np.ascontiguousarray(np.frombuffer(raw[i:], dtype="<f4").reshape((w, h, c), order="F").transpose(1, 0, 2)[:, :, 0])


def treffer(dicht, ids, K, X, pi, ii, n=30000, seed=1):
    """Anteil der Beobachtungen, deren Projektionstiefe in der Tiefenkarte der zugeordneten Kamera stimmt (je Kamera gemittelt)."""
    rng = np.random.default_rng(seed); j = rng.choice(len(pi), min(n, len(pi)), replace=False); ok = np.zeros(len(j), bool); cache = {}
    for q in np.unique(ii[j]):
        sel = np.where(ii[j] == q)[0]; k = K[ids[q]]; f = os.path.join(dicht, "stereo", "depth_maps", f"{k['bild']}.geometric.bin")
        if not os.path.exists(f): continue
        D = depth_lesen(f); pc = (np.array(k["R"]) @ X[pi[j[sel]]].T).T + np.array(k["t"]); z = pc[:, 2]
        u = k["fx"] * pc[:, 0] / z + k["cx"]; v = k["fy"] * pc[:, 1] / z + k["cy"]; su = D.shape[1] / k["W"]; sv = D.shape[0] / k["H"]
        iu = np.floor(u * su).astype(int); iv = np.floor(v * sv).astype(int); g = (z > 0) & (iu >= 0) & (iu < D.shape[1]) & (iv >= 0) & (iv < D.shape[0])
        d = np.zeros(len(sel)); d[g] = D[iv[g], iu[g]]; ok[sel] = g & (d > 0) & (np.abs(d - z) < 0.03 * z)
    kam = [ok[ii[j] == q].mean() for q in np.unique(ii[j]) if (ii[j] == q).sum() >= 20]
    return float(ok.mean()), float(np.mean(kam)), float(np.min(kam))


def test_a(ordner):
    print("A Tiefenkarten-Rueckprojektion"); diskriminiert = False; n_geprueft = 0
    for d in ordner:
        if not (os.path.exists(os.path.join(d, "fused.ply.vis")) and os.path.exists(os.path.join(d, "kameras_unverzerrt.json")) and os.path.exists(os.path.join(d, "sparse", "images.bin")) and os.path.isdir(os.path.join(d, "stereo", "depth_maps"))): continue
        K = json.load(open(os.path.join(d, "kameras_unverzerrt.json"))); X = FP.ply_lesen(os.path.join(d, "fused.ply")); pi, ii = FP.vis_lesen(os.path.join(d, "fused.ply.vis"))
        richtig = FP.vis_ids(d, K); naiv = sorted(K, key=int); n_geprueft += 1
        a = treffer(d, richtig, K, X, pi, ii); b = treffer(d, naiv, K, X, pi, ii); abw = sum(x != y for x, y in zip(richtig, naiv))
        print(f"   {d}: {len(K)} Bilder, {abw} Positionen verschieden; Treffer vis_ids {a[0]:.1%} (je Kamera Mittel {a[1]:.1%}, schlechteste {a[2]:.1%}) | Namensreihenfolge {b[0]:.1%} (schlechteste {b[2]:.1%})")
        check(a[1] >= 0.85 and a[2] >= 0.5, f"vis_ids richtig: {os.path.basename(os.path.dirname(d)) or d} Kamera-Mittel {a[1]:.1%} >= 85 %")
        check(a[0] >= b[0] - 1e-9, "vis_ids nicht schlechter als Namensreihenfolge")
        if abw and b[2] < 0.5: diskriminiert = True
    check(n_geprueft >= 2, f"mindestens 2 dichte Objekte geprueft ({n_geprueft})")
    check(diskriminiert, "Test nicht blind: Objekt mit Kamera unter 50 % Treffer bei Namensreihenfolge")


def images_bin(pfad, eintraege):
    """eintraege [(id, name)] in DATEIREIHENFOLGE; 0 Punkte2D."""
    with open(pfad, "wb") as f:
        f.write(struct.pack("<Q", len(eintraege)))
        for iid, nm in eintraege: f.write(struct.pack("<I", iid) + b"\0" * 32 + b"\0" * 24 + struct.pack("<I", 1) + nm.encode() + b"\0" + struct.pack("<Q", 0))


def test_bc():
    print("B Fallback / C Synthetik")
    with tempfile.TemporaryDirectory() as t:
        try: FP.vis_namen(t); check(False, "fehlende images.bin muss FileNotFoundError ausloesen")
        except FileNotFoundError: check(True, "fehlende images.bin -> FileNotFoundError (kein stilles Raten)")
        err = io.StringIO()
        with contextlib.redirect_stderr(err): r = FP.vis_namen(t, ["b", "a"])
        check(r == ["b", "a"] and "WARNUNG" in err.getvalue(), "ausdruecklicher Fallback nur mit Warnung")
        os.makedirs(os.path.join(t, "sparse")); images_bin(os.path.join(t, "sparse", "images.bin"), [(3, "205.jpg"), (1, "100.jpg"), (2, "216.jpg"), (4, "222.jpg"), (5, "10.jpg")])
        K = {k: {} for k in ["100", "216", "222", "205", "10"]}
        check(FP.vis_ids(t, K) == ["100", "216", "205", "222", "10"], "Reihenfolge nach Bild-ID (nicht Datei-, nicht Namens-, nicht Zahlenreihenfolge)")
        check(sorted(K, key=int) != FP.vis_ids(t, K), "Gegenprobe: Namensreihenfolge waere hier verschieden")
        try: FP.vis_ids(t, {"100": {}}); check(False, "Bildmengen-Abweichung muss abbrechen")
        except ValueError: check(True, "Bildmengen-Abweichung images.bin/K -> ValueError")


def test_d():
    print("D Quelltext aller Werkzeuge"); bad = []; geprueft = []
    for p in sorted(glob.glob(os.path.join(HERE, "*.py"))):
        if os.path.basename(p) in ("freiraum_pruefen.py", "test_vis_mapping.py", "test_wolke_carving.py"): continue   # test_wolke_carving: baut synthetische Wolken, filtert Punkte und behaelt die Kameraindizes (Index = Synthese-Reihenfolge)
        s = open(p, encoding="utf-8", errors="ignore").read()
        code = "\n".join(l.split("#")[0] for l in s.splitlines() if not l.strip().startswith(('"""', "'''")))
        # gefaehrdet = liest die KAMERA-Indizes (zweites Ziel von vis_lesen, nicht '_'); reine Punktzaehler (pi, _) sind unabhaengig von der Zuordnung
        if not re.search(r"\b(?!_\b)\w+\s*,\s*(?!_\b)\w+\s*=\s*(FP\.)?vis_lesen\(", code): continue
        geprueft.append(os.path.basename(p))
        if not re.search(r"vis_ids\(|vis_namen\(", code): bad.append(os.path.basename(p) + " (liest vis-Kameraindizes ohne vis_ids)")
    print("   Werkzeuge mit vis-Kameraindizes:", ", ".join(geprueft))
    check(len(geprueft) >= 3 and not bad, "alle Werkzeuge mit vis-Kameraindizes nutzen die gemeinsame Hilfe" + ("" if not bad else ": " + "; ".join(bad)))


if __name__ == "__main__":
    test_a(sys.argv[1:] or STANDARD); test_bc(); test_d()
    print("ALLE VIS-ZUORDNUNGSTESTS BESTANDEN" if not fehler else f"{len(fehler)} FEHLER"); sys.exit(1 if fehler else 0)
