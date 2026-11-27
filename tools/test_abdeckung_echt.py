#!/usr/bin/env python3
"""Fester Test (~5 s) fuer tools/abdeckung_meldung.py auf ECHTEN Kameras + Spurpunkten (Review 27.11.2026: der alte Test sicherte nur bedingte Logik, Mini-Datensatz
ohne Spurpunkte, laden_sparse ungetestet, echte Zonenliste nicht geprueft, Bruecke/Treppe/Unterdurchgang standen fest auf 'mitte: null' = immer 'nicht belegt').

DATEN (tools/testdata/, erzeugt mit --bauen aus den echten Rekonstruktionen; je Kamera nur Spurpunkte in der Huelle der Zone +-2,5 m, alle Kameras mit
geometrischer Sicht auf die Zone - Spurbeleg und Zaehlung sind damit identisch zum vollen Lauf):
  abdeckung_echt_treppenturm_1126.npz  Handy 26.11. (zusatz_20261126: sparse_handy/0 + SFM-AUSRICHTUNG) - Treppenturm-Befund 26.11.: 320 geometrisch, 186 mit
                                       Spurbeleg, davon 24 Handy (Bildstichprobe 8/8 behaltene zeigen den Turm, Logbuch Doku/projekt/foto-sfm/grundbegriffe.md).
  abdeckung_echt_steg_1127.npz         Handy voll (zusatz_20261126_voll/lg) + eingepasstes Teilmodell (einpassung.json neben BRUECKE-LAGE.json, 634 Kameras).
PRUEFUNGEN (jede mit eigener roter Gegenprobe):
  1 Treppenturm echt   Spurbeleg 186 / geometrisch 320 / Handy 24, belegt.             Gegenprobe: spur=False -> 320 (Spurbeleg wirkt wirklich).
  2 echte Zonenliste   modelle/schwabentor-1122/abdeckung_zonen.json: Bruecke findet ihre Lagedatei (keine Lagewerte in der Zonenliste), Treppe/Unterdurchgang
                       ohne Lage = 'nicht belegt' + 'Lage unbekannt'.               Gegenprobe: Lagedatei weg -> Bruecke 'Lage unbekannt'.
  3 Steg gemessen      jeder Teil der Bruecke hat Zellen, Lage bekannt, Seiten/Treppenende belegt mit gemessenen Fotos > 0 - ROT, wenn trotz Lagedatei
                       'nicht belegt' ohne Messung.                                 Gegenprobe: Kameras weg -> dieselben Teile 'nicht belegt', 0 Fotos.
  4 0 Fotos nie belegt jede Zone mit 0 Fotos ist 'nicht belegt' (Steg-Dach echt: 0). Gegenprobe: MIN_FOTOS = 0 gesetzt -> Pruefung schlaegt an (Test nicht trivial).
  5 laden_sparse       Sim3 aus einpassung.json (M_teil_modell) auf eine Mini-Rekonstruktion: Kamerazentrum + Blickrichtung im Modellrahmen (pycolmap, sonst uebersprungen).
Python: /media/oem/scan/venv-seg/bin/python -I tools/test_abdeckung_echt.py   (Bauen: tools/py tools/test_abdeckung_echt.py --bauen)"""
import os, sys, json, copy
import numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import abdeckung_meldung as AM

R = os.path.dirname(T); OBJ_DIR = os.path.join(R, "modelle", "schwabentor-1122"); ZONEN = os.path.join(OBJ_DIR, "abdeckung_zonen.json")
DT = os.path.join(T, "testdata"); F_TT = os.path.join(DT, "abdeckung_echt_treppenturm_1126.npz"); F_ST = os.path.join(DT, "abdeckung_echt_steg_1127.npz")
OBJ_KEYS = ("name", "rahmen", "rahmen_wand", "seiten_konvention", "hoehe_m")
RAND = 2.5; Q_M = 0.001


