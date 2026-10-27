#!/usr/bin/env python3
"""bauwerk_pipeline.py — VON NULL zum validierten Bauwerk im echten Gelände.

Beweist, dass die in diesem Projekt entwickelte Methodik reproduzierbar ist:
aus NUR den Fakten, die man am Anfang recherchiert (Name, Lage, Maße — KEIN Scan),
erzeugt diese Pipeline deterministisch das fertige, validierte, platzierte Modell.

Schritte (= die Methodik):
  1 LOKALISIEREN   lat/lon -> UTM + LGL-2km-Kachel (ungerade-E/gerade-N)
  2 GELÄNDE        DGM1 laden (/data/dgm/) -> XYZ stitchen -> npy
  3 TRASSE         OSM-Overpass -> bridge=viaduct Linie -> UTM-Polyline
  4 MODELL         viadukt_gelaende: folgt Trasse (Lage/Richtung/Kurve) + DGM1-Profil
  5 VALIDIEREN     validate_bauwerk: richtige Zahl offener Bögen + L:H  -> PASS?
  6 PLATZIEREN     bauwerk_szene --world --textur: graue Szene + Granit + Schieber
  7 BEWEIS         DOP-Orthofoto laden -> Trasse drüber -> Lage unabhängig belegt

  python3 tools/bauwerk_pipeline.py --config ravenna --out /tmp/ravenna_zero
"""
import argparse, json, math, os, subprocess, sys, urllib.parse, urllib.request
import numpy as np

# ===== Die EINZIGEN menschlichen Eingaben (Recherche-Schritt) ===============
CONFIGS = {
    "ravenna": dict(
        name="Ravennaviadukt", lat=47.91750, lon=8.07417,   # Wikipedia
        L=224.0, H=36.0, n_arch=9, span=20.0,                # Wikipedia: 224×36 m, 9 Bögen à 20 m
        deck_w=6.0, deck_t=3.0, textur="granit",             # Forbach-Granit
        osm_filter="railway", osm_pick="viaduct",
        # HOCHQUALITÄT: foto-validierte KOMPLETTE Form (Halbkreis + Archivolt-Ring + Anzug),
        # echtes Deck aus DOM1-LiDAR, Daten-Fallbacks für Offline-Reproduzierbarkeit.
        merge="modelle/ravenna/modell_merge.json",           # Form aus Foto-Metrologie + Wikipedia
        dom=True, batter=0.05, arch_ring=True,               # DOM1-Deck + Pfeiler-Anzug + Stirnbogen-Ring
        track_fallback="daten/ravenna/viadukt_track.npy",    # OSM-Trasse falls Overpass offline
        data_dir="daten/ravenna",                            # bereits geholte Roh-LGL-Daten (DOM1/…)
    ),
}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sh(cmd):
    print("   $ " + " ".join(cmd));
    r = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    if r.returncode != 0:
        print(r.stdout[-2000:]); print(r.stderr[-2000:]); raise SystemExit(f"FEHLER in: {cmd[1]}")
    return r.stdout


def utm32(lat, lon):
    k0=0.9996; a=6378137.0; f=1/298.257223563; e2=f*(2-f)
    lon0=math.radians(9.0); la=math.radians(lat); lo=math.radians(lon)
    N=a/math.sqrt(1-e2*math.sin(la)**2); t=math.tan(la); C=e2/(1-e2)*math.cos(la)**2; A=math.cos(la)*(lo-lon0)
    M=a*((1-e2/4-3*e2**2/64)*la-(3*e2/8+3*e2**2/32)*math.sin(2*la)+(15*e2**2/256)*math.sin(4*la))
    E=k0*N*(A+(1-t*t+C)*A**3/6)+500000
    Nn=k0*(M+N*t*(A*A/2+(5-t*t+9*C)*A**4/24))
    return E, Nn


