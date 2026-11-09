#!/usr/bin/env python3
"""kaempfer_sweep.py - Kaempferhoehe und Pfostenlagen der Fenstergruppen per Sweep ueber ALLE Gruppen gemeinsam, zwei getrennte Quellen (nie gemischt):
  foto : Kantenstuetzung (Stabilitaetskarten) aller Fotos vor der Front, Kontrast = Linie minus dieselbe Linie 0,1 m versetzt (freie Flaeche)
  wolke: Punktdichte der dichten Wolke in einer Scheibe +-6 cm um die Fassadenebene entlang der Linie, Kontrast wie oben
Gesucht: z_kaempfer (alle Gruppen gleich), Pfostenraster je Gruppe = Mitte + dx (alle gleich) + i*w_licht (i = -n/2..n/2), w_licht und dx gemeinsam.
Aggregation: Median ueber die Gruppen (Wiederholungsprior). Entscheidung je Quelle (Schwellen wie muster_fit --pruefen, Auftrag Koordinator):
  Spitze - Median >= 3 MAD im Profil; Fotos: >= 3 sehende Fotos aus >= 2 Richtungen je Gruppe; Wolke: >= 30 Punkte je Gruppe; >= 3 Gruppen.
Uebernahme nur, wenn beide Quellen entschieden UND einig (z: <= 0,05 m; dx/w_licht: <= 0,05 m), sonst offene Beobachtung mit beiden Werten, Wert bleibt.

  python -I kaempfer_sweep.py FE_v9.json KAM.json STABILDIR WOLKE.npy OUT.json [--bilder DIR --audit DIR --fotos a.jpg,b.jpg]
Ausgabe OUT.json: je Quelle Optimum, Plateau, Signifikanz, Daten; 'instanzen' (Achse, Masse, Teilungen) fuer das Beleg-Tor; 'entscheidung'."""
import sys, os, json, math, argparse
import numpy as np

KONTR = 0.10; NPT = 16; TOL_M = 0.04; SCHEIBE = 0.06


def projiziere(Q, k, sj, torch):
    R = torch.tensor(k["Rn"], device=Q.device, dtype=torch.float32); t = torch.tensor(k["tn"], device=Q.device, dtype=torch.float32)
    X = Q @ R.T + t; z = X[:, 2].clamp(min=0.3); x = X[:, 0] / z; y = X[:, 1] / z; f1 = 1 + k["params"][3] * (x * x + y * y)
    return ((k["f"] * x * f1 + k["cx"]) * sj).round().long(), ((k["f"] * y * f1 + k["cy"]) * sj).round().long(), X[:, 2] > 1


def foto_stuetzung(L, fs, KAM, karte, torch, dev, mitte):
    """L: (M, 2, 3) Linien -> mittlere Stuetzung je Linie (Punkte ganz im Bild, alle Fotos), Zahl Fotos je Linie."""
    tt = torch.linspace(0, 1, NPT, device=dev); A = torch.tensor(L[:, 0], device=dev, dtype=torch.float32); B = torch.tensor(L[:, 1], device=dev, dtype=torch.float32)
    Q = (A[:, None] + (B - A)[:, None] * tt[None, :, None]).reshape(-1, 3); H = torch.zeros(len(L), device=dev); N = torch.zeros(len(L), device=dev); nf = torch.zeros(len(L), device=dev)
    for f in fs:
        k = KAM[f]; V = karte(f); sj = V.shape[1] / k["W"]; dist = float(np.linalg.norm(np.array(k["C"]) - mitte))
        rad = int(np.clip(round(TOL_M * k["f"] * sj / max(dist, 1.0)), 1, 6)); Vm = torch.nn.functional.max_pool2d(V[None, None], 2 * rad + 1, 1, rad)[0, 0]; Hh, Ww = Vm.shape
        uu, vv, okz = projiziere(Q, k, sj, torch); ok = okz & (uu >= 0) & (uu < Ww) & (vv >= 0) & (vv < Hh); hit = torch.zeros(len(Q), device=dev); hit[ok] = Vm[vv[ok], uu[ok]]
        okk = ok.view(-1, NPT).all(1); H += torch.where(okk, hit.view(-1, NPT).sum(1), torch.zeros_like(H)); N += okk.float() * NPT; nf += okk.float()
    return (H / N.clamp(min=1)).cpu().numpy(), nf.cpu().numpy()


