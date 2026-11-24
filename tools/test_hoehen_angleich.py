#!/usr/bin/env python3
"""test_hoehen_angleich.py - synthetische Pruefung von tools/hoehen_angleich.py (Hoehen-Angleich waagerechter Bauteile, 24.11.2026) und bauteile.hoehen_aus_json.

Nachgebaut: Turm 10 x 8 x 20 m, Gesimse z 6 und 13 (0,4 m hoch, 0,4 m Ausladung), Traufplatte 20 m (wie tools/test_hoehensitz.py). Wolke = WAHRE Form.
MODELL: das obere Gesims sitzt ringsum 0,6 m zu hoch (13,6) - typisch fuer eine Hoehe aus einem auf die Wandebene entzerrten Foto (Auskragungs-Falle).
  A  Fotokanten an den WAHREN Gesimskanten (13,0 / 13,4) + senkrechte Eckkanten + Rauschen -> Wolke und Kanten einig -> Korrektur ~ -0,6 je Seite angenommen;
     nach der Abbildung sitzt das Gesims (Hoehensitz steigt je Seite), Gesims z 6 und Traufe z 20 bleiben (Verschiebung ~0), Abbildung umkehrbar.
  B  Fotokanten an der MODELL-Hoehe (13,6 / 14,0) -> Quellen uneinig / Kanten stuetzen das Modell -> KEINE Korrektur (Guard: zwei Quellen noetig).
  C  keine Kantendatei -> rc 3, nichts angenommen (nur Bericht).
  F  Faltungs-Guard: unbelegte Nachbarlinie 0,2 m unter einer -0,6-m-Korrektur -> verworfen.
  G  bauteile.hoehen_aus_json verschiebt einen Manifold-Koerper (warp_batch), Beleg 'Hoehenangleich'; ohne angenommene Korrektur unveraendert.
Nur CPU, ~1-2 min. Aufruf: /media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_hoehen_angleich.py
"""
import sys, os, json, io, contextlib
os.environ["CUDA_VISIBLE_DEVICES"] = ""
import numpy as np, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pfade import temp_ordner
import hoehensitz as HS, hoehen_angleich as HA
from test_hoehensitz import kam, box, stl

F = 0


def pruef(ok, text):
    global F
    print(("    ok    " if ok else "    FEHLER ") + text)
    if not ok: F += 1


def turm(z_oben=13.0):
    teile = [box([10, 8, 20], [0, 0, 10]), box([11.2, 9.2, 0.3], [0, 0, 20.15]), box([6, 5, 4], [0, 0, 22.3])]
    for zu in (6.0, z_oben):
        teile += [box([0.4, 8.8, 0.4], [5.2, 0, zu + 0.2]), box([0.4, 8.8, 0.4], [-5.2, 0, zu + 0.2]), box([10.8, 0.4, 0.4], [0, 4.2, zu + 0.2]), box([10.8, 0.4, 0.4], [0, -4.2, zu + 0.2])]
    return trimesh.util.concatenate(teile)


def kantenpunkte(z_gesims, rng):
    """Triangulierte Kantenpunkte wie die Kantenstufe: waagerechte Gesimskanten (Unter-/Oberkante, Aussenflaeche), Gesims z 6, Traufe, senkrechte Ecken, Rauschen."""
    P = []
    for zk in (z_gesims, z_gesims + 0.4, 6.0, 6.4, 20.0):
        for s in (1, -1):
            x = rng.uniform(-5, 5, 400); P.append(np.c_[x, np.full(400, 4.4 * s), np.full(400, zk)])
            y = rng.uniform(-4, 4, 400); P.append(np.c_[np.full(400, 5.4 * s), y, np.full(400, zk)])
    for cx in (5, -5):
        for cy in (4, -4): P.append(np.c_[np.full(600, cx), np.full(600, cy), rng.uniform(0, 20, 600)])
    P.append(rng.uniform([-6, -5, 0], [6, 5, 22], (1500, 3)))
    P = np.vstack(P); return (P + rng.normal(0, 0.03, P.shape)).astype(np.float32)


