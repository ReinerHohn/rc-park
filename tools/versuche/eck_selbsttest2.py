#!/usr/bin/env python3
"""eck_selbsttest2.py <sparse> <db> <fotos> <ausrichtung.json> --aus DIR [--k 3 5] [--modus neu ausgeschnitten] [--verformung keine massstab:0.02 ...]
                     [--nachmatchen 0|1] [--lotfeld] [--faeden 6]   (22.11.2026, Recherche duenne Bruecken Methode 1)

SELBSTTEST STUFE 2 DER BRUECKENKOPPLUNG: wie eck_selbsttest.py (ein gutes Modell an EINER Stelle kuenstlich getrennt, Bruecke = k Bilder an der Trennstelle,
alle A-B-Paare aus einer DB-Kopie geloescht), aber
 (a) modus 'neu': Teil A und Teil B werden JE FUER SICH NEU gerechnet (schrittweiser COLMAP-Mapper wie in der Kette, auf der DB-Kopie, vorhandene Zuordnungen,
     Schwelle 30) -> echte Eigenverformung und Eigenmassstab der Teile. Modus 'ausgeschnitten' = Stufe 1 (Ausschnitte des Ursprungsmodells) als Vergleich.
 (b) kuenstliche Verformung von Teil B (Punkte UND Kameras): massstab:a (Massstab 1 + a*u), biegung_lot:b / biegung_quer:b (Drehung um das Lot bzw. um die
     waagerechte Tangente des Rundgangs, Winkel b*u Grad, um die Kernmitte); u = Lage auf dem Rundgang (teil_verformung.ort_koordinate, -0,5..0,5 ueber 5-95 %).
     Faelle wie eck_rest_eichung.py (2/5 %, 1/3 Grad).
 (c) Kennzahlen gegen die WAHRHEIT (Ursprungsmodell, Meter ueber die Ausrichtung) getrennt: Fehler der gekoppelten B-Kameras an der NAHT (naechstes Viertel
     der B-Kameras entlang des Rundgangs) und am FERNEN ENDE (fernstes Viertel), Gesamt-Median; Drehung, Kippung (Lot), Gier (um das Lot), Massstab des
     gekoppelten B gegen die beste starre Lage von B; dazu der Eigenfehler (beste starre Lage von B bzw. A gegen die Wahrheit, nah/fern) = Untergrenze, die
     keine starre Kopplung unterschreiten kann.
 (d) je Fall eine Zeile 'SELBSTTEST2 ...' + selbsttest2.json; jede neue Methode laesst sich vorher/nachher an denselben Faellen messen.
 (e) Zwischenergebnisse gecacht: DB-Kopie je k, neu gerechnete Teile (fertig.json), Stufenlauf je (k, modus, nachmatchen) - verformte Faelle koppeln NEU
     auf den Zwischenmodellen des unverformten Stufenlaufs (seiten_eck_koppeln.koppeln, dieselben Grenzen; Verformung von B aendert das Zwischenmodell nicht).
     --stufe-je-fall: stattdessen voller Stufenlauf je Fall (langsam, fuer die Endprobe).
 (f) --lotfeld: teil_verformung.messen an Teil A und jedem (verformten) Teil B -> sieht das Lotfeld die eingespielte Verformung? (Beleg 2(i)).
Kopplungs-Varianten in der Auswertung: 'stufe' (Ergebnis der Stufe, M_nach_A), 'sift' / 'nachmatchen' (je Zwischenmodell neu gekoppelt).
pycolmap 4.2.1 oeffnet die 4.3-Datenbank nicht: DB nur per sqlite3 (immutable), Mapper = eigene COLMAP (seiten_eck_koppeln.mapper)."""
import os, sys, json, argparse, sqlite3, shutil, subprocess, time, numpy as np, pycolmap
T = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, T)
from sim3_robust import sim3_meter, matrix, anwenden, umeyama
import seiten_eck_koppeln as EK
import teil_verformung as TV
MAXID = EK.MAXID


def teilmodell(src, behalten, aus, M=None):
    r = pycolmap.Reconstruction(src)
    for fid in {im.frame_id for im in r.images.values() if im.has_pose and im.name not in behalten}: r.deregister_frame(fid)
    for pid in [p for p, q in r.points3D.items() if q.track.length() < 2]: r.delete_point3D(pid)
    if M is not None: r.transform(pycolmap.Sim3d(np.asarray(M)[:3, :]))
    os.makedirs(aus, exist_ok=True); r.write(aus); return aus


