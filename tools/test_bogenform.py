#!/usr/bin/env python3
"""test_bogenform.py — Regression + Methodik-Schutz: die GEBAUTE Bogenform muss der
FOTO-gemessenen Form entsprechen. Soll den Fehler "Bögen zu flach" dauerhaft verhindern.

Anlass (Nutzer): ein Papier-Wert (Bautechnik 1928 "Stich 5,985 / Stich-Span 0,31") wurde
blind als Default genommen → die Bögen wurden viel zu FLACH, obwohl die Fotos klar runde
(Halbkreis-)Bögen zeigen (foto_bogen_abgleich: Stich/Span 0,43–0,49 ≈ 0,46). Lehre:
FOTO schlägt PAPIER für die sichtbare Form — und das wird hier hart abgesichert.

Prüft:
 1. ENGINE: arch_profile.basket_arch_profile ist formtreu (span/2 → Halbkreis; reproduziert
    einen verlangten Stich) — damit die Korbbogen-Maschinerie selbst korrekt ist.
 2. MODELL: das real gebaute Ravenna-STL (via echter CLI --merge) hat eine Bogenform, die
    (direkt aus der Geometrie gemessen) zur Foto-Referenz in der Merge-Spec passt.
 3. NEGATIV-KONTROLLE: ein bewusst flach gebauter Bogen (--rise 5.985, die Papier-Zahl) wird
    vom Messer als ZU FLACH erkannt → beweist, dass der Test genau diesen Fehler fängt.

  python3 tools/test_bogenform.py
"""
import os, sys, json, subprocess, tempfile, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arch_profile as apr
import trimesh

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MERGE = os.path.join(ROOT, "modelle", "ravenna", "modell_merge.json")


def build(stl, extra):
    """Ravenna über die echte CLI bauen (End-to-End, nicht Interna)."""
    cmd = [sys.executable, os.path.join(HERE, "ravenna_viadukt.py"),
           "--stl", stl, "--face", stl.replace(".stl", ".png")] + extra
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout); print(r.stderr); raise RuntimeError("Build fehlgeschlagen")
    return r.stdout


def measure_stichspan(stl, span_hint, H):
    """Stich/Span des MITTLEREN Bogens direkt aus der gebauten Geometrie messen:
    Öffnungsbreite über Höhe rastern → Span = max. Breite (am Kämpfer), Scheitel = höchste
    offene Stelle in der Bogenmitte, Stich = Scheitel − Kämpfer. Rein geometrisch, unabhängig
    vom Generator (misst das, was man SIEHT)."""
    m = trimesh.load(stl)
    mid_y = (m.bounds[0][1] + m.bounds[1][1]) / 2.0
    xc = 0.0                                             # Mittelbogen bei x=0 (ungerade n)
    halfwin = span_hint * 0.62                           # knapp über Halbspann, nicht ins Nachbarfeld
    X = np.linspace(xc - halfwin, xc + halfwin, 181)
    Z = np.linspace(1.0, H - 1.0, 161)
    XX, ZZ = np.meshgrid(X, Z)
    pts = np.column_stack([XX.ravel(), np.full(XX.size, mid_y), ZZ.ravel()])
    openg = (~m.contains(pts)).reshape(ZZ.shape)         # True = Öffnung (kein Material)
    jc = int(np.argmin(np.abs(X - xc)))
    widths = np.zeros(len(Z))
    for i in range(len(Z)):
        row = openg[i]
        if not row[jc]:
            continue
        l = jc
        while l - 1 >= 0 and row[l - 1]:
            l -= 1
        r = jc
        while r + 1 < len(X) and row[r + 1]:
            r += 1
        widths[i] = X[r] - X[l]
    span = float(widths.max())
    # Kämpfer = wo die Öffnung AM BREITESTEN ist (Anzug verengt unten, Bogen oben) → die
    # Breite hat dort ihr Maximum. Grid-Quantisierung verschmiert dieses Maximum zu einem
    # flachen Plateau; der Kämpfer liegt in dessen MITTE (argmax='Plateau-Unterkante' läse
    # den Kämpfer ~1 Zelle zu tief → Stich künstlich zu groß → falscher "zu rund"-Alarm).
    dx = float(X[1] - X[0])
    plateau = Z[widths >= span - dx]
    z_spring = float((plateau.min() + plateau.max()) / 2.0)
    center_open = openg[:, jc]
    z_crown = float(Z[center_open].max()) if center_open.any() else z_spring
    rise = z_crown - z_spring
    return rise / span, span, rise


def main():
    fails = []
    fm = json.load(open(MERGE))["form_maschinell"]
    ref = fm["bogenform_foto_stichspan"]; tol = fm["bogenform_foto_tol"]
    FLAT = 0.42                                          # alles darunter = flacher als jeder Rundbogen

    # 1) ENGINE ----------------------------------------------------------------
    _, d_half = apr.basket_arch_profile(20.0, 10.0)
    if np.max(np.abs(d_half)) > 0.02:
        fails.append(f"Engine: span/2 ergibt keinen Halbkreis (|delta|max {np.max(np.abs(d_half)):.3f})")
    th, d6 = apr.basket_arch_profile(20.0, 6.0)
    crown_r = 10.0 * (1.0 + float(np.interp(np.pi/2, th, d6)))
    if abs(crown_r - 6.0) > 0.25:
        fails.append(f"Engine: verlangter Stich 6,0 nicht reproduziert (gemessen {crown_r:.2f})")

    # 2) MODELL vs FOTO --------------------------------------------------------
    with tempfile.TemporaryDirectory() as td:
        stl = os.path.join(td, "rv.stl")
        build(stl, ["--merge", MERGE])
        ss, span, rise = measure_stichspan(stl, fm["span"], fm["H"])
        print(f"Gebaute Bogenform: Span {span:.1f} m, Stich {rise:.1f} m, Stich/Span {ss:.3f}  "
              f"(Foto-Referenz {ref:.2f} ±{tol:.2f})")
        if abs(ss - ref) > tol:
            fails.append(f"MODELL weicht von der Foto-Form ab: {ss:.3f} vs {ref:.2f}±{tol:.2f} "
                         f"— Bögen zu {'flach' if ss < ref else 'rund'}!")
        if ss < FLAT:
            fails.append(f"MODELL-Bögen zu flach ({ss:.3f} < {FLAT}) — das ist genau der Papier-Zahl-Fehler")

        # 3) NEGATIV-KONTROLLE: flacher Bogen (Papier 0,31) MUSS als zu flach erkannt werden
        flatstl = os.path.join(td, "flat.stl")
        build(flatstl, ["--rise", "5.985"])
        ss_flat, _, _ = measure_stichspan(flatstl, fm["span"], fm["H"])
        print(f"Negativ-Kontrolle (--rise 5.985): Stich/Span {ss_flat:.3f} "
              f"→ {'erkannt als zu flach ✓' if ss_flat < FLAT else 'NICHT erkannt ✗'}")
        if ss_flat >= FLAT:
            fails.append(f"Negativ-Kontrolle versagt: flacher Bogen {ss_flat:.3f} nicht als flach erkannt "
                         f"— der Test würde den Fehler NICHT fangen")

    if fails:
        print("\nFAIL:")
        for f in fails:
            print("  -", f)
        sys.exit(1)
    print("\nOK — Bogenform entspricht der Foto-Evidenz; der Flach-Bogen-Fehler wird abgefangen.")


if __name__ == "__main__":
    main()
