#!/usr/bin/env python3
"""test_vordach_ohne_kasten.py - Vordach-Profil und Galerie-Pfosten auch OHNE Kanten-Kasten (24.11.2026). Sekunden, < 400 MB.
Verwandt: tools/test_kette_vordach_laterne.py (Kettenfall 1122c mit Kasten), tools/test_vordach_traufe.py, tools/test_vordach_vorbau.py, tools/test_vorbau_pfosten.py.
Vorlaeufer: tools/vordach_profil.py (Profil nur mit kanten_mass.kasten), bauteile.vorbauten_aus_json (Hoehenfeld-Zweig ohne Vordach-Profil).

Anlass (Nutzer 24.11.: "so wirklich gut ist es noch nicht, wir hatten schon mal einen viel besseren Stand" = Handstand schwab_v3, Vordach GENEIGT/geschweift):
Kette 1122w-zc: audit/vordach_profil.json 'fassaden: []' - vordach_profil.messen verlangte kanten_mass.kasten; bei duennen Vorbau-Kanten (ebenen_masse ohne zwei volle
Linien) wurde das Profil NIE gemessen, der Generator baute das Vordach als Hoehenfeld-Stufen bzw. ebene Platte. Galerie: nur 1 Kanten-Pfosten (Knagge), Sweep-Pfosten
an den Enden wurden nur genommen, wenn GAR KEIN Kanten-Pfosten da war.
A) kasten_oder_ersatz: Kanten-Kasten bevorzugt; ohne ihn Galerie-Band des Sweeps; degeneriert/ohne Vordach -> None.  ROT: alte Regel (nur kanten_mass.kasten) -> None.
B) Hoehenfeld-Zweig mit Vordach-Profil: Front bei 25 % Traufe->Anschluss deutlich hinter der Geraden (geschweift), oberhalb kein Hoehenfeld-Kasten.
   ROT: OHNE_VORDACH_PROFIL=1 -> Hoehenfeld-Stufe (w konstant) -> nicht geschweift.
C) Kasten-Zweig: 1 Kanten-Pfosten + Sweep-Pfosten an beiden Enden -> Pfosten an beiden Enden.  ROT: OHNE_SWEEP_PFOSTEN_ERGAENZEN=1 -> nur ein Ende."""
import sys, os, json, copy, tempfile, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bauteile as BT
import vordach_profil as VDP
from manifold3d import Manifold as M

fehler = []
def pruef(ok, text):
    print(("    ok   " if ok else "FEHLER  ") + text)
    if not ok: fehler.append(text)

FX = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "testdata", "schwabentor_1122c_vordach_laterne.json")))
F0 = FX["vorbauten_auto"]["fassaden"][0]; VP = FX["vordach_profil"]["fassaden"][0]
o, d, n = (np.array(F0[k], float) for k in ("o", "d", "n")); ww = float(F0["w_wand"])
P = lambda u, z, w: [o[0] + u * d[0] + w * n[0], o[1] + u * d[1] + w * n[1], z]


def wand():
    return M.hull_points([P(u, z, w) for u in (-6.0, 6.5) for w in (-3.0, ww) for z in (0.0, 30.0)])


def front(k, z, u0=-8.0, u1=9.0):
    pts = np.vstack([np.asarray(p) for p in k.slice(z).to_polygons()] or [np.zeros((0, 2))])
    if not len(pts): return None, np.zeros(0), np.zeros(0)
    rel = pts - o[:2]; u = rel @ d[:2]; w = rel @ n[:2]; s = (u > u0) & (u < u1) & (w > -1.0)
    return (float(w[s].max()) if s.any() else None), u[s], w[s]


def bauen(F, env=None, mit_profil=True):
    alt = {k: os.environ.get(k) for k in (env or {})}; os.environ.update(env or {})
    try:
        with tempfile.TemporaryDirectory() as td:
            json.dump(dict(fassaden=[F]), open(os.path.join(td, "vorbauten_auto.json"), "w"))
            if mit_profil: json.dump(FX["vordach_profil"], open(os.path.join(td, "vordach_profil.json"), "w"))
            return BT.vorbauten_aus_json(wand(), os.path.join(td, "vorbauten_auto.json"))
    finally:
        for k_, v_ in alt.items():
            if v_ is None: os.environ.pop(k_, None)
            else: os.environ[k_] = v_


g0 = F0["gruppen"][0]; GAL = dict(g0["galerie"], u0=-3.9, u1=4.58, pfosten=[-3.71, 4.45])