def main():
    print("test_hoehen_angleich:")
    R0 = temp_ordner("test_hoehen_angleich_"); OD = os.path.join(R0, "modelle", "probe"); MP = os.path.join(OD, "messprotokoll")
    for d in (MP, os.path.join(OD, "sfm"), os.path.join(R0, "modelle", "stl"), os.path.join(R0, "daten", "probe", "fotos")): os.makedirs(d, exist_ok=True)
    SK = {"+x": "Sued", "-x": "Nord", "+y": "Ost", "-y": "West", "quelle": "Test"}
    obj = dict(name="probe", stl="modelle/stl/probe.stl", stl_massstab=87, stl_einheit_mm=True, zentrierung="achse", audit="modelle/probe/audit",
               fotos_dir="daten/probe/fotos", seiten_konvention=SK, elemente="modelle/probe/elemente.json")
    OJ = os.path.join(OD, "objekt.json"); json.dump(obj, open(OJ, "w"))
    json.dump([dict(seite="wand", element="Gesims oben z 13.60..14.00 m", quelle="Test"), dict(seite="wand", element="Gesims unten", quelle="Test", z0=6.0, z1=6.4)],
              open(os.path.join(OD, "elemente.json"), "w"))
    wahr = turm(13.0); modell = turm(13.6); stl_m = os.path.join(R0, "modelle", "stl", "probe.stl"); stl(modell, stl_m)
    S = dict(k=1, seiten={}, ersetzungen=[])
    for ax, C in {"+x": [30.0, 0, 8], "-x": [-30.0, 0, 8], "+y": [0, 30.0, 8], "-y": [0, -30.0, 8]}.items():
        nr = f"k{ax[1]}{'p' if ax[0] == '+' else 'm'}"; json.dump(dict(foto=nr, kamera=kam(C, [0, 0, 8.0])), open(os.path.join(MP, f"K-{nr}.json"), "w"))
        S["seiten"][ax] = dict(name=SK[ax], fotos=[nr])
    sp = os.path.join(R0, "fotosatz.json"); json.dump(S, open(sp, "w"))
    Pw = np.asarray(trimesh.sample.sample_surface(wahr, 1500000, seed=5)[0]) + np.random.default_rng(6).normal(0, 0.02, (1500000, 3))
    np.save(os.path.join(OD, "sfm", "punkte_modell_probe.npy"), Pw.astype(np.float32))
    rng = np.random.default_rng(3)
    kA = os.path.join(R0, "kanten_wahr.npz"); np.savez(kA, P=kantenpunkte(13.0, rng)); kB = os.path.join(R0, "kanten_modell.npz"); np.savez(kB, P=kantenpunkte(13.6, rng))
    N = ["--n-modell", "1500000", "--n-wolke", "1500000", "--fotosatz", sp]

    def lauf(name, extra):
        jp = os.path.join(R0, name + ".json"); buf = io.StringIO()
        with contextlib.redirect_stdout(buf): rc = HA.main([OJ, "--aus", jp] + N + extra)
        if rc not in (0, 2, 3): print(buf.getvalue()[-2000:])
        return rc, (json.load(open(jp)) if os.path.exists(jp) else {}), buf.getvalue()

    # --- A: beide Quellen einig
    rc, A, txt = lauf("A", ["--kanten", kA, "--bild", os.path.join(R0, "ha.png")])
    ang = [q for q in A.get("korrekturen", []) if q.get("angenommen")]
    seiten_ang = sorted({q["achse"] for q in ang})
    pruef(rc == 0 and seiten_ang == sorted(["+x", "-x", "+y", "-y"]), f"A: rc {rc}, Korrekturen auf allen vier Seiten ({seiten_ang})")
    pruef(all(-0.72 <= q["dz"] <= -0.48 and 13.4 <= q["z"] <= 14.2 for q in ang), f"A: dz ~ -0,6 am oberen Gesims ({[(q['achse'], q['z'], q['dz']) for q in ang]})")
    pruef(all(any("Gesims oben" in b for b in q.get("bauteile", [])) for q in ang), "A: Bauteil-Zuordnung nennt 'Gesims oben'")
    pruef(os.path.exists(os.path.join(R0, "ha.png")), "A: Kontrollbild geschrieben")
    Pt = np.array([[0, 4.0, 6.2], [5.0, 0, 6.2], [0, -4.0, 20.0], [5.0, 0, 20.1], [0, 4.0, 13.8], [-5.0, 0, 13.8], [0, 0, 13.8]], float)
    d = HA.verschiebung(Pt, A)
    pruef(np.all(np.abs(d[:4]) < 0.02) and np.all(d[4:6] < -0.45), f"A: Gesims z 6 und Traufe z 20 bleiben, oberes Gesims verschoben ({np.round(d, 3).tolist()})")
    pruef(abs(d[6]) < 0.05, f"A: Kern (Turmmitte, ausserhalb der Aussenschale) bleibt ({d[6]:.3f})")
    Q = np.c_[rng.uniform(-5.5, 5.5, 5000), rng.uniform(-4.5, 4.5, 5000), rng.uniform(0, 22, 5000)]
    W_ = HA.verschoben(Q, A); back = HA.zurueckrechnen(W_, A)
    pruef(float(np.abs(back - Q).max()) < 0.01, f"A: Abbildung umkehrbar (Fixpunkt, max {np.abs(back - Q).max():.4f} m)")
    zz = np.linspace(0, 22, 2000); col = np.c_[np.full(2000, 5.0), np.zeros(2000), zz]; zn = HA.verschoben(col, A)[:, 2]
    pruef(np.all(np.diff(zn) > 0), "A: Abbildung streng monoton in z (keine Faltung)")
    # Hoehensitz vorher / nachher (Modell-STL mit der Abbildung)
    T = HS.np.asarray(modell.vertices, float); m2 = modell.copy(); m2.vertices = HA.verschoben(T, A); stl_n = os.path.join(R0, "modelle", "stl", "probe_nach.stl"); stl(m2, stl_n)
    hs = {}
    for nm, sp_ in (("vor", stl_m), ("nach", stl_n)):
        jp = os.path.join(R0, f"hs_{nm}.json")
        with contextlib.redirect_stdout(io.StringIO()): HS.main([OJ, "--fotosatz", sp, "--json", jp, "--stl", sp_, "--n-modell", "1500000", "--n-wolke", "1500000"])
        hs[nm] = {ax: e["hoehensitz"] for ax, e in json.load(open(jp))["seiten"].items()}
    pruef(all((hs["nach"][ax] or 0) >= (hs["vor"][ax] or 0) + 0.1 for ax in hs["vor"]), f"A: Hoehensitz steigt je Seite (vor {hs['vor']}, nach {hs['nach']})")
    # Basis-Rueckrechnung: dasselbe JSON, STL bereits korrigiert + Beleg -> misst gegen die unkorrigierte Basis, gleiche Korrekturen
    json.dump(json.load(open(os.path.join(OD, "elemente.json"))) + [dict(seite="+x", element=f"{HA.ELEMENT_BELEG}: Test", quelle="Test")], open(os.path.join(OD, "elemente.json"), "w"))
    os.replace(os.path.join(R0, "A.json"), os.path.join(R0, "A2.json")); import shutil; shutil.copy(os.path.join(R0, "A2.json"), os.path.join(R0, "A.json"))
    import time as _t; os.utime(os.path.join(R0, "A.json"), (_t.time() - 60, _t.time() - 60)); os.utime(stl_n, None)   # Bau nach dem JSON (Platte mit grober Zeitaufloesung)
    rc2, A2, txt2 = lauf("A", ["--kanten", kA, "--stl", stl_n])
    pruef("zurueckgerechnet" in A2.get("basis", "") and sorted({q["achse"] for q in A2["korrekturen"] if q.get("angenommen")}) == seiten_ang
          and all(abs(q2["dz"] - q["dz"]) < 0.1 for q, q2 in zip(sorted(ang, key=lambda q: q["achse"]), sorted([q for q in A2["korrekturen"] if q.get("angenommen")], key=lambda q: q["achse"]))),
          f"A: korrigiertes STL -> Basis zurueckgerechnet, gleiche Korrekturen (kein Aufschaukeln) ({A2.get('basis')})")
    if "zurueckgerechnet" not in A2.get("basis", ""): print(txt2[:1500])

    # --- B: Kanten an der Modell-Hoehe -> Guard
    rc, B, txt = lauf("B", ["--kanten", kB])
    pruef(rc == 2 and not any(q.get("angenommen") for q in B.get("korrekturen", [])), f"B: Kanten stuetzen das Modell -> keine Korrektur (rc {rc})")
    gr = [e["grund"] for s in B.get("seiten", {}).values() for e in s["zuege"] if 13.4 <= e["z"] <= 14.2]
    pruef(gr and all(("kanten" in g.lower()) or ("uneinig" in g) for g in gr), f"B: Grund je Linie nennt die Fotokanten ({gr[:2]})")

    # --- C: ohne Kantendatei
    rc, C, txt = lauf("C", ["--kanten", os.path.join(R0, "fehlt.npz")])
    pruef(rc == 3 and not any(q.get("angenommen") for q in C.get("korrekturen", [])), f"C: keine Kantenpunkte -> rc 3, nichts angenommen (rc {rc})")

    # --- F: Faltungs-Guard
    korr = [dict(achse="+x", z=13.6, dz=-0.6, t0=-4, t1=4, stuetze=0.8, angenommen=True)]
    pruef(HA.faltung_pruefen(korr, [dict(achse="+x", z=13.4, t0=-4, t1=4)], "+x") == [0], "F: unbelegte Nachbarlinie 0,2 m darunter -> Korrektur verworfen")
    pruef(HA.faltung_pruefen(korr, [dict(achse="+x", z=11.0, t0=-4, t1=4)], "+x") == [], "F: Nachbarlinie 2,6 m entfernt -> Korrektur bleibt")
    pruef(HA.faltung_pruefen(korr, [dict(achse="+x", z=13.4, t0=10, t1=14)], "+x") == [], "F: Nachbarlinie in anderem t-Bereich begrenzt nicht")

    # --- G: Generator-Baustein
    import bauteile as BT
    from manifold3d import Manifold as M
    k0 = M.cube((10.0, 8.0, 20.0)).translate((-5.0, -4.0, 0.0)) + M.cube((10.8, 8.8, 0.4)).translate((-5.4, -4.4, 13.6))
    jp = os.path.join(R0, "A2.json"); k1, bel = BT.hoehen_aus_json(k0, jp)
    zmax_gesims = lambda k: float(k.trim_by_plane((1.0, 0.0, 0.0), 5.2).bounding_box()[5]) if not k.trim_by_plane((1.0, 0.0, 0.0), 5.2).is_empty() else None
    pruef(bel and all(HA.ELEMENT_BELEG in b["element"] for b in bel) and abs(k1.volume() - k0.volume()) / k0.volume() < 0.05,
          f"G: hoehen_aus_json -> Belege '{HA.ELEMENT_BELEG}' ({len(bel)}), Volumen erhalten ({k0.volume():.1f} -> {k1.volume():.1f})")
    zg0, zg1 = zmax_gesims(k0), zmax_gesims(k1)
    pruef(zg0 is not None and zg1 is not None and -0.75 <= zg1 - zg0 <= -0.45, f"G: Gesims-Oberkante im Koerper verschoben ({zg0} -> {zg1})")
    jn = os.path.join(R0, "B.json"); k2, bel2 = BT.hoehen_aus_json(k0, jn)
    pruef(not bel2 and abs(k2.volume() - k0.volume()) < 1e-9, "G: ohne angenommene Korrektur unveraendert")
    print(f"test_hoehen_angleich: {F} Fehler"); return 1 if F else 0


if __name__ == "__main__":
    sys.exit(main())
