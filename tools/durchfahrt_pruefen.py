#!/usr/bin/env python3
"""durchfahrt_pruefen.py - Ist eine gebaute Bogenoeffnung eine DURCHFAHRT durch das ganze Gebaeude? (21.11.2026, Kettenstufe 'fenster' nach oeffnungen_bogen)

Anlass (Kettenlauf Schwabentor 21.11.): das Stadttor f00 war gebaut (Spitzbogen, Durchblick im Ebenen-Sweep belegt), aber nur als Nische von 0,6 m (ANNAHME). Ursache:
tools/oeffnungen_bogen.py erkennt eine Durchfahrt nur, wenn die GEGENSEITE (Normale entgegengesetzt) selbst einen Bogenkandidaten des Parsings hat (Fall a/b). Am Schwabentor
liegt gegenueber von f00 die Fassade f01 mit nur 4 Fotos - das Parsing fand dort nichts, kein Sweep, also 'kein Gegenstueck' -> Nische. Die Fotos der Torseite sehen aber
TIEF in den Torweg hinein: die dichte Wolke (aus diesen Fotos trianguliert) hat Gewoelbe-/Laibungspunkte in jeder Tiefe bis zur Gegenseite und keine Rueckwand.

Pruefung je gebauter Oeffnung ohne Durchfahrt (nur LAGE aus der Wolke - die Form bleibt die aus dem Wandbild/Sweep):
  1. Gegenseite = Fassade mit entgegengesetzter Normalen (n_a . n_b < -0,9), Dicke = Abstand der Ebenen; die Oeffnung muss quer in deren Breite liegen.
  2. LAIBUNG DURCHGEHEND: die Seitenwand des Torwegs (Streifen +-LAIBUNG_M um die Torkante, z unter dem Kaempfer) hat in jeder Tiefenscheibe (SCHEIBE_M) von 1 m hinter der
     Wand bis Dicke - 0,5 m mind. MIN_PUNKTE Wolkenpunkte und KONTRAST x so viele wie ein Kontrollstreifen im Mauerwerk daneben - auf mind. einer Seite in ANTEIL_SCHEIBEN
     der Scheiben. Eine Nische endet an ihrer Rueckwand; Streupunkte im Inneren (erste Fassung zaehlte alle Punkte im Querschnitt: massive Wand neben dem Tor 'bestand' auch) haben keinen Kontrast.
  3. KEINE RUECKWAND: keine Tiefenscheibe ab 1 m hinter der Wand deckt das Rechteck unter dem Kaempfer (Zellen ZELLE_M, Rand RAND_M) zu mehr als RUECKWAND_DECKUNG ab.
Treffer -> durchfahrt=True, gegen=<id>, tiefe_m = Dicke + 0,6 (Querschnitt dieser Seite gerade durch das ganze Gebaeude, ANNAHME), beleg_durchfahrt {scheiben, deckung}.
Aufruf: durchfahrt_pruefen.py <fassaden.json> <oeffnungen_auto.json> --wolke <punkte.npy>   (schreibt oeffnungen_auto.json in place)
rc 0 = mind. eine Durchfahrt (neu oder schon da), rc 3 = keine.
"""
import sys, os, json, argparse, numpy as np

BODEN_M = 0.5          # Boden/Fahrbahn und Leute/Autos darauf ausblenden
RAND_M = 0.3           # Laibung/Gewaende am Rand ausblenden (die Seitenwaende des Torwegs liegen auf dem Rand)
SCHEIBE_M = 1.0        # Tiefenscheibe
MIN_PUNKTE = 10        # Punkte je Scheibe und Laibungsstreifen, damit sie als 'gesehen' zaehlt
KONTRAST = 2.0         # ... und mind. doppelt so viele wie im Kontrollstreifen dahinter (im Mauerwerk): die Wolke hat im Inneren Streupunkte (Schwabentor einige 100 je m3)
LAIBUNG_M = 0.4        # halbe Breite des Laibungsstreifens um die Torkante (Kante aus dem Wandbild auf ~5 cm, Laibung leicht schraeg/verputzt)
KONTROLLE_M = (0.8, 1.6)  # Kontrollstreifen 0,8-1,6 m seitlich der Laibung, BEIDE Richtungen (Mauerwerk aussen, Torweg innen): eine Laibung ist eine duenne Flaeche, kein Streuband
ANTEIL_SCHEIBEN = 0.7  # Anteil gesehener Scheiben bis zur Gegenseite (eine Laibungsseite reicht - die andere liegt oft im Schatten)
RUECKWAND_DECKUNG = 0.6  # eine Rueckwand fuellt das Rechteck unter dem Kaempfer weitgehend (Schwabentor-Torweg max. 0,38 ab 1 m Tiefe)
ZELLE_M = 0.25


