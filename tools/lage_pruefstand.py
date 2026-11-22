#!/usr/bin/env python3
"""lage_pruefstand.py - LAGE-PRUEFSTAND: Ausrichtung + Lage-Tore der Gesamtkette auf GESPEICHERTEN Staenden in Minuten statt in einem 60-90-min-Kettenlauf (22.11.2026).

WARUM: in der Sitzung 22.11. kostete jede Aenderung an der Ausrichtung einen ganzen Kettenlauf, und dreimal rechneten zwei Stufen dieselbe Groesse verschieden
(Lot Mittel/Achsen, GPS Tor/Ausrichtung, GPS-Kameraauswahl). Lehre: eine Funktion, ein Pruefstand. Hier laufen die ECHTEN Funktionen der Kette (Import, keine Kopie):
  Ausrichtung   sfm_lod2_ausrichten.ausrichten (mit denselben Argumenten wie pipeline_objekt/gesamtkette: --kameras --dicht --name --radius 30 --schreiben --fotos --loesung K)
  GPS-Tor       lage_gps_pruefen.main;  Lageproben-Tor lage_proben.tor_rc;  Urteil lage_proben.lage_bestanden (wie gesamtkette.tore)
  Grundriss     wolke_grundriss_pruefen.main;  Wanddicke wand_dicke_tor.py (Unterprozess in venv-colmap wie in der Kette, braucht pycolmap)
  Teil-Beleg    seiten_lage_beleg.lage_belegt je Seitenteil aus pipe/sfm/seiten_modelle.json (neu bewertet gegen den gespeicherten Entscheid)
und dazu die Gegenproben, an denen sich zwei Stufen widersprechen koennen:
  Lot           Lot der Ausrichtung (Kameraebene/Kamerablick) gegen seiten_gps_vereinen.lot_aus_bild_achsen auf denselben Kameras (Grad)
  GPS-Kameras   Auswahl der Ausrichtung (gps_massstab -> gps_kameras_alle) gegen die des GPS-Tors (lage_gps_pruefen.gps_daten): Anzahl, nur hier / nur dort
  GPS-Fit       Veto der Ausrichtung (gps_tor_urteil auf der gewaehlten Loesung) gegen das GPS-Tor auf der geschriebenen Datei (rc, Drehung, Massstab)
  EINE FUNKTION eigene Zeile je Loesung (eine_funktion, 22.11.2026): Kameramenge, GPS-Ehrlichkeit (Anker-Urteil, Gruppen, Sigma), GPS-Veto-rc gegen GPS-Tor-rc, Lot
                gegen lot_info - ROT bei jeder Abweichung (seit heute rechnen beide Stufen diese Groessen mit denselben Funktionen; ROT = jemand hat eine Kopie eingebaut)
  Referenz      Kamerastandorte der neuen Lage gegen Referenz-Ausrichtungen (gleiche Fotonamen, robuste 3D-Aehnlichkeit): Versatz m, Drehung/Kippung Grad, Massstab;
                Referenz 'kette' = die von der Kette geschriebene Ausrichtung desselben Stands (Probe = Kette?).
NUR LESEND auf Kettenordner und Repo: objekt.json wird nach <aus>/<stand>/objekt.json kopiert (fotos_dir absolut), dort schreiben Ausrichtung (messprotokoll/, sfm/,
Zwischenstand .ausr_zwischen) und Tore (audit/). Fehlende Eingaben -> Stand 'fehlt' (mit Liste), kein Absturz.
Zwischenstand: die Ausrichtung haelt Grobsuche und Feinfits nach INHALT (sfm_lod2_ausrichten.Zwischenstand) - zweiter Lauf mit gleichem Datenstand rechnet nur noch,
was sich geaendert hat (z. B. Veto/Proben). Abschalten: --ohne-cache (= AUSR_ZWISCHEN=0). Der Cache aendert das Ergebnis nicht (tools/test_lage_pruefstand.py).
GPU: Standard 'auto' = CPU, solange ein rcpark-Kettenjob laeuft (systemctl --user), sonst GPU; --cpu / --gpu erzwingen. RAM ~1-2 GB je Stand (dichte Wolke 8 Mio Punkte).
Aufruf:  tools/py tools/lage_pruefstand.py [--stand schwabentor-1120 ...] [--aus DIR] [--loesungen 0|0,1|alle|kreislauf] [--ohne-tore] [--ohne-cache] [--cpu|--gpu]
         (Konfig tools/lage_pruefstand.json, eigene mit --konfig). Ausgabe: je Stand eine Zeile + <aus>/<stand>/pruefstand.json, alles in <aus>/pruefstand.json.
Exit 0 = gelaufen (Urteile stehen in den Zeilen), 2 = Konfig/Stand unbekannt."""
import os, sys, io, json, time, math, argparse, contextlib, subprocess
import numpy as np

T = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(T); sys.path.insert(0, T)
STANDARD_KONFIG = os.path.join(T, "lage_pruefstand.json")


