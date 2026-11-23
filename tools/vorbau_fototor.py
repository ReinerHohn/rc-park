#!/usr/bin/env python3
"""vorbau_fototor.py - FOTO-TOR fuer gebaute Vorbauten (Erker, Galerie, Vordach) je Gruppe aus audit/vorbauten_auto.json (22.11.2026, Kettenstufe 'bauplan').

Anlass (Kettenlauf schwabentor-1122n): der Bilderker der Stadtseite fehlte, ohne dass ein Tor es meldete; foto_diff bewertet nur das ganze Modell.
Hier je Vorbau-Gruppe:
  1. EXPORT (Generator-Umgebung, manifold3d): bauteile.vorbauten_aus_json nur mit dieser Gruppe auf leerem Koerper -> <teile>/vorbau_<fid>_<k>.stl
     (Massstab wie das Modell-STL: m x 1000/SKALA, Rahmen nicht zentriert).
  2. FOTO-F1 (teil_fotoform, GPU): Praezision/Recall/F1 der Teilkanten gegen die Fotokanten in den Fotos, die die Fassade am besten sehen (fassaden.json 'fotos', Zellen).
     --vorher_stl: zusaetzlich PHANTOM-Messung (Bereich des neuen Teils am Modell OHNE Vorbau) = Foto-F1 vorher/nachher.
  3. TOR je Gruppe: BELEGT, wenn >= --min_fotos Fotos das Teil beurteilen und die Praezision (Anteil Modellkanten mit Fotokante <= 0,14 m) >= --praez_min
     (ANNAHME 0,5: mehr als die Haelfte der gebauten Kanten liegt auf Fotokanten = nicht erfunden). Sonst NICHT BELEGT (rc 2), ohne Beurteilung rc 3.
Aufruf: vorbau_fototor.py <objekt> <fassaden.json> [--fotos 8] [--stl S] [--vorher_stl S] [--aus audit/vorbau_fototor.json] [--bilder_dir D]
Export allein (rcpark-Umgebung): vorbau_fototor.py --export <vorbauten_auto.json> <teile-ordner> [--skala 87]
BELEG-TOR vor dem Bau (23.11.2026, Phantom f03 1122t): vorbau_fototor.py --beleg <vorbauten_auto.json> <fassade-ordner> <ebenen.json> - verwirft Gruppen ohne Fotokanten
  auf ihrer Ebene (a) oder mit Front am Rand des Sweep-Suchraums (b); im Fototor Regel (c) schwache Praezision + knapper Beleg -> verworfen, rc 4 (neu bauen).
"""
import sys, os, json, argparse, subprocess, tempfile

HIER = os.path.dirname(os.path.abspath(__file__)); R0 = os.path.dirname(HIER); sys.path.insert(0, HIER)
GEN_PY = os.path.expanduser("~/.venvs/rcpark/bin/python")


def exportieren(vj, td, skala=87.0):
    """Je Gruppe ein STL (mm, Modellrahmen). Liefert Liste (name, fid, k)."""
    import numpy as np, trimesh
    from manifold3d import Manifold as M
    from bauteile import vorbauten_aus_json
    J = json.load(open(vj)); out = []; os.makedirs(td, exist_ok=True); K = 1000.0 / skala
    for F in J.get("fassaden", []):
        for k, g in enumerate(F["gruppen"]):
            tj = os.path.join(td, f"_vb_{F['id']}_{k}.json")
            json.dump(dict(J, fassaden=[dict(F, gruppen=[g])]), open(tj, "w"))
            # vordach_profil.json liegt neben vorbauten_auto.json und wird ueber (id, gruppe) zugeordnet -> Gruppe k muss Gruppe k bleiben
            if k:
                json.dump(dict(J, fassaden=[dict(F, gruppen=[dict(g0, kanten_mass=None, galerie=None, w=[[0.0]]) for g0 in F["gruppen"][:k]] + [g])]), open(tj, "w"))
            vp = os.path.join(os.path.dirname(os.path.abspath(vj)), "vordach_profil.json")
            if os.path.exists(vp): __import__("shutil").copy(vp, os.path.join(td, "vordach_profil.json"))
            kp, _ = vorbauten_aus_json(M(), tj)
            os.remove(tj)
            if kp.is_empty(): continue
            m = kp.scale((K, K, K)).to_mesh(); nm = f"vorbau_{F['id']}_{k}"
            trimesh.Trimesh(np.asarray(m.vert_properties)[:, :3], np.asarray(m.tri_verts)).export(os.path.join(td, nm + ".stl")); out.append((nm, F["id"], k))
    vp_ = os.path.join(td, "vordach_profil.json")
    if os.path.exists(vp_): os.remove(vp_)
    return out


