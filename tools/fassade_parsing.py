#!/usr/bin/env python3
"""fassade_parsing.py - Fassadenelemente vollautomatisch aus den Einzelfoto-Orthobildern von fassade_ortho.py (Qualitaetsstufe 3, 2026-11-04).

Erkenner: OWLv2 (google/owlv2-base-patch16-ensemble, Apache 2.0, Zero-Shot, kein eigenes Training) mit MEHREREN Begriffen je Klasse
(Probe Foto 018: 'a window' fand die gotischen Fenster nicht, 'a gothic window with tracery' alle 5 -> Ergebnis darf nicht an einem Begriff haengen).
Je Fassade die `--fotos-je` besten Einzelfotos (Zellen x Guete), je Foto Kaesten in Metern (u, z); dann Abstimmung UEBER DIE FOTOS:
ein Element gilt, wenn es in >= `--mind-stimmen` Fotos UND in >= `--anteil` der Fotos, die die Stelle ueberhaupt sehen, gefunden wird
(Passanten/Baeume/Schatten sind in jedem Foto anders). Lage = Median der Kaesten. Danach Reihen/Spalten-Regel: Elemente einer Klasse mit
gleicher Unter-/Oberkante (+-`--reihe-tol`) bekommen die Reihenwerte (Fassadenraster, wie fenster_struktur / Mathias 2016).

S4 (2026-11-05, Spec SPEC_S4): (1) Flaechen werden NICHT mehr nach m2 (Handschwelle 20 m2 schloss Erkerseiten von 1-3 m2 aus), sondern nach Aufloesung geparst:
`--mind-px` Pixel in der kleineren Ortho-Ausdehnung und `--mind-fotos` Fotos mit Guete > 0. (2) OWLv2 sieht nur 960 px (Prozessorgrenze): das Ortho wird in Kacheln
von `--kachel` px mit `--ueberlapp` Ueberlappung erkannt (vorher: ganzes Ortho, auf 960 verkleinert - 2x-Hochskalieren half dabei nicht), Boxen zurueck in Orthokoordinaten, NMS
ueber die Kachelgrenzen; Textembeddings einmal je Lauf, fp16, Kacheln als Batch nach freiem VRAM. (3) Gegenbegriffe (Schild, Lampe, Markise, Wappen ...): liegt eine Box naeher an einem
Gegenbegriff als an jeder Klasse, faellt sie weg. (4) Z-Protokoll je Fassade und Klasse am besten Foto (`--objekt`), Regel 9: das Protokoll ist NICHT die Datei, die der Generator liest.

Ausgabe --aus/elemente.json (je Fassade: Klasse, u0,u1,z0,z1 in m, Stimmen, gesehen, Score) + elemente_<fid>.jpg (Fusionsbild mit Kaesten).
Zaehlung am Foto (Regel 9): die Anzahl kommt aus dem Erkenner auf den Fotos, NICHT aus Dateien des Generators; Protokoll schreibt der Aufrufer.

  HF_HOME=/media/oem/scan/hf_cache /media/oem/scan/venv-seg/bin/python -I tools/fassade_parsing.py --ortho DIR [--aus DIR] [--gpu]
"""
import os, sys, json, math, time, argparse
import numpy as np, cv2

KLASSEN = {
    "fenster": ["a window", "a gothic window with tracery", "a tall window", "a dark window opening", "a shuttered window"],
    "tuer": ["a door", "a doorway"],
    "bogen": ["an arch", "an arcade arch"],
    "figur": ["a statue"],
    "gaube": ["a dormer", "a roof window"],
    "balkon": ["a balcony", "a balustrade"],
    "uhr": ["a clock", "a clock face"],          # 21.11.2026: Turmuhr (Kettenluecke 9) - Zone fuer tools/uhren_wandbild.py, Mass aus dem feinen Wandbild
}
# Gegenbegriffe (aus zier_ausschnitt.GEGEN + S4-Spec): Dinge, die Fensterkasten/Figurkasten vortaeuschen. Eine Box, deren bester Begriff ein Gegenbegriff ist, wird verworfen.
GEGEN = ["a wrought iron sign", "a shop sign", "a lamp", "an awning", "a canopy", "a coat of arms", "a half-timbered wall panel", "a wooden beam", "a carved wooden ornament"]   # 15.11.2026: Fachwerkfelder/Balken/Schnitzfelder wurden am Schwabentor-Nachbarhaus als Fenster gemeldet
MODELL = "google/owlv2-base-patch16-ensemble"


