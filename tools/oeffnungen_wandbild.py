#!/usr/bin/env python3
"""oeffnungen_wandbild.py - OEFFNUNGEN einer Wand aus ihrem Wandbild: Zone (Erkenner), TIEFE (Parallaxe der Einzelfoto-Orthos), UMRISS (Bildsegmentierung).
18.11.2026 (Agent Rueckwand/Laube, Kaufhaus-Laubenrueckwand). Grundsatz "Wandbild = Bauplan": Erkennen bestimmt nur die Zone; ob dort ein Loch ist, wie tief
es ist und welche Gestalt es hat, kommt aus den Bildern. Gedacht fuer jede Wand mit Fassadenbild (Aussenwand oder Innenwand aus fassade_ortho innenwaende).

  1. ZONEN aus fassade_parsing.py (elemente.json): 'fenster'-Kaesten nebeneinander (Luecke < --luecke) = ein Fenster (Lichter), 'tuer'-Kaesten ebenso;
     ein 'bogen'-Kasten, der eine Tuer enthaelt, erweitert deren Zone (Spitz-/Rundbogen-Tor). Andere Klassen (gaube, figur ...) werden nicht benutzt.
  2. TIEFE je Zone (Ebenen-Sweep ohne Wolke): ein Punkt L hinter der Wandebene erscheint im Ortho von Foto i um L * (C_i - P).d / (C_i - P).n (waagerecht) und
     L * (C_i - P).z / (C_i - P).n (senkrecht) verschoben. Fuer L = -0,2 .. 1,2 m werden die Einzelorthos (fassade_ortho --einzeln, 1 cm) zurueckgeschoben und die
     paarweise NCC im Zoneninneren gemittelt; Tiefe = bestes L innen MINUS bestes L im Wandring um die Zone (Kamerarest, gleiche Rechnung). Unter --loch_stufe = flaches
     Feld (Tafel, Bild, Schild), KEINE Oeffnung (Kaufhaus: OWLv2 hielt die Bronzetafel fuer ein Fenster).
  3. UMRISS aus dem feinen Wandbild (fassade_fein.py; wo es leer ist, aus dem groben Ortho): Wandfarbe = Median des Rings um die Zone, Lab-Abstand je Zelle, Schwelle Otsu,
     Schliessen/Oeffnen 3 cm, groesste Region(en) im Zoneninneren -> Aussenumriss (Polygon, 1 cm). Innerhalb des Umrisses: Zellen in Wandfarbe (Pfosten, Kaempfer, Rahmen)
     als 'stege' (Polygone) - der Generator setzt sie als Stege vor die Rueckwand.
Ausgabe JSON {fid: {o, d, n, oeffnungen: [{klasse, zone, tiefe, tiefe_innen, tiefe_ring, ncc, umriss [[u, z]..], stege [[[u, z]..]..], flach, quelle}]}} + Kontrollbild <aus>.jpg
(Wandbild | Segmentierung mit Umriss | Tiefenkurven). u entlang d der Fassade (fassaden.json), z absolut.
Generator: bauteile.oeffnungen_aus_wandbild(koerper, json, ...) (Niche bis zur gemessenen Tiefe, Stege, Eintrag in DURCH fuer aushoehlen + rueckwaende).
  /media/oem/scan/venv-seg/bin/python -I tools/oeffnungen_wandbild.py <objekt.json> <ortho_fein_ordner> --grob <ortho_ordner> --nur i00 --aus <x.json>
Grenzen: Tiefe braucht >= 2 Fotos mit verschiedenen Blickwinkeln auf die Zone (sonst 'tiefe': null -> Zone wird nicht gebaut); Umriss nur, wo sich die Oeffnung farblich
von der Wand abhebt (Glas, Torblatt); Profile der Gewaende (Stufen, Kehlen) macht dieses Werkzeug nicht (tools/form_aus_wandbild.py).
"""
import os, sys, json, glob, argparse, numpy as np, cv2


