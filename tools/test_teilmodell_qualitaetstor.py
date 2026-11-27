#!/usr/bin/env python3
"""Test Qualitaetstor teilmodell_ausrichten.einpassung_guete (27.11.2026, Sekunden, nur numpy).
1. ECHTE alte Einpassung 27.11. (Handy-Teilmodell 0, 324 gemeinsame Bilder; Rest 1,43 m, Steg spaeter 1 m zu hoch) -> UNSICHER (Rest + Drehfehler).
2. ECHTE schlechte Einpassung 26.11. Teil 2 (Rest 1,0 m, "unbrauchbar") -> UNSICHER; ECHTE gute 26.11. Teil 0 -> ausgerichtet.
3. Synthetisch gute Einpassung -> ausgerichtet; Gegenprobe: jede Bedingung einzeln verletzt -> UNSICHER mit genau diesem Grund.
4. Nachtkette: tor() und die Skripte handy_dicht_nachlauf.sh / handy_fusion_nachlauf.sh rufen das Tor vor der Rechnung.
Daten: tools/testdaten/teilmodell_einpassung_echt.npz (Kamerazentren, Drehungen als Drehvektor, 3000 Teilpunkte; aus pycolmap gelesen 27.11.)."""
import os, sys, json, tempfile, numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import teilmodell_ausrichten as TA
fehler = []
def pruef(ok, text): print(("    ok   " if ok else "    FEHL ") + text); ok or fehler.append(text)


def rotm(v):
    v = np.atleast_2d(np.asarray(v, float)); th = np.linalg.norm(v, axis=1); out = np.empty((len(v), 3, 3))
    for i, (w, a) in enumerate(zip(v, th)):
        if a < 1e-15: out[i] = np.eye(3); continue
        k = w / a; K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]]); out[i] = np.eye(3) + np.sin(a) * K + (1 - np.cos(a)) * K @ K
    return out


def echt(key, D):
    A, B = D[key + "_A"], D[key + "_B"]; inl, s, R, t, e = TA.ransac(A, B)
    return TA.einpassung_guete(A, B, inl, s, R, t, float(D["m_je_einheit"]), rotm(D[key + "_rt"]), rotm(D[key + "_rh"]), D[key + "_P"])


D = np.load(os.path.join(T, "testdaten", "teilmodell_einpassung_echt.npz"))
g = echt("voll_1127_t0", D); k = g["kennzahlen"]; print("  alt 27.11.:", g["status"]); print("   ", json.dumps(k))
pruef(g["status"].startswith("UNSICHER"), "echte alte Einpassung 27.11. -> UNSICHER")
pruef(abs(k["rest_mittel_m"] - 1.43) < 0.05 and k["anker"] in (294, 295), f"echte Zahlen wiedererkannt (Rest {k['rest_mittel_m']} m, {k['anker']} Anker)")
pruef(any("Rest" in x for x in g["gruende"]) and any("Drehfehler" in x for x in g["gruende"]), "Grund: Rest UND Drehfehler")
g2 = echt("z1126_t2", D); print("  26.11. Teil 2:", g2["status"])
pruef(g2["status"].startswith("UNSICHER"), "echte schlechte Einpassung 26.11. Teil 2 (Rest 1,0 m) -> UNSICHER")
g0 = echt("z1126_t0", D); print("  26.11. Teil 0:", g0["status"], json.dumps(g0["kennzahlen"]))
pruef(g0["status"] == "ausgerichtet", "echte gute Einpassung 26.11. Teil 0 -> ausgerichtet")

# synthetisch: Anker auf 60 x 40 x 3 m (Hand-Kameras, wie Handyrunde), Rest 2 cm, Drehrauschen 0,1 Grad
rng = np.random.default_rng(3); n = 120
Bm = np.c_[rng.uniform(-30, 30, n), rng.uniform(-20, 20, n), rng.normal(1.6, 0.5, n)]
s0, ang = 0.7, 0.9; c, sn = np.cos(ang), np.sin(ang); R0 = np.array([[c, -sn, 0], [sn, c, 0], [0, 0, 1]]); t0 = np.array([5.0, -3.0, 1.0])
A = ((Bm - t0) @ R0) / s0                                  # Teilrahmen: B = s0 R0 A + t0
Pm = np.c_[rng.uniform(-30, 30, 3000), rng.uniform(-20, 20, 3000), rng.uniform(0, 20, 3000)]; P = ((Pm - t0) @ R0) / s0
Rt = rotm(rng.normal(0, 1, (n, 3)))


