#!/usr/bin/env python3
"""teil_varianten_tor.py - BEST-OF-N MIT TEIL-LOKALEM RAUSCHTOR (Option A der Recherche 11.11., Auftrag Hauptsitzung).

Warum: der Foto-F1 (teil_fotoform, 0,18 m Glaettung) ist blind fuer Ornament (REZEPT L45/L46/L55: um 90 Grad gedrehte Erker-Rippen schnitten besser ab als
richtige). Ein Varianten-Sieger darf nur gelten, wenn der Abstand groesser ist als das, was die Kennzahl an BEKANNT FALSCHEN Varianten (Nullkontrollen) trennt.

Ablauf (alle Varianten auf GEMEINSAMEN Fotos und GEMEINSAMEM Bildbereich = Vereinigung der Silhouetten aller Varianten und Nullkontrollen, --bereich_von):
  1. Nullkontrollen aus der Referenzvariante (--null_von, Standard die erste): Teil-STL um 0,3 m verschoben (x), um 0,3 m angehoben (z), um 90 Grad um die Hochachse
     (Teilmitte) gedreht. Das Gesamt-STL der Nullkontrolle = Referenz-Gesamt-STL ohne die Dreiecke des Teils + verschobenes/gedrehtes Teil (Verdeckung bleibt stimmig).
  2. Je Variante (und Nullkontrolle): teil_fotoform (Kanten-F1, f1_fein, Hoehen-/Seitenwert) und flaechen_mass (SAM vit-large, Masken-IoU der Teilflaechen/-silhouette im ROI).
  3. Rauschen je Kennzahl: Kennzahl TRENNT, wenn ALLE Nullkontrollen darunter liegen; Rauschschwelle = --schwellfaktor (Standard 0,5) x kleinster Abfall der
     Referenz gegen eine Nullkontrolle. Sieger je Kennzahl nur, wenn trennend UND Abstand zum Zweiten > Schwelle. Gesamtsieger nur, wenn alle trennenden Kennzahlen
     denselben Sieger zeigen (sonst "kein Sieger"). Blinde Kennzahlen (Nullkontrolle >= Referenz) werden berichtet, nie benutzt.
  4. Kollage Foto | Render je Variante (teil_render_foto) je Foto zum ANSEHEN.

Aufruf (venv-seg): python -W ignore -I tools/teil_varianten_tor.py <objekt> <teil> --varianten NAME:TEILE_DIR:GESAMT_STL,... --fotos a,b,c,d [--aus DIR] [--null_von NAME]
  (Doppelpunkt statt Komma-Paar D1:S1 im Auftrag: Name davor, damit Kollagen/JSON lesbar sind; Form D:S ohne Namen wird auto-benannt v1,v2,...)
Lange Laeufe: JOB_GPU_MB=4500 tools/job_start.sh NAME LOG python tools/teil_varianten_tor.py ...   (flaechen_mass ~3,5 GB, teil_fotoform serialisiert ueber gpu_slot)
Kein Objektname im Code.
"""
import sys, os, json, argparse, subprocess, time, shutil, numpy as np, trimesh

R0 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
HERE = os.path.dirname(os.path.abspath(__file__))
KENNZAHLEN = [("f1", "Kanten-F1 (0,18 m)"), ("f1_fein", "f1_fein (0,03 m)"), ("f1_h", "F1 waagerecht"), ("f1_v", "F1 senkrecht"),
              ("iou_flaechen", "SAM Flaechen-IoU"), ("iou_silhouette", "SAM Silhouetten-IoU")]


def parse_var(s):
    out = []
    for i, v in enumerate(s.split(",")):
        p = v.split(":")
        if len(p) == 3: out.append((p[0], p[1], p[2]))
        elif len(p) == 2: out.append((f"v{i + 1}", p[0], p[1]))
        else: raise SystemExit("Variante NAME:TEILE_DIR:STL oder TEILE_DIR:STL: " + v)
    return out


def _schluessel(m, nd=3):
    return {tuple(np.round(c, nd)) for c in m.triangles_center}