def pruefen(W, o, d, n, x, dicke):
    """W: Punkte (k x 3), Fassadenrahmen o/d/n, Oeffnung x (u, breite, kaempfer, scheitel, unten), Dicke bis zur Gegenseite.
    -> dict(ok, laibung {links, rechts: [[seite, kontrolle] je Scheibe]}, gesehen_anteil, max_deckung, grund)."""
    u = (W[:, :2] - o) @ d; w = -((W[:, :2] - o) @ n); z = W[:, 2]          # w > 0 = hinter der Wand (ins Gebaeude)
    zb = float(x.get("unten", 0.0)); hb = x["breite"] / 2; uc = x["u"]
    hz = (z > zb + BODEN_M) & (z < x["kaempfer"]) & (w > 1.0) & (w < dicke - 0.5)
    kanten = np.arange(1.0, dicke - 0.5 + 1e-9, SCHEIBE_M)
    if len(kanten) < 3: return dict(ok=False, grund=f"zu duenn fuer eine Durchfahrtspruefung ({dicke:.1f} m)")
    sei = {}
    for nm, sg in (("links", -1), ("rechts", 1)):
        ui = uc + sg * hb; st = hz & (np.abs(u - ui) < LAIBUNG_M); ka = np.abs(u - ui)
        ko = hz & (ka > KONTROLLE_M[0]) & (ka < KONTROLLE_M[1]) & (sg * (u - ui) > 0); ki = hz & (ka > KONTROLLE_M[0]) & (ka < KONTROLLE_M[1]) & (sg * (u - ui) < 0)   # Mauerwerk aussen / Torweg innen
        wl, wk, wi = w[st], w[ko], w[ki]; sei[nm] = [[int(((wl >= a) & (wl < b)).sum()), max(int(((wk >= a) & (wk < b)).sum()), int(((wi >= a) & (wi < b)).sum()))] for a, b in zip(kanten[:-1], kanten[1:])]
    ant = {nm: float(np.mean([s_ >= MIN_PUNKTE and s_ >= KONTRAST * max(k_, 1) for s_, k_ in v])) for nm, v in sei.items()}
    rq = (np.abs(u - uc) < hb - RAND_M) & hz; dmax = 0.0; nu = max(1, int(2 * (hb - RAND_M) / ZELLE_M)); nz = max(1, int((x["kaempfer"] - zb - BODEN_M) / ZELLE_M))
    for a, b in zip(kanten[:-1], kanten[1:]):
        r = rq & (w >= a) & (w < b)
        if r.any():
            iu = np.clip(((u[r] - uc + hb - RAND_M) / ZELLE_M).astype(int), 0, nu - 1); iz = np.clip(((z[r] - zb - BODEN_M) / ZELLE_M).astype(int), 0, nz - 1)
            dmax = max(dmax, len(set(zip(iu.tolist(), iz.tolist()))) / (nu * nz))
    best = max(ant.values()); ok = best >= ANTEIL_SCHEIBEN and dmax <= RUECKWAND_DECKUNG
    grund = None if ok else ("Rueckwand im Torweg (Deckung %.2f)" % dmax if dmax > RUECKWAND_DECKUNG else "Laibung nicht bis zur Gegenseite gesehen (beste Seite %.0f %% der Tiefenscheiben)" % (100 * best))
    return dict(ok=ok, laibung=sei, gesehen_anteil={k_: round(v_, 2) for k_, v_ in ant.items()}, max_deckung=round(dmax, 2), grund=grund)


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("fassaden"); ap.add_argument("oeffnungen"); ap.add_argument("--wolke", required=True); a = ap.parse_args(argv)
    FL = {F.get("id"): F for F in json.load(open(a.fassaden))["fassaden"]}; OE = json.load(open(a.oeffnungen))
    W = None; n_df = 0
    for fid, A in OE.items():
        if not isinstance(A, dict): continue
        for x in A.get("oeffnungen", []):
            if not x.get("gebaut") or "u" not in x: continue
            if x.get("durchfahrt"): n_df += 1; continue
            oa, da, na = (np.array(A[q], float) for q in ("o", "d", "n"))
            for gid, F in FL.items():
                if gid == fid: continue
                nb = np.array(F["n"], float)
                if na @ nb > -0.9: continue
                dicke = float(-(np.array(F["o"], float) - oa) @ na)
                ub = float((oa + x["u"] * da - np.array(F["o"], float)) @ np.array(F["d"], float)); r_ = F.get("raster") or {}
                if dicke <= 1.5 or (r_ and not (r_["u0"] <= ub <= r_["u0"] + r_["nu"] * r_["zelle"])): continue
                if W is None: W = np.asarray(np.load(a.wolke, mmap_mode="r")[:, :3])
                P = pruefen(W, oa, da, na, x, dicke); print(f"{fid} u {x['u']:+.2f} gegen {gid} (Dicke {dicke:.2f} m): {'DURCHFAHRT' if P['ok'] else 'keine'} - Laibung gesehen {P.get('gesehen_anteil')}, Deckung max {P.get('max_deckung')}" + (f" ({P['grund']})" if P.get("grund") else ""))
                x["beleg_durchfahrt"] = dict(P, gegen=gid, dicke=round(dicke, 2), quelle="tools/durchfahrt_pruefen.py (dichte Wolke: Lage)")
                if P["ok"]:
                    x.update(durchfahrt=True, gegen=gid, tiefe_m=round(dicke + 0.6, 3), annahmen=[a_ for a_ in x.get("annahmen", []) if "kein Gegenstueck" not in a_] +
                             [f"ANNAHME: Durchfahrt mit DIESEM Querschnitt gerade durch das ganze Gebaeude ({dicke:.2f} m) - Gegenseite {gid} ohne eigenen Bogenkandidaten, Torweg in der Wolke durchgehend ohne Rueckwand"]); n_df += 1
                    break
    json.dump(OE, open(a.oeffnungen, "w"), indent=1, ensure_ascii=False); print("->", a.oeffnungen, f"({n_df} Durchfahrt(en))")
    return 0 if n_df else 3


if __name__ == "__main__": sys.exit(main())
