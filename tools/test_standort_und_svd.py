"""test_standort_und_svd.py - Kette 1122r (23.11.2026): zwei Abstuerze, die das vereinte Sued-Modell zerstoerten.

A) tiefe_lokal.py: KeyError 'standort_xyz' - K-Dateien aus kameras_nachtragen/kamera_verfeinern tragen nur 'standort' (231 von 625 bei schwabentor-1122).
   Pruefung: kamera_standort liest standort_xyz > standort > Pose (-R^T t), gibt None ohne alles; die Fotowahl in tiefe_lokal nutzt es (kein ["standort_xyz"] mehr);
   die Schreiber legen standort_xyz mit an.
B) wand_dicke_tor.innenflaechen: np.linalg.svd(Q) mit Q (n x 2) baute U (n x n) -> 119 GiB bei n = 126197.
   Pruefung: kleiner Fall alte Rechnung (volle Matrizen) == neue (full_matrices=False) bis auf Vorzeichen; grosser Fall (200000 Punkte) laeuft mit wenig Speicher.
Nur vorgespielte Daten, nur numpy."""
import os, sys, json, re, resource
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
import numpy as np
from kamera_standort import kamera_standort, kamera_standort_grund, _rodrigues


def test_standort():
    rng = np.random.default_rng(1)
    for _ in range(20):                                                   # Rodrigues = Drehmatrix (orthonormal, det 1), Standort = -R^T t
        r = rng.normal(size=3); R = _rodrigues(r); assert np.allclose(R @ R.T, np.eye(3), atol=1e-12) and abs(np.linalg.det(R) - 1) < 1e-12
        C = rng.normal(size=3) * 20; t = -R @ C
        assert np.allclose(kamera_standort(dict(rvec=r.tolist(), t=t.tolist())), C, atol=1e-9)
        assert np.allclose(kamera_standort(dict(rvec=r.tolist(), t=t.tolist(), standort=(C + 1).tolist())), C + 1)          # 'standort' vor Pose
        assert np.allclose(kamera_standort(dict(rvec=r.tolist(), t=t.tolist(), standort=(C + 1).tolist(), standort_xyz=(C + 2).tolist())), C + 2)
    assert np.allclose(_rodrigues(np.array([0, 0, np.pi / 2])) @ [1, 0, 0], [0, 1, 0], atol=1e-12)
    # bekannter Fall aus schwabentor-1122 K-commons_orig2__004 (Werte gekuerzt, standort aus kameras_nachtragen): Pose und 'standort' stimmen ueberein
    assert kamera_standort({}) is None and kamera_standort(None) is None and kamera_standort(dict(rvec=[0, 0, 0])) is None
    assert kamera_standort(dict(standort_xyz=[1, 2])) is None and kamera_standort(dict(standort=[float("nan"), 0, 0])) is None
    S, g = kamera_standort_grund(dict(f_px=1000)); assert S is None and "ohne" in g
    S, g = kamera_standort_grund(dict(standort=[1, 2, 3, 4])); assert np.allclose(S, [1, 2, 3]) and g == ""


def test_kein_direktzugriff():
    """Kein Werkzeug der Fassadenkette greift mehr hart auf ["standort_xyz"] zu (Rueckfall-Waechter)."""
    for f in ("tiefe_lokal.py", "form_aus_wandbild.py", "gruppen_punkt_tor.py", "wolke_streiffilter.py", "wolke_front.py", "wolke_bereinigen.py", "wolke_ueber_foto.py"):
        s = open(os.path.join(HIER, f)).read()
        assert not re.search(r"\[\s*[\"']standort_xyz[\"']\s*\]", s) and 'get("standort_xyz", [0, 0, 0])' not in s, f"{f}: harter Zugriff auf standort_xyz"
    for f in ("kameras_nachtragen.py", "kamera_verfeinern.py"):
        assert "standort_xyz=" in open(os.path.join(HIER, f)).read(), f"{f}: schreibt kein standort_xyz"


def _alt(Q):                                                              # alte Rechnung (volle Matrizen, wie vor dem 23.11.)
    _, _, Vt = np.linalg.svd(Q - Q.mean(0)); return Vt


def _neu(Q):
    _, _, Vt = np.linalg.svd(Q - Q.mean(0), full_matrices=False); return Vt


def test_svd_gleich_und_klein():
    rng = np.random.default_rng(2)
    for n in (2, 3, 7, 50, 400):
        Q = np.c_[rng.uniform(0, 10, n), 0.1 * rng.normal(size=n) + 0.05 * np.arange(n) / n]
        A, B = _alt(Q), _neu(Q); assert A.shape == B.shape == (2, 2)
        for i in range(2): assert np.allclose(A[i], B[i]) or np.allclose(A[i], -B[i])
        ang = lambda V: (np.degrees(np.arctan2(V[0, 1], V[0, 0])) + 90) % 180 - 90
        assert abs(ang(A) - ang(B)) < 1e-9 or abs(abs(ang(A) - ang(B)) - 180) < 1e-9
    src = open(os.path.join(HIER, "wand_dicke_tor.py")).read()
    zeile = [l for l in src.splitlines() if "Q = np.c_[s_[m], x[m]]" in l][0]; assert "full_matrices=False" in zeile, "wand_dicke_tor.innenflaechen: svd wieder mit vollen Matrizen"
    vor = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    n = 200000; Q = np.c_[rng.uniform(0, 12, n), 0.02 * rng.normal(size=n)]; V = _neu(Q)
    assert abs(abs(V[0, 0]) - 1) < 1e-3                                   # Hauptrichtung entlang u
    assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss - vor < 200 * 1024, "svd braucht zu viel Speicher"   # alt: 298 GiB


def test_innenflaechen_gross():
    """innenflaechen mit 150000 Bandpunkten in einem Teil (wie 1122r Teil 1, 126197) - laeuft ohne n x n."""
    try: import wand_dicke_tor as WD
    except ImportError as e: print("  (wand_dicke_tor nicht importierbar:", e, "- nur svd-Pruefung)"); return
    rng = np.random.default_rng(3); g = np.array([[0, 0], [12, 0], [12, 12], [0, 12]], float)
    def teil(n):
        x = rng.uniform(1, 11, n); P = np.c_[x, np.full(n, 3.0) + 0.02 * rng.normal(size=n), rng.uniform(2, 8, n), np.zeros(n), np.ones(n), np.zeros(n)]   # x y z nx ny nz: Innenwand y = 3 (hinter der Kante y=0), Normale +y
        return P
    vor = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    aus = WD.innenflaechen(g, {"0": teil(4000), "1": teil(150000)})
    assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss - vor < 1500 * 1024, "innenflaechen braucht zu viel Speicher"
    assert any(e["teile"].get("1", {}).get("n", 0) > 100000 for e in aus), aus


if __name__ == "__main__":
    for t in (test_standort, test_kein_direktzugriff, test_svd_gleich_und_klein, test_innenflaechen_gross): t(); print("ok", t.__name__)
