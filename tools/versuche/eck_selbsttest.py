#!/usr/bin/env python3
"""eck_selbsttest.py <sparse> <db> <fotos> <ausrichtung.json> --aus DIR --k 3 5 10  (22.11.2026)

SELBSTTEST DER BRUECKENKOPPLUNG (seiten_eck_koppeln) AN ECHTEN DATEN OHNE VORWISSEN: ein zusammenhaengendes gutes Modell wird an EINER Stelle kuenstlich getrennt.
- Kameras nach ihrem Blickwinkel (Azimut um die Punktmitte) sortiert; die groesste Luecke im Azimut ist das offene Ende, die Mitte der uebrigen Folge die Trennstelle.
- BRUECKE = die k Bilder an der Trennstelle (k/2 je Seite); sie gehoeren zu KEINEM Teil (wie die Eckbilder am Schwabentor). Teil A / Teil B = die Bilder links / rechts davon.
- DB-Kopie: alle Paare zwischen A und B geloescht (two_view_geometries + matches), nur Paare mit Brueckenbildern bleiben. seiten.json: 'durchblick' = alle Paare
  mit einem Brueckenbild und >= 200 Inliern (Vorwissen nur, dass es echte Paare desselben Gebaeudes sind - die Durchblick-Stufe pruefte sonst dasselbe).
- Teilmodelle = das Ursprungsmodell eingeschraenkt auf A bzw. B (deregistriert), B zusaetzlich mit einer zufaelligen Sim3 bewegt -> WAHRE Lage bekannt.
  ANNAHME: die Eigenverformung getrennt gerechneter Teilmodelle ist hier NICHT enthalten (gemessen wird die Kopplung, nicht der Teil-Mapper).
- Stufe laufen lassen, Ergebnis gegen die Wahrheit: Drehung (Grad), Massstab (%), Lagefehler der B-Punkte (Median, Meter ueber die Ausrichtung)."""
import os, sys, json, argparse, sqlite3, shutil, subprocess, numpy as np, pycolmap
T = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, T)
from sim3_robust import sim3_meter, matrix, anwenden
import seiten_eck_koppeln as EK
MAXID = EK.MAXID


def teilmodell(src, behalten, aus, M=None):
    r = pycolmap.Reconstruction(src)
    for fid in {im.frame_id for im in r.images.values() if im.has_pose and im.name not in behalten}: r.deregister_frame(fid)
    for pid in [p for p, q in r.points3D.items() if q.track.length() < 2]: r.delete_point3D(pid)
    if M is not None: r.transform(pycolmap.Sim3d(np.asarray(M)[:3, :]))
    os.makedirs(aus, exist_ok=True); r.write(aus); return r


