#!/usr/bin/env python3
"""test_kamera_rahmen.py - K-Kameras im alten Rahmen (schwabentor-1122, 23.11.2026: 231 nachgetragene/verfeinerte Kameras aus dem Nachholen 1122q
blieben nach neuem SfM 1122r liegen, kameras_aus_buendel hielt sie fuer 'handkalibriert'; Zentrum Median 48 m, Bild ~600 px daneben).

Vorgespielte Daten, nur CPU:
  A) umrechnen: gleiches SfM, neue Ausrichtung (anderer Massstab/Drehung/Verschiebung, anderes T_) -> projizierte Pixel bitgenau gleich (< 1e-6 px).
  B) gleiches_sfm: gleiche SfM-Zentren -> ja; neu gerechnetes SfM (Zentren verschoben) -> nein.
  C) veraltet: rahmen != aktuell -> ja; gleich -> nein; Altbestand ohne rahmen: abgeleitet + aelter als die Ausrichtung -> ja, Handkalibrierung nie.
  D) kameras_aus_buendel Ende-zu-Ende: (1) abgeleitete Kamera im alten Rahmen, Foto im neuen SfM -> Buendelkamera (alte als kamera_veraltet);
     (2) abgeleitet, Foto NICHT im SfM, anderes SfM -> .veraltet; (3) mit Picks -> Datei bleibt, kamera -> kamera_veraltet; (4) Handkalibrierung bleibt;
     (5) abgeleitet im aktuellen Rahmen bleibt; (6) gleiches SfM, nur neue Ausrichtung -> umgerechnet; RAHMEN.json geschrieben; alle Kameras tragen rahmen.
  E) Leser: fassade_ein_foto.kamera und fassaden_kette.fotos_fuer_wand nehmen eine veraltete Kamera nicht.
"""
import os, sys, json, time, shutil, subprocess, tempfile
HIER = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HIER); sys.path.insert(0, HIER)
import numpy as np
import kamera_rahmen as KR
from kamera_standort import _rodrigues

FEHLER = []


def pruef(b, txt):
    print(("ok   " if b else "FEHLT ") + txt)
    if not b: FEHLER.append(txt)


def rot_aus(rng):
    from scipy.spatial.transform import Rotation as Rot
    return Rot.from_rotvec(rng.normal(size=3)).as_matrix()


def rot_z(rng):
    a = float(rng.uniform(0, 2 * np.pi)); return np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1.0]])


def ausrichtung(sfm, s, R, t, bild=(400, 300)):
    """sfm: {name: (R_sfm, C_sfm)} -> Ausrichtung im Format sfm_lod2_ausrichten (kameras im Modellrahmen: X_sfm = s R X_m + t)."""
    from scipy.spatial.transform import Rotation as Rot
    kams = {}
    for n, (Rs, Cs) in sfm.items():
        Cm = R.T @ (Cs - t) / s; Rm = Rs @ R                                 # x ~ Rs (X_s - Cs) = Rs (s R X_m + t - Cs) ~ (Rs R)(X_m - Cm)
        kams[n] = dict(R=Rm.tolist(), t=(-Rm @ Cm).tolist(), f_px_original=300.0, cx=200.0, cy=150.0, k=[0.0], bild_b=bild[0], bild_h=bild[1])
    return dict(transformation=dict(s=s, rvec=Rot.from_matrix(R).as_rotvec().tolist(), t=t.tolist()), kameras=kams, sparse=None)


def proj(k, X):
    R = _rodrigues(np.array(k["rvec"])); q = X @ R.T + np.array(k["t"]); return q[:, :2] / q[:, 2:3]


def sfm_netz(rng, n=8):
    out = {}
    for i in range(n):
        a = 2 * np.pi * i / n; C = np.array([30 * np.cos(a), 30 * np.sin(a), 2.0]); out[f"eigen__f{i}"] = (rot_aus(rng), C)
    return out