def zonen(elemente, luecke=0.35, rand_z=0.3):
    """Erkenner-Kaesten -> Zonen [(klasse, u0, u1, z0, z1)]."""
    def gruppe(kl):
        K = sorted([e for e in elemente if e["klasse"] == kl], key=lambda e: e["u0"]); G = []
        for e in K:
            if G and e["u0"] - G[-1][1] < luecke and min(e["z1"], G[-1][3]) - max(e["z0"], G[-1][2]) > 0.5 * min(e["z1"] - e["z0"], G[-1][3] - G[-1][2]):
                g = G[-1]; G[-1] = [min(g[0], e["u0"]), max(g[1], e["u1"]), min(g[2], e["z0"]), max(g[3], e["z1"])]
            else: G.append([e["u0"], e["u1"], e["z0"], e["z1"]])
        return G
    Z = [("fenster", *g) for g in gruppe("fenster")]
    for g in gruppe("tuer"):
        for b in [e for e in elemente if e["klasse"] == "bogen"]:
            if b["u0"] - 0.2 <= g[0] and g[1] <= b["u1"] + 0.2 and b["z0"] - rand_z <= g[2]: g = [min(g[0], b["u0"]), max(g[1], b["u1"]), g[2], max(g[3], b["z1"])]
        Z.append(("tuer", *g))
    return Z


def kameras(objekt_json):
    od = os.path.dirname(os.path.abspath(objekt_json)); K = {}
    for f in glob.glob(os.path.join(od, "messprotokoll", "K-*.json")):
        c = json.load(open(f)).get("kamera")
        if isinstance(c, dict) and "rvec" in c: R = cv2.Rodrigues(np.array(c["rvec"], float))[0]; K[os.path.basename(f)[2:-5]] = -R.T @ np.array(c["t"], float)
    return K


def tiefe_sweep(F, edir, C, zone, Ls, rand=0.25, min_fotos=2):
    """Parallaxen-Sweep (siehe Kopf). Liefert (L_innen, L_ring, ncc_innen_kurve, ncc_ring_kurve, n_fotos) oder None."""
    r = F["raster"]; zl = r["zelle"]; o, d, n = np.array(F["o"]), np.array(F["d"]), np.array(F["n"])
    u0, u1, z0, z1 = zone; ua, ub, za, zb = u0 - rand, u1 + rand, z0 - rand, z1 + rand
    j0, j1 = int((ua - r["u0"]) / zl), int(np.ceil((ub - r["u0"]) / zl)); i0, i1 = int((r["z1"] - zb) / zl), int(np.ceil((r["z1"] - za) / zl))
    j0, i0 = max(j0, 0), max(i0, 0); j1, i1 = min(j1, r["nu"]), min(i1, r["nz"])
    uu = r["u0"] + (np.arange(j0, j1) + 0.5) * zl; zz = r["z1"] - (np.arange(i0, i1) + 0.5) * zl; U, Z = np.meshgrid(uu, zz)
    innen = (U > u0 + 0.05) & (U < u1 - 0.05) & (Z > z0 + 0.05) & (Z < z1 - 0.05); ring = ~((U > u0 - 0.05) & (U < u1 + 0.05) & (Z > z0 - 0.05) & (Z < z1 + 0.05))
    Pm = np.array([*(o + 0.5 * (u0 + u1) * d), 0.5 * (z0 + z1)]); B = []
    for p in sorted(glob.glob(os.path.join(edir, "*.png"))):
        nr = os.path.basename(p)[:-4]
        if nr not in C: continue
        im = cv2.imread(p)
        if im is None: continue
        g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32); m = (im.sum(2) > 0).astype(np.float32)
        if m[i0:i1, j0:j1][innen].mean() < 0.8: continue
        v = C[nr] - Pm; vn = v[:2] @ n
        if vn <= 0.5: continue
        B.append((nr, g, m, (v[:2] @ d) / vn, v[2] / vn))
    if len(B) < min_fotos: return None
    spread = np.ptp([b[3] for b in B]) + np.ptp([b[4] for b in B])
    if spread < 0.3: return None                                                 # zu aehnliche Blickrichtungen: Tiefe nicht messbar
    def kurve(maske):
        out = []
        for L in Ls:
            S = []
            for nr, g, m, ru, rz in B:                                          # Punkt bei w = -L sieht Foto i bei u + L*ru, z + L*rz
                mx = ((U + L * ru) - r["u0"]) / zl - 0.5; my = (r["z1"] - (Z + L * rz)) / zl - 0.5
                S.append((cv2.remap(g, mx.astype(np.float32), my.astype(np.float32), cv2.INTER_LINEAR), cv2.remap(m, mx.astype(np.float32), my.astype(np.float32), cv2.INTER_NEAREST)))
            nc = []
            for a in range(len(S)):
                for b in range(a + 1, len(S)):
                    k = maske & (S[a][1] > 0) & (S[b][1] > 0)
                    if k.sum() < 200: continue
                    x = S[a][0][k] - S[a][0][k].mean(); y = S[b][0][k] - S[b][0][k].mean(); nc.append(float((x * y).sum() / (np.sqrt((x * x).sum() * (y * y).sum()) + 1e-6)))
            out.append(np.mean(nc) if nc else np.nan)
        return np.array(out)
    ki, kr = kurve(innen), kurve(ring)
    if np.isnan(ki).all() or np.isnan(kr).all(): return None
    return float(Ls[np.nanargmax(ki)]), float(Ls[np.nanargmax(kr)]), ki, kr, len(B)


