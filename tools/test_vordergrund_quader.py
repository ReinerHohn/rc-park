#!/usr/bin/env python3
"""test_vordergrund_quader.py - synthetischer Test (21.11.2026, Schwabentor w01, Lauf 1121s) fuer
  (1) tools/relief_vordergrund.py: Verkehrsschild (0,6 x 0,8 m, +15 cm) DIREKT auf einem durchgehenden Sockelband (+20 cm) im Quaderwerk -> Schild auf Wandniveau;
      Sockelband, einzelner Bossenquader (+12 cm, 0,15 m2), Eckquaderung am Feldrand und das Quaderrelief bleiben. Dazu relief_mischen.py Ende-zu-Ende
      (OHNE_VORDERGRUND=1 = alter Stand: Schild bleibt -> der Test muss dort den Buckel sehen).
  (2) putz_wandbild.glatt_karte 'quader' + relief_putz.quader_veto: Wandbild mit hellem, wenig gesaettigtem Quaderwerk links und glattem Putz rechts
      (5 entzerrte Einzelbilder, eines mit einem 'Kabel' quer) -> Veto links, rechts kein Veto; ohne fassade_fein -> None (Farbe allein wie bisher).
Aufruf: /media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_vordergrund_quader.py   (Sekunden, keine GPU)
"""
import sys, os, json, tempfile, subprocess, numpy as np
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
FEHLER = []


def pruef(ok, text):
    print(("    ok " if ok else "    FEHLER ") + text)
    if not ok: FEHLER.append(text)


def quaderwand(H, W, px, rng, kurs=0.4, lang=0.6, bosse=0.03, fuge=-0.02):
    """Hoehenbild Quaderwerk: Steine +bosse (je Stein +-1 cm), Fugen 2 cm breit auf fuge."""
    zz = (H - 1 - np.arange(H))[:, None] * px; uu = np.arange(W)[None, :] * px
    lage = np.floor(zz / kurs); vers = (lage % 2) * lang / 2; stein = np.floor((uu + vers) / lang)
    r = bosse + 0.01 * np.sin(lage * 7.1 + stein * 3.3) + 0.004 * rng.standard_normal((H, W))
    fz = (zz % kurs) < 0.02; fu = ((uu + vers) % lang) < 0.02
    return np.where(fz | fu, fuge, r)