# ---------- Konfig und Pfade
def konfig_laden(pfad):
    k = json.load(open(pfad)); k.setdefault("staende", {}); k.setdefault("ausrichtung_args", []); return k


def _abs(p, wurzel):
    return p if (not p or os.path.isabs(p)) else os.path.join(wurzel, p)


def stand_pfade(st, wurzel):
    """Eintrag der Konfig -> Pfade wie in der Kette (gesamtkette: D = daten, P = D/pipe, FV = D/fotos, Z = wurzel/modelle/<ziel>)."""
    D = _abs(st.get("daten", ""), wurzel); P = os.path.join(D, "pipe"); ziel = st["ziel"]
    z = dict(ziel=ziel, objekt=_abs(st.get("objekt") or f"modelle/{ziel}/objekt.json", wurzel), daten=D,
             kameras=_abs(st.get("kameras") or os.path.join(P, "kameras.json"), wurzel), dicht=_abs(st.get("dicht") or os.path.join(P, "dicht", "fused.ply"), wurzel),
             fotos=_abs(st.get("fotos") or os.path.join(D, "fotos"), wurzel), seiten_modelle=_abs(st.get("seiten_modelle") or os.path.join(P, "sfm", "seiten_modelle.json"), wurzel),
             kette_au=_abs(st.get("kette_ausrichtung") or f"modelle/{ziel}/messprotokoll/SFM-AUSRICHTUNG-{ziel}.json", wurzel))
    z["referenzen"] = {n: _abs(p, wurzel) for n, p in (st.get("referenzen") or {}).items()}
    return z


def fehlende(z):
    """Pflicht-Eingaben der Ausrichtung -> Liste der fehlenden (leer = laeuft)."""
    f = [f"{k} {z[k]}" for k in ("objekt", "kameras", "dicht") if not os.path.isfile(z[k])]
    if not os.path.isdir(z["fotos"]): f.append(f"fotos {z['fotos']}")
    return f


def objekt_kopie(objekt, ordner, fotos):
    """objekt.json -> <ordner>/objekt.json mit fotos_dir absolut (Kette: --fotos FV). Nur schreiben, wenn sich der Inhalt aendert (Dateizeit bleibt fuer Zwischenstaende)."""
    o = json.load(open(objekt)); o["fotos_dir"] = os.path.abspath(fotos); o["_pruefstand"] = dict(quelle=os.path.abspath(objekt), hinweis="Kopie des Lage-Pruefstands - nicht bearbeiten")
    os.makedirs(ordner, exist_ok=True); ziel = os.path.join(ordner, "objekt.json"); text = json.dumps(o, indent=1, ensure_ascii=False)
    if not (os.path.isfile(ziel) and open(ziel, encoding="utf-8").read() == text): open(ziel, "w", encoding="utf-8").write(text)
    return ziel


class Mitschrift:
    """stdout in eine Datei (und auf Wunsch weiter auf den Bildschirm) - die Werkzeuge drucken ihre Begruendungen, der Pruefstand zeigt nur die Zeile."""
    def __init__(self, pfad, laut=False): self.f = open(pfad, "a", encoding="utf-8"); self.laut = laut; self.alt = sys.stdout
    def write(self, s):
        self.f.write(s)
        if self.laut: self.alt.write(s)
    def flush(self): self.f.flush(); self.alt.flush()
    def __enter__(self): sys.stdout = self; return self
    def __exit__(self, *e): sys.stdout = self.alt; self.f.close()


def _rc_aus(fn, argv):
    """main(argv) eines Werkzeugs im Prozess: Rueckgabe/SystemExit -> rc (None = 0, Text = 1 wie python)."""
    try: r = fn(argv); return int(r or 0)
    except SystemExit as e:
        c = e.code
        return 0 if c is None else (c if isinstance(c, int) else 1)


# ---------- Vergleich zweier Lagen (Kamerastandorte im Modellsystem)
def aehnlichkeit3d(A, B, runden=4, min_n=6):
    """Robuste 3D-Aehnlichkeit B ~ s R A + t (Umeyama, getrimmt: Nachfit auf Reste < max(80-%-Wert, 1 m)). -> (s, R, t, Maske) oder None."""
    A = np.asarray(A, float); B = np.asarray(B, float); w = np.isfinite(A).all(1) & np.isfinite(B).all(1)
    for _ in range(runden):
        if w.sum() < min_n: return None
        ma, mb = A[w].mean(0), B[w].mean(0); A0, B0 = A[w] - ma, B[w] - mb; U, S, Vt = np.linalg.svd(B0.T @ A0 / w.sum()); E = np.eye(3); E[2, 2] = np.sign(np.linalg.det(U @ Vt))
        R = U @ E @ Vt; s = float((S * np.diag(E)).sum() / max((A0 ** 2).sum() / w.sum(), 1e-12)); t = mb - s * R @ ma
        r = np.linalg.norm(s * A @ R.T + t - B, axis=1); w = np.isfinite(r) & (r < max(float(np.percentile(r[np.isfinite(r)], 80)), 1.0))
    return s, R, t, w


