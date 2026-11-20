#!/usr/bin/env python3
"""bildsuche_paare.py <bilder-ordner> --aus <paare.txt> [--k 40] [--liste namen.txt] [--pruefen-db <db>]

Paarvorauswahl per Bildsuche (Recherche 19.11.2026 Punkt 6): statt alle Paare (Martinstor 305 000) durch einen teuren Abgleich (FlexGlue ~0,17 s je Paar) zu schicken,
nur die k aehnlichsten Bilder je Bild. Merkmal: DINOv2-base (facebook/dinov2-base, Apache-2.0) - GeM-gepoolte Patch-Merkmale + CLS, L2-normiert, Kosinus-Aehnlichkeit.
Lizenzsauber gewaehlt statt MegaLoc (Trainingsdaten-Weitergabe ungeklaert).
--pruefen-db: Trefferquote = Anteil der von SIFT bestaetigten Paare (>= 15 Inlier) der Datenbank, die in der Liste stehen.
GPU: ~1,5 GB (fp16, 448 px)."""
import os, sys, argparse, sqlite3, numpy as np
os.environ.setdefault("HF_HOME", "/media/oem/scan/hf_cache")


def merkmale(ordner, namen, groesse=448, stapel=16):
    import torch, cv2
    from transformers import AutoModel
    m = AutoModel.from_pretrained("facebook/dinov2-base", torch_dtype=torch.float16).cuda().eval()
    mittel = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1).cuda().half(); streu = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1).cuda().half(); aus = []
    for i in range(0, len(namen), stapel):
        B = []
        for n in namen[i:i + stapel]:
            b = cv2.imread(os.path.join(ordner, n), cv2.IMREAD_COLOR)
            b = np.zeros((groesse, groesse, 3), np.uint8) if b is None else cv2.resize(cv2.cvtColor(b, cv2.COLOR_BGR2RGB), (groesse, groesse), interpolation=cv2.INTER_AREA)
            B.append(b)
        x = (torch.from_numpy(np.stack(B)).cuda().permute(0, 3, 1, 2).half() / 255 - mittel) / streu
        with torch.inference_mode():
            h = m(pixel_values=x).last_hidden_state.float(); cls, pt = h[:, 0], h[:, 1:]
            gem = pt.clamp(min=1e-6).pow(3).mean(1).pow(1 / 3)                         # GeM-Pooling (p = 3) ueber die Patches
            v = torch.cat([torch.nn.functional.normalize(cls, dim=1), torch.nn.functional.normalize(gem, dim=1)], 1)
        aus.append(torch.nn.functional.normalize(v, dim=1).cpu().numpy())
    return np.concatenate(aus)


def paare_topk(V, k):
    S = V @ V.T; np.fill_diagonal(S, -1); idx = np.argsort(-S, 1)[:, :k]; P = set()
    for i in range(len(V)):
        for j in idx[i]: P.add((min(i, j), max(i, j)))
    return sorted(P)


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("ordner"); ap.add_argument("--aus", required=True); ap.add_argument("--k", type=int, default=40); ap.add_argument("--liste"); ap.add_argument("--pruefen-db")
    a = ap.parse_args(argv)
    namen = [l.strip() for l in open(a.liste)] if a.liste else sorted(n for n in os.listdir(a.ordner) if n.lower().endswith((".jpg", ".jpeg", ".png")))
    if a.pruefen_db and not a.liste:
        c = sqlite3.connect(f"file:{a.pruefen_db}?mode=ro", uri=True); namen = [n for (n,) in c.execute("select name from images order by image_id")]
    V = merkmale(a.ordner, namen); np.save(a.aus + ".npy", V)
    for k in sorted({a.k, 10, 20, 40, 80}):
        P = paare_topk(V, k)
        if k == a.k: open(a.aus, "w").write("".join(f"{namen[i]} {namen[j]}\n" for i, j in P))
        msg = f"k {k}: {len(P)} Paare"
        if a.pruefen_db:
            c = sqlite3.connect(f"file:{a.pruefen_db}?mode=ro", uri=True); nm = dict(c.execute("select image_id, name from images")); ix = {n: i for i, n in enumerate(namen)}; S = set(P); ok = n = 0
            for pid, in c.execute("select pair_id from two_view_geometries where rows >= 15"):
                j = pid % 2147483647; i = (pid - j) // 2147483647; a_, b_ = ix.get(nm[i]), ix.get(nm[j])
                if a_ is None or b_ is None: continue
                n += 1; ok += (min(a_, b_), max(a_, b_)) in S
            msg += f", enthaelt {ok} von {n} SIFT-bestaetigten Paaren ({100 * ok / max(1, n):.1f} %)"
        print(msg, flush=True)
    return 0


if __name__ == "__main__": sys.exit(main())
