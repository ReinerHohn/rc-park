#!/usr/bin/env python3
"""gpu_messen.py - VRAM-Spitzenbedarf eines Befehls messen (nvidia-smi alle 0,5 s, je Prozess).
  python3 tools/gpu_messen.py <log.csv> -- BEFEHL...
Zaehlt nur Compute-Prozesse, die beim Start NICHT schon auf der GPU waren (Fremdlast zaehlt nicht); meldet zusaetzlich die Gesamtbelegung.
Ausgabe (letzte Zeile): MESSUNG rc=<n> dauer=<s> spitze_prozess=<MiB> spitze_gesamt=<MiB> fremd_vorher=<MiB>"""
import subprocess, sys, time, threading

def smi(q):
    try: return subprocess.run(["nvidia-smi", *q, "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10).stdout.strip().splitlines()
    except Exception: return []

def main():
    log = sys.argv[1]; cmd = sys.argv[sys.argv.index("--") + 1:]
    base = {l.split(",")[0].strip() for l in smi(["--query-compute-apps=pid,used_memory"])}
    fremd = int((smi(["--query-gpu=memory.used"]) or ["0"])[0])
    stop = False; pk = [0, 0]
    with open(log, "w") as f:
        f.write("t,gesamt_mib,neu_mib,pids\n")
        def lauf():
            t0 = time.time()
            while not stop:
                g = int((smi(["--query-gpu=memory.used"]) or ["0"])[0]); neu = 0; ps = []
                for l in smi(["--query-compute-apps=pid,used_memory"]):
                    p, m = [x.strip() for x in l.split(",")]
                    if p not in base and m.isdigit(): neu += int(m); ps.append(f"{p}:{m}")
                pk[0] = max(pk[0], neu); pk[1] = max(pk[1], g)
                f.write(f"{time.time()-t0:.1f},{g},{neu},{' '.join(ps)}\n"); f.flush(); time.sleep(0.5)
        th = threading.Thread(target=lauf); th.start(); t0 = time.time()
        rc = subprocess.call(cmd); dt = time.time() - t0; time.sleep(1.0); stop = True; th.join()
    print(f"MESSUNG rc={rc} dauer={dt:.1f} spitze_prozess={pk[0]} spitze_gesamt={pk[1]} fremd_vorher={fremd}")

main()
