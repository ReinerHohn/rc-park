#!/usr/bin/env python3
"""stadt_lod2_schneiden.py - Stadt-Freiburg-LoD2 (Quellentyp 18, STADT_LOD2) auf ein Objekt zuschneiden (Auftrag G4).

Zweite, unabhaengige Dachquelle neben dem LGL-LoD2 (Regel 5: NICHT mitteln, nur vergleichen). Geht NICHT in den Generator.

Ablauf:
  1. LGL-LoD2-Gebaeude des Objekts laden - GENAUSO wie tools/baukasten_gen.py lod2_flaechen():
     lod2_gebaeude.extract(gml, center=rahmen.mitte_utm, radius=60) und Auswahl ueber lod2.id (objekt.json); ohne lod2-Eintrag
     (Martinstor) ueber --lgl-id bzw. "Lage im Grundriss / naechste Mitte" wie tools/objekt_daten.py.
  2. Modellrahmen aus objekt.json "rahmen" (mitte_utm, xhat_utm, yhat_utm, gelaende) bzw. anker3d.json: lokal(P) = (d@xhat, d@yhat, z-gelaende).
  3. Stadt-GML (CityGML 2.0, EPSG:25832) STREAMEND lesen (1,6 GB), nur Gebaeude, deren Huellquader den Umriss + rand schneidet.
  4. Auswahl: Stadt-Gebaeude, dessen Grundriss (Boden- + Dachprojektion) die LGL-Grundrissflaeche um mehr als --min-ueberlapp m2 schneidet
     = "schneidet"; Gebaeude nur im Randstreifen (--rand m) = "nachbar_im_rand" (nur gelistet, nicht in den Vergleich).
  5. Ausgabe JSON: Flaechen (Wand/Dach/Boden, lokale + UTM-Koordinaten), First, Traufe(n), Grundrissflaeche, Dachflaechenzahl,
     Quelle + Lizenz + Datum + EPSG; daneben die gleichen Kennzahlen des LGL-LoD2 (gleicher Schaetzer).

  python tools/stadt_lod2_schneiden.py modelle/kaufhaus_null5/objekt.json --gml /media/oem/scan/rc-park_daten/freiburg_stadt/lod2/20261007_Freiburg_LoD2.gml
"""
import argparse, datetime, glob, json, os, re, sys
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lod2_gebaeude as LG

QUELLE = "Stadt Freiburg, Stadtmodell LoD2 (CityGML 2.0, tridicon/virtualcitysystems), geoportal.freiburg.de/stadtmodell"
LIZENZ = {"id": "dl-de/by-2-0", "name": "Datenlizenz Deutschland - Namensnennung - Version 2.0", "url": "https://www.govdata.de/dl-de/by-2-0",
          "vermerk": "Datengrundlage: Stadt Freiburg, www.freiburg.de",
          "metadaten": "https://metadaten.geoportal-bw.de/geonetwork/srv/api/records/1c576440-e5e1-4095-bff1-a14d76cec6f4"}
ENV = re.compile(r"<gml:lowerCorner>([-\d.eE+ ]+)</gml:lowerCorner>\s*<gml:upperCorner>([-\d.eE+ ]+)</gml:upperCorner>")
SURF = re.compile(r"<bldg:(WallSurface|RoofSurface|GroundSurface|ClosureSurface)\b.*?</bldg:\1>", re.S)
POS = re.compile(r"<gml:posList[^>]*>([^<]+)</gml:posList>")
ATTR = re.compile(r'<gen:stringAttribute name="([^"]+)">\s*<gen:value>([^<]*)</gen:value>')
TYP = {"WallSurface": "Wand", "RoofSurface": "Dach", "GroundSurface": "Boden", "ClosureSurface": "Verschluss"}


def rahmen_von(obj, objpfad):
    R = obj.get("rahmen")
    if not R:
        R = json.load(open(os.path.join(os.path.dirname(objpfad), "anker3d.json")))
    return np.array(R["mitte_utm"], float), np.array(R["xhat_utm"], float), np.array(R["yhat_utm"], float), float(R["gelaende"])


def lokal_fn(C0, XH, YH, Z0):
    def f(P):
        P = np.asarray(P, float); d = P[:, :2] - C0
        return np.c_[d @ XH, d @ YH, P[:, 2] - Z0]
    return f


