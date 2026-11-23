#!/usr/bin/env python3
"""rund_aus_huelle.py - RUNDKOERPER (Treppentuermchen, Rundturm) mit DACH als Drehkoerper aus EINSEITIGEN Foto-Silhouetten (Sehstrahl-Huelle), 23.11.2026.

Anlass (Kette 1122s, neben_eigen__IMG_20261106_113231 rechts unten: weisser Rundbau mit geschweiftem Kegeldach; Modell: schlanker hoher Zylinder ohne Dach):
 URSACHE (koerper_auto.json rund0): rund_aus_umriss sucht Umriss-Tangenten bis kasten-Oberkante + 3 m (10,94 + 3 = 13,94). Ueber der wahren Traufe (~12,4-13 m) liegen die
 Beruehrlinien eines r-1,87-Kreises weiter auf senkrechten Kanten (Hauptturmkante, Eckquader, Erkerpfosten) - die Umriss-Stuetze faellt nie unter 50 %, darum
 Oberkante = Suchende 13,75 m, keine Traufe (kein Ueberstand > 8 %), Kegeldach gesucht AB 13,75 m (ueber der wahren Spitze ~14,5) -> 'nur 2 Fotos einig' -> kein Dach.
 Der Gradient misst KEINE Silhouette: eine senkrechte Kante neben dem Koerper ist fuer ihn so gut wie sein Umriss. Eine Silhouette gegen HIMMEL dagegen endet, wo der
 Koerper endet (Dachschraege, Spitze = Himmel an der Achse).
VERFAHREN (Bausteine aus tools/drehkoerper_aus_fotos.py, wie die Laternenhaube):
 1. Fotoauswahl ueber ALLE Kameras: Koerper oben im Bild, >= --min-ppm, Himmelsmaske im Cache (nur lesen), Himmelsfarbe plausibel (Maske nicht auf Fassaden).
 2. Je Foto und Hoehe die EINSEITIGE Silhouette (einseitig_halb): vom Achsenpunkt nach aussen bis zur Himmelsfarbe; Seite ohne Himmel dahinter = +-inf (keine Schranke),
    Himmel an der Achse = ueber der Spitze.
 3. Achse = Lage aus Umriss/Wolke (KERNMETHODE: Wolke nur Lage; --achse-frei sucht sie aus den Silhouetten - einseitig mit Mitte/Radius gekoppelt, am Schwabentor
    0,6 m daneben), Huelle r(z) = K_HUELLE-kleinster Wert der einschraenkenden Fotos; Fotos, die die Huelle in > 30 % ihrer Hoehen einschnueren, raus (Maske/Kamera).
 4. Zonen aus r(z): Spitze = oberste Hoehe mit Koerper unter bestaetigtem Himmel; Traufe = von der Spitze abwaerts erste Hoehe, unter der r nicht mehr waechst; Dachprofil = Huelle
    Traufe -> Spitze (nach oben nicht wachsend); Schaft = Huelle darunter. Formfamilie gerade/geschweift/gebaucht aus der Abweichung von der Geraden.
Ausgabe: koerper_auto.json je Rundhaufen Block 'huelle'; mit --uebernehmen: gueltiges Dach -> 'dach' (bauteile.kegeldach_teile baut es), Traufe, Profil bis zur Traufe,
 Schaftradius aus der Huelle (wenn >= SCHAFT_ANTEIL der Schafthoehen gemessen). Bild audit/rund_huelle_<id>.jpg.
Aufruf: rund_aus_huelle.py <objekt.json> [--koerper K] [--uebernehmen] [--bild B] [--cache C] [--root R] [--min-ppm 20]
rc 0 = Dach gueltig, rc 3 = kein Rundkandidat, rc 4 = zu wenig Fotos/kein gueltiges Dach (nichts uebernommen).
"""
import sys, os, json, argparse, math, numpy as np

H_ = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H_)
import drehkoerper_aus_fotos as DK

