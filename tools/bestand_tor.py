#!/usr/bin/env python3
"""bestand_tor.py - BESTAND-TOR: nie schlechter als der beste bisherige Kettenstand (24.11.2026, HART; Nutzer: "wir hatten mal so einen geilen Stand und du machst
KI-Muell" / "sichere das hart ab!").
Verwandt: tools/foto_tor_bezug.py (ganzes Modell je Foto), tools/vorbau_fototor.py (Foto-F1 je Vorbau), tools/teil_fotoform.py (Messung), tools/konvergenz.py (Verlauf).
Vorlaeufer: keiner je Bauteilzone - der Rueckfall Galerie -> Treppenkloetze (Kette 1122z/zb/zc, Hoehenfeld als Gestalt) lief an allen Toren vorbei.

ZONEN kommen aus der Erkennung, nicht von Hand: audit/neben_details.json (tools/neben_details.py; z. B. vorbau_f00, uhr_f00, fenster_f00_2, oeffnung_bogen_f01,
spitze) - Kasten im Fassadenrahmen + Fotoansichten. Kasten und Fotosatz werden beim Anlegen im Bestand EINGEFROREN; Bestand und neuer Stand werden mit demselben
Kasten aus ihrem STL ausgeschnitten (konvergenz.teile_schreiben) und an denselben Fotos gemessen.
MESSUNG (GPU, tools/teil_fotoform.py): Foto-F1 je Zone und Foto (Praezision/Recall der Modellkanten gegen die Fotokanten im sichtbaren Teilbereich).
URTEIL je Zone (gepaart ueber die gemeinsamen Fotos): d_i = F1_neu_i - F1_best_i; Rauschen = Standardfehler sd(d)/sqrt(n) (Nullkontrolle: derselbe Stand gibt
d = 0); RUECKSCHRITT, wenn mean(d) < -k x Standardfehler UND mean(d) < -Nullrauschen (Nullkontrolle = k x Streuung der Bestands-F1 ueber die Fotos / sqrt(n), d. h. wie genau die Zonen-F1 ueberhaupt bekannt ist; bestand.json "nullrauschen" je Zone ueberschreibt), n >= min_fotos.
Keine feste F1-Schwelle. FORTSCHREIBEN (bestand.json + Bestand-STL/Teile auf der Datenplatte) nur, wenn KEINE Zone schlechter ist (mean(d) >= 0 in allen
beurteilten Zonen) - neue Zonen kommen dann dazu.
Ablage: modelle/<objekt>/bestand/bestand.json (klein, ins Repo); STL und Zonen-STLs: /media/oem/rcdaten/rc-park_bestand/<objekt>/ (gross, nie ins Repo).
Bericht je Lauf: modelle/<objekt>/audit/bestand_tor.json ('rueckschritt': Liste "zone F1 alt->neu") - tools/merge_sperre.sh liest ihn.

Aufruf (GPU, venv-seg):
  bestand_tor.py modelle/<objekt>/objekt.json                      # Tor: aktuelles STL gegen den Bestand
  bestand_tor.py modelle/<objekt>/objekt.json --anlegen --stl S    # Bestand aus einem bekannten guten STL anlegen (z. B. 07:50-Kopie), Zonen aus neben_details
  bestand_tor.py ... --messung M.json                              # Messung aus Datei (teil_fotoform-Format) statt GPU - Tests
EINGANGS-TOR: Kantenpunkte je Ebene / Frontpunkte je Vorbau gegen den Bestwert (bestand.json 'eingang', Maximum), Abfall unter die Haelfte = Rueckschritt
"EINGANG <zone>:<groesse> alt->neu" (die Zonen-F1 kann ein Ersatzbau verdecken, die Belegdichte nicht).
rc: 0 = kein Rueckschritt (ggf. fortgeschrieben), 2 = kein Urteil (kein Bestand -> angelegt, oder < min_fotos), 5 = BESTAND RUECKSCHRITT, 1 = Absturz.
"""
import sys, os, json, argparse, hashlib, shutil, tempfile, time
import numpy as np

HIER = os.path.dirname(os.path.abspath(__file__)); R0 = os.path.dirname(HIER); sys.path.insert(0, HIER)
DATEN_WURZEL = os.environ.get("RCPARK_BESTAND_DATEN", "/media/oem/rcdaten/rc-park_bestand")
RC_RUECKSCHRITT = 5


