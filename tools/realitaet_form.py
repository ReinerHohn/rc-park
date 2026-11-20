#!/usr/bin/env python3
"""realitaet_form.py - FORMNOTE (Realitaet Teil 2: Form). Spec modelle/archiv/SPEC_FORMNOTE.md (Nutzerentscheid 11.11.).

Foto-F1 misst nur LAGE der Kanten und ist blind fuer die Form. Hier urteilt ein Bildpruefer (claude -p, opus) je Bauteil ueber die FORM:
Je Teil feste Wahl von 3-4 Fotos (+ 1 Kontur-Kachel), je Foto ein Zweierbild Fotoausschnitt | Render (Teil orange, Rest grau).
Ausgabe je Teil: form in {1,0; 0,5; 0}, sicher, fehler[]. Gesamt: form_prozent = Mittel gewichtet mit sichtbarer Teilflaeche (sicht_px).
FALLEN (feste, bekannt falsche Teile in <cache_dir>/fallen/) werden in JEDEM Lauf frisch (nie gecacht) unter neutralem Namen mitbewertet;
bekommt eine Falle form >= 0,5, ist der Lauf `ungueltig` und form_prozent wird nicht ausgegeben.

Aufruf: /media/oem/scan/venv-seg/bin/python -I tools/realitaet_form.py <objekt> (--teile_dir D | --stl S) [--aus x.json] [--nur a,b] [--cache_dir C]
        [--kein_cache] [--nur_bilder] [--buendel 2] [--parallel 3] [--formliste F] [--fallen_neu]
Nur importiert werden formfund_pruefen/formfamilie_pruefen/foto_lokal; nichts im Repo wird veraendert.
"""
import sys, os, json, glob, re, argparse, time, math, subprocess, hashlib, random, shutil, numpy as np, cv2, trimesh
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import foto_diff as FD, fehlteile_finden as FF, render_kern as RK, teil_fotoform as TF
import formfamilie_pruefen as FP
import formfund_pruefen as FFP
import foto_lokal as FL

R0 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_STD = "/media/oem/scan/rc-park_tmp/formnote"
PROMPT_VERSION = "v2"
PANEL = 620
MIN_SICHT = FP.MIN_SICHT

PROMPT = """Du bist Bildpruefer fuer ein 3D-Modell (H0 1:87, 3D-Druck) des Gebaeudes "{objekt}". Du bewertest die FORM einzelner Bauteile, nicht deren Lage.
Es folgen {n_teile} Bauteil(e) mit Kennung. Zu jedem gehoeren Bilddateien; jede Datei ist ein ZWEIERBILD: LINKS ein Foto (Ausschnitt), RECHTS ein schattierter Render
des Modells aus DERSELBEN Kamera und demselben Ausschnitt. Im Render ist das zu bewertende Bauteil ORANGE, alles andere grau (nur Umgebung); dunkle Linien = Kanten/Spruenge.
Dateien mit [Kontur] sind FRONTAL-PARALLELE Ansichten ohne Perspektive: links das Foto auf die Frontebene des Teils entzerrt (nur Dinge in der Teilebene stimmen),
rechts das Modell orthografisch; fuer Stufen, Zacken, Bogenarten gut geeignet.
Sieh dir jede Datei mit dem Read-Werkzeug an (Bilder werden angezeigt).

{teilbloecke}
Vorgehen je Bauteil:
1. Zaehle im FOTO die formbestimmenden Merkmale des Teils auf: Umriss, Bogenart (Rund/Spitz/Segment), Anzahl und Anordnung der Wiederholungen (Fenster, Gauben, Zinnen, Stufen, Pfeiler),
   Profile/Gesimse, Oeffnungen, Dachform, Aufsaetze. Nimm die Mehrheit der Bilder; ein Foto allein kann verdeckt oder schief sein.
2. Beurteile jedes Merkmal im RENDER: `stimmt`, `teilweise`, `falsch` oder `fehlt` (fehlt = im Foto da, im Modell nicht). Zusaetzlich: gibt es im Modell einen Koerper oder ein Merkmal,
   das im Foto NICHT da ist (erfunden)? Das ist `falsch`.
3. Gesamturteil `form` (strenge Regel, im Zweifel die niedrigere Note):
   - 1.0 = KEIN wesentliches Merkmal fehlt oder ist falsch: Umriss, Bogenart, Anzahl der Wiederholungen, Profile/Rippen/Grate/Gesimse/Abdeckungen ab etwa 0,3 m Groesse, Oeffnungen stimmen. Hat ein Merkmal nur `teilweise`, ist es hoechstens 0.5.
   - 0.5 = Grundform und Hauptmerkmal stimmen, aber mindestens ein Nebenmerkmal (Profil, Rippe, Abdeckung, Oeffnung, Detail) fehlt oder ist nur teilweise richtig.
   - 0 = das FORMBESTIMMENDE HAUPTMERKMAL ist falsch: falsche Bogenart, falsche Umrissform (z. B. Saegezaehne statt waagerechter Stufen, Schweifung statt gerader Kante), falsche Dachform,
     falsche ANZAHL der Wiederholungen (ein Fenster/Gaube/Baldachin/Figur/Bogen zu viel oder zu wenig; im Foto auszaehlen!), ein erfundener Koerper, der im Foto nicht vorkommt, oder die Grundform ist nicht das Foto.
   `sicher`: hoch nur, wenn dein Urteil in mindestens 2 Bildern klar zu sehen ist; ein einziges Bild oder unklare Sicht = hoechstens mittel; Vermutung = niedrig.
   `fehler`: Liste kurzer Saetze (deutsch) zu allem, was nicht stimmt; leer, wenn alles stimmt.
Nicht bewerten: Farbe, Textur, Lage/Feinlage von wenigen cm, Verdeckungen im Foto (Baeume, Personen, Gerueste, Nachbarhaeuser), Details unter ca. 0,3 m. Urteile nur ueber das orange Teil.
Ist das Teil in den Fotos nicht erkennbar: form null, sicher niedrig, in `fehler` begruenden.

Letzte Zeile deiner Antwort GENAU (eine Zeile, gueltiges JSON, deutsche Texte, ein Eintrag je Bauteil in der Reihenfolge oben):
ERGEBNIS {{"teile": [{{"id": "<Kennung>", "merkmale": [{{"name": "...", "urteil": "stimmt|teilweise|falsch|fehlt"}}], "form": 1.0|0.5|0|null, "sicher": "hoch|mittel|niedrig", "fehler": ["..."]}}]}}
"""
TEILBLOCK = """### Bauteil {kennung}
Dateien:
{pfade}
"""


