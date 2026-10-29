#!/usr/bin/env python3
"""test_hybrid_hart.py — ADVERSARIALES Geometrie-Audit des Hybrid-Modells. Will beweisen, dass der
Bau geschlampt ist: falsche Höhe, Fassade fehlt/floats, Box statt LOD2, geratene weiße Farbe, Spikes.

Lauf: /tmp/rv/bin/python tests/test_hybrid_hart.py   (trimesh nötig → rv-venv)
"""
import json, os, sys
import numpy as np
import trimesh

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT)
MD = "modelle/hofgut_sternen"
GLB = f"{MD}/hofgut_hybrid.glb"


def _scene():
    return trimesh.load(GLB)


def test_1_hoehe_passt_zu_lod2_und_ndom():
    """Modell-Firsthöhe muss LOD2 (17.63) UND Laser-nDOM bestätigen — sonst ist das Massing falsch."""
    sc = _scene(); h = (sc.bounds[1] - sc.bounds[0])[2]
    lod2 = max((t.get("ridge_m") or 0) for t in json.load(open(f"{MD}/footprint.json"))["teile"])
    assert abs(h - lod2) < 0.8, f"Modellhöhe {h:.2f} ≠ LOD2-First {lod2} (Massing verbogen)"
    nd = json.load(open(f"{MD}/ndom.json"))["first_ueber_boden_m"]
    assert abs(h - nd) < 2.5, f"Modellhöhe {h:.2f} widerspricht Laser-nDOM {nd}"


def test_2_footprint_komplex_nicht_box():
    """Grundfläche muss der ~47×43-Komplex sein, nicht die alte schmale Box."""
    sc = _scene(); ext = sc.bounds[1] - sc.bounds[0]
    assert ext[0] > 44 and ext[1] > 22, f"Grundfläche {ext[0]:.0f}×{ext[1]:.0f} zu klein — Box-Verdacht"


def test_3_fassade_vorhanden():
    """Die Schaufassade muss da sein: Fenster, Lauben, Blumen, Fresko als eigene Geometrien."""
    sc = _scene()
    for g in ("fenster", "balkone", "blumen", "fresko"):
        assert g in sc.geometry, f"Fassadenteil '{g}' FEHLT — Detail nicht verbaut"
        assert len(sc.geometry[g].vertices) > 0, f"'{g}' leer"


def test_4_keine_spikes_ueber_first():
    """Kein Fassadenteil darf über den First hinausragen (curtain_window-Spike-Lehre)."""
    sc = _scene(); top = sc.bounds[1][2]
    for name in ("fenster", "fensterrahmen", "blumen", "balkone"):
        if name in sc.geometry:
            zmax = sc.geometry[name].bounds[1][2]
            assert zmax <= top + 0.1, f"'{name}' ragt bei {zmax:.1f} über First {top:.1f} = Spike"


def test_5_farben_gemessen_nicht_weiss():
    """Wand = gemessenes DUNKLES Holz, nicht geratenes Weiß; Dach = gemessenes Graubraun."""
    FM = json.load(open(f"{MD}/farben.json"))
    sc = _scene()
    w = sc.geometry["waende"].visual.face_colors[0][:3]
    assert max(w) < 160, f"Wandfarbe {list(w)} zu hell — geratenes Weiß statt Holz {FM['og_lauben']}"
    d = sc.geometry["daecher"].visual.face_colors[0][:3]
    assert abs(int(d[0]) - FM["dach"][0]) < 25, f"Dachfarbe {list(d)} ≠ gemessen {FM['dach']}"


def test_6_fassade_sitzt_am_hauptfluegel():
    """Fassade darf nicht frei im Raum schweben: ihre x-Spanne muss in der Hauptflügel-Front liegen."""
    fr = json.load(open(f"{MD}/massing_frame.json"))["front"]
    sc = _scene(); fb = sc.geometry["fenster"].bounds
    assert fb[0][0] >= fr["x0"] - 2 and fb[1][0] <= fr["x1"] + 2, \
        f"Fenster-x {fb[0][0]:.1f}..{fb[1][0]:.1f} außerhalb Hauptflügel {fr['x0']:.1f}..{fr['x1']:.1f}"


if __name__ == "__main__":
    tests = sorted(k for k in globals() if k.startswith("test_"))
    fails = 0
    for t in tests:
        try:
            globals()[t](); print(f"  PASS  {t}")
        except AssertionError as e:
            fails += 1; print(f"  FAIL  {t}\n          └─ {e}")
        except Exception as e:
            fails += 1; print(f"  ERROR {t}\n          └─ {type(e).__name__}: {e}")
    print(f"\n{len(tests)-fails}/{len(tests)} bestanden.")
    sys.exit(1 if fails else 0)
