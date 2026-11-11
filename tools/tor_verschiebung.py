#!/usr/bin/env python3
"""tor_verschiebung.py - NULLKONTROLLE fuer das Foto-Tor ("F1 nachher > vorher"), Rippen-Befund 11.11. (rippen_diag/BERICHT.md).

Problem: die Teil-Foto-F1 (teil_fotoform -> foto_diff, Toleranz 0,14 m, Zellen ~9 cm) wirkt auf reich verzierten Flaechen wie ein DICHTEMASS: Rippen um
0,3/0,6 m verschoben oder um 90 Grad gedreht erreichten HOEHERE F1 als die richtigen. Ein Tor "nachher > vorher" kann also Dichte statt Lage belohnen.

Kontrolle: das Ziel-Teil wird um +-VERSATZ (Standard 0,3 m, > 2 x Toleranz 0,14 m) in der Hauptfassadenebene des Teils (waagerecht entlang der Fassade
+-t und senkrecht +-z) verschoben, jede Variante im GANZEN Modell (alle anderen Teile unveraendert) mit derselben teil_fotoform-Messung (gleiche Fotos,
gleicher Skalenfaktor, GLEICHER Bildbereich) bewertet. Ist die echte Lage nicht besser als die verschobenen, misst die F1 Dichte, nicht Lage.

  marge = f1_echt - max(f1_versatz)  (Kennzahl wie gefordert); lage_belegt = marge_min >= --schwelle (Standard 0,03; Begruendung unten), wobei marge_min der
  schlechteste Wert ueber die Achsen ist (t: f1_v der senkrechten, z: f1_h der waagerechten Kanten, s. u.)

Wahl der Verschiebungsachsen: in der Fassadenebene (t = waagerecht entlang der dominanten Teil-Normalen, z), weil die Foto-F1 senkrecht zur Bildebene
blind ist (Tiefe aendert Bildkanten kaum) - die Lage-Aussage der F1 lebt nur in der Bildebene. Alternativ --achsen x,y,z (Modellrahmen, +-).
Ganzes Modell einer Variante = Verkettung ALLER Teil-STLs (mit dem verschobenen Ziel), nicht das Haupt-STL: die Haupt-STL ist die Vereinigung der Teile
(Boolesch, halbe Flaeche); die Verkettung hat innere Flaechen, die im Z-Puffer verdeckt sind. Damit der Vergleich redlich ist, wird auch f1_echt mit der
Verkettung gemessen (f1_echt_haupt = mit --stl_basis, nur zur Information; Abweichung steht im Bericht).
Bereich: --bereich_von = Teile-Ordner mit der Huelle aus Original + allen Varianten (Vereinigung) - jede Variante wird auf demselben Bildbereich bewertet
(Recall zaehlt Fotokanten in der Vereinigung; Schrumpf-Falle). ANNAHME: Verdeckung der Huellen-Kopien gegen das Variantenmodell (bei Verschiebung in der Ebene
fast ohne Wirkung).
Schwelle 0,03: Wiederholrauschen der Messung 0,002-0,01 (Kreis-Protokoll); 3 x das obere Ende. Wird mit den Beweisfaellen in BERICHT.md nachkalibriert.

Aufruf: /media/oem/scan/venv-seg/bin/python -W ignore -I tools/tor_verschiebung.py <objekt> --teile_dir D --teil NAME --fotos a,b,c [--versatz 0.3]
        [--stl_basis voll.stl] [--skala 0.5] --aus bericht.json
        --synth : Beweis auf synthetischem Objekt (ohne Echtdaten)
"""
import sys, os, json, glob, argparse, subprocess, tempfile, time, shutil, numpy as np, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

R0 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = "/media/oem/scan/venv-seg/bin/python"
TMP = "/media/oem/scan/rc-park_tmp/verschiebung"
SCHWELLE = 0.03


