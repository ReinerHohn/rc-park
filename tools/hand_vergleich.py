#!/usr/bin/env python3
"""hand_vergleich.py - Kettenergebnis (von null) gegen einen frueheren Handstand pruefen (21.11.2026, Kettenstufe 'bauplan', Ende).

Nutzer 21.11.: "Warum klappt das nicht, alles, was wir manuell gebaut haben, in eine Pipeline einzubauen?" - es gab keinen Massstab, der die Luecke zeigt;
die Kette meldete 'alle Stufen in Ordnung' bei einem Quader. Hier: <objekt>/referenz_hand.json (Bauteile + Masse aus dem Hand-Generator) gegen das, was die Kette
SELBST erzeugt hat (audit/vorbauten_auto.json, uhren_auto.json, oeffnungen_auto.json, fenster_auto.json, elemente.json, STL). Je Bauteil: PASST (alle Masse in Toleranz),
FALSCH (gefunden, Mass daneben), FEHLT (Kette baut es nicht). Nur Hoehen/Groessen, keine u-Lagen (anderer Rahmen).
Aufruf: hand_vergleich.py <objekt.json>   -> audit/hand_vergleich.json; rc 0 immer (Bericht, kein Tor), ohne referenz_hand.json rc 3.
"""
import sys, os, json


def lade(p):
    try: return json.load(open(p))
    except Exception: return None


FORM_NAME = (("rundbogen", "rund"), ("spitzbogen", "spitz"), ("stichbogen", "stich"), ("segmentbogen", "stich"), ("korbbogen", "korb"), ("rechteckfenster", "gerade"))


def soll_form(bauteil):
    """Formfamilie aus dem BAUTEILNAMEN der Referenz (kein Mass aus dem Handstand): 'rundbogenfenster' -> 'rund'. None = Name sagt keine Form."""
    return next((f for k, f in FORM_NAME if k in bauteil), None)


def form_ist(fz, tor, fid):
    """Gebaute Formfamilie der gezaehlten Fenster (bogen.form, Rechteck = 'gerade') + Urteil des Form-Tors (audit/fenster_form_tor.json) an denselben Kaesten.
    Kein Form-Tor-Bericht = 'unsicher' (die Form ist dann nicht an den Fotos geprueft)."""
    fo = sorted({(q.get("bogen") or {}).get("form", "gerade") for q in fz})
    L = [t for k, v in ((tor.get("fassaden") or {}).items() if tor else []) if (fid is None or k == fid) and isinstance(v, list) for t in v]
    ur = []
    for q in fz:
        t = next((t for t in L if isinstance(t, dict) and max(abs(a - b) for a, b in zip(t["kasten"], (q["u0"], q["u1"], q["z0"], q["z1"]))) < 0.05), None)
        ur.append(t["urteil"] if t else "FEHLT")
    e = dict(ist=fo[0] if len(fo) == 1 else ",".join(fo), tor=ur)
    if "FALSCH" in ur: e["tor_falsch"] = True; e["grund"] = "Form-Tor: Einzelfotos sagen eine andere Formfamilie"
    elif any(u != "PASST" for u in ur): e["unsicher"] = True; e["grund"] = "Form-Tor fehlt/unbestimmt (< 3 Fotos) - Form nicht an Fotos belegt"
    if any(q.get("form_unsicher") for q in fz): e["unsicher"] = True; e["grund"] = "nischen_fenster: " + next(q["form_unsicher"] for q in fz if q.get("form_unsicher"))
    return e


