#!/usr/bin/env python3
"""sfm_seiten_vorstufe.py - Vorstufe 'seiten' der SfM (tools/iphone_sfm.py ruft die Funktionen hier auf; kein eigenes Kommandozeilenwerkzeug).

Anlass 21.11.2026 (Martinstor, 4. Seitenverwechslung, 8,4 h Mapper umsonst): Masken, Seitenerkennung und DB-Bereinigung gab es als Werkzeuge, die Kette rief sie nicht auf.
Die von Hand bewiesene Folge (modelle/LOGBUCH_SCHWABENTOR_KETTE_2026-11-21.md, Nachtraege 10:25-11:29) laeuft hier VOR dem Mapper:
  1. masken_rechnen()   tools/handy_masken.py (GPU, Personen/Fahrzeuge/Baeume) -> <w>/masken/<serie>/<bildname>.png; nur fuer Bilder OHNE aktuelle Maske.
  2. masken_colmap()    Verknuepfungen <w>/masken_colmap/<bild mit Endung>.png fuer COLMAP ImageReader.mask_path: die Merkmalssuche laesst den Vordergrund gleich weg.
     masken_filter()    Rueckfall fuer VORHANDENE Datenbanken ohne Masken in der Merkmalssuche: tools/db_masken_filter.py -> <w>/db_maske.db.
  3. seiten()           tools/seiten_erkennen.py --streng --masken -> <w>/seiten.json + <w>/db_seiten.db (rc 3 = Verwechslung gefunden und bereinigt, kein Fehler).
  4. bereinigen()       tools/sfm_db_variante.py --priors loeschen --kamera-je-clip (+ Panoramen raus) -> <w>/db_mapper.db fuer JEDEN Mapper-Weg
                        (Befund: Ketten-DB Martinstor 2107 Bilder = 2107 Kameras, EXIF-Brennweiten bis 2185 x Bildbreite; die Bereinigung lief nur im Konsens-Weg).
  5. teile_im_modell()  nach dem Mapper: welcher Bildteil (Seite) steht mit wie vielen Bildern in welchem Modell - eine fehlende Seite wird GEMELDET, nie still weggelassen.
Zwischenstaende werden wiederverwendet (Stand-Datei je Schritt mit Groesse + Zeit der Eingaben). Abschalten: RCPARK_SEITEN=0 (iphone_sfm.py).
Mapper je Seite + dichte Wolke je Seite + tools/seiten_vereinen.py: tools/sfm_seiten_modelle.py (iphone_sfm.py ruft es bei mehreren Bildteilen auf).
Fester Test: tools/test_seiten_kette.py (ohne GPU, Unterprozesse durch Attrappen ersetzt)."""
import os, sys, json, subprocess

T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T); from pfade import PY; PY_SEG = PY["seg"]
BILD_ENDUNGEN = (".jpg", ".jpeg", ".png")


def bilder(img):
    return sorted(f for f in os.listdir(img) if os.path.isfile(os.path.join(img, f)))


def _stand(*pfade):
    """Fingerabdruck der Eingaben (Groesse + Aenderungszeit): gleicher Stand = Zwischenergebnis darf wiederverwendet werden."""
    return [[os.path.abspath(p), os.path.getsize(p), int(os.path.getmtime(p))] if os.path.exists(p) else [os.path.abspath(p), None, None] for p in pfade]


def _aktuell(standdatei, stand, *ausgaben):
    try: return all(os.path.exists(x) for x in ausgaben) and json.load(open(standdatei)) == stand
    except Exception: return False


def masken_index(roh):
    """{Bildname ohne Endung: Maskenpfad} - handy_masken.py legt <roh>/<serie>/<name ohne Endung>.png ab (beliebig tief)."""
    M = {}
    for w_, _, fs in os.walk(roh) if os.path.isdir(roh) else []:
        for f in fs:
            if f.endswith(".png"): M[f[:-4]] = os.path.join(w_, f)
    return M


def masken_fehlend(img, roh):
    """Bilder ohne Maske oder mit Maske, die aelter ist als das Bild."""
    M = masken_index(roh); F = []
    for f in bilder(img):
        m = M.get(os.path.splitext(f)[0])
        if m is None or os.path.getmtime(m) < os.path.getmtime(os.path.join(img, f)): F.append(f)
    return F


