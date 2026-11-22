#!/usr/bin/env python3
"""test_sohlbank.py - fester synthetischer Test fuer tools/sohlbank_aus_fotos.py + bauteile.sohlbank (21.11.2026 spaet), < 20 s, nur CPU.

Wand u = x, aussen -y (w = -y), Fotos von unten (Kamerahoehe 1,5 m). Zwei GESCHWISTER-Fenster in Nischen; unter jeder Nische eine Sohlbank
(Unterkante 10,00 m, Oberkante 10,08 m, Auskragung 0,08 m, Enden je 0,05 m ausserhalb der Nische). Einzelfoto-Orthos aus der Strahlgeometrie
(Strahl Kamera -> Wandzelle trifft vorher die Sohlbank = dunkel), Unschaerfe 1,5 Pixel, JE FOTO eine zufaellige Verschiebung bis +-3 cm (Registrierfehler wie im
echten Bestand), in zwei Fotos ein dunkler Mast ueber dem rechten Ende (verdeckt). Ein drittes Fenster OHNE Sohlbank (glatte Wand) darf keine bekommen.
Erwartung: Auskragung 0,08 +-0,03 (>= 3 Fotos), Enden +-0,04, Unterkante +-0,04; Fenster C ohne 'sohlbank'.
Bauteil: bauteile.sohlbank an einem Wandquader, dessen Flaeche 0,15 m HINTER der Fassadenebene liegt -> Leiste haengt am Koerper (ein Stueck), Volumen wie erwartet;
ohne Wand darunter wird nichts gebaut; Auskragung unter Druckmindestmass -> ANNAHME-Vermerk.
"""
import sys, os, json, tempfile, shutil, subprocess, numpy as np
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
from pfade import temp_ordner                                         # 22.11.2026: Temp nicht auf Root, beim Ende aufgeraeumt (auch nach assert)
U0, U1, Z0, Z1, C = -4.0, 4.0, 9.3, 12.0, 0.01
SB = [dict(u0=-3.05, u1=-0.95, z0=10.0, z1=10.08, d=0.08), dict(u0=0.95, u1=3.05, z0=10.0, z1=10.08, d=0.08)]
FE = [dict(u0=-2.3, u1=-1.7, z0=10.12, z1=11.6, nische=dict(u0=-3.0, u1=-1.0, z0=10.08, z1=11.9, tiefe=0.07)),
      dict(u0=1.7, u1=2.3, z0=10.12, z1=11.6, nische=dict(u0=1.0, u1=3.0, z0=10.08, z1=11.9, tiefe=0.07)),
      dict(u0=-0.25, u1=0.25, z0=9.9, z1=10.6)]                      # C: kein Band darunter
KAM = [(-10.0, 30.0), (-6.0, 22.0), (-3.0, 14.0), (0.0, 9.0), (2.0, 11.0), (5.0, 18.0), (9.0, 26.0), (1.0, 7.5), (-1.0, 40.0), (4.0, 8.0)]


def ortho(Cu, Cw, n_):
    from scipy import ndimage as ndi
    rng = np.random.default_rng(n_); H_, W_ = int((Z1 - Z0) / C), int((U1 - U0) / C)
    du, dz = rng.uniform(-0.03, 0.03, 2)                                   # Registrierfehler dieses Fotos
    uu = U0 + C * (np.arange(W_) + 0.5) + du; zz = Z1 - C * (np.arange(H_) + 0.5) + dz; UU, ZZ = np.meshgrid(uu, zz)
    g = np.full((H_, W_), 205.0)
    for f in FE[:2]:
        N = f["nische"]; g[(UU >= N["u0"]) & (UU <= N["u1"]) & (ZZ >= N["z0"]) & (ZZ <= N["z1"])] = 225.0
        g[(UU >= f["u0"]) & (UU <= f["u1"]) & (ZZ >= f["z0"]) & (ZZ <= f["z1"])] = 70.0
    g[(UU >= FE[2]["u0"]) & (UU <= FE[2]["u1"]) & (ZZ >= FE[2]["z0"]) & (ZZ <= FE[2]["z1"])] = 70.0
    for s in SB:                                                           # Strahl Kamera (Cu, Cw, 1,5) -> Wandzelle (u, 0, z): Punkt bei Tiefe w
        for w in np.linspace(0.0, s["d"], 17):
            f_ = (Cw - w) / Cw; uw = Cu + (UU - Cu) * f_; zw = 1.5 + (ZZ - 1.5) * f_
            g[(uw >= s["u0"]) & (uw <= s["u1"]) & (zw >= s["z0"]) & (zw <= s["z1"])] = 55.0
    if n_ in (2, 5): g[(UU >= 3.0) & (UU <= 3.4)] = 40.0                     # Mast vor dem rechten Ende
    g = ndi.gaussian_filter(g, 1.5) + rng.normal(0, 2, g.shape)
    return np.clip(g, 1, 255).astype(np.uint8)


