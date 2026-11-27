#!/usr/bin/env python3
"""runpod_dicht.py <paket-ordner> <arbeit> <ergebnis> [--groesse 0] [--window_step 2] [--fusion_groesse auto] [--nur_pruefen]

RECHENKERN der dichten Wolke in EINEM Stueck (ohne Kacheln, ohne Teilfusion) - fuer Runpod (tools/cloud/runpod_dicht.sh), laeuft genauso lokal.
Optionen wie die lokale Stufe 'schnell' von tools/dicht_modell.py (Handy-Teilmodell 27.11.: --ohne-bildwahl --stufe schnell), nur in voller Bildgroesse:
  undistort_images (max_image_size = --groesse, 0 = volle Groesse) -> PatchMatch (GPU, photometrisch, filter, window_step 2, geom_consistency aus)
  -> stereo_fusion (photometric, min_num_pixels 3, ALLE Bilder am Stueck, use_cache aus; Bilder-RAM-Bedarf siehe unten).
FUSIONS-RAM: Bedarf = Bilder x Megapixel(Fusionsgroesse) x --ram_mb_je_mpx (22,5 MB/Mpx = 45 MB je 1600-px-Bild, Messung 18.11.; Mini-Test 27.11. siehe
Doku/projekt/betrieb/cloud-runpod.md). Frei = min(MemAvailable, cgroup-Grenze des Containers) - Runpod zeigt in /proc/meminfo den GANZEN Host.
Passt der Bedarf nicht in --ram_anteil x frei: --fusion_groesse auto verkleinert NUR die Fusion (Tiefenkarten bleiben voll) und protokolliert
"FUSION VERKLEINERT"; --fusion_streng bricht stattdessen ab (rc 6). Grund: use_cache lief am 18.11. 4 h einspurig ohne Ende.
Protokoll: <ergebnis>/protokoll.log (Takt --takt s: Phase, RAM des Prozesses/Spitze, frei, GPU-Last %, VRAM) und <ergebnis>/protokoll.json (Phasenzeiten, Spitzen).
Ergebnis: <ergebnis>/fused.ply (Rahmen = Rahmen des Paket-Sparse, also wie lokal), patch-match.cfg, fusion.cfg. Tiefenkarten bleiben in <arbeit>.
Rueckgabe: 0 ok; 2 Aufruf; 3 Pruefung (CUDA/Bilder/Platz); 4 PatchMatch unvollstaendig; 5 Fusion leer; 6 RAM reicht nicht (--fusion_streng).
Verwandt: tools/cloud/runpod_dicht.sh (Umgebung, Kostenbremse, Packen), tools/cloud/runpod_paket.py (Paket), tools/dicht_modell.py (lokale Stufe), tools/wolke_vereinigen.py (danach lokal).
Vorlaeufer: tools/dicht_modell.py + tools/teilfusion.py / tools/kachelfusion.py - lokal musste die Fusion wegen 15 GB RAM zerlegt werden (Punktverluste an Treppe/Anbau/Steg).
"""
import os, sys, json, glob, time, argparse, threading, subprocess

PHASE = {"name": "start", "t0": time.time()}; SPITZE = {"rss_mb": 0, "gpu_mb": 0, "gpu_last": 0, "rss_je_phase_mb": {}}


def frei_mb():
    """verfuegbarer RAM in MB; beachtet die cgroup-Grenze (Container)."""
    m = {l.split(":")[0]: int(l.split()[1]) for l in open("/proc/meminfo")}; frei = m["MemAvailable"] / 1024
    for grenze, belegt, stat in (("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory.current", "/sys/fs/cgroup/memory.stat"),
                                 ("/sys/fs/cgroup/memory/memory.limit_in_bytes", "/sys/fs/cgroup/memory/memory.usage_in_bytes", "/sys/fs/cgroup/memory/memory.stat")):
        try:
            g = open(grenze).read().strip()
            if g == "max" or int(g) > 1 << 50: continue
            b = int(open(belegt).read()); st = {l.split()[0]: int(l.split()[1]) for l in open(stat)}
            cache = st.get("inactive_file", st.get("total_inactive_file", 0))
            return min(frei, (int(g) - b + cache) / 1048576), int(g) / 1048576
        except Exception: pass
    return frei, m["MemTotal"] / 1024


def rss_mb():
    try:
        s = {l.split(":")[0]: int(l.split()[1]) for l in open("/proc/self/status") if l.startswith(("VmRSS", "VmHWM"))}; return s["VmRSS"] / 1024, s["VmHWM"] / 1024
    except Exception: return 0, 0


def gpu():
    try:
        o = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total,name", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=20).stdout.strip().splitlines()[0]
        u, m, mt, n = [x.strip() for x in o.split(",")]; return int(u), int(m), int(mt), n
    except Exception: return -1, -1, -1, "?"


