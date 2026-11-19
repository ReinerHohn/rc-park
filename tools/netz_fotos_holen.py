#!/usr/bin/env python3
"""netz_fotos_holen.py <objekt.json> --aus DIR [--tage 7] [--neu] [--max-openverse 300] [--max-commons 250] [--max-hochblick 40] [--bekannt-wurzel DIR ...]

KETTENSTUFE (19.11.2026, Nutzer: "der automatische Bilderholer muss in die Pipeline"): ALLE freien Netzquellen fuer ein Objekt abernten, BEVOR die SfM laeuft.
Bisher holte die Kette am Anfang nur eine Commons-Kategorie (120 Bilder); Openverse/Flickr, Commons-Umkreissuche und Hochblicke kamen erst in der spaeten Stufe
'seiten' (nach Lage-Toren und Fassaden) - scheiterte die Lage an fehlenden Seiten (Martinstor 19.11.: 586 von 833 Kameras in einem Sektor), kam sie nie dran.
Quellen (nur freie Lizenzen, Urheber+Lizenz je Bild in herkunft.json / manifest.json; Mapillary/Google NICHT - modelle/LIZENZ_WERKZEUGE.md):
  openverse   tools/openverse_holen.py   Flickr, Museen u. a. (CC0/PDM/BY/BY-SA)      Suchbegriffe: Name+Stadt, Name, objekt.json bildquellen.commons.suchen
  commons_geo tools/commons_harvest.py   Umkreis 250 m um koordinate_utm + Namenssuche  (Titel frueherer Ernten werden uebersprungen: manifest.json unter --bekannt-wurzel)
  hochblick   tools/online_ansichten_holen.py  Luftbilder/Panoramen/Turmblicke (sehen Seiten ueber Nachbardaecher)
Ob ein Bild das Objekt zeigt, entscheidet NICHT dieses Werkzeug, sondern danach tools/bilder_vorpruefen.py (ALIKED+LightGlue gegen die eigenen Fotos).
ZWISCHENSPEICHER: DIR/netz_stand.json merkt je Quelle Zeitpunkt und Bildzahl; juenger als --tage (7) = nicht noch einmal fragen (--neu erzwingt). Die Werkzeuge selbst
laden bekannte Bilder nicht doppelt. Wikimedia drosselt Serien (4 s bzw. 25 s je Datei) - die Stufe kann 30-60 min dauern, laeuft aber ohne GPU und fast ohne CPU.
rc 0 = gelaufen (auch mit 0 neuen Bildern); rc 2 = keine einzige Quelle erreichbar (kein Netz?) - die Kette rechnet mit dem Bestand weiter und meldet es."""
import sys, os, json, glob, time, argparse, subprocess

T = os.path.dirname(os.path.abspath(__file__)); BILD = (".jpg", ".jpeg", ".png", ".webp")


def n_bilder(d):
    return sum(1 for dp, _, fn in os.walk(d) for f in fn if f.lower().endswith(BILD)) if os.path.isdir(d) else 0


def suchbegriffe(obj):
    """(begriffe, stadt): Name+Stadt zuerst, dann Name, dann die gepflegten Suchen aus objekt.json; ohne Doppelte."""
    name = (obj.get("name") or "").strip(); stadt = (obj.get("ort") or "").split(",")[0].strip()
    roh = [f"{name} {stadt}".strip(), name] + list(((obj.get("bildquellen") or {}).get("commons") or {}).get("suchen") or [])
    aus = []
    for b in roh:
        if b and b.lower() not in [x.lower() for x in aus]: aus.append(b)
    return aus, stadt


