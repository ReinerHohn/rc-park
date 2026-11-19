import sqlite3, numpy as np, collections
d=np.load("duenn2.npz"); reg=set(d["namen"]); st=dict(zip(d["namen"],d["stabil"]))
db=sqlite3.connect("file:/media/oem/scan/rc-park_daten/martinstor_gk3/pipe/sfm/db.db?mode=ro",uri=True)
nm=dict(db.execute("select image_id,name from images")); print("Bilder in DB",len(nm))
E=[]
for pid,rows in db.execute("select pair_id,rows from two_view_geometries where rows>=30"):
    a,b=divmod(pid,2147483647); E.append((a,b,rows))
print("Paare >=30 Inlier",len(E))
un={i for i,n in nm.items() if n not in reg}; par={i:i for i in un}
def f(x):
    while par[x]!=x: par[x]=par[par[x]]; x=par[x]
    return x
quer=collections.defaultdict(list)
for a,b,r in E:
    if a in un and b in un: par[f(a)]=f(b)
    elif a in un and b in nm: quer[a].append((r,b))
    elif b in un and a in nm: quer[b].append((r,a))
K=collections.defaultdict(list)
for i in un: K[f(i)].append(i)
for k in sorted(K.values(),key=len,reverse=True)[:8]:
    g=collections.Counter(nm[i].split("__vf_")[0][-11:] if "__vf_" in nm[i] else nm[i].split("__")[0] for i in k)
    q=[(r,nm[b]) for i in k for r,b in quer[i]]; qs=sum(1 for r,n in q if st.get(n)); 
    print(len(k),"Bilder;",dict(g.most_common(6)),"; Verbindungen ins Modell:",len(q),"davon zu Rueckgrat",qs,"staerkste",sorted(q,reverse=True)[:2])
ziel=["eigen__000_","eigen__025_","eigen__075_","eigen__124_","eigen__121_","fotos_eingang__neu_957","netz_openverse__ov_0009"]
for i,n in nm.items():
    if any(n.startswith(z) for z in ziel): print(n[:34],"Komponente",len(K[f(i)]),"quer",len(quer[i]),sorted(quer[i],reverse=True)[:2] and [(r,nm[b][-30:]) for r,b in sorted(quer[i],reverse=True)[:2]])