def masken_rechnen(img, w, lauf=subprocess.run):
    """Schritt 1. -> dict(ordner, bilder, neu, ohne_maske). Rechnet nur die fehlenden Masken (Verknuepfungsordner <w>/masken_eingang), alle anderen bleiben.
    RCPARK_MASKEN_BATCH (Standard 2: 21.11.2026 Batch 4 = OOM-Rueckfaelle auf der 8-GB-Karte, Batch 2 Spitze 6,9 GiB, 2042 Bilder 13 min)."""
    roh = os.path.join(w, "masken"); alle = bilder(img); fehlt = masken_fehlend(img, roh); neu = 0
    if fehlt:
        quelle = img
        if len(fehlt) < len(alle):                                     # nur den Rest rechnen: Verknuepfungen der fehlenden Bilder in einen eigenen Eingangsordner
            quelle = os.path.join(w, "masken_eingang"); os.makedirs(quelle, exist_ok=True)
            for f in os.listdir(quelle):
                if os.path.islink(os.path.join(quelle, f)): os.unlink(os.path.join(quelle, f))
            for f in fehlt: os.symlink(os.path.abspath(os.path.join(img, f)), os.path.join(quelle, f))
        print(f"SEITEN 1/3 Masken: {len(fehlt)} von {len(alle)} Bildern ohne aktuelle Maske -> tools/handy_masken.py (GPU)", flush=True)
        r = lauf([PY_SEG, "-W", "ignore", "-I", os.path.join(T, "handy_masken.py"), quelle, "--ausgabe", roh, "--batch", os.environ.get("RCPARK_MASKEN_BATCH", "2")], check=False)
        if r.returncode != 0: raise SystemExit(f"SEITEN-VORSTUFE: Masken gescheitert (rc {r.returncode}, tools/handy_masken.py) - Mapper NICHT gestartet (ohne Masken verklebt eine Person im Vordergrund die Seiten). Bewusst ohne Vorstufe: RCPARK_SEITEN=0")
        neu = len(fehlt) - len(masken_fehlend(img, roh))
    ohne = masken_fehlend(img, roh)
    if ohne: print(f"ACHTUNG Masken: {len(ohne)} Bilder weiterhin OHNE Maske (nicht lesbar oder unbekannte Endung), z. B. {', '.join(ohne[:3])} - sie gehen unmaskiert in die Merkmalssuche", flush=True)
    else: print(f"SEITEN 1/3 Masken: alle {len(alle)} Bilder mit aktueller Maske ({neu} neu gerechnet, {len(alle) - neu} wiederverwendet)", flush=True)
    return dict(ordner=roh, bilder=len(alle), neu=neu, ohne_maske=len(ohne))


def masken_colmap(img, roh, ziel):
    """Schritt 2 (Vorzugsweg). COLMAP sucht die Maske unter <mask_path>/<Bildname MIT Endung>.png in voller Bildgroesse (handy_masken schreibt volle Groesse, aber <Name ohne Endung>.png)
    -> Verknuepfungen anlegen. Rueckgabe: (Zahl der Bilder mit Maske, Zahl der Bilder mit LEERER Maske).
    PFLICHT (Mini-Probe 21.11.2026, pycolmap 4.2.1): ein Bild OHNE Maskendatei wird von COLMAP UEBERSPRUNGEN ('MASK_ERROR: Failed to read the mask file') und fehlt dann in der
    Datenbank -> jedes Bild ohne Maske bekommt eine leere (ganz weisse) Maske in Bildgroesse; nur ein unlesbares Bild bleibt ohne (COLMAP koennte es ohnehin nicht lesen)."""
    os.makedirs(ziel, exist_ok=True); M = masken_index(roh); n = leer = 0
    for f in bilder(img):
        m = M.get(os.path.splitext(f)[0]); z = os.path.join(ziel, f + ".png")
        if m is None:
            if os.path.islink(z): os.unlink(z)
            if not os.path.exists(z):
                import cv2, numpy as np
                b = cv2.imread(os.path.join(img, f), cv2.IMREAD_GRAYSCALE)
                if b is None: continue
                cv2.imwrite(z, np.full(b.shape[:2], 255, np.uint8))
            leer += 1; continue
        n += 1
        if os.path.islink(z) and os.path.realpath(z) == os.path.realpath(m): continue
        if os.path.lexists(z): os.unlink(z)                               # alte Verknuepfung oder eigene leere Maske von frueher
        os.symlink(os.path.abspath(m), z)
    return n, leer