# --- BELEG-TOR (23.11.2026, Kette 1122t: 'Vorbau f03' West z 17,5-25,4 m war ein PHANTOM - Sweep-Tiefen am Rand des Suchraums, Ebene f03_vb0 ohne einen
# Kantenpunkt, im Foto nichts; das Fototor meldete trotzdem BELEGT, Praezision 0,52: Wandkanten hinter dem Phantom liegen in der Projektion auf Fotokanten).
# Messwerte 1122t (echter Erker f00 / Phantom f03):
#   Kantenpunkte der Vorbau-Ebene je m2 gegen die eigene Wandebene:   1,46 / 0,00   (22 590 / 0 Punkte)
#   Randanteil (Front-Zellen >= Suchgrenze - 0,25 m):                 0,047 / 0,248
#   Fototor-Praezision:                                               0,605 (1122u 0,664) / 0,518
KANTEN_MIN_PUNKTE = 40          # wie oeffnungen_aus_kanten.KANTEN_MIN_PUNKTE (Form aus Kantenpunkten erst ab 40 Punkten)
KANTEN_DICHTE_REL_MIN = 0.2     # ANNAHME: Vorbau-Ebene braucht >= 1/5 der Kantendichte ihrer Wand (f00 liegt 7x darueber, f03 bei 0)
RAND_TOL = 0.25                 # wie vorbauten_bauplan.gruppen_bilden (Front bis 0,25 m an der Suchgrenze = kein echtes Kostenminimum)
RAND_ANTEIL_MAX = 0.12          # ANNAHME: geometrisches Mittel von f00 0,047 und f03 0,248 (= 0,108), aufgerundet
PRAEZ_SCHWACH = 0.56            # ANNAHME: zwischen Phantom 0,518 und dem schwaechsten echten Erker-Wert 0,605
KNAPP = 2.0                     # 'knapp' = Faktor 2 vor der Schwelle; knapp + schwache Praezision -> verwerfen (Regel c)


def _flaeche(zone): return max((zone[1] - zone[0]) * (zone[3] - zone[2]), 1e-6)


