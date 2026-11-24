#!/usr/bin/env python3
"""wolke_neu_fusionieren.py <objekt.json> <pipe-ordner> [--stufe schnell|fein] - dichte Wolke OHNE die unplausiblen Kameras neu fusionieren.

Warum (Schwabentor 15.11.2026): eine Geisterwand (Haufen auf der Strasse, Grundriss-Tor rc 3) kam aus Bildern eines Videoclips, deren Kameras unter dem
Gelaende standen. tools/kamera_gelaende.py schreibt diese Bilder nach audit/kamera_plausibel.json ('ausschliessen'). Hier: fusion.cfg ohne sie neu
schreiben, stereo_fusion (CPU, Minuten; Tiefenkarten bleiben), alte fused.ply -> fused_alle.ply, dann die VORHANDENE Ausrichtung auf die neue Wolke
anwenden (X_m = R^T (X_sfm - t) / s, keine neue LoD2-Suche) -> sfm/punkte_modell_<name>.npy + punkte_farben_<name>.npy.
  /media/oem/scan/venv-colmap/bin/python -I tools/wolke_neu_fusionieren.py modelle/<obj>/objekt.json /media/oem/scan/rc-park_daten/<obj>/pipe
Danach die Tore wiederholen (gesamtkette.py --ab tore bzw. wolke_grundriss_pruefen.py). rc 2 = nichts zu tun (Wolke entspricht schon der Ausschlussliste), rc 4 = es bliebe kein Bild.

17.11.2026 (Durchsicht), zwei stille Fehler behoben:
  1. Ausschluesse waren DAUERHAFT: 'alle Bilder' wurde aus der schon gekuerzten fusion.cfg gelesen. Ein Bild, das heute in keiner Liste mehr steht (neue Ausrichtung, Kamera nicht mehr
     unter Gelaende), kam nie zurueck - und niemand sah, warum es fehlt. Jetzt: Grundmenge ist immer fusion.cfg.alle; Listen-Ausschluesse (audit/kamera_plausibel.json, kette_insel.json)
     gelten nur, solange das Bild dort steht. Haufenquellen (--haufen) lassen sich an der bereinigten Wolke NICHT neu feststellen - sie werden deshalb ausdruecklich gemerkt:
     <pipe>/dicht/stereo/fusion_ausschluss.json ('haufen'; beim ersten Lauf nach dieser Aenderung zusaetzlich 'uebernommen' = was in fusion.cfg fehlt und in keiner Liste steht).
     Diese Datei loeschen (oder Eintraege streichen) = die Bilder kommen beim naechsten Lauf zurueck.
  2. Ein Absturz der Fusion (Arbeitsspeicher, Zeitlimit) hinterliess einen halben Zustand: fusion.cfg schon gekuerzt, fused.ply schon nach fused_alle.ply verschoben, keine neue Wolke -
     die Korrektur der Ausrichtung und der naechste Pipeline-Lauf fanden keine dichte Wolke. Jetzt: Fusion in fused_neu.ply; erst wenn sie fertig ist und Punkte hat, wird umbenannt;
     scheitert sie, steht fusion.cfg wieder wie vorher. Marke stereo/fusion.cfg.laeuft: liegt sie beim Start noch da (Prozess wurde hart beendet), wird in jedem Fall neu fusioniert.
"""
import sys, os, json, shutil, time, numpy as np


def ply_lesen(p):
    with open(p, "rb") as f:
        kopf = b""
        while not kopf.endswith(b"end_header\n"):
            l = f.readline()
            if not l: raise ValueError(f"{p}: kein vollstaendiger PLY-Kopf (Datei abgeschnitten?)")      # 17.11.2026: an einer abgeschnittenen fused.ply lief diese Schleife endlos (readline liefert am Dateiende b"")
            kopf += l
        n = int([l for l in kopf.decode().splitlines() if l.startswith("element vertex")][0].split()[-1])
        props = [l.split()[1:] for l in kopf.decode().splitlines() if l.startswith("property")]
        dt = np.dtype([(nm, {"float": "<f4", "uchar": "u1", "double": "<f8"}[t]) for t, nm in props]); return np.frombuffer(f.read(n * dt.itemsize), dtype=dt, count=n)


