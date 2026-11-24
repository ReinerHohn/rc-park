#!/usr/bin/env python3
"""test_seiten_wiederholung.py - Kettenluecke 23.11.2026 (Lauf 1122q, schwabentor-1122): seiten_luecken holte Fotos fuer die ungesehenen Waende f01/f02 nach
(327 Kameras, 'gegenprobe' 0), aber die Stufe lief NACH Wandbild/Bau - nichts davon kam ins Modell desselben Laufs; die neuen Posen prueft niemand.
Prueft mit kleinen vorgespielten Daten (keine Rechenlaeufe):
  (1) kamera_plausibel.messkamera: nachregistriert ohne 'vertrauen' zaehlt nicht, am Modell nachgezogenes Videobild zaehlt, alte Regeln bleiben;
  (2) kameras_nachtragen_tor: unplausibel -> .unplausibel, unbelegt -> .unbelegt, K-Datei mit Picks behaelt die Picks ohne Kamera, belegte bleibt;
      je Wand Zahl der belegten neuen Kameras mit Sicht; zweiter Lauf idempotent;
  (3) seiten_luecken: Nachhol-Skript endet mit dem Tor-Schritt (nach kamera_verfeinern), wand_abdeckung = Mass des Berichts;
  (4) seiten_wiederholung.kandidaten/gewinn: nur ungesehene Waende mit belegter neuer Kamera, Tor-Bericht eines frueheren Laufs gilt nicht, Gewinnschwelle;
  (5) gesamtkette.seiten_wiederholen: Gewinn -> EIN Teillauf (--ab startstufe = fassaden --bis seiten, RCPARK_TEILLAUF=1), Bericht danach mit den Teillauf-Stufen;
      kein Gewinn -> kein Teillauf; Teillauf selbst holt nicht nach und wiederholt nicht.
Aufruf: /media/oem/scan/venv-seg/bin/python -I tools/test_seiten_wiederholung.py  (oder tools/py ...)   Exit 0 = alles bestanden."""
import os, sys, json, time, struct, subprocess
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import numpy as np, cv2
from pfade import temp_ordner
import kamera_plausibel as KP, kameras_nachtragen_tor as KT, seiten_wiederholung as SW, seiten_luecken as SL

fehler = 0


def pruef(ok, text):
    global fehler
    print(("ok   " if ok else "FEHLER ") + text, flush=True); fehler += 0 if ok else 1


def kamera(C, blick, f=1000.0, W=2000, H=1500, **zus):
    """K-'kamera' am Standort C mit Blickrichtung blick (waagrecht), Bild W x H."""
    z = np.asarray(blick, float); z /= np.linalg.norm(z); y = np.array([0, 0, -1.0]); x = np.cross(y, z); R = np.vstack([x, y, z])
    return dict(rvec=cv2.Rodrigues(R)[0].ravel().tolist(), t=(-R @ np.asarray(C, float)).tolist(), f_px=f, cx=W / 2, cy=H / 2, k1=0.0, standort=list(map(float, C)), **zus)


def wand(fid, n, o, d):
    """Wand 10 x 10 m, Raster 0,1 m (wie fassade_ortho: u0/z1 mit 0,5 m Rand)."""
    return dict(id=fid, n=n, d=d, o=o, u=[-5.0, 5.0], z=[0.0, 10.0], flaeche_m2=100.0, polys_uz=[[[-5, 0], [5, 0], [5, 10], [-5, 10]]],
                raster=dict(u0=-5.5, z1=10.5, nu=110, nz=110, zelle=0.1), fotos={})


def ortho(ordner, F, anteil):
    """ortho_<id>.png mit Bilddaten auf dem linken <anteil> der Wand."""
    im = np.zeros((110, 110, 3), np.uint8); im[5:105, 5:5 + int(round(100 * anteil))] = 120; cv2.imwrite(os.path.join(ordner, f"ortho_{F['id']}.png"), im)
    # 23.11.2026: wie fassade_ortho auch abdeckung_ (3 Fotos x 20) und struktur_ (10 = Fotos einig) - das Gewinn-Tor verlangt Deckungsgleichheit (wandbild_einigkeit)
    cv2.imwrite(os.path.join(ordner, f"abdeckung_{F['id']}.png"), np.where(im[:, :, 0] > 0, 60, 0).astype(np.uint8)); cv2.imwrite(os.path.join(ordner, f"struktur_{F['id']}.png"), np.where(im[:, :, 0] > 0, 10, 0).astype(np.uint8))


