#!/usr/bin/env python3
"""lizenz_register.py - JEDES Bild nach Lizenzklasse ordnen, damit spaeter (Veroeffentlichung/Verkauf) sichtbar ist, was erlaubt ist und was nicht. Zentrales Modul der Pipeline.

Klassen (ANNAHME: Einordnung nach dem Lizenztext; keine Rechtsberatung, vor Veroeffentlichung am Original pruefen - modelle/LIZENZ_WERKZEUGE.md):
  frei               CC0 / Public domain / gemeinfrei                        -> Pixel im Produkt: ja
  frei_namensnennung CC BY (alle Versionen)                                  -> ja, Urheber nennen
  frei_sharealike    CC BY-SA                                                -> bedingt: Ableitung nur unter gleicher Lizenz; als Messvorlage ohne Bild im Produkt (UNVERIFIZIERT fuer Texturen)
  nc                 NonCommercial (CC BY-NC...), Mapillary (Projektregel)   -> nein (nur private Messvorlage/Vorschau)
  unfrei             urheberrechtlich geschuetzt (YouTube-Standardlizenz u. a.) -> nein (nur private Messvorlage/Vorschau)
  unklar             Text fehlt oder nicht erkannt (z. B. nur 'Attribution')  -> nein, bis geklaert
Quellen (je Objekt): alle manifest.json neben dem Fotoordner (fotos, commons_neu, fotos_eingang, mly_fotos ... ; Dubletten ueber die URL), Videos aus objekt.json video_stufe.clips (= unfrei).
Ausgabe: modelle/<objekt>/LIZENZ_BILDER.json + LIZENZ_BILDER.md (AUTOMATISCH erzeugt, nicht von Hand schreiben), je Bild: Quelle, URL, Urheber, Lizenztext, Klasse, Produkt-Pixel ja/nein/bedingt, Auflage, Verwendung (Netz/Kamera).
  python3 -I tools/lizenz_register.py modelle/<objekt>/objekt.json [--produkt-pruefen]
--produkt-pruefen: Exit 1, wenn ein im Modell GENUTZTES Bild (SfM-Liste oder Kamera in messprotokoll/K-*.json) nicht 'frei*' ist.
Import: klasse(text) -> Klasse; produkt(klasse) -> (ja|bedingt|nein, Auflage); foto_klassen(objekt.json) -> {foto-nr: klasse}.
"""
import sys, os, re, json, glob, html, collections

PRODUKT = {"frei": ("ja", ""), "frei_namensnennung": ("ja", "Urheber nennen"),
           "frei_sharealike": ("bedingt", "Ableitung nur unter gleicher Lizenz (ShareAlike); als Messvorlage ohne Bild im Produkt; Textur im Produkt rechtlich pruefen"),
           "nc": ("nein", "nur nichtkommerziell: private Messvorlage/Vorschau"), "unfrei": ("nein", "urheberrechtlich geschuetzt: private Messvorlage/Vorschau"),
           "unklar": ("nein", "Lizenz fehlt oder nicht erkannt: erst klaeren")}
REIHENFOLGE = ["frei", "frei_namensnennung", "frei_sharealike", "nc", "unfrei", "unklar"]

def klasse(text, quelle=""):
    t = (str(text or "") + " " + str(quelle or "")).lower()
    if not t.strip(): return "unklar"
    if "mapillary" in t: return "nc"                                             # Projektregel (LIZENZ_WERKZEUGE.md): CC BY-NC-SA behandelt
    if re.search(r"(^|[^a-z])nc([^a-z]|$)|noncommercial|non-commercial|nichtkommerz", t): return "nc"
    if re.search(r"youtube|all rights|alle rechte|urheberrecht|standard-?lizenz|copyright|proprietaer|proprietary", t): return "unfrei"
    if re.search(r"cc0|public domain|gemeinfrei|publicdomain|\bpd\b", t): return "frei"
    if re.search(r"cc[ -]?by[ -]?sa|sharealike|share-alike", t): return "frei_sharealike"
    if re.search(r"cc[ -]?by(?![a-z-])", t): return "frei_namensnennung"
    return "unklar"