# ------------------------------------------------------------------ Kontext (ein Modell, mehrere Fotos)
class Kontext:
    def __init__(s, obj, objp, stl_real, ganz):
        s.obj, s.objp, s.stl_real, s.ganz, s.c = obj, objp, stl_real, ganz, {}
    def get(s, nr, voll=True):
        if nr in s.c and (not voll or "dv" in s.c[nr]): return s.c[nr]
        kp = FF.k_datei(s.objp, s.obj, R0, nr); K = json.load(open(kp)); bild = glob.glob(os.path.join(R0, s.obj["fotos_dir"], nr + "_*"))
        if not bild: return None
        im0 = cv2.imread(bild[0]); im0, K = FD.foto_skalieren(im0, K); kk = K["kamera"]; im0, _ = FF.foto_entzerren(im0, kk); H, W = im0.shape[:2]
        R, t, f, _, _ = FF.kamera_laden(K, s.obj, nr, R0, W, H); cx, cy = float(kk.get("cx", W / 2)), float(kk.get("cy", H / 2))
        c = {"im0": im0, "R": R, "t": t, "f": f, "cx": cx, "cy": cy, "W": W, "H": H, "tr": TF.rahmen(s.stl_real, s.obj, kk)}
        if voll:
            Mw = s.ganz.copy(); Mw.apply_translation(c["tr"]); dv, fid, _ = RK.dreiecke_rastern(Mw, R, t, f, cx, cy, W, H)
            c["dv"] = dv; c["img"], c["kante"] = FP.schattieren(Mw, fid, dv, R)
        if len(s.c) > 6: s.c.pop(next(iter(s.c)))
        s.c[nr] = c; return c


def zweier(foto, rn, titel, pfad, panel=PANEL):
    s = panel / max(foto.shape[:2]); sz = (max(2, int(foto.shape[1] * s)), max(2, int(foto.shape[0] * s)))
    f = cv2.resize(foto, sz, interpolation=cv2.INTER_AREA)
    n = cv2.resize(rn, sz, interpolation=cv2.INTER_NEAREST if s > 1 else cv2.INTER_AREA)
    sp = np.full((f.shape[0], 6, 3), 255, np.uint8)
    cv2.imwrite(pfad, np.hstack([FP.beschriften(f, f"FOTO {titel}"), sp, FP.beschriften(n, "MODELL (Teil orange)")]), [cv2.IMWRITE_JPEG_QUALITY, 90]); return pfad