def test_vordergrund():
    from relief_vordergrund import vordergrund_weg
    rng = np.random.default_rng(3); px = 0.02; H, W = 320, 175                     # 3,5 m x 6,4 m wie w01_misch
    rel = quaderwand(H, W, px, rng); ok = np.ones((H, W), bool)
    def feld(u0, u1, z0, z1):
        m = np.zeros((H, W), bool); m[H - int(z1 / px):H - int(z0 / px), int(u0 / px):int(u1 / px)] = True; return m
    sockel = feld(0, 3.5, 1.0, 1.6); rel[sockel] = 0.20 + 0.01 * rng.standard_normal(sockel.sum())
    schild = feld(1.8, 2.4, 1.6, 2.4); rel[schild] = 0.15                         # sitzt direkt auf dem Sockelband
    bosse = feld(0.7, 1.1, 4.0, 4.35); rel[bosse] = 0.12                          # ein einzelner vorstehender Quader (0,14 m2)
    ecke = feld(3.25, 3.5, 2.0, 6.4); rel[ecke] = 0.12                            # Eckquaderung am Feldrand
    neu, m, info = vordergrund_weg(rel, ok, px)
    print("   ", info)
    pruef(m[schild].mean() >= 0.9, f"Schild als Vordergrund erkannt ({m[schild].mean() * 100:.0f} % >= 90 %)")
    pruef(np.percentile(neu[schild], 90) <= 0.06, f"Schild danach auf Wandniveau (p90 {np.percentile(neu[schild], 90) * 100:.1f} cm <= 6 cm, vorher 15)")
    pruef(m[sockel].mean() <= 0.03 and np.median(neu[sockel]) >= 0.19, f"Sockelband bleibt (maskiert {m[sockel].mean() * 100:.1f} %, Median {np.median(neu[sockel]) * 100:.0f} cm)")
    pruef(not m[bosse].any(), "einzelner Bossenquader (+12 cm, 0,14 m2) bleibt")
    pruef(not m[ecke].any(), "Eckquaderung am Feldrand bleibt")
    rest = ~(schild | sockel | bosse | ecke)
    pruef(m[rest].mean() <= 0.01, f"Quaderrelief sonst unberuehrt ({m[rest].mean() * 100:.2f} % maskiert)")
    # Ende-zu-Ende relief_mischen: fein = grob = diese Wand (fein mit Loechern), Ebene flach
    with tempfile.TemporaryDirectory() as td:
        a_ = np.array([0.0, 0.0]); t_ = np.array([1.0, 0.0]); n_ = np.array([0.0, -1.0])
        fe = rel.copy(); fe[rng.random((H, W)) < 0.3] = 0.0; fe[fe == 0] = 0.0
        np.savez(os.path.join(td, "f.npz"), rel=np.where(fe == 0, 0, fe + 1e-4).astype(np.float32), a=a_, t=t_, n=n_, u0=0.0, z0=0.0, px=px, ebene_abstand_m=0.0, trend_je_m=np.zeros(2))
        Hg, Wg = H // 2, W // 2; g = rel[:Hg * 2, :Wg * 2].reshape(Hg, 2, Wg, 2).mean((1, 3))
        np.savez(os.path.join(td, "g.npz"), rel=(g + 1e-4).astype(np.float32), a=a_, t=t_, n=n_, u0=0.0, z0=0.0, px=0.04, ebene_abstand_m=0.0, trend_je_m=np.zeros(2),
                 putz=np.zeros((Hg, Wg), bool), generiert=np.zeros((Hg, Wg), bool))
        erg = {}
        for name, env in (("neu", {}), ("alt", {"OHNE_VORDERGRUND": "1"})):
            r = subprocess.run([sys.executable, "-W", "ignore", "-I", os.path.join(HIER, "relief_mischen.py"), os.path.join(td, "f.npz"), os.path.join(td, "g.npz"), os.path.join(td, name + ".npz")],
                               capture_output=True, text=True, env={**os.environ, **env})
            if r.returncode: pruef(False, "relief_mischen lief nicht: " + (r.stderr or r.stdout)[-300:]); return
            erg[name] = np.load(os.path.join(td, name + ".npz"))
        def buckel(Z):                                                              # Schild gegen die Wand derselben Zeilen daneben
            rr = Z["rel"]; s = schild[:rr.shape[0], :rr.shape[1]]; ne = feld(0.6, 1.6, 1.7, 2.3)[:rr.shape[0], :rr.shape[1]]
            return float(np.percentile(rr[s], 90) - np.median(rr[ne]))
        pruef(buckel(erg["alt"]) >= 0.10, f"Gegenprobe alter Stand: Schild-Buckel im Mischrelief {buckel(erg['alt']) * 100:.0f} cm (>= 10)")
        pruef(buckel(erg["neu"]) <= 0.05, f"relief_mischen neu: Schild-Buckel {buckel(erg['neu']) * 100:.1f} cm (<= 5), Maske 'vordergrund' {int(erg['neu']['vordergrund'].sum())} Zellen")
        so = sockel[:erg["neu"]["rel"].shape[0]]; d_ = float(np.median(erg["neu"]["rel"][so]) - np.median(erg["alt"]["rel"][so]))
        pruef(abs(d_) <= 0.01, f"relief_mischen neu: Sockelband unveraendert ({d_ * 100:+.1f} cm)")