def produkt(kl): return PRODUKT.get(kl, PRODUKT["unklar"])

def _bild_liste(root, obj):
    """[(manifest-ordner, eintrag)] aus allen manifest.json neben dem Fotoordner; Dubletten ueber die URL entfernt."""
    fd = os.path.realpath(os.path.join(root, obj["fotos_dir"])); eltern = os.path.dirname(fd); seen = set(); out = []
    pfade = [os.path.join(fd, "manifest.json")] + sorted(glob.glob(os.path.join(eltern, "*", "manifest.json")))
    for p in pfade:
        if not os.path.exists(p) or any(p == q[0] for q in out if False): continue
        try: d = json.load(open(p)); I = d["images"] if isinstance(d, dict) and "images" in d else d
        except Exception: continue
        if isinstance(d, dict) and "views" in d:                                   # Mapillary-Manifest (mapillary_rip.py): Lizenz laut Projektregel nc
            I = [dict(m, license="Mapillary (CC BY-NC-SA laut Projektregel)", url="https://www.mapillary.com/app/?pKey=%s" % m.get("mapillary_id"), artist="Mapillary-Beitragende") for m in d["views"] if isinstance(m, dict)]
        if not isinstance(I, list): continue
        for m in I:
            if not isinstance(m, dict): continue
            key = re.sub(r"[?&]utm_[^&]*", "", (m.get("url") or "")) or (os.path.basename(os.path.dirname(p)) + "/" + str(m.get("file")))
            if key in seen: continue
            seen.add(key); out.append((os.path.basename(os.path.dirname(p)), m))
    return out

def foto_klassen(objp):
    objp = os.path.abspath(objp); obj = json.load(open(objp)); root = os.path.dirname(os.path.dirname(os.path.dirname(objp))); res = {}
    fd = os.path.realpath(os.path.join(root, obj["fotos_dir"]))
    try: M = json.load(open(os.path.join(fd, "manifest.json")))["images"]
    except Exception: M = []
    for m in M:
        nr = str(m.get("file", ""))[:3]
        if nr.isdigit(): res[nr] = klasse(m.get("license"), m.get("url"))
    return res