def speichern(pfad, kams, P, obj, neu, zonen_namen, cfg, basis):
    zon = [z for z in AM.zonen_bauen(cfg, obj, basis) if z["name"] in zonen_namen or z.get("gruppe") in zonen_namen]
    keep = np.zeros(len(kams), bool)
    for z in zon:
        if len(z["X"]):
            S = AM.sicht(kams, z["X"], z["N"], z.get("koerper"))
            if z.get("innen_box"): S &= AM.im_kasten(np.array([k["C"] for k in kams]), z["innen_box"])[:, None]
            keep |= S.any(1)
    X = np.vstack([z["X"] for z in zon if len(z["X"])]); lo, hi = X.min(0) - RAND, X.max(0) + RAND; K = [k for k, m in zip(kams, keep) if m]; B, off = [], [0]
    for k in K: b = np.asarray(k["beob"], np.float32).reshape(-1, 3); b = b[np.all((b >= lo) & (b <= hi), 1)]; B.append(b); off.append(off[-1] + len(b))
    P = np.asarray(P); P = P[np.all((P >= lo) & (P <= hi), 1)].astype(np.float32)
    assert (np.vstack(B + [P]) - lo).max() / Q_M < 65535, "Huelle zu gross fuer uint16"
    q = lambda A: np.round((np.asarray(A, float) - lo) / Q_M).astype(np.uint16)          # 1 mm Raster ab Huellenecke (1 cm kippte 1 Kamera an der 2-m-Schwelle) (< 1 MB, Hook)
    np.savez_compressed(pfad, C=np.array([k["C"] for k in K]), R=np.array([k["R"] for k in K]), f=np.array([k["f"] for k in K]), w=np.array([k["w"] for k in K]),
                        h=np.array([k["h"] for k in K]), name=np.array([k["name"] for k in K]), neu=np.array([k["name"] in neu for k in K]), beob=q(np.vstack(B)), off=np.array(off), P=q(P), lo=lo,
                        obj=json.dumps({k: obj[k] for k in OBJ_KEYS if k in obj}))
    print(f"{pfad}: {len(K)} Kameras, {off[-1]} Spurpunkte, {len(P)} Punkte, {os.path.getsize(pfad) // 1024} KB")


def bauen():
    obj = json.load(open(os.path.join("/home/oem/git/rc-park/modelle/schwabentor-1122/objekt.json"))); cfg = json.load(open(ZONEN))
    au = "/home/oem/git/rc-park/modelle/schwabentor-1122/messprotokoll/SFM-AUSRICHTUNG-schwabentor-1122.json"
    z = "/media/oem/rcdaten/rc-park_daten_neu/zusatz_20261126"; reg = json.load(open(os.path.join(z, "registrierung.json"))); k, P = AM.laden_sparse(os.path.join(z, "sparse_handy", "0"), au)
    speichern(F_TT, k, P, obj, {n for n, v in reg["bilder"].items() if v.get("status") == "registriert"}, {"Treppenturm"}, cfg, OBJ_DIR)
    z = "/media/oem/rcdaten/rc-park_daten_neu/zusatz_20261126_voll/lg"; reg = json.load(open(os.path.join(z, "registrierung.json"))); k, P = AM.laden_sparse(os.path.join(z, "sparse_handy", "0"), au)
    neu = {n for n, v in reg["bilder"].items() if v.get("status") == "registriert"}; Ps = [P]
    for ep in AM.einpassungen_finden(cfg, OBJ_DIR):
        kz, Pz = AM.laden_einpassung(ep); k = AM.kameras_vereinen(k, kz); neu |= {x["name"] for x in kz}; Ps.append(Pz)
    speichern(F_ST, k, np.vstack(Ps), obj, neu, {"Bruecke"}, cfg, OBJ_DIR)


def laden(pfad):
    d = np.load(pfad); o = d["off"]; B = d["beob"] * Q_M + d["lo"]
    K = [dict(name=str(d["name"][i]), C=d["C"][i], R=d["R"][i], f=float(d["f"][i]), w=float(d["w"][i]), h=float(d["h"][i]), beob=B[o[i]:o[i + 1]]) for i in range(len(d["C"]))]
    return K, [k["name"] for k, n in zip(K, d["neu"]) if n], d["P"] * Q_M + d["lo"], json.loads(str(d["obj"]))


fehler = []
def pruef(b, t):
    if not b: fehler.append(t); print("FEHLER:", t)
    return b


def zonen_von(m): return {e["name"]: e for e in m["zonen"]}
REG = dict(min_inlier=30, bilder={})