def masken_filter(db, roh, w, lauf=subprocess.run):
    """Schritt 2 (Rueckfall fuer vorhandene Datenbanken): Vordergrund-Zuordnungen aus den bestaetigten Paaren nehmen -> <w>/db_maske.db. Wiederverwendung bei gleichem Stand der Eingangs-DB."""
    aus = os.path.join(w, "db_maske.db"); sd = aus + ".stand.json"; st = _stand(db) + [len(masken_index(roh))]
    if _aktuell(sd, st, aus, aus + ".masken.json"): print("SEITEN 2/3 Maskenfilter: wiederverwendet", aus, flush=True); return aus
    r = lauf([sys.executable, "-I", os.path.join(T, "db_masken_filter.py"), db, roh, "--aus", aus], check=False)
    if r.returncode != 0: raise SystemExit(f"SEITEN-VORSTUFE: Maskenfilter gescheitert (rc {r.returncode}, tools/db_masken_filter.py) - Mapper NICHT gestartet. Bewusst ohne Vorstufe: RCPARK_SEITEN=0")
    json.dump(st, open(sd, "w")); return aus


def seiten_lesen(sj, n_bilder=None):
    """seiten.json -> Kurzbericht: Bildteile (Zahl, Bilder je Teil), fremde Bilder, Urteile des Paar-Pruefers. 'verwechselt_pruefer' = Gruppenpaare, die der Pruefer (oder GPS)
    ausdruecklich als verschiedene, aehnliche Waende beurteilt hat - nur das ist ein BELEG fuer eine Verwechslungsgefahr (--streng loescht auch Ungeprueftes)."""
    d = json.load(open(sj)); V = d.get("verbindungen", [])
    return dict(teile=[t["bilder"] for t in d.get("seiten", [])], fremd=len(d.get("fremd", [])), gruppen=len(d.get("groessen", [])), bilder=n_bilder if n_bilder is not None else len(d.get("gemeinschaft", {})),
                verwechselt_pruefer=sum(1 for v in V if v.get("urteil") == "verwechselt"), echt=sum(1 for v in V if v.get("urteil") == "echt"), unklar=sum(1 for v in V if v.get("urteil") == "unklar"),
                geloeschte_paare=d.get("geloeschte_paare"))


def seiten(db, img, w, roh, lauf=subprocess.run, modus="1"):
    """Schritt 3. -> (Datenbank fuer den Mapper, Bericht). Wiederverwendung, wenn Eingangs-DB und Maskenzahl unveraendert sind.
    GUELTIGKEITS-GUARD (ANNAHME, nicht am Lauf gemessen): --streng loescht ALLE Verbindungen zwischen Bildgruppen, die der Pruefer nicht als 'echt' bestaetigt hat - auch die
    ungeprueften kleiner Gruppen (< 12 Bilder). Hat der Pruefer KEIN Gruppenpaar als 'verwechselt' beurteilt, gibt es keinen Beleg fuer aehnliche Seiten; dann wuerde --streng
    einen kleinen Fotosatz nur zerstueckeln -> der Mapper rechnet auf der Eingangs-DB weiter (seiten.json bleibt fuer das Blick-Tor). modus 'immer' (RCPARK_SEITEN=immer) nimmt
    db_seiten.db in jedem Fall."""
    sj = os.path.join(w, "seiten.json"); dbs = os.path.join(w, "db_seiten.db"); sd = sj + ".stand.json"; st = _stand(db) + [len(masken_index(roh))]; alle = bilder(img)
    if _aktuell(sd, st, sj, dbs): print("SEITEN 3/3 Seitenerkennung: wiederverwendet", sj, flush=True)
    else:
        # Objektfotos heissen im Sammelordner 'eigen__...' (tools/fotos_sammeln.py); Teile ohne Objektfoto gelten als FREMD und verlieren alle Paare. Ein Ordner ohne solche Namen
        # (iphone_sfm.py direkt auf einem Fotoordner) haette danach KEIN Paar mehr -> dann zaehlt jedes Bild als Objektfoto.
        ref = [] if any(f.startswith("eigen__") for f in alle) else ["--referenz", ""]
        r = lauf([PY_SEG, "-W", "ignore", "-I", os.path.join(T, "seiten_erkennen.py"), db, img, "--aus", sj, "--db-aus", dbs, "--streng", "--masken", roh] + ref, check=False)
        if r.returncode not in (0, 3) or not os.path.isfile(sj) or not os.path.isfile(dbs):
            raise SystemExit(f"SEITEN-VORSTUFE: Seitenerkennung gescheitert (rc {r.returncode}, tools/seiten_erkennen.py) - Mapper NICHT gestartet (ohne sie klebt der Mapper aehnliche Seiten aufeinander). Bewusst ohne Vorstufe: RCPARK_SEITEN=0")
        json.dump(st, open(sd, "w"))
    b = seiten_lesen(sj, len(alle)); b["seiten_json"] = sj
    if b["verwechselt_pruefer"] == 0 and modus != "immer":
        b["db"] = db; b["hinweis"] = "kein Gruppenpaar als 'verwechselt' beurteilt - Mapper rechnet auf der ungeteilten Datenbank (Guard gegen Zerstueckeln kleiner Fotosaetze)"
    else: b["db"] = dbs
    b["getrennt"] = b["db"] == dbs and len(b["teile"]) > 1
    print(f"SEITEN 3/3: {b['gruppen']} Bildgruppen, Pruefer: {b['verwechselt_pruefer']} verwechselt / {b['echt']} echt / {b['unklar']} unklar; {len(b['teile'])} Bildteil(e) mit Objektfotos: "
          + ", ".join(f"Teil {i} {n} Bilder" for i, n in enumerate(b["teile"][:8])) + f"; {b['fremd']} fremde Bilder; Mapper auf {os.path.basename(b['db'])}", flush=True)
    if b.get("hinweis"): print("SEITEN HINWEIS:", b["hinweis"], flush=True)
    if b["getrennt"]:
        print(f"ACHTUNG SEITEN GETRENNT: {len(b['teile'])} Bildteile ohne echte Verbindung ({', '.join(str(n) for n in b['teile'][:8])} Bilder) - der Mapper kann sie NICHT in ein Modell legen. "
              "Weiter mit tools/sfm_seiten_modelle.py (je Teil ein Modell + dichte Wolke, dann tools/seiten_vereinen.py; RCPARK_SEITEN_MODELLE=0 schaltet das ab); was in sparse/0 steht, meldet 'SEITEN IM MODELL'.", flush=True)
    return b["db"], b