def namen_schluessel(n):
    """Fotoname ohne Ordner/Endung (Kette: eigen__IMG_x)."""
    return os.path.splitext(os.path.basename(str(n)))[0]


def lage_vergleich(kam, ref, nah_m=150.0):
    """kam, ref: {Fotoname: [x, y, z] im Modellsystem}. Nur gemeinsame Fotos, Referenzkameras < nah_m von der Objektmitte (ferne Kameras kippen den Fit).
    -> dict(n, versatz_median_m (roh, ohne Fit), versatz_mitte_m (wohin die Referenz die Objektmitte legt, waagerecht), drehung_grad (um das Lot), kippung_grad,
    massstab (Groesse hier / Referenz), rest_median_m) oder dict(n, grund)."""
    a = {namen_schluessel(k): v for k, v in kam.items()}; b = {namen_schluessel(k): v for k, v in ref.items()}
    gem = sorted(k for k in a if k in b and np.isfinite(np.asarray(a[k], float)).all() and np.isfinite(np.asarray(b[k], float)).all())
    A = np.array([a[k] for k in gem], float).reshape(-1, 3); B = np.array([b[k] for k in gem], float).reshape(-1, 3)
    if len(gem): nah = np.hypot(B[:, 0], B[:, 1]) < nah_m; A, B = A[nah], B[nah]
    if len(A) < 6: return dict(n=int(len(A)), grund=f"nur {len(A)} gemeinsame Kameras (< 6) - kein Vergleich")
    f = aehnlichkeit3d(A, B)
    if f is None: return dict(n=int(len(A)), grund="Aehnlichkeit nicht bestimmbar")
    s, R, t, w = f; r = np.linalg.norm(s * A @ R.T + t - B, axis=1)
    return dict(n=int(len(A)), n_fit=int(w.sum()), versatz_median_m=round(float(np.median(np.linalg.norm(A - B, axis=1))), 3), versatz_mitte_m=round(float(np.hypot(t[0], t[1])), 3),
                drehung_grad=round(float(math.degrees(math.atan2(R[1, 0], R[0, 0]))), 3), kippung_grad=round(float(math.degrees(math.acos(min(1.0, abs(float(R[2, 2])))))), 3),
                massstab=round(float(1.0 / s), 4), rest_median_m=round(float(np.median(r[w])), 3))


def kameras_aus_au(pfad):
    try: return {k: v["standort"] for k, v in (json.load(open(pfad)).get("kameras") or {}).items() if v.get("standort") is not None}
    except Exception: return None


# ---------- Gegenproben zwischen den Stufen
def lot_vergleich(E, kameras_json):
    """Lot der Ausrichtung (E['lot']) gegen seiten_gps_vereinen.lot_aus_bild_achsen auf denselben Kameras (beides SfM-System). -> dict (Grad)."""
    import seiten_gps_vereinen as SG
    KJ = json.load(open(kameras_json)); Rs = np.array([np.asarray(d["R"], float) for d in KJ["bilder"]]); ach = np.asarray(SG.lot_aus_bild_achsen(Rs), float)
    w = lambda u, v: None if u is None else round(float(math.degrees(math.acos(min(1.0, abs(float(np.dot(np.asarray(u, float) / np.linalg.norm(u), v / np.linalg.norm(v)))))))), 3)
    L = E.get("lot") or {}
    return dict(quelle_ausrichtung=L.get("quelle"), ausrichtung_gegen_bildachsen_grad=w(L.get("oben"), ach), ebene_gegen_bildachsen_grad=w(L.get("ebene"), ach),
                blick_gegen_bildachsen_grad=w(L.get("blick"), ach), ebene_gegen_blick_grad=L.get("winkel_ebene_blick_grad"), flach=L.get("flach"))