def main():
    a = sys.argv[1:]; objp = os.path.abspath(a[0]); obj = json.load(open(objp)); od = os.path.dirname(objp); root = os.path.dirname(os.path.dirname(od)); pruefen = "--produkt-pruefen" in a
    sfm_nrs = set(); [sfm_nrs.update(v) for v in (obj.get("sfm") or {}).values() if isinstance(v, list)]
    kam = set()
    for p in glob.glob(os.path.join(od, "messprotokoll", "K-*.json")):
        try:
            if "kamera" in json.load(open(p)): kam.add(os.path.basename(p)[2:5])
        except Exception: pass
    eintraege = []
    for quelle, m in _bild_liste(root, obj):
        nr = str(m.get("file", ""))[:3]; nr = nr if (quelle == os.path.basename(os.path.realpath(os.path.join(root, obj["fotos_dir"]))) and nr.isdigit()) else None
        kl = klasse(m.get("license"), m.get("url")); pr, auf = produkt(kl)
        eintraege.append(dict(art="foto", quelle=quelle, foto=nr, datei=m.get("file"), titel=m.get("title"), url=re.sub(r"[?&]utm_[^&]*", "", (m.get("url") or "")), urheber=re.sub(r"<[^>]+>", "", html.unescape(str(m.get("artist") or ""))).strip(),
                              lizenz_text=m.get("license"), klasse=kl, produkt_pixel=pr, auflage=auf, im_netz=bool(nr and nr in sfm_nrs), kamera_geloest=bool(nr and nr in kam)))
    clips = list((obj.get("video_stufe") or {}).get("clips", [])); vs = (obj.get("video_stufe") or {}).get("ordner")      # auch die Clips aller Video-SfM-Laeufe (Boden, Drohne ...)
    for ep in (sorted(glob.glob(os.path.join(vs, "*", "ergebnis.json"))) if vs else []):
        try: clips += [c for c in json.load(open(ep)).get("clips", []) if c not in clips]
        except Exception: pass
    for c in clips:
        kl = klasse("YouTube Standardlizenz", "youtube"); pr, auf = produkt(kl)
        eintraege.append(dict(art="video", quelle="youtube", foto=None, datei=None, titel=c, url="https://www.youtube.com/watch?v=" + c, urheber="", lizenz_text=(obj["video_stufe"].get("lizenz") or "Standard-YouTube-Lizenz"),
                              klasse=kl, produkt_pixel=pr, auflage=auf, im_netz=True, kamera_geloest=False))
    z = collections.Counter(e["klasse"] for e in eintraege); genutzt = [e for e in eintraege if e["im_netz"] or e["kamera_geloest"]]; zg = collections.Counter(e["klasse"] for e in genutzt)
    bericht = dict(objekt=obj.get("name"), anzahl=len(eintraege), je_klasse={k: z.get(k, 0) for k in REIHENFOLGE}, genutzt_im_modell=len(genutzt), genutzt_je_klasse={k: zg.get(k, 0) for k in REIHENFOLGE},
                   produkt_blockiert_genutzt=[(e["foto"] or e["titel"]) for e in genutzt if e["produkt_pixel"] == "nein"], hinweis="ANNAHME: Einordnung nach Lizenztext, keine Rechtsberatung; vor Veroeffentlichung am Original pruefen", bilder=eintraege)
    json.dump(bericht, open(os.path.join(od, "LIZENZ_BILDER.json"), "w"), indent=1, ensure_ascii=False)
    md = [f"# Lizenz der Bilder - {obj.get('name')} (AUTOMATISCH, nicht von Hand schreiben)", "", "Einordnung nach Lizenztext (ANNAHME, keine Rechtsberatung). Erzeugt von `tools/lizenz_register.py`.", "",
          "| Klasse | Pixel im Produkt | alle Bilder | davon im Modell genutzt | Auflage |", "|---|---|---|---|---|"]
    for k in REIHENFOLGE: md.append(f"| {k} | {produkt(k)[0]} | {z.get(k,0)} | {zg.get(k,0)} | {produkt(k)[1]} |")
    md += ["", f"Im Modell genutzt (SfM-Netz oder geloeste Kamera): {len(genutzt)} von {len(eintraege)}. Davon NICHT im Produkt erlaubt: {len(bericht['produkt_blockiert_genutzt'])}.", ""]
    for k in REIHENFOLGE:
        L = [e for e in eintraege if e["klasse"] == k]
        if not L: continue
        md += [f"## {k} ({len(L)})", ""]
        for e in L[:400]: md.append(f"- {e['foto'] or '-'} {e['titel'] or e['datei']} - {e['urheber'] or '?'} - {e['lizenz_text']}" + (" [genutzt]" if (e["im_netz"] or e["kamera_geloest"]) else ""))
        md.append("")
    open(os.path.join(od, "LIZENZ_BILDER.md"), "w").write("\n".join(md))
    print(f"{len(eintraege)} Bilder:", {k: z.get(k, 0) for k in REIHENFOLGE}); print(f"im Modell genutzt {len(genutzt)}:", {k: zg.get(k, 0) for k in REIHENFOLGE})
    print("-> LIZENZ_BILDER.json / .md in", od)
    if pruefen and bericht["produkt_blockiert_genutzt"]: print("PRUEFUNG: genutzte Bilder ohne Produktfreigabe:", bericht["produkt_blockiert_genutzt"][:20]); sys.exit(1)

if __name__ == "__main__": main()
