#!/usr/bin/env python3
"""druck_farbteile.py <objekt> --masken relief/nord_putz.npz,relief/sued_putz.npz[,...] [--stl PFAD] [--einsatz --wand_mm 1.0 --innen_mm 1.0 --falz_mm 3] [--tief_mm 0.4] [--spiel_mm 0.15] [--min_m2 1.5] [--glatt_m 0.2] [--vor_m 0.4] [--ring] [--schnitt_m 0.5] [--schnittbild 12,25]
FARBTEILE: Steinflaechen einer Wand als EIGENE, flach druckbare Platten aus dem fertigen Modell loesen; der Koerper bekommt passende Taschen.

Anlass 17.11.2026 (Nutzer): "verschiedene Farben muessen eigene Teile sein - das Steinrelief ein anderes Teil als der Putz; dann muss ich nicht anmalen, es kann flach gedruckt
werden, und die Druckzeit zaehlt." Bisher: ein Teil = eine Farbe, Stein und Putz derselben Wand blieben zusammen (tools/druck_farben.py).
Verfahren (generisch, arbeitet am fertigen STL - der Generator bleibt unberuehrt):
  1. Je Maske (Reliefdatei mit Feld 'putz', Wandrahmen a/t/n/u0/z0/px wie tools/relief_einsatz.py): STEIN = nicht Putz. Reinigen: schliessen/oeffnen (15 cm), Loecher < min_m2
     fuellen, Inseln < min_m2 verwerfen (bleiben am Koerper = nachmalen). Je zusammenhaengender Flaeche eine Platte; hoeher als das Druckbett -> in Baender geteilt.
  2. Lage der Wandflaeche des Modells gegen die Maskenebene per Strahlen messen; Plattenrueckseite = tiefste 5 % des Reliefs + --tief_mm (Druck) Traegerschicht.
     Prisma der Flaeche von dort bis --vor_m vor der Ebene.  PLATTE = Modell geschnitten mit dem Prisma.
     KOERPER = Modell minus Prisma, das seitlich und in der Tiefe um --spiel_mm groesser ist (Tasche mit Fuegespiel).
  3. Platte in Drucklage: Wandnormale nach oben (Relief oben, Rueckseite plan auf dem Bett = stuetzenfrei, schnell), auf z = 0. Luftinseln knapp ueber dem Bett
     (Rueckseite nicht ganz plan) fuellt tools/druck_luft.stuetzen bis 1,2 mm auf (--schicht_mm 0.16 = Bambu; --ohne_luft aus); Ergebnis je Platte 'luft' in farbteile.json.
Bauart --einsatz (duenne Wand, 17.11.2026): die Platte ist die GANZE Wand (--wand_mm tief), der Koerper bekommt dort ein Loch und dahinter - im Hohlraum - eine Innenschicht
(--innen_mm), auf die die Platte geklebt wird: eben je Wand (auf den Innenraum des Gebaeudes beschnitten) + eine Ringschicht aus den Hoehenschnitten, die um die Gebaeudeecken laeuft
und --falz_mm unter den Putz greift (Funktion ringschicht; mit --ring auch in der Taschen-Bauart: Turm 2,4 mm Wand ohne Ring 3 von 73 Schnitten offen, mit Ring 0, +68 cm3). Massive Bereiche vorher mit tools/druck_hohl.py aushoehlen. Nicht Platte wird: was hinter einem Vorbau liegt (> --vor_m
vor der Wand, Strahl von 3 m aussen), Streifen schmaler als 1 m, Flaechen, von denen nur ein Streifen < 8 mm im Prisma liegt; verworfene Kruemel kommen an den Koerper zurueck.
Ausgabe: modelle/stl/<objekt>_farbteile/ (Datenplatte): koerper.stl, platte_<wand>_NN.stl (Drucklage, mm), lage/ (Originallage), farbteile.json (je Teil Flaeche, Masse, Bett, Koerperzahl).
rc 3, wenn der Koerper zerfaellt, eine Platte nicht aufs Bett passt, eine Platte den Koerper durchdringt (> 1 mm3) oder Hoehenschnitte offen sind
("offene Hoehenschnitte: n von m" - der Koerper ist dort offener als das Modell; Bilder <ausgabe>/schnitte/schnitt_z*.png ansehen, weitere mit --schnittbild 12,25).
Grenzen: nur Flaechen, die die Putzmaske als Stein ausweist (Fotofarbe; Fehler der Maske = Fehler der Platte - Bild <wand>_putz.jpg ansehen); die Tasche braucht Wandstaerke
(> tief_mm + 0,4 mm; hohles Modell mit WAND_MM 1,2 ist knapp -> mit WAND_MM=2.0 bauen); was mehr als --vor_m vor der Wand steht (Vordach, Galerie), bleibt am Koerper.
"""
import sys, os, json, argparse, numpy as np, cv2, trimesh
from manifold3d import Manifold as M, Mesh, CrossSection as CS, FillRule, JoinType, OpType
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, "tools"))