def gps_vergleich(E, au_pfad, fotos, lgp_json, mitte_utm=None):
    """GPS-Kameraauswahl und GPS-Fit: Ausrichtung (E['gps']) gegen GPS-Tor (gps_daten + audit/lage_gps.json). -> dict."""
    import lage_gps_pruefen as LGP, sfm_lod2_ausrichten as SA
    erg = {}; ga = (E.get("gps") or {}).get("alle")
    kam = (json.load(open(au_pfad)).get("kameras") or {}) if au_pfad and os.path.isfile(au_pfad) else {}
    with contextlib.redirect_stdout(io.StringIO()): nt, *_ = LGP.gps_daten(kam, fotos, mitte_utm=mitte_utm) if kam else ([],)
    na = list(ga["namen"]) if ga else []
    erg["kameras"] = dict(ausrichtung=len(na), tor=len(nt), nur_ausrichtung=sorted(set(na) - set(nt))[:20], nur_tor=sorted(set(nt) - set(na))[:20],
                          n_nur_ausrichtung=len(set(na) - set(nt)), n_nur_tor=len(set(nt) - set(na)))
    tor = (json.load(open(lgp_json)) if lgp_json and os.path.isfile(lgp_json) else {}).get("gps_fit")
    if ga and E.get("kameras_gewaehlt") is not None:                                     # Veto der Ausrichtung auf der GEWAEHLTEN Loesung (Kamerastandorte ungerundet)
        Xm = np.asarray(E["kameras_gewaehlt"], float)[np.asarray(ga["idx"], int), :2]
        rc_a, ea = SA.gps_tor_urteil(ga["namen"], Xm, np.asarray(ga["Mxy"], float), ga["zeiten"]); fa = ea.get("gps_fit") or {}
        erg["fit"] = dict(ausrichtung=dict(rc=rc_a, drehung_grad=fa.get("drehung_grad"), massstab=fa.get("massstab"), warnungen=ea.get("warnungen")),
                          tor=dict(drehung_grad=(tor or {}).get("drehung_grad"), massstab=(tor or {}).get("massstab")))
        if tor and fa: erg["fit"]["unterschied"] = dict(drehung_grad=round(float(fa["drehung_grad"]) - float(tor["drehung_grad"]), 3), massstab=round(float(fa["massstab"]) - float(tor["massstab"]), 4))
        L_ = json.load(open(lgp_json)) if lgp_json and os.path.isfile(lgp_json) else None
        erg["fit"]["tor"]["rc"] = None if L_ is None or not L_.get("geprueft") else (3 if (L_.get("warnungen") or not L_.get("gps_fit")) else 0)
    erg["ehrlich"] = dict(ausrichtung=_ehrlich_kurz((E.get("gps") or {}).get("fit")), tor=_ehrlich_kurz(tor, tor=True))
    return erg


EHRLICH_TOL_GRAD, EHRLICH_TOL_REL, LOT_TOL_GRAD = 0.5, 0.25, 0.1   # Pruefstand-Toleranzen 'eine Funktion' (keine Torgrenzen): Sigma darf zwischen Lotsystem (Ausrichtung) und
                                                                    # fertiger Lage (Tor) um Rundung/Kippung schwanken, das URTEIL (Anker ja/nein, Gruppen) nicht; Lot = dieselbe Funktion


def _ehrlich_kurz(f, tor=False):
    """GPS-Ehrlichkeit aus dem Fit der Ausrichtung (E['gps']['fit']) bzw. des Tors (lage_gps.json 'gps_fit') -> dict(anker, sd_drehung_grad, n_gruppen) oder None."""
    if not f or (not tor and not f.get("ok")): return None
    sy = f.get("systematik") or {}
    return dict(anker=bool(f.get("lage_festgelegt")) if tor else f.get("anker") is not None, sd_drehung_grad=f.get("sd_drehung_grad"), n_gruppen=sy.get("n_gruppen"))


def eine_funktion(gv, lot, ausrichtung_veto=None):
    """ZEILE 'eine Funktion' (22.11.2026): rechnen Ausrichtung und Lage-Tore dieselben Groessen gleich? gv = gps_vergleich(), lot = lot_vergleich().
    Prueft (1) GPS-Kameramenge (gleiche Fotonamen), (2) GPS-Ehrlichkeit (Anker-Urteil + Zahl der Gruppen gleich, Sigma Drehung innerhalb max(EHRLICH_TOL_GRAD,
    EHRLICH_TOL_REL x Tor)), (3) GPS-Veto gegen GPS-Tor (gleicher rc auf der gewaehlten Loesung), (4) Lot der Ausrichtung = seiten_gps_vereinen.lot_info (<= LOT_TOL_GRAD).
    -> dict(farbe gruen/rot/grau, abweichungen [Text], je {name: True/False/None})."""
    ab, je = [], {}
    k = (gv or {}).get("kameras")
    if k: je["kameramenge"] = k["n_nur_ausrichtung"] == 0 and k["n_nur_tor"] == 0
    if je.get("kameramenge") is False: ab.append(f"GPS-Kameramenge Ausrichtung {k['ausrichtung']} / Tor {k['tor']} (nur Ausrichtung {k['n_nur_ausrichtung']}, nur Tor {k['n_nur_tor']})")
    eh = (gv or {}).get("ehrlich") or {}; ea, et = eh.get("ausrichtung"), eh.get("tor")
    if ea and et:
        tol = max(EHRLICH_TOL_GRAD, EHRLICH_TOL_REL * float(et["sd_drehung_grad"] or 0))
        je["ehrlichkeit"] = ea["anker"] == et["anker"] and ea["n_gruppen"] == et["n_gruppen"] and abs(float(ea["sd_drehung_grad"]) - float(et["sd_drehung_grad"])) <= tol
        if not je["ehrlichkeit"]: ab.append(f"GPS-Ehrlichkeit Ausrichtung +-{ea['sd_drehung_grad']:.1f} Grad, {ea['n_gruppen']} Gruppe(n), {'ankert' if ea['anker'] else 'legt nicht fest'} / "
                                            f"Tor +-{et['sd_drehung_grad']:.1f} Grad, {et['n_gruppen']} Gruppe(n), {'ankert' if et['anker'] else 'legt nicht fest'}")
    elif ea or et: je["ehrlichkeit"] = False; ab.append(f"GPS-Ehrlichkeit nur in {'der Ausrichtung' if ea else 'dem Tor'} gerechnet")
    fi = (gv or {}).get("fit") or {}
    if (fi.get("ausrichtung") or {}).get("rc") is not None and (fi.get("tor") or {}).get("rc") is not None:
        je["veto"] = fi["ausrichtung"]["rc"] == fi["tor"]["rc"]
        if not je["veto"]: ab.append(f"GPS-Veto rc {fi['ausrichtung']['rc']} / GPS-Tor rc {fi['tor']['rc']} auf derselben Lage")
    w = (lot or {}).get("ausrichtung_gegen_bildachsen_grad")
    if w is not None:
        je["lot"] = float(w) <= LOT_TOL_GRAD
        if not je["lot"]: ab.append(f"Lot der Ausrichtung ({lot.get('quelle_ausrichtung')}) {float(w):.2f} Grad neben seiten_gps_vereinen.lot_info")
    farbe = "grau" if not je else ("gruen" if all(je.values()) else "rot")
    return dict(farbe=farbe, abweichungen=ab, je=je)