def pruef_bau(pruef):
    import bauteile as BT
    W = BT.Wand([0, 0], [1, 0], aussen=[0, -5])                            # u = x, w = -y (wie die Fassade im JSON: o = 0, d = x)
    wand = W.kasten(-4, 4, 0, 12, -1.0, -0.15)                             # Flaeche 0,15 m hinter der Fassadenebene
    k, v = BT.sohlbank(wand, W, dict(u0=0.95, u1=3.05, z0=10.0, z1=10.08, auskragung=0.08), druck_min=0.0696)
    soll = 2.1 * 0.08 * 0.08                                               # sichtbarer Zuwachs: nur der Teil vor der Flaeche (eingebundener Teil liegt im Koerper)
    dv = k.volume() - wand.volume()
    pruef(abs(dv - soll) < 0.02 * soll + 1e-4 and len(k.decompose()) == 1, f"Bau: Zuwachs {dv:.5f} m3 (soll {soll:.5f}), Stuecke {len(k.decompose())}, Vermerke {v}")
    k2, v2 = BT.sohlbank(W.kasten(-4, 4, 0, 5, -1.0, -0.15), W, dict(u0=0.95, u1=3.05, z0=10.0, z1=10.08, auskragung=0.08), druck_min=0.0696)
    pruef(abs(k2.volume() - W.kasten(-4, 4, 0, 5, -1.0, -0.15).volume()) < 1e-6 and v2 and "nicht gebaut" in v2[0], f"ohne Wand darunter nichts gebaut: {v2}")
    k3, v3 = BT.sohlbank(wand, W, dict(u0=0.95, u1=3.05, z0=10.0, z1=10.08, auskragung=0.03), druck_min=0.0696)
    pruef(any("Druckmindestmass" in x for x in v3) and abs((k3.volume() - wand.volume()) - 2.1 * 0.08 * 0.0696) < 1e-3, f"Auskragung 0,03 -> Druckmass: {v3}")
    # fenster_aus_json baut die Sohlbank mit
    d = temp_ordner("test_sb_bau_"); fa = os.path.join(d, "fenster_auto.json")
    fe = [dict(u0=1.7, u1=2.3, z0=10.12, z1=11.6, stimmen_min=3, tiefe=0.12, nische=dict(u0=1.0, u1=3.0, z0=10.08, z1=11.9, tiefe=0.07),
               sohlbank=dict(u0=0.95, u1=3.05, z0=10.0, z1=10.08, auskragung=0.08, quelle="test"))]
    json.dump(dict(f00=dict(o=[0, 0], d=[1, 0], n=[0, -1], fenster=fe)), open(fa, "w"))
    wand0 = W.kasten(-4, 4, 0, 12, -1.0, 0.0); k4, b4 = BT.fenster_aus_json(wand0, fa)
    fe[0].pop("sohlbank"); json.dump(dict(f00=dict(o=[0, 0], d=[1, 0], n=[0, -1], fenster=fe)), open(fa, "w")); k5, _ = BT.fenster_aus_json(wand0, fa)
    pruef(abs((k4.volume() - k5.volume()) - 2.1 * 0.08 * 0.08) < 2e-3 and any("Sohlbank" in b["element"] for b in b4), f"fenster_aus_json: Sohlbank-Zuwachs {k4.volume() - k5.volume():.4f} m3, Beleg {[b['element'] for b in b4]}")
    shutil.rmtree(d, ignore_errors=True)