def bilder_teil(kenn, mt, wahl, kam, fl_teil, kx, bdir, kontur=True):
    """Zweierbilder je gewaehltem Foto + eine Kontur-Kachel. mt: Teilnetz (Modellrahmen, Meter). Rueckgabe {etikett: pfad}."""
    out = {}
    for nr in wahl:
        c = kx.get(nr)
        if not c: continue
        m = mt.copy(); m.apply_translation(c["tr"]); W, H = c["W"], c["H"]
        dp, _, _ = RK.dreiecke_rastern(m, c["R"], c["t"], c["f"], c["cx"], c["cy"], W, H)
        ss = np.isfinite(dp) & (dp <= c["dv"] * 1.003 + 0.03)
        if ss.sum() < 200: print(f"  {kenn} {nr}: Teil kaum sichtbar", flush=True); continue
        box = FP.box_aus_maske(ss, W, H)
        rn = FFP.panel_render(c["img"], c["kante"], ss, box, "n")
        out[nr] = zweier(c["im0"][box[1]:box[3], box[0]:box[2]].copy(), rn, nr, os.path.join(bdir, f"{kenn}_{nr}.jpg"))
    if kontur:
        v2 = mt.vertices[:, :2] - mt.vertices[:, :2].mean(0); ax = np.linalg.eigh(np.cov(v2.T) + 1e-9 * np.eye(2))[1][:, 1]
        nrm = np.array([-ax[1], ax[0]]); ctr = mt.bounds.mean(0); fr = []
        smax = max([v.get("sicht_px", 0) for v in fl_teil.values() if isinstance(v, dict)] + [1])
        for nr, v in fl_teil.items():
            if not isinstance(v, dict) or v.get("sicht_px", 0) < max(MIN_SICHT, 0.08 * smax) or nr not in kam: continue
            d = kam[nr][:2] - ctr[:2]; ang = math.degrees(math.acos(min(1.0, abs(float(d @ nrm)) / (np.linalg.norm(d) + 1e-9)))); fr.append((ang, nr))
        for ang, nr in sorted(fr)[:8]:
            c = kx.get(nr, voll=False)
            if not c: continue
            m1 = mt.copy(); m1.apply_translation(c["tr"])
            tmp = os.path.join(bdir, f"_{kenn}_k.jpg")
            r_ = FFP.kontur_dreier(kenn, m1, m1, (c["im0"], c["R"], c["t"], c["f"], c["cx"], c["cy"], c["W"], c["H"]), nr, tmp)
            if not r_: continue
            im = cv2.imread(tmp); w3 = (im.shape[1] - 12) // 3; z = im[:, : 2 * w3 + 6].copy()   # Foto | Modell (Dreierbild links zwei Drittel)
            cv2.rectangle(z, (w3 + 6, 0), (z.shape[1], 26), (0, 0, 0), -1)
            cv2.putText(z, "MODELL [Kontur] (Teil orange)", (w3 + 12, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
            pf = os.path.join(bdir, f"{kenn}_Kontur_{nr}.jpg"); cv2.imwrite(pf, z, [cv2.IMWRITE_JPEG_QUALITY, 90]); os.remove(tmp)
            out["Kontur " + nr] = pf; break
    return out


# ------------------------------------------------------------------ Pruefer
def pruefer_aufruf(objekt, bloecke, arbeit, modell, timeout, tag):
    """bloecke: [(kennung, [pfade])]. Rueckgabe {kennung: urteilsdict} und Meta."""
    tb = "\n".join(TEILBLOCK.format(kennung=k, pfade="\n".join(f"- {p}" for p in ps)) for k, ps in bloecke)
    p = PROMPT.format(objekt=objekt, n_teile=len(bloecke), teilbloecke=tb)
    logp = os.path.join(arbeit, f"pruefer_{tag}.log"); t0 = time.time(); res = {}
    try:
        r = subprocess.run(["claude", "-p", p, "--model", modell, "--permission-mode", "plan"], cwd=arbeit, capture_output=True, text=True, timeout=timeout)
        out = r.stdout + ("\n[stderr]\n" + r.stderr if r.stderr else "")
    except subprocess.TimeoutExpired:
        open(logp, "w").write("ZEITLIMIT"); return {k: {"status": "ungeprueft", "grund": "Zeitlimit"} for k, _ in bloecke}, round(time.time() - t0)
    open(logp, "w").write(out); erg = None
    for m in re.finditer(r"ERGEBNIS\s*(\{)", out):
        try: erg = json.JSONDecoder().raw_decode(out[m.start(1):])[0]
        except Exception: pass
    liste = erg.get("teile") if isinstance(erg, dict) else None
    for k, _ in bloecke:
        e = next((x for x in (liste or []) if isinstance(x, dict) and x.get("id") == k), None)
        if not e or e.get("form") not in (0, 0.0, 0.5, 1, 1.0):
            res[k] = {"status": "ungeprueft", "grund": "kein lesbares Urteil (rc %s)" % r.returncode, "log": logp}
        else:
            e = dict(e); e["form"] = float(e["form"]); e["status"] = "ok"; e["log"] = logp; res[k] = e
    return res, round(time.time() - t0)


# ------------------------------------------------------------------ Fallen
def fallen_zusatz(fd, teile_dir, meta):
    """Fallen f6-f8 (11.11. nachgeliefert, VOR dem Blick auf Urteile gebaut): Erker mit verdoppelter Fensterzone, Gauben mit Tonnendach statt Satteldach, Bruestung ohne Docken.
    Nur fehlende Dateien werden erzeugt; bestehende Fallen bleiben unveraendert."""
    # f6: Erker, Fensterzone (Hoehenband 45-80 %) dupliziert und darueber gesetzt -> doppelt so viele Fenster
    if not os.path.exists(os.path.join(fd, "f6.stl")):
        m = trimesh.load(os.path.join(teile_dir, "erker_polygon__0.stl"), force="mesh"); b = m.bounds; z0, h = b[0, 2], b[1, 2] - b[0, 2]
        band = m.slice_plane([0, 0, z0 + 0.45 * h], [0, 0, 1], cap=True).slice_plane([0, 0, z0 + 0.80 * h], [0, 0, -1], cap=True)
        extra = band.copy(); extra.apply_translation([0, 0, 0.35 * h]); top = m.slice_plane([0, 0, z0 + 0.80 * h], [0, 0, 1], cap=True); top.apply_translation([0, 0, 0.35 * h])
        low = m.slice_plane([0, 0, z0 + 0.80 * h], [0, 0, -1], cap=True)
        trimesh.util.concatenate([low, extra, top]).export(os.path.join(fd, "f6.stl"))
        meta["f6"] = {"ersetzt": "erker_polygon__0", "was": "Erker mit doppelter Fensterzone (Fensterband dupliziert, Erker 35 % hoeher)", "quelle": "erker_polygon__0 Band 45-80 % dupliziert"}
    # f7: Gaubenreihe unten, jede Gaube mit Tonnendach (Halbzylinder) statt Satteldach
    if not os.path.exists(os.path.join(fd, "f7.stl")):
        g = trimesh.load(os.path.join(teile_dir, "gaubenreihe__unten.stl"), force="mesh"); out = []
        for c in g.split(only_watertight=False):
            bb = c.bounds; w, d, h = bb[1] - bb[0]; r = w / 2; cen = c.bounds.mean(0)
            kasten = trimesh.creation.box(extents=[w, d, h - r]); kasten.apply_translation([cen[0], cen[1], bb[0, 2] + (h - r) / 2])
            zyl = trimesh.creation.cylinder(radius=r, height=d, sections=24); zyl.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0])); zyl.apply_translation([cen[0], cen[1], bb[0, 2] + h - r])
            out += [kasten, zyl]
        trimesh.util.concatenate(out).export(os.path.join(fd, "f7.stl"))
        meta["f7"] = {"ersetzt": "gaubenreihe__unten", "was": "3 Gauben mit Tonnendach (Halbzylinder) statt Satteldach", "quelle": "gaubenreihe__unten, Gauben ersetzt"}
    # f8: Bruestung ohne Docken (mittleres Hoehenband 18-82 % herausgeschnitten: nur Ober- und Untergurt)
    if not os.path.exists(os.path.join(fd, "f8.stl")):
        m = trimesh.load(os.path.join(teile_dir, "bruestung__balkon.stl"), force="mesh"); b = m.bounds; z0, h = b[0, 2], b[1, 2] - b[0, 2]
        trimesh.util.concatenate([m.slice_plane([0, 0, z0 + .18 * h], [0, 0, -1], cap=True), m.slice_plane([0, 0, z0 + .82 * h], [0, 0, 1], cap=True)]).export(os.path.join(fd, "f8.stl"))
        meta["f8"] = {"ersetzt": "bruestung__balkon", "was": "Bruestung ohne Docken (nur Ober- und Untergurt)", "quelle": "bruestung__balkon, Band 18-82 % entfernt"}
    return meta


