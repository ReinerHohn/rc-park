#!/usr/bin/env python3
"""Synthetischer Test verbund_schwachstellen.py (Sekunden): zwei dichte Bildgruppen, verbunden ueber 1 / 3 / 10 Bruecken-Bilder; eine Gruppe allein.
Erwartet: Gelenk bei 1 Bild (zu_duenn, das Bild wird genannt), knotendisjunkt = Zahl der Brueckenbilder, Schnitt trennt die Gruppen, eine Gruppe allein 'stark';
Modellweg ueber eine echte images.bin (geschrieben im COLMAP-Binaerformat) mit Spuren quer."""
import os, sys, struct
import numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import verbund_schwachstellen as V


def gruppen_graph(k, n=30, rng=np.random.default_rng(0)):
    kanten = {}
    for g in (0, 1):
        for i in range(n):
            for j in range(i + 1, n):
                if rng.random() < 0.5: kanten[(g * n + i, g * n + j)] = int(rng.integers(50, 400))
    br = list(range(2 * n, 2 * n + k))                                                  # Brueckenbilder: je mit 4 Bildern beider Gruppen
    for b in br:
        for x in rng.choice(n, 4, replace=False): kanten[(int(x), b)] = 200
        for x in rng.choice(n, 4, replace=False): kanten[(int(n + x), b)] = 200
    namen = [f"a{i}" for i in range(n)] + [f"b{i}" for i in range(n)] + [f"k{i}" for i in range(k)]
    return namen, kanten


def bin_schreiben(pfad, bilder):
    os.makedirs(pfad, exist_ok=True)
    with open(os.path.join(pfad, "images.bin"), "wb") as f:
        f.write(struct.pack("<Q", len(bilder)))
        for i, (name, pids) in enumerate(bilder.items()):
            f.write(struct.pack("<I", i + 1) + struct.pack("<4d", 1, 0, 0, 0) + struct.pack("<3d", 0, 0, 0) + struct.pack("<I", 1) + name.encode() + b"\x00")
            f.write(struct.pack("<Q", len(pids) + 1))
            for p in pids: f.write(struct.pack("<ddQ", 1.0, 2.0, p))
            f.write(struct.pack("<ddQ", 0.0, 0.0, 2 ** 64 - 1))                      # Bildpunkt ohne 3D-Punkt


def main():
    for k in (1, 3, 10):
        namen, kanten = gruppen_graph(k); st, sw = V.analysieren(namen, kanten)
        sch = [z for z in sw if z["art"] == "schnitt" and z["tiefe"] == 0][0]
        assert sch["staerke"]["knoten_disjunkt"] == k, (k, sch["staerke"])
        a = set(n[0] for n in sch["seite_klein"]); assert a <= {"a", "k"} or a <= {"b", "k"}, a       # Schnitt trennt die Gruppen
        if k == 1:
            assert sch["urteil"] == "zu_duenn" and sch["bilder"] == ["k0"], sch
            assert any(z["art"] == "gelenk" and z["bilder"] == ["k0"] for z in sw), [z["art"] for z in sw]
        elif k == 3: assert sch["urteil"] == "duenn", sch["urteil"]
        else: assert sch["urteil"] == "stark", sch
        print(f"OK k={k}: {sch['urteil']} knotendisjunkt {sch['staerke']['knoten_disjunkt']} kantendisjunkt {sch['staerke']['kanten_disjunkt']} Leitwert {sch['staerke']['leitwert']}")
    namen, kanten = gruppen_graph(0); namen = namen[:30]; kanten = {e: w for e, w in kanten.items() if e[1] < 30}
    st, sw = V.analysieren(namen, kanten); assert all(z["urteil"] == "stark" for z in sw if z["art"] == "schnitt"), [(z["urteil"], z["staerke"]) for z in sw]
    assert not [z for z in sw if z["art"] in ("gelenk", "bruecke")]; print("OK eine Gruppe: stark, kein Gelenk")
    # Modellweg: Spuren. Gruppe A sieht Punkte 0..999, Gruppe B 1000..1999, ein Bruecken-Bild sieht 5 Punkte von A und 5 von B
    rng = np.random.default_rng(1); bilder = {}
    for g, off in (("a", 0), ("b", 1000)):
        for i in range(20): bilder[f"{g}{i}"] = list(rng.choice(1000, 150, replace=False) + off)
    bilder["bruecke"] = list(rng.choice(1000, 5, replace=False)) + list(rng.choice(1000, 5, replace=False) + 1000)
    d = __import__("pfade").temp_ordner("radar_test_"); bin_schreiben(d, bilder)
    b = V.radar(modelle=[d]); sch = [z for z in b["schwachstellen"] if z["art"] == "schnitt" and z["tiefe"] == 0][0]
    assert b["format"] == "verbund_schwachstellen/1" and b["urteil"] == "zu_duenn", b["zeile"]
    assert sch["staerke"]["spuren_quer"] == 5 and sch["staerke"]["knoten_disjunkt"] == 1 and sch["bilder"] == ["bruecke"], sch
    assert any(z["art"] == "gelenk" and z["bilder"] == ["bruecke"] for z in b["schwachstellen"])
    print("OK Modellweg:", b["zeile"][:160])
    print("ALLE OK")


if __name__ == "__main__": main()
