#!/usr/bin/env python3
"""test_schlitz_gewaende_unschaerfe.py - Befund Kettenlauf 1122zb (24.11.2026, Schwabentor, audit/neben_detail_fenster_*.jpg), synthetisch, nur CPU, < 20 s.

  1 fenster_f03_3  Foto: schmaler Lichtschlitz (0,09 x 0,73 m) in einem GESTUFTEN Sandsteingewaende (1,33 x 1,66 m). Kette: breites Rundbogenfenster mit
                   Kaempferlinie. Ursache: loch_gewaende.loch_messen verlangte >= 0,1 m in BEIDEN Richtungen -> 'Loch zu klein (0.09 x 0.73 m)' -> Eintrag blieb
                   der Erkennerkasten des Gewaendes mit der Bogenform aus nischen_fenster. Jetzt: schmale Seite >= max(Druckmindestmass, 3 Zellen), lange >= 0,1 m
                   -> Loch = Schlitz, Rechteck, Gewaende als eigener Umriss. Rot-Probe: Schlitz unter dem Druckmindestmass (0,05 m) bleibt verworfen (Guard).
  2 fenster_f04    Foto (verwaschenes Videobild): 'Fenster' 0,39 x 0,26 m am Sockel zwischen Bossenquadern, 11 von 18 Fotos 'bestaetigt' - davon 7 von 8
                   Videobildern, aber nur 5 von 10 scharfen Fotos. Ursache: schlitze_wandbild.bestaetigen zaehlte unscharfe Bilder mit; Unschaerfe verschmilzt
                   Schatten zwischen Steinen zu einem dunklen Fleck. Jetzt: UNSCHAERFE-TOR (Laplace-Varianz < 0,4 x 80-%-Wert der sehenden Fotos stimmt nicht mit).
                   Probe: Schattenfleck (scharf 50 %, unscharf alle) -> ohne Tor angenommen (Rot: alter Weg), mit Tor verworfen; echter Schlitz bleibt (alle scharfen).
"""
import sys, os, json, numpy as np
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(HIER), "tools"))
import loch_gewaende as LG
import schlitze_wandbild as SW

F = 0


def pruef(ok, text):
    global F
    print(("    ok " if ok else "FEHLER ") + text)
    if not ok: F += 1


WAND, SAND, DUNKEL = (200, 205, 212), (95, 108, 165), (25, 25, 30)          # BGR wie test_loch_gewaende


def gewaende_bild(schlitz_b, C=0.01):
    """Wand 4 x 4 m (u -2..2, z 16..20), gestuftes Sandsteingewaende um einen Schlitz schlitz_b x 0,73 m (Mitte u 0, z 17,8..18,53)."""
    rng = np.random.default_rng(5); H = W = int(4.0 / C)
    im = np.zeros((H, W, 3)) + np.array(WAND) + rng.normal(0, 3.0, (H, W, 1))
    UU, ZZ = np.meshgrid(-2.0 + C * (np.arange(W) + 0.5), 20.0 - C * (np.arange(H) + 0.5))
    def feld(u0, u1, z0, z1, f): im[(UU >= u0) & (UU <= u1) & (ZZ >= z0) & (ZZ <= z1)] = f
    feld(-0.5, 0.5, 17.5, 19.15, SAND); feld(-0.66, 0.66, 17.75, 18.7, SAND); feld(-0.6, 0.6, 17.48, 17.75, SAND)     # Stufen (Kreuzform wie f03_3)
    feld(-schlitz_b / 2, schlitz_b / 2, 17.8, 18.53, DUNKEL)
    return np.clip(im, 0, 255).astype(np.uint8), LG.Raster(-2.0, 20.0, C, H, W)


