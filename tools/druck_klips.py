#!/usr/bin/env python3
"""druck_klips.py <modell.stl> --mitte x,y,z --normal nx,ny,nz (--radius R | --rechteck B,H) [--name uhr] [--aus ORDNER] [--schicht_mm 0.08]
Ein Wanddetail (Uhr, Wappen, Schild, Zierteil) als eigenes KLIPSTEIL fuer den feinen Drucker aus dem Modell loesen - allgemein fuer jedes Gebaeude.

Anlass 17.11.2026 (Nutzer: "solche Details soll doch der Bambu drucken und dann klipsen wir es drauf"; Uhr als Handskript gedruckt: "extrem gut",
aber die Stiftloecher (1,2 mm tief in 1,26 mm Feld) schienen vorne durch, die Zeiger schwebten beim ersten Versuch -> Spaghetti).
Eingabe: Modell-STL in Druck-mm (Druckmassstab, z nach oben), Mitte des Details auf/vor der Wand, Wandnormale nach AUSSEN (nur Richtung, z-Anteil wird ignoriert),
Umriss im Wandbild: Kreis (--radius, mm) oder Rechteck (--rechteck Breite,Hoehe mm). Alle Masse in den Einheiten des STL (Druck-mm).
Verfahren:
  1. Schnittebene: von vorn die erste Ebene, auf der das Detail seinen Umriss zu 90 % fuellt (seine Grundplatte), --boden_mm (0,8) dahinter. Der Wandring wird nur gemeldet.
  2. Detail = Modell geschnitten mit dem Umrissprisma vor der Wand (w >= w0); Wand = Modell ohne dieses Prisma (Wandflaeche dort plan bei w0).
  3. Detail in Drucklage: Rueckseite aufs Bett, Schauseite nach oben; frei Haengendes wird unterfuettert (tools/druck_luft.py), damit nichts in der Luft beginnt.
  4. Stiftloecher (fuer 1,75-mm-Filament als Stift, Bohrung --loch_mm 1,9): nur wo das Teil mindestens Lochtiefe + --haut_mm (0,6) dick ist; zwei Stellen moeglichst weit
     auseinander auf der waagerechten Achse. In der Wand dieselben Stellen als DURCHGEHENDE Bohrung (duenne Wand), Stiftlaenge = Lochtiefe + Wanddicke dort.
Ausgabe (--aus): <name>_klips.stl (Drucklage), <name>_wand.stl (Modell ohne Detail, mit Gegenloechern), <name>_klips.json (Masse, Stifte, Luftinseln).
Grenzen: Wand muss um das Detail eben sein (Ring); Details, die ueber Wandkanten/Ecken greifen, werden am Umriss abgeschnitten; Gegenloecher sitzen im Wandmodell -
dieses muss dann statt des alten Modells in den Bausatz (tools/bausatz.sh) gehen.
"""
import sys, os, json, argparse, numpy as np, trimesh
from manifold3d import Manifold as M, Mesh, CrossSection as CS, FillRule, OpType
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, "tools"))
from bauteile import stl_schreiben
import druck_luft