def umriss(bild, F, zone, rand=0.15, oeffnen=0.03, min_m2=0.05):
    """Segmentierung (siehe Kopf). Liefert (umriss [[u, z]], stege [[[u, z]]], maske, ausschnitt) oder None."""
    r = F["raster"]; zl = r["zelle"]; u0, u1, z0, z1 = zone
    j0, j1 = max(int((u0 - rand - r["u0"]) / zl), 0), min(int(np.ceil((u1 + rand - r["u0"]) / zl)), r["nu"]); i0, i1 = max(int((r["z1"] - z1 - rand) / zl), 0), min(int(np.ceil((r["z1"] - z0 + rand) / zl)), r["nz"])
    A = bild[i0:i1, j0:j1]; gueltig = A.sum(2) > 0
    if gueltig.mean() < 0.7: return None
    lab = cv2.cvtColor(A, cv2.COLOR_BGR2LAB).astype(np.float32); H, W = gueltig.shape
    ri = int(rand / zl); innen = np.zeros((H, W), bool); innen[ri:H - ri, ri:W - ri] = True; ring = ~innen & gueltig
    # Oeffnung = DUNKLER als die Wand (Glas, Torblatt, Schatten der Leibung): Helligkeit L unter der Mitte zwischen Wand (Median des Rings) und dem dunklen Inneren (P10).
    # (Erste Fassung: Otsu auf dem Lab-Abstand zur Wandfarbe - Holzrahmen und halbe Lichter fielen heraus, Kaufhaus-Fenster 2 bekam einen zerrissenen Umriss.)
    Lw = float(np.median(lab[ring][:, 0])); Lp = float(np.percentile(lab[innen & gueltig][:, 0], 10)); t = 0.5 * (Lw + Lp)
    # ... UND farblich weg von der Wand: verschattete Wand (Gewoelbe ueber dem Tor) ist dunkel, behaelt aber ihren Farbton -> Abstand in a*/b* zur Wandfarbe mehr als halb so gross
    # wie der Abstand der Wandfarbe zum Unbunten (128, 128). Bei unbunter Wand (grauer Stein) greift nur die Helligkeit.
    ab_w = np.median(lab[ring][:, 1:], axis=0); bunt = np.linalg.norm(ab_w - 128.0); fremd = np.linalg.norm(lab[:, :, 1:] - ab_w, axis=2) > 0.5 * bunt if bunt > 8 else np.ones(gueltig.shape, bool)
    m = ((lab[:, :, 0] < t) & fremd & innen & gueltig).astype(np.uint8); k = max(int(oeffnen / zl), 1) * 2 + 1; K = np.ones((k, k), np.uint8)
    m = cv2.morphologyEx(cv2.morphologyEx(m, cv2.MORPH_CLOSE, K), cv2.MORPH_OPEN, K)
    n_, lb, st, _ = cv2.connectedComponentsWithStats(m)
    keep = [i for i in range(1, n_) if st[i, cv2.CC_STAT_AREA] * zl * zl >= min_m2]
    if not keep: return None
    mk = np.isin(lb, keep).astype(np.uint8)
    huelle = cv2.morphologyEx(mk, cv2.MORPH_CLOSE, np.ones((int(0.25 / zl) | 1,) * 2, np.uint8))          # Lichter + Pfosten zu einer Oeffnung (Pfosten < 25 cm)
    cs, _ = cv2.findContours(huelle, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE); c = max(cs, key=cv2.contourArea); c = cv2.approxPolyDP(c, 2.0, True)[:, 0, :]
    zu = lambda P: [[round(float(r["u0"] + (j0 + x + 0.5) * zl), 3), round(float(r["z1"] - (i0 + y + 0.5) * zl), 3)] for x, y in P]
    hm = np.zeros_like(mk); cv2.drawContours(hm, [c.reshape(-1, 1, 2)], -1, 1, -1)
    steg = ((hm > 0) & (mk == 0)).astype(np.uint8); steg = cv2.morphologyEx(steg, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    ss, _ = cv2.findContours(steg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    stege = [zu(cv2.approxPolyDP(s, 1.0, True)[:, 0, :]) for s in ss if cv2.contourArea(s) * zl * zl >= 0.004 and len(s) >= 3]
    return zu(c), stege, (mk, hm, i0, j0), A


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("fein", help="Ordner mit fassaden.json, ortho_<id>_fein.png, ortho_<id>_einzeln/ (1 cm)")
    ap.add_argument("--grob", help="Ordner mit elemente.json (fassade_parsing) und ortho_<id>.png (Ersatzbild, wo das feine leer ist)"); ap.add_argument("--nur"); ap.add_argument("--aus", required=True)
    ap.add_argument("--loch_stufe", type=float, default=0.06, help="Tiefe (m) ab der eine Zone als Oeffnung gilt (darunter flaches Feld)")
    ap.add_argument("--l_min", type=float, default=-0.2); ap.add_argument("--l_max", type=float, default=1.2); ap.add_argument("--l_schritt", type=float, default=0.02)
    a = ap.parse_args(); C = kameras(a.objekt); Ls = np.arange(a.l_min, a.l_max + 1e-9, a.l_schritt)
    FA = {F["id"]: F for F in json.load(open(os.path.join(a.fein, "fassaden.json")))["fassaden"]}
    EL = json.load(open(os.path.join(a.grob or a.fein, "elemente.json")))["fassaden"]; GR = {F["id"]: F for F in json.load(open(os.path.join(a.grob, "fassaden.json")))["fassaden"]} if a.grob else {}
    aus = {}; bilder = []
    for fid, F in FA.items():
        if (a.nur and fid not in a.nur.split(",")) or fid not in EL: continue
        fein = cv2.imread(os.path.join(a.fein, f"ortho_{fid}_fein.png")); grob = cv2.imread(os.path.join(a.grob, f"ortho_{fid}.png")) if a.grob else None
        if grob is not None and fein is not None:      # Ersatz: grobes Ortho auf das feine Raster ziehen, wo das feine leer ist (gleiche Ebene, gleicher Rahmen)
            g2 = cv2.resize(grob, (fein.shape[1], fein.shape[0]), interpolation=cv2.INTER_CUBIC); leer = fein.sum(2) == 0; fein[leer] = g2[leer]
        oe = []
        for kl, u0, u1, z0, z1 in zonen(EL[fid]["elemente"]):
            e = dict(klasse=kl, zone=[round(u0, 3), round(u1, 3), round(z0, 3), round(z1, 3)])
            ts = tiefe_sweep(F, os.path.join(a.fein, f"ortho_{fid}_einzeln"), C, (u0, u1, z0, z1), Ls)
            if ts is None: e.update(tiefe=None, hinweis="Tiefe nicht messbar (zu wenige/zu aehnliche Fotos)"); oe.append(e); continue
            li, lr, ki, kr, nf = ts; e.update(tiefe=round(li - lr, 3), tiefe_innen=round(li, 3), tiefe_ring=round(lr, 3), ncc_innen=round(float(np.nanmax(ki)), 3), ncc_ring=round(float(np.nanmax(kr)), 3), fotos=nf)
            e["flach"] = bool(e["tiefe"] < a.loch_stufe)
            um = umriss(fein, F, (u0, u1, z0, z1)) if not e["flach"] else None
            if um: e.update(umriss=um[0], stege=um[1])
            e["quelle"] = f"Zone OWLv2 (fassade_parsing); Tiefe Parallaxen-Sweep ueber {nf} Einzelfoto-Orthos (innen {li:+.2f} minus Ring {lr:+.2f}); Umriss Lab-Abstand zur Wandfarbe (Otsu) im feinen Wandbild"
            oe.append(e); bilder.append((fid, e, um, ki, kr))
            print(f"{fid} {kl:7s} u {u0:6.2f}..{u1:6.2f} z {z0:4.2f}..{z1:4.2f}: Tiefe {e['tiefe']:+.2f} (innen {li:+.2f}, Ring {lr:+.2f}, NCC {e['ncc_innen']:.2f}/{e['ncc_ring']:.2f}, {nf} Fotos)"
                  + (" FLACH (keine Oeffnung)" if e["flach"] else f", Umriss {len(e.get('umriss', []))} Ecken, {len(e.get('stege', []))} Stege"))
        aus[fid] = dict(o=F["o"], d=F["d"], n=F["n"], innen=F.get("innen", False), oeffnungen=oe)
    json.dump(aus, open(a.aus, "w"), indent=1, ensure_ascii=False)
    tafeln = []                                                                  # Kontrollbild je Zone: Ausschnitt | Maske+Umriss | Tiefenkurven
    for fid, e, um, ki, kr in bilder:
        F = FA[fid]; r = F["raster"]; zl = r["zelle"]; u0, u1, z0, z1 = e["zone"]
        A = fein[max(int((r["z1"] - z1 - 0.15) / zl), 0):int((r["z1"] - z0 + 0.15) / zl), max(int((u0 - 0.15 - r["u0"]) / zl), 0):int((u1 + 0.15 - r["u0"]) / zl)].copy() if um is None else um[3].copy()
        B_ = A.copy()
        if um is not None:
            mk, hm, i0, j0 = um[2]; B_[mk > 0] = (0.5 * B_[mk > 0] + (0, 0, 127)).astype(np.uint8)
            P = np.array([[(u_ - r["u0"]) / zl - 0.5 - j0, (r["z1"] - z_) / zl - 0.5 - i0] for u_, z_ in e["umriss"]], np.int32); cv2.polylines(B_, [P], True, (0, 255, 255), 2)
            for s in e["stege"]: cv2.polylines(B_, [np.array([[(u_ - r["u0"]) / zl - 0.5 - j0, (r["z1"] - z_) / zl - 0.5 - i0] for u_, z_ in s], np.int32)], True, (255, 255, 0), 1)
        h = 300; s_ = h / A.shape[0]; A = cv2.resize(A, None, fx=s_, fy=s_); B_ = cv2.resize(B_, None, fx=s_, fy=s_)
        G = np.full((h, 260, 3), 255, np.uint8)
        for k_, col in ((ki, (0, 0, 255)), (kr, (0, 160, 0))):
            q = np.nan_to_num(k_, nan=np.nanmin(k_)); q = (q - q.min()) / (np.ptp(q) + 1e-6)
            cv2.polylines(G, [np.array([[int(10 + 240 * i / (len(q) - 1)), int(h - 40 - 200 * v)] for i, v in enumerate(q)], np.int32)], False, col, 2)
        cv2.putText(G, f"{e['klasse']} Tiefe {e['tiefe']:+.2f} m", (5, 20), 0, 0.5, (0, 0, 0), 1); cv2.putText(G, "rot innen, gruen Ring", (5, h - 10), 0, 0.45, (0, 0, 0), 1)
        cv2.putText(G, f"L {Ls[0]:.1f} .. {Ls[-1]:.1f} m", (5, h - 25), 0, 0.45, (0, 0, 0), 1)
        tafeln.append(np.hstack([A, B_, G]))
    if tafeln:
        Wm = max(t.shape[1] for t in tafeln); cv2.imwrite(a.aus[:-5] + ".jpg", np.vstack([np.pad(t, ((0, 6), (0, Wm - t.shape[1]), (0, 0)), constant_values=255) for t in tafeln]))
    print("->", a.aus)


if __name__ == "__main__":
    main()