def beleg(g, w_grenze=None, ebene=None, wand=None, w_min=0.5):
    """Beleg einer Vorbau-Gruppe (vorbauten_auto.json) ohne Foto-F1: (a) Fotokanten auf der eigenen Ebene (ebenen.json-Eintrag 'f<nr>_vb<k>', Dichte gegen die
    Wandebene derselben Fassade), (b) Randtreffer = Anteil der Front-Zellen im Hoehenfeld, die an der Suchgrenze des Sweeps kleben (w_grenze = w_bereich[1] - wand_versatz).
    Fehlende Daten (keine Ebene / keine Grenze) urteilen nicht. -> dict(kanten_punkte, kanten_dichte_rel, rand_anteil, gruende, knapp, verwerfen)."""
    import numpy as np
    w = np.asarray(g.get("w") or [[0.0]], float); front = w[w > 0.5 * w_min]
    rand = round(float((front >= w_grenze - RAND_TOL).mean()), 3) if (w_grenze is not None and front.size) else None
    kp = rel = None
    if ebene is not None:
        kp = int(ebene.get("punkte") or 0)
        if wand and wand.get("punkte"): rel = round((kp / _flaeche(ebene["zone"])) / (wand["punkte"] / _flaeche(wand["zone"])), 3)
    gruende, knapp = [], []
    if kp is not None and (kp < KANTEN_MIN_PUNKTE or (rel is not None and rel < KANTEN_DICHTE_REL_MIN)):
        gruende.append(f"(a) Fotokanten fehlen: {kp} Punkte auf der Vorbau-Ebene" + (f", Dichte {rel:.2f} x Wand (< {KANTEN_DICHTE_REL_MIN})" if rel is not None else f" (< {KANTEN_MIN_PUNKTE})"))
    elif rel is not None and rel < KNAPP * KANTEN_DICHTE_REL_MIN: knapp.append(f"Kantendichte knapp {rel:.2f} x Wand")
    if rand is not None and rand > RAND_ANTEIL_MAX:
        gruende.append(f"(b) Randtreffer: {rand:.0%} der Front am Rand des Suchraums (Grenze {w_grenze:.2f} m, > {RAND_ANTEIL_MAX:.0%}) - kein Kostenminimum")
    elif rand is not None and rand > RAND_ANTEIL_MAX / KNAPP: knapp.append(f"Randanteil knapp {rand:.0%}")
    return dict(kanten_punkte=kp, kanten_dichte_rel=rel, rand_anteil=rand, w_grenze=None if w_grenze is None else round(float(w_grenze), 3), gruende=gruende, knapp=knapp, verwerfen=bool(gruende))


def beleg_anwenden(vj, fassade_ordner=None, ebenen_json=None, schreiben=True):
    """Beleg-Tor auf alle Gruppen von vorbauten_auto.json: g['beleg'] = beleg(...), bei Verwerfen g['verworfen'] = Grund (bauteile.vorbauten_aus_json baut die Gruppe
    dann nicht). Liefert [(name, beleg)]."""
    J = json.load(open(vj)); EB = {}
    if ebenen_json and os.path.exists(ebenen_json): EB = {e["id"]: e for e in json.load(open(ebenen_json)).get("ebenen", [])}
    out = []
    for F in J.get("fassaden", []):
        nr = F.get("nr"); vf = os.path.join(fassade_ordner, f"vorbauten_f{nr:02d}.json") if (fassade_ordner and nr is not None) else None
        v = json.load(open(vf)) if vf and os.path.exists(vf) else {}
        wg = (v["w_bereich"][1] - v["wand_versatz_m"]) if v.get("w_bereich") and v.get("wand_versatz_m") is not None else None
        for k, g in enumerate(F["gruppen"]):
            b = beleg(g, wg, EB.get(f"f{nr:02d}_vb{k}") if nr is not None and EB else None, EB.get(f"f{nr:02d}_wand") if nr is not None else None)
            g["beleg"] = b
            if b["verwerfen"]: g["verworfen"] = "Beleg-Tor: " + "; ".join(b["gruende"])
            out.append((f"vorbau_{F['id']}_{k}", b))
    if schreiben: json.dump(J, open(vj, "w"), indent=0)
    return out


