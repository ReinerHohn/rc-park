#!/usr/bin/env python3
"""foto_auftrag_lage.py - FOTOAUFTRAG fuer eine SONDERSTELLE MIT LAGEDATEI (Bruecke/Steg, Anbau ...): Fernfotos, die HAUPTBAU UND STELLE zugleich zeigen, plus
gezielte Nahstandpunkte fuer die duennen/nicht belegten Teile der Stelle aus tools/abdeckung_meldung.py (27.11.2026, Schwabentorsteg).

WARUM: Die Lage des Stegs stammt aus einem eingepassten Handy-Teilmodell; das Hauptnetz hat am Steg nur 34 Punkte, Hauptnetzkamera vf_244 und Laser (DOM1-Dach,
Kamerahoehe ueber DGM1) widersprechen sich um ~1 m in der Hoehe (BRUECKE-LAGE.json 'widerspruch'). Fotos, die Turm (gut verankert) UND Steg zeigen, verbinden
beide im selben Buendel; erhoehte Standpunkte (Hang) zeigen zusaetzlich das Stegdach, das bisher 0 Fotos hat.

AUS DEN DATEN (nichts fest eingetragen): Lagedatei (abdeckung_meldung.lage_lesen: Mitte, Achse, Laenge, Breite, z), Hauptbau = objekt.json rahmen_wand + Zonenliste
  wand_oben_m, Sicht = DOM1 + DGM1 + LoD2 (foto_auftrag_skizze.Sicht), Bildwinkel = abdeckung_meldung.json bildwinkel_grad (eigene Fotos), Luecken je Teil =
  abdeckung_meldung.json zonen[gruppe == Stelle] (status, zellen_luecke).
FERN (n <= --n_fern): Raster FERN_RASTER_M um die Mitte Hauptbau/Stelle, D_MIN..D_MAX m; Ort ausserhalb jedes LoD2-Grundrisses mit DGM1; Hauptbau (Wandmitte
  zum Standort, Wandband >= MIN_HAUPT_BAND_M unter der Traufe sichtbar) UND >= MIN_STELLE_SICHT von 5 Stellenpunkten (Seite zum Standort, halbe Hoehe) ueber Haeuser+Gelaende sichtbar
  (Baeume nur Hinweis); Hauptbau-Ecken + Stellen-Enden passen in BILD_ANTEIL x kurzen Bildwinkel (Hochformat-Breite). Auswahl gierig nach Punktzahl
  (sichtbare Stellenpunkte, Dach von oben sichtbar, kein Baum) mit >= MIN_AZ_ABSTAND Grad Azimutabstand um die Stellenmitte.
NAH je Teil mit Status != belegt: Unterseite -> unter/neben der Stelle (Strasse) an den Lueckenzellen, Blick hoch; Deck innen -> auf der Stelle an den Luecken,
  Blick entlang der Achse beide Richtungen; Ende/Seite -> Faecher +-MAX_SCHRITT um die Normale vor der Lueckenmitte; Dach -> nur ueber Fernstandpunkte mit Dachsicht.
AUFRUF: tools/py seg tools/foto_auftrag_lage.py --objekt modelle/<obj>/objekt.json --zonen modelle/<obj>/abdeckung_zonen.json --meldung <aus>/abdeckung_meldung.json
          --stelle Bruecke [--n_fern 5] --aus modelle/<obj>/fotoauftrag_<stelle>
  -> <aus>/foto_auftrag_<stelle>.{json,md,jpg} (Karte, Luftbild DOP20 wenn lokal da, Norden oben). Nur CPU, ~1 min.
TEST: tools/test_foto_auftrag_lage.py (synthetisch: ebenes Gelaende, Hauptbau + Steg, ein Haus versperrt eine Seite)."""
import os, sys, json, math, argparse
import numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import abdeckung_meldung as AM

D_MIN, D_MAX = 30.0, 180.0         # ANNAHME: >= 30 m (beides im Bild), <= 180 m (Register BI: brauchbar bis 150 m, Hauptbau gross)
FERN_RASTER_M = 3.0
MIN_STELLE_SICHT = 3               # von 5 Stellenpunkten (Mehrheit)
BILD_ANTEIL = 0.85                 # ANNAHME: Rand 7,5 % je Seite frei
MIN_AZ_ABSTAND = 20.0              # ANNAHME: Fernstandpunkte >= 20 Grad auseinander (Triangulation)
MIN_HAUPT_BAND_M = 8.0            # ANNAHME: >= 8 m Wand des Hauptbaus sichtbar (vom Hang verdeckt der Anbau den Turm bis ~25 m)
NAH_ABSTAND_M = 4.0                # ANNAHME: Nahfoto Unterseite/Ende ~4 m neben der Kante (Strasse/Weg)


