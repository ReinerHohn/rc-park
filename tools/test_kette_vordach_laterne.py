#!/usr/bin/env python3
"""test_kette_vordach_laterne.py - KETTENFALL Vordach + Laterne mit den echten JSON-Staenden des Kettenlaufs 1122c (22.11.2026). Sekunden, < 300 MB.

Anlass: Nach Lauf 1122c hiess es am Nebeneinander-Bild audit/neben_eigen__IMG_20261106_113231.jpg "Vordach weiter flache Platte ohne Schweifung/Ueberstand,
Laterne nur winziger Stumpf", obwohl vordach_profil.py (geschweift 14/15, Ueberstand 0,35 / seitlich 0,45 m) und laterne_aus_fotos.py (4 Pfosten, Zwiebel,
"Nadel z None") rc 0 meldeten. Nachgemessen: das Ketten-STL 04:45 ENTHAELT beides (Schnitte und Render aus SfM-Kameras); das Bild ist ein Steilblick von
unten mit Licht von der Kamera (Schweifung und Pfosten nicht lesbar), IMG_113231 ist fuer die Laterne sogar Ausreisser-Foto. Dieser Test haelt den Weg
JSON -> Generator-Einstieg (bauteile.vorbauten_aus_json liest vordach_profil.json NEBEN vorbauten_auto.json; bauteile.dach_aus_profil liest laterne_foto)
-> Geometrie fest, in der Reihenfolge des Generators (Vorbau vor Dach; Dach traegt erst ab z0 ab), damit "Probe ok, Kette nicht" auffaellt.

Fixture tools/testdata/schwabentor_1122c_vordach_laterne.json = die drei echten Audit-JSONs, auf die gelesenen Felder gekuerzt.
A) Vordach: Traufe 0,35 m vor der Galeriefront, seitlich >= 0,3 m ueber den Kasten, Profil geschweift (Front bei 25 % der Hoehe deutlich hinter der Geraden);
   ROT-Probe: OHNE_VORDACH_PROFIL=1 (ebene Platte) muss an der Schweifung scheitern.
B) Laterne: Schnitt in Pfostenhoehe = 4 Pfosten um die Achse, Haube breiter als die Pfosten, Spitze bis spitze_foto.spitze_z (Nadel z None ist KEIN
   Ausschlussgrund), Dach unter z0 (Vordach) unberuehrt; ROT-Probe: laterne_foto ungueltig -> keine 4 Pfosten (Drehringe)."""
import sys, os, json, shutil, tempfile, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bauteile as BT
from manifold3d import Manifold as M

fehler = []
def pruef(ok, text):
    print(("    ok   " if ok else "FEHLER  ") + text)
    if not ok: fehler.append(text)

FX = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "testdata", "schwabentor_1122c_vordach_laterne.json")))
F = FX["vorbauten_auto"]["fassaden"][0]; KM = F["gruppen"][0]["kanten_mass"]; Kb = KM["kasten"]; VP = FX["vordach_profil"]["fassaden"][0]; D = FX["dach_profil"]
o, d, n = (np.array(F[k], float) for k in ("o", "d", "n")); ww = float(F["w_wand"]); wf = ww + float(KM["ausladung"])
P = lambda u, z, w: [o[0] + u * d[0] + w * n[0], o[1] + u * d[1] + w * n[1], z]
oD, dD, nD = (np.array(D[k], float) for k in ("o", "d", "n")); hd, hn = D["wand_halb"]


def turm():
    """Grundkoerper: Turm im Dach-Rahmen bis z0 + Wandscheibe der Fassade f00 hinter der gemessenen Wandebene (w <= w_wand)."""
    t = M.hull_points([[oD[0] + a * dD[0] + b * nD[0], oD[1] + a * dD[1] + b * nD[1], z] for a in (-hd, hd) for b in (-hn, hn) for z in (0.0, float(D["z0"]))])
    return t + M.hull_points([P(u, z, w) for u in (-6.0, 6.5) for w in (-3.0, ww) for z in (0.0, 30.0)])


def front(k, z, u0=-8.0, u1=9.0):
    """Schnitt bei z: groesste Ausladung w vor f00 und u-Bereich der Teile mit w > wf - 0,2 (Galeriefront)."""
    pts = np.vstack([np.asarray(p) for p in k.slice(z).to_polygons()] or [np.zeros((0, 2))])
    if not len(pts): return None, None
    rel = pts - o[:2]; u = rel @ d[:2]; w = rel @ n[:2]; s = (u > u0) & (u < u1) & (w > -1.0)
    v = s & (w > wf - 0.2)
    return float(w[s].max()) if s.any() else None, ((float(u[v].min()), float(u[v].max())) if v.any() else None)