def main():
    import cv2
    d = temp_ordner("test_sb_"); ff = os.path.join(d, "fassade_fein"); ez = os.path.join(ff, "ortho_f00_einzeln"); mp = os.path.join(d, "messprotokoll"); au = os.path.join(d, "audit")
    for x in (ez, mp, au): os.makedirs(x)
    for n_, (Cu, Cw) in enumerate(KAM):
        cv2.imwrite(os.path.join(ez, f"k{n_}.png"), ortho(Cu, Cw, n_))
        json.dump(dict(kamera=dict(rvec=[0, 0, 0], t=[-Cu, Cw, -1.5], f_px=1000, cx=0, cy=0)), open(os.path.join(mp, f"K-k{n_}.json"), "w"))   # R = I: Zentrum = -t = (Cu, -Cw, 1,5)
    json.dump(dict(fassaden=[dict(id="f00", o=[0, 0], d=[1, 0], n=[0, -1], raster=dict(u0=U0, z1=Z1, zelle=C))]), open(os.path.join(ff, "fassaden.json"), "w"))
    ob = os.path.join(d, "objekt.json"); json.dump({}, open(ob, "w"))
    fa = os.path.join(au, "fenster_auto.json"); json.dump(dict(f00=dict(o=[0, 0], d=[1, 0], n=[0, -1], fenster=FE)), open(fa, "w"))
    r = subprocess.run([sys.executable, "-W", "ignore", "-I", os.path.join(H, "sohlbank_aus_fotos.py"), fa, ff, ob], capture_output=True, text=True)
    F = 0
    def pruef(ok, t):
        nonlocal F; print(("  ok     " if ok else "  FEHLER ") + t); F += not ok
    pruef(r.returncode == 0, f"rc {r.returncode} {r.stdout.strip()[-400:]} {r.stderr[-300:]}")
    J = json.load(open(fa))["f00"]["fenster"]
    for q, s in zip(J[:2], SB):
        S = q.get("sohlbank") or {}
        pruef(abs(S.get("auskragung", -9) - s["d"]) <= 0.03 and S.get("fotos", 0) >= 3, f"Fenster u {q['u0']}: Auskragung {S.get('auskragung')} +-{S.get('auskragung_streuung')} (soll {s['d']}), {S.get('fotos')} Fotos, aus {S.get('auskragung_aus')}")
        pruef(abs(S.get("u0", -9) - s["u0"]) <= 0.04 and abs(S.get("u1", -9) - s["u1"]) <= 0.04, f"  Enden {S.get('u0')}..{S.get('u1')} (soll {s['u0']}..{s['u1']})")
        pruef(abs(S.get("z0", -9) - s["z0"]) <= 0.04 and S.get("z1", -9) >= S.get("z0", 9), f"  Hoehe {S.get('z0')}..{S.get('z1')} (soll {s['z0']}..{s['z1']})")
    pruef("sohlbank" not in J[2], "C (kein Band) ohne Sohlbank")
    if F and os.environ.get("TEST_DEBUG"):
        for e in json.load(open(os.path.join(au, "sohlbank_aus_fotos.json")))["f00"][:2]:
            print({k: v for k, v in e.items() if k != "punkte"})
            for p in e.get("punkte", []): print("   ", {k: p.get(k) for k in ("foto", "z_oben", "z_unten", "kappa", "H", "u_links", "u_rechts", "Ku", "laenge")})
    shutil.rmtree(d, ignore_errors=True)
    pruef_bau(pruef)
    print(f"test_sohlbank: {F} Fehler"); return 1 if F else 0


if __name__ == "__main__": sys.exit(main())