def objekt_bauen(d):
    od = os.path.join(d, "modelle", "obj_test"); mp = os.path.join(od, "messprotokoll"); au = os.path.join(od, "audit"); fd = os.path.join(d, "fotos")
    for p_ in (mp, au, fd): os.makedirs(p_)
    json.dump(dict(name="Test", ort="Testort", fotos_dir="fotos"), open(os.path.join(od, "objekt.json"), "w"))
    fo = os.path.join(d, "fassade"); os.makedirs(fo)
    FJ = dict(fassaden=[wand("f00", [-1.0, 0.0], [-5.0, 0.0], [0.0, -1.0]), wand("f01", [1.0, 0.0], [5.0, 0.0], [0.0, 1.0])])
    json.dump(FJ, open(os.path.join(fo, "fassaden.json"), "w"))
    return od, mp, au, fd, fo, FJ


def k_schreiben(mp, n, k, **zus):
    json.dump(dict(foto=n, seite="unbekannt", punkte={}, linien={}, kamera=k, **zus), open(os.path.join(mp, f"K-{n}.json"), "w"))


def test_regel():
    k = kamera([25, 0, 5], [-1, 0, 0])
    pruef(not KP.messkamera("eigen__a", dict(k, quelle="nachregistriert (sparse_handy), Abbildung aus 369 gemeinsamen Kameras"), False), "messkamera: nachregistriert ohne vertrauen zaehlt NICHT (1122q: Praefix eigen__/commons_ umging die dl_-Regel)")
    pruef(KP.messkamera("video_frames_x__vf_001", dict(k, vertrauen=True), False), "messkamera: am Modell nachgezogenes Videobild zaehlt (1122q: 10 belegte Videobilder auf f01 fielen weg)")
    pruef(not KP.messkamera("video_frames_x__vf_001", dict(k), False), "messkamera: Videobild ohne Siegel/vertrauen zaehlt weiter nicht")
    pruef(KP.messkamera("eigen__b", dict(k, quelle="kameras_aus_buendel.py"), False) and not KP.messkamera("eigen__b", dict(k), True), "messkamera: eigene Buendelkamera ohne Siegel im Objekt ja, mit Siegel-Objekt nur mit buendel_tor ok")
    pruef(not KP.messkamera("dl_commons__c", dict(k), False) and KP.messkamera("dl_commons__c", dict(k, vertrauen=True), False), "messkamera: dl_ nur mit vertrauen")