def sha(p, n=16):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()[:n]


def f1_von(e):
    """teil_fotoform-Eintrag je Teil+Foto -> F1 (None = nicht beurteilbar)."""
    if not isinstance(e, dict) or "praez" not in e or "recall" not in e: return None
    p, r = float(e["praez"]), float(e["recall"]); return 2 * p * r / (p + r) if p + r > 0 else 0.0


def zonen_f1(messung, zonen=None):
    """teil_fotoform-Bericht {'teile': {zone: {foto: {...}}}} -> {zone: {foto: f1}} (ohne '_gesamt' und nicht beurteilbare Fotos)."""
    out = {}
    for z, je in (messung.get("teile") or {}).items():
        if zonen is not None and z not in zonen: continue
        v = {f: f1_von(e) for f, e in je.items() if not f.startswith("_")}
        v = {f: round(x, 4) for f, x in v.items() if x is not None}
        if v: out[z] = v
    return out


def urteil(bestand, neu, k=2.0, min_fotos=3):
    """REINE Urteilslogik (testbar ohne GPU). bestand = {'zonen': {zone: {'f1': {foto: f1}, 'nullrauschen': x}}}, neu = {zone: {foto: f1}}.
    -> dict(zonen={zone: dict(urteil, alt, neu, d, se, n)}, rueckschritt=[...], alle_mindestens=bool)."""
    erg = {}; rs = []; alle = True
    for z, B in (bestand.get("zonen") or {}).items():
        alt = B.get("f1") or {}; nv = neu.get(z) or {}; ff = sorted(set(alt) & set(nv))
        if len(ff) < min_fotos:
            erg[z] = dict(urteil="kein Urteil", grund=f"{len(ff)} gemeinsame Fotos < {min_fotos}" + (" (Zone fehlt im neuen Modell)" if not nv else ""), n=len(ff))
            if not nv: alle = False                                       # verschwundene Zone: nie fortschreiben (sie koennte das Problem sein)
            continue
        d = np.array([nv[f] - alt[f] for f in ff]); m = float(d.mean()); se = float(d.std(ddof=1) / np.sqrt(len(d))) if len(d) > 1 else 0.0
        # Nullkontrolle: wie genau ist die Zonen-F1 des Bestands selbst bekannt? (Streuung ueber die Fotos / sqrt(n)); ueberschreibbar per bestand.json 'nullrauschen'
        av = np.array([alt[f] for f in ff]); nr = float(B["nullrauschen"]) if B.get("nullrauschen") is not None else float(av.std(ddof=1) / np.sqrt(len(av))) * k; a_m = float(np.mean([alt[f] for f in ff])); n_m = float(np.mean([nv[f] for f in ff]))
        schlechter = m < -k * se - 1e-9 and m < -nr
        u = "RUECKSCHRITT" if schlechter else ("besser" if m > k * se + 1e-9 and m > nr else "gleich")
        erg[z] = dict(urteil=u, alt=round(a_m, 4), neu=round(n_m, 4), d=round(m, 4), se=round(se, 4), schwelle=round(-max(k * se, nr), 4), n=len(ff))
        if schlechter: rs.append(f"{z} F1 {a_m:.3f}->{n_m:.3f}")
        if m < 0: alle = False
    for z in neu:
        if z not in (bestand.get("zonen") or {}): erg[z] = dict(urteil="neu", neu=round(float(np.mean(list(neu[z].values()))), 4), n=len(neu[z]))
    return dict(zonen=erg, rueckschritt=rs, alle_mindestens=alle and not rs)


