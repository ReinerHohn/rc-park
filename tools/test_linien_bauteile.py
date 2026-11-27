#!/usr/bin/env python3
"""test_linien_bauteile.py - fester synthetischer Test fuer tools/linien_bauteile.py + bauteile.linien_aus_json (24.11.2026), < 30 s, nur CPU.
Verwandt: tools/test_sohlbank.py (gleiche Bauweise des Bautests).

Szene: Wand f00 (o = 0, d = x, n = -y, Ebene w = 0, u 0..12, z 0..20), triangulierte Kantenpunkte wie ein Ebenen-Sweep (Rauschen w 2 cm, z 1 cm, 10 Fotos):
  - senkrechte Fugenkanten ueberall (duerfen keine Linie ergeben),
  - FARBKANTE z 5,00 ueber die ganze Wand, flach (w 0)                       -> KEIN Bauteil (linienhaft nie per Farbe),
  - GESIMS: Wandanschluss z 10,00 (w 0) + Vorderkante z 10,40 (w 0,20), ganze Breite -> gesims z 10,0..10,4(+Abdeckung), Ausladung 0,20 +-0,03,
  - VERDACHUNG ueber einem Fenster (fenster_auto u 4..6, z 5,6..6,6): Anschluss z 7,00 (w 0) + Vorderkante 7,10 (w 0,12), u 3,5..6,5 -> typ verdachung,
  - BALKENKOEPFE: 3 kompakte Haufen u 2 / 6 / 10, z 12,4..12,8, w 0,30 -> Reihe n 3, Teilung 4,0, Ausladung 0,30 +-0,04,
  - UHR (uhren_auto u 6, z 16, d 2): vorstehender Ring w 0,2 -> darf weder Band noch Balkenkopf werden,
  - Kante z 14,0 (w 0,2) nur aus 2 Fotos -> nicht gebaut (Form aus >= 3 Fotos).
ROTE PROBEN (muessen scheitern bzw. anschlagen): (a) Gesims ohne Ausladung (alle w 0) -> kein Gesims; (b) ohne uhren_auto.json wird der Uhrring als Haufen sichtbar
  (Ausschluss wirkt); (c) Bau ohne Wand an der Stelle -> nichts gebaut; (d) Profil unter Druckmindestmass -> angehoben + Vermerk.
Bauteil: bauteile.linien_aus_json an einem Wandquader (Flaeche bei w 0): Zuwachs = Profilflaeche vor der Wand x Laenge, ein Stueck.
"""
import sys, os, json, subprocess, numpy as np
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
from pfade import temp_ordner
F = 0


def pruef(ok, t):
    global F; print(("  ok     " if ok else "  FEHLER ") + t); F += not ok


def szene(rng, gesims_w=0.20, uhr=True):
    P = []; R = []
    def linie(u0, u1, z, w, n, fotos=10):
        u = rng.uniform(u0, u1, n); P.append(np.c_[u, -(w + rng.normal(0, 0.02, n)), z + rng.normal(0, 0.01, n)]); R.append(rng.integers(0, fotos, n))
    for u_ in np.arange(0.4, 12, 0.9):                                   # senkrechte Fugen
        z = rng.uniform(0, 20, 300); P.append(np.c_[u_ + rng.normal(0, 0.01, 300), rng.normal(0, 0.02, 300), z]); R.append(rng.integers(0, 10, 300))
    linie(0, 12, 5.0, 0.0, 1500)                                          # Farbkante
    linie(0, 12, 10.0, 0.0, 1500); linie(0, 12, 10.4, gesims_w, 1500)     # Gesims
    linie(3.5, 6.5, 7.0, 0.0, 600); linie(3.5, 6.5, 7.1, 0.12, 600)       # Verdachung
    for uc in (2.0, 6.0, 10.0):                                           # Balkenkoepfe (Umriss)
        for z_ in (12.4, 12.8): linie(uc - 0.2, uc + 0.2, z_, 0.30, 80)
        for u_ in (uc - 0.2, uc + 0.2):
            z = rng.uniform(12.4, 12.8, 80); P.append(np.c_[u_ + rng.normal(0, 0.01, 80), -(0.30 + rng.normal(0, 0.02, 80)), z]); R.append(rng.integers(0, 10, 80))
    t = rng.uniform(0, 2 * np.pi, 800); P.append(np.c_[6 + np.cos(t), -(0.2 + rng.normal(0, 0.02, 800)), 16 + np.sin(t)]); R.append(rng.integers(0, 10, 800))   # Uhrring
    linie(1, 4, 14.0, 0.2, 400, fotos=2)                                  # nur 2 Fotos
    return np.vstack(P).astype(np.float32), np.concatenate(R)


