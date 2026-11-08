#!/usr/bin/env python3
"""bauteil_element_wolke.py - Elemente, die die AUTOMATISCHE Elementschleife (generator_elemente_schleife.py) aus dem Restfeld der Wolke ableitet.

Nichts Objektspezifisches: Die Elemente stehen als Daten in objekt.json['bauteile'] ({"typ": "element_wolke", "elemente": [...]}); jede Familie ist eine
Funktion mit freien Parametern in Metern im Modellrahmen (Weltachsen x,y,z wie rumpf_wolke).
Lokaler Rahmen eines Elements: Ursprung (cx, cy) auf der Wandflaeche, n = (cos phi, sin phi) Aussennormale, t = (-sin phi, cos phi) entlang der Wand.
Familien (Parameter -> Koerper):
  block      [cx,cy,phi,w,tiefe,z0,z1]        Quader, s in [-EINBINDUNG, tiefe]                       (additiv)
  giebel     [cx,cy,phi,w,tiefe,z0,z1,gh]     Quader + Giebeldach (First senkrecht zur Wand, Hoehe gh)  (additiv)
  keil       [cx,cy,phi,w,tiefe,z0,z1,kh]     Quader mit Pultdach (Oberkante faellt zur Front um kh)    (additiv)
  zylinder   [cx,cy,r,z0,z1]                  Rundkoerper (Turm/Erker rund), Achse senkrecht            (additiv)
  nische     [cx,cy,phi,w,tiefe,z0,z1]        Quader-Ausschnitt, s in [-tiefe, +AUSTRITT]               (Ausschnitt)
  rundnische [cx,cy,r,z0,z1]                  Zylinder-Ausschnitt                                       (Ausschnitt)
  bogenreihe [cx,cy,phi,tiefe,z_unten,z_oben,stich] + laeufe [[start,breite],..] (t relativ cx): Reihe gleicher Segmentbogen-Oeffnungen
             ueber bauteile.segmentbogen_reihe (Ausschnitt)
ANNAHME: EINBINDUNG 0,3 m (Koerper ragt so weit in die Wand, damit er wasserdicht anschliesst), AUSTRITT 0,3 m (Ausschnitt reicht so weit nach aussen).
"""
import math
import numpy as np

EINBINDUNG = 0.3
AUSTRITT = 0.3
FAMILIEN = {
    "block": ["cx", "cy", "phi", "w", "tiefe", "z0", "z1"],
    "giebel": ["cx", "cy", "phi", "w", "tiefe", "z0", "z1", "gh"],
    "keil": ["cx", "cy", "phi", "w", "tiefe", "z0", "z1", "kh"],
    "zylinder": ["cx", "cy", "r", "z0", "z1"],
    "nische": ["cx", "cy", "phi", "w", "tiefe", "z0", "z1"],
    "rundnische": ["cx", "cy", "r", "z0", "z1"],
    "bogenreihe": ["cx", "cy", "phi", "tiefe", "z_unten", "z_oben", "stich"],
}
SCHNITT = {"nische", "rundnische", "bogenreihe"}


def _lokal(M, k, cx, cy, phi):
    """Koerper im lokalen Rahmen (x = t, y = s, z) -> Welt."""
    return k.rotate((0, 0, math.degrees(phi) - 90.0)).translate((cx, cy, 0.0))      # lokal +y (s) soll auf n = (cos phi, sin phi) zeigen: Drehung phi - 90 Grad


def _hull(M, pts): return M.hull_points([tuple(map(float, p)) for p in pts])


