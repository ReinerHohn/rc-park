#!/usr/bin/env python3
"""quellen_inventar.py — ERSCHÖPFENDE, ERZWUNGENE Quellen-Inventur für ein Bauwerk.

Grund (User, SEHR sauer): ich vergesse wiederholt Datenquellen (LOD2-Grundriss zur Box verworfen;
DOP/DOM1/DGM1 übersehen; radiometrische/LiDAR-Daten nicht bedacht). Das wird strukturell UNMÖGLICH
gemacht: Es gibt eine KANONISCHE, VOLLSTÄNDIGE Liste ALLER Quellentypen (REGISTER unten). Das Tool
druckt IMMER JEDEN Typ mit explizitem Status — nichts kann still übersprungen werden:
   ✅ genutzt | ⚠️ IM REPO, NICHT GENUTZT | ⬇️ UPSTREAM VERFÜGBAR, NICHT GELADEN | — n/a hier

HARTE REGEL (User, x-mal): alles Öffentliche mergen, NICHTS raten solange eine Quelle existiert.
PFLICHT vor jedem Bau. Exit-Code 2, solange ⚠️/⬇️ offen sind (CI-/Guard-tauglich).

Lauf:  python3 tools/quellen_inventar.py --name hofgut_sternen [--utm E,N] [--lat.. --lon..]
"""
import argparse, glob, json, os, re, sys

# ------------------------------------------------------------------------------------------------
# KANONISCHES REGISTER ALLER QUELLENTYPEN. Reihenfolge = Vollständigkeits-Checkliste.
# jeder Eintrag: key, kurz, liefert, repo-regex, upstream (wo zu holen, BW/global), bw_standard
#   bw_standard=True → für JEDE BW-Koordinate upstream verfügbar (LGL), also „nicht geladen" = Bringschuld.
# ------------------------------------------------------------------------------------------------
REGISTER = [
    ("LOD2",     "3D-Gebäudemodell", "Grundriss(Teile)+Trauf/First = amtliches Massing",
     [r"LoD2.*\.gml"], "LGL BW opengeodata (LoD2_32_*.zip)", True),
    ("LOD1",     "3D-Klötzchen",     "einfaches Blockmodell (Fallback zu LOD2)",
     [r"LoD1.*\.gml"], "LGL BW opengeodata", True),
    ("DOP_RGB",  "Luft-Orthofoto",   "Dachplan v. oben: First/Gauben/Kamine + Dach-/Bodentextur",
     [r"dop\d*rgb.*\.(tif|jp2)"], "LGL BW opengeodata (dop20rgb_*)", True),
    ("DOP_CIR",  "Color-Infrarot",   "RADIOMETRISCH: NIR-Band → Vegetation/Material/Versiegelung",
     [r"dop\d*cir.*\.(tif|jp2)", r"dop.*nir.*\.(tif|jp2)"], "LGL BW opengeodata (dop20cir_*)", True),
    ("DOM1",     "Laser-Oberfläche", "1 m Oberfläche MIT Dächern/Bäumen: echte Dach-/Objektgeometrie",
     [r"dom1_.*\.(tif|xyz|asc)"], "LGL BW opengeodata (dom1_*)", True),
    ("DGM1",     "Laser-Boden",      "1 m Gelände: Sockel-/Umgebungshöhe",
     [r"dgm1_.*\.(xyz|tif|asc)"], "LGL BW opengeodata (dgm1_*)", True),
    ("nDOM",     "Objekthöhe",       "DOM−DGM = Höhe über Boden (sonst SELBST rechnen aus DOM1/DGM1!)",
     [r"ndom.*\.(tif|xyz|asc)"], "LGL oder = DOM1−DGM1 selbst rechnen", True),
    ("LAZ_ALS",  "LiDAR-Punktwolke", "ROHE 3D-Laserpunkte (dichter als Raster) + INTENSITÄT/Radiometrie/Klassen",
     [r".*\.(laz|las|copc)"], "LGL BW 3D-Messdaten (ALS Punktwolke)", True),
    ("ALKIS",    "Kataster",         "amtl. Flurstück-/Gebäudeumriss + Nutzung (Grundwahrheit Footprint)",
     [r".*alkis.*", r".*flurstueck.*", r".*hausumring.*\.(shp|gml|geojson)"], "LGL BW / Geoportal", True),
    ("HIST_DOP", "Historik-Luftbild","frühere Orthofotos/Zustände (zeitliche Referenz)",
     [r".*(hist|19\d\d|20[01]\d).*dop.*\.(tif|jpg)"], "LGL BW / LUBW Archiv", False),
    ("S2_MSI",   "Sentinel-2",       "MULTISPEKTRAL 10 m, 13 Bänder (regional, Landbedeckung)",
     [r".*(sentinel.?2|S2[AB]_|_MSIL).*"], "Copernicus Open Access Hub", True),
    ("S1_SAR",   "Sentinel-1 Radar", "SAR (wetterunabhängig, Struktur/Feuchte)",
     [r".*(sentinel.?1|S1[AB]_).*"], "Copernicus Open Access Hub", True),
    ("COP_DEM",  "Copernicus DEM",   "30 m globales DEM (grob, Fallback-Gelände)",
     [r".*(cop.?dem|glo.?30|COP30).*\.(tif|dt2)"], "AWS copernicus-dem-30m (no-auth)", True),
    ("OSM",      "OpenStreetMap",    "Vektor: Gebäudeumriss/Wege/Trasse/Tags",
     [r".*(osm|track|trasse|building).*\.(npy|json|geojson|osm|pbf)"], "Overpass / OSM extract", True),
    ("FOTO_BODEN", "Bodenfotos",     "Fassadendetail/Material/Farben/Stückzahlen (eigene/Commons)",
     [r".*\.(jpg|jpeg|png)"], "eigene / Wikimedia Commons / Google", True),
    ("STREET",   "Street-Level",     "Panorama/Street-Level (Fassade schräg, Mapillary)",
     [r".*(mapillary|streetview|pano).*\.(jpg|png)"], "Mapillary API / eigene", False),
]
SUCHE = ["daten/**", "modelle/**"]