def main():
    obj = os.path.abspath(sys.argv[1]); od = os.path.dirname(obj); A = os.path.join(od, "audit"); R = lade(os.path.join(od, "referenz_hand.json"))
    if not R: print("keine referenz_hand.json"); return 3
    VB = lade(os.path.join(A, "vorbauten_auto.json")) or {}; UH = lade(os.path.join(A, "uhren_auto.json")) or {}; OE = lade(os.path.join(A, "oeffnungen_auto.json")) or {}
    FE = lade(os.path.join(A, "fenster_auto.json")) or {}; TOR = lade(os.path.join(A, "fenster_form_tor.json")) or {}; EL = lade(os.path.join(od, "elemente.json")) or []; txt = " ".join(e.get("element", "") for e in EL).lower()
    gal = [g["galerie"] for F in VB.get("fassaden", []) for g in F["gruppen"] if g.get("galerie")]
    ist = {}
    km = [(g["kanten_mass"], g) for F in VB.get("fassaden", []) for g in F["gruppen"] if (g.get("kanten_mass") or {}).get("kasten")]      # 21.11.2026: Masse aus den triangulierten Fotokanten gehen vor
    if km:
        k_, g_ = km[0]; K_ = k_["kasten"]; ist["galerie"] = dict(schwelle_unten=K_["z_unten"], holm_oben=K_["z_oben"], ausladung=k_["ausladung"], breite=K_["breite"], pfosten=len(k_.get("pfosten") or []), streben=(k_.get("konsolen") or {}).get("anzahl"))
        v = (g_.get("galerie") or {}).get("vordach")
        if v: ist["vordach"] = dict(traufe_z=v["z_traufe"], anschluss_z=v["z_anschluss"], ausladung=round(k_["ausladung"] + 0.25, 2))
    elif gal:
        g = gal[0]; wand = g["w_wand"] + 0.05
        ist["galerie"] = dict(schwelle_unten=g["z_boden"], holm_oben=g["z_holm"], ausladung=round(g["w"] - wand, 2), breite=round(g["u1"] - g["u0"], 2), pfosten=len(g["pfosten"]), streben=g.get("streben"))
        if g.get("vordach"): v = g["vordach"]; ist["vordach"] = dict(traufe_z=v["z_traufe"], anschluss_z=v["z_anschluss"], ausladung=round(v["w_traufe"] - wand, 2))
    uh = [u for F in UH.values() if isinstance(F, dict) for u in F.get("uhren", [])]
    if uh: ist["uhr"] = dict(durchmesser=uh[0]["d_aussen"], mitte_z=uh[0]["z"])
    to = [o for F in OE.values() if isinstance(F, dict) for o in F.get("oeffnungen", []) if o.get("gebaut")]
    if to:    # 21.11.2026: gleiches mit gleichem - breite/scheitel/kaempfer = LICHTE Oeffnung (Innenkante), scheitel_aussen = Aussenkante inkl. Gewaende (oeffnungen_aus_kanten 'aussenmass')
        o = max(to, key=lambda o: o.get("breite") or 0); ist["tor"] = dict(breite=o.get("breite"), scheitel=o.get("scheitel"), kaempfer=o.get("kaempfer"), scheitel_aussen=(o.get("aussenmass") or {}).get("scheitel"))
    if any(o.get("durchfahrt") for o in to): ist["tor_durchfahrt"] = {}
    for r in R["bauteile"]:
        if r["bauteil"] == "rundbogenfenster":
            fid_ = next((k for k, F in UH.items() if isinstance(F, dict) and F.get("uhren")), None)       # Seite der Uhr = Stadtseite (Referenz)
            z_ = r["masse"]["sohlbank_z"]; fz = [q for k, F in FE.items() if isinstance(F, dict) and (fid_ is None or k == fid_) for q in F.get("fenster", []) if abs(q["z0"] - z_) < 2.0]
            nb_ = lambda q: q.get("nische") or q          # 21.11.2026 tools/nischen_fenster.py: Nische als eigene Ebene - vorher galt die Fensteroeffnung (0,59 m) als 'Nische'
            if fz:
                ist["rundbogenfenster"] = dict(anzahl=len(fz), sohlbank_z=round(sum(nb_(q)["z0"] for q in fz) / len(fz), 2), nische_breite=round(max(nb_(q)["u1"] - nb_(q)["u0"] for q in fz), 2))
                ist["rundbogenfenster"]["_form"] = form_ist(fz, TOR, fid_)
    # 21.11.2026: Bauteile aus der Wolke (Kettenstufen wolke_rest -> koerper_auto.json, dach_profil_wolke -> dach_profil.json) - vorher nur Stichwort in elemente.json,
    # darum standen Treppenturm/Laterne/Ueberstand immer auf FEHLT, obwohl die Kette sie baut. Hier mit ihren gemessenen Massen.
    KA = lade(os.path.join(A, "koerper_auto.json")) or {}
    rd = [h for h in KA.get("haufen", []) if h.get("form") == "rund" and h.get("kreis") and h.get("urteil", "angenommen") != "verworfen"]
    if rd:
        h = max(rd, key=lambda h: h.get("punkte", 0)); U_ = h.get("umriss") or {}
        if U_.get("gueltig"): ist["treppenturm"] = dict(radius=U_.get("r_schaft", U_["r"]), traufe=U_.get("traufe") or h["kasten"][5], _quelle="foto")   # tools/rund_aus_umriss.py
        else: ist["treppenturm"] = dict(radius=h["kreis"]["r"], traufe=h["kasten"][5], _quelle="wolke")
    DP = lade(os.path.join(A, "dach_profil.json")) or {}; sch = DP.get("scheiben") or []
    if len(sch) >= 4 and DP.get("wand_halb"):
        wh = DP["wand_halb"]; s_ = float(DP.get("schritt", 0.5))
        unten = [s for s in sch if s[0] <= sch[0][0] + 2.0]                 # Traufzone: die untersten 2 m des Dachprofils
        ue = [sorted([-s[1] - wh[0], s[2] - wh[0], -s[3] - wh[1], s[4] - wh[1]])[1:3] for s in unten]   # je Scheibe die zwei mittleren Seiten (robust gegen eine schiefe Seite)
        ist["zeltdach_ueberstand"] = dict(ueberstand=round(max(sum(x) / 2 for x in ue), 2), _quelle="wolke")
        br = [(s[0], (s[2] - s[1] + s[4] - s[3]) / 4) for s in sch]; obere = [b for b in br if b[0] >= (br[0][0] + br[-1][0]) / 2]
        if obere:
            i_h = min(range(len(obere)), key=lambda i: obere[i][1]); hals = obere[i_h]
            kr = next((b for b in obere[i_h + 1:] if b[1] > 1.2 * hals[1]), None)   # Krempe = erste Verbreiterung > 20 % ueber dem schmalsten Hals
            if kr: ist["laterne"] = dict(spitze_z=round(br[-1][0] + s_ / 2, 2), krempe_z=kr[0], _quelle="wolke")
    SF = DP.get("spitze_foto") or {}          # 21.11.2026 tools/spitze_aus_umriss.py (Kettenstufe bauplan_spitze_umriss): Spitze/Krempe aus der Himmelskante der Fotos gehen vor
    if SF.get("gueltig") and SF.get("spitze_z") is not None: ist["laterne"] = dict(spitze_z=SF["spitze_z"], krempe_z=SF.get("krempe_z"), _quelle="foto")
    ug = [e for e in EL if e.get("pfosten_je_seite") is not None and "umgang" in e.get("element", "").lower()]   # 21.11.2026: Umgang aus tools/umgang_aus_fotos.py (Beleg mit gezaehlter Pfostenzahl)
    if ug: ist["umgang"] = dict(pfosten_je_seite=ug[0]["pfosten_je_seite"])
    for k, w in (("laterne", "laterne"), ("treppenturm", "treppenturm"), ("umgang", "umgang"), ("eckquader", "eckquader"), ("zeltdach_ueberstand", "ueberstand")):
        if w in txt: ist.setdefault(k, {})
    for r in R["bauteile"]:                                                     # 21.11.2026 spaet: FORM je Bauteil mit Formnamen (rundbogen/spitzbogen/...), nicht nur Hoehe/Anzahl
        sf = soll_form(r["bauteil"])
        if sf and r["bauteil"] in ist and "_form" not in ist[r["bauteil"]] and r["bauteil"] != "tor": ist[r["bauteil"]]["_form"] = dict(ist=None, grund="Form nicht gemessen")
    erg = []; n_passt = 0
    for r in R["bauteile"]:
        b = r["bauteil"]; t = float(r.get("toleranz_m", 0.3))
        if b not in ist: erg.append(dict(bauteil=b, urteil="FEHLT", soll=r["masse"])); continue
        ab = {}; q_ = ist[b].get("_quelle", "foto")    # 21.11.2026 KERNMETHODE: Masse nur aus der Wolke zaehlen als VORLAEUFIG (Quelle je Bauteil)
        ann = r.get("hand_annahme") or {}              # 21.11.2026: Handwerte, die die Handquelle selbst als ANNAHME fuehrt und die ein Fotobeleg widerlegt - angezeigt, nicht geurteilt
        for k, s in r["masse"].items():
            i = ist[b].get(k)
            if k in ann: ab[k] = dict(soll=s, ist=i, ok=True, hand_annahme=ann[k]); continue
            if i is None: ab[k] = dict(soll=s, ist=None, ok=False); continue
            ok = abs(float(i) - float(s)) <= (t if k not in ("anzahl", "pfosten", "streben", "pfosten_je_seite") else 0)
            ab[k] = dict(soll=s, ist=i, ok=ok)
        sf = soll_form(b); fi_ = ist[b].get("_form")
        if sf and fi_ is not None:          # Formfamilie: gebaute Form aller gezaehlten Umrisse UND Form-Tor an den Einzelfotos (tools/fenster_form_tor.py)
            ab["form"] = dict(soll=sf, ist=fi_.get("ist"), ok=fi_.get("ist") == sf and not fi_.get("tor_falsch") and not fi_.get("unsicher"), grund=fi_.get("grund"))
        u = "PASST" if all(x["ok"] for x in ab.values()) else "FALSCH"; n_passt += u == "PASST"; erg.append(dict(bauteil=b, urteil=u, masse=ab, quelle=q_))
        if ann and u == "PASST": erg[-1]["hinweis"] = "ohne Handannahme(n): " + ", ".join(f"{k} Hand {r['masse'][k]} / Kette {ist[b].get(k)}" for k in ann if k in r["masse"])
    for e in erg:
        z = f"{e['urteil']:6s} {e['bauteil']:20s}" + ("  [nur Wolke - vorlaeufig]" if e.get("quelle") == "wolke" else "")
        if e["urteil"] == "FALSCH": z += "  " + ", ".join(f"{k} {v['ist']} statt {v['soll']}" for k, v in e["masse"].items() if not v["ok"])
        print(z)
    n_wolke = sum(1 for e in erg if e["urteil"] == "PASST" and e.get("quelle") == "wolke")
    print(f"HANDSTAND ERREICHT: {n_passt} von {len(erg)} Bauteilen passen ({100 * n_passt / len(erg):.0f} %), davon {n_passt - n_wolke} aus Fotos, {n_wolke} nur aus der Wolke (vorlaeufig)")
    json.dump(dict(referenz=R["quelle"], passt=n_passt, passt_nur_wolke=n_wolke, gesamt=len(erg), bauteile=erg), open(os.path.join(A, "hand_vergleich.json"), "w"), indent=1, ensure_ascii=False)
    import time, subprocess      # 21.11.2026 (Nutzer: "Loggst du deine ganzen Versuche mit, dass wir das spaeter nochmal nachspielen koennen?"): Verlauf je Lauf mit git-Stand
    try: rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=od).stdout.strip()
    except Exception: rev = "?"
    with open(os.path.join(A, "hand_vergleich_verlauf.jsonl"), "a") as f_:
        f_.write(json.dumps(dict(zeit=time.strftime("%Y-%m-%d %H:%M"), git=rev, passt=n_passt, passt_nur_wolke=n_wolke, gesamt=len(erg), urteile={e["bauteil"]: e["urteil"] for e in erg},
                                 daneben={e["bauteil"]: {k: [v["ist"], v["soll"]] for k, v in e["masse"].items() if not v["ok"]} for e in erg if e["urteil"] == "FALSCH"}), ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__": sys.exit(main())