def urteil(je, min_fotos=3, praez_min=0.5, beleg_=None):
    """je = teil_fotoform erg['teile'][name]. (BELEGT|NICHT BELEGT|KEIN URTEIL, gesamt).
    beleg_ (dict aus beleg()): Regel (c) - schwache Praezision (< PRAEZ_SCHWACH) zusammen mit knappem Kanten-/Randbeleg -> NICHT BELEGT."""
    g = (je or {}).get("_gesamt")
    if not g or g.get("fotos", 0) < min_fotos: return "KEIN URTEIL", g
    if g["praez"] < praez_min: return "NICHT BELEGT", g
    if beleg_ and (beleg_.get("knapp") or beleg_.get("gruende")) and g["praez"] < PRAEZ_SCHWACH: return "NICHT BELEGT", g
    return "BELEGT", g


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt", nargs="?"); ap.add_argument("fassaden", nargs="?")
    ap.add_argument("--export", nargs=2, metavar=("VORBAUTEN_JSON", "TEILE")); ap.add_argument("--skala", type=float, default=float(os.environ.get("SCALE", "87")))
    ap.add_argument("--fotos", type=int, default=8); ap.add_argument("--stl"); ap.add_argument("--vorher_stl"); ap.add_argument("--aus"); ap.add_argument("--bilder_dir")
    ap.add_argument("--min_fotos", type=int, default=3); ap.add_argument("--praez_min", type=float, default=0.5)
    ap.add_argument("--beleg", nargs=3, metavar=("VORBAUTEN_JSON", "FASSADE_ORDNER", "EBENEN_JSON"), help="nur Beleg-Tor (a)/(b) vor dem Bau; rc 0 alle belegt, 2 = verworfen, 3 = nichts")
    a = ap.parse_args(argv)
    if a.export:
        for nm, fid, k in exportieren(a.export[0], a.export[1], a.skala): print("EXPORT", nm)
        return 0
    if a.beleg:
        if not os.path.exists(a.beleg[0]) or not json.load(open(a.beleg[0])).get("fassaden"): print("keine Vorbauten - nichts zu pruefen"); return 3
        erg = beleg_anwenden(*a.beleg); rc = 0
        for nm, b in erg:
            print(f"VORBAU-BELEG {nm}: {'VERWORFEN' if b['verwerfen'] else 'belegt'}  Kantenpunkte {b['kanten_punkte']} (Dichte {b['kanten_dichte_rel']} x Wand), Randanteil {b['rand_anteil']}"
                  + ("  | " + "; ".join(b["gruende"]) if b["gruende"] else "") + ("  | knapp: " + "; ".join(b["knapp"]) if b["knapp"] else ""))
            if b["verwerfen"]: rc = 2
        return rc
    od = os.path.join(R0, "modelle", a.objekt); vj = os.path.join(od, "audit", "vorbauten_auto.json")
    if not os.path.exists(vj) or not json.load(open(vj)).get("fassaden"): print("keine Vorbauten gebaut - nichts zu pruefen"); return 3
    VJ = json.load(open(vj)); GR = {f"vorbau_{F['id']}_{k}": g for F in VJ["fassaden"] for k, g in enumerate(F["gruppen"])}; neu_verworfen = []
    td = tempfile.mkdtemp(prefix="vbft_", dir=os.environ.get("TMPDIR") or None)
    r = subprocess.run([GEN_PY, "-W", "ignore", "-I", os.path.abspath(__file__), "--export", vj, td, "--skala", str(a.skala)], capture_output=True, text=True)
    teile = [l.split()[1] for l in r.stdout.splitlines() if l.startswith("EXPORT ")]
    if not teile:
        vw_ = [nm for nm, g in GR.items() if g.get("verworfen")]
        print(f"keine gebauten Vorbauten ({len(vw_)} vom Beleg-Tor verworfen: {', '.join(vw_)})" if vw_ else "Export ohne Teile: " + (r.stderr or r.stdout)[-300:]); return 3
    FA = {F.get("id", f"f{i:02d}"): F for i, F in enumerate(json.load(open(a.fassaden))["fassaden"])}
    import teil_fotoform as TF
    wo_ = os.path.join(od, "sfm", f"punkte_modell_{a.objekt}.npy")      # eigene dichte Wolke als Verdecker (ohne kreis.wolke nimmt teil_fotoform sonst eine fremde Standardwolke)
    if os.path.exists(wo_) and not (json.load(open(os.path.join(od, "objekt.json"))).get("kreis") or {}).get("wolke"): TF_WOLKE = ["--wolke", wo_]
    else: TF_WOLKE = []
    bericht = dict(quelle="tools/vorbau_fototor.py (teil_fotoform je Vorbau-Gruppe)", praez_min=a.praez_min, min_fotos=a.min_fotos, praez_schwach=PRAEZ_SCHWACH, gruppen={}); rc = 0
    for nm, g0 in GR.items():
        if g0.get("verworfen"): bericht["gruppen"][nm] = dict(urteil="VERWORFEN", grund=g0["verworfen"], beleg=g0.get("beleg")); print(f"VORBAU-FOTOTOR {nm}: VERWORFEN ({g0['verworfen']})")
    for nm in teile:
        fid = nm.split("_")[1]; F = FA.get(fid) or {}
        fotos = [f_ for f_, _ in sorted((F.get("fotos") or {}).items(), key=lambda kv: -kv[1].get("zellen", 0))][:a.fotos]
        if not fotos: bericht["gruppen"][nm] = dict(urteil="KEIN URTEIL", grund="keine Fotos der Fassade"); continue
        arg = [a.objekt, "--teile_dir", td, "--nur", nm, "--fotos", ",".join(fotos)] + TF_WOLKE + (["--stl", a.stl] if a.stl else []) + (["--bilder", "--bilder_dir", a.bilder_dir] if a.bilder_dir else [])
        bl_ = (GR.get(nm) or {}).get("beleg")
        e_n = TF.main(arg + ["--etikett", "nachher"]); u_, g_ = urteil(e_n["teile"].get(nm), a.min_fotos, a.praez_min, bl_)
        if u_ == "NICHT BELEGT" and bl_ and g_ and g_["praez"] >= a.praez_min:      # Regel (c): Praezision schwach + Beleg knapp -> verwerfen, Kette baut neu
            GR[nm]["verworfen"] = f"Fototor (c): Praezision {g_['praez']:.3f} < {PRAEZ_SCHWACH} und Beleg knapp ({'; '.join(bl_.get('knapp') or bl_.get('gruende'))})"; neu_verworfen.append(nm)
        b_ = dict(urteil=u_, nachher=g_, beleg=bl_, fotos=fotos, je_foto={k: dict(praez=v["praez"], recall=v["recall"]) for k, v in (e_n["teile"].get(nm) or {}).items() if k != "_gesamt"})
        if a.vorher_stl:      # Phantom: Teilbereich des neuen Teils, Modellkanten aus dem Stand OHNE Vorbau (teil_fotoform --bereich_von)
            tv = tempfile.mkdtemp(prefix="vbft_v_", dir=os.environ.get("TMPDIR") or None)
            e_v = TF.main([a.objekt, "--teile_dir", tv, "--nur", nm, "--bereich_von", td, "--stl", a.vorher_stl, "--fotos", ",".join(fotos)] + TF_WOLKE + (["--bilder", "--bilder_dir", a.bilder_dir, "--etikett", "vorher"] if a.bilder_dir else []))
            b_["vorher"] = (e_v["teile"].get(nm) or {}).get("_gesamt")
        bericht["gruppen"][nm] = b_
        f1n = (g_ or {}).get("f1"); f1v = (b_.get("vorher") or {}).get("f1")
        print(f"VORBAU-FOTOTOR {nm}: {u_}" + (f"  Praez {g_['praez']:.3f} Recall {g_['recall']:.3f} F1 {g_['f1']:.3f} ({g_['fotos']} Fotos)" if g_ else "") + (f"  | vorher F1 {f1v:.3f} -> nachher {f1n:.3f}" if f1v is not None and f1n is not None else ""))
        if u_ == "NICHT BELEGT": rc = 2
        elif u_ == "KEIN URTEIL" and rc == 0: rc = 3
    aus = a.aus or os.path.join(od, "audit", "vorbau_fototor.json"); json.dump(bericht, open(aus, "w"), indent=1, ensure_ascii=False); print("->", aus)
    if neu_verworfen:      # rc 4 = Gruppe(n) jetzt verworfen -> Kette baut ohne sie neu
        json.dump(VJ, open(vj, "w"), indent=0); print("VERWORFEN (Regel c), neu bauen:", ", ".join(neu_verworfen)); return 4
    return rc


if __name__ == "__main__": sys.exit(main())
