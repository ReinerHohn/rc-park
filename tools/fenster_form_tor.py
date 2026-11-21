#!/usr/bin/env python3
"""fenster_form_tor.py - FORM-TOR fuer gebaute Fenster/Nischen: stimmt die Formfamilie, die der Generator baut, mit den EINZELFOTOS ueberein? (21.11.2026 spaet)

Anlass (Nutzer "Das ist noch nicht gut", Schwabentor f00, audit/neben_eigen__IMG_20261106_113231.jpg, Lauf 1121s): im Foto zwei Rundbogenfenster in Rundbogennischen,
im Modell ein Rechteck und ein flacher Bogen. hand_vergleich meldete 'rundbogenfenster PASST' nur ueber Sohlbankhoehe und Anzahl - die FORM prueft niemand.
Methode (KERNMETHODE: Form aus Fotokanten, Formfamilie aus >= 3 Fotos; Erkennen = nur Zone):
  1. Je Eintrag der Fensterliste (fenster_auto.json bzw. fenster_bau.json = was der Generator baut): gebaute Form = bogen.form ('gerade' = Rechteck),
     bei 'nische' zusaetzlich die Nische (inneres Fenster ausgespart).
  2. LAGE (nur Bericht): Umriss im fusionierten 1-cm-Wandbild aus den Kanten (nischen_fenster.form_aus_kanten, Zone = gebauter Kasten) -> lage_abweichung.
  3. FORM: je Einzelfoto-Ortho (ortho_fNN_einzeln/) eigene Umrisssuche in derselben Zone, deren Formfamilie (einfachste im Gleichstand) = eine Stimme.
  4. URTEIL je Umriss: PASST = gebaute Familie hat die meisten Stimmen und >= 3; FALSCH = eine andere Familie hat >= 3 und mehr Stimmen als die gebaute;
     UNBESTIMMT = weniger als 3 Fotos stimmen ueberhaupt (kein Urteil ohne Belege). Zusaetzlich LAGE_ABWEICHUNG (m) zwischen gebautem und gefundenem Umriss.
Aufruf: fenster_form_tor.py <fenster.json> <fassade_fein-ordner> [--aus audit/fenster_form_tor.json] [--nur f00]
rc 0 = kein FALSCH, 2 = mindestens ein Umriss FALSCH (Bericht trotzdem geschrieben), 3 = nichts pruefbar.
"""
import sys, os, json, argparse, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nischen_fenster as NF



def vorzeichen_p(a, g):
    """Einseitiger Vorzeichentest: Wahrscheinlichkeit, dass a oder mehr von a+g Stimmen bei Gleichstand (p = 1/2) auf die andere Familie fallen."""
    from math import comb
    n = a + g; return sum(comb(n, i) for i in range(a, n + 1)) / 2.0 ** n if n else 1.0


def urteil(gebaut, st, min_fotos=NF.MIN_FOTOS, p_max=0.2):
    """Urteil aus gebauter Familie und Stimmen {form: n}.
    22.11.2026 (Kettenlauf 1121v, f00 rechte Nische: korb 7 / rund 6 / stich 1 -> FALSCH -> hand_vergleich 'rundbogenfenster FALSCH' trotz rund/rund):
    eine knappe Mehrheit benachbarter Familien ist kein Beleg. FALSCH nur, wenn die andere Familie die gebaute im Vorzeichentest schlaegt (p < p_max = 0,2: 3:0 und 4:1 reichen, 7:6 und 8:5 nicht),
    sonst UNBESTIMMT (Gleichstand, nicht belegt)."""
    n = sum(st.values()); g = st.get(gebaut, 0); andere = {f: v for f, v in st.items() if f != gebaut}
    best_a = max(andere.values()) if andere else 0
    if best_a >= min_fotos and best_a > g and vorzeichen_p(best_a, g) < p_max: return "FALSCH", max(andere, key=andere.get)
    if g >= min_fotos and g >= best_a: return "PASST", gebaut
    return "UNBESTIMMT", (max(st, key=st.get) if st else None)


