#!/usr/bin/env python3
"""verlustbilanz.py - Verlustbilanz eines Kettenlaufs: je Stufe, die eine Menge verarbeitet, "rein / raus / verloren + Grund" (22.11.2026).
Anlass (Nulllauf schwabentor-1122): ein von der Kette gewaehltes Video (hBlkpdGf6LY) ging verloren - der Download war kaputt, video_frames.py
endete mit rc 0 und 0 Bildern, KEINE Zeile im Bericht. Gemessen am selben Lauf: 766 Bilder -> 394 im SfM-Modell -> 305 in der dichten Wolke,
die Gruende standen nur verstreut in Unterlogs (seiten_modelle.json, dicht_bildwahl.json, gesamtkette.log, quarantaene/sammlung.json).

Liest NUR vorhandene Ergebnisdateien der Stufen (kein Rechnen, kein Schreiben ausser --json):
  video_clips      clips.json 'gewaehlt' -> video_frames/<id> mit Bildern (Fehler der Stufe frames_<id> im Bericht = Grund)
  vorpruefen       vorpruefung.json: geprueft -> >= min_inlier (je Quelle)
  sammeln          sammlung.json (im Sammelordner oder von fotos_pruefen nach quarantaene/ verschoben): Kandidaten -> gesammelt, Dubletten je Quelle
  fotos_pruefen    Sammelordner -> SfM-Fotosatz (defekte Bilder in quarantaene/)
  sfm_seiten       Fotosatz -> Bildteile der Seitenerkennung (pipe/sfm/seiten.json, 'fremd' = Grund)
  sfm_teile        Bildteile -> gerechnete Teilmodelle (seiten_modelle.json 'grund')
  sfm_registriert  Bilder der gerechneten Teile -> vom Mapper registriert (ohne Seitenmodelle: pipeline_bericht 'registriert X von Y')
  sfm_vereint      registrierte Bilder -> im Endmodell sparse/0 (nicht vereinte Teile mit Grund aus fotoluecken/meldungen)
  dicht_bildwahl   Endmodell -> Bilder der dichten Wolke (dicht/sparse_dicht/dicht_bildwahl.json weg_*)
  kameras          Ausrichtung -> geschriebene K-Kameras (Gruende je Kamera aus dem Log-Abschnitt fototor_kameras dieses Laufs)
  fototor          gewaehlte Fotos -> beurteilbare Fotos (audit/fototor_vergleich.json)
  fassaden_relief  Waende -> Waende mit Relief ('aus' = Grund), Mono-Relief (rc 4 = keine Fotos ueber der Korrelationsschwelle)
  fenster          erkannte -> gebaute Fenster (fenster_tiefe_tor VERWORFEN = Grund, Ergaenzungen der Nischenstufe mitgezaehlt)
  oeffnungen       erkannte Oeffnungen -> gebaut ('grund')
Benannter Grund = die Stufe hat den Verlust selbst in eine Ergebnisdatei/den Bericht geschrieben. Alles andere ist STILL verloren.
WARNUNG, wenn eine Stufe mehr als RCPARK_VERLUST_MAX (Standard 0,05) ihrer Eingabe ohne benannten Grund verliert (je Stufe: RCPARK_VERLUST_MAX_<STUFE>).
  Begruendung 5 %: der einzige unbenannte Verlust einer gesunden Stufe im Lauf 1122 (Mapper, 590 -> 584 Bilder) lag bei 1 %; der kaputte Clip waren 1 von 12 = 8 %.
HINWEIS, wenn eine Quelle/Stufe > RCPARK_VERLUST_BENANNT_MAX (Standard 0,8) MIT Grund verliert (gewollt? Schwelle pruefen) - z. B. Video 64 -> 1 als 'Dubletten'.
Eintraege aus Dateien, die aelter als der Laufstart sind, tragen stand='frueher' (Stufe lief in diesem Lauf nicht).

  python3 -I tools/verlustbilanz.py <ziel> [--daten DIR] [--seit UNIXZEIT] [--log gesamtkette.log --ab-zeile N] [--json aus.json]
Kette: tools/gesamtkette.py ruft bilanz() + drucken() am Ende jedes Laufs (abschluss) -> Bericht 'verlustbilanz', Tabelle im Log."""
import os, sys, re, json, glob, time, argparse
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BILD = (".jpg", ".jpeg", ".png")


