#!/usr/bin/env python3
"""innenwaende_finden.py <objekt.json> <fassaden-ordner> --arbeit DIR [--aus audit/innenwaende_auto.json] [--schreiben] [--nur f02,..]
   innenwaende_finden.py <objekt.json> --sicht_stl <modell.stl> <sicht.stl>      (Sicht-Modell fuer fassade_ortho der Innenwaende)
INNENWAENDE AUTOMATISCH FINDEN (18.11.2026, Ziel H0 von null, Luecke L2; Kettenstufe 'bauplan'). Zurueckgesetzte Wand hinter Arkade/Laube/Torhalle:
die Fotos sehen durch grosse Oeffnungen eine Flaeche deutlich HINTER der LoD2-Wand. Bisher trug ein Agent sie von Hand ein (Kaufhaus i00, Versatz -4,25).

Messung (KERNMETHODE: Triangulation mit den SfM-Kameras, keine Wolke; die Tiefe ist nur die LAGE): je Fassade mit grossen, bodennahen Oeffnungszonen des
Erkenners (fassade_parsing elemente.json, Klassen bogen/tuer/tor, >= 1,0 x 1,8 m, Unterkante <= 2 m) ein Ebenen-Sweep (tools/fassade_tiefe.py, GPU) ueber
w = -(Gebaeudetiefe + 1,5 m) .. +1 m (10 cm, Zelle 6 cm, Kosten ueber 21 Zellen = 1,26 m gemittelt, bis 24 Fotos). Ausgewertet werden nur die KERNE der Zonen
(ohne 20 % Rand je Seite = Pfeilerkanten, ohne oberes Drittel = Bogenzwickel, ohne unterste 15 % = Autos/Menschen) und nur sichere Zellen ('gut').
KRITERIUM Innenwand (alle Bedingungen):
  1. Wandtiefe (haeufigste sichere Tiefe) liegt INNEN im Suchbereich (am Rand = die Wand selbst nicht gefunden -> keine Aussage);
  2. Tiefenhistogramm der Kernzellen >= --min_tiefe (1,0 m) hinter der Wand (ohne die Randklassen des Suchbereichs) hat eine SPITZE >= --signifikanz (3) x Median
     der Klassen (Fehltiefen verteilen sich flach, eine echte Flaeche haeuft sich in EINER Tiefe);
  3. Zonen mit >= --zone_anteil (15 %) ihrer sicheren Kernzellen in der Spitze (+-0,4 m) gehoeren dazu; zusammen >= --min_m2 (2 m2);
  4. Spitze VOR der Gebaeuderueckseite (Strahl von der Zonenmitte entgegen der Normale gegen die LoD2-Waende, erster Treffer, - 0,5 m); sonst Durchblick
     (Tordurchfahrt/Durchgang) -> keine Innenwand.
Eintrag: versatz = Wandtiefe + Spitze (gegen die LoD2-Ebene), u = Huelle der Zonen +-0,2 m (ANNAHME: Wand laeuft hinter den Pfeilern durch), z = Zonen + 0,3 m oben,
zonen_davor = Erkennerzonen (fuer das Sicht-Modell). Kalibriert 18.11.2026: Kaufhaus f02 -> Versatz -4,36 (Hand -4,25), u -8,9..9,0 (Hand -8,4..9,0), z 0,78..5,5
(Hand 0,65..5,5), Signifikanz 15; Schwabentor (Tordurchfahrt) -> keine Innenwand.
Verworfen (gleicher Tag): Zonen-NCC-Kurve ueber die ganze Oeffnung (wie oeffnungen_wandbild.tiefe_sweep) - breite Buckel, Tiefen 1,3/2,0/2,9/-0,8 m statt 4,25;
Sweep-Kostenfenster 9 Zellen (54 cm) - Spitze nur 1,8 x Hintergrund.
Ausgabe: --aus JSON (je Fassade Zonen, Spitze, Befund), Bild <aus>.jpg (Foto | Tiefe; gelb Zonen, gruen Innenwand, rot Durchblick) - ANSEHEN.
--schreiben: objekt.json "innenwaende" (Eintraege mit "auto"); von Hand eingetragene (ohne "auto") werden NIE ueberschrieben (rc 3, Vorschlag nur in --aus).
Grenzen: braucht >= 3 Fotos mit Parallaxe in die Oeffnung; Rueckwand ohne Struktur (glatt, dunkel) -> keine sichere Tiefe; nur Waende parallel zur Fassade;
nur durch Erkennerzonen (findet OWLv2 die Boegen nicht, wird nicht gesucht).
"""
import os, sys, json, glob, argparse, subprocess, shutil, time, numpy as np, cv2

HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)


def wand_segmente(obj):
    """LoD2-Waende des eigenen Gebaeudes als 2D-Strecken (Modellrahmen wie fassaden.json)."""
    from fassade_ortho import lod2_waende
    waende, _ = lod2_waende(obj); S = []
    for P in waende:
        q = np.asarray(P, float)[:, :2]; c = q.mean(0); _, _, vt = np.linalg.svd(q - c); t = vt[0]; s = (q - c) @ t
        if np.ptp(s) > 0.05: S.append((c + s.min() * t, c + s.max() * t))
    return S


def gebaeudetiefe(S, Q, n, min_s=0.3):
    """Erster Treffer eines Strahls von Q entgegen der Normale n mit den Wandstrecken S (Abstand in m; inf = kein Treffer)."""
    r = -np.asarray(n, float); best = np.inf
    for A, B in S:
        e = B - A; M_ = np.array([[r[0], -e[0]], [r[1], -e[1]]])
        if abs(np.linalg.det(M_)) < 1e-9: continue
        s, t = np.linalg.solve(M_, A - Q)
        if s > min_s and -1e-6 <= t <= 1 + 1e-6: best = min(best, s)
    return best


def spitze(werte, lo, hi, schritt=0.1, glatt=3):
    """Hoechste Spitze des Tiefenhistogramms in [lo, hi]: (tiefe, hoehe, hintergrund = Median der Klassen)."""
    nb = max(int(round((hi - lo) / schritt)), 1); h, k = np.histogram(werte, bins=nb, range=(lo, hi)); hs = np.convolve(h, np.ones(glatt) / glatt, "same"); m = 0.5 * (k[1:] + k[:-1]); i = int(np.argmax(hs))
    return float(m[i]), float(hs[i]), max(float(np.median(hs)), 1.0)


def zonen_gross(elemente, zf0, min_b=1.0, min_h=1.8, boden=2.0, klassen=("bogen", "tuer", "tor")):
    """Grosse, bodennahe Oeffnungs-Zonen des Erkenners (fassade_parsing elemente.json): nur durch sie sieht man eine Innenwand (Arkade, Laube, Torhalle)."""
    Z = []
    for e in elemente:
        if e["klasse"] in klassen and e["u1"] - e["u0"] >= min_b and e["z1"] - e["z0"] >= min_h and e["z0"] <= zf0 + boden: Z.append((e["klasse"], e["u0"], e["u1"], e["z0"], e["z1"]))
    Z.sort(key=lambda z: z[1]); out = []
    for z in Z:                                                                     # ueberlappende Kaesten (Tuer im Bogen) zusammenfassen
        if out and z[1] < out[-1][2] - 0.2: q = out[-1]; out[-1] = (q[0], min(q[1], z[1]), max(q[2], z[2]), min(q[3], z[3]), max(q[4], z[4]))
        else: out.append(z)
    return out


