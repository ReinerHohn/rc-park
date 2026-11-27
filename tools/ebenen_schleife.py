#!/usr/bin/env python3
"""ebenen_schleife.py - KONVERGIERENDE SCHLEIFE: Arbeitsliste der Abweichung abarbeiten, Umbau nur bei besserer Kennzahl behalten (21.11.2026).

Methode: modelle/METHODE_EBENEN_BAUPLAN.md Schritt 6. Nutzer 21.11.: "du musst mich ersetzen durch eine automatische Bauplanabweichung ... wir brauchen eine konvergierende Loop."
Je Runde:
  1. KANDIDAT = (a) Wandversatz: Wandebene liegt laut Kanten/Sweep >= 8 cm neben der Fassadenebene des Koerpers -> ganze Wand auf die gemessene Tiefe;
                (b) groesster noch nicht versuchter Fleck 'Form fehlt' aus audit/ebenen_abweichung*.json (Fotokanten ohne Modellflaeche): Rechteck des Flecks auf die
                    gemessene Tiefe der Kanten (Ebene + mittlere Tiefe des Flecks); Ist-Tiefe = Modellflaeche am Fleck (naechste Flaechenpunkte).
  2. Korrektur in audit/schleife_korrekturen.json eintragen -> Generator baut (bauteile.korrekturen_aus_json) -> tools/ebenen_abweichung.py misst neu.
  3. ANNEHMEN nur, wenn auf der Ebene des Kandidaten 'an Kante' oder 'an Flaeche' steigt (>= --gewinn), keine andere Ebene bei 'an Flaeche' um mehr als --verlust faellt
     und die Gegenprobe dichte Wolke auf der Ebene nicht um mehr als --verlust faellt. Sonst: angenommen = false mit Grund (bleibt als Protokoll in der Datei, wird nicht gebaut).
  4. ENDE: kein Kandidat mehr, --runden erreicht oder zwei Runden hintereinander ohne Gewinn.
Flecken auf Vorbau-Ebenen werden noch nicht bearbeitet (der Vorbau wird NACH den Korrekturen gebaut - 1. Lauf: drei Runden ohne jede Wirkung); sie bleiben OFFEN in der Liste.
Ein verworfener Fleck wird nicht wiederholt (Schluessel auf 0,5 m gerundet) (gilt als OFFEN: Methode fehlt oder Fotoluecke). Verlauf: audit/schleife_verlauf.jsonl (je Runde Kandidat, Kennzahlen, Urteil, git-Stand).
Aufruf: ebenen_schleife.py <objekt.json> <ebenen-ordner> [--wolke npy] [--runden 8] [--neu | --neu_eigene] [--ohne_wandversatz]
  --neu: alle vorhandenen Korrekturen verwerfen; --neu_eigene (27.11.2026, Kette): nur die EIGENEN (quelle ebenen_schleife oder ohne quelle) verwerfen, fremde
  (tools/wandlage_fotokanten.py 'wl_*') bleiben; --ohne_wandversatz: Kandidat (a) aus (die Kette setzt die Wand mit wandlage_fotokanten.py, dessen Guards gelten).
Danach die volle Abnahme (tools/bauen_abnehmen.sh) laufen lassen - die Schleife baut nur den Generator.
27.11.2026 (K7, Kette hinter RCPARK_EBENEN_SCHLEIFE=1): Flecken auch auf Schichten des Stapels (art 'schicht', tools/ebenen_stapel.py: Spitze + Wolke >= 80 %);
  Generator = objekt.json 'generator' (wie tools/bauen_abnehmen.sh; Bau gilt nur mit frisch geschriebenem STL), sonst modelle/<obj>_gen.py;
  ERFUNDEN-Guard: ein Umbau wird verworfen, wenn auf seiner Ebene der Anteil erfundener Modellkanten um mehr als --verlust steigt (nur wenn die Ebene vorher Modellkanten hatte).
rc 0 = mindestens eine Korrektur angenommen, 3 = keine, 2 = Abbruch (Ausgang nicht baubar/messbar).
"""
SCHLEIFE = "tools/ebenen_schleife.py"
import sys, os, json, argparse, subprocess, time, numpy as np