def _j(p):
    try: return json.load(open(p))
    except Exception: return None


def _bilder(d):
    try: return sorted(f for f in os.listdir(d) if f.lower().endswith(BILD))
    except Exception: return []


def _quelle(p):
    """Quelle eines Bildpfads unter rc-park_daten/<objekt>/... -> 'video_frames/<id>', 'netz/commons_geo', ..."""
    r = p.split("/rc-park_daten/")[-1]; r = r.split("/", 1)[-1] if "/" in r else r
    return os.path.dirname(r) or "?"


def _grenze(stufe, umg=None):
    umg = os.environ if umg is None else umg
    try: return float(umg.get("RCPARK_VERLUST_MAX_" + stufe.upper(), umg.get("RCPARK_VERLUST_MAX", "0.05")))
    except ValueError: return 0.05


def log_abschnitt(log, name, ab_zeile=0):
    """Zeilen des LETZTEN Abschnitts '=== <name>  [...]' im Kettenlog ab Zeile ab_zeile (lauf() schreibt je Stufe einen Kopf)."""
    if not log or not os.path.exists(log): return []
    letzter, akt = [], None
    with open(log, errors="replace") as L:
        for i, z in enumerate(L):
            if i < ab_zeile: continue
            if z.startswith("=== "):
                akt = [] if z[4:].split("  [")[0].strip() == name else None
                if akt is not None: letzter = akt
            elif akt is not None: akt.append(z.rstrip("\n"))
    return letzter


def eintrag(stufe, einheit, rein, raus, verloren=(), quelle="", seit=None, je=None, hinweis=""):
    """Eine Zeile der Bilanz. verloren = [(n, grund)] MIT benanntem Grund; ohne_grund = rein - raus - Summe(benannt) (>= 0; ergaenzte Elemente gehen in 'raus')."""
    v = [dict(n=int(n), grund=str(g)[:200]) for n, g in verloren if n]
    e = dict(stufe=stufe, einheit=einheit, rein=int(rein), raus=int(raus), verloren=v, ohne_grund=max(0, int(rein) - int(raus) - sum(x["n"] for x in v)), quelle=quelle)
    if quelle and seit and os.path.exists(quelle): e["stand"] = "dieser Lauf" if os.path.getmtime(quelle) >= seit - 2 else "frueher " + time.strftime("%d.%m. %H:%M", time.localtime(os.path.getmtime(quelle)))
    if je: e["je"] = je
    if int(raus) > int(rein): hinweis = (hinweis + "; " if hinweis else "") + "raus > rein: Eingaben aus verschiedenen Laeufen?"
    if hinweis: e["hinweis"] = hinweis[:300]
    return e


def _schritt_fehler(B, name, n_start=0):
    """Fehlertext der LETZTEN Stufe <name> im Bericht (ueber alle Laeufe: ein Einstieg --ab tore rechnet die Clips nicht neu, ihr Fehler stand im frueheren Lauf); '' = ok/nicht da."""
    for e in reversed((B or {}).get("schritte", [])):
        if e.get("stufe") == name:
            if e.get("ok") is False or e.get("rc") not in (0, None): return f"Stufe {name} rc {e.get('rc')}: " + str(e.get("fehler") or " | ".join(e.get("ende", [])))[:150]
            return ""
    return ""