def teil1():
    print("1 Schlitz im gestuften Gewaende (fenster_f03_3)")
    zone = [-0.665, 0.665, 17.49, 19.15]
    bgr, R = gewaende_bild(0.08)                                               # gemessen 2-/98-%-Kasten + halbe Zellen ~ 0,09 wie im Lauf
    erg = LG.loch_messen(bgr, R, zone)
    pruef("fehler" not in erg, f"Schlitz 0,08 m wird als Loch gemessen ({erg.get('fehler', 'ok')})")
    if "fehler" in erg: return
    L = erg["loch"]; b, h = L["u1"] - L["u0"], L["z1"] - L["z0"]
    pruef(abs(b - 0.08) <= 0.025 and abs(h - 0.73) <= 0.04, f"Loch {b:.3f} x {h:.3f} m (Soll 0,08 x 0,73)")
    pruef(bool(erg.get("gewaende")) and erg["gewaende"]["flaeche_m2"] > 1.0, f"Gewaende als eigener Umriss ({(erg.get('gewaende') or {}).get('flaeche_m2')} m2, Soll > 1)")
    e = dict(u0=zone[0], u1=zone[1], z0=zone[2], z1=zone[3], bogen=dict(form="rund", kaempfer=18.486, scheitel=19.15), tiefe=0.12, tiefe_quelle="ANNAHME")
    erg.pop("_masken", None); LG.eintrag_anpassen(e, erg, None)
    pruef(e["bogen"]["form"] == "gerade" and e["u1"] - e["u0"] < 0.15, f"Eintrag: Rechteck {e['u1'] - e['u0']:.2f} m statt Rundbogen 1,33 m (Form {e['bogen']['form']})")
    pruef("Gewaende" in e.get("form_quelle", ""), "form_quelle nennt: Bogen war die Form des Gewaendes")
    pruef(bool(e.get("gewaende")), "Gewaende im Eintrag (bauteile.fenster_aus_json baut es als Relief)")
    # Rot-Probe alter Weg: min 0,1 in beiden Richtungen haette den Schlitz verworfen
    pruef(min(b, h) < 0.1, "Rot: Schlitz ist schmaler als die alte Schwelle 0,1 m (alter Weg: 'Loch zu klein')")
    # Guard: unter dem Druckmindestmass bleibt es verworfen
    bgr2, R2 = gewaende_bild(0.04)
    e2 = LG.loch_messen(bgr2, R2, zone)
    pruef("fehler" in e2, f"Guard: Schlitz 0,04 m (< Druckmindestmass {LG.druck_min():.3f}) bleibt verworfen ({e2.get('fehler', 'ANGENOMMEN')[:40]})")
    pruef(abs(LG.schmal_minimum(0.01) - LG.druck_min()) < 1e-9 and abs(LG.schmal_minimum(0.05) - 0.1) < 1e-9, "schmal_minimum: Druckmass bei 1 cm, min_m bei 5-cm-Zellen (3 Zellen)")


def foto(c, H, W, fleck, unscharf, seed):
    """Einzelfoto (RGB) im Mosaikrahmen: Bossenquader-Raster mit Schattenfugen; fleck = dunkle Stelle (Loch/Schatten) u 0,3..0,7 z 0,2..0,45; unscharf = Gauss."""
    from scipy import ndimage as ndi
    rng = np.random.default_rng(seed)
    UU, ZZ = np.meshgrid((np.arange(W) + 0.5) * c, 2.0 - (np.arange(H) + 0.5) * c)
    a = np.zeros((H, W, 3), np.float32) + 205 + rng.normal(0, 4.0, (H, W, 1))
    st = ((UU % 0.4) < 0.03) | ((ZZ % 0.3) < 0.03); a[st] = 120                    # Fugen/Steinkanten (Textur fuer die Schaerfe)
    if fleck: a[(UU >= 0.3) & (UU <= 0.7) & (ZZ >= 0.2) & (ZZ <= 0.45)] = 25
    if unscharf: a = ndi.gaussian_filter(a, sigma=(unscharf, unscharf, 0))
    return np.clip(a, 0, 255).astype(np.uint8)