def hauptebene(m):
    """Waagerechte Hauptnormale des Teils (flaechengewichtet, Winkel verdoppelt = Gegenrichtungen zaehlen gleich) -> (n_h, t) Einheitsvektoren."""
    n = m.face_normals; a = m.area_faces; w = a * (np.abs(n[:, 2]) < 0.5)
    if w.sum() <= 0: return np.array([0, -1.0, 0]), np.array([1.0, 0, 0])
    ang = np.arctan2(n[:, 1], n[:, 0]); s = (w * np.sin(2 * ang)).sum(); c = (w * np.cos(2 * ang)).sum(); th = 0.5 * np.arctan2(s, c)
    nh = np.array([np.cos(th), np.sin(th), 0.0]); return nh, np.array([-nh[1], nh[0], 0.0])


def varianten_vektoren(m, versatz, achsen=None):
    """{name: Verschiebungsvektor in Metern (Modellrahmen)}."""
    if achsen:
        out = {}
        for ax in achsen.split(","):
            i = "xyz".index(ax)
            for sg in (1, -1): v = np.zeros(3); v[i] = sg * versatz; out[f"{'+' if sg > 0 else '-'}{ax}"] = v
        return out
    nh, t = hauptebene(m); z = np.array([0, 0, 1.0])
    return {"+t": versatz * t, "-t": -versatz * t, "+z": versatz * z, "-z": -versatz * z}


MESSER_SKRIPT = os.environ.get("TV_MESSER_SKRIPT") or os.path.join(R0, "tools", "teil_fotoform.py")   # --messer_skript: Ersatz (Diagnose-Kopie mit anderem foto_diff), gleiche Kommandozeile


def f1_messen(objekt, tdir, stl, teil, fotos, aus, bereich_von, skala, wolke="an", log=None):
    """teil_fotoform als Unterprozess (wie bauteil_kreis.form_messen). Rueckgabe dict mit f1/praez/recall oder None."""
    env = dict(os.environ, RCPARK_FOTO_SKALA=str(skala))
    cmd = [PY, "-W", "ignore", "-I", MESSER_SKRIPT, objekt, "--teile_dir", tdir, "--stl", stl, "--nur", teil, "--fotos", ",".join(fotos),
           "--aus", aus, "--wolke_verdeckung", wolke] + (["--bereich_von", bereich_von] if bereich_von else []) \
          + (["--schwelle", os.environ["TV_SCHWELLE"]] if os.environ.get("TV_SCHWELLE") else [])   # Diagnose: feinere Kantentoleranz (Anteil der Kappe 0,35 m)
    if os.path.exists(aus): os.remove(aus)
    if os.path.exists(aus + ".teil"): os.remove(aus + ".teil")
    r = subprocess.run(cmd, cwd=R0, env=env, capture_output=True, text=True)
    if log: open(log, "w").write((r.stdout or "") + (r.stderr or ""))
    try:
        g = json.load(open(aus))["teile"][teil]["_gesamt"]; return {"f1": g["f1"], "praez": g["praez"], "recall": g["recall"], "fotos": g["fotos"], "f1_h": g.get("f1_h"), "f1_v": g.get("f1_v")}
    except Exception: return None