def zonen_einfrieren(od, daten, n=8):
    """ZONEN AUS DER ERKENNUNG: audit/neben_details.json (tools/neben_details.py: je erkanntem Bauteil - Vorbau, Uhr, Fenster, Bogen, Rundkoerper - Kasten im
    Fassadenrahmen bzw. Achse/Radius, dazu die Fotoansichten). -> {zone: dict(geo, fotos)}; geo im Format von konvergenz.bauteile_einfrieren, Fotos = Ansichten
    mit Messkamera (messprotokoll/K-<foto>.json), bis n. Einmal eingefroren (im Bestand gespeichert), danach immer dieselbe Zone + derselbe Fotosatz."""
    import neben_details as ND
    ndp = os.path.join(od, "audit", "neben_details.json")
    if not os.path.exists(ndp): return {}
    rahmen = ND.fassaden_rahmen(os.path.join(od, "audit"), daten); out = {}
    fj = os.path.join(daten or "", "fassade", "fassaden.json"); FA = json.load(open(fj))["fassaden"] if daten and os.path.exists(fj) else []
    FF = {F.get("id", f"f{i:02d}"): [f for f, _ in sorted((F.get("fotos") or {}).items(), key=lambda kv: -kv[1].get("zellen", 0))] for i, F in enumerate(FA)}
    FALLE = [f for f, _ in sorted({f: v.get("zellen", 0) for F in FA for f, v in (F.get("fotos") or {}).items()}.items(), key=lambda kv: -kv[1])]
    for b in json.load(open(ndp)).get("bauteile") or []:
        nm = b.get("name")
        if not nm: continue
        if b.get("art") == "rund": geo = dict(art="rund", achse=b["achse"], r=b["r"], z0=b["z"][0], z1=b["z"][1])
        else:
            fr = rahmen.get(b.get("fassade"))
            if not fr: continue
            geo = dict(art="fassade", fassade=b["fassade"], o=list(map(float, fr["o"])), d=list(map(float, fr["d"])), n=list(map(float, fr["n"])), u0=b["u"][0], u1=b["u"][1],
                       z0=b["z"][0], z1=b["z"][1], w0=b.get("w", [-0.3, 0.3])[0], w1=b.get("w", [-0.3, 0.3])[1])
        ff = []
        for a_ in b.get("ansichten") or []:
            f_ = (a_ or {}).get("foto")
            if f_ and f_ not in ff and os.path.exists(os.path.join(od, "messprotokoll", "K-" + f_ + ".json")): ff.append(f_)
        # Ansichten allein sind 1-2 Fotos (zu wenig fuer ein gepaartes Urteil): auffuellen mit den Fotos derselben Fassade (fassaden.json, meiste Zellen zuerst)
        for f_ in FF.get(b.get("fassade")) or FALLE:
            if len(ff) >= n: break
            if f_ not in ff and os.path.exists(os.path.join(od, "messprotokoll", "K-" + f_ + ".json")): ff.append(f_)
        out[nm] = dict(geo=geo, fotos=ff[:n])
    return out


def teile_ausschneiden(stl, obj, zonen, td):
    """Zonen-STLs aus dem Modell-STL ausschneiden (gleiche eingefrorene Kaesten fuer Bestand und neuen Stand; konvergenz.teile_schreiben)."""
    import konvergenz as KV
    os.makedirs(td, exist_ok=True); return KV.teile_schreiben(stl, obj, {z: dict(geo=e["geo"]) for z, e in zonen.items()}, td)


def messen(obj_pfad, td, stl, fotos_z, bereich_von=None):
    """teil_fotoform je Fotosatz (Zonen mit gleichem Satz zusammen) -> {zone: {foto: f1}}."""
    import teil_fotoform as TF
    gruppen = {}
    for z, ff in fotos_z.items(): gruppen.setdefault(tuple(ff), []).append(z)
    out = {}
    for ff, zz in gruppen.items():
        if not ff: continue
        arg = [obj_pfad, "--teile_dir", td, "--nur", ",".join(zz), "--fotos", ",".join(ff), "--stl", stl] + (["--bereich_von", bereich_von] if bereich_von else [])
        out.update(zonen_f1(TF.main(arg), set(zz)))
    return out


def bestand_lesen(p):
    try: return json.load(open(p))
    except Exception: return None