def iou(a, b):
    w = min(a[1], b[1]) - max(a[0], b[0]); h = min(a[3], b[3]) - max(a[2], b[2])
    if w <= 0 or h <= 0: return 0.0
    i = w * h; return i / ((a[1] - a[0]) * (a[3] - a[2]) + (b[1] - b[0]) * (b[3] - b[2]) - i)


def nms(kk, thr=0.5):
    kk = sorted(kk, key=lambda k: -k["score"]); out = []
    for k in kk:
        if all(iou(k["box"], o["box"]) < thr for o in out): out.append(k)
    return out


def kachel_raster(W, H, k, ueber):
    """Kacheln (x0,y0,x1,y1) der Kantenlaenge k mit Ueberlappung `ueber` (Anteil); k <= 0 oder Bild kleiner: ganzes Bild. Letzte Kachel an den Rand gelegt."""
    if k <= 0 or (W <= k and H <= k): return [(0, 0, W, H)]
    schritt = max(1, int(k * (1 - ueber)))
    def achse(L):
        if L <= k: return [(0, L)]
        st = list(range(0, L - k, schritt)) + [L - k]
        return [(a_, a_ + k) for a_ in st]
    return [(x0, y0, x1, y1) for (y0, y1) in achse(H) for (x0, x1) in achse(W)]