def kennzahlen(polys):
    """EIN Schaetzer fuer beide LoD2: polys = [(typ 'Wand'|'Dach'|'Boden', Nx3 UTM)]. Hoehen ueber min(Boden-z) des Gebaeudes."""
    bod = [P for t, P in polys if t == "Boden"]; dach = [P for t, P in polys if t == "Dach"]
    gz = min(float(P[:, 2].min()) for P in bod) if bod else min(float(P[:, 2].min()) for _, P in polys)
    fl = [Polygon(P[:, :2]).buffer(0) for P in bod + [d for d in dach if Polygon(d[:, :2]).buffer(0).area >= 0.05]]
    flaeche = unary_union(fl) if fl else Polygon()
    bflaeche = unary_union([Polygon(P[:, :2]).buffer(0) for P in bod]) if bod else Polygon()
    dz = np.concatenate([P[:, 2] for P in dach]) if dach else np.array([gz])
    mins = sorted({round(float(P[:, 2].min() - gz) * 4) / 4 for P in dach if Polygon(P[:, :2]).buffer(0).area >= 0.05})
    n_dach = sum(1 for P in dach if Polygon(P[:, :2]).buffer(0).area >= 0.05)       # wie rumpf_lod2: senkrechte/entartete Flaechen zaehlen nicht
    return dict(boden_z_abs=round(gz, 3), first_m=round(float(dz.max() - gz), 3), traufe_m=round(float(dz.min() - gz), 3),
                traufe_ebenen_m=mins, grundriss_m2=round(float(flaeche.area), 2), bodenflaeche_m2=round(float(bflaeche.area), 2),
                n_dachflaechen=n_dach, n_bodenflaechen=len(bod), n_wandflaechen=sum(1 for t, _ in polys if t == "Wand")), flaeche


def lgl_laden(obj, objpfad, C0, lgl_id, lgl_gml):
    gml = lgl_gml or (obj.get("lod2") or {}).get("gml")
    lid = lgl_id or (obj.get("lod2") or {}).get("id")
    if not gml:
        t = f"{int(C0[0]) // 1000}_{int(C0[1]) // 1000}"
        c = glob.glob(f"/media/oem/scan/rc-park_daten/_geo/LoD2_32_*/LoD2_32_{t}_1_BW.gml")
        if not c: sys.exit(f"kein LGL-LoD2 fuer Kachel {t} gefunden (--lgl-gml angeben)")
        gml = c[0]
    picked = LG.extract(gml, center=tuple(C0), radius=60.0)
    if lid:
        eig = [(m, p) for m, p in picked if m.get("id") == lid]
        if not eig: sys.exit(f"LGL-LoD2-Gebaeude {lid} nicht in {gml}")
        return gml, eig[0][0], eig[0][1]
    from matplotlib.path import Path as _P
    def trifft(mp):
        return any(_P(P[:, :2]).contains_point(tuple(C0)) for t, P in mp[1] if t == "GroundSurface")
    mp = next((m for m in picked if trifft(m)), None) or min(picked, key=lambda m: np.hypot(*(np.array(m[0]["center_utm"]) - C0)))
    return gml, mp[0], mp[1]


def stadt_lesen(gml, bbox):
    """Streamend: liefert (id, member_text) der Gebaeude, deren Huellquader bbox=(x0,y0,x1,y1) schneidet."""
    buf, an = [], False
    with open(gml, encoding="utf-8", errors="replace") as f:
        for line in f:
            if not an:
                if "<cityObjectMember>" in line: an = True; buf = [line]
                continue
            buf.append(line)
            if "</cityObjectMember>" in line:
                an = False; txt = "".join(buf); m = ENV.search(txt)
                if m:
                    lo = [float(v) for v in m.group(1).split()]; hi = [float(v) for v in m.group(2).split()]
                    if not (hi[0] < bbox[0] or lo[0] > bbox[2] or hi[1] < bbox[1] or lo[1] > bbox[3]):
                        gid = re.search(r'<bldg:Building gml:id="([^"]+)"', txt)
                        yield (gid.group(1) if gid else "?"), txt
                buf = []