HIER = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HIER)
GEN_PY = os.path.expanduser("~/.venvs/rcpark/bin/python")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("ebenen"); ap.add_argument("--wolke"); ap.add_argument("--runden", type=int, default=8); ap.add_argument("--neu", action="store_true")
    ap.add_argument("--neu_eigene", action="store_true"); ap.add_argument("--ohne_wandversatz", action="store_true")
    ap.add_argument("--gewinn", type=float, default=0.003); ap.add_argument("--verlust", type=float, default=0.01); ap.add_argument("--min_punkte", type=int, default=300); a = ap.parse_args()
    import trimesh
    from scipy.spatial import cKDTree
    objp = os.path.abspath(a.objekt); od = os.path.dirname(objp); ob = os.path.basename(od); obj = json.load(open(objp)); A = os.path.join(od, "audit"); os.makedirs(A, exist_ok=True); stl = os.path.join(ROOT, obj.get("stl") or f"modelle/stl/{ob}_1-87.stl"); skala = float(obj.get("stl_massstab", 87)) / 1000.0
    kp = os.path.join(A, "schleife_korrekturen.json"); gen = os.path.join(ROOT, "modelle", f"{ob}_gen.py"); EJ = {e["id"]: e for e in json.load(open(os.path.join(a.ebenen, "ebenen.json")))["ebenen"]}
    KO = dict(quelle=SCHLEIFE, korrekturen=[]) if a.neu or not os.path.exists(kp) else json.load(open(kp))
    if a.neu_eigene: KO["korrekturen"] = [k_ for k_ in KO.get("korrekturen", []) if k_.get("quelle", SCHLEIFE) != SCHLEIFE]
    try: rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=od).stdout.strip()
    except Exception: rev = "?"

    def bauen_messen():
        json.dump(KO, open(kp, "w"), indent=1); t_b = time.time()
        r = subprocess.run(["bash", "-c", obj["generator"]] if obj.get("generator") else [GEN_PY, gen], capture_output=True, text=True, cwd=ROOT)
        if r.returncode != 0: return None, (r.stderr.strip().splitlines() or ["Generator abgestuerzt"])[-1][:200]
        if not os.path.exists(stl) or os.path.getmtime(stl) < t_b - 1 or os.path.getsize(stl) < 200: return None, f"Generator schrieb kein frisches STL ({stl})"      # wie bauen_abnehmen.sh/kette_beleg
        r = subprocess.run([sys.executable, "-W", "ignore", "-I", os.path.join(HIER, "ebenen_abweichung.py"), objp, a.ebenen, "--name", "_schleife"] + (["--wolke", a.wolke] if a.wolke else []), capture_output=True, text=True)
        if r.returncode != 0: return None, (r.stderr.strip().splitlines() or ["Abweichung abgestuerzt"])[-1][:200]
        return json.load(open(os.path.join(A, "ebenen_abweichung_schleife.json"))), ""

    def kenn(B): return {b["id"]: (b["an_flaeche"], b["an_kante"], b.get("wolke_an_flaeche"), b.get("erfunden"), b.get("modellkanten", 0)) for b in B["ebenen"]}
    def text(k): return " | ".join(f"{i} Fl {v[0] * 100:.0f} Ka {v[1] * 100:.0f}" + (f" Wo {v[2] * 100:.0f}" if v[2] is not None else "") for i, v in k.items())

    B, err = bauen_messen()
    if B is None: print("ABBRUCH beim Ausgangsstand:", err); return 2
    K0 = kenn(B); print("Ausgang:", text(K0), flush=True); versucht = {(k_["ebene"], k_["art"], k_.get("schluessel")) for k_ in KO["korrekturen"]}; ohne_gewinn = 0; runde = 0; n_neu = 0
    while runde < a.runden and ohne_gewinn < 2:
        kand = None
        for e in EJ.values():                                               # (a) Wandversatz zuerst
            if a.ohne_wandversatz: break
            if e["art"] == "wand" and abs(e["w"]) >= 0.08 and (e["id"], "wandversatz", None) not in versucht and any(b["id"] == e["id"] for b in B["ebenen"]):
                kand = dict(id=f"k{len(KO['korrekturen']):02d}", ebene=e["id"], art="wandversatz", schluessel=None, fassade=e["fassade"], o=e["o"], d=e["d"], n=e["n"], u0=e["zone"][0], u1=e["zone"][1], z0=max(e["zone"][2], 0.0), z1=e["zone"][3],
                            w_ist=0.0, w_soll=e["w"], grund=f"Wandebene {e['id']} liegt gemessen {e['w']:+.2f} m neben der Fassadenebene des Koerpers"); break
        if kand is None:                                                    # (b) groesster offener Fleck 'Form fehlt'
            fl = [(f_, b) for b in B["ebenen"] if EJ.get(b["id"], {}).get("art") in ("wand", "schicht") for f_ in b["liste_form"] if f_["punkte"] >= a.min_punkte]
            fl = [(f_, b) for f_, b in fl if (b["id"], "fleck", f"{round(f_['u0'] * 2) / 2},{round(f_['z0'] * 2) / 2},{round(f_['u1'] * 2) / 2},{round(f_['z1'] * 2) / 2}") not in versucht]
            if fl:
                f_, b = max(fl, key=lambda x: x[0]["punkte"]); e = EJ[b["id"]]; o = np.array(e["o"]); d = np.array(e["d"]); n = np.array(e["n"])
                u0, u1, z0, z1 = f_["u0"], f_["u1"], f_["z0"], f_["z1"]
                if u1 - u0 < 0.15: u0, u1 = 0.5 * (u0 + u1) - 0.075, 0.5 * (u0 + u1) + 0.075
                if z1 - z0 < 0.15: z0, z1 = 0.5 * (z0 + z1) - 0.075, 0.5 * (z0 + z1) + 0.075
                m = trimesh.load(stl); m.apply_scale(skala); C = m.triangles_center; cu = (C[:, :2] - o) @ d; fm = (cu > u0 - 1) & (cu < u1 + 1) & (C[:, 2] > z0 - 1) & (C[:, 2] < z1 + 1)
                w_soll = e["w"] + f_["tiefe"]; w_ist = None
                if fm.sum() >= 2:
                    mm = trimesh.Trimesh(m.vertices, m.faces[fm], process=False); Q, _ = trimesh.sample.sample_surface_even(mm, 200000)
                    G = np.array([[o[0] + u_ * d[0] + w_soll * n[0], o[1] + u_ * d[1] + w_soll * n[1], z_] for u_ in np.linspace(u0, u1, 6) for z_ in np.linspace(z0, z1, 6)]); _, ix = cKDTree(Q).query(G); w_ist = float(np.median((Q[ix][:, :2] - o) @ n))
                if w_ist is not None and abs(w_soll - w_ist) >= 0.05:
                    kand = dict(id=f"k{len(KO['korrekturen']):02d}", ebene=b["id"], art="fleck", schluessel=f"{round(f_['u0'] * 2) / 2},{round(f_['z0'] * 2) / 2},{round(f_['u1'] * 2) / 2},{round(f_['z1'] * 2) / 2}", fassade=e["fassade"], o=e["o"], d=e["d"], n=e["n"], u0=round(u0, 2), u1=round(u1, 2), z0=round(z0, 2), z1=round(z1, 2),
                                w_ist=round(w_ist, 3), w_soll=round(w_soll, 3), grund=f"{f_['punkte']} Fotokanten ohne Modellflaeche auf {b['id']}, Tiefe {f_['tiefe']:+.2f} m gegen die Ebene")
                else: versucht.add((b["id"], "fleck", f"{round(f_['u0'] * 2) / 2},{round(f_['z0'] * 2) / 2},{round(f_['u1'] * 2) / 2},{round(f_['z1'] * 2) / 2}")); continue
        if kand is None: print("kein Kandidat mehr"); break
        runde += 1; versucht.add((kand["ebene"], kand["art"], kand["schluessel"])); kand["angenommen"] = None; kand["quelle"] = SCHLEIFE; KO["korrekturen"].append(kand); t0 = time.time(); Bn, err = bauen_messen()
        if Bn is None: kand["angenommen"] = False; kand["urteil"] = "Bau/Messung gescheitert: " + err; Kn = None
        elif kand["ebene"] not in kenn(Bn): kand["angenommen"] = False; kand["urteil"] = "verworfen: Ebene nach dem Umbau nicht mehr messbar"; Kn = None
        else:
            Kn = kenn(Bn); v, nn = K0[kand["ebene"]], Kn[kand["ebene"]]; gew = ((nn[1] - v[1] >= a.gewinn) or (nn[0] - v[0] >= a.gewinn + 0.002)) and (v[1] - nn[1] <= a.verlust) and (v[0] - nn[0] <= a.verlust)      # 2. Fassung: weder Kante noch Flaeche duerfen merklich fallen (1. Lauf nahm einen Umbau an, der das Relief abtrug: Kante 50,5 -> 43,7)
            andere = [i for i in Kn if i != kand["ebene"] and i in K0 and K0[i][0] - Kn[i][0] > a.verlust]; wolke = v[2] is not None and nn[2] is not None and v[2] - nn[2] > a.verlust
            erf = v[4] > 0 and v[3] is not None and nn[3] is not None and nn[3] - v[3] > a.verlust      # 27.11.2026: Umbau darf keine erfundenen Modellkanten dazubauen (Ziel K7: erfunden abbauen)
            kand["vorher"] = dict(an_flaeche=v[0], an_kante=v[1], wolke=v[2], erfunden=v[3]); kand["nachher"] = dict(an_flaeche=nn[0], an_kante=nn[1], wolke=nn[2], erfunden=nn[3])
            if gew and not andere and not wolke and not erf: kand["angenommen"] = True; kand["urteil"] = "angenommen"
            else: kand["angenommen"] = False; kand["urteil"] = "verworfen: " + ("kein Gewinn auf der Ebene" if not gew else "") + (f" andere Ebene faellt ({', '.join(andere)})" if andere else "") + (" Wolken-Gegenprobe faellt" if wolke else "") + (f" erfundene Modellkanten steigen ({v[3] * 100:.0f} -> {nn[3] * 100:.0f} %)" if erf else "")
        print(f"Runde {runde}: {kand['id']} {kand['art']} {kand['ebene']} u {kand['u0']:.1f}..{kand['u1']:.1f} z {kand['z0']:.1f}..{kand['z1']:.1f} {kand['w_ist']:+.2f} -> {kand['w_soll']:+.2f} m: {kand['urteil']}"
              + (f"  [Fl {kand['vorher']['an_flaeche'] * 100:.1f} -> {kand['nachher']['an_flaeche'] * 100:.1f}, Ka {kand['vorher']['an_kante'] * 100:.1f} -> {kand['nachher']['an_kante'] * 100:.1f}"
                 + (f", Wolke {kand['vorher']['wolke'] * 100:.1f} -> {kand['nachher']['wolke'] * 100:.1f}" if kand['vorher']['wolke'] is not None else "") + "]" if Kn else "") + f" ({time.time() - t0:.0f} s)", flush=True)
        with open(os.path.join(A, "schleife_verlauf.jsonl"), "a") as f_: f_.write(json.dumps(dict(zeit=time.strftime("%Y-%m-%d %H:%M"), git=rev, runde=runde, **{k_: v_ for k_, v_ in kand.items() if k_ not in ("o", "d", "n")}), ensure_ascii=False) + "\n")
        if kand["angenommen"]: B, K0, ohne_gewinn = Bn, Kn, 0; n_neu += 1
        else: ohne_gewinn += 1
    Bf, err = bauen_messen()                                                # Endstand: nur angenommene Korrekturen gebaut
    if Bf is None: print("ABBRUCH beim Endstand:", err); return 2
    print("Ende:   ", text(kenn(Bf)))
    n_an = sum(1 for k_ in KO["korrekturen"] if k_.get("angenommen") and k_.get("quelle", SCHLEIFE) == SCHLEIFE); print(f"SCHLEIFE: {runde} Runden, {n_an} Korrekturen angenommen, {sum(1 for k_ in KO['korrekturen'] if k_.get('angenommen') is False)} verworfen -> {kp}")
    print(f"in diesem Lauf angenommen: {n_neu}"); return 0 if n_neu else 3


if __name__ == "__main__": sys.exit(main())