def fallen_erzeugen(cache, teile_dir, sk_mm_zu_m):
    """Einmal erzeugen und dann NIE aendern. Rueckgabe Verzeichnis. Quellen siehe fallen.json (Herkunft, ersetzt Teil)."""
    fd = os.path.join(cache, "fallen"); os.makedirs(fd, exist_ok=True); meta = {}
    KR = "/media/oem/scan/rc-park_kreis/kaufhaus_grob3"
    def kop(src, name, ersetzt, was):
        shutil.copy(src, os.path.join(fd, name + ".stl")); meta[name] = {"ersetzt": ersetzt, "was": was, "quelle": src}
    kop(f"{KR}/20261111_125136a125135/teile_r1_vorher_form/staffelgiebel__west.stl", "f1", "staffelgiebel__west", "Westgiebel als Saegezahn (Altstand a125135 vorher)")
    kop(f"{KR}/20261111_091923a091923/teile_r2_nachher/freiform__tor_b2__ausschnitt.stl", "f2", "freiform__tor_b2__ausschnitt", "Tor rund statt spitz (a091923 r2 nachher)")
    # f3: erfundener Kasten auf dem Obergeschoss-Rumpf (Teil + grosser Quader, ragt aus der Wand)
    m = trimesh.load(os.path.join(teile_dir, "fensterreihe__og.stl"), force="mesh"); b = m.bounds; mitte = b.mean(0)
    kasten = trimesh.creation.box(extents=[1000 / 87 * 3.5, 1000 / 87 * 3.5, 1000 / 87 * 3.0]); kasten.apply_translation(mitte)
    trimesh.util.concatenate([m, kasten]).export(os.path.join(fd, "f3.stl")); meta["f3"] = {"ersetzt": "fensterreihe__og", "was": "erfundener Kasten 3,5x3,5x3 m in der Mitte der Fensterreihe OG", "quelle": "fensterreihe__og + box"}
    # f4/f5: Wiederholungsreihen mit einem Element weniger (Baldachine 4 -> 3, Figuren 4 -> 3; Gaubenreihe oben hat nur 2 Elemente: zu schwach als Anzahlfalle)
    for fn, tn in (("f4", "baldachinreihe__baldachine"), ("f5", "figurenreihe__figuren")):
        g = trimesh.load(os.path.join(teile_dir, tn + ".stl"), force="mesh"); teile = g.split(only_watertight=False)
        teile = sorted(teile, key=lambda t: t.bounds.mean(0)[0] + 1e-3 * t.bounds.mean(0)[1]); print(f"Falle {fn}: {tn} hat {len(teile)} Komponenten", flush=True)
        if len(teile) >= 3:
            k = 1; trimesh.util.concatenate(teile[:k] + teile[k + 1:]).export(os.path.join(fd, fn + ".stl"))
            meta[fn] = {"ersetzt": tn, "was": f"{tn} mit {len(teile) - 1} statt {len(teile)} Elementen (zweites von links entfernt)", "quelle": f"{tn} minus Komponente {k}"}
    fallen_zusatz(fd, teile_dir, meta)
    json.dump(meta, open(os.path.join(fd, "fallen.json"), "w"), ensure_ascii=False, indent=1)
    return fd