def teil_neu(namen, db, fotos, aus, faeden):
    """Teil fuer sich neu rechnen (gecacht). -> Pfad des groessten Modells oder None."""
    fj = os.path.join(aus, "fertig.json")
    if os.path.isfile(fj): return json.load(open(fj)).get("modell")
    t0 = time.time(); rc, mods = EK.mapper(sorted(namen), db, fotos, aus, faeden, 30); best = None
    for m in mods:
        n = sum(im.has_pose for im in pycolmap.Reconstruction(m).images.values())
        if best is None or n > best[0]: best = (n, m)
    json.dump(dict(rc=rc, modell=best[1] if best else None, bilder=best[0] if best else 0, soll=len(namen), sekunden=round(time.time() - t0)), open(fj, "w"))
    return best[1] if best else None


# ---------- Verformung ----------
def ort_parameter(rec, up):
    """Rundgang-Koordinate wie teil_verformung: Kernmitte, Basis, Azimut-Start, Median, Spanne (aus den Kameras)."""
    box = TV.kern_box(rec); P = np.array([p.xyz for p in rec.points3D.values()]); P = P[np.all((P >= box[0]) & (P <= box[1]), 1)]
    c0 = np.median(P, 0); C = np.array([im.projection_center() for im in rec.images.values() if im.has_pose])
    h = C - c0; h = h - np.outer(h @ up, up); b1, b2 = TV.basis(up, h + c0); phi = np.degrees(np.arctan2(h @ b2, h @ b1)) % 360
    o = np.argsort(phi); gap = np.diff(np.r_[phi[o], phi[o][0] + 360]); start = phi[o][(int(np.argmax(gap)) + 1) % len(o)]; ph = (phi - start) % 360
    return dict(c0=c0, b1=b1, b2=b2, start=start, med=float(np.median(ph)), sp=max(float(np.percentile(ph, 95) - np.percentile(ph, 5)), 1e-6))


def u_von(X, op, up):
    h = X - op["c0"]; h = h - np.outer(h @ up, up); phi = np.degrees(np.arctan2(h @ op["b2"], h @ op["b1"])) % 360
    return np.clip((((phi - op["start"]) % 360) - op["med"]) / op["sp"], -1.0, 1.0)


def rot(ax, w):
    ax = ax / np.linalg.norm(ax); K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]]); return np.eye(3) + np.sin(w) * K + (1 - np.cos(w)) * K @ K


def verformen_modell(src, art, wert, up, aus):
    """Teil-Modell (Pfad) verformt nach aus schreiben (Punkte + Kameras konsistent). art in massstab, biegung_lot, biegung_quer."""
    r = pycolmap.Reconstruction(src); op = ort_parameter(r, up); c0 = op["c0"]
    tang = None
    if art == "biegung_quer":                                                         # waagerechte Tangente des Rundgangs in der Mitte
        a = np.radians(op["start"] + op["med"]); radial = np.cos(a) * op["b1"] + np.sin(a) * op["b2"]; tang = np.cross(up, radial)
    def feld(X):
        u = u_von(X, op, up)
        if art == "massstab": return u, None
        ax = up if art == "biegung_lot" else tang; return u, [rot(ax, np.radians(wert) * x) for x in u]
    pids = list(r.points3D.keys()); X = np.array([r.points3D[p].xyz for p in pids]); u, Rs = feld(X)
    Xn = c0 + (X - c0) * (1 + wert * u)[:, None] if art == "massstab" else np.array([c0 + Rk @ (x - c0) for Rk, x in zip(Rs, X)])
    for p, x in zip(pids, Xn): r.points3D[p].xyz = x
    for im in r.images.values():
        if not im.has_pose: continue
        C = im.projection_center(); Rcw = im.cam_from_world().rotation.matrix(); uu, Rr = feld(C[None])
        if art == "massstab": Cn = c0 + (C - c0) * (1 + wert * uu[0]); Rn = Rcw
        else: Cn = c0 + Rr[0] @ (C - c0); Rn = Rcw @ Rr[0].T
        r.frames[im.frame_id].rig_from_world = pycolmap.Rigid3d(pycolmap.Rotation3d(Rn), -Rn @ Cn)
    os.makedirs(aus, exist_ok=True); r.write(aus); return aus


