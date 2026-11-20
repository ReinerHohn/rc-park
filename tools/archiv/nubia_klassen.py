#!/usr/bin/env python3
"""Stufe 4: Inventar zusammenfuehren, Dubletten, GPS-Pruefung der Ordnerzuordnung, Turmfotos, Klassen, Sortierlisten, Kontaktboegen.
SICHER (aus Datei): EXIF, MD5, Aufloesung, GPS-Koordinaten, Laplace-Zahl.
HINWEIS (heuristisch): Inhaltsklasse, Merkmalsabgleich, Zeit-interpolierte Position, Zoomverdacht.
Koordinaten des Kaufhauses/Martinstors werden aus modelle/<objekt>/objekt.json bzw. anker3d.json gelesen."""
import os, sys, json, ast, math, csv, datetime, collections, shutil
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nubia_kontaktbogen import bogen
AUS = "/media/oem/TOSHIBA EXT/rc-park_auslagern/nubia_sortierung"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def dms(s):
    t = ast.literal_eval(s); return t[0] + t[1] / 60 + t[2] / 3600

def utm_zu_wgs84(E, N, zone=32):
    # WGS84-Umkehrformel (Snyder) - unabhaengig von tools/bilder_holen.py
    a = 6378137.0; f = 1 / 298.257223563; k0 = 0.9996
    e2 = f * (2 - f); ep2 = e2 / (1 - e2)
    x = E - 500000.0; y = N
    M = y / k0
    mu = M / (a * (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256))
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    p = (mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu) + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu)
         + (151 * e1 ** 3 / 96) * math.sin(6 * mu))
    C1 = ep2 * math.cos(p) ** 2; T1 = math.tan(p) ** 2
    N1 = a / math.sqrt(1 - e2 * math.sin(p) ** 2); R1 = a * (1 - e2) / (1 - e2 * math.sin(p) ** 2) ** 1.5
    D = x / (N1 * k0)
    lat = p - (N1 * math.tan(p) / R1) * (D ** 2 / 2 - (5 + 3 * T1 + 10 * C1 - 4 * C1 ** 2 - 9 * ep2) * D ** 4 / 24)
    lon0 = math.radians(zone * 6 - 183)
    lon = lon0 + (D - (1 + 2 * T1 + C1) * D ** 3 / 6 + (5 - 2 * C1 + 28 * T1 - 3 * C1 ** 2 + 8 * ep2 + 24 * T1 ** 2) * D ** 5 / 120) / math.cos(p)
    return math.degrees(lat), math.degrees(lon)

def dist_m(lat1, lon1, lat2, lon2):
    return math.hypot((lat1 - lat2) * 111200.0, (lon1 - lon2) * 111200.0 * math.cos(math.radians(lat1)))

def ham(a, b): return bin(int(a, 16) ^ int(b, 16)).count("1")

def ts(s):
    return datetime.datetime.strptime(s, "%Y:%m:%d %H:%M:%S").timestamp() if s else None

