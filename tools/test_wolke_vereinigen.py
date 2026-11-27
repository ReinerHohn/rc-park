#!/usr/bin/env python3
"""test_wolke_vereinigen.py - ROTER TEST fuer tools/wolke_vereinigen.py (27.11.2026, Nutzer: "Immer vereinen"; Schwabentor: Handy-Wolke ersetzte die alte NICHT).
Synthetische Wolken (kein Rechenjob, ~5 s): Turm-Rechteck mit vier Waenden + Dach, Quelle A (Modellrahmen, PLY) dicht unten, Quelle B (SfM-Rahmen ueber eine
SFM-AUSRICHTUNG, PLY mit Normalen) dicht oben, Quelle C (npy + Farben) nur an der Bruecke. Prueft:
  1. vereint >= beste zugelassene Quelle in JEDER Zone (Nord/Sued/West/Ost/Dach/Bruecke), rc-Logik 'rot' leer;
  2. MUTATION Quelle weglassen (B fehlt im Vereinen, Zaehlung gegen B) -> rot; MUTATION Regel 'erste Quelle je Voxel' statt 'meiste Punkte' -> rot;
  3. Rahmen: B landet nach sfm-Rueckrechnung auf der Modellwand (< 1 mm), Normale zeigt nach aussen (+x);
  4. Lagetor global: um 1 m verschobene Quelle -> ABGELEHNT; Blocktor: in einem Block um 20 cm verschobene Kopie -> nur dort weggelassen;
  5. Lagetor-Eintrag spuren mit tor_rot -> nicht vereint; Register anmelden ersetzt gleichnamige Quelle.
Aufruf: tools/py tools/test_wolke_vereinigen.py  (rc 0 = alles gruen)."""
import os, sys, json, tempfile
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wolke_vereinigen as WV  # noqa: E402

FEHLER = []


def pruef(ok, text):
    print(("OK    " if ok else "FEHLER") + " " + text, flush=True)
    if not ok: FEHLER.append(text)


def wand(rng, n, ax, pos, a, b, z0, z1, normal):
    P = np.zeros((n, 3)); P[:, ax] = pos + rng.normal(0, 0.003, n); P[:, 1 - ax] = rng.uniform(a, b, n); P[:, 2] = rng.uniform(z0, z1, n)
    N = np.zeros((n, 3)); N[:, ax] = normal; return P, N


def ply(pfad, P, N=None, F=None):
    a = np.zeros(len(P), WV.DT); a["x"], a["y"], a["z"] = P.T
    if N is not None: a["nx"], a["ny"], a["nz"] = N.T
    if F is not None: a["r"], a["g"], a["b"] = F.T
    with open(pfad, "wb") as f: f.write(WV.ply_kopf(len(P))); f.write(a.tobytes())


def turm(rng, dichte_unten, dichte_oben):
    """Vier Waende x 0..10, y 0..10 (Nord +x usw.), z 0..20; Dach z 20..22. Punkte je Wand unten (z<10) / oben."""
    T = []
    for ax, pos, nv in ((0, 10, 1), (0, 0, -1), (1, 10, 1), (1, 0, -1)):
        for (z0, z1), n in (((0, 10), dichte_unten), ((10, 20), dichte_oben)):
            if n: T.append(wand(rng, n, ax, pos, 0, 10, z0, z1, nv))
    D = np.c_[rng.uniform(0.5, 9.5, dichte_oben), rng.uniform(0.5, 9.5, dichte_oben), 21 + rng.normal(0, 0.003, dichte_oben)]      # Flachdach z 21
    T.append((D, np.tile([0, 0, 1.0], (len(D), 1))))
    return np.concatenate([t[0] for t in T]), np.concatenate([t[1] for t in T])