# ---------- Auswertung gegen die Wahrheit ----------
def kopplung_neu(modell, rA, rB):
    """Zwischenmodell an A und B koppeln (Grenzen der Stufe). -> (M B->A oder None, Pruefungen)."""
    ausd = {0: EK.ausdehnung([p.xyz for p in rA.points3D.values()]), 1: EK.ausdehnung([p.xyz for p in rB.points3D.values()])}
    _, gut, alle = EK.koppeln(modell, [0, 1], {0: rA, 1: rB}, None, ausd)
    pr = {str(t): {x: v.get(x) for x in ("anteil", "rest_rel", "hebel", "massstab_haelften_rel", "grund")} for t, v in alle.items()}
    if 0 in gut and 1 in gut: return gut[0][0] @ np.linalg.inv(gut[1][0]), pr
    return None, pr


def bewerten(rA, rB, M, wahr, bruecke, m_je, up):
    """M: B -> A. wahr: {name: Zentrum im Ursprungsmodell}; bruecke: Mitte der Brueckenkameras (Ursprung). NAHT/ENDE = naechstes/fernstes Viertel der B-Kameras
    nach dem 3D-Abstand zur Bruecke (erster Lauf nach der Azimut-Folge: Martinstor-Kameras decken nur 82 Grad Azimut, Fernfotos nahe der Naht im Azimut lagen
    weit weg -> 'Naht' 0,22 m > 'Ende' 0,09 m). -> Kennzahlen (Meter, Grad, Prozent)."""
    A = {im.name: im.projection_center() for im in rA.images.values() if im.has_pose and im.name in wahr}
    B = {im.name: im.projection_center() for im in rB.images.values() if im.has_pose and im.name in wahr}
    na, nb = sorted(A), sorted(B, key=lambda n: np.linalg.norm(wahr[n] - bruecke))
    TA = matrix(*umeyama(np.array([A[n] for n in na]), np.array([wahr[n] for n in na])))
    TB = matrix(*umeyama(np.array([B[n] for n in nb]), np.array([wahr[n] for n in nb])))
    W = np.array([wahr[n] for n in nb]); q = max(1, len(nb) // 4)
    # Naht = B-Kameras mit der kleinsten Folgenummer-Entfernung zur Bruecke; die Folge laeuft von A ueber die Bruecke nach B
    eA = np.linalg.norm(anwenden(TA, np.array([A[n] for n in na])) - np.array([wahr[n] for n in na]), axis=1) * m_je
    eB = np.linalg.norm(anwenden(TB, np.array([B[n] for n in nb])) - W, axis=1) * m_je
    aus = dict(b_kameras=len(nb), a_kameras=len(na), eigen_a_m=round(float(np.median(eA)), 3), eigen_b_naht_m=round(float(np.median(eB[:q])), 3), eigen_b_ende_m=round(float(np.median(eB[-q:])), 3))
    if M is None: return dict(aus, gekoppelt=False)
    X = anwenden(TA @ M, np.array([B[n] for n in nb])); e = np.linalg.norm(X - W, axis=1) * m_je
    D = TA @ M @ np.linalg.inv(TB); s, R, _ = EK.zerlegen(D)
    kipp = float(np.degrees(np.arccos(np.clip((R @ up) @ up, -1, 1))))
    h = np.cross(up, [1.0, 0, 0] if abs(up[0]) < 0.9 else [0, 1.0, 0]); h /= np.linalg.norm(h); hr = R @ h; hr = hr - (hr @ up) * up
    gier = float(np.degrees(np.arctan2(np.cross(h, hr) @ up, h @ hr)))
    return dict(aus, gekoppelt=True, naht_m=round(float(np.median(e[:q])), 3), ende_m=round(float(np.median(e[-q:])), 3), median_m=round(float(np.median(e)), 3),
                p90_m=round(float(np.percentile(e, 90)), 3), drehung_grad=round(EK.winkel(R), 3), kipp_grad=round(kipp, 3), gier_grad=round(gier, 3),
                massstab_prozent=round((s - 1) * 100, 3))


def zeile(fall, z):
    if not z.get("gekoppelt"): return f"SELBSTTEST2 {fall}: NICHT GEKOPPELT (Eigenfehler B Naht/Ende {z['eigen_b_naht_m']}/{z['eigen_b_ende_m']} m)"
    return (f"SELBSTTEST2 {fall}: Naht {z['naht_m']:.3f} m | Ende {z['ende_m']:.3f} m | Drehung {z['drehung_grad']:.2f} (Kipp {z['kipp_grad']:.2f}, Gier {z['gier_grad']:+.2f}) Grad | "
            f"Massstab {z['massstab_prozent']:+.2f} % | Eigen B Naht/Ende {z['eigen_b_naht_m']:.3f}/{z['eigen_b_ende_m']:.3f} m")


def main():
    ap = argparse.ArgumentParser(); [ap.add_argument(x) for x in ("sparse", "db", "fotos", "ausrichtung")]; ap.add_argument("--aus", required=True)
    ap.add_argument("--k", type=int, nargs="+", default=[3, 5]); ap.add_argument("--modus", nargs="+", default=["neu", "ausgeschnitten"])
    ap.add_argument("--verformung", nargs="+", default=["keine", "massstab:0.02", "massstab:0.05", "biegung_lot:1", "biegung_lot:3", "biegung_quer:1", "biegung_quer:3"])
    ap.add_argument("--nachmatchen", type=int, default=0); ap.add_argument("--lotfeld", action="store_true"); ap.add_argument("--stufe-je-fall", action="store_true")
    ap.add_argument("--faeden", type=int, default=6); a = ap.parse_args(); os.makedirs(a.aus, exist_ok=True); t_start = time.time()
    r = pycolmap.Reconstruction(a.sparse); ims = [im for im in r.images.values() if im.has_pose]
    au = json.load(open(a.ausrichtung)); st = {k: np.asarray(v["standort"], float) for k, v in au["kameras"].items() if v.get("standort") is not None}
    ns = [im for im in ims if os.path.splitext(im.name)[0] in st]
    f = sim3_meter(np.array([im.projection_center() for im in ns]), np.array([st[os.path.splitext(im.name)[0]] for im in ns])); m_je = float(np.cbrt(np.linalg.det(f["M"][:3, :3])))
    Rm = f["M"][:3, :3] / m_je; up_au = Rm.T @ np.array([0, 0, 1.0])                  # Lot im Modellrahmen laut Ausrichtung (z oben) - nur fuer die Trennstelle (wie Stufe 1)
    # LOT FUER VERFORMUNG UND KIPP/GIER = Fluchtpunkt-Lot des ungetrennten Modells (teil_verformung.messen): die Ausrichtung martinstor_gk (Kameraebene-Lot) liegt
    # 40,6 Grad daneben (kaufhaus_gk 1,9) - mit ihr war 'biegung_lot' eine schraege Drehung (erster Lauf 22.11.: Lot-Feld sprang bei 'Gier'-Biegung um 1,8 Grad).
    rw_p = os.path.join(a.aus, "lot_wahr_roh.json"); bw, roh_w = TV.messen(r, a.fotos, 4, None, json.load(open(rw_p)) if os.path.isfile(rw_p) else None); json.dump(roh_w, open(rw_p, "w"))
    up = np.asarray(bw["lot"], float) if bw.get("lot") else up_au; up = up if up @ up_au >= 0 else -up
    lot_info = dict(quelle="fluchtpunkte" if bw.get("lot") else "ausrichtung", gegen_ausrichtung_grad=round(float(np.degrees(np.arccos(np.clip(abs(up @ up_au), -1, 1)))), 2))
    P = np.array([p.xyz for p in r.points3D.values()]); mitte = np.median(P, 0); C = np.array([im.projection_center() for im in ims])
    Cw = (C - mitte) @ Rm.T; az = np.degrees(np.arctan2(Cw[:, 1], Cw[:, 0])) % 360
    o = np.argsort(az); gap = np.diff(np.r_[az[o], az[o][0] + 360]); start = (int(np.argmax(gap)) + 1) % len(o); folge = [ims[i].name for i in np.roll(o, -start)]
    wahr = {im.name: im.projection_center() for im in ims}
    mid = len(folge) // 2; erg = dict(modell=a.sparse, bilder=len(folge), meter_je_einheit=m_je, lot=lot_info, faelle=[], zeilen=[])
    db0 = sqlite3.connect(f"file:{a.db}?immutable=1", uri=True); nm = {n: i for i, n in db0.execute("select image_id, name from images")}
    rows = {pid: rw for pid, rw in db0.execute("select pair_id, rows from two_view_geometries")}
    rng = np.random.default_rng(7); q = rng.normal(size=4); q /= np.linalg.norm(q); MB = matrix(1.7, pycolmap.Rotation3d(q).matrix(), [5.0, -3.0, 2.0])
    for k in a.k:
        lo, hi = mid - k // 2, mid - k // 2 + k; K = set(folge[lo:hi]); brk = np.mean([wahr[n] for n in K], 0); A = set(folge[:lo]); B = set(folge[hi:]); o_ = os.path.join(a.aus, f"k{k}"); os.makedirs(o_, exist_ok=True)
        db = os.path.join(o_, "db.db"); sj = os.path.join(o_, "seiten.json")
        if not os.path.isfile(os.path.join(o_, "db_fertig.json")):
            shutil.copyfile(a.db, db); c = sqlite3.connect(db); ia, ib = {nm[n] for n in A}, {nm[n] for n in B}
            weg = [pid for pid in rows if (pid // MAXID in ia and pid % MAXID in ib) or (pid // MAXID in ib and pid % MAXID in ia)]
            c.executemany("delete from two_view_geometries where pair_id = ?", [(p,) for p in weg]); c.executemany("delete from matches where pair_id = ?", [(p,) for p in weg]); c.commit(); c.close()
            iv = {i: n for n, i in nm.items()}; ik = {nm[n] for n in K}; ws = set(weg)
            db_ = [dict(a=iv[p // MAXID], b=iv[p % MAXID], urteil="durchblick") for p, rw in rows.items() if rw >= EK.NACHBAR_MIN and (p // MAXID in ik or p % MAXID in ik) and p not in ws]
            json.dump(dict(durchblick=db_), open(sj, "w")); json.dump(dict(geloescht=len(weg), brueckenpaare=len(db_)), open(os.path.join(o_, "db_fertig.json"), "w"))
        for modus in a.modus:
            om = os.path.join(o_, modus); os.makedirs(om, exist_ok=True)
            if modus == "neu":
                ta = teil_neu(A, db, a.fotos, os.path.join(om, "teilA_map"), a.faeden); tb = teil_neu(B, db, a.fotos, os.path.join(om, "teilB_map"), a.faeden)
                if not ta or not tb: erg["faelle"].append(dict(k=k, modus=modus, grund="Teil nicht rechenbar")); continue
            else:
                ta = os.path.join(om, "teilA"); tb = os.path.join(om, "teilB")
                if not os.path.isfile(os.path.join(ta, "images.bin")): teilmodell(a.sparse, A, ta)
                if not os.path.isfile(os.path.join(tb, "images.bin")): teilmodell(a.sparse, B, tb, MB)
            rA = pycolmap.Reconstruction(ta); upA = None
            lot_roh = os.path.join(om, "lotfeld_roh.json"); roh = json.load(open(lot_roh)) if os.path.isfile(lot_roh) else None
            if a.lotfeld:
                ba, roh = TV.messen(rA, a.fotos, 4, None, roh); json.dump(roh, open(lot_roh, "w"))
            stufe = os.path.join(om, f"stufe_nm{a.nachmatchen}"); ej_p = os.path.join(stufe, "eck.json")
            def stufe_laufen(tb_, ziel):
                env = dict(os.environ, RCPARK_ECK_NACHMATCHEN=str(a.nachmatchen), RCPARK_ECK_VRAM_MB=os.environ.get("RCPARK_ECK_VRAM_MB", "2000"))
                t0 = time.time(); rc = subprocess.call([sys.executable, "-I", os.path.join(T, "seiten_eck_koppeln.py"), db, sj, a.fotos, "--aus", ziel, "--faeden", str(a.faeden),
                                                       f"--teil=0={ta}", f"--teil=1={tb_}"], stdout=open(ziel + ".log", "w"), stderr=subprocess.STDOUT, env=env)
                return rc, round(time.time() - t0)
            sek = None
            if not os.path.isfile(ej_p): os.makedirs(stufe, exist_ok=True); _, sek = stufe_laufen(tb, stufe)
            ej = json.load(open(ej_p)); varianten = {}
            # ALLE Zwischenmodelle der Stufe (23.11.: nur [0] genommen -> Kaufhaus koppelte in der Stufe ueber zwischen1, die Neukopplung meldete 'nicht gekoppelt')
            for zi, zw in enumerate(ej.get("zwischenmodelle") or []):
                if zw.get("varianten"): kand = {"sift": zw["varianten"]["sift"].get("modell"), "nachmatchen": zw["varianten"]["nachmatchen"].get("modell")}
                elif (zw.get("nachmatchen") or {}).get("rc") == 0: kand = {"nachmatchen": zw.get("modell")}
                else: kand = {"sift": zw.get("modell")}
                for v, mod in kand.items():
                    if mod: varianten.setdefault(v, []).append(mod)
            for vf in a.verformung:
                art, wert = (vf.split(":") + ["0"])[:2]; wert = float(wert)
                if art == "keine": tbv = tb
                else:
                    tbv = os.path.join(om, f"teilB_{art}_{wert:g}_fl")    # _fl: mit Fluchtpunkt-Lot verformt
                    if not os.path.isfile(os.path.join(tbv, "images.bin")): verformen_modell(tb, art, wert, _up_teil(tb, up, wahr), tbv)
                rB = pycolmap.Reconstruction(tbv); fall = f"{os.path.basename(a.aus.rstrip('/'))} k{k} {modus} {vf}"
                ergebnisse = {}
                if art == "keine" and (ej.get("teile") or {}).get("1", {}).get("ok"):
                    ergebnisse["stufe"] = bewerten(rA, rB, np.asarray(ej["teile"]["1"]["M_nach_A"]), wahr, brk, m_je, up)
                elif art == "keine": ergebnisse["stufe"] = dict(bewerten(rA, rB, None, wahr, brk, m_je, up), grund=ej.get("urteil"))
                if a.stufe_je_fall and art != "keine":
                    z_ = stufe + f"_{art}_{wert:g}"
                    if not os.path.isfile(os.path.join(z_, "eck.json")): os.makedirs(z_, exist_ok=True); stufe_laufen(tbv, z_)
                    e2 = json.load(open(os.path.join(z_, "eck.json"))); t1 = (e2.get("teile") or {}).get("1") or {}
                    ergebnisse["stufe"] = bewerten(rA, rB, np.asarray(t1["M_nach_A"]) if t1.get("ok") else None, wahr, brk, m_je, up)
                for v, mods in varianten.items():
                    M, prs = None, {}
                    for mod in mods:                                           # erstes Zwischenmodell, das A und B stimmig koppelt (wie die Stufe)
                        M, pr = kopplung_neu(mod, rA, rB); prs[os.path.basename(os.path.dirname(os.path.dirname(mod)))] = pr
                        if M is not None: break
                    z = bewerten(rA, rB, M, wahr, brk, m_je, up); z["pruefung"] = prs; ergebnisse[v] = z
                lf = None
                if a.lotfeld:
                    bb, roh = TV.messen(rB, a.fotos, 4, None, roh); json.dump(roh, open(lot_roh, "w"))
                    lf = dict(urteil=bb.get("urteil"), zeile=bb.get("zeile"), felder={x: {y: f_.get(y) for y in ("trend_grad", "se_grad", "t", "sprung_grad", "sprung_t", "gruppen_knick", "urteil")}
                                                                                   for x, f_ in (bb.get("felder") or {}).items()})
                eintrag = dict(k=k, modus=modus, verformung=vf, nachmatchen=a.nachmatchen, stufe_sekunden=sek, teil_a=ta, teil_b=tbv, kopplung=ergebnisse, lotfeld_b=lf)
                erg["faelle"].append(eintrag)
                for v, z in ergebnisse.items():
                    zl = zeile(f"{fall} [{v}]", z) + (f" | Lotfeld B {lf['urteil']}" if lf else ""); erg["zeilen"].append(zl); print(zl, flush=True)
                json.dump(erg, open(os.path.join(a.aus, "selbsttest2.json"), "w"), indent=1, ensure_ascii=False)
            if a.lotfeld: erg.setdefault("lotfeld_a", {})[f"k{k} {modus}"] = ba.get("zeile")
    erg["sekunden"] = round(time.time() - t_start); json.dump(erg, open(os.path.join(a.aus, "selbsttest2.json"), "w"), indent=1, ensure_ascii=False)


def _up_teil(tb, up, wahr):
    """Lot im Rahmen von Teil B (fuer die Verformung): Ursprungs-Lot per Sim3 B -> Ursprung (gemeinsame Kameras) zurueckgedreht."""
    rB = pycolmap.Reconstruction(tb); C = {im.name: im.projection_center() for im in rB.images.values() if im.has_pose and im.name in wahr}; n = sorted(C)
    s, R, _ = umeyama(np.array([C[x] for x in n]), np.array([wahr[x] for x in n])); u = R.T @ up; return u / np.linalg.norm(u)


if __name__ == "__main__": main()