def test_umrechnen():
    rng = np.random.default_rng(3); sfm = sfm_netz(rng)
    A1 = ausrichtung(sfm, 0.12, rot_aus(rng), rng.normal(size=3)); A2 = ausrichtung(sfm, 0.098, rot_aus(rng), rng.normal(size=3) * 3)
    S1 = KR.stempel(A1, [0.5, -0.2, 0.3]); S2 = KR.stempel(A2, [-1.0, 2.0, 0.0])
    pruef(S1["id"] != S2["id"] and KR.stempel(A1, [0.5, -0.2, 0.3])["id"] == S1["id"], "Stempel: neue Ausrichtung = neue Kennung, gleiche = gleiche")
    pruef(KR.gleiches_sfm(S1, A2), "gleiches_sfm: nur neu ausgerichtet -> ja")
    sfm_b = {n: (R, C + rng.normal(size=3) * 0.05) for n, (R, C) in sfm.items()}; A3 = ausrichtung(sfm_b, 0.098, rot_aus(rng), rng.normal(size=3))
    pruef(not KR.gleiches_sfm(S1, A3), "gleiches_sfm: neu gerechnetes SfM (Zentren 5 cm anders) -> nein")
    # Punkte im SfM-Rahmen; Kamera im Werkzeugrahmen 1 (X_w = X_m + T_), dann umgerechnet: dieselben Pixel fuer dieselben Punkte im Werkzeugrahmen 2
    Xs = rng.normal(size=(50, 3)) * 3 + [0, 0, 0]
    def werkzeug(A, T_, X):
        T = A["transformation"]; R = _rodrigues(np.array(T["rvec"])); return (R.T @ (X - np.array(T["t"])).T).T / T["s"] + np.array(T_)
    Xw1 = werkzeug(A1, S1["T_"], Xs); Xw2 = werkzeug(A2, S2["T_"], Xs)
    Rc = rot_aus(rng); Cc = Xw1.mean(0) - Rc[2] * 400; k = dict(rvec=KR._rvec(Rc).tolist(), t=(-Rc @ Cc).tolist(), f_px=900, cx=200, cy=150, standort=Cc.tolist(), quelle="nachregistriert (t)")
    if (proj(k, Xw1) is not None) and ((Xw1 - Cc) @ Rc[2] > 0).all():
        k2 = KR.umrechnen(k, S1, S2); d = float(np.abs(proj(k, Xw1) - proj(k2, Xw2)).max() * 900)
        C2 = -_rodrigues(np.array(k2["rvec"])).T @ np.array(k2["t"])
        pruef(d < 1e-6 and k2["rahmen"] == S2["id"] and np.allclose(k2["standort"], C2) and np.allclose(k2["standort_xyz"], C2, atol=1e-3), f"umrechnen: Pixel gleich ({d:.1e} px), rahmen neu, standort mitgerechnet")
    else: pruef(False, "Testaufbau: Punkte hinter der Kamera")


def test_veraltet(S):
    mp = os.path.join(S, "mp_v"); os.makedirs(mp)
    rng = np.random.default_rng(4); A = ausrichtung(sfm_netz(rng), 0.1, np.eye(3), np.zeros(3)); st = KR.stempel(A, [0, 0, 0], zeit=time.time())
    KR.setzen(mp, st); kp = os.path.join(mp, "K-a.json"); json.dump({}, open(kp, "w")); os.utime(kp, (time.time() - 99, time.time() - 99))
    pruef(KR.veraltet(dict(rahmen="alt123"), mp) and not KR.veraltet(dict(rahmen=st["id"]), mp), "veraltet: anderer rahmen ja, gleicher nein")
    pruef(KR.veraltet(dict(quelle="kamera_verfeinern.py: 10 Inlier"), mp, kp), "veraltet: Altbestand abgeleitet + aelter als Ausrichtung -> ja")
    pruef(not KR.veraltet(dict(quelle="", brennweite_quelle="geloest"), mp, kp), "veraltet: Handkalibrierung (Martinstor-Art) nie")
    os.utime(kp, None); pruef(not KR.veraltet(dict(quelle="nachregistriert (x)"), mp, kp), "veraltet: Altbestand juenger als Ausrichtung -> nein (gleicher Lauf)")
    pruef(not KR.veraltet(dict(rahmen="x"), os.path.join(S, "leer")), "veraltet: ohne RAHMEN.json (alte Objekte) nie")