# ---------------------------------------------------------------- Stufen
def s_video(D, B, n_start, seit, **_):
    cj = os.path.join(D, "clips.json"); C = _j(cj)
    if not C or not C.get("gewaehlt"): return []
    ok, weg, je = [], [], {}
    for c in C["gewaehlt"]:
        n = len(_bilder(os.path.join(D, "video_frames", c["id"]))); je[c["id"]] = n
        (ok if n else weg).append(c["id"])
    benannt = [(1, f"{i}: {_schritt_fehler(B, 'frames_' + i, n_start)}") for i in weg if _schritt_fehler(B, "frames_" + i, n_start)]
    still = [i for i in weg if not _schritt_fehler(B, "frames_" + i, n_start)]
    return [eintrag("video_clips", "Clips", len(C["gewaehlt"]), len(ok), benannt, cj, seit, je=je,
                    hinweis=("ohne Bilder und ohne Fehlerzeile im Bericht: " + ", ".join(still)) if still else "")]


def s_vorpruefen(D, seit, **_):
    vj = os.path.join(D, "vorpruefung.json"); V = _j(vj)
    if not V or not V.get("bilder"): return []
    mi = V.get("min_inlier", 60); tot, hit = Counter(), Counter()
    for p, e in V["bilder"].items(): tot[_quelle(p)] += 1; hit[_quelle(p)] += (e.get("inlier") or 0) >= mi
    je = {q: f"{hit[q]}/{tot[q]}" for q in sorted(tot)}
    return [eintrag("vorpruefen", "Bilder", sum(tot.values()), sum(hit.values()), [(sum(tot.values()) - sum(hit.values()), f"< {mi} Inlier gegen die Referenzfotos")], vj, seit, je=je)]


def s_sammeln(D, seit, **_):
    out = []; FV = os.path.join(D, "fotos")
    sj = next((p for p in (os.path.join(FV, "sammlung.json"), os.path.join(D, "quarantaene", "sammlung.json")) if os.path.exists(p)), None); S = _j(sj) if sj else None
    if S:
        n, dub = len(S.get("bilder", [])), S.get("dubletten", [])
        je_weg = Counter(_quelle(d["weg"]) for d in dub); je_ein = Counter(x.get("quelle", "?") for x in S.get("bilder", []))
        je = {q: f"-{k}" for q, k in je_weg.most_common()}
        out.append(eintrag("sammeln", "Bilder", n + len(dub), n, [(len(dub), "Dublette (32x32-Vorschau, eigene/groessere Aufnahme bleibt)")], sj, seit, je=je))
    q = os.path.join(D, "quarantaene"); defekt = [f for f in _bilder(q)]
    fs = _j(os.path.join(D, "pipe", "fotosatz.json"))
    if fs and (S or defekt):
        n0 = len(S.get("bilder", [])) if S else fs["n"] + len(defekt)
        out.append(eintrag("fotos_pruefen", "Bilder", n0, fs["n"], [(len(defekt), "defekt (tools/fotos_pruefen.py -> quarantaene/)")], os.path.join(D, "pipe", "fotosatz.json"), seit))
    return out