def test():
    cfg = json.load(open(ZONEN))
    # ---------- 1 Treppenturm echt (Befund 26.11.)
    K, neu, P, obj = laden(F_TT); m, _ = AM.melden(obj, cfg, K, neu, REG, P, basis=OBJ_DIR); tt = zonen_von(m)["Treppenturm"]
    pruef(tt["fotos"] == 186 and tt["fotos_geometrisch"] == 320 and tt["fotos_neu"] == 24 and tt["status"] == "belegt",
          f"1 Treppenturm: {tt['fotos']} Fotos (Soll 186), geometrisch {tt['fotos_geometrisch']} (320), Handy {tt['fotos_neu']} (24), {tt['status']}")
    g = zonen_von(AM.melden(obj, cfg, K, neu, REG, P, spur=False, basis=OBJ_DIR)[0])["Treppenturm"]
    pruef(g["fotos"] == 320, f"1 Gegenprobe: ohne Spurbeleg {g['fotos']} statt 320 - Spurbeleg wirkt nicht nachweisbar")
    # ---------- 2 echte Zonenliste
    br = next(s for s in cfg["sonderstellen"] if s["name"] == "Bruecke")
    pruef(br.get("mitte") is None and not any(k in br for k in ("achse", "laenge_m", "groesse_m")), "2 Zonenliste: Bruecke traegt Lagewerte selbst (nur Verweis auf Lagedatei erlaubt)")
    pf = AM.lage_finden(br, OBJ_DIR); pruef(pf is not None and os.path.isfile(pf), "2 Bruecke findet ihre Lagedatei nicht")
    pruef(AM.lage_finden(dict(br, lage=None), OBJ_DIR) == pf, "2 automatische Suche messprotokoll/*/BRUECKE-LAGE*.json findet die Lagedatei nicht")
    for s in ("Treppe", "Unterdurchgang"): pruef(AM.lage_finden(next(x for x in cfg["sonderstellen"] if x["name"] == s), OBJ_DIR) is None, f"2 {s}: Lagedatei gefunden, die es nicht gibt")
    K, neu, P, obj = laden(F_ST); m, _ = AM.melden(obj, cfg, K, neu, REG, P, basis=OBJ_DIR); zs = zonen_von(m); auf = {a["stelle"]: a for a in m["fotoauftrag"]}
    for s in ("Treppe", "Unterdurchgang"):
        pruef(zs[s]["status"] == "nicht belegt" and not zs[s]["lage_bekannt"] and "Lage unbekannt" in auf.get(s, {}).get("anweisung", ""), f"2 {s}: ohne Lage nicht 'nicht belegt' + Lage unbekannt")
    leer = os.path.join(__import__("pfade").temp_ordner("test_abdeckung_echt_"), "x")
    m0, _ = AM.melden(obj, cfg, K, neu, REG, P, basis=leer); z0 = zonen_von(m0)
    pruef("Bruecke" in z0 and not z0["Bruecke"]["lage_bekannt"] and "Lage unbekannt" in {a["stelle"]: a for a in m0["fotoauftrag"]}["Bruecke"]["anweisung"],
          "2 Gegenprobe: ohne Lagedatei muss Bruecke 'Lage unbekannt' sein")
    # ---------- 3 Steg gemessen (Lage belegt)
    teile = {n: e for n, e in zs.items() if e.get("gruppe") == "Bruecke"}
    pruef(len(teile) >= 6 and "Bruecke" not in zs, f"3 Bruecke nicht in Teile zerlegt: {sorted(teile)}")
    for n, e in teile.items():
        pruef(e["lage_bekannt"] and e["zellen"] > 0 and "Lage im Netz unbekannt" not in " ".join(e["fehlt"]), f"3 {n}: trotz Lagedatei ohne Messung ({e['fehlt']})")
    seiten = [e for n, e in teile.items() if "Seite" in n]
    pruef(len(seiten) == 2 and all(e["status"] == "belegt" and e["fotos"] >= AM.MIN_FOTOS for e in seiten), f"3 Seiten des Stegs nicht belegt: {[(e['name'], e['status'], e['fotos']) for e in seiten]}")
    pruef(teile.get("Bruecke Treppenende", {}).get("status") == "belegt", "3 Treppenende nicht belegt (echte Messung 27.11.: 55 Fotos, Faecher 119 Grad)")
    pruef(sum(e["fotos"] for e in teile.values()) > 100 and any(e["fotos_neu"] > 0 for e in teile.values()), "3 Steg: kaum gemessene Fotos - eingepasste Teilmodell-Kameras fehlen?")
    mk, _ = AM.melden(obj, cfg, [], [], REG, P, basis=OBJ_DIR); zk = zonen_von(mk)
    pruef(all(zk[n]["status"] == "nicht belegt" and zk[n]["fotos"] == 0 for n in teile), "3 Gegenprobe: ohne Kameras muessen alle Stegteile 'nicht belegt' sein")
    # ---------- 4 Zone mit 0 Fotos nie belegt (harte Regel im Code, unabhaengig von den Schwellen)
    def null_ok(mm): return all(e["status"] == "nicht belegt" for e in mm["zonen"] if e["fotos"] == 0)
    pruef(null_ok(m) and null_ok(mk) and zs["Bruecke Dach"]["fotos"] == 0, f"4 Zone mit 0 Fotos gilt als belegt / Steg-Dach hat {zs['Bruecke Dach']['fotos']} Fotos (echt 0)")
    alt = (AM.MIN_FOTOS, AM.MIN_FAECHER_GRAD, AM.MIN_ZELLEN, AM.MIN_TIEFE_REL); AM.MIN_FOTOS = AM.MIN_FAECHER_GRAD = AM.MIN_ZELLEN = AM.MIN_TIEFE_REL = 0
    try: mr, _ = AM.melden(obj, cfg, K, neu, REG, P, basis=OBJ_DIR)
    finally: AM.MIN_FOTOS, AM.MIN_FAECHER_GRAD, AM.MIN_ZELLEN, AM.MIN_TIEFE_REL = alt
    pruef(null_ok(mr) and zonen_von(mr)["Bruecke Dach"]["status"] == "nicht belegt", "4 alle Schwellen 0: Zone mit 0 Fotos wurde 'belegt' (harte Regel fehlt)")
    falsch = copy.deepcopy(m); next(e for e in falsch["zonen"] if e["fotos"] == 0)["status"] = "belegt"
    pruef(not null_ok(falsch), "4 Gegenprobe: Pruefung erkennt eine belegte 0-Foto-Zone nicht (Test trivial)")
    # ---------- 5 laden_sparse mit Sim3 M (einpassung.json) und Spurpunkten - Attrappe statt pycolmap (gleiche Schnittstelle, ohne Datei)
    s_, th = 2.0, np.radians(30); Rm = np.array([[np.cos(th), -np.sin(th), 0], [np.sin(th), np.cos(th), 0], [0, 0, 1]]); M = np.eye(4); M[:3, :3] = s_ * Rm; M[:3, 3] = [10, -5, 1]
    Ct = np.array([1.0, 2.0, 3.0]); Rw = np.array([[0, 1, 0], [-1, 0, 0], [0, 0, 1.0]]); Xt = np.array([2.0, 3.5, 9.0])
    ns = lambda **k: type("NS", (), k)
    pkt = [ns(point3D_id=7, has_point3D=lambda: True), ns(point3D_id=-1, has_point3D=lambda: False)]
    im = ns(has_pose=True, camera_id=1, name="a.jpg", points2D=pkt, cam_from_world=lambda: ns(rotation=ns(matrix=lambda: Rw)), projection_center=lambda: Ct)
    rec = ns(images={1: im}, cameras={1: ns(params=[90.0, 50, 40], width=100, height=80)}, points3D={7: ns(xyz=Xt)})
    echt = sys.modules.get("pycolmap"); sys.modules["pycolmap"] = ns(Reconstruction=lambda p: rec)
    try: k5, P5 = AM.laden_sparse("attrappe", M=M)
    finally:
        if echt is None: del sys.modules["pycolmap"]
        else: sys.modules["pycolmap"] = echt
    c5, x5 = M[:3, :3] @ Ct + M[:3, 3], M[:3, :3] @ Xt + M[:3, 3]
    pruef(np.allclose(k5[0]["C"], c5) and np.allclose(P5[0], x5) and np.allclose(k5[0]["beob"], [x5], atol=1e-4), f"5 laden_sparse M: Zentrum/Punkt/Spur {k5[0]['C']} {P5} statt {c5} {x5}")
    pruef(np.allclose(k5[0]["R"].T @ [0, 0, 1], Rm @ (Rw.T @ [0, 0, 1])), "5 laden_sparse M: Blickrichtung falsch")
    v = k5[0]["R"] @ (x5 - k5[0]["C"]); vt = Rw @ (Xt - Ct)
    pruef(np.allclose(v[:2] / v[2], vt[:2] / vt[2]), "5 laden_sparse M: Projektion des Punktes aendert sich durch die Einpassung (muss gleich bleiben)")
    print(f"Treppenturm {tt['fotos']}/{tt['fotos_geometrisch']} (Handy {tt['fotos_neu']}); Steg: " + ", ".join(f"{n.split(' ', 1)[1]} {e['status']} {e['fotos']}" for n, e in teile.items()))


if __name__ == "__main__":
    if "--bauen" in sys.argv: bauen(); sys.exit(0)
    test()
    if fehler: print(f"ROT: {len(fehler)} Fehler"); sys.exit(1)
    print("ok test_abdeckung_echt")
