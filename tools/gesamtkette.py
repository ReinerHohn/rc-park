#!/usr/bin/env python3
"""gesamtkette.py - EINE Kette von den Bildquellen bis zur 3D-Seite, fuer jedes Objekt, mit Toren und Korrekturkreislauf.
Lehre Schwabentor 2026-11-14: Bausteine waren allgemein, die Kette nicht (Quellen von Hand, Clipwahl von Hand, Tore nur im Nullstart,
Lagefehler von Hand korrigiert). Nutzer: "bau die Gesamtkette und beweise es".

  /media/oem/scan/venv-seg/bin/python -I tools/gesamtkette.py <quelle_objekt> --ziel <neuer_name> [--ab stufe] [--bis stufe]
        [--fremd ORDNER ...] [--commons-kategorie "Category:..."] [--ohne-video] [--referenz-wolke npy] [--max-loesung 3]
Stufen (Bericht: /media/oem/scan/rc-park_daten/<ziel>/gesamtkette_bericht.json; jede Stufe ok/fehler/uebersprungen mit Grund):
  anlegen    modelle/<ziel>/objekt.json aus der Quelle (name, ort, lod2, rahmen, fotos_dir, ...) + Generator-Vorlage (LoD2+Dach);
             fehlen lod2/rahmen: tools/rahmen_aus_lod2.py (Gebaeude per GML-Namensattribut, Rahmen aus Grundriss, Gelaende DGM1)
  commons    optional: tools/commons_harvest.py --category (frei lizenziert) -> Fremdordner
  video      tools/video_suchen.py (GPU) -> tools/clips_waehlen.py (Regeln statt Sichtpruefung) -> tools/video_frames.py
  vorpruefen tools/bilder_vorpruefen.py (GPU, Videokette) gegen fotos_dir (vertrauenswuerdige Bilder)
  sammeln    tools/fotos_sammeln.py (Dubletten, Quelle im Namen)
  sfm        tools/pipeline_objekt.py fein (SfM mit Paarliste, Bildwahl, Tiefenkarten GPU, LoD2-Abgleich)
  tore       kamera_abdeckung, lage_gps_pruefen, wolke_grundriss_pruefen; KORREKTUR: faellt GPS (rc 3) oder Grundriss A (rc 3) durch,
             sfm_lod2_ausrichten --loesung 1..max probieren, die erste Loesung, die ALLE Tore besteht, gilt; sonst Abbruch mit Bericht
  dach       tools/dach_vermessen.py (DOM1, mit Wolke)
  bauen      tools/bauen_abnehmen.sh <ziel> (Generator aus Vorlage = LoD2 + Dach)
  kanten     KERNMETHODE (15.11.): tools/kantenstufe.py - SfM-Kameras -> Stabilkarten -> Kanten-Tiefen-Sweep um die Modellflaeche -> 3D-Kanten-F1 + Liste fehlender Kanten
  fototor    tools/kameras_aus_buendel.py (K-<foto>.json) -> tools/foto_diff.py auf den Fotos mit bester Modellsicht (Foto-Tor)
  html       tools/modell_3d_html.py -> <daten>/<ziel>_3d.html
  vergleich  optional --referenz-wolke: Abstand neue Wolke -> bewiesene Wolke (Median, Anteil < 0,5 m) = Konvergenzbeweis
"""
import sys, os, json, glob, shutil, subprocess, time, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = "/media/oem/scan/venv-seg/bin/python"; PYC = "/media/oem/scan/venv-colmap/bin/python"
STUFEN = ["anlegen", "commons", "video", "vorpruefen", "sammeln", "sfm", "tore", "dach", "bauen", "kanten", "fototor", "html", "vergleich"]
UEBERNEHMEN = ["name", "ort", "lod2", "rahmen", "rahmen_wand", "koordinate_utm", "hoehe_m", "fotos_dir", "seiten_konvention", "bildquellen"]


def lauf(B, name, cmd, log, ok=(0,), timeout=None):
    t0 = time.time(); print(f"[{time.strftime('%H:%M:%S')}] {name}: {' '.join(cmd)[:220]}", flush=True)
    with open(log, "a") as L:
        L.write(f"\n=== {name}\n"); L.flush()
        r = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout); L.write(r.stdout)
    e = dict(stufe=name, rc=r.returncode, ok=r.returncode in ok, sekunden=round(time.time() - t0), ende=r.stdout.strip().splitlines()[-3:] if r.stdout.strip() else [])
    B["schritte"].append(e); json.dump(B, open(B["_pfad"], "w"), indent=1, ensure_ascii=False)
    print(f"    rc {r.returncode} ({e['sekunden']} s) {' | '.join(e['ende'])[:300]}", flush=True); return r.returncode, r.stdout


