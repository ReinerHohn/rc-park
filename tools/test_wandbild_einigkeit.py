#!/usr/bin/env python3
"""test_wandbild_einigkeit.py - Befund 23.11.2026 (Lauf 1122t): Sued-Wand f01 Abdeckung 0,037 -> 0,998 per Nachholen = 'GEWINN', Wandbild aber verschmiert
(Kameras ungenau). Prueft mit synthetischen Einzelprojektionen (keine Rechenlaeufe, < 10 s):
  (1) wandbild_einigkeit: deckungsgleiche Projektionen -> einig, Foto-r hoch; zwei von sechs um 0,6 m versetzt -> genau diese zwei r < R_MIN, Ausschluss reicht;
      alle versetzt -> uneinig, Ausschluss reicht nicht; Struktur aus dem Stapel = Mass der Karte struktur_<id>.png;
  (2) seiten_wiederholung.gewinn: Abdeckung UND Einigkeit -> wiederholen; Abdeckung ohne Einigkeit -> nicht, Meldung 'Kameras ungenau', Sperrvorschlag;
  (3) gesamtkette.seiten_wiederholen: uneinig -> EINE gesperrte Probe (RCPARK_ORTHO_SPERRE) -> einig -> Teillauf mit Sperre; Umgebung danach zurueck;
  (4) fassade_ortho: Sperre nur bei gleicher Kennung UND Normale, Einzelbilder frueherer Laeufe werden geloescht (Quelltext).
Aufruf: tools/py tools/test_wandbild_einigkeit.py   Exit 0 = alles bestanden."""
import os, sys, json, time
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import warnings; warnings.filterwarnings("ignore")
import numpy as np, cv2
from pfade import temp_ordner
import wandbild_einigkeit as WE, seiten_wiederholung as SW

fehler = 0
NZ = NU = 200; ZELLE = 0.05


def pruef(ok, text):
    global fehler
    print(("ok   " if ok else "FEHLER ") + text, flush=True); fehler += 0 if ok else 1


def wand(fid="f01"):
    return dict(id=fid, n=[1.0, 0.0], d=[0.0, 1.0], o=[5.0, 0.0], u=[-5.0, 5.0], z=[0.0, 10.0], flaeche_m2=100.0, polys_uz=[[[-5, 0], [5, 0], [5, 10], [-5, 10]]],
                raster=dict(u0=-5.0, z1=10.0, nu=NU, nz=NZ, zelle=ZELLE), fotos={})


