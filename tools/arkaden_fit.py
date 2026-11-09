"""arkaden_fit.py - Arkadenboegen als FORMFAMILIE statt freier Kettenbildung (Koordinator 9.11., Runde 3).
Eingabe: Gitter mit "saeulen" [{cx,cy,R,z_fuss,z_kopf}], ein oder mehrere Sweeps (P, ref). Fuer jedes benachbarte Pfeilerpaar (Abstand dmin-dmax, keine dritte
Achse naeher als 1 m an der Verbindungslinie): vertikale Ebene durch beide Achsen, Sweep-Punkte innerhalb +-band der Ebene, z >= z_kopf_min - 0,5, zwischen den
Pfeilerraendern; nur Paare laengs der Reihenachse (Hauptachse der Pfeilerlagen, Winkel < reihe_winkel). Darin GPU-Gittersuche (Inlier bei tol 4 cm, nur Punkte oberhalb des Zentrums/der Kaempferlinie):
  (a) Kreisbogen: Zentrum auf der Mittelsenkrechten (s = Mitte), zc und R frei;
  (b) Spitzbogen: zwei Kreise, Zentren auf der Kaempferlinie z = zk bei s_m +- d, R = W/2 + d (gemeinsame Spitze), zk und d frei.
Modellwahl: Spitzbogen nur, wenn er die Ausreisser unter den bogennahen Punkten (< 15 cm) gegenueber dem Kreisbogen HALBIERT (0,5-Regel), sonst Kreisbogen.
Gleichheitsregel: alle Boegen einer Reihe gleicher Typ (Mehrheit) und Radius (Median), wenn |R - Median| < 10 cm -> R fest, zc/zk neu gesucht.
Fotopruefung (gitter_kurven.fotopruefung mit Z-Puffer): Bogen gilt nur mit >= nmin sichtbaren Ja-Fotos.
Ausgabe: OUT.json {"segmente": Polylinien quelle 15 [p0,p1,15,score], "arkaden": [...]} + OUT.bericht.json.
Aufruf: arkaden_fit.py GITTER.json SWEEP.npz[,SWEEP2,...] OUT.json [--kam KAM --stabil DIR --wolke KANTEN.npz] [--band 0.25] [--tol 0.04] [--dmin 3] [--dmax 8] [--nmin 3]"""
import sys, os, json, time, argparse
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
import numpy as np, torch
sys.path.insert(0, __file__.rsplit("/", 1)[0]); from gitter_kurven import fotopruefung
DEV = "cuda"; Q_ARKADE = 15


def lade_sweeps(pfade):
    P = []
    for sw in pfade.split(","):
        z = np.load(sw); P.append(z["P"].astype(np.float32))
    return np.concatenate(P)


def inlier_rund(S, Z, zc_grid, R_grid, tol):
    """S,Z: Punktkoordinaten in der Ebene (s relativ zur Mitte s_m -> s' = s - s_m). Inlier je (zc, R): | sqrt(s'^2 + (z-zc)^2) - R | < tol und z >= zc."""
    best = (-1, None, None)
    for zc in zc_grid:
        d = torch.sqrt(S ** 2 + (Z - zc) ** 2); ob = Z >= zc                                      # (N,)
        n = ((d[None] - R_grid[:, None]).abs() < tol) & ob[None]                                   # (nR, N)
        c = n.sum(1); i = int(c.argmax())
        if int(c[i]) > best[0]: best = (int(c[i]), float(zc), float(R_grid[i]))
    return best


def inlier_spitz(S, Z, W, zk_grid, d_grid, tol):
    """Spitzbogen: linker Bogen Zentrum (+d, zk) fuer s' < 0, rechter Zentrum (-d, zk) fuer s' >= 0, R = W/2 + d; Inlier bei z >= zk."""
    best = (-1, None, None)
    for zk in zk_grid:
        ob = Z >= zk; dz2 = (Z - zk) ** 2
        sc = torch.where(S < 0, S[None] - d_grid[:, None], S[None] + d_grid[:, None])            # (nd, N) Abstand in s zum jeweiligen Zentrum
        dist = torch.sqrt(sc ** 2 + dz2[None]); R = (W / 2 + d_grid)[:, None]
        n = ((dist - R).abs() < tol) & ob[None]; c = n.sum(1); i = int(c.argmax())
        if int(c[i]) > best[0]: best = (int(c[i]), float(zk), float(d_grid[i]))
    return best