def seiten_beleg(smj):
    """Regel 'Teil nur bei belegter Lage' neu bewerten (seiten_lage_beleg.lage_belegt) gegen den in seiten_modelle.json gespeicherten Entscheid. -> Liste je Teil."""
    import seiten_lage_beleg as SLB
    sm = json.load(open(smj)); out = []
    for e in sm.get("teile") or []:
        v = e.get("vereinen")
        if not isinstance(v, dict) or not v.get("weg"): continue
        belegt, grund, _ = SLB.lage_belegt(v); alt = (v.get("lage_belegt") or {}).get("belegt")
        out.append(dict(teil=e.get("teil"), weg=v.get("weg"), belegt=bool(belegt), gespeichert=alt, gleich=(alt is None or bool(alt) == bool(belegt)), grund=str(grund)[:300]))
    return out


# ---------- Tore (wie gesamtkette.tore, Ausgaben in den eigenen Ordner)
def tore(z, ok_, au, wolke, cfg, log):
    """ok_ = objekt.json-Kopie. -> dict je Tor: rc, farbe (gruen/rot/grau), wert (kurz), datei."""
    import sfm_lod2_ausrichten as SA  # noqa: F401  (gleiches sys.path wie die Kette)
    import lage_proben as LPR
    od = os.path.dirname(ok_); au_j = json.load(open(au)); g = {}
    # GPS-Tor
    import lage_gps_pruefen as LGP
    with Mitschrift(log): rc = _rc_aus(LGP.main, [ok_, au, "--fotos", z["fotos"]])
    lj = os.path.join(od, "audit", "lage_gps.json"); L = json.load(open(lj)) if os.path.isfile(lj) else {}; gf = L.get("gps_fit") or {}
    g["gps"] = dict(rc=rc, farbe=("gruen" if rc == 0 and L.get("geprueft") else "grau" if rc == 0 else "rot"), datei=lj,
                    wert=(f"{gf['drehung_grad']:+.1f} Grad x{gf['massstab']:.3f}" if gf else str(L.get("ergebnis"))) + (f" ({'; '.join(L.get('warnungen') or [])})" if L.get("warnungen") else ""))
    # Lageproben (aus der geschriebenen Ausrichtung)
    rc_p, txt_p = LPR.tor_rc(au_j.get("transformation"))
    g["lage_proben"] = dict(rc=rc_p, farbe="grau" if rc_p is None else "gruen" if rc_p == 0 else "rot", wert=(((au_j.get("transformation") or {}).get("lage_proben") or {}).get("ergebnis")), text=txt_p)
    # Grundriss-Tor
    import wolke_grundriss_pruefen as WG
    with Mitschrift(log): rc = _rc_aus(WG.main, [ok_, "--wolke", wolke])
    gj = os.path.join(od, "audit", "wolke_grundriss.json"); Gr = json.load(open(gj)) if os.path.isfile(gj) else {}; sa = Gr.get("strasse") or {}
    hf = [h for h in (sa.get("haufen") or []) if not h.get("geklaert")]
    g["grundriss"] = dict(rc=rc, farbe="gruen" if rc == 0 else "rot", datei=gj, bild=os.path.join(od, "audit", "wolke_grundriss.png"),
                          wert=(f"A {100 * sa['anteil']:.1f} %" + (f", Haufen {hf[0]['punkte']} bei {hf[0]['mitte']}" if hf else "") if sa.get("anteil") is not None else str(Gr.get("ergebnis"))))
    # Wanddicke (Unterprozess wie in der Kette: braucht pycolmap)
    if os.environ.get("RCPARK_WANDDICKE", "1") == "0": g["wand_dicke"] = dict(rc=None, farbe="grau", wert="abgeschaltet (RCPARK_WANDDICKE=0)")
    elif not os.path.isfile(z["seiten_modelle"]): g["wand_dicke"] = dict(rc=None, farbe="grau", wert="fehlt: keine seiten_modelle.json")
    else:
        wj = os.path.join(od, "audit", "wand_dicke.json"); py = cfg.get("python_colmap") or sys.executable
        with open(log, "a") as lf: rc = subprocess.run([py, "-I", os.path.join(T, "wand_dicke_tor.py"), ok_, "--seiten", z["seiten_modelle"], "--ausrichtung", au, "--aus", wj],
                                                       stdout=lf, stderr=subprocess.STDOUT, cwd=ROOT, timeout=1800).returncode
        W = json.load(open(wj)) if os.path.isfile(wj) else {}
        g["wand_dicke"] = dict(rc=rc, farbe="gruen" if rc == 0 else "rot" if rc == 3 else "grau", wert=str(W.get("urteil"))[:200], datei=wj)
    # Teil-Beleg (Regel 'nur bei belegter Lage')
    if os.path.isfile(z["seiten_modelle"]):
        try:
            sb = seiten_beleg(z["seiten_modelle"])
            g["teil_beleg"] = dict(rc=None, farbe="grau" if not sb else ("gruen" if all(x["gleich"] for x in sb) else "rot"), teile=sb,
                                   wert=", ".join(f"Teil {x['teil']} {'belegt' if x['belegt'] else 'weg'}{'' if x['gleich'] else ' (ANDERS als gespeichert)'}" for x in sb) or "kein GPS-Teil")
        except Exception as e: g["teil_beleg"] = dict(rc=None, farbe="grau", wert=f"nicht lesbar: {type(e).__name__} {e}")
    else: g["teil_beleg"] = dict(rc=None, farbe="grau", wert="fehlt: keine seiten_modelle.json")
    g["bestanden"] = LPR.lage_bestanden(dict(gps=g["gps"]["rc"], grundriss=g["grundriss"]["rc"], lage_proben=rc_p, seiten_blick=None))
    return g


