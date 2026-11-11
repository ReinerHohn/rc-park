#!/usr/bin/env python3
"""realitaet_prozent.py - EINE Prozentzahl "wie nah ist das Modell an der Realitaet" fuer den aktuellen main-Stand (Nutzerwunsch 10.11.:
"nach jedem neuen Ergebnis eine Prozentzahl"). Wird am Ende von tools/main_abnahme.sh aufgerufen (nach jeder GRUENEN main-Abnahme).

Hauptzahl = Mittel des Wolkenbelegs ueber alle Bauteile mit Daten (konvergenz_bericht.py, Abschnitt Wolkenbeleg: Anteil der datennahen,
kamera-zugewandten Teilflaeche, die naeher als --beleg an der Fotowolke liegt). Das ist dieselbe Zahl wie im Konvergenzstand (0,769 am 10.11.).
Daneben (nicht eingerechnet, damit die Hauptzahl vergleichbar bleibt): Fotokanten im Modell (Kanten-Recall gesamt), Teile >= 0,9, Pruefstand.
Grenzen (ehrlich mitschreiben): Teile ohne Daten (Rueckseite/Hof) zaehlen nicht; der Wolkenbeleg sieht Lage/Masse, nicht Feinform
(Docken, Profile) - die steht in teil_fotoform.

Ablauf: Bauteile des main-Stands exportieren (Generator mit BAUTEILE_AUS, CPU), konvergenz_bericht --trocken --json_aus (GPU, unter
gpu_tor.lock wie ein Kreis-Torschritt), Zeile an modelle/<objekt>/realitaet_verlauf.jsonl anhaengen. Gleicher STL-sha wie die letzte
Zeile -> nur ausgeben (keine Neumessung).
  python3 tools/realitaet_prozent.py <objekt> [--neu]
"""
import sys, os, json, time, hashlib, subprocess, fcntl, tempfile, shutil

a = sys.argv; OBJ = a[1]; NEU = "--neu" in a
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT)
PY = "/media/oem/scan/venv-seg/bin/python"; KD = "/media/oem/scan/rc-park_kreis"; D = "/media/oem/scan/rc-park_daten/kaufhaus_alle"
O = json.load(open(f"modelle/{OBJ}/objekt.json")); K = O.get("kreis") or {}
STL = K.get("stl", f"modelle/stl/{OBJ}_1-87.stl"); SK = K.get("skala", 0.087)
GIT = K.get("gitter", D + "/segmente_gitter_v12.json"); KAM = K.get("kameras", D + "/sfm/kam_lot2.json")
WOLKE = K.get("wolke", "/media/oem/scan/rc-park_null/wolke_gemeinsam/lot2/j_voll_lot2.npy")
VF = f"modelle/{OBJ}/realitaet_verlauf.jsonl"

FD = os.path.join(KD, OBJ, "fotoform")
def foto_zahl(sha):
    """HAUPTZAHL seit 10.11. abends (Nutzer: 'umstellen'): Mittel der Form am Foto (teil_fotoform-F1, alle kalibrierten Fotos, Verdeckung beachtet)
    ueber alle Bauteile ohne Schnittkoerper, aus der Formliste des main-STL (fotoform_auffrischen.sh). Die Wolkenzahl war blind an steilen Flaechen
    (Tuer EG1 Wolke 0,989, Foto 0,457). None, solange die Formliste zu diesem STL fehlt."""
    import re as _re   # Metrik-Version (10.11. nachts): Formliste <sha>_<METRIK>.json bevorzugt, sonst v1 <sha>.json; Version steht in der Ausgabe (Zahlen verschiedener Metrik nicht vergleichen)
    _m = _re.search(r'^METRIK = "([^"]+)"', open(os.path.join(ROOT, "tools", "teil_fotoform.py")).read(), _re.M); met = _m.group(1) if _m else "v1"
    f = os.path.join(FD, f"{sha}_{met}.json")
    if not os.path.exists(f): f, met = os.path.join(FD, sha + ".json"), "v1"
    if not os.path.exists(f): return None
    t = {k: (v.get("_gesamt") or {}) for k, v in json.load(open(f))["teile"].items() if "__ausschnitt" not in k}
    t = {k: g for k, g in t.items() if g.get("f1") is not None}
    if not t: return None
    h = [g["f1_h"] for g in t.values() if g.get("f1_h") is not None]
    # PIXELGEWICHTET (11.11.): das Teilmittel FAELLT, wenn ein neues Teil dazukommt (Laubensockel 0,50/0,55: 23 Teile 69,6 %, mit Sockeln 68,2 %),
    # obwohl das Modell besser wurde -> Gewoelbe/Baldachine wuerden als Rueckschritt erscheinen. Zusatzzahl: Praezision/Recall ueber ALLE
    # Teil-Foto-Paare nach Kantenpixeln gewichtet (kleine neue Teile wiegen wenig; Bereiche gleicher Teile zaehlen mehrfach - nur Verlauf vergleichen).
    _T = json.load(open(f))["teile"]; mk = fk = pm = rf = 0.0
    for k, v in _T.items():
        if "__ausschnitt" in k: continue
        for fo, e in v.items():
            if fo == "_gesamt" or not isinstance(e, dict) or "mk_px" not in e: continue
            mk += e["mk_px"]; fk += e["fk_px"]; pm += e["praez"] * e["mk_px"]; rf += e["recall"] * e["fk_px"]
    _p, _r = (pm / mk if mk else 0.0), (rf / fk if fk else 0.0)
    pix = dict(prozent_foto_pixel=round(200 * _p * _r / (_p + _r), 1) if _p + _r else None, praez_pixel=round(_p, 3), recall_pixel=round(_r, 3))
    pm = maskiert_zahl(sha, met); pm = dict(prozent_foto_maskiert=pm) if pm is not None else {}
    return dict(metrik=met, **pm, prozent_foto=round(100 * sum(g["f1"] for g in t.values()) / len(t), 1), hoehe_prozent=round(100 * sum(h) / len(h), 1) if h else None, **pix,
                foto_teile={k: g["f1"] for k, g in t.items()}, foto_schwaechste=[[k, g["f1"]] for k, g in sorted(t.items(), key=lambda kv: kv[1]["f1"])[:4]])