def punkte_rund(zc, R, W, abtast):
    """Kreisbogen zwischen den Kaempfern bei s' = +-W/2 (falls R >= W/2), sonst Halbkreis; Rueckgabe (s', z) Abtastung."""
    if R <= W / 2 + 1e-6: th0 = 0.0
    else: th0 = np.arccos(min(1.0, (W / 2) / R))
    th = np.linspace(th0, np.pi - th0, max(3, int((np.pi - 2 * th0) * R / abtast) + 1))
    return np.stack([R * np.cos(th), zc + R * np.sin(th)], 1)


def punkte_spitz(zk, d, W, abtast):
    R = W / 2 + d; th0 = np.arccos(min(1.0, d / R)) if R > 0 else 0.0                              # Spitze bei s'=0: cos(th) = d/R
    thl = np.linspace(np.pi - th0, np.pi, max(3, int(th0 * R / abtast) + 1))                      # linker Bogen (Zentrum +d): von Kaempfer (-W/2, zk) bis Spitze
    L = np.stack([d + R * np.cos(thl), zk + R * np.sin(thl)], 1)
    thr = np.linspace(0.0, th0, max(3, int(th0 * R / abtast) + 1))[::-1]
    Rr = np.stack([-d + R * np.cos(thr), zk + R * np.sin(thr)], 1)                                 # rechter Bogen: von Spitze bis Kaempfer (+W/2, zk)
    return np.vstack([L, Rr[1:]])


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("gitter"); ap.add_argument("sweeps"); ap.add_argument("out")
    ap.add_argument("--kam"); ap.add_argument("--stabil"); ap.add_argument("--wolke"); ap.add_argument("--band", type=float, default=0.25); ap.add_argument("--tol", type=float, default=0.04)
    ap.add_argument("--dmin", type=float, default=3.0); ap.add_argument("--dmax", type=float, default=8.0); ap.add_argument("--nmin", type=int, default=3); ap.add_argument("--abtast", type=float, default=0.10)
    ap.add_argument("--gleich", type=float, default=0.10); ap.add_argument("--reihe_winkel", type=float, default=25.0); ap.add_argument("--gpu_mb", type=int, default=2000); a = ap.parse_args()
    t0 = time.time(); torch.cuda.set_per_process_memory_fraction(min(1.0, a.gpu_mb / (torch.cuda.get_device_properties(0).total_memory / 2 ** 20)))
    G = json.load(open(a.gitter)); SA = G["saeulen"]; P = lade_sweeps(a.sweeps); Pt = torch.as_tensor(P, device=DEV)
    print("Pfeiler", len(SA), "| Sweep-Punkte", len(P))
    ax = np.array([[s["cx"], s["cy"]] for s in SA]); paare = []; verworfen_reihe = []
    _, _, vt = np.linalg.svd(ax - ax.mean(0)); achse = vt[0]                                     # Reihenachse = Hauptachse der Pfeilerlagen (keine Objektkonstante)
    for i in range(len(SA)):
        for j in range(i + 1, len(SA)):
            L = np.linalg.norm(ax[j] - ax[i])
            if not (a.dmin <= L <= a.dmax): continue
            e = (ax[j] - ax[i]) / L; n2 = np.array([-e[1], e[0]]); dritte = False
            if abs(e @ achse) < np.cos(np.radians(a.reihe_winkel)): verworfen_reihe.append((i, j, round(float(np.degrees(np.arccos(abs(e @ achse)))), 0))); continue   # Quer-/Diagonalpaar (Lauf 2: 0-1, 2-3, 3-4 kreuzten die Oeffnungen)
            for k in range(len(SA)):
                if k in (i, j): continue
                v = ax[k] - ax[i]; t_ = v @ e; q = abs(v @ n2)
                if -0.5 < t_ < L + 0.5 and q < 1.0: dritte = True
            if not dritte: paare.append((i, j, L, e, n2))
    print("Pfeilerpaare (%.0f-%.0f m, keine dritte Achse dazwischen, Winkel zur Reihenachse < %.0f Grad): %d" % (a.dmin, a.dmax, a.reihe_winkel, len(paare)), [(i, j, round(L, 2)) for i, j, L, _, _ in paare], "| verworfen (quer/diagonal, Winkel):", verworfen_reihe)
    arkaden = []
    for (i, j, L, e, n2) in paare:
        A = SA[i]; B = SA[j]; zk0 = min(A["z_kopf"], B["z_kopf"]); sa = A["R"]; sb = L - B["R"]; W = sb - sa; sm = (sa + sb) / 2
        et = torch.tensor(e, device=DEV, dtype=torch.float32); nt = torch.tensor(n2, device=DEV, dtype=torch.float32); o = torch.tensor(ax[i], device=DEV, dtype=torch.float32)
        rel = Pt[:, :2] - o; q = rel @ nt; s_ = rel @ et; z = Pt[:, 2]
        m = (q.abs() <= a.band) & (z >= zk0 - 2.5) & (z <= zk0 + W / 2 + 2.5) & (s_ >= sa - 0.1) & (s_ <= sb + 0.1)
        S = s_[m] - sm; Z = z[m]; N = int(m.sum())
        if N < 50: print("Paar %d-%d: nur %d Punkte, uebersprungen" % (i, j, N)); continue
        zc_grid = torch.arange(zk0 - 4.0, zk0 + 2.0, 0.02, device=DEV); R_grid = torch.arange(0.5, max(0.6, W / 2 + 2.0), 0.02, device=DEV)
        n_r, zc, R = inlier_rund(S, Z, zc_grid, R_grid, a.tol)
        zk_grid = torch.arange(zk0 - 1.5, zk0 + 2.0, 0.02, device=DEV); d_grid = torch.arange(0.0, W / 2 + 0.01, 0.02, device=DEV)
        n_s, zk, d = inlier_spitz(S, Z, W, zk_grid, d_grid, a.tol)
        # 0,5-Regel auf den bogennahen Punkten (< 15 cm von einem der beiden Modelle)
        d_r = (torch.sqrt(S ** 2 + (Z - zc) ** 2) - R).abs(); d_r = torch.where(Z >= zc, d_r, torch.full_like(d_r, 9.0))
        sc = torch.where(S < 0, S - d, S + d); d_s = (torch.sqrt(sc ** 2 + (Z - zk) ** 2) - (W / 2 + d)).abs(); d_s = torch.where(Z >= zk, d_s, torch.full_like(d_s, 9.0))
        nah = (d_r < 0.15) | (d_s < 0.15); aus_r = int((nah & (d_r >= a.tol)).sum()); aus_s = int((nah & (d_s >= a.tol)).sum())
        typ = "spitz" if (aus_s <= 0.5 * aus_r and n_s > n_r) else "rund"
        arkaden.append(dict(pfeiler=[i, j], abstand_m=float(L), spannweite_m=float(W), n_punkte=N, rund=dict(inlier=n_r, zc=zc, R=R, ausreisser_nah=aus_r),
                            spitz=dict(inlier=n_s, zk=zk, d=d, R=float(W / 2 + d), ausreisser_nah=aus_s), typ=typ, _geo=(e, n2, ax[i], sm), _SZ=(S, Z)))
        print("Paar %d-%d  L %.2f W %.2f N %d | rund: inlier %d zc %.2f R %.2f (Ausreisser nah %d) | spitz: inlier %d zk %.2f d %.2f R %.2f (Ausreisser nah %d) -> %s"
              % (i, j, L, W, N, n_r, zc, R, aus_r, n_s, zk, d, W / 2 + d, aus_s, typ))
    def zk0_von(k): return min(SA[k["pfeiler"][0]]["z_kopf"], SA[k["pfeiler"][1]]["z_kopf"])
    # Gleichheitsregel je Reihe (alle Paare = eine Reihe; Typ = Mehrheit, R = Median)
    if arkaden:
        typen = [k["typ"] for k in arkaden]; typ_reihe = max(set(typen), key=typen.count)
        Rs = np.array([k[typ_reihe]["R"] for k in arkaden]); Rmed = float(np.median(Rs))
        print("Gleichheitsregel: Typ Mehrheit = %s, Radien %s, Median %.2f" % (typ_reihe, np.round(Rs, 2).tolist(), Rmed))
        for k in arkaden:
            S, Z = k["_SZ"]; W = k["spannweite_m"]; k["typ_einzeln"] = k["typ"]; k["R_einzeln"] = k[k["typ"]]["R"]
            gleich = abs(k[typ_reihe]["R"] - Rmed) < a.gleich
            k["typ"] = typ_reihe; k["gleich"] = bool(gleich)
            if typ_reihe == "rund":
                zc_grid = torch.arange(zk0_von(k) - 4.0, zk0_von(k) + 2.0, 0.01, device=DEV); n_, zc, _ = inlier_rund(S, Z, zc_grid, torch.tensor([Rmed], device=DEV), a.tol)
                k["rund_fest"] = dict(inlier=n_, zc=zc, R=Rmed)
                if gleich or n_ >= 0.7 * k["rund"]["inlier"]:                                   # R fest (Reihe); auch fuer 'ungleiche', wenn der feste Radius >= 70 % der Inlier des freien Fits haelt (freier Fit = meist fremde Struktur)
                    k["erzwungen"] = not gleich; k["rund"].update(inlier=n_, zc=zc, R=Rmed)
                k.update(R=k["rund"]["R"], inlier=k["rund"]["inlier"], zc=k["rund"]["zc"])
            else:
                k["erzwungen"] = False
                if gleich:                                                                       # R fest -> d = Rmed - W/2 fest, zk neu
                    d = max(0.0, Rmed - W / 2); zk_grid = torch.arange(k["spitz"]["zk"] - 0.5, k["spitz"]["zk"] + 0.5, 0.01, device=DEV)
                    n_, zk, _ = inlier_spitz(S, Z, W, zk_grid, torch.tensor([d], device=DEV), a.tol); k["spitz"].update(inlier=n_, zk=zk, d=d, R=float(W / 2 + d))
                k.update(R=k["spitz"]["R"], inlier=k["spitz"]["inlier"], zk=k["spitz"]["zk"], d=k["spitz"]["d"])
    # Polylinien in 3D
    stuecke = []
    for k in arkaden:
        e, n2, o, sm = k["_geo"]; W = k["spannweite_m"]
        sz = punkte_rund(k["zc"], k["R"], W, a.abtast) if k["typ"] == "rund" else punkte_spitz(k["zk"], k["d"], W, a.abtast)
        xy = o[None] + (sm + sz[:, 0])[:, None] * e[None]; P3 = np.column_stack([xy, sz[:, 1]]); k["punkte"] = P3.tolist(); k["laenge_m"] = float(np.linalg.norm(np.diff(P3, axis=0), axis=1).sum())
        if k["typ"] == "rund": k["zentrum"] = (np.r_[o + sm * e, k["zc"]]).tolist()
        else: k["zentren"] = [(np.r_[o + (sm + k["d"]) * e, k["zk"]]).tolist(), (np.r_[o + (sm - k["d"]) * e, k["zk"]]).tolist()]
        stuecke.append(k)
    fotos_benutzt = 0
    if a.kam and stuecke:
        kam = json.load(open(a.kam)); wolke = None
        if a.wolke: w_ = np.load(a.wolke); wolke = (w_["P"] if hasattr(w_, "files") else w_)[:, :3]
        ja, nein, fotos_benutzt = fotopruefung(stuecke, kam, a.stabil, wolke=wolke)
        for k, j_, n_ in zip(stuecke, ja, nein): k.update(fotos_ja=int(j_), fotos_nein=int(n_), fotobelegt=bool(j_ >= a.nmin))
        print("Fotopruefung (%d Fotos): ja/nein je Bogen" % fotos_benutzt, [(k["pfeiler"], k["fotos_ja"], k["fotos_nein"]) for k in stuecke])
    seg = []
    for k in stuecke:
        if a.kam and not k["fotobelegt"]: continue
        sc = round(k["fotos_ja"] / max(k["fotos_ja"] + k["fotos_nein"], 1), 3) if "fotos_ja" in k else round(k["inlier"] / max(k["n_punkte"], 1), 3); pts = k["punkte"]
        for i_ in range(len(pts) - 1): seg.append([pts[i_], pts[i_ + 1], Q_ARKADE, sc])
    out_ark = [{kk: v for kk, v in k.items() if not kk.startswith("_")} for k in stuecke]
    json.dump({"segmente": seg, "arkaden": out_ark}, open(a.out, "w"))
    json.dump(dict(parameter=vars(a), paare=len(paare), arkaden=len(out_ark), fotobelegt=sum(1 for k in out_ark if k.get("fotobelegt", True)), segmente=len(seg), fotos_benutzt=fotos_benutzt, zeit_s=time.time() - t0),
              open((a.out[:-5] if a.out.endswith(".json") else a.out) + ".bericht.json", "w"), indent=1)
    print("Arkaden %d, fotobelegt %d, Segmente %d, %.1f s -> %s" % (len(out_ark), sum(1 for k in out_ark if k.get("fotobelegt", True)), len(seg), time.time() - t0, a.out))


if __name__ == "__main__":
    main()
