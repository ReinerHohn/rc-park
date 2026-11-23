#!/usr/bin/env python3
"""kamera_rahmen.py - In welchem Rahmen (Ausrichtung/Buendel-Stand) gilt eine K-Kamera? Veraltete abgeleitete Kameras erkennen, umrechnen oder sperren.

Anlass 23.11.2026 (schwabentor-1122, Kette 1122s): 231 K-Dateien aus dem Nachholen des Laufs 1122q (08:52-10:05) - 144 'nachregistriert (sparse_handy)'
(tools/kameras_nachtragen.py) und 87 'kamera_verfeinern.py' (vertrauen=True) - lagen im DAMALIGEN Rahmen (1122q: Sued-Teilmodell getrennt, lage_frueh +9,9 Grad x0,902).
1122r rechnete SfM + Ausrichtung neu (Sued vereint, -0,4 Grad x0,980); tools/kameras_aus_buendel.py hielt jede K-Datei mit brennweite_quelle != 'buendel' fuer
'handkalibriert' und ueberschrieb sie NIE - auch wenn das neue SfM das Foto selbst registrierte. Gemessen an der Ausrichtung 1122r (80 gemeinsame Fotos):
Kamerazentrum Median 48 m daneben, Blickrichtung Median 137 Grad (Seitenverwechslung), Modellpunkte im Bild Median ~600 px versetzt, nur 10 von 80 < 60 px.
Leser (fassade_ortho, fassaden_kette, neben_details, steine_aus_foto, teil_fotoform, kamera_verfeinern-Referenzen, kameras_nachtragen-Anker) nahmen sie trotzdem.

Regel:
  - Jede Kamera, die kameras_aus_buendel / kameras_nachtragen / kamera_verfeinern schreibt, traegt kamera.rahmen = Kennung der Ausrichtung (Transformation s/rvec/t,
    Rahmenverschiebung T_ und Stichprobe der SfM-Kamerazentren). Der gerade gueltige Rahmen steht in messprotokoll/RAHMEN.json (schreibt kameras_aus_buendel).
  - ABGELEITET = quelle 'nachregistriert...' oder 'kamera_verfeinern...' (oder herkunft 'abgeleitet'). Nur diese werden umgerechnet/gesperrt. Echte Handkalibrierungen
    (Picks, quelle leer, brennweite_quelle 'geloest'/'EXIF'/'SfM-Buendel ...') tragen kein solches Merkmal und bleiben unberuehrt.
  - Veraltet = rahmen gesetzt und != aktueller Rahmen; ohne rahmen (Altbestand) = abgeleitet UND Datei aelter als die gueltige Ausrichtung.
  - Neuer Rahmen aus DEMSELBEN SfM (gleiche SfM-Zentren, nur neue Ausrichtung) -> exakte Umrechnung alt -> neu (Aehnlichkeit, Projektion bleibt gleich).
    Anderes SfM (neu gerechnet) -> keine bekannte Abbildung -> sperren (.veraltet, bzw. bei Picks kamera -> kamera_veraltet); das naechste Nachholen bestimmt sie neu.
Test: tools/test_kamera_rahmen.py (Schnelltest)."""
import os, json, hashlib, numpy as np

RAHMEN_DATEI = "RAHMEN.json"
N_ZENTREN = 12


def _rodrigues(r):
    th = float(np.linalg.norm(r))
    if th < 1e-12: return np.eye(3)
    k = np.asarray(r, float) / th; Kx = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + np.sin(th) * Kx + (1 - np.cos(th)) * Kx @ Kx


def _rvec(R):
    from scipy.spatial.transform import Rotation as Rot
    return Rot.from_matrix(R).as_rotvec()


def _sfm_zentren(A, namen=None):
    """SfM-Rahmen-Zentren der Kameras der Ausrichtung A (A['kameras'] liegen im Modellrahmen: X_sfm = s R X_modell + t)."""
    T = A["transformation"]; s = float(T["s"]); R = _rodrigues(T["rvec"]); t = np.asarray(T["t"], float); out = {}
    for n in (namen if namen is not None else sorted(A["kameras"])[:N_ZENTREN]):
        k = A["kameras"].get(n)
        if not k: continue
        Rk = np.asarray(k["R"], float); Cm = -Rk.T @ np.asarray(k["t"], float); out[n] = (s * R @ Cm + t).tolist()
    return out


def stempel(A, T_, ausrichtung_pfad="", zeit=None):
    """Rahmenstempel einer Ausrichtung (dict aus SFM-AUSRICHTUNG-*.json) mit Rahmenverschiebung T_ des Werkzeugrahmens."""
    T = A["transformation"]; T_ = [round(float(x), 4) for x in T_]
    z = _sfm_zentren(A)
    roh = json.dumps(dict(s=round(float(T["s"]), 10), rvec=[round(float(x), 10) for x in T["rvec"]], t=[round(float(x), 8) for x in T["t"]], T_=T_,
                          z={n: [round(x, 5) for x in v] for n, v in z.items()}), sort_keys=True)
    return dict(id=hashlib.sha1(roh.encode()).hexdigest()[:12], ausrichtung=ausrichtung_pfad, zeit=zeit, s=float(T["s"]), rvec=[float(x) for x in T["rvec"]],
                t=[float(x) for x in T["t"]], T_=T_, sfm_zentren=z)


