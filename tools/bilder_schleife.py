#!/usr/bin/env python3
"""bilder_schleife.py - Bilder in STUFEN holen, nur wenn sie eine GEMESSENE Luecke schliessen (Plan M9/M10, Nutzerbeschluss 3.11.).

Stufen (Plan als Voreinstellung, alles ANNAHME und Argument):
  Stufe 0  grobes Annahmemodell: moeglichst wenige, moeglichst VERSCHIEDENE Bilder: nur Klasse 'neu' (neuer Blickwinkel), hoechstens --s0-je-seite (1) je Seite; aehnliche Bilder werden NICHT genommen.
  Stufe 1  weitere 'neu'-Blickwinkel fuer Seiten/Baender ohne Abdeckung (--s1-je-seite, 3).
  Stufe >=2 zusaetzlich 'aehnlich' (Inlier-Anteil 0,25..0,85 = Parallaxe) NUR fuer Seiten, deren Netz schlecht bestimmt scheint (ANNAHME: Seite hat schon >= --viele-fotos Fotos und liegt trotzdem
           unter dem Ziel - viele Fotos, wenig Basis), gedeckelt je Blickgruppe (--max-je-gruppe) und je Seite (--s2-je-seite). Dubletten nie.
  Nach JEDER Stufe wird gemessen (Foto-Farbflaeche je Seite aus textur_abdeckung.json, Kamerazahl aus abdeckung.json; mit --bewerten-kommando werden vorher Netze/Textur neu gerechnet und der Gewinn ist
  GEMESSEN; ohne Kommando gilt nur ein PROXY (neue brauchbare Kameras = EXIF vollstaendig auf Luecken-Seiten, kein Modellgewinn)). Stopp: Gewinn <= Rauschen in --geduld Stufen hintereinander,
  keine Luecke mehr, keine neue Quelle, oder --stufen erreicht.
Luecke einer Seite: Foto-Farbanteil < --ziel-proz (60 %, ANNAHME). Fehlen audit/abdeckung.json oder textur_abdeckung.json (oder --aktualisieren), laufen abdeckung_quellen.py / textur_projektion.py (CPU) vorher.
Lizenzklassen: zentral aus tools/lizenz_register.py (frei, frei_namensnennung, frei_sharealike, nc, unfrei, unklar) je Bild im Manifest ('lizenz_klasse', Originaltext 'license'); Mapillary = nc;
  --produkt holt/sortiert nur Klassen mit Produkt-Pixel ja/bedingt. OHNE --produkt werden auch nc/unfrei/unklar Bilder geholt (nur private Messvorlage). Am Ende ruft die Schleife lizenz_register.py auf.
EXIF (M10): Modell/Brennweite aus der Commons-API (Thumbnails tragen keins); Stufe vollstaendig/teilweise/fehlt je Bild; 'fehlt' = als Texturquelle abwerten.

  python3 -I tools/bilder_schleife.py modelle/<objekt>/objekt.json [--stufen 4] [--geduld 1] [--produkt] [--cpu] [--nur-kandidaten] [--max-neu 20] [--max-kandidaten N]
        [--ausgabe DIR] [--mapillary] [--einsortieren] [--bewerten-kommando "..."] [--rauschen-proz 2] [--rauschen-kameras 2] [--aktualisieren]
  EINZELSTUFE (fuer treppe.py): ... --stufe K   (nur Stufe K; Zustand aus audit/bilder_schleife.json). Exit 0 = Gewinn ueber Rauschen, weiter; Exit 3 = STOPP (Grund im Bericht); Exit 1 = Fehler.
Bericht: modelle/<objekt>/audit/bilder_schleife.json - je Stufe: Parameter, Luecken vorher, jedes Bild (Klasse, Seite, Luecke die es schliessen soll, Lizenzklasse, EXIF), gemessener Gewinn, Stopp-Grund.
EHRLICH: Commons liefert nur frei lizenzierte Bilder; nc/unfrei kommen ueber Mapillary (angebunden, mit --mapillary, noch NICHT kalibriert) oder von Hand (Video). Flickr/Google/Bing/Social Media sind NICHT angebunden
(API-Schluessel bzw. Nutzungsbedingungen; Google Street View darf nicht gescrapt werden). Wo nirgends ein Bild existiert, meldet der Bericht eine Luecke und erfindet nichts. 'Hoechstens 1 Bild je Hoehenband' ist vor der
Kalibrierung NICHT umsetzbar (ein Bild hat noch keine Kamera) - Stufe 0 begrenzt je Seite; Hoehenbaender werden erst nach der Messung (schlechte_baender) ausgewertet.
"""
import sys, os, json, argparse, subprocess, time

