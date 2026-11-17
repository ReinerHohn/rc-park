#!/usr/bin/env python3
"""feinteil_tor.py - FEINTEIL-MASS: sieht, ob das Modell die FEINSTRUKTUR des Fotos dort hat, wo das Foto sie hat (Figuren, Masswerk, Schindeln, Gesimse),
und dort glatt ist, wo das Foto glatt ist (Putz). Hinweis, KEIN hartes Tor (Nachweis bisher nur Kaufhaus, 17.11.2026).

Warum: foto_diff/foto_tor_bezug glaetten das Foto auf ~0,18 m und vergleichen Kantenlinien mit 0,35 m Toleranz. Damit sind kaufhaus_grob3 (Handmodell mit
Figuren, Baldachinen, Erker-Masswerk, Schindeln) und kaufhaus_gk (Wolkenbrei zwischen den Fenstern, kein Feinteil) "gleich gut" (F1 0,77 / 0,78), das Auge sieht grob3 klar vorn.

Mass (je Foto, gleiches Foto + gleiche Kamera fuer alle verglichenen STL):
  1. Modell mit der kalibrierten Kamera rastern (foto_diff, Schnellweg _RUECK nur_masken + mit_grau): Normalenbild (zur Kamera gedreht), Silhouette, Verdecker.
  2. Arbeitsaufloesung ~--ppm px/m (Standard 60 = 1,7 cm/px). FEINBAND = Gauss(--fein m) - Gauss(--grob m) (Standard 2 cm / 12 cm):
     Foto = Graubild; Modell = drei Normalenkanaele (lichtunabhaengig). Gradienten -> Strukturtensor (Kanaele summiert): Staerke + Richtung (ohne Vorzeichen).
  3. Staerke normiert: Foto auf sein Mittel im Bewertungsbereich (Kontrast faellt heraus); Modelle (Normalen = gleiche Einheit) alle mit dem Mittel des ERSTEN STL
     (--norm bezug, Standard seit 17.11. abends). Vorher (--norm eigen) je Modell auf das eigene Mittel: dann aenderte Brei-Entfernen an der Wand die Dachnote
     (Ablation kaufhaus_gk: Dach 0,545 -> 0,605 nur durch die Wand) - Zonen waren nicht unabhaengig.
  4. Kacheln --kachel m (Standard 1,0 m), je Kachel 2x2 Zellen x 6 Richtungsklassen = Richtungshistogramm (HOG) -> Kachelnote
        s = (2 a.b + c) / (|a|^2 + |b|^2 + c)      (SSIM-artig: 1 = gleiche Feinstruktur; beide glatt = 1; Foto fein / Modell glatt oder umgekehrt -> 0)
     c = 0,1 x Median |Foto-Kachel|^2 (haengt NUR am Foto -> fuer alle Modelle gleich).
  5. Bewertungsbereich = Vereinigung der Silhouetten ALLER verglichenen Staende (erodiert 0,1 m), ohne Verdecker (dichte Tiefenkarten), fuer alle Staende gleich.
  6. Zonen (optional, --zonen json): benannte Kaesten im Modellrahmen, entweder {"name", "box": [x0,y0,z0,x1,y1,z1]} oder {"name", "wand": {"a":[x,y],"b":[x,y],
     "aussen":[x,y]}, "u":[u0,u1], "w":[w0,w1], "z":[z0,z1]} (u entlang a->b, w auf der Aussennormalen). Zonenmaske = projizierte Huelle der 8 Ecken
     (modellunabhaengig, ohne Verdeckung). Note je Zone = Mittel der Kachelnoten mit Kachelmitte in der Zone.
  7. Zusatz (nur Bericht): Rangkorrelation der Kachel-Feinenergie Foto <-> Modell ("energie_rho").
Kontrollen (--kontrolle): Wiederholung des ersten STL (muss bitgleich sein) und FALSCHES PAAR (Kamera dieses Fotos, Bild des naechsten Fotos der Liste,
  auf Bildgroesse gebracht) -> muss schlechter sein als das richtige Paar, sonst sagt das Mass nichts ueber das Foto.
Ausgabe: JSON (--aus) mit Note je STL, Foto, Zone und Mittel ueber Fotos; Bild je Foto <bilder>/feinteil_<foto>.jpg (oben Foto-Feinband | je STL Modell-Feinband,
  unten Kachelnoten rot = 0 .. gruen = 1).
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/feinteil_tor.py modelle/<objekt>/objekt.json --fotos a,b --stl A.stl,B.stl [--namen a,b] [--zonen z.json]
      [--aus bericht.json] [--bilder DIR] [--kontrolle]
Exit 0 immer (Hinweis); 2 = nicht beurteilbar (kein Foto lief).
"""
import sys, os, json, argparse, numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