def _az(rahmen, v): return rahmen.azimut(np.asarray(v, float))


def fern_kandidaten(rahmen, sicht, koerper, L, hfov, oben_haupt, n_fern=5, alle=False):
    u0, u1, v0, v1, _ = koerper; c = np.asarray(L["mitte"]); u = np.asarray(L["achse"]); q = np.array([-u[1], u[0]]); Ln, B, zu, zo = L["laenge"], L["breite"], L["z_unten"], L["z_oben"]
    ecken = np.array([[u0, v0], [u0, v1], [u1, v0], [u1, v1]]); hm = ecken.mean(0); enden = np.array([c + u * Ln / 2, c - u * Ln / 2]); mz = (hm + c) / 2
    r = np.arange(-D_MAX - 40, D_MAX + 40 + 1e-6, FERN_RASTER_M); G = mz + np.stack(np.meshgrid(r, r), -1).reshape(-1, 2); out = []
    for p in G:
        d_h, d_s = np.linalg.norm(hm - p), np.linalg.norm(c - p)
        if min(d_h, d_s) < D_MIN or max(d_h, d_s) > D_MAX: continue
        if ((p[0] > u0 - 2) & (p[0] < u1 + 2) & (p[1] > v0 - 2) & (p[1] < v1 + 2)): continue
        a = np.degrees(np.arctan2(*(np.r_[ecken, enden] - p).T[::-1])); a = np.sort(a % 360); sp = 360 - np.diff(np.r_[a, a[0] + 360]).max()
        if sp > BILD_ANTEIL * hfov: continue
        rel = (p - c) @ u, (p - c) @ q
        if abs(rel[0]) <= Ln / 2 + 1 and abs(rel[1]) <= B / 2 + 1: continue
        if not sicht.ort_frei(p): continue
        b = sicht.boden(p)
        if sicht.dgm is not None and np.isnan(AM_raster(sicht, p)): continue
        # Hauptbau: Wandmitte zum Standort (aussen +0,5 m), Hoehe = Stellen-Oberkante (dort liegt der Anschluss)
        k = int(np.argmax([(p - hm) @ n for n in ([1, 0], [-1, 0], [0, 1], [0, -1])])); n = np.array(([1, 0], [-1, 0], [0, 1], [0, -1])[k], float)
        wm = np.array([[u1, (v0 + v1) / 2], [u0, (v0 + v1) / 2], [(u0 + u1) / 2, v1], [(u0 + u1) / 2, v0]])[k] + 0.5 * n
        zh, zbh, za = sicht.z_min(p, wm)
        if zh > oben_haupt - MIN_HAUPT_BAND_M: continue        # Hauptbau: Wandband >= MIN_HAUPT_BAND_M unter der Traufe sichtbar (Anker im Bild)
        seite = np.sign((p - c) @ q) or 1.0; zs = (zu + zo) / 2; sv, bv = 0, 0
        for s in (-0.4, -0.2, 0.0, 0.2, 0.4):
            Tp = c + u * s * Ln + q * seite * (B / 2 + 0.5); h_, w_, _ = sicht.z_min(p, Tp); sv += h_ <= zs; bv += w_ <= zs
        if sv < MIN_STELLE_SICHT: continue
        dach = bool(za > zo + 1.0 and sicht.z_min(p, c + q * seite * (B / 2 - 0.5), rand=B / 2 + 1)[0] <= zo)
        punkte = sv + 2 * dach + (bv >= MIN_STELLE_SICHT) + (zbh <= oben_haupt - MIN_HAUPT_BAND_M)
        out.append(dict(p=p, boden=b, auge=za, sicht_stelle=int(sv), sicht_baum_frei=int(bv), haupt_baum_frei=bool(zbh <= oben_haupt - MIN_HAUPT_BAND_M), haupt_ab_z=round(float(zh), 1), dach=dach, spanne=float(sp), punkte=punkte,
                        d_haupt=float(d_h), d_stelle=float(d_s), az_stelle=_az(rahmen, p - c)))
    out.sort(key=lambda x: (-x["punkte"], x["d_stelle"])); wahl = []
    if alle: return out, len(out)
    # zuerst die beste mit Dachsicht (Dach bisher ohne Foto), dann gierig mit Azimutabstand
    for x in [y for y in out if y["dach"]][:1] + out:
        if len(wahl) >= n_fern: break
        if any(abs((x["az_stelle"] - w["az_stelle"] + 180) % 360 - 180) < MIN_AZ_ABSTAND for w in wahl): continue
        wahl.append(x)
    return wahl, len(out)


