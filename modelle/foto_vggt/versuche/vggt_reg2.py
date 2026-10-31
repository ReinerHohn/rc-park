import numpy as np, trimesh, torch, math
dev="cuda"; S="/tmp/claude-29999/-home-oem-git-rc-park/bf197a0c-a706-4c3e-9f93-17b19691b58c/scratchpad/vggt/"
X=np.load(S+"X.npy"); rng=np.random.default_rng(0); X=X[rng.choice(len(X),5000,replace=False)]
zt=np.percentile(X[:,2],99.5); X[:,2]-=zt            # Oberkante = 0
M=trimesh.load("/home/oem/git/rc-park/modelle/stl/martinstor_v4_1-87.stl"); M.apply_scale(87/1000.0)
c=M.bounds.mean(0); M.apply_translation([-c[0],-c[1],-M.bounds[0,2]])
pm,_=trimesh.sample.sample_surface(M,60000,seed=0); pm=pm[pm[:,2]>14]; pm=pm[::max(1,len(pm)//12000)]
Xt=torch.tensor(X,dtype=torch.float32,device=dev); Pm=torch.tensor(pm,dtype=torch.float32,device=dev)
def xform(th):                                    # th: (B,6) s, phi, yaw, tx, ty, tz
    s,phi,yaw,tx,ty,tz=[th[:,i,None] for i in range(6)]
    x,y,z=Xt[None,:,0],Xt[None,:,1],Xt[None,:,2]
    cp,sp=torch.cos(phi),torch.sin(phi)           # Neigung um die a-Achse (x)
    y2=cp*y-sp*z; z2=sp*y+cp*z
    cy,sy=torch.cos(yaw),torch.sin(yaw); x3=cy*x-sy*y2; y3=sy*x+cy*y2
    return torch.stack([s*x3+tx,s*y3+ty,s*z2+54.8+tz],-1)
def cost(th,chunk=4):
    out=[]
    for i in range(0,len(th),chunk):
        W=xform(th[i:i+chunk]); B=W.shape[0]
        D=torch.cdist(W,Pm[None].expand(B,-1,-1))                # (B,n,m)
        d1=D.min(2).values; k1=int(.7*d1.shape[1]); c1=d1.sort(1).values[:,:k1].mean(1)
        d2=D.min(1).values                                       # Modell->Wolke
        zlo=W[:,:,2].min(1).values[:,None]; zhi=W[:,:,2].max(1).values[:,None]
        sel=(Pm[None,:,2]>=zlo)&(Pm[None,:,2]<=zhi)
        n=sel.sum(1).clamp(min=1); d2m=torch.where(sel,d2,torch.full_like(d2,1e3))
        k2=(0.5*n).long().clamp(min=1); srt=d2m.sort(1).values
        c2=torch.stack([srt[b,:k2[b]].mean() for b in range(B)]); cov=(sel.sum(1).float()/len(pm)).clamp(max=1)
        out.append(c1+c2+3.0*(1-cov.clamp(min=0.05)**0.3)*0)    # beidseitig
    return torch.cat(out)
lo=torch.tensor([20,-0.5,0,-8,-8,-10.],device=dev); hi=torch.tensor([70,0.5,2*math.pi,8,8,10.],device=dev)
g=torch.Generator(device=dev).manual_seed(0)
th=lo+(hi-lo)*torch.rand((2048,6),device=dev,generator=g); sc=cost(th); k=sc.topk(60).indices
mu=th[k].mean(0); sd=th[k].std(0)+1e-3; best=(sc[k[0]].item(),th[k[0]].clone())
for it in range(40):
    cand=torch.max(torch.min(mu+sd*torch.randn((384,6),device=dev,generator=g),hi),lo); cand[0]=best[1]
    sc=cost(cand); k=sc.topk(40).indices
    if sc[k[0]].item()<best[0]: best=(sc[k[0]].item(),cand[k[0]].clone())
    mu=0.5*mu+0.5*cand[k].mean(0); sd=0.7*sd+0.3*cand[k].std(0)+1e-4
f,t=best; t=t.cpu().numpy()
print(f"Kosten {f:.3f} m  s={t[0]:.2f} m/Einheit  Neigung {math.degrees(t[1]):.1f} Grad  Drehung {math.degrees(t[2])%360:.0f} Grad  t=({t[3]:.2f},{t[4]:.2f},{t[5]:.2f})")
W=xform(torch.tensor(t,dtype=torch.float32,device=dev)[None])[0].cpu().numpy()
print("Wolkenhoehe",W[:,2].min().round(1),"bis",W[:,2].max().round(1),"m; Grenzen: s in [20,70]:", "AN GRENZE" if (t[0]<21 or t[0]>69) else "ok", "| Neigung",("AN GRENZE" if abs(t[1])>0.49 else "ok"))
from scipy.spatial import cKDTree
d,_=cKDTree(pm).query(W)
for z0 in range(15,56,5):
    kk=(W[:,2]>=z0)&(W[:,2]<z0+5)
    if kk.sum()>100: print(f" z {z0:2d}-{z0+5:2d} m  Punkte {kk.sum():5d}  Median {np.median(d[kk]):.2f} m  P90 {np.percentile(d[kk],90):.2f} m")
np.save(S+"W2.npy",W)