TOOLS = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, TOOLS)
import lizenz_register as LR
PY = "/media/oem/scan/venv-seg/bin/python"; PC = "/media/oem/scan/venv-colmap/bin/python"
SEITEN = ["Nord", "Sued", "Ost", "West"]; PRODUKT_KL = "frei,frei_namensnennung,frei_sharealike"

def lade(p, std=None):
    try: return json.load(open(p))
    except Exception: return std

def luecken(od, objp, ziel_proz, aktualisieren, env):
    """-> {seite: dict(foto_proz, fotos_zahl, luecke, schlechte_baender)}; ruft bei Bedarf die Messwerkzeuge auf (CPU)."""
    ap_, tp_ = os.path.join(od, "audit", "abdeckung.json"), os.path.join(od, "audit", "textur_abdeckung.json")
    if aktualisieren or not os.path.exists(ap_): subprocess.run([PC, "-I", os.path.join(TOOLS, "abdeckung_quellen.py"), objp], env=env, check=False, stdout=subprocess.DEVNULL)
    if aktualisieren or not os.path.exists(tp_): subprocess.run([PY, "-W", "ignore", "-I", os.path.join(TOOLS, "textur_projektion.py"), objp, "--ohne-drohne"], env=env, check=False, stdout=subprocess.DEVNULL)
    tex, abd = lade(tp_, {}), lade(ap_, {}); out = {}
    for s in SEITEN:
        b = (tex.get("je_seite_und_band") or {}).get(s, {}); fl = sum(x["flaeche_m2"] for x in b.values())
        foto = sum(x["flaeche_m2"] * x["foto_proz"] for x in b.values()) / fl if fl else 0.0
        out[s] = dict(foto_proz=round(foto, 1), fotos_zahl=((abd.get("quellen") or {}).get("fotos", {}).get("je_seite") or {}).get(s, 0), luecke=foto < ziel_proz,
                      schlechte_baender={k: x["foto_proz"] for k, x in b.items() if x["foto_proz"] < ziel_proz and x["flaeche_m2"] > 1.0})
    return out

def stufen_plan(k, L, a):
    """Parameter der Stufe k aus den gemessenen Luecken L. -> dict(bild_klassen, max_je_seite, aehnlich_seiten, seiten, beschreibung)."""
    gap = [s for s in sorted(L, key=lambda s: L[s]["foto_proz"]) if L[s]["luecke"]]
    if k == 0: return dict(bild_klassen="neu", max_je_seite=a.s0_je_seite, aehnlich_seiten=[], seiten=gap, beschreibung="grobes Annahmemodell: nur 'neu', wenige verschiedene Blickwinkel")
    if k == 1: return dict(bild_klassen="neu", max_je_seite=a.s1_je_seite, aehnlich_seiten=[], seiten=gap, beschreibung="weitere 'neu'-Blickwinkel fuer Seiten ohne Abdeckung")
    schlecht = [s for s in gap if L[s]["fotos_zahl"] >= a.viele_fotos]     # viele Fotos, trotzdem Luecke -> Netz schlecht bestimmt (ANNAHME)
    return dict(bild_klassen="neu,aehnlich", max_je_seite=a.s2_je_seite, aehnlich_seiten=schlecht, seiten=gap,
                beschreibung=f"'aehnlich' (Parallaxe) nur fuer Seiten mit >= {a.viele_fotos} Fotos und trotzdem Luecke: {schlecht or 'keine'}; sonst 'neu'")