def AM_raster(sicht, p):
    from foto_auftrag_skizze import raster_wert
    return raster_wert(sicht.dgm, sicht.rahmen.utm(np.atleast_2d(p)))[0]


def nah_standpunkte(zone, L, sicht):
    """Standpunkte fuer einen duennen Teil der Stelle (siehe Kopf). -> Liste dict(p, ziel(3), text)."""
    c = np.asarray(L["mitte"]); u = np.asarray(L["achse"]); q = np.array([-u[1], u[0]]); B = L["breite"]; lu = np.asarray(zone.get("zellen_luecke") or [], float).reshape(-1, 3)
    if not len(lu): return []
    s = (lu[:, :2] - c) @ u; name = zone["name"]; out = []
    if name.endswith("Dach"): return []
    qs = np.unique(np.round(np.quantile(s, [0.15, 0.5, 0.85]) / 2) * 2) if len(lu) > 2 else np.unique(np.round(s / 2) * 2)
    if name.endswith("Unterseite"):
        for si in qs:
            for sg in (1, -1):
                p = c + u * si + q * sg * (B / 2 + NAH_ABSTAND_M)
                if sicht.ort_frei(p, 0.5): out.append(dict(p=p, ziel=[*(c + u * si), L["z_unten"]], text=f"neben/unter dem Rand, Blick schraeg hoch an die Unterseite (Stelle {si:+.0f} m entlang); NUR vom Gehweg/Fussweg - liegt der Punkt auf der Fahrbahn, vom naechsten Gehweg aus")); break
    elif name.endswith("Deck innen"):
        for si in qs:
            p = c + u * si; z_ = L.get("z_lauf") or L["z_unten"]
            out.append(dict(p=p, ziel=[*(p + u * 6), z_ + AM.AUGE_M], innen=True, auge=z_ + AM.AUGE_M, beide=True,
                            text=f"AUF dem Steg ({si:+.0f} m entlang): je 1 Foto in BEIDE Richtungen entlang des Stegs, Boden + Gelaender + Decke im Bild"))
    else:
        m = lu.mean(0); n2 = np.asarray(zone.get("normal2") or [0, 0], float)
        if not n2.any(): return []
        b0 = math.atan2(n2[1], n2[0])
        for da in (-AM.MAX_SCHRITT_GRAD, 0, AM.MAX_SCHRITT_GRAD):
            a = b0 + math.radians(da); p = m[:2] + (B + NAH_ABSTAND_M) * np.array([math.cos(a), math.sin(a)])
            out.append(dict(p=p, ziel=list(m), text=f"vor {name.split(' ', 1)[1]}, Blick auf die Lueckenmitte ({da:+.0f} Grad zur Normale)"))
    return out


