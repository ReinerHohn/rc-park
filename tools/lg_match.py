#!/usr/bin/env python3
"""lg_match.py - Merkmale + Zuordnungen mit ALIKED + LightGlue (gelernter Matcher) fuer grosse Blickwinkel (Luftbild gegen Strasse).

Lizenz (modelle/LIZENZ_WERKZEUGE.md): LightGlue Apache-2.0; ALIKED-Gewichte BSD-3-Clause; DISK Apache-2.0. SuperPoint (Magic Leap)
ist NICHT kommerziell - hier bewusst nicht waehlbar. Laeuft in der torch-Umgebung (venv-seg), schreibt eine npz, die
tools/sfm_netz.py --matcher lightglue in die COLMAP-Datenbank uebernimmt.
  /media/oem/scan/venv-seg/bin/python -I tools/lg_match.py <bilderordner> <ausgabe.npz> [--namen a.jpg b.jpg ...] [--extractor aliked|disk]
        [--max-kp 4096] [--resize 2048] [--min-matches 15]
npz: kp_<name> (N,2 float32, Pixel im Bild wie gespeichert), m_<a>|<b> (M,2 int32 Indexpaare), namen (Liste), meta (json).
"""
import sys, os, json, argparse, itertools, time, numpy as np, torch
from lightglue import LightGlue, ALIKED, DISK
from lightglue.utils import load_image, rbd

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("ordner"); ap.add_argument("ausgabe"); ap.add_argument("--namen", nargs="*")
    ap.add_argument("--extractor", default="aliked", choices=["aliked", "disk"]); ap.add_argument("--max-kp", type=int, default=4096)
    ap.add_argument("--resize", type=int, default=2048); ap.add_argument("--min-matches", type=int, default=15)
    a = ap.parse_args(); dev = "cuda" if torch.cuda.is_available() else "cpu"
    vmb = int(os.environ.get("RCPARK_LG_VRAM_MB", "0"))               # 22.11.2026 (bruecke_nachmatchen.py): harte VRAM-Obergrenze dieses Prozesses (torch-Zuteiler), 0 = keine
    if vmb and dev == "cuda": torch.cuda.set_per_process_memory_fraction(min(1.0, vmb / (torch.cuda.get_device_properties(0).total_memory / 2**20)))
    namen = a.namen or sorted(f for f in os.listdir(a.ordner) if f.lower().endswith((".jpg", ".jpeg", ".png")))
    ext = (ALIKED(max_num_keypoints=a.max_kp) if a.extractor == "aliked" else DISK(max_num_keypoints=a.max_kp)).eval().to(dev)
    matcher = LightGlue(features=a.extractor, mp=os.environ.get("RCPARK_LG_MP", "1") != "0").eval().to(dev)   # 20.11.2026 gemischte Genauigkeit: -22 % Zeit, 99,2 % identische Zuordnungen, RANSAC-Inlier +1 % (tools/versuche/lg_mp_ab2.py); RCPARK_LG_MP=0 = alter Stand
    feats = {}; t0 = time.time()
    for n in namen:
        img = load_image(os.path.join(a.ordner, n)); H, W = img.shape[-2:]
        with torch.no_grad(): f = ext.extract(img.to(dev), resize=a.resize)
        feats[n] = f; print(f"  {n}: {W}x{H}, {f['keypoints'].shape[1]} Merkmale", flush=True)
    print(f"Merkmale {time.time() - t0:.0f} s auf {dev}", flush=True)
    out = {"namen": np.array(namen)}; meta = dict(extractor=a.extractor, max_kp=a.max_kp, resize=a.resize, paare={})
    for n in namen: out["kp_" + n] = feats[n]["keypoints"][0].cpu().numpy().astype(np.float32)   # bereits auf Originalgroesse zurueckskaliert
    t0 = time.time(); npaar = 0
    for a_, b_ in itertools.combinations(namen, 2):
        with torch.no_grad(): m = matcher({"image0": feats[a_], "image1": feats[b_]})
        idx = m["matches"][0].cpu().numpy().astype(np.int32)
        if len(idx) >= a.min_matches: out[f"m_{a_}|{b_}"] = idx; npaar += 1
        meta["paare"][f"{a_}|{b_}"] = int(len(idx))
    print(f"Zuordnung {time.time() - t0:.0f} s: {npaar} Paare mit >= {a.min_matches} Matches von {len(namen) * (len(namen) - 1) // 2}", flush=True)
    out["meta"] = np.array(json.dumps(meta)); np.savez_compressed(a.ausgabe, **out); print("geschrieben:", a.ausgabe)

if __name__ == "__main__":
    main()
