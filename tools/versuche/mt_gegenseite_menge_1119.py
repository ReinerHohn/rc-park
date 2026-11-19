import sqlite3, numpy as np, collections
d=np.load("duenn2.npz"); st=dict(zip(d["namen"],d["stabil"])); pos=dict(zip(d["namen"],d["K"]))
db=sqlite3.connect("file:/media/oem/scan/rc-park_daten/martinstor_gk3/pipe/sfm/db.db?mode=ro",uri=True); nm=dict(db.execute("select image_id,name from images")); inv={n:i for i,n in nm.items()}
N=collections.defaultdict(dict)
for pid,rows in db.execute("select pair_id,rows from two_view_geometries where rows>=50"):
    a,b=divmod(pid,2147483647); N[a][b]=rows; N[b][a]=rows
kern=[i for i,n in nm.items() if any(n.startswith(z) for z in ("eigen__000_","eigen__025_","eigen__075_","eigen__124_","eigen__121_","fotos_eingang__neu_957","netz_openverse__ov_0009"))]
S=set(kern)
for runde in range(3):
    neu={j for j in nm if j not in S and not st.get(nm[j],False) and sum(1 for k in N[j] if k in S)>=3}; print("Runde",runde,"+",len(neu)); S|=neu
g=collections.Counter(nm[i].split("__vf_")[0][-11:] if "__vf_" in nm[i] else nm[i].split("__")[0] for i in S); print(len(S),dict(g))
print("davon im Modell (unstabil)",sum(1 for i in S if nm[i] in pos),"nicht registriert",sum(1 for i in S if nm[i] not in pos))
open("sued_liste.txt","w").write("\n".join(sorted(nm[i] for i in S))+"\n")