def maskiert_zahl(sha, met):
    """NEBENZAHL (SPEC_STOERMASKE, 11.11.): Mittel Foto-F1 derselben Teile mit Stoermaske (teil_fotoform --stoermaske an), aus
    rc-park_kreis/<objekt>/fotoform_stoermaske/<sha>_<metrik>_stoermaske.json (Erzeugung: tools/stoermaske_auffrischen.sh). Hauptzahl bleibt unmaskiert.
    None, solange die maskierte Liste zu diesem STL fehlt. Eigener Ordner, damit kreis-Formlisten-Suche (glob im fotoform-Ordner) sie nie findet."""
    f = os.path.join(KD, OBJ, "fotoform_stoermaske", f"{sha}_{met}_stoermaske.json")
    if not os.path.exists(f): return None
    t = {k: (v.get("_gesamt") or {}) for k, v in json.load(open(f))["teile"].items() if "__ausschnitt" not in k}
    t = {k: g for k, g in t.items() if g.get("f1") is not None}
    return round(100 * sum(g["f1"] for g in t.values()) / len(t), 1) if t else None

def zeile_ausgeben(z, vor):
    if z.get("prozent_foto") is not None:
        vf = next((v for v in [vor] if v and v.get("prozent_foto") is not None), None)
        d = "" if vf is None else f" ({'+' if z['prozent_foto'] >= vf['prozent_foto'] else ''}{z['prozent_foto'] - vf['prozent_foto']:.1f} Punkte gegen {vf['zeit'][11:16]})"
        print(f"REALITAET (Foto) {z['prozent_foto']:.1f} %{d} | Hoehe {z.get('hoehe_prozent')} % | schwaechste am Foto: "
              + ", ".join(f"{t} {b:.2f}" for t, b in z.get("foto_schwaechste") or []), flush=True)
        if z.get("prozent_foto_maskiert") is not None:
            print(f"  Nebenzahl Foto mit Stoermaske {z['prozent_foto_maskiert']:.1f} % (Menschen/Fahrzeuge/Schilder/Moebel/Pflanzen/Fahnen ausgenommen; Hauptzahl unveraendert)", flush=True)
        if z.get("prozent_foto_pixel") is not None:
            vp = vor.get("prozent_foto_pixel") if vor else None
            print(f"  Foto pixelgewichtet {z['prozent_foto_pixel']:.1f} %" + (f" ({z['prozent_foto_pixel'] - vp:+.1f})" if vp is not None else "")
                  + f" (Praezision {z['praez_pixel']}, Recall {z['recall_pixel']}; neue Teile senken diese Zahl nicht)", flush=True)
    else:
        print("REALITAET (Foto): folgt, sobald die Formliste zu diesem STL fertig ist (fotoform_auffrischen.sh ruft --nur_foto auf)", flush=True)
    if "prozent" not in z: return
    d = "" if (vor is None or "prozent" not in vor) else f" ({'+' if z['prozent'] >= vor['prozent'] else ''}{z['prozent'] - vor['prozent']:.1f} Punkte gegen {vor['zeit'][11:16]})"
    print(f"  Nebenzahl Wolke {z['prozent']:.1f} %{d} | Fotokanten im Modell {z['kanten_recall_prozent']:.1f} % | Teile >= 0,9: {z['teile_gut']}/{z['teile_n']}"
          f" | Pruefstand {z['pruefstand']} | schwaechste: " + ", ".join(f"{t} {b:.2f}" for t, b in z["schwaechste"]), flush=True)