def waechter(log, takt, stop):
    while not stop.wait(takt):
        r, h = rss_mb(); f, _ = frei_mb(); u, m, _, _ = gpu()
        SPITZE["rss_mb"] = max(SPITZE["rss_mb"], h); SPITZE["gpu_mb"] = max(SPITZE["gpu_mb"], m); SPITZE["gpu_last"] = max(SPITZE["gpu_last"], u)
        jp = SPITZE["rss_je_phase_mb"]; jp[PHASE["name"]] = max(jp.get(PHASE["name"], 0), round(r))
        with open(log, "a") as L: L.write(f"{time.strftime('%F %T')} TAKT phase={PHASE['name']} t={time.time() - PHASE['t0']:.0f}s rss={r:.0f}MB spitze={h:.0f}MB frei={f:.0f}MB gpu={u}% vram={m}MB\n")


def mpx_je_bild(bilder_ordner, namen, groesse):
    from PIL import Image
    s = 0.0
    for n in namen:
        w, h = Image.open(os.path.join(bilder_ordner, n)).size
        f = min(1.0, groesse / max(w, h)) if groesse > 0 else 1.0; s += (w * f) * (h * f) / 1e6
    return s / max(1, len(namen))


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("paket"); ap.add_argument("arbeit"); ap.add_argument("ergebnis")
    ap.add_argument("--groesse", type=int, default=0, help="max_image_size fuer Entzerren+PatchMatch, 0 = volle Bildgroesse (lokal war 1600)")
    ap.add_argument("--window_step", type=int, default=2); ap.add_argument("--min_num_pixels", type=int, default=3); ap.add_argument("--gpu_index", default="0")
    ap.add_argument("--fusion_groesse", default="auto", help="auto = wie PatchMatch, nur bei RAM-Mangel kleiner; Zahl = fest"); ap.add_argument("--fusion_streng", action="store_true")
    ap.add_argument("--ram_mb_je_mpx", type=float, default=22.5); ap.add_argument("--ram_anteil", type=float, default=0.8); ap.add_argument("--takt", type=int, default=30)
    ap.add_argument("--nur_pruefen", action="store_true", help="Dry-Run: CUDA, Bilder, Platz, RAM-Plan; rechnet nichts")
    a = ap.parse_args(argv)
    os.makedirs(a.ergebnis, exist_ok=True); os.makedirs(a.arbeit, exist_ok=True); LOG = os.path.join(a.ergebnis, "protokoll.log"); PJ = os.path.join(a.ergebnis, "protokoll.json")
    prot = {"start": time.strftime("%F %T"), "argumente": vars(a), "phasen": {}}

    def p(*x):
        z = f"{time.strftime('%F %T')} " + " ".join(str(v) for v in x); print(z, flush=True); open(LOG, "a").write(z + "\n")

    def phase(n):
        if PHASE["name"] != "start": prot["phasen"][PHASE["name"]] = round(time.time() - PHASE["t0"], 1)
        PHASE["name"], PHASE["t0"] = n, time.time(); prot["spitzen"] = dict(SPITZE); json.dump(prot, open(PJ, "w"), indent=1); p("PHASE", n)

    import pycolmap
    from PIL import Image
    sparse = os.path.join(a.paket, "sparse"); bilder = os.path.join(a.paket, "bilder")
    u, m, mt, gname = gpu(); f, grenze = frei_mb()
    p(f"pycolmap {pycolmap.__version__} cuda={pycolmap.has_cuda} GPU {gname} {mt} MB, RAM frei {f / 1024:.1f} GB (Grenze {grenze / 1024:.1f} GB), Kerne {os.cpu_count()}")
    prot.update(pycolmap=pycolmap.__version__, gpu=gname, vram_mb=mt, ram_grenze_mb=round(grenze), kerne=os.cpu_count())
    if not pycolmap.has_cuda: p("ABBRUCH: pycolmap ohne CUDA (pip install pycolmap-cuda12==4.2.1)"); return 3
    rec = pycolmap.Reconstruction(sparse); reg = [im for im in rec.images.values() if im.has_pose]; n = len(reg)
    falsch = [im.name for im in reg if not os.path.isfile(os.path.join(bilder, im.name)) or Image.open(os.path.join(bilder, im.name)).size != (rec.cameras[im.camera_id].width, rec.cameras[im.camera_id].height)]
    p(f"Modell: {n} Bilder, {rec.num_points3D()} Punkte; Bild/Kamera passt nicht: {len(falsch)}")
    if falsch: p("ABBRUCH: Bilder passen nicht zum Modell:", falsch[:5]); return 3
    mpx = mpx_je_bild(bilder, [im.name for im in reg], a.groesse)
    platz_gb = n * mpx * 1e6 * (16 + 3) / 1e9 * 1.15; frei_platz = os.statvfs(a.arbeit).f_bavail * os.statvfs(a.arbeit).f_frsize / 1e9
    p(f"PatchMatch-Groesse {a.groesse or 'voll'}: {mpx:.2f} Mpx je Bild; Platzbedarf ~{platz_gb:.0f} GB (Tiefe+Normale+Bild, ANNAHME), frei {frei_platz:.0f} GB in {a.arbeit}")
    if frei_platz < platz_gb: p("ABBRUCH: zu wenig Platz in", a.arbeit); return 3
    fg = a.groesse if a.fusion_groesse == "auto" else int(a.fusion_groesse)
    def bedarf(g): return n * mpx_je_bild(bilder, [im.name for im in reg[:40]], g) * a.ram_mb_je_mpx
    b = bedarf(fg); p(f"Fusion {fg or 'voll'} px: Bedarf ~{b / 1024:.1f} GB (ANNAHME {a.ram_mb_je_mpx} MB/Mpx), erlaubt {a.ram_anteil * f / 1024:.1f} GB")
    if b > a.ram_anteil * f:
        if a.fusion_streng or a.fusion_groesse != "auto": p("ABBRUCH: Fusions-RAM reicht nicht (rc 6)"); return 6
        w0 = max(Image.open(os.path.join(bilder, reg[0].name)).size); g = fg or w0
        while g > 400 and bedarf(g) > a.ram_anteil * f: g = int(g * 0.9)
        p(f"FUSION VERKLEINERT auf {g} px (Bedarf {bedarf(g) / 1024:.1f} GB) - Tiefenkarten bleiben {a.groesse or 'voll'}"); fg = g
    prot.update(bilder=n, mpx_je_bild=round(mpx, 3), fusion_groesse=fg, fusion_bedarf_gb=round(bedarf(fg) / 1024, 1))
    if a.nur_pruefen: phase("dry_run_ok"); json.dump(prot, open(PJ, "w"), indent=1); p("DRY-RUN OK"); return 0
    stop = threading.Event(); threading.Thread(target=waechter, args=(LOG, a.takt, stop), daemon=True).start()
    try:
        phase("entzerren")
        uo = pycolmap.UndistortCameraOptions(); uo.max_image_size = a.groesse if a.groesse > 0 else -1
        if not os.path.isfile(os.path.join(a.arbeit, "sparse", "images.bin")): pycolmap.undistort_images(a.arbeit, sparse, bilder, output_type="COLMAP", undistort_options=uo)
        nb = len(os.listdir(os.path.join(a.arbeit, "images"))); p(f"entzerrt: {nb} Bilder"); w, h = Image.open(glob.glob(os.path.join(a.arbeit, "images", "*"))[0]).size; p(f"Beispielgroesse {w}x{h}")
        phase("patchmatch")
        dm = os.path.join(a.arbeit, "stereo", "depth_maps")
        fertig = len(glob.glob(os.path.join(dm, "*.photometric.bin"))) >= n
        if not fertig:
            po = pycolmap.PatchMatchOptions(); po.max_image_size = a.groesse if a.groesse > 0 else -1; po.gpu_index = a.gpu_index; po.geom_consistency = False; po.filter = True; po.window_step = a.window_step
            p("PatchMatch-Optionen:", po); pycolmap.patch_match_stereo(a.arbeit, options=po)
        k = len(glob.glob(os.path.join(dm, "*.photometric.bin"))); p(f"Tiefenkarten {k}/{n}"); prot["tiefenkarten"] = k
        if k < n: p("ABBRUCH: PatchMatch unvollstaendig"); return 4
        phase("fusion")
        f, _ = frei_mb(); p(f"vor Fusion frei {f / 1024:.1f} GB")
        fo = pycolmap.StereoFusionOptions(); fo.max_image_size = fg if fg > 0 else -1; fo.min_num_pixels = a.min_num_pixels; fo.use_cache = False
        ziel = os.path.join(a.ergebnis, "fused.ply"); pycolmap.stereo_fusion(ziel, a.arbeit, options=fo, input_type="photometric", output_type="ply")
        if not os.path.isfile(ziel) or os.path.getsize(ziel) < 1000: p("ABBRUCH: fused.ply leer"); return 5
        with open(ziel, "rb") as F:
            kopf = F.read(400).decode("latin1"); pkt = int(kopf.split("element vertex ")[1].split()[0])
        for c in ("patch-match.cfg", "fusion.cfg"):
            q = os.path.join(a.arbeit, "stereo", c)
            if os.path.isfile(q): open(os.path.join(a.ergebnis, c), "w").write(open(q).read())
        phase("fertig"); prot.update(punkte=pkt, fused_mb=round(os.path.getsize(ziel) / 1e6, 1), ende=time.strftime("%F %T"))
        p(f"FERTIG {ziel} {pkt} Punkte, {os.path.getsize(ziel) / 1e6:.0f} MB; Phasen {prot['phasen']}; Spitzen {SPITZE}")
        return 0
    finally:
        stop.set(); prot["spitzen"] = dict(SPITZE); r, h = rss_mb(); prot["spitzen"]["rss_mb"] = max(SPITZE["rss_mb"], h); json.dump(prot, open(PJ, "w"), indent=1)


if __name__ == "__main__":
    sys.exit(main())
