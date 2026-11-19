#!/usr/bin/env python3
"""seiten_geometrie.py <seiten.json> <db.db> <bilder_ordner> --arbeit <ordner> [--db-aus <kopie.db>] [--sim3 0.5] [--parallel 4] [--nur-messen]

Zweite Stufe der SEITENERKENNUNG (nach tools/seiten_erkennen.py): GEOMETRISCHE Gegenprobe jeder verdaechtigen Gruppenverbindung.
Warum: der gelernte Paar-Pruefer allein trennt nicht sicher (Martinstor 19.11.2026: 31 von 80 Verbindungen unter der Schwelle, darunter Drohne <-> Strasse;
verwechselt 0,33, vermutlich echt 0,38). Unabhaengiges Mass ohne Bildinhalt:
  1. Jede beteiligte Bildgruppe ALLEIN rekonstruieren (schrittweiser Mapper, CPU, --parallel Laeufe gleichzeitig) - innerhalb einer Gruppe gibt es nichts zu verwechseln.
  2. Verbindung X <-> Y: die bestaetigten Zuordnungen zwischen Bildern aus X und Y verbinden 3D-Punkte beider Teilmodelle. Eine ECHTE Verbindung sind dieselben
     Punkte im Raum -> EINE Aehnlichkeitsabbildung (Sim3, RANSAC) erklaert fast alle (Martinstor echt 75 %). Eine VERWECHSLUNG verbindet aehnliche, aber
     verschiedene Bauteile -> keine starre Abbildung passt (33 %, 33 %, 15 %).
Urteil je Verbindung: 'verwechselt', wenn Sim3-Anteil < --sim3 UND der Pruefer nicht 'echt' sagt; 'echt', wenn Sim3-Anteil >= --sim3; sonst bleibt das Pruefer-Urteil
als 'unklar' stehen (nichts geloescht). --db-aus: Kopie der Datenbank ohne die Paare verwechselter Gruppen und ohne fremde Bilder (wie seiten_erkennen.py).
Schreibt die Masse in seiten.json zurueck (verbindungen[].sim3_anteil, gemeinsam, urteil_endgueltig). rc 0 = nichts verwechselt, rc 3 = bereinigt.
GRENZEN: Schwelle 0,5 ist ANNAHME aus einem Objekt; Gruppen < 12 Bilder oder ohne Teilmodell werden nicht geprueft."""
import sys, os, json, argparse, sqlite3, shutil, subprocess, collections
from concurrent.futures import ThreadPoolExecutor
import numpy as np

MAXID = 2147483647
COLMAP_BIN = "/media/oem/scan/colmap-build/prefix/bin/colmap"
ENV = dict(os.environ, LD_LIBRARY_PATH=":".join(["/media/oem/scan/cuda-toolkit-combo/lib64", "/media/oem/scan/venv-seg/lib/python3.12/site-packages/nvidia/cu13/lib", "/media/oem/scan/cudss-pkg/py/nvidia/cu13/lib",
                                                 "/media/oem/scan/venv-colmap/lib/python3.12/site-packages/nvidia/curand/lib"]))


def umeyama(P, Q):
    mp, mq = P.mean(0), Q.mean(0); H = (Q - mq).T @ (P - mp) / len(P); U, S, Vt = np.linalg.svd(H); D = np.diag([1, 1, np.sign(np.linalg.det(U @ Vt))]); R = U @ D @ Vt
    s = (S * np.diag(D)).sum() / max(1e-12, ((P - mp) ** 2).sum(1).mean()); return s, R, mq - s * R @ mp


def sim3_anteil(P, Q, runden=2000, rel=0.03, saat=0):
    """Anteil der Punktpaare P[i] <-> Q[i], den EINE Aehnlichkeitsabbildung erklaert (Schranke rel x mittlere Ausdehnung von Q)."""
    if len(P) < 12: return 0.0
    rng = np.random.default_rng(saat); thr = rel * np.percentile(np.linalg.norm(Q - np.median(Q, 0), axis=1), 50); best = 0
    for _ in range(runden):
        ix = rng.choice(len(P), 3, replace=False); s, R, t = umeyama(P[ix], Q[ix])
        if not np.isfinite(s): continue
        k = int((np.linalg.norm(s * P @ R.T + t - Q, axis=1) < thr).sum()); best = max(best, k)
    return best / len(P)


