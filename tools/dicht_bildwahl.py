#!/usr/bin/env python3
"""dicht_bildwahl.py <sparse_ein> <sparse_aus> - Bildauswahl fuer die dichte Wolke (Tiefenkarten = teuerster Schritt).
Lehre Schwabentor 2026-11-14 (Nutzer: 'koennen wir nicht weiter beschleunigen?'): ~580 Bilder, davon Fernansichten der Stadt und fast gleiche
Videobilder - jede Tiefenkarte kostet gleich viel, traegt am Objekt aber wenig bei. Regeln (allgemein, kein Objektwissen noetig):
  1. Objektmitte = Median der 3D-Punkte mit Spur >= 5 (meistgesehene Struktur).
  2. Objektkern = diese Punkte bis zum --kern-Perzentil des Abstands zur Mitte. Bild behalten, wenn es >= --min_kern Kernpunkte beobachtet
     und der Abstand <= --fern x Median-Abstand ist. (Erst 'Mitte im Bild' getestet: warf 66 von 178 alten Bildern weg, darunter Nahaufnahmen.)
  3. Videobilder ('<clip>__vf_NNN'): nur behalten, wenn sich die Kamera seit dem letzten behaltenen Bild >= --schritt x Median-Abstand
     bewegt oder >= --winkel Grad gedreht hat.
Abgewaehlte Bilder werden im Ausgabemodell abgemeldet (Frame deregistriert); die SfM selbst bleibt unveraendert. Bericht dicht_bildwahl.json.
"""
import sys, os, re, json, argparse
import numpy as np, pycolmap


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("ein"); ap.add_argument("aus")
    ap.add_argument("--fern", type=float, default=4.0); ap.add_argument("--kern", type=float, default=80); ap.add_argument("--min_kern", type=int, default=150); ap.add_argument("--schritt", type=float, default=0.03); ap.add_argument("--winkel", type=float, default=4.0)
    a = ap.parse_args(); r = pycolmap.Reconstruction(a.ein)
    P = np.array([p.xyz for p in r.points3D.values() if p.track.length() >= 5]); mitte = np.median(P, 0)
    rk = np.percentile(np.linalg.norm(P - mitte, axis=1), a.kern); kern = {pid for pid, p in r.points3D.items() if np.linalg.norm(p.xyz - mitte) <= rk}
    info = {}
    for iid in r.reg_image_ids():
        im = r.images[iid]; C = np.asarray(im.projection_center()); R = np.asarray(im.cam_from_world().rotation.matrix())
        nk = sum(1 for p2 in im.points2D if p2.has_point3D() and p2.point3D_id in kern)
        info[iid] = dict(name=im.name, C=C, d=float(np.linalg.norm(C - mitte)), blick=R[2], drin=bool(nk >= a.min_kern), kernpunkte=nk)
    dmed = float(np.median([v["d"] for v in info.values()])); behalten = {i for i, v in info.items() if v["drin"] and v["d"] <= a.fern * dmed}
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
    for i in info:
        if i not in behalten: r.deregister_frame(r.images[i].frame_id)
    os.makedirs(a.aus, exist_ok=True); r.write(a.aus)
    erg = dict(registriert=len(info), behalten=len(behalten), weg_zu_wenig_kern=sum(not v["drin"] for v in info.values()),
               weg_zu_fern=sum(v["drin"] and v["d"] > a.fern * dmed for v in info.values()), weg_video_doppelt=weg_video, median_abstand=dmed)
    json.dump(dict(erg, behalten_namen=sorted(info[i]["name"] for i in behalten)), open(os.path.join(a.aus, "dicht_bildwahl.json"), "w"), indent=1)
    print("Bildwahl dicht:", erg, flush=True)


if __name__ == "__main__":
    main()
