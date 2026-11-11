#!/usr/bin/env python3
"""foto_stoermaske.py - STOERMASKE JE KALIBRIERTEM FOTO fuer die Foto-Metrik (SPEC_STOERMASKE.md, Nutzerfreigabe 11.11.).

Zweck: Fotokanten von Dingen, die ein Gebaeudemodell nie hat (Menschen, Fahrzeuge, Schilder, Tische/Stuehle/Schirme/Staende/Zelte/Markisen,
Pflanzen/Kuebel, Fahnen), senken den Recall dauerhaft. Diese Pixel sollen in teil_fotoform (--stoermaske an) nicht zaehlen.
NICHT maskiert: Gebaeudeteile, Lampen/Masten, Himmel, Figuren/Statuen am Gebaeude (Modellteile!) - 'person' nur mit Bodenkontakt
(handy_masken_v2: Statuen haben unter sich Fassade/Balkon, nie Boden), siehe dort (b).

WIEDERVERWENDET aus tools/handy_masken_v2.py (nichts neu gebaut): SegFormer-ADE20K (seg_analyse, namen, ids_von), Komponentenlogik inkl.
Bodenkontakt-Test (komponenten), OWLv2-Boxen fuer Plane/Zelt/Schirm (owl_laden, owl_boxen, owl_flaechen), Maskenschreiben (nachbearbeiten).
Neu hier nur: die Klassenliste, das Entzerren des Fotos wie foto_diff (die Kostenkarte liegt im k1-entzerrten Bild), der Randpuffer aus der Kamera
(Schwelle 0,14 m im Bild) und Cache/Bericht/Blickbilder.

Ausgabe: <ausgabe>/<objekt>/<foto>.png (255 = benutzen, 0 = ignorieren; Rahmen = entzerrtes Foto in Volllaufloesung),
         <ausgabe>/<objekt>/bericht.json (Klassen, Flaechenanteil je Foto), <ausgabe>/<objekt>/blick/<foto>.jpg (Maske rot ueber dem Foto).
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/foto_stoermaske.py <objekt> [--fotos a,b] [--alle] [--kein_blick]
Lizenz: wie handy_masken_v2 (SegFormer s. modelle/LIZENZ_WERKZEUGE.md, OWLv2 Apache-2.0)."""
import sys, os, json, glob, argparse, time
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import handy_masken_v2 as H

R0 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = "/media/oem/scan/rc-park_tmp/stoermaske"
# Klassen (ADE20K-Namen aus id2label). Gebaeude/Himmel/Lampen/Masten/Skulpturen/Saeulen stehen bewusst NICHT hier.
STOERER_ZUSATZ = ("signboard", "poster", "trade name", "bulletin board",                     # Schilder / Plakate / Ladenschilder
                  "table", "chair", "armchair", "swivel chair", "stool", "bench", "awning",   # Tische, Stuehle, Markise
                  "tree", "plant", "flower", "pot", "palm", "basket", "barrel", "ashcan",     # Pflanzen, Kuebel, Tonnen
                  "flag", "bag")                                                              # Fahnen, Taschen
# Pflanzen/Kuebel/Taschen NUR mit Bodenkontakt (Sichtprobe 11.11.: ohne Test maskierte 'plant/flower' Erker-Wappen und Rippenflecken im Gewoelbe = Gebaeude);
# OWL-Boxen > 25 % Bild verworfen (Schirm-Box ueber dem ganzen Gewoelbe d17 = 47,7 % Fehlmaske).
H.BODENPFLICHT = tuple(H.BODENPFLICHT) + ("plant", "flower", "pot", "palm", "tree", "bag", "barrel", "basket", "ashcan")
H.P["owl_max"] = 0.25
SCHILD, SCHILD_MIN = ("signboard", "poster", "trade name", "bulletin board"), 0.002
WAND_RING, WAND_FLAECHE = 0.6, 0.004   # kleine 'Person/Pflanze' mit ringsum Wand/Gewoelbe = Schlussstein/Wappen (Sichtprobe d17, 6182, 6206, 6124)
_komp0 = H.komponenten
def _komponenten(seg, nm, cls_ids):
    res = _komp0(seg, nm, cls_ids)
    for rec, comp in res:
        if rec["behalten"] and "ring_fassade" in rec and rec["flaeche"] < WAND_FLAECHE and rec["ring_fassade"] >= WAND_RING:
            rec.update(behalten=False, grund="kleiner Fleck ringsum Fassade/Gewoelbe (Bauschmuck)")
        if rec["behalten"] and rec["klasse"] in SCHILD and rec["flaeche"] < SCHILD_MIN:   # Schlusssteine/Wappen werden als winziges 'signboard' erkannt (d17, 6182, 6124)
            rec.update(behalten=False, grund="Schild < %.1f %% Bild (Bauschmuck-Verdacht)" % (100 * SCHILD_MIN))
    return res
