#!/usr/bin/env python3
"""modellgen.py — DIRIGENT: Bauwerk-Name → druck/cutbares Hybrid-Modell.

Idee: nicht noch ein Generator, sondern EIN Dirigent, der die bestehenden
Tools in der richtigen Reihenfolge aufruft. Du sagst ein BAUWERK ("Linach-
talsperre", "Schluchsee", "Ravenna-Viadukt"), der Dirigent wählt den
ARCHETYP und fährt die passende Hybrid-Pipeline:

    Laser-Gerüst (Volumen, schnell, gratis) + 3D-Haut/Parametrik (Detail)

Archetypen
    staumauer   parametrische Mauer (linachtalsperre.py) + Gelände-Gerüst
    see         reines Gelände: Gerüst (eggcrate) + Haut (skin) + Oberfläche (ortho)
    gelaende    wie see, Oberfläche optional (Trasse/Features möglich)
    viadukt     Bogen-Viadukt (parametrisch) + Taleinschnitt — GENERATOR FEHLT NOCH

Die Fallen aus dem Projekt-Gedächtnis sind als Checks eingebaut:
  * Daten erst LOKALISIEREN (Katalog nennt LGL-Kachel; fehlt DEM → ehrlicher Abbruch)
  * Maßstab → mm konsistent aus Zellgröße (keine Trasse-Maßstab-Falle)
  * nach dem Bauen euler/watertight der STL melden

Aufrufe
    python3 tools/modellgen.py --list
    python3 tools/modellgen.py linachtalsperre --dry-run
    python3 tools/modellgen.py linachtalsperre
    python3 tools/modellgen.py hirschsprung --scale N --only geruest
"""
import argparse, os, subprocess, sys, textwrap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Maßstab → Modell-mm je ECHTEM Meter (vertikal) ----------------------------
SCALES = {"N": 6.25, "TT": 8.33, "H0": 11.54, "1:100": 10.0, "1:160": 6.25}

# Validiert erprobte Defaults (siehe tools/validate_modell.py):
# smooth 0.3 hält steile Topographien treu; split-len hält Teile auf dem Bogen.
SMOOTH_DEFAULT = 0.3
SPLIT_LEN_DEFAULT = 380.0      # S9-Bogen 410 mm minus Rand/Flare
SHEET_X, SHEET_Y = 410.0, 400.0

# ---------------------------------------------------------------------------
# KATALOG: Bauwerk → Lage, Maßstab, Archetyp, Daten.  cell_m = DEM-Zellgröße.
# dem=None  → Daten fehlen noch; Dirigent nennt die LGL-Kachel zum Holen.
# ---------------------------------------------------------------------------
KATALOG = {
    "linachtalsperre": dict(
        titel="Linachtalsperre (Gewölbereihen-Staumauer)",
        koord=(48.0636, 8.1736), lgl_tile="447_5318", scale="1:100",
        archetyp="staumauer",
        dem="daten/linach/linach_dgm1.npy", cell_m=1.0, fenster=None,
        script="linachtalsperre.py",
        hinweis="Mauer parametrisch (13 Bögen), Gelände-Gerüst drumrum.",
    ),
    "hirschsprung": dict(
        titel="Hirschsprung / Höllentalbahn-Enge",
        koord=(47.8206, 8.0431), lgl_tile="426_5309", scale="N",
        archetyp="gelaende",
        dem="daten/hoellental/dgm025_full.npy", cell_m=0.25,
        fenster=(470, 640, 3310, 3570),
        track="daten/hoellental/hoellental_track.npy",
        tfw="daten/hoellental/dgm025_32_426_5309_1_bw_2017.tfw", dop_tile="426_5309",
        hinweis="Gelände-Hybrid mit Trasse+Tunnel; Oberfläche per LGL-DOP.",
    ),
    "schluchsee": dict(
        # KORREKTUR: Staumauer liegt in Seebrugg (SO-Ende), NICHT See-Mitte.
        # Mauer UTM E438867/N5294465 → Paket 437_5294, Subkachel 438_5294 (dgm025 vorhanden).
        titel="Schluchsee-Staumauer (Seebrugg)",
        koord=(47.80064, 8.18361), lgl_tile="437_5294", scale="N",
        archetyp="staumauer",   # markant ist die GEWICHTSMAUER (63,5 m × 250 m), nicht das Gelände
        dem=None, cell_m=0.25, fenster=None,
        hinweis="Gewichtsstaumauer-Generator nötig (Trapez-Querschnitt, leicht gekrümmt). "
                "DGM025 Paket 437_5294. Reines Gelände fällt bei Markanz durch (siehe bewerter_voting).",
    ),
    "ravenna-viadukt": dict(
        titel="Ravenna-Viadukt (Höllental)",
        koord=(47.9036, 8.0881), lgl_tile="427_5305", scale="N",
        archetyp="viadukt",
        dem=None, cell_m=1.0, fenster=None,
        hinweis="DEM fehlt UND Bogen-Viadukt-Generator fehlt (≈ Staumauer-Bögen).",
    ),
}