def tile_of(E, N):
    return f"{int(E)//1000}_{int(N)//1000}"


def used_markers(name):
    md = f"modelle/{name}"

    def ex(*fs):
        return any(os.path.exists(f"{md}/{f}") for f in fs)
    return {
        "LOD2": ex("footprint.json", "hofgut_lod2.json", "hofgut_massing.glb") or bool(glob.glob(f"{md}/*lod2*")),
        "LOD1": ex("lod1.json"),
        "DOP_RGB": ex("dop_dach.png") or bool(glob.glob(f"{md}/*textured*")) or bool(glob.glob(f"{md}/*dop*")),
        "DOP_CIR": ex("cir.json") or bool(glob.glob(f"{md}/*cir*")),
        "DOM1": ex("dom_roof.json") or bool(glob.glob(f"{md}/*dom*")),
        "DGM1": ex("terrain.json", "gelaende.json") or bool(glob.glob(f"{md}/*dgm*")),
        "nDOM": ex("ndom.json", "ndom.png"),
        "LAZ_ALS": ex("punktwolke.json") or bool(glob.glob(f"{md}/*.laz") + glob.glob(f"{md}/*.las")),
        "ALKIS": ex("alkis.json", "flurstueck.json"),
        "HIST_DOP": ex("hist_dop.json"),
        "S2_MSI": ex("sentinel2.json"),
        "S1_SAR": ex("sentinel1.json"),
        "COP_DEM": ex("copdem.json"),
        "OSM": bool(glob.glob(f"{md}/*track*") + glob.glob(f"{md}/*osm*")),
        "FOTO_BODEN": ex("farben.json") or bool(glob.glob(f"daten/{name}/fotos/*_mask.png")),
        "STREET": ex("street.json"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--utm", default=None, help="E,N (UTM32)")
    a = ap.parse_args()

    E = N = None
    if a.utm:
        E, N = [float(v) for v in a.utm.split(",")]
    elif os.path.exists(f"modelle/{a.name}/footprint.json"):
        E, N, *_ = json.load(open(f"modelle/{a.name}/footprint.json"))["origin_utm"]
    tile = tile_of(E, N) if E else None
    inBW = bool(E and 400000 < E < 620000 and 5260000 < N < 5520000)   # grob Baden-Württemberg
    tnums = set()
    if tile:
        e, n = int(E) // 1000, int(N) // 1000
        for de in (-2, -1, 0, 1):
            for dn in (-2, -1, 0, 1):
                tnums.add(f"{e+de}_{n+dn}")

    allfiles = [f for pat in SUCHE for f in glob.glob(pat, recursive=True) if os.path.isfile(f)]
    used = used_markers(a.name)

    rows, offen = [], []
    for key, kurz, liefert, pats, upstream, bw_std in REGISTER:
        rx = re.compile("|".join(pats), re.I)
        hits = [f for f in allfiles if rx.search(os.path.basename(f))]
        if key in ("FOTO_BODEN",):
            hits = [f for f in hits if f"/{a.name}/fotos/" in f.replace("\\", "/")
                    and not re.search(r"_(mask|seg|silhouette)", f)]
        elif key in ("STREET", "HIST_DOP"):
            hits = [f for f in hits if a.name in f]
        elif tile:                                            # Geo-Kacheln auf Bauwerks-Umfeld filtern
            hits = [f for f in hits if any(t in f for t in tnums) or re.search(r"53\d\d", f) and key in ("LOD2", "LOD1")]
        if used.get(key):
            st = "✅ genutzt"
        elif hits:
            st = "⚠️  IM REPO, NICHT GENUTZT"; offen.append((key, upstream))
        elif bw_std and inBW:
            st = "⬇️  UPSTREAM VERFÜGBAR (BW), NICHT GELADEN"; offen.append((key, upstream))
        elif bw_std:
            st = "⬇️  upstream verfügbar, nicht geladen"; offen.append((key, upstream))
        else:
            st = "—  hier n/a"
        rows.append((key, kurz, liefert, len(hits), st, upstream, hits[:2]))

    # Manifest
    md = [f"# QUELLEN-MANIFEST — {a.name}", "",
          f"Kachel UTM32 **{tile}** · E {E:.0f} N {N:.0f} · {'in BW (LGL-Standarddaten upstream verfügbar)' if inBW else 'außerhalb BW'}",
          "", "Auto-Inventur `tools/quellen_inventar.py` — KANONISCHE Vollständigkeits-Checkliste.",
          "HARTE REGEL: alles Vorhandene mergen, NICHTS raten. ⚠️=im Repo ungenutzt, ⬇️=upstream Bringschuld.",
          "", "| # | Quelle | liefert | Dateien | Status | woher |", "|--|--|--|--|--|--|"]
    for i, (key, kurz, liefert, nf, st, up, ex) in enumerate(rows, 1):
        md.append(f"| {i} | **{key}** ({kurz}) | {liefert} | {nf} | {st} | {up} |")
    open(f"modelle/{a.name}/QUELLEN.md", "w").write("\n".join(md) + "\n")

    print(f"\n=== QUELLEN-INVENTUR  {a.name}  (Kachel {tile}, {'BW' if inBW else '—'}) — {len(REGISTER)} Typen ===")
    for i, (key, kurz, liefert, nf, st, up, ex) in enumerate(rows, 1):
        print(f" {i:2d}. {key:10s} {st:42s} [{nf}]  {kurz}")
        if ("NICHT GELADEN" in st or "NICHT GENUTZT" in st):
            print(f"        └─ woher: {up}")
    genutzt = sum(1 for r in rows if "✅" in r[4])
    print(f"\n  {genutzt}/{len(REGISTER)} Typen genutzt · {len(offen)} offen.")
    if offen:
        print("  ⚠️  OFFEN (merge-pflichtig, nicht raten!): " + ", ".join(k for k, _ in offen))
    print(f"-> modelle/{a.name}/QUELLEN.md")
    sys.exit(2 if offen else 0)


if __name__ == "__main__":
    main()
