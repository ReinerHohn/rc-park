import sqlite3, numpy as np, collections, networkx as nx, sys
D="/media/oem/scan/rc-park_daten/martinstor_gk3/pipe/sfm/"; res=float(sys.argv[1]) if len(sys.argv)>1 else 1.0
db=sqlite3.connect(f"file:{D}db.db?mode=ro",uri=True); nm=dict(db.execute("select image_id,name from images"))
G=nx.Graph(); G.add_nodes_from(nm)
for pid,rows in db.execute("select pair_id,rows from two_view_geometries where rows>=30"):
    a,b=divmod(pid,2147483647); G.add_edge(a,b,weight=rows)
C=sorted(nx.community.louvain_communities(G,weight="weight",seed=1,resolution=res),key=len,reverse=True)
links=("eigen__000_","eigen__025_","eigen__075_","eigen__121_","eigen__124_","video_frames_A_PUR2GXND0","eigen__041_","eigen__030_"); rechts=("eigen__089","video_frames_LSi6HGXqmiY","video_frames_h792HhnMgR8","eigen__051","eigen__087")
uns=set(l.strip() for l in open(D+"konsens_arbeit/unstabil.txt")); reg=set(np.load("duenn2.npz")["namen"])
print(len(C),"Gemeinschaften, Aufloesung",res)
for k,c in enumerate(C[:12]):
    if len(c)<12: break
    n=[nm[i] for i in c]; g=collections.Counter(x.split("__vf_")[0][-11:] if "__vf_" in x else x.split("__")[0] for x in n)
    print(k,len(c),"| Nebenhaus-links",sum(x.startswith(links) for x in n),"rechts",sum(x.startswith(rechts) for x in n),"| Rueckgrat",sum(x in reg and x not in uns for x in n),"|",dict(g.most_common(5)))
import json; json.dump({nm[i]:k for k,c in enumerate(C) for i in c},open("gem_all.json","w"))