def bestand_schreiben(p, alt, neu, fotos_z, stl, td, objekt, quelle, geos=None):
    """Bestand fortschreiben: Zonenwerte, Fotosatz, STL + Zonen-STLs auf die Datenplatte (Zeitstempel-Ordner, alte bleiben)."""
    z_ = time.strftime("%Y-%m-%d_%H%M"); dd = os.path.join(DATEN_WURZEL, objekt, z_)
    try:
        os.makedirs(dd, exist_ok=True); shutil.copy2(stl, os.path.join(dd, os.path.basename(stl)))
        if td and os.path.isdir(td): shutil.copytree(td, os.path.join(dd, "zonen"), dirs_exist_ok=True)
        ablage = dd
    except OSError as e: ablage = f"nicht abgelegt: {e}"
    B = dict(alt or {}); B.setdefault("zonen", {}); B["verlauf"] = (B.get("verlauf") or [])[-20:]
    for z, v in neu.items():
        e = dict(B["zonen"].get(z) or {}); e.update(f1=v, fotos=fotos_z.get(z) or sorted(v), seit=z_)
        if (geos or {}).get(z): e["geo"] = geos[z]
        B["zonen"][z] = e
    B.update(objekt=objekt, stl_sha=sha(stl), stl_ablage=ablage, zeit=z_, quelle=quelle); B["verlauf"].append(dict(zeit=z_, stl_sha=B["stl_sha"], quelle=quelle))
    os.makedirs(os.path.dirname(p), exist_ok=True); json.dump(B, open(p, "w"), indent=1, ensure_ascii=False)
    return B


def eingang_lesen(od, ebenen_json):
    """EINGANGS-TOR (24.11.2026, P3 PLAN_HANDMODELL_IN_KETTE): Belegdichte je Bauteilzone, bevor gebaut wird - Kantenpunkte je Ebene (ebenen.json 'punkte')
    und Frontpunkte je Vorbau (audit/ebenen_masse.json 'punkte_front'). Rueckfall 1122: f00_vb0 punkte_front 40 902 (1120) -> 11 573 (06:18) -> 2430 (abends)."""
    out = {}
    try:
        for e in json.load(open(ebenen_json)).get("ebenen") or []:
            if e.get("punkte") is not None: out[f"{e['id']}:kantenpunkte"] = int(e["punkte"])
    except Exception: pass
    try:
        for k, v in json.load(open(os.path.join(od, "audit", "ebenen_masse.json"))).items():
            if isinstance(v, dict) and v.get("punkte_front") is not None: out[f"{k}:punkte_front"] = int(v["punkte_front"])
    except Exception: pass
    return out