def test_tor(d):
    od, mp, au, fd, fo, FJ = objekt_bauen(d)
    neu = dict(gut=kamera([25, 0, 5], [-1, 0, 0], vertrauen=True, quelle="kamera_verfeinern.py: 900 Inlier auf 2 Waenden"),
               tief=kamera([200, 0, -120], [-1, 0, 0.5], quelle="nachregistriert (sparse_handy)"),
               ohne=kamera([25, 3, 5], [-1, 0, 0], quelle="nachregistriert (sparse_handy)"),
               video_frames_v__vf_1=kamera([24, -2, 5], [-1, 0.05, 0], vertrauen=True, quelle="kamera_verfeinern.py"))
    for n_, k_ in neu.items(): k_schreiben(mp, n_, k_)
    k_schreiben(mp, "picks", kamera([25, 1, 5], [-1, 0, 0], quelle="nachregistriert (sparse_handy)")); j_ = json.load(open(os.path.join(mp, "K-picks.json"))); j_["punkte"] = {"traufe": [1, 2]}; json.dump(j_, open(os.path.join(mp, "K-picks.json"), "w"))
    json.dump(dict(neu=[dict(foto=n_) for n_ in list(neu) + ["picks"]], gegenprobe=[]), open(os.path.join(au, "kameras_nachtragen.json"), "w"))
    e = KT.pruefen(os.path.join(od, "objekt.json"), os.path.join(fo, "fassaden.json"))
    pruef(sorted(e["belegt"]) == ["gut", "video_frames_v__vf_1"], f"Tor: belegt = am Modell nachgezogen + plausibel ({e['belegt']})")
    pruef(os.path.exists(os.path.join(mp, "K-tief.json.unplausibel")) and not os.path.exists(os.path.join(mp, "K-tief.json")), "Tor: 120 m unter dem Gelaende -> K-Datei .unplausibel (kein Werkzeug liest sie)")
    pruef(os.path.exists(os.path.join(mp, "K-ohne.json.unbelegt")) and not os.path.exists(os.path.join(mp, "K-ohne.json")), "Tor: reine SfM-Pose ohne Gegenprobe am Modell -> .unbelegt")
    jp = json.load(open(os.path.join(mp, "K-picks.json")))
    pruef("kamera" not in jp and jp.get("punkte") and "kamera_gesperrt" in jp, "Tor: K-Datei mit eigenen Picks bleibt lesbar, nur die unbelegte Kamera faellt weg")
    pruef(os.path.exists(os.path.join(mp, "K-gut.json")), "Tor: belegte Kamera bleibt")
    w = {x["id"]: x for x in e["waende"]}
    pruef(w["f01"]["neu_sicht"] == 2 and w["f00"]["neu_sicht"] == 0, f"Tor: belegte neue Kameras mit Sicht je Wand (f01 {w['f01']['neu_sicht']}, Rueckseite f00 {w['f00']['neu_sicht']})")
    pruef(os.path.exists(os.path.join(au, "kameras_nachtragen_tor.json")), "Tor: Bericht audit/kameras_nachtragen_tor.json")
    e2 = KT.pruefen(os.path.join(od, "objekt.json"), os.path.join(fo, "fassaden.json"))
    pruef(sorted(e2["belegt"]) == sorted(e["belegt"]) and len(e2["gesperrt"]) == len(e["gesperrt"]) and any("schon gesperrt" in g["grund"] for g in e2["gesperrt"]), "Tor: zweiter Lauf idempotent (schon gesperrt)")
    return od, mp, au, fd, fo, FJ


def test_skript(d, od, au, fd, fo, FJ):
    for F in FJ["fassaden"]: ortho(fo, F, 1.0 if F["id"] == "f00" else 0.03)
    cv2.imwrite(os.path.join(fd, "eigen__x.jpg"), np.zeros((20, 20, 3), np.uint8))
    sp = os.path.join(d, "sparse"); os.makedirs(sp); open(os.path.join(sp, "images.bin"), "wb").write(struct.pack("<Q", 0))
    env = dict(os.environ, SEITEN_LUECKEN_DATEN=os.path.join(d, "daten"))
    r = subprocess.run([sys.executable, "-I", os.path.join(T, "seiten_luecken.py"), os.path.join(od, "objekt.json"), fo, "--sparse", sp, "--ref-db", os.path.join(d, "db.db"), "--min_m2", "10"], capture_output=True, text=True, env=env)
    pruef(r.returncode == 3, f"seiten_luecken: Wand f01 ungesehen -> rc 3 (rc {r.returncode} {r.stdout[-200:]} {r.stderr[-300:]})")
    sk = open(os.path.join(au, "seiten_luecken_holen.sh")).read() if os.path.exists(os.path.join(au, "seiten_luecken_holen.sh")) else ""
    i_v, i_t = sk.find("kamera_verfeinern.py"), sk.rfind("kameras_nachtragen_tor.py")      # rfind: seit 24.11.2026 laeuft das Tor zusaetzlich mit --altbestand VOR kameras_nachtragen
    pruef(i_v > 0 and i_t > i_v and "|| [ $? = 3 ]" in sk, "Nachhol-Skript: Tor-Schritt nach kamera_verfeinern, rc 3 bricht nicht ab")
    S = json.load(open(os.path.join(au, "seiten_luecken.json")))
    pruef(S["ungesehen"] == [1] and S["waende"][1]["id"] == "f01" and abs(S["waende"][1]["abdeckung"] - SL.wand_abdeckung(fo, FJ["fassaden"][1], 1)) < 1e-3, f"seiten_luecken: Bericht mit Kennung, Mass = wand_abdeckung ({S['waende'][1]['abdeckung']})")
    return S