def mapillary_holen(obj, od, aus, n_max, radius, env):
    """Offizielle Graph-API ueber mapillary_rip.py; Seite je Bild aus der Position relativ zum Objekt im Modellrahmen. Klasse nc (lizenz_register: Mapillary = nc)."""
    import bilder_holen as BH, abdeckung_quellen as AQ
    if not (os.path.exists(os.path.expanduser("~/.config/mapillary_token")) or os.environ.get("MAPILLARY_TOKEN")): return dict(status="kein Token (~/.config/mapillary_token)", bilder=0)
    A3 = lade(os.path.join(od, "anker3d.json")); E0, N0 = A3["mitte_utm"]; lat, lon = BH.utm_zu_wgs84(E0, N0); xh, yh = A3["xhat_utm"], A3["yhat_utm"]
    out = os.path.join(aus, "mapillary"); os.makedirs(out, exist_ok=True)
    r = subprocess.run([PY, os.path.join(TOOLS, "mapillary_rip.py"), "--lat", str(lat), "--lon", str(lon), "--out", out, "--radius", str(radius), "--max", str(n_max), "--aim-tol", "180"], env=env, capture_output=True, text=True)
    M = lade(os.path.join(out, "manifest.json"), {}); views = M.get("views", []); konv = AQ.seiten_aus_konvention(obj); je = {}
    for v in views:
        E, N = BH.wgs84_zu_utm(v["lat"], v["lon"]); dE, dN = E - E0, N - N0; x = dE * xh[0] + dN * xh[1]; y = dE * yh[0] + dN * yh[1]
        v["seite"] = AQ.seite_von(x, y, konv); v["lizenz"] = "Mapillary (CC BY-NC-SA laut Projektdoku; ANNAHME, vor Verkauf pruefen)"; v["lizenz_klasse"] = LR.klasse(v["lizenz"], "mapillary")
        v["kamera"] = "nicht bewertet (kein EXIF, nicht kalibriert)"; je[v["seite"]] = je.get(v["seite"], 0) + 1
    json.dump(dict(M, views=views), open(os.path.join(out, "manifest.json"), "w"), indent=1, ensure_ascii=False)
    return dict(status="ok" if views else "keine Bilder (" + ((r.stdout + r.stderr).strip().splitlines() or [""])[-1][:160] + ")", bilder=len(views), je_seite=je, lizenz_klasse=LR.klasse("", "mapillary"), ordner=out)