def bereinigen(db, w, lauf=subprocess.run):
    """Schritt 4: DB-Kopie fuer den Mapper (Kamera je Videoclip, EXIF-Prioren weg, Panoramen '_360.' raus) - dieselbe Bereinigung wie tools/global_mapper_konsens.py, aber fuer JEDEN Weg.
    Scheitert sie, rechnet der Mapper auf der unbereinigten DB weiter (gemeldet) - das ist der Stand vor dem 21.11., kein neuer Schaden."""
    aus = os.path.join(w, "db_mapper.db"); sd = aus + ".stand.json"; st = _stand(db)
    if _aktuell(sd, st, aus): print("DB-Bereinigung: wiederverwendet", aus, flush=True); return aus
    r = lauf([sys.executable, "-I", os.path.join(T, "sfm_db_variante.py"), db, aus, "--priors", "loeschen", "--kamera-je-clip", "--loeschen", r"_360\."], check=False)
    if r.returncode != 0 or not os.path.isfile(aus):
        print(f"ACHTUNG DB-Bereinigung gescheitert (rc {r.returncode}, tools/sfm_db_variante.py) - Mapper rechnet auf der UNBEREINIGTEN Datenbank (jedes Videobild eigene Kamera, EXIF-Prioren ungeprueft)", flush=True); return db
    json.dump(st, open(sd, "w")); return aus


def teile_im_modell(sj, modelle):
    """modelle = {Modellname: Menge der Bildnamen im Modell} -> je Bildteil aus seiten.json: Bildzahl und wie viele davon in welchem Modell stehen.
    Liefert (Liste, Meldungen); eine Meldung je Teil >= 10 Bilder, der im ersten Modell (das die Kette weiterverwendet) fehlt oder mit einem anderen Teil zusammen im selben Modell steht."""
    d = json.load(open(sj)); g = {os.path.basename(k): v for k, v in d.get("gemeinschaft", {}).items()}; L = []; meld = []
    erstes = sorted(modelle)[0] if modelle else None
    for i, t in enumerate(d.get("seiten", [])):
        gs = set(t["gruppen"]); namen = {n for n, k in g.items() if k in gs}
        L.append(dict(teil=i, bilder=len(namen), im_modell={m: len(namen & {os.path.basename(x) for x in N}) for m, N in modelle.items()}))
    gross = [t for t in L if t["bilder"] >= 10]
    for t in gross:
        if erstes is not None and t["im_modell"].get(erstes, 0) == 0:
            wo = {m: n for m, n in t["im_modell"].items() if n}; meld.append(f"Teil {t['teil']} ({t['bilder']} Bilder) FEHLT im Modell {erstes}" + (f" (steht in {wo})" if wo else " (in keinem Modell)"))
    if erstes is not None and len(d.get("seiten", [])) > 1:
        drin = [t for t in gross if t["im_modell"].get(erstes, 0) >= 5]
        if len(drin) > 1: meld.append(f"Modell {erstes} enthaelt {len(drin)} Bildteile ohne echte Verbindung (" + ", ".join(f"Teil {t['teil']}: {t['im_modell'][erstes]}" for t in drin) + " Bilder) - Verklebung pruefen: tools/seiten_blick_tor.py")
    return L, meld