def rekonstruieren(db, bilder, namen, ziel, threads=3, zeit=2400):
    os.makedirs(os.path.join(ziel, "sparse"), exist_ok=True); lst = os.path.join(ziel, "liste.txt"); open(lst, "w").write("\n".join(sorted(namen)) + "\n")
    fertig = os.path.join(ziel, "fertig")
    if not os.path.isfile(fertig):
        try: subprocess.run([COLMAP_BIN, "mapper", "--database_path", db, "--image_path", bilder, "--Mapper.image_list_path", lst, "--output_path", os.path.join(ziel, "sparse"), "--Mapper.ba_use_gpu", "0",
                             "--Mapper.num_threads", str(threads), "--Mapper.min_model_size", "8"], env=ENV, stdout=open(os.path.join(ziel, "mapper.log"), "w"), stderr=subprocess.STDOUT, timeout=zeit)
        except subprocess.TimeoutExpired: pass
        open(fertig, "w").write("1")
    kand = [os.path.join(ziel, "sparse", d) for d in os.listdir(os.path.join(ziel, "sparse")) if os.path.isfile(os.path.join(ziel, "sparse", d, "images.bin"))]   # mehrere Anlaeufe: das groesste Modell zaehlt
    return max(kand, key=lambda q: os.path.getsize(os.path.join(q, "images.bin"))) if kand else None


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("seiten"); ap.add_argument("db"); ap.add_argument("bilder"); ap.add_argument("--arbeit", required=True); ap.add_argument("--db-aus"); ap.add_argument("--sim3", type=float, default=0.5)
    ap.add_argument("--parallel", type=int, default=4); ap.add_argument("--min-inlier", type=int, default=15); ap.add_argument("--nur-messen", action="store_true"); ap.add_argument("--alle", action="store_true", help="auch 'echt' beurteilte Verbindungen messen (Eichung)")
    a = ap.parse_args(argv); import pycolmap
    S = json.load(open(a.seiten)); g = S["gemeinschaft"]; verb = S["verbindungen"]; zu = [v for v in verb if a.alle or v["urteil"] in ("verwechselt", "unklar")]
    gruppen = sorted({v["a"] for v in zu} | {v["b"] for v in zu}); mitgl = collections.defaultdict(list)
    for n, k in g.items(): mitgl[k].append(n)
    print(f"{len(zu)} Verbindungen zu pruefen, {len(gruppen)} Bildgruppen allein rekonstruieren ({sum(len(mitgl[k]) for k in gruppen)} Bilder, {a.parallel} gleichzeitig)", flush=True)
    # Jeder gleichzeitige Mapper braucht seine EIGENE Datenbank-Kopie: COLMAP oeffnet schreibend, vier Laeufe auf einer Datei = 'database is locked' -> Absturz
    # (19.11.2026: 12 von 23 Gruppen ohne Modell); die Datenbank der Kette wird so auch nicht angefasst.
    import queue; os.makedirs(a.arbeit, exist_ok=True); frei = queue.Queue(); reihen = sorted(gruppen, key=lambda k: -len(mitgl[k]))
    offen = [k for k in reihen if not os.path.isfile(os.path.join(a.arbeit, f"gruppe_{k}", "fertig"))]
    for i in range(min(a.parallel, len(offen))):
        q = os.path.join(a.arbeit, f"db_platz{i}.db"); shutil.copyfile(a.db, q); frei.put(q)
    def einer(k):
        if k not in offen: return rekonstruieren(a.db, a.bilder, mitgl[k], os.path.join(a.arbeit, f"gruppe_{k}"))
        q = frei.get()
        try: return rekonstruieren(q, a.bilder, mitgl[k], os.path.join(a.arbeit, f"gruppe_{k}"))
        finally: frei.put(q)
    with ThreadPoolExecutor(a.parallel) as ex: pf = dict(zip(reihen, ex.map(einer, reihen)))
    for i in range(a.parallel):
        q = os.path.join(a.arbeit, f"db_platz{i}.db")
        if os.path.isfile(q): os.remove(q)
    db = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True); nm = dict(db.execute("select image_id, name from images")); M = {}
    for k in gruppen:
        if pf[k] is None: continue
        r = pycolmap.Reconstruction(pf[k]); M[k] = ({im.name: np.array([p.point3D_id if p.has_point3D() else -1 for p in im.points2D], dtype=np.int64) for im in r.images.values() if im.has_pose}, {i: p.xyz for i, p in r.points3D.items()})
        print(f"  Gruppe {k}: {len(M[k][0])} von {len(mitgl[k])} Bildern, {len(M[k][1])} Punkte", flush=True)
    kor = collections.defaultdict(dict); paarz = collections.Counter(); wahl = {(v["a"], v["b"]) for v in zu}
    for pid, data in db.execute("select pair_id, data from two_view_geometries where rows >= ?", (a.min_inlier,)):
        x, y = nm[pid // MAXID], nm[pid % MAXID]; kx, ky = g[x], g[y]
        if kx == ky: continue
        m = np.frombuffer(data, np.uint32).reshape(-1, 2)
        if kx > ky: x, y, kx, ky, m = y, x, ky, kx, m[:, ::-1]
        if (kx, ky) not in wahl or kx not in M or ky not in M or x not in M[kx][0] or y not in M[ky][0]: continue
        qa, qb = M[kx][0][x][m[:, 0]], M[ky][0][y][m[:, 1]]; ok = (qa >= 0) & (qb >= 0); paarz[(kx, ky)] += 1
        for u, w in zip(qa[ok], qb[ok]): kor[(kx, ky)].setdefault(int(u), collections.Counter())[int(w)] += 1
    for v in zu:
        k = (v["a"], v["b"]); c = kor.get(k, {})
        if k[0] not in M or k[1] not in M or len(c) < 30: v.update(gemeinsam=len(c), sim3_anteil=None, urteil_endgueltig="unklar" if v["urteil"] != "echt" else "echt"); continue
        P = np.array([M[k[0]][1][u] for u in c]); Q = np.array([M[k[1]][1][cc.most_common(1)[0][0]] for cc in c.values()]); an = sim3_anteil(P, Q)
        v.update(gemeinsam=len(c), sim3_anteil=round(an, 3), urteil_endgueltig="echt" if an >= a.sim3 else ("verwechselt" if v["urteil"] != "echt" else "unklar"))
    for v in verb: v.setdefault("urteil_endgueltig", v["urteil"])
    for v in sorted(zu, key=lambda v: (v.get("sim3_anteil") is None, v.get("sim3_anteil") or 0)):
        print(f"  Gruppe {v['a']:3d} <-> {v['b']:3d}: {v['paare']:5d} Paare, Pruefer {v['p_median']}, gemeinsame Punkte {v['gemeinsam']:5d}, Sim3-Anteil {v['sim3_anteil']}  -> {v['urteil_endgueltig']}")
    falsch = {(v["a"], v["b"]) for v in verb if v["urteil_endgueltig"] == "verwechselt"}; S["verwechselt"] = [list(k) for k in sorted(falsch)]; geloescht = 0
    if a.db_aus and not a.nur_messen:
        fremd = set(S.get("fremd", [])); shutil.copyfile(a.db, a.db_aus); d2 = sqlite3.connect(a.db_aus); weg = []
        for (pid,) in d2.execute("select pair_id from two_view_geometries"):
            x, y = nm[pid // MAXID], nm[pid % MAXID]
            if tuple(sorted((g[x], g[y]))) in falsch or x in fremd or y in fremd: weg.append((pid,))
        d2.executemany("delete from two_view_geometries where pair_id = ?", weg); d2.executemany("delete from matches where pair_id = ?", weg); d2.commit(); d2.close(); geloescht = len(weg); S["geloeschte_paare"] = geloescht
    json.dump(S, open(a.seiten, "w"), indent=1)
    print(f"Seiten-Geometrie: {len(falsch)} Verbindung(en) verwechselt (Sim3-Anteil < {a.sim3} und Pruefer nicht 'echt'), {sum(1 for v in verb if v['urteil_endgueltig'] == 'unklar')} unklar" + (f"; {geloescht} Paare geloescht -> {a.db_aus}" if geloescht else ""))
    return 3 if falsch else 0


if __name__ == "__main__": sys.exit(main())
