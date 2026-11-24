#!/usr/bin/env python3
"""Test tools/sift_paar_speicher.py (24.11.2026, Kette 1122zb: merkmale 1005 s von 1777 s seiten_luecken, jedes neue SfM -> neue Paarliste -> alles neu).
Synthetische Bilder, SIFT + Abgleich auf der CPU (keine GPU):
  1. Voraussetzung: COLMAP matcht je Paar unabhaengig (Teil-/Umkehrliste bitgleich), vorhandene Paare werden uebersprungen.
  2. Erster Lauf (leerer Speicher) = Inhalt wie ohne Speicher; zweiter Lauf: Treffer eingesetzt, Inhalt bitgleich; geaenderte Liste: Teiltreffer, bitgleich.
  3. Guard: verfaelschter Speicher -> Stichprobe weicht ab -> alles neu gerechnet, Inhalt bitgleich, Speicher verworfen.
  4. Geaenderte Kamera eines Bildes -> seine Paare kein Treffer; Paare der Referenz-DB unberuehrt; Schalter aus.
  5. Verdrahtung zusatzfotos_registrieren.merkmale -> sift_paare_matchen_gespeichert.
Aufruf: CUDA_VISIBLE_DEVICES= /media/oem/scan/venv-colmap/bin/python -I tests/test_sift_paar_speicher.py"""
import os, sys, shutil, sqlite3, itertools, tempfile
T = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"); sys.path.insert(0, T)
import numpy as np, cv2, pycolmap
F = []
def ok(c, t):
    print(("    ok   " if c else "    FEHLER ") + t, flush=True)
    if not c: F.append(t)