def test_entscheidung(d, au, fo, FJ):
    sl, tj = os.path.join(au, "seiten_luecken.json"), os.path.join(au, "kameras_nachtragen_tor.json")
    k, g = SW.kandidaten(tj, sl, seit=time.time() - 60)
    pruef([w["id"] for w in k] == ["f01"] and k[0]["neu_sicht"] == 2, f"kandidaten: ungesehene f01 mit 2 belegten neuen Kameras ({k} {g})")
    k2, g2 = SW.kandidaten(tj, sl, seit=time.time() + 60)
    pruef(k2 == [] and "nicht aus diesem Lauf" in g2, "kandidaten: Tor-Bericht eines frueheren Laufs gilt nicht (Nachholen uebersprungen)")
    T_ = json.load(open(tj)); T0 = dict(T_, belegt=[]); tj0 = os.path.join(d, "tor_leer.json"); json.dump(T0, open(tj0, "w"))
    pruef(SW.kandidaten(tj0, sl)[0] == [], "kandidaten: keine belegte Kamera -> kein Wiederholen")
    fn = os.path.join(d, "fassade_nachgeholt"); os.makedirs(fn); F1 = json.loads(json.dumps(FJ["fassaden"][1])); json.dump(dict(fassaden=[F1]), open(os.path.join(fn, "fassaden.json"), "w"))
    ortho(fn, F1, 0.6); G = SW.gewinn(sl, fn)
    pruef(G["wiederholen"] and G["waende"][0]["id"] == "f01" and G["waende"][0]["nachher"] > 0.55, f"gewinn: 3 % -> 60 % = wiederholen ({G['waende']})")
    ortho(fn, F1, 0.05); G2 = SW.gewinn(sl, fn)
    pruef(not G2["wiederholen"], f"gewinn: 3 % -> 5 % unter der Schwelle {SW.MIN_GEWINN} -> nicht wiederholen")
    cmd = SW.teillauf_befehl("py", "q", "z")
    pruef(cmd[cmd.index("--ab") + 1] == "fenster" and cmd[cmd.index("--bis") + 1] == "seiten", "teillauf_befehl: ab fenster bis seiten")
    return fn


