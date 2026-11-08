#!/usr/bin/env python3
"""beweis_ansatz_bericht.py - Tabellen und Kriterium aus den ergebnisse.json von tools/beweis_ansatz.py (keine Nachjustierung; Regeln stehen in SPEC_BEWEIS_ANSATZ.md).
Kriterium: C >= A und C >= B in JEDER Metrik 1-5 (gleich = innerhalb 0,01 absolut bei Anteilen bzw. 1 % relativ sonst; Saatstreuung S1b T0 lag nicht vor),
und C < A und C < B in Metrik 2 (rot UND gelb im Mittel) bei mindestens 2 von 3 Objekten. Metrik 6 (Aufwand) nur berichtet.
  python3 tools/beweis_ansatz_bericht.py > Ausgabe.md
"""
import json, os, sys
BASIS = "/media/oem/scan/rc-park_null/beweis_ansatz"
OBJ = [("kaufhaus_null5", "kaufhaus_null5"), ("martinstor", "martinstor"), ("synthetisch", "synthetisch"), ("synthetisch_stark", "synthetisch_stark")]


def lade(n):
    p = os.path.join(BASIS, n, "ergebnisse.json"); return json.load(open(p)) if os.path.exists(p) else None


def mittel(d, key):
    v = [x[key] for x in (d or {}).values() if x]; return sum(v) / len(v) if v else None


def f(x, n=3): return "-" if x is None else (f"{x:.{n}f}" if isinstance(x, float) else str(x))


def pruef_ok(ps, filt):
    z = [r for r in (ps or {}).get("zeilen", []) if filt(r)]; return (sum(1 for r in z if r["status"] == "ok"), len(z), z)