def anlegen(d, P, R, uhr=True):
    os.makedirs(os.path.join(d, "obj", "audit"), exist_ok=True); os.makedirs(os.path.join(d, "eb", "f00_wand"), exist_ok=True); os.makedirs(os.path.join(d, "fa"), exist_ok=True)
    sw = os.path.join(d, "eb", "f00_wand", "sweep.npz"); np.savez(sw, P=P, s=np.ones(len(P), np.float32), ref=R, fotos=np.array([f"k{i}.jpg" for i in range(10)]))
    F_ = dict(id="f00", o=[0.0, 0.0], d=[1.0, 0.0], n=[0.0, -1.0], u=[0, 12], z=[0, 20])
    json.dump(dict(ebenen=[dict(id="f00_wand", art="wand", fassade="f00", o=F_["o"], d=F_["d"], n=F_["n"], w=0.0, zone=[0.0, 12.0, 0.0, 20.0], sweep=sw)]),
              open(os.path.join(d, "eb", "ebenen.json"), "w"))
    json.dump(dict(fassaden=[F_]), open(os.path.join(d, "fa", "fassaden.json"), "w"))
    json.dump({}, open(os.path.join(d, "obj", "objekt.json"), "w"))
    json.dump(dict(f00=dict(o=F_["o"], d=F_["d"], n=F_["n"], fenster=[dict(u0=4.0, u1=6.0, z0=5.6, z1=6.6)])), open(os.path.join(d, "obj", "audit", "fenster_auto.json"), "w"))
    if uhr: json.dump(dict(f00=dict(o=F_["o"], d=F_["d"], n=F_["n"], uhren=[dict(u=6.0, z=16.0, d_aussen=2.0)])), open(os.path.join(d, "obj", "audit", "uhren_auto.json"), "w"))


def laufen(d):
    aus = os.path.join(d, "linien.json")
    r = subprocess.run([sys.executable, "-W", "ignore", "-I", os.path.join(H, "linien_bauteile.py"), os.path.join(d, "obj", "objekt.json"), os.path.join(d, "eb"), os.path.join(d, "fa"),
                        "--aus", aus, "--ohne_kappa"], capture_output=True, text=True)
    return r, (json.load(open(aus))["fassaden"]["f00"] if os.path.exists(aus) else {})