# ------------------------------------------------------------------ Hauptlauf
def lauf(objekt, teile_dir=None, stl=None, aus=None, nur=None, cache_dir=CACHE_STD, kein_cache=False, nur_bilder=False, buendel=2, parallel=3,
         formliste=None, modell="opus", timeout=900, n_fotos=3, extra=None, bilder_wiederverwenden=True):
    t_start = time.time()
    objp = os.path.join(R0, "modelle", objekt, "objekt.json"); obj = json.load(open(objp)); name = str(obj.get("name") or objekt).split(" - ")[0]
    stl_real = os.path.join(R0, obj["stl"]); sk = obj.get("stl_massstab", 87) / 1000.0
    os.makedirs(cache_dir, exist_ok=True)
    if not teile_dir:
        teile_dir = os.path.join(cache_dir, "teile_" + time.strftime("%Y%m%d_%H%M%S")); os.makedirs(teile_dir)
        env = dict(os.environ, BAUTEILE_AUS=teile_dir); subprocess.run(obj["generator"], shell=True, cwd=R0, env=env, check=True, capture_output=True)
    namen = sorted(os.path.basename(p)[:-4] for p in glob.glob(os.path.join(teile_dir, "*.stl")))
    if nur: namen = [n for n in namen if n in nur]
    # Formliste + Kameras
    if not formliste:
        cand = sorted(glob.glob("/media/oem/scan/rc-park_kreis/%s/fotoform/*_v2_wolkenverdeckung_festbereich.json" % objekt), key=os.path.getmtime)
        cand = [c for c in cand if len(json.load(open(c)).get("teile", {})) >= 35] or cand; formliste = cand[-1]
    FLd = json.load(open(formliste)); kam = {}
    for nr in FLd["fotos"]:
        try:
            kk = json.load(open(FF.k_datei(objp, obj, R0, nr)))["kamera"]; Rm, _ = cv2.Rodrigues(np.array(kk["rvec"])); kam[nr] = -Rm.T @ np.array(kk["t"], float) - TF.rahmen(stl_real, obj, kk)
        except Exception: continue
    # Fotowahl fest
    wp = os.path.join(cache_dir, "fotowahl.json"); wahl_alle = json.load(open(wp)) if os.path.exists(wp) else {}
    # Fallen
    fd = os.path.join(cache_dir, "fallen")
    if not os.path.exists(os.path.join(fd, "fallen.json")): fallen_erzeugen(cache_dir, teile_dir, sk)
    fmeta = json.load(open(os.path.join(fd, "fallen.json")))
    if not all(k in fmeta for k in ("f6", "f7", "f8")): fmeta = fallen_zusatz(fd, teile_dir, fmeta); json.dump(fmeta, open(os.path.join(fd, "fallen.json"), "w"), ensure_ascii=False, indent=1)
    # Gesamtmodell
    ganz_stl = FL.stl_aus_teilen(teile_dir); g = trimesh.load(ganz_stl, force="mesh"); g.apply_scale(sk)
    kx = Kontext(obj, objp, stl_real, g)
    bdir = os.path.join(cache_dir, "bilder"); os.makedirs(bdir, exist_ok=True)
    arbeit = os.path.join(cache_dir, "lauf_" + time.strftime("%Y%m%d_%H%M%S")); os.makedirs(arbeit)
    import gpu_slot; gpu_slot.belegen("realitaet_form")
    # Aufgaben: (kennung, teilname, stl-pfad, ist_falle)
    aufg = [(n, n, os.path.join(teile_dir, n + ".stl"), False) for n in namen]
    aufg += [(f, m["ersetzt"], os.path.join(fd, f + ".stl"), True) for f, m in sorted(fmeta.items())]   # Fallen: bei JEDEM Lauf (Spec)
    for x in (extra or []): fmeta[x["id"]] = {"ersetzt": x["ersetzt"], "was": x["was"], "extra": True}; aufg.append((x["id"], x["ersetzt"], x["stl"], True))
    kenn_neutral = {}; rnd = random.Random(4711)   # neutrale Namen, feste Zuordnung, Fallen nicht erkennbar
    ids = [f"T{i + 1:02d}" for i in range(len(aufg))]; rnd.shuffle(ids)
    cache_pfad = os.path.join(cache_dir, "urteile.json"); cache = json.load(open(cache_pfad)) if os.path.exists(cache_pfad) and not kein_cache else {}
    ergebnisse = {}; offen = []; tbilder = time.time(); n_bilder_teile = 0
    for (n, tn, pfad, falle), kid in zip(aufg, ids):
        mt = trimesh.load(pfad, force="mesh"); mt.apply_scale(sk)
        shash = hashlib.md5(open(pfad, "rb").read()).hexdigest()
        fl_teil = FLd["teile"].get(tn) or FFP.ersatz_sicht(mt, kam, objp, obj)
        if tn not in wahl_alle:
            wahl_alle[tn] = FP.fotowahl(tn, fl_teil, kam, mt, n_fotos)
            json.dump(wahl_alle, open(wp, "w"), indent=1)
        wahl = wahl_alle[tn]
        sicht = sum(fl_teil.get(f, {}).get("sicht_px", 0) for f in wahl if isinstance(fl_teil.get(f), dict))
        schl = hashlib.md5((shash + PROMPT_VERSION + ",".join(wahl)).encode()).hexdigest()
        e = {"teil": n, "falle": falle and not fmeta[n].get("extra"), "extra": bool(falle and fmeta[n].get("extra")), "kennung": kid, "sicht_px": sicht, "wahl": wahl, "schluessel": schl}
        if falle: e["falle_was"] = fmeta[n]["was"]
        if not falle and schl in cache and not kein_cache:
            e.update(cache[schl]); e["aus_cache"] = True; ergebnisse[n] = e; continue
        # Fallen: Teil im Gesamtmodell ersetzen -> eigener Kontext
        if falle:
            teile_f = dict()
            ersatz_dir = os.path.join(cache_dir, "_ersatz_" + n); shutil.rmtree(ersatz_dir, ignore_errors=True); os.makedirs(ersatz_dir)
            for p in glob.glob(os.path.join(teile_dir, "*")): os.symlink(p, os.path.join(ersatz_dir, os.path.basename(p)))
            os.remove(os.path.join(ersatz_dir, tn + ".stl")); shutil.copy(pfad, os.path.join(ersatz_dir, tn + ".stl"))
            gf = trimesh.load(FL.stl_aus_teilen(ersatz_dir), force="mesh"); gf.apply_scale(sk); k2 = Kontext(obj, objp, stl_real, gf)
        else: k2 = kx
        bd = os.path.join(bdir, kid); os.makedirs(bd, exist_ok=True)
        bkey = schl + "|" + os.path.basename(ganz_stl if not falle else FL.stl_aus_teilen(ersatz_dir)) + "|" + str(sk); bk = os.path.join(bd, "_key.json")
        if bilder_wiederverwenden and os.path.exists(bk) and json.load(open(bk)).get("key") == bkey: bi = json.load(open(bk))["bilder"]; print(f"{kid}: Bilder wiederverwendet", flush=True)
        else:
            for f_ in glob.glob(os.path.join(bd, "*")): os.remove(f_)
            bi = bilder_teil(kid, mt, wahl, kam, fl_teil, k2, bd); json.dump({"key": bkey, "bilder": bi}, open(bk, "w"))
        if not bi: e.update({"status": "ungeprueft", "grund": "keine Bilder (Teil in keinem gewaehlten Foto sichtbar)"}); ergebnisse[n] = e; continue
        e["bilder"] = bi; ergebnisse[n] = e; offen.append(n); n_bilder_teile += 1
        print(f"{kid} ({'FALLE ' if falle else ''}{n}): {len(bi)} Bilder, Fotos {wahl}", flush=True)
    sek_bilder = round(time.time() - tbilder)
    # Pruefer: Buendel
    aufrufe = 0; sek_pruefer = {}
    if not nur_bilder and offen:
        ordnung = sorted(offen, key=lambda n: ergebnisse[n]["kennung"])
        gruppen = [ordnung[i:i + buendel] for i in range(0, len(ordnung), buendel)]
        def job(gr):
            bl = [(ergebnisse[n]["kennung"], list(ergebnisse[n]["bilder"].values())) for n in gr]
            return gr, pruefer_aufruf(name, bl, arbeit, modell, timeout, "_".join(ergebnisse[n]["kennung"] for n in gr))
        with ThreadPoolExecutor(parallel) as ex:
            for gr, (res, sek) in ex.map(job, gruppen):
                aufrufe += 1
                for n in gr:
                    e = ergebnisse[n]; r = res[e["kennung"]]; e.update(r); e["sek_aufruf"] = sek; e["buendel"] = len(gr)
                    if not e["falle"] and not e["extra"] and r["status"] == "ok": cache[e["schluessel"]] = {k: r[k] for k in ("status", "form", "sicher", "fehler", "merkmale") if k in r}
        if not kein_cache: json.dump(cache, open(cache_pfad, "w"), ensure_ascii=False, indent=1)
    elif nur_bilder:
        for n in offen: ergebnisse[n]["status"] = "nur_bilder"
    # Auswertung
    echte = [e for e in ergebnisse.values() if not e["falle"] and not e["extra"]]; fallen = [e for e in ergebnisse.values() if e["falle"]]; extras = [e for e in ergebnisse.values() if e["extra"]]
    ungueltig = []
    if not nur_bilder:
        for e in fallen:
            if e.get("status") != "ok": ungueltig.append(f"Falle {e['teil']} ungeprueft (kein Urteil)")
            elif e["form"] >= 0.5: ungueltig.append(f"Falle {e['teil']} ({e['falle_was']}) bekam form {e['form']}")
    gewertet = [e for e in echte if e.get("status") == "ok" and e["sicht_px"] > 0]
    form_prozent = None
    if gewertet and not ungueltig and not nur_bilder:
        form_prozent = round(100 * sum(e["form"] * e["sicht_px"] for e in gewertet) / sum(e["sicht_px"] for e in gewertet), 1)
    form_fein_prozent = None
    gf = [e for e in gewertet if feinnote(e.get("merkmale")) is not None]
    if gf and not ungueltig and not nur_bilder: form_fein_prozent = round(100 * sum(feinnote(e["merkmale"]) * e["sicht_px"] for e in gf) / sum(e["sicht_px"] for e in gf), 1)
    erg = {"objekt": objekt, "teile_dir": teile_dir, "formliste": formliste, "prompt_version": PROMPT_VERSION, "status": "ungueltig" if ungueltig else ("nur_bilder" if nur_bilder else "ok"),
           "ungueltig_gruende": ungueltig, "form_prozent": form_prozent, "form_fein_prozent": form_fein_prozent, "teile": ergebnisse,
           "extras": {e["teil"]: dict({k: e.get(k) for k in ("form", "sicher", "fehler", "merkmale", "status")}, fein=feinnote(e.get("merkmale"))) for e in extras},
           "form_unter_1": [{"teil": e["teil"], "form": e["form"], "sicher": e.get("sicher"), "fehler": e.get("fehler")} for e in gewertet if e["form"] < 1],
           "nicht_geprueft": [e["teil"] for e in echte if e.get("status") != "ok"], "claude_aufrufe": aufrufe, "aus_cache": sum(1 for e in echte if e.get("aus_cache")),
           "sek_bilder": sek_bilder, "sek_gesamt": round(time.time() - t_start), "buendel": buendel}
    if aus: json.dump(erg, open(aus, "w"), ensure_ascii=False, indent=1)
    return erg