H.komponenten = _komponenten
PUFFER_M = 0.14        # = teil_fotoform --schwelle 0,4 x Kappe 0,35 m: Saum, in dem eine Modellkante noch als 'getroffen' gilt
PUFFER_MIN, PUFFER_MAX = 2, 40


def klassen(nm):
    """Klassen-Id-Liste: Bewegtes/Bodenpflichtiges/Stand aus handy_masken_v2 plus Zusatzliste (alles aus id2label, keine Festnummern)."""
    return sorted(H.ids_von(nm, H.IMMER + H.BODENPFLICHT + H.MARKT + STOERER_ZUSATZ))


def foto_laden(obj, objp, nr):
    """(Bild entzerrt wie foto_diff, K, Pfad) oder None. Gleiche Quelle wie teil_fotoform/foto_diff: fotos_dir/<nr>_*, K-Datei des Objekts."""
    import fehlteile_finden as FF
    kp = FF.k_datei(objp, obj, R0, nr)
    if not kp or not os.path.exists(kp): return None
    K = json.load(open(kp)); bild = glob.glob(os.path.join(R0, obj["fotos_dir"], nr + "_*"))
    if not bild or "kamera" not in K: return None
    im = cv2.imread(bild[0])
    if im is None: return None
    im, _k1 = FF.foto_entzerren(im, K.get("kamera", {}))
    return im, K, bild[0]