def laden(pfad, s):
    global NETZ
    m = trimesh.load(pfad, process=True); NETZ = m.copy(); NETZ.apply_scale(s); return M(Mesh(vert_properties=(np.asarray(m.vertices) * s).astype(np.float32), tri_verts=np.asarray(m.faces, np.uint32)))


def schreiben(k, pfad, s, boden=False):
    from bauteile import stl_schreiben, kneifkanten_schliessen      # verschweisst Ecken, entfernt Lappen (17.11.2026: der direkte Export war nach dem Wiedereinlesen nicht wasserdicht - druck_teilung lehnte den Koerper ab)
    k = k.scale((s, s, s))
    if boden: k = kneifkanten_schliessen(k, r=0.25, stellen=3).trim_by_plane((0.0, 0.0, 1.0), 0.0)      # Drucklage: die Kloetzchen an Kneifkanten ragten 0,25 mm unter die Auflageflaeche - der Slicer lehnte die Platte ab ("no extrusions in the first layer")
    stl_schreiben(k, pfad, b"rcpark farbteil")


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


def _fl(q):
    return 0.5 * float(np.sum(q[:, 0] * np.roll(q[:, 1], -1) - np.roll(q[:, 0], -1) * q[:, 1]))


def offene_schnitte(modell, koerper, z0, z1, schritt=0.5):
    """FESTE PRUEFUNG (17.11.2026): in welchen Hoehenschnitten ist der Koerper OFFENER als das Modell?
    Je Hohlraum des Modellschnitts (Innenkontur > 0,5 m2): der Teil, den der Koerper frei laesst, muss wieder von einer Innenkontur des Koerpers umschlossen sein
    (sonst ist der Wandring gerissen = OFFEN); ein vom Koerper ganz gefuellter Hohlraum (Innenschicht) ist nicht offen. Ausserdem OFFEN: der Koerper zerfaellt im Schnitt in mehr
    Stuecke (> 0,05 m2) als das Modell. Fensterschlitze des Modells zaehlen nicht (das Modell ist dort selbst offen). -> (Liste (z, Grund), Zahl Schnitte)."""
    zs = np.arange(np.ceil(z0 / schritt - 1e-6) * schritt, z1, schritt); off = []
    for z in zs:
        pm = modell.slice(float(z)).to_polygons(); pk = koerper.slice(float(z)).to_polygons(); B = CS(pk, FillRule.Positive) if pk else CS()
        lk = [q[::-1] for q in pk if _fl(q) < -0.05]; BH = CS(lk, FillRule.Positive) if lk else CS(); am = sum(1 for q in pm if _fl(q) > 0.05); ak = sum(1 for q in pk if _fl(q) > 0.05); grund = []
        for q in pm:
            if _fl(q) > -0.5: continue
            frei = CS([q[::-1]], FillRule.Positive) - B
            if frei.area() > 0.2 * -_fl(q) and (frei ^ BH).area() < 0.5 * frei.area(): grund.append(f"Hohlraum {-_fl(q):.1f} m2 nicht mehr umschlossen")
        if ak > am: grund.append(f"{ak} Stuecke statt {am}")
        if grund: off.append((float(z), "; ".join(grund)))
    return off, len(zs)


def schnittbild(pfad, z, modell, koerper, platten, px=0.01):
    """Querschnitt als Bild: Koerper blau, Platten rot, Umriss des Modells schwarz (1 cm je Pixel) - zum ANSEHEN, nicht nur zaehlen."""
    bb = modell.bounding_box(); x0, y0 = bb[0] - 0.3, bb[1] - 0.3; W = int((bb[3] - bb[0] + 0.6) / px); H = int((bb[4] - bb[1] + 0.6) / px); im = np.full((H, W, 3), 255, np.uint8)
    def zeichne(k, farbe, fuell=True):
        po = k.slice(float(z)).to_polygons(); cc = [np.stack([(q[:, 0] - x0) / px, H - (q[:, 1] - y0) / px], 1).astype(np.int32) for q in po]
        if not fuell: cv2.polylines(im, cc, True, farbe, 1); return
        m = np.zeros((H, W), np.uint8)
        for c, q in sorted(zip(cc, po), key=lambda t_: -abs(_fl(t_[1]))): cv2.fillPoly(m, [c], 1 if _fl(q) > 0 else 0)
        im[m > 0] = farbe
    zeichne(koerper, (200, 160, 60))
    for p_ in platten: zeichne(p_, (60, 60, 220))
    zeichne(modell, (0, 0, 0), False); cv2.putText(im, f"z = {z:.1f} m  blau Koerper, rot Platten, schwarz Modellumriss", (10, 30), 0, 0.8, (0, 0, 0), 2); cv2.imwrite(pfad, im)