def erzeugen(objekt, zonen_json, meldung_json, stelle, aus, n_fern=5, geo=True, obj=None, cfg=None, meldung=None, sicht=None):
    import foto_auftrag_skizze as F
    obj = obj or json.load(open(objekt)); cfg = cfg or json.load(open(zonen_json)); meldung = meldung or json.load(open(meldung_json)); rahmen = F.Rahmen(obj)
    s = next(x for x in cfg["sonderstellen"] if x["name"] == stelle); pf = AM.lage_finden(s, os.path.dirname(os.path.abspath(zonen_json)) if zonen_json else None)
    if not pf: raise SystemExit(f"keine Lagedatei fuer {stelle} - Lage unbekannt, Fotoauftrag nur ueber abdeckung_meldung (Anschlussweg)")
    L = AM.lage_lesen(pf); rw = obj["rahmen_wand"]; koerper = (rw["u0"], rw["u1"], rw["v0"], rw["v1"], float(cfg.get("wand_oben_m", obj.get("hoehe_m", 20))))
    hfov = float(meldung.get("bildwinkel_grad") or AM.HFOV_ANNAHME); geb = dop = None
    if sicht is None:
        geb, _ = F.gebaeude(obj, rahmen, 260.0); dom = F.raster("dom1", rahmen, 260.0) if geo else None; dgm = F.raster("dgm1", rahmen, 260.0) if geo else None
        sicht = F.Sicht(geb, rahmen, dom, dgm, radius=260.0); dop = F.raster("dop20rgb", rahmen, 260.0) if geo else None
    fern, n_kand = fern_kandidaten(rahmen, sicht, koerper, L, hfov, koerper[4], n_fern)
    c = np.asarray(L["mitte"]); hm = np.array([(koerper[0] + koerper[1]) / 2, (koerper[2] + koerper[3]) / 2]); SP = []
    for i, x in enumerate(fern, 1):
        p = x["p"]; ziel = (hm + c) / 2; blick = ziel - p; la, lo = rahmen.geo(p); zz = (L["z_unten"] + L["z_oben"]) / 2
        SP.append(dict(nr=f"F{i}", art="fern", x=round(float(p[0]), 1), y=round(float(p[1]), 1), lat=round(la, 6), lon=round(lo, 6), blick_kompass_grad=round(_az(rahmen, blick)),
                       neigung_grad=round(math.degrees(math.atan2(zz - x["auge"], np.linalg.norm(blick)))), abstand_stelle_m=round(x["d_stelle"]), abstand_haupt_m=round(x["d_haupt"]),
                       gelaende_m=round(x["boden"], 1), format="Hochformat UND Querformat", stelle_sichtbar=f"{x['sicht_stelle']}/5", dach_sichtbar=x["dach"],
                       baum=None if (x["sicht_baum_frei"] >= MIN_STELLE_SICHT and x["haupt_baum_frei"]) else "Baum/Mast laut DOM1 in der Sichtlinie - im Winter meist kahl, sonst 5-10 m seitlich",
                       text=f"Turm UND {stelle} ganz im Bild ({x['spanne']:.0f} Grad von {hfov:.0f}), Turm ab z {x['haupt_ab_z']:.0f} m frei; " + ("von oben: Dach sichtbar" if x["dach"] else "von unten/seitlich")))
    teile = [z for z in meldung["zonen"] if z.get("gruppe") == stelle]; nah = []
    for z in teile:
        if z["status"] == "belegt": continue
        for j, x in enumerate(nah_standpunkte(z, L, sicht), 1):
            p = x["p"]; ziel = np.asarray(x["ziel"], float); la, lo = rahmen.geo(p); auge = x.get("auge", sicht.boden(p) + AM.AUGE_M); d = float(np.linalg.norm(ziel[:2] - p))
            nah.append(dict(nr=f"N{len(nah) + 1}", art="nah", teil=z["name"], status=z["status"], x=round(float(p[0]), 1), y=round(float(p[1]), 1), lat=round(la, 6), lon=round(lo, 6),
                            blick_kompass_grad=round(_az(rahmen, ziel[:2] - p)), neigung_grad=round(math.degrees(math.atan2(ziel[2] - auge, max(d, 0.5)))), abstand_m=round(d, 1),
                            format="Querformat", text=x["text"]))
            if x.get("beide"): nah[-1]["blick2_kompass_grad"] = round((nah[-1]["blick_kompass_grad"] + 180) % 360)
    luecken = [dict(teil=z["name"], status=z["status"], fehlt=z["fehlt"], fotos=z["fotos"]) for z in teile if z["status"] != "belegt"]
    dach_teil = next((z for z in teile if z["name"].endswith("Dach")), None)
    e = dict(stelle=stelle, lagedatei=_rel(pf), lage=L, bildwinkel_grad=hfov, fern_kandidaten=n_kand, standpunkte=SP + nah, luecken=luecken,
             teile=[dict(name=z["name"], status=z["status"], fotos=z["fotos"], faecher_grad=z["faecher_grad"], zellen_gesehen=z["zellen_gesehen"]) for z in teile],
             dach_ueber_fern=bool(dach_teil and dach_teil["status"] != "belegt" and any(x["dach_sichtbar"] for x in SP)),
             schwellen=dict(D_MIN=D_MIN, D_MAX=D_MAX, MIN_STELLE_SICHT=MIN_STELLE_SICHT, BILD_ANTEIL=BILD_ANTEIL, MIN_AZ_ABSTAND=MIN_AZ_ABSTAND, sicht=sicht.quelle))
    if aus:
        os.makedirs(aus, exist_ok=True); b = os.path.join(aus, f"foto_auftrag_{stelle.lower()}"); json.dump(e, open(b + ".json", "w"), indent=1, ensure_ascii=False, default=float)
        open(b + ".md", "w").write(markdown(e, obj)); zeichnen(e, koerper, L, rahmen, geb or [], dop, b + ".jpg")
    return e