# ---------- ein Stand
def _json_sicher(x):
    if isinstance(x, np.ndarray): return x.tolist()
    if isinstance(x, (np.floating, np.integer)): return x.item()
    if isinstance(x, (set, tuple)): return list(x)
    return str(x)


def loesung_kurz(E, l, referenzen):
    """Eine Loesung aus E['loesungen'] -> kurze Fassung + Vergleich ihrer Kamerastandorte mit den Referenzen."""
    kam = {n: c for n, c in zip(E["namen"], np.asarray(l["kameras_modell"], float).tolist())}
    return dict(guete=round(l["guete"], 4), massstab_sfm_je_m=round(l["massstab"], 5), anker=l["anker"], wandfit=l["wandfit"],
                referenz={n: lage_vergleich(kam, r) for n, r in referenzen.items() if r})


def pruefe_stand(name, st, cfg, a):
    t0 = time.time(); wurzel = a.wurzel or cfg.get("wurzel") or ROOT; z = stand_pfade(st, wurzel); od = os.path.join(a.aus, name)
    R = dict(stand=name, ziel=z["ziel"], pfade={k: v for k, v in z.items() if k != "referenzen"}, zeit=time.strftime("%Y-%m-%d %H:%M"))
    f = fehlende(z)
    if f: R.update(status="fehlt", fehlt=f); return R
    ok_ = objekt_kopie(z["objekt"], od, z["fotos"]); log = os.path.join(od, "pruefstand.log"); open(log, "a").write(f"\n===== {R['zeit']} Stand {name}\n")
    refs = {"kette": kameras_aus_au(z["kette_au"])}; refs.update({n: kameras_aus_au(p) for n, p in z["referenzen"].items()})
    R["referenzen_fehlen"] = [n for n, r in refs.items() if r is None]
    import sfm_lod2_ausrichten as SA
    basis = [ok_, "--kameras", z["kameras"], "--dicht", z["dicht"], "--name", z["ziel"]] + list(cfg.get("ausrichtung_args") or []) + ["--schreiben", "--fotos", z["fotos"]]
    if a.ohne_cache: os.environ["AUSR_ZWISCHEN"] = "0"
    ks = [0] if a.loesungen in ("0", "kreislauf") else (None if a.loesungen == "alle" else [int(x) for x in a.loesungen.split(",")])
    au = os.path.join(od, "messprotokoll", f"SFM-AUSRICHTUNG-{z['ziel']}.json"); wolke = os.path.join(od, "sfm", f"punkte_modell_{z['ziel']}.npy")
    R["laeufe"] = []; k = ks[0] if ks else 0; E0 = None
    while True:
        t1 = time.time()
        try:
            with Mitschrift(log, laut=a.laut): E = SA.ausrichten(basis + ["--loesung", str(k)])
        except Exception as e:
            R["laeufe"].append(dict(loesung=k, status="abgestuerzt", fehler=f"{type(e).__name__}: {e}")); break
        if E0 is None: E0 = E
        lauf = dict(loesung=k, rc=E["rc"], geschrieben=E.get("loesung_nr"), n_unterscheidbar=E["n_unterscheidbar"], sekunden_ausrichtung=round(time.time() - t1, 1),
                    zwischenstand=E.get("zwischenstand"))
        if E["rc"] == 5 and E.get("loesung_nr") is None: lauf["status"] = "keine solche Loesung"; R["laeufe"].append(lauf); break
        kam_neu = {n: c for n, c in zip(E["namen"], np.asarray(E["kameras_gewaehlt"], float).tolist())}
        lauf["referenz"] = {n: lage_vergleich(kam_neu, r) for n, r in refs.items() if r}
        lauf["massstab_sfm_je_m"] = E["transformation"]["s"]; lauf["lageproben"] = (E.get("lage_proben") or {}).get("ergebnis")
        if not a.ohne_tore:
            t2 = time.time(); lauf["tore"] = tore(z, ok_, au, wolke, cfg, log); lauf["sekunden_tore"] = round(time.time() - t2, 1)
            try:
                _mu = ((json.load(open(ok_)).get("rahmen") or {}).get("mitte_utm"))
                lauf["gps_vergleich"] = gps_vergleich(E, au, z["fotos"], os.path.join(od, "audit", "lage_gps.json"), mitte_utm=_mu)
            except Exception as e: lauf["gps_vergleich"] = dict(fehler=f"{type(e).__name__}: {e}")
            try: lauf["eine_funktion"] = eine_funktion(lauf.get("gps_vergleich"), lot_vergleich(E, z["kameras"]))
            except Exception as e: lauf["eine_funktion"] = dict(farbe="rot", abweichungen=[f"nicht pruefbar: {type(e).__name__}: {e}"], je={})
        R["laeufe"].append(lauf)
        if ks is None: k += 1; ks_ok = k < E["n_unterscheidbar"]
        elif a.loesungen == "kreislauf": ks_ok = not (lauf.get("tore") or {}).get("bestanden") and k < a.max_loesung; k += 1
        else: ks = ks[1:]; ks_ok = bool(ks); k = ks[0] if ks else k
        if not ks_ok or E["rc"] == 5: break
    if E0 is not None:
        try: R["lot"] = lot_vergleich(E0, z["kameras"])
        except Exception as e: R["lot"] = dict(fehler=f"{type(e).__name__}: {e}")
        R["loesungen"] = [loesung_kurz(E0, l, refs) for l in E0["loesungen"]]
        gf = (E0.get("gps") or {}).get("fit") or {}
        R["gps_ausrichtung"] = dict(ok=gf.get("ok"), n=gf.get("n"), rest_median_m=gf.get("rest_median_m"), sd_drehung_grad=gf.get("sd_drehung_grad"), sd_massstab=gf.get("sd_massstab"),
                                    anker=gf.get("anker"), n_fern_inlier=gf.get("n_fern_inlier"), veto_kameras=(E0.get("gps") or {}).get("veto_kameras"), startmassstab=(E0.get("gps") or {}).get("startmassstab"))
    R["status"] = "gelaufen" if R["laeufe"] and R["laeufe"][0].get("rc") is not None else "abgestuerzt"; R["sekunden"] = round(time.time() - t0, 1)
    json.dump(R, open(os.path.join(od, "pruefstand.json"), "w"), indent=1, ensure_ascii=False, default=_json_sicher)
    return R


