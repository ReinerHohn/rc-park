#!/usr/bin/env python3
"""seiten_luecken.py <objekt.json> <fassaden-ordner> --sparse <SfM-Ordner mit images.bin> --ref-db <db.db> [--schwelle 0.2] [--min_m2 40] [--holen] [--download]

TOR + AUFTRAG: Welche Wand zeigt kein Foto - und woher kommen Fotos dafuer?
Nutzer 16.11.2026 (Schwabentor Ostseite): "Warum wurde es nicht automatisch gefunden? Er muss doch wissen, dass dort Bilder fehlen und die sich dann holen,
notfalls downloaden." Bisher meldete tools/kamera_abdeckung.py nur die Luecke im Kamerakranz (seit 14.11. bekannt) - niemand handelte danach.
Ablauf:
  1. Je Wand aus <fassaden-ordner>/fassaden.json (tools/fassade_ortho.py): Anteil der Wandzellen mit Bilddaten in ortho_fNN.png. < --schwelle = UNGESEHEN.
  2. Fotobestand (objekt.json fotos_dir) gegen die registrierten Bilder des SfM (images.bin) abgleichen -> Liste der NICHT registrierten Fotos (Kandidaten).
  3. Skript <audit>/seiten_luecken_holen.sh schreiben: Kandidaten mit ALIKED+LightGlue gegen das Netz nachregistrieren
     (tools/zusatzfotos_registrieren.py vorbereiten/merkmale/registrieren, tools/zusatzfotos_lightglue.py refnamen/paare/einlesen), Zielordner <daten>/seiten_nachholen.
     --download: davor ALLE freien Quellen: tools/commons_harvest.py (Geosuche 250 m + Namenssuche), tools/online_ansichten_holen.py (Hochblicke auf Commons),
     tools/openverse_holen.py (Flickr u. a., nur CC0/BY/BY-SA) nach <daten>/seiten_nachholen/{commons,hochblick,openverse}; Mapillary/Google NICHT (Lizenz, LIZENZ_WERKZEUGE.md);
     diese Bilder kommen zu den Kandidaten.
     --holen: das Skript sofort ausfuehren (GPU; nur ueber tools/job_start.sh starten, wenn es lange laeuft).
  4. Bericht <audit>/seiten_luecken.json. Exit-Code 3, solange eine Wand ungesehen ist.
Letzter Skriptschritt: tools/kameras_nachtragen.py (K-Dateien im Modellrahmen). Danach je ungesehener Wand: registrierte Neuzugaenge -> fassade_ortho/fassade_fein neu; bleibt ein Foto unregistriert, das die Wand zeigt (Kontaktbogen
<audit>/seiten_luecken_kandidaten.jpg ANSEHEN): Kamera aus gemessenen Modellpunkten + tools/fassade_ein_foto.py (modelle/PIPELINE_FASSADEN.md "Ungesehene Seite").
Grenze: Schritt 1 braucht einen fassade_ortho-Lauf; ob ein Kandidat die Wand wirklich zeigt, entscheidet erst die Registrierung bzw. der Blick auf den Kontaktbogen.
"""
import sys, os, json, glob, struct, argparse, subprocess, numpy as np, cv2