MIN_ZEILEN = 5          # Foto zaehlt nur mit >= 5 Hoehen, in denen eine Seite gegen Himmel gemessen ist
S_MAX_R = 2.5           # Suchgrenze der Huelle: 2,5 x Startradius (Traufe bis 140 % + Spiel; groesser = Seite unbeschraenkt)
TRAUFE_FENSTER = 0.5    # Traufe: unter ihr waechst r in 0,5 m um hoechstens 3 % (ANNAHME: Huellenstreuung 2-3 %; das Dach waechst je 0,5 m um >> 3 %)
TRAUFE_ZUWACHS = 0.03
SCHAFT_FENSTER = 3.0    # Schaftradius = Median der Huelle 0,3..3 m unter der Traufe (oberer Schaft vor Himmel; ANNAHME: lotrechter Zylinder)
SPITZE_R = 0.03         # Hoehe 'leer' (Himmel an der Achse in >= K Fotos): Huellenradius < 3 cm
DACH_ABDECKUNG = 0.6    # Dach gueltig nur, wenn >= 60 % der Hoehen Traufe..Spitze gemessen sind
SCHAFT_ANTEIL = 0.5     # Schaftradius aus der Huelle nur, wenn >= 50 % der Schafthoehen gemessen sind (sonst bleibt das Umriss-Mass)
FAMILIE_TOL = 0.12      # geschweift/gebaucht: Radius auf halber Dachhoehe > 12 % unter/ueber der Geraden Traufe-Spitze (ANNAHME, Huellenstreuung ~3 %)
R_TRAUFE = (0.8, 1.5)   # Traufradius / Schaftradius (Ueberstand bis 50 %, eingezogen bis 80 %), sonst kein Dach dieses Koerpers
DZ = 0.1                # Hoehenraster (m)
EINSCHNUER_MAX = 0.3    # Foto raus, wenn es in > 30 % seiner einschraenkenden Hoehen > 10 % unter der Huelle liegt (je Hoehe sind das sonst hoechstens k-1 Fotos)


def zonen(zs, r, r_schaft_start):
    """Zonen aus dem Huellenprofil r(z) (NaN = nicht gemessen). -> dict(z_spitze, z_traufe, r_traufe, r_schaft, schaft_anteil, dach_anteil, dach_profil) oder (None, Grund)."""
    zs = np.asarray(zs, float); r = np.asarray(r, float); f = np.isfinite(r)
    if f.sum() < 5: return None, f"nur {int(f.sum())} Hoehen gemessen"
    voll = f & (r > SPITZE_R); leer = f & (r <= SPITZE_R)
    if not voll.any(): return None, "kein Koerper in der Huelle"
    # Spitze: oberste Koerperhoehe, ueber der (innerhalb 1 m) Himmel bestaetigt ist
    iv = np.where(voll)[0]; z_s = None
    for i in iv[::-1]:
        ob = leer & (zs > zs[i]) & (zs <= zs[i] + 1.0)
        if ob.any(): z_s = float(zs[i]); break
    if z_s is None: return None, "Spitze nicht gemessen (kein Himmel ueber dem Koerper in >= K Fotos)"
    # Traufe: von der Spitze abwaerts waechst r (Dach); die Traufe ist die erste Hoehe, unter der r in TRAUFE_FENSTER nicht mehr um > TRAUFE_ZUWACHS waechst (Schaft
    # erreicht). Nicht 'groesster Radius': tief unten sehen nur wenige Fotos Himmel neben dem Koerper (Nachbarhaeuser, Strasse) - dort ist die Huelle weit (Schwabentor
    # 1122s: r 2,2..4,5 unter z 8,5 bei Schaft 1,9).
    unter = voll & (zs <= z_s); i_t = None
    for i in np.where(unter)[0][::-1]:
        fe = f & (zs >= zs[i] - TRAUFE_FENSTER) & (zs < zs[i])
        if fe.sum() >= 2 and np.nanmax(r[fe]) <= (1 + TRAUFE_ZUWACHS) * r[i]: i_t = i; break
    if i_t is None: return None, "keine Traufe (Huelle waechst bis zum unteren Ende)"
    z_t = float(zs[i_t]); nah = unter & (zs >= z_t - TRAUFE_FENSTER) & (zs <= z_t); r_t = float(np.nanmax(np.where(nah, r, np.nan)))
    sch = (zs < z_t - 0.3) & (zs >= z_t - SCHAFT_FENSTER); r_s = float(np.median(r[sch & voll])) if (sch & voll).any() else None
    s_ant = float((sch & f).sum() / max(sch.sum(), 1)); r_k = r_t
    band = (zs >= z_t) & (zs <= z_s); d_ant = float((band & f).sum() / max(band.sum(), 1))
    P = [[z_t, r_t]]
    for z_, r_ in zip(zs[band & voll], r[band & voll]):
        if z_ <= P[-1][0] + 0.25 - 1e-6: continue
        P.append([float(z_), float(min(r_, P[-1][1]))])
    if z_s > P[-1][0] + 1e-6: P.append([z_s, 0.0])
    else: P[-1] = [z_s, 0.0]
    P = [[round(z_, 2), round(r_, 3)] for z_, r_ in P]
    # Formfamilie: Radius auf halber Dachhoehe gegen die Gerade Traufe-Spitze
    zm = (z_t + z_s) / 2; rm = float(np.interp(zm, [p[0] for p in P], [p[1] for p in P])); rg = r_t / 2
    fam = "geschweift" if rm < (1 - FAMILIE_TOL) * rg else "gebaucht" if rm > (1 + FAMILIE_TOL) * rg else "kegel"
    return dict(z_spitze=round(z_s, 2), z_traufe=round(z_t, 2), r_traufe=round(r_t, 3), r_koerper=round(r_k, 3), r_schaft=None if r_s is None else round(r_s, 3),
                schaft_anteil=round(s_ant, 2), dach_anteil=round(d_ant, 2), dach_profil=P, familie=fam, r_halbe_hoehe=round(rm, 3), r_gerade=round(rg, 3)), None