def batch_groesse(max_batch=8, gb_je_kachel=1.0):
    """Kacheln je Batch nach freiem Grafikspeicher (ANNAHME 1 GB je 960-px-Kachel in fp16 inkl. Reserve); ohne nvidia-smi/GPU: 1."""
    import subprocess
    try:
        frei = float(subprocess.run(["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout.split()[0]) / 1024 - 0.7
    except Exception: return 1
    return int(max(1, min(max_batch, frei // gb_je_kachel)))


class Erkenner:
    """OWLv2 mit einmal berechneten Textembeddings (Klassen + Gegenbegriffe), fp16 auf der GPU, Kacheln als Batch. detect(rgb_uint8) -> Liste (box_px(x0,y0,x1,y1), score, text_index)."""
    def __init__(self, texte, dev, schwelle, kachel, ueberlapp, hoch):
        import torch
        from transformers import Owlv2Processor, Owlv2ForObjectDetection
        self.t = torch; self.dev = dev; self.schwelle = schwelle; self.kachel = kachel; self.ueberlapp = ueberlapp; self.hoch = hoch
        self.P = Owlv2Processor.from_pretrained(MODELL); self.M = Owlv2ForObjectDetection.from_pretrained(MODELL).eval().to(dev); self.n = len(texte)
        tok = self.P.tokenizer(texte, padding="max_length", max_length=16, truncation=True, return_tensors="pt").to(dev)
        with torch.no_grad():                                                                       # Text einmal je Lauf; Bild nur Platzhalter
            o = self.M.owlv2(input_ids=tok["input_ids"], attention_mask=tok["attention_mask"], pixel_values=torch.zeros(1, 3, 960, 960, device=dev))
        self.q = o.text_embeds.detach(); self.mask = (tok["input_ids"][:, 0] > 0)[None]; self.batch = batch_groesse() if dev == "cuda" else 1
    def detect(self, rgb):
        from PIL import Image
        torch = self.t; H0, W0 = rgb.shape[:2]; s = float(self.hoch) if (self.kachel <= 0 or max(H0, W0) < self.kachel) else 1.0     # hoch nur fuer Orthos kleiner als eine Kachel (S4); kachel 0 = Verhalten vor S4
        if s != 1.0: rgb = cv2.resize(rgb, None, fx=s, fy=s, interpolation=cv2.INTER_LANCZOS4)
        H, W = rgb.shape[:2]; ks = kachel_raster(W, H, self.kachel, self.ueberlapp); out = []
        for i in range(0, len(ks), self.batch):
            kb = ks[i:i + self.batch]; ims = [Image.fromarray(rgb[y0:y1, x0:x1]) for (x0, y0, x1, y1) in kb]
            pv = self.P.image_processor(images=ims, return_tensors="pt")["pixel_values"].to(self.dev)
            with torch.no_grad(), torch.autocast("cuda", dtype=torch.float16, enabled=(self.dev == "cuda")):
                fm = self.M.image_embedder(pixel_values=pv)[0]; B, nh, nw, D = fm.shape; feats = fm.reshape(B, nh * nw, D)
                logits = self.M.class_predictor(feats, self.q.expand(B, -1, -1), self.mask.expand(B, -1))[0]; bx = self.M.box_predictor(feats, fm)
            sc, lab = logits.float().sigmoid().max(-1); bx = bx.float()
            for j, (x0, y0, x1, y1) in enumerate(kb):
                ss = max(x1 - x0, y1 - y0); m = sc[j] > self.schwelle; c = bx[j][m].cpu().numpy() * ss; sj = sc[j][m].cpu().numpy(); lj = lab[j][m].cpu().numpy()
                for (cx, cy, w, h), sv, lv in zip(c, sj, lj):
                    b = np.array([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]); b = np.clip(b, 0, [x1 - x0, y1 - y0, x1 - x0, y1 - y0])
                    # an einer INNEREN Kachelkante abgeschnittene Boxen weg: die Nachbarkachel (Ueberlappung) sieht das Element ganz
                    if (b[0] <= 2 and x0 > 0) or (b[1] <= 2 and y0 > 0) or (b[2] >= x1 - x0 - 2 and x1 < W) or (b[3] >= y1 - y0 - 2 and y1 < H): continue
                    out.append(((b[0] + x0) / s, (b[1] + y0) / s, (b[2] + x0) / s, (b[3] + y0) / s, float(sv), int(lv)))
        return out, len(ks)


def abstimmen(je_foto, masken, r, mind_stimmen=2, anteil=0.4):
    """Abstimmung ueber die Fotos je Klasse: Kaesten (Meter, je Foto nach NMS) per IoU > 0,5 clustern, Stimmen = Fotos mit Treffer, gesehen = Fotos, deren Sichtmaske
    (Raster r, Zelle r['zelle']) den Kasten zu > 70 % abdeckt. Element gilt ab mind_stimmen UND anteil x gesehen. Rueckgabe Liste der Elemente (u0,u1,z0,z1 in m)."""
    z_ = r["zelle"]; elemente = []
    for kl in KLASSEN:
        alle = [dict(k, foto=nr) for nr, L in je_foto.items() for k in L if k["klasse"] == kl]; cl = []
        for k in sorted(alle, key=lambda k: -k["score"]):
            for c in cl:
                if iou(k["box"], c["kern"]) > 0.5 and k["foto"] not in c["fotos"]: c["m"].append(k); c["fotos"].add(k["foto"]); break
            else: cl.append(dict(kern=k["box"], m=[k], fotos={k["foto"]}))
        for c in cl:
            B = np.median(np.array([k["box"] for k in c["m"]]), 0); gesehen = 0
            for nr, mk in masken.items():
                x0, x1 = int((B[0] - r["u0"]) / z_), int(math.ceil((B[1] - r["u0"]) / z_)); y0, y1 = int((r["z1"] - B[3]) / z_), int(math.ceil((r["z1"] - B[2]) / z_))
                sub = mk[max(0, y0):y1, max(0, x0):x1]; gesehen += int(sub.size > 0 and sub.mean() > 0.7)
            st = len(c["fotos"])
            if st >= mind_stimmen and st >= anteil * max(1, gesehen):
                elemente.append(dict(klasse=kl, u0=float(B[0]), u1=float(B[1]), z0=float(B[2]), z1=float(B[3]), stimmen=st, gesehen=gesehen,
                                     score=round(float(np.median([k["score"] for k in c["m"]])), 3), texte=sorted({k["text"] for k in c["m"]})))
    return elemente


def boegen_vereinen(elemente, z_luecke=0.3):
    """Der Erkenner liefert je Bogen oft ZWEI Kaesten (nur Bogenfeld / ganze Oeffnung bis zum Boden) -> eine Oeffnung, Kaempfer = Unterkante des Bogenfelds.
    Zwei Bogenkaesten gehoeren zusammen, wenn sie sich waagerecht zu > 60 % der schmaleren Breite UND senkrecht ueberdecken (Luecke <= z_luecke: Bogenfeld sitzt auf der Oeffnung).
    22.11.2026 (Kettenlauf schwabentor 1122c): vorher nur die waagerechte Bedingung - die linke Rundbogennische in 23 m Hoehe (u -3,07..-0,86) lag ueber dem Tor
    (u -2,48..2,22, z 0..6,8) und wurde mit ihm zu EINEM 'Bogen' z -0,03..25,57 verschmolzen; das linke Fenster verlor seine Zone (rundbogenfenster 1 statt 2).
    Rueckgabe: vereinte Bogen-Elemente (andere Klassen unberuehrt, nicht enthalten)."""
    bo = sorted([e for e in elemente if e["klasse"] == "bogen"], key=lambda e: -(e["z1"] - e["z0"])); gr = []
    for e in bo:
        for g in gr:
            h = g[0]; ue = min(e["u1"], h["u1"]) - max(e["u0"], h["u0"])
            zl = max(e["z0"], min(x["z0"] for x in g)) - min(e["z1"], max(x["z1"] for x in g))          # > 0 = senkrechte Luecke zwischen Kasten und Gruppe
            if ue > 0.6 * min(e["u1"] - e["u0"], h["u1"] - h["u0"]) and zl <= z_luecke: g.append(e); break
        else: gr.append([e])
    neu = []
    for g in gr:
        h = g[0]; kae = max(x["z0"] for x in g); e = dict(h, z0=min(x["z0"] for x in g), z1=max(x["z1"] for x in g), stimmen=max(x["stimmen"] for x in g), teile=len(g))
        e["kaempfer"] = kae if kae > e["z0"] + 0.5 else None; neu.append(e)
    return neu


def felder_zaehlen(e, r, bilder, sw=0.8, abst_m=0.3, rand=0.08):
    """Fensterfelder AM FOTO zaehlen (Regel 9; 2026-11-05: param_suche wollte 4 statt 3, weil Zusatzpfosten auf Masswerkkanten fallen):
    je Einzelfoto-Ortho das Helligkeitsprofil quer durch das mittlere Fensterband, helle Steinpfosten = lokale Maxima > sw Standardabweichungen,
    Mindestabstand abst_m, Rand ausgenommen; Felder = Pfosten + 1; Ergebnis = Median ueber die Fotos (Stimmen = Fotos mit diesem Wert)."""
    z_ = r["zelle"]; x0, x1 = int((e["u0"] - r["u0"]) / z_), int((e["u1"] - r["u0"]) / z_); y0, y1 = int((r["z1"] - e["z1"]) / z_), int((r["z1"] - e["z0"]) / z_); cnt = {}
    for nr, im in bilder.items():
        sub = im[max(0, y0):y1, max(0, x0):x1]
        if sub.size == 0 or (sub.sum(2) == 0).mean() > 0.2: continue
        g = cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY).astype(float); h = g.shape[0]; prof = g[int(h * 0.25):int(h * 0.75)].mean(0); prof = (prof - prof.mean()) / (prof.std() + 1e-6)
        n = len(prof); w = max(2, int(round(abst_m / z_ / 2))); sel = []
        for i in range(2, n - 2):
            if prof[i] > sw and prof[i] == prof[max(0, i - w):i + w + 1].max() and n * rand < i < n * (1 - rand) and (not sel or i - sel[-1] >= 2 * w): sel.append(i)
        cnt[nr] = len(sel) + 1
    if not cnt: return None
    med = int(round(float(np.median(list(cnt.values()))))); return dict(felder=med, stimmen=sum(1 for v in cnt.values() if v == med), fotos=len(cnt), je_foto=cnt)


def z_protokolle(objp, F, fid, elemente, rang, aus_dir, lauf):
    """Z-Protokoll je Fassade und Klasse AM FOTO (Regel 9; Format wie foto_zaehlung.py): Foto = das mit den meisten Ortho-Zellen fuer diese Fassade;
    die Elementmitten (u, z auf der Wandebene) werden mit der K-Datei des Fotos in Originalpixel projiziert und im Foto markiert. 'art' = voll, wenn das Foto
    alle Elemente der Klasse sieht (Stimmen/gesehen), sonst teil. Das Protokoll ist NICHT die Datei, die der Generator liest (elemente.json) - es ist der Nachweis
    der Zaehlung; wer es zum Sollwert machen will, braucht die Pruefstand-Regel CB (Zaehlart, kein Selbstbezug). Rueckgabe: Liste geschriebener Protokoll-IDs."""
    import glob as _g; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import fehlteile_finden as FF; from fassade_ortho import projizieren
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); obj = json.load(open(objp)); mp = aus_dir or os.path.join(os.path.dirname(os.path.abspath(objp)), "messprotokoll"); os.makedirs(mp, exist_ok=True)
    nr = max(F["fotos"], key=lambda k: F["fotos"][k]["zellen"]); K = json.load(open(FF.k_datei(objp, obj, root, nr))); kk = K["kamera"]
    pf = _g.glob(os.path.join(root, obj["fotos_dir"], nr + ".*")) or _g.glob(os.path.join(root, obj["fotos_dir"], nr + "_*")); im = cv2.imread(pf[0]); H, W = im.shape[:2]; R, t, f, _, _ = FF.kamera_laden(K, obj, nr, root, W, H)
    tr = np.asarray(kk.get("rahmen_verschiebung", [0, 0, 0]), float); cx, cy = float(kk.get("cx", W / 2)), float(kk.get("cy", H / 2)); k1 = float(kk.get("k1") or 0.0)
    o, d = np.array(F["o"]), np.array(F["d"]); ids = []
    for kl in KLASSEN:
        L = [e for e in elemente if e["klasse"] == kl]
        if not L: continue
        X = np.array([[o[0] + 0.5 * (e["u0"] + e["u1"]) * d[0], o[1] + 0.5 * (e["u0"] + e["u1"]) * d[1], 0.5 * (e["z0"] + e["z1"])] for e in L])
        px, z = projizieren(X + tr, R, np.asarray(t, float), f, cx, cy, k1); ok = (z > 1) & (px[:, 0] >= 0) & (px[:, 0] < W) & (px[:, 1] >= 0) & (px[:, 1] < H)
        if not ok.any(): continue
        voll = all(e["stimmen"] >= 0.7 * e["gesehen"] for e in L) and ok.all()
        pts = [dict(flaeche=fid, art="voll" if voll else "teil", x=float(p[0]), y=float(p[1])) for p, g in zip(px, ok) if g]
        vor = [json.load(open(q)) for q in _g.glob(os.path.join(mp, "Z-*.json"))]; alt = [v for v in vor if v.get("lauf") == lauf and v.get("fassade") == fid and v.get("klasse") == kl]
        pid = alt[0]["id"] if alt else f"Z-{nr}-{1 + max([int(os.path.basename(q).split('-')[2].split('.')[0]) for q in _g.glob(os.path.join(mp, f'Z-{nr}-*.json'))] or [0]):03d}"
        im2 = im.copy()
        for p in pts:
            c = (int(p["x"]), int(p["y"])); col = (0, 200, 0) if p["art"] == "voll" else (0, 160, 255); cv2.circle(im2, c, 22, col, 4)
        for e, p, g in zip(L, px, ok):
            if g: cv2.putText(im2, f"{kl[:3]}", (int(p[0]) - 20, int(p[1]) - 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 200, 0), 3)
        x0, y0 = int(max(0, min(p["x"] for p in pts) - 250)), int(max(0, min(p["y"] for p in pts) - 250)); x1, y1 = int(min(W, max(p["x"] for p in pts) + 250)), int(min(H, max(p["y"] for p in pts) + 250))
        cv2.imwrite(os.path.join(mp, pid + ".jpg"), im2[y0:y1, x0:x1], [cv2.IMWRITE_JPEG_QUALITY, 90])
        prot = dict(id=pid, typ="zaehlung", foto=nr, datei=os.path.basename(pf[0]), was=f"{kl}: Anzahl je Flaeche {fid} (OWLv2 auf Foto-Ortho, Abstimmung ueber Fotos, automatisch)", wer="fassade_parsing.py (OWLv2, automatisch; KEINE Handzaehlung)",
                    datum=time.strftime("%Y-%m-%d"), punkte=pts, je_flaeche_gezaehlt={fid: dict(art="voll" if voll else "teil", n=len(pts))}, ergebnis=dict(je_flaeche=len(pts) if voll else None, voll_sichtbare_flaechen=int(voll)),
                    bild=pid + ".jpg", ausschnitt=[x0, y0, x1, y1], lauf=lauf, fassade=fid, klasse=kl, zaehlart="automatisch_erkenner",
                    regel="Quelle: Foto (Erkenner auf Foto-Ortho). Nicht die Generatoreingabe (elemente.json); Handzaehlung kann widersprechen -> dann gilt die Handzaehlung.")
        json.dump(prot, open(os.path.join(mp, pid + ".json"), "w"), indent=1, ensure_ascii=False); ids.append(pid)
    return ids


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--ortho", required=True); ap.add_argument("--aus"); ap.add_argument("--gpu", action="store_true")
    ap.add_argument("--fotos-je", type=int, default=10); ap.add_argument("--schwelle", type=float, default=0.15); ap.add_argument("--hoch", type=int, default=2, help="Ortho vor dem Erkenner hochskalieren")
    ap.add_argument("--mind-stimmen", type=int, default=2); ap.add_argument("--anteil", type=float, default=0.4); ap.add_argument("--reihe-tol", type=float, default=0.25)
    ap.add_argument("--mind-flaeche", type=float, default=0.0, help="ALT (m2, Standard aus): war eine Handschwelle (20 m2) und schloss Erkerseiten aus; Ersatz --mind-px/--mind-fotos")
    ap.add_argument("--mind-px", type=int, default=96, help="Flaeche wird geparst, wenn ihr Ortho in der kleineren Ausdehnung mind. so viele Pixel hat (Aufloesung ist die physikalische Grenze des Erkenners; 96 px = Kachelwert/10: ein Fenster ist dann >= ~10 px gross)")
    ap.add_argument("--mind-fotos", type=int, default=3, help="... und mind. so viele Fotos mit Guete > 0 liefert (Abstimmung braucht >= 2 Stimmen, Puffer 1)")
    ap.add_argument("--kachel", type=int, default=960, help="Kachelkante in px (OWLv2-Prozessorgrenze 960); 0 = ganzes Ortho wie vor S4 (Vergleich)")
    ap.add_argument("--ueberlapp", type=float, default=0.25); ap.add_argument("--nms", type=float, default=0.5, help="IoU der NMS ueber Kachelgrenzen")
    ap.add_argument("--ohne-gegen", action="store_true", help="Gegenbegriffe aus (Vergleich)")
    ap.add_argument("--sammel-ab-m", type=float, default=6.0, help="--max-breite-anteil (Sammelkasten ueber mehrere Elemente) gilt nur fuer Flaechen breiter als dies; auf einer 1,5-m-Erkerseite ist ein 0,9-m-Fenster KEIN Sammelkasten (S4)")
    ap.add_argument("--objekt", help="objekt.json: Z-Protokolle (messprotokoll/Z-<foto>-<nr>.json) je Fassade und Klasse am besten Foto schreiben (Regel 9)"); ap.add_argument("--z-aus", help="Ordner fuer die Z-Protokolle statt <objekt>/messprotokoll (Tests)")
    ap.add_argument("--max-breite-anteil", type=float, default=0.45)
    a = ap.parse_args(argv); t0 = time.time(); aus = a.aus or a.ortho; os.makedirs(aus, exist_ok=True)
    import torch
    from transformers import Owlv2Processor, Owlv2ForObjectDetection
    from PIL import Image
    dev = "cuda" if a.gpu and torch.cuda.is_available() else "cpu"; torch.set_num_threads(os.cpu_count() or 8)
    texte = [t for k in KLASSEN for t in KLASSEN[k]]; klasse_von = [k for k in KLASSEN for _ in KLASSEN[k]]
    if not a.ohne_gegen: texte += GEGEN; klasse_von += ["_gegen"] * len(GEGEN)
    ER = Erkenner(texte, dev, a.schwelle, a.kachel, a.ueberlapp, a.hoch); n_gegen = 0; zprot = []
    FA = json.load(open(os.path.join(a.ortho, "fassaden.json"))); erg = dict(modell=MODELL, lizenz="Apache-2.0 (Modellkarte google/owlv2-base-patch16-ensemble)", klassen=KLASSEN, gegenbegriffe=[] if a.ohne_gegen else GEGEN,
                                                                           ortho=os.path.abspath(a.ortho), parameter=vars(a), fassaden={})
    for F in FA["fassaden"]:
        fid = F["id"]; r = F["raster"]; z_ = r["zelle"]
        if F["flaeche_m2"] < a.mind_flaeche or not F.get("fotos"): continue
        px_min = min(F["u"][1] - F["u"][0], F["z"][1] - F["z"][0]) / z_; n_fotos = sum(1 for v in F["fotos"].values() if v["guete_median"] > 0)
        if px_min < a.mind_px or n_fotos < a.mind_fotos:
            print(f"  {fid}: uebersprungen ({px_min:.0f} px < {a.mind_px} oder {n_fotos} Fotos < {a.mind_fotos}; {F['flaeche_m2']} m2)", flush=True); erg.setdefault("uebersprungen", {})[fid] = dict(px=round(px_min), fotos=n_fotos, m2=F["flaeche_m2"]); continue
        ed = os.path.join(a.ortho, f"ortho_{fid}_einzeln")
        if not os.path.isdir(ed): sys.exit(f"{ed} fehlt: fassade_ortho.py mit --einzeln laufen lassen")
        rang = sorted(F["fotos"].items(), key=lambda kv: -kv[1]["zellen"] * kv[1]["guete_median"])[:a.fotos_je]
        breite = r["nu"] * z_; je_foto = {}; masken = {}
        for nr, _ in rang:
            bild = cv2.imread(os.path.join(ed, f"{nr}.png")); masken[nr] = bild.any(2)
            roh, nk = ER.detect(cv2.cvtColor(bild, cv2.COLOR_BGR2RGB)); kk = []
            for x0, y0, x1, y1, sc, l in roh:
                if klasse_von[l] == "_gegen": n_gegen += 1; continue
                x0, y0, x1, y1 = np.clip([x0, y0, x1, y1], 0, [r["nu"], r["nz"], r["nu"], r["nz"]])
                box = (r["u0"] + x0 * z_, r["u0"] + x1 * z_, r["z1"] - y1 * z_, r["z1"] - y0 * z_)          # (u0, u1, z0, z1) in m
                if box[1] - box[0] < 0.3 or box[3] - box[2] < 0.3 or (breite > a.sammel_ab_m and box[1] - box[0] > a.max_breite_anteil * breite): continue
                kk.append(dict(klasse=klasse_von[int(l)], text=texte[int(l)], score=float(sc), box=box))
            je_foto[nr] = [k for kl in KLASSEN for k in nms([k for k in kk if k["klasse"] == kl], a.nms)]
            print(f"  {fid} Foto {nr}: {len(je_foto[nr])} Kaesten, {nk} Kacheln ({time.time() - t0:.0f} s)", flush=True)
        # Abstimmung ueber die Fotos (je Klasse): Cluster per IoU, Stimmen = Fotos mit Treffer, gesehen = Fotos mit >= 70 % Abdeckung im Kasten
        elemente = abstimmen(je_foto, masken, r, a.mind_stimmen, a.anteil)
        # verschachtelte Kaesten gleicher Klasse (Sammelkasten ueber mehrere Elemente) weg: Kasten, der >= 2 andere zu > 80 % enthaelt
        def enthaelt(A, B_):
            w = min(A["u1"], B_["u1"]) - max(A["u0"], B_["u0"]); h = min(A["z1"], B_["z1"]) - max(A["z0"], B_["z0"])
            return w > 0 and h > 0 and w * h > 0.8 * (B_["u1"] - B_["u0"]) * (B_["z1"] - B_["z0"])
        elemente = [e for e in elemente if sum(1 for o in elemente if o is not e and o["klasse"] == e["klasse"] and enthaelt(e, o)) < 2]
        # Reihenregel je Klasse: gleiche Unter-/Oberkante innerhalb reihe_tol -> Reihenmedian
        for kl in KLASSEN:
            L = sorted([e for e in elemente if e["klasse"] == kl], key=lambda e: e["z0"]); reihen = []
            for e in L:
                for rr in reihen:
                    if abs(e["z0"] - np.median([x["z0"] for x in rr])) < a.reihe_tol and abs(e["z1"] - np.median([x["z1"] for x in rr])) < a.reihe_tol: rr.append(e); break
                else: reihen.append([e])
            for i, rr in enumerate(reihen):
                z0, z1 = float(np.median([x["z0"] for x in rr])), float(np.median([x["z1"] for x in rr]))
                for e in rr: e.update(reihe=i, z0_roh=e["z0"], z1_roh=e["z1"], z0=z0, z1=z1)
        # Boegen: der Erkenner liefert je Bogen oft ZWEI Kaesten (nur Bogenfeld / ganze Oeffnung bis zum Boden) -> eine Oeffnung, Kaempfer = Unterkante des Bogenfelds
        neu = boegen_vereinen(elemente)
        elemente = [e for e in elemente if e["klasse"] != "bogen"] + neu
        for e in elemente:                                                                            # Fenster/Tueren IN einer Bogenoeffnung liegen auf der Rueckwand (Arkade) -> markieren
            if e["klasse"] in ("fenster", "tuer"):
                uc, zc = 0.5 * (e["u0"] + e["u1"]), 0.5 * (e["z0"] + e["z1"])
                e["in_bogen"] = any(b["u0"] < uc < b["u1"] and b["z0"] < zc < b["z1"] for b in neu)
        bilder = {nr: cv2.imread(os.path.join(ed, f"{nr}.png")) for nr, _ in rang}
        for e in elemente:
            if e["klasse"] == "fenster" and not e.get("in_bogen"):
                fz = felder_zaehlen(e, r, bilder)
                if fz: e["felder"] = fz["felder"]; e["felder_zaehlung"] = fz
        erg["fassaden"][fid] = dict(n=F["n"], d=F["d"], o=F["o"], fotos=[nr for nr, _ in rang], elemente=elemente,
                                    anzahl={kl: sum(1 for e in elemente if e["klasse"] == kl) for kl in KLASSEN})
        if a.objekt:
            try: zprot += z_protokolle(a.objekt, F, fid, elemente, rang, a.z_aus, os.path.abspath(aus))
            except Exception as ex: print(f"  {fid}: Z-Protokoll fehlgeschlagen ({type(ex).__name__}: {ex})", flush=True)
        # Sichtbild
        fus = cv2.imread(os.path.join(a.ortho, f"ortho_{fid}.png")); fus = cv2.resize(fus, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
        farbe = dict(fenster=(0, 255, 255), tuer=(255, 0, 255), bogen=(0, 255, 0), figur=(255, 128, 0), gaube=(255, 255, 0), balkon=(0, 0, 255), uhr=(255, 255, 255))
        for e in elemente:
            p0 = (int((e["u0"] - r["u0"]) / z_ * 3), int((r["z1"] - e["z1"]) / z_ * 3)); p1 = (int((e["u1"] - r["u0"]) / z_ * 3), int((r["z1"] - e["z0"]) / z_ * 3))
            cv2.rectangle(fus, p0, p1, farbe[e["klasse"]], 2); cv2.putText(fus, f"{e['klasse'][:4]} {e['stimmen']}/{e['gesehen']}", (p0[0] + 2, p0[1] + 14), 0, 0.45, farbe[e["klasse"]], 1)
        cv2.imwrite(os.path.join(aus, f"elemente_{fid}.jpg"), fus)
        print(f"{fid}: {erg['fassaden'][fid]['anzahl']}", flush=True)
    erg["gegen_verworfen"] = n_gegen; erg["z_protokolle"] = zprot; erg["sekunden"] = round(time.time() - t0, 1); json.dump(erg, open(os.path.join(aus, "elemente.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