from pfade import temp_ordner
W = temp_ordner("siftpaar_")
os.environ["RCPARK_NACHHOL_CACHE"] = os.path.join(W, "ablage"); os.environ.pop("RCPARK_SIFT_PAARSPEICHER", None)
import sift_paar_speicher as SP
try:
    B = os.path.join(W, "bilder"); os.makedirs(B); rng = np.random.default_rng(1)
    base = cv2.GaussianBlur((rng.random((900, 1200)) * 255).astype(np.uint8), (0, 0), 3)
    for k in range(60): cv2.circle(base, tuple(int(v) for v in rng.integers(0, 1100, 2)), int(rng.integers(5, 60)), int(rng.integers(0, 255)), -1)
    for i in range(9):
        s = 0.03 * i; H = np.array([[1 + s * 0.3, s * 0.2, 15 * i], [-s * 0.1, 1 - s * 0.2, 8 * i], [s * 1e-4, 0, 1]])
        cv2.imwrite(os.path.join(B, f"b{i}.jpg"), cv2.warpPerspective(base, H, (640, 480)))
    db0 = os.path.join(W, "db0.db"); pycolmap.extract_features(db0, B, device=pycolmap.Device.cpu)
    names = sorted(os.listdir(B)); paare = list(itertools.combinations(names, 2))
    def liste(ps, tag):
        p = os.path.join(W, tag + ".txt"); open(p, "w").write("".join(f"{a} {b}\n" for a, b in ps)); return p
    ZAEHL = []
    def rechnen(db, pf):
        con = sqlite3.connect(db); n0 = con.execute("select count(*) from matches").fetchone()[0]; con.close()
        mo = pycolmap.FeatureMatchingOptions(); mo.use_gpu = False; mo.num_threads = 1; vo = pycolmap.TwoViewGeometryOptions(); vo.ransac.random_seed = 0
        pycolmap.match_image_pairs(db, matching_options=mo, pairing_options=pycolmap.ImportedPairingOptions(match_list_path=pf), verification_options=vo, device=pycolmap.Device.cpu)
        con = sqlite3.connect(db); n1 = con.execute("select count(*) from matches").fetchone()[0]; ver = con.execute("select count(*) from two_view_geometries where rows>0").fetchone()[0]; con.close()
        ZAEHL.append(n1 - n0); return ver
    def inhalt(db):
        con = sqlite3.connect(db); m = list(con.execute("select * from matches")); g = list(con.execute("select * from two_view_geometries")); con.close(); return m, g
    n_k = [0]
    def kopie():
        n_k[0] += 1; p = os.path.join(W, f"k{n_k[0]}", "seiten_nachholen", "db.db"); os.makedirs(os.path.dirname(p)); shutil.copy(db0, p); return p
    pycolmap.set_random_seed(0)
    print("1. Voraussetzung (COLMAP je Paar unabhaengig, vorhandene Paare uebersprungen)")
    A = kopie(); rechnen(A, liste(paare, "alle")); IA = inhalt(A)
    Bd = kopie(); rechnen(Bd, liste(paare[::2], "halb")); rechnen(Bd, liste(list(reversed(paare)), "umgekehrt")); ok(inhalt(Bd) == IA, f"Teil- und Umkehrliste ergeben denselben Inhalt ({len(IA[0])} Paare)")
    ok(ZAEHL[-1] == len(paare) - len(paare[::2]), f"zweiter Aufruf matchte nur die fehlenden Paare ({ZAEHL[-1]} von {len(paare)})")
    print("2. Speicher: leer = ohne Speicher, Treffer bitgleich, Teiltreffer bitgleich")
    pf = liste(paare, "alle"); b = SP.basis(pycolmap, "probe-quelle", A)
    C1 = kopie(); o = SP.ablage(C1); v1, st1 = SP.matchen(C1, pf, rechnen, b, o, stichprobe_min=3)
    ok(inhalt(C1) == IA and st1["treffer"] == 0 and st1.get("abgelegt") == len(paare), f"leerer Speicher: Inhalt wie ohne Speicher, {st1.get('abgelegt')} Paare abgelegt")
    C2 = kopie(); v2, st2 = SP.matchen(C2, pf, rechnen, b, o, stichprobe_min=3)
    ok(inhalt(C2) == IA and v2 == v1, f"zweiter Lauf: Inhalt bitgleich, verifiziert {v2} = {v1}")
    ok(st2["treffer"] == len(paare) and st2["eingesetzt"] == len(paare) - 3 and ZAEHL[-1] == 3, f"zweiter Lauf: {st2['eingesetzt']} eingesetzt, COLMAP matchte nur die Stichprobe ({ZAEHL[-1]})")
    teil = [p for p in paare if p[0] != "b0.jpg"]
    C3 = kopie(); SP.matchen(C3, liste(teil, "teil"), rechnen, b, o, stichprobe_min=2)
    R3 = kopie(); rechnen(R3, liste(teil, "teil")); ok(inhalt(C3) == inhalt(R3), "andere Paarliste: Inhalt wie ohne Speicher")
    print("3. Guard: verfaelschter Speicher -> Stichprobe weicht ab -> alles neu")
    sp = os.path.join(o, f"paare_{b[:8]}.sqlite"); S = sqlite3.connect(sp); S.execute("update m set m_rows = m_rows + 1"); S.commit(); S.close()
    C4 = kopie(); v4, st4 = SP.matchen(C4, pf, rechnen, b, o, stichprobe_min=3)
    ok(st4["verworfen"] and inhalt(C4) == IA and v4 == v1, f"Abweichung erkannt ({st4.get('abweichend')} Paare), Inhalt wie ohne Speicher")
    S = sqlite3.connect(sp); k1 = S.execute("select k from m order by k limit 1").fetchone()[0]; S.execute("update m set m_rows = m_rows + 1 where k=?", (k1,)); S.commit(); S.close()
    C4b = kopie(); _, st4b = SP.matchen(C4b, pf, rechnen, b, o, stichprobe_min=len(paare))
    ok(not st4b["verworfen"] and st4b["abweichend"] == 1, f"ein Einzelausreisser (Rauschen wie COLMAP mehrfaedig) verwirft den Speicher nicht (abweichend {st4b['abweichend']})")
    S = sqlite3.connect(sp); ok(S.execute("select count(*) from m where 1").fetchone()[0] == len(paare), "Speicher neu aufgebaut (nur frisch gerechnete Zeilen)"); S.close()
    print("4. Schluessel: Kamera geaendert, Referenz-DB-Paare, Schalter")
    C5 = kopie(); con = sqlite3.connect(C5); cid = con.execute("select camera_id from images where name='b3.jpg'").fetchone()[0]
    n_cam = con.execute("select count(*) from images where camera_id=?", (cid,)).fetchone()[0]
    con.execute("update cameras set prior_focal_length = 1 - prior_focal_length where camera_id=?", (cid,)); con.commit(); con.close()
    _, st5 = SP.matchen(C5, pf, rechnen, b, o, stichprobe_min=1)
    betroffen = sum(1 for x, y in paare if "b3.jpg" in (x, y)) if n_cam == 1 else None
    ok(n_cam > 1 or st5["treffer"] == len(paare) - betroffen, f"Kamera von b3 geaendert: {st5['treffer']} Treffer (ohne die {betroffen} Paare mit b3; Kamera geteilt: {n_cam > 1})")
    C6 = kopie(); rechnen(C6, liste(paare[:4], "ref")); I6 = inhalt(C6); _, st6 = SP.matchen(C6, pf, rechnen, b, o, stichprobe_min=1)
    ok(st6["offen"] == len(paare) - 4 and inhalt(C6)[0][:0] == [] and all(r in inhalt(C6)[0] for r in I6[0]), "Paare schon in der Referenz-DB: nicht angefasst, nicht gezaehlt")
    ok(SP.basis(pycolmap, "andere-quelle", A) != b, "anderer Quelltext -> andere Basis")
    os.environ["RCPARK_SIFT_PAARSPEICHER"] = "0"; ok(SP.ablage(C6) is None, "RCPARK_SIFT_PAARSPEICHER=0 -> aus"); os.environ.pop("RCPARK_SIFT_PAARSPEICHER")
    print("5. Verdrahtung zusatzfotos_registrieren")
    import inspect, zusatzfotos_registrieren as ZR
    ok("sift_paare_matchen_gespeichert(db, pf, pycolmap)" in inspect.getsource(ZR.merkmale), "merkmale ruft sift_paare_matchen_gespeichert")
    ok("sift_paar_speicher.py" in inspect.getsource(ZR.merkmale_schluessel), "Eintrags-Schluessel enthaelt sift_paar_speicher.py")
    alt = ZR.sift_paare_matchen; ZR.sift_paare_matchen = lambda d_, p_, pc=None, saat=False: rechnen(d_, p_)
    try:
        C7 = kopie(); v7 = ZR.sift_paare_matchen_gespeichert(C7, pf, pycolmap); ok(inhalt(C7) == IA and v7 == v1, "sift_paare_matchen_gespeichert: Inhalt wie ohne Speicher")
    finally: ZR.sift_paare_matchen = alt
    import seiten_luecken as SL; ok("sift_paar_speicher.py" in SL.NACHHOL_WERKZEUGE, "Fehlschlag-Marke: sift_paar_speicher.py im CODE-STAND")
finally:
    shutil.rmtree(W, ignore_errors=True)
print("ALLE OK" if not F else f"FEHLER: {len(F)}: {F}")
sys.exit(1 if F else 0)