def test_kette(d, od, au, fo, FJ):
    os.environ.pop("RCPARK_TEILLAUF", None)
    import importlib, gesamtkette as G
    importlib.reload(G)
    sl = os.path.join(au, "seiten_luecken.json"); Z = od; D = os.path.join(d, "kette"); os.makedirs(D, exist_ok=True); bp = os.path.join(D, "bericht.json"); log = os.path.join(D, "log.txt")
    class A: quelle = "quelle_obj"; ziel = "obj_test"
    def falsch_lauf(anteil):
        def lauf(B, name, cmd, log, ok=(0,), timeout=None, platz=()):
            if name == "seiten_gewinn_ortho":
                fn_ = cmd[cmd.index("--aus") + 1]; os.makedirs(fn_, exist_ok=True); F1 = json.loads(json.dumps(FJ["fassaden"][1])); json.dump(dict(fassaden=[F1]), open(os.path.join(fn_, "fassaden.json"), "w")); ortho(fn_, F1, anteil)
                pruef(cmd[cmd.index("--nur") + 1] == "f01" and "eben" in cmd, "Kette: Wandbild-Probe nur fuer die betroffene Wand, Messflaeche eben"); rc = 0
            elif name == "seiten_gewinn":
                e_ = SW.gewinn(cmd[cmd.index("gewinn") + 1], cmd[cmd.index("gewinn") + 2]); __import__("json_sicher").schreiben(cmd[cmd.index("--aus") + 1], e_); rc = 0 if e_["wiederholen"] else 3
            else: rc = 0
            B["schritte"].append(dict(stufe=name, rc=rc, ok=rc in ok)); __import__("json_sicher").schreiben(B["_pfad"], B); return rc, ""
        return lauf
    aufrufe = []
    def falsch_einmal(B, name, cmd, log, ok=(0,), timeout=None, platz=()):
        aufrufe.append((name, cmd, os.environ.get("RCPARK_TEILLAUF")))
        Bi = json.load(open(bp)); Bi["schritte"] += [dict(stufe="LAUF_START", ok=True, ab="fassaden", bis="seiten"), dict(stufe="fenster_ortho", ok=True), dict(stufe="seiten", ok=False, ungesehen=[])]
        __import__("json_sicher").schreiben(bp, Bi); time.sleep(0.01); ortho(fo, FJ["fassaden"][1], 0.6)
        S_ = json.load(open(sl)); S_["waende"][1]["abdeckung"] = 0.6; S_["ungesehen"] = []; __import__("json_sicher").schreiben(sl, S_)
        e = dict(stufe=name, rc=0, ok=True); B["schritte"].append(e); return 0, ""
    S_alt = open(sl).read()
    # (a) kein Gewinn -> kein Teillauf
    B = dict(schritte=[dict(stufe="LAUF_START", ok=True)], _pfad=bp); __import__("json_sicher").schreiben(bp, B)
    G.lauf = falsch_lauf(0.05); G._lauf_einmal = falsch_einmal
    r = G.seiten_wiederholen(B, A, "modelle/obj_test/objekt.json", Z, D, fo, sl, time.time() - 60, log, bp)
    pruef(r is False and not aufrufe and B["schritte"][-1]["stufe"] == "seiten_wiederholung" and B["schritte"][-1]["wiederholt"] is False, "Kette: kein messbarer Gewinn -> kein Teillauf, Grund im Bericht")
    # (b) Gewinn -> ein Teillauf, Bericht neu geladen
    B = dict(schritte=[dict(stufe="LAUF_START", ok=True)], _pfad=bp); __import__("json_sicher").schreiben(bp, B)
    G.lauf = falsch_lauf(0.6)
    r = G.seiten_wiederholen(B, A, "modelle/obj_test/objekt.json", Z, D, fo, sl, time.time() - 60, log, bp)
    pruef(r is True and len(aufrufe) == 1, f"Kette: Gewinn -> genau EIN Teillauf ({len(aufrufe)})")
    if aufrufe:
        n_, cmd, env_ = aufrufe[0]
        pruef(env_ == "1" and cmd[cmd.index("--ab") + 1] == "fassaden" and cmd[cmd.index("--bis") + 1] == "seiten" and "tools/gesamtkette.py" in cmd, "Kette: Teillauf mit RCPARK_TEILLAUF=1, --ab fassaden (Relief mit den neuen Kameras, 1122t) --bis seiten")
    st = [e["stufe"] for e in B["schritte"]]
    pruef("fenster_ortho" in st and st[-2:] == ["seiten_wiederholung_teillauf", "seiten_wiederholung"] and B["schritte"][-1]["wiederholt"] is True, f"Kette: Bericht enthaelt die Teillauf-Stufen, danach Schritt + Notiz ({st[-5:]})")
    pruef(B["schritte"][-1]["waende"][0]["nachher_bericht"] == 0.6, "Kette: Abdeckung nachher aus dem neuen seiten-Bericht")
    pruef(json.load(open(bp))["schritte"][-1]["stufe"] == "seiten_wiederholung" and os.environ.get("RCPARK_TEILLAUF") is None, "Kette: Bericht auf Platte vollstaendig, Umgebung zurueckgesetzt")
    open(sl, "w").write(S_alt)
    # (c) im Teillauf: kein Nachholen, keine zweite Wiederholung (Quelltext-Pruefung der Bedingungen)
    src = open(os.path.join(T, "gesamtkette.py")).read()
    pruef('([] if TEILLAUF else ["--download", "--holen"])' in src and "not TEILLAUF and seiten_wiederholen(" in src, "Kette: Teillauf holt nicht nach und wiederholt nicht (hoechstens eine Wiederholung)")


def main():
    d = temp_ordner("test_seiten_wh_")
    test_regel()
    od, mp, au, fd, fo, FJ = test_tor(d)
    test_skript(d, od, au, fd, fo, FJ)
    test_entscheidung(d, au, fo, FJ)
    test_kette(d, od, au, fo, FJ)
    print(f"{'ALLES BESTANDEN' if not fehler else str(fehler) + ' FEHLER'}"); return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
