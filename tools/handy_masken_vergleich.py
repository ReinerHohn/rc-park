#!/usr/bin/env python3
"""handy_masken_vergleich.py - Sichtblaetter v1 | v2 mit Blob-Nummern (Register DI) und Auswertung der Handlabels (Sichtprobe, KEIN unabhaengiger Beleg).
  blatt:    python3 tools/handy_masken_vergleich.py blatt <stichprobe.json> <v1_dir> <v2_dir> <prefix> [--teil alt|neu|alle]
  auswerten: python3 tools/handy_masken_vergleich.py auswerten <labels.json> <stichprobe.json>
labels.json: {"<bild>": {"v1": {"ok": [Blob-Nr..], "fp": [..], "fehlt": n}, "v2": {...}}}  (ok = maskiertes Ding ist wirklich bewegt/Markt; fp = Bauwerk/Boden/Statue maskiert;
fehlt = Anzahl sichtbarer Personen/Fahrzeuge/Plane-Staende ohne Maske). Blob = Zusammenhangsgebiet der Maske (0-Pixel), Nummer = Reihenfolge der Beschriftung im Blatt."""
import sys, os, json, glob, cv2, numpy as np

def lade(d, name):
    m = cv2.imread(os.path.join(d, name[2], name[:-4] + ".png"), 0); return m

def blobs(m, minfl=0.0003):
    n, lab, st, cen = cv2.connectedComponentsWithStats((m == 0).astype(np.uint8), connectivity=8)
    out = [(i, st[i], cen[i]) for i in range(1, n) if st[i][4] >= minfl * m.size]
    out.sort(key=lambda t: (t[2][1] // (m.shape[0] / 4), t[2][0]))   # Reihenfolge oben->unten, links->rechts (Zeilenband)
    return out

def kachel(img, m, tag, tw=480, th=370):
    o = img.copy(); z = m == 0; o[z] = (0.45 * o[z] + 0.55 * np.array([0, 0, 255])).astype(np.uint8)
    f = min(tw / o.shape[1], th / o.shape[0]); o = cv2.resize(o, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
    for k, (i, st, c) in enumerate(blobs(m), 1):
        p = (int(c[0] * f), int(c[1] * f)); cv2.putText(o, str(k), p, 0, 0.8, (0, 0, 0), 4); cv2.putText(o, str(k), p, 0, 0.8, (255, 255, 255), 2)
    c = np.zeros((th, tw, 3), np.uint8); c[:o.shape[0], :o.shape[1]] = o; cv2.putText(c, tag, (4, 18), 0, 0.55, (0, 255, 255), 2); return c

def finde(name):
    for d in ("kaufhaus_handy2k", "kaufhaus_handy_npq"):
        p = f"/media/oem/scan/rc-park_null/{d}/bilder/{name}"
        if os.path.exists(p): return cv2.imread(p)

def blatt(a):
    sp = json.load(open(a[0])); v1, v2, pre = a[1], a[2], a[3]; teil = a[a.index("--teil") + 1] if "--teil" in a else "alle"
    L = (sp["alt"] if teil in ("alt", "alle") else []) + (sp["neu"] if teil in ("neu", "alle") else [])
    for b in range(0, len(L), 3):
        rows = []
        for nm in L[b:b + 3]:
            im = finde(nm); rows.append(np.hstack([kachel(im, lade(v1, nm), nm + " v1"), kachel(im, lade(v2, nm), nm + " v2")]))
        cv2.imwrite(f"{pre}_{b // 3 + 1}.jpg", np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 82]); print(f"{pre}_{b // 3 + 1}.jpg", L[b:b + 3])

def auswerten(a):
    lab = json.load(open(a[0])); sp = json.load(open(a[1])); res = {}
    for gruppe in ("alt", "neu", "alle"):
        L = sp["alt"] + sp["neu"] if gruppe == "alle" else sp[gruppe]; r = {}
        for v in ("v1", "v2"):
            ok = sum(len(lab[n][v]["ok"]) for n in L if n in lab); fp = sum(len(lab[n][v]["fp"]) for n in L if n in lab); fe = sum(lab[n][v]["fehlt"] for n in L if n in lab)
            r[v] = dict(bilder=sum(n in lab for n in L), richtig=ok, fehltreffer=fp, fehlend=fe)
        res[gruppe] = r; print(gruppe, r)
    return res

if __name__ == "__main__":
    {"blatt": blatt, "auswerten": auswerten}[sys.argv[1]](sys.argv[2:])
