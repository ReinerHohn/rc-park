#!/usr/bin/env python3
"""drahtmasken.py - Draht-Masken je Foto (Detektor tools/drahtmaske.py) mit Zwischenspeicher, fuer alle Verbraucher der Kette.

  tools/py tools/drahtmasken.py <bildordner> --aus <ordner> [--colmap] [--rand 2] [--overlay <ordner>] [--arbeiter 4] [--nur a.jpg,b.jpg]
     --colmap: <aus>/<Bildname MIT Endung>.png, 0 = Draht ODER sicherer Himmel (ignorieren, seit 24.11. Geisterblatt), 255 = benutzen - Format von COLMAP StereoFusionOptions.mask_path
               (wie ImageReader.mask_path; fehlt eine Datei, fusioniert COLMAP das Bild ungemasked). Sonst <aus>/<Name ohne Endung>.png, 255 = Draht.
     Schreibt <aus>/drahtmasken.json (Stand, Bilder, Anteil maskierter Pixel, Bilder mit Draht).

VERBRAUCHER (24.11.2026; Schalter OHNE_DRAHTMASKE=1 schaltet ALLE ab = Stand vorher):
  - dichte Wolke: tools/pipeline_objekt.py (Fusion mask_path, auch teilfusion.py --mask_path), tools/wolke_neu_fusionieren.py. Masken auf den ENTZERRTEN Bildern
    dicht/images (gleiche Geometrie wie die Tiefenkarten), Rand 2 px gegen das PatchMatch-Fenster. PatchMatch selbst kennt keine Maske; die Tiefenkarten bleiben,
    nur die Fusion nimmt Drahtpixel nicht mehr auf -> die 'Fahnen' entstehen nicht.
  - Wandbild: tools/fassade_ortho.py (Drahtpixel tragen nicht bei; andere Fotos fuellen; fassade_fein liest die Einzelbilder und sieht dort 'ungueltig').
  - Kantenstufe: tools/stabil_alle.py (Stabilitaetskarte auf Drahtpixeln = 0 -> der Kanten-Sweep sieht dort keine Kante).
ZWISCHENSPEICHER (Muster masken_rechnen in tools/sfm_seiten_vorstufe.py, gleicher Ordner masken_speicher(), RCPARK_MASKEN_CACHE=0 = aus):
  <speicher>/draht_<CODE-STAND drahtmaske.py>_cv<OpenCV>/<sha1 Bildinhalt>_<H>x<W>.png (255 = Draht, ohne Rand). Neue Detektorversion = neuer Ordner."""
import os, sys, json, argparse
from concurrent.futures import ProcessPoolExecutor
import numpy as np, cv2

T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import drahtmaske as DM

BILD_ENDUNGEN = (".jpg", ".jpeg", ".png")


def aktiv():
    return os.environ.get("OHNE_DRAHTMASKE", "0") != "1"


def stand():
    """Kennung der Detektorversion (Inhalt drahtmaske.py + OpenCV-Version) - gehoert in jede Stand-Datei, die Drahtmasken benutzt."""
    import code_stand
    return code_stand.code_stand("drahtmaske.py") + "_cv" + cv2.__version__


def _speicher():
    v = os.environ.get("RCPARK_MASKEN_CACHE", "")
    if v == "0": return None
    from sfm_seiten_vorstufe import masken_speicher
    return os.path.join(masken_speicher(), "draht_" + stand())


def _sha1(p):
    from sfm_seiten_vorstufe import _inhalt_sha1
    return _inhalt_sha1(p)


def maske_fuer(pfad, bild=None, rand_px=0, info=None, himmel=False):
    """Drahtmaske (uint8, 255 = Draht) in der Groesse von `bild` (so geladen, wie der Verbraucher das Foto liest; None = cv2.imread(pfad)).
    himmel=True (nur FUSION, 24.11.2026 Geisterblatt 1122z): zusaetzlich sicherer Himmel (drahtmaske.himmelmaske, Silhouette + Saum bleiben) - Himmelspixel bekamen
    von PatchMatch Tiefen und standen als blaues Blatt vor der Nordwand. Wandbild/Kantenstufe behalten die reine Drahtmaske (Silhouettenkanten liegen am Himmel).
    Mit Zwischenspeicher (Schluessel Bildinhalt + Groesse). OHNE_DRAHTMASKE=1 -> leere Maske."""
    if bild is None: bild = cv2.imread(pfad)
    if bild is None: return None
    H, W = bild.shape[:2]
    if not aktiv(): return np.zeros((H, W), np.uint8)
    C = _speicher(); z = None; m = None
    if C and info is None:
        try: z = os.path.join(C, f"{_sha1(pfad)}_{H}x{W}.png"); m = cv2.imread(z, cv2.IMREAD_GRAYSCALE) if os.path.isfile(z) else None
        except OSError: z = None
    if m is None or m.shape != (H, W):
        m = DM.drahtmaske(bild, info=info)
        if z:
            try: os.makedirs(C, exist_ok=True); cv2.imwrite(z + ".tmp.png", m); os.replace(z + ".tmp.png", z)
            except OSError as e: print(f"HINWEIS Drahtmasken-Zwischenspeicher nicht geschrieben ({e})", flush=True)
    if rand_px > 0: m = cv2.dilate(m, DM._kern(2 * int(rand_px) + 1))
    if himmel: m = np.maximum(m, _himmel_fuer(pfad, bild, C))
    return m


