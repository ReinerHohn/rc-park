"""gpu_slot.py - gemeinsame GPU-Warteschlange fuer alle schweren GPU-Werkzeuge (rechnerweit, ueber Prozesse und Kreis-Spuren).

Warum (Messung 10.11. mittags, teil_fotoform 2 Fotos, 5 fremde GPU-Jobs im Hintergrund): 1 allein 66-70 s, 2 gleichzeitig 79 s (gut),
3 gleichzeitig 400 s statt 200 s nacheinander (Einbruch: VRAM voll -> Warten/Wiederholen). 8 Spuren mit je bauen_abnehmen (xargs -P 4 Fotodiagnosen)
+ eigenen Agenten-Pruefungen starteten bis zu ~30 GPU-Prozesse. Ergebnis jedes Werkzeugs bleibt gleich, nur die Reihenfolge aendert sich.

Nutzung am Anfang von main():  import gpu_slot; gpu_slot.belegen("teil_fotoform")
  - haelt einen Platz bis Prozessende (atexit + tote PIDs werden freigegeben)
  - Kindprozesse erben RCPARK_GPU_SLOT und belegen nichts zusaetzlich (kein Verklemmen Eltern/Kind)
  - Plaetze: RCPARK_GPU_SLOTS (Vorgabe 2; 10.11. gemessen: 2 gleichzeitig = fast doppelter Durchsatz, 3 = halber Durchsatz, L-KR30), Zulassung zusaetzlich nur bei >= RCPARK_GPU_FREI_MIB freiem VRAM (Vorgabe 1500)
  - RCPARK_GPU_SLOT=aus schaltet die Schlange ab (z. B. fuer Tests)
"""
import os, time, json, fcntl, atexit, subprocess

DIR = os.environ.get("RCPARK_GPU_SLOT_DIR", "/media/oem/scan/rc-park_kreis/gpu_slots")

def _frei_mib():
    try:
        return float(subprocess.run(["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                                    capture_output=True, text=True, timeout=10).stdout.split()[0])
    except Exception:
        return 1e9

def _lebende():
    n = []
    for f in os.listdir(DIR):
        if not f.endswith(".slot"): continue
        pid = f[:-5]
        if pid.isdigit() and os.path.exists(f"/proc/{pid}"): n.append(pid)
        else:
            try: os.remove(os.path.join(DIR, f))
            except OSError: pass
    return n

def belegen(name="", max_warten=7200):
    if os.environ.get("RCPARK_GPU_SLOT"): return   # Elternprozess haelt schon einen Platz / abgeschaltet
    os.makedirs(DIR, exist_ok=True)
    plaetze = int(os.environ.get("RCPARK_GPU_SLOTS", "2")); frei_min = float(os.environ.get("RCPARK_GPU_FREI_MIB", "1500"))
    t0, gemeldet = time.time(), False
    while True:
        with open(os.path.join(DIR, "mutex.lock"), "w") as lk:
            fcntl.flock(lk, fcntl.LOCK_EX)
            belegt = _lebende()
            if len(belegt) < plaetze and (not belegt or _frei_mib() >= frei_min):
                p = os.path.join(DIR, f"{os.getpid()}.slot")
                json.dump({"name": name, "start": time.strftime("%H:%M:%S")}, open(p, "w"))
                os.environ["RCPARK_GPU_SLOT"] = str(os.getpid())
                atexit.register(lambda: os.path.exists(p) and os.remove(p))
                if gemeldet: print(f"[gpu_slot] {name}: Platz nach {time.time() - t0:.0f} s Warten", flush=True)
                return
        if not gemeldet:
            print(f"[gpu_slot] {name}: warte auf GPU-Platz ({len(belegt)}/{plaetze} belegt)", flush=True); gemeldet = True
        if time.time() - t0 > max_warten:
            print(f"[gpu_slot] {name}: nach {max_warten} s ohne Platz - laufe trotzdem", flush=True); return
        time.sleep(3)