def zeile(R):
    """Eine Zeile je Stand (und Loesung): Lage gegen Referenz, jedes Tor mit Farbe und Wert."""
    if R.get("status") == "fehlt": return f"{R['stand']}: FEHLT - " + "; ".join(R["fehlt"])
    teile = []
    for l in R.get("laeufe") or []:
        if l.get("status"): teile.append(f"{R['stand']} L{l['loesung']}: {l['status']} {l.get('fehler', '')}".rstrip()); continue
        s = [f"{R['stand']} L{l['loesung']}/{l['n_unterscheidbar']}"]
        for n, v in (l.get("referenz") or {}).items():
            s.append(f"Ref {n}: " + (f"{v['versatz_median_m']:.2f} m / {v['drehung_grad']:+.2f} Grad / x{v['massstab']:.3f}" if "massstab" in v else v.get("grund", "?")))
        tg = l.get("tore") or {}
        for n in ("gps", "lage_proben", "grundriss", "wand_dicke", "teil_beleg"):
            if n in tg: s.append(f"{n} {tg[n]['farbe'].upper()} ({tg[n].get('wert')})")
        if tg: s.append("LAGE " + ("BESTANDEN" if tg.get("bestanden") else "NICHT bestanden"))
        gv = (l.get("gps_vergleich") or {}).get("kameras")
        if gv: s.append(f"GPS-Kameras Ausr {gv['ausrichtung']} / Tor {gv['tor']} (nur Ausr {gv['n_nur_ausrichtung']}, nur Tor {gv['n_nur_tor']})")
        fu = ((l.get("gps_vergleich") or {}).get("fit") or {}).get("unterschied")
        if fu: s.append(f"GPS-Fit Ausr-Tor {fu['drehung_grad']:+.2f} Grad / {fu['massstab']:+.4f}")
        ef = l.get("eine_funktion")
        if ef: s.append(f"eine Funktion {ef['farbe'].upper()}" + (f" ({'; '.join(ef['abweichungen'])})" if ef["abweichungen"] else f" ({', '.join(k_ for k_, v_ in ef['je'].items() if v_)} gleich)"))
        s.append(f"{l.get('sekunden_ausrichtung', 0):.0f}+{l.get('sekunden_tore', 0):.0f} s")
        teile.append(" | ".join(s))
    lo = R.get("lot") or {}
    if lo.get("ausrichtung_gegen_bildachsen_grad") is not None: teile.append(f"{R['stand']} Lot ({lo['quelle_ausrichtung']}) gegen Bild-x-Achsen {lo['ausrichtung_gegen_bildachsen_grad']:.2f} Grad")
    return "\n".join(teile)