def puffer_px(obj, objp, K, nr, W, H_, modell_zentrum):
    """Randpuffer in Pixeln: PUFFER_M am Modell (Abstand Kamera - Modellmitte, Rahmen wie teil_fotoform.rahmen)."""
    import fehlteile_finden as FF
    R, t, f, _, _ = FF.kamera_laden(K, obj, nr, R0, W, H_)
    cam = -np.asarray(R).T @ np.asarray(t, float).reshape(3)
    d = float(np.linalg.norm(np.asarray(modell_zentrum, float) - cam))
    return int(np.clip(round(PUFFER_M * float(f) / max(d, 1.0)), PUFFER_MIN, PUFFER_MAX)), d


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--fotos"); ap.add_argument("--alle", action="store_true")
    ap.add_argument("--ausgabe", default=CACHE); ap.add_argument("--stl"); ap.add_argument("--breite", type=int, default=1536)
    ap.add_argument("--owl_score", type=float, default=H.P["owl_score"]); ap.add_argument("--kein_owl", action="store_true")
    ap.add_argument("--kein_blick", action="store_true"); ap.add_argument("--blick_fotos", help="Blickbilder nur fuer diese Fotos (Komma), sonst alle")
    ap.add_argument("--neu", action="store_true", help="vorhandene Masken neu rechnen")
    a = ap.parse_args(argv); H.P["owl_score"] = a.owl_score
    objp = os.path.join(R0, "modelle", a.objekt, "objekt.json"); obj = json.load(open(objp))
    fotos = a.fotos.split(",") if a.fotos else sorted(os.path.basename(p)[2:-5] for p in glob.glob(os.path.join(os.path.dirname(objp), "messprotokoll", "K-*.json")))
    od = os.path.join(a.ausgabe, a.objekt); bd = os.path.join(od, "blick"); os.makedirs(bd, exist_ok=True)
    bp = os.path.join(od, "bericht.json"); bericht = json.load(open(bp)) if os.path.exists(bp) else {"fotos": {}}
    todo = [nr for nr in fotos if a.neu or not os.path.exists(os.path.join(od, nr + ".png"))]
    print(f"{len(fotos)} Fotos, {len(todo)} zu rechnen", flush=True)
    # Modellmitte (Kamerarahmen) fuer den Pixelpuffer
    import trimesh, teil_fotoform as TFF
    stl = a.stl or os.path.join(R0, obj["stl"]); m = trimesh.load(stl, force="mesh"); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0)
    import fehlteile_finden as FF
    zentrum_roh = m.bounds.mean(0)
    if todo:
        import torch
        from transformers import SegformerForSemanticSegmentation
        dev = "cuda" if torch.cuda.is_available() else "cpu"; fp16 = dev == "cuda"
        model = SegformerForSemanticSegmentation.from_pretrained(H.MODELL).eval().to(dev)
        if fp16: model = model.half()
        nm = H.namen(model.config.id2label); cls_ids = dict(alle=klassen(nm))
        print("Klassen:", {c: nm[c] for c in cls_ids["alle"]}, flush=True)
        owl = None if a.kein_owl else H.owl_laden(dev)
        mean = np.array([0.485, 0.456, 0.406], np.float32); std = np.array([0.229, 0.224, 0.225], np.float32)
        t0 = time.time()
        for i, nr in enumerate(todo):
            r = foto_laden(obj, objp, nr)
            if r is None: print(f"  {nr}: kein Foto/keine Kamera", flush=True); continue
            im, K, pfad = r; Hh, Ww = im.shape[:2]
            tr = TFF.rahmen(stl, obj, K["kamera"]); pu, dist = puffer_px(obj, objp, K, nr, Ww, Hh, zentrum_roh + tr)
            try:
                seg = H.seg_analyse(model, [im], a.breite, dev, fp16, mean, std, H.ANALYSE_B)[0]
                bx = H.owl_boxen(owl, [im], dev, a.owl_score)[0] if owl else []
            except torch.cuda.OutOfMemoryError:
                torch.cuda.empty_cache(); print(f"  {nr}: OOM", flush=True); raise
            torch.cuda.empty_cache()
            pa = os.path.join(od, nr + ".png")
            _, anteil, recs = H.nachbearbeiten((pa, seg, (Hh, Ww), bx, nm, cls_ids, pu))
            kl = {}
            for rc in recs:
                if rc["behalten"]: kl[rc["klasse"]] = kl.get(rc["klasse"], 0) + 1
            bericht["fotos"][nr] = dict(maskiert_anteil=anteil, puffer_px=pu, abstand_m=round(dist, 1), bild=[Ww, Hh], klassen=kl,
                                        komponenten=[{k: v for k, v in rc.items()} for rc in recs])
            json.dump(bericht, open(bp, "w"), ensure_ascii=False, indent=1)
            print(f"  {nr}: maskiert {100 * anteil:.1f} % Puffer {pu} px Klassen {kl} ({time.time() - t0:.0f} s)", flush=True)
        if dev == "cuda": print(f"GPU-Spitze {torch.cuda.max_memory_allocated() / 2**30:.2f} GiB", flush=True)
    bericht.update(version="v1", segformer=H.MODELL, owl=None if a.kein_owl else H.OWL, abfragen=H.OWL_ABFRAGEN, zusatzklassen=list(STOERER_ZUSATZ), puffer_m=PUFFER_M)
    json.dump(bericht, open(bp, "w"), ensure_ascii=False, indent=1)
    if not a.kein_blick:
        bf = set(a.blick_fotos.split(",")) if a.blick_fotos else None
        for nr in fotos:
            if bf is not None and nr not in bf: continue
            pa = os.path.join(od, nr + ".png")
            if not os.path.exists(pa): continue
            r = foto_laden(obj, objp, nr)
            if r is None: continue
            im = r[0]; mk = cv2.imread(pa, 0) == 0
            ov = im.copy(); ov[mk] = (0.45 * ov[mk] + 0.55 * np.array((0, 0, 255))).astype(np.uint8)
            cs, _ = cv2.findContours(mk.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE); cv2.drawContours(ov, cs, -1, (0, 255, 255), 2)
            s = 1500.0 / ov.shape[1]; ov = cv2.resize(ov, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
            cv2.putText(ov, f"{nr} maskiert {100 * mk.mean():.1f}%", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 3)
            cv2.imwrite(os.path.join(bd, nr + ".jpg"), ov, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return bericht


def maske_laden(objekt, nr, W, H_, ausgabe=CACHE):
    """Von teil_fotoform genutzt: bool-Feld (H,W), True = Stoerer (ignorieren); None, wenn keine Maske fuer das Foto existiert."""
    p = os.path.join(ausgabe, objekt, nr + ".png")
    if not os.path.exists(p): return None
    m = cv2.imread(p, 0)
    if m is None: return None
    if m.shape != (H_, W):
        m = cv2.resize(m, (W, H_), interpolation=cv2.INTER_NEAREST)
    return m == 0


if __name__ == "__main__":
    main()
