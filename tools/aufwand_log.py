#!/usr/bin/env python3
"""aufwand_log.py - Aufwand eines Rechenjobs MITSCHREIBEN, damit spaeter bewertet werden kann, ob er sich gelohnt hat (Nutzerwunsch 3.11.: Sweetspot fuer 'schnell durch die Stadt,
moeglichst viele Modelle in kurzer Zeit').  Reine Messung, keine Eingriffe, laeuft mit nice; keine Zusatzlast ausser einem Probenzug je --intervall Sekunden.

  python3 -I tools/aufwand_log.py messen --name boden-dicht --pid 3593479 --fortschritt "find DIR -type f | wc -l" --gesamt 700 [--intervall 60] [--ausgabe DIR]
        schreibt je Probe eine Zeile in <ausgabe>/<name>.jsonl: Zeit, GPU (Auslastung, Leistung W, Speicher MiB, Takt, Temperatur), CPU-Load, Kern-Prozent des Jobs, RAM, Fortschritt;
        endet, wenn die PID weg ist (Schlusszeile 'ende').  Nutzen wird NICHT hier bestimmt.
  python3 -I tools/aufwand_log.py nutzen --name boden-dicht --text "..." [--metrik k=v ...]     (Nutzen-/Ereigniszeile: Messwerte VOR/NACH, gleiche Schaetzer!)
  python3 -I tools/aufwand_log.py bericht --name boden-dicht                                    (Zusammenfassung: Wanduhr, GPU-Energie, mittlere Auslastung, Kosten je Fortschrittseinheit, Nutzen-Zeilen)

EHRLICH: CPU-Leistung ist nicht lesbar (RAPL ohne Rechte) -> Energie nur GPU (nvidia-smi, gemessen) plus ANNAHME CPU = 45 W + 1,2 W je ausgelastetem Kern (Laptop i7-14700HX, geschaetzt, nicht gemessen).
Bewertungsregel (vorab festgelegt, ANNAHME): ein Job lohnt sich fuer den Sweetspot, wenn sein MESSBARER Nutzen (Gewinn an bestandenen unabhaengigen Pruefungen / neu abgedeckte
Flaeche je Seite / Wegfall einer offenen Beobachtung) pro Wanduhrstunde ueber dem der billigeren Stufen liegt (siehe sweetspot.json, treppe.py) - nicht 'er hat etwas geliefert'.
"""
import sys, os, json, time, subprocess, argparse

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def sh(c):
    try: return subprocess.run(c, shell=True, capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception: return ""

def gpu():
    r = sh("nvidia-smi --query-gpu=utilization.gpu,power.draw,memory.used,clocks.sm,temperature.gpu --format=csv,noheader,nounits").split(",")
    try: return dict(auslastung=float(r[0]), watt=float(r[1]), mib=float(r[2]), mhz=float(r[3]), grad=float(r[4]))
    except Exception: return {}

def probe(pid, fort):
    mem = {l.split(":")[0]: int(l.split()[1]) for l in open("/proc/meminfo") if l.split(":")[0] in ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree")}
    d = dict(t=time.strftime("%F %T"), ts=round(time.time(), 1), gpu=gpu(), load1=float(open("/proc/loadavg").read().split()[0]),
             ram_frei_gb=round(mem["MemAvailable"] / 1048576, 2), swap_benutzt_gb=round((mem["SwapTotal"] - mem["SwapFree"]) / 1048576, 2),
             job_cpu_prozent=float(sh(f"ps -o pcpu= -p {pid}") or 0), job_ram_gb=round(float(sh(f"ps -o rss= -p {pid}") or 0) / 1048576, 2))
    if fort:
        v = sh(fort)
        try: d["fortschritt"] = float(v.split()[0])
        except Exception: pass
    return d

def lade(p): return [json.loads(z) for z in open(p) if z.strip()] if os.path.exists(p) else []

def pfad(a):
    od = a.ausgabe or os.path.join(REPO, "modelle", "aufwand"); os.makedirs(od, exist_ok=True); return os.path.join(od, a.name + ".jsonl")

def messen(a):
    p = pfad(a); f = open(p, "a"); f.write(json.dumps(dict(art="start", t=time.strftime("%F %T"), ts=round(time.time(), 1), pid=a.pid, name=a.name, gesamt=a.gesamt, fortschritt_kommando=a.fortschritt, intervall=a.intervall, host=os.uname().nodename)) + "\n"); f.flush()
    while os.path.exists(f"/proc/{a.pid}"):
        f.write(json.dumps(dict(art="probe", **probe(a.pid, a.fortschritt))) + "\n"); f.flush(); time.sleep(a.intervall)
    f.write(json.dumps(dict(art="ende", t=time.strftime("%F %T"), ts=round(time.time(), 1), **{k: v for k, v in probe(a.pid, a.fortschritt).items() if k == "fortschritt"})) + "\n"); f.close()

def nutzen(a):
    z = dict(art="nutzen", t=time.strftime("%F %T"), ts=round(time.time(), 1), text=a.text, metrik=dict(x.split("=", 1) for x in a.metrik))
    open(pfad(a), "a").write(json.dumps(z, ensure_ascii=False) + "\n"); print("Nutzenzeile geschrieben:", pfad(a))

def bericht(a):
    Z = lade(pfad(a)); P = [z for z in Z if z["art"] == "probe"]; st = next((z for z in Z if z["art"] == "start"), None); en = next((z for z in Z if z["art"] == "ende"), None)
    if not P or not st: sys.exit("keine Proben")
    t0 = st["ts"]; t1 = (en or P[-1])["ts"]; dt = t1 - t0
    def mittel(f): v = [f(p) for p in P if f(p) is not None]; return sum(v) / len(v) if v else float("nan")
    gw = mittel(lambda p: p.get("gpu", {}).get("watt")); ga = mittel(lambda p: p.get("gpu", {}).get("auslastung")); ld = mittel(lambda p: p["load1"])
    kern = mittel(lambda p: p["load1"]); cpu_w = 45 + 1.2 * kern; e_gpu = gw * dt / 3.6e6; e_cpu = cpu_w * dt / 3.6e6
    fo = [(p["ts"], p["fortschritt"]) for p in P if "fortschritt" in p]
    print(f"== Aufwand {a.name} ==\nWanduhr {dt / 60:.0f} min ({'beendet' if en else 'laeuft noch'}), Proben {len(P)}\n"
          f"GPU: mittlere Auslastung {ga:.0f} %, mittlere Leistung {gw:.0f} W (Maximum {max(p.get('gpu', {}).get('watt', 0) for p in P):.0f} W), Speicher max {max(p.get('gpu', {}).get('mib', 0) for p in P):.0f} MiB -> Energie {e_gpu:.3f} kWh (gemessen)\n"
          f"CPU: mittlere Last {ld:.1f} (Kerne), Energie ca. {e_cpu:.3f} kWh (ANNAHME 45 W + 1,2 W je Kern, nicht gemessen); RAM frei min {min(p['ram_frei_gb'] for p in P):.1f} GB, Swap max {max(p['swap_benutzt_gb'] for p in P):.1f} GB")
    if len(fo) >= 2 and fo[-1][1] > fo[0][1]:
        r = (fo[-1][1] - fo[0][1]) / ((fo[-1][0] - fo[0][0]) / 60); ges = st.get("gesamt")
        print(f"Fortschritt {fo[0][1]:.0f} -> {fo[-1][1]:.0f}" + (f" von {ges}" if ges else "") + f": {r:.1f} je min" + (f", Rest {(ges - fo[-1][1]) / r:.0f} min" if ges else ""))
    for z in Z:
        if z["art"] == "nutzen": print(f"NUTZEN {z['t']}: {z['text']}  {z['metrik'] or ''}")
    print("Nutzen/Aufwand bewerten: nur mit Nutzenzeilen (VOR/NACH, gleicher Schaetzer) und gegen billigere Stufen (Regel im Kopf dieser Datei).")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("modus", choices=["messen", "nutzen", "bericht"]); ap.add_argument("--name", required=True); ap.add_argument("--ausgabe")
    ap.add_argument("--pid", type=int); ap.add_argument("--fortschritt"); ap.add_argument("--gesamt", type=float); ap.add_argument("--intervall", type=float, default=60.0); ap.add_argument("--text"); ap.add_argument("--metrik", nargs="*", default=[])
    a = ap.parse_args()
    if a.modus == "messen":
        if not a.pid: sys.exit("--pid fehlt")
        messen(a)
    elif a.modus == "nutzen":
        if not a.text: sys.exit("--text fehlt")
        nutzen(a)
    else: bericht(a)

if __name__ == "__main__":
    main()
