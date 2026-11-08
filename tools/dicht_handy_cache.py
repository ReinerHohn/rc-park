#!/usr/bin/env python3
"""dicht_handy_cache.py - Tiefenkarten-Cache fuer dicht_handy.py (Entwurf 2026-11-06, noch NICHT in dicht_handy.py eingehaengt).

Ziel: Wiederholungslaeufe rechnen per COLMAP-PatchMatch nur NEUE oder GEAENDERTE Bilder; unveraenderte Bilder liefern ihre Tiefen-/Normalenkarten aus dem Cache.
Grundsatz: lieber Fehltreffer als veraltete Karte. Alles, was das Ergebnis eines Bildes beeinflussen kann, steckt im Schluessel.

Was PatchMatch (geom_consistency) je Referenzbild liest (COLMAP-Quellcode-Wissen, ANNAHME bis zum GPU-Beweis):
  - das entzerrte Bild selbst + Kamera + Pose,
  - die Quellbilder aus patch-match.cfg (Bild, Kamera, Pose) und, fuer die geometrische Konsistenz, deren PHOTOMETRISCHE Tiefen-/Normalenkarten.
    Diese wiederum haengen nur von Bild/Pose/Partnerliste (+ Bilder/Posen der Partner) und dem Tiefenbereich ab, nicht von weiteren Tiefenkarten.
    => Schluessel = Hash ueber 2 Stufen des Partnergraphen (Partner und Partner-der-Partner, je mit Bild-Hash, Pose, Kamera, Tiefenbereichs-Fingerabdruck).
  - Tiefenbereich depth_min/max (-1 = automatisch aus den vom Bild gesehenen Sparse-Punkten) -> Fingerabdruck der Sparse-Punkte, die das Bild sieht.
  - PatchMatch-Optionen (alle ausser gpu_index/num_threads/cache_size, die das Ergebnis nicht aendern sollen: ANNAHME), pycolmap-Version.
  - Maske (nur optional, mit_maske=True; Standard True = sicher). dicht_handy.fusionieren maskiert NACH PatchMatch: speichert man die Karten VOR der Maske
    (siehe Einhaengen), darf mit_maske=False gesetzt werden (dann gibt eine Maskenaenderung keinen Fehltreffer).
Ablage: <cache>/<schluessel>/{depth_geometric.bin, depth_photometric.bin, normal_geometric.bin, normal_photometric.bin, manifest.json}; <cache>/index.json.
Rueckholen wird mit sha256 aus dem Manifest geprueft (Bitrot/halbe Dateien -> Fehltreffer). Eintraege werden atomar (tmp + rename) geschrieben.
Es wird KOPIERT, nie hartverlinkt: dicht_handy.fusionieren oeffnet depth_maps/*.bin mit "wb" (Maskierung in place) und wuerde sonst den Cache zerstoeren.
Nichts wird geloescht; Platz-/LRU-Aufraeumen nur als Bericht (bericht).
Aufruf: /media/oem/scan/venv-colmap/bin/python -I tools/dicht_handy_cache.py plan|fuellen|bericht --arbeit W --cache DIR [--max-size N]
Lizenz: nur eigener Code + pycolmap (BSD).
"""
import os, sys, json, hashlib, shutil, struct, time, argparse, fcntl, contextlib

FORMAT = 1
OPT_AUSGENOMMEN = ("gpu_index", "num_threads", "cache_size", "summary")
ARTEN = ("geometric", "photometric")
# (Cache-Datei, Unterordner in W/stereo, Dateiname in COLMAP)
DATEIEN = [("depth_geometric.bin", "depth_maps", "{n}.geometric.bin"), ("depth_photometric.bin", "depth_maps", "{n}.photometric.bin"),
           ("normal_geometric.bin", "normal_maps", "{n}.geometric.bin"), ("normal_photometric.bin", "normal_maps", "{n}.photometric.bin")]


def cache_pfad(objekt, basis="/media/oem/scan/rc-park_daten"):
    """Standardort; objekt ist Argument (nichts Objektspezifisches im Code)."""
    return os.path.join(basis, objekt, "tiefen_cache")