STANDARD = dict(ppm=60.0, fein=0.02, grob=0.12, kachel=1.0, bins=6, c_faktor=0.1, rand=0.1, min_kacheln=6, norm="bezug")


def masken(objekt, nr, stl, dmed_fix=None, bild=None):
    """Rohmasken + Graubild + Kamera aus foto_diff (Raster/GPU)."""
    import foto_diff as FD
    argv = [objekt, nr, "--stl", stl] + (["--bild", bild] if bild else [])
    FD._RUECK = {"nur_masken": True, "mit_grau": True, **({"dmed_fix": float(dmed_fix)} if dmed_fix else {})}
    try:
        FD.main(argv); m = FD._RUECK.get("masken")
    finally: FD._RUECK = None
    if m is None: raise RuntimeError(f"foto_diff lieferte keine Masken fuer {nr}")
    return m


def _band(x, s1, s2):
    return cv2.GaussianBlur(x, (0, 0), s1) - cv2.GaussianBlur(x, (0, 0), s2)


def struktur(kanaele, s1, s2):
    """Feinband je Kanal -> Strukturtensor summiert -> (Staerke, Richtung in [0, pi))."""
    Jxx = Jyy = Jxy = 0.0
    for k in kanaele:
        b = _band(k.astype(np.float32), s1, s2)
        gx = cv2.Sobel(b, cv2.CV_32F, 1, 0, ksize=3) / 8.0; gy = cv2.Sobel(b, cv2.CV_32F, 0, 1, ksize=3) / 8.0
        Jxx = Jxx + gx * gx; Jyy = Jyy + gy * gy; Jxy = Jxy + gx * gy
    mag = np.sqrt(Jxx + Jyy); ori = (0.5 * np.arctan2(2 * Jxy, Jxx - Jyy)) % np.pi
    return mag.astype(np.float32), ori.astype(np.float32)


def deskriptoren(mag, ori, M, kpx, bins, norm=None):
    """HOG je Kachel (2x2 Zellen x bins), Staerke vorher auf Mittel im Bereich M normiert. Rueckgabe (D [ny, nx, 4*bins], Anteil gueltig, Energie je Kachel)."""
    H, W = mag.shape; ny, nx = H // kpx, W // kpx; c = kpx // 2
    m = np.where(M, mag / max(1e-9, float(norm if norm is not None else mag[M].mean())), 0.0).astype(np.float64)
    b = np.minimum((ori / np.pi * bins).astype(int), bins - 1)
    yy = np.arange(ny * kpx) // c; xx = np.arange(nx * kpx) // c
    cid = (yy[:, None] * (2 * nx) + xx[None, :]) * bins + b[:ny * kpx, :nx * kpx]
    h = np.bincount(cid.ravel(), m[:ny * kpx, :nx * kpx].ravel(), (2 * ny) * (2 * nx) * bins).reshape(2 * ny, 2 * nx, bins)
    D = h.reshape(ny, 2, nx, 2, bins).transpose(0, 2, 1, 3, 4).reshape(ny, nx, 4 * bins) / float(kpx * kpx)
    g = M[:ny * kpx, :nx * kpx].reshape(ny, kpx, nx, kpx).mean((1, 3))
    return D, g, D.sum(2)


def zonen_maske(z, R, t, f, cx, cy, W, H):
    if "box" in z:
        x0, y0, z0, x1, y1, z1 = z["box"]; P = np.array([[x, y, zz] for x in (x0, x1) for y in (y0, y1) for zz in (z0, z1)], float)
    else:
        a = np.asarray(z["wand"]["a"], float); b = np.asarray(z["wand"]["b"], float); e = (b - a) / np.linalg.norm(b - a); n = np.array([-e[1], e[0]])
        if np.dot(np.asarray(z["wand"]["aussen"], float) - a, n) < 0: n = -n
        P = np.array([[*(a + u * e + w * n), zz] for u in z["u"] for w in z["w"] for zz in z["z"]], float)
    Xc = P @ np.asarray(R).T + np.asarray(t); mk = np.zeros((H, W), np.uint8)
    if (Xc[:, 2] < 0.3).any(): return mk > 0                                                    # Kasten hinter/an der Kamera: Zone hier nicht bewertet
    uv = np.c_[f * Xc[:, 0] / Xc[:, 2] + cx, f * Xc[:, 1] / Xc[:, 2] + cy]
    cv2.fillConvexPoly(mk, cv2.convexHull(np.round(uv).astype(np.int32)), 1)
    return mk > 0