def kontrolle(objekt, teile_dir, teil, fotos, versatz=0.3, stl_basis=None, skala=0.5, achsen=None, wolke="an", arbeit=None, schwelle=SCHWELLE,
              messer=f1_messen, massstab=87.0, verbose=True, bereich="huelle"):
    """Kern. `messer` austauschbar (Beweistest). Rueckgabe dict (siehe Ausgabe)."""
    t0 = time.time(); os.makedirs(TMP, exist_ok=True)
    arbeit = os.path.abspath(arbeit) if arbeit else tempfile.mkdtemp(prefix=f"{teil}_", dir=TMP); os.makedirs(arbeit, exist_ok=True)
    teile_dir = os.path.abspath(teile_dir)
    pfade = {os.path.basename(p)[:-4]: p for p in sorted(glob.glob(os.path.join(teile_dir, "*.stl")))}
    if teil not in pfade: raise SystemExit(f"Teil {teil} nicht in {teile_dir}")
    ms = {n: trimesh.load(p, force="mesh") for n, p in pfade.items()}
    ziel = ms[teil]; andere = [m for n, m in ms.items() if n != teil and isinstance(m, trimesh.Trimesh) and len(m.faces)]
    ziel_m = ziel.copy(); ziel_m.apply_scale(massstab / 1000.0)             # Metern fuer Hauptebene (Teil ist STL-mm bei 1:massstab)
    vek = varianten_vektoren(ziel_m, versatz, achsen)
    sk = 1000.0 / massstab                                                     # Meter (Modell) -> STL-Einheit
    hue = [ziel]; var_t = {}
    for nm, v in vek.items():
        s = ziel.copy(); s.apply_translation(v * sk); var_t[nm] = s; hue.append(s)
    hdir = os.path.join(arbeit, "huelle"); os.makedirs(hdir, exist_ok=True)
    # bereich="huelle": Vereinigung aus Original und ALLEN Varianten fuer jede Messung (gleiche Pixel, aber verduennt Recall bei grossen Teilen);
    # bereich="original": nur das Originalteil (wie das Tor: Vereinigung Vorher/Nachher = Original + Variante; echt = Original allein)
    trimesh.util.concatenate(hue if bereich == "huelle" else [ziel]).export(os.path.join(hdir, teil + ".stl"))
    erg = {"objekt": objekt, "teil": teil, "versatz_m": versatz, "skala": skala, "bereich": bereich, "fotos": fotos, "schwelle": schwelle, "achsen": {k: np.round(v, 3).tolist() for k, v in vek.items()},
           "arbeit": arbeit, "varianten": {}}
    def lauf(name, mesh):
        d = os.path.join(arbeit, name); os.makedirs(d, exist_ok=True)
        mesh.export(os.path.join(d, teil + ".stl"))
        voll = os.path.join(d, "voll.stl"); trimesh.util.concatenate(andere + [mesh]).export(voll)
        t1 = time.time(); r = messer(objekt, d, voll, teil, fotos, os.path.join(d, "ff.json"), hdir, skala, wolke, os.path.join(d, "ff.log"))
        if r is not None: r["sekunden"] = round(time.time() - t1, 1)
        if verbose: print(f"  {name:6s} {r}", flush=True)
        return r
    erg["echt"] = lauf("echt", ziel)
    if stl_basis:
        d = os.path.join(arbeit, "echt_haupt"); os.makedirs(d, exist_ok=True); ziel.export(os.path.join(d, teil + ".stl"))
        erg["echt_haupt"] = messer(objekt, d, stl_basis, teil, fotos, os.path.join(d, "ff.json"), hdir, skala, wolke, os.path.join(d, "ff.log"))
    for nm, s in var_t.items(): erg["varianten"][nm] = lauf(nm.replace("+", "p").replace("-", "m"), s)
    fe = (erg["echt"] or {}).get("f1"); fv = [v["f1"] for v in erg["varianten"].values() if v]
    erg["f1_echt"] = fe
    if fe is None or not fv:
        erg.update({"f1_versatz_max": None, "f1_versatz_mittel": None, "marge": None, "marge_achse": None, "lage_belegt": None, "urteil": "NICHT MESSBAR"})
    else:
        erg["f1_versatz_max"] = round(max(fv), 3); erg["f1_versatz_mittel"] = round(float(np.mean(fv)), 3)
        erg["marge"] = round(fe - max(fv), 3); erg["marge_mittel"] = round(fe - float(np.mean(fv)), 3)
        # ACHSENWEISE (Befund der Synthetik, A: Vorbau 3 m hoch, +-0,3 m senkrecht schiebt nur 0,025 F1): steile Kanten gleiten bei Hoehenversatz an sich selbst
        # entlang (teil_fotoform.waagerecht, Nutzer 10.11. Helm O). Senkrechte Verschiebung deshalb mit f1_h (nur waagerechte Kanten) bewerten, sonst f1.
        ge = {}
        for nm, v in erg["varianten"].items():
            if v: ge.setdefault(nm[1:], []).append(v)
        ma = {}
        for ax, vs in ge.items():
            # Seitenachse t symmetrisch dazu mit f1_v (nur senkrechte Kanten): waagerechte Kanten langer Teile gleiten bei Seitenversatz an sich selbst entlang
            # (11.11. Laubensockel O marge t -0,002, Gauben -0,001). Fehlt f1_v (alte Messung), bleibt f1.
            km = "f1_h" if ax == "z" else "f1_v" if ax == "t" else None
            hh = km is not None and (erg["echt"] or {}).get(km) is not None and all(v.get(km) is not None for v in vs)
            mm = km if hh else "f1"
            e0 = erg["echt"][mm]; ma[ax] = {"mass": mm, "echt": e0, "versatz_max": max(v[mm] for v in vs), "marge": round(e0 - max(v[mm] for v in vs), 3)}
        for m_ in ma.values(): m_["belegt"] = bool(m_["marge"] >= schwelle)
        erg["marge_achse"] = ma; erg["marge_min"] = round(min(m["marge"] for m in ma.values()), 3)
        erg["lage_belegt"] = bool(erg["marge_min"] >= schwelle)
        # GUELTIGKEIT der Verkettung (Befund fensterreihe__og: Verkettung F1 0,382 gegen Haupt-STL 0,886): Teile, die im Haupt-STL von anderen abgezogen werden
        # (Fenster-/Nischen-/Ausschnitt-Teile, Boolesche Differenz) sind in der Verkettung ein falsches Modell -> Kontrolle nicht beurteilbar.
        eh = (erg.get("echt_haupt") or {}).get("f1")
        if eh is not None and abs(eh - fe) > 0.03:
            erg["lage_belegt"] = None; erg["konkat_gueltig"] = False
        else: erg["konkat_gueltig"] = True if eh is not None else None
        erg["urteil"] = ("NICHT BEURTEILBAR: F1 der Verkettung aller Teile (%s) weicht vom Haupt-STL (%s) ab - Teil wird im Haupt-STL abgezogen/verschmolzen, Variantenmodell waere falsch" % (fe, eh)
                         if erg["lage_belegt"] is None else "LAGE BELEGT: echte Lage schlaegt jede Verschiebung (je Achse) um mindestens die Schwelle" if erg["lage_belegt"] else
                         ("LAGE NICHT BELEGT (Dichte): eine verschobene Variante erreicht/uebertrifft die echte Lage" if erg["marge_min"] <= 0 else
                          "LAGE NICHT BELEGT (Marge unter Schwelle)"))
    erg["sekunden"] = round(time.time() - t0, 1)
    return erg


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt", nargs="?"); ap.add_argument("--teile_dir"); ap.add_argument("--teil"); ap.add_argument("--fotos")
    ap.add_argument("--versatz", type=float, default=0.3); ap.add_argument("--stl_basis"); ap.add_argument("--skala", type=float, default=0.5)
    ap.add_argument("--achsen", help="x,y,z statt Fassadenebene"); ap.add_argument("--wolke_verdeckung", default="an", choices=["an", "aus"])
    ap.add_argument("--schwelle", type=float, default=SCHWELLE); ap.add_argument("--aus"); ap.add_argument("--arbeit"); ap.add_argument("--synth", action="store_true"); ap.add_argument("--messer_skript"); ap.add_argument("--bereich", default="huelle", choices=["huelle", "original"])
    a = ap.parse_args(argv)
    global MESSER_SKRIPT
    if a.messer_skript: MESSER_SKRIPT = os.path.abspath(a.messer_skript)
    if a.synth:
        import test_tor_verschiebung as T; return T.main([])
    if not (a.objekt and a.teile_dir and a.teil and a.fotos): ap.error("objekt, --teile_dir, --teil, --fotos noetig")
    objp = os.path.join(R0, "modelle", a.objekt, "objekt.json"); ms = json.load(open(objp)).get("stl_massstab", 87)
    e = kontrolle(a.objekt, a.teile_dir, a.teil, a.fotos.split(","), a.versatz, a.stl_basis, a.skala, a.achsen, a.wolke_verdeckung, a.arbeit, a.schwelle, massstab=ms, bereich=a.bereich)
    print(json.dumps({k: v for k, v in e.items() if k not in ("achsen",)}, ensure_ascii=False, indent=1))
    if a.aus: json.dump(e, open(a.aus, "w"), ensure_ascii=False, indent=1)
    return e


if __name__ == "__main__":
    main()
