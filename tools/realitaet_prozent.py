#!/usr/bin/env python3
"""realitaet_prozent.py - EINE Prozentzahl "wie nah ist das Modell an der Realitaet" fuer den aktuellen main-Stand (Nutzerwunsch 10.11.:
"nach jedem neuen Ergebnis eine Prozentzahl"). Wird am Ende von tools/main_abnahme.sh aufgerufen (nach jeder GRUENEN main-Abnahme).

Hauptzahl = Mittel des Wolkenbelegs ueber alle Bauteile mit Daten (konvergenz_bericht.py, Abschnitt Wolkenbeleg: Anteil der datennahen,
kamera-zugewandten Teilflaeche, die naeher als --beleg an der Fotowolke liegt). Das ist dieselbe Zahl wie im Konvergenzstand (0,769 am 10.11.).
Daneben (nicht eingerechnet, damit die Hauptzahl vergleichbar bleibt): Fotokanten im Modell (Kanten-Recall gesamt), Teile >= 0,9, Pruefstand.
Grenzen (ehrlich mitschreiben): Teile ohne Daten (Rueckseite/Hof) zaehlen nicht; der Wolkenbeleg sieht Lage/Masse, nicht Feinform
(Docken, Profile) - die steht in teil_fotoform.

Ablauf: Bauteile des main-Stands exportieren (Generator mit BAUTEILE_AUS, CPU), konvergenz_bericht --trocken --json_aus (GPU, unter
gpu_tor.lock wie ein Kreis-Torschritt), Zeile an modelle/<objekt>/realitaet_verlauf.jsonl anhaengen. Gleicher STL-sha wie die letzte
Zeile -> nur ausgeben (keine Neumessung).
  python3 tools/realitaet_prozent.py <objekt> [--neu]
"""
import sys, os, json, time, hashlib, subprocess, fcntl, tempfile, shutil

a = sys.argv; OBJ = a[1]; NEU = "--neu" in a
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT)
PY = "/media/oem/scan/venv-seg/bin/python"; KD = "/media/oem/scan/rc-park_kreis"; D = "/media/oem/scan/rc-park_daten/kaufhaus_alle"
O = json.load(open(f"modelle/{OBJ}/objekt.json")); K = O.get("kreis") or {}
STL = K.get("stl", f"modelle/stl/{OBJ}_1-87.stl"); SK = K.get("skala", 0.087)
GIT = K.get("gitter", D + "/segmente_gitter_v12.json"); KAM = K.get("kameras", D + "/sfm/kam_lot2.json")
WOLKE = K.get("wolke", "/media/oem/scan/rc-park_null/wolke_gemeinsam/lot2/j_voll_lot2.npy")
VF = f"modelle/{OBJ}/realitaet_verlauf.jsonl"

def zeile_ausgeben(z, vor):
    d = "" if vor is None else f" ({'+' if z['prozent'] >= vor['prozent'] else ''}{z['prozent'] - vor['prozent']:.1f} Punkte gegen {vor['zeit'][11:16]})"
    print(f"REALITAET {z['prozent']:.1f} %{d} | Fotokanten im Modell {z['kanten_recall_prozent']:.1f} % | Teile >= 0,9: {z['teile_gut']}/{z['teile_n']}"
          f" | Pruefstand {z['pruefstand']} | schwaechste: " + ", ".join(f"{t} {b:.2f}" for t, b in z["schwaechste"]), flush=True)

def main():
    sha = hashlib.sha256(open(STL, "rb").read()).hexdigest()[:16]
    alt = [json.loads(l) for l in open(VF) if l.strip()] if os.path.exists(VF) else []
    if alt and alt[-1]["stl_sha"] == sha and not NEU:
        zeile_ausgeben(alt[-1], alt[-2] if len(alt) > 1 else None); return 0
    tmp = tempfile.mkdtemp(prefix="realitaet_", dir="/media/oem/scan/rc-park_kreis")
    ml = None
    if not os.environ.get("REALITAET_MERGE_LOCK_GEHALTEN"):   # main_abnahme.sh haelt merge.lock schon (zweites flock = Verklemmung)
        ml = open(os.path.join(KD, OBJ, "merge.lock"), "a"); fcntl.flock(ml, fcntl.LOCK_EX)   # kein Spur-Merge waehrend des Exports
    try:
        tdir = os.path.join(tmp, "teile"); os.makedirs(tdir)
        r = subprocess.run(O["generator"], shell=True, cwd=ROOT, env=dict(os.environ, BAUTEILE_AUS=tdir), capture_output=True, text=True)
        if r.returncode != 0: print("Export fehlgeschlagen:", r.stderr[-800:]); return 1
        if hashlib.sha256(open(STL, "rb").read()).hexdigest()[:16] != sha: print("STL hat sich beim Export geaendert - abgebrochen"); return 1
        js = os.path.join(tmp, "zeile.json")
        cmd = [PY, "-W", "ignore", "-I", "tools/konvergenz_bericht.py", OBJ, "--stl", STL, "--skala", str(SK), "--gitter", GIT, "--wolke", WOLKE,
               "--teile_dir", tdir, "--kameras", KAM, "--etikett", "realitaet main", "--trocken", "--json_aus", js]
        for v in range(6):   # wie sh_tor: unter der Torsperre, CUDA-OOM = Infrastruktur -> warten und wiederholen
            with open(os.path.join(KD, "gpu_tor.lock"), "a") as lk:
                fcntl.flock(lk, fcntl.LOCK_EX); r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
            if "out of memory" not in (r.stdout + r.stderr).lower(): break
            print(f"OOM in konvergenz_bericht (Versuch {v + 1}/6), warte", flush=True); time.sleep(120)
        if not os.path.exists(js): print("konvergenz_bericht ohne Ergebnis:", (r.stdout + r.stderr)[-800:]); return 1
        k = json.load(open(js))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        if ml: ml.close()
    tl = [t for t in k.get("wolkenbeleg_teile") or [] if t.get("beleg") is not None]
    if not tl: print("keine Bauteile mit Daten"); return 1
    ps = k.get("pruefstand") or {}
    z = dict(zeit=time.strftime("%Y-%m-%d %H:%M:%S"), git=subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip(),
             stl_sha=sha, prozent=round(100 * sum(t["beleg"] for t in tl) / len(tl), 1),
             kanten_recall_prozent=round(100 * k["kanten"]["gesamt"]["recall"], 1), teile_n=len(tl), teile_gut=sum(t["beleg"] >= 0.9 for t in tl),
             pruefstand=f"{ps.get('ok')}/{ps.get('n')}", schwaechste=[[t["teil"], t["beleg"]] for t in sorted(tl, key=lambda t: t["beleg"])[:4]],
             teile={t["teil"]: t["beleg"] for t in tl}, masz="Mittel Wolkenbeleg je Bauteil (konvergenz_bericht, beleg 0,15 m, Sicht >= 3 Kameras)")
    with open(VF, "a") as f: f.write(json.dumps(z, ensure_ascii=False) + "\n")
    zeile_ausgeben(z, alt[-1] if alt else None); return 0

if __name__ == "__main__":
    sys.exit(main())
