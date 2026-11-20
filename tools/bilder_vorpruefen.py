#!/usr/bin/env python3
"""bilder_vorpruefen.py - Fremdbilder (Commons, Web, Videobilder) vor der SfM pruefen: zeigt das Bild das Objekt? GPU (ALIKED+LightGlue,
gleiche Funktionen wie tools/video_suchen.py) gegen die eigenen Objektfotos; Treffer = >= --min-inlier RANSAC-Inlier (Fundamentalmatrix).
Lehre Schwabentor 2026-11-14: 206 Commons-Bilder lagen geladen herum, nur 49 waren von Hand ausgewaehlt; Innenraeume/Gemaelde stoeren die SfM.
  /media/oem/scan/venv-seg/bin/python -I tools/bilder_vorpruefen.py modelle/<objekt>/objekt.json <ordner_oder_bild>... --aus liste.json [--ref 24] [--min-inlier 60]
Kette (--kette 40, bis 14.11. 6): Nachbarbilder eines Treffers im selben Ordner, die ihn >= min-inlier treffen, zaehlen mit (Videostetigkeit).
Ausgabe: JSON {bild: {inlier, foto}} + Zusammenfassung; Bilder werden auf <= 1000 px (kurze Seite 720) verkleinert geprueft.
ZWISCHENSPEICHER (19.11.2026, Nutzer 'viel Caching'): Ergebnis je Bild (Datei + Groesse + Aenderungszeit) und je Kettenpaar unter
/media/oem/scan/rc-park_daten/_cache/vorpruefen/<schluessel>.json; der Schluessel haengt an den Referenzfotos (Datei, Groesse, Zeit), min-inlier und der
Verfahrensversion - aendert sich eines davon, wird neu gerechnet. Alle 200 Bilder gesichert (Abbruch verliert nichts). --ohne-cache schaltet ab.
"""
import sys, os, json, glob, argparse, time, hashlib
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import video_suchen as VS


CACHE_DIR = os.environ.get("RCPARK_CACHE", "/media/oem/scan/rc-park_daten/_cache"); CACHE_VERSION = "v1-aliked-lg-720-1000"


def bild_id(p):
    """Kennung einer Bilddatei fuer den Zwischenspeicher: echter Pfad + Groesse + Aenderungszeit (Verknuepfungen werden aufgeloest)."""
    try: st = os.stat(p); return f"{os.path.realpath(p)}|{st.st_size}|{int(st.st_mtime)}"
    except OSError: return None


