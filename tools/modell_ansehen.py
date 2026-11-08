#!/usr/bin/env python3
"""modell_ansehen.py - schattierter Dreiecks-Render (Painter-Algorithmus, Rueckseiten weg) eines STL zum ANSEHEN nach jedem Bau (CLAUDE.md Regel 3: Zahlen allein gelten nicht).
Warum: Punkt-Renderer (Abtastrauschen, doppelseitig) verdeckten Gauben und taeuschten ueber Fehler; die Konsolen-Huelle fuellte tagelang unbemerkt die Arkadenboegen.
  /media/oem/scan/venv-seg/bin/python -I tools/modell_ansehen.py modell.stl aus.jpg [az el]...   (Hauptfassade des Kaufhauses: az 180; Blick entlang +y)"""
import sys,trimesh,numpy as np,cv2
def rot(az,el):
    a,e=np.radians(az),np.radians(el)
    Rz=np.array([[np.cos(a),-np.sin(a),0],[np.sin(a),np.cos(a),0],[0,0,1]]);Rx=np.array([[1,0,0],[0,np.cos(e),-np.sin(e)],[0,np.sin(e),np.cos(e)]]);return Rx@Rz
def render(m,az,el,W=1000,H=800,gpu=True):
    """GPU: PyTorch3D rasterize_meshes (orthografisch, Tiefenpuffer); gpu=False: alter Painter (modell_ansehen_cpu.py)"""
    if not gpu:
        import modell_ansehen_cpu as c;return c.render(m,az,el,W,H)
    sys.path.insert(0,"/media/oem/scan/p3d_site")
    import torch;from pytorch3d.renderer.mesh.rasterize_meshes import rasterize_meshes;from pytorch3d.structures import Meshes
    R=rot(az,el);V=m.vertices@R.T;F=m.faces;N=m.face_normals@R.T
    lo=V.min(0);hi=V.max(0);s=min(W/(hi[0]-lo[0]),H/(hi[2]-lo[2]))*.95
    X=(V[:,0]-lo[0])*s+10;Y=H-10-(V[:,2]-lo[2])*s;S=max(W,H)           # Pixelkoordinaten, quadratische Leinwand S x S
    L=np.array([-.4,-.8,.5]);L/=np.linalg.norm(L);vis=N[:,1]<0.02
    sh=np.clip(N@L,0,1);col=(60+180*sh).astype(np.float32)
    ndc=np.stack([-(X/S*2-1),-(Y/S*2-1),V[:,1]-V[:,1].min()+1],1)       # pytorch3d: +x links, +y oben
    dev="cuda";Fv=F[vis];mesh=Meshes(verts=[torch.tensor(ndc,dtype=torch.float32,device=dev)],faces=[torch.tensor(Fv,dtype=torch.int64,device=dev)])
    pf,zb,_,_=rasterize_meshes(mesh,image_size=S,blur_radius=0.0,faces_per_pixel=1,perspective_correct=False,cull_backfaces=False)
    pf=pf[0,:,:,0].cpu().numpy()[:H,:W];cv=col[vis];img=np.full((H,W,3),30,np.uint8);ok=pf>=0
    img[ok]=cv[pf[ok]].astype(np.uint8)[:,None];return img
if __name__=='__main__':
    m=trimesh.load(sys.argv[1]);cv2.imwrite(sys.argv[2],np.hstack([render(m,float(sys.argv[i]),float(sys.argv[i+1])) for i in range(3,len(sys.argv),2)]))
