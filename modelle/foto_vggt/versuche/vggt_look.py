import numpy as np, cv2
S="/tmp/claude-29999/-home-oem-git-rc-park/bf197a0c-a706-4c3e-9f93-17b19691b58c/scratchpad/vggt/"
d=np.load(S+"vggt.npz"); ext=d["ext"]; P=d["pts"].reshape(-1,3); C=d["conf"].reshape(-1); col=(d["cols"].reshape(-1,3)*255).astype(np.uint8)
Rs=ext[:,:,:3]; xs=Rs[:,0,:]; ys=Rs[:,1,:]
A=sum(np.outer(x,x) for x in xs); w,V=np.linalg.eigh(A); up=V[:,0]
if (up@(-ys.mean(0)))<0: up=-up
print("Eigenwerte x-Achsen",w.round(3),"Senkrechte",up.round(3),"Winkel Kamera-x zur Senkrechten (Grad)",[round(float(np.degrees(np.arcsin(abs(x@up)))),1) for x in xs])
print("Neigung Blickrichtung ueber Horizont (Grad)",[round(float(np.degrees(np.arcsin(Rs[i][2]@up))),1) for i in range(len(Rs))])
hsv=cv2.cvtColor(col.reshape(-1,1,3),cv2.COLOR_RGB2HSV).reshape(-1,3)
sky=((hsv[:,1]<40)&(hsv[:,2]>150))|((hsv[:,0]>95)&(hsv[:,0]<130)&(hsv[:,1]>50))
ok=(C>np.percentile(C,40))&np.isfinite(P).all(1)&~sky
Q=P[ok]; cq=col[ok]; m=np.median(Q,0); r=np.linalg.norm(Q-m,axis=1); k=r<np.percentile(r,92); Q=Q[k]; cq=cq[k]
a=np.cross(up,[1,0,0]); a/=np.linalg.norm(a); b=np.cross(up,a); X=np.c_[(Q-m)@a,(Q-m)@b,(Q-m)@up]
print("Ausdehnung (Wolkeneinheiten) a,b,hoch:",(X.max(0)-X.min(0)).round(2))
def img(u,v,name,W=700):
    lo=np.array([u.min(),v.min()]); sc=W/max(u.max()-lo[0],v.max()-lo[1]); im=np.full((W,W,3),255,np.uint8)
    px=((u-lo[0])*sc).astype(int).clip(0,W-1); py=(W-1-((v-lo[1])*sc)).astype(int).clip(0,W-1)
    o=np.argsort(-X[:,1] if name=="seite" else X[:,2]); im[py[o],px[o]]=cq[o][:,::-1]; cv2.imwrite(S+name+".png",im)
img(X[:,0],X[:,2],"front"); img(X[:,1],X[:,2],"seite"); img(X[:,0],X[:,1],"oben")
np.save(S+"X.npy",X)
