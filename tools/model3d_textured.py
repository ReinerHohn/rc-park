import numpy as np, rasterio
from rasterio.windows import from_bounds
import cv2, plotly.graph_objects as go
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

cell=0.25
R0,R1,C0,C1=150,750,2900,3700          # Gesamt-Szene: Bogen + Bahn + Hirschsprung-Wand
dem=np.load('daten/hoellental/dgm025_full.npy').astype(float)
dem=np.where(dem<-1000,np.nan,dem)
win=dem[R0:R1,C0:C1]; win=np.where(np.isnan(win),np.nanmin(win),win)
win=win[::-1]                           # +y=Nord
relief=win-win.min()
NYf,NXf=relief.shape

# Ortho (DOP20 2025) deckungsgleich
tfw=[float(x) for x in open('daten/hoellental/dgm025_32_426_5309_1_bw_2017.tfw')]
A,D,B,E,C,F=tfw
E0=C+C0*A; E1=C+C1*A; N0=F+R1*E; N1=F+R0*E
dop='/tmp/ortho50/dop_extract/dop20rgb_32_425_5308_2_bw/dop20rgb_32_426_5309_1_bw_2025.tif'
with rasterio.open(dop) as ds:
    w=from_bounds(E0,N0,E1,N1,ds.transform)
    rgb0=np.transpose(ds.read([1,2,3],window=w),(1,2,0)).astype(np.uint8)
rgb0=rgb0[::-1]

# Mesh downsample (plotly-tauglich) — Textur bleibt per-Vertex gleich fein
step=3
rel=relief[::step,::step]; NY,NX=rel.shape
rgb=cv2.resize(rgb0,(NX,NY),interpolation=cv2.INTER_AREA)
print(f"Szene {NXf*cell:.0f}x{NYf*cell:.0f} m, Relief {relief.max():.0f} m | Mesh {NX}x{NY}={NX*NY} Vertices")

X=np.arange(NX)*cell*step; Y=np.arange(NY)*cell*step
XX,YY=np.meshgrid(X,Y)
xv=XX.ravel(); yv=YY.ravel(); zv=rel.ravel()
col=['rgb(%d,%d,%d)'%(r,g,b) for r,g,b in rgb.reshape(-1,3)]
I=[];J=[];K=[]
for i in range(NY-1):
    base=i*NX
    for j in range(NX-1):
        a=base+j; b=a+1; c=a+NX; d=c+1
        I+=[a,b]; J+=[c,c]; K+=[b,d]
fig=go.Figure(go.Mesh3d(x=xv,y=yv,z=zv,i=I,j=J,k=K,vertexcolor=col,
              flatshading=False,lighting=dict(ambient=0.72,diffuse=0.55,specular=0.1)))
fig.update_layout(title="Hirschsprung / Höllental — echtes Relief (DGM 0,25m) + echtes Luftbild (DOP20 2025), Original-Proportion",
    scene=dict(aspectmode='data',xaxis=dict(title='Ost m'),yaxis=dict(title='Nord m'),zaxis=dict(title='Höhe m')),height=860)
fig.write_html('/tmp/model3d.html',include_plotlyjs='cdn')

# statische Vorschau (2 Winkel)
fig2=plt.figure(figsize=(16,7))
for n,(el,az) in enumerate([(32,-65),(50,-110)]):
    ax=fig2.add_subplot(1,2,n+1,projection='3d')
    ax.plot_surface(XX,YY,rel,facecolors=rgb/255,linewidth=0,antialiased=True,shade=False,rcount=NY,ccount=NX)
    ax.set_box_aspect((NX*cell*step,NY*cell*step,relief.max()))
    ax.view_init(elev=el,azim=az); ax.set_xlabel('Ost m'); ax.set_ylabel('Nord m'); ax.set_zlabel('Höhe m')
plt.suptitle('Texturiertes 3D — Hirschsprung (Original-Proportion, DGM 0,25m + Luftbild 2025)')
plt.tight_layout(); plt.savefig('/tmp/model3d_preview.png',dpi=105)
print("-> /tmp/model3d.html  +  /tmp/model3d_preview.png")