def zu_mf(tm): return M(Mesh(vert_properties=np.asarray(tm.vertices, np.float32), tri_verts=np.asarray(tm.faces, np.uint32)))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("stl"); ap.add_argument("--mitte", required=True); ap.add_argument("--normal", required=True)
    ap.add_argument("--radius", type=float, default=0.0); ap.add_argument("--rechteck", default=""); ap.add_argument("--name", default="detail"); ap.add_argument("--aus", default="")
    ap.add_argument("--loch_mm", type=float, default=1.9); ap.add_argument("--loch_tief_mm", type=float, default=1.5); ap.add_argument("--haut_mm", type=float, default=0.6)
    ap.add_argument("--aufsatz", default="", help="Hoehenbaender (mm ueber der Rueckseite) 'z0-z1,z1-z2': alles darueber wird abgetrennt, je Band ein FLACHES Teil (Zeiger)")
    ap.add_argument("--zeiger_min_mm", type=float, default=1.0, help="Mindestdicke flacher Aufsaetze (Zeiger)")
    ap.add_argument("--achse_mm", type=float, default=0.0, help="Achsloch in der Detailmitte durch Blatt und Aufsaetze (z. B. 1.9 fuer Filamentstift)")
    ap.add_argument("--farbe_ab_mm", type=float, default=0.0, help="Farbwechsel ab dieser Hoehe melden (z. B. Oberkante Zifferblatt -> Ziffern andere Farbe)")
    ap.add_argument("--schicht_mm", type=float, default=0.08); ap.add_argument("--vor_mm", type=float, default=0.0, help="Schnitt zusaetzlich so weit nach vorn"); ap.add_argument("--boden_mm", type=float, default=0.8, help="Grundplatte unter der vollen Detailebene")
    a = ap.parse_args()
    if (a.radius > 0) == bool(a.rechteck): sys.exit("genau eines von --radius oder --rechteck angeben")
    aus = a.aus or os.path.dirname(os.path.abspath(a.stl)); os.makedirs(aus, exist_ok=True)
    tm = trimesh.load(a.stl, process=True); mo = zu_mf(tm)
    c = np.array([float(v) for v in a.mitte.split(",")]); n = np.array([float(v) for v in a.normal.split(",")]); n[2] = 0; n /= np.linalg.norm(n)
    u = np.array([-n[1], n[0], 0.0]); v = np.array([0.0, 0.0, 1.0])                 # u waagerecht in der Wand, v senkrecht; (u, v, n) rechtshaendig
    R = a.radius if a.radius > 0 else 0.5 * float(np.hypot(*[float(t) for t in a.rechteck.split(",")]))
    # 1. Wandebene messen
    ang = np.linspace(0, 2 * np.pi, 72, endpoint=False); rr = R * np.array([1.15, 1.3, 1.5]); o = []
    for r_ in rr:
        for t_ in ang: o.append(c + r_ * (np.cos(t_) * u + np.sin(t_) * v) + 50.0 * n)
    o = np.array(o); loc, ri, _ = tm.ray.intersects_location(o, np.tile(-n, (len(o), 1)), multiple_hits=False)
    if len(ri) < 20: print(f"FEHLER: Wand um das Detail nicht gefunden ({len(ri)} Treffer von {len(o)})"); return 2
    w_tr = (loc - c) @ n; w0 = float(np.median(w_tr)); streu = float(np.percentile(np.abs(w_tr - w0), 80))
    print(f"Wandflaeche: w0 = {w0:+.2f} mm vor der Mitte, Streuung (80 %) {streu:.2f} mm aus {len(ri)} Strahlen" + ("  ACHTUNG: Wand um das Detail uneben" if streu > 0.5 else ""))
    if a.radius > 0: um = CS.circle(a.radius, 128)
    else: B, H = [float(t) for t in a.rechteck.split(",")]; um = CS.square((B, H), True)
    # Normale aus der Schauseite selbst (17.11.2026: Turmwand stand leicht schraeg zur angegebenen Normale, kein Schnitt fuellte den Umriss): Strahlen auf das Detail,
    # robuste Ebene (RANSAC) durch die Treffer - jede Stufe des Details ist dazu parallel, die groesste genuegt.
    g_ = np.linspace(-0.9 * R, 0.9 * R, 41); o2 = np.array([c + x * u + y * v + 50.0 * n for x in g_ for y in g_ if x * x + y * y <= (0.9 * R) ** 2])
    l2, _, _ = tm.ray.intersects_location(o2, np.tile(-n, (len(o2), 1)), multiple_hits=False); rng = np.random.default_rng(0); best = (0, n)
    for _ in range(400):
        q = l2[rng.choice(len(l2), 3, replace=False)]; nq = np.cross(q[1] - q[0], q[2] - q[0])
        if np.linalg.norm(nq) < 1e-9: continue
        nq /= np.linalg.norm(nq); nq = nq if nq @ n > 0 else -nq
        if nq @ n < 0.95: continue
        k = int((np.abs((l2 - q[0]) @ nq) < 0.05).sum())
        if k > best[0]: best = (k, nq)
    if best[0] > 0.2 * len(l2):
        inl = l2[np.abs((l2 - l2[0]) @ best[1]) < 1e9]; n = best[1]; u = np.cross(np.array([0.0, 0.0, 1.0]), n); u /= np.linalg.norm(u); v = np.cross(n, u)
        print(f"Normale aus der Schauseite: {np.degrees(np.arccos(np.clip(best[1] @ np.array([float(x) for x in a.normal.split(',')]) / np.linalg.norm([float(x) for x in a.normal.split(',')]), -1, 1))):.2f} Grad gegen die Angabe ({best[0]} von {len(l2)} Treffern auf einer Ebene)")
    # Schnittebene (17.11.2026, Uhr Schwabentor: das Steinrelief um die Uhr stand so hoch wie das Zifferblatt - Ring-Median lag MITTEN im Blatt, Detail halb):
    # von vorn nach hinten die erste Ebene, auf der der Querschnitt den Umriss zu >= 90 % fuellt (= Grundplatte des Details), dann --boden_mm tiefer.
    T0 = np.array([[u[0], u[1], u[2], -c @ u], [v[0], v[1], v[2], -c @ v], [n[0], n[1], n[2], -c @ n]]); lok0 = mo.transform(T0.tolist()) ^ um.extrude(200.0).translate((0, 0, -100.0))
    z_voll = None
    for z_ in np.arange(float(lok0.bounding_box()[5]) - 0.02, float(lok0.bounding_box()[2]), -0.05):
        if lok0.slice(float(z_)).area() >= 0.9 * um.area(): z_voll = float(z_); break
    if z_voll is None: print("FEHLER: das Detail fuellt seinen Umriss nirgends (Umriss zu gross?)"); return 2
    wc = z_voll - a.boden_mm + a.vor_mm
    print(f"Grundplatte des Details voll ab w = {z_voll:+.2f} mm; Schnitt bei {wc:+.2f} mm (Boden {a.boden_mm} mm); Wand-Ring-Median {w0:+.2f} mm")
    # lokales System: Weltpunkt p -> (p-c)@u, (p-c)@v, (p-c)@n - wc
    T = np.array([[u[0], u[1], u[2], -c @ u], [v[0], v[1], v[2], -c @ v], [n[0], n[1], n[2], -c @ n - wc]])
    Ti = np.linalg.inv(np.vstack([T, [0, 0, 0, 1]]))[:3]
    lok = mo.transform(T.tolist())
    hoch = float(lok.bounding_box()[5]) + 10.0
    prisma = um.extrude(hoch)                                                       # lokal: z = w (vor der Wand), ab w = 0 (Schnittflaeche)
    detail = lok ^ prisma; wand_l = lok - prisma
    if detail.is_empty(): print("FEHLER: vor der Wand liegt im Umriss nichts"); return 2
    st = sorted(detail.decompose(), key=lambda k: -k.volume()); detail = M.batch_boolean(st, OpType.Add) if len(st) > 1 else st[0]
    if len(st) > 1: print(f"  Detail besteht aus {len(st)} Stuecken (kleinste {st[-1].volume():.2f} mm3)")
    aufsaetze = []
    if a.aufsatz:                                                                  # 17.11.2026 Nutzer: Zeiger getrennt (Blatt blau malen, Ziffern/Zeiger gold) - je Band ein flaches Teil
        bd = [tuple(float(x) for x in b_.split("-")) for b_ in a.aufsatz.split(",")]; z_cut = min(b_[0] for b_ in bd); oben = detail.trim_by_plane((0, 0, 1), z_cut); detail = detail.trim_by_plane((0, 0, -1), -z_cut)
        achse = CS.circle(max(2.0, a.achse_mm), 32)
        def an_achse(k_): return (k_.project() ^ achse).area() > 0.05
        oz = oben.decompose(); zeig = [k_ for k_ in oz if an_achse(k_)]; rest = [k_ for k_ in oz if not an_achse(k_)]   # Zeiger haengen an der Nabe; Wulste/Ringe bleiben am Blatt
        if rest: detail = detail + M.batch_boolean(rest, OpType.Add); print(f"  {len(rest)} Stueck(e) ueber {z_cut} mm ohne Nabe bleiben am Blatt (Wulste, Ringe)")
        zg = M.batch_boolean(zeig, OpType.Add) if zeig else M(); flach = []
        for z0, z1 in bd: flach.append(zg.trim_by_plane((0, 0, 1), z0).trim_by_plane((0, 0, -1), -z1).project() if not zg.is_empty() else CS())
        for k in range(len(flach) - 1, 0, -1):                                      # Teile eines oberen Bands ohne Nabe (z. B. dicke Sonne am Stundenzeiger) gehoeren zum Band darunter
            lo = [s_ for s_ in flach[k].decompose() if (s_ ^ achse).area() <= 0.05]
            if lo: flach[k - 1] = flach[k - 1] + CS.batch_boolean(lo, OpType.Add); flach[k] = flach[k] - CS.batch_boolean(lo, OpType.Add)
        for k, ((z0, z1), fl) in enumerate(zip(bd, flach)):
            if fl.is_empty(): print(f"  Aufsatz-Band {z0}-{z1} mm leer"); continue
            dk = max(a.zeiger_min_mm, z1 - z0); teil = fl.extrude(dk)                     # 17.11.2026 Druck v4: Stundenzeiger 0,68 mm loeste sich und wurde Faeden, Minutenzeiger 1,1 mm gut -> mind. 1,0 mm
            if a.achse_mm > 0: teil = teil - M.cylinder(dk + 1, a.achse_mm / 2, a.achse_mm / 2, 24).translate((0, 0, -0.5))
            import bauteile as _bt                                                    # Kneifkanten hier schliessen und danach plan schneiden - sonst setzt stl_schreiben 0,25-mm-Kugeln UNTER die Bettflaeche (Luftinseln)
            teil = _bt.kneifkanten_schliessen(teil, r=0.25, stellen=3).trim_by_plane((0, 0, 1), 0.0).trim_by_plane((0, 0, -1), -dk)
            aufsaetze.append((k + 1, teil, z0, z1, dk))
    if a.achse_mm > 0: detail = detail - M.cylinder(50, a.achse_mm / 2, a.achse_mm / 2, 24).translate((0, 0, -1))
    # 3. Drucklage = lokal (Rueckseite z = 0); unterfuettern
    li, zs, S = druck_luft.luftinseln(detail, a.schicht_mm, 45.0, 2.0, 5.0); bb = detail.bounding_box(); runde = 0
    while li and runde < 6:
        runde += 1; stuetz = []
        for x in li:
            z_unten = bb[2]
            for j in range(x["i"] - 1, -1, -1):
                if not (S[j] ^ x["cs"]).is_empty(): z_unten = float(zs[j]); break
            stuetz.append(x["cs"].offset(0.2, druck_luft.JoinType.Round, 2.0, 12).extrude(x["z"] - z_unten + 0.02).translate((0, 0, z_unten - 0.01)))
        detail = detail + M.batch_boolean(stuetz, OpType.Add); li, zs, S = druck_luft.luftinseln(detail, a.schicht_mm, 45.0, 2.0, 5.0)
    print(f"Detail: {bb[3] - bb[0]:.1f} x {bb[4] - bb[1]:.1f} x {bb[5]:.2f} mm, {detail.volume():.0f} mm3; Luftinseln danach: {len(li)}" + (f" (unterfuettert in {runde} Runde(n))" if runde else ""))
    # 4. Stiftloecher: Dicke je Stelle = erste Austrittshoehe eines Strahls von unten
    dm = trimesh.Trimesh(*(lambda m_: (m_.vert_properties[:, :3], m_.tri_verts))(detail.to_mesh()))
    def dicke(x, y):
        l_, _, _ = dm.ray.intersects_location([[x, y, -1.0]], [[0, 0, 1.0]], multiple_hits=True)
        z_ = np.sort(l_[:, 2]) if len(l_) else np.array([])
        return float(z_[1]) if len(z_) >= 2 else 0.0                                 # Eintritt bei 0, Austritt = erste Oberseite
    r_max = (a.radius if a.radius > 0 else 0.5 * B) - a.loch_mm
    stellen = []
    for s_ in (1, -1):
        best = None
        for x in np.linspace(r_max, 0.25 * r_max, 25) * s_:
            d_ = dicke(x, 0.0)
            if d_ >= a.haut_mm + 0.5: t_ = min(a.loch_tief_mm, d_ - a.haut_mm); best = (x, t_, d_); break
        if best: stellen.append(best)
    if len(stellen) < 2: print("ACHTUNG: keine zwei Stellen mit genug Material fuer Stiftloecher - Detail wird nur geklebt")
    loch = []
    for x, t_, d_ in stellen: loch.append(M.cylinder(t_ + 0.01, a.loch_mm / 2, a.loch_mm / 2, 24).translate((x, 0, -0.01)))
    if loch: detail = detail - M.batch_boolean(loch, OpType.Add)
    # Wand: durchgehende Gegenloecher (Wand ist duenn), Stiftlaenge
    stifte = []; wloch = []
    for x, t_, d_ in stellen:
        p0 = c + x * u + wc * n; l_, _, _ = tm.ray.intersects_location([p0 + 0.01 * n], [-n], multiple_hits=True)
        wd = float(np.sort(((p0 - l_) @ n))[1]) if len(l_) >= 2 else 3.0               # Wanddicke: zweiter Treffer = Innenseite
        wd = min(wd, 6.0); wloch.append(M.cylinder(wd + 0.4, a.loch_mm / 2, a.loch_mm / 2, 24).translate((x, 0, -wd - 0.2)))
        stifte.append(dict(u_mm=round(x, 2), loch_tief_mm=round(t_, 2), teil_dicke_mm=round(d_, 2), wand_dicke_mm=round(wd, 2), stift_laenge_mm=round(t_ + wd, 1)))
    if wloch: wand_l = wand_l - M.batch_boolean(wloch, OpType.Add)
    wand = wand_l.transform(Ti.tolist())
    fk = os.path.join(aus, f"{a.name}_klips.stl"); fw = os.path.join(aus, f"{a.name}_wand.stl")
    stl_schreiben(detail, fk, b"rcpark klips"); stl_schreiben(wand, fw, b"rcpark wand ohne klips")
    ok_k = trimesh.load(fk).is_watertight; ok_w = trimesh.load(fw).is_watertight
    for k, teil, z0, z1, dk in aufsaetze:
        fa = os.path.join(aus, f"{a.name}_aufsatz{k}.stl"); stl_schreiben(teil, fa, b"rcpark aufsatz"); bb_ = teil.bounding_box()
        print(f"  Aufsatz {k} (Band {z0}-{z1} mm, flach {dk:.2f} mm): {bb_[3] - bb_[0]:.1f} x {bb_[4] - bb_[1]:.1f} mm, {len(teil.decompose())} Stueck(e) -> {fa}")
    if a.farbe_ab_mm > 0:
        sch = int(round(a.farbe_ab_mm / a.schicht_mm)); print(f"  FARBWECHSEL: ab {a.farbe_ab_mm:.2f} mm (Schicht {sch} bei {a.schicht_mm} mm, erste Schicht 0,2 mm mitgezaehlt pruefen) - darueber andere Farbe (z. B. Ziffern gold)")
    for s in stifte: print(f"  Stift bei u {s['u_mm']:+.1f} mm: Loch {s['loch_tief_mm']} mm im Teil (dort {s['teil_dicke_mm']} mm dick), Wand {s['wand_dicke_mm']} mm -> Filamentstift 1,75 x {s['stift_laenge_mm']} mm")
    print(f"-> {fk} (wasserdicht {ok_k}), {fw} (wasserdicht {ok_w})")
    import json_sicher; json_sicher.schreiben(os.path.join(aus, f"{a.name}_klips.json"), dict(quelle=os.path.abspath(a.stl), mitte=c.tolist(), normal=n.tolist(), wand_w0_mm=round(w0, 3), wand_streuung_mm=round(streu, 3),
                                                                                        masse_mm=[round(bb[3] - bb[0], 1), round(bb[4] - bb[1], 1), round(bb[5], 2)], stifte=stifte, luftinseln=len(li)))
    return 0 if (ok_k and ok_w and not li) else 3


if __name__ == "__main__":
    sys.exit(main())
