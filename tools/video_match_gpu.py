#!/usr/bin/env python3
"""video_match_gpu.py - Deskriptor-Matching Videoframes x Strassenfotos auf der GPU (torch), zu video_ausrichten.py --modus dump/fit.
  /media/oem/scan/venv-seg/bin/python -I tools/video_match_gpu.py <video_sfm_ordner> [--ratio 0.85]   (liest match_dump.npz, schreibt paare.json)
"""
import sys, os, json, argparse, numpy as np, torch

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("video"); ap.add_argument("--ratio", type=float, default=0.85); a = ap.parse_args()
    Z = np.load(os.path.join(a.video, "match_dump.npz")); dev = "cuda" if torch.cuda.is_available() else "cpu"; nv = len(Z["vnames"]); nn = len(Z["nnames"])
    N = [(torch.tensor(Z[f"N{k}_d"], dtype=torch.float32, device=dev) / 512.0, Z[f"N{k}_i"]) for k in range(nn)]; paare = {}; npaar = 0
    print(f"{nv} Frames x {nn} Fotos auf {dev}", flush=True)
    for i in range(nv):
        ids = Z[f"V{i}_i"]
        if (ids >= 0).sum() < 30: continue
        tv = torch.tensor(Z[f"V{i}_d"], dtype=torch.float32, device=dev) / 512.0
        for tn, idn in N:
            sim = tv @ tn.T; v2, i2 = sim.topk(2, dim=1); ok = torch.acos(v2[:, 0].clamp(-1, 1)) < a.ratio * torch.acos(v2[:, 1].clamp(-1, 1))
            mut = sim.argmax(0)[i2[:, 0]] == torch.arange(len(tv), device=dev); m = (ok & mut).nonzero().squeeze(1).cpu().numpy()
            if len(m) < 12: continue
            j = i2[m, 0].cpu().numpy(); pv = ids[m]; pn = idn[j]; g = (pv >= 0) & (pn >= 0)
            for x, y in zip(pv[g], pn[g]): paare[f"{int(x)},{int(y)}"] = paare.get(f"{int(x)},{int(y)}", 0) + 1
            npaar += 1
    json.dump(dict(bildpaare=npaar, paare=paare), open(os.path.join(a.video, "paare.json"), "w")); print(f"{npaar} Bildpaare, {len(paare)} 3D-3D-Paare")

if __name__ == "__main__":
    main()