def sha(pfad, block=1 << 22):
    h = hashlib.sha256()
    with open(pfad, "rb") as f:
        while True:
            b = f.read(block)
            if not b: break
            h.update(b)
    return h.hexdigest()


def _h(*teile):
    h = hashlib.sha256()
    for t in teile:
        b = t if isinstance(t, bytes) else json.dumps(t, sort_keys=True, separators=(",", ":")).encode()
        h.update(struct.pack("<Q", len(b))); h.update(b)
    return h.hexdigest()


def _fl(xs):
    return [struct.pack("<d", float(x)).hex() for x in xs]                 # exakte Gleitkommadarstellung, keine Rundung


# ---------------------------------------------------------------- Beschreibung eines Stapels (pycolmap nur hier)
def lese_cfg(cfg):
    """patch-match.cfg -> [(ref, [quellen...])] in Dateireihenfolge."""
    z = [l.strip() for l in open(cfg) if l.strip()]
    if len(z) % 2: raise ValueError(f"{cfg}: ungerade Zeilenzahl")
    return [(z[i], [s.strip() for s in z[i + 1].split(",") if s.strip()]) for i in range(0, len(z), 2)]


def beschreibe_stapel(W, maske_dir=None):
    """Liest entzerrtes Sparse-Modell + Bilder + cfg eines Arbeitsordners W und liefert reine Daten (JSON-faehig):
    {'bilder': {name: {bild, kamera, pose, punkte, maske}}, 'partner': {name: [quellen]}}. Reihenfolge der Partner bleibt erhalten."""
    import pycolmap
    rec = pycolmap.Reconstruction(os.path.join(W, "sparse"))
    cfg = lese_cfg(os.path.join(W, "stereo", "patch-match.cfg")); partner = {r: q for r, q in cfg}
    brauch = set(partner) | {s for q in partner.values() for s in q}
    maske_dir = maske_dir or os.path.join(W, "masken_ud", "images")
    bilder = {}
    for im in rec.images.values():
        if im.name not in brauch: continue
        c = im.camera; r = im.cam_from_world()
        pts = []
        for p in im.points2D:
            if p.has_point3D(): pts.append(tuple(rec.points3D[p.point3D_id].xyz))
        pts.sort()
        mp = os.path.join(maske_dir, im.name)
        bilder[im.name] = dict(bild=sha(os.path.join(W, "images", im.name)),
                               kamera=[c.model.name if hasattr(c.model, "name") else str(c.model), int(c.width), int(c.height)] + _fl(c.params),
                               pose=_fl(list(r.rotation.quat) + list(r.translation)),
                               punkte=_h(*[_fl(p) for p in pts]) if pts else "keine",
                               maske=sha(mp) if os.path.exists(mp) else None)
    fehlt = sorted(brauch - set(bilder))
    if fehlt: raise ValueError(f"Bilder im Modell/cfg nicht gefunden: {fehlt[:5]}")
    return dict(bilder=bilder, partner=partner)


def optionen_dict(opt):
    """PatchMatchOptions -> dict ohne Felder, die das Ergebnis nicht aendern sollen."""
    d = dict(opt.todict()) if hasattr(opt, "todict") else dict(opt)
    for k in OPT_AUSGENOMMEN: d.pop(k, None)
    return d


# ---------------------------------------------------------------- Schluessel (reine Funktion, ohne pycolmap)
def _eigen(b, mit_maske):
    return dict(bild=b["bild"], kamera=b["kamera"], pose=b["pose"], punkte=b["punkte"], **({"maske": b["maske"]} if mit_maske else {}))


def schluessel(name, besch, optionen, colmap_version, mit_maske=True):
    """Schluessel eines Bildes. Aendert sich bei JEDER Aenderung von: eigenem Bild/Kamera/Pose/Sparse-Punkten (/Maske), Optionen, COLMAP-Version, Partnerliste
    (Reihenfolge inkl.), Bild/Kamera/Pose/Punkten der Partner und deren Partnerlisten samt Bild/Pose der Partner-Partner."""
    B, P = besch["bilder"], besch["partner"]

    def stufe(n):                                                          # was die photometrische Karte von n bestimmt
        q = P.get(n, [])
        return dict(ich=_eigen(B[n], False), quellen=[[s, _eigen(B[s], False)] for s in q])
    q = P.get(name, [])
    return _h(dict(format=FORMAT, colmap=colmap_version, optionen=optionen, ich=_eigen(B[name], mit_maske)),
              dict(quellen=[[s, stufe(s)] for s in q]))