def lesen(mp):
    """messprotokoll/RAHMEN.json -> dict(aktuell=stempel, frueher=[stempel...]) oder None."""
    p = os.path.join(mp, RAHMEN_DATEI)
    try: return json.load(open(p))
    except Exception: return None


def aktuell(mp):
    d = lesen(mp); return (d or {}).get("aktuell")


def setzen(mp, st):
    """Neuen gueltigen Rahmen eintragen (alter wandert nach 'frueher', hoechstens 20)."""
    d = lesen(mp) or dict(aktuell=None, frueher=[])
    if (d.get("aktuell") or {}).get("id") != st["id"]:
        if d.get("aktuell"): d["frueher"] = ([d["aktuell"]] + [f for f in d.get("frueher", []) if f.get("id") != d["aktuell"]["id"]])[:20]
    d["aktuell"] = st; os.makedirs(mp, exist_ok=True); __import__("json_sicher").schreiben(os.path.join(mp, RAHMEN_DATEI), d); return d


def abgeleitet(k):
    """Kamera aus Nachholen/Nachziehen (nicht Buendel, nicht Handkalibrierung)."""
    if not isinstance(k, dict): return False
    q = str(k.get("quelle", ""))
    return k.get("herkunft") == "abgeleitet" or q.startswith("nachregistriert") or q.startswith("kamera_verfeinern")


def veraltet(k, mp, kp=None, st=None):
    """True, wenn die Kamera k nicht im gueltigen Rahmen des Messprotokolls mp liegt. kp = Pfad der K-Datei (fuer Altbestand ohne rahmen: Dateialter)."""
    if not isinstance(k, dict): return False
    st = st if st is not None else aktuell(mp)
    if not st: return False                                      # kein Rahmen bekannt (alte Objekte) -> wie bisher
    if k.get("rahmen"): return k["rahmen"] != st["id"]
    if abgeleitet(k) and kp and st.get("zeit") is not None:
        try: return os.path.getmtime(kp) < float(st["zeit"])
        except OSError: return False
    return False


def gleiches_sfm(alt, A_neu, tol_rel=1e-4):
    """Stammen alter Stempel und neue Ausrichtung aus DEMSELBEN SfM (nur neu ausgerichtet)? Vergleich der SfM-Zentren gemeinsamer Kameras."""
    za = alt.get("sfm_zentren") or {}; zn = _sfm_zentren(A_neu, [n for n in za if n in A_neu["kameras"]])
    if len(zn) < 3: return False
    a = np.array([za[n] for n in zn]); b = np.array([zn[n] for n in zn]); spann = float(np.median(np.linalg.norm(a - a.mean(0), axis=1))) or 1.0
    return float(np.max(np.linalg.norm(a - b, axis=1))) <= tol_rel * spann


def umrechnen(k, alt, neu):
    """Kamera k (Werkzeugrahmen von Stempel alt) in den Werkzeugrahmen von Stempel neu. Beide Ausrichtungen muessen auf dasselbe SfM zeigen.
    X_sfm = s R X_m + t, X_w = X_m + T_  ->  X_w_alt = a M X_w_neu + b;  Kamera R_c, t_c: R' = R_c M, t' = (R_c b + t_c) / a (Projektion unveraendert)."""
    s1, R1, t1, T1 = float(alt["s"]), _rodrigues(alt["rvec"]), np.asarray(alt["t"], float), np.asarray(alt["T_"], float)
    s2, R2, t2, T2 = float(neu["s"]), _rodrigues(neu["rvec"]), np.asarray(neu["t"], float), np.asarray(neu["T_"], float)
    a = s2 / s1; M = R1.T @ R2; b = R1.T @ (t2 - t1) / s1 + T1 - a * M @ T2
    Rc = _rodrigues(k["rvec"]); tc = np.asarray(k["t"], float); Rn = Rc @ M; tn = (Rc @ b + tc) / a; C = -Rn.T @ tn
    k2 = dict(k); k2.update(rvec=_rvec(Rn).tolist(), t=tn.tolist(), rahmen=neu["id"], rahmen_umgerechnet_aus=alt["id"])
    if "standort" in k2: k2["standort"] = C.tolist()
    k2["standort_xyz"] = [round(float(x), 3) for x in C]
    if "hoehe_ueber_gelaende" in k2: k2["hoehe_ueber_gelaende"] = round(float(C[2]), 2)
    return k2


def kamera_ok(kp, k, mp, st=None):
    """Leser-Filter: K-Datei kp mit Kamera k benutzbar (nicht veraltet)?"""
    return not veraltet(k, mp, kp, st)