def koerper(fam, p, M, C, laeufe=None):
    """-> (manifold, ist_schnitt). p: dict der Parameter (Namen aus FAMILIEN)."""
    if fam in ("zylinder", "rundnische"):
        h = max(0.05, p["z1"] - p["z0"]); k = M.cylinder(h, max(0.05, p["r"]), max(0.05, p["r"]), 40).translate((p["cx"], p["cy"], p["z0"]))
        return k, fam in SCHNITT
    cx, cy, phi = p["cx"], p["cy"], p["phi"]
    if fam in ("block", "giebel", "keil"):
        w, T = max(0.1, p["w"]) / 2, max(0.1, p["tiefe"]); s0, s1 = -EINBINDUNG, T; z0, z1 = p["z0"], max(p["z0"] + 0.1, p["z1"])
        ecken = [(x, y, z0) for x in (-w, w) for y in (s0, s1)]
        if fam == "block": ecken += [(x, y, z1) for x in (-w, w) for y in (s0, s1)]
        elif fam == "giebel":
            ecken += [(x, y, z1) for x in (-w, w) for y in (s0, s1)] + [(0.0, y, z1 + max(0.05, p["gh"])) for y in (s0, s1)]
        else:
            kh = min(max(0.0, p["kh"]), z1 - z0 - 0.05)
            ecken += [(x, s0, z1) for x in (-w, w)] + [(x, s1, z1 - kh) for x in (-w, w)]
        return _lokal(M, _hull(M, ecken), cx, cy, phi), False
    if fam == "nische":
        w, T = max(0.1, p["w"]), max(0.05, p["tiefe"]); k = M.cube((w, T + AUSTRITT, max(0.1, p["z1"] - p["z0"]))).translate((-w / 2, -T, p["z0"]))
        return _lokal(M, k, cx, cy, phi), True
    if fam == "bogenreihe":
        import bauteile as B
        T = max(0.05, p["tiefe"]); zo, zu = p["z_oben"], p["z_unten"]; teile = []
        for o in B.segmentbogen_reihe(laeufe, len(laeufe), zo, max(0.2, zo - zu), min(0.5, max(0.02, p["stich"]))):
            uc, R, zt, zk = o["uc"], o["R"], o["zt"], o["zk"]; th0 = math.asin(min(1.0, (o["u1"] - o["u0"]) / 2 / R))
            arc = [(uc + R * math.sin(a), zt - R + R * math.cos(a)) for a in np.linspace(th0, -th0, 13)]
            poly = [(o["u0"], zu), (o["u1"], zu)] + arc                                    # (t, z); Bogen von rechts ueber Scheitel nach links
            pr = M.extrude(C([[list(q) for q in poly]]), T + AUSTRITT).rotate((90.0, 0, 0)).translate((0, AUSTRITT, 0))   # extrudiert entlang s: nach Drehung s in [-T, +AUSTRITT]
            teile.append(pr)
        from manifold3d import OpType
        return _lokal(M, M.batch_boolean(teile, OpType.Add), cx, cy, phi), True
    raise ValueError(f"unbekannte Familie {fam}")


def _seite(phi):
    c, s = math.cos(phi), math.sin(phi)
    return ("+x" if c > 0 else "-x") if abs(c) >= abs(s) else ("+y" if s > 0 else "-y")


def bauteil(cfg, ctx, H):
    """Generator-Eintrag: H = dict(M, C, ROOT, OD, beleg). Rueckgabe (adds, cuts)."""
    M, C, beleg = H["M"], H["C"], H["beleg"]; adds, cuts = [], []
    for el in cfg.get("elemente", []):
        if el.get("aktiv", True) is False: continue
        k, schnitt = koerper(el["familie"], el["p"], M, C, el.get("laeufe"))
        (cuts if schnitt else adds).append(k)
        seite = _seite(el["p"]["phi"]) if "phi" in el["p"] else "alle"
        beleg(seite, f"Element {el['id']} ({el['familie']}, {'Ausschnitt' if schnitt else 'Anbau'})",
              f"Wolke: Restfeld-Cluster {el.get('cluster', '?')} (Runde {el.get('runde', '?')}); Parameter eingepasst an die Wolke; Tor: {el.get('tor_kurz', 'siehe protokoll.jsonl')}; "
              f"ANNAHME Einbindung {EINBINDUNG} m / Austritt {AUSTRITT} m", **{k_: float(v) for k_, v in el["p"].items()})
    return adds, cuts
