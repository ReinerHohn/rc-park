#!/usr/bin/env python3
"""druck_farbteile.py <objekt> --masken relief/nord_putz.npz,relief/sued_putz.npz[,...] [--stl PFAD] [--tief_mm 0.4] [--spiel_mm 0.15] [--min_m2 1.5] [--glatt_m 0.2] [--vor_m 0.4]
FARBTEILE: Steinflaechen einer Wand als EIGENE, flach druckbare Platten aus dem fertigen Modell loesen; der Koerper bekommt passende Taschen.

Anlass 17.11.2026 (Nutzer): "verschiedene Farben muessen eigene Teile sein - das Steinrelief ein anderes Teil als der Putz; dann muss ich nicht anmalen, es kann flach gedruckt
werden, und die Druckzeit zaehlt." Bisher: ein Teil = eine Farbe, Stein und Putz derselben Wand blieben zusammen (tools/druck_farben.py).
Verfahren (generisch, arbeitet am fertigen STL - der Generator bleibt unberuehrt):
  1. Je Maske (Reliefdatei mit Feld 'putz', Wandrahmen a/t/n/u0/z0/px wie tools/relief_einsatz.py): STEIN = nicht Putz. Reinigen: schliessen/oeffnen (15 cm), Loecher < min_m2
     fuellen, Inseln < min_m2 verwerfen (bleiben am Koerper = nachmalen). Je zusammenhaengender Flaeche eine Platte; hoeher als das Druckbett -> in Baender geteilt.
  2. Lage der Wandflaeche des Modells gegen die Maskenebene per Strahlen messen; Plattenrueckseite = tiefste 5 % des Reliefs + --tief_mm (Druck) Traegerschicht.
     Prisma der Flaeche von dort bis --vor_m vor der Ebene.  PLATTE = Modell geschnitten mit dem Prisma.
     KOERPER = Modell minus Prisma, das seitlich und in der Tiefe um --spiel_mm groesser ist (Tasche mit Fuegespiel).
  3. Platte in Drucklage: Wandnormale nach oben (Relief oben, Rueckseite plan auf dem Bett = stuetzenfrei, schnell), auf z = 0.
Ausgabe: modelle/stl/<objekt>_farbteile/ (Datenplatte): koerper.stl, platte_<wand>_NN.stl (Drucklage, mm), lage/ (Originallage), farbteile.json (je Teil Flaeche, Masse, Bett, Koerperzahl).
rc 3, wenn der Koerper zerfaellt oder eine Platte nicht aufs Bett passt.
Grenzen: nur Flaechen, die die Putzmaske als Stein ausweist (Fotofarbe; Fehler der Maske = Fehler der Platte - Bild <wand>_putz.jpg ansehen); die Tasche braucht Wandstaerke
(> tief_mm + 0,4 mm; hohles Modell mit WAND_MM 1,2 ist knapp -> mit WAND_MM=2.0 bauen); was mehr als --vor_m vor der Wand steht (Vordach, Galerie), bleibt am Koerper.
"""
import sys, os, json, argparse, numpy as np, cv2, trimesh
from manifold3d import Manifold as M, Mesh, CrossSection as CS, FillRule, JoinType, OpType
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, "tools"))


def laden(pfad, s):
    global NETZ
    m = trimesh.load(pfad, process=True); NETZ = m.copy(); NETZ.apply_scale(s); return M(Mesh(vert_properties=(np.asarray(m.vertices) * s).astype(np.float32), tri_verts=np.asarray(m.faces, np.uint32)))


def schreiben(k, pfad, s):
    from bauteile import stl_schreiben      # verschweisst Ecken, entfernt Lappen (17.11.2026: der direkte Export war nach dem Wiedereinlesen nicht wasserdicht - druck_teilung lehnte den Koerper ab)
    stl_schreiben(k.scale((s, s, s)), pfad, b"rcpark farbteil")