def eingang_urteil(best, neu, anteil=0.5):
    """Abfall unter 'anteil' x Bestwert (Nutzervorgabe 'Abfall > Haelfte') = rot. -> Liste 'EINGANG <zone>:<groesse> alt->neu'."""
    return [f"EINGANG {k} {int(best[k])}->{int(v)}" for k, v in sorted(neu.items()) if best.get(k) and v < anteil * float(best[k])]


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--stl"); ap.add_argument("--bestand"); ap.add_argument("--aus")
    ap.add_argument("--anlegen", action="store_true", help="Bestand aus --stl anlegen/ueberschreiben (ohne Vergleich) - nur fuer einen nachweislich guten Stand")
    ap.add_argument("--messung", help="teil_fotoform-Bericht des neuen Stands (statt GPU-Messung; Tests)"); ap.add_argument("--teile_dir")
    ap.add_argument("--daten", help="Datenordner des Objekts (Fassadenrahmen; Standard /media/oem/scan/rc-park_daten/<objekt>)"); ap.add_argument("--fotos", type=int, default=8)
    ap.add_argument("--k", type=float, default=2.0, help="Rauschfaktor (Standardfehler der gepaarten Differenz)"); ap.add_argument("--min_fotos", type=int, default=3)
    ap.add_argument("--ebenen", help="ebenen.json fuer das Eingangs-Tor (Standard <daten>/ebenen/ebenen.json)")
    a = ap.parse_args(argv)
    op = os.path.abspath(a.objekt); od = os.path.dirname(op); objekt = os.path.basename(od); obj = json.load(open(op))
    stl = a.stl or os.path.join(R0, obj.get("stl") or f"modelle/stl/{objekt}_1-87.stl")
    bp = a.bestand or os.path.join(od, "bestand", "bestand.json"); aus = a.aus or os.path.join(od, "audit", "bestand_tor.json")
    a.daten = a.daten or os.path.join("/media/oem/scan/rc-park_daten", objekt)
    B = bestand_lesen(bp)
    EIN = eingang_lesen(od, a.ebenen or os.path.join(a.daten, "ebenen", "ebenen.json"))
    ein_rs = eingang_urteil((B or {}).get("eingang") or {}, EIN)
    td = a.teile_dir
    geos = {}
    if a.messung:
        neu = zonen_f1(json.load(open(a.messung))); fotos_z = {z: sorted(v) for z, v in neu.items()}
    else:
        Z_ = zonen_einfrieren(od, a.daten, a.fotos)                                   # Erkennung dieses Laufs
        for z, e in ((B or {}).get("zonen") or {}).items():                           # eingefrorene Zonen des Bestands haben Vorrang (gleicher Kasten, gleicher Fotosatz)
            if not a.anlegen and e.get("geo") and e.get("fotos"): Z_[z] = dict(geo=e["geo"], fotos=e["fotos"])
        if not td: td = tempfile.mkdtemp(prefix="bestand_zonen_", dir=os.environ.get("TMPDIR") or None)
        nt = teile_ausschneiden(stl, obj, Z_, td)
        print(f"Zonen aus der Erkennung: {len(Z_)}, im Modell ausgeschnitten {nt}")
        fotos_z = {z: e["fotos"] for z, e in Z_.items()}; geos = {z: e["geo"] for z, e in Z_.items()}
        neu = messen(op, td, stl, fotos_z)
    if a.anlegen or not B:
        B2 = bestand_schreiben(bp, None if a.anlegen else B, neu, fotos_z, stl, td, objekt, "angelegt" + (f" aus {a.stl}" if a.stl else ""), geos)
        bericht = dict(zeit=time.strftime("%Y-%m-%d %H:%M:%S"), stl=stl, stl_sha=sha(stl), urteil="angelegt", rueckschritt=[], zonen={z: dict(urteil="neu", n=len(v)) for z, v in neu.items()})
        B2["eingang"] = {k: max(v, int((B2.get("eingang") or {}).get(k) or 0)) for k, v in EIN.items()}; json.dump(B2, open(bp, "w"), indent=1, ensure_ascii=False)
        json.dump(bericht, open(aus, "w"), indent=1, ensure_ascii=False)
        print(f"BESTAND angelegt: {len(neu)} Zonen -> {bp}" + ("" if a.anlegen else " (kein Bestand vorhanden - KEIN Urteil in diesem Lauf)")); return 0 if a.anlegen else 2
    U = urteil(B, neu, k=a.k, min_fotos=a.min_fotos)
    U["rueckschritt"] = list(U["rueckschritt"]) + ein_rs; U["eingang"] = EIN; U["alle_mindestens"] = U["alle_mindestens"] and not ein_rs
    bericht = dict(zeit=time.strftime("%Y-%m-%d %H:%M:%S"), stl=stl, stl_sha=sha(stl), bestand_sha=B.get("stl_sha"), bestand_zeit=B.get("zeit"), k=a.k, **U)
    for z, e in sorted(U["zonen"].items()):
        print(f"  {z}: {e['urteil']}" + (f"  F1 {e['alt']:.3f} -> {e['neu']:.3f} (d {e['d']:+.3f}, Schwelle {e['schwelle']:+.3f}, {e['n']} Fotos)" if "d" in e else f"  {e.get('grund', '')}"))
    for r in U["rueckschritt"]: print("BESTAND RUECKSCHRITT: " + r, flush=True)
    beurteilt = [e for e in U["zonen"].values() if "d" in e]
    if not U["rueckschritt"] and U["alle_mindestens"] and beurteilt:
        bestand_schreiben(bp, B, neu, fotos_z, stl, td, objekt, "fortgeschrieben (alle Zonen >= Bestand)", geos); bericht["fortgeschrieben"] = True
        print("BESTAND fortgeschrieben (alle Zonen mindestens so gut)")
    B_ = bestand_lesen(bp) or {}; B_["eingang"] = {k: max(int(v), int((B_.get("eingang") or {}).get(k) or 0)) for k, v in {**(B_.get("eingang") or {}), **EIN}.items()}
    json.dump(B_, open(bp, "w"), indent=1, ensure_ascii=False)                       # Eingangs-Bestwerte = Maximum (kann einen Rueckfall nie verdecken)
    json.dump(bericht, open(aus, "w"), indent=1, ensure_ascii=False); print("->", aus)
    if U["rueckschritt"]: return RC_RUECKSCHRITT
    return 0 if beurteilt else 2


if __name__ == "__main__":
    try: sys.exit(main())
    except SystemExit: raise
    except Exception as e:
        import traceback; traceback.print_exc(); sys.exit(1)