def alle_schluessel(besch, optionen, colmap_version, mit_maske=True):
    return {n: schluessel(n, besch, optionen, colmap_version, mit_maske) for n in besch["partner"]}


# ---------------------------------------------------------------- Cache
@contextlib.contextmanager
def _sperre(cache):
    os.makedirs(cache, exist_ok=True)
    with open(os.path.join(cache, ".lock"), "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try: yield
        finally: fcntl.flock(lf, fcntl.LOCK_UN)


def _index_lesen(cache):
    p = os.path.join(cache, "index.json")
    return json.load(open(p)) if os.path.exists(p) else {}


def _index_schreiben(cache, idx):
    p = os.path.join(cache, "index.json"); t = p + ".tmp"
    json.dump(idx, open(t, "w"), indent=1); os.replace(t, p)


def quell_pfade(W, n):
    return [(c, os.path.join(W, "stereo", sub, fn.format(n=n))) for c, sub, fn in DATEIEN]


def speichern(cache, key, W, name, tag=""):
    """Legt die 4 Karten des Bildes unter key ab. Fehlt eine Datei -> nichts wird gespeichert (False). Existierender Eintrag bleibt unveraendert."""
    quellen = quell_pfade(W, name)
    if not all(os.path.exists(p) for _, p in quellen): return False
    with _sperre(cache):
        ziel = os.path.join(cache, key)
        if os.path.isdir(ziel): return True
        tmp = os.path.join(cache, f".tmp_{key}_{os.getpid()}"); shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
        man = {}
        for c, p in quellen:
            shutil.copyfile(p, os.path.join(tmp, c)); man[c] = dict(sha256=sha(os.path.join(tmp, c)), bytes=os.path.getsize(os.path.join(tmp, c)))
            os.chmod(os.path.join(tmp, c), 0o444)
        json.dump(dict(format=FORMAT, key=key, bild=name, tag=tag, dateien=man, erzeugt=time.time()), open(os.path.join(tmp, "manifest.json"), "w"), indent=1)
        os.rename(tmp, ziel)
        idx = _index_lesen(cache); idx[key] = dict(bild=name, tag=tag, bytes=sum(m["bytes"] for m in man.values()), erzeugt=time.time(), zuletzt=time.time())
        _index_schreiben(cache, idx)
    return True


def gueltig(cache, key):
    """Eintrag vorhanden UND alle Dateien stimmen mit dem Manifest (Groesse+sha256) ueberein."""
    d = os.path.join(cache, key); mp = os.path.join(d, "manifest.json")
    if not os.path.exists(mp): return False
    try:
        m = json.load(open(mp))
        if m.get("format") != FORMAT or m.get("key") != key: return False
        for c, info in m["dateien"].items():
            p = os.path.join(d, c)
            if not os.path.exists(p) or os.path.getsize(p) != info["bytes"] or sha(p) != info["sha256"]: return False
        return set(m["dateien"]) == {c for c, _, _ in DATEIEN}
    except Exception:
        return False


def einsetzen(cache, key, W, name):
    """Kopiert (nicht hartverlinken!) die Karten in W/stereo. Atomar je Datei. True bei Erfolg."""
    if not gueltig(cache, key): return False
    for c, p in quell_pfade(W, name):
        os.makedirs(os.path.dirname(p), exist_ok=True); t = p + ".cachetmp"
        shutil.copyfile(os.path.join(cache, key, c), t); os.replace(t, p)
    with _sperre(cache):
        idx = _index_lesen(cache)
        if key in idx: idx[key]["zuletzt"] = time.time(); _index_schreiben(cache, idx)
    return True


def cfg_filtern(cfg_in, cfg_out, fehlend):
    """Schreibt nur die Referenzbilder aus 'fehlend' (Quellenzeilen unveraendert). Rueckgabe Anzahl."""
    fehlend = set(fehlend); n = 0
    with open(cfg_out, "w") as f:
        for r, q in lese_cfg(cfg_in):
            if r in fehlend: f.write(f"{r}\n{', '.join(q)}\n"); n += 1
    return n


def vor_patchmatch(W, opt, cache, mit_maske=True):
    """Vor patch_match_stereo je Stapel: Treffer einsetzen, gefilterte cfg schreiben. Rueckgabe dict(cfg=Pfad der cfg fuer PatchMatch, keys, treffer, fehlend).
    Wenn alle Bilder Treffer sind: cfg=None (PatchMatch ueberspringen)."""
    import pycolmap
    cfg0 = os.path.join(W, "stereo", "patch-match.cfg"); besch = beschreibe_stapel(W)
    keys = alle_schluessel(besch, optionen_dict(opt), pycolmap.__version__, mit_maske)
    if os.path.exists(cfg0 + ".voll") is False: shutil.copyfile(cfg0, cfg0 + ".voll")      # Original bleibt erhalten (Nachvollziehbarkeit)
    treffer, fehlend = [], []
    for n, k in keys.items():
        (treffer if einsetzen(cache, k, W, n) else fehlend).append(n)
    cfg_f = os.path.join(W, "stereo", "patch-match.fehlend.cfg"); nf = cfg_filtern(cfg0 + ".voll", cfg_f, fehlend)
    return dict(cfg=cfg_f if nf else None, keys=keys, treffer=sorted(treffer), fehlend=sorted(fehlend))


def nach_patchmatch(W, cache, vor, tag=""):
    """Speichert die frisch gerechneten Karten der fehlenden Bilder (VOR der Maskierung/Fusion aufrufen!). Rueckgabe Liste gespeicherter Bilder."""
    return [n for n in vor["fehlend"] if speichern(cache, vor["keys"][n], W, n, tag)]


def bericht(cache, budget_gb=None):
    """Nur Bericht/Vorschlag, loescht nichts: Groesse, Eintraege, LRU-Reihenfolge, Vorschlag welche Eintraege ueber dem Budget lagen."""
    idx = _index_lesen(cache); gesamt = sum(v["bytes"] for v in idx.values()); lru = sorted(idx.items(), key=lambda kv: kv[1]["zuletzt"])
    vorschlag, rest = [], gesamt
    if budget_gb is not None:
        for k, v in lru:
            if rest <= budget_gb * 1e9: break
            vorschlag.append(dict(key=k, bild=v["bild"], bytes=v["bytes"])); rest -= v["bytes"]
    return dict(eintraege=len(idx), gesamt_gb=gesamt / 1e9, pro_bild_mb=(gesamt / len(idx) / 1e6) if idx else None, budget_gb=budget_gb,
                vorschlag_loeschen_lru=vorschlag, hinweis="nur Vorschlag; Loeschen nur durch Nutzer-Skript")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("befehl", choices=["plan", "fuellen", "bericht"]); ap.add_argument("--arbeit"); ap.add_argument("--cache", required=True)
    ap.add_argument("--max-size", type=int, default=1600); ap.add_argument("--ohne-maske", action="store_true"); ap.add_argument("--budget-gb", type=float, default=None)
    a = ap.parse_args()
    if a.befehl == "bericht": print(json.dumps(bericht(a.cache, a.budget_gb), indent=1)); return
    import pycolmap
    opt = pycolmap.PatchMatchOptions(); opt.max_image_size = a.max_size; opt.geom_consistency = True
    besch = beschreibe_stapel(a.arbeit); keys = alle_schluessel(besch, optionen_dict(opt), pycolmap.__version__, not a.ohne_maske)
    if a.befehl == "plan":                                                  # nur lesen
        t = [n for n, k in keys.items() if gueltig(a.cache, k)]
        print(json.dumps(dict(bilder=len(keys), treffer=len(t), fehlend=sorted(set(keys) - set(t))), indent=1))
    else:                                                                   # fuellen: fertige Karten aus einem Arbeitsordner einlesen (nur kopieren)
        print(json.dumps(dict(gespeichert=[n for n, k in keys.items() if speichern(a.cache, k, a.arbeit, n, os.path.basename(a.arbeit.rstrip('/')))]), indent=1))


if __name__ == "__main__":
    main()