def lauf(A_=A, Bm_=Bm, P_=P, Rh_=None, rauschen=0.02, dreh=0.1, nn=None):
    m = len(A_) if nn is None else nn
    Bn = Bm_[:m] + rng.normal(0, rauschen, (m, 3))
    Rh = Rh_ if Rh_ is not None else np.einsum("nij,njk->nik", rotm(rng.normal(0, np.radians(dreh) / np.sqrt(3), (m, 3))), Rt[:m] @ R0.T)
    inl, s, R, t, e = TA.ransac(A_[:m], Bn)
    return TA.einpassung_guete(A_[:m], Bn, inl, s, R, t, 1.0, Rt[:m], Rh, P_)


gs = lauf(); print("  synthetisch gut:", gs["status"], json.dumps(gs["kennzahlen"]))
pruef(gs["status"] == "ausgerichtet", "synthetisch gute Einpassung -> ausgerichtet")
# Gegenproben: je Bedingung einzeln
r = lauf(rauschen=1.2); pruef(r["status"].startswith("UNSICHER") and len(r["gruende"]) >= 1 and all("Rest" in x for x in r["gruende"]), f"(a) nur Rest gross -> UNSICHER ({r['gruende']})")
r = lauf(nn=6); pruef(any("zu wenige Anker" in x for x in r["gruende"]) and r["status"].startswith("UNSICHER"), f"(b) 6 Anker -> UNSICHER ({r['gruende']})")
Bl = Bm.copy(); Bl[:, 1] = rng.normal(0, 0.5, n); Bl[:, 2] = 1.6 + rng.normal(0, 0.1, n); Al = ((Bl - t0) @ R0) / s0
r = lauf(A_=Al, Bm_=Bl); pruef(any("Linie" in x for x in r["gruende"]) and r["status"].startswith("UNSICHER"), f"(b) Anker auf einer Linie -> UNSICHER ({r['gruende']})")
Bk = Bm * 0.15; Ak = ((Bk - t0) @ R0) / s0              # Anker nur 9 x 6 m, Teilmodell weiter 60 x 40 m
r = lauf(A_=Ak, Bm_=Bk, rauschen=0.002); pruef(r["gruende"] and all("Extrapolation" in x for x in r["gruende"]), f"(b) Teilmodell weit ueber die Anker -> UNSICHER: Extrapolation ({r['gruende']})")
r = lauf(dreh=2.0); pruef(r["gruende"] and all("Drehfehler" in x for x in r["gruende"]), f"(c) nur Drehfehler 2 Grad -> UNSICHER ({r['gruende']})")
inl = np.ones(n, bool); inl[: n // 2 + 5] = False; s_, R_, t_ = TA.umeyama(A[inl], Bm[inl])
r = TA.einpassung_guete(A, Bm, inl, s_, R_, t_, 1.0, Rt, np.einsum("nij,njk->nik", np.broadcast_to(np.eye(3), (n, 3, 3)), Rt @ R0.T), P)
pruef(r["gruende"] and all("Inlier-Anteil" in x for x in r["gruende"]), f"(b) Inlier-Anteil < 0,5 -> UNSICHER ({r['gruende']})")
r = TA.einpassung_guete(A, Bm, np.ones(n, bool), *TA.umeyama(A, Bm), 1.0, None, None, P)
pruef(r["status"].startswith("UNSICHER") and "nicht pruefbar" in r["status"], "ohne Drehungen -> UNSICHER (nicht pruefbar)")

# Tor fuer die Nachtkette
import sys as _s, os as _o; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__)))
from pfade import temp_ordner
d = temp_ordner("test_qtor_"); p = os.path.join(d, "ausrichtung.json")
json.dump({"0": {"status": g["status"], "rest_mittel_m": 1.43}, "1": {"status": "ausgerichtet"}}, open(p, "w"))
pruef(TA.tor(p, "0")[0] == 3 and TA.tor(p, "1")[0] == 0 and TA.tor(p, "7")[0] == 3 and TA.tor(os.path.join(d, "fehlt.json"))[0] == 3, "tor(): nur 'ausgerichtet' -> rc 0; UNSICHER/fehlend -> rc 3")
for sh in ("handy_dicht_nachlauf.sh", "handy_fusion_nachlauf.sh"):
    src = open(os.path.join(T, sh)).read(); i_tor = src.find("teilmodell_ausrichten.py --tor"); i_job = src.find("tools/job_start.sh")
    pruef(0 <= i_tor < i_job and "ABBRUCH" in src[i_tor:i_job], f"{sh}: Tor vor dem ersten Rechenjob, Abbruch mit Grund")
print("FEHLER:" if fehler else "alle ok", len(fehler)); sys.exit(1 if fehler else 0)