def s_sfm(D, seit, **_):
    P = os.path.join(D, "pipe"); out = []; fs = _j(os.path.join(P, "fotosatz.json")); n_fs = (fs or {}).get("n") or len(_bilder(os.path.join(D, "fotos")))
    sj = os.path.join(P, "sfm", "seiten.json"); S = _j(sj); mj = os.path.join(P, "sfm", "seiten_modelle.json"); M = _j(mj)
    if S and S.get("seiten") is not None and n_fs:
        fremd = len(S.get("fremd") or []); in_t = sum(t.get("bilder", 0) for t in S["seiten"])
        out.append(eintrag("sfm_seiten", "Bilder", n_fs, in_t, [(fremd, "fremd (Seitenerkennung: kein Bezug zum Objekt)")], sj, seit, je={f"teil{i}": t.get("bilder") for i, t in enumerate(S["seiten"][:8])}))
    if M and M.get("teile"):
        T = M["teile"]; ger = [t for t in T if t.get("gerechnet")]; ng = Counter(str(t.get("grund") or "") for t in T if not t.get("gerechnet"))
        out.append(eintrag("sfm_teile", "Bilder", sum(t.get("bilder", 0) for t in T), sum(t.get("bilder", 0) for t in ger),
                           [(sum(t.get("bilder", 0) for t in T if not t.get("gerechnet") and str(t.get("grund") or "") == g), g) for g in ng if g], mj, seit))
        mit = [t for t in ger if t.get("im_modell") is not None]
        out.append(eintrag("sfm_registriert", "Bilder", sum(t.get("bilder", 0) for t in mit), sum(t["im_modell"] for t in mit), [], mj, seit,
                           je={f"teil{t['teil']}": f"{t['im_modell']}/{t.get('bilder')}" for t in mit}))
        ver = set(M.get("vereint") or []); fl = {f.get("teil"): f.get("grund") or f.get("text") for f in M.get("fotoluecken") or []}
        mld = M.get("meldungen") or []
        def grund_teil(t):
            if t in fl: return f"Teil {t}: {fl[t]}"
            m = [z for z in mld if re.search(rf"Teil {t}\b.*NICHT vereint", z)]
            return m[0] if m else ""
        nv = [t for t in mit if t["teil"] not in ver]
        out.append(eintrag("sfm_vereint", "Bilder", sum(t["im_modell"] for t in mit), sum(t["im_modell"] for t in mit if t["teil"] in ver),
                           [(t["im_modell"], grund_teil(t["teil"])) for t in nv if grund_teil(t["teil"])], mj, seit))
    else:
        pb = os.path.join(P, "pipeline_bericht.json"); R = _j(pb) or {}
        for s in R.get("stufen", []):
            m = re.search(r"registriert (\d+) von (\d+)", str(s.get("detail", "")))
            if s.get("name") == "sfm" and m: out.append(eintrag("sfm_registriert", "Bilder", int(m.group(2)), int(m.group(1)), [], pb, seit))
    bw = os.path.join(P, "dicht", "sparse_dicht", "dicht_bildwahl.json"); W = _j(bw)
    if W and "registriert" in W:
        out.append(eintrag("dicht_bildwahl", "Bilder", W["registriert"], W["behalten"], [(v, k[4:].replace("_", " ")) for k, v in W.items() if k.startswith("weg_")], bw, seit))
    return out


def s_kameras(Z, seit, log, log_ab, **_):
    zs = log_abschnitt(log, "fototor_kameras", log_ab); gr = Counter(); ok = 0
    for z in zs:
        m = re.match(r"\s+K-\S+: (.*)$", z)
        if not m: continue
        if re.match(r"f -?\d+ px", m.group(1)): ok += 1
        else: gr[re.sub(r"-?\d+(\.\d+)?", "N", m.group(1).split(":")[0])[:90]] += 1
    if not zs or not (ok or gr): return []
    return [eintrag("kameras", "Kameras", ok + sum(gr.values()), ok, list((n, g) for g, n in gr.items()), log, seit)]


def s_fototor(Z, seit, **_):
    fj = os.path.join(Z, "audit", "fototor_vergleich.json"); F = _j(fj)
    if not F or "gesamt" not in F: return []
    fo = F.get("fotos") if isinstance(F.get("fotos"), dict) else {}
    if not fo: return []
    gr = Counter(str(v.get("grund") or "") for v in fo.values() if v.get("urteil") == "nicht beurteilbar")
    return [eintrag("fototor", "Fotos", len(fo), sum(1 for v in fo.values() if v.get("urteil") != "nicht beurteilbar"),
                    [(n, "nicht beurteilbar: " + g) for g, n in gr.items() if g], fj, seit, hinweis="Gesamturteil: " + str(F["gesamt"].get("urteil")) + " (" + str(F["gesamt"].get("grund") or "") + ")")]