def huelle_messen(beob, A, zs, r_start, achse_frei=False, log=print):
    """Kern ohne Dateien (Test): beob = Fotos dict(C, az, A0, zg, l, r, nr) mit einseitigen Silhouetten (+-inf = Seite nicht messbar). -> dict Ergebnis."""
    s_max = S_MAX_R * r_start; zs = np.asarray(zs, float)
    if len(beob) < DK.MIN_FOTOS: return dict(gueltig=False, grund=f"nur {len(beob)} Fotos mit Silhouette gegen Himmel")
    if achse_frei: A, _ = DK.achse_suchen(beob, A, zs, s_max, log=log)
    weg = {}
    for _ in range(3):
        r, S, bd = DK.drehprofil(beob, A, zs, s_max=s_max, einseitig=True)
        e = DK.einschnuerung(S, r, s_max); raus = [B["nr"] for B, e_ in zip(beob, e) if e_ > EINSCHNUER_MAX]
        if not raus or len(beob) - len(raus) < DK.MIN_FOTOS: break
        for B, e_ in zip(beob, e):
            if B["nr"] in raus: weg[B["nr"]] = f"schnuert die Huelle in {e_:.0%} seiner Hoehen um > 10 % ein (Maske/Kamera falsch)"
        beob = [B for B in beob if B["nr"] not in raus]
        if achse_frei: A, _ = DK.achse_suchen(beob, A, zs, s_max, halb=0.1, schritt=0.05, log=log)
    r = DK.glaetten_nan(r)
    Z, g = zonen(zs, r, r_start)
    erg = dict(achse=[round(float(A[0]), 3), round(float(A[1]), 3)], fotos=[B["nr"] for B in beob], weg=weg, k_huelle=DK.K_HUELLE,
               profil=[[round(float(z), 2), None if not np.isfinite(v) else round(float(v), 3), int(b)] for z, v, b in zip(zs, r, bd)],
               einschnuerung={B["nr"]: round(float(v), 2) for B, v in zip(beob, e)})
    if Z is None: return dict(erg, gueltig=False, grund=g)
    band = (zs >= Z["z_traufe"]) & (zs <= Z["z_spitze"])
    bind = sorted({beob[i]["nr"] for i in range(len(beob)) for j in np.where(band & np.isfinite(r))[0] if S[i, j] <= 1.05 * r[j] + 1e-3 and S[i, j] < 0.999 * s_max})
    r_s = Z["r_schaft"] if Z["r_schaft"] is not None and Z["schaft_anteil"] >= SCHAFT_ANTEIL else r_start
    grund = None
    if len(bind) < DK.MIN_FAMILIE: grund = f"Dach nur von {len(bind)} Fotos gebunden (verlangt {DK.MIN_FAMILIE})"
    elif Z["dach_anteil"] < DACH_ABDECKUNG: grund = f"Dach nur zu {Z['dach_anteil']:.0%} gemessen (verlangt {DACH_ABDECKUNG:.0%})"
    elif Z["z_spitze"] < Z["z_traufe"] + 0.2: grund = f"Spitze {Z['z_spitze']} nicht ueber der Traufe {Z['z_traufe']}"
    elif not R_TRAUFE[0] * r_s <= Z["r_traufe"] <= R_TRAUFE[1] * r_s: grund = f"Traufradius {Z['r_traufe']} nicht in {R_TRAUFE} x Schaft {r_s:.2f}"
    return dict(erg, **Z, r_schaft_dach=round(float(r_s), 3), bindende_fotos=bind, gueltig=grund is None, grund=grund)