def sicht_stl(objekt, stl_in, stl_out):
    """SICHT-MODELL fuer fassade_ortho auf Innenwaenden: das Kettenmodell ist vor der Innenwand noch voll (die Laube/Halle baut erst ein Bauteil), jeder Fotostrahl
    traefe die Aussenwand -> leeres Wandbild. Hier wird je Innenwand jede Erkennerzone davor (zonen_davor, Rechteck = ANNAHME, nur fuer die Sicht) von 0,5 m vor der
    Aussenwand bis genau auf die Innenwandebene ausgeschnitten: die Fotos sehen die Innenwand durch die Oeffnungen, Pfeiler dazwischen verdecken weiter.
    Nur fuer die Sicht der Wandbilder, nie ins Modell."""
    import trimesh
    from manifold3d import Manifold as M, Mesh
    obj = json.load(open(objekt)); k = obj.get("stl_massstab", 87) / 1000.0; tm = trimesh.load(stl_in); tm.apply_scale(k)
    m = M(Mesh(vert_properties=np.asarray(tm.vertices, np.float32), tri_verts=np.asarray(tm.faces, np.uint32))); n_ = 0
    for iw in obj.get("innenwaende", []):
        o = np.asarray(iw["a"], float); d = np.asarray(iw["b"], float) - o; d /= np.linalg.norm(d); n = np.asarray(iw["aussen"], float) - o; n = n - (n @ d) * d; n /= np.linalg.norm(n); vs = float(iw["versatz"])
        for u0, u1, z0, z1 in iw.get("zonen_davor", []):
            box = M.cube((u1 - u0, z1 - z0 + 0.5, 0.5 - vs)).translate((u0, z0 - 0.5, vs))          # Wandkoordinaten (u, z, w), w = vs .. +0.5
            T = [[d[0], 0.0, n[0], o[0]], [d[1], 0.0, n[1], o[1]], [0.0, 1.0, 0.0, 0.0]]; m = m - box.transform(T); n_ += 1
    me = m.to_mesh(); out = trimesh.Trimesh(np.asarray(me.vert_properties)[:, :3] / k, np.asarray(me.tri_verts)); out.export(stl_out); print(f"Sicht-Modell: {n_} Zonen bis auf die Innenwand geoeffnet -> {stl_out}"); return n_


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("ordner", nargs="?", help="Fassaden-Ordner der Stufe fenster (fassaden.json, elemente.json von fassade_parsing)"); ap.add_argument("--arbeit", help="eigener Ordner fuer die Tiefen-Sweeps (fassaden.json wird hineinkopiert)")
    ap.add_argument("--aus"); ap.add_argument("--schreiben", action="store_true"); ap.add_argument("--nur")
    ap.add_argument("--min_tiefe", type=float, default=1.0, help="m hinter der Wand (tiefer als Leibung/Nische; oeffnungen_bogen nimmt 0,6 m als Nische an)")
    ap.add_argument("--signifikanz", type=float, default=3.0, help="Spitze des Tiefenhistogramms mindestens so hoch wie dies x Median der tiefen Klassen"); ap.add_argument("--band", type=float, default=0.4)
    ap.add_argument("--zone_anteil", type=float, default=0.15, help="eine Zone gehoert zur Innenwand, wenn so viel ihrer sicheren Kernzellen in der Spitze (+-band) liegen"); ap.add_argument("--min_zellen", type=int, default=150); ap.add_argument("--min_m2", type=float, default=2.0, help="Flaeche der Kernzellen in der Spitze (m2)")
    ap.add_argument("--max_tiefe", type=float, default=15.0); ap.add_argument("--zelle", type=float, default=0.06); ap.add_argument("--dw", type=float, default=0.1); ap.add_argument("--fenster", type=int, default=21); ap.add_argument("--max_fotos", type=int, default=24)
    ap.add_argument("--sicht_stl", nargs=2, metavar=("STL_EIN", "STL_AUS"), help="nur das Sicht-Modell fuer fassade_ortho der Innenwaende schreiben (objekt.json innenwaende) und enden")
    a = ap.parse_args(); t0 = time.time()
    if a.sicht_stl: return 0 if sicht_stl(a.objekt, *a.sicht_stl) else 2
    if not a.ordner or not a.arbeit: ap.error("ordner und --arbeit noetig")
    obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); aus = a.aus or os.path.join(od, "audit", "innenwaende_auto.json")
    os.makedirs(a.arbeit, exist_ok=True); shutil.copy(os.path.join(a.ordner, "fassaden.json"), os.path.join(a.arbeit, "fassaden.json"))
    FS = json.load(open(os.path.join(a.arbeit, "fassaden.json")))["fassaden"]; EL = json.load(open(os.path.join(a.ordner, "elemente.json")))["fassaden"] if os.path.exists(os.path.join(a.ordner, "elemente.json")) else {}
    S = wand_segmente(obj); print(f"{len(S)} LoD2-Wandstrecken, Erkenner-Zonen auf {len(EL)} Fassaden")
    ergebnis = dict(zeit=time.strftime("%Y-%m-%d %H:%M"), objekt=os.path.relpath(a.objekt), kriterium={k: getattr(a, k) for k in ("min_tiefe", "signifikanz", "band", "zone_anteil", "min_zellen", "min_m2", "zelle", "dw", "fenster", "max_fotos")}, fassaden={}, innenwaende=[]); bilder = []
    for nr, F in enumerate(FS):
        fid = F.get("id") or f"f{nr:02d}"
        if F.get("innen") or (a.nur and fid not in a.nur.split(",")): continue
        o, d, n = np.array(F["o"], float), np.array(F["d"], float), np.array(F["n"], float); u0, u1 = F["u"]; zf0, zf1 = F["z"]; ZO = zonen_gross((EL.get(fid) or {}).get("elemente", []), zf0)
        if not ZO: ergebnis["fassaden"][fid] = dict(geprueft=False, grund="keine grosse bodennahe Oeffnungszone (bogen/tuer/tor) im Erkenner"); continue
        tg = {i_: gebaeudetiefe(S, o + 0.5 * (z_[1] + z_[2]) * d, n) for i_, z_ in enumerate(ZO)}; tmax = max([t_ for t_ in tg.values() if np.isfinite(t_)] or [a.max_tiefe]); wlo = -min(tmax + 1.5, a.max_tiefe)
        cmd = ["/media/oem/scan/venv-seg/bin/python", "-W", "ignore", "-I", os.path.join(HIER, "fassade_tiefe.py"), a.objekt, a.arbeit, str(nr), "--w", f"{wlo:.2f}", "1.0", "--dw", str(a.dw), "--zelle", str(a.zelle), "--fenster", str(a.fenster), "--max_fotos", str(a.max_fotos)]
        rc = subprocess.run(cmd, capture_output=True, text=True); npz = os.path.join(a.arbeit, f"tiefe_f{nr:02d}.npz"); vj = os.path.join(a.arbeit, f"vorbauten_f{nr:02d}.json")
        if rc.returncode not in (0, 4) or not os.path.exists(npz): ergebnis["fassaden"][fid] = dict(geprueft=False, grund=f"fassade_tiefe rc {rc.returncode}: " + " | ".join((rc.stdout + rc.stderr).splitlines()[-3:])[:300]); continue
        Dz = np.load(npz); w = Dz["w"]; gut = Dz["gut"]; c = float(Dz["zelle"]); V = json.load(open(vj)); ww = float(V["wand_versatz_m"]); H, Wd = w.shape; wr = w - ww
        U = u0 + (np.arange(Wd) + 0.5) * c; Z = zf1 - (np.arange(H) + 0.5) * c; kern = np.zeros((H, Wd), int) - 1
        for i_, (kl, zu0, zu1, zz0, zz1) in enumerate(ZO):                       # Kern der Oeffnung: ohne Pfeilerkanten (20 % je Seite) und Bogenzwickel (oberes Drittel), ohne den untersten Streifen (Autos, Menschen)
            b_ = zu1 - zu0; h_ = zz1 - zz0; kern[np.ix_((Z > zz0 + 0.15 * h_) & (Z < zz0 + 0.65 * h_), (U > zu0 + 0.2 * b_) & (U < zu1 - 0.2 * b_))] = i_
        lo, hi = wlo - ww + 0.35, -a.min_tiefe; tief = gut & (kern >= 0) & (wr <= hi) & (wr >= lo)
        e = dict(geprueft=True, fotos=len(V.get("fotos", [])), wand_versatz=ww, sweep=[round(wlo, 2), 1.0], zonen=[dict(klasse=z_[0], zone=[round(x, 2) for x in z_[1:]], gebaeudetiefe=round(tg[i_], 2) if np.isfinite(tg[i_]) else None) for i_, z_ in enumerate(ZO)], befund="keine Innenwand")
        gruen = np.zeros((H, Wd), bool); rot = np.zeros((H, Wd), bool)
        if not (wlo + 3 * a.dw < ww < 1.0 - 3 * a.dw): e["befund"] = f"keine Innenwand (Wandtiefe {ww:+.2f} am Rand des Suchbereichs = Wand selbst nicht gefunden, Sweep nicht belastbar)"
        elif tief.sum() >= a.min_zellen:
            p, hoch, bg = spitze(wr[tief], lo, hi, a.dw); sig = hoch / bg; inband = tief & (np.abs(wr - p) <= a.band); e.update(spitze_rel=round(p, 2), signifikanz=round(sig, 2), zellen_tief=int(tief.sum()))
            dabei = []
            for i_, z_ in enumerate(ZO):
                gk = gut & (kern == i_); ant = float(inband[kern == i_].sum() / max(gk.sum(), 1)); e["zonen"][i_].update(anteil_spitze=round(ant, 3), sichere_zellen=int(gk.sum()))
                durch = bool(np.isfinite(tg[i_]) and -(p + ww) >= tg[i_] - 0.5); e["zonen"][i_]["durchblick"] = durch
                if ant >= a.zone_anteil: (rot if durch else gruen)[inband & (kern == i_)] = True; dabei.append((i_, durch))
            iw = [i_ for i_, du in dabei if not du]; db = [i_ for i_, du in dabei if du]
            fl_iw = float((inband & np.isin(kern, iw)).sum() * c * c); e["flaeche_spitze_m2"] = round(fl_iw, 2)
            if sig >= a.signifikanz and iw and len(iw) >= len(db) and fl_iw >= a.min_m2:
                g = [ZO[i_] for i_ in iw]; vs = round(p + ww, 2); ua = max(u0, min(z_[1] for z_ in g) - 0.2); ub = min(u1, max(z_[2] for z_ in g) + 0.2); za = min(z_[3] for z_ in g); zb = min(zf1, max(z_[4] for z_ in g) + 0.3)
                name = f"i{len(ergebnis['innenwaende']):02d}"; wv = wr[inband & np.isin(kern, iw)]
                ergebnis["innenwaende"].append(dict(name=name, fassade=fid, a=[round(float(x), 4) for x in o], b=[round(float(x), 4) for x in o + d], aussen=[round(float(x), 4) for x in o + n], versatz=vs,
                    u=[round(ua, 2), round(ub, 2)], z=[round(float(za), 2), round(zb, 2)], relief_vorn=round(min(0.5, 0.5 * abs(vs)), 2), auto="bauplan " + time.strftime("%Y-%m-%d"),
                    tiefe_hinter_wand=round(-p, 2), streuung=[round(float(np.percentile(wv, 10)), 2), round(float(np.percentile(wv, 90)), 2)], signifikanz=round(sig, 2), zonen=len(g), zonen_davor=[[round(float(x), 2) for x in z_[1:]] for z_ in ZO if z_[2] > ua and z_[1] < ub],      # alle grossen Zonen im u-Bereich (auch ohne eigene sichere Tiefe: Autos davor) - fuer das Sicht-Modell
                    quelle=f"tools/innenwaende_finden.py: Ebenen-Sweep (fassade_tiefe.py, {e['fotos']} Fotos, Fenster {a.fenster} x {a.zelle * 100:.0f} cm) an Fassade {fid}, Kerne von {len(g)} grossen Oeffnungszonen des Erkenners: "
                           f"Tiefenspitze {-p:.2f} m hinter der Wandflaeche (Wand {ww:+.2f} gegen LoD2), Signifikanz {sig:.1f}; Gebaeudetiefe dort (LoD2) >= {min(tg[i_] for i_ in iw):.1f} m -> keine Durchsicht. "
                           "Tiefe = nur LAGE; u = Huelle der Zonen +-0,2 m (ANNAHME: Wand laeuft hinter den Pfeilern durch), z = Zonen + 0,3 m; a/b = Fassadenrahmen (u wie fassaden.json)"))
                e["befund"] = f"Innenwand {name} ({-p:.2f} m hinter der Wand, Signifikanz {sig:.1f})"
            elif sig >= a.signifikanz and db: e["befund"] = f"Durchblick durch das Gebaeude ({-(p + ww):.1f} m >= Gebaeudetiefe - 0,5) - Durchfahrt, keine Innenwand"
            else: e["befund"] = f"keine Innenwand (Spitze {-p:.2f} m, Signifikanz {sig:.1f}, {fl_iw:.1f} m2, Zonen dabei {len(dabei)})"
        if e["befund"] == "keine Innenwand" and tief.sum() < a.min_zellen: e["befund"] = f"keine Innenwand ({int(tief.sum())} sichere tiefe Kernzellen < {a.min_zellen})"
        ergebnis["fassaden"][fid] = e; print(f"{fid}: {e['befund']}", flush=True)
        jb = cv2.imread(os.path.join(a.arbeit, f"tiefe_f{nr:02d}.jpg"))
        if jb is not None and jb.shape[1] == 2 * Wd and jb.shape[0] == H:
            for k_ in (0, Wd):
                ov = jb[:, k_:k_ + Wd]; ov[gruen] = (0.4 * ov[gruen] + (0, 150, 0)).astype(np.uint8); ov[rot] = (0.4 * ov[rot] + (0, 0, 150)).astype(np.uint8)
                for kl, zu0, zu1, zz0, zz1 in ZO: cv2.rectangle(ov, (int((zu0 - u0) / c), int((zf1 - zz1) / c)), (int((zu1 - u0) / c), int((zf1 - zz0) / c)), (0, 255, 255), 1)
            s_ = 2.0 if Wd < 500 else 1.0; jb = cv2.resize(jb, None, fx=s_, fy=s_, interpolation=cv2.INTER_NEAREST)
            kopf = np.full((40, max(jb.shape[1], 700), 3), 255, np.uint8); cv2.putText(kopf, f"{fid}: {e['befund']}"[:110], (5, 16), 0, 0.5, (0, 0, 0), 1); cv2.putText(kopf, f"links Foto, rechts Tiefe {wlo:.1f}..+1 m; gelb Erkennerzone, gruen Innenwand, rot Durchblick", (5, 34), 0, 0.45, (0, 0, 0), 1)
            jb = np.pad(jb, ((0, 0), (0, kopf.shape[1] - jb.shape[1]), (0, 0)), constant_values=255); bilder.append(np.vstack([kopf, jb]))
    if bilder:
        Wm = max(b.shape[1] for b in bilder); cv2.imwrite(aus[:-5] + ".jpg", np.vstack([np.pad(b, ((0, 6), (0, Wm - b.shape[1]), (0, 0)), constant_values=255) for b in bilder]))
    os.makedirs(os.path.dirname(aus), exist_ok=True); json.dump(ergebnis, open(aus, "w"), indent=1, ensure_ascii=False)
    print(f"{len(ergebnis['innenwaende'])} Innenwand/-waende gefunden ({time.time() - t0:.0f} s) -> {aus}: " + "; ".join(f"{x['name']} an {x['fassade']} Versatz {x['versatz']:+.2f} u {x['u']} z {x['z']}" for x in ergebnis["innenwaende"]))
    if a.schreiben:
        alt = obj.get("innenwaende") or []
        if any(not x.get("auto") for x in alt): print("objekt.json hat VON HAND eingetragene innenwaende - NICHT ueberschrieben (Vorschlag nur in", aus, ")"); return 3
        if ergebnis["innenwaende"]: obj["innenwaende"] = ergebnis["innenwaende"]
        else: obj.pop("innenwaende", None)
        __import__("json_sicher").schreiben(a.objekt, obj); print("objekt.json innenwaende:", [x["name"] for x in ergebnis["innenwaende"]])
    return 0


if __name__ == "__main__":
    sys.exit(main())
