#!/usr/bin/env python3
"""VOTING — die drei Juroren (Geometrie-Treue · Fertigbarkeit · Markanz) stimmen ab.

HINWEIS: abgelöst durch tools/bewerter_panel.py (3 UNABHÄNGIGE Juroren PRO Kategorie,
harte Einstimmigkeit). Dieses Tool (1 Juror/Kategorie) bleibt als schnelle Variante nutzbar.


KRITISCH, kein Schönreden:
  - Jedes FAIL eines Jurors deckelt das Gesamturteil auf max. WARN, egal wie gut der Rest.
  - "BAUEN" nur wenn ALLE drei ≥ WARN UND gewichteter Schnitt ≥ 68 UND ≥2× PASS.
  - Der größte Einwand (schwächster Juror) wird explizit als nächster Schritt genannt.

Gewichte: Markanz 0.40 (lohnt es sich?), Geometrie 0.33 (ist es echt?),
Fertigbarkeit 0.27 (kriegen wir es gebaut?). Markanz führt, weil ein unspektakuläres
Modell perfekt gefertigt trotzdem wertlos ist.

Aufruf:
  python3 tools/bewerter_voting.py --manifest modelle/x/manifest.json
  python3 tools/bewerter_voting.py --batch modelle/schwarzwald_manifests/*.json --rank
"""
import argparse, sys, os, glob, json
import bewerter_common as bc
import bewerter_geometrie as jg
import bewerter_fertigung as jf
import bewerter_markanz as jm

W = {"Geometrie-Treue": 0.33, "Fertigbarkeit": 0.27, "Markanz": 0.40}
RANK = {"PASS": 2, "WARN": 1, "FAIL": 0}


def evaluate(m):
    vs = [jm.judge(m), jg.judge(m), jf.judge(m)]
    mean = sum(W[v["judge"]] * v["score"] for v in vs)
    worst = min(vs, key=lambda v: v["score"])
    n_pass = sum(v["verdict"] == "PASS" for v in vs)
    n_fail = sum(v["verdict"] == "FAIL" for v in vs)

    if n_fail > 0:
        overall = "NACHBESSERN"          # ein Juror blockt
    elif mean >= 68 and n_pass >= 2 and all(v["verdict"] != "FAIL" for v in vs):
        overall = "BAUEN"
    elif mean >= 55:
        overall = "BEDINGT"
    else:
        overall = "VERWERFEN"
    # echten Einwand bevorzugen: erste Warn-/Fehlerzeile über ALLE Juroren
    einwand = ""
    for v in sorted(vs, key=lambda v: v["score"]):
        hit = next((r for r in v["reasons"] if ("⚠" in r or "❌" in r)), None)
        if hit:
            einwand = f"[{v['judge']}] {hit}"; break
    if not einwand:
        einwand = "kein harter Einwand — alle Juroren zufrieden"
    return {"name": m.get("name", "?"), "mean": round(mean, 1), "overall": overall,
            "n_pass": n_pass, "n_fail": n_fail, "worst": worst["judge"],
            "einwand": einwand, "judges": vs}


def report(res):
    icon = {"BAUEN": "🟢", "BEDINGT": "🟡", "NACHBESSERN": "🟠", "VERWERFEN": "🔴"}[res["overall"]]
    print("=" * 66)
    print(f"{icon}  {res['name']}  —  GESAMT {res['mean']}/100  →  {res['overall']}")
    print("=" * 66)
    for v in res["judges"]:
        bc.print_verdict(v)
    print(f"\n  Größter Einwand (schwächster Juror = {res['worst']}):")
    print(f"    → {res['einwand']}")
    if res["overall"] != "BAUEN":
        print(f"  Nächster Schritt: {res['worst']} verbessern, bevor gebaut wird.")
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest")
    ap.add_argument("--batch", nargs="*", default=[])
    ap.add_argument("--rank", action="store_true")
    ap.add_argument("--json", action="store_true", help="Ergebnis als JSON ausgeben")
    a = ap.parse_args()

    mans = []
    if a.manifest:
        mans.append(a.manifest)
    for g in a.batch:
        mans.extend(sorted(glob.glob(g)))
    if not mans:
        sys.exit("--manifest oder --batch angeben")

    results = []
    for p in mans:
        m = bc.load_manifest(p)
        try:
            results.append(evaluate(m))
        except Exception as e:
            print(f"!! {p}: {e}")

    if a.rank:
        results.sort(key=lambda r: (-RANK.get(r["overall"] == "BAUEN" and "PASS" or "WARN", 0), -r["mean"]))
        results.sort(key=lambda r: -r["mean"])
        print("\n################  RANGLISTE  ################")
        order = {"BAUEN": 0, "BEDINGT": 1, "NACHBESSERN": 2, "VERWERFEN": 3}
        results.sort(key=lambda r: (order[r["overall"]], -r["mean"]))
        for i, r in enumerate(results, 1):
            print(f"{i:2}. {r['mean']:5.1f}  {r['overall']:<11} {r['name']:<34} (schwach: {r['worst']})")
        print()
    else:
        for r in results:
            report(r)

    if a.json:
        print(json.dumps(results, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
