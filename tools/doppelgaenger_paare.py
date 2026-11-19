#!/usr/bin/env python3
"""doppelgaenger_paare.py <bilder_ordner> <paare.txt> --aus <ergebnis.json> [--groesse 1024]

Gelernter PAAR-PRUEFER gegen Seitenverwechslung: zeigt ein Bildpaar DIESELBE Wand oder nur eine aehnliche (Vorder-/Rueckseite eines Turms)?
Anlass Martinstor 19.11.2026: beide Turmseiten (Uhr, Ecktuermchen, Helm) wurden im SfM verklebt; die Zwei-Bild-Geometrie laesst solche Paare durch.
Verfahren = "Doppelgangers: Learning to Disambiguate Images of Similar Structures" (Cai et al., ICCV 2023, https://github.com/RuojinCai/doppelgangers, MIT-Lizenz):
  1. LoFTR-Zuordnungen (kornia, Gewichte 'outdoor', Apache 2.0) auf 1024 px, quadratisch aufgefuellt.
  2. Bild 0 per Aehnlichkeitsabbildung auf Bild 1 gelegt; Masken der Merkmale und der bestaetigten Zuordnungen (Fundamentalmatrix) + beide Bilder = 10 Kanaele.
  3. Kleines Faltungsnetz (Gewichte doppelgangers_classifier_loftr.pt) -> Wahrscheinlichkeit 'gleiche Wand'.
Netzaufbau und Eingabe sind aus dem MIT-Repo uebernommen (cnn_classifier.py, utils/dataset.py read_loftr_matches), damit kein fremder Code ausgefuehrt wird;
die Gewichte werden mit weights_only=True geladen. paare.txt: je Zeile 'bild0 bild1' (relativ zum Ordner). Ausgabe: {"paare": [[bild0, bild1, p_gleich, n_loftr], ...]}.
GRENZEN: trainiert auf Wikimedia-Bildern beruehmter Bauten; je Paar ~0,3 s GPU -> nur auf Paare ZWISCHEN Bildgruppen anwenden (tools/seiten_erkennen.py), nicht auf alle.
GPU: ~4 GB (JOB_GPU_MB=4500)."""
import sys, os, json, math, argparse
import numpy as np, cv2

GEWICHTE = os.environ.get("RCPARK_DOPPEL_GEWICHTE", "/media/oem/scan/doppelgangers/ck/doppelgangers/checkpoints/doppelgangers_classifier_loftr.pt")
os.environ.setdefault("TORCH_HOME", "/media/oem/scan/doppelgangers/hub")


def netz():
    import torch, torch.nn as nn

    class Block(nn.Module):
        def __init__(s, ein, aus, stride=1):
            super().__init__(); s.conv1 = nn.Conv2d(ein, aus, 3, stride, 1, bias=False); s.conv2 = nn.Conv2d(aus, aus, 3, 1, 1, bias=False); s.bn1 = nn.BatchNorm2d(aus); s.bn2 = nn.BatchNorm2d(aus); s.relu = nn.ReLU(inplace=True)
            s.downsample = None if stride == 1 else nn.Sequential(nn.Conv2d(ein, aus, 1, stride, 0, bias=False), nn.BatchNorm2d(aus))

        def forward(s, x):
            y = s.bn2(s.conv2(s.relu(s.bn1(s.conv1(x)))))
            return s.relu((x if s.downsample is None else s.downsample(x)) + y)

    class Dec(nn.Module):
        def __init__(s):
            super().__init__(); s.conv1 = nn.Conv2d(10, 128, 7, 2, 3, bias=False); s.bn1 = nn.BatchNorm2d(128); s.relu = nn.ReLU(inplace=True)
            s.layer1 = nn.Sequential(Block(128, 128, 2), Block(128, 128)); s.layer2 = nn.Sequential(Block(128, 256, 2), Block(256, 256)); s.layer3 = nn.Sequential(Block(256, 512, 2), Block(512, 512))
            s.avgpool = nn.AdaptiveAvgPool2d((1, 1)); s.fc = nn.Linear(512, 2)

        def forward(s, x):
            return s.fc(torch.flatten(s.avgpool(s.layer3(s.layer2(s.layer1(s.relu(s.bn1(s.conv1(x))))))), 1))

    ck = torch.load(GEWICHTE, map_location="cpu", weights_only=True); sd = ck["dec"] if "dec" in ck else ck
    sd = {(k[7:] if k.startswith("module.") else k): v for k, v in sd.items()}; m = Dec(); m.load_state_dict(sd, strict=True)
    return m.eval().cuda()


def masse(w, h, groesse, df=8):
    f = groesse / max(w, h); wn, hn = int(round(w * f)), int(round(h * f)); return max(df, wn // df * df), max(df, hn // df * df)


def grau_quadrat(bgr, groesse):
    h, w = bgr.shape[:2]; wn, hn = masse(w, h, groesse); g = cv2.resize(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), (wn, hn)); P = np.zeros((1, 1, groesse, groesse), np.float32); P[0, 0, :hn, :wn] = g / 255.0
    M = np.zeros((1, groesse, groesse), bool); M[:, :hn, :wn] = True
    return P, M                                                                    # kornia verkleinert die Maske selbst auf 1/8


