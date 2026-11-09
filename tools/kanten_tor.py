#!/usr/bin/env python3
"""kanten_tor.py - Beleg-Tor auf KANTEN (neutral, keine Bauteiltypen): jede 3D-Kante einer Wiederholung wird getrennt gegen (a) nur die Wolke (Wolke + Tiefen-Sweep, Kantenpunkte im Schlauch)
und (b) nur die Fotokanten (Stabilitaetskarten bzw. Sobel der Originalfotos, Z-Puffer der Wolke) im Versatz-Sweep geprueft: Versatz in der Fassadenebene (senkrecht zur Kante), Versatz in die Tiefe,
Endpunkt-Verlaengerung/-Kuerzung (Aenderungspunkt-Score) je Ende. Eingabe = KANTEN.json: {"rahmen":{"n":[..]}, "kanten":[{"id","A","B","gruppe","spiegel"?}]}; Kopplungsgruppe = gleiche Kante in wiederholten
Instanzen (gemeinsamer Sweep, staerkeres Signal); die Kopplung wird AUFGETRENNT, wenn die je-Kante-Optima in getrennten, je signifikanten Untergruppen liegen (Mittel-Kaempfer-Fall).
Entscheidung je Parameter: GRUEN / BESTAETIGT(Quelle) / KORRIGIERT(Quelle) / OFFEN mit Begruendungssatz (Kennzahlen a-e), nie gemittelt. Wiederverwendet wird die Engine (Tor, Fotos) - sie liegt hier; muster_fit.py importiert sie.
Aufruf: kanten_tor.py --kanten K.json --wolke W.npz --sweep A.npz,B.npz --kam KAM.json --stabil DIR --bilder DIR --out OUT.json [--audit DIR --fotos ip_IMG_6120,ip_IMG_6261]
Verwandte Bausteine (nicht dupliziert, hier Verweis): gitter_verfeinern.py (DT-Verlust gegen Stabilitaetskarten), gitter_zurueck.py (Fotopruefung mit distanzabhaengiger Toleranz), gitter_pruefblatt.py (Z-Puffer);
der Z-Puffer/Fotoabgleich dieser Engine folgt der Logik von baluster_fit.py/gitter_pruefblatt.py (1/4 Aufloesung, 3x3-Min-Pool)."""
import sys, os, json, math, time
import numpy as np

HIER = os.path.dirname(os.path.abspath(__file__))
a = sys.argv; g = lambda k, d, t=float: t(a[a.index(k) + 1]) if k in a else d
NFOTO = g("--nfoto", 3, int); FANTEIL = g("--fanteil", 0.3); KANTE = g("--kante_anteil", 0.5); PX = g("--px", 3, int); THR = g("--thr", 0.3)


def log(*s):
    print(*s, flush=True)


def torch_dev():
    import torch
    if torch.cuda.is_available():
        torch.cuda.set_per_process_memory_fraction(float(os.environ.get("RCPARK_GPU_ANTEIL", "0.18")))
        return torch, "cuda"
    return torch, "cpu"



# ----------------------------------------------------------------------------------------------- Fotos: Abnahme jeder Kopie
class Fotos:
    def __init__(s, kam, stabil, bilder=None):
        s.KAM = json.load(open(kam)); s.sd = stabil; s.bd = bilder; s.torch, s.dev = torch_dev(); s.cache = {}
        s.liste = [f for f in sorted(s.KAM) if os.path.exists(os.path.join(stabil, os.path.splitext(f)[0] + ".png"))]

    def karte(s, f):
        import cv2
        if f not in s.cache:
            V = cv2.imread(os.path.join(s.sd, os.path.splitext(f)[0] + ".png"), 0); Vd = cv2.dilate(V, np.ones((2 * PX + 1, 2 * PX + 1), np.uint8)); s.cache = {f: (V, Vd)}   # nur ein Foto im Speicher
        return s.cache[f]

    def zpuffer(s, f, W):
        """Z-Puffer der Wolke (1/4 Aufloesung von 1500 px, 3x3-Min-Pool, Loecher mit 9x9) wie baluster_fit."""
        torch, dev = s.torch, s.dev; k = s.KAM[f]; R = torch.tensor(k["Rn"], device=dev, dtype=torch.float32); t_ = torch.tensor(k["tn"], device=dev, dtype=torch.float32); Xw = W @ R.T + t_; zw = Xw[:, 2]; m = zw > 0.5
        sjq = 1500.0 / k["W"] / 4; xw = Xw[m, 0] / zw[m]; yw = Xw[m, 1] / zw[m]; fw = 1 + k["params"][3] * (xw * xw + yw * yw); Hq, Wq = int(k["H"] * 1500.0 / k["W"] / 4) + 1, int(1500 / 4) + 1
        uw = ((k["f"] * xw * fw + k["cx"]) * sjq).long(); vw = ((k["f"] * yw * fw + k["cy"]) * sjq).long(); inb = (uw >= 0) & (uw < Wq) & (vw >= 0) & (vw < Hq)
        zb = torch.full((Hq * Wq,), 1e9, device=dev); zb.scatter_reduce_(0, vw[inb] * Wq + uw[inb], zw[m][inb], reduce="amin"); zb = zb.view(Hq, Wq)
        zb = -torch.nn.functional.max_pool2d(-zb[None, None], 3, 1, 1)[0, 0]; leer = zb > 1e8; zb9 = -torch.nn.functional.max_pool2d(-zb[None, None], 9, 1, 4)[0, 0]
        return torch.where(leer, zb9, zb).cpu().numpy(), sjq

    def proj(s, f, X3):
        k = s.KAM[f]; R = np.array(k["Rn"]); t_ = np.array(k["tn"]); X = R @ X3.T + t_[:, None]; z = X[2]
        with np.errstate(divide="ignore", invalid="ignore"):
            x = X[0] / z; y = X[1] / z
        f1 = 1 + k["params"][3] * (x * x + y * y); return k["f"] * x * f1 + k["cx"], k["f"] * y * f1 + k["cy"], z

    def abnahme(s, kopien, W, kontroll=None, dmax=45.0, nfoto=None, schritt=1):
        """kopien: Liste von dict(pts=[n,3] Umriss-Stuetzpunkte, mitte=[3]). Je Foto: sichtbar (Z-Puffer >= 60 % der Punkte, >= 90 % im Bild, > 6 px Ausdehnung, Kamera < dmax);
        Treffer = Anteil der Umrisspunkte auf Kante der Stabilitaetskarte (Toleranz PX) >= KANTE. kontroll = dict(pts_shift) gleiche Umrisse um dt seitlich versetzt (Gegenprobe)."""
        torch = s.torch; Wt = torch.tensor(W, device=s.dev, dtype=torch.float32); n = len(kopien); sicht = np.zeros(n, int); treff = np.zeros(n, int); csicht = np.zeros(n, int); ctreff = np.zeros(n, int)
        anteile = [[] for _ in range(n)]; fotos_ja = [[] for _ in range(n)]; mitten = np.array([k["mitte"] for k in kopien]); kontrolle = kontroll or [None] * n
        for f in s.liste[::schritt]:
            k = s.KAM[f]; C = np.array(k["C"]); dist = np.linalg.norm(mitten - C, axis=1); ids = np.where(dist < dmax)[0]
            if not len(ids): continue
            u0, v0, z0 = s.proj(f, mitten[ids]); sj0 = 1.0
            ids = ids[(z0 > 2) & (np.abs((u0 - k["cx"]) / k["f"]) < 0.8) & (np.abs((v0 - k["cy"]) / k["f"]) < 0.8)]
            if not len(ids): continue
            V, Vd = s.karte(f); H, Wd = V.shape; sj = Wd / k["W"]; zb, sjq = s.zpuffer(f, Wt)
            def pruefen(pts):
                u, v, z = s.proj(f, pts); u = u * sj; v = v * sj; ok = (z > 1) & (u >= 0) & (u < Wd) & (v >= 0) & (v < H)
                if ok.mean() < 0.9 or (u[ok].max() - u[ok].min()) < 6 * sj and (v[ok].max() - v[ok].min()) < 6 * sj: return None
                uq = np.clip((u * sjq / sj).astype(int), 0, zb.shape[1] - 1); vq = np.clip((v * sjq / sj).astype(int), 0, zb.shape[0] - 1); vis = ok & (z <= zb[vq, uq] + 0.5)
                if vis.mean() < 0.6: return None
                uu = u[vis].astype(int); vv = v[vis].astype(int); return float((Vd[vv, uu] >= THR * 255).mean())
            for i in ids:
                r = pruefen(kopien[i]["pts"])
                if r is not None:
                    sicht[i] += 1; anteile[i].append(r)
                    if r >= KANTE: treff[i] += 1; fotos_ja[i].append(f)
                if kontrolle[i] is not None:
                    r = pruefen(kontrolle[i])
                    if r is not None:
                        csicht[i] += 1
                        if r >= KANTE: ctreff[i] += 1
        nf = NFOTO if nfoto is None else nfoto
        return [dict(fotos_gesehen=int(sicht[i]), fotos_kante=int(treff[i]), kantenanteil_median=float(np.median(anteile[i])) if anteile[i] else None, kantenanteil_mittel=float(np.mean(anteile[i])) if anteile[i] else None, kontrolle_gesehen=int(csicht[i]), kontrolle_kante=int(ctreff[i]),
                     fotos=fotos_ja[i][:6], bestanden=bool(treff[i] >= nf and treff[i] >= FANTEIL * sicht[i])) for i in range(n)]



