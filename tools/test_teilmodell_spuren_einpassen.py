#!/usr/bin/env python3
"""Test teilmodell_spuren_einpassen (Sekunden): direkte Paare, robuste Sim3 aus Spuren mit Ausreissern, Steg-Messung (Laenge/Neigung), Steg-Tor wird ROT bei
geneigtem Steg (> 5 Grad ohne Beleg), Massstab gegen LoD2 > 3 %, Dach neben DOM1; Kippung aus Kamerahoehen. Echte Daten (falls vorhanden): neue Einpassung gruen,
alte Kamerazentren-Einpassung rot (Stegdach +1 m ueber DOM1) - Lehre 27.11.2026."""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from teilmodell_spuren_einpassen import direkte_paare_aus_listen, steg_messen, steg_tor, kipp_aus_hoehen
from sim3_robust import sim3_meter, anwenden, matrix
from scipy.spatial.transform import Rotation as Ro

ECHT = "/media/oem/rcdaten/tmp/handy_teil_spuren/einpassung.json"


def steg_wolke(rng, laenge=24.0, breite=4.0, z_deck=5.8, z_first=10.5, n=20000):
    s = rng.uniform(-laenge / 2, laenge / 2, n); q = rng.uniform(-breite / 2, breite / 2, n)
    z = z_first - 1.2 * np.abs(q) / (breite / 2) + rng.normal(0, 0.03, n)                # Satteldach
    d = rng.uniform(-laenge / 2, laenge / 2, n // 2); dq = rng.uniform(-1.5, 1.5, n // 2); dz = np.full(n // 2, z_deck) + rng.normal(0, 0.03, n // 2)
    return np.r_[np.c_[s, q, z], np.c_[d, dq, dz]]


def main():
    rng = np.random.default_rng(3); fehler = 0
    # 1) direkte Paare: gleicher Keypoint in beiden -> Paar, sonst nicht
    p = direkte_paare_aus_listen([{1: 10, 2: 11, 5: 12}], [{1: 100, 5: 105, 7: 107}]); assert p == [(10, 100), (12, 105)], p
    # 2) Sim3 aus Spuren mit 40 % Ausreissern, feste Meter-Schwelle
    Y = rng.normal(size=(3000, 3)) * [6, 6, 12]; s0, R0, t0 = 5.28, Ro.from_rotvec([0.3, -1.1, 0.4]).as_matrix(), np.array([3.0, -7.0, 1.0])
    X = ((Y - t0) @ R0) / s0 + rng.normal(0, 0.002, Y.shape); k = rng.random(len(Y)) < 0.4; X[k] += rng.normal(0, 1.0, (k.sum(), 3))
    r = sim3_meter(X, Y, schwelle_m=0.15, runden=2000, min_anteil=0.05); M = r["M"]; s = np.cbrt(np.linalg.det(M[:3, :3]))
    assert abs(s / s0 - 1) < 0.003, s; assert np.linalg.norm(anwenden(M, X[~k]) - Y[~k], axis=1).max() < 0.1
    # 3) Steg waagerecht: Laenge, Neigung ~0, Tor gruen
    P = steg_wolke(rng); P[:, :2] = P[:, :2] @ Ro.from_euler("z", 25, degrees=True).as_matrix()[:2, :2].T + [1.0, -24.0]
    u = Ro.from_euler("z", 25, degrees=True).as_matrix()[:2, 0]
    st = steg_messen(P, [1.0, -24.0], u + [0.1, 0.05], z_dach_min=8.0)
    assert abs(st["laenge_m"] - 24) < 1.0, st; assert abs(st["neigung_dach_grad"]) < 0.3, st; assert abs(st["deck_unterkante_z"] - 5.8) < 0.2, st
    assert steg_tor(dict(neigung_dach_grad=st["neigung_dach_grad"], massstab_lod2=1.01, dom_dach_dz_m=0.1, dom_seite_m=0.3)) == []
    # 4) Steg um 6 Grad gekippt (verkippte Einpassung) -> ROT; 3 Grad -> gruen (Toleranz 5)
    for grad, rot in [(6.0, True), (3.0, False), (30.0, True)]:
        c = P[:, :2].mean(0); Rk = Ro.from_rotvec(np.r_[-u[1], u[0], 0] * np.radians(grad)).as_matrix(); Pk = (P - [*c, 8]) @ Rk.T + [*c, 8]
        st2 = steg_messen(Pk, [1.0, -24.0], u, z_dach_min=float(np.median(Pk[:, 2])))
        g = steg_tor(dict(neigung_dach_grad=st2["neigung_dach_grad"]))
        assert bool(g) == rot, (grad, st2["neigung_dach_grad"], g)
        assert abs(abs(st2["neigung_dach_grad"]) - grad) < (1.0 if grad < 10 else 0.2 * grad), (grad, st2["neigung_dach_grad"])
    assert steg_tor(dict(neigung_dach_grad=6.0), beleg_neigung=True) == []          # mit Beleg (z. B. Rampe im Foto) erlaubt
    # 5) Massstab und DOM1
    assert steg_tor(dict(massstab_lod2=1.05)) and not steg_tor(dict(massstab_lod2=0.98))
    assert steg_tor(dict(dom_dach_dz_m=0.98)) and not steg_tor(dict(dom_dach_dz_m=0.04)) and steg_tor(dict(dom_seite_m=1.5))
    # 6) Kippung aus Kamerahoehen: Kameras 1,5 m ueber ebenem Gelaende, um 1 Grad gekippt -> Korrektur -1 Grad
    C = np.c_[rng.uniform(-40, 40, 200), rng.uniform(-50, 30, 200), np.full(200, 1.5) + rng.normal(0, 0.1, 200)]
    Rk = Ro.from_rotvec([np.radians(1.0), 0, 0]).as_matrix(); piv = np.array([0, 10.0, 5.0]); Ck = (C - piv) @ Rk.T + piv
    ax, ay, h0 = kipp_aus_hoehen(Ck, lambda x, y: np.zeros_like(np.asarray(x, float)), piv)
    assert abs(np.degrees(ax) + 1.0) < 0.1 and abs(np.degrees(ay)) < 0.1 and abs(h0 - 1.5) < 0.05, (np.degrees(ax), np.degrees(ay), h0)
    # 7) echte Daten (Schwabentor-Handyfotos 26.11.), falls vorhanden
    if os.path.exists(ECHT):
        e = json.load(open(ECHT)); kn = e["kandidaten"]
        assert kn["spuren"]["tor_rot"] == [], kn["spuren"]["tor_rot"]
        assert kn["spuren"]["lot_bildx_neigung_grad"] < 2.0
        if "alt" in kn: assert kn["alt"]["tor_rot"], "alte Kamerazentren-Einpassung muss rot sein (Stegdach ~1 m ueber DOM1)"
        print("echte Daten:", ECHT)
    else: print("echte Daten fehlen, nur synthetisch")
    print("OK test_teilmodell_spuren_einpassen"); return fehler


if __name__ == "__main__":
    sys.exit(main())