def stufe_ausfuehren(k, L, a, ctx, bekannt):
    """Eine Stufe: holen -> (einsortieren) -> (bewerten) -> messen. -> (stufen_dict, L_neu, weiter:bool, stopp_grund|None)."""
    objp, od, obj, env = ctx["objp"], ctx["od"], ctx["obj"], ctx["env"]; plan = stufen_plan(k, L, a); aus_r = os.path.join(ctx["basis"], f"stufe_{k}"); os.makedirs(aus_r, exist_ok=True); t0 = time.time()
    st = dict(stufe=k, beschreibung=plan["beschreibung"], parameter={x: plan[x] for x in ("bild_klassen", "max_je_seite", "aehnlich_seiten", "seiten")}, luecken_vorher={s: dict(L[s]) for s in SEITEN}, ordner=aus_r)
    if not plan["seiten"]: return st, L, False, "keine Luecke (alle Seiten >= Ziel)"
    cmd = [PY, "-W", "ignore", "-I", os.path.join(TOOLS, "bilder_holen.py"), objp, "--ausgabe", aus_r, "--seiten", ",".join(s.lower() for s in plan["seiten"]), "--nur-seiten", "--lizenz-klassen", ctx["klassen"],
           "--max-neu", str(a.max_neu), "--bild-klassen", plan["bild_klassen"], "--max-je-gruppe", str(a.max_je_gruppe),
           "--cache-ordner", os.path.join(ctx["basis"], "_cache"), "--schwellen-cache", os.path.join(ctx["basis"], "schwellen.json")]
    if plan["aehnlich_seiten"]: cmd += ["--aehnlich-seiten", ",".join(s.lower() for s in plan["aehnlich_seiten"])]
    if plan["max_je_seite"]: cmd += ["--max-je-seite", str(plan["max_je_seite"])]
    if a.nur_kandidaten: cmd.append("--nur-kandidaten")
    if a.max_kandidaten: cmd += ["--max-kandidaten", str(a.max_kandidaten)]
    if bekannt: cmd += ["--bekannt-aus"] + bekannt
    print(f"\nStufe {k}: {plan['beschreibung']}; Seiten {plan['seiten']}", flush=True); st["bilder_holen_rc"] = subprocess.run(cmd, env=env).returncode
    if a.nur_kandidaten:
        kd = lade(os.path.join(aus_r, "kandidaten.json"), []); lk = {}
        for x in kd: lk[x.get("lizenz_klasse", "?")] = lk.get(x.get("lizenz_klasse", "?"), 0) + 1
        st.update(kandidaten=len(kd), lizenzklassen=lk, exif_stufen={e: sum(1 for x in kd if x.get("exif_stufe") == e) for e in ("vollstaendig", "teilweise", "fehlt")}); return st, L, False, "nur Kandidaten (kein Laden, keine Bewertung)"
    man = lade(os.path.join(aus_r, "manifest.json"), {"images": []}); imgs = man.get("images", []); st["manifest"] = os.path.join(aus_r, "manifest.json"); gaps = [s.lower() for s in plan["seiten"]]
    bilder = []
    for i in imgs:
        sv = ((i.get("aehnlich_basis") or {}).get("seite") or "unbekannt").lower(); sn = sv.capitalize(); ln = L.get(sn, {})
        warum = (f"{i.get('klasse')}: Seite {sn} hat {ln.get('foto_proz', '?')} % Foto-Farbe (Luecke)" + ("; neuer Blickwinkel" if i.get("klasse") == "neu" else f"; Parallaxe zu {i.get('aehnlich_zu')} fuer Seite mit {ln.get('fotos_zahl', '?')} Fotos und schlecht bestimmtem Netz"))
        bilder.append(dict(datei=i["file"], titel=i["title"], klasse=i.get("klasse"), seite=sv, schliesst_luecke=sv in gaps, begruendung=warum, lizenz=i.get("license"), lizenz_klasse=i.get("lizenz_klasse"),
                           produkt_pixel=i.get("produkt_pixel"), exif_stufe=i.get("exif_stufe"), inlier_zum_basisfoto=(i.get("aehnlich_basis") or {}).get("inlier")))
    brauchbar = sum(1 for b in bilder if b["schliesst_luecke"] and b["exif_stufe"] == "vollstaendig")
    st.update(neu_geladen=len(imgs), bilder=bilder, neue_brauchbare_kameras_auf_luecken=brauchbar, texturabwertung=[b["datei"] for b in bilder if b["exif_stufe"] == "fehlt"])
    if a.mapillary: st["mapillary"] = mapillary_holen(obj, od, aus_r, a.mapillary_max, a.mapillary_radius, env)
    if a.einsortieren and imgs:
        st["einsortiert_rc"] = subprocess.run([PY, "-W", "ignore", "-I", os.path.join(TOOLS, "bilder_einsortieren.py"), objp, "--eingang", aus_r] + (["--produkt"] if a.produkt else []), env=env).returncode
    L_neu, gewinn = L, None
    if a.bewerten_kommando:
        st["bewerten_rc"] = subprocess.run(a.bewerten_kommando, shell=True, env=env).returncode; L_neu = luecken(od, objp, a.ziel_proz, True, env)
        gewinn = round(sum(L_neu[s]["foto_proz"] - L[s]["foto_proz"] for s in plan["seiten"]) / len(plan["seiten"]), 2); st["gewinn_proz_punkte_auf_luecken"] = gewinn; st["gewinn_art"] = "GEMESSEN (Foto-Farbflaeche, Mittel der Luecken-Seiten)"
    else: st["gewinn_art"] = "PROXY (neue brauchbare Kameras, kein Modellgewinn gemessen)"
    st["luecken_nachher"] = {s: dict(L_neu[s]) for s in SEITEN}; st["sekunden"] = round(time.time() - t0)
    print(f"  Stufe {k}: {len(imgs)} Bilder (brauchbare Kameras auf Luecken {brauchbar}), {st['gewinn_art']}" + (f", Gewinn {gewinn} Pp" if gewinn is not None else ""), flush=True)
    if not imgs: return st, L_neu, False, "keine neue Quelle (nichts Neues gefunden, das die Luecken-Seiten betrifft)"
    kein_gewinn = (gewinn <= a.rauschen_proz) if gewinn is not None else (brauchbar <= a.rauschen_kameras)
    st["gewinn_im_rauschen"] = bool(kein_gewinn)
    return st, L_neu, True, None

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--stufen", type=int, default=4); ap.add_argument("--stufe", type=int, help="nur diese Stufe (Einzelstufe fuer treppe.py)"); ap.add_argument("--geduld", type=int, default=1)
    ap.add_argument("--ziel-proz", type=float, default=60.0, help="ANNAHME: Seite mit weniger Foto-Farbflaeche (%%) hat eine Luecke"); ap.add_argument("--viele-fotos", type=int, default=10, help="ANNAHME: >= N Fotos auf einer Seite und trotzdem Luecke = Netz schlecht bestimmt -> 'aehnlich' erlaubt")
    ap.add_argument("--s0-je-seite", type=int, default=1); ap.add_argument("--s1-je-seite", type=int, default=3); ap.add_argument("--s2-je-seite", type=int, default=6); ap.add_argument("--max-je-gruppe", type=int, default=2, help="Deckel 'aehnlich' je Blickgruppe und Stufe")
    ap.add_argument("--produkt", action="store_true", help="nur Lizenzklassen mit Produkt-Pixel ja/bedingt holen/einsortieren (Verkaufsweg)"); ap.add_argument("--cpu", action="store_true", help="GPU fuer Kindprozesse ausblenden")
    ap.add_argument("--nur-kandidaten", action="store_true"); ap.add_argument("--max-neu", type=int, default=20); ap.add_argument("--max-kandidaten", type=int)
    ap.add_argument("--ausgabe", help="Basisordner der Stufen (Standard: bildquellen.ausgabe + '_schleife')"); ap.add_argument("--mapillary", action="store_true"); ap.add_argument("--mapillary-max", type=int, default=30); ap.add_argument("--mapillary-radius", type=float, default=80)
    ap.add_argument("--einsortieren", action="store_true", help="in den Objektordner einsortieren (aendert objekt.json und den Fotoordner!)"); ap.add_argument("--bewerten-kommando", help="Shell-Kommando zum Neurechnen (Netze/Kameras/Textur); danach wird der Gewinn gemessen")
    ap.add_argument("--rauschen-proz", type=float, default=2.0, help="ANNAHME: Gewinn <= 2 Prozentpunkte Foto-Farbe = Rauschen"); ap.add_argument("--rauschen-kameras", type=int, default=2, help="ANNAHME: <= 2 neue brauchbare Kameras auf Luecken-Seiten = Rauschen (PROXY)")
    ap.add_argument("--aktualisieren", action="store_true", help="Messwerkzeuge vor der ersten Stufe neu laufen lassen")
    a = ap.parse_args(); objp = os.path.abspath(a.objekt); obj = lade(objp); od = os.path.dirname(objp); repo = os.path.dirname(os.path.dirname(od)); env = dict(os.environ)
    if a.cpu: env["CUDA_VISIBLE_DEVICES"] = ""
    Q = obj.get("bildquellen") or {}; basis = a.ausgabe or (Q.get("ausgabe", f"daten/{os.path.basename(od)}/fotos_eingang").rstrip("/") + "_schleife"); basis = basis if os.path.isabs(basis) else os.path.join(repo, basis); os.makedirs(basis, exist_ok=True)
    klassen = PRODUKT_KL if a.produkt else "alle"; ctx = dict(objp=objp, od=od, obj=obj, env=env, basis=basis, klassen=klassen); op = os.path.join(od, "audit", "bilder_schleife.json"); os.makedirs(os.path.dirname(op), exist_ok=True)
    alt = lade(op, {}) if a.stufe is not None else {}; stufen = list(alt.get("stufen", [])) if a.stufe is not None else []
    bericht = dict(objekt=obj.get("name"), stand=time.strftime("%F %T"), produkt=a.produkt, lizenzklassen_erlaubt=klassen, ziel_proz=a.ziel_proz, geduld=a.geduld, rauschen=dict(proz=a.rauschen_proz, kameras=a.rauschen_kameras),
                   annahmen=["Luecke = Foto-Farbanteil der Seite < --ziel-proz (flaechengewichtet ueber Hoehenbaender)", "Netz 'schlecht bestimmt' = >= --viele-fotos Fotos auf der Seite und trotzdem Luecke", "Rauschen: Gewinn <= --rauschen-proz bzw. <= --rauschen-kameras (PROXY)",
                             "hoechstens 1 Bild je Hoehenband vor der Kalibrierung nicht umsetzbar -> je Seite", "Mapillary = nc (lizenz_register, Projektregel)"], stufen=stufen, stopp=None)
    L = luecken(od, objp, a.ziel_proz, a.aktualisieren, env); bericht["luecken_start"] = (alt.get("luecken_start") if a.stufe is not None else None) or L
    print("Luecken (Foto-Farbflaeche je Seite):", {s: f"{v['foto_proz']} %{' LUECKE' if v['luecke'] else ''}" for s, v in L.items()})
    ks = [a.stufe] if a.stufe is not None else list(range(a.stufen)); bekannt = [s["manifest"] for s in stufen if s.get("manifest")]; stopp, rc, ruhig = None, 0, 0
    for s_ in stufen[::-1]:                                        # Geduld-Zaehler aus dem Zustand (Einzelstufenmodus)
        if s_.get("gewinn_im_rauschen"): ruhig += 1
        else: break
    for k in ks:
        st, L, weiter, grund = stufe_ausfuehren(k, L, a, ctx, bekannt); stufen = [x for x in stufen if x.get("stufe") != k] + [st]; bericht["stufen"] = stufen
        if st.get("manifest"): bekannt.append(st["manifest"])
        if not weiter: stopp = grund; break
        ruhig = ruhig + 1 if st.get("gewinn_im_rauschen") else 0
        if ruhig >= a.geduld: stopp = f"Gewinn <= Rauschen in {ruhig} Stufe(n) hintereinander (--geduld {a.geduld})"; break
    else: stopp = f"{'Stufe ' + str(a.stufe) if a.stufe is not None else '--stufen ' + str(a.stufen)} erreicht" if a.stufe is None else None
    bericht["stopp"] = stopp; bericht["luecken_ende"] = L; rc = 3 if stopp else 0
    bericht["quellen"] = dict(commons="angebunden (bilder_holen.py): nur frei lizenzierte Bilder; Kategorien/Suchen/Geosearch aus objekt.json", mapillary="angebunden mit --mapillary (mapillary_rip.py, Graph-API, Token): Klasse nc; noch NICHT kalibriert/einsortiert (kein EXIF)",
        video="nicht automatisch: Urheberrecht (Standard-YouTube-Lizenz); nur von Hand als private Messvorlage, Klasse unfrei", flickr_google_bing_social="NICHT angebunden: API-Schluessel bzw. Nutzungsbedingungen noetig; Google Street View darf nicht gescrapt werden")
    bericht["was_fehlt"] = {s: dict(foto_proz=L[s]["foto_proz"], schlechte_baender=L[s]["schlechte_baender"], hinweis=("kein (weiteres) Bild aus den angebundenen Quellen gefunden oder Kamera nicht loesbar - Luecke bleibt; neue eigene Fotos von dieser Seite noetig" if L[s]["luecke"] else "ok")) for s in SEITEN}
    lr = subprocess.run(["python3", "-I", os.path.join(TOOLS, "lizenz_register.py"), objp], env=env, capture_output=True, text=True); bericht["lizenzregister"] = dict(rc=lr.returncode, ausgabe="modelle/<objekt>/LIZENZ_BILDER.json und .md (von lizenz_register.py)")
    json.dump(bericht, open(op, "w"), indent=1, ensure_ascii=False); print(f"\nSTOPP: {stopp}" if stopp else "\nweiter (Gewinn ueber Rauschen)", f"\nBericht: {op}"); sys.exit(rc)

if __name__ == "__main__":
    main()
