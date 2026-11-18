#!/usr/bin/env python3
"""dicht_bildwahl.py <sparse_ein> <sparse_aus> - Bildauswahl fuer die dichte Wolke (Tiefenkarten = teuerster Schritt).
Lehre Schwabentor 2026-11-14 (Nutzer: 'koennen wir nicht weiter beschleunigen?'): ~580 Bilder, davon Fernansichten der Stadt und fast gleiche
Videobilder - jede Tiefenkarte kostet gleich viel, traegt am Objekt aber wenig bei. Regeln (allgemein, kein Objektwissen noetig):
  1. Objektmitte = Median der 3D-Punkte mit Spur >= 5 (meistgesehene Struktur).
  2. Objektkern = ZYLINDER: Punkte bis zum --kern-Perzentil des WAAGERECHTEN Abstands zur Lotachse durch die Mitte (jede Hoehe, auch Dach). Bild behalten, wenn es >= --min_kern Kernpunkte beobachtet
     und der Abstand <= --fern x Median-Abstand ist. (Erst 'Mitte im Bild' getestet: warf 66 von 178 alten Bildern weg, darunter Nahaufnahmen.)
  3. Videobilder ('<clip>__vf_NNN'): nur behalten, wenn sich die Kamera seit dem letzten behaltenen Bild >= --schritt x Median-Abstand
     bewegt oder >= --winkel Grad gedreht hat.
Abgewaehlte Bilder werden im Ausgabemodell abgemeldet (Frame deregistriert); die SfM selbst bleibt unveraendert. Bericht dicht_bildwahl.json.
"""
import sys, os, re, json, argparse
import numpy as np, pycolmap


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("ein"); ap.add_argument("aus")
    ap.add_argument("--fern", type=float, default=40.0); ap.add_argument("--max_bilder", type=int, default=0); ap.add_argument("--kern", type=float, default=80); ap.add_argument("--min_kern", type=int, default=60); ap.add_argument("--schritt", type=float, default=0.03); ap.add_argument("--winkel", type=float, default=4.0)
    a = ap.parse_args(); r = pycolmap.Reconstruction(a.ein)
    P = np.array([p.xyz for p in r.points3D.values() if p.track.length() >= 5]); mitte = np.median(P, 0)
    # OBJEKT = ZYLINDER um die Lotachse durch die Mitte (15.11.2026, Nutzer: "kein Spezialfall von oben - Bilder, die das Objekt zeigen, sollen in die Wolke").
    # Vorher Kugel um die Mitte: das Dach lag ausserhalb, Drohnen-/Hangbilder sahen 0 "Kernpunkte" und flogen raus (20 von 22 hohen Kameras, Dach ohne Punkte).
    # Lot = Normale der Kameraebene (Kern der Kameras), Radius = --kern-Perzentil des WAAGERECHTEN Abstands; die Hoehe ist frei.
    Cc = np.array([np.asarray(r.images[i].projection_center()) for i in r.reg_image_ids()]); cmed = np.median(Cc, 0); dk = np.linalg.norm(Cc - cmed, axis=1); kk = dk <= np.percentile(dk, 70)
    up = np.linalg.svd(Cc[kk] - Cc[kk].mean(0))[2][2]
    hor = lambda X: np.linalg.norm((X - mitte) - np.outer((X - mitte) @ up, up), axis=1)
    rk = np.percentile(hor(P), a.kern); ids = np.array(list(r.points3D.keys())); XYZ = np.array([r.points3D[i].xyz for i in ids]); kern = set(ids[hor(XYZ) <= rk].tolist())
    info = {}
    for iid in r.reg_image_ids():
        im = r.images[iid]; C = np.asarray(im.projection_center()); R = np.asarray(im.cam_from_world().rotation.matrix())
        nk = sum(1 for p2 in im.points2D if p2.has_point3D() and p2.point3D_id in kern)
        info[iid] = dict(name=im.name, C=C, d=float(np.linalg.norm(C - mitte)), blick=R[2], drin=bool(nk >= a.min_kern), kernpunkte=nk)
    dmed = float(np.median([v["d"] for v in info.values()])); behalten = {i for i, v in info.items() if v["drin"] and v["d"] <= a.fern * dmed}   # --fern jetzt 40 (nur noch Schutz gegen Ausreisserkameras): wer genug Objektpunkte sieht, zeigt das Objekt
    clips = {}
    for i in behalten:
        m = re.match(r"(.+)__vf_(\d+)\.", info[i]["name"])
        if m: clips.setdefault(m.group(1), []).append((int(m.group(2)), i))
    weg_video = 0
    for k, L in clips.items():
        letzt = None
        for _, i in sorted(L):
            v = info[i]
            if letzt is not None:
                w = np.degrees(np.arccos(np.clip(v["blick"] @ letzt["blick"], -1, 1)))
                if np.linalg.norm(v["C"] - letzt["C"]) < a.schritt * dmed and w < a.winkel: behalten.discard(i); weg_video += 1; continue
            letzt = v
    # OBERGRENZE nach Platz (18.11.2026, Kaufhaus gk2: 867 Bilder -> 14 GB Tiefenkarten nach 758 Bildern, Datenplatte voll; ~18,5 MB/Bild bei 1600 px + Fusion):
    # --max_bilder 0 = automatisch: die Haelfte des freien Platzes im Zielordner / 20 MB, begrenzt auf 150..600. Auswahl per Fernster-Punkt-Folge ueber
    # Kameraort (in Median-Abstaenden) + Blickrichtung, Start beim Bild mit den meisten Kernpunkten -> Abdeckung bleibt, Doppelte fallen zuerst.
    weg_platz = 0; mx = a.max_bilder
    if mx <= 0:
        sv = os.statvfs(os.path.dirname(os.path.abspath(a.aus)) if not os.path.isdir(a.aus) else a.aus); frei_gb = sv.f_bavail * sv.f_frsize / 1e9
        mx = int(min(600, max(150, frei_gb * 1000 * 0.5 / 20)))
    if len(behalten) > mx:
        ids_ = sorted(behalten); F = np.array([np.concatenate([info[i]["C"] / dmed, info[i]["blick"]]) for i in ids_])
        wahl = [int(np.argmax([info[i]["kernpunkte"] for i in ids_]))]; dmin = np.linalg.norm(F - F[wahl[0]], axis=1)
        while len(wahl) < mx: j = int(np.argmax(dmin)); wahl.append(j); dmin = np.minimum(dmin, np.linalg.norm(F - F[j], axis=1))
        neu_b = {ids_[j] for j in wahl}; weg_platz = len(behalten) - len(neu_b); behalten = neu_b
    for i in info:
        if i not in behalten: r.deregister_frame(r.images[i].frame_id)
    os.makedirs(a.aus, exist_ok=True); r.write(a.aus)
    erg = dict(registriert=len(info), behalten=len(behalten), weg_zu_wenig_kern=sum(not v["drin"] for v in info.values()),
               weg_zu_fern=sum(v["drin"] and v["d"] > a.fern * dmed for v in info.values()), weg_video_doppelt=weg_video, weg_platz=weg_platz, max_bilder=mx, median_abstand=dmed)
    json.dump(dict(erg, behalten_namen=sorted(info[i]["name"] for i in behalten)), open(os.path.join(a.aus, "dicht_bildwahl.json"), "w"), indent=1)
    print("Bildwahl dicht:", erg, flush=True)


if __name__ == "__main__":
    main()