def test_ende_zu_ende(S):
    from PIL import Image
    od = os.path.join(S, "modelle", "x"); mp = os.path.join(od, "messprotokoll"); fd = os.path.join(S, "fotos"); os.makedirs(mp); os.makedirs(fd)
    open(os.path.join(S, "m.stl"), "w").write("solid a\nfacet normal 0 0 1\nouter loop\nvertex -5000 -5000 0\nvertex 5000 -5000 0\nvertex 0 5000 20000\nendloop\nendfacet\nendsolid a\n")
    json.dump(dict(name="x", stl="m.stl", fotos_dir="fotos", zentrierung="achse"), open(os.path.join(od, "objekt.json"), "w"))
    rng = np.random.default_rng(5); sfm = sfm_netz(rng)
    for n in list(sfm) + ["eigen__weg", "eigen__picks", "eigen__hand", "eigen__jetzt"]: Image.new("RGB", (400, 300)).save(os.path.join(fd, n + ".jpg"))
    # Lauf 1: Ausrichtung A1 -> kameras_aus_buendel (RAHMEN 1); danach "Nachholen" schreibt abgeleitete Kameras
    au = os.path.join(mp, "SFM-AUSRICHTUNG-x.json"); A1 = ausrichtung(sfm, 1.0, rot_z(rng), rng.normal(size=3) * [1, 1, 0.1]); json.dump(A1, open(au, "w"))
    def lauf():
        r = subprocess.run([sys.executable, "-W", "ignore", "-I", os.path.join(HIER, "kameras_aus_buendel.py"), os.path.join(od, "objekt.json"), "--ausrichtung", au], capture_output=True, text=True, cwd=S)
        return r.returncode, r.stdout + r.stderr
    rc, out = lauf(); st1 = KR.aktuell(mp)
    pruef(rc == 0 and st1 and all(json.load(open(os.path.join(mp, f"K-{n}.json")))["kamera"].get("rahmen") == st1["id"] for n in sfm), "Lauf 1: Buendelkameras tragen rahmen, RAHMEN.json geschrieben")
    kref = json.load(open(os.path.join(mp, "K-eigen__f1.json")))["kamera"]
    def abg(n, rahmen=None, picks=False, quelle="kamera_verfeinern.py: 900 Inlier auf 2 Waenden", alt_s=True):
        d = dict(foto=n, seite="unbekannt", punkte=({"p1": [1, 2]} if picks else {}), linien={}, kamera=dict(kref, quelle=quelle, vertrauen=True, brennweite_quelle=None))
        d["kamera"].pop("rahmen", None)
        if rahmen: d["kamera"]["rahmen"] = rahmen
        p = os.path.join(mp, f"K-{n}.json"); json.dump(d, open(p, "w"))
        if alt_s: os.utime(p, (time.time() - 30, time.time() - 30))
        return p
    p_sfm = abg("eigen__f2", rahmen=st1["id"]); p_weg = abg("eigen__weg", quelle="nachregistriert (sparse_handy), Abbildung aus 300 gemeinsamen Kameras")
    p_pick = abg("eigen__picks", rahmen=st1["id"], picks=True)
    p_hand = os.path.join(mp, "K-eigen__hand.json"); json.dump(dict(foto="eigen__hand", punkte={"a": [1, 1]}, kamera=dict(kref, quelle="", brennweite_quelle="geloest", rahmen=None)), open(p_hand, "w"))
    os.utime(p_hand, (time.time() - 30, time.time() - 30))
    # Lauf 2a: GLEICHES SfM, neue Ausrichtung -> abgeleitete Kameras umgerechnet (Foto f2 im SfM bekommt aber die Buendelkamera)
    A2 = ausrichtung(sfm, 0.9, rot_z(rng), rng.normal(size=3) * [1, 1, 0.1]); json.dump(A2, open(au, "w")); time.sleep(0.05)
    rc, out = lauf(); st2 = KR.aktuell(mp)
    pruef(rc == 0 and st2["id"] != st1["id"], "Lauf 2a: neuer Rahmen eingetragen")
    pruef(json.load(open(p_sfm))["kamera"].get("brennweite_quelle") == "buendel" and "kamera_veraltet" in json.load(open(p_sfm)), "Lauf 2a: abgeleitet im alten Rahmen, Foto im SfM -> Buendelkamera (alte als kamera_veraltet)")
    kp_ = json.load(open(p_pick))
    pruef(kp_.get("kamera", {}).get("rahmen") == st2["id"] and kp_["kamera"].get("rahmen_umgerechnet_aus") == st1["id"], "Lauf 2a: gleiches SfM -> abgeleitete Kamera (mit rahmen) exakt umgerechnet")
    pruef(not os.path.exists(p_weg) and os.path.exists(p_weg + ".veraltet"), "Lauf 2a: Altbestand ohne rahmen, aelter als Ausrichtung, Foto nicht im SfM -> .veraltet")
    pruef(json.load(open(p_hand))["kamera"].get("brennweite_quelle") == "geloest", "Handkalibrierung bleibt unberuehrt")
    p_jetzt = abg("eigen__jetzt", rahmen=st2["id"])
    # Lauf 2b: NEU GERECHNETES SfM -> keine Abbildung: abgeleitete mit Picks -> kamera_veraltet (Datei bleibt), im aktuellen Rahmen geschriebene -> gesperrt (Rahmen 2 alt)
    sfm_b = {n: (R, C + rng.normal(size=3) * 0.3) for n, (R, C) in sfm.items()}; A3 = ausrichtung(sfm_b, 1.1, rot_z(rng), rng.normal(size=3) * [1, 1, 0.1]); json.dump(A3, open(au, "w"))
    rc, out = lauf(); st3 = KR.aktuell(mp); kp3 = json.load(open(p_pick))
    pruef(rc == 0 and "kamera" not in kp3 and "kamera_veraltet" in kp3 and kp3.get("punkte"), "Lauf 2b: neues SfM, abgeleitet mit Picks -> Kamera gesperrt, Picks bleiben")
    pruef(not os.path.exists(p_jetzt) and os.path.exists(p_jetzt + ".veraltet"), "Lauf 2b: neues SfM, abgeleitet ohne Picks -> .veraltet")
    pruef(json.load(open(p_hand))["kamera"].get("brennweite_quelle") == "geloest", "Lauf 2b: Handkalibrierung bleibt")
    # Lauf 2c: gleiche Ausrichtung noch einmal -> eine im aktuellen Rahmen abgeleitete Kamera bleibt
    p_neu = abg("eigen__jetzt", rahmen=st3["id"]); rc, out = lauf()
    pruef(rc == 0 and os.path.exists(p_neu) and json.load(open(p_neu))["kamera"].get("rahmen") == st3["id"] and "kamera_veraltet" not in json.load(open(p_neu)), "Lauf 2c: abgeleitete Kamera im aktuellen Rahmen bleibt")
    # E) Leser
    import fassade_ein_foto as FE
    p_alt = abg("eigen__weg", rahmen=st1["id"], alt_s=False)
    pruef(FE.kamera(p_alt) is None and FE.kamera(p_neu) is not None, "Leser fassade_ein_foto.kamera: alter Rahmen -> keine Kamera, aktueller -> Kamera")
    import fassaden_kette as FK
    namen, _ = FK.fotos_fuer_wand(od, [-100, -100], [100, -100], np.array([0, -1.0]), 0, 50, k=50, max_winkel=180)
    pruef("eigen__weg" not in namen and "eigen__jetzt" in namen, "Leser fassaden_kette.fotos_fuer_wand: veraltete Kamera nicht unter den Wandfotos")


def main():
    S = tempfile.mkdtemp(prefix="kamera_rahmen_", dir="/media/oem/scan/tmp" if os.path.isdir("/media/oem/scan/tmp") else None)
    try:
        test_umrechnen(); test_veraltet(S); test_ende_zu_ende(S)
    finally: shutil.rmtree(S, ignore_errors=True)
    print(f"{len(FEHLER)} Fehler" + (": " + "; ".join(FEHLER) if FEHLER else "")); return 1 if FEHLER else 0


if __name__ == "__main__":
    sys.exit(main())