def kettenjob_aktiv():
    try:
        r = subprocess.run(["systemctl", "--user", "list-units", "--type=service", "--state=active", "--no-legend", "rcpark-*"], capture_output=True, text=True, timeout=10)
        return any(l.strip() for l in r.stdout.splitlines())
    except Exception: return True                                                       # unbekannt -> vorsichtig CPU


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--konfig", default=STANDARD_KONFIG); ap.add_argument("--stand", nargs="*", help="Namen aus der Konfig (Standard: alle)")
    ap.add_argument("--aus", default=None, help="Ausgabeordner (Standard: Konfig 'aus', sonst /media/oem/rcdaten/tmp/lage_pruefstand)")
    ap.add_argument("--wurzel", default=None, help="Repo-Wurzel fuer relative Pfade der Konfig (Standard: Konfig 'wurzel')")
    ap.add_argument("--loesungen", default="0", help="0 | Liste 0,1,2 | alle (jede unterscheidbare Loesung) | kreislauf (wie gesamtkette: 0, dann 1.. bis die Lage besteht)")
    ap.add_argument("--max-loesung", type=int, default=3, dest="max_loesung"); ap.add_argument("--ohne-tore", action="store_true", dest="ohne_tore")
    ap.add_argument("--ohne-cache", action="store_true", dest="ohne_cache"); ap.add_argument("--laut", action="store_true", help="Werkzeugausgaben auch auf den Bildschirm")
    g = ap.add_mutually_exclusive_group(); g.add_argument("--cpu", action="store_true"); g.add_argument("--gpu", action="store_true")
    a = ap.parse_args(argv)
    try: cfg = konfig_laden(a.konfig)
    except Exception as e: print(f"Konfig {a.konfig} nicht lesbar: {type(e).__name__} {e}"); return 2
    a.aus = os.path.abspath(a.aus or cfg.get("aus") or "/media/oem/rcdaten/tmp/lage_pruefstand")
    namen = a.stand or list(cfg["staende"])
    unbekannt = [n for n in namen if n not in cfg["staende"]]
    if unbekannt: print("unbekannte Staende:", ", ".join(unbekannt), "- Konfig:", ", ".join(cfg["staende"])); return 2
    cpu = a.cpu or (not a.gpu and kettenjob_aktiv())
    if cpu: os.environ["CUDA_VISIBLE_DEVICES"] = ""                                     # vor jedem torch-Import (Werkzeuge importieren torch erst beim Aufruf)
    print(f"LAGE-PRUEFSTAND {time.strftime('%Y-%m-%d %H:%M')} - {'CPU' if cpu else 'GPU'}, Ausgabe {a.aus}, Loesungen {a.loesungen}" + (", OHNE Zwischenstand" if a.ohne_cache else ""), flush=True)
    os.makedirs(a.aus, exist_ok=True); alle = []
    for n in namen:
        try: R = pruefe_stand(n, cfg["staende"][n], cfg, a)
        except Exception as e: R = dict(stand=n, status="abgestuerzt", laeufe=[dict(loesung=0, status="abgestuerzt", fehler=f"{type(e).__name__}: {e}")])
        alle.append(R); print(zeile(R), flush=True)
    json.dump(dict(zeit=time.strftime("%Y-%m-%d %H:%M"), geraet="cpu" if cpu else "gpu", staende=alle), open(os.path.join(a.aus, "pruefstand.json"), "w"), indent=1, ensure_ascii=False, default=_json_sicher)
    print("Ergebnis:", os.path.join(a.aus, "pruefstand.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
