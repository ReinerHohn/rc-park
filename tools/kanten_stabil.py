"""Kanten-Stabilitaet je Foto (GPU): viele Vorverarbeitungen x Masstaebe x Schwellen, jede Kante bekommt den Anteil der Laeufe, in denen sie steht (Peak = stabil).
Vorverarbeitung: Kanaele (Grau,L,a,b,S,V,R,G,B) x Ton (Original, Gamma 0.5/2, CLAHE, lokale Kontrastnormierung = Helligkeits-/Kontrast-Sweep), Masstab sigma 1/2/3,
Schwelle: oberste q % der unterdrueckten Gradientenpixel (q 3/5/8) mit Hysterese. Ergebnis votes[H,W] in 0..1 (Toleranz 1 px) und Laeufe-Zahl.
Aufruf als Modul: stabilkarte(bgr, breite=1500) -> (votes, n_laeufe)."""
import numpy as np, cv2, torch, torch.nn.functional as Fn
dev = "cuda"
def gauss(x, s):
    r = int(3 * s + 1); t = torch.arange(-r, r + 1, device=x.device, dtype=torch.float32); k = torch.exp(-t * t / (2 * s * s)); k /= k.sum()
    x = Fn.conv2d(Fn.pad(x, (r, r, 0, 0), mode="reflect"), k.view(1, 1, 1, -1)); return Fn.conv2d(Fn.pad(x, (0, 0, r, r), mode="reflect"), k.view(1, 1, -1, 1))
SX = torch.tensor([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=torch.float32, device=dev).view(1, 1, 3, 3) / 8
def nms_kanten(x, q, gen=3):
    gx = Fn.conv2d(Fn.pad(x, (1, 1, 1, 1), mode="replicate"), SX); gy = Fn.conv2d(Fn.pad(x, (1, 1, 1, 1), mode="replicate"), SX.transpose(2, 3)); m = (gx * gx + gy * gy).sqrt()
    ang = torch.atan2(gy, gx); d = ((ang / (np.pi / 4)).round().long() % 4)                       # 0:horizontal 1:diag 2:vertikal 3:diag
    sh = [(0, 1), (1, 1), (1, 0), (1, -1)]; keep = torch.zeros_like(m, dtype=torch.bool); mp = Fn.pad(m, (1, 1, 1, 1))
    for k, (dy, dx) in enumerate(sh):
        a = mp[..., 1 + dy:1 + dy + m.shape[2], 1 + dx:1 + dx + m.shape[3]]; b = mp[..., 1 - dy:1 - dy + m.shape[2], 1 - dx:1 - dx + m.shape[3]]; keep |= (d == k) & (m >= a) & (m >= b)
    mm = m * keep; v = mm[mm > 0]
    if v.numel() < 100: return torch.zeros_like(keep)
    v = v[torch.randint(0, v.numel(), (min(v.numel(), 800000),), device=x.device)]; hi = torch.quantile(v, 1 - q); lo = torch.quantile(v, 1 - 2.2 * q)
    st = mm >= hi; sw = mm >= lo
    for _ in range(gen): st = (Fn.max_pool2d(st.float(), 3, 1, 1) > 0) & sw                      # Hysterese (Naeherung): schwache Kante nur nahe starker
    return st
def varianten(bgr):
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB); hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV); gr = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    ch = {"gray": gr, "L": lab[..., 0], "a": lab[..., 1], "b": lab[..., 2], "S": hsv[..., 1], "V": hsv[..., 2], "R": bgr[..., 2], "G": bgr[..., 1], "B": bgr[..., 0]}
    cl = {c: cv2.createCLAHE(clipLimit=c, tileGridSize=(8, 8)) for c in (2.0, 5.0)}; out = []
    for n, c in ch.items():
        f = c.astype(np.float32) / 255; out.append((n + "/orig", f))
        if n in ("gray", "L", "V", "G"):
            out += [(n + "/g0.5", f ** 0.5), (n + "/g2", f ** 2)] + [(n + "/clahe%g" % k, cl[k].apply(c).astype(np.float32) / 255) for k in cl]
            t = torch.from_numpy(f).to(dev)[None, None]; mu = gauss(t, 12); sd = gauss((t - mu) ** 2, 12).sqrt().clamp(min=0.02); out.append((n + "/lokal", ((t - mu) / sd)[0, 0].cpu().numpy() * 0.2 + 0.5))
    return out
@torch.no_grad()
def stabilkarte(bgr, breite=1500, sigmas=(1.0, 2.0, 3.0), qs=(0.03, 0.05, 0.08), detail=False):
    h, w = bgr.shape[:2]; bgr = cv2.resize(bgr, (breite, int(h * breite / w)), interpolation=cv2.INTER_AREA); V = varianten(bgr); acc = None; n = 0; fam = {}
    for nm, f in V:
        t = torch.from_numpy(np.ascontiguousarray(f)).to(dev)[None, None].float(); a2 = torch.zeros_like(t, dtype=torch.float32)
        for s in sigmas:
            g = gauss(t, s)
            for q in qs: a2 += Fn.max_pool2d(nms_kanten(g, q).float(), 3, 1, 1)
        k = len(sigmas) * len(qs); fam[nm] = (a2 / k)[0, 0]; acc = a2 if acc is None else acc + a2; n += k
    v = (acc / n)[0, 0].cpu().numpy()
    return (v, n, {k: x.cpu().numpy() for k, x in fam.items()}) if detail else (v, n)
if __name__ == "__main__":
    import sys, time; t0 = time.time(); im = cv2.imread(sys.argv[1], cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION); v, n = stabilkarte(im)
    print("Laeufe", n, "%.1fs" % (time.time() - t0), "Peaks>=0.5:", int((v >= 0.5).sum()), "max", float(v.max())); np.save(sys.argv[2], v.astype(np.float16))
    cv2.imwrite(sys.argv[2].replace(".npy", ".jpg"), (255 * np.clip(v * 1.6, 0, 1)).astype(np.uint8))