def main():
    out = []; kriterium = {}; daten = {n: lade(d) for n, d in OBJ}
    for n, E in daten.items():
        out.append(f"\n### {n}\n")
        if not E: out.append("nicht gelaufen\n"); continue
        v_ = [v for v in ("A", "B", "C", "W") if v in E.get("stl", {})]
        out.append(f"Zurueckgehaltene Fotos: {', '.join(E.get('zurueckgehaltene_fotos', []))}\n")
        m2 = E["metriken"].get("2_fotos", {})
        out.append("| Metrik | " + " | ".join(v_) + " |\n|---|" + "---|" * len(v_))
        row = lambda name, fn: out.append(f"| {name} | " + " | ".join(fn(v) for v in v_) + " |")
        if "1_geometrie" in E["metriken"]:
            g = E["metriken"]["1_geometrie"]
            row("1 Chamfer (m)", lambda v: f(g.get(v, {}).get("chamfer_m"), 4)); row("1 Hausdorff (m)", lambda v: f(g.get(v, {}).get("hausdorff_m"), 2))
            row("1 Anteil > 3,5 cm", lambda v: f(g.get(v, {}).get("ueber_3_5cm"))); row("1 Anteil > 10 cm", lambda v: f(g.get(v, {}).get("ueber_10cm")))
        row("2 rot Mittel (Modellkante ohne Foto)", lambda v: f(mittel(m2.get(v), "rot"))); row("2 gelb Mittel (Fotokante ohne Modell)", lambda v: f(mittel(m2.get(v), "gelb")))
        for nr in E.get("zurueckgehaltene_fotos", []):
            row(f"2 Foto {nr} rot/gelb", lambda v, nr=nr: (lambda e: "-" if not e else f"{e['rot']:.3f}/{e['gelb']:.3f}")((m2.get(v) or {}).get(nr)))
        d3 = E["metriken"].get("3_dom1", {}); ps = E["metriken"].get("pruefstand", {})
        g3 = lambda v, a, b: (d3.get(v, {}).get(a) or {}).get(b)
        for lab, a_ in (("Zellmax", "zellmax"), ("Strahl", "strahl")):
            row(f"3 Dach {lab}: Abdeckung (Zellen mit Netz)", lambda v, a_=a_: f(g3(v, a_, "abdeckung"))); row(f"3 Dach {lab}: Median |dz| nur getroffen (m)", lambda v, a_=a_: f(g3(v, a_, "median_abs_m")))
            row(f"3 Dach {lab}: Mittel |dz| nur getroffen (m)", lambda v, a_=a_: f(g3(v, a_, "mittel_abs_m"))); row(f"3 Dach {lab}: Bias nur getroffen (m)", lambda v, a_=a_: f(g3(v, a_, "bias_m")))
        row("3 Dach alt (ohne Netz = Hoehe 0) Mittel (m), ueberholt", lambda v: f(g3(v, "alt_null_hoehe", "mittel_abs_m")))
        row("3 Pruefstand laser/lod2 bestanden", lambda v: (lambda r: f"{r[0]}/{r[1]}")(pruef_ok(ps.get(v), lambda r: r["quelltyp"] in ("laser", "laser_dom1", "lod2"))))
        row("4 Pruefstand merkmal anzahl bestanden", lambda v: (lambda r: f"{r[0]}/{r[1]}")(pruef_ok(ps.get(v), lambda r: r["merkmal"] == "anzahl")))
        d5 = E["metriken"].get("5_druck", {})
        row("5 wasserdicht / Koerper", lambda v: f"{d5.get(v, {}).get('wasserdicht')}/{d5.get(v, {}).get('koerper')}"); row("5 Dreiecke", lambda v: f(d5.get(v, {}).get("dreiecke")))
        row("5 Volumen (cm3, STL 1:87)", lambda v: f(d5.get(v, {}).get("volumen_cm3"), 0)); row("5 Wand min / p5 (mm)", lambda v: f"{(d5.get(v, {}).get('wand_mm') or {}).get('min')}/{(d5.get(v, {}).get('wand_mm') or {}).get('p5')}")
        row("5 Wand-Anteil < 0,8 mm", lambda v: f((d5.get(v, {}).get("wand_mm") or {}).get("anteil_unter_0_8")))
        row("5 Slicer rc / Zeit", lambda v: (lambda s: "-" if not s else f"{s.get('rc')} / {json.loads(s['ausgabe']).get('zeit') if s.get('ausgabe','').startswith('{') else s.get('fehler','')[:40]}")(d5.get(v, {}).get("slicer")))
        row("6 Rechenzeit Bauen (s)", lambda v: f((E["verfahren"].get(v) or {}).get("sekunden"), 1)); row("6 foto_diff 6 Fotos, Summe Rechenzeit (s, ohne GPU-Wartezeit)", lambda v: f(sum(x["sekunden"] for x in (m2.get(v) or {}).values() if x), 1) if m2.get(v) else "-")
        out.append("")
        for v in v_:
            z = (ps.get(v) or {}).get("zeilen")
            if z and v in ("A", "B", "C"): out.append(f"Pruefstand {v}: " + "; ".join(f"{r['name'][:45]}={f(r['wert'],2)} [{r['status']}]" for r in z))
        # Kriterium
        def st(v):
            r = dict(rot=mittel(m2.get(v), "rot"), gelb=mittel(m2.get(v), "gelb"))
            return r
        if all(v in m2 for v in ("A", "B", "C")):
            kriterium[n] = dict(m2_C_besser_als_A=bool(st("C")["rot"] < st("A")["rot"] and st("C")["gelb"] < st("A")["gelb"]), m2_C_besser_als_B=bool(st("C")["rot"] < st("B")["rot"] and st("C")["gelb"] < st("B")["gelb"]),
                                rot=[round(st(v)["rot"], 4) for v in "ABC"], gelb=[round(st(v)["gelb"], 4) for v in "ABC"])
    out.append("\n### Kriterium Metrik 2 (C < A und C < B, rot UND gelb im Mittel)\n")
    for n, k in kriterium.items(): out.append(f"- {n}: C<A {k['m2_C_besser_als_A']}, C<B {k['m2_C_besser_als_B']}; rot A/B/C {k['rot']}, gelb A/B/C {k['gelb']}")
    ok = sum(1 for k in kriterium.values() if k["m2_C_besser_als_A"] and k["m2_C_besser_als_B"]); out.append(f"\n=> Metrik-2-Bedingung erfuellt bei {ok} von {len(kriterium)} Objekten (verlangt: >= 2 von 3)")
    print("\n".join(out))


if __name__ == "__main__":
    main()