def wolke_dichte(L, Pw, u, n, of, torch, dev):
    """Punkte je m in einem Schlauch (Breite 0,04 m quer zur Linie in der Fassadenebene, +-SCHEIBE in der Tiefe) um jede Linie."""
    P = torch.tensor(Pw, device=dev, dtype=torch.float32); al = P @ torch.tensor(u, device=dev, dtype=torch.float32); off = P @ torch.tensor(n, device=dev, dtype=torch.float32) - of; z = P[:, 2]
    m = off.abs() < SCHEIBE; al = al[m]; z = z[m]; out = np.zeros(len(L)); cnt = np.zeros(len(L))
    for i, (p0, p1) in enumerate(L):
        a0, a1 = sorted((float(p0 @ u), float(p1 @ u))); z0, z1 = sorted((float(p0[2]), float(p1[2])))
        if a1 - a0 > z1 - z0: sel = (al >= a0) & (al <= a1) & ((z - z0).abs() < 0.02); lng = a1 - a0
        else: sel = (z >= z0) & (z <= z1) & ((al - a0).abs() < 0.02); lng = z1 - z0
        c = float(sel.sum()); cnt[i] = c; out[i] = c / max(lng, 1e-3)
    return out, cnt


def main():
    import torch, cv2
    ap = argparse.ArgumentParser(); ap.add_argument("fe"); ap.add_argument("kam"); ap.add_argument("stabil"); ap.add_argument("wolke"); ap.add_argument("out")
    ap.add_argument("--bilder"); ap.add_argument("--audit"); ap.add_argument("--fotos", default="ip_IMG_6120.jpg,ip_IMG_6261.jpg"); ap.add_argument("--dmax", type=float, default=45.0)
    ap.add_argument("--anwenden", action="store_true", help="uebernommene Werte (beide Quellen einig) in FE_v9.json schreiben (alter Wert unter fenster.vorher_sweep)")
    a = ap.parse_args(); dev = "cuda" if torch.cuda.is_available() else "cpu"
    if dev == "cuda": torch.cuda.set_per_process_memory_fraction(min(1.0, 2000 / (torch.cuda.get_device_properties(0).total_memory / 2**20)))
    D = json.load(open(a.fe)); u = np.array(D["u"]); n = np.array(D["n"]); of = D["off_front"]; F = D["fenster"]; KAM = json.load(open(a.kam))
    gr = [g for g in F["gruppen"] if g.get("belegt", True)]; nl = F["n_licht"]; wl0 = F["w_licht"]; zs, zk0, zsch = F["z_sohl"], F["z_kaempfer"], F["z_schulter"]
    W = lambda al, z, off=0.0: al * u + (of + off) * n + np.array([0, 0, z])
    log = []; L_ = lambda s: (print(s, flush=True), log.append(s))
    mitte = W(np.mean([g["mitte"] for g in gr]), 0.5 * (zs + zsch))
    fs = []
    for f in sorted(KAM):
        if not os.path.exists(os.path.join(a.stabil, os.path.splitext(f)[0] + ".png")): continue
        k = KAM[f]; C = np.array(k["C"])
        if C @ n - of < 2.0 or np.linalg.norm(C - mitte) > a.dmax: continue
        fs.append(f)
    cache = {}
    def karte(f):
        if f not in cache: cache[f] = torch.from_numpy(cv2.imread(os.path.join(a.stabil, os.path.splitext(f)[0] + ".png"), 0))
        return cache[f].to(dev).float() / 255.0
    Wl = np.load(a.wolke, mmap_mode="r"); Pw = np.asarray((Wl["P"] if hasattr(Wl, "files") else Wl)[:, :3], dtype=np.float64)
    L_(f"Gruppen {len(gr)} (Mitten {np.round([g['mitte'] for g in gr], 2).tolist()}), Lichter {nl}, w_licht {wl0:.3f}; z Sohl {zs:.2f} Kaempfer {zk0:.2f} Schulter {zsch:.2f}; Fotos vor der Front {len(fs)}; Wolke {len(Pw)} Punkte")
    ergebnis = {"quelle_fe": a.fe, "vorher": {"z_kaempfer": zk0, "w_licht": wl0, "dx": 0.0, "z_sohl": zs, "z_scheitel": F["z_scheitel"]}}
    G = len(gr); klassen = sorted(set(min(i, nl - 1 - i) for i in range(nl)))          # Spiegelsymmetrie der Zelle: Licht i und nl-1-i teilen Parameter
    kname = lambda c: ("mitte" if 2 * c == nl - 1 else f"seite{c}" if c else "seite")
    lichter = lambda c: [i for i in range(nl) if min(i, nl - 1 - i) == c]
    x_licht = lambda g, i, dx=0.0, w=wl0: (g["mitte"] + dx + (i - nl / 2) * w, g["mitte"] + dx + (i - nl / 2 + 1) * w)

    def auswerten(S_gr, achsen, daten):
        """S_gr: (G, *achsen) Kontrast je Gruppe. Median ueber Gruppen; Optimum, Plateau, Signifikanz (Spitze-Median in MAD), Grenze, Einigkeit je Instanz."""
        S = np.median(S_gr, 0); bi = np.unravel_index(np.argmax(S), S.shape); prof = S.reshape(S.shape[0], -1).max(1) if S.ndim > 1 else S
        med = float(np.median(prof)); mad = float(np.median(np.abs(prof - med))); sig = (float(prof.max()) - med) / max(mad, 1e-9)
        pl = []
        for ax in range(S.ndim):
            idx = list(bi); line = np.array([S[tuple(idx[:ax] + [i] + idx[ax + 1:])] for i in range(S.shape[ax])]); b = bi[ax]; thr = 0.95 * line[b]; lo = hi = b
            while lo > 0 and line[lo - 1] >= thr: lo -= 1
            while hi < len(line) - 1 and line[hi + 1] >= thr: hi += 1
            pl.append([float(achsen[ax][lo]), float(achsen[ax][hi])])
        rand = [ax for ax in range(S.ndim) if S.shape[ax] > 1 and bi[ax] in (0, S.shape[ax] - 1)]
        je = [[float(achsen[ax][j]) for ax, j in enumerate(np.unravel_index(np.argmax(S_gr[gi]), S.shape))] for gi in range(G)]
        opt = [float(achsen[ax][bi[ax]]) for ax in range(S.ndim)]; streu = float(np.median([max(abs(e[ax] - opt[ax]) for ax in range(S.ndim)) for e in je]))
        nd = sum(d_["genug"] for d_ in daten)
        return {"optimum": opt, "score": float(S[bi]), "signifikanz_mad": sig, "plateau_95": pl, "plateau_breite": float(max(p_[1] - p_[0] for p_ in pl)), "auf_grenze": rand,
                "je_instanz": je, "instanz_streuung_median": streu, "instanzen_genug": nd, "daten": daten,
                "qualifiziert": bool(sig >= 3 and nd >= 3 and not rand), "profil": S.tolist() if S.ndim == 1 else None}

    def waehle(name, rf, rw, alt):
        """Nutzerentscheid: nie mitteln; die Quelle mit den besseren Daten gewinnt (Datenmenge, Signifikanz MAD, Plateaubreite, Einigkeit je Instanz),
        Suchgrenze disqualifiziert. Rueckgabe dict mit Wert, Quelle, Begruendung."""
        def txt(q, r): return f"{q}: Optimum {np.round(r['optimum'], 3).tolist()}, {r['signifikanz_mad']:.1f} MAD, Plateau {r['plateau_breite']:.2f} m, Instanzstreuung {r['instanz_streuung_median']:.2f} m, Daten {r['instanzen_genug']}/{G}" + (f", GRENZE Achse {r['auf_grenze']}" if r["auf_grenze"] else "")
        kand = [(q, r) for q, r in (("foto", rf), ("wolke", rw)) if r["qualifiziert"]]
        if not kand: return {"wert": alt, "quelle": "ANNAHME (Gitterwert, beide Quellen blind/disqualifiziert)", "begruendung": txt("Foto", rf) + " | " + txt("Wolke", rw), "uebernommen": False}
        if len(kand) == 2:   # Rangfolge: Einigkeit je Instanz, dann Plateau, dann Signifikanz (Zahlen im Satz)
            kand.sort(key=lambda qr: (qr[1]["instanz_streuung_median"], qr[1]["plateau_breite"], -qr[1]["signifikanz_mad"]))
        q, r = kand[0]; andere = "wolke" if q == "foto" else "foto"; ra = rw if q == "foto" else rf
        grund = f"{q} gewinnt ({'einzige qualifizierte Quelle' if len(kand) == 1 else 'bessere Einigkeit/Plateau/Signifikanz'}): " + txt(q, r) + " | " + txt(andere, ra)
        return {"wert": r["optimum"], "quelle": f"{q}_sweep", "begruendung": grund, "uebernommen": True, "abstand_quellen": float(max(abs(x - y) for x, y in zip(rf["optimum"], rw["optimum"])))}

    def daten_foto(z_ref):
        dat = []
        for g in gr:
            c = W(g["mitte"], z_ref); seh = 0; ri = set()
            for f in fs:
                k = KAM[f]; X = np.array(k["Rn"]) @ c + np.array(k["tn"])
                if X[2] < 1: continue
                px = X[0] / X[2] * k["f"] + k["cx"]; py = X[1] / X[2] * k["f"] + k["cy"]
                if 0 <= px < k["W"] and 0 <= py < k["H"]:
                    seh += 1; dv = np.array(k["C"]) - c; ang = math.degrees(math.atan2(dv @ u, dv @ n)); ri.add(-1 if ang < -15 else (1 if ang > 15 else 0))
            dat.append({"mitte": g["mitte"], "fotos": seh, "richtungen": sorted(ri), "genug": bool(seh >= 3 and len(ri) >= 2)})
        return dat
    alw = Pw @ u; ofw = Pw @ n - of; zzw = Pw[:, 2]
    def daten_wolke(c, z_ref, hz=0.15):
        dat = []
        for g in gr:
            n_ = 0
            for i in lichter(c):
                x0, x1 = x_licht(g, i); n_ += int(((alw >= x0) & (alw <= x1) & (np.abs(zzw - z_ref) <= hz) & (np.abs(ofw) < SCHEIBE)).sum())
            dat.append({"mitte": g["mitte"], "punkte_kasten": n_, "genug": n_ >= 30})
        return dat

    def hsweep(merkmal, c, zg, rand_x=0.1, halb=None):
        """Horizontale Linie je Licht der Klasse c (ganze Lichtbreite minus rand_x, oder +-halb um die Lichtmitte) fuer alle z in zg; Kontrast gegen +-KONTR."""
        def linien(dz):
            L = []
            for g in gr:
                for i in lichter(c):
                    x0, x1 = x_licht(g, i)
                    if halb: xm = 0.5 * (x0 + x1); x0, x1 = xm - halb, xm + halb
                    else: x0, x1 = x0 + rand_x, x1 - rand_x
                    for z in zg: L.append([W(x0, z + dz), W(x1, z + dz)])
            return np.array(L)
        res = {}
        for quelle in ("foto", "wolke"):
            vals = {}
            for dz in (0.0, KONTR, -KONTR):
                L = linien(dz); v = foto_stuetzung(L, fs, KAM, karte, torch, dev, mitte)[0] if quelle == "foto" else wolke_dichte(L, Pw, u, n, of, torch, dev)[0]
                vals[dz] = v.reshape(G, len(lichter(c)), len(zg)).mean(1)
            S_gr = vals[0.0] - 0.5 * (vals[KONTR] + vals[-KONTR]); zopt = float(zg[int(np.argmax(np.median(S_gr, 0)))])
            res[quelle] = auswerten(S_gr, [zg], daten_foto(zopt) if quelle == "foto" else daten_wolke(c, zopt))
        e = waehle(f"{merkmal}_{kname(c)}", res["foto"], res["wolke"], None); res["entscheidung"] = e
        L_(f"{merkmal} [{kname(c)}, Lichter {lichter(c)}]: Foto z {res['foto']['optimum'][0]:.3f} ({res['foto']['signifikanz_mad']:.1f} MAD, Streuung {res['foto']['instanz_streuung_median']:.2f}, Grenze {bool(res['foto']['auf_grenze'])}, Daten {res['foto']['instanzen_genug']}/{G}) | "
           f"Wolke z {res['wolke']['optimum'][0]:.3f} ({res['wolke']['signifikanz_mad']:.1f} MAD, Streuung {res['wolke']['instanz_streuung_median']:.2f}, Grenze {bool(res['wolke']['auf_grenze'])}, Daten {res['wolke']['instanzen_genug']}/{G}) -> {e['quelle']}")
        return res

    zsch_s = F["z_scheitel"]
    erg = {"kaempfer": {}, "sohl": {}, "scheitel": {}}
    for c in klassen:
        erg["scheitel"][kname(c)] = hsweep("Scheitel", c, np.round(np.arange(zsch - 0.3, zsch_s + 1.21, 0.01), 3), halb=0.15)
        e_ = erg["scheitel"][kname(c)]["entscheidung"]; z_top = e_["wert"][0] if e_["uebernommen"] else zsch_s
        erg["sohl"][kname(c)] = hsweep("Sohlbank", c, np.round(np.arange(zs - 0.5, zs + 0.81, 0.01), 3))
        e_ = erg["sohl"][kname(c)]["entscheidung"]; z_bot = e_["wert"][0] if e_["uebernommen"] else zs
        # Kaempfer = staerkste Horizontale zwischen Sohlbank+0,3 und Scheitel-0,3 DIESER Lichtklasse (Formfamilie: je Licht eigener Riegel)
        erg["kaempfer"][kname(c)] = hsweep("Kaempfer", c, np.round(np.arange(z_bot + 0.3, z_top - 0.3 + 1e-6, 0.01), 3))
    ergebnis.update(erg)
    # ---- Pfostenraster: vertikale Linien (Sohl+0,15 .. Schulter-0,15) an mitte + dx + (i - nl/2) * w; Kontrast seitlich +-KONTR
    dxg = np.round(np.arange(-0.4, 0.401, 0.02), 3); wg = np.round(np.arange(wl0 - 0.3, wl0 + 0.301, 0.02), 3)
    def pfosten_linien(sh=0.0):
        L = []
        for g in gr:
            for dx in dxg:
                for w in wg:
                    for i in range(nl + 1):
                        x = g["mitte"] + dx + (i - nl / 2) * w + sh; L.append([W(x, zs + 0.15), W(x, zsch - 0.15)])
        return np.array(L)
    res_p = {}
    for quelle in ("foto", "wolke"):
        vals = {}
        for sh in (0.0, KONTR, -KONTR):
            L = pfosten_linien(sh); v = foto_stuetzung(L, fs, KAM, karte, torch, dev, mitte)[0] if quelle == "foto" else wolke_dichte(L, Pw, u, n, of, torch, dev)[0]
            vals[sh] = v.reshape(G, len(dxg), len(wg), nl + 1).mean(3)
        dat = daten_foto(0.5 * (zs + zsch)) if quelle == "foto" else [{"mitte": g["mitte"], "punkte_kasten": int(((np.abs(alw - g["mitte"]) <= nl * wl0 / 2) & (zzw > zs) & (zzw < zsch) & (np.abs(ofw) < SCHEIBE)).sum()), "genug": True} for g in gr]
        if quelle == "wolke":
            for d_ in dat: d_["genug"] = d_["punkte_kasten"] >= 30
        res_p[quelle] = auswerten(vals[0.0] - 0.5 * (vals[KONTR] + vals[-KONTR]), [dxg, wg], dat)
    res_p["entscheidung"] = waehle("pfosten", res_p["foto"], res_p["wolke"], [0.0, wl0]); ergebnis["pfosten"] = res_p
    L_(f"Pfosten: Foto dx/w {res_p['foto']['optimum']} ({res_p['foto']['signifikanz_mad']:.1f} MAD, Grenze {res_p['foto']['auf_grenze']}) | Wolke {res_p['wolke']['optimum']} ({res_p['wolke']['signifikanz_mad']:.1f} MAD, Grenze {res_p['wolke']['auf_grenze']}) -> {res_p['entscheidung']['quelle']}")
    for m in ("kaempfer", "sohl", "scheitel"):
        for kn, r in erg[m].items(): L_(f"  BEGRUENDUNG {m}/{kn}: {r['entscheidung']['begruendung']}")
    L_(f"  BEGRUENDUNG pfosten: {res_p['entscheidung']['begruendung']}")
    # ---- je Licht Werte (Spiegelklasse), Instanzen fuer das Beleg-Tor
    def wert(m, i, alt):
        e = erg[m][kname(min(i, nl - 1 - i))]["entscheidung"]; return (e["wert"][0], e["quelle"]) if e["uebernommen"] else (alt, e["quelle"])
    dx, wl = (res_p["entscheidung"]["wert"] if res_p["entscheidung"]["uebernommen"] else [0.0, wl0])
    je_licht = [{"index": i, "klasse": kname(min(i, nl - 1 - i)), "z_kaempfer": wert("kaempfer", i, zk0), "z_sohl": wert("sohl", i, zs), "z_scheitel": wert("scheitel", i, zsch_s)} for i in range(nl)]
    ergebnis["je_licht"] = je_licht; ergebnis["pfosten_raster"] = {"dx": dx, "w_licht": wl}
    for jl in je_licht: L_(f"Licht {jl['index']} ({jl['klasse']}): Kaempfer {jl['z_kaempfer'][0]:.3f} [{jl['z_kaempfer'][1]}], Sohl {jl['z_sohl'][0]:.3f} [{jl['z_sohl'][1]}], Scheitel {jl['z_scheitel'][0]:.3f} [{jl['z_scheitel'][1]}]")
    ergebnis["instanzen"] = [{"familie": "fenster", "achse": {"along": g["mitte"] + dx, "u": u.tolist(), "n": n.tolist(), "off": of},
                              "masse": {"breite": nl * wl, "je_licht": [{k_: (v_[0] if isinstance(v_, tuple) else v_) for k_, v_ in jl.items()} for jl in je_licht]},
                              "teilungen": {"pfosten_along": [g["mitte"] + dx + (i - nl / 2) * wl for i in range(nl + 1)], "kaempfer_z_je_licht": [jl["z_kaempfer"][0] for jl in je_licht]}} for g in gr]
    ergebnis["log"] = log; json.dump(ergebnis, open(a.out, "w"), indent=1, default=float); print("->", a.out)
    if a.anwenden:
        F.setdefault("vorher_sweep", {k_: F.get(k_) for k_ in ("z_kaempfer", "z_sohl", "z_scheitel", "w_licht")})
        F["je_licht"] = [{"z_kaempfer": jl["z_kaempfer"][0], "z_sohl": jl["z_sohl"][0], "z_scheitel": jl["z_scheitel"][0], "quellen": {k_: jl[k_][1] for k_ in ("z_kaempfer", "z_sohl", "z_scheitel")}} for jl in je_licht]
        if res_p["entscheidung"]["uebernommen"]:
            F["w_licht"] = wl
            for g in F["gruppen"]: g["mitte"] = g["mitte"] + dx
        F["sweep_begruendung"] = [l_ for l_ in log if "BEGRUENDUNG" in l_]
        D["fenster"] = F; json.dump(D, open(a.fe, "w"), indent=1); print("FE je Licht geschrieben ->", a.fe)
    # Overlay mit Fehlerliste je Licht: rot vorher, gruen Ergebnis
    if a.bilder and a.audit:
        os.makedirs(a.audit, exist_ok=True)
        for f in a.fotos.split(","):
            if f not in KAM: continue
            k = KAM[f]; im = cv2.imread(os.path.join(a.bilder, f)); sj = im.shape[1] / k["W"]; uvs = []
            def lin(p0, p1, col, th=2):
                X = np.array([p0, p1]) @ np.array(k["Rn"]).T + np.array(k["tn"])
                if (X[:, 2] < 1).any(): return
                xx = X[:, 0] / X[:, 2]; yy = X[:, 1] / X[:, 2]; f1 = 1 + k["params"][3] * (xx * xx + yy * yy); uv = np.c_[(k["f"] * xx * f1 + k["cx"]) * sj, (k["f"] * yy * f1 + k["cy"]) * sj]
                uvs.append(uv); cv2.line(im, tuple(uv[0].round().astype(int)), tuple(uv[1].round().astype(int)), col, th)
            for g in gr:
                for i in range(nl):
                    x0, x1 = x_licht(g, i); lin(W(x0, zk0), W(x1, zk0), (0, 0, 255), 1); lin(W(x0 + 0.05, zs), W(x1 - 0.05, zs), (0, 0, 255), 1)
                    x0, x1 = x_licht(g, i, dx, wl); jl = je_licht[i]
                    for m_, col in (("z_kaempfer", (0, 255, 0)), ("z_sohl", (0, 255, 255)), ("z_scheitel", (255, 0, 255))):
                        lin(W(x0 + 0.05, jl[m_][0]), W(x1 - 0.05, jl[m_][0]), col)
                for i in range(nl + 1):
                    x = g["mitte"] + dx + (i - nl / 2) * wl; lin(W(x, min(jl_["z_sohl"][0] for jl_ in je_licht)), W(x, zsch), (255, 128, 0))
            if not uvs: continue
            U = np.concatenate(uvs); x0, y0 = np.clip(U.min(0) - 100, 0, None).astype(int); x1, y1 = np.minimum(U.max(0) + 100, [im.shape[1], im.shape[0]]).astype(int)
            c = im[y0:y1, x0:x1]; sc = min(1.0, 1600 / max(1, c.shape[1])); c = cv2.resize(c, None, fx=sc, fy=sc)
            cv2.putText(c, "rot duenn: vorher | gruen Kaempfer, gelb Sohlbank, magenta Scheitel je Licht | blau Pfosten", (10, 30), 0, 0.7, (255, 255, 255), 2)
            out = os.path.join(a.audit, f"kaempfer_je_licht_{os.path.splitext(f)[0]}.jpg"); cv2.imwrite(out, c); print("->", out)


if __name__ == "__main__":
    main()