# ----------------------------------------------------------------------------------------------- Beleg-Tor
TOR_K = g("--tor_k", 3.0)            # Signifikanz: Spitze - Median >= k * MAD der Sweepkurve
TOR_NPKT = g("--tor_npunkte", 30, int)   # Wolke: Mindestpunkte im Pruefkasten je Instanz
TOR_NFOTO = g("--tor_nfoto", 3, int)     # Fotos: Mindestzahl sehender Fotos je Instanz
TOR_WINKEL = g("--tor_winkel", 20.0)
TOR_EINIG = g("--tor_einigkeit", 0.5)   # (d): >= 50 % der Instanz-Optima im Toleranzband um das Quellenoptimum, sonst ist die Quelle fuer diesen Parameter nicht belastbar     # Fotos: Mindest-Winkelabstand der Blickrichtungen (Grad)


class Tor:
    """Beleg-Tor: jeder Lage-/Teilungsparameter einer Instanzmenge wird in einem Versatz-Sweep GETRENNT gegen (a) nur die Wolke und (b) nur die Fotokanten geprueft.
    feat(wert) -> dict(punkte=[N,3], inst=[N]) Stuetzpunkte des betroffenen Bauteils ALLER Instanzen bei diesem Wert (Linien alle 3 cm, Flaechen im Raster).
    Wolke: Anteil der Stuetzpunkte mit >= 1 Wolkenpunkt (Wolke + Tiefen-Sweep) im Radius r (GPU ball_query). Fotos: Anteil der sichtbaren Stuetzpunkte (Z-Puffer) auf Kante der Stabilitaetskarte,
    je (Instanz, Foto) gemittelt, dann ueber Instanzen. Entscheidung: siehe urteil()."""
    def __init__(s, F, cloud, r_wolke=0.04, max_fotos=30):
        s.F = F; s.cloud = cloud; s.r = r_wolke; s.maxf = max_fotos; s.maps = {}; s.zb = {}
        sys.path.insert(0, HIER); from gpu_knn import ball_anzahl; s.ball = ball_anzahl

    def _karte(s, f, modus="karte"):
        """modus karte: Stabilitaetskarte (>= THR, 1500 px breit, Toleranz PX); gradient: Sobelbetrag des Originalfotos (1500 px breit, 3x3-Maximum, 0..1) fuer feine Teile (Baluster)."""
        import cv2
        key = (f, modus)
        if key not in s.maps:
            if modus == "karte":
                V = cv2.imread(os.path.join(s.F.sd, os.path.splitext(f)[0] + ".png"), 0); sc = 1500.0 / V.shape[1]; V = cv2.resize(V, (1500, int(V.shape[0] * sc)), interpolation=cv2.INTER_AREA)
                s.maps[key] = cv2.dilate((V >= THR * 255).astype(np.uint8), np.ones((2 * PX + 1, 2 * PX + 1), np.uint8)).astype(np.float32)
            else:
                im = cv2.imread(os.path.join(s.F.bd, f), cv2.IMREAD_GRAYSCALE | cv2.IMREAD_IGNORE_ORIENTATION); sc = 1500.0 / im.shape[1]; im = cv2.resize(im, (1500, int(im.shape[0] * sc)), interpolation=cv2.INTER_AREA)
                gx = cv2.Sobel(im, cv2.CV_32F, 1, 0, ksize=3); gy = cv2.Sobel(im, cv2.CV_32F, 0, 1, ksize=3); s.maps[key] = cv2.dilate(np.clip(np.sqrt(gx * gx + gy * gy) / 400.0, 0, 1), np.ones((3, 3), np.uint8))
        return s.maps[key]

    def _zb(s, f, Wt):
        if f not in s.zb: s.zb[f] = s.F.zpuffer(f, Wt)
        return s.zb[f]

    def fotos_waehlen(s, zentren, Wt):
        """Je Instanz bis max_fotos sichtbare Fotos (Zentrum im Bild, Z-Puffer, Abstand 8..45 m), auf Blickrichtungen verteilt (Azimut-Raster 20 Grad); Rueckgabe {inst: [(foto, azimut)]}."""
        F = s.F; res = {i: [] for i in range(len(zentren))}
        for f in F.liste:
            k = F.KAM[f]; C = np.array(k["C"]); u_, v_, z_ = F.proj(f, zentren); dist = np.linalg.norm(zentren - C, axis=1)
            for i in range(len(zentren)):
                if not (z_[i] > 2 and abs((u_[i] - k["cx"]) / k["f"]) < 0.7 and abs((v_[i] - k["cy"]) / k["f"]) < 0.7 and 6 < dist[i] < 45): continue
                res[i].append((float(dist[i]), f, float(np.degrees(np.arctan2(C[1] - zentren[i][1], C[0] - zentren[i][0])))))
        out = {}
        for i, lst in res.items():
            lst.sort(); belegt = {}; pick = []
            for d_, f, az in lst:                                                       # naechste Fotos je 20-Grad-Sektor zuerst, dann auffuellen
                sek = int((az % 360) // TOR_WINKEL)
                if sek not in belegt: belegt[sek] = 1; pick.append((f, az))
            for d_, f, az in lst:
                if len(pick) >= s.maxf: break
                if (f, az) not in pick: pick.append((f, az))
            out[i] = pick[:s.maxf]
        return out

    def sweep(s, name, feat, werte, gesetzt, tol, zentren, r_wolke=None, kmax=4, modus="karte"):
        """Ein Parameter: Kurven fuer Wolke und Fotos, Datenlage, Optima, Plateaus, Urteil."""
        torch = s.F.torch; werte = np.asarray(werte, float); pts0 = feat(gesetzt); n_inst = len(zentren); Wt = torch.tensor(s.cloud[:, :3], device=s.F.dev, dtype=torch.float32) if False else None
        # ---- Wolke
        allp = [feat(v) for v in werte]; P = np.concatenate([q["punkte"] for q in allp]); N0 = len(pts0["punkte"]); iid = np.concatenate([q["inst"] for q in allp]); wi = np.repeat(np.arange(len(werte)), [len(q["punkte"]) for q in allp])
        c = s.ball(P.astype(np.float32), s.cloud, r_wolke or s.r, kmax=kmax); sc_w = np.zeros(len(werte)); Mw = np.zeros((len(werte), n_inst))
        for vi in range(len(werte)):
            m = wi == vi; ii = iid[m]; gw = np.concatenate([q_['gew'] for q_ in allp])[m]; cc = np.minimum(c[m], kmax) / float(kmax) * gw; per = np.bincount(ii, weights=cc, minlength=n_inst) / np.maximum(np.bincount(ii, weights=np.abs(gw), minlength=n_inst), 1e-9); sc_w[vi] = per.mean(); Mw[vi] = per
        # Datenlage Wolke: Punkte (Wolke+Sweep) im Kasten (Radius 0,15) um die Stuetzpunkte beim gesetzten Wert, je Instanz
        cb = s.ball(pts0["punkte"].astype(np.float32), s.cloud, 0.15, kmax=64); pro_inst = np.array([float(cb[pts0["inst"] == i].sum()) for i in range(n_inst)])
        # ---- Fotos
        Wt = torch.tensor(s.F_cloudW, device=s.F.dev, dtype=torch.float32); fw = s.fotos_waehlen(zentren, Wt); sc_f_i = np.zeros((len(werte), n_inst)); n_f_i = np.zeros(n_inst, int); winkel_i = np.zeros(n_inst); zaehl = np.zeros((len(werte), n_inst))
        phot = {}
        for i, lst in fw.items():
            for f, az in lst: phot.setdefault(f, []).append(i)
        ph_i = {i: [] for i in range(n_inst)}
        for f, insts in phot.items():
            k = s.F.KAM[f]; M = s._karte(f, modus); H, Wd = M.shape; sj = Wd / k["W"]; zb, sjq = s._zb(f, Wt)
            for i in insts:
                pi = np.concatenate([allp[vi]["punkte"][allp[vi]["inst"] == i] for vi in range(len(werte))]); nper = len(pi) // len(werte); gwi = np.stack([allp[vi]["gew"][allp[vi]["inst"] == i] for vi in range(len(werte))])
                u_, v_, z_ = s.F.proj(f, pi); uu = (u_ * sj).astype(int); vv = (v_ * sj).astype(int); ok = (z_ > 1) & (uu >= 0) & (uu < Wd) & (vv >= 0) & (vv < H)
                uq = np.clip((u_ * sjq).astype(int), 0, zb.shape[1] - 1); vq = np.clip((v_ * sjq).astype(int), 0, zb.shape[0] - 1); vis = ok & (z_ <= zb[vq, uq] + 0.5)
                hit = np.zeros(len(pi)); hit[ok] = M[vv[ok], uu[ok]]; hit = hit.reshape(len(werte), nper); vis = vis.reshape(len(werte), nper)
                if vis[werte.searchsorted(gesetzt) if False else int(np.argmin(np.abs(werte - gesetzt)))].mean() < 0.5: continue     # Instanz im Foto zu mehr als der Haelfte verdeckt (am gesetzten Wert)
                frac = (hit * vis * gwi).sum(1) / np.maximum((vis * np.abs(gwi)).sum(1), 1e-9); sc_f_i[:, i] += frac; zaehl[:, i] += 1; ph_i[i].append((f, float(np.degrees(np.arctan2(s.F.KAM[f]["C"][1] - pi[:, 1].mean(), s.F.KAM[f]["C"][0] - pi[:, 0].mean())))))
        n_f_i = zaehl[0].astype(int); Mf = sc_f_i / np.maximum(zaehl, 1); sc_f = Mf[:, zaehl[0] > 0].mean(1) if (zaehl[0] > 0).any() else Mf.mean(1)
        for i in range(n_inst):
            az = np.array([a_ for _, a_ in ph_i[i]]); winkel_i[i] = float(np.max(np.abs(((az[:, None] - az[None]) + 180) % 360 - 180))) if len(az) > 1 else 0.0
        out = dict(name=name, werte=[float(x) for x in werte], gesetzt=float(gesetzt), tol=float(tol))
        out["wolke"] = s.quelle(sc_w, werte, gesetzt, tol, Mw, ok_daten=bool((pro_inst >= TOR_NPKT).sum() >= min(3, n_inst)), info="Wolke: Punkte im Kasten je Instanz min %d / median %d / max %d; Instanzen mit >= %d Punkten: %d von %d" % (pro_inst.min(), np.median(pro_inst), pro_inst.max(), TOR_NPKT, (pro_inst >= TOR_NPKT).sum(), n_inst))
        okf = ((n_f_i >= TOR_NFOTO) & (winkel_i >= TOR_WINKEL)).sum() >= min(3, n_inst)
        out["foto"] = s.quelle(sc_f, werte, gesetzt, tol, Mf, ok_daten=bool(okf), info="Fotos: sehende Fotos je Instanz min %d / median %d / max %d; Blickwinkelspanne je Instanz min %.0f / median %.0f Grad; Instanzen mit >= %d Fotos und >= %.0f Grad: %d von %d" % (n_f_i.min(), np.median(n_f_i), n_f_i.max(), winkel_i.min(), np.median(winkel_i), TOR_NFOTO, TOR_WINKEL, ((n_f_i >= TOR_NFOTO) & (winkel_i >= TOR_WINKEL)).sum(), n_inst))
        out["urteil"] = s.urteil(out); return out

    def quelle(s, sc, werte, gesetzt, tol, M, ok_daten, info):
        """Kennzahlen je Quelle und Parameter (alle protokolliert): (a) daten_ok, (b) Signifikanz (Spitze - Median)/MAD, (c) Plateaubreite 95 % (>= Median + 0,95 (Spitze - Median)),
        (d) Einigkeit: MAD der Instanz-Optima und Anteil der Instanzen mit Optimum im Toleranzband um das Quellenoptimum, (e) Optimum auf der Suchgrenze (Schritt 1 am Rand)."""
        sc = np.asarray(sc, float); sm_ = lambda x: np.convolve(np.pad(x, 1, mode="edge"), np.ones(3) / 3, "valid"); sm = sm_(sc); med = float(np.median(sm)); mad = float(np.median(np.abs(sm - med))) + 1e-9; j = int(np.argmax(sm)); peak = float(sm[j])
        def plateau(fr):
            ok = sm >= med + fr * (peak - med); lo = j; hi = j
            while lo > 0 and ok[lo - 1]: lo -= 1
            while hi < len(ok) - 1 and ok[hi + 1]: hi += 1
            return lo, hi
        lo, hi = plateau(0.9); lo95, hi95 = plateau(0.95); step = float(werte[1] - werte[0]); breite = float(werte[hi] - werte[lo]) if hi > lo else step; breite95 = float(werte[hi95] - werte[lo95]) if hi95 > lo95 else step
        suche = float(werte[-1] - werte[0]); sig_mad = (peak - med) / mad; signif = bool(sig_mad >= TOR_K and breite < 0.5 * suche); grenze = bool(j <= 0 or j >= len(werte) - 1)
        opts = []; optfull = np.full(M.shape[1], np.nan)
        for i_ in range(M.shape[1]):
            c_ = sm_(M[:, i_])
            if c_.max() - c_.min() > 1e-9: opts.append(float(werte[int(np.argmax(c_))])); optfull[i_] = opts[-1]
        opts = np.array(opts); e_mad = float(np.median(np.abs(opts - np.median(opts)))) if len(opts) else float("nan"); e_anteil = float((np.abs(opts - werte[j]) <= tol).mean()) if len(opts) else 0.0
        ig = int(np.argmin(np.abs(werte - gesetzt))); return dict(daten_ok=bool(ok_daten), info=info, signifikant=signif, signif_mad=float(sig_mad), optimum=float(werte[j]), plateau=(float(werte[lo]), float(werte[hi])), plateau_breite=breite, plateau95_breite=breite95,
                                                                  spitze=peak, median=med, mad=mad, wert_am_istwert=float(sm[ig]), gewinn=float(peak - sm[ig]), einigkeit_mad=e_mad, einigkeit_anteil=e_anteil, n_inst_mit_optimum=int(len(opts)), auf_grenze=grenze, opt_je_kante=[float(x) for x in optfull], kurve=[round(float(x), 4) for x in sc])

    def urteil(s, o):
        """Entscheidung nach Nutzerregel (nie mitteln; bessere Daten gewinnen, schriftlich begruendet): GRUEN / BESTAETIGT(Quelle) / KORRIGIERT(Quelle) / OFFEN.
        Qualifiziert = (a) Daten ok UND nicht auf Suchgrenze (e) UND signifikant. Beide qualifiziert + beide innerhalb Toleranz -> GRUEN; beide, einig ausserhalb -> KORRIGIERT (Wert der in (b)(c)(d) besseren Quelle);
        beide, widerspruechlich -> Sieger nur bei besser in >= 2 von 3 Kennzahlen (b,c,d) und in keiner deutlich schlechter (Faktor 2), sonst OFFEN; genau eine qualifiziert -> sie entscheidet; keine -> OFFEN (Istwert bleibt ANNAHME)."""
        w, f = o["wolke"], o["foto"]; tol = o["tol"]; ist = o["gesetzt"]; q = {"Wolke": w, "Fotos": f}
        def kz(x): return "Optimum %+.3f, Daten %s [%s], (b) %.1f MAD, (c) Plateau95 %.3f m, (d) Streuung %.3f / %.0f %% im Band, (e) Grenze %s" % (x["optimum"] - ist, "ja" if x["daten_ok"] else "NEIN", x["info"], x["signif_mad"], x["plateau95_breite"], x["einigkeit_mad"], 100 * x["einigkeit_anteil"], "JA" if x["auf_grenze"] else "nein")
        qual = {n: (x["daten_ok"] and not x["auf_grenze"] and x["signifikant"] and x["einigkeit_anteil"] >= TOR_EINIG) for n, x in q.items()}; nm = lambda n: n
        def besser(a_, b_):                                                           # Zahl der Kennzahlen (b,c,d), in denen a_ besser ist; None wenn a_ in einer deutlich schlechter (Faktor 2) ist
            b1 = a_["signif_mad"] > b_["signif_mad"]; c1 = a_["plateau95_breite"] < b_["plateau95_breite"]; d1 = (a_["einigkeit_anteil"], -a_["einigkeit_mad"]) > (b_["einigkeit_anteil"], -b_["einigkeit_mad"])
            schlecht = (a_["signif_mad"] * 2 < b_["signif_mad"]) or (a_["plateau95_breite"] > 2 * b_["plateau95_breite"] + 1e-9) or (a_["einigkeit_anteil"] * 2 < b_["einigkeit_anteil"])
            return (int(b1) + int(c1) + int(d1)) if not schlecht else None
        def fertig(status, quelle, wert, satz): return dict(status=status, quelle_gewinner=quelle, wert=float(wert), grund=satz, quelle_wert=("beleg_tor (%s)" % quelle) if status in ("KORRIGIERT", "BESTAETIGT", "GRUEN") else "ANNAHME: gesetzter Wert bleibt (%s)" % satz)
        nmn = o["name"]
        for n_, x_ in q.items():                                                     # Istwert im Plateau/Gewinn < k MAD -> Istwert statistisch nicht vom Optimum zu trennen: Optimum = Istwert fuer die Toleranzpruefung
            if qual[n_] and x_["gewinn"] < TOR_K * x_["mad"]: x_ = dict(x_); x_["optimum"] = ist; q[n_] = x_
        w, f = q["Wolke"], q["Fotos"]
        if qual["Wolke"] and qual["Fotos"]:
            dw, df = w["optimum"] - ist, f["optimum"] - ist
            if abs(w["optimum"] - f["optimum"]) <= tol:
                if abs(dw) <= tol and abs(df) <= tol: return fertig("GRUEN", "Wolke+Fotos", ist, "%s: GRUEN, beide Quellen genug Daten, beide Optima innerhalb %.3f (Wolke %+.3f, Fotos %+.3f). Wolke: %s. Fotos: %s." % (nmn, tol, dw, df, kz(w), kz(f)))
                bw = besser(w, f); bf = besser(f, w); gew = "Wolke" if (bw or 0) >= (bf or 0) else "Fotos"; x = q[gew]
                return fertig("KORRIGIERT", gew, x["optimum"], "%s %.3f: beide Quellen stimmen ueberein (Abstand %.3f <= %.3f), liegen ausserhalb der Toleranz vom Istwert %.3f; Wert der besseren Quelle (%s) uebernommen (nicht gemittelt). Wolke: %s. Fotos: %s." % (nmn, x["optimum"], abs(w["optimum"] - f["optimum"]), tol, ist, gew, kz(w), kz(f)))
            bw, bf = besser(w, f), besser(f, w)
            if bw is not None and bw >= 2: gew, x = "Wolke", w
            elif bf is not None and bf >= 2: gew, x = "Fotos", f
            else: return fertig("OFFEN", None, ist, "%s: OFFEN, Wolke (%+.3f) und Fotos (%+.3f) widersprechen sich (> %.3f), keine Quelle in >= 2 von 3 Kennzahlen klar besser. Wolke: %s. Fotos: %s." % (nmn, dw, df, tol, kz(w), kz(f)))
            return fertig("KORRIGIERT" if abs(x["optimum"] - ist) > tol else "BESTAETIGT", gew, x["optimum"], "%s %.3f: Wolke und Fotos widersprechen sich (Wolke %+.3f, Fotos %+.3f); %s gewinnt (in >= 2 von 3 Kennzahlen besser, in keiner deutlich schlechter), nicht gemittelt. Wolke: %s. Fotos: %s." % (nmn, x["optimum"], dw, df, gew, kz(w), kz(f)))
        if qual["Wolke"] or qual["Fotos"]:
            gew = "Wolke" if qual["Wolke"] else "Fotos"; ander = "Fotos" if gew == "Wolke" else "Wolke"; x = q[gew]; gr = []
            if not q[ander]["daten_ok"]: gr.append("zu wenig Daten (%s)" % q[ander]["info"])
            elif q[ander]["auf_grenze"]: gr.append("Optimum auf der Suchgrenze")
            elif not q[ander]["signifikant"]: gr.append("Kurve nicht signifikant (%.1f MAD < %.1f oder Plateau >= halbe Suchbreite)" % (q[ander]["signif_mad"], TOR_K))
            else: gr.append("Einigkeit der Instanzen %.0f %% < %.0f %%" % (100 * q[ander]["einigkeit_anteil"], 100 * TOR_EINIG))
            st = "KORRIGIERT" if abs(x["optimum"] - ist) > tol else "BESTAETIGT"
            return fertig(st, gew, x["optimum"], "%s %.3f: %s blind (%s) -> %s gewinnt. %s: %s." % (nmn, x["optimum"], ander, "; ".join(gr), gew, gew, kz(x)))
        return fertig("OFFEN", None, ist, "%s: OFFEN, keine Quelle qualifiziert. Wolke: %s. Fotos: %s." % (nmn, kz(w), kz(f)))


def tor_bericht(res):
    for o in res:
        u_ = o["urteil"]; log("TOR %-28s gesetzt %8.3f  tol %.3f  -> %s" % (o["name"], o["gesetzt"], o["tol"], u_["status"])); log("     %s" % u_["grund"])
        for nm in ("wolke", "foto"):
            q = o[nm]; log("     %-6s Optimum %8.3f Plateau90 %.3f..%.3f (Breite %.3f, 95%%: %.3f) (b) %.1f MAD Gewinn gg. Istwert %.3f (d) Streuung %.3f, %.0f%% im Band (%d Inst.) (e) Grenze %s signifikant %s Daten %s | %s" % (nm, q["optimum"], q["plateau"][0], q["plateau"][1], q["plateau_breite"], q["plateau95_breite"], q["signif_mad"], q["gewinn"], q["einigkeit_mad"], 100 * q["einigkeit_anteil"], q["n_inst_mit_optimum"], q["auf_grenze"], q["signifikant"], q["daten_ok"], q["info"]))


def linie(A, B, schritt=0.03):
    A = np.asarray(A, float); B = np.asarray(B, float); k = max(2, int(np.linalg.norm(B - A) / schritt) + 1); return A + (B - A) * np.linspace(0, 1, k)[:, None]


def flaeche_raster(eck, schritt=0.05):
    """Trapez/Rechteck (4 Ecken 3D) -> Rasterpunkte (bilinear)."""
    e = [np.asarray(x, float) for x in eck]; n1 = max(2, int(np.linalg.norm(e[1] - e[0]) / schritt) + 1); n2 = max(2, int(np.linalg.norm(e[3] - e[0]) / schritt) + 1); out = []
    for a_ in np.linspace(0, 1, n1):
        for b_ in np.linspace(0, 1, n2): out.append((1 - b_) * ((1 - a_) * e[0] + a_ * e[1]) + b_ * ((1 - a_) * e[3] + a_ * e[2]))
    return np.array(out)


def sammeln(listen):
    """listen: [(punkte, instanz[, gewicht])]; gewicht +1 = Merkmal (soll Signal haben), -1 = Kontrollpunkt (Kontrast gegen Zufall; z. B. Luecke zwischen Stuetzen)."""
    P = np.vstack([np.asarray(t[0], float) for t in listen]); I = np.concatenate([np.full(len(t[0]), t[1]) for t in listen]); Wg = np.concatenate([np.full(len(t[0]), t[2] if len(t) > 2 else 1.0) for t in listen]); return dict(punkte=P, inst=I, gew=Wg)



def lade_wolke(pfad):
    W = np.load(pfad); return (W["P"] if hasattr(W, "files") else W)[:, :3].astype(np.float32)


def wolke_kasten(W, sweeps, zen, rand=3.0):
    """Wolke + Tiefen-Sweep, auf den Kasten um die Instanzzentren (+ rand m) beschnitten (Speicher)."""
    lo = zen.min(0) - rand; hi = zen.max(0) + rand; P = [W]
    for pf in sweeps: P.append(np.load(pf)["P"][:, :3].astype(np.float32))
    C = np.vstack([p_[(p_ >= lo).all(1) & (p_ <= hi).all(1)] for p_ in P]); return C




# ----------------------------------------------------------------------------------------------- Kanten-Ebene (neutral)
def _nin(nrm, d):
    v = np.cross(nrm, d); l = np.linalg.norm(v)
    if l < 1e-6: v = np.cross([0, 0, 1.0], d); l = np.linalg.norm(v)
    return v / l


def kanten_dofs(members, nrm, ende_laenge=0.3, tiefe=False):
    """Freiheitsgrade einer Kopplungsgruppe (members = Kantendicts mit A,B[,vorzeichen]). Je Dof: dict(name, werte, gesetzt, tol, feat). Alle Merkmale sind Punktmengen: Linien (Versatz) bzw.
    Aenderungspunkt-Profil (Ende): Punkte entlang der Verlaengerung s in [-L, +L] mit Gewicht +1 (s <= v: Kante soll da sein) und -1 (s > v: soll nichts sein)."""
    nrm = np.asarray(nrm, float); A = [np.asarray(m["A"], float) for m in members]; B = [np.asarray(m["B"], float) for m in members]; D = [(b - a_) / np.linalg.norm(b - a_) for a_, b in zip(A, B)]
    sg = [float(m.get("vorzeichen", 1.0)) for m in members]; N = [_nin(nrm, d) for d in D]
    dofs = [dict(name="versatz_ebene", werte=np.arange(-0.80, 0.80 + 1e-9, 0.01), gesetzt=0.0, tol=0.05, feat=lambda v: sammeln([(linie(A[i] + sg[i] * v * N[i], B[i] + sg[i] * v * N[i]), i) for i in range(len(A))]))]
    if tiefe: dofs.append(dict(name="versatz_tiefe", werte=np.arange(-0.30, 0.30 + 1e-9, 0.01), gesetzt=0.0, tol=0.05, feat=lambda v: sammeln([(linie(A[i] + v * nrm, B[i] + v * nrm), i) for i in range(len(A))])))
    for nm, P0, sgn in (("ende_a", A, -1.0), ("ende_b", B, 1.0)):
        def feat(v, P0=P0, sgn=sgn):
            ss = np.arange(-ende_laenge, ende_laenge + 1e-9, 0.03); L = []
            for i in range(len(A)):
                pts = P0[i][None] + sgn * D[i][None] * ss[:, None]; w = np.where(ss <= v + 1e-9, 1.0, -1.0); L.append((pts, i, None)); L[-1] = (pts, i, 1.0)
            out = sammeln([(l[0], l[1]) for l in L]); out["gew"] = np.concatenate([np.where(ss <= v + 1e-9, 1.0, -1.0) for _ in range(len(A))]); return out
        dofs.append(dict(name=nm, werte=np.arange(-0.24, 0.24 + 1e-9, 0.03), gesetzt=0.0, tol=0.06, feat=feat))
    zen = np.array([0.5 * (a_ + b) for a_, b in zip(A, B)]); return dofs, zen, N


def trenne_gruppe(o, tol):
    """Kopplung aufbrechen: Je-Kante-Optima (Quelle mit mehr belastbaren Kanten) in Cluster (Luecke > tol); aufgetrennt wird nur bei >= 2 Clustern mit je >= 2 Kanten.
    Rueckgabe (Quelle, [Indexlisten]) oder None."""
    best = None
    for nm in ("foto", "wolke"):
        q = o[nm]; opt = np.array(q.get("opt_je_kante", []), float)
        if not q["daten_ok"] or np.isfinite(opt).sum() < 4: continue
        idx = np.where(np.isfinite(opt))[0]; od = np.argsort(opt[idx]); cl = [[idx[od[0]]]]
        for k_ in od[1:]:
            if opt[idx[k_]] - opt[cl[-1][-1]] > tol: cl.append([idx[k_]])
            else: cl[-1].append(idx[k_])
        cl2 = [c for c in cl if len(c) >= 2]
        if len(cl2) >= 2 and (best is None or len(idx) > best[2]): best = (nm, cl2, len(idx), [float(np.median(opt[c])) for c in cl2])
    return best


def kanten_tor(F, cloud, WK, K, tiefe=False, ende=True, audit_log=None):
    """K = {"rahmen":{"n"}, "kanten":[{id,A,B,gruppe,vorzeichen?}]}. Rueckgabe Liste je Kante: id, gruppe, status je Dof, versatz, Begruendung."""
    nrm = K["rahmen"]["n"]; T = Tor(F, cloud); T.F_cloudW = WK; gr = {}
    for k_ in K["kanten"]: gr.setdefault(k_["gruppe"], []).append(k_)
    kanten_aus = {k_["id"]: dict(id=k_["id"], gruppe=k_["gruppe"], A=k_["A"], B=k_["B"], dofs={}) for k_ in K["kanten"]}; bericht = []
    for gname, mem in gr.items():
        def laufe(members, tag):
            dofs, zen, N = kanten_dofs(members, nrm, tiefe=tiefe); res = []
            for q in dofs:
                if q["name"].startswith("ende") and not ende: continue
                o = T.sweep("%s/%s" % (tag, q["name"]), q["feat"], q["werte"], q["gesetzt"], q["tol"], zen); res.append(o)
            return res
        log("=== Gruppe %s: %d Kanten" % (gname, len(mem))); res = laufe(mem, gname); tor_bericht(res); verwendet = [(mem, res, gname, None)]
        o_eb = res[0]; sp = trenne_gruppe(o_eb, o_eb["tol"]) if len(mem) >= 4 else None
        if sp:
            nm, cls, nn, meds = sp; log("  Kopplung %s: je-Kante-Optima (%s) in %d Clustern %s (Kanten %s) -> Untergruppen werden einzeln geprueft" % (gname, nm, len(cls), np.round(meds, 3).tolist(), [len(c) for c in cls]))
            subs = []
            for ci, c in enumerate(cls):
                sm_ = [mem[i] for i in c]; sres = laufe(sm_, "%s#%d" % (gname, ci)); tor_bericht(sres); subs.append((sm_, sres, "%s#%d" % (gname, ci), dict(quelle=nm, median=meds[ci])))
            if all(s_[1][0]["urteil"]["status"] in ("KORRIGIERT", "BESTAETIGT", "GRUEN") for s_ in subs):
                verwendet = subs; log("  Kopplung %s AUFGETRENNT: je Untergruppe signifikant entschieden (%s); Begruendung: je-Kante-Optima der Quelle %s bilden %d getrennte Cluster (Mediane %s), jede Untergruppe besteht ihren eigenen Sweep" % (gname, [s_[1][0]["urteil"]["status"] for s_ in subs], nm, len(cls), np.round(meds, 3).tolist()))
            else: log("  Kopplung %s bleibt (Untergruppen nicht je entschieden)" % gname)
        for members, rs, tag, info in verwendet:
            for ro in rs:
                for m in members: kanten_aus[m["id"]]["dofs"][ro["name"].split("/")[-1]] = dict(status=ro["urteil"]["status"], wert=ro["urteil"]["wert"], gruppe_tag=tag, grund=ro["urteil"]["grund"], quelle_wert=ro["urteil"]["quelle_wert"], aufgetrennt=bool(info))
            bericht += [dict(gruppe=tag, kanten=[m["id"] for m in members], **{k_: v for k_, v in ro.items()}) for ro in rs]
    return kanten_aus, bericht


def kanten_korrigieren(K, kanten_aus):
    """Korrigierte Kanten (nur bei KORRIGIERT): Versatz in der Ebene, Enden verlaengert/gekuerzt; Quelle 'beleg_tor'."""
    nrm = np.asarray(K["rahmen"]["n"], float); out = []
    for k_ in K["kanten"]:
        r = kanten_aus[k_["id"]]; A = np.asarray(k_["A"], float); B = np.asarray(k_["B"], float); d = (B - A) / np.linalg.norm(B - A); nin = _nin(nrm, d); sg = float(k_.get("vorzeichen", 1.0)); ch = []
        e = r["dofs"].get("versatz_ebene")
        if e and e["status"] == "KORRIGIERT": A = A + sg * e["wert"] * nin; B = B + sg * e["wert"] * nin; ch.append("versatz_ebene %+.3f" % e["wert"])
        ea = r["dofs"].get("ende_a"); eb = r["dofs"].get("ende_b")
        if ea and ea["status"] == "KORRIGIERT": A = A - d * ea["wert"]; ch.append("ende_a %+.3f" % ea["wert"])
        if eb and eb["status"] == "KORRIGIERT": B = B + d * eb["wert"]; ch.append("ende_b %+.3f" % eb["wert"])
        out.append(dict(id=k_["id"], gruppe=k_["gruppe"], A=[float(x) for x in A], B=[float(x) for x in B], quelle="beleg_tor" if ch else "unveraendert", aenderung=ch))
    return out


def kantenliste_lesen(K):
    """Format von koerper_kantenliste.py export ({segmente:[{id,p0,p1,gruppe_id,instanz,spiegel_partner,parameter}], gruppen, rahmen}) -> interne Form; Parameterpfad je Kante bleibt erhalten."""
    if "segmente" not in K: return K, {}
    ed = []; par = {}
    for sg in K["segmente"]:
        ed.append(dict(id=str(sg["id"]), A=sg["p0"], B=sg["p1"], gruppe=sg["gruppe_id"], instanz=sg.get("instanz"), spiegel_partner=sg.get("spiegel_partner"))); par[str(sg["id"])] = sg.get("parameter", {})
    return dict(rahmen=K.get("rahmen", {}), kanten=[e for e in ed], gruppen=K.get("gruppen", {})), par


def tor_json(K, par, ka, korr):
    """TOR.json fuer koerper_kantenliste.py zuruecklesen: je Einzelpfad ein Wert (absolute Koordinate entlang der Achse 'z'); zusammengesetzte Pfade (a|b) werden nicht geschrieben, sondern als offen gemeldet."""
    out = []; offen = []; kd = {c["id"]: c for c in korr}
    for tag in sorted({d_["gruppe_tag"] for r in ka.values() for dn, d_ in r["dofs"].items() if dn == "versatz_ebene"}):
        mem = [k_ for k_ in K["kanten"] if ka[k_["id"]]["dofs"].get("versatz_ebene", {}).get("gruppe_tag") == tag]; st = ka[mem[0]["id"]]["dofs"]["versatz_ebene"]
        if st["status"] != "KORRIGIERT": continue
        pf = {}
        for k_ in mem:
            p_ = par.get(k_["id"], {}); pf.setdefault((p_.get("datei"), p_.get("pfad"), p_.get("achse")), []).append(kd[k_["id"]])
        for (dat, pfad, ach), cs in pf.items():
            if not dat or not pfad: continue
            if "|" in pfad or ach != "z": offen.append(dict(pfad=pfad, achse=ach, wert_ebene=st["wert"], grund="zusammengesetzter Parameter bzw. Achse != z: Tor liefert Kantenversatz, Einzelpfad fehlt")); continue
            w_ = float(np.mean([0.5 * (c["A"][2] + c["B"][2]) for c in cs])); out.append(dict(parameter=dict(datei=dat, pfad=pfad), wert=w_, quelle=st.get("quelle_wert"), begruendung=st["grund"], gruppe=tag))
    return dict(korrekturen=out, offen=offen, werkzeug="kanten_tor.py")


def main():
    K = json.load(open(g("--kanten", "", str))); K, par = kantenliste_lesen(K)
    if "--rahmen" in a: R = json.load(open(g("--rahmen", "", str))); K["rahmen"] = dict(K.get("rahmen") or {}, n=R.get("n", K.get("rahmen", {}).get("n")))
    if "--gruppen" in a: keep = set(g("--gruppen", "", str).split(",")); K["kanten"] = [k_ for k_ in K["kanten"] if k_["gruppe"] in keep]
    WK = lade_wolke(g("--wolke", "", str)); F = Fotos(g("--kam", "", str), g("--stabil", "", str), g("--bilder", "", str))
    zen = np.array([0.5 * (np.array(k_["A"]) + np.array(k_["B"])) for k_ in K["kanten"]]); cloud = wolke_kasten(WK, [x for x in g("--sweep", "", str).split(",") if x], zen, 3.0)
    log("Kanten %d in %d Gruppen; Pruefkasten %d Wolken-/Sweeppunkte" % (len(K["kanten"]), len({k_["gruppe"] for k_ in K["kanten"]}), len(cloud)))
    ka, ber = kanten_tor(F, cloud, WK, K, tiefe="--tiefe" in a, ende="--ohne_ende" not in a); korr = kanten_korrigieren(K, ka)
    json.dump(dict(eingabe=g("--kanten", "", str), kanten=list(ka.values()), korrigiert=korr, parameter=ber, quelle="kanten_tor"), open(g("--out", "", str), "w"), indent=1, default=float)
    if par: tj = tor_json(K, par, ka, korr); pj = g("--out", "", str).replace(".json", "") + "_TOR.json"; json.dump(tj, open(pj, "w"), indent=1, default=float); log("TOR.json fuer zuruecklesen:", pj, len(tj["korrekturen"]), "Korrekturen,", len(tj["offen"]), "offen")
    cnt = {}
    for r in ka.values():
        for dn, d_ in r["dofs"].items(): cnt[(dn, d_["status"])] = cnt.get((dn, d_["status"]), 0) + 1
    log("Zusammenfassung (Dof, Status): Anzahl Kanten:", {"%s/%s" % k_: v for k_, v in sorted(cnt.items())}); log("geschrieben:", g("--out", "", str))
    if "--audit" in a: overlay_kanten(F, K, ka, korr, g("--audit", "", str), g("--fotos", "ip_IMG_6120,ip_IMG_6261", str).split(","))


def overlay_kanten(F, K, ka, korr, ziel, fotos):
    """Kanten nach Status gefaerbt (gruen = GRUEN/BESTAETIGT, orange = KORRIGIERT alte Lage, cyan = korrigierte Lage, rot = OFFEN) in Fotos; Fehlerliste je Kante als JSON-Zeilen neben dem Bild."""
    import cv2
    os.makedirs(ziel, exist_ok=True); st = lambda r: [d_["status"] for dn, d_ in r["dofs"].items() if dn == "versatz_ebene"] or ["OFFEN"]
    for foto in fotos:
        f = [x for x in F.KAM if x.endswith(foto) or foto in x]
        if not f: continue
        f = f[0]; k = F.KAM[f]; im = cv2.imread(os.path.join(F.bd, f)); sj = im.shape[1] / k["W"]; pts = []
        def zeichne(A, B, col, w=2):
            P = linie(A, B, 0.1); u, v, z = F.proj(f, P); u = u * sj; v = v * sj; ok = z > 1
            for i in range(len(u) - 1):
                if ok[i] and ok[i + 1]: cv2.line(im, (int(u[i]), int(v[i])), (int(u[i + 1]), int(v[i + 1])), col, w, cv2.LINE_AA)
            if ok.any(): pts.append((u[ok].mean(), v[ok].mean()))
        for k_, c_ in zip(K["kanten"], korr):
            s_ = st(ka[k_["id"]])[0]
            if s_ in ("GRUEN", "BESTAETIGT"): zeichne(k_["A"], k_["B"], (0, 200, 0))
            elif s_ == "KORRIGIERT": zeichne(k_["A"], k_["B"], (0, 140, 255), 1); zeichne(c_["A"], c_["B"], (255, 255, 0), 3)
            else: zeichne(k_["A"], k_["B"], (0, 0, 255))
        if pts:
            pts = np.array(pts); x0, x1, y0, y1 = int(max(0, pts[:, 0].min() - 120)), int(min(im.shape[1], pts[:, 0].max() + 120)), int(max(0, pts[:, 1].min() - 120)), int(min(im.shape[0], pts[:, 1].max() + 120)); im = im[y0:y1, x0:x1]
        s = 1800 / max(im.shape[:2])
        if s < 1: im = cv2.resize(im, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        pf = os.path.join(ziel, "kanten_tor_%s_entwurf.jpg" % foto); cv2.imwrite(pf, im, [cv2.IMWRITE_JPEG_QUALITY, 88]); log("Overlay:", pf)
    fl = [dict(id=r["id"], gruppe=r["gruppe"], **{dn: d_["status"] for dn, d_ in r["dofs"].items()}) for r in ka.values()]; json.dump(fl, open(os.path.join(ziel, "kanten_tor_fehlerliste.json"), "w"), indent=0)


# ----------------------------------------------------------------------------------------------- Beweistest
def synth_szene(tmp, kaempfer_mitte=1.95, kaempfer_seite=1.40, kaempfer_gesetzt=1.40, wolke_aus=False, wolke_falsch=False, rng_seed=3):
    """Synthetische Fassade (Ebene y = 0, x laengs, z hoch): 5 Fenstergruppen (Periode 4,0 m) a 3 Lichter (0,9 m) mit Pfosten und Kaempfer (Seitenlichter 1,40, Mittellicht 1,95 = HOEHER).
    Wolke = dichte Wandpunkte + Kantenpunkte (sigma 1,5 cm) auf den echten Kanten; 6 Kameras im Bogen, Stabilitaetskarten = die echten Kanten gezeichnet (+ Rauschlinien). Eingabe-Kanten tragen die Kaempferhoehe
    `kaempfer_gesetzt` fuer ALLE Lichter (Koerper-Fehler). Rueckgabe (K, Pfade)."""
    import cv2
    rng = np.random.default_rng(rng_seed); os.makedirs(tmp + "/stabil", exist_ok=True); os.makedirs(tmp + "/bilder", exist_ok=True); wl = 0.9; per = 4.0; kanten_wahr = []; kanten_gesetzt = []
    for gi in range(5):
        xc = (gi - 2) * per; px = [xc + (k - 1.5) * wl for k in range(4)]
        for k, x in enumerate(px): kanten_wahr.append((("pfosten%d_%d" % (gi, k)), [x, 0, 0.5], [x, 0, 2.6], "pfosten%d" % k))
        for k in range(3):
            zk = kaempfer_mitte if k == 1 else kaempfer_seite
            kanten_wahr.append((("kaempfer%d_%d" % (gi, k)), [px[k], 0, zk], [px[k + 1], 0, zk], "kaempfer"))
        kanten_wahr.append((("sohle%d" % gi), [px[0], 0, 0.5], [px[-1], 0, 0.5], "sohle"))
    Pw = np.column_stack([rng.uniform(-11, 11, 120000), rng.normal(0, 0.01, 120000), rng.uniform(0, 3.2, 120000)]); pts = []
    for _, A, B, _g in kanten_wahr:
        A = np.array(A, float); B = np.array(B, float); n = int(np.linalg.norm(B - A) / 0.004); t = rng.random(n)[:, None]; pts.append(A + (B - A) * t + rng.normal(0, 0.015, (n, 3)))
    E = np.vstack(pts).astype(np.float32); P = np.vstack([Pw, E]).astype(np.float32)               # P = Oberflaeche (Z-Puffer), E = Kantenpunkte (Signal der Quelle Wolke)
    if wolke_aus: E = E[:0]                                          # keine Kantenpunkte (Quelle Wolke blind)
    cams = {}
    for ci, az in enumerate(np.radians([-50, -30, -10, 10, 30, 50])):
        C = np.array([14 * np.sin(az), -14 * np.cos(az), 1.6]); z_ = -C / np.linalg.norm(C) * 0 + (np.array([0, 0, 1.5]) - C); z_ /= np.linalg.norm(z_); x_ = np.cross(z_, [0, 0, 1.0]); x_ /= np.linalg.norm(x_); y_ = np.cross(z_, x_); R = np.stack([x_, y_, z_]); t = -R @ C
        cams["synth_%d.jpg" % ci] = dict(Rn=R.tolist(), tn=t.tolist(), C=C.tolist(), f=2400.0, cx=1500.0, cy=2000.0, W=3000, H=4000, modell="SIMPLE_RADIAL", params=[2400.0, 1500.0, 2000.0, 0.0])
    json.dump(cams, open(tmp + "/kam.json", "w"))
    for fn, k in cams.items():
        im = np.zeros((2000, 1500), np.uint8); R = np.array(k["Rn"]); t = np.array(k["tn"])
        for _, A, B, _g in kanten_wahr:
            Q = np.array(A, float)[None] + (np.array(B, float) - np.array(A, float))[None] * np.linspace(0, 1, 60)[:, None]; X = R @ Q.T + t[:, None]; u = (k["f"] * X[0] / X[2] + k["cx"]) * 0.5; v = (k["f"] * X[1] / X[2] + k["cy"]) * 0.5
            for i in range(len(u) - 1): cv2.line(im, (int(u[i]), int(v[i])), (int(u[i + 1]), int(v[i + 1])), 255, 3)
        for _ in range(25): cv2.line(im, (int(rng.integers(0, 1500)), int(rng.integers(0, 2000))), (int(rng.integers(0, 1500)), int(rng.integers(0, 2000))), 200, 2)   # Rauschlinien
        cv2.imwrite(tmp + "/stabil/" + os.path.splitext(fn)[0] + ".png", im); cv2.imwrite(tmp + "/bilder/" + fn, np.zeros((40, 30), np.uint8))
    if wolke_falsch:                                                 # Wolke widerspricht: Kaempfer-Kantenpunkte bei +0,35 m versetzt (verrauscht, sigma 10 cm) und Originalkanten-Punkte entfernt
        keep = np.ones(len(E), bool)
        for _, A, B, gg in kanten_wahr:
            if gg == "kaempfer": A_ = np.array(A); B_ = np.array(B); m = (np.abs(E[:, 2] - A_[2]) < 0.05) & (E[:, 0] > A_[0]) & (E[:, 0] < B_[0]) & (np.abs(E[:, 1]) < 0.05); keep &= ~m
        E = E[keep]; extra = []
        for _, A, B, gg in kanten_wahr:
            if gg == "kaempfer": A_ = np.array(A, float) + [0, 0, 0.35]; B_ = np.array(B, float) + [0, 0, 0.35]; n = int(np.linalg.norm(B_ - A_) / 0.002); extra.append(A_ + (B_ - A_) * rng.random(n)[:, None] + rng.normal(0, 0.10, (n, 3)))
        E = np.vstack([E] + extra).astype(np.float32)
    np.savez(tmp + "/wolke.npz", P=P, E=E)
    K = dict(rahmen=dict(n=[0, 1, 0]), kanten=[])
    for kid, A, B, gg in kanten_wahr:
        A = list(A); B = list(B)
        if gg == "kaempfer": A[2] = B[2] = kaempfer_gesetzt
        K["kanten"].append(dict(id=kid, A=A, B=B, gruppe=gg, wahr_z=(kaempfer_mitte if kid.endswith("_1") else kaempfer_seite) if gg == "kaempfer" else None))
    return K, tmp


def synth_tor():
    """Beweistests des Beleg-Tors: (1) Mittel-Kaempfer hoeher: Kopplung wird aufgetrennt, Mittellicht korrigiert um +0,55 m, Seitenlichter bestaetigt; (2) Wolke leer: Fotos entscheiden (ENTSCHIEDEN),
    (3) Wolke widerspricht den Fotos (Kaempferpunkte +0,35 m): Quelle mit besseren Daten gewinnt mit Begruendung (kein Mitteln)."""
    import tempfile
    fehl = 0
    for fall, kw in (("1_mittel_hoeher", dict()), ("2_wolke_leer", dict(wolke_aus=True)), ("3_wolke_widerspricht", dict(wolke_falsch=True))):
        tmp = tempfile.mkdtemp(prefix="muster_synth_"); K, _ = synth_szene(tmp, **kw); F = Fotos(tmp + "/kam.json", tmp + "/stabil", tmp + "/bilder"); Z_ = np.load(tmp + "/wolke.npz"); WK = Z_["P"]; cloud = Z_["E"] if len(Z_["E"]) else np.zeros((1, 3), np.float32) + 1e6
        log("##### Synth-Fall", fall); ka, ber = kanten_tor(F, cloud, WK, dict(K, kanten=[k_ for k_ in K["kanten"] if k_["gruppe"] == "kaempfer"]), ende=False); korr = {c["id"]: c for c in kanten_korrigieren(dict(K, kanten=[k_ for k_ in K["kanten"] if k_["gruppe"] == "kaempfer"]), ka)}
        err = []
        for k_ in K["kanten"]:
            if k_["gruppe"] != "kaempfer": continue
            z_neu = korr[k_["id"]]["A"][2]; err.append(abs(z_neu - k_["wahr_z"])); st = ka[k_["id"]]["dofs"]["versatz_ebene"]["status"]
        log("Fall %s: max. Hoehenfehler korrigiert vs. wahr %.3f m; Status je Kante %s" % (fall, max(err), sorted({ka[k_["id"]]["dofs"]["versatz_ebene"]["status"] for k_ in K["kanten"] if k_["gruppe"] == "kaempfer"})))
        kid = [k_["id"] for k_ in K["kanten"] if k_["gruppe"] == "kaempfer"]; ok = max(err) < 0.05
        if fall == "2_wolke_leer": ok = ok and all(ka[i]["dofs"]["versatz_ebene"]["status"] in ("KORRIGIERT", "BESTAETIGT") and "Wolke blind" in ka[i]["dofs"]["versatz_ebene"]["grund"] for i in kid)
        log("SYNTH %s: %s" % (fall, "BESTANDEN" if ok else "FEHLGESCHLAGEN")); fehl += 0 if ok else 1
    log("Beweistest Beleg-Tor:", "alle bestanden" if not fehl else "%d Faelle fehlgeschlagen" % fehl); return fehl


if __name__ == "__main__" and "--kanten" in a: main()
if __name__ == "__main__" and "--synth" in a: sys.exit(synth_tor())
