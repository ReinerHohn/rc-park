#!/usr/bin/env python3
"""schwarzwald_katalog.py — Katalog markanter, schwarzwaldtypischer Modelle.
Verifizierte Koordinaten (WebSearch), berechnet LGL-2km-Kachel je Ort,
schreibt JSON (maschinell) + MD (lesbar). Basis für die Bewertung/Rangliste.
"""
import json, os
from pyproj import Transformer

T = Transformer.from_crs(4326, 25832, always_xy=True)

def tile(lat, lon):
    E, N = T.transform(lon, lat)
    Ekm, Nkm = int(E // 1000), int(N // 1000)
    Ep = Ekm if Ekm % 2 == 1 else Ekm - 1
    Np = Nkm if Nkm % 2 == 0 else Nkm - 1
    return dict(E=round(E), N=round(N), paket=f"{Ep}_{Np}", subkachel=f"{Ekm}_{Nkm}")

# kat = Natur (Gelände) ; typ dramatic_relief aus Recherche
NATUR = [
    ("Feldsee", 47.870278, 8.0325, "see/kar", 300, True, "Lehrbuch-Karsee: bis 300 m hohe halbrunde Steilwand unter dem Feldberg — eines der dramatischsten Reliefs des Schwarzwalds"),
    ("Hirschsprung / Höllental", 47.937778, 8.020278, "schlucht/felswand", 130, True, "engste Klause mit ~senkrechten 130-m-Gneiswänden + durchtunnelte Höllentalbahn"),
    ("Triberger Wasserfälle", 48.126799, 8.228309, "wasserfall", 163, True, "163 m über 7 Kaskaden — höchstes Wasser-Wahrzeichen; ideal als Lasercut-Stufenmodell"),
    ("Belchen", 47.8225, 7.833611, "gipfel", 1414, True, "ikonisch symmetrischer baumfreier Kegel — berühmtestes Schwarzwald-Profil von der Rheinebene"),
    ("Feldberg", 47.873611, 8.003889, "gipfel", 1493, True, "höchster Gipfel BWs, markante Kuppe + steiles Feldseekar an der Nordseite"),
    ("Schauinsland", 47.911944, 7.898611, "gipfel", 1284, True, "Freiburger Hausberg mit historischer Seilbahn, zerklüftete Bergbau-Flanken (~750 m Abfall ins Dreisamtal)"),
    ("Herzogenhorn", 47.835, 8.019444, "gipfel", 1415, True, "zweithöchster eigenständiger Gipfel, alpiner Charakter, steile Hänge"),
    ("Kandel", 48.062222, 8.011944, "gipfel", 1241, True, "freistehender Aussichts-/Gleitschirmberg über dem Elztal, klare Silhouette"),
    ("Wutachschlucht", 47.844722, 8.311944, "schlucht", 170, True, "größter Cañon Deutschlands, bis 170 m tiefe Steilwand-Schlucht (Ausschnitt wählen)"),
    ("Ravennaschlucht", 47.919722, 8.085, "schlucht", 80, True, "enge V-Schlucht des Höllentals mit Ravennaviadukt + Wasserfällen"),
    ("Todtnauer Wasserfall", 47.8434, 7.9391, "wasserfall", 97, True, "97 m Fallhöhe in steiler Felskerbe, teils freier Fall"),
    ("Allerheiligen-Wasserfälle", 48.5303, 8.1889, "wasserfall", 66, True, "66 m über 7 Stufen in enger Felsklamm bei der Klosterruine"),
    ("Mummelsee / Hornisgrinde", 48.5975, 8.201111, "see/kar", 135, True, "Karsee am Fuß der Hornisgrinde, Wahrzeichen der Schwarzwaldhochstraße"),
    ("Battertfelsen", 48.778889, 8.253333, "felsen", 60, True, "freistehende Porphyr-Felstürme (15–60 m) über Baden-Baden — dankbares Felsmodell"),
    ("Titisee", 47.893333, 8.146111, "see", 20, False, "größter natürlicher See, aber flache Ufer — als reines Gelände wenig markant (lebt vom Kontext)"),
    ("Schluchsee (See)", 47.821389, 8.152778, "see", 30, False, "größter See, aber sanfte Ufer — markant ist die Staumauer (Bauwerk), nicht das Gelände"),
]

# bau = Bauwerke ; parametrisierbar aus Recherche
BAU = [
    ("Schluchsee-Staumauer", 47.80064, 8.18361, "staumauer", dict(hoehe=63.5, laenge=250), True, "größtes Massebauwerk im Schwarzwald, gekrümmte Gewichtsstaumauer am größten See"),
    ("Linachtalsperre", 48.01833, 8.29056, "staumauer", dict(hoehe=25, laenge=143, bogen=13), True, "einzige Gewölbereihen-Staumauer Deutschlands (13 Gewölbe) — unverwechselbar; Generator vorhanden"),
    ("Ravenna-Viadukt", 47.9175, 8.07417, "viadukt", dict(hoehe=40, laenge=224, bogen=9), True, "9 Sandstein-Rundbögen der Höllentalbahn — Postkarten-Ikone; Generator vorhanden"),
    ("Epfenhofer Viadukt (Sauschwänzlebahn)", 47.8332, 8.525, "viadukt", dict(hoehe=34, laenge=264, bogen=8), True, "größter Viadukt der Sauschwänzlebahn, 8 hohe Natursteinbögen"),
    ("Biesenbach-Viadukt (Sauschwänzlebahn)", 47.82549, 8.55303, "viadukt", dict(hoehe=24, laenge=252, bogen=4, radius=360), True, "elegant gekrümmter Fischbauch-Bogenviadukt, R=360 m"),
    ("Hornberg-Viadukt (Schwarzwaldbahn)", 48.21433, 8.23079, "viadukt", dict(hoehe=35, laenge=236), True, "Gewölbeviadukt über das Reichenbachtal (Bogenzahl verifizieren)"),
    ("Hängebrücke Blackforestline Todtnau", 47.84423, 7.93666, "bruecke", dict(hoehe=120, laenge=450), True, "eine der längsten Fußgänger-Hängebrücken DEs, 450 m über den Todtnauer Wasserfall"),
    ("Freiburger Münster (Turm)", 47.99556, 7.85278, "turm", dict(hoehe=116), False, "einziger im MA vollendeter gotischer Turm DEs — Maßwerk-Helm nur über Skelett+Maßwerk-Platten"),
    ("Feldbergturm", 47.86445, 8.02219, "turm", dict(hoehe=42), True, "runder Turm auf dem höchsten Berg BWs, Rotationskörper"),
    ("Schauinslandturm", 47.91193, 7.89858, "turm", dict(hoehe=21.75), True, "dreieckiger Holz-Aussichtsturm, reguläres Stabwerk — gut für Lasercut-Stäbe"),
    ("Hochfirstturm", 47.90125, 8.18433, "turm", dict(hoehe=25), True, "Stahlgitterturm 1890, reguläres Fachwerk"),
    ("Kastelburg Waldkirch", 48.09755, 7.95761, "burg", dict(hoehe=28), True, "kompakte Kernburg mit hohem quadratischem Bergfried über dem Elztal"),
    ("Yburg Baden-Baden", 48.73056, 8.20028, "burg", dict(hoehe=25), True, "dominanter runder Bergfried mit Zinnenkranz über den Reben"),
    ("Martinstor Freiburg", 47.99361, 7.84889, "turm", dict(hoehe=60), True, "ältestes Stadttor Freiburgs, Torturm mit Spitzhelm"),
    ("Schwabentor Freiburg", 47.99306, 7.85417, "turm", dict(hoehe=26), True, "mittelalterliches Stadttor mit bemaltem Staffelgiebel"),
    ("Villinger Münster", 48.0602, 8.45916, "kirche", dict(hoehe=54), True, "markante Doppeltürme prägen die Silhouette Villingens"),
    ("Burg Hohengeroldseck", 48.3325, 7.98028, "burg", dict(hoehe=30), False, "ausgedehnte unregelmäßige Ruine am Felsgrat — realistisch nur über LiDAR/LOD2"),
    ("Hochburg Emmendingen", 48.11667, 7.90056, "burg", dict(hoehe=20), False, "verwinkelte Renaissance-Festung mit Bastionen — nur über LiDAR/LOD2"),
]


def build():
    cat = {"natur": [], "bauwerk": []}
    for name, lat, lon, typ, relief, dramatic, grund in NATUR:
        cat["natur"].append(dict(name=name, lat=lat, lon=lon, typ=typ, relief_m=relief,
                                 dramatic_relief=dramatic, markant=grund, **tile(lat, lon)))
    for name, lat, lon, typ, masse, param, grund in BAU:
        cat["bauwerk"].append(dict(name=name, lat=lat, lon=lon, typ=typ, masse=masse,
                                   parametrisierbar=param, markant=grund, **tile(lat, lon)))
    return cat


def write(cat, outdir="modelle"):
    jp = os.path.join(outdir, "schwarzwald_kandidaten.json")
    json.dump(cat, open(jp, "w"), ensure_ascii=False, indent=2)
    md = ["# Schwarzwald-Kandidaten — markante Modelle für 3D-Druck + Lasercut\n",
          "Verifizierte Koordinaten, berechnete LGL-2km-Kachel (DGM025/DOP20: "
          "`.../data/dgm025/dgm025_32_{paket}_2_bw.zip`).\n",
          "## Natur / Gelände (Reihenfolge ≈ Markanz)\n",
          "| Ort | Typ | Relief m | dramatisch | LGL-Paket | Subkachel | warum markant |",
          "|---|---|--:|:--:|---|---|---|"]
    for c in sorted(cat["natur"], key=lambda c: -c["relief_m"] * (1 if c["dramatic_relief"] else 0.2)):
        md.append(f"| {c['name']} | {c['typ']} | {c['relief_m']} | "
                  f"{'✅' if c['dramatic_relief'] else '⚠️'} | {c['paket']} | {c['subkachel']} | {c['markant']} |")
    md += ["\n## Bauwerke (parametrisch nachbaubar?)\n",
           "| Bauwerk | Typ | Maße | parametrisierbar | LGL-Paket | warum markant |",
           "|---|---|---|:--:|---|---|"]
    for c in sorted(cat["bauwerk"], key=lambda c: (0 if c["parametrisierbar"] else 1, c["name"])):
        masse = ", ".join(f"{k}={v}" for k, v in c["masse"].items())
        md.append(f"| {c['name']} | {c['typ']} | {masse} | "
                  f"{'✅' if c['parametrisierbar'] else '❌'} | {c['paket']} | {c['markant']} |")
    md += ["\n---", "Bewertung je Modell: `tools/bewerter_voting.py` (3 Juroren + Voting). "
           "DEM holen: Kachel oben → DGM025-ZIP. Dann Manifest + Voting."]
    mp = os.path.join(outdir, "schwarzwald_kandidaten.md")
    open(mp, "w").write("\n".join(md) + "\n")
    print(f"-> {jp}\n-> {mp}  ({len(cat['natur'])} Natur, {len(cat['bauwerk'])} Bauwerke)")


if __name__ == "__main__":
    write(build())