def teil2():
    print("2 Unschaerfe-Tor fuer Formbelege (fenster_f04 am Sockel, Videobilder)")
    c = 0.01; H, W = 200, 120
    R = dict(c=c, u0=0.0, z1=2.0, form=(H, W), grob_zelle=None)
    k = dict(u0=0.3, u1=0.7, z0=0.2, z1=0.45)
    # Schattenfleck: 10 scharfe Fotos, nur 5 zeigen ihn (lichtabhaengig); 8 unscharfe Videobilder zeigen ihn alle (Schatten verschmilzt)
    fotos = [dict(rgb=foto(c, H, W, i < 5, 0, i), datei=f"IMG_{i:02d}.png") for i in range(10)]
    fotos += [dict(rgb=foto(c, H, W, True, 4.0, 50 + i), datei=f"video_frames_vf_{i:03d}.png") for i in range(8)]
    n0, g0, *_ = SW.bestaetigen(k, fotos, R, schaerfe_min=0)
    n1, g1, _, _, je = SW.bestaetigen(k, fotos, R)
    pruef(n0 >= SW.MEHRHEIT * g0, f"Rot (alter Weg ohne Tor): {n0} von {g0} - Mehrheit, waere gebaut worden")
    pruef(n1 < SW.MEHRHEIT * g1, f"mit Unschaerfe-Tor: {n1} von {g1} sehenden (< 60 %) -> verworfen")
    pruef(sum(1 for v in je.values() if v.startswith("unscharf")) == 8, f"die 8 Videobilder stimmen nicht mit ({sum(1 for v in je.values() if v.startswith('unscharf'))})")
    # echter Schlitz/Luke: alle scharfen Fotos zeigen ihn -> bleibt
    fotos2 = [dict(rgb=foto(c, H, W, True, 0, i), datei=f"IMG_{i:02d}.png") for i in range(6)] + [dict(rgb=foto(c, H, W, True, 4.0, 70 + i), datei=f"vf_{i}.png") for i in range(4)]
    n2, g2, kan, *_ = SW.bestaetigen(k, fotos2, R)
    pruef(n2 >= 3 and n2 >= SW.MEHRHEIT * g2 and kan is not None and abs(kan[1] - kan[0] - 0.4) < 0.05, f"echtes Loch bleibt: {n2} von {g2}, Breite {None if kan is None else round(kan[1] - kan[0], 3)}")
    # alle gleich scharf -> niemand faellt weg
    # 24.11.2026 abends (Regression merge-probe-30): Tor nur bei schwachem Kontrast. Rot-Proben aus 1122zb: Sockelschatten f04 L 9,8 / Ring 20,4 -> Tor AN;
    # Schlitze f00 z 34 L 18,2 / Ring 71,0 und L 15,4 / Ring 70,3 -> Tor AUS (unscharfe = entfernte Fotos zaehlen, 15 von 21 bzw. 12 von 20 statt 8 von 14)
    t_s, tx = SW.tor_schaerfe(dict(L=9.8, ring_L=20.4)); pruef(t_s > 0, f"Sockelschatten f04 (Kontrast 0,48): Unschaerfe-Tor an - {tx}")
    t_a, _ = SW.tor_schaerfe(dict(L=18.2, ring_L=71.0)); t_b, _ = SW.tor_schaerfe(dict(L=15.4, ring_L=70.3))
    pruef(t_a == 0 and t_b == 0, "Schlitze f00 z 34 in hellem Putz (Kontrast 0,26/0,22): Tor aus")
    pruef(SW.tor_schaerfe(dict(L=10.0, ring_L=float("nan")))[0] > 0 and SW.tor_schaerfe(dict(L=5.0, ring_L=70.0), 0)[0] == 0, "Ring unbekannt -> Tor an; --schaerfe 0 -> aus")
    # Rot-Probe Ablauf: starker Schlitz, den v. a. unscharfe Fotos bestaetigen und scharfe groesser sehen (f00 z 34): mit Tor verworfen, ohne (Kontrast stark) Mehrheit
    def gross(seed):                                                              # scharfes Foto sieht das Loch samt Schattenrand groesser (0,6 x 0,4 m)
        a_ = foto(c, H, W, True, 0, seed); a_[int((2.0 - 0.55) / c):int((2.0 - 0.15) / c), int(0.2 / c):int(0.8 / c)] = 25; return a_
    fs = [dict(rgb=foto(c, H, W, True, 4.0 if i < 8 else 0, 30 + i), datei=f"IMG_fern_{i:02d}.png") for i in range(12)] + [dict(rgb=gross(60 + i), datei=f"IMG_nah_{i}.png") for i in range(5)]
    na, ga, *_ = SW.bestaetigen(k, fs, R, schaerfe_min=SW.SCHAERFE_MIN); nb, gb, *_ = SW.bestaetigen(k, fs, R, schaerfe_min=0)
    pruef(na < SW.MEHRHEIT * ga and nb >= SW.MEHRHEIT * gb, f"heller-Putz-Schlitz: mit Tor {na} von {ga} (verworfen), Tor aus {nb} von {gb} (Mehrheit)")
    s, ref = SW.scharfe_auswahl([100.0, 110.0, 95.0, 105.0])
    pruef(all(s), "gleich scharfe Fotos: alle stimmen mit")
    s, ref = SW.scharfe_auswahl([100.0, None, 10.0])
    pruef(s == [True, True, False], f"unbekannte Schaerfe zaehlt, 10 % faellt weg ({s})")


if __name__ == "__main__":
    teil1(); teil2()
    print("FEHLER:", F) if F else print("alle Proben bestanden")
    sys.exit(1 if F else 0)
