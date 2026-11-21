#!/usr/bin/env python3
"""ebenen_form.py - GESTALT eines Vorbaus aus dem feinen Wandbild AUF SEINER EIGENEN EBENE (21.11.2026, Kettenstufe 'bauplan').

Nutzer 21.11.: "Nein, nicht aus dem Baukasten. Du musst mit dem feinen Raster aus dem Bauplan die Kanten erkennen." Methode (LOGBUCH_SCHWABENTOR_KETTE_2026-11-21.md):
ein Gebaeude = mehrere Ebenen, jede Ebene bekommt ihren eigenen Bauplan. Der Ebenen-Sweep (fassade_tiefe -> vorbauten_bauplan) liefert nur ZONE und EBENE (w vor der Wand).
Hier je Vorbau-Gruppe aus audit/vorbauten_auto.json:
  1. Feines Wandbild (--px, Standard 1 cm) der Zone direkt aus den Fotos auf der Ebene der Front (form_aus_wandbild.wandbild_fotos, w = Wandversatz + Frontausladung).
     Probe Schwabentor: auf der Wandebene liegt die Bruestung 0,3 m zu hoch (Parallaxe), auf der eigenen Ebene trifft sie den Handstand auf ~0,1 m.
  2. FLAECHEN aus dem Bild: Farbklassen (k-means in Lab, --klassen), Oeffnen 5 cm (Draehte, Rauschen), zusammenhaengende Stuecke. Die Kanten der Stuecke = Bildkanten.
  3. TIEFE entscheidet je Stueck (nicht je Zelle - die Sweep-Tiefe ist auf ~0,4 m geglaettet): Median der sicheren Sweep-Zellen im Stueck; FRONT, wenn >= 60 % der Zellen
     >= halbe Frontausladung und der Median hoechstens --tol neben der Front liegt.
  4. Schmale Stuecke (< Glaettungsbreite des Sweeps, z. B. Pfosten), die der Sweep nicht aufloesen kann: FRONT, wenn sie eine Farbklasse haben, die ueberwiegend Front ist,
     und ein Frontstueck beruehren (Material laeuft durch). ANNAHME je Stueck im Bericht gezaehlt.
  5. Ausgabe: Umrisse (u, z) der Frontflaeche + Baender mit voller Tiefe bis zur Wand (aus dem Hoehenfeld: Zeilen mit >= 50 % Front = Boden/Bruestungskasten, Traufband)
     + gemessenes Vordach (Traufe, Anschluss) aus vorbauten_bauplan. Bau: bauteile.ebenen_form_aus_json. Kein Katalogteil.
Grenzen: nur die Frontebene. Schraege Streben/Konsolen UNTER dem Boden laufen zur Wand zurueck (Parallaxe) -> nicht gebaut, als 'offen' gemeldet. Staerke der Frontteile = ANNAHME (--dicke).
Aufruf:  ebenen_form.py <objekt.json> [--vorbauten audit/vorbauten_auto.json] [--tiefe_ordner <fassade>] [--aus audit/ebenen_form.json]
rc 0 = mindestens eine Ebene, rc 3 = keine.
"""
import sys, os, json, argparse, numpy as np, cv2
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def front_maske(img, A, G, front, px, klassen=6, tol=0.35, glatt=0.45, min_m2=0.03):
    """img BGR, A = Sweep-Tiefe relativ zur Wand je Bildzelle, G = sicher. -> (maske, bericht)."""
    H, W = img.shape[:2]; lab = cv2.cvtColor(cv2.bilateralFilter(img, 9, 40, 7), cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)
    cv2.setRNGSeed(1); _, lbl, _ = cv2.kmeans(lab, klassen, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0), 2, cv2.KMEANS_PP_CENTERS); lbl = lbl.reshape(H, W)
    of = max(3, int(round(0.05 / px)) | 1); St = []; fl_front = np.zeros(klassen); fl_stimme = np.zeros(klassen)
    for k in range(klassen):
        L, n = ndi.label(ndi.binary_opening(lbl == k, np.ones((of, of))))
        for i, sl in enumerate(ndi.find_objects(L), 1):
            r = L[sl] == i; fl = r.sum() * px * px
            if fl < min_m2: continue
            gz = G[sl][r]; breite = 2 * float(ndi.distance_transform_edt(r).max()) * px; e = dict(k=k, sl=sl, r=r, fl=fl, breite=breite, stimme=None)
            if gz.sum() >= 30 and gz.mean() >= 0.08:
                a = A[sl][r][gz]; e["wm"] = float(np.median(a)); e["vorn"] = float((a > 0.5 * front).mean()); e["stimme"] = bool(e["vorn"] >= 0.6 and abs(e["wm"] - front) <= tol)
                fl_stimme[k] += fl; fl_front[k] += fl if e["stimme"] else 0
            St.append(e)
    M = np.zeros((H, W), bool)
    for e in St:
        if e["stimme"]: M[e["sl"]] |= e["r"]
    KM = np.full((H, W), -1, np.int16)                    # Farbklasse der Frontzellen: ein schmales Stueck erbt nur von beruehrender Front GLEICHER Klasse (Material laeuft durch)
    for e in St:
        if e["stimme"]: KM[e["sl"]][e["r"]] = e["k"]
    front_kl = sorted({e["k"] for e in St if e["stimme"]}); geerbt = 0
    for _ in range(4):
        neu = False
        for e in St:
            if e["stimme"] or e.get("erbt") or e["breite"] >= glatt: continue
            sl = tuple(slice(max(0, s_.start - 5), s_.stop + 5) for s_ in e["sl"]); rr = np.zeros(KM[sl].shape, bool); rr[e["sl"][0].start - sl[0].start:e["sl"][0].start - sl[0].start + e["r"].shape[0], e["sl"][1].start - sl[1].start:e["sl"][1].start - sl[1].start + e["r"].shape[1]] = e["r"]
            if ((KM[sl] == e["k"]) & ndi.binary_dilation(rr, np.ones((9, 9)))).sum() >= 10: M[e["sl"]] |= e["r"]; KM[e["sl"]][e["r"]] = e["k"]; e["erbt"] = True; geerbt += 1; neu = True
        if not neu: break
    M = ndi.binary_closing(M, np.ones((of, of))); M = ndi.binary_opening(M, np.ones((max(3, int(round(0.07 / px)) | 1),) * 2))      # Mindestmass 0,8 mm in H0 = 7 cm
    return M, dict(stuecke=len(St), front=int(sum(1 for e in St if e["stimme"])), geerbt_schmal=geerbt, frontklassen=sorted(front_kl), flaeche_m2=round(float(M.sum() * px * px), 2))