def s_fassaden(Z, seit, **_):
    fj = os.path.join(Z, "audit", "fassaden_kette.json"); F = _j(fj)
    if not F or not F.get("waende"): return []
    W = F["waende"]; aus = Counter(str(w.get("aus")) for w in W if w.get("aus"))
    out = [eintrag("fassaden_relief", "Waende", len(W), sum(1 for w in W if not w.get("aus")), [(n, g) for g, n in aus.items()], fj, seit)]
    mo = [w for w in W if w.get("mono")]
    if mo:
        rc = Counter((w["mono"].get("rc"), bool(w["mono"].get("datei"))) for w in mo)
        out.append(eintrag("fassaden_mono", "Waende", len(mo), sum(1 for w in mo if w["mono"].get("datei")),
                           [(sum(1 for w in mo if not w["mono"].get("datei") and w["mono"].get("rc") == 4), "rc 4: kein Foto ueber der Korrelationsschwelle")], fj, seit,
                           je={w["name"]: w["mono"].get("rc") for w in mo}))
    return out


def _zahl_fenster(J):
    return sum(len(v.get("fenster", [])) for v in (J or {}).values() if isinstance(v, dict))


def s_fenster(Z, seit, **_):
    A = os.path.join(Z, "audit"); out = []
    roh, bau, tt = (_j(os.path.join(A, n)) for n in ("fenster_auto_roh.json", "fenster_bau.json", "fenster_tiefe_tor.json"))
    if roh is not None and bau is not None:
        nr, nb = _zahl_fenster(roh), _zahl_fenster(bau)
        vw = sum(1 for L in (tt or {}).values() if isinstance(L, list) for x in L if str(x.get("urteil", "")).startswith("VERWORFEN"))
        erg = max(0, nb - (nr - vw))                                          # Nischen-/Rasterstufe ergaenzt Fenster: zaehlen nicht als Gewinn gegen Verluste
        e = eintrag("fenster", "Fenster", nr + erg, nb, [(vw, "fenster_tiefe_tor: VERWORFEN (etwas steht davor / keine Nische)")], os.path.join(A, "fenster_bau.json"), seit)
        if erg: e["ergaenzt"] = erg
        out.append(e)
    O = _j(os.path.join(A, "oeffnungen_auto.json"))
    if O:
        L = [o for v in O.values() if isinstance(v, dict) for o in v.get("oeffnungen", [])]
        if L:
            gr = Counter(str(o.get("grund") or "").split(" - ")[0][:80] for o in L if not o.get("gebaut") and o.get("grund"))
            out.append(eintrag("oeffnungen", "Oeffnungen", len(L), sum(1 for o in L if o.get("gebaut")), [(n, g) for g, n in gr.items()], os.path.join(A, "oeffnungen_auto.json"), seit))
    return out


STUFEN = [s_video, s_vorpruefen, s_sammeln, s_sfm, s_kameras, s_fototor, s_fassaden, s_fenster]


def bilanz(D, Z, B=None, n_start=0, seit=None, log=None, log_ab=0, umg=None):
    """-> dict(stufen=[eintrag...], warnungen=[...], hinweise=[...]). Jede Stufe einzeln abgesichert: eine unlesbare Datei = Zeile 'fehler', nie Abbruch."""
    st, fe = [], []
    for f in STUFEN:
        try: st += f(D=D, Z=Z, B=B, n_start=n_start, seit=seit, log=log, log_ab=log_ab)
        except Exception as e: fe.append(f"{f.__name__}: {type(e).__name__} {e}"[:200])
    umg = os.environ if umg is None else umg; w, h = [], []
    try: bmax = float(umg.get("RCPARK_VERLUST_BENANNT_MAX", "0.8"))
    except ValueError: bmax = 0.8
    for e in st:
        g = _grenze(e["stufe"], umg); e["grenze"] = g
        if e["rein"] and e["ohne_grund"] and e["ohne_grund"] / e["rein"] > g:
            w.append(f"{e['stufe']}: {e['ohne_grund']} von {e['rein']} {e['einheit']} ({100 * e['ohne_grund'] / e['rein']:.0f} %) OHNE benannten Grund verloren (Grenze {100 * g:.0f} %)"
                     + (f" - {e['hinweis']}" if e.get("hinweis") else "") + (f" [{e['stand']}]" if e.get("stand", "dieser Lauf") != "dieser Lauf" else ""))
        for v in e["verloren"]:
            if e["rein"] and v["n"] / e["rein"] > bmax: h.append(f"{e['stufe']}: {v['n']} von {e['rein']} {e['einheit']} weg als '{v['grund'][:80]}' - gewollt? Schwelle pruefen")
    return dict(zeit=time.strftime("%Y-%m-%d %H:%M:%S"), stufen=st, warnungen=w, hinweise=h, fehler=fe)