def registrierte(sparse):
    namen = []
    with open(os.path.join(sparse, "images.bin"), "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        for _ in range(n):
            f.read(4 + 32 + 24 + 4); b = b""
            while True:
                c = f.read(1)
                if c == b"\x00": break
                b += c
            k = struct.unpack("<Q", f.read(8))[0]; f.read(24 * k); namen.append(b.decode())
    return namen


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("fassaden"); ap.add_argument("--sparse", required=True); ap.add_argument("--ref-db", required=True); ap.add_argument("--schwelle", type=float, default=0.2)
    ap.add_argument("--min_m2", type=float, default=40.0); ap.add_argument("--holen", action="store_true"); ap.add_argument("--download", action="store_true"); a = ap.parse_args()
    od = os.path.dirname(os.path.abspath(a.objekt)); root = os.path.dirname(os.path.dirname(od)); obj = json.load(open(a.objekt)); audit = os.path.join(root, obj.get("audit", os.path.join(od, "audit"))); os.makedirs(audit, exist_ok=True)
    FJ = json.load(open(os.path.join(a.fassaden, "fassaden.json"))); waende = []
    for i, F in enumerate(FJ["fassaden"]):
        if F.get("flaeche_m2", 0) < a.min_m2: continue
        p = os.path.join(a.fassaden, f"ortho_f{i:02d}.png"); R = F["raster"]; maske = np.zeros((R["nz"], R["nu"]), np.uint8)
        for poly in F["polys_uz"]: cv2.fillPoly(maske, [np.array([[(u - R["u0"]) / R["zelle"], (R["z1"] - z) / R["zelle"]] for u, z in poly], np.int32)], 1)
        im = cv2.imread(p); daten = (im.max(2) > 8) if im is not None else np.zeros(maske.shape, bool); ant = float((daten & (maske > 0)).sum() / max(maske.sum(), 1))
        waende.append(dict(nr=i, normale=F["n"], mitte=F["o"], flaeche_m2=F["flaeche_m2"], abdeckung=round(ant, 3), fotos=len(F.get("fotos", {})), ungesehen=ant < a.schwelle))
        print(f"Wand f{i:02d}: Normale ({F['n'][0]:+.2f}, {F['n'][1]:+.2f}), {F['flaeche_m2']:.0f} m2, {ant * 100:5.1f} % mit Bilddaten aus {len(F.get('fotos', {}))} Fotos" + ("   <-- UNGESEHEN" if ant < a.schwelle else ""))
    reg = set(os.path.splitext(os.path.basename(n))[0] for n in registrierte(a.sparse)); fd = os.path.join(root, obj["fotos_dir"]); alle = sorted(f for f in glob.glob(os.path.join(fd, "*")) if f.lower().endswith((".jpg", ".jpeg", ".png")))
    kand = [f for f in alle if os.path.splitext(os.path.basename(f))[0] not in reg]; print(f"Fotobestand {len(alle)}, im SfM registriert {len(alle) - len(kand)}, NICHT registriert {len(kand)}")
    ung = [w for w in waende if w["ungesehen"]]; daten = os.path.join("/media/oem/scan/rc-park_daten", os.path.basename(od)); Z = os.path.join(daten, "seiten_nachholen"); T = os.path.join(root, "tools"); VC = "/media/oem/scan/venv-colmap/bin/python -I"; VS = "/media/oem/scan/venv-seg/bin/python -I"
    zeilen = ["#!/bin/bash", "# erzeugt von tools/seiten_luecken.py - Kandidaten fuer ungesehene Waende nachregistrieren", "set -e", f"mkdir -p {Z}/roh"]
    if a.download and obj.get("koordinate_utm"):
        from pyproj import Transformer
        lon, lat = Transformer.from_crs("EPSG:25832", "EPSG:4326", always_xy=True).transform(*obj["koordinate_utm"][:2])
        zeilen.append(f"{VS} {T}/commons_harvest.py --lat {lat:.6f} --lon {lon:.6f} --radius 250 --max 300 --search \"{obj.get('name', '')} {obj.get('ort', '')}\" --out {Z}/commons   # freie Lizenzen, manifest.json")
        nm = f"{obj.get('name', '')} {obj.get('ort', '').split(' im ')[0]}".strip(); ort = obj.get("ort", "").split(" im ")[0]
        zeilen.append(f"python3 {T}/online_ansichten_holen.py --aus {Z}/hochblick --suche \"{nm}\" \"{ort} Luftbild\" \"{ort} Panorama\" --max 40 || true   # Hochblicke (Commons): sehen Seiten ueber Nachbardaechern")
        zeilen.append(f"python3 {T}/openverse_holen.py --aus {Z}/openverse --suche \"{nm}\" \"{obj.get('name', '')}\" \"{ort} Altstadt Blick\" --max 150 || true   # Flickr u. a. ueber Openverse, nur CC0/BY/BY-SA")
        zeilen.append(f"for f in {Z}/commons/*.jpg {Z}/hochblick/orig/*.jpg {Z}/openverse/*.jpg; do [ -e \"$f\" ] && ln -sf \"$f\" {Z}/roh/dl_$(basename $(dirname \"$f\"))__$(basename \"$f\"); done")
    zeilen += [f"ln -sf \"{f}\" {Z}/roh/" for f in kand]
    zeilen += [f"{VC} {T}/zusatzfotos_registrieren.py vorbereiten --fotos {Z}/roh --aus {Z} --unten 0.0", f"{VC} {T}/zusatzfotos_registrieren.py merkmale --ref-db {a.ref_db} --sparse {a.sparse} --aus {Z}",
               f"{VC} {T}/zusatzfotos_lightglue.py refnamen --ziel {Z} --ref-sparse {a.sparse}", f"{VS} {T}/zusatzfotos_lightglue.py paare --ziel {Z} --ref-sparse {a.sparse} --ref-bilder {fd}",
               f"{VC} {T}/zusatzfotos_lightglue.py einlesen --ziel {Z} --ref-sparse {a.sparse}", f"{VC} {T}/zusatzfotos_registrieren.py registrieren --sparse {Z}/lg/ref_tri --aus {Z}/lg --je-bild --kalibrieren", f"{VC} {T}/kameras_nachtragen.py {os.path.abspath(a.objekt)} {Z}/lg/sparse_handy/0 --bilder {Z}/roh   # neue Posen als K-Dateien in den Modellrahmen (Gegenprobe gegen vorhandene Kameras)", "echo NACHHOLEN_FERTIG"]
    sk = os.path.join(audit, "seiten_luecken_holen.sh"); open(sk, "w").write("\n".join(zeilen) + "\n"); os.chmod(sk, 0o755)
    if ung and kand:                                                          # Kontaktbogen der Kandidaten zum Ansehen
        Tn = 200; kacheln = []
        for f in kand[:120]:
            im = cv2.imread(f)
            if im is None: continue
            s = Tn / max(im.shape[:2]); im = cv2.resize(im, (max(int(im.shape[1] * s), 1), max(int(im.shape[0] * s), 1)), interpolation=cv2.INTER_AREA); c = np.zeros((Tn, Tn, 3), np.uint8); c[:im.shape[0], :im.shape[1]] = im
            cv2.putText(c, os.path.splitext(os.path.basename(f))[0][-14:], (2, Tn - 5), 0, 0.4, (0, 255, 255), 1); kacheln.append(c)
        while len(kacheln) % 10: kacheln.append(np.zeros((Tn, Tn, 3), np.uint8))
        if kacheln: cv2.imwrite(os.path.join(audit, "seiten_luecken_kandidaten.jpg"), np.vstack([np.hstack(kacheln[i:i + 10]) for i in range(0, len(kacheln), 10)]))
    json.dump(dict(waende=waende, ungesehen=[w["nr"] for w in ung], fotobestand=len(alle), nicht_registriert=[os.path.basename(f) for f in kand], skript=sk, zielordner=Z), open(os.path.join(audit, "seiten_luecken.json"), "w"), indent=1)
    if not ung: print("alle Waende gesehen"); return 0
    print(f"UNGESEHEN: {', '.join('f%02d' % w['nr'] for w in ung)} -> {len(kand)} nicht registrierte Fotos als Kandidaten; Skript {sk}" + ("" if a.holen else "  (mit --holen ausfuehren; --download holt zusaetzlich Commons-Fotos)"))
    if a.holen:
        rc = subprocess.call(["bash", sk])
        if rc: print("Nachholen abgebrochen, rc", rc)
    return 3


if __name__ == "__main__":
    sys.exit(main())
