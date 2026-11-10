"""Git-Merge-Treiber fuer JSON-Tabellen (masstabelle.json, 10.11.): 8 Kreis-Spuren tragen parallel Zeilen ein; Textmerge erzeugt Konflikte.
Aufruf durch git:  python3 tools/json_merge.py %O %A %B   (Basis, unsere = Ergebnisdatei, deren)
Regeln je Schluessel (rekursiv fuer Objekte):
  - nur eine Seite geaendert -> diese Seite
  - Listen: Elemente nach JSON-Identitaet; Ergebnis = unsere Liste ohne die von DENEN geloeschten + die von denen neu hinzugefuegten (Reihenfolge: unsere, dann deren neue)
  - beide aendern denselben Skalar verschieden -> Konflikt (Exit 1, unsere Datei bleibt unveraendert -> git meldet Konflikt)
Einrichtung (einmal je Klon): git config merge.jsontabelle.driver "python3 tools/json_merge.py %O %A %B" ; .gitattributes: modelle/*/masstabelle.json merge=jsontabelle
"""
import sys, json

def ident(x): return json.dumps(x, sort_keys=True, ensure_ascii=False)

class Konflikt(Exception): pass

def merge(b, o, t, pfad=""):
    if o == t: return o
    if o == b: return t
    if t == b: return o
    if isinstance(b, dict) and isinstance(o, dict) and isinstance(t, dict):
        r = {}
        for k in list(o.keys()) + [k for k in t if k not in o]:
            if k in o and k in t: r[k] = merge(b.get(k), o[k], t[k], pfad + "/" + k)
            elif k in o:   # nur bei uns: neu, oder bei denen geloescht
                if k in b and ident(b[k]) == ident(o[k]): continue
                if k in b: raise Konflikt(pfad + "/" + k + " (bei denen geloescht, bei uns geaendert)")
                r[k] = o[k]
            else:
                if k in b and ident(b[k]) == ident(t[k]): continue
                if k in b: raise Konflikt(pfad + "/" + k + " (bei uns geloescht, bei denen geaendert)")
                r[k] = t[k]
        return r
    if isinstance(o, list) and isinstance(t, list):
        bl = b if isinstance(b, list) else []
        bi = {ident(x) for x in bl}; oi = {ident(x) for x in o}; ti = {ident(x) for x in t}
        weg_t = bi - ti; neu_t = [x for x in t if ident(x) not in bi and ident(x) not in oi]
        return [x for x in o if ident(x) not in weg_t] + neu_t
    raise Konflikt(pfad or "/")

if __name__ == "__main__":
    O, A, B = sys.argv[1:4]
    try:
        r = merge(json.load(open(O)), json.load(open(A)), json.load(open(B)))
    except Konflikt as e:
        print("json_merge: Konflikt bei", e, file=sys.stderr); sys.exit(1)
    except Exception as e:
        print("json_merge: nicht lesbar -", e, file=sys.stderr); sys.exit(1)
    json.dump(r, open(A, "w"), ensure_ascii=False, indent=1)
    sys.exit(0)