def tabelle(V):
    """Textzeilen der Verlustbilanz (schmal: eine Zeile je Stufe, Gruende eingerueckt darunter)."""
    z = ["VERLUSTBILANZ (rein -> raus; verloren mit Grund / OHNE Grund):"]
    for e in V.get("stufen", []):
        z.append(f"  {e['stufe']:16s} {e['rein']:6d} -> {e['raus']:6d} {e['einheit']:10s} ohne Grund {e['ohne_grund']:4d}" + (f"  (+{e['ergaenzt']} ergaenzt)" if e.get("ergaenzt") else "")
                 + (f"  [{e['stand']}]" if e.get("stand", "dieser Lauf") != "dieser Lauf" else ""))
        for v in e["verloren"]: z.append(f"      - {v['n']:5d}  {v['grund'][:150]}")
        if e.get("je"): z.append("      je: " + ", ".join(f"{k} {v}" for k, v in list(e["je"].items())[:14])[:220])
        if e.get("hinweis"): z.append("      HINWEIS: " + e["hinweis"][:200])
    for f in V.get("fehler", []): z.append("  NICHT LESBAR: " + f)
    for h in V.get("hinweise", []): z.append("HINWEIS VERLUST: " + h)
    for w in V.get("warnungen", []): z.append("WARNUNG VERLUST: " + w)
    if not V.get("warnungen"): z.append("Verlustbilanz: keine Stufe verliert mehr als ihre Grenze ohne benannten Grund")
    return z


def drucken(V, log=None):
    t = tabelle(V); print("\n".join(t), flush=True)
    if log:
        try:
            with open(log, "a") as L: L.write("\n=== verlustbilanz  [" + time.strftime("%Y-%m-%d %H:%M:%S") + "]\n" + "\n".join(t) + "\n")
        except OSError as e: print("Verlustbilanz nicht ins Log geschrieben:", e, flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("ziel"); ap.add_argument("--daten", default=""); ap.add_argument("--seit", type=float, default=None)
    ap.add_argument("--log", default=""); ap.add_argument("--ab-zeile", type=int, default=0); ap.add_argument("--json", default="")
    a = ap.parse_args(argv); D = a.daten or os.path.join("/media/oem/scan/rc-park_daten", a.ziel); Z = os.path.join(ROOT, "modelle", a.ziel)
    B = _j(os.path.join(D, "gesamtkette_bericht.json")); n0 = 0
    if B:
        st = [i for i, e in enumerate(B.get("schritte", [])) if e.get("stufe") == "LAUF_START"]; n0 = st[-1] if st else 0
    V = bilanz(D, Z, B=B, n_start=n0, seit=a.seit, log=a.log or os.path.join(D, "gesamtkette.log"), log_ab=a.ab_zeile)
    print("\n".join(tabelle(V)))
    if a.json: json.dump(V, open(a.json, "w"), indent=1, ensure_ascii=False)
    return 3 if V["warnungen"] else 0


if __name__ == "__main__":
    sys.exit(main())
