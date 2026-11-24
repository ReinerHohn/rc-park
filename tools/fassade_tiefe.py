#!/usr/bin/env python3
"""fassade_tiefe.py <objekt.json> <fassaden-ordner> <nr> [--zelle 0.04] [--w -0.8 2.5] [--dw 0.05] [--fotos a,b,...] [--min_m2 0.5] [--min_w 0.25]

VORBAUTEN AUTOMATISCH FINDEN: in welcher Tiefe vor/hinter der Wandebene wird das Mehrfoto-Bild scharf?
Nutzer 16.11.2026: Balkon vor der Wand braucht eine zweite Messebene - "mache den naechsten Automatisierungsschritt ... bald ein fast massstabsgetreuer Bauplan automatisch".
Bisher erkannte nur das Auge, dass ein Teil vor der Wand steht (im Fassadenbild doppelt/verschmiert). Jetzt Ebenen-Sweep:
  fuer w = --w in Schritten --dw: jede Wandzelle um w entlang der Normale verschieben, in alle Fotos der Fassade projizieren (Kameras K-<FOTO>.json), Grauwert lesen;
  oertlich normieren (Mittel/Streuung in 0,6 m, gegen Belichtung/Schatten); Kosten = mittlere Abweichung der Fotos von ihrem Median (uebereinstimmend = richtige Tiefe);
  Kosten ueber 5x5 Zellen glaetten; je Zelle die Tiefe mit den kleinsten Kosten, Sicherheit = Abstand zum Kostenmittel in Streuungen.
  Haeufigste sichere Tiefe = Wand selbst (Versatz der LoD2-Ebene wird gemeldet); w zaehlt ab dort.
  Zusammenhaengende sichere Bereiche mit |w| >= --min_w und Flaeche >= --min_m2 = VORBAU-/NISCHEN-KANDIDATEN mit eigener Ebene.
Ausgabe im Fassadenordner: tiefe_fNN.npz (w, sicher), tiefe_fNN.jpg (Tiefenbild neben Kostenminimum - ANSEHEN), vorbauten_fNN.json:
  [{u0, u1, z0, z1 (Wandkoordinaten der Fassade: u entlang d ab o), w_median, w_p10, w_p90, flaeche_m2, ebene: "nx,ny,0=d" fuer foto_mass.py --ebene}].
Danach: je Kandidat mit foto_mass.py auf SEINER Ebene messen bzw. fassade_ortho/fassade_fein auf dieser Ebene rechnen; bauen mit tools/bauteile.py.
Grenzen: braucht >= 3 Fotos mit Parallaxe (verschiedene Standorte); glatte Flaechen ohne Struktur (Putz) haben keine sichere Tiefe (bleiben 'unsicher', kein Kandidat);
keine Verdeckungspruefung; spiegelnde Scheiben und Baeume geben Fehltiefen - Kandidaten sind VORSCHLAEGE, am Bild pruefen.
"""
import sys, os, json, glob, argparse, numpy as np, cv2, torch, torch.nn.functional as Fn
from scipy import ndimage as ndi
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vorbauten_bauplan import wand_ebene_schaetzen, wand_ebene_w      # numpy-only, testbar ohne GPU


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("ordner"); ap.add_argument("nr", type=int); ap.add_argument("--zelle", type=float, default=0.04); ap.add_argument("--w", nargs=2, type=float, default=[-0.8, 2.5])
    ap.add_argument("--dw", type=float, default=0.05); ap.add_argument("--fotos"); ap.add_argument("--min_sicht_anteil", type=float, default=0.5, help="Tiefe nur werten, wenn so viele der auf der Wandebene sehenden Fotos sie sehen"); ap.add_argument("--min_basis", type=float, default=0.5, help="Mindestabstand der Kamerastandorte bei automatischer Fotowahl (m)"); ap.add_argument("--min_m2", type=float, default=0.5); ap.add_argument("--min_w", type=float, default=0.25); ap.add_argument("--sicher", type=float, default=1.5); ap.add_argument("--max_fotos", type=int, default=14); ap.add_argument("--min_wand", type=float, default=0.35, help="Tor: Anteil der sicheren Zellen auf der Wandtiefe (Schwabentor 16.11.: Nord 0,47 gut, Sued 0,43 gut (Wandversatz -0,75 = bekannter LoD2-Fehler), West 0,26 unbrauchbar)"); ap.add_argument("--fenster", type=int, default=11, help="Kosten ueber so viele Zellen mitteln (ungerade; 11 x 4 cm = 44 cm)")
    ap.add_argument("--ohne_neigung", action="store_true", help="Wand nur als konstanter Versatz (Verhalten bis 22.11.2026)"); ap.add_argument("--max_neigung", type=float, default=0.10, help="Guard: groesste Wandneigung gegen LoD2 (m/m), die als Lage-/Lotfehler ausgeglichen wird"); a = ap.parse_args()
    od = os.path.dirname(os.path.abspath(a.objekt)); root = os.path.dirname(os.path.dirname(od)); obj = json.load(open(a.objekt)); F = json.load(open(os.path.join(a.ordner, "fassaden.json")))["fassaden"][a.nr]
    o = np.array(F["o"]); d = np.array(F["d"]); n = np.array(F["n"]); u0, u1 = F["u"]; z0, z1 = F["z"]; c = a.zelle; W = int((u1 - u0) / c); H = int((z1 - z0) / c); dev = "cuda" if torch.cuda.is_available() else "cpu"
    namen = a.fotos.split(",") if a.fotos else sorted(F.get("fotos", {}), key=lambda k: -F["fotos"][k].get("zellen", 0))
    if not a.fotos:      # 18.11.2026 (Kaufhaus gk2: 241 Kamerapaare < 5 cm - Duplikate aus zwei Quellordnern, Serienbilder): ohne Parallaxe passen zwei Bilder in JEDER Tiefe -> Sweep landete am Rand (-15 m). Standorte mit Mindestabstand waehlen
        wahl = []; cz = []
        for nm in namen:
            kf = os.path.join(od, "messprotokoll", "K-" + nm + ".json")
            if not os.path.exists(kf): continue
            k_ = json.load(open(kf))["kamera"]; c_ = -cv2.Rodrigues(np.array(k_["rvec"]))[0].T @ np.array(k_["t"])
            if any(np.linalg.norm(c_ - q_) < a.min_basis for q_ in cz): continue
            wahl.append(nm); cz.append(c_)
            if len(wahl) >= a.max_fotos: break
        print(f"Fotowahl: {len(wahl)} Standorte mit >= {a.min_basis} m Abstand (aus {len(namen)} Fotos mit Wandzellen)"); namen = wahl
    if len(namen) < 3: print(f"nur {len(namen)} Fotos - kein Tiefen-Sweep moeglich"); return 2
    jj, ii = torch.meshgrid(torch.arange(W, device=dev), torch.arange(H, device=dev), indexing="xy"); U = u0 + (jj + 0.5) * c; Z = z1 - (ii + 0.5) * c
    B = torch.stack([o[0] + U * d[0], o[1] + U * d[1], Z], -1).reshape(-1, 3).float(); nv = torch.tensor([n[0], n[1], 0.0], device=dev).float(); K = []; G = []; cen = []
    for nm in namen:
        kf = os.path.join(od, "messprotokoll", "K-" + nm + ".json"); ff = glob.glob(os.path.join(root, obj["fotos_dir"], nm + ".*"))
        if not os.path.exists(kf) or not ff: continue
        k = json.load(open(kf))["kamera"]
        if k.get("tiefe_unsicher"): continue      # 16.11.2026: Abstand/Zoom dieser Kamera nicht belegt (kamera_verfeinern Tiefenspanne-Tor) - fuer Tiefen VOR/HINTER der Wand unbrauchbar
        im = cv2.imread(ff[0], 0)
        if im is None: continue
        s = min(1.0, 2400.0 / max(im.shape)); im = cv2.resize(im, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else im
        R = cv2.Rodrigues(np.array(k["rvec"]))[0]; K.append((torch.tensor(R, device=dev).float(), torch.tensor(k["t"], device=dev).float(), k["f_px"] * s, k["cx"] * s, k["cy"] * s, float(k.get("k1") or 0))); G.append(torch.tensor(im, device=dev).float()[None, None]); cen.append(-R.T @ np.array(k["t"]))
    N = len(K); cen = np.array(cen); basis = float(np.linalg.norm(cen - cen.mean(0), axis=1).max()) if N else 0.0; print(f"Fassade f{a.nr:02d}: {W}x{H} Zellen a {c * 100:.0f} cm, {N} Fotos, groesster Standortabstand vom Mittel {basis:.1f} m")
    if N < 3: print("zu wenige Fotos mit Kamera"); return 2
    def lies(i, w):
        R, t, f, cx, cy, k1 = K[i]; p = (B + w * nv) @ R.T + t; zc = p[:, 2].clamp(min=0.3); x = p[:, 0] / zc; y = p[:, 1] / zc; q = 1 + k1 * (x * x + y * y); h, b = G[i].shape[2:]
        gx = (f * x * q + cx) / (b - 1) * 2 - 1; gy = (f * y * q + cy) / (h - 1) * 2 - 1; ok = (gx.abs() < 1) & (gy.abs() < 1) & (p[:, 2] > 0.3)
        v = Fn.grid_sample(G[i], torch.stack([gx, gy], -1)[None, None], align_corners=True)[0, 0, 0]; return v.reshape(H, W), ok.reshape(H, W)
    kq = max(3, int(round(0.6 / c)) | 1)
    def norm(v, ok):
        m = ok.float()[None, None]; x = v[None, None] * m; mu = Fn.avg_pool2d(x, kq, 1, kq // 2) / Fn.avg_pool2d(m, kq, 1, kq // 2).clamp(min=1e-3); var = Fn.avg_pool2d((x - mu * m) ** 2, kq, 1, kq // 2) / Fn.avg_pool2d(m, kq, 1, kq // 2).clamp(min=1e-3)
        return ((v - mu[0, 0]) / (var[0, 0].sqrt() + 4.0)), var[0, 0].sqrt()
    ws = np.arange(a.w[0], a.w[1] + 1e-6, a.dw); B0 = B

    def sweep(Bs):
        """Ein Ebenen-Sweep um die Bezugsflaeche Bs (je Zelle ein 3D-Punkt): w_best (relativ zu Bs), sicher, gut, struktur, gesehen."""
        nonlocal B
        B = Bs; kosten = torch.empty((len(ws), H, W), device=dev); struktur = torch.zeros((H, W), device=dev); gesehen = torch.zeros((H, W), device=dev)
        # 18.11.2026 (Kaufhaus gk2 f02, Suchbereich -15..+1: Scheinminimum am Rand -15 m, mit -6/-10 Wand richtig -0,20): tief hinter der Wand sehen nur noch wenige, eng
        # stehende Kameras die Ebene und stimmen 'gut' ueberein. Eine Tiefe zaehlt nur, wenn >= min_sicht_anteil der Fotos sie sieht, die die Zelle auf der Wandebene sehen.
        cnt0 = torch.stack([lies(i, 0.0)[1] for i in range(N)]).sum(0); cnt_min = torch.clamp(torch.ceil(a.min_sicht_anteil * cnt0.float()), min=3)
        for wi, w in enumerate(ws):
            V = []; O = []; S = []
            for i in range(N): v, ok = lies(i, float(w)); nvv, sd = norm(v, ok); V.append(nvv); O.append(ok); S.append(sd)
            V = torch.stack(V); O = torch.stack(O); cnt = O.sum(0); Vn = torch.where(O, V, torch.full_like(V, float("nan"))); med = torch.nanmedian(Vn, 0).values
            ab = torch.where(O, (V - med).abs(), torch.zeros_like(V)).sum(0) / cnt.clamp(min=1); ab = torch.where(cnt >= cnt_min, ab, torch.full_like(ab, 9.0)); kosten[wi] = Fn.avg_pool2d(ab[None, None], a.fenster, 1, a.fenster // 2)[0, 0]
            if abs(w) < a.dw / 2: struktur = torch.stack(S).mean(0); gesehen = cnt
        kmin, arg = kosten.min(0); kmit = kosten.mean(0); kstd = kosten.std(0); sicher = ((kmit - kmin) / (kstd + 1e-6)).cpu().numpy(); wbest = ws[arg.cpu().numpy()]; struktur = struktur.cpu().numpy(); gesehen = gesehen.cpu().numpy()
        gut = (sicher >= a.sicher) & (struktur > 6.0) & (gesehen >= 3) & (kmin.cpu().numpy() < 0.5)
        _arg = arg.cpu().numpy(); gut &= (_arg >= 2) & (_arg <= len(ws) - 3)      # 18.11.2026: Minimum in den 2 Randschritten = Kosten fallen nur weiter (kein echtes Minimum; Kaufhaus gk2 f02 Scheinwand bei -15 m)
        return wbest, sicher, gut, struktur, gesehen

    wbest, sicher, gut, struktur, gesehen = sweep(B0)
    # 22.11.2026 (Schwabentor-1122 f00, Bilderker fehlte): die Wand stand im Kamerarahmen GENEIGT gegen die LoD2-Ebene (dichte Wolke und Sweep: 0 m am Boden, -0,45 bei z 12,
    # -1,4 bei z 33 = Lotfehler der Ausrichtung ~2,6 Grad). Mit konstantem Wandversatz verschmierte die Wandtiefe, lag ab z 15 ausserhalb des Suchbereichs, Tor 31 % < 35 % ->
    # 'nicht belastbar' -> kein Vorbau. Jetzt: Wand als geneigte Ebene schaetzen (wand_ebene_schaetzen, Guard), zweiter Sweep RELATIV zu dieser Ebene. Gespeichertes w und
    # wand_versatz_m beziehen sich auf die Ebene am Fassadenfuss (u Mitte, z unten = Grundriss, dort sitzt die LoD2-Wand); Neigung in vorbauten_fNN.json 'wand_ebene'.
    Un, Zn = U.cpu().numpy(), Z.cpu().numpy(); u_ref, z_ref = 0.5 * (u0 + u1), float(z0)
    we = None if a.ohne_neigung else wand_ebene_schaetzen(Un, Zn, wbest, gut, u_ref, z_ref, max_neigung=a.max_neigung)
    if we:
        print(f"Wandebene GENEIGT gegen LoD2: {we['b_u'] * 100:+.1f} cm/m entlang u, {we['c_z'] * 100:+.1f} cm/m nach oben ({we['neigung_grad']:.1f} Grad), Fuss {we['a']:+.2f} m; "
              f"auf der Ebene {we['inlier']} statt {we['inlier_konst']} Zellen konstant -> zweiter Sweep relativ zur geneigten Ebene")
        plan = torch.tensor(we["a"] + we["b_u"] * (Un - u_ref) + we["c_z"] * (Zn - z_ref), device=dev).float().reshape(-1, 1)
        wbest, sicher, gut, struktur, gesehen = sweep(B0 + plan * nv)
    hist, kanten = np.histogram(wbest[gut], bins=len(ws), range=(ws[0] - a.dw / 2, ws[-1] + a.dw / 2)); w_wand = float(ws[int(np.argmax(hist))])      # haeufigste sichere Tiefe = die Wand selbst (LoD2-Ebene liegt oft 0,1-0,3 m daneben)
    print(f"Wandebene: haeufigste sichere Tiefe {w_wand:+.2f} m gegen die " + ("geneigte Wandebene" if we else "Fassadenebene (LoD2)") + " - Kandidaten zaehlen relativ dazu")
    wm = ndi.median_filter(np.where(gut, wbest - w_wand, 0.0), 7)
    wand_anteil = float((gut & (np.abs(wm) < 0.12)).sum() / max(gut.sum(), 1)); belastbar = wand_anteil >= a.min_wand and gut.mean() >= 0.3 and (a.w[0] + 3 * a.dw) < w_wand < (a.w[1] - 3 * a.dw)      # Wandtiefe am Rand des Suchbereichs = kein echtes Minimum
    print(f"Guete: {wand_anteil * 100:.0f} % der sicheren Zellen liegen auf der Wandtiefe (Tor >= {a.min_wand * 100:.0f} %), sichere Tiefe auf {gut.mean() * 100:.0f} % der Wand -> " + ("belastbar" if belastbar else "NICHT BELASTBAR (zu wenig Parallaxe / falsche Kameras) - keine Kandidaten"))
    out = []; rel_lo, rel_hi = a.w[0] - w_wand + 2 * a.dw, a.w[1] - w_wand - 2 * a.dw            # Tiefen am Rand des Suchbereichs = kein Minimum gefunden (Draehte, Spiegelungen)
    for lo, hi in ((0.6, rel_hi), (a.min_w, 0.6), (rel_lo, -a.min_w * 0.8)):                      # Tiefenklassen getrennt segmentieren: weit vorn (Balkon/Vordach), knapp vorn (Gesims/Erkerfuss), hinten (Nische/Laibung)
        kand = ndi.binary_closing(ndi.binary_opening(gut & (wm >= lo) & (wm < hi), np.ones((3, 3))), np.ones((9, 9))); lab, nl = ndi.label(kand)
        for li, sl in enumerate(ndi.find_objects(lab), 1):
            m = lab[sl] == li; fl = m.sum() * c * c
            if fl < a.min_m2: continue
            wv = wm[sl][m & gut[sl]]
            if len(wv) < 20: continue
            wmd = float(np.median(wv)); uc_, zc_ = u0 + 0.5 * (sl[1].start + sl[1].stop) * c, z1 - 0.5 * (sl[0].start + sl[0].stop) * c
            P0 = o + n * (wmd + w_wand + (wand_ebene_w(we, uc_, zc_) if we else 0.0))      # Ebene im Kamerarahmen (foto_mass --ebene): ortsfeste Wand + Ausladung
            out.append(dict(u0=round(u0 + sl[1].start * c, 2), u1=round(u0 + sl[1].stop * c, 2), z0=round(z1 - sl[0].stop * c, 2), z1=round(z1 - sl[0].start * c, 2), w_median=round(wmd, 2), w_p10=round(float(np.percentile(wv, 10)), 2), w_p90=round(float(np.percentile(wv, 90)), 2),
                            flaeche_m2=round(float(fl), 1), art="Vorbau" if wmd > 0 else "Nische", ebene=f"{n[0]:.5f},{n[1]:.5f},0={float(n @ P0):.4f}"))
    if not belastbar: out = []
    A_ = we["a"] if we else 0.0      # gespeicherte Tiefen: relativ zur (geneigten) Wand + Wand am Fassadenfuss -> w - wand_versatz_m = Abstand zur oertlichen Wand (Verbraucher unveraendert)
    out.sort(key=lambda e: -e["flaeche_m2"]); np.savez_compressed(os.path.join(a.ordner, f"tiefe_f{a.nr:02d}.npz"), w=(wbest + A_).astype(np.float32), sicher=sicher.astype(np.float32), gut=gut, u0=u0, z1=z1, zelle=c, fenster_m=a.fenster * c)   # fenster_m: Kosten-Mittelungsfenster (m) - kleinere Loecher loest der Sweep nicht auf (fenster_tiefe_tor)
    json.dump(dict(fassade=a.nr, fotos=namen[:N], zelle=c, wand_versatz_m=round(w_wand + A_, 3), belastbar=bool(belastbar), wand_anteil=round(wand_anteil, 2), w_bereich=[round(a.w[0] + A_, 3), round(a.w[1] + A_, 3)],
                   wand_ebene=dict(we, a=round(we["a"] + w_wand, 3), hinweis="Wand im Kamerarahmen: w(u,z) = a + b_u*(u-u_ref) + c_z*(z-z_ref); a = wand_versatz_m") if we else None,
                   kandidaten=out, hinweis="Vorschlaege aus dem Ebenen-Sweep; am Bild tiefe_fNN.jpg pruefen, dann auf der eigenen Ebene messen"), open(os.path.join(a.ordner, f"vorbauten_f{a.nr:02d}.json"), "w"), indent=1)
    v0, _ = lies(0, 0.0); farbe = cv2.applyColorMap(np.clip((wbest - a.w[0]) / (a.w[1] - a.w[0]) * 255, 0, 255).astype(np.uint8), cv2.COLORMAP_TURBO); farbe[~gut] = (farbe[~gut] * 0.25).astype(np.uint8)
    bild = cv2.cvtColor(np.clip(v0.cpu().numpy(), 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
    for e in out:
        for b_ in (bild, farbe): cv2.rectangle(b_, (int((e["u0"] - u0) / c), int((z1 - e["z1"]) / c)), (int((e["u1"] - u0) / c), int((z1 - e["z0"]) / c)), (0, 0, 255), 1); cv2.putText(b_, f"{e['w_median']:+.2f}", (int((e["u0"] - u0) / c) + 2, int((z1 - e["z1"]) / c) + 12), 0, 0.4, (0, 0, 255), 1)
    cv2.imwrite(os.path.join(a.ordner, f"tiefe_f{a.nr:02d}.jpg"), np.hstack([bild, farbe]))
    print(f"sichere Tiefe auf {gut.mean() * 100:.0f} % der Wand; {len(out)} Kandidaten:")
    for e in out[:12]: print(f"  {e['art']:6s} u {e['u0']:6.2f}..{e['u1']:6.2f}  z {e['z0']:5.2f}..{e['z1']:5.2f}  w {e['w_median']:+.2f} m ({e['w_p10']:+.2f}..{e['w_p90']:+.2f})  {e['flaeche_m2']:.1f} m2")
    return 0 if belastbar else 4


if __name__ == "__main__":
    sys.exit(main())