def main():
    inv = [r for r in json.load(open(AUS + "/inventar_roh.json")) if r["ok"]]
    q = [r for r in inv if r["typ"] == "quelle"]
    vorh = [r for r in inv if r["typ"] in ("vorhanden", "eingang_root")]
    ab = json.load(open(AUS + "/abgleich.json")) if os.path.exists(AUS + "/abgleich.json") else {"paare": {}, "pools": {}}
    seg = json.load(open(AUS + "/segment.json")) if os.path.exists(AUS + "/segment.json") else {}
    # ---- Referenzkoordinaten aus dem Repo
    ref = {}
    ref["kaufhaus"] = json.load(open(f"{REPO}/modelle/kaufhaus_null5/objekt.json"))["lage"]
    ref["kaufhaus"] = (ref["kaufhaus"]["lat"], ref["kaufhaus"]["lon"])
    try:
        a = json.load(open(f"{REPO}/modelle/martinstor/anker3d.json"))["mitte_utm"]
        ref["martinstor"] = utm_zu_wgs84(a[0], a[1])
    except Exception:
        pass
    # ---- GPS
    for r in q:
        g = r["gps_tags"]
        r["t"] = ts(r["datum"])
        if g and "2" in g and "4" in g:
            r["lat"] = dms(g["2"]); r["lon"] = dms(g["4"]); r["alt"] = float(g.get("6", "nan")); r["gps_quelle"] = "exif"
        else:
            r["lat"] = r["lon"] = r["alt"] = None; r["gps_quelle"] = "keine"
    qg = sorted([r for r in q if r["lat"] is not None], key=lambda r: r["t"])
    tg = np.array([r["t"] for r in qg])
    for r in q:
        if r["lat"] is None and len(qg):
            nb = [qg[i] for i in np.where(np.abs(tg - r["t"]) <= 90)[0]]
            if nb:
                r["lat"] = float(np.median([n["lat"] for n in nb])); r["lon"] = float(np.median([n["lon"] for n in nb]))
                r["alt"] = float(np.median([n["alt"] for n in nb])); r["gps_quelle"] = f"zeit_interpoliert({len(nb)})"
    # ---- Turm: GPS-Hoehe
    hoch = [r for r in qg if r["alt"] >= 385]
    tlat = float(np.median([r["lat"] for r in hoch])); tlon = float(np.median([r["lon"] for r in hoch]))
    for r in q:
        r["turm"] = ""
        if r["lat"] is not None and r["alt"] >= 380 and dist_m(r["lat"], r["lon"], tlat, tlon) < 40:
            r["turm"] = "gps_exif" if r["gps_quelle"] == "exif" else "gps_zeit"
    tw = sorted(r["t"] for r in q if r["turm"] == "gps_exif")
    # Zeitfenster Turm (GPS-lose Bilder dazwischen)
    for r in q:
        if not r["turm"] and r["lat"] is None and tw and tw[0] <= r["t"] <= tw[-1]:
            r["turm"] = "nur_zeitfenster"
    # ---- Dubletten
    mv = {}
    for r in vorh: mv.setdefault(r["md5"], []).append(f'{r["ordner"]}/{r["name"]}')
    vu = list({r["md5"]: r for r in vorh}.values())
    for r in q:
        r["dub_md5_vorhanden"] = ";".join(mv.get(r["md5"], []))
        best = (99, 99, "")
        for v in vu:
            d1 = ham(r["phash"], v["phash"]); d2 = ham(r["dhash"], v["dhash"])
            if d1 + d2 < best[0] + best[1]: best = (d1, d2, f'{v["ordner"]}/{v["name"]}')
        r["nahdub_vorhanden"] = best[2] if (best[0] <= 6 and best[1] <= 10 and r["md5"] not in mv) else ""
        r["ph_dist_vorh"] = best[0]
    qs = sorted(q, key=lambda r: r["t"] or 0)
    grp = {}
    for i, r in enumerate(qs):
        r["nahdub_quelle"] = ""
        for s in qs[max(0, i - 15):i]:
            if ham(r["phash"], s["phash"]) <= 5 and ham(r["dhash"], s["dhash"]) <= 8 and abs(r["t"] - s["t"]) < 120:
                r["nahdub_quelle"] = s["name"]; break
    # ---- Schaerfe
    k90 = np.array([r["lap_k90"] for r in q])
    for r in q:
        r["scharf"] = "ok"
        if r["lap_k90"] < 250: r["scharf"] = "verwackelt_verdacht"
        elif r["lap_k90"] < 600: r["scharf"] = "weich"
        if r["belichtung_s"] and r["belichtung_s"] >= 0.04 and r["lap_k90"] < 800: r["scharf"] = "verwackelt_verdacht"
    # ---- Abgleich
    pools = ab["pools"]; key2r = {r["key"]: r for r in inv + json.load(open(AUS + "/inventar_ref.json"))}
    kh_pool = set(pools.get("kaufhaus_handy", [])) ; khw = set(pools.get("kaufhaus_web", [])); mw = set(pools.get("martinstor_web", []))
    best = collections.defaultdict(lambda: {"kaufhaus_handy": (0, ""), "kaufhaus_web": (0, ""), "martinstor_web": (0, "")})
    nb_edges = collections.defaultdict(dict)
    qkey = {r["key"]: r for r in q}
    for a, lst in ab["paare"].items():
        for b, v in lst:
            for nm, pset in (("kaufhaus_handy", kh_pool), ("kaufhaus_web", khw), ("martinstor_web", mw)):
                if b in pset and v > best[a][nm][0]: best[a][nm] = (v, key2r[b]["name"])
            if b in qkey:
                nb_edges[a][b] = v; nb_edges[b][a] = v
            elif False:
                pass
    # Dubletten-Schluessel: md5 -> rep key (gleiche md5 selten)
    for r in q:
        b = best[r["key"]]
        r["m_kaufhaus_handy"] = b["kaufhaus_handy"][0]; r["m_kaufhaus_handy_ref"] = b["kaufhaus_handy"][1]
        r["m_kaufhaus_web"] = b["kaufhaus_web"][0]; r["m_kaufhaus_web_ref"] = b["kaufhaus_web"][1]
        r["m_martinstor_web"] = b["martinstor_web"][0]; r["m_martinstor_web_ref"] = b["martinstor_web"][1]
        # Dublette gegen vorhanden gilt als kaufhaus-bekannt
        r["m_kaufhaus"] = max(r["m_kaufhaus_handy"], r["m_kaufhaus_web"])
    SCHW = 25
    for r in q:
        h = ""
        if r["dub_md5_vorhanden"]: h = "kaufhaus(dublette_vorhanden)"
        elif r["m_kaufhaus"] >= SCHW and r["m_kaufhaus"] > r["m_martinstor_web"]: h = "kaufhaus"
        elif r["m_martinstor_web"] >= SCHW and r["m_martinstor_web"] > r["m_kaufhaus"]: h = "martinstor"
        r["inhalt_hinweis"] = h
    # Nachbar-Propagation (zeitliche Nachbarn mit >=SCHW Inlier)
    for r in q:
        if r["inhalt_hinweis"] == "":
            c = collections.Counter()
            for b, v in nb_edges.get(r["key"], {}).items():
                if v >= SCHW and qkey[b]["inhalt_hinweis"]:
                    c[qkey[b]["inhalt_hinweis"].split("(")[0]] += 1
            if c: r["inhalt_hinweis"] = c.most_common(1)[0][0] + "(nachbar)"
    # ---- Segmentierung
    for r in q:
        s = seg.get(r["md5"], {})
        r["seg_himmel"] = s.get("sky", 0.0); r["seg_himmel_oben"] = s.get("_sky_oben", 0.0)
        r["seg_gebaeude"] = round(sum(s.get(k, 0) for k in ("building", "house", "wall", "skyscraper")), 3)
        r["seg_natur"] = round(sum(s.get(k, 0) for k in ("tree", "plant", "grass", "palm")), 3)
        r["seg_strasse"] = round(sum(s.get(k, 0) for k in ("road", "sidewalk", "floor", "path", "earth")), 3)
        r["seg_person_auto"] = round(sum(s.get(k, 0) for k in ("person", "car", "bus", "truck")), 3)
    # ---- Entfernungen
    for r in q:
        for o, (la, lo) in ref.items():
            r["dist_" + o] = round(dist_m(r["lat"], r["lon"], la, lo), 1) if r["lat"] is not None else None
    # Ordner-Plausibilitaet
    for r in q:
        o = r["ordner"]; pl = ""
        if r["turm"]:
            pl = "turmblick_position_unabhaengig"
        elif o == "kaufhaus" and r["dist_kaufhaus"] is not None:
            pl = "ok_nah" if r["dist_kaufhaus"] <= 110 else "ZWEIFEL_weit_vom_Kaufhaus"
        elif o == "martinstor" and r.get("dist_martinstor") is not None:
            pl = "ok_nah" if r["dist_martinstor"] <= 120 else "ZWEIFEL_weit_vom_Martinstor"
        elif o == "schwabentor" and r["lat"] is not None:
            pl = "kein_Referenzpunkt_im_Repo"
        r["ordner_gps_pruefung"] = pl
        ih = r["inhalt_hinweis"].split("(")[0]
        fl = ""
        if ih == "kaufhaus" and o != "kaufhaus": fl = "KAUFHAUS_IN_ANDEREM_ORDNER"
        elif ih == "martinstor" and o != "martinstor": fl = "MARTINSTOR_IN_ANDEREM_ORDNER"
        elif o == "kaufhaus" and ih == "martinstor": fl = "MARTINSTOR_IM_KAUFHAUS_ORDNER"
        r["falsch_einsortiert_hinweis"] = fl
    json.dump(q, open(AUS + "/zwischen.json", "w"))
    return q

if __name__ == "__main__":
    main()
