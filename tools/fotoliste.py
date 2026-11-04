#!/usr/bin/env python3
"""fotoliste.py - Fotoeingang festschreiben und pruefen (Nullstart-Ehrlichkeit, Register BZ).
Der Nullstart liest die Fotos aus fotos_dir; er laedt nichts herunter. Damit der Lauf trotzdem belegbar ist, haelt `fotoliste.json` je Foto:
Datei, Groesse, SHA-256, Quelle/Titel/URL/Urheber/Lizenz (aus manifest.json des Fotoordners bzw. LIZENZ_BILDER.json, wenn vorhanden).
  fotoliste.py <objekt.json> --schreiben   Liste erzeugen/erneuern (nur mit Absicht: neue Fotos = neuer Eingang)
  fotoliste.py <objekt.json> --pruefen     Ordner gegen Liste: FEHLT / GEAENDERT (Hash) / NEU; Exit 0 nur bei exakter Gleichheit, 1 sonst
Quellen ohne Eintrag (kein Manifest-Eintrag): 'quelle_unbekannt' wird gemeldet (Herkunft nicht belegbar).
"""
import sys, os, json, hashlib, time

def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()

def main():
    a = sys.argv[1:]
    if not a or ("--schreiben" not in a and "--pruefen" not in a): sys.exit(__doc__)
    op = os.path.abspath(a[0]); obj = json.load(open(op)); root = os.path.dirname(os.path.dirname(os.path.dirname(op))); od = os.path.dirname(op)
    fd = os.path.join(root, obj["fotos_dir"]); lp = os.path.join(od, "fotoliste.json")
    meta = {}
    mp = os.path.join(fd, "manifest.json")
    if os.path.exists(mp):
        for e in json.load(open(mp)).get("images", []): meta[e["file"]] = dict(titel=e.get("title"), url=e.get("url", "").split("?")[0], urheber=e.get("artist"), lizenz=e.get("license"), quelle="wikimedia_commons")
    lz = os.path.join(od, "LIZENZ_BILDER.json")
    if os.path.exists(lz):
        for e in json.load(open(lz)).get("bilder", []):
            if e.get("datei") and e["datei"] not in meta: meta[e["datei"]] = dict(titel=e.get("titel"), url=e.get("url"), urheber=e.get("urheber"), lizenz=e.get("lizenz_text"), quelle=e.get("quelle"))
    dateien = sorted(f for f in os.listdir(fd) if f.lower().endswith((".jpg", ".jpeg", ".png")))
    ist = {f: dict(groesse=os.path.getsize(os.path.join(fd, f)), sha256=sha(os.path.join(fd, f)), **meta.get(f, dict(quelle_unbekannt=True))) for f in dateien}
    if "--schreiben" in a:
        json.dump(dict(stand=time.strftime("%Y-%m-%d %H:%M"), fotos_dir=obj["fotos_dir"], anzahl=len(ist), ohne_quelle=sum(1 for v in ist.values() if v.get("quelle_unbekannt")), fotos=ist), open(lp, "w"), indent=1, ensure_ascii=False)
        print(f"fotoliste.json: {len(ist)} Fotos, davon ohne Quellenangabe: {sum(1 for v in ist.values() if v.get('quelle_unbekannt'))}"); return
    soll = json.load(open(lp))["fotos"]
    fehlt = sorted(set(soll) - set(ist)); neu = sorted(set(ist) - set(soll)); geaend = sorted(f for f in set(soll) & set(ist) if soll[f]["sha256"] != ist[f]["sha256"])
    print(f"Fotoliste: {len(soll)} festgeschrieben, {len(ist)} im Ordner | FEHLT {len(fehlt)} | GEAENDERT {len(geaend)} | NEU {len(neu)} | ohne Quelle {sum(1 for v in ist.values() if v.get('quelle_unbekannt'))}")
    for n, l in (("FEHLT", fehlt), ("GEAENDERT", geaend), ("NEU", neu)):
        for f in l[:10]: print(f"  {n}: {f}")
    sys.exit(0 if not (fehlt or neu or geaend) else 1)

if __name__ == "__main__":
    main()