def bauen(env=None, lf=None):
    """Generator-Reihenfolge (modelle/schwabentor-1120_gen.py): vorbauten_aus_json -> dach_aus_profil, Dateinamen wie im Objektordner audit/."""
    alt = {k: os.environ.get(k) for k in (env or {})}
    os.environ.update(env or {})
    try:
        with tempfile.TemporaryDirectory() as td:
            json.dump(FX["vorbauten_auto"], open(os.path.join(td, "vorbauten_auto.json"), "w"))
            json.dump(FX["vordach_profil"], open(os.path.join(td, "vordach_profil.json"), "w"))
            json.dump(dict(D, laterne_foto=lf if lf is not None else D["laterne_foto"]), open(os.path.join(td, "dach_profil.json"), "w"))
            k, bv = BT.vorbauten_aus_json(turm(), os.path.join(td, "vorbauten_auto.json"))
            k, bd = BT.dach_aus_profil(k, os.path.join(td, "dach_profil.json"))
    finally:
        for k_, v_ in alt.items():
            if v_ is None: os.environ.pop(k_, None)
            else: os.environ[k_] = v_
    return k, bv, bd


def vordach_pruefen(k, bv, soll_ok):
    zt, za, wt = float(VP["z_t"]), float(VP["z_a"]), float(VP["w_t"])
    w_tr, ub = front(k, zt - 0.05)                                    # in der Traufscheibe (dk unter z_t)
    ue_f = (w_tr or 0) - wf; ue_s = min(Kb["u0"] - ub[0], ub[1] - Kb["u1"]) if ub else -1
    zq = zt + 0.25 * (za - zt); w_q, _ = front(k, zq)                  # Front bei 25 % der Hoehe Traufe -> Anschluss
    w_lin = wt - 0.25 * (wt - ww)                                     # gerade Dachflaeche gleicher Traufe/Anschluss
    gesch = w_q is not None and w_q < w_lin - 0.2
    beleg = any("Vordach geschweift" in b.get("hinweis", "") for b in bv)
    ok = abs(ue_f - 0.35) < 0.08 and ue_s >= 0.3 and gesch and beleg
    pruef(ok == soll_ok, f"A Vordach{' (ROT-Probe ebene Platte)' if not soll_ok else ''}: Ueberstand vor der Galeriefront {ue_f:.2f} m (Soll 0,35), seitlich {ue_s:.2f} m (Soll >= 0,3), "
                         f"Front bei z {zq:.2f}: w {w_q if w_q is None else round(w_q, 2)} gegen Gerade {w_lin:.2f} -> geschweift {gesch}, Beleg {beleg} -> {'gebaut' if ok else 'NICHT gebaut'}")


def laterne_pruefen(k, bd, soll_ok):
    LF = D["laterne_foto"]; A = np.array(LF["achse"], float); Z = LF["zonen"]
    zp = 0.5 * (Z["z_pfosten_unten"] + Z["z_pfosten_oben"])
    tl = [t for t in k.slice(zp).decompose() if np.hypot(*(np.mean(np.asarray(t.to_polygons()[0]), 0) - A)) < 1.5]
    r_ = [float(np.hypot(*(np.mean(np.asarray(t.to_polygons()[0]), 0) - A))) for t in tl]
    def halb(z):
        q = np.vstack([np.asarray(p) for p in k.slice(z).to_polygons()]); q = q[np.hypot(*(q - A).T) < 3.0]
        return float(np.hypot(*(q - A).T).max()) if len(q) else 0.0
    rb = halb(Z["z_bauch"]); zt = k.bounding_box()[5]; sz = float(D["spitze_foto"]["spitze_z"])
    beleg = any("Laterne aus Fotokanten" in b["element"] for b in bd)
    ok = len(tl) == int(LF["pfosten"]["n"]) and all(abs(r - LF["pfosten"]["R"]) < 0.15 for r in r_) and rb > max(r_ or [9]) + 0.2 and abs(zt - sz) < 0.1 and beleg
    pruef(ok == soll_ok, f"B Laterne{' (ROT-Probe Block ungueltig)' if not soll_ok else ''}: Schnitt z {zp:.2f}: {len(tl)} Pfosten (Soll {LF['pfosten']['n']}) bei r {[round(r, 2) for r in r_]}, "
                         f"Haube z {Z['z_bauch']}: r {rb:.2f}, Spitze z {zt:.2f} (spitze_foto {sz}, nadel_z {LF.get('nadel_z')}), Beleg {beleg} -> {'gebaut' if ok else 'NICHT gebaut'}")


print("Kettenfall 1122c: " + FX["quelle"][:90])
pruef(D["laterne_foto"].get("nadel_z") is None and D["laterne_foto"].get("gueltig"), "Fixture: laterne_foto gueltig mit nadel_z None (wie im Lauf 1122c)")
pruef(float(D["z0"]) > float(VP["z_a"]) + 1.0, f"Reihenfolge: dach_aus_profil traegt erst ab z0 {float(D['z0']):.2f} ab, Vordach-Anschluss z {VP['z_a']} liegt darunter")
k, bv, bd = bauen()
vordach_pruefen(k, bv, True); laterne_pruefen(k, bd, True)
pruef(len(k.decompose()) == 1, f"ein Koerper (Vorbau + Dach + Laterne): {len(k.decompose())}")
k2, bv2, _ = bauen(env={"OHNE_VORDACH_PROFIL": "1"}); vordach_pruefen(k2, bv2, False)
k3, _, bd3 = bauen(lf=dict(D["laterne_foto"], gueltig=False)); laterne_pruefen(k3, bd3, False)
print(("FEHLER " if fehler else "OK ") + f"test_kette_vordach_laterne: {len(fehler)} Fehler"); sys.exit(1 if fehler else 0)
