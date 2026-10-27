#!/usr/bin/env python3
"""schluchsee_modell.py — texturiertes 3D der Schluchsee-Staumauer (Seebrugg) aus LGL-Daten.
DGM025 (0,25m) + DOP20-Luftbild, Original-Proportion. Mauer bei UTM E438867 N5294465."""
import numpy as np, rasterio, glob, cv2, argparse
from rasterio.windows import from_bounds
import plotly.graph_objects as go
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--win", type=int, default=1300, help="Fenster in px (0,25m)")
    ap.add_argument("--step", type=int, default=4)
    ap.add_argument("--out", default="/tmp/schluchsee")
    a=ap.parse_args()
    cell=0.25
    dgt='/tmp/schluch/dgm_x/dgm025_32_437_5294_2_bw/dgm025_32_438_5294_1_bw_2022.tif'
    dopf=glob.glob('/tmp/schluch/dop_x/**/*438_5294*.tif',recursive=True)[0]
    with rasterio.open(dgt) as ds: dem=ds.read(1).astype(float)
    dem=np.where(dem<-1000,np.nan,dem)
    E0t,N0t=438000.125,5294999.875
    r=int(round((N0t-5294465)/0.25)); c=int(round((438867-E0t)/0.25))
    H=a.win; rr0=max(0,r-H//2); rr1=min(4000,rr0+H); cc0=max(0,c-H//2); cc1=min(4000,cc0+H)
    win=dem[rr0:rr1,cc0:cc1]; win=np.where(np.isnan(win),np.nanmin(win),win); win=win[::-1]
    relief=win-win.min(); NYf,NXf=relief.shape
    E0=E0t+cc0*0.25; E1=E0t+cc1*0.25; N1=N0t-rr0*0.25; N0=N0t-rr1*0.25
    with rasterio.open(dopf) as ds:
        w=from_bounds(E0,N0,E1,N1,ds.transform)
        rgb0=np.transpose(ds.read([1,2,3],window=w),(1,2,0)).astype(np.uint8)
    rgb0=rgb0[::-1]
    s=a.step; rel=relief[::s,::s]; NY,NX=rel.shape
    rgb=cv2.resize(rgb0,(NX,NY),interpolation=cv2.INTER_AREA)
    print(f"Szene {NXf*cell:.0f}x{NYf*cell:.0f}m relief {relief.max():.0f}m | mesh {NX}x{NY}={NX*NY}")
    X=np.arange(NX)*cell*s; Y=np.arange(NY)*cell*s; XX,YY=np.meshgrid(X,Y)
    col=['rgb(%d,%d,%d)'%(rr,gg,bb) for rr,gg,bb in rgb.reshape(-1,3)]
    I=[];J=[];K=[]
    for i in range(NY-1):
        base=i*NX
        for j in range(NX-1):
            A_=base+j; B_=A_+1; Cc=A_+NX; D_=Cc+1
            I+=[A_,B_]; J+=[Cc,Cc]; K+=[B_,D_]
    fig=go.Figure(go.Mesh3d(x=XX.ravel(),y=YY.ravel(),z=rel.ravel(),i=I,j=J,k=K,vertexcolor=col,
                  flatshading=False,lighting=dict(ambient=0.72,diffuse=0.55)))
    fig.update_layout(title="Schluchsee-Staumauer (Seebrugg) — DGM 0,25m + DOP20 2025, Original-Proportion",
        scene=dict(aspectmode='data',xaxis=dict(title='Ost m'),yaxis=dict(title='Nord m'),zaxis=dict(title='Höhe m')),height=860)
    import os; os.makedirs(a.out,exist_ok=True)
    fig.write_html(f'{a.out}/schluchsee.html',include_plotlyjs='cdn')
    np.save(f'{a.out}/dem_win.npy',win); np.save(f'{a.out}/relief.npy',relief); np.save(f'{a.out}/rgb.npy',rgb0)
    fig2=plt.figure(figsize=(17,8))
    ax0=fig2.add_subplot(1,2,1); ax0.imshow(rgb,origin='lower',extent=[0,NX*cell*s,0,NY*cell*s])
    ax0.set_title('Draufsicht Luftbild — Staumauer + Stausee'); ax0.set_xlabel('Ost m'); ax0.set_ylabel('Nord m')
    ax1=fig2.add_subplot(1,2,2,projection='3d')
    ax1.plot_surface(XX,YY,rel,facecolors=rgb/255,linewidth=0,antialiased=True,shade=False,rcount=NY,ccount=NX)
    ax1.set_box_aspect((NX*cell*s,NY*cell*s,relief.max())); ax1.view_init(elev=26,azim=-60)
    ax1.set_title('3D Original-Proportion'); ax1.set_xlabel('Ost m'); ax1.set_ylabel('Nord m')
    plt.tight_layout(); plt.savefig(f'{a.out}/schluchsee_preview.png',dpi=115)
    print(f"-> {a.out}/schluchsee.html + schluchsee_preview.png")

if __name__=="__main__": main()