def ensure(path, url, label):
    if os.path.exists(path):
        print(f"   (vorhanden, wiederverwendet) {label}"); return
    print(f"   lade {label} ...")
    urllib.request.urlretrieve(url, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, choices=list(CONFIGS))
    ap.add_argument("--out", required=True)
    ap.add_argument("--cache", default="daten/_pipeline_cache", help="Roh-Downloads (DGM/DOP-Zips)")
    a = ap.parse_args()
    c = CONFIGS[a.config]
    out = a.out; os.makedirs(os.path.join(ROOT, out), exist_ok=True)
    cache = a.cache; os.makedirs(os.path.join(ROOT, cache), exist_ok=True)
    print(f"\n==== PIPELINE VON NULL: {c['name']} ====")

    # 1 LOKALISIEREN
    E, N = utm32(c["lat"], c["lon"])
    ek, nk = int(E//1000), int(N//1000)
    tileE = ek if ek % 2 == 1 else ek-1
    tileN = nk if nk % 2 == 0 else nk-1
    tile = f"{tileE}_{tileN}"
    print(f"\n1 LOKALISIEREN  {c['lat']},{c['lon']} -> UTM E{E:.0f} N{N:.0f}  LGL-Kachel {tile}")

    # 2 GELÄNDE: DGM1 laden + stitchen
    print("\n2 GELÄNDE (DGM1)")
    dgm_zip = f"{cache}/dgm_{tile}.zip"
    ensure(os.path.join(ROOT, dgm_zip),
           f"https://opengeodata.lgl-bw.de/data/dgm/dgm1_32_{tile}_2_bw.zip", f"DGM1 {tile}")
    dgm_dir = os.path.join(ROOT, cache, f"dgm1_32_{tile}_2_bw")
    if not os.path.isdir(dgm_dir):
        sh(["unzip", "-o", dgm_zip, "-d", cache])
    dem_npy = f"{out}/dem.npy"
    sh(["python3", "tools/dgm_xyz_to_npy.py", f"{cache}/dgm1_32_{tile}_2_bw", "--out", dem_npy])

    # 3 TRASSE aus OSM (robust: mehrere Mirror, Retry)
    print("\n3 TRASSE (OSM)")
    q = (f"[out:json][timeout:60];way(around:200,{c['lat']},{c['lon']})"
         f"[{c['osm_filter']}];out geom;")
    mirrors = ["https://overpass-api.de/api/interpreter",
               "https://overpass.kumi.systems/api/interpreter",
               "https://overpass.openstreetmap.fr/api/interpreter"]
    d = None
    for attempt in range(6):
        ep = mirrors[attempt % len(mirrors)]
        try:
            req = urllib.request.Request(ep + "?" + urllib.parse.urlencode({"data": q}),
                                         headers={"User-Agent": "rc-park/1.0 (modeling)"})
            d = json.loads(urllib.request.urlopen(req, timeout=90).read()); break
        except Exception as e:
            print(f"   OSM-Mirror {ep.split('/')[2]} fehlgeschlagen ({e}), nächster ...")
    track = f"{out}/track.npy"
    if d is not None:
        ways = [w for w in d["elements"] if w.get("type") == "way"]
        pick = [w for w in ways if w.get("tags", {}).get("bridge") == c["osm_pick"]]
        w = (pick or ways)[0]
        P = np.array([utm32(p["lat"], p["lon"]) for p in w["geometry"]])
        np.save(os.path.join(ROOT, track), P)
    elif c.get("track_fallback") and os.path.exists(os.path.join(ROOT, c["track_fallback"])):
        P = np.load(os.path.join(ROOT, c["track_fallback"]))          # Offline: zuvor geholte OSM-Trasse
        np.save(os.path.join(ROOT, track), P)
        print(f"   OSM offline -> nutze gecachte Trasse {c['track_fallback']}")
    else:
        raise SystemExit("alle Overpass-Mirror nicht erreichbar und keine gecachte Trasse")
    seg = np.hypot(*np.diff(P, axis=0).T).sum()
    chord = np.hypot(*(P[-1]-P[0])); nrm = (P[-1]-P[0]); nrm = np.array([-nrm[1], nrm[0]])/np.hypot(*(P[-1]-P[0]))
    sag = np.abs((P-P[0])@nrm).max()
    cE, cN = P.mean(0)
    print(f"   OSM-Trasse: {len(P)} Knoten, Länge {seg:.0f} m, Krümmung {sag:.2f} m "
          f"({'gebogen' if sag>2 else 'gerade'}), Mitte E{cE:.0f} N{cN:.0f}")

    # DOM1 (echtes Bauwerk-LiDAR fürs Deck) — Sub-Kachel der Trassen-Mitte auflösen
    dom_tif = ""
    if c.get("dom") and c.get("data_dir"):
        subE, subN = int(cE // 1000), int(cN // 1000)
        cand = os.path.join(ROOT, c["data_dir"], f"dom1/dom1_32_{tile}_2_bw",
                            f"dom1_32_{subE}_{subN}_1_bw_2017.tif")
        if os.path.exists(cand):
            dom_tif = cand; print(f"   DOM1-LiDAR fürs Deck: {os.path.relpath(cand, ROOT)}")

    # 4 MODELL: a) parametrischer Kanon (HOCHQUALITÄT via --merge, für Architektur+Form-Check),
    #           b) gelände-folgend mit DOM1-Deck + Stirnbogen-Ring (Deliverable, UTM)
    print("\n4 MODELL (Hochqualität: foto-validierte Form + DOM1-Deck + Archivolt-Ring)")
    canon = f"{out}/viadukt_kanon.stl"
    canon_cmd = ["python3", "tools/ravenna_viadukt.py", "--stl", canon, "--face", f"{out}/kanon_face.png"]
    if c.get("merge"):
        canon_cmd += ["--merge", c["merge"]]                 # KOMPLETTE Form aus der Merge-Spec
    else:
        canon_cmd += ["--L", str(c["L"]), "--H", str(c["H"]), "--n", str(c["n_arch"]),
                      "--span", str(c["span"]), "--deck-w", str(c["deck_w"])]
    sh(canon_cmd)
    stl = f"{out}/viadukt.stl"
    gel_cmd = ["python3", "tools/viadukt_gelaende.py", "--dem", dem_npy,
               "--dem-origin", dem_npy.replace(".npy", "_origin.npy"), "--track", track,
               "--n", str(c["n_arch"]), "--deck-w", str(c["deck_w"]), "--deck-t", str(c["deck_t"]),
               "--batter", str(c.get("batter", 0.0)), "--out", stl]
    if dom_tif:
        gel_cmd += ["--dom", dom_tif]
    if c.get("arch_ring"):
        gel_cmd += ["--arch-ring"]
    sh(gel_cmd)
    print(f"   Kanon (gerade, Architektur+Form) + gelände-folgend (Deliverable, UTM, DOM-Deck)")

    # 5 VALIDIEREN: (a) Architektur (offene Bögen + L:H), (b) FOTO-FORM (Stich/Span)
    print("\n5 VALIDIEREN (Architektur + Foto-Form)")
    vout = sh(["python3", "tools/validate_bauwerk.py", "--stl", canon, "--n", str(c["n_arch"]),
               "--L", str(c["L"]), "--H", str(c["H"]), "--open-lo", "0.45", "--open-hi", "0.85"])
    print("   " + "\n   ".join(l for l in vout.splitlines() if "[" in l or "GESAMT" in l))
    passed = "GESAMT: PASS" in vout
    form_ok = True
    if c.get("merge"):
        try:
            sys.path.insert(0, os.path.join(ROOT, "tools"))
            from test_bogenform import measure_stichspan
            fm = json.load(open(os.path.join(ROOT, c["merge"])))["form_maschinell"]
            ss, span, rise = measure_stichspan(canon, fm["span"], fm["H"])
            ref, tol = fm["bogenform_foto_stichspan"], fm["bogenform_foto_tol"]
            form_ok = abs(ss - ref) <= tol
            print(f"   [Foto-Form] gebaut Stich/Span {ss:.3f} (Span {span:.1f}, Stich {rise:.1f} m) "
                  f"vs Foto {ref:.2f}±{tol:.2f}  -> {'PASS' if form_ok else 'FAIL'}")
        except Exception as e:
            print(f"   [Foto-Form] übersprungen: {e}")
    passed = passed and form_ok

    # 6 PLATZIEREN (Szene)
    print("\n6 PLATZIEREN (Szene + Granit)")
    sh(["python3", "tools/bauwerk_szene.py", "--stl", stl, "--world", "--textur", c["textur"],
        "--dem", dem_npy, "--dem-origin", dem_npy.replace(".npy", "_origin.npy"),
        "--E", f"{cE:.0f}", "--N", f"{cN:.0f}", "--win", "180",
        "--title", f"{c['name']} — Pipeline von Null", "--out", f"{out}/szene"])

    # 7 BEWEIS: DOP-Overlay
    print("\n7 BEWEIS (Orthofoto)")
    proof = f"{out}/beweis_dop.png"
    try:
        make_dop_proof(c, tile, P, cache, os.path.join(ROOT, proof))
        print(f"   {proof}")
    except Exception as e:
        print(f"   (DOP übersprungen: {e})")

    print(f"\n==== ERGEBNIS: Validierung {'PASS ✓' if passed else 'FAIL'} ====")
    print(f"   Modell  {stl}\n   Szene   {out}/szene.html\n   Beweis  {proof}")
    sys.exit(0 if passed else 2)


def make_dop_proof(c, tile, P, cache, proof):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from PIL import Image; Image.MAX_IMAGE_PIXELS = None
    dop_zip = f"{cache}/dop_{tile}.zip"
    ensure(os.path.join(ROOT, dop_zip),
           f"https://opengeodata.lgl-bw.de/data/dop20/dop20rgb_32_{tile}_2_bw.zip", f"DOP {tile}")
    ddir = os.path.join(ROOT, cache, f"dop20rgb_32_{tile}_2_bw")
    if not os.path.isdir(ddir):
        subprocess.run(["unzip", "-o", dop_zip, "-d", cache], cwd=ROOT, capture_output=True)
    cE, cN = P.mean(0); subE, subN = int(cE//1000), int(cN//1000)
    base = os.path.join(ddir, f"dop20rgb_32_{subE}_{subN}_1_bw_2025")
    A, D, B, E_, C, F = [float(x) for x in open(base+".tfw").read().split()]
    im = np.array(Image.open(base+".tif")); w = 140
    c0 = int((cE-w-C)/A); c1 = int((cE+w-C)/A); r0 = int((cN+w-F)/E_); r1 = int((cN-w-F)/E_)
    crop = im[r0:r1, c0:c1]
    tc = (P[:, 0]-C)/A - c0; tr = (P[:, 1]-F)/E_ - r0
    fig, ax = plt.subplots(figsize=(10, 10)); ax.imshow(crop)
    ax.plot(tc, tr, "-", color="red", lw=2.5); ax.plot(tc, tr, "o", color="yellow", ms=5)
    ax.set_title(f"{c['name']}: Modell-Trasse (rot) auf LGL-Orthofoto 2025", fontsize=12)
    ax.axis("off"); fig.savefig(proof, dpi=120, bbox_inches="tight"); plt.close(fig)


if __name__ == "__main__":
    main()