def haufen_quellen(od, D, name, anteil=0.7, min_punkte=3000):
    """Bilder, die einen Strassenhaufen des Grundriss-Tors erzeugen (15.11.2026, schwab_v3: Geisterwand 5442 Punkte, Kameras NICHT unter Gelaende).
    Je Haufen aus audit/wolke_grundriss.json (>= min_punkte): Beobachtungen je Bild aus fused.ply.vis; stammen >= anteil von EINER Quelle
    (Videoclip bzw. Namensteil vor '__'), gilt deren Bildgruppe dort als falsch verortet -> diese Bilder ausschliessen. Echte Bauteile
    (Galerie, Erker) werden von vielen Quellen gesehen und bleiben."""
    import pycolmap, collections
    from scipy.spatial.transform import Rotation as Rot
    gj = os.path.join(od, "audit", "wolke_grundriss.json"); vis = os.path.join(D, "fused.ply.vis"); f = os.path.join(D, "fused.ply")
    if not (os.path.exists(gj) and os.path.exists(vis) and os.path.exists(f)): return set()
    H = [h for h in json.load(open(gj))["strasse"]["haufen"] if h["punkte"] >= min_punkte]
    if not H: return set()
    T = json.load(open(os.path.join(od, "messprotokoll", f"SFM-AUSRICHTUNG-{name}.json")))["transformation"]; s = T["s"]; R = Rot.from_rotvec(T["rvec"]).as_matrix(); t = np.array(T["t"])
    V = ply_lesen(f); P = ((np.c_[V["x"], V["y"], V["z"]].astype(float) - t) / s) @ R
    raw = np.fromfile(vis, dtype=np.uint32); n = int(raw[0]) | (int(raw[1]) << 32)
    if n != len(P): print("Haufenquellen: fused.ply.vis passt nicht zur Wolke"); return set()
    start = np.zeros(n, np.int64); cnt = np.zeros(n, np.int32); p = 2
    for i in range(n): c = raw[p]; cnt[i] = c; start[i] = p + 1; p += 1 + int(c)
    rec = pycolmap.Reconstruction(os.path.join(D, "sparse")); namen = [rec.images[i].name for i in sorted(rec.reg_image_ids())]
    quelle = lambda nm: nm.split("__vf_")[0] if "__vf_" in nm else nm.split("__")[0]; weg = set()
    for h in H:
        m = np.array(h["mitte"], float); r = 0.5 * np.array(h["ausdehnung_m"], float) + 1.0
        idx = np.flatnonzero((np.abs(P[:, 0] - m[0]) < r[0]) & (np.abs(P[:, 1] - m[1]) < r[1]) & (P[:, 2] > 0.7))
        from_lod2 = idx  # Haufenkasten kann Wandpunkte enthalten; der Quellenanteil entscheidet
        z = collections.Counter()
        for j in from_lod2[::max(1, len(from_lod2) // 20000)]:
            for b_ in raw[start[j]:start[j] + cnt[j]]: z[namen[b_]] += 1
        if not z: continue
        q = collections.Counter(); 
        for nm, c in z.items(): q[quelle(nm)] += c
        top, c_top = q.most_common(1)[0]; a_ = c_top / sum(q.values())
        print(f"Haufen bei {h['mitte']} ({h['punkte']} Punkte): groesste Quelle {top[:40]} mit {100 * a_:.0f} % der Beobachtungen")
        if a_ >= anteil and top != "eigen": weg |= {os.path.splitext(nm)[0] for nm, c in z.items() if quelle(nm) == top and c >= 0.01 * c_top}
    if weg: print(f"Haufenquellen: {len(weg)} Bilder ausgeschlossen")
    return weg


def zeilen(p): return [l.strip() for l in open(p) if l.strip()]


def text_atomar(p, text):
    with open(p + ".neu", "w") as f: f.write(text); f.flush(); os.fsync(f.fileno())
    os.replace(p + ".neu", p)


def npy_atomar(p, feld):
    """Verknuepfung (Datenplatte) bleibt erhalten; erst fertig schreiben, dann umbenennen."""
    p = os.path.realpath(p) if os.path.islink(p) else p
    with open(p + ".neu", "wb") as f: np.save(f, feld); f.flush(); os.fsync(f.fileno())
    os.replace(p + ".neu", p)


def ply_punkte(p):
    """Punktzahl aus dem Kopf (0, wenn die Datei fehlt oder kein PLY ist)."""
    try:
        with open(p, "rb") as f:
            for _ in range(40):
                l = f.readline()
                if l.startswith(b"element vertex"): return int(l.split()[-1])
                if not l or l.startswith(b"end_header"): break
    except OSError: pass
    return 0


def _draht_stand(D):
    """Detektorstand der Drahtmaske, mit der jetzt fusioniert wuerde (None = ohne: OHNE_DRAHTMASKE=1 oder keine entzerrten Bilder)."""
    if os.environ.get("OHNE_DRAHTMASKE", "0") == "1" or not os.path.isdir(os.path.join(D, "images")): return None
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import code_stand
    return code_stand.code_stand("drahtmaske.py")


def draht_veraltet(f, D):
    """24.11.2026: fused.ply entstand mit anderem Drahtmasken-Stand (oder ohne) als jetzt -> neu fusionieren (Marke <fused.ply>.drahtmaske.json, wie pipeline_objekt.py)."""
    try: alt = json.load(open(f + ".drahtmaske.json")).get("detektor")
    except Exception: alt = None
    neu = _draht_stand(D)
    if alt != neu: print(f"Drahtmaske: Wolke mit Stand {alt}, jetzt {neu} -> neu fusionieren", flush=True)
    return alt != neu


def draht_marke(f, D):
    s = _draht_stand(D)
    if s is None:                                                          # ohne Maske: keine Marke (fehlende Marke = 'ohne Drahtmaske')
        if os.path.exists(f + ".drahtmaske.json"): os.remove(f + ".drahtmaske.json")
        return
    json.dump(dict(detektor=s, masken=os.path.join(D, "drahtmasken") if s else None), open(f + ".drahtmaske.json", "w"))


def fusionieren(ziel, D, stufe):
    """COLMAP-Fusion (CPU, Minuten) mit der fusion.cfg des Arbeitsordners D nach `ziel` (+ ziel.vis)."""
    import pycolmap
    fo = pycolmap.StereoFusionOptions(); fo.max_image_size = 1600
    if stufe == "schnell": fo.min_num_pixels = 3   # 19.11.2026 gemessen, siehe pipeline_objekt.py
    # 24.11.2026 Drahtmasken wie in pipeline_objekt.py (Oberleitung nicht fusionieren); OHNE_DRAHTMASKE=1 = Stand vorher
    if os.environ.get("OHNE_DRAHTMASKE", "0") != "1" and os.path.isdir(os.path.join(D, "images")):
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import drahtmasken as DMK; dmk = os.path.join(D, "drahtmasken")
        if not DMK.colmap_masken_aktuell(dmk): DMK.masken_ordner(os.path.join(D, "images"), dmk, colmap=True, rand_px=2)
        fo.mask_path = dmk
    # 19.11.2026 (Durchsicht Punkt 38): wie in pipeline_objekt.py - passt die Fusion nicht in 60 % des freien RAM, Teilfusion; sonst OOM-Kill und die Kette lief auf der
    # UNGEFILTERTEN Wolke weiter (alle Dichtlaeufe > ~200 Bilder brauchten die Teilfusion).
    try: frei = int([l for l in open("/proc/meminfo") if l.startswith("MemAvailable")][0].split()[1]) / 1048576
    except Exception: frei = 8.0
    nf = len([l for l in open(os.path.join(D, "stereo", "fusion.cfg")) if l.strip()]); bedarf = nf * 0.045
    print(f"Fusion: {nf} Bilder, Bedarf ~{bedarf:.1f} GB, frei {frei:.1f} GB" + (" -> TEILFUSION" if bedarf > 0.6 * frei else ""), flush=True)
    if bedarf > 0.6 * frei:
        import subprocess
        rc = subprocess.call([sys.executable, "-I", os.path.join(os.path.dirname(os.path.abspath(__file__)), "teilfusion.py"), D, ziel, "--max_image_size", str(fo.max_image_size), "--min_num_pixels", str(fo.min_num_pixels)] + (["--mask_path", fo.mask_path] if fo.mask_path else []) + ["--input_type", "geometric" if stufe == "fein" else "photometric"])
        if rc: raise RuntimeError(f"Teilfusion rc {rc}")
        return
    pycolmap.stereo_fusion(ziel, D, options=fo, input_type="geometric" if stufe == "fein" else "photometric", output_type="ply")


def main():
    from scipy.spatial.transform import Rotation as Rot
    objp, pipe = os.path.abspath(sys.argv[1]), sys.argv[2]; od = os.path.dirname(objp); name = os.path.basename(od)
    stufe = sys.argv[sys.argv.index("--stufe") + 1] if "--stufe" in sys.argv else "schnell"; stamm = lambda b: os.path.splitext(b)[0]
    listen = set(json.load(open(os.path.join(od, "audit", "kamera_plausibel.json")))["ausschliessen"]); D = os.path.join(pipe, "dicht"); cfg = os.path.join(D, "stereo", "fusion.cfg")
    aktiv = zeilen(cfg) if os.path.exists(cfg) else None
    alle = zeilen(cfg + ".alle") if os.path.exists(cfg + ".alle") else (aktiv if aktiv is not None else sorted(os.listdir(os.path.join(D, "images"))))      # Grundmenge = ALLE Bilder, nicht die schon gekuerzte Liste
    if aktiv is None: aktiv = list(alle)
    ki = os.path.join(od, "audit", "kette_insel.json")                    # 15.11.2026: Insel-Ketten (tools/kette_insel_pruefen.py) - Bilder ohne Fremdstuetze, Massstab der Kette nicht belegt
    if os.path.exists(ki): n0 = len(listen); listen |= set(json.load(open(ki))["ausschliessen"]); print(f"Insel-Ketten: {len(listen) - n0} weitere Bilder ausgeschlossen")
    wg = os.path.join(od, "audit", "wolke_gruppen.json")                  # 19.11.2026 (Martinstor): Bildgruppen/Einzelfotos, die Punkte hoch ueber die LoD2-Hoehe setzen (tools/wolke_gruppen_pruefen.py)
    if os.path.exists(wg): n0 = len(listen); listen |= {stamm(b) for b in json.load(open(wg)).get("ausschliessen", [])}; print(f"Wolken-Gruppen-Tor: {len(listen) - n0} weitere Bilder ausgeschlossen")
    aj = os.path.join(D, "stereo", "fusion_ausschluss.json"); gem_neu = not os.path.exists(aj)
    gem = dict(haufen=[], uebernommen=sorted(({stamm(b) for b in alle} - {stamm(b) for b in aktiv}) - listen)) if gem_neu else json.load(open(aj))
    if gem_neu and gem["uebernommen"]: print(f"Ausschluss uebernommen: {len(gem['uebernommen'])} Bilder fehlen in fusion.cfg und stehen heute in keiner Liste (frueherer Listenstand oder Haufenquelle) - bleiben ausgeschlossen, gemerkt in {aj}")
    if "--haufen" in sys.argv: gem["haufen"] = sorted(set(gem.get("haufen", [])) | haufen_quellen(od, D, name))
    aus = listen | set(gem.get("haufen", [])) | set(gem.get("uebernommen", []))
    bleibt = [b for b in alle if stamm(b) not in aus]; zurueck = len({stamm(b) for b in bleibt} - {stamm(b) for b in aktiv})
    print(f"Fusion: {len(alle)} Bilder, {len(alle) - len(bleibt)} ausgeschlossen (Listen: Kameras unter Gelaende/Insel-Ketten; gemerkt: {len(gem.get('haufen', []))} Haufenquelle, {len(gem.get('uebernommen', []))} uebernommen), {len(bleibt)} bleiben"
          + (f"; {zurueck} frueher ausgeschlossene Bilder kommen ZURUECK (stehen in keiner Liste mehr)" if zurueck else ""))
    laeuft = cfg + ".laeuft"; f = os.path.join(D, "fused.ply"); fn = os.path.join(D, "fused_neu.ply")
    merken = lambda: text_atomar(aj, json.dumps(dict(gem, hinweis="tools/wolke_neu_fusionieren.py: gemerkte Ausschluesse (Haufenquellen lassen sich an der bereinigten Wolke nicht neu feststellen). Datei loeschen = Bilder kommen beim naechsten Lauf zurueck."), indent=1, ensure_ascii=False))
    if os.path.exists(laeuft): print(f"ACHTUNG: {laeuft} liegt noch da - ein frueherer Lauf wurde hart beendet; es wird in jedem Fall neu fusioniert")
    elif bleibt == aktiv and ply_punkte(f) > 0 and not draht_veraltet(f, D):
        if gem_neu and os.path.isdir(os.path.dirname(aj)): merken()
        return 2
    if len(bleibt) < 2: print(f"FEHLER: nach dem Ausschluss blieben {len(bleibt)} Bilder - nichts geaendert (Listen pruefen: audit/kamera_plausibel.json, kette_insel.json, {aj})"); return 4
    if not os.path.exists(cfg + ".alle"): text_atomar(cfg + ".alle", "\n".join(alle) + "\n")
    open(laeuft, "w").write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} pid {os.getpid()}\n"); text_atomar(cfg, "\n".join(bleibt) + "\n")
    try:
        for q in (fn, fn + ".vis"):
            if os.path.exists(q): os.remove(q)
        fusionieren(fn, D, stufe); n_neu = ply_punkte(fn)
        if n_neu == 0: raise RuntimeError(f"Fusion lieferte keine Punkte ({fn})")
    except BaseException as e:                                             # auch Strg-C/Zeitlimit (SIGTERM der Kette kommt als SystemExit nur, wenn ein Handler gesetzt ist - sonst hilft die Marke)
        text_atomar(cfg, "\n".join(aktiv) + "\n")
        for q in (fn, fn + ".vis", laeuft):
            if os.path.exists(q): os.remove(q)
        print(f"FEHLER: Fusion gescheitert ({type(e).__name__}: {str(e)[:200]}) - fusion.cfg und fused.ply stehen wie vor dem Lauf", flush=True); raise
    if os.path.exists(f) and not os.path.exists(os.path.join(D, "fused_alle.ply")): shutil.move(f, os.path.join(D, "fused_alle.ply"))
    os.replace(fn, f)
    if os.path.exists(fn + ".vis"): os.replace(fn + ".vis", f + ".vis")
    draht_marke(f, D)
    T = json.load(open(os.path.join(od, "messprotokoll", f"SFM-AUSRICHTUNG-{name}.json")))["transformation"]; s = T["s"]; R = Rot.from_rotvec(T["rvec"]).as_matrix(); t = np.array(T["t"])
    V = ply_lesen(f); X = np.c_[V["x"], V["y"], V["z"]].astype(float); Pm = ((X - t) / s) @ R
    npy_atomar(os.path.join(od, "sfm", f"punkte_modell_{name}.npy"), Pm.astype(np.float32)); npy_atomar(os.path.join(od, "sfm", f"punkte_farben_{name}.npy"), np.c_[V["red"], V["green"], V["blue"]].astype(np.uint8))
    merken(); os.remove(laeuft)
    print(f"neue Wolke: {len(Pm)} Punkte, z p1 {np.percentile(Pm[:, 2], 1):.1f} .. p99 {np.percentile(Pm[:, 2], 99):.1f} m -> sfm/punkte_modell_{name}.npy"); return 0


if __name__ == "__main__":
    sys.exit(main())