def main():
    rng = np.random.default_rng(7); d = temp_ordner("test_linien_")
    P, R = szene(rng); anlegen(d, P, R); r, W = laufen(d)
    pruef(r.returncode == 0, f"rc {r.returncode} {r.stdout.strip()[-300:]} {r.stderr[-300:]}")
    B = W.get("bauteile", []); G = [b for b in B if b["typ"] == "gesims"]; V = [b for b in B if b["typ"] == "verdachung"]
    pruef(len(G) == 1 and abs(G[0]["z0"] - 10.0) <= 0.05 and 10.35 <= G[0]["z1"] <= 10.55 and abs(G[0]["ausladung"] - 0.20) <= 0.03 and G[0]["u1"] - G[0]["u0"] >= 10,
          f"Gesims gemessen: {[(b['z0'], b['z1'], b['ausladung'], b['u0'], b['u1']) for b in G]} (soll z 10,0..10,4+, a 0,20, ganze Breite)")
    pruef(len(V) == 1 and abs(V[0]["z0"] - 7.0) <= 0.05 and abs(V[0]["ausladung"] - 0.12) <= 0.03 and 3.3 <= V[0]["u0"] <= 3.8 and 6.2 <= V[0]["u1"] <= 6.7,
          f"Verdachung ueber dem Fenster: {[(b['z0'], b['z1'], b['ausladung'], b['u0'], b['u1']) for b in V]} (soll z 7,0..7,1+, a 0,12, u 3,5..6,5)")
    pruef(not any(b["z0"] - 0.1 <= 5.0 <= b["z1"] + 0.1 for b in B), "Farbkante z 5,0 (flach) ist kein Bauteil")
    pruef(not any(b["z0"] - 0.1 <= 14.0 <= b["z1"] + 0.1 for b in B), "Kante aus nur 2 Fotos (z 14,0) nicht gebaut")
    K = W.get("balkenkoepfe", [])
    pruef(len(K) == 1 and K[0]["n"] == 3 and all(abs(t - 4.0) <= 0.25 for t in K[0]["teilung"]) and abs(K[0]["ausladung"] - 0.30) <= 0.04,
          f"Balkenkopf-Reihe: {[(k['n'], k['u'], k['teilung'], k['ausladung'], k['z0'], k['z1']) for k in K]} (soll 3 Stueck, Teilung 4,0, a 0,30)")
    pruef(not any(abs(0.5 * (k["z0"] + k["z1"]) - 16) < 1.5 for k in K) and not any(15 <= b["z0"] <= 17 for b in B), "Uhrring weder Band noch Balkenkopf")
    # ROTE PROBE (a): Gesims ohne Ausladung -> kein Gesims
    d2 = temp_ordner("test_linien_a_"); P2, R2 = szene(np.random.default_rng(7), gesims_w=0.0); anlegen(d2, P2, R2); _, W2 = laufen(d2)
    pruef(not any(b["typ"] == "gesims" for b in W2.get("bauteile", [])), f"ROT (a) flaches 'Gesims' wird nicht gebaut: {[b['typ'] for b in W2.get('bauteile', [])]}")
    # ROTE PROBE (b): ohne uhren_auto.json schlaegt der Uhrring an (der Ausschluss ist es, der ihn fernhaelt)
    d3 = temp_ordner("test_linien_b_"); anlegen(d3, P, R, uhr=False); _, W3 = laufen(d3)
    um = [k for k in W3.get("kanten", []) if 15 <= k["z"] <= 17 and k.get("zustand")] + [k for k in W3.get("balkenkoepfe", []) if 15 <= k["z0"] <= 17]
    pruef(len(um) > 0, f"ROT (b) ohne Uhr-Ausschluss erscheint der Ring als Kandidat ({len(um)})")
    # Bau
    import bauteile as BT
    Wd = BT.Wand([0, 0], [1, 0], aussen=[0, -5]); wand = Wd.kasten(0, 12, 0, 20, -1.0, 0.0)
    jd = os.path.join(d, "bau.json")
    json.dump(dict(fassaden=dict(f00=dict(o=[0, 0], d=[1, 0], n=[0, -1], bauteile=[dict(typ="gesims", u0=1.0, u1=11.0, z0=10.0, z1=10.5, ausladung=0.2, fotos=10, kanten=[dict(aus=None), dict(aus=None)],
              profil=[[10.0, 0.0], [10.4, 0.2], [10.5, 0.2]])], balkenkoepfe=[dict(n=2, u=[3.0, 7.0], b=0.4, z0=12.4, z1=12.8, ausladung=0.3)]))), open(jd, "w"))
    k, bel = BT.linien_aus_json(wand, jd)
    soll = 10.0 * (0.5 * 0.4 * 0.2 + 0.1 * 0.2) + 2 * 0.4 * 0.4 * 0.3            # Gesims: Dreieck (Unterseite) + Abdeckplatte; 2 Koepfe
    dv = k.volume() - wand.volume()
    pruef(abs(dv - soll) < 0.02 * soll and len(k.decompose()) == 1 and len(bel) == 2, f"Bau: Zuwachs {dv:.4f} m3 (soll {soll:.4f}), Stuecke {len(k.decompose())}, Belege {[b['element'] for b in bel]}")
    k2, b2 = BT.linien_aus_json(Wd.kasten(0, 12, 0, 5, -1.0, 0.0), jd)                # ROT (c): keine Wand an der Stelle
    pruef(abs(k2.volume() - Wd.kasten(0, 12, 0, 5, -1.0, 0.0).volume()) < 1e-6 and any("NICHT gebaut" in b["element"] for b in b2), f"ROT (c) ohne Wand nichts gebaut: {[b['element'] for b in b2]}")
    t_, ann = BT.linien_profil(Wd, 1.0, 2.0, [[10.0, 0.0], [10.02, 0.03]], 0.0, druck_min=0.0696)   # ROT (d)
    pruef(t_ is not None and any("Druckmindestmass" in x for x in ann) and len(ann) == 2, f"ROT (d) Profil unter Druckmindestmass angehoben: {ann}")
    print(f"test_linien_bauteile: {F} Fehler"); return 1 if F else 0


if __name__ == "__main__": sys.exit(main())