def geo(obj):
    k = obj.get("koordinate_utm") or (obj.get("rahmen") or {}).get("mitte_utm")
    if not k: return None
    sys.path.insert(0, T); from seiten_luecken import utm32_nach_geo
    return utm32_nach_geo(float(k[0]), float(k[1]))


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--aus", required=True); ap.add_argument("--tage", type=float, default=7.0); ap.add_argument("--neu", action="store_true")
    ap.add_argument("--max-openverse", type=int, default=300); ap.add_argument("--max-commons", type=int, default=250); ap.add_argument("--max-hochblick", type=int, default=40)
    ap.add_argument("--bekannt-wurzel", nargs="*", default=[], help="Ordner, unter denen manifest.json/herkunft.json frueherer Ernten liegen (nicht doppelt laden)")
    ap.add_argument("--nur", default="", help="Komma-Liste openverse,commons_geo,hochblick"); ap.add_argument("--trocken", action="store_true", help="nur Befehle zeigen")
    a = ap.parse_args(argv); obj = json.load(open(a.objekt)); os.makedirs(a.aus, exist_ok=True); sp = os.path.join(a.aus, "netz_stand.json")
    stand = json.load(open(sp)) if os.path.isfile(sp) else {}; begriffe, stadt = suchbegriffe(obj); ll = geo(obj); py = sys.executable
    if not begriffe: print("FEHLER: objekt.json ohne 'name' - keine Suchbegriffe"); return 2
    man, her = [], []
    for w in a.bekannt_wurzel + [a.aus]:
        for t in range(1, 5):
            man += glob.glob(os.path.join(w, *["*"] * (t - 1), "manifest.json")); her += glob.glob(os.path.join(w, *["*"] * (t - 1), "herkunft.json"))
    man = sorted(set(m for m in man if "video_frames" not in m)); her = sorted(set(her))
    Q = dict(
        openverse=["python3", os.path.join(T, "openverse_holen.py"), "--aus", os.path.join(a.aus, "openverse"), "--suche"] + begriffe + ([f"{stadt} Altstadt Blick"] if stadt else [])
                  + ["--max", str(a.max_openverse)] + (["--bekannt"] + her if her else []),
        commons_geo=([py, os.path.join(T, "commons_harvest.py")] + (["--lat", f"{ll[0]:.6f}", "--lon", f"{ll[1]:.6f}", "--radius", "250"] if ll else [])
                     + ["--search", begriffe[0], "--max", str(a.max_commons), "--pause", "4", "--width", "1920", "--out", os.path.join(a.aus, "commons_geo")] + (["--skip-manifest"] + man if man else [])),
        hochblick=["python3", os.path.join(T, "online_ansichten_holen.py"), "--aus", os.path.join(a.aus, "hochblick"), "--suche", begriffe[0]] + ([f"{stadt} Luftbild", f"{stadt} Panorama"] if stadt else [])
                  + ["--max", str(a.max_hochblick)])
    nur = [x for x in a.nur.split(",") if x] or list(Q); erreicht = 0; neu_gesamt = 0
    if not ll: print("HINWEIS: objekt.json ohne koordinate_utm - Commons nur ueber die Namenssuche, keine Umkreissuche", flush=True)
    for q in nur:
        d = os.path.join(a.aus, q); alt = stand.get(q) or {}; frisch = alt.get("zeit") and time.time() - alt["zeit"] < a.tage * 86400 and alt.get("rc") == 0
        if frisch and not a.neu:
            print(f"{q}: vor {(time.time() - alt['zeit']) / 3600:.1f} h geerntet ({alt.get('bilder', 0)} Bilder) - uebersprungen (--neu erzwingt)", flush=True); erreicht += 1; continue
        print(f"{q}: {' '.join(Q[q])[:300]}", flush=True)
        if a.trocken: continue
        n0 = n_bilder(d); t0 = time.time()
        try: rc = subprocess.run(Q[q], cwd=os.path.dirname(T), timeout=5400).returncode
        except subprocess.TimeoutExpired: rc = 124
        except Exception as e: print(f"  {q}: nicht startbar ({e})", flush=True); rc = 127
        n1 = n_bilder(d); neu_gesamt += n1 - n0
        ok = rc == 0 or n1 > n0 or (q == "commons_geo" and rc == 2 and n1 >= n0)       # commons_harvest rc 2 = 0 Bilder (alles schon bekannt) - kein Netzfehler
        erreicht += bool(ok); stand[q] = dict(zeit=time.time(), datum=time.strftime("%Y-%m-%d %H:%M"), rc=0 if ok else rc, bilder=n1, neu=n1 - n0, sekunden=round(time.time() - t0))
        print(f"  {q}: {n1 - n0} neue Bilder (gesamt {n1}), rc {rc}, {time.time() - t0:.0f} s" + ("" if ok else "  ACHTUNG Quelle nicht erreicht/gescheitert"), flush=True)
        json.dump(stand, open(sp + ".tmp", "w"), indent=1); os.replace(sp + ".tmp", sp)
    if a.trocken: return 0
    print(f"NETZFOTOS: {neu_gesamt} neue Bilder, {n_bilder(a.aus)} im Ordner {a.aus}; {erreicht} von {len(nur)} Quellen erreicht -> tools/bilder_vorpruefen.py entscheidet je Bild", flush=True)
    return 0 if erreicht else 2


if __name__ == "__main__": sys.exit(main())