def parse_gebaeude(txt):
    polys = []
    for ms in SURF.finditer(txt):
        for m in POS.finditer(ms.group(0)):
            v = np.array([float(x) for x in m.group(1).split()]);
            if len(v) < 9 or len(v) % 3: continue
            P = v.reshape(-1, 3)
            if np.allclose(P[0], P[-1]): P = P[:-1]
            if len(P) >= 3: polys.append((TYP[ms.group(1)], P))
    return polys, dict(ATTR.findall(txt))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("objekt"); ap.add_argument("--gml", required=True, help="Stadt-LoD2 GML (Datei oder Ordner mit *.gml)")
    ap.add_argument("--aus", default=None); ap.add_argument("--rand", type=float, default=2.0)
    ap.add_argument("--min-ueberlapp", type=float, default=1.0, help="m2 Mindestueberlapp der Grundrisse fuer 'schneidet'")
    ap.add_argument("--lgl-id", default=None); ap.add_argument("--lgl-gml", default=None)
    a = ap.parse_args()
    od = os.path.dirname(os.path.abspath(a.objekt)); obj = json.load(open(a.objekt))
    aus = a.aus or os.path.join(od, "stadt_lod2.json")
    C0, XH, YH, Z0 = rahmen_von(obj, a.objekt); lok = lokal_fn(C0, XH, YH, Z0)
    gml_l, meta_l, polys_l = lgl_laden(obj, a.objekt, C0, a.lgl_id, a.lgl_gml)
    TYPL = {"WallSurface": "Wand", "RoofSurface": "Dach", "GroundSurface": "Boden", "ClosureSurface": "Verschluss"}
    pl = [(TYPL[t], P) for t, P in polys_l]
    kz_l, fl_l = kennzahlen(pl)
    print(f"LGL-LoD2 {meta_l['id']}: {kz_l}")
    bbox = fl_l.buffer(a.rand).bounds
    gmls = sorted(glob.glob(os.path.join(a.gml, "*.gml"))) if os.path.isdir(a.gml) else [a.gml]
    sel, rand_nb, epsg, creation = [], [], set(), set()
    for g in gmls:
        epsg.update(re.findall(r'srsName="([^"]+)"', open(g, encoding="utf-8", errors="replace").read(20000)))
        for gid, txt in stadt_lesen(g, bbox):
            polys, attr = parse_gebaeude(txt)
            if not polys: continue
            creation.update(re.findall(r"<creationDate>([^<]+)</creationDate>", txt)[:1])
            kz, fl = kennzahlen(polys); ue = fl.intersection(fl_l).area
            nah = fl.distance(fl_l) <= a.rand
            rec = dict(id=gid, ueberlapp_m2=round(ue, 2), attribute=attr, kennzahlen=kz, polys=polys)
            if ue > a.min_ueberlapp: sel.append(rec)
            elif nah: rand_nb.append(rec)
    if not sel: sys.exit("kein Stadt-LoD2-Gebaeude schneidet den Objektumriss")
    allp = [p for r in sel for p in r["polys"]]
    kz_s, _ = kennzahlen(allp)
    def flaechen(polys):
        return [dict(typ=t, lokal=np.round(lok(P), 3).tolist(), utm=np.round(P, 3).tolist()) for t, P in polys]
    out = dict(
        objekt=a.objekt, erzeugt=datetime.date.today().isoformat(), werkzeug="tools/stadt_lod2_schneiden.py (G4)",
        quelle=QUELLE, lizenz=LIZENZ, quelltyp="stadt_lod2", register_typ=18,
        gml_datei=os.path.abspath(a.gml), gml_stand=sorted(creation), gml_dateidatum=datetime.date.fromtimestamp(os.path.getmtime(gmls[0])).isoformat(),
        epsg_gml=sorted(epsg), epsg_erwartet="urn:ogc:def:crs:EPSG::25832 (ETRS89/UTM32, h = ue.NN wie LGL)",
        rahmen=dict(mitte_utm=C0.tolist(), xhat_utm=XH.tolist(), yhat_utm=YH.tolist(), gelaende=Z0, quelle="objekt.json rahmen bzw. anker3d.json (wie baukasten_gen.lokal)"),
        auswahl=dict(kriterium=f"Grundriss-Ueberlapp mit LGL-Grundriss > {a.min_ueberlapp} m2; Randstreifen {a.rand} m nur gelistet", rand=a.rand),
        lgl=dict(id=meta_l["id"], gml=gml_l, kennzahlen=kz_l),
        stadt=dict(gebaeude_ids=[r["id"] for r in sel], kennzahlen=kz_s,
                   gebaeude=[dict(id=r["id"], ueberlapp_m2=r["ueberlapp_m2"], attribute=r["attribute"], kennzahlen=r["kennzahlen"], flaechen=flaechen(r["polys"])) for r in sel]),
        nachbar_im_rand=[dict(id=r["id"], kennzahlen=r["kennzahlen"], attribute={k: r["attribute"].get(k) for k in ("Firsthoehe", "MittlereTraufHoehe", "Lagebezeichnung", "Funktion_Gebaeude")}) for r in rand_nb],
        vergleich={k: dict(lgl=kz_l[k], stadt=kz_s[k]) for k in ("first_m", "traufe_m", "traufe_ebenen_m", "grundriss_m2", "n_dachflaechen")},
        hinweis="Regel 5: zwei Quellen, NICHT mitteln. Wand-/Dachzuordnung nach CityGML-Typ der Quelle; Hoehen ueber min(Boden-z) des jeweiligen Gebaeudes.")
    tmp = aus + ".tmp"; json.dump(out, open(tmp, "w"), ensure_ascii=False); os.replace(tmp, aus)
    print(f"Stadt-LoD2 {out['stadt']['gebaeude_ids']}: {kz_s}")
    print(f"Nachbarn im Rand: {[r['id'] for r in rand_nb]}; EPSG {sorted(epsg)}; -> {aus}")


if __name__ == "__main__":
    main()