def main():
    sha = hashlib.sha256(open(STL, "rb").read()).hexdigest()[:16]
    alt = [json.loads(l) for l in open(VF) if l.strip()] if os.path.exists(VF) else []
    if "--nur_foto" in a:   # nach der Formliste: Fotozahl zur letzten Zeile dieses STL nachtragen (neue Zeile, Wolkenwerte uebernommen)
        fz = foto_zahl(sha)
        if fz is None: print("keine Formliste zu", sha); return 1
        basis = next((z for z in reversed(alt) if z["stl_sha"] == sha), None)
        if basis and basis.get("prozent_foto") == fz["prozent_foto"]: zeile_ausgeben(basis, None); return 0
        vor = next((z for z in reversed(alt) if z.get("prozent_foto") is not None), None)
        z = dict(basis or dict(stl_sha=sha, git=subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()))
        z.update(fz); z["zeit"] = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(VF, "a") as f: f.write(json.dumps(z, ensure_ascii=False) + "\n")
        zeile_ausgeben(z, vor); return 0
    if alt and alt[-1]["stl_sha"] == sha and not NEU:
        zeile_ausgeben(alt[-1], alt[-2] if len(alt) > 1 else None); return 0
    tmp = tempfile.mkdtemp(prefix="realitaet_", dir="/media/oem/scan/rc-park_kreis")
    ml = None
    if not os.environ.get("REALITAET_MERGE_LOCK_GEHALTEN"):   # main_abnahme.sh haelt merge.lock schon (zweites flock = Verklemmung)
        ml = open(os.path.join(KD, OBJ, "merge.lock"), "a"); fcntl.flock(ml, fcntl.LOCK_EX)   # kein Spur-Merge waehrend des Exports
    try:
        tdir = os.path.join(tmp, "teile"); os.makedirs(tdir)
        r = subprocess.run(O["generator"], shell=True, cwd=ROOT, env=dict(os.environ, BAUTEILE_AUS=tdir), capture_output=True, text=True)
        if r.returncode != 0: print("Export fehlgeschlagen:", r.stderr[-800:]); return 1
        if hashlib.sha256(open(STL, "rb").read()).hexdigest()[:16] != sha: print("STL hat sich beim Export geaendert - abgebrochen"); return 1
        js = os.path.join(tmp, "zeile.json")
        cmd = [PY, "-W", "ignore", "-I", "tools/konvergenz_bericht.py", OBJ, "--stl", STL, "--skala", str(SK), "--gitter", GIT, "--wolke", WOLKE,
               "--teile_dir", tdir, "--kameras", KAM, "--etikett", "realitaet main", "--trocken", "--json_aus", js]
        for v in range(6):   # wie sh_tor: unter der Torsperre, CUDA-OOM = Infrastruktur -> warten und wiederholen
            with open(os.path.join(KD, "gpu_tor.lock"), "a") as lk:
                fcntl.flock(lk, fcntl.LOCK_EX); r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
            if "out of memory" not in (r.stdout + r.stderr).lower(): break
            print(f"OOM in konvergenz_bericht (Versuch {v + 1}/6), warte", flush=True); time.sleep(120)
        if not os.path.exists(js): print("konvergenz_bericht ohne Ergebnis:", (r.stdout + r.stderr)[-800:]); return 1
        k = json.load(open(js))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        if ml: ml.close()
    tl = [t for t in k.get("wolkenbeleg_teile") or [] if t.get("beleg") is not None]
    if not tl: print("keine Bauteile mit Daten"); return 1
    ps = k.get("pruefstand") or {}
    z = dict(zeit=time.strftime("%Y-%m-%d %H:%M:%S"), git=subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip(),
             stl_sha=sha, prozent=round(100 * sum(t["beleg"] for t in tl) / len(tl), 1),
             kanten_recall_prozent=round(100 * k["kanten"]["gesamt"]["recall"], 1), teile_n=len(tl), teile_gut=sum(t["beleg"] >= 0.9 for t in tl),
             pruefstand=f"{ps.get('ok')}/{ps.get('n')}", schwaechste=[[t["teil"], t["beleg"]] for t in sorted(tl, key=lambda t: t["beleg"])[:4]],
             teile={t["teil"]: t["beleg"] for t in tl}, masz="prozent = Mittel Wolkenbeleg (Nebenzahl); prozent_foto = Mittel Foto-F1 (HAUPTZAHL seit 10.11. abends)")
    z.update(foto_zahl(sha) or {})
    with open(VF, "a") as f: f.write(json.dumps(z, ensure_ascii=False) + "\n")
    zeile_ausgeben(z, next((v for v in reversed(alt) if v.get("prozent_foto") is not None), alt[-1] if alt else None)); return 0

if __name__ == "__main__":
    sys.exit(main())