def notiz(B, name, ok, **k):
    B["schritte"].append(dict(stufe=name, ok=ok, **k)); json.dump(B, open(B["_pfad"], "w"), indent=1, ensure_ascii=False); print(f"    {name}: {k}", flush=True)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("quelle"); ap.add_argument("--ziel", required=True)
    ap.add_argument("--ab", default="anlegen", choices=STUFEN); ap.add_argument("--bis", default="vergleich", choices=STUFEN)
    ap.add_argument("--fremd", nargs="*", default=[]); ap.add_argument("--commons-kategorie", default=""); ap.add_argument("--ohne-video", action="store_true")
    ap.add_argument("--dicht-stufe", default="schnell", choices=["grob", "schnell", "fein"], help="schnell = ohne geometrischen PatchMatch-Durchgang (Standard 15.11.2026); fein nur wenn ein Tor zweifelt"); ap.add_argument("--referenz-wolke", default=""); ap.add_argument("--max-loesung", type=int, default=3); ap.add_argument("--fotos", default="", help="fotos_dir ersetzen")
    a = ap.parse_args()
    D = f"/media/oem/scan/rc-park_daten/{a.ziel}"; os.makedirs(D, exist_ok=True); log = os.path.join(D, "gesamtkette.log")
    Z = os.path.join(ROOT, "modelle", a.ziel); ZJ = os.path.join(Z, "objekt.json"); ZR = os.path.relpath(ZJ, ROOT)
    bp = os.path.join(D, "gesamtkette_bericht.json")
    B = json.load(open(bp)) if os.path.exists(bp) and a.ab != "anlegen" else dict(quelle=a.quelle, ziel=a.ziel, start=time.strftime("%Y-%m-%d %H:%M"), schritte=[])
    B["_pfad"] = bp; i0, i1 = STUFEN.index(a.ab), STUFEN.index(a.bis); dran = lambda s: i0 <= STUFEN.index(s) <= i1
    QJ = os.path.join(ROOT, "modelle", a.quelle, "objekt.json")

    if dran("anlegen"):
        if not os.path.exists(ZJ):
            lauf(B, "anlegen", ["python3", "-I", "tools/objekt_anlegen.py", a.ziel], log)
        q = json.load(open(QJ)); z = json.load(open(ZJ))
        for k in UEBERNEHMEN:
            if k in q: z[k] = q[k]
        if a.fotos: z["fotos_dir"] = a.fotos
        z["gesamtkette"] = dict(quelle=a.quelle, hinweis="von tools/gesamtkette.py angelegt; Masse/Pruefungen nur aus Quellen dieser Kette")
        json.dump(z, open(ZJ, "w"), indent=1, ensure_ascii=False)
        if not isinstance(z.get("lod2"), dict) or not z["lod2"].get("id") or "rahmen" not in z:          # von null: Gebaeude per GML-Name, Rahmen aus Grundriss
            lauf(B, "rahmen_aus_lod2", [PY, "-I", "tools/rahmen_aus_lod2.py", ZR, "--schreiben"], log); z = json.load(open(ZJ))
        notiz(B, "anlegen", bool(z.get("lod2", {}).get("id")) and "rahmen" in z, lod2=z.get("lod2", {}).get("id"), fotos_dir=z.get("fotos_dir"))
    obj = json.load(open(ZJ)); fd = obj["fotos_dir"]; fd = fd if os.path.isabs(fd) else os.path.join(ROOT, fd)
    fremd = list(a.fremd); VF = os.path.join(D, "video_frames"); CO = os.path.join(D, "commons")

    kat = a.commons_kategorie or ((obj.get("bildquellen") or {}).get("commons", {}).get("kategorien") or [""])[0]   # objekt.json bildquellen
    if dran("commons") and kat:
        lauf(B, "commons", ["python3", "-I", "tools/commons_harvest.py", "--category", kat, "--max", "120", "--width", "1600", "--out", CO], log)
    bild = lambda d: os.path.isdir(d) and any(f.lower().endswith((".jpg", ".jpeg", ".png")) for f in os.listdir(d))
    if not bild(fd):                                       # Lehre Martinstor 2026-11-14: eigene Fotos verloren (Auslagerungsplatte) -> Commons-Kategorie wird Basis
        if not bild(CO): notiz(B, "basis", False, fehler=f"keine Bilder in fotos_dir {fd} und keine Commons-Ernte (--commons-kategorie)"); return 1
        fd = CO; obj["fotos_dir"] = CO; json.dump(obj, open(ZJ, "w"), indent=1, ensure_ascii=False)
        notiz(B, "basis", True, fotos_dir=CO, hinweis="ANNAHME: Bilder der Commons-Kategorie zeigen das Objekt (Kategorie = Kuratierung); Ausreisser faellt die SfM")
    if os.path.isdir(CO) and CO not in fremd and os.path.realpath(CO) != os.path.realpath(fd): fremd.append(CO)

    if dran("video") and not a.ohne_video:
        VK = os.path.join(D, "video_kand")
        lauf(B, "video_suchen", [PY, "-I", "tools/video_suchen.py", ZR, "--aus", VK, "--suchen", "12"], log)
        lauf(B, "clips_waehlen", ["python3", "-I", "tools/clips_waehlen.py", os.path.join(VK, "video_kandidaten.json"), "--objekt", ZR, "--aus", os.path.join(D, "clips.json")], log)
        for c in json.load(open(os.path.join(D, "clips.json")))["gewaehlt"]:
            if not os.path.isdir(os.path.join(VF, c["id"])):
                lauf(B, f"frames_{c['id']}", ["python3", "tools/video_frames.py", "--url", f"https://www.youtube.com/watch?v={c['id']}", "--out", os.path.join(VF, c["id"]),
                                              "--fps", str(c["fps"]), "--max", str(c["max"]), "--min-sharp", "20"], log)
    if os.path.isdir(VF): fremd.append(VF)

    vp = os.path.join(D, "vorpruefung.json")
    if dran("vorpruefen"):
        if fremd: lauf(B, "vorpruefen", [PY, "-I", "tools/bilder_vorpruefen.py", ZR] + fremd + ["--aus", vp], log)
        else: notiz(B, "vorpruefen", True, uebersprungen="keine Fremdquellen")
    FV = os.path.join(D, "fotos")
    if dran("sammeln"):
        lauf(B, "sammeln", ["python3", "-I", "tools/fotos_sammeln.py", FV, "--eigen", fd] + (["--geprueft", vp] if os.path.exists(vp) else []), log)

    P = os.path.join(D, "pipe")
    if dran("sfm"):
        lauf(B, "sfm", [PY, "-u", "-I", "tools/pipeline_objekt.py", a.ziel, FV, P, "--stufe", a.dicht_stufe], log)
    W = os.path.join(Z, "sfm", f"punkte_modell_{a.ziel}.npy"); AU = os.path.join(Z, "messprotokoll", f"SFM-AUSRICHTUNG-{a.ziel}.json")

    def tore(tag):
        sp = os.path.join(P, "sfm", "sparse", "0"); erg = {}
        if os.path.isdir(sp): erg["kamera"] = lauf(B, f"tor_kamera{tag}", [PY, "-I", "tools/kamera_abdeckung.py", sp], log, ok=(0, 2))[0]
        erg["gps"] = lauf(B, f"tor_gps{tag}", [PY, "-I", "tools/lage_gps_pruefen.py", ZR, os.path.relpath(AU, ROOT), "--fotos", FV], log)[0] if os.path.exists(AU) else None
        erg["grundriss"] = lauf(B, f"tor_grundriss{tag}", [PY, "-I", "tools/wolke_grundriss_pruefen.py", ZR, "--wolke", W], log)[0] if os.path.exists(W) else None
        return erg

    if dran("tore"):
        erg = tore("")
        bestanden = lambda e: e.get("gps") in (0, None) and e.get("grundriss") == 0
        kaputt = lambda e: e.get("gps") in (1, 4) or e.get("grundriss") == 1          # rc 1/4 = Werkzeug abgestuerzt/nicht geprueft (15.11.: CUDA out of memory) - kein Lage-Urteil
        if kaputt(erg): print(f"ABBRUCH: Tor-Werkzeug abgestuerzt/nicht geprueft {erg} (Log ansehen, z. B. GPU-Speicher) - KEIN Lage-Urteil", flush=True); B["lage"] = dict(tore=erg, bestanden=False, fehler="tor_abgestuerzt"); json.dump(B, open(bp, "w"), indent=1, ensure_ascii=False); return 4
        k = 0
        while not bestanden(erg) and k < a.max_loesung:
            k += 1
            rc, out = lauf(B, f"korrektur_loesung{k}", [PY, "-u", "-I", "tools/sfm_lod2_ausrichten.py", ZR, "--kameras", os.path.join(P, "kameras.json"), "--dicht",
                                                        os.path.join(P, "dicht", "fused.ply"), "--name", a.ziel, "--radius", "30", "--schreiben", "--fotos", FV, "--loesung", str(k)], log, ok=(0, 5))
            if rc == 5: break
            if rc != 0: print(f"ABBRUCH: Ausrichtung Loesung {k} abgestuerzt (rc {rc}) - KEIN Lage-Urteil", flush=True); return 4
            erg = tore(f"_l{k}")
            if kaputt(erg): print(f"ABBRUCH: Tor-Werkzeug abgestuerzt {erg} - KEIN Lage-Urteil", flush=True); return 4
        B["lage"] = dict(loesung=k, tore=erg, bestanden=bestanden(erg)); json.dump(B, open(bp, "w"), indent=1, ensure_ascii=False)
        print(f"    LAGE: Loesung {k}, Tore {erg} -> {'BESTANDEN' if bestanden(erg) else 'NICHT bestanden'}", flush=True)
        if not bestanden(erg):
            print("ABBRUCH: keine Lage besteht alle Tore - nicht modellieren (Bericht, audit/lage_gps.json, audit/wolke_grundriss.png)", flush=True); return 3

    if dran("dach"):
        lauf(B, "dach", [PY, "-I", "tools/dach_vermessen.py", ZR] + (["--wolke", W] if os.path.exists(W) else []), log)
    if dran("bauen"):
        lauf(B, "bauen", ["bash", "tools/bauen_abnehmen.sh", a.ziel], log, ok=(0, 1))
    KD = os.path.join(D, "kanten")
    if dran("kanten"):
        if os.path.exists(AU): lauf(B, "kanten", [PY, "-u", "-I", "tools/kantenstufe.py", ZR, "--ausrichtung", AU, "--bilder", FV, "--aus", KD], log, ok=(0, 4))
        else: notiz(B, "kanten", False, fehler=f"keine Ausrichtung {AU}")
    if dran("fototor") and os.path.exists(AU):
        lauf(B, "fototor_kameras", [PYC, "-I", "tools/kameras_aus_buendel.py", ZR, "--ausrichtung", AU], log)
        kw = os.path.join(KD, "kam_wahl.json"); wahl = list(json.load(open(kw)))[:6] if os.path.exists(kw) else []
        for f in wahl: lauf(B, f"fototor_{os.path.splitext(f)[0]}", [PY, "-W", "ignore", "-I", "tools/foto_diff.py", ZR, os.path.splitext(f)[0]], log)
    if dran("html"):
        args = [PY, "-I", "tools/modell_3d_html.py", ZR, os.path.join(D, f"{a.ziel}_3d.html")]
        if os.path.exists(W): args += ["--wolke", W, "--farben", W.replace("punkte_modell_", "punkte_farben_")]
        lauf(B, "html", args, log)
    if dran("vergleich") and a.referenz_wolke and os.path.exists(W):
        import numpy as np
        sys.path.insert(0, os.path.join(ROOT, "tools")); from gpu_knn import min_abstand
        rng = np.random.default_rng(0); N = np.load(W, mmap_mode="r"); R_ = np.load(a.referenz_wolke, mmap_mode="r")
        n = np.asarray(N[rng.choice(len(N), min(200000, len(N)), replace=False)], float); r_ = np.asarray(R_[rng.choice(len(R_), min(400000, len(R_)), replace=False)], float)
        mr = np.median(r_[:, :2], 0); n = n[np.hypot(*(n[:, :2] - mr).T) < 30]; d = min_abstand(n, r_)
        notiz(B, "vergleich", bool(np.median(d) < 0.5), referenz=a.referenz_wolke, punkte=int(len(d)), median_m=round(float(np.median(d)), 3),
              anteil_unter_0_5m=round(float((d < 0.5).mean()), 3), p90_m=round(float(np.percentile(d, 90)), 3))
    try:                                                                   # 15.11. (Nutzer): Warnungen aller Logs des Laufs in den Bericht - nichts ungelesen verwerfen
        sys.path.insert(0, os.path.join(ROOT, "tools")); import log_warnungen as LW
        w = LW.sammeln([log] + sorted(glob.glob(os.path.join(P, "*.log"))) + sorted(glob.glob(os.path.join(P, "sfm", "*.log"))))
        B["warnungen"] = [dict(n=e["n"], text=e["text"][:240], datei=os.path.basename(e["datei"]), zeile=e["zeile"]) for e in w[:40]]; json.dump(B, open(bp, "w"), indent=1, ensure_ascii=False)
        print(f"WARNUNGEN im Lauf: {len(w)} verschiedene (Bericht 'warnungen'); haeufigste: " + " | ".join(f"{e['n']}x {e['text'][:90]}" for e in w[:3]), flush=True)
    except Exception as e: print("Warnungen nicht gesammelt:", type(e).__name__, e, flush=True)
    print("GESAMTKETTE_ENDE", bp, flush=True); return 0


if __name__ == "__main__":
    sys.exit(main())