def _rel(p):
    r = os.path.relpath(p, os.path.dirname(T)); return p if r.startswith("..") else r


def markdown(e, obj):
    L = e["lage"]; Z = [f"# Fotoauftrag {e['stelle']} ({obj.get('name', '')})", "",
         f"Lage aus `{_rel(e['lagedatei'])}`: Mitte x {L['mitte'][0]:.1f} / y {L['mitte'][1]:.1f} m, Laenge {L['laenge']} m, Breite {L['breite']} m, z {L['z_unten']}..{L['z_oben']} m.",
         "Handy: nubia Focus 2, Hauptkamera (Weitwinkel), feste Linse, KEIN Zoom, Wasserzeichen AUS, Ort speichern AN. Je Standpunkt 1 Foto hoch + 1 quer, ruhig halten.", "",
         "## Was fehlt (gemessen, tools/abdeckung_meldung.py)"]
    for t in e["teile"]: Z.append(f"- {t['name']}: {t['status']} - {t['fotos']} Fotos, Faecher {t['faecher_grad']:.0f} Grad, Flaeche von >= 3 Fotos gesehen {100 * t['zellen_gesehen']:.0f} %")
    Z += ["", f"## A Fernfotos: Turm UND {e['stelle']} zugleich ({sum(s['art'] == 'fern' for s in e['standpunkte'])} von {e['fern_kandidaten']} geprueften Orten)",
          "Standpunkte aus DGM1/DOM1/LoD2 berechnet; Strassen/Wege sind lokal nicht als Daten vorhanden: liegt ein Punkt auf der Fahrbahn oder ohne Weg, den naechsten Geh-/Fussweg mit gleicher Blickrichtung nehmen.",
          "Zweck: verbindet den gut verankerten Turm mit dem Steg im selben Bild (loest den 1-m-Hoehenwiderspruch Hauptnetz vf_244 gegen Laser); vom Hang zusaetzlich das Dach."]
    for s in e["standpunkte"]:
        if s["art"] != "fern": continue
        Z.append(f"- **{s['nr']}** GPS {s['lat']}, {s['lon']} (Modell x {s['x']} / y {s['y']} m, Gelaende {s['gelaende_m']:+.1f} m): Blick Kompass {s['blick_kompass_grad']} Grad, "
                 f"Handy {s['neigung_grad']} Grad, {s['abstand_stelle_m']} m zum Steg / {s['abstand_haupt_m']} m zum Turm. {s['text']}." + (f" Hinweis: {s['baum']}." if s.get("baum") else ""))
    Z += ["", "## B Nahfotos fuer die duennen Teile"]
    for s in e["standpunkte"]:
        if s["art"] == "nah": Z.append(f"- **{s['nr']}** ({s['teil']}, {s['status']}) GPS {s['lat']}, {s['lon']} (x {s['x']} / y {s['y']}): {s['text']}; Blick {s['blick_kompass_grad']} Grad"
                                       + (f" und {s['blick2_kompass_grad']} Grad" if s.get("blick2_kompass_grad") is not None else "") + f", Handy {s['neigung_grad']} Grad, {s['abstand_m']} m.")
    if e["dach_ueber_fern"]: Z.append("- Dach: ueber die Fernstandpunkte mit 'Dach sichtbar' (von oben).")
    Z += ["", "Danach: Fotos in den Zusatzordner, `tools/zusatzfotos_registrieren.py`, Kette (Stufe seiten, Schritt abdeckung_zusatz) meldet die Teile neu."]
    return "\n".join(Z) + "\n"