class Speicher:
    """Zwischenspeicher {bild_id: ergebnis} + {paar: inlier} als eine JSON-Datei je Referenzsatz; atomar geschrieben; ohne schreibbaren Ordner still aus."""
    def __init__(self, referenz, min_inlier, an=True):
        self.an = an; self.neu = 0; self.treffer = 0; self.d = dict(bilder={}, paare={})
        if not an: return
        key = hashlib.sha1(json.dumps([CACHE_VERSION, min_inlier, sorted(bild_id(r) or r for r in referenz)]).encode()).hexdigest()[:16]
        self.pfad = os.path.join(CACHE_DIR, "vorpruefen", key + ".json")
        try:
            os.makedirs(os.path.dirname(self.pfad), exist_ok=True)
            if os.path.isfile(self.pfad): self.d = json.load(open(self.pfad))
        except Exception as e: print(f"HINWEIS Zwischenspeicher aus ({e})", flush=True); self.an = False
    def hole(self, art, k):
        v = self.d[art].get(k) if self.an and k else None
        if v is not None: self.treffer += 1
        return v
    def setze(self, art, k, v):
        if not self.an or not k: return
        self.d[art][k] = v; self.neu += 1
        if self.neu % 200 == 0: self.sichern()
    def sichern(self):
        if not self.an or not self.neu: return
        try:
            t = self.pfad + f".tmp{os.getpid()}"; json.dump(self.d, open(t, "w")); os.replace(t, self.pfad)
        except Exception as e: print(f"HINWEIS Zwischenspeicher nicht geschrieben ({e})", flush=True)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--ohne-cache", action="store_true"); ap.add_argument("objekt"); ap.add_argument("quellen", nargs="+"); ap.add_argument("--aus", required=True)
    ap.add_argument("--ref", type=int, default=24); ap.add_argument("--min-inlier", type=int, default=60)
    ap.add_argument("--kette", type=int, default=40,   # 15.11.2026: 6 liess vom Drohnenclip nur 6 von 81 Bildern durch (Dach fehlte); mit allen 81 behielt die Objektregel der Bildwahl 23 -> Kette lang, Aussortieren uebernimmt dicht_bildwahl (>= 60 Objektpunkte)
                     help="Videobilder: Nachbarbilder (<= N Schritte, gleicher Ordner) eines Treffers zaehlen, wenn sie ihn >= min-inlier treffen")
    ap.add_argument("--fenster", type=int, default=12, help="Videobilder: so viele Bilder vor/nach jedem Treffer im selben Clip zaehlen mit, auch ohne Merkmalstreffer (0 = aus)")
    a = ap.parse_args(); t0 = time.time(); op = os.path.abspath(a.objekt); obj = json.load(open(op))
    root = os.path.dirname(os.path.dirname(os.path.dirname(op))); fotos, fd, woher = VS.referenzfotos(obj, root)      # 17.11.2026: .JPG wurde nicht gefunden; Referenz kam nach dem ersten Kettenlauf auch aus Fremdbildern (siehe video_suchen.referenzfotos)
    if not fotos: print(f"FEHLER: kein Objektfoto (.jpg/.jpeg/.png) in {fd} - ohne Referenz waere jedes Fremdbild 'zeigt das Objekt nicht'; {a.aus} NICHT geschrieben"); return 2
    R = VS.sift_ref(fotos[::max(1, len(fotos) // a.ref)][:a.ref]); s = VS._sift(2048)
    if not R: print(f"FEHLER: keines der Referenzfotos aus {fd} lesbar/mit Merkmalen - {a.aus} NICHT geschrieben"); return 2
    bilder = []
    for q in a.quellen:
        bilder += [q] if os.path.isfile(q) else sorted(p for p in glob.glob(os.path.join(q, "**", "*"), recursive=True) if p.lower().endswith((".jpg", ".jpeg", ".png", ".webp")))
    print(f"{len(R)} Referenzfotos aus {fd} [{woher}], {len(bilder)} Bilder (GPU {VS.DEV})", flush=True)
    erg = {}; SP = Speicher([r[0] for r in R], a.min_inlier, not a.ohne_cache); ZU = None if os.environ.get("RCPARK_VORPRUEFEN_ALLE") == "1" else {}   # 20.11.2026: letzter Treffer zuerst + Abbruch beim ersten Treffer (VS.treffer); RCPARK_VORPRUEFEN_ALLE=1 = alter Stand (bester Wert ueber alle Referenzfotos)
    for p in bilder:
        bid = bild_id(p); alt = SP.hole("bilder", bid)
        if alt is not None: erg[p] = dict(alt); continue
        g = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
        if g is None: erg[p] = dict(inlier=0, foto=None, fehler="nicht lesbar"); continue
        k = min(1.0, 720 / min(g.shape), 1000 / max(g.shape)); g = cv2.resize(g, None, fx=k, fy=k, interpolation=cv2.INTER_AREA) if k < 1 else g
        n, ref = VS.treffer(g, R, None, s, a.min_inlier, ZU); erg[p] = dict(inlier=int(n), foto=ref); SP.setze("bilder", bid, dict(erg[p]))
    n_direkt = SP.treffer; print(f"Zwischenspeicher: {n_direkt} von {len(bilder)} Bildern uebernommen, {len(bilder) - n_direkt} neu gerechnet", flush=True)
    # Kette (Lehre Schwabentor 2026-11-14): Drohnenbilder der Turmspitze (vf_004..007) haben 0 Inlier gegen Strassenfotos, ueberlappen aber
    # stark mit den Nachbarbildern vf_000..003 -> nur 1 von 80 Drohnenbildern kam durch. Stetigkeit im Video = Beleg fuer dasselbe Objekt.
    if a.kette > 0:
        from collections import defaultdict
        ordner = defaultdict(list)
        for p in bilder: ordner[os.path.dirname(p)].append(p)
        cache = {}
        def mk(p):
            if p not in cache:
                g = cv2.imread(p, cv2.IMREAD_GRAYSCALE); k = min(1.0, 720 / min(g.shape), 1000 / max(g.shape))
                g = cv2.resize(g, None, fx=k, fy=k, interpolation=cv2.INTER_AREA) if k < 1 else g; cache[p] = VS._merkmale(s, g)
            return cache[p]
        for d, L in ordner.items():
            L = sorted(L); schritt = {p: 0 for p in L if erg[p]["inlier"] >= a.min_inlier}; offen = list(schritt)
            while offen:
                q = offen.pop(); i = L.index(q)
                if schritt[q] >= a.kette: continue
                for j in (i - 1, i + 1):
                    if not 0 <= j < len(L) or L[j] in schritt: continue
                    ia, ib = bild_id(L[j]), bild_id(q); pk = f"{ia}>{ib}" if ia and ib else None; n = SP.hole("paare", pk)
                    if n is None:
                        P0, f0 = mk(L[j]); P1, f1 = mk(q)
                        with VS.torch.inference_mode() if hasattr(VS, "torch") else __import__("torch").inference_mode():
                            m = VS._LG["m"]({"image0": f0, "image1": f1})["matches"][0].cpu().numpy()
                        n = 0
                        if len(m) >= a.min_inlier:
                            F, msk = cv2.findFundamentalMat(P0[m[:, 0]], P1[m[:, 1]], cv2.FM_RANSAC, 3.0, 0.999); n = int(msk.sum()) if msk is not None else 0
                        SP.setze("paare", pk, n)
                    if n >= a.min_inlier:
                        schritt[L[j]] = schritt[q] + 1; offen.append(L[j])
                        erg[L[j]].update(inlier_kette=n, kette_von=os.path.basename(q), kette_schritt=schritt[L[j]], inlier_direkt=erg[L[j]]["inlier"], inlier=a.min_inlier)
            cache.clear()
        print(f"Kette: {sum('kette_von' in e for e in erg.values())} Nachbarbilder dazu ({SP.treffer - n_direkt} Paare aus dem Zwischenspeicher)", flush=True)
    # ZEITFENSTER (19.11.2026, Martinstor: 568 Kameras auf einer Turmseite, 4 dahinter - und die blicken vom Turm weg). Die Pruefung vergleicht mit den Objektfotos; zeigen die
    # alle DIESELBE Seite, faellt jedes Bild der Gegenseite durch ('zeigt das Objekt nicht'), auch im Videoclip, der durch das Tor geht - die Kette oben reisst im dunklen Durchgang.
    # Regel: in einem Videoclip zaehlen die --fenster Bilder vor und nach jedem Treffer mit (der Clip ist am Objekt; ob das Bild taugt, entscheidet die SfM). Nur Videobilder (vf_NNN).
    if a.fenster > 0:
        from collections import defaultdict
        ordner = defaultdict(list); n_f = 0
        for p in bilder:
            if "vf_" in os.path.basename(p): ordner[os.path.dirname(p)].append(p)
        for d, L in ordner.items():
            L = sorted(L); tr = [i for i, p in enumerate(L) if erg[p]["inlier"] >= a.min_inlier and "fenster_von" not in erg[p]]
            if not tr: continue
            nah = np.zeros(len(L), bool)
            for i in tr: nah[max(0, i - a.fenster):i + a.fenster + 1] = True
            for j in np.where(nah)[0]:
                e = erg[L[j]]
                if e["inlier"] < a.min_inlier and not e.get("fehler"):
                    k = min(tr, key=lambda i: abs(i - j)); e.update(inlier_direkt=e["inlier"], fenster_von=os.path.basename(L[k]), fenster_abstand=int(abs(k - j)), inlier=a.min_inlier); n_f += 1
        print(f"Zeitfenster: {n_f} Videobilder im Abstand <= {a.fenster} Bilder zu einem Treffer dazu (Gegenseite/Durchgang; die SfM entscheidet)", flush=True)
    SP.sichern()
    ja = [p for p, e in erg.items() if e["inlier"] >= a.min_inlier]
    json.dump(dict(objekt=op, min_inlier=a.min_inlier, referenz=[r[0] for r in R], treffer=len(ja), bilder=erg), open(a.aus, "w"), indent=1, ensure_ascii=False)
    print(f"{len(ja)} von {len(bilder)} zeigen das Objekt (>= {a.min_inlier} Inlier), {time.time() - t0:.0f} s -> {a.aus}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