def prisma(maske, u0, z0, px, a, t, n, hinten, vorn, weiten=0.0):
    """Maske (H x W, Zeile 0 = oben) -> Koerper im Modellrahmen: Flaeche in (u, z), Tiefe von -hinten bis +vorn entlang n."""
    H, W = maske.shape; ko, _ = cv2.findContours(maske.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE); polys = []
    for c in ko:
        if len(c) < 3: continue
        c = c[:, 0, :].astype(float); polys.append(np.stack([u0 + (c[:, 0] + 0.5) * px, z0 + (H - 1 - c[:, 1] + 0.5) * px], 1))
    if not polys: return M()
    cs = CS(polys, FillRule.EvenOdd)
    if weiten: cs = cs.offset(weiten + px / 2, JoinType.Miter)
    else: cs = cs.offset(px / 2, JoinType.Miter)                                              # Konturen laufen durch Pixelmitten -> halbes Pixel nach aussen
    k = cs.extrude(hinten + vorn)                                             # lokal: X = u, Y = z, Z = Tiefe (0 = hinten)
    T = np.array([[t[0], 0.0, n[0], a[0] - n[0] * hinten], [t[1], 0.0, n[1], a[1] - n[1] * hinten], [0.0, 1.0, 0.0, 0.0]])
    return k.transform(T)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--masken", required=True); ap.add_argument("--stl"); ap.add_argument("--tief_mm", type=float, default=0.4); ap.add_argument("--spiel_mm", type=float, default=0.15)
    ap.add_argument("--wand_mm", type=float, default=2.2, help="Wandstaerke des (hohlen) Koerpers im Druck - begrenzt die Taschentiefe"); ap.add_argument("--innen_mm", type=float, default=0.8, help="Innenschicht hinter jeder Tasche (Druck-mm): haelt den Koerper an Ecken und duennen Waenden geschlossen"); ap.add_argument("--min_m2", type=float, default=1.5); ap.add_argument("--glatt_m", type=float, default=0.2, help="Glaettung der Stein/Putz-Grenze (m am Gebaeude; 0,2 m = 2,3 mm im Druck)"); ap.add_argument("--vor_m", type=float, default=0.4); ap.add_argument("--bett_mm", type=float, default=244.0); a = ap.parse_args()
    od = os.path.join(ROOT, "modelle", a.objekt); obj = json.load(open(os.path.join(od, "objekt.json"))); sc = float(obj.get("stl_massstab", 87)); s = sc / 1000.0; K = 1000.0 / sc
    stl = a.stl or os.path.join(ROOT, obj["stl"]); modell = laden(stl, s); v0 = modell.volume(); print(f"Modell {os.path.basename(stl)}: {modell.num_tri()} Dreiecke, {v0:.1f} m3, {len(modell.decompose())} Koerper")
    ad = os.path.join(ROOT, "modelle", "stl", f"{a.objekt}_farbteile"); gross = "/media/oem/scan/rc-park_stl"
    if not os.path.exists(ad) and os.path.isdir(gross): os.makedirs(os.path.join(gross, f"{a.objekt}_farbteile"), exist_ok=True); os.symlink(os.path.join(gross, f"{a.objekt}_farbteile"), ad)
    os.makedirs(os.path.join(ad, "lage"), exist_ok=True)
    for alt in os.listdir(ad):
        if alt.endswith(".stl"): os.remove(os.path.join(ad, alt))
    for alt in os.listdir(os.path.join(ad, "lage")): os.remove(os.path.join(ad, "lage", alt))
    tief, spiel = a.tief_mm / K, a.spiel_mm / K; koerper = modell; teile = []; schlecht = False; kruemel = [0.0]; taschen = []; innen = []
    for mp in a.masken.split(","):
        p = mp if os.path.isabs(mp) else os.path.join(od, mp); Z = np.load(p); wand = os.path.basename(p).split("_")[0].replace(".npz", "")
        if "putz" not in Z.files: print(f"{mp}: kein Feld 'putz' - uebersprungen"); continue
        px = float(Z["px"]); u0, z0 = float(Z["u0"]), float(Z["z0"]); A, t, n = Z["a"], Z["t"], Z["n"]; stein = ~Z["putz"].astype(bool)
        if "oeffnung" in Z.files: stein &= ~Z["oeffnung"].astype(bool)
        r = max(1, int(round(0.15 / px))); ke = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1)); st = cv2.morphologyEx(cv2.morphologyEx(stein.astype(np.uint8), cv2.MORPH_CLOSE, ke), cv2.MORPH_OPEN, ke)
        sg = max(1.0, a.glatt_m / px); st = (cv2.GaussianBlur(st.astype(np.float32), (0, 0), sg) > 0.5).astype(np.uint8)      # 17.11.2026: Raender glaetten (Maske aus Fotofarbe franst pixelweise aus -> Platte mit Zacken, die abbrechen und nicht in die Tasche gehen)
        nmin = int(a.min_m2 / px ** 2); nl, lab, stat, _ = cv2.connectedComponentsWithStats(1 - st, 4)
        for i in range(1, nl):
            if stat[i, cv2.CC_STAT_AREA] < nmin: st[lab == i] = 1              # kleine Putzinseln im Stein fuellen
        # Wo liegt die Wandflaeche des MODELLS gegen die Ebene der Maske? (17.11.2026: Nordwand des Turms liegt 9 cm hinter der Maskenebene - die Platte biss nur 1 cm ins Modell und zerfiel in 422 Stuecke)
        ii, jj = np.nonzero(st); w_ = np.random.default_rng(0).choice(len(ii), min(len(ii), 20000), replace=False) if len(ii) else []
        hinten = tief; vor = a.vor_m
        if len(w_):
            uu = u0 + (jj[w_] + 0.5) * px; zz = z0 + (st.shape[0] - 1 - ii[w_] + 0.5) * px; O = np.stack([A[0] + t[0] * uu + n[0] * 1.5, A[1] + t[1] * uu + n[1] * 1.5, zz], 1)
            loc, ir, _ = NETZ.ray.intersects_location(O, np.tile([-n[0], -n[1], 0.0], (len(O), 1)), multiple_hits=False); dd = 1.5 - np.linalg.norm(loc - O[ir], axis=1); dd = dd[dd > -0.6]
            if len(dd) > 100:
                d50, d5 = float(np.median(dd)), float(np.percentile(dd, 5)); hinten = -d5 + tief; vor = d50 + a.vor_m; grenze = (a.wand_mm - 0.6 - a.spiel_mm) / K - d50
                if hinten > grenze: print(f"{wand}: Platte waere {(d50 + hinten) * K:.2f} mm tief - auf {(d50 + grenze) * K:.2f} mm begrenzt, damit hinter der Tasche 0,6 mm Wand bleiben (Wand {a.wand_mm} mm; tiefere Reliefstellen bleiben am Koerper)"); hinten = grenze      # 17.11.2026: an der Westwand schnitt die Tasche (2,14 + 0,15 mm) durch die 2,2-mm-Wand - der Koerper war dort offen      # Relief bis --vor_m vor der mittleren Wandflaeche; was weiter vorsteht (Vordach, Galerie), ist kein Stein dieser Platte
                print(f"{wand}: Modellflaeche im Mittel {d50 * 100:+.1f} cm gegen die Maskenebene, tiefste 5 % bei {d5 * 100:+.1f} cm -> Plattenrueckseite {hinten * 100:.1f} cm hinter der Ebene = {(d50 + hinten) * K:.2f} mm im Druck hinter der Wandflaeche (so viel Wandstaerke + 0,4 mm braucht der Koerper)")
        # Oeffnungen (Fenster, Tor) der Wand: Strahl von aussen trifft erst weit hinter der Wand oder gar nicht -> dort KEINE Innenschicht
        offen = np.zeros(st.shape, bool)
        if len(w_):
            gi, gj = np.mgrid[0:st.shape[0]:2, 0:st.shape[1]:2]; gi, gj = gi.ravel(), gj.ravel(); uu = u0 + (gj + 0.5) * px; zz = z0 + (st.shape[0] - 1 - gi + 0.5) * px
            O = np.stack([A[0] + t[0] * uu + n[0] * 1.5, A[1] + t[1] * uu + n[1] * 1.5, zz], 1); loc, ir, _ = NETZ.ray.intersects_location(O, np.tile([-n[0], -n[1], 0.0], (len(O), 1)), multiple_hits=False)
            tr = np.full(len(O), -9.0); tr[ir] = 1.5 - np.linalg.norm(loc - O[ir], axis=1); o2 = tr < float(np.median(tr[tr > -0.6])) - a.wand_mm / K - 0.15
            og = np.zeros(((st.shape[0] + 1) // 2, (st.shape[1] + 1) // 2), np.uint8); og[gi // 2, gj // 2] = o2; og = cv2.dilate(og, np.ones((3, 3), np.uint8)); offen = cv2.resize(og, (st.shape[1], st.shape[0]), interpolation=cv2.INTER_NEAREST).astype(bool)
        nl, lab, stat, _ = cv2.connectedComponentsWithStats(st, 4); nr = 0; rest = 0.0
        for i in range(1, nl):
            fl = stat[i, cv2.CC_STAT_AREA] * px * px
            if fl < a.min_m2: rest += fl; continue
            reg = lab == i; y0, hh = stat[i, cv2.CC_STAT_TOP], stat[i, cv2.CC_STAT_HEIGHT]; nb = int(np.ceil(hh * px * K / a.bett_mm)); gr = np.linspace(y0, y0 + hh, nb + 1).astype(int)
            for b in range(nb):
                band = np.zeros_like(reg); band[gr[b]:gr[b + 1]] = reg[gr[b]:gr[b + 1]]
                if band.sum() * px * px < 0.3: continue
                pl = modell ^ prisma(band, u0, z0, px, A, t, n, hinten, vor)
                if pl.is_empty() or pl.volume() < 1e-4: continue
                st_ = pl.decompose(); vg = max(x_.volume() for x_ in st_); kr = [x_ for x_ in st_ if x_.volume() < 0.02 * vg]
                if kr: pl = M.batch_boolean([x_ for x_ in st_ if x_.volume() >= 0.02 * vg], OpType.Add) if len(st_) - len(kr) > 1 else max(st_, key=lambda x_: x_.volume()); kruemel[0] += sum(x_.volume() for x_ in kr)      # Kruemel (< 2 % der Platte) verwerfen
                taschen.append(prisma(band, u0, z0, px, A, t, n, hinten + spiel, vor + 0.05, weiten=spiel))
                iw = band & ~offen                                                # Innenschicht hinter der Tasche (17.11.2026: an den Gebaeudeecken nahmen die Taschen zweier Waende die ganze Wand weg - der Koerper war in 34 von 48 Hoehenschnitten offen)
                if iw.any(): innen.append(prisma(iw, u0, z0, px, A, t, n, hinten + spiel + a.innen_mm / K, -(hinten + spiel) + 0.002, weiten=spiel))
                nr += 1; name = f"platte_{wand}_{nr:02d}"; schreiben(pl, os.path.join(ad, "lage", name + ".stl"), K)
                R = np.array([[t[0], t[1], 0.0], [0.0, 0.0, 1.0], [n[0], n[1], 0.0]])                    # Drucklage: u -> x, z -> y, Wandnormale -> oben
                fl_ = pl.transform(np.hstack([R, np.zeros((3, 1))])); lo, hi = fl_.bounding_box()[:3], fl_.bounding_box()[3:]; fl_ = fl_.translate((-lo[0], -lo[1], -lo[2])); schreiben(fl_, os.path.join(ad, name + ".stl"), K)
                ma = [(hi[j] - lo[j]) * K for j in range(3)]; passt = max(ma[0], ma[1]) <= a.bett_mm + 0.5; nk = len(pl.decompose()); schlecht |= not passt
                teile.append(dict(name=name, wand=wand, farbe="Stein", flaeche_m2=round(float(band.sum() * px * px), 1), masse_mm=[round(float(x), 1) for x in ma], passt_aufs_bett=bool(passt), koerper=nk, volumen_cm3=round(float(pl.volume() * K ** 3 / 1000), 1)))
                print(f"  {name}: {band.sum() * px * px:6.1f} m2 Stein, Drucklage {ma[0]:.0f} x {ma[1]:.0f} x {ma[2]:.1f} mm, {'passt' if passt else 'PASST NICHT aufs Bett'}, {nk} Koerper")
        print(f"{wand}: {nr} Platten; {rest:.1f} m2 Stein in Inseln < {a.min_m2} m2 bleiben am Koerper (nachmalen)")
    if taschen:
        huelle = modell.hull(); zus = (M.batch_boolean(innen, OpType.Add) ^ huelle) if innen else M()
        koerper = (modell + zus) - M.batch_boolean(taschen, OpType.Add); print(f"Innenschicht {a.innen_mm} mm hinter den Taschen: {zus.volume():.2f} m3 = {zus.volume() * K ** 3 / 1000:.1f} cm3 im Druck")
    st_ = sorted(koerper.decompose(), key=lambda x_: -x_.volume()); lose = sum(x_.volume() for x_ in st_[1:]); gr_ = [x_.volume() for x_ in st_]
    if len(st_) > 1 and lose <= 0.001 * gr_[0]: koerper = st_[0]; kruemel[0] += lose; lose = 0.0      # Splitter am Taschenrand verwerfen (gemeldet); groessere lose Stuecke bleiben und sind ein Fehler
    nk = len(koerper.decompose()); schreiben(koerper, os.path.join(ad, "koerper.stl"), K); schlecht |= nk > 1
    print(f"Koerper: {koerper.num_tri()} Dreiecke, {koerper.volume():.1f} m3 (vorher {v0:.1f}), {nk} Koerper" + (f" - LOSE STUECKE {lose:.3f} m3 (was vor der Platte stand, hat den Halt verloren)" if nk > 1 else ""))
    import json_sicher
    json_sicher.schreiben(os.path.join(ad, "farbteile.json"), dict(objekt=a.objekt, stl=os.path.relpath(stl, ROOT), tief_mm=a.tief_mm, spiel_mm=a.spiel_mm, koerper=dict(farbe="Putz/Grundfarbe", koerperzahl=nk, lose_m3=round(float(lose), 4), volumen_cm3=round(float(koerper.volume() * K ** 3 / 1000), 1)), platten=teile))
    if kruemel[0]: print(f"verworfene Kruemel/Splitter: {kruemel[0]:.3f} m3 = {kruemel[0] * K ** 3 / 1000:.2f} cm3 im Druck")
    print(f"-> {ad}: koerper.stl + {len(teile)} Steinplatten ({sum(t_['flaeche_m2'] for t_ in teile):.0f} m2), farbteile.json")
    return 3 if schlecht else 0


if __name__ == "__main__":
    sys.exit(main())
