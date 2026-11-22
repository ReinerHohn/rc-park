import sys; sys.path.insert(0, "/tmp/claude-29999/-home-oem-git-rc-park/dc62add2-9ee3-4f76-85e0-42c96eea284b/scratchpad/e")
from lib import *
import collections
gp = set(json.load(open(S + "obj22/audit/kamera_plausibel.json"))["ausschliessen"])


def gruppe(n):
    g = n.split("__")[0]
    if g == "eigen":
        b = n.split("__", 1)[1]
        return "eigen_IMG" if b.startswith("IMG") else ("eigen_vf" if b.startswith("vf_") else ("eigen_od" if b.startswith("od_") else "eigen_nr"))
    return g


for teil, pfad in [("teil0", B22 + "seiten_modelle/teil0_b/0"), ("teil1", B22 + "seiten_modelle/teil1_b/0")]:
    r = pycolmap.Reconstruction(pfad); P = {pid: p.xyz for pid, p in r.points3D.items()}
    rows = []
    for im in r.images.values():
        cam = im.camera; prm = np.array(cam.params); W = max(cam.width, cam.height)
        e = []
        for p2 in im.points2D:
            if p2.has_point3D():
                q = im.project_point(P[p2.point3D_id])
                if q is not None: e.append(np.linalg.norm(np.asarray(q) - np.asarray(p2.xy)))
        n = stamm(im.name)
        rows.append(dict(n=n, g=gruppe(n), f=prm[0] / W, k=prm[3], cx=(prm[1] - cam.width / 2) / W, cy=(prm[2] - cam.height / 2) / W, err=np.median(e) if e else np.nan,
                         nobs=len(e), tief=n in gp, cid=im.camera_id))
    print("=====", teil, len(rows), "Bilder,", len({x['cid'] for x in rows}), "Kameras")
    G = collections.defaultdict(list)
    for x in rows: G[x["g"]].append(x)
    fm_all = np.median([x["f"] for x in rows])
    for g, L_ in sorted(G.items(), key=lambda kv: -len(kv[1])):
        f = np.array([x["f"] for x in L_]); k = np.array([x["k"] for x in L_]); e = np.array([x["err"] for x in L_]); t = np.array([x["tief"] for x in L_])
        fm = np.median(f); aus = [x for x in L_ if abs(x["f"] / fm - 1) > 0.10 or abs(x["k"] - np.median(k)) > 0.1]
        print(f"  {g:28s} n {len(L_):3d} Kameras {len({x['cid'] for x in L_}):3d} f/W median {fm:.3f} (p10 {np.percentile(f,10):.3f} p90 {np.percentile(f,90):.3f}) k median {np.median(k):+.3f} "
              f"| Reproj median {np.nanmedian(e):.2f} px p90 {np.nanpercentile(e,90):.2f} | tief {t.sum()} | Intrinsik-Ausreisser {len(aus)}"
              + (f" (davon tief {sum(x['tief'] for x in aus)})" if aus else ""))
    # tiefe vs nicht tiefe
    for lab, sel in [("tief", [x for x in rows if x["tief"]]), ("normal", [x for x in rows if not x["tief"]])]:
        if sel: print(f"  {lab}: n {len(sel)} Reproj median {np.nanmedian([x['err'] for x in sel]):.2f} px, |f/Gruppenmedian-1| median {np.median([abs(x['f']/np.median([y['f'] for y in G[x['g']]])-1) for x in sel]):.3f}, Beob median {np.median([x['nobs'] for x in sel]):.0f}")
    json.dump(rows, open(S + f"e/expB_{teil}.json", "w"), default=float)
