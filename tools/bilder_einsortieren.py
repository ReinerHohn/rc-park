#!/usr/bin/env python3
"""bilder_einsortieren.py - PIPELINE-SCHRITT nach bilder_holen.py: geerntete Fotos (fotos_eingang) in den Fotoordner des Objekts einsortieren.

Je Bild: fortlaufende Nummer (hoechste vorhandene + 1), Datei <nr>_<Titel>.jpg, Eintrag im Foto-Manifest (Lizenz/Autor/URL Pflicht),
Eintrag in objekt.json["fotos"][nr] mit Seite (aus dem Seitenvorschlag der Ernte = aehnlichstes Basisfoto, sonst 'unbekannt'),
seite_quelle, Klasse (neu/aehnlich) und Bezugsbild; Fotos mit Seite nord/sued kommen in die SfM-Liste der Seite (objekt.json["sfm"][seite]),
Fotos ohne Seite nicht (die Seitentrennung im Netz entscheidet spaeter; symmetrischer Turm, Register AH),
ausser objekt.json sfm.netz_ohne_seite nennt ein gemeinsames Netz (nicht symmetrische Objekte, Kaltstart). Kaltstart-Saatbilder (bilder_holen) passieren das Inlier-Gate.
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/bilder_einsortieren.py modelle/<objekt>/objekt.json [--nur-anzeigen] [--mindest-inlier 20]
Idempotent: Titel, die im Foto-Manifest schon stehen, werden uebersprungen. Der Eingang bleibt liegen (Beleg), die Vorschau-Caches ebenso.
"""
import sys, os, json, re, shutil, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import lizenz_register as LR

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--nur-anzeigen", action="store_true"); ap.add_argument("--eingang", help="Eingangsordner (ueberschreibt bildquellen.ausgabe), z. B. eine Runde der Bilder-Schleife"); ap.add_argument("--produkt", action="store_true", help="nur Bilder mit Produkt-Pixel ja/bedingt (lizenz_register.produkt) einsortieren; nc/unfrei/unklar bleiben im Eingang (nur private Messung)"); ap.add_argument("--mindest-inlier", type=int, default=40, help="Relevanz-Nachgate: Bilder mit weniger Inliern zum aehnlichsten Basisfoto bleiben im Eingang")
    a = ap.parse_args(); obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); repo = os.path.dirname(os.path.dirname(od))
    Q = obj.get("bildquellen", {}); ein = os.path.join(repo, a.eingang or Q.get("ausgabe", f"daten/{os.path.basename(od)}/fotos_eingang")); fd = os.path.join(repo, obj["fotos_dir"])
    E = json.load(open(os.path.join(ein, "manifest.json"))); mp = os.path.join(fd, "manifest.json"); M = json.load(open(mp)) if os.path.exists(mp) else dict(source="gemischt", images=[])
    bekannt = {it.get("title") for it in M["images"]}; fotos = obj.setdefault("fotos", {}); sfm = obj.setdefault("sfm", {})
    nr = max([int(k) for k in fotos if k.isdigit()] + [int(f[:3]) for f in os.listdir(fd) if f[:3].isdigit()] + [-1]) + 1
    seiten_name = {"nord": "Nord", "sued": "Sued", "ost": "Ost", "west": "West"}; neu = []; uebergangen = []
    for it in E["images"]:
        if it["title"] in bekannt: continue
        if a.produkt and LR.produkt(it.get("lizenz_klasse", "unklar"))[0] == "nein": uebergangen.append((it["title"], f"Lizenzklasse {it.get('lizenz_klasse', 'unklar')}")); continue
        quelle = os.path.join(ein, it["file"])
        if not os.path.exists(quelle): continue
        titel = re.sub(r"[^A-Za-z0-9._-]+", "_", it["title"].replace("File:", ""))[:60]; ziel = f"{nr:03d}_{titel}"
        if not ziel.lower().endswith((".jpg", ".jpeg", ".png")): ziel += ".jpg"
        ab = it.get("aehnlich_basis") or {}
        if ab.get("inlier", 0) < a.mindest_inlier and not ab.get("saat"): uebergangen.append((it["title"], ab.get("inlier", 0))); continue   # Relevanz-Nachgate (Ernte 2: Fremdobjekte bei 20-35 Inliern)
        seite = it.get("seite_vorschlag")
        eintrag = dict(lizenz_klasse=it.get("lizenz_klasse", "unklar"), exif_stufe=it.get("exif_stufe", "fehlt"), seite=seiten_name.get(seite, "unbekannt") if seite else "unbekannt", silhouette_frei=False, vollbild=[it.get("orig_w"), it.get("orig_h")],
                       quelle=f"bilder_holen.py ({E.get('stand')}): {it['title']}, {it['license']}, {it['artist']}; Klasse {it['klasse']}" + (f", aehnlich zu {it['aehnlich_zu']}" if it.get("aehnlich_zu") else ""),
                       seite_quelle=(f"Seitenvorschlag: aehnlichstes Basisfoto {ab.get('name')} ({ab.get('inlier')} Inlier, Seite {ab.get('seite')}) - automatisch, nicht gesichtet" if seite else "offen: kein Bezugsbild mit Seite - Seitentrennung im Netz"))
        if seite in ("nord", "sued") or (seite and isinstance(sfm.get(seite), list)): eintrag["sfm_netz"] = seite
        elif sfm.get("netz_ohne_seite"): eintrag["sfm_netz"] = sfm["netz_ohne_seite"]          # Objekt ohne Seitentrennung (nicht symmetrisch): ein gemeinsames Netz, Seite spaeter aus der Kameralage
        if ab.get("saat"): eintrag["seite_quelle"] = "offen: Kaltstart-Saatbild (Objekt-Kategorie, in der groessten sich bestaetigenden Bildgruppe) - Seite aus der Kameralage im Netz"
        neu.append((f"{nr:03d}", ziel, quelle, it, eintrag)); nr += 1
    if uebergangen: print(f"  uebergangen (Inlier < {a.mindest_inlier} oder Lizenzklasse): {len(uebergangen)} - z. B. " + "; ".join(f"{t[:40]} ({n})" for t, n in uebergangen[:5]))
    print(f"Eingang: {len(E['images'])} Bilder, davon neu {len(neu)}; Seiten: " + json.dumps({s: sum(1 for n in neu if n[4]['seite'] == s) for s in set(n[4]['seite'] for n in neu)}, ensure_ascii=False))
    for n, ziel, q, it, e in neu[:8]: print(f"  {n} {e['seite']:9s} {it['klasse']:8s} {it['license']:12s} {it['title'][:60]}")
    if a.nur_anzeigen: return
    for n, ziel, q, it, e in neu:
        shutil.copy2(q, os.path.join(fd, ziel)); fotos[n] = e
        M["images"].append(dict(file=ziel, title=it["title"], url=it["url"], license=it["license"], artist=it["artist"], w=it.get("orig_w"), h=it.get("orig_h"), exif_f35=it.get("exif_f35"), exif_f_mm=it.get("exif_f_mm"), exif_model=it.get("exif_model"), exif_stufe=it.get("exif_stufe", "fehlt"), lizenz_klasse=it.get("lizenz_klasse", "unklar"), produkt_pixel=LR.produkt(it.get("lizenz_klasse", "unklar"))[0], quelle="bilder_holen", klasse=it["klasse"], stand=E.get("stand")))
        if e.get("sfm_netz") and n not in sfm.setdefault(e["sfm_netz"], []): sfm[e["sfm_netz"]].append(n)
    json.dump(M, open(mp, "w"), indent=1, ensure_ascii=False); __import__("json_sicher").schreiben(a.objekt, obj)
    print(f"einsortiert: {len(neu)} Fotos -> {os.path.relpath(fd, repo)}, objekt.json fotos/sfm aktualisiert (nord {len(sfm.get('nord', []))}, sued {len(sfm.get('sued', []))})")

if __name__ == "__main__":
    main()