def nullkontrolle(art, teil, d_ref, stl_ref, obj, aus):
    """Gibt (teile_dir, gesamt_stl) der Nullkontrolle. Einheiten: STL * stl_massstab/1000 = Meter."""
    k = obj.get("stl_massstab", 87) / 1000.0
    p = trimesh.load(os.path.join(d_ref, teil + ".stl"), force="mesh"); ganz = trimesh.load(stl_ref, force="mesh")
    c = p.bounds.mean(0)
    T = np.eye(4)
    if art == "verschoben": T[0, 3] = 0.3 / k
    elif art == "hoch": T[2, 3] = 0.3 / k
    elif art == "gedreht":
        T = trimesh.transformations.rotation_matrix(np.pi / 2, [0, 0, 1], point=[c[0], c[1], 0])
    else: raise SystemExit("unbekannte Nullkontrolle " + art)
    # Gesamt-STL: Dreiecke des Teils entfernen (Schwerpunkt-Abgleich), transformiertes Teil anfuegen
    sk = _schluessel(p); keep = np.array([tuple(np.round(x, 3)) not in sk for x in ganz.triangles_center])
    n_weg = int((~keep).sum())
    rest = ganz.submesh([np.flatnonzero(keep)], append=True) if n_weg else ganz
    p2 = p.copy(); p2.apply_transform(T)
    neu = trimesh.util.concatenate([rest, p2])
    dd = os.path.join(aus, "null_" + art); os.makedirs(dd, exist_ok=True)
    for f in os.listdir(d_ref):                       # alle Teile als Symlink (Verdecker), das Teil ersetzt
        if f.endswith(".stl") and f != teil + ".stl":
            lp = os.path.join(dd, f)
            if not os.path.lexists(lp): os.symlink(os.path.abspath(os.path.join(d_ref, f)), lp)
    p2.export(os.path.join(dd, teil + ".stl")); sp = os.path.join(dd, "gesamt.stl"); neu.export(sp)
    return dd, sp, n_weg, len(p.faces)


