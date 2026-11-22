"""2D-Aehnlichkeitssuche Wandband-Punkte -> LoD2-Kanten (Ziel + Nachbarn), FFT je (Drehung, Massstab)."""
import numpy as np, pickle
from scipy import ndimage
S = "/tmp/claude-29999/-home-oem-git-rc-park/dc62add2-9ee3-4f76-85e0-42c96eea284b/scratchpad/e/"
L = pickle.load(open(S + "lod2.pkl", "rb"))
Z = 0.1; X0, Y0, N = -45.0, -35.0, 900   # Raster 90 m
C = np.array([-2.0, 15.0])


def kanten_raster(nur_ziel=False):
    m = np.zeros((N, N), bool)
    for g in (L["ziel"] if nur_ziel else L["ziel"] + L["andere"]):
        g = np.vstack([g, g[:1]])
        for a, b in zip(g[:-1], g[1:]):
            k = int(np.linalg.norm(b - a) / 0.03) + 2
            for t in np.linspace(0, 1, k):
                p = a + t * (b - a); i, j = int((p[0] - X0) / Z), int((p[1] - Y0) / Z)
                if 0 <= i < N and 0 <= j < N: m[i, j] = True
    return m


KR = kanten_raster(); DIST = ndimage.distance_transform_edt(~KR) * Z
NAEHE = np.exp(-0.5 * (DIST / 0.35) ** 2)
FN = np.fft.rfft2(NAEHE)


def trafo(P, th, s, t):
    c, si = np.cos(np.radians(th)), np.sin(np.radians(th)); R = np.array([[c, -si], [si, c]])
    return (P - C) @ R.T * s + C + t


def dist(P):
    i = np.clip(((P[:, 0] - X0) / Z).astype(int), 0, N - 1); j = np.clip(((P[:, 1] - Y0) / Z).astype(int), 0, N - 1)
    d = DIST[i, j]; d[(P[:, 0] < X0) | (P[:, 0] >= X0 + N * Z) | (P[:, 1] < Y0) | (P[:, 1] >= Y0 + N * Z)] = 99; return d


def anteil(P, grenze=0.3): return float((dist(P) < grenze).mean())


def suche(P, dreh=np.arange(-20, 20.1, 1.0), mass=np.arange(0.80, 1.42, 0.02), tmax=10.0):
    best = []
    for th in dreh:
        for s in mass:
            Q = trafo(P, th, s, 0)
            i = ((Q[:, 0] - X0) / Z).astype(int); j = ((Q[:, 1] - Y0) / Z).astype(int); ok = (i >= 0) & (i < N) & (j >= 0) & (j < N)
            H = np.zeros((N, N)); np.add.at(H, (i[ok], j[ok]), 1.0)
            K = np.fft.irfft2(FN * np.conj(np.fft.rfft2(H)), s=(N, N))   # K[d] = sum_x H[x] NAEHE[x+d]
            K = np.roll(np.roll(K, N // 2, 0), N // 2, 1); k = int(tmax / Z)
            sub = K[N // 2 - k:N // 2 + k + 1, N // 2 - k:N // 2 + k + 1]; a, b = np.unravel_index(np.argmax(sub), sub.shape)
            best.append((sub[a, b] / len(P), th, s, np.array([(a - k) * Z, (b - k) * Z])))
    best.sort(key=lambda x: -x[0]); return best


def fein(P, th, s, t, schritte=3):
    for _ in range(schritte):
        kand = [(th + dt, s * (1 + ds), t + np.array([dx, dy])) for dt in (-0.4, -0.2, 0, 0.2, 0.4) for ds in (-0.01, -0.005, 0, 0.005, 0.01)
                for dx in (-0.2, 0, 0.2) for dy in (-0.2, 0, 0.2)]
        sc = [np.exp(-0.5 * (np.minimum(dist(trafo(P, *k)), 3) / 0.35) ** 2).mean() for k in kand]
        th, s, t = kand[int(np.argmax(sc))]
    return th, s, t