def eingabe(b0, b1, groesse, k0, k1, conf):
    """10 Kanaele wie read_loftr_matches(..., resize, 8, True, k0, k1, matches, warp=True, conf=conf) des MIT-Repos."""
    stark = conf > 0.8; matches = None
    if stark.sum() >= 8:
        F, msk = cv2.findFundamentalMat(k0[stark], k1[stark], cv2.FM_RANSAC, 3, 0.99)
        if F is not None and msk is not None: matches = np.arange(len(k0))[stark][msk.ravel() == 1]
    (w0, h0), (w1, h1) = masse(b0.shape[1], b0.shape[0], groesse), masse(b1.shape[1], b1.shape[0], groesse)
    M = None; wk, hk = w0, h0; kw = k0
    if matches is not None and len(matches) >= 3:
        M, _ = cv2.estimateAffinePartial2D(np.float32(k0[matches]).reshape(-1, 1, 2), np.float32(k1[matches]).reshape(-1, 1, 2), method=cv2.RANSAC, ransacReprojThreshold=20.0)
        if M is not None:
            kw = cv2.transform(np.float32(k0).reshape(-1, 1, 2), M).reshape(-1, 2); wk, hk = w1, h1
    gueltig = (kw[:, 0] >= 0) & (kw[:, 0] < wk) & (kw[:, 1] >= 0) & (kw[:, 1] < hk) if len(kw) else np.zeros(0, bool)
    if M is not None and gueltig.sum() == 0: M = None; kw = k0; wk, hk = w0, h0; gueltig = (kw[:, 0] >= 0) & (kw[:, 0] < wk) & (kw[:, 1] >= 0) & (kw[:, 1] < hk)
    pad = max(h1, w1); K = np.zeros((4, pad, pad), np.float32); iy = lambda v, mx: np.minimum(np.floor(v).astype(int), mx - 1)
    if gueltig.sum(): K[0, np.minimum(iy(kw[gueltig, 1], hk), pad - 1), np.minimum(iy(kw[gueltig, 0], wk), pad - 1)] = conf[gueltig]
    if len(k1): K[2, iy(k1[:, 1], h1), iy(k1[:, 0], w1)] = conf
    if matches is not None:
        g = gueltig[matches]
        if g.sum(): K[1, np.minimum(iy(kw[matches, 1][g], hk), pad - 1), np.minimum(iy(kw[matches, 0][g], wk), pad - 1)] = 1.0
        K[3, iy(k1[matches, 1], h1), iy(k1[matches, 0], w1)] = 1.0
    rgb = np.zeros((6, pad, pad), np.float32); rgb[:3, :h1, :w1] = np.transpose(cv2.resize(b1.astype(np.float32), (w1, h1)), (2, 0, 1)) / 255.0
    i0 = cv2.resize(b0.astype(np.float32), (w0, h0))
    if M is not None: rgb[3:, :h1, :w1] = np.transpose(cv2.warpAffine(i0, M, (w1, h1), flags=cv2.INTER_AREA), (2, 0, 1)) / 255.0
    else: rgb[3:, :min(h0, pad), :min(w0, pad)] = (np.transpose(i0, (2, 0, 1)) / 255.0)[:, :pad, :pad]
    return np.concatenate((K, rgb), 0)


def pruefen(ordner, paare, groesse=1024, melden=50):
    """paare = [(bild0, bild1), ...] -> [(bild0, bild1, p_gleich, n_loftr)]. p_gleich klein = Doppelgaenger (andere Wand)."""
    import torch, kornia.feature as KF
    lo = KF.LoFTR(pretrained="outdoor").eval().cuda(); dec = netz(); aus = []; cache = {}

    def bild(n):
        if n not in cache:
            if len(cache) > 400: cache.clear()
            b = cv2.imread(os.path.join(ordner, n), cv2.IMREAD_COLOR); cache[n] = (b,) + grau_quadrat(b, groesse) if b is not None else None
        return cache[n]
    for i, (a, b) in enumerate(paare):
        A, B = bild(a), bild(b)
        if A is None or B is None: aus.append((a, b, None, 0)); continue
        with torch.inference_mode():
            r = lo({"image0": torch.from_numpy(A[1]).cuda(), "image1": torch.from_numpy(B[1]).cuda(), "mask0": torch.from_numpy(A[2]).cuda(), "mask1": torch.from_numpy(B[2]).cuda()})
            k0, k1, cf = r["keypoints0"].cpu().numpy(), r["keypoints1"].cpu().numpy(), r["confidence"].cpu().numpy()
            x = torch.from_numpy(eingabe(A[0], B[0], groesse, k0, k1, cf))[None].cuda()
            p = float(torch.softmax(dec(x), 1)[0, 1])
        aus.append((a, b, round(p, 4), int(len(k0))))
        if melden and (i + 1) % melden == 0: print(f"  {i + 1} von {len(paare)} Paaren", flush=True)
    return aus


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("ordner"); ap.add_argument("paare"); ap.add_argument("--aus", required=True); ap.add_argument("--groesse", type=int, default=1024)
    a = ap.parse_args(argv); paare = [tuple(l.split()[:2]) for l in open(a.paare) if len(l.split()) >= 2]
    erg = pruefen(a.ordner, paare, a.groesse); json.dump(dict(paare=erg), open(a.aus, "w"))
    p = np.array([e[2] for e in erg if e[2] is not None]); print(f"{len(erg)} Paare geprueft; p_gleich Median {np.median(p):.2f}, unter 0,5: {(p < 0.5).sum()}")
    return 0


if __name__ == "__main__": sys.exit(main())