def mm_per_cell(scale, cell_m):
    """HORIZONTAL mm je DEM-Zelle = (mm/Meter) * Zellgröße[m]."""
    return SCALES[scale] * cell_m


def run(argv, dry):
    """Ein Pipeline-Schritt. Gibt (rc, captured_stdout) zurück."""
    print("    $ " + " ".join(argv))
    if dry:
        return 0, ""
    p = subprocess.run(argv, cwd=ROOT, text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for line in p.stdout.splitlines():
        print("      " + line)
    return p.returncode, p.stdout


def win_args(spec):
    f = spec["fenster"]
    return [] if not f else ["--r0", str(f[0]), "--r1", str(f[1]),
                             "--c0", str(f[2]), "--c1", str(f[3])]


# --- Pipelines pro Archetyp -------------------------------------------------
def pipe_gelaende(name, spec, scale, out, steps, dry):
    """see / gelaende: Gerüst (cut) + Haut (print) + optional Oberfläche."""
    mm = mm_per_cell(scale, spec["cell_m"])
    vmm = SCALES[scale]
    results = []

    smooth = spec.get("smooth", SMOOTH_DEFAULT)
    if "geruest" in steps:
        print("  [Gerüst] Laser-Eggcrate (Volumen, zusammensteckbar)")
        argv = ["python3", "tools/terrain_eggcrate.py", "--dem", spec["dem"],
                "--mm", f"{mm:g}", "--nscale", f"{vmm:g}",
                "--smooth", f"{smooth:g}",
                "--split-len", f"{spec.get('split_len', SPLIT_LEN_DEFAULT):g}",
                "--dump-surface", os.path.join(out, "surface.npz"),
                "--out", os.path.join(out, "geruest")] + win_args(spec)
        if spec.get("track"):
            argv += ["--track", spec["track"], "--tunnel"]
        results.append(("geruest", *run(argv, dry)))

    if "haut" in steps:
        print("  [Haut] 3D-Druck-Schale, flach gelegt + nummeriert")
        argv = ["python3", "tools/skin_smart_split.py", "--dem", spec["dem"],
                "--mm", f"{mm:g}", "--nscale", f"{vmm:g}", "--smooth", f"{smooth:g}",
                "--out", os.path.join(out, "haut")] + win_args(spec)
        results.append(("haut", *run(argv, dry)))

    if "ortho" in steps and spec.get("tfw"):
        print("  [Oberfläche] LGL-DOP20-Luftbild deckungsgleich")
        argv = ["python3", "tools/ortho_drape.py", "--tfw", spec["tfw"],
                "--tile", spec.get("dop_tile", ""), "--mm", f"{mm:g}",
                "--out", os.path.join(out, "ortho")] + win_args(spec)
        results.append(("ortho", *run(argv, dry)))
    elif "ortho" in steps:
        print("  [Oberfläche] übersprungen — keine .tfw-Georef im Katalog")
    return results


def pipe_staumauer(name, spec, scale, out, steps, dry):
    """Parametrische Mauer (eigenes Skript) + optional Gelände-Gerüst."""
    results = []
    if "mauer" in steps:
        print("  [Mauer] parametrische Gewölbereihe (Skript, hardcodiert)")
        argv = ["python3", "tools/" + spec["script"]]
        results.append(("mauer", *run(argv, dry)))
    if "geruest" in steps and spec.get("dem"):
        print("  [Gerüst] Gelände um die Mauer (eggcrate)")
        mm = mm_per_cell(scale, spec["cell_m"])
        argv = ["python3", "tools/terrain_eggcrate.py", "--dem", spec["dem"],
                "--mm", f"{mm:g}", "--nscale", f"{SCALES[scale]:g}",
                "--out", os.path.join(out, "geruest")] + win_args(spec)
        results.append(("geruest", *run(argv, dry)))
    return results


def pipe_viadukt(name, spec, scale, out, steps, dry):
    print("  [Viadukt] GENERATOR FEHLT NOCH.")
    print(textwrap.indent(textwrap.dedent("""\
        Plan (fast identisch zur Staumauer-Gewölbereihe):
          1. Trasse+Bogen-Stützweiten aus OSM/Foto (Ravenna: 9 Bögen, ~37 m hoch)
          2. parametrische Bögen wie N_ARCH in linachtalsperre.py, aber offen/hoch
          3. Taleinschnitt-DEM als Gerüst drunter (eggcrate), Viadukt als 3D-Druck
        → tools/viadukt.py anlegen, dann hier archetyp='viadukt' verdrahten."""), "    "))
    return []


PIPES = {"see": pipe_gelaende, "gelaende": pipe_gelaende,
         "staumauer": pipe_staumauer, "viadukt": pipe_viadukt}
STEPS_FOR = {"see": ["geruest", "haut", "ortho"],
             "gelaende": ["geruest", "haut", "ortho"],
             "staumauer": ["mauer", "geruest"], "viadukt": []}


def validate(name, spec, scale, out, dry):
    """Dirigent prüft das ECHTE gebaute Modell gegen die Realität (Pflicht-Schritt)."""
    surf = os.path.join(ROOT, out, "surface.npz")
    if dry or not os.path.exists(surf):
        return None
    print("\n  [Validierung] echtes Modell vs. Realität")
    argv = ["python3", "tools/validate_modell.py", "--surface", surf,
            "--mode", "cut", "--artifact", os.path.join(out, "geruest")]
    rc, _ = run(argv, False)
    return rc


def euler_check(out, dry):
    """Nachprüfen: produzierte STL watertight? (haut_druck_pipeline-Falle)"""
    if dry:
        return
    try:
        import trimesh, glob
    except ImportError:
        return
    stls = glob.glob(os.path.join(out, "**", "*.stl"), recursive=True)
    if not stls:
        return
    print("\n  [Check] STL-Geometrie:")
    for s in sorted(stls)[:12]:
        try:
            m = trimesh.load(s, force="mesh")
            print(f"    {os.path.relpath(s, out):40s} "
                  f"watertight={m.is_watertight} euler={m.euler_number}")
        except Exception as e:
            print(f"    {os.path.relpath(s, out):40s} FEHLER {e}")


def build(name, scale_override, only, dry):
    spec = KATALOG[name]
    scale = scale_override or spec["scale"]
    if scale not in SCALES:
        sys.exit(f"Maßstab {scale} unbekannt. Bekannt: {', '.join(SCALES)}")
    out = os.path.join("modelle", name)
    print(f"\n=== {spec['titel']} ===")
    print(f"  Lage {spec['koord']}  LGL {spec['lgl_tile']}  "
          f"Maßstab {scale}  Archetyp {spec['archetyp']}")
    print(f"  {spec['hinweis']}")

    # Falle 1: Daten erst LOKALISIEREN
    if spec["archetyp"] != "viadukt" and not spec.get("dem"):
        print(f"\n  ✗ DEM fehlt. Zuerst LGL-DGM1 Kachel {spec['lgl_tile']} holen "
              f"→ daten/{name}/ , dann Katalog-Feld dem= setzen.")
        return
    if spec.get("dem") and not os.path.exists(os.path.join(ROOT, spec["dem"])):
        print(f"\n  ✗ DEM-Pfad im Katalog existiert nicht: {spec['dem']}")
        return

    steps = STEPS_FOR[spec["archetyp"]]
    if only:
        steps = [s for s in steps if s in only]
    os.makedirs(os.path.join(ROOT, out), exist_ok=True)

    results = PIPES[spec["archetyp"]](name, spec, scale, out, steps, dry)

    bad = [n for n, rc, _ in results if rc != 0]
    for n, rc, outtxt in results:
        if "track" in outtxt.lower() and "punkt" in outtxt.lower():
            pass  # Trasse-Meldung steht schon im durchgereichten stdout
    euler_check(os.path.join(ROOT, out), dry)
    vrc = validate(name, spec, scale, out, dry)
    print()
    if bad:
        print(f"  ⚠ Schritte mit Fehler: {', '.join(bad)}")
    elif vrc == 2:
        print(f"  ✗ Modell-Validierung FAIL — Nacharbeit nötig, siehe oben ({out}/)")
    elif vrc == 1:
        print(f"  ⚠ Modell-Validierung WARN → {out}/")
    elif not dry:
        tail = " (validiert ✓)" if vrc == 0 else ""
        print(f"  ✓ fertig → {out}/{tail}")


def list_catalog():
    print("Bauwerke im Katalog:\n")
    for k, s in KATALOG.items():
        state = "✓ Daten da" if s.get("dem") else "✗ Daten fehlen"
        if s["archetyp"] == "viadukt":
            state += " + Generator fehlt"
        print(f"  {k:18s} {s['archetyp']:10s} {state}")
        print(f"  {'':18s} {s['titel']}")
    print("\n  python3 tools/modellgen.py <name> [--scale N] "
          "[--only geruest,haut] [--dry-run]")


def main():
    ap = argparse.ArgumentParser(description="Dirigent: Bauwerk → Hybrid-Modell")
    ap.add_argument("ort", nargs="?", help="Bauwerk-Name (siehe --list)")
    ap.add_argument("--list", action="store_true", help="Katalog zeigen")
    ap.add_argument("--scale", help="Maßstab überschreiben (" + ",".join(SCALES) + ")")
    ap.add_argument("--only", help="nur diese Schritte, kommagetrennt "
                    "(geruest,haut,ortho,mauer)")
    ap.add_argument("--dry-run", action="store_true", help="nur Plan zeigen")
    a = ap.parse_args()

    if a.list or not a.ort:
        list_catalog(); return
    if a.ort not in KATALOG:
        sys.exit(f"Unbekannt: {a.ort}\nBekannt: {', '.join(KATALOG)}  (--list)")
    only = set(a.only.split(",")) if a.only else None
    build(a.ort, a.scale, only, a.dry_run)


if __name__ == "__main__":
    main()