def umrisse(M, zone, px, eps=0.015):
    cs, _ = cv2.findContours(M.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE); out = []
    for c in cs:
        if cv2.contourArea(c) * px * px < 0.01: continue
        c = cv2.approxPolyDP(c, eps / px, True)[:, 0, :]
        if len(c) >= 3: out.append([[round(zone[0] + (x + 0.5) * px, 3), round(zone[3] - (y + 0.5) * px, 3)] for x, y in c])
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--vorbauten"); ap.add_argument("--tiefe_ordner", required=True); ap.add_argument("--aus")
    ap.add_argument("--px", type=float, default=0.01); ap.add_argument("--k", type=int, default=5); ap.add_argument("--klassen", type=int, default=6); ap.add_argument("--tol", type=float, default=0.35)
    ap.add_argument("--dicke", type=float, default=0.2, help="Staerke der Frontteile (m) - ANNAHME, von vorn nicht messbar"); a = ap.parse_args()
    from form_aus_wandbild import wandbild_fotos, _ebene
    od = os.path.dirname(os.path.abspath(a.objekt)); vp = a.vorbauten or os.path.join(od, "audit", "vorbauten_auto.json"); aus = a.aus or os.path.join(od, "audit", "ebenen_form.json")
    if not os.path.exists(vp): print("keine vorbauten_auto.json"); return 3
    erg = []; bilder = []
    for F in json.load(open(vp)).get("fassaden", []):
        o = np.array(F["o"], float); d = np.array(F["d"], float); n = np.array(F["n"], float); A_, T_, N_ = _ebene(o, o + d, o + n); ww = float(F.get("w_wand", 0.0)); eb = []
        nz = os.path.join(a.tiefe_ordner, f"tiefe_f{F['nr']:02d}.npz")
        if not os.path.exists(nz): continue
        Z = np.load(nz); tw, tg, c, tu0, tz1 = Z["w"], Z["gut"], float(Z["zelle"]), float(Z["u0"]), float(Z["z1"])
        for g in F["gruppen"]:
            front = float(g["koerper"]["w_median"]); ga = g.get("galerie") or {}; vd = ga.get("vordach")
            z_unten = (ga.get("z_boden") or g["koerper"]["z0"]) - 0.4; z_oben = (vd["z_traufe"] if vd else g["z1"]) + 0.3; zone = (g["u0"] - 0.4, g["u1"] + 0.4, z_unten, z_oben)
            img, gueltig, qi = wandbild_fotos(a.objekt, A_, T_, N_, zone, a.px, w=ww + front, k=a.k)
            if img is None: print(f"{F['id']}: kein Wandbild auf der Ebene ({qi})"); continue
            H, W = img.shape[:2]; ix = lambda u: int(np.clip((u - tu0) / c, 0, tw.shape[1])); iz = lambda z: int(np.clip((tz1 - z) / c, 0, tw.shape[0]))
            At = cv2.resize((tw[iz(zone[3]):iz(zone[2]), ix(zone[0]):ix(zone[1])] - ww).astype(np.float32), (W, H), interpolation=cv2.INTER_NEAREST)
            Gt = cv2.resize(tg[iz(zone[3]):iz(zone[2]), ix(zone[0]):ix(zone[1])].astype(np.uint8), (W, H), interpolation=cv2.INTER_NEAREST) > 0
            M, ber = front_maske(img, At, Gt, front, a.px, klassen=a.klassen, tol=a.tol)
            feld = np.array(g["w"], float); r_ = float(g["raster"]); baender = []; voll = (feld >= 0.5 * front).mean(1); i = 0      # Baender mit voller Tiefe bis zur Wand (gemessen: Hoehenfeld)
            while i < len(voll):
                if voll[i] >= 0.5:
                    j = i
                    while j + 1 < len(voll) and voll[j + 1] >= 0.5: j += 1
                    zb1, zb0 = g["z1"] - i * r_, g["z1"] - (j + 1) * r_
                    if zb1 - zb0 >= 2 * r_ - 1e-6 and zb0 >= z_unten - 0.2 and zb1 <= z_oben + 0.2: sp = np.where((feld[i:j + 1] >= 0.5 * front).mean(0) >= 0.5)[0]; baender.append(dict(z0=round(zb0, 2), z1=round(zb1, 2), u0=round(g["u0"] + sp.min() * r_, 2), u1=round(g["u0"] + (sp.max() + 1) * r_, 2)))
                    i = j + 1
                else: i += 1
            eb.append(dict(zone=[round(x, 2) for x in zone], w_front=round(ww + front, 3), w_wand=round(ww, 3), dicke=a.dicke, polys=umrisse(M, zone, a.px), baender=baender, vordach=vd, bericht=ber,
                           fotos=[f_["foto"] for f_ in (qi or {}).get("fotos", [])][:a.k], offen="schraege Streben/Konsolen unter dem Boden (laufen zur Wand zurueck, Parallaxe auf der Frontebene) nicht gebaut",
                           quelle=f"feines Wandbild {a.px * 100:.0f} cm auf der Ebene w {ww + front:+.2f} m (Fotos), Farbflaechen + Sweep-Tiefe je Flaeche; Staerke {a.dicke} m = ANNAHME"))
            print(f"{F['id']}: EBENE w {ww + front:+.2f} m, Zone u {zone[0]:.2f}..{zone[1]:.2f} z {zone[2]:.2f}..{zone[3]:.2f}: {ber['flaeche_m2']} m2 Front aus {ber['front']} Flaechen (+{ber['geerbt_schmal']} schmale geerbt), {len(eb[-1]['polys'])} Umrisse, {len(baender)} Baender")
            vis = img.copy(); vis[M] = (0.4 * vis[M] + 0.6 * np.array([0, 220, 255])).astype(np.uint8); bilder.append(np.hstack([img, vis]))
        if eb: erg.append(dict(id=F["id"], nr=F["nr"], o=F["o"], d=F["d"], n=F["n"], ebenen=eb))
    os.makedirs(os.path.dirname(aus), exist_ok=True); json.dump(dict(quelle="tools/ebenen_form.py", fassaden=erg), open(aus, "w"))
    if bilder:
        h = max(b.shape[0] for b in bilder); b0 = np.vstack([np.pad(b, ((0, 0), (0, max(x.shape[1] for x in bilder) - b.shape[1]), (0, 0))) for b in bilder]); s = min(1.0, 2000.0 / b0.shape[1])
        cv2.imwrite(aus[:-5] + ".jpg", cv2.resize(b0, None, fx=s, fy=s, interpolation=cv2.INTER_AREA), [1, 85])
    nE = sum(len(e["ebenen"]) for e in erg); print(f"-> {aus}: {nE} Ebenen"); return 0 if nE else 3


if __name__ == "__main__": sys.exit(main())