# --- A: Ersatz-Kasten ---
print("A) kasten_oder_ersatz")
mit = VDP.kasten_oder_ersatz(dict(g0, galerie=GAL)); pruef(mit and abs(mit["u0"] - g0["kanten_mass"]["kasten"]["u0"]) < 1e-9 and "Fotokanten" in mit["quelle"], f"mit Kanten-Kasten -> Kasten ({mit})")
ohne_g = dict(g0, galerie=GAL); ohne_g.pop("kanten_mass")
er = VDP.kasten_oder_ersatz(ohne_g); pruef(er is not None and er["u0"] == -3.9 and er["u1"] == 4.58 and "Ersatz" in er["quelle"], f"ohne Kasten -> Galerie-Band ({er})")
alt_regel = (ohne_g.get("kanten_mass") or {}).get("kasten"); pruef(alt_regel is None, "ROT-Probe: alte Regel (nur kanten_mass.kasten) haette kein Vordach gemessen")
pruef(VDP.kasten_oder_ersatz(dict(ohne_g, galerie=dict(GAL, vordach=None))) is None, "ohne Vordach im Galerie-Band -> None")
pruef(VDP.kasten_oder_ersatz(dict(ohne_g, galerie=dict(GAL, u0=1.0, u1=1.5))) is None, "degeneriertes Band (0,5 m) -> None")

# --- B: Hoehenfeld-Zweig ---
print("B) Hoehenfeld-Zweig mit Vordach-Profil")
z0, z1, r_ = 9.0, 20.6, 0.2; nz = int(round((z1 - z0) / r_)); nu = int(round((4.6 - -3.9) / r_))
Wg = [[(1.2 if (z1 - (i + 1) * r_) >= 15.4 or (z1 - (i + 1) * r_) < 12.5 else 0.3) for _ in range(nu)] for i in range(nz)]   # Vordach als Hoehenfeld-Kasten 1,2 m + Galerie
FH = dict(F0, gruppen=[dict(u0=-3.9, u1=-3.9 + nu * r_, z0=z0, z1=z1, raster=r_, w=Wg, koerper=g0["koerper"], galerie=GAL)])
zt, za, wt = float(VP["z_t"]), float(VP["z_a"]), float(VP["w_t"]); zq = zt + 0.25 * (za - zt); w_lin = wt - 0.25 * (wt - ww)
k_s, _ = bauen(FH); w_s, _, _ = front(k_s, zq)        # Merge 24.11.: Standardweg baut das Hoehenfeld nie mehr als Gestalt (bauteile.vorbau_kasten_ersatz) - auch dort geschweift
pruef(w_s is not None and w_s < w_lin - 0.2, f"Standardweg (Ersatz-Kasten, kein Hoehenfeld): Front bei z {zq:.2f}: w {w_s} geschweift")
HF = {"MIT_HOEHENFELD": "1"}                           # der Hoehenfeld-Zweig selbst lebt nur noch als Vergleich/rote Probe
k, bv = bauen(FH, env=HF); w_q, _, _ = front(k, zq); w_hi, _, _ = front(k, za - 0.3)
pruef(w_q is not None and w_q < w_lin - 0.2, f"Front bei z {zq:.2f}: w {w_q} < gerade {w_lin:.2f} - 0,2 (geschweift)")
pruef(w_hi is not None and w_hi < ww + 1.2 - 0.2, f"nahe Anschluss z {za - 0.3:.2f}: w {w_hi} - kein Hoehenfeld-Kasten (ww + 1,2) mehr")
pruef(any("Vordach" in b.get("element", "") and "geschweift" in b.get("element", "") for b in bv), "Beleg 'Vordach ... geschweift'")
k_r, _ = bauen(FH, env=dict(HF, OHNE_VORDACH_PROFIL="1")); w_r, _, _ = front(k_r, zq)
pruef(not (w_r is not None and w_r < w_lin - 0.2), f"ROT-Probe OHNE_VORDACH_PROFIL=1: w {w_r} (Hoehenfeld-Stufe, nicht geschweift)")

# --- C: Pfosten ergaenzen ---
print("C) Kasten-Zweig: Sweep-Pfosten ergaenzen")
gk = copy.deepcopy(g0); gk["galerie"] = GAL; gk["kanten_mass"]["pfosten"] = [dict(u=-3.17, breite=None, punkte=135, quelle="Knagge im Bruestungsfeld")]
FK = dict(F0, gruppen=[gk]); Kb = gk["kanten_mass"]["kasten"]; wf = ww + float(gk["kanten_mass"]["ausladung"]); zp = 0.5 * (Kb["z_oben"] + GAL["z_dach"])


def enden(k):
    _, u, w = front(k, zp); v = w > wf - 0.3
    return (bool((v & (u < Kb["u0"] + 1.0)).any()), bool((v & (u > Kb["u1"] - 1.0)).any()))


k, bv = bauen(FK, mit_profil=False); li, re = enden(k)
pruef(li and re, f"Pfosten an beiden Enden (links {li}, rechts {re}) in z {zp:.2f}")
k_r, _ = bauen(FK, env={"OHNE_SWEEP_PFOSTEN_ERGAENZEN": "1"}, mit_profil=False); li_r, re_r = enden(k_r)
pruef(not (li_r and re_r), f"ROT-Probe ohne Ergaenzung: links {li_r}, rechts {re_r} (nur ein Ende)")

print(("FEHLER: " + "; ".join(fehler)) if fehler else "alle Pruefungen bestanden")
sys.exit(1 if fehler else 0)