def feinnote(merkmale):
    """Feinere Zusatznote 0..1 aus den Merkmalsurteilen (stimmt 1, teilweise 0,5, falsch/fehlt 0). Die grobe `form` (1/0,5/0) hat nur 3 Stufen und trennt kleine Besserungen nicht;
    die Feinnote ist NUR Zusatz (Sortierung/Vergleich), nie Teil von form_prozent."""
    w = {"stimmt": 1.0, "teilweise": 0.5, "falsch": 0.0, "fehlt": 0.0}; v = [w[m.get("urteil")] for m in (merkmale or []) if isinstance(m, dict) and m.get("urteil") in w]
    return round(sum(v) / len(v), 2) if v else None


def tabelle(erg):
    z = ["Teil | form | sicher | fehler"]
    for n, e in sorted(erg["teile"].items()):
        if e["falle"] or e["extra"]: continue
        z.append(f"{n} | {e.get('form', e.get('status'))} (fein {feinnote(e.get('merkmale'))}) | {e.get('sicher', '-')} | {'; '.join(e.get('fehler') or [])[:140]}")
    return "\n".join(z)


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--teile_dir"); ap.add_argument("--stl"); ap.add_argument("--aus"); ap.add_argument("--nur")
    ap.add_argument("--cache_dir", default=CACHE_STD); ap.add_argument("--kein_cache", action="store_true"); ap.add_argument("--nur_bilder", action="store_true")
    ap.add_argument("--buendel", type=int, default=2); ap.add_argument("--parallel", type=int, default=3); ap.add_argument("--formliste"); ap.add_argument("--modell", default="opus")
    a = ap.parse_args(argv)
    if a.stl and not a.teile_dir: print("--stl: Export ueber den Generator aus objekt.json (generator) wird verwendet");
    e = lauf(a.objekt, a.teile_dir, a.stl, a.aus, a.nur.split(",") if a.nur else None, a.cache_dir, a.kein_cache, a.nur_bilder, a.buendel, a.parallel, a.formliste, a.modell)
    print(tabelle(e)); print(json.dumps({k: e[k] for k in ("status", "ungueltig_gruende", "form_prozent", "form_fein_prozent", "claude_aufrufe", "aus_cache", "sek_bilder", "sek_gesamt", "nicht_geprueft")}, ensure_ascii=False, indent=1))
    return e


if __name__ == "__main__":
    main()