def dach_block(E):
    """Ergebnis -> Block 'dach' fuer bauteile.kegeldach_teile."""
    return dict(gueltig=bool(E["gueltig"]), grund=E.get("grund"), z_traufe=E["z_traufe"], r_traufe=E["r_traufe"], z_spitze=E["z_spitze"], hoehe=round(E["z_spitze"] - E["z_traufe"], 2),
                neigung_grad=round(math.degrees(math.atan2(E["z_spitze"] - E["z_traufe"], E["r_traufe"])), 1), profil=E["dach_profil"], familie=E["familie"],
                fotos=len(E["fotos"]), einig=len(E["bindende_fotos"]), stuetze=None, r_schaft=E["r_schaft_dach"],
                quelle="tools/rund_aus_huelle.py: Sehstrahl-Huelle aus einseitigen Foto-Silhouetten gegen Himmel (tools/drehkoerper_aus_fotos.py)")


def main(argv=None):
    import cv2, flaeche_ortho as FO, dach_aus_fotos as DA
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--koerper"); ap.add_argument("--uebernehmen", action="store_true"); ap.add_argument("--bild")
    ap.add_argument("--cache"); ap.add_argument("--root"); ap.add_argument("--min-ppm", type=float, default=20.0); ap.add_argument("--roh", help="Silhouetten als JSON (Nachrechnung)")
    ap.add_argument("--achse-frei", action="store_true", help="Achse aus den Silhouetten suchen (Standard: Lage aus Umriss/Wolke, KERNMETHODE 'Wolke nur Lage')")
    a = ap.parse_args(argv)
    if a.root: FO.ROOT = a.root
    od = os.path.dirname(os.path.abspath(a.objekt)); Au = os.path.join(od, "audit"); kp = a.koerper or os.path.join(Au, "koerper_auto.json")
    try: KA = json.load(open(kp))
    except Exception: print("keine", kp); return 3
    rund = [h for h in KA.get("haufen", []) if h.get("form") == "rund" and h.get("kreis") and h.get("angenommen") is not False]
    if not rund: print("kein Rundkandidat in", kp); return 3
    _, cams = FO.kameras_laden(a.objekt); cache = a.cache or os.path.join(Au, "himmel_cache"); rc = 4
    for H in rund:
        k = H["kreis"]; A = np.array([k["x"], k["y"]], float); r0 = float((H.get("umriss") or {}).get("r_schaft") or k["r"]); kz = H["kasten"]
        z_lo = float(kz[2]); z_ob = max(float(kz[5]), float((H.get("umriss") or {}).get("oberkante") or 0.0)); z_hi = z_ob + 3.5 * r0
        zs = np.round(np.arange(z_lo, z_hi + 1e-9, DZ), 2); xr = S_MAX_R * r0 + 0.6
        print(f"{H.get('id')}: Achse {A.round(2).tolist()} r {r0:.2f}, z {z_lo:.1f}..{z_hi:.1f}")
        kand = []; gr = {}
        def grund(g): gr[g] = gr.get(g, 0) + 1
        for nr, (c, pf) in sorted(cams.items()):
            W0, H0 = c.get("bild") or (c["cx"] * 2, c["cy"] * 2)
            C = FO.projektion(np.array([[A[0], A[1], 0.0]]), c)[2]
            if np.hypot(C[0] - A[0], C[1] - A[1]) < 1.5 * r0: grund("Kamera am Koerper"); continue
            az = math.degrees(math.atan2(C[1] - A[1], C[0] - A[0])); q = np.array([math.sin(math.radians(az)), -math.cos(math.radians(az))])
            P_ = np.array([[A[0] + x * q[0], A[1] + x * q[1], z] for x in (-r0, r0) for z in (z_ob - 2.0, z_hi - 1.5 * r0)]); pe, ze, _ = FO.projektion(P_, c)
            if (ze <= 0).any() or (pe[:, 0] < 0).any() or (pe[:, 1] < 0).any() or (pe[:, 0] > W0 - 1).any() or (pe[:, 1] > H0 - 1).any(): grund("Koerper oben nicht im Bild"); continue
            ppm = float(np.linalg.norm(pe[2] - pe[0])) / (2 * r0)
            if ppm < a.min_ppm: grund("zu klein (px/m)"); continue
            kand.append((ppm, az, nr, c, pf, C, q, W0, H0))
        print(f"  Kandidaten {len(kand)}; verworfen {gr}")
        beob = []; gr = {}
        for ppm, az, nr, c, pf, C, q, W0, H0 in kand:
            M_, _ = DA.himmel_laden(dict(name=nr, W0=int(round(W0)), H0=int(round(H0)), foto=pf), cache, nur_cache=True)
            if M_ is None: grund("keine Himmelsmaske"); continue
            im = cv2.imread(pf)
            if im is None: grund("Foto fehlt"); continue
            sb = im.shape[1] / (c["cx"] * 2); sm = M_.shape[1] / float(W0); xs = np.arange(-xr, xr + 1e-9, max(0.01, 0.5 / (ppm * sb)))
            X = np.array([[A[0] + x * q[0], A[1] + x * q[1], z] for z in zs for x in xs]); p, zp, _ = FO.projektion(X, c)
            pb = p * sb; inn = (zp > 0.5) & (pb[:, 0] >= 0) & (pb[:, 1] >= 0) & (pb[:, 0] <= im.shape[1] - 1) & (pb[:, 1] <= im.shape[0] - 1)
            col = cv2.remap(im, pb[:, 0].astype(np.float32).reshape(len(zs), -1), pb[:, 1].astype(np.float32).reshape(len(zs), -1), cv2.INTER_LINEAR,
                            borderMode=cv2.BORDER_REPLICATE).reshape(-1, 3).astype(float)        # Gitter Hoehen x quer (remap: je Achse < 32767)
            col[~inn] = np.nan; pm = np.round(p * sm).astype(int); im_ok = inn & (pm[:, 0] >= 0) & (pm[:, 1] >= 0) & (pm[:, 0] < M_.shape[1]) & (pm[:, 1] < M_.shape[0])
            hm = np.where(im_ok, M_[np.clip(pm[:, 1], 0, M_.shape[0] - 1), np.clip(pm[:, 0], 0, M_.shape[1] - 1)], False)
            del im
            hf = DK.himmelsfarbe(col[inn], hm[inn])
            if hf is None: grund("Himmelsmaske nicht plausibel/zu wenig Himmel"); continue
            sky, T = hf; d = np.linalg.norm(col - sky, axis=1); nrm = 2.0 * T                       # einseitig_halb: > 0,5 = Abstand > T
            D = (d / nrm).reshape(len(zs), len(xs)); HM = hm.reshape(len(zs), len(xs)); IN = inn.reshape(len(zs), len(xs))
            l = np.full(len(zs), -np.inf); r = np.full(len(zs), np.inf)
            for i in range(len(zs)):
                if IN[i, np.argmin(np.abs(xs))]: l[i], r[i] = DK.einseitig_halb(D[i], xs, HM[i])
            n_mess = int((np.isfinite(l) | np.isfinite(r)).sum())
            if n_mess < MIN_ZEILEN: grund("keine Seite gegen Himmel"); continue
            beob.append(dict(C=[float(v) for v in C], az=float(az), A0=A.copy(), zg=zs.copy(), l=l, r=r, nr=nr, ppm=ppm, pf=pf, c=c, q=q, n_mess=n_mess))
        print(f"  Fotos mit Silhouette gegen Himmel: {len(beob)}; verworfen {gr}")
        streu = DK.fotos_streuen([(B["ppm"] * min(1.0, B["n_mess"] / 40.0), B["az"], i) for i, B in enumerate(beob)])
        beob = [beob[t[2]] for t in streu]
        if a.roh: json.dump([dict(nr=B["nr"], C=B["C"], az=B["az"], A0=B["A0"].tolist(), l=[None if np.isnan(v) else float(v) if np.isfinite(v) else str(v) for v in B["l"]],
                                  r=[None if np.isnan(v) else float(v) if np.isfinite(v) else str(v) for v in B["r"]]) for B in beob] + [dict(zs=zs.tolist(), A=A.tolist(), r0=r0)], open(a.roh, "w"))
        E = huelle_messen(beob, A, zs, r0, achse_frei=a.achse_frei)
        E["sektoren"] = sorted({int((B["az"] % 360) // DK.SEKTOR_GRAD) for B in beob if B["nr"] in E["fotos"]})
        print(f"  HUELLE: Achse {E.get('achse')}, Fotos {len(E.get('fotos', []))} (raus {list(E.get('weg', {}))}), Traufe z {E.get('z_traufe')} r {E.get('r_traufe')}, Schaft {E.get('r_schaft')} "
              f"({E.get('schaft_anteil')}), Spitze z {E.get('z_spitze')}, Familie {E.get('familie')}, bindend {len(E.get('bindende_fotos', []))} -> " + ("GUELTIG" if E["gueltig"] else "UNGUELTIG: " + str(E.get("grund"))))
        H["huelle"] = E
        if E["gueltig"]:
            rc = 0
            if a.uebernehmen:
                KD = dach_block(E); H["dach_umriss"] = H.get("dach"); H["dach"] = KD; H["traufe"] = E["z_traufe"]
                H.setdefault("kreis_umriss", dict(H["kreis"])); H["kreis"] = dict(H["kreis"], x=E["achse"][0], y=E["achse"][1])
                H.setdefault("profil_umriss", H.get("profil"))
                if E.get("r_schaft") is not None and E["schaft_anteil"] >= SCHAFT_ANTEIL:
                    # Schaft = Huellenradius des oberen Schafts (vor Himmel), lotrecht (ANNAHME): unten sehen nur wenige Fotos Himmel neben dem Koerper, die Huelle ist dort weit
                    H["profil"] = [[p[0], E["r_schaft"], p[2]] for p in H["profil"]]; H["kreis"]["r"] = E["r_schaft"]; H["schaft_quelle"] = "foto_huelle"
                H["profil"] = [p for p in H["profil"] if p[0] < E["z_traufe"]]               # Schaft endet an der Traufe (vorher: Umriss bis zum Suchende 13,75)
                if len(H["profil"]) < 2: H["profil"] = [[z_lo, H["kreis"]["r"], 0], [E["z_traufe"] - 0.3, H["kreis"]["r"], 0]]
        if a.bild:
            try: bild(beob, E, a.bild.replace(".jpg", f"_{H.get('id', 'r')}.jpg") if len(rund) > 1 else a.bild)
            except Exception as e_: print("  Bild fehlgeschlagen:", e_)
    json.dump(KA, open(kp, "w"), indent=1, ensure_ascii=False); print("->", kp)
    return rc


def bild(beob, E, aus, n=6):
    """Pruefbild: bis 6 Fotos (verschiedene Blickrichtungen, bindende zuerst) mit gemessener Silhouette (gelb Punkte) und Huellen-Umriss (gruen, vorhergesagt aus r(z)),
    Traufe/Spitze als Querstriche (blau/rot); rechts das Profil r(z)."""
    import cv2, flaeche_ortho as FO
    if not beob or not E.get("profil"): return
    zs = np.array([p[0] for p in E["profil"]]); rr = np.array([np.nan if p[1] is None else p[1] for p in E["profil"]]); A = np.array(E["achse"], float); ok = np.isfinite(rr)
    gb = set(E.get("bindende_fotos") or []); o = sorted(beob, key=lambda B: (B["nr"] not in gb, -B["ppm"])); pick = []
    for B in o:
        if len(pick) < n and all(abs((B["az"] - P["az"] + 180) % 360 - 180) >= 15 for P in pick): pick.append(B)
    kach = []
    for B in pick:
        im = cv2.imread(B["pf"]); c = B["c"]; s = im.shape[1] / (c["cx"] * 2); q = np.array([math.sin(math.radians(B["az"])), -math.cos(math.radians(B["az"]))]); lw = max(2, im.shape[1] // 900)
        P_ = lambda x, z: (FO.projektion(np.array([[B["A0"][0] + x * q[0], B["A0"][1] + x * q[1], z]]), c)[0] * s)[0].astype(int)
        for z, l, r in zip(B["zg"], B["l"], B["r"]):
            for v in (l, r):
                if np.isfinite(v): cv2.circle(im, tuple(P_(v, z)), lw, (0, 255, 255), -1)
        if ok.sum() > 2:
            lp, rp = DK.silhouette_vorhersage(dict(B, A0=B["A0"]), A, zs[ok], rr[ok], DK.querschnitt_einheit())
            for v_ in (lp, rp):
                pts = [P_(v, z) for z, v in zip(B["zg"], v_) if np.isfinite(v)]
                if len(pts) > 1: cv2.polylines(im, [np.array(pts).reshape(-1, 1, 2)], False, (0, 200, 0), lw)
        for zk, col in ((E.get("z_traufe"), (255, 128, 0)), (E.get("z_spitze"), (0, 0, 255))):
            if zk is not None: cv2.line(im, tuple(P_(-2.2, zk)), tuple(P_(2.2, zk)), col, lw)
        z0 = E.get("z_traufe") or float(zs[ok].min()) if ok.any() else float(zs[0])
        a0 = P_(0, z0 - 4.0); a1 = P_(0, (E.get("z_spitze") or z0) + 1.5); h = max(abs(a0[1] - a1[1]), 50)
        k = im[max(0, min(a0[1], a1[1])):max(a0[1], a1[1]), max(0, a0[0] - h // 2):a0[0] + h // 2]
        if k.size == 0: continue
        k = cv2.resize(k, (max(1, int(k.shape[1] * 420 / k.shape[0])), 420)); cv2.putText(k, f"{B['nr'][-16:]} az {B['az']:.0f}", (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2); kach.append(k)
    pr = np.full((420, 260, 3), 255, np.uint8)
    if ok.any():
        za, zb = float(zs[ok].min()), float(zs[ok].max()); rm = float(np.nanmax(rr)) * 1.2 + 1e-3
        for z, v in zip(zs[ok], rr[ok]): cv2.circle(pr, (int(20 + v / rm * 220), int(400 - (z - za) / max(zb - za, 1e-6) * 380)), 2, (0, 140, 0), -1)
        cv2.putText(pr, f"Traufe {E.get('z_traufe')} Spitze {E.get('z_spitze')}", (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
        cv2.putText(pr, f"{E.get('familie')} gueltig {E.get('gueltig')}", (4, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
    cv2.imwrite(aus, np.hstack(kach + [pr]), [cv2.IMWRITE_JPEG_QUALITY, 85]); print("  Bild:", aus)


if __name__ == "__main__": sys.exit(main())