def muster(seed):
    """Wandstruktur: Steine/Fenster ~0,2-0,5 m (grobes Rauschen hochskaliert), Grauwerte 40..220."""
    g = np.random.default_rng(seed).uniform(40, 220, (NZ // 4 + 8, NU // 4 + 8)).astype(np.float32)
    return cv2.GaussianBlur(cv2.resize(g, ((NU // 4 + 8) * 4, (NZ // 4 + 8) * 4), interpolation=cv2.INTER_NEAREST), (0, 0), 1.0)


def projektion(M, du=0, dz=0, hell=1.0, seed=0):
    """Einzelprojektion eines Fotos: Wand um (du, dz) Zellen versetzt (falsche Kamera), andere Belichtung, Rauschen."""
    rng = np.random.default_rng(seed); x = M[16 + dz:16 + dz + NZ, 16 + du:16 + du + NU] * hell + rng.normal(0, 4, (NZ, NU))
    return np.repeat(np.clip(x, 1, 255).astype(np.uint8)[:, :, None], 3, 2)


def ordner_schreiben(d, F, bilder, abdeckung_anteil=1.0):
    """Wie fassade_ortho --einzeln: ortho_<id>_einzeln/<nr>.png, struktur_<id>.png, abdeckung_<id>.png, fassaden.json (fotos)."""
    os.makedirs(os.path.join(d, f"ortho_{F['id']}_einzeln"), exist_ok=True); nu_ = int(round(NU * abdeckung_anteil))
    F = json.loads(json.dumps(F)); F["fotos"] = {}
    for nr, im in bilder.items():
        im = im.copy(); im[:, nu_:] = 0; cv2.imwrite(os.path.join(d, f"ortho_{F['id']}_einzeln", f"{nr}.png"), im); F["fotos"][nr] = dict(zellen=int(NZ * nu_), guete_median=1.0)
    _, Ns = WE.stapel(d, F); st = np.nan_to_num(WE.struktur_aus_stapel(Ns))
    cv2.imwrite(os.path.join(d, f"struktur_{F['id']}.png"), cv2.resize(np.clip(st, 0, 255).astype(np.uint8), (NU, NZ), interpolation=cv2.INTER_NEAREST))
    cnt = np.zeros((NZ, NU), np.int32); cnt[:, :nu_] = len(bilder); cv2.imwrite(os.path.join(d, f"abdeckung_{F['id']}.png"), np.clip(cnt * 20, 0, 255).astype(np.uint8))
    om = np.median(np.stack(list(bilder.values())), 0).astype(np.uint8); om[:, nu_:] = 0; cv2.imwrite(os.path.join(d, f"ortho_{F['id']}.png"), om)
    json.dump(dict(fassaden=[F]), open(os.path.join(d, "fassaden.json"), "w")); return F


def test_mass(d):
    M = muster(1)
    gut = {f"p{i}": projektion(M, hell=0.7 + 0.1 * i, seed=i) for i in range(6)}
    Fg = ordner_schreiben(os.path.join(d, "gut"), wand(), gut)
    wg = WE.wand_einigkeit(os.path.join(d, "gut"), Fg); fg = WE.foto_einigkeit(os.path.join(d, "gut"), Fg)
    pruef(wg["einig_anteil"] >= 0.9 and wg["beurteilt_anteil"] > 0.95, f"deckungsgleich: einig {wg['einig_anteil']} (>= 0,9) trotz Belichtung 0,7..1,2")
    pruef(min(x["r"] for x in fg) > 0.8, f"deckungsgleich: jedes Foto r > 0,8 ({[x['r'] for x in fg]})")
    teil = dict(gut); teil["p4"] = projektion(M, du=12, dz=5, seed=4); teil["p5"] = projektion(M, du=-9, dz=-12, seed=5)     # 0,6 m versetzt = falsche Kamera
    Ft = ordner_schreiben(os.path.join(d, "teil"), wand(), teil); ft = WE.foto_einigkeit(os.path.join(d, "teil"), Ft)
    sch = sorted(x["nr"] for x in ft if x["r"] < WE.R_MIN)
    pruef(sch == ["p4", "p5"], f"zwei versetzte von sechs: genau diese r < R_MIN {WE.R_MIN} ({[(x['nr'], x['r']) for x in ft]})")
    v = WE.ausschluss_vorschlag(os.path.join(d, "teil"), Ft)
    pruef(v["reicht"] and sorted(v["ohne"]) == ["p4", "p5"] and v["einig_nachher"] >= v["einig_vorher"], f"Ausschluss der zwei: reicht, einig {v['einig_vorher']} -> {v['einig_nachher']}")
    rng = np.random.default_rng(7)
    alle = {f"p{i}": projektion(M, du=int(rng.integers(-14, 15)), dz=int(rng.integers(-14, 15)), seed=i) for i in range(6)}
    Fa = ordner_schreiben(os.path.join(d, "alle"), wand(), alle)
    wa = WE.wand_einigkeit(os.path.join(d, "alle"), Fa); va = WE.ausschluss_vorschlag(os.path.join(d, "alle"), Fa)
    pruef(wa["einig_anteil"] < WE.E_MIN, f"alle versetzt (Kameras ungenau): einig {wa['einig_anteil']} < E_MIN {WE.E_MIN}")
    pruef(not va["reicht"], f"alle versetzt: Ausschluss reicht nicht (ohne {len(va['ohne'])}, einig danach {va['einig_nachher']})")
    # Stapel-Mass = Kartenmass (die Karte wurde hier aus dem Stapel geschrieben; die Gleichheit mit fassade_ortho prueft die Probe 1122t: 0,766 Stapel / 0,777 Karte)
    e_st, _ = WE.einig_aus_stapel(WE.stapel(os.path.join(d, "alle"), Fa)[1])
    pruef(abs(e_st - wa["einig_anteil"]) < 0.05, f"Stapel-Einigkeit {e_st} = Karten-Einigkeit {wa['einig_anteil']}")
    # Einzelbild eines frueheren Laufs (nicht in fassaden.json 'fotos') zaehlt nicht
    cv2.imwrite(os.path.join(d, "gut", "ortho_f01_einzeln", "alt_lauf.png"), projektion(M, du=14, seed=9))
    pruef("alt_lauf" not in WE.stapel(os.path.join(d, "gut"), Fg)[0], "Einzelbild frueherer Laeufe (nicht in fassaden.json) bleibt draussen")
    return M


def seiten_json(d, abd):
    p = os.path.join(d, "seiten_luecken.json"); json.dump(dict(ungesehen=[1], waende=[dict(nr=1, id="f01", abdeckung=abd, fotos=2)]), open(p, "w")); return p


def test_gewinn(d, M):
    sl = seiten_json(d, 0.03)
    gut = {f"p{i}": projektion(M, hell=0.8 + 0.05 * i, seed=i) for i in range(6)}
    ordner_schreiben(os.path.join(d, "g_gut"), wand(), gut)
    G = SW.gewinn(sl, os.path.join(d, "g_gut"))
    pruef(G["wiederholen"] and G["waende"][0]["ok_einig"] and not G["sperre"], f"gewinn: Abdeckung 3 % -> 100 % und einig -> wiederholen ({G['waende'][0]['einig_anteil']})")
    rng = np.random.default_rng(3)
    alle = {f"p{i}": projektion(M, du=int(rng.integers(-14, 15)), dz=int(rng.integers(-14, 15)), seed=i) for i in range(6)}
    ordner_schreiben(os.path.join(d, "g_alle"), wand(), alle)
    G2 = SW.gewinn(sl, os.path.join(d, "g_alle")); w2 = G2["waende"][0]
    pruef(not G2["wiederholen"] and w2["ok_abdeckung"] and not w2["ok_einig"] and "Abdeckung ohne Deckungsgleichheit - Kameras ungenau" in w2["meldung"] and not G2["sperre"],
          f"gewinn: Abdeckung ohne Einigkeit -> NICHT wiederholen, Meldung, kein Sperrvorschlag ({w2['meldung'][:120]})")
    teil = {k: v for k, v in list(gut.items())[:3]}; rng = np.random.default_rng(11)          # 3 deckungsgleiche + 6 Fotos mit falscher Kamera (Mehrheit uneinig, wie f01 1122t)
    for i in range(6): teil[f"b{i}"] = projektion(M, du=int(rng.choice([-1, 1]) * rng.integers(8, 15)), dz=int(rng.choice([-1, 1]) * rng.integers(8, 15)), seed=20 + i)
    ordner_schreiben(os.path.join(d, "g_teil"), wand(), teil)
    G3 = SW.gewinn(sl, os.path.join(d, "g_teil")); w3 = G3["waende"][0]
    pruef((not G3["wiederholen"]) and G3["sperre"] and sorted(G3["sperre"]["waende"][0]["ohne"]) == ["b0", "b1", "b2", "b3", "b4", "b5"] and G3["sperre"]["waende"][0]["n"] == [1.0, 0.0],
          f"gewinn: sechs von neun versetzt -> nicht wiederholen, Sperre der sechs uneinigen Fotos vorgeschlagen ({w3['einig_anteil']}, {w3['meldung'][-110:]})")
    # vorher schon einig und gleich bedeckt (alt_dir): einige Flaeche steigt nicht -> kein Gewinn, auch wenn seiten_luecken.json alt ist
    G4 = SW.gewinn(sl, os.path.join(d, "g_gut"), alt_dir=os.path.join(d, "g_gut"))
    pruef(not G4["wiederholen"] and G4["waende"][0]["einig_flaeche_vorher"] > 0.9, "gewinn: einige Flaeche vorher (alt_dir) gleich nachher -> kein Gewinn")
    return sl, gut, teil


def test_kette(d, M, sl, gut, teil):
    os.environ.pop("RCPARK_TEILLAUF", None); os.environ.pop("RCPARK_ORTHO_SPERRE", None)
    import gesamtkette as G
    Z = os.path.join(d, "obj"); os.makedirs(os.path.join(Z, "audit")); D = os.path.join(d, "kette"); os.makedirs(D); bp = os.path.join(D, "bericht.json"); log = os.path.join(D, "log.txt")
    fo = os.path.join(d, "fassade_k"); ordner_schreiben(fo, wand(), {k: v for k, v in list(gut.items())[:3]}, abdeckung_anteil=0.03)
    json.dump(dict(belegt=["x"], waende=[dict(nr=1, id="f01", neu_sicht=3)]), open(os.path.join(Z, "audit", "kameras_nachtragen_tor.json"), "w"))
    class A: quelle = "q"; ziel = "obj"
    proben = []; teil_env = []
    def lauf(B, name, cmd, log, ok=(0,), timeout=None, platz=()):
        if name.startswith("seiten_gewinn_ortho"):
            fn_ = cmd[cmd.index("--aus") + 1]; sp_ = os.environ.get("RCPARK_ORTHO_SPERRE"); ohne = set()
            if sp_: ohne = set(json.load(open(sp_))["waende"][0]["ohne"])
            proben.append((name, "--einzeln" in cmd, sorted(ohne))); ordner_schreiben(fn_, wand(), {k: v for k, v in teil.items() if k not in ohne}); rc = 0
        elif name.startswith("seiten_gewinn"):
            g_ = cmd.index("gewinn"); e_ = SW.gewinn(cmd[g_ + 1], cmd[g_ + 2], alt_dir=cmd[cmd.index("--alt") + 1]); __import__("json_sicher").schreiben(cmd[cmd.index("--aus") + 1], e_)
            if "--sperre-aus" in cmd and e_.get("sperre"): __import__("json_sicher").schreiben(cmd[cmd.index("--sperre-aus") + 1], e_["sperre"])
            rc = 0 if e_["wiederholen"] else 3
        else: rc = 0
        B["schritte"].append(dict(stufe=name, rc=rc, ok=rc in ok)); __import__("json_sicher").schreiben(B["_pfad"], B); return rc, ""
    def einmal(B, name, cmd, log, ok=(0,), timeout=None, platz=()):
        teil_env.append(os.environ.get("RCPARK_ORTHO_SPERRE")); B["schritte"].append(dict(stufe=name, rc=0, ok=True)); return 0, ""
    G.lauf = lauf; G._lauf_einmal = einmal
    B = dict(schritte=[dict(stufe="LAUF_START", ok=True)], _pfad=bp); __import__("json_sicher").schreiben(bp, B)
    r = G.seiten_wiederholen(B, A, "obj/objekt.json", Z, D, fo, sl, time.time() - 60, log, bp)
    pruef(len(proben) == 2 and proben[0][1] and proben[0][2] == [] and proben[1][2] == ["b0", "b1", "b2", "b3", "b4", "b5"], f"Kette: uneinige Probe -> EINE zweite Probe ohne die sechs uneinigen Fotos, mit Einzelbildern ({proben})")
    pruef(r is True and teil_env and teil_env[0] and teil_env[0].endswith("ortho_sperre.json"), f"Kette: gesperrte Probe einig -> Teillauf MIT Sperre ({r}, {teil_env})")
    pruef(os.environ.get("RCPARK_ORTHO_SPERRE") is None and B["schritte"][-1].get("sperre"), "Kette: Umgebung danach zurueck, Sperre im Bericht")


def test_quelltext():
    s = open(os.path.join(T, "fassade_ortho.py")).read()
    pruef('RCPARK_ORTHO_SPERRE' in s and 'F["_id"] == w_.get("id") and float(np.dot(F["n"][:2]' in s, "fassade_ortho: Sperre nur bei gleicher Kennung UND Normale")
    pruef('for alt_ in glob.glob(os.path.join(ed, "*.png")): os.remove(alt_)' in s, "fassade_ortho: Einzelbilder frueherer Laeufe werden vor dem Schreiben geloescht")


def main():
    d = temp_ordner("test_wandbild_einig_")
    M = test_mass(d)
    sl, gut, teil = test_gewinn(d, M)
    test_kette(d, M, sl, gut, teil)
    test_quelltext()
    print(f"{'ALLES BESTANDEN' if not fehler else str(fehler) + ' FEHLER'}"); return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