def lauf(cmd, log):
    t0 = time.time()
    with open(log, "w") as lf: r = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, cwd=R0)
    return r.returncode, time.time() - t0


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("teil"); ap.add_argument("--varianten", required=True); ap.add_argument("--fotos", required=True)
    ap.add_argument("--aus"); ap.add_argument("--null_von"); ap.add_argument("--nullen", default="verschoben,hoch,gedreht"); ap.add_argument("--schwellfaktor", type=float, default=0.5)
    ap.add_argument("--ohne_sam", action="store_true"); ap.add_argument("--ohne_kollage", action="store_true"); ap.add_argument("--wiederaufnahme", action="store_true")
    a = ap.parse_args(argv)
    obj = json.load(open(os.path.join(R0, "modelle", a.objekt, "objekt.json")))
    var = parse_var(a.varianten)
    aus = a.aus or f"/media/oem/scan/rc-park_tmp/varianten_tor/{a.teil}_{time.strftime('%Y%m%d_%H%M%S')}"; os.makedirs(aus, exist_ok=True)
    ref = next((v for v in var if v[0] == a.null_von), var[0]) if a.null_von else var[0]
    alle = list(var); nullen = []
    for art in [x for x in a.nullen.split(",") if x]:
        dd, sp, nw, nf = nullkontrolle(art, a.teil, ref[1], ref[2], obj, aus)
        print(f"Nullkontrolle {art}: {nw} Dreiecke aus Gesamt-STL entfernt (Teil hat {nf})", flush=True)
        alle.append(("null_" + art, dd, sp)); nullen.append("null_" + art)
    # Vereinigungs-Bereich (gemeinsamer ROI/Band aller Varianten)
    ud = os.path.join(aus, "bereich_union"); os.makedirs(ud, exist_ok=True)
    trimesh.util.concatenate([trimesh.load(os.path.join(d, a.teil + ".stl"), force="mesh") for _, d, _ in alle]).export(os.path.join(ud, a.teil + ".stl"))
    erg = {"objekt": a.objekt, "teil": a.teil, "fotos": a.fotos, "referenz": ref[0], "nullen": nullen, "schwellfaktor": a.schwellfaktor, "aus": aus, "varianten": {}}
    for name, d, stl in alle:
        e = {"teile_dir": d, "stl": stl}; jf = os.path.join(aus, f"fotoform_{name}.json"); sj = os.path.join(aus, f"sam_{name}.json")
        if not (a.wiederaufnahme and os.path.exists(jf)):
            rc, t = lauf([PY, "-W", "ignore", "-I", os.path.join(HERE, "teil_fotoform.py"), a.objekt, "--teile_dir", d, "--stl", stl, "--nur", a.teil, "--fotos", a.fotos,
                          "--bereich_von", ud, "--aus", jf, "--bilder_dir", os.path.join(aus, "bilder_f1")], os.path.join(aus, f"fotoform_{name}.log"))
        else: rc, t = 0, 0.0
        e["laufzeit_f1_s"] = round(t, 1)
        try: g = json.load(open(jf))["teile"][a.teil]["_gesamt"]; e.update({k: g.get(k) for k in ("f1", "f1_fein", "f1_h", "f1_v", "praez", "recall", "fotos")})
        except Exception as ex: e["fehler_f1"] = f"rc={rc} {type(ex).__name__}"
        try:
            je = json.load(open(jf))["teile"][a.teil]; e["f1_je_foto"] = {k: v.get("f1_f") for k, v in je.items() if k != "_gesamt"}
            e["sicht_px"] = int(sum(v["sicht_px"] for k, v in je.items() if k != "_gesamt")); e["mk_px_je_sicht"] = round(sum(v["mk_px"] for k, v in je.items() if k != "_gesamt") / max(e["sicht_px"], 1), 4)
        except Exception: pass
        if not a.ohne_sam:
            if not (a.wiederaufnahme and os.path.exists(sj)):
                rc, t = lauf([PY, "-W", "ignore", "-I", os.path.join(HERE, "flaechen_mass.py"), a.objekt, "--teile_dir", d, "--nur", a.teil, "--fotos", a.fotos,
                              "--bereich_von", ud, "--aus", sj, "--bilder", "--bilder_dir", os.path.join(aus, "bilder_sam")], os.path.join(aus, f"sam_{name}.log"))
            else: rc, t = 0, 0.0
            e["laufzeit_sam_s"] = round(t, 1)
            try: g = json.load(open(sj))["_gesamt"]; e.update({"iou_flaechen": g["iou_flaechen"], "iou_silhouette": g["iou_silhouette"]})
            except Exception as ex: e["fehler_sam"] = f"rc={rc} {type(ex).__name__}"
        erg["varianten"][name] = e
        print(name, {k: e.get(k) for k, _ in KENNZAHLEN}, "t", e.get("laufzeit_f1_s"), e.get("laufzeit_sam_s"), flush=True)
        json.dump(erg, open(os.path.join(aus, "varianten_tor_zwischen.json"), "w"), ensure_ascii=False, indent=1)
    # ---- Rauschtor ----
    V = erg["varianten"]; echte = [v[0] for v in var]; tor = {}
    for k, bez in KENNZAHLEN:
        if any(V[n].get(k) is None for n in echte + nullen): tor[k] = {"bezeichnung": bez, "status": "nicht gemessen"}; continue
        rv = V[ref[0]][k]; abf = {n: round(rv - V[n][k], 4) for n in nullen}
        trennt = bool(nullen) and all(x > 0 for x in abf.values()); schw = a.schwellfaktor * min(abf.values()) if trennt else None
        rang = sorted(echte, key=lambda n: -V[n][k]); gap = round(V[rang[0]][k] - V[rang[1]][k], 4) if len(rang) > 1 else None
        t = {"bezeichnung": bez, "werte": {n: V[n][k] for n in echte}, "nullen": {n: V[n][k] for n in nullen}, "abfall_referenz_gegen_null": abf, "trennt": trennt,
             "schwelle": round(schw, 4) if schw is not None else None, "rangliste": rang, "abstand_1_2": gap,
             "sieger": rang[0] if (trennt and gap is not None and gap > schw) else None,
             "nullen_ueber_variante": [n for n in echte if any(V[z][k] >= V[n][k] for z in nullen)]}
        tor[k] = t
    siegerliste = {t["sieger"] for t in tor.values() if t.get("trennt") and t.get("sieger")}
    trennende = [k for k, t in tor.items() if t.get("trennt")]
    erg["tor"] = tor; erg["trennende_kennzahlen"] = trennende
    erg["sieger"] = (siegerliste.pop() if len(siegerliste) == 1 and all(tor[k]["sieger"] for k in trennende) else None) if trennende else None
    erg["hinweis"] = "Sieger nur wenn alle trennenden Kennzahlen denselben Sieger mit Abstand > Rauschschwelle zeigen; sonst None (Best-of-N entscheidet nicht)."
    json.dump(erg, open(os.path.join(aus, "varianten_tor.json"), "w"), ensure_ascii=False, indent=1)
    # ---- Kollage ----
    if not a.ohne_kollage:
        cmd = [PY, "-W", "ignore", "-I", os.path.join(HERE, "teil_render_foto.py"), a.objekt, a.teil, "--fotos", a.fotos, "--teile_dir", alle[0][1], "--stl", alle[0][2], "--name", alle[0][0],
               "--aus", os.path.join(aus, "kollage"), "--kontur", "--maxbreite", "3200"]
        for n, d, s in alle[1:]: cmd += ["--vergleich", f"{n}:{d}:{s}"]
        rc, _ = lauf(cmd, os.path.join(aus, "kollage.log")); erg["kollage"] = os.path.join(aus, "kollage") if rc == 0 else f"fehlgeschlagen rc={rc}"
        json.dump(erg, open(os.path.join(aus, "varianten_tor.json"), "w"), ensure_ascii=False, indent=1)
    print("\nKennzahl | " + " | ".join(echte + nullen))
    for k, bez in KENNZAHLEN:
        t = tor[k]
        if "werte" in t: print(f"{k:15s} " + " ".join(f"{V[n][k]:.3f}" for n in echte + nullen) + f" | trennt={t['trennt']} schwelle={t['schwelle']} Abstand1-2={t['abstand_1_2']} sieger={t['sieger']}")
    print("Sieger gesamt:", erg["sieger"], "| Ergebnis:", os.path.join(aus, "varianten_tor.json"))
    return erg


if __name__ == "__main__":
    main()