def ringschicht(modell, tasche, innen, wand, falz, spiel, dz=0.1, schliess=0.6):
    """Innenschicht aus den HOEHENSCHNITTEN des Modells (17.11.2026, Einsatz-Bauart) -> (Ring, Innenraum).
    Anlass: die ebenen Innenschichten je Wand enden an der Gebaeudeecke - dort nimmt die Tasche der Nachbarwand das Wandende weg, und zwischen Innenschicht und Nachbarwand blieb
    ein Spalt von < 1 cm (27 von 48 Hoehenschnitten offen; Schnittbilder angesehen). Ausserdem ragten ebene Innenschichten durch duenne Nachbarwaende ins Freie (Treppenturm).
    Je Scheibe dz: geschlossener Schnitt (Fenster bis 2 x schliess m ueberbrueckt); Hohlraum C = dessen Loecher.
      RING = (Wand um `innen` verdickt) geschnitten mit (C, das `wand`/2 in die Wand greift), nur im Umkreis `falz` + innen der Taschen; vor Fensteroeffnungen
             (geschlossener Schnitt minus Schnitt) kein Ring. Er laeuft im Hohlraum um die Ecke und verbindet Innenschicht, Nachbarwand und Putz.
      INNENRAUM = gefuellter Umriss, um `wand`/2 nach innen versetzt: darauf werden die ebenen Innenschichten beschnitten (nichts ragt nach aussen).
    Nur fuer (nahezu) senkrechte Waende - beides sind Treppen aus Scheiben. Die Scheiben ueberlappen um ein Viertel (nicht um 1 Promille: Stufen von 1 Mikrometer im Druck
    gaben in druck_teilung Flaechenfetzen ohne Volumen an der Schnittebene)."""
    bb = tasche.bounding_box(); ringe = []; raum = []; J = JoinType.Miter
    for z in np.arange(bb[2] - falz - dz, bb[5] + falz + dz, dz):
        zm = float(z + dz / 2); S = modell.slice(zm)
        if S.is_empty(): continue
        po = S.offset(schliess, J).to_polygons(); voll = [q for q in po if _fl(q) > 0.05]; lo = [q[::-1] for q in po if _fl(q) < -0.05]      # Vorzeichen nur am VERDICKTEN Schnitt lesen: nach dem Zurueckversetzen liefert Clipper den Ring als Vielecke ohne Loch (an Engstellen zusammengekniffen)
        if not voll: continue
        um = CS(voll, FillRule.Positive).offset(-schliess, JoinType.Round, 2.0, 24); r_ = um.offset(-0.5 * wand, JoinType.Round, 2.0, 8).simplify(0.005)      # nach innen RUND versetzen: mit Gehrung schnitt jede Kerbe der Aussenhaut einen bis 25 cm tiefen Keil in den Innenraum (Schnittbild z = 25,5 m: Innenschicht an der Ecke keilfoermig weg)
        if not r_.is_empty(): raum.append(r_.extrude(dz * 1.25).translate((0, 0, float(z))))
        T = CS.batch_boolean([tasche.slice(float(zt)) for zt in (z - falz, z - falz / 2, z + 0.002, zm, z + dz - 0.002, z + dz + falz / 2, z + dz + falz)], OpType.Add)      # alle Taschen, die die Scheibe beruehren oder bis `falz` darueber/darunter liegen (die ebene Innenschicht reicht so weit ueber den Plattenrand und hing dort sonst frei im Hohlraum)
        if not lo or T.is_empty(): continue
        Co = CS(lo, FillRule.Positive).offset(schliess, JoinType.Round, 2.0, 24); frei = um - S      # Co = geoeffneter Hohlraum (RUND versetzt: Ecken abgerundet, taugt nur zum Finden der Fenster; mit Gehrung stachen Spitzen durch die Wand, und die Kehle zwischen Treppenturm und Wand galt als Fenster); frei = alles Freie im geschlossenen Umriss
        if Co.area() < 0.5: continue
        fe = (frei - Co).offset(-0.3 * wand, J).offset(0.3 * wand, J); tu_ = []     # Fenstertunnel = Stuecke des Freien ausserhalb von Co, die vom Hohlraum bis zur Aussenhaut reichen (duenne Reste der Reliefkanten und die Ecken des Hohlraums zaehlen nicht)
        if not fe.is_empty():
            haut = um - um.offset(-0.2 * wand, JoinType.Round, 2.0, 8); cr = Co.offset(0.2 * wand, J); tu_ = [f_ for f_ in fe.decompose() if (f_ ^ haut).area() > 1e-5 and (f_ ^ cr).area() > 1e-5]
        tun = CS.batch_boolean(tu_, OpType.Add) if tu_ else CS()
        hohl = [c_ for c_ in (frei - tun.offset(0.05 * wand, J) if tu_ else frei).decompose() if c_.area() > 0.5 and (c_ ^ Co).area() > 0.25]      # der WAHRE Hohlraum (scharfe Ecken): grosse Stuecke des Freien ohne die Fenstertunnel
        if not hohl: continue
        C = CS.batch_boolean(hohl, OpType.Add)
        ring = ((S + T).offset(innen, J) ^ C.offset(0.5 * wand, J)) ^ T.offset(falz + innen, J)      # S + T: auch um Taschen herum, die in einen Hohlraum VOR der Wand schneiden (Treppenturm am Turmfuss: Tasche oeffnete den Turmring)
        if tu_: ring = ring - tun.offset(innen + spiel + 0.1 * wand, J)
        ring = ring.simplify(0.003)
        if not ring.is_empty(): ringe.append(ring.extrude(dz * 1.25).translate((0, 0, float(z))))
    return (M.batch_boolean(ringe, OpType.Add) if ringe else M()), (M.batch_boolean(raum, OpType.Add) if raum else M())


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--masken", required=True); ap.add_argument("--stl"); ap.add_argument("--tief_mm", type=float, default=0.4); ap.add_argument("--spiel_mm", type=float, default=0.15)
    ap.add_argument("--wand_mm", type=float, default=2.2, help="Wandstaerke des (hohlen) Koerpers im Druck - begrenzt die Taschentiefe"); ap.add_argument("--innen_mm", type=float, default=0.8, help="Innenschicht hinter jeder Tasche (Druck-mm): haelt den Koerper an Ecken und duennen Waenden geschlossen"); ap.add_argument("--einsatz", action="store_true", help="duenne Wand (1 mm): Steinplatte = ganze Wand, Koerper mit Oeffnung + Klebefalz innen statt Tasche"); ap.add_argument("--falz_mm", type=float, default=3.0); ap.add_argument("--pfosten_mm", type=float, default=0.0, help="Eckpfosten innen (Druck-mm) in der Einsatz-Bauart"); ap.add_argument("--min_m2", type=float, default=1.5); ap.add_argument("--glatt_m", type=float, default=0.2, help="Glaettung der Stein/Putz-Grenze (m am Gebaeude; 0,2 m = 2,3 mm im Druck)"); ap.add_argument("--vor_m", type=float, default=0.4); ap.add_argument("--bett_mm", type=float, default=244.0); ap.add_argument("--ring", action="store_true", help="Ringschicht auch in der Taschen-Bauart (bei --einsatz immer): schliesst Ecken, an denen Taschen zweier Waende die Wand wegnehmen; kostet Material"); ap.add_argument("--schnitt_m", type=float, default=0.5, help="Abstand der Pruef-Hoehenschnitte (m)"); ap.add_argument("--schnittbild", default="", help="z-Werte (m, Komma) fuer zusaetzliche Querschnittsbilder in <ausgabe>/schnitte/")
    ap.add_argument("--schicht_mm", type=float, default=0.16, help="Schichthoehe des Plattendrucks fuer die Luftinsel-Stuetzen (druck_luft.stuetzen)"); ap.add_argument("--ohne_luft", action="store_true"); a = ap.parse_args()
    od = os.path.join(ROOT, "modelle", a.objekt); obj = json.load(open(os.path.join(od, "objekt.json"))); sc = float(obj.get("stl_massstab", 87)); s = sc / 1000.0; K = 1000.0 / sc
    stl = a.stl or os.path.join(ROOT, obj["stl"]); modell = laden(stl, s); v0 = modell.volume(); print(f"Modell {os.path.basename(stl)}: {modell.num_tri()} Dreiecke, {v0:.1f} m3, {len(modell.decompose())} Koerper")
    ad = os.path.join(ROOT, "modelle", "stl", f"{a.objekt}_farbteile"); gross = "/media/oem/scan/rc-park_stl"
    if not os.path.exists(ad) and os.path.isdir(gross): os.makedirs(os.path.join(gross, f"{a.objekt}_farbteile"), exist_ok=True); os.symlink(os.path.join(gross, f"{a.objekt}_farbteile"), ad)
    os.makedirs(os.path.join(ad, "lage"), exist_ok=True)
    for alt in os.listdir(ad):
        if alt.endswith(".stl"): os.remove(os.path.join(ad, alt))
    for alt in os.listdir(os.path.join(ad, "lage")): os.remove(os.path.join(ad, "lage", alt))
    tief, spiel = a.tief_mm / K, a.spiel_mm / K; koerper = modell; teile = []; schlecht = False; kruemel = [0.0]; taschen = []; innen = []; waende = []; platten = []; zurueck = []
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
                if a.einsatz: hinten = a.wand_mm / K - d50; print(f"{wand}: EINSATZ - die Platte ist die ganze Wand ({a.wand_mm} mm), dahinter traegt eine durchgehende Innenschicht von {a.innen_mm} mm (im Hohlraum, nicht in der Wand)")
                elif hinten > grenze: print(f"{wand}: Platte waere {(d50 + hinten) * K:.2f} mm tief - auf {(d50 + grenze) * K:.2f} mm begrenzt, damit hinter der Tasche 0,6 mm Wand bleiben (Wand {a.wand_mm} mm; tiefere Reliefstellen bleiben am Koerper)"); hinten = grenze      # 17.11.2026: an der Westwand schnitt die Tasche (2,14 + 0,15 mm) durch die 2,2-mm-Wand - der Koerper war dort offen      # Relief bis --vor_m vor der mittleren Wandflaeche; was weiter vorsteht (Vordach, Galerie), ist kein Stein dieser Platte
                print(f"{wand}: Modellflaeche im Mittel {d50 * 100:+.1f} cm gegen die Maskenebene, tiefste 5 % bei {d5 * 100:+.1f} cm -> Plattenrueckseite {hinten * 100:.1f} cm hinter der Ebene = {(d50 + hinten) * K:.2f} mm im Druck hinter der Wandflaeche (so viel Wandstaerke + 0,4 mm braucht der Koerper)")
        # Oeffnungen (Fenster, Tor) der Wand: Strahl von aussen trifft erst weit hinter der Wand oder gar nicht -> dort KEINE Innenschicht
        offen = np.zeros(st.shape, bool)
        if len(w_):
            gi, gj = np.mgrid[0:st.shape[0]:2, 0:st.shape[1]:2]; gi, gj = gi.ravel(), gj.ravel(); uu = u0 + (gj + 0.5) * px; zz = z0 + (st.shape[0] - 1 - gi + 0.5) * px
            R0 = 3.0; O = np.stack([A[0] + t[0] * uu + n[0] * R0, A[1] + t[1] * uu + n[1] * R0, zz], 1); loc, ir, _ = NETZ.ray.intersects_location(O, np.tile([-n[0], -n[1], 0.0], (len(O), 1)), multiple_hits=False)
            tr = np.full(len(O), -9.0); tr[ir] = R0 - np.linalg.norm(loc - O[ir], axis=1); med = float(np.median(tr[(tr > -0.6) & (tr < 1.4)])); o2 = tr < med - a.wand_mm / K - 0.15
            og = np.zeros(((st.shape[0] + 1) // 2, (st.shape[1] + 1) // 2), np.uint8); og[gi // 2, gj // 2] = o2; og = cv2.dilate(og, np.ones((3, 3), np.uint8)); offen = cv2.resize(og, (st.shape[1], st.shape[0]), interpolation=cv2.INTER_NEAREST).astype(bool)
            # VERDECKT (17.11.2026): steht bis 3 m vor der Wand ein Gebaeudeteil mehr als --vor_m vor der Wandflaeche (Anbau, Treppenturm, Vordach), ist das Pixel keine Platte: sie liesse sich nicht
            # einsetzen, und die Tasche oeffnete den Hohlraum des Vorbaus (Schnittbild z = 11 m: Anbau an der Wand, 9 m2 Hohlraum offen). Die Flaeche bleibt am Koerper.
            vg = np.zeros_like(og); vg[gi // 2, gj // 2] = tr > med + a.vor_m; vg = cv2.dilate(vg, np.ones((5, 5), np.uint8)); verdeckt = cv2.resize(vg, (st.shape[1], st.shape[0]), interpolation=cv2.INTER_NEAREST).astype(bool)
            if (verdeckt & (st > 0)).any(): print(f"{wand}: {(verdeckt & (st > 0)).sum() * px * px:.1f} m2 Stein liegen hinter einem Vorbau (> {a.vor_m} m vor der Wand) - keine Platte, bleibt am Koerper"); st[verdeckt] = 0
            rs = max(1, int(round(0.5 / px))); er = cv2.erode(st, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * rs + 1, 2 * rs + 1))); nl, lab = cv2.connectedComponents(st, connectivity=4); gut_ = np.zeros(nl, bool); gut_[np.unique(lab[er > 0])] = True; gut_[0] = False
            if (~gut_[1:]).any(): print(f"{wand}: {(st > 0).sum() * px * px - gut_[lab].sum() * px * px:.1f} m2 Stein in Streifen schmaler als 1 m (11 mm im Druck) - keine Platte, bleibt am Koerper"); st = (gut_[lab]).astype(np.uint8)
        fz = max(1, int(round(a.falz_mm / K / px)))
        if len(w_) and 'd50' in dir(): waende.append(dict(A=np.array(A, float), t=np.array(t, float), n=np.array(n, float), innen=d50 - a.wand_mm / K, u=(u0, u0 + st.shape[1] * px), z=(z0, z0 + st.shape[0] * px)))
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
                bq = pl.transform(np.array([[t[0], t[1], 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [n[0], n[1], 0.0, 0.0]])).bounding_box()
                if min(bq[3] - bq[0], bq[4] - bq[1]) * K < 8.0:      # 17.11.2026: Maskenflaeche gross, aber vom Modell liegt nur ein Streifen im Prisma (Sturz ueber der Tordurchfahrt: "Platte" 137 x 4 mm) - kein Teil, keine Tasche
                    print(f"  {wand}: Flaeche {band.sum() * px * px:.1f} m2 ergibt nur einen Streifen {(bq[3] - bq[0]) * K:.0f} x {(bq[4] - bq[1]) * K:.0f} mm - keine Platte, bleibt am Koerper"); rest += float(band.sum() * px * px); continue
                if kr:      # 17.11.2026: ein verworfener Kruemel hinterliess ein LOCH in der Wand (Schnittbild z = 25 m: Wandstueck an der Ecke weg, keine Platte dafuer). Jetzt kommt er nach dem Taschenschnitt zurueck an den Koerper, mit einer Bruecke ueber das Fuegespiel dahinter (nachmalen). Die Tasche unter dem Kruemel zu sperren, gab 13 mm3 Durchdringung.
                    km = np.zeros(band.shape, np.uint8); Hb = band.shape[0]
                    for x_ in kr:
                        me = x_.to_mesh(); vv = np.asarray(me.vert_properties)[:, :3]; uu_ = (vv[:, 0] - A[0]) * t[0] + (vv[:, 1] - A[1]) * t[1]; pp = np.stack([(uu_ - u0) / px - 0.5, Hb - 1 - ((vv[:, 2] - z0) / px - 0.5)], 1)
                        for d_ in np.asarray(me.tri_verts): cv2.fillConvexPoly(km, np.round(pp[d_]).astype(np.int32), 1)
                    zurueck.append((M.batch_boolean(kr, OpType.Add) + prisma(km.astype(bool), u0, z0, px, A, t, n, hinten + spiel + 0.005, -hinten + 0.005)) - pl)
                taschen.append(prisma(band, u0, z0, px, A, t, n, hinten + spiel, vor + 0.05, weiten=spiel)); platten.append((None, pl))
                iw = (cv2.dilate(band.astype(np.uint8), np.ones((2 * fz + 1, 2 * fz + 1), np.uint8)).astype(bool) if a.einsatz else band) & ~offen                                                # Innenschicht hinter der Tasche (17.11.2026: an den Gebaeudeecken nahmen die Taschen zweier Waende die ganze Wand weg - der Koerper war in 34 von 48 Hoehenschnitten offen)
                if iw.any(): innen.append(prisma(iw, u0, z0, px, A, t, n, hinten + spiel + a.innen_mm / K, -(hinten + spiel) + (0.5 / K if a.einsatz else 0.002), weiten=spiel))      # Einsatz: Innenschicht greift 0,5 mm in die Wandtiefe und --falz_mm seitlich unter den Putz (sonst trennt das Fuegespiel Wand und Innenschicht: 47 von 48 Schnitten offen)
                nr += 1; name = f"platte_{wand}_{nr:02d}"
                R = np.array([[t[0], t[1], 0.0], [0.0, 0.0, 1.0], [n[0], n[1], 0.0]])                    # Drucklage: u -> x, z -> y, Wandnormale -> oben
                fl_ = pl.transform(np.hstack([R, np.zeros((3, 1))])); lo, hi = fl_.bounding_box()[:3], fl_.bounding_box()[3:]; fl_ = fl_.translate((-lo[0], -lo[1], -lo[2])); lu = None
                if not a.ohne_luft:      # 17.11.2026: 5 von 8 Platten hatten Luftinseln 0,24..1,04 mm ueber dem Bett (Rueckseite nicht ganz plan: Ruecksprung, Laibung) -> druck_luft.stuetzen fuellt bis 1,2 mm (Rueckseite, unsichtbar)
                    import druck_luft as DL
                    erg_, rest_, prot_ = DL.stuetzen(fl_.scale((K, K, K)), a.schicht_mm, 45.0, 2.0, 5.0, 1.2, 15.0, saeule_mm2=40.0, gitter_mm=4.0)      # Saeule/Gitter = Abbrech-Stuetzen fuer den Rest (in farbteile.json)
                    if prot_["volumen_mm3"] > 0: fl_ = erg_.scale((1 / K, 1 / K, 1 / K)); pl = fl_.translate(tuple(float(x) for x in lo)).transform(np.hstack([np.linalg.inv(R), np.zeros((3, 1))]))
                    lu = dict(schicht_mm=a.schicht_mm, inseln_vorher=prot_["inseln_vorher"], gefuellt=prot_["fuellen"], schraegen=prot_["schraege"], stuetzen_mm3=prot_["volumen_mm3"], saeulen_abbrechen=prot_["saeulen"], gitter_abbrechen=prot_["gitter"], luftinseln=len(rest_), flaeche_mm2=prot_["flaeche_rest_mm2"])
                    if prot_["inseln_vorher"]: print(f"  {name}: Luftinseln {prot_['inseln_vorher']} -> {len(rest_)} ({prot_['fuellen']} gefuellt, {prot_['schraege']} Schraegen, +{prot_['volumen_mm3']:.0f} mm3)" + (" - STUETZEN NOETIG" if rest_ else ""))
                platten[-1] = (name, pl); schreiben(pl, os.path.join(ad, "lage", name + ".stl"), K); schreiben(fl_, os.path.join(ad, name + ".stl"), K, boden=True)
                ma = [(hi[j] - lo[j]) * K for j in range(3)]; passt = max(ma[0], ma[1]) <= a.bett_mm + 0.5; nk = len(pl.decompose()); schlecht |= not passt
                teile.append(dict(name=name, wand=wand, farbe="Stein", flaeche_m2=round(float(band.sum() * px * px), 1), masse_mm=[round(float(x), 1) for x in ma], passt_aufs_bett=bool(passt), koerper=nk, volumen_cm3=round(float(pl.volume() * K ** 3 / 1000), 1), luft=lu))
                deck = float(pl.volume() / max(band.sum() * px * px * a.wand_mm / K, 1e-9)) if a.einsatz else 1.0; teile[-1]["deckung"] = round(min(deck, 9.99), 2)
                if deck < 0.5: print(f"  ACHTUNG {name}: nur {deck * 100:.0f} % der Maskenflaeche sind als Platte da - die Wand weicht dort mehr als die Wandstaerke von der mittleren Wandebene ab (Anzug, Ruecksprung) oder ist offen; der Rest bleibt am Koerper (nachmalen)")
                print(f"  {name}: {band.sum() * px * px:6.1f} m2 Stein, Drucklage {ma[0]:.0f} x {ma[1]:.0f} x {ma[2]:.1f} mm, {'passt' if passt else 'PASST NICHT aufs Bett'}, {nk} Koerper")
        print(f"{wand}: {nr} Platten; {rest:.1f} m2 Stein in Inseln < {a.min_m2} m2 oder blossen Streifen bleiben am Koerper (nachmalen)")
    if a.einsatz and a.pfosten_mm > 0:      # Eckpfosten innen - VERWORFEN als Standard (17.11.2026): mit Klebefalz nur am Rand zerfiel der Koerper in 243 Stuecke (Putzinseln im Stein ohne Halt); jetzt traegt eine durchgehende Innenschicht, Pfosten nur auf Wunsch (17.11.2026): Steinplatten auf BEIDEN Waenden einer Gebaeudeecke nehmen die ganze Ecke weg - der Koerper zerfiel in 47 von 48 Hoehenschnitten
        sp = a.pfosten_mm / K; wd = a.wand_mm / K; zs = [w["z"] for w in waende]
        if zs:
            z0_, z1_ = min(z[0] for z in zs), max(z[1] for z in zs); np_ = 0
            for zq in np.arange(z0_ + 1.0, z1_, 4.0):                         # Ecken aus dem Querschnitt des MODELLS (alle 4 m neu: Ruecksprunge), nicht aus den Masken - auch Ecken zu Waenden ohne Steinmaske verlieren ihr Ende
                pg = [q for q in modell.slice(float(zq)).to_polygons() if len(q) >= 4 and 0.5 * float(np.sum(q[:, 0] * np.roll(q[:, 1], -1) - np.roll(q[:, 0], -1) * q[:, 1])) > 20.0]
                for q in pg:
                    e = cv2.approxPolyDP(q.astype(np.float32).reshape(-1, 1, 2), 0.4, True).reshape(-1, 2).astype(float)
                    for k_ in range(len(e)):
                        p0, p1, p2 = e[k_ - 1], e[k_], e[(k_ + 1) % len(e)]; d1 = (p1 - p0) / max(np.linalg.norm(p1 - p0), 1e-9); d2 = (p2 - p1) / max(np.linalg.norm(p2 - p1), 1e-9)
                        if d1[0] * d2[1] - d1[1] * d2[0] < 0.5 or min(np.linalg.norm(p1 - p0), np.linalg.norm(p2 - p1)) < 1.0: continue      # nur ausspringende Ecken (Umlauf gegen den Uhrzeiger) mit langen Schenkeln
                        n1 = np.array([-d1[1], d1[0]]); n2 = np.array([-d2[1], d2[0]]); c = p1 + wd * 0.7 * (n1 + n2)                       # nach innen (links der Kante), 30 % in die Wand hinein
                        qd = np.array([c, c + sp * n2, c + sp * (n1 + n2), c + sp * n1]); fl_ = 0.5 * float(np.sum(qd[:, 0] * np.roll(qd[:, 1], -1) - np.roll(qd[:, 0], -1) * qd[:, 1]))
                        innen.append(CS([qd if fl_ > 0 else qd[::-1]], FillRule.Positive).extrude(4.0).translate((0, 0, float(zq) - 2.0))); np_ += 1
            print(f"Eckpfosten {a.pfosten_mm} mm innen: {np_} Abschnitte (je 4 m) an den ausspringenden Ecken des Querschnitts, z {z0_:.1f}..{z1_:.1f} m")
    if taschen:
        zus = M.batch_boolean(innen, OpType.Add) if innen else M(); tu = M.batch_boolean(taschen, OpType.Add)
        if a.einsatz or a.ring:
            rg, raum = ringschicht(modell, tu, a.innen_mm / K, a.wand_mm / K, a.falz_mm / K, spiel); zus = (zus ^ raum) + rg; print(f"Ringschicht aus den Hoehenschnitten (um die Gebaeudeecken, im Hohlraum): {rg.volume() * K ** 3 / 1000:.1f} cm3 im Druck")
        else: zus = zus ^ modell.hull()
        koerper = (modell + zus) - tu
        if zurueck: koerper = koerper + (M.batch_boolean(zurueck, OpType.Add) - M.batch_boolean([pl_ for nm_, pl_ in platten if nm_], OpType.Add))      # minus ALLE Platten: der Kruemel eines Bandes lag 0,6 mm3 in der Platte des Nachbarbandes
        print(f"Innenschicht {a.innen_mm} mm hinter den Taschen: {zus.volume():.2f} m3 = {zus.volume() * K ** 3 / 1000:.1f} cm3 im Druck")
    st_ = sorted(koerper.decompose(), key=lambda x_: -x_.volume()); lose = sum(x_.volume() for x_ in st_[1:]); gr_ = [x_.volume() for x_ in st_]
    if len(st_) > 1 and lose <= 0.001 * gr_[0]: koerper = st_[0]; kruemel[0] += lose; lose = 0.0      # Splitter am Taschenrand verwerfen (gemeldet); groessere lose Stuecke bleiben und sind ein Fehler
    nk = len(koerper.decompose()); schreiben(koerper, os.path.join(ad, "koerper.stl"), K); schlecht |= nk > 1
    print(f"Koerper: {koerper.num_tri()} Dreiecke, {koerper.volume():.1f} m3 (vorher {v0:.1f}), {nk} Koerper" + (f" - LOSE STUECKE {lose:.3f} m3 (was vor der Platte stand, hat den Halt verloren)" if nk > 1 else ""))
    # Pruefungen am fertigen Koerper: Passung (Durchdringung Platte/Koerper) und offene Hoehenschnitte
    dmax = 0.0; pruef = dict()
    for name, pl in platten:
        if name is None: continue
        d_ = (pl ^ koerper).volume() * K ** 3; dmax = max(dmax, d_)
        for t_ in teile:
            if t_["name"] == name: t_["durchdringung_mm3"] = round(float(d_), 3)
    if platten: print(f"Durchdringung Platte/Koerper: hoechstens {dmax:.3f} mm3 je Platte (Druckmass; > 1 mm3 = Platte passt nicht in die Tasche)"); schlecht |= dmax > 1.0
    if taschen:
        bt_ = tu.bounding_box(); off, nz = offene_schnitte(modell, koerper, bt_[2], bt_[5], a.schnitt_m); sd = os.path.join(ad, "schnitte"); os.makedirs(sd, exist_ok=True)
        for alt in os.listdir(sd): os.remove(os.path.join(sd, alt))
        print(f"offene Hoehenschnitte: {len(off)} von {nz} (z {bt_[2]:.1f}..{bt_[5]:.1f} m alle {a.schnitt_m} m; offen = Koerper offener als das Modell)" + ("".join(f"\n  z {z:5.1f} m: {g_}" for z, g_ in off[:40])))
        zb = [o[0] for o in off[:6]] + [float(x) for x in a.schnittbild.split(",") if x]
        if not zb: zb = [round(float(bt_[2] + f_ * (bt_[5] - bt_[2])) * 2) / 2 for f_ in (0.15, 0.5, 0.85)]      # immer drei Bilder (Regel: ansehen, nicht nur zaehlen)
        for z in zb: schnittbild(os.path.join(sd, f"schnitt_z{z:05.1f}.png"), z, modell, koerper, [pl for nm_, pl in platten if nm_])
        if zb: print(f"  Querschnittsbilder (ansehen): {sd}/schnitt_z*.png")
        pruef = dict(offene_schnitte=len(off), schnitte=nz, offen_z=[o[0] for o in off], durchdringung_max_mm3=round(float(dmax), 3)); schlecht |= len(off) > 0
    import json_sicher
    json_sicher.schreiben(os.path.join(ad, "farbteile.json"), dict(objekt=a.objekt, stl=os.path.relpath(stl, ROOT), tief_mm=a.tief_mm, spiel_mm=a.spiel_mm, koerper=dict(farbe="Putz/Grundfarbe", koerperzahl=nk, lose_m3=round(float(lose), 4), volumen_cm3=round(float(koerper.volume() * K ** 3 / 1000), 1)), pruefung=pruef, platten=teile))
    if kruemel[0]: print(f"verworfene Kruemel/Splitter: {kruemel[0]:.3f} m3 = {kruemel[0] * K ** 3 / 1000:.2f} cm3 im Druck")
    print(f"-> {ad}: koerper.stl + {len(teile)} Steinplatten ({sum(t_['flaeche_m2'] for t_ in teile):.0f} m2), farbteile.json")
    return 3 if schlecht else 0


if __name__ == "__main__":
    sys.exit(main())