def main():
    ap = argparse.ArgumentParser(); [ap.add_argument(x) for x in ("sparse", "db", "fotos", "ausrichtung")]; ap.add_argument("--aus", required=True)
    ap.add_argument("--k", type=int, nargs="+", default=[3, 5, 10]); ap.add_argument("--faeden", type=int, default=14); a = ap.parse_args(); os.makedirs(a.aus, exist_ok=True)
    r = pycolmap.Reconstruction(a.sparse); ims = [im for im in r.images.values() if im.has_pose]
    au = json.load(open(a.ausrichtung)); st = {k: np.asarray(v["standort"], float) for k, v in au["kameras"].items() if v.get("standort") is not None}
    ns = [im for im in ims if os.path.splitext(im.name)[0] in st]
    f = sim3_meter(np.array([im.projection_center() for im in ns]), np.array([st[os.path.splitext(im.name)[0]] for im in ns])); m_je = float(np.cbrt(np.linalg.det(f["M"][:3, :3])))
    P = np.array([p.xyz for p in r.points3D.values()]); mitte = np.median(P, 0); C = np.array([im.projection_center() for im in ims])
    # Azimut in der Ebene senkrecht zur Lotrichtung (Ausrichtung: z oben)
    Rm = f["M"][:3, :3] / m_je; Cw = (C - mitte) @ Rm.T; az = np.degrees(np.arctan2(Cw[:, 1], Cw[:, 0])) % 360
    o = np.argsort(az); gap = np.diff(np.r_[az[o], az[o][0] + 360]); start = (int(np.argmax(gap)) + 1) % len(o); folge = [ims[i].name for i in np.roll(o, -start)]
    mid = len(folge) // 2; erg = dict(modell=a.sparse, bilder=len(folge), meter_je_einheit=m_je, azimut_luecke_grad=round(float(gap.max()), 1), laeufe=[])
    db0 = sqlite3.connect(f"file:{a.db}?immutable=1", uri=True); nm = {n: i for i, n in db0.execute("select image_id, name from images")}
    rows = {pid: rw for pid, rw in db0.execute("select pair_id, rows from two_view_geometries")}
    rng = np.random.default_rng(7); q = rng.normal(size=4); q /= np.linalg.norm(q); MB = matrix(1.7, pycolmap.Rotation3d(q).matrix(), [5.0, -3.0, 2.0])
    for k in a.k:
        lo, hi = mid - k // 2, mid - k // 2 + k; K = set(folge[lo:hi]); A = set(folge[:lo]); B = set(folge[hi:]); o_ = os.path.join(a.aus, f"k{k}"); os.makedirs(o_, exist_ok=True)
        db = os.path.join(o_, "db.db"); shutil.copyfile(a.db, db); c = sqlite3.connect(db); ia, ib = {nm[n] for n in A}, {nm[n] for n in B}
        weg = [pid for pid in rows if (pid // MAXID in ia and pid % MAXID in ib) or (pid // MAXID in ib and pid % MAXID in ia)]
        c.executemany("delete from two_view_geometries where pair_id = ?", [(p,) for p in weg]); c.executemany("delete from matches where pair_id = ?", [(p,) for p in weg]); c.commit(); c.close()
        iv = {i: n for n, i in nm.items()}; ik = {nm[n] for n in K}
        db_ = [dict(a=iv[p // MAXID], b=iv[p % MAXID], urteil="durchblick") for p, rw in rows.items() if rw >= EK.NACHBAR_MIN and (p // MAXID in ik or p % MAXID in ik) and p not in weg]
        sj = os.path.join(o_, "seiten.json"); json.dump(dict(durchblick=db_), open(sj, "w"))
        ta = os.path.join(o_, "teilA"); tb = os.path.join(o_, "teilB"); teilmodell(a.sparse, A, ta); teilmodell(a.sparse, B, tb, MB)
        rc = subprocess.call([sys.executable, "-I", os.path.join(T, "seiten_eck_koppeln.py"), db, sj, a.fotos, "--aus", os.path.join(o_, "stufe"), "--faeden", str(a.faeden),
                              f"--teil=0={ta}", f"--teil=1={tb}"], stdout=open(os.path.join(o_, "stufe.log"), "w"), stderr=subprocess.STDOUT)
        ej = json.load(open(os.path.join(o_, "stufe", "eck.json"))); t1 = (ej.get("teile") or {}).get("1") or {}
        z = dict(k=k, teil_a=len(A), teil_b=len(B), brueckenpaare=len(db_), rc=rc, urteil=ej.get("urteil"),
                 schwelle=[x.get("schwelle") for x in ej.get("zwischenmodelle", [])], sensitivitaet=[x.get("sensitivitaet") for x in ej.get("zwischenmodelle", [])],
                 kopplungen=[x.get("kopplungen") for x in ej.get("zwischenmodelle", [])], wiederholbarkeit=[(x.get("wiederholbarkeit") or {}).get("max") for x in ej.get("zwischenmodelle", [])])
        if t1.get("ok"):
            Mest = np.asarray(t1["M_nach_A"]); Mtrue = np.linalg.inv(MB); s, R_, _ = EK.zerlegen(np.linalg.inv(Mtrue) @ Mest)
            PB = np.array([p.xyz for p in pycolmap.Reconstruction(tb).points3D.values()]); d = np.linalg.norm(anwenden(Mest, PB) - anwenden(Mtrue, PB), axis=1) * m_je
            z.update(drehung_grad=round(winkel := EK.winkel(R_), 3), massstab_prozent=round(abs(s - 1) * 100, 3), lagefehler_m=dict(median=round(float(np.median(d)), 3), p90=round(float(np.percentile(d, 90)), 3)),
                     massstab_unsicher_gemeldet=t1.get("massstab_unsicher"))
        erg["laeufe"].append(z); print(json.dumps({x: z.get(x) for x in ("k", "rc", "schwelle", "wiederholbarkeit", "drehung_grad", "massstab_prozent", "lagefehler_m", "urteil")}, ensure_ascii=False))
    json.dump(erg, open(os.path.join(a.aus, "selbsttest.json"), "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__": main()
