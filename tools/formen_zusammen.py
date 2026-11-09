"""Formsegmente (helm_fit/gauben_fit/baluster_fit-Ausgaben) an ein Kantengitter anhaengen: formen_zusammen.py GITTER.json OUT.json FORM1.json [FORM2.json ...]
Jede Formdatei traegt 'segmente' [[p0,p1,quelle,score],...] und ihre Parameterlisten (helme/gauben/baluster), die mit uebernommen werden; vorhandene Segmente
derselben Quelle im Gitter werden ERSETZT (ein Lauf = ein Stand je Formfamilie). Historie bekommt einen Eintrag."""
import sys, json, os, collections
G = json.load(open(sys.argv[1])); neu = []; quellen = set(); info = {}
for f in sys.argv[3:]:
    F = json.load(open(f)); seg = F.get("segmente", []); neu += seg; quellen |= {s[2] for s in seg}
    for k in ("helme", "gauben", "baluster"):
        if k in F: G[k] = F[k]; info[k] = len(F[k]) if isinstance(F[k], list) else F[k]
    for k in ("periode", "profil", "anzahl_fotogeprueft", "band", "dachebenen", "traufe"):
        if k in F: G.setdefault("formen_parameter", {})[k] = F[k]
alt = len(G["segmente"]); G["segmente"] = [s for s in G["segmente"] if s[2] not in quellen] + neu
G.setdefault("historie", []).append({"schritt": "formen_zusammen", "quellen_ersetzt": sorted(quellen), "dateien": [os.path.basename(f) for f in sys.argv[3:]], "n_vorher": alt, "n_nachher": len(G["segmente"])})
json.dump(G, open(sys.argv[2], "w")); print("Segmente vorher %d, nachher %d; je Quelle %s; Formen %s" % (alt, len(G["segmente"]), dict(collections.Counter(s[2] for s in G["segmente"])), info))
