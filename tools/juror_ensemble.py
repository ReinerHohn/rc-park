#!/usr/bin/env python3
"""juror_ensemble.py — GENERISCH: mehrere Vision-Juror-Urteile (JSON) zu einem STABILEN
Konsens aggregieren. Median der Zählungen, Mehrheit der Bool-Flags, häufigkeits-gerankte
Fixes → beseitigt das Oszillieren einzelner LLM-Juroren.

Aufruf:  python3 tools/juror_ensemble.py juror1.json juror2.json juror3.json
Jedes JSON = ein Juror-Urteil (gleiches Schema). Fehlende Felder werden toleriert.
"""
import sys, json, re
from collections import Counter


def med(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    return xs[n//2] if n % 2 else (xs[n//2-1]+xs[n//2])/2


def get(d, *path, default=None):
    for p in path:
        if isinstance(d, dict) and p in d:
            d = d[p]
        else:
            return default
    return d


def norm_fix(s):
    """grobe Normalisierung, um ähnliche Fix-Anweisungen zu bündeln (erstes Schlüsselwort)."""
    s = s.lower()
    for kw in ["statue", "figur", "dach", "gaube", "lukarne", "bogen", "arkade", "erker",
               "turm", "helm", "fenster", "farbe", "proportion", "giebel", "ziegel"]:
        if kw in s:
            return kw
    return s[:16]


def aggregate(jurors):
    out = {"n_juroren": len(jurors)}
    # Zählungen (Felder, deren Wert [foto, modell] oder {"foto":..,"modell":..} ist)
    count_keys = set()
    for j in jurors:
        for k, v in j.items():
            if isinstance(v, (list, dict)) and k in ("anzahl",):
                count_keys |= set(v.keys())
    counts = {}
    for ck in count_keys:
        fotos, modells = [], []
        for j in jurors:
            v = get(j, "anzahl", ck)
            if isinstance(v, list) and len(v) == 2:
                fotos.append(v[0]); modells.append(v[1])
            elif isinstance(v, dict):
                fotos.append(v.get("foto")); modells.append(v.get("modell"))
        mf, mm = med(fotos), med(modells)
        counts[ck] = {"foto_median": mf, "modell_median": mm,
                      "match": (mf is not None and mm is not None and abs(mf-mm) < 0.6),
                      "streuung_foto": sorted(set(x for x in fotos if x is not None))}
    out["anzahl"] = counts
    # Bool-Flags per Mehrheit
    bool_keys = set()
    for j in jurors:
        for k, v in j.items():
            if isinstance(v, bool):
                bool_keys.add(k)
    flags = {}
    for bk in bool_keys:
        vals = [j.get(bk) for j in jurors if isinstance(j.get(bk), bool)]
        flags[bk] = (sum(vals) > len(vals)/2) if vals else None
    out["flags_mehrheit"] = flags
    # Note: Median
    out["note_median"] = med([get(j, "gesamt_note") for j in jurors])
    # Verdikt: Mehrheit (FAIL falls Note<6)
    verd = [str(j.get("verdikt", "")).upper() for j in jurors]
    out["verdikt"] = "PASS" if (verd.count("PASS") > len(verd)/2 and (out["note_median"] or 0) >= 6) else "FAIL"
    # Fixes: alle sammeln, nach Häufigkeit (gebündelt) ranken
    allfix = []
    for j in jurors:
        for f in (j.get("fixes") or j.get("top3_schwaechen") or []):
            allfix.append(f)
    buckets = Counter(norm_fix(f) for f in allfix)
    ranked = []
    seen = set()
    for kw, cnt in buckets.most_common():
        # repräsentative Formulierung = erster Fix mit diesem Keyword
        rep = next((f for f in allfix if norm_fix(f) == kw), kw)
        ranked.append({"thema": kw, "nennungen": cnt, "fix": rep})
    out["konsens_fixes"] = ranked
    return out


def main():
    jurors = []
    for p in sys.argv[1:]:
        txt = open(p).read()
        m = re.search(r'\{.*\}', txt, re.S)        # JSON aus evtl. Prosa extrahieren
        jurors.append(json.loads(m.group(0) if m else txt))
    print(json.dumps(aggregate(jurors), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