def zeichnen(e, koerper, L, rahmen, geb, dop, png):
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        from foto_auftrag_skizze import _luftbild
    except Exception: return None
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(18, 9.5), dpi=100, gridspec_kw=dict(width_ratios=[1.25, 1]))
    u0, u1, v0, v1, _ = koerper; H = rahmen.lokal(np.array([[u0, v0], [u1, v0], [u1, v1], [u0, v1], [u0, v0]]))
    c = np.asarray(L["mitte"]); u = np.asarray(L["achse"]); q = np.array([-u[1], u[0]]); Ln, B = L["laenge"], L["breite"]
    S = rahmen.lokal(np.array([c + a * u * Ln / 2 + b * q * B / 2 for a, b in ((1, 1), (1, -1), (-1, -1), (-1, 1), (1, 1))]))
    SP = e["standpunkte"]; P = rahmen.lokal(np.array([[s["x"], s["y"]] for s in SP]).reshape(-1, 2)) if SP else np.zeros((0, 2))
    for a, nah in ((ax, False), (ax2, True)):
        A = np.r_[H, S] if nah else np.r_[H, S, P]; lo, hi = A.min(0) - (12 if nah else 25), A.max(0) + (12 if nah else 25); w = max(hi - lo) / 2; m = (lo + hi) / 2; lo, hi = m - w, m + w
        _luftbild(a, dop, rahmen, lo, hi)
        for g in geb:
            for r in g["ringe"]: rr = rahmen.lokal(r); a.fill(rr[:, 0], rr[:, 1], color="#999", alpha=0.25, lw=0)
        a.plot(H[:, 0], H[:, 1], "-", color="#2e8b3e", lw=3, label="Turm (belegt)"); a.plot(S[:, 0], S[:, 1], "-", color="#d0281c", lw=3, label=f"{e['stelle']} (Lagedatei)")
        for s, p in zip(SP, P):
            if nah and s["art"] == "fern": continue
            col = "#6a1b9a" if s["art"] == "fern" else "#1f5fbf"; az = math.radians(s["blick_kompass_grad"]); L_ = 14 if s["art"] == "fern" else 4
            a.plot(*p, "o", ms=11, color=col, mec="white", zorder=5); a.annotate("", p + L_ * np.array([math.sin(az), math.cos(az)]), p, arrowprops=dict(arrowstyle="-|>", color=col, lw=2), zorder=5)
            a.text(p[0] + 2, p[1] + 2, s["nr"], fontsize=13 if s["art"] == "fern" else 10, weight="bold", color=col, zorder=6, bbox=dict(fc="white", ec="none", alpha=0.7, pad=1))
        a.set_xlim(lo[0], hi[0]); a.set_ylim(lo[1], hi[1]); a.set_aspect("equal"); a.set_xlabel("Ost (m)"); a.set_ylabel("Nord (m)")
    ax.set_title(f"Fotoauftrag {e['stelle']}: F = Fernfoto Turm+Steg (violett), Norden oben", loc="left"); ax2.set_title("Nahplan: N = Nahfoto fuer duenne Teile (blau)", loc="left")
    ax.legend(loc="lower left", fontsize=9); t = [f"{s['nr']}: {s['lat']:.6f}, {s['lon']:.6f}  Blick {s['blick_kompass_grad']} Grad" for s in SP]
    fig.text(0.01, 0.005, "   ".join(t)[:330], fontsize=8.5); fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.savefig(png, pil_kwargs=dict(quality=85)); plt.close(fig); return png


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0]); ap.add_argument("--objekt", required=True); ap.add_argument("--zonen", required=True)
    ap.add_argument("--meldung", required=True); ap.add_argument("--stelle", required=True); ap.add_argument("--n_fern", type=int, default=5); ap.add_argument("--aus", required=True)
    a = ap.parse_args(argv); e = erzeugen(a.objekt, a.zonen, a.meldung, a.stelle, a.aus, a.n_fern)
    for s in e["standpunkte"]: print(f"  {s['nr']:4s} {s['art']:4s} {s['lat']:.6f},{s['lon']:.6f} Blick {s['blick_kompass_grad']:4d} Grad {s.get('teil', '')} {s.get('text', '')[:80]}")
    print(f"-> {os.path.join(a.aus, 'foto_auftrag_' + a.stelle.lower())}.{{json,md,jpg}}"); return 0


if __name__ == "__main__": sys.exit(main())