def note(Dp, Dm, ok, c):
    s = (2 * (Dp * Dm).sum(2) + c) / ((Dp * Dp).sum(2) + (Dm * Dm).sum(2) + c)
    return np.where(ok, s, np.nan)


def _rho(a, b):
    if len(a) < 4: return None
    ra = np.argsort(np.argsort(a)).astype(float); rb = np.argsort(np.argsort(b)).astype(float)
    return float(np.corrcoef(ra, rb)[0, 1])


def foto_messen(objekt, nr, stls, p, zonen, bild_falsch=None, bilder=None, namen=None, bereich=None):
    """Alle STL auf einem Foto. Rueckgabe dict(name -> dict(gesamt, zonen, energie_rho, kacheln)), plus Bild.
    bereich = STL-Liste, deren Silhouetten (Vereinigung) den Bewertungsbereich festlegen (Standard: die verglichenen STL). Fester Bereich = Noten
    verschiedener Aufrufe vergleichbar (sonst haengt die Note vom Vergleichssatz ab: grob3 0,537 neben gk, 0,549 neben verschobenen grob3)."""
    ms = []
    for i, s in enumerate(stls):
        ms.append(masken(objekt, nr, s, dmed_fix=(ms[0]["dmed"] if ms else None)))
    mb = ms if not bereich else [ms[stls.index(b)] if b in stls else masken(objekt, nr, b, dmed_fix=ms[0]["dmed"]) for b in bereich]
    m0 = ms[0]; H, W = m0["sil"].shape
    r = min(1.0, p["ppm"] / m0["ppm"]); ppm = m0["ppm"] * r
    def kl(x, interp=cv2.INTER_AREA): return cv2.resize(x, None, fx=r, fy=r, interpolation=interp) if r < 1 else x
    U = np.zeros((H, W), bool); O = np.zeros((H, W), bool)
    for m in mb: U |= m["sil"]; O |= m["occ"]
    er = max(1, int(round(p["rand"] * m0["ppm"]))) | 1
    Mfull = (cv2.erode(U.astype(np.uint8), np.ones((er, er), np.uint8)) > 0) & ~O
    M = kl(Mfull.astype(np.uint8), cv2.INTER_NEAREST) > 0
    s1, s2 = max(0.7, p["fein"] * ppm), max(2.0, p["grob"] * ppm); kpx = max(8, int(round(p["kachel"] * ppm)) // 2 * 2)
    def foto_D(gray):
        g = kl(gray.astype(np.float32) / 255.0); mag, ori = struktur([g], s1, s2); return deskriptoren(mag, ori, M, kpx, p["bins"]), mag
    (Dp, g, Ep), magp = foto_D(m0["grau"])
    ok = g >= 0.5; cpar = p["c_faktor"] * float(np.median((Dp[ok] ** 2).sum(1))) if ok.any() else 1e-6
    Zm = {}
    for z in zonen or []:
        zm = kl(zonen_maske(z, m0["R"], m0["t"], m0["f"], m0["cx"], m0["cy"], W, H).astype(np.uint8), cv2.INTER_NEAREST) > 0
        ny, nx = Dp.shape[:2]; Zm[z["name"]] = zm[:ny * kpx, :nx * kpx].reshape(ny, kpx, nx, kpx).mean((1, 3)) >= 0.5
    erg = {}; mags = []; noten = []
    def bewerten(Dm, Em, Dp_, Ep_):
        S = note(Dp_, Dm, ok, cpar); e = dict(gesamt=None, zonen={}, kacheln=int(ok.sum()))
        if ok.sum() >= p["min_kacheln"]: e["gesamt"] = round(float(np.nanmean(S)), 4); e["energie_rho"] = round(_rho(Ep_[ok], Em[ok]), 4)
        for zn, zk in Zm.items():
            sel = ok & zk; e["zonen"][zn] = dict(note=round(float(np.nanmean(S[sel])), 4) if sel.sum() >= 2 else None, kacheln=int(sel.sum()))
        return e, S
    for i, m in enumerate(ms):
        nr_ = np.nan_to_num(m["nrm"].astype(np.float32)); nr_[~m["sil"]] = 0
        mag, ori = struktur([kl(nr_[..., k]) for k in range(3)], s1, s2)
        if i == 0: norm_m = float(mag[M].mean()) if p["norm"] == "bezug" else None                    # Modellstaerke mit FESTEM Mass je Foto (erstes STL = Bezug): Normalen sind lichtunabhaengig, gleiche Einheit
        Dm, _, Em = deskriptoren(mag, ori, M, kpx, p["bins"], norm=norm_m if p["norm"] == "bezug" else None)
        e, S = bewerten(Dm, Em, Dp, Ep); erg[(namen or stls)[i]] = e; mags.append(mag); noten.append(S)
    if bild_falsch is not None:                                                                    # Kontrolle: falsches Paar (anderes Foto, gleiche Kamera/Modell 1)
        gf = cv2.resize(bild_falsch, (W, H), interpolation=cv2.INTER_AREA)
        (Dpf, _, Epf), _ = foto_D(gf); okf = ok
        nr_ = np.nan_to_num(ms[0]["nrm"].astype(np.float32)); nr_[~ms[0]["sil"]] = 0
        mag, ori = struktur([kl(nr_[..., k]) for k in range(3)], s1, s2); Dm, _, Em = deskriptoren(mag, ori, M, kpx, p["bins"])     # erstes STL: eigene = Bezugsnorm
        cf = p["c_faktor"] * float(np.median((Dpf[okf] ** 2).sum(1))) if okf.any() else 1e-6
        Sf = note(Dpf, Dm, okf, cf); erg["_falsches_paar_" + (namen or stls)[0]] = dict(gesamt=round(float(np.nanmean(Sf)), 4) if okf.sum() >= p["min_kacheln"] else None)
    if bilder:
        os.makedirs(bilder, exist_ok=True)
        def vis(mag):
            v = np.clip(mag / max(1e-9, np.percentile(mag[M], 98)) * 255, 0, 255).astype(np.uint8); v = cv2.cvtColor(v, cv2.COLOR_GRAY2BGR); v[~M] //= 3; return v
        def kach(S, basis):
            o = basis.copy().astype(np.float32) * 0.5
            for (y, x), s in np.ndenumerate(S):
                if np.isnan(s): continue
                col = np.array([0, 255 * s, 255 * (1 - s)], np.float32); o[y * kpx:(y + 1) * kpx, x * kpx:(x + 1) * kpx] = o[y * kpx:(y + 1) * kpx, x * kpx:(x + 1) * kpx] * 0.5 + col * 0.5
            o = o.astype(np.uint8)
            for zn, zk in Zm.items():
                cs, _ = cv2.findContours((cv2.resize(zk.astype(np.uint8), (zk.shape[1] * kpx, zk.shape[0] * kpx), interpolation=cv2.INTER_NEAREST)), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                cv2.drawContours(o, cs, -1, (255, 255, 0), 2)
                if cs: x_, y_, _, _ = cv2.boundingRect(cs[0]); cv2.putText(o, zn, (x_ + 3, y_ + 22), 0, 0.7, (255, 255, 0), 2)
            return o
        gb = cv2.cvtColor(kl(m0["grau"]), cv2.COLOR_GRAY2BGR)
        oben = [vis(magp)] + [vis(x) for x in mags]; unten = [gb] + [kach(S, gb) for S in noten]
        for j, n_ in enumerate(["Foto"] + list(namen or stls)):
            t_ = n_ if j == 0 else f"{n_}: {erg[n_]['gesamt']}"; cv2.putText(oben[j], t_, (10, 40), 0, 1.2, (0, 0, 0), 6); cv2.putText(oben[j], t_, (10, 40), 0, 1.2, (255, 255, 255), 2)
        o = np.vstack([np.hstack(oben), np.hstack(unten)]); fx = min(1.0, 3000.0 / o.shape[1])
        cv2.imwrite(os.path.join(bilder, f"feinteil_{nr[:40]}.jpg"), cv2.resize(o, None, fx=fx, fy=fx, interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 85])
    return erg


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--fotos", required=True); ap.add_argument("--stl", required=True, help="STL-Liste, Komma; das erste liefert dmed")
    ap.add_argument("--namen"); ap.add_argument("--zonen"); ap.add_argument("--aus"); ap.add_argument("--bilder"); ap.add_argument("--kontrolle", action="store_true")
    ap.add_argument("--bereich_stl", help="STL-Liste (Komma) fuer den festen Bewertungsbereich; Standard = --stl")
    for k, v in STANDARD.items(): ap.add_argument("--" + k, type=type(v), default=v)
    a = ap.parse_args(argv); p = {k: getattr(a, k) for k in STANDARD}
    fotos = [x for x in a.fotos.split(",") if x]; stls = [x for x in a.stl.split(",") if x]; namen = a.namen.split(",") if a.namen else [os.path.basename(s) for s in stls]
    if a.kontrolle: stls = stls + [stls[0]]; namen = namen + [namen[0] + "_wiederholung"]
    zonen = json.load(open(a.zonen))["zonen"] if a.zonen else []
    obj = json.load(open(a.objekt)); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(a.objekt))))
    import glob
    def foto_pfad(nr): return (glob.glob(os.path.join(root, obj["fotos_dir"], nr + "_*")) + glob.glob(os.path.join(root, obj["fotos_dir"], nr + ".*")))[0]
    alle = {}
    for i, nr in enumerate(fotos):
        falsch = cv2.cvtColor(cv2.imread(foto_pfad(fotos[(i + 1) % len(fotos)])), cv2.COLOR_BGR2GRAY) if a.kontrolle and len(fotos) > 1 else None
        try: alle[nr] = foto_messen(a.objekt, nr, stls, p, zonen, bild_falsch=falsch, bilder=a.bilder, namen=namen, bereich=[x for x in (a.bereich_stl or "").split(",") if x] or None)
        except (RuntimeError, SystemExit, IndexError) as ex: print(f"  {nr}: nicht beurteilbar ({ex})", flush=True); continue
        print(f"{nr[:34]:34s} " + " | ".join(f"{k}: {v.get('gesamt')}" + "".join(f" {zn}={zv['note']}" for zn, zv in v.get("zonen", {}).items()) for k, v in alle[nr].items()), flush=True)
    if not alle: print("nicht beurteilbar: kein Foto"); return 2
    mittel = {}
    for n_ in list(next(iter(alle.values())).keys()):
        g = [v[n_]["gesamt"] for v in alle.values() if n_ in v and v[n_].get("gesamt") is not None]
        mittel[n_] = dict(gesamt=round(float(np.mean(g)), 4) if g else None, fotos=len(g), zonen={})
        for z in zonen:
            zz = [v[n_]["zonen"][z["name"]]["note"] for v in alle.values() if n_ in v and v[n_].get("zonen", {}).get(z["name"], {}).get("note") is not None]
            mittel[n_]["zonen"][z["name"]] = dict(note=round(float(np.mean(zz)), 4) if zz else None, fotos=len(zz))
    print("MITTEL " + " | ".join(f"{k}: {v['gesamt']} (" + ", ".join(f"{zn} {zv['note']}" for zn, zv in v["zonen"].items()) + ")" for k, v in mittel.items()))
    if a.kontrolle:
        w = [v[namen[0]]["gesamt"] == v[namen[-1]]["gesamt"] and v[namen[0]]["zonen"] == v[namen[-1]]["zonen"] for v in alle.values()]
        fp = [(v[namen[0]]["gesamt"], v.get("_falsches_paar_" + namen[0], {}).get("gesamt")) for v in alle.values()]
        print(f"KONTROLLE Wiederholung bitgleich {sum(w)}/{len(w)}; richtiges Paar > falsches Paar {sum(1 for r_, f_ in fp if f_ is not None and r_ > f_)}/{sum(1 for _, f_ in fp if f_ is not None)}")
        mittel["_kontrolle"] = dict(wiederholung_bitgleich=f"{sum(w)}/{len(w)}", richtig_vor_falsch=f"{sum(1 for r_, f_ in fp if f_ is not None and r_ > f_)}/{sum(1 for _, f_ in fp if f_ is not None)}")
    if a.aus: json.dump(dict(parameter=p, stl=dict(zip(namen, stls)), mittel=mittel, fotos=alle), open(a.aus, "w"), indent=1, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