def test_quader_veto():
    from PIL import Image
    import putz_wandbild as P
    from relief_putz import quader_veto
    rng = np.random.default_rng(5)
    with tempfile.TemporaryDirectory() as td:
        ffn = os.path.join(td, "fassade_fein"); os.makedirs(os.path.join(ffn, "ortho_f00_einzeln"))
        c = 0.01; nu, nz = 400, 300                                                  # 4 m x 3 m, 1 cm
        json.dump(dict(fassaden=[dict(id="f00", o=[0.0, 0.0], d=[1.0, 0.0], n=[0.0, -1.0], raster=dict(u0=0.0, z1=3.0, nu=nu, nz=nz, zelle=c))]), open(os.path.join(ffn, "fassaden.json"), "w"))
        zz = np.arange(nz)[:, None] * c; uu = np.arange(nu)[None, :] * c
        lage = np.floor(zz / 0.4); vers = (lage % 2) * 0.3; stein = np.floor((uu + vers) / 0.6)
        hell = 175 + 25 * np.sin(lage * 5.3 + stein * 2.1)                          # helle, wenig gesaettigte Steine (bestehen das Farbkriterium)
        tex = hell + 14 * rng.standard_normal((nz, nu)); fuge = ((zz % 0.4) < 0.015) | (((uu + vers) % 0.6) < 0.015); tex[fuge] = 95
        for k in range(5):
            g = np.where(uu < 2.0, tex, 215 + 1.5 * rng.standard_normal((nz, nu)))   # links Quader, rechts glatter Putz
            if k == 1: g[140:143, :] = 40                                               # Kabel in einem Foto
            img = np.clip(np.stack([g, g * 0.97, g * 0.94], -1), 1, 255).astype(np.uint8); Image.fromarray(img).save(os.path.join(ffn, "ortho_f00_einzeln", f"b{k}.png"))
        oj = os.path.join(td, "objekt.json"); json.dump(dict(fassade_fein=ffn), open(oj, "w"))
        px = 0.05; Hr, Wr = 60, 80
        Z = dict(rel=np.ones((Hr, Wr), np.float32), a=np.array([0.0, 0.0, 0.0]), t=np.array([1.0, 0.0, 0.0]), n=np.array([0.0, -1.0, 0.0]), u0=0.0, z0=0.0, px=px)
        P._CACHE.clear(); v = quader_veto(Z, oj)
        pruef(v is not None, "quader_veto liefert eine Maske, wenn fassade_fein passt")
        if v is None: return
        li = v[5:-5, 5:35].mean(); re_ = v[5:-5, 45:-5].mean()
        pruef(li >= 0.9, f"Quaderwerk links als Quaderflaeche belegt ({li * 100:.0f} % >= 90 %)")
        pruef(re_ <= 0.02, f"glatter Putz rechts kein Quader ({re_ * 100:.1f} % <= 2 %; Kabel in einem Foto zaehlt nicht)")
        farbe = np.ones((Hr, Wr), bool); putz = farbe & ~v
        pruef(putz[:, 45:].mean() >= 0.98 and putz[5:-5, 5:35].mean() <= 0.1, "Farb-Putz nach Veto: nur rechts")
        json.dump(dict(fassade_fein=os.path.join(td, "fehlt")), open(oj, "w")); P._CACHE.clear()
        pruef(quader_veto(Z, oj) is None, "ohne fassade_fein: kein Veto (None) - Farbe allein wie bisher")
        json.dump(dict(fassade_fein=ffn), open(oj, "w")); os.environ["OHNE_QUADER_VETO"] = "1"
        pruef(quader_veto(Z, oj) is None, "OHNE_QUADER_VETO=1 schaltet das Veto ab"); os.environ.pop("OHNE_QUADER_VETO")


if __name__ == "__main__":
    print("(1) Vordergrund (relief_vordergrund + relief_mischen)"); test_vordergrund()
    print("(2) Quader-Veto der Putzmaske (putz_wandbild 'quader' + relief_putz.quader_veto)"); test_quader_veto()
    print("FEHLER:", len(FEHLER)) if FEHLER else print("alle Tests bestanden")
    sys.exit(1 if FEHLER else 0)