def main():
    import cv2
    rng = np.random.default_rng(1); tmp = tempfile.mkdtemp(prefix="test_wv_", dir="/media/oem/scan/tmp" if os.path.isdir("/media/oem/scan/tmp") else None)
    od = os.path.join(tmp, "obj"); os.makedirs(os.path.join(od, "lage"))
    json.dump(dict(name="testturm", hoehe_m=22, rahmen_wand=dict(u0=0, u1=10, v0=0, v1=10), seiten_konvention={"+x": "Nord", "-x": "Sued", "+y": "West", "-y": "Ost"}), open(os.path.join(od, "objekt.json"), "w"))
    json.dump(dict(steg=dict(mitte_modell_xy=[5, -8], achse_modell_xy=[0, -1], laenge_dach_m=10, breite_dach_m=3, dach_first_z_m=6)), open(os.path.join(od, "lage", "STEG.json"), "w"))
    json.dump(dict(dach_oben_m=22, sonderstellen=[dict(name="Bruecke", form="lage", lage="lage/STEG.json")]), open(os.path.join(od, "abdeckung_zonen.json"), "w"))
    OBJ = os.path.join(od, "objekt.json")
    # A: Modellrahmen, unten dicht, oben duenn
    PA, NA = turm(rng, 40000, 3000); ply(os.path.join(tmp, "a.ply"), PA, NA, np.full((len(PA), 3), 100, np.uint8))
    # B: oben dicht, unten duenn - im SfM-Rahmen gespeichert
    PB, NB = turm(rng, 3000, 40000)
    fl = np.c_[rng.uniform(0, 0.02, 60000), np.zeros(60000), rng.uniform(12, 12.5, 60000)]; fl[:, 0] = 2 + rng.uniform(0, 0.5, 60000)      # dichter Fleck auf Ost (y 0): B 60 000, A 3 000
    fl[:, 1] = 0.005; PB = np.r_[PB, fl]; NB = np.r_[NB, np.tile([0, -1.0, 0], (len(fl), 1))]
    PA = np.r_[PA, fl[:3000]]; NA = np.r_[NA, np.tile([0, -1.0, 0], (3000, 1))]
    s, rvec, t = 0.37, np.array([0.3, -1.1, 0.4]), np.array([5.0, -2.0, 1.0]); R = cv2.Rodrigues(rvec)[0]
    au = os.path.join(tmp, "SFM-AUSRICHTUNG.json"); json.dump({"transformation": dict(s=s, rvec=rvec.tolist(), t=t.tolist())}, open(au, "w"))
    ply(os.path.join(tmp, "b_sfm.ply"), s * PB @ R.T + t, NB @ R.T, np.full((len(PB), 3), 200, np.uint8))
    # C: nur Bruecke (npy + farben)
    PC = np.c_[rng.uniform(4, 6, 20000), rng.uniform(-12, -4, 20000), 5 + rng.normal(0, 0.003, 20000)]      # Bruecken-Deck z 5
    np.save(os.path.join(tmp, "c_punkte_modell.npy"), PC); np.save(os.path.join(tmp, "c_punkte_farben.npy"), np.full((len(PC), 3), 50, np.uint8))
    # C braucht Ueberlapp mit dem Bezug fuer das globale Tor: A bekommt etwas Bruecke (duenn)
    q = [dict(name="A", pfad=os.path.join(tmp, "a.ply"), rahmen="modell"), dict(name="B", pfad=os.path.join(tmp, "b_sfm.ply"), rahmen="sfm:" + au),
         dict(name="C", pfad=os.path.join(tmp, "c_punkte_modell.npy"), rahmen="modell")]
    PA2 = np.r_[PA, PC[:3000] + rng.normal(0, 0.003, (3000, 3))]; NA2 = np.r_[NA, np.zeros((3000, 3))]; ply(os.path.join(tmp, "a.ply"), PA2, NA2, np.full((len(PA2), 3), 100, np.uint8))
    kw = dict(voxel=0.02, stichprobe=50000, bloecke=7000, objekt=OBJ, zonen_z=(1.0, 19.5), basis=tmp, log=lambda s_: None)
    B = WV.vereinigen(q, os.path.join(tmp, "v1"), **kw); Zz = B["zonen_zahlen"]
    print("  Zonen:", {zn: {k: Zz[k][zn] for k in ("A", "B", "C", "VEREINT")} for zn in Zz["VEREINT"]})
    pruef(all(z.get("angenommen") for z in B["quellen"]), "alle drei Quellen angenommen: " + str([(z["name"], z.get("median_abstand_m"), z.get("grund")) for z in B["quellen"]]))
    pruef(B["rot"] == [], f"vereint >= beste Quelle in jeder Zone (rot {B['rot']})")
    pruef(set(Zz["VEREINT"]) >= {"Nord", "Sued", "West", "Ost", "Dach", "Bruecke-Streifen"}, f"Zonen gebaut: {sorted(Zz['VEREINT'])}")
    pruef(all(Zz["VEREINT"][zn] >= max(Zz["A"][zn], Zz["B"][zn], Zz["C"][zn]) for zn in Zz["VEREINT"]), "vereint >= max(A,B,C) roh je Zone")
    pruef(Zz["VEREINT"]["Nord"] > 1.3 * max(Zz["A"]["Nord"], Zz["B"]["Nord"]), f"vereint Nord {Zz['VEREINT']['Nord']} deutlich mehr als jede Quelle (A {Zz['A']['Nord']}, B {Zz['B']['Nord']})")
    # Ausgabe pruefen
    L = WV.Quelle(B["ply"]); X, N, F = L.block(0, L.n); qn = np.load(B["ply"] + ".quellen.npy"); pm = np.load(os.path.join(tmp, "v1", "punkte_modell.npy"))
    pruef(len(X) == B["punkte"] == len(qn) == len(pm), f"Ausgabe {len(X)} Punkte, quellen.npy {len(qn)}, punkte_modell.npy {len(pm)}")
    mb = (qn == 1) & (np.abs(X[:, 0] - 10) < 0.05) & (X[:, 2] > 11) & (X[:, 1] > 1) & (X[:, 1] < 9)
    pruef(mb.sum() > 1000 and np.percentile(np.abs(X[mb, 0] - 10), 99) < 0.012, f"B (SfM-Rahmen) auf der Nordwand im Modellrahmen: {mb.sum()} Punkte, p99 Abstand {np.percentile(np.abs(X[mb, 0] - 10), 99):.4f} m (Rauschen 3 mm)")
    pruef(mb.sum() and float(np.median(N[mb, 0])) > 0.999, f"Normale von B nach Rueckdrehung = +x (Median nx {np.median(N[mb, 0]):.4f})")
    pruef(set(np.unique(F[qn == 2][:, 0]).tolist()) == {50} and set(np.unique(F[qn == 1][:, 0]).tolist()) == {200}, "Farben je Quelle erhalten (C 50, B 200)")
    # MUTATION 1: B weglassen, gegen B zaehlen
    B2 = WV.vereinigen([q[0], q[2]], os.path.join(tmp, "v2"), **kw); kv = WV.vkey(np.load(os.path.join(tmp, "v2", "punkte_modell.npy")), 0.02)
    zon = WV.zonen_bauen(OBJ, None, (1.0, 19.5)); zon = [dict(z_, ebene=next(x for x in B["zonen"] if x["name"] == z_["name"]).get("ebene", z_.get("ebene"))) for z_ in zon]
    zahlen = {"B|zugelassen": Zz["B|zugelassen"], "VEREINT": WV.zonen_zaehlen(zon, kv, 0.02)}
    rot = WV.zonen_urteil(zahlen, ["B|zugelassen"]); pruef(len(rot) > 0, f"MUTATION Quelle B weggelassen -> rot: {[r_['zone'] for r_ in rot]}")
    # MUTATION 2: Regel 'erste Quelle je Voxel' (alte Basis-Regel) -> rot
    alt = WV.gewinner
    def erste(keys, src, prio):
        o = np.lexsort((src, keys)); erst = np.r_[True, keys[o][1:] != keys[o][:-1]]; ks = keys[o][erst]; ss = src[o][erst]; pos = np.searchsorted(ks, keys); return ss[pos] == src
    WV.gewinner = erste
    try: B3 = WV.vereinigen(q, os.path.join(tmp, "v3"), **kw)
    finally: WV.gewinner = alt
    pruef(len(B3["rot"]) > 0, f"MUTATION Regel 'erste Quelle je Voxel' -> rot: {[r_['zone'] for r_ in B3['rot']]}")
    # Lagetor global + Blocktor
    PE = PA + [1.0, 0, 0]; ply(os.path.join(tmp, "e.ply"), PE)
    PD = PA.copy(); blk = (PD[:, 0] > 9) & (PD[:, 2] > 0) & (PD[:, 2] < 5) & (PD[:, 1] > 5) & (PD[:, 1] < 10); PD[blk, 0] += 0.20; ply(os.path.join(tmp, "d.ply"), PD)
    B4 = WV.vereinigen([q[0], dict(name="E", pfad=os.path.join(tmp, "e.ply")), dict(name="D", pfad=os.path.join(tmp, "d.ply"))], os.path.join(tmp, "v4"), **dict(kw, block=5.0))
    zE = next(z for z in B4["quellen"] if z["name"] == "E"); zD = next(z for z in B4["quellen"] if z["name"] == "D")
    pruef(zE.get("angenommen") is False and "Median" in zE.get("grund", ""), f"1 m verschobene Quelle ABGELEHNT ({zE.get('grund')})")
    pruef(zD.get("angenommen") and len(zD.get("bloecke_weg", [])) >= 1 and 0 < zD["punkte_weg_blocktor"] < len(PD) // 4,
          f"Blocktor: 20 cm verschobener Block weg ({len(zD.get('bloecke_weg', []))} Bloecke, {zD.get('punkte_weg_blocktor')} Punkte), Rest der Quelle bleibt")
    # Lagetor-Eintrag + Register
    ep = os.path.join(tmp, "einpassung.json"); json.dump({"kandidaten": {"spuren": {"tor_rot": ["Stegdach 1.04 m neben DOM1"]}}}, open(ep, "w"))
    B5 = WV.vereinigen([q[0], dict(q[2], lagetor="spuren:" + ep)], os.path.join(tmp, "v5"), **kw); z5 = B5["quellen"][1]
    pruef(z5.get("angenommen") is False and "Lagetor" in z5.get("grund", ""), f"Lagetor-Eintrag rot -> nicht vereint ({z5.get('grund')})")
    WV.anmelden(OBJ, WV.quelle_aus_text("A=" + q[0]["pfad"])); WV.anmelden(OBJ, WV.quelle_aus_text("B=" + q[1]["pfad"] + "@sfm:" + au)); R_ = WV.anmelden(OBJ, WV.quelle_aus_text("A=/neu.ply"))
    pruef([x["name"] for x in R_["quellen"]] == ["A", "B"] and R_["quellen"][0]["pfad"] == "/neu.ply" and R_["quellen"][1]["rahmen"] == "sfm:" + au, "Register: gleichnamige Quelle ersetzt, Reihenfolge bleibt")
    __import__("shutil").rmtree(tmp, ignore_errors=True)
    print("ERGEBNIS:", "ALLES GRUEN" if not FEHLER else f"{len(FEHLER)} FEHLER"); return 1 if FEHLER else 0


if __name__ == "__main__":
    sys.exit(main())