def pruefe_umriss(B, bilder, o, innen=None, kante=4.0, anteil_min=0.5):
    """Ein gebauter Umriss o (u0,u1,z0,z1,bogen?) gegen die Einzelfotos: JE FOTO eigene Umrisssuche (nischen_fenster.form_aus_kanten, Zone = gebauter Kasten) mit
    eigener Formfamilie = eine Stimme. Feste Lage je Foto taugt nicht als Tor: 5-10 cm Lagefehler eines Erkennerkastens machen am 0,6-m-Fenster aus Rund 'gerade'
    (gemessen Schwabentor f00, 1121s). Liefert dict(gebaut, stimmen, urteil, fotos_sagen, lage_wandbild, lage_abweichung)."""
    gebaut = (o.get("bogen") or {}).get("form", "gerade"); K = (o["u0"], o["u1"], o["z0"], o["z1"])
    r = NF.form_aus_kanten(B, K, innen=innen, anteil_min=anteil_min, kante=kante) if B is not None else dict(fehler="kein Wandbild")
    st, je = NF.form_fotos(bilder, K, innen, kante, anteil_min)
    u, f = urteil(gebaut, st); lw = None if "fehler" in r else [r[k] for k in ("u0", "u1", "z0", "z1")]
    return dict(gebaut=gebaut, stimmen=st, fotos=len(je), urteil=u, fotos_sagen=f, lage_wandbild=lw,
                lage_abweichung=None if lw is None else round(max(abs(r[k] - o[k]) for k in ("u0", "u1", "z0", "z1")), 3), wandbild=r.get("fehler", "Umriss gefunden"))


def main():
    import cv2
    ap = argparse.ArgumentParser(); ap.add_argument("fenster"); ap.add_argument("fein"); ap.add_argument("--aus"); ap.add_argument("--nur", nargs="*")
    ap.add_argument("--kante", type=float, default=4.0); ap.add_argument("--anteil_min", type=float, default=0.5)
    a = ap.parse_args()
    aus = a.aus or os.path.join(os.path.dirname(os.path.abspath(a.fenster)), "fenster_form_tor.json")
    J = json.load(open(a.fenster)); FF = {F["id"]: F for F in json.load(open(os.path.join(a.fein, "fassaden.json")))["fassaden"]}
    bericht = {}; n_falsch = n_gep = 0
    for fid, F in J.items():
        if not isinstance(F, dict) or not F.get("fenster") or (a.nur and fid not in a.nur): continue
        png = os.path.join(a.fein, f"ortho_{fid}.png")
        if fid not in FF or not os.path.exists(png): bericht[fid] = "kein feines Wandbild"; continue
        rs = FF[fid]["raster"]; B = NF.Bild(cv2.imread(png, cv2.IMREAD_GRAYSCALE), rs["u0"], rs["z1"], rs["zelle"]); L = []
        for q in F["fenster"]:
            N = q.get("nische"); A_ = N or q
            bil = NF.einzelbilder(a.fein, fid, (rs["u0"], rs["z1"], rs["zelle"]), (A_["u0"], A_["u1"], A_["z0"], A_["z1"]))
            e = dict(kasten=[q["u0"], q["u1"], q["z0"], q["z1"]], fenster=pruefe_umriss(B, bil, q, kante=a.kante, anteil_min=a.anteil_min))
            if N: e["nische"] = pruefe_umriss(B, bil, N, innen=(q["u0"], q["u1"], q["z0"], q["z1"]), kante=a.kante, anteil_min=a.anteil_min)
            us = [e[k]["urteil"] for k in ("fenster", "nische") if k in e]
            e["urteil"] = "FALSCH" if "FALSCH" in us else "PASST" if all(u == "PASST" for u in us) else "UNBESTIMMT"
            n_falsch += e["urteil"] == "FALSCH"; n_gep += 1; L.append(e)
            print(f"{fid} u {q['u0']:+.2f}..{q['u1']:+.2f} z {q['z0']:.2f}: {e['urteil']:10s} " + "; ".join(
                f"{k} gebaut {e[k]['gebaut']}, Fotos {e[k]['stimmen']}" for k in ("fenster", "nische") if k in e))
        bericht[fid] = L
    json.dump(dict(fenster=os.path.abspath(a.fenster), falsch=n_falsch, geprueft=n_gep, fassaden=bericht), open(aus, "w"), indent=1, ensure_ascii=False)
    print(f"FENSTER-FORM-TOR: {n_gep} geprueft, {n_falsch} FALSCH -> {aus}")
    return 3 if not n_gep else 2 if n_falsch else 0


if __name__ == "__main__": sys.exit(main())
