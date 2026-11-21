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


def main():
    obj = os.path.abspath(sys.argv[1]); od = os.path.dirname(obj); A = os.path.join(od, "audit"); R = lade(os.path.join(od, "referenz_hand.json"))
    if not R: print("keine referenz_hand.json"); return 3
    VB = lade(os.path.join(A, "vorbauten_auto.json")) or {}; UH = lade(os.path.join(A, "uhren_auto.json")) or {}; OE = lade(os.path.join(A, "oeffnungen_auto.json")) or {}
    FE = lade(os.path.join(A, "fenster_auto.json")) or {}; EL = lade(os.path.join(od, "elemente.json")) or []; txt = " ".join(e.get("element", "") for e in EL).lower()
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
    if to: o = max(to, key=lambda o: o.get("breite") or 0); ist["tor"] = dict(breite=o.get("breite"), scheitel=o.get("scheitel"), kaempfer=o.get("kaempfer"))
    if any(o.get("durchfahrt") for o in to): ist["tor_durchfahrt"] = {}
    for r in R["bauteile"]:
        if r["bauteil"] == "rundbogenfenster":
            fid_ = next((k for k, F in UH.items() if isinstance(F, dict) and F.get("uhren")), None)       # Seite der Uhr = Stadtseite (Referenz)
            z_ = r["masse"]["sohlbank_z"]; fz = [q for k, F in FE.items() if isinstance(F, dict) and (fid_ is None or k == fid_) for q in F.get("fenster", []) if abs(q["z0"] - z_) < 2.0]
            if fz: ist["rundbogenfenster"] = dict(anzahl=len(fz), sohlbank_z=round(sum(q["z0"] for q in fz) / len(fz), 2), nische_breite=round(max(q["u1"] - q["u0"] for q in fz), 2))
    for k, w in (("laterne", "laterne"), ("treppenturm", "treppenturm"), ("umgang", "umgang"), ("eckquader", "eckquader"), ("zeltdach_ueberstand", "ueberstand")):
        if w in txt: ist.setdefault(k, {})
    erg = []; n_passt = 0
    for r in R["bauteile"]:
        b = r["bauteil"]; t = float(r.get("toleranz_m", 0.3))
        if b not in ist: erg.append(dict(bauteil=b, urteil="FEHLT", soll=r["masse"])); continue
        ab = {}
        for k, s in r["masse"].items():
            i = ist[b].get(k)
            if i is None: ab[k] = dict(soll=s, ist=None, ok=False); continue
            ok = abs(float(i) - float(s)) <= (t if k not in ("anzahl", "pfosten", "streben", "pfosten_je_seite") else 0)
            ab[k] = dict(soll=s, ist=i, ok=ok)
        u = "PASST" if all(x["ok"] for x in ab.values()) else "FALSCH"; n_passt += u == "PASST"; erg.append(dict(bauteil=b, urteil=u, masse=ab))
    for e in erg:
        z = f"{e['urteil']:6s} {e['bauteil']:20s}"
        if e["urteil"] == "FALSCH": z += "  " + ", ".join(f"{k} {v['ist']} statt {v['soll']}" for k, v in e["masse"].items() if not v["ok"])
        print(z)
    print(f"HANDSTAND ERREICHT: {n_passt} von {len(erg)} Bauteilen passen ({100 * n_passt / len(erg):.0f} %)")
    json.dump(dict(referenz=R["quelle"], passt=n_passt, gesamt=len(erg), bauteile=erg), open(os.path.join(A, "hand_vergleich.json"), "w"), indent=1, ensure_ascii=False)
    import time, subprocess      # 21.11.2026 (Nutzer: "Loggst du deine ganzen Versuche mit, dass wir das spaeter nochmal nachspielen koennen?"): Verlauf je Lauf mit git-Stand
    try: rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=od).stdout.strip()
    except Exception: rev = "?"
    with open(os.path.join(A, "hand_vergleich_verlauf.jsonl"), "a") as f_:
        f_.write(json.dumps(dict(zeit=time.strftime("%Y-%m-%d %H:%M"), git=rev, passt=n_passt, gesamt=len(erg), urteile={e["bauteil"]: e["urteil"] for e in erg},
                                 daneben={e["bauteil"]: {k: [v["ist"], v["soll"]] for k, v in e["masse"].items() if not v["ok"]} for e in erg if e["urteil"] == "FALSCH"}), ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__": sys.exit(main())