def _himmel_fuer(pfad, bild, C):
    """himmelmaske mit Zwischenspeicher (<sha1>_<H>x<W>_himmel.png); ohne Rand-Aufweitung (der Silhouettensaum ist in himmelmaske festgelegt)."""
    H, W = bild.shape[:2]; z = None; m = None
    if C:
        try: z = os.path.join(C, f"{_sha1(pfad)}_{H}x{W}_himmel.png"); m = cv2.imread(z, cv2.IMREAD_GRAYSCALE) if os.path.isfile(z) else None
        except OSError: z = None
    if m is None or m.shape != (H, W):
        m = DM.himmelmaske(bild)
        if z:
            try: os.makedirs(C, exist_ok=True); cv2.imwrite(z + ".tmp.png", m); os.replace(z + ".tmp.png", z)
            except OSError as e: print(f"HINWEIS Himmelmasken-Zwischenspeicher nicht geschrieben ({e})", flush=True)
    return m


def _eins(args):
    pfad, ziel, colmap, rand, ov = args
    bild = cv2.imread(pfad)
    if bild is None: return os.path.basename(pfad), None
    m = maske_fuer(pfad, bild, rand, himmel=colmap)                        # COLMAP-Format = Fusion -> mit Himmel
    cv2.imwrite(ziel, (255 - m) if colmap else m)
    if ov: cv2.imwrite(os.path.join(ov, os.path.splitext(os.path.basename(pfad))[0] + "_draht.jpg"), DM.overlay(bild, m))
    return os.path.basename(pfad), float((m > 0).mean())


def masken_ordner(bilder, aus, colmap=False, rand_px=0, overlay=None, arbeiter=None, nur=None):
    """Masken fuer alle Bilder eines Ordners -> dict (Bericht, auch als <aus>/drahtmasken.json). Bei OHNE_DRAHTMASKE=1 nichts schreiben, Bericht 'aus'."""
    if not aktiv(): return dict(aus=True)
    os.makedirs(aus, exist_ok=True)
    if overlay: os.makedirs(overlay, exist_ok=True)
    namen = sorted(f for f in os.listdir(bilder) if f.lower().endswith(BILD_ENDUNGEN) and (not nur or f in nur))
    auf = [(os.path.join(bilder, f), os.path.join(aus, (f + ".png") if colmap else (os.path.splitext(f)[0] + ".png")), colmap, rand_px, overlay) for f in namen]
    n = arbeiter or int(os.environ.get("RCPARK_DRAHT_ARBEITER", "0") or 0) or max(1, min(8, (os.cpu_count() or 2) // 2))
    if n > 1 and len(auf) > 1:
        with ProcessPoolExecutor(n) as ex: erg = list(ex.map(_eins, auf, chunksize=4))
    else: erg = [_eins(x) for x in auf]
    ant = {k: v for k, v in erg if v is not None}
    B = dict(stand=stand(), format="colmap (0 = Draht oder Himmel)" if colmap else "255 = Draht", rand_px=rand_px, bilder=len(ant), mit_draht=sum(1 for v in ant.values() if v > 0),
             anteil_mittel=round(float(np.mean(list(ant.values()))) if ant else 0.0, 5), anteil_max=round(max(ant.values(), default=0.0), 4),
             je_bild={k: round(v, 5) for k, v in ant.items() if v > 0})
    json.dump(B, open(os.path.join(aus, "drahtmasken.json"), "w"), indent=1)
    print(f"DRAHTMASKEN {B['mit_draht']} von {B['bilder']} Bildern mit {'Draht oder Himmel' if colmap else 'Draht'}, Anteil im Mittel {B['anteil_mittel']:.2%}, hoechstens {B['anteil_max']:.1%} -> {aus}", flush=True)
    return B


def colmap_masken_aktuell(aus):
    """True, wenn <aus>/drahtmasken.json zum aktuellen Detektorstand passt (sonst neu rechnen)."""
    try: return json.load(open(os.path.join(aus, "drahtmasken.json"))).get("stand") == stand()
    except Exception: return False


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("bilder"); ap.add_argument("--aus", required=True); ap.add_argument("--colmap", action="store_true")
    ap.add_argument("--rand", type=int, default=0); ap.add_argument("--overlay"); ap.add_argument("--arbeiter", type=int, default=0); ap.add_argument("--nur", default="")
    a = ap.parse_args()
    if not aktiv(): print("OHNE_DRAHTMASKE=1 - keine Drahtmasken", flush=True); return 0
    masken_ordner(a.bilder, a.aus, a.colmap, a.rand, a.overlay, a.arbeiter or None, set(x for x in a.nur.split(",") if x) or None); return 0


if __name__ == "__main__":
    sys.exit(main())
