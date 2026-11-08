#!/usr/bin/env python3
"""modell_ansehen.py - schattierter Dreiecks-Render (Painter-Algorithmus, Rueckseiten weg) eines STL zum ANSEHEN nach jedem Bau (CLAUDE.md Regel 3: Zahlen allein gelten nicht).
Warum: Punkt-Renderer (Abtastrauschen, doppelseitig) verdeckten Gauben und taeuschten ueber Fehler; die Konsolen-Huelle fuellte tagelang unbemerkt die Arkadenboegen.
  /media/oem/scan/venv-seg/bin/python -I tools/modell_ansehen.py modell.stl aus.jpg [az el]...   (Hauptfassade des Kaufhauses: az 180; Blick entlang +y)"""
import sys,trimesh,numpy as np,cv2
def rot(az,el):
    a,e=np.radians(az),np.radians(el)
    Rz=np.array([[np.cos(a),-np.sin(a),0],[np.sin(a),np.cos(a),0],[0,0,1]]);Rx=np.array([[1,0,0],[0,np.cos(e),-np.sin(e)],[0,np.sin(e),np.cos(e)]]);return Rx@Rz
def render(m,az,el,W=1000,H=800):
    R=rot(az,el);V=m.vertices@R.T;F=m.faces;N=m.face_normals@R.T
    lo=V.min(0);hi=V.max(0);s=min(W/(hi[0]-lo[0]),H/(hi[2]-lo[2]))*.95
    X=(V[:,0]-lo[0])*s+10;Y=H-10-(V[:,2]-lo[2])*s;D=V[:,1]
    L=np.array([-.4,-.8,.5]);L/=np.linalg.norm(L);vis=N[:,1]<0.02    # Blick entlang +y: sichtbar wenn Normale zum Betrachter (-y)
    sh=(np.clip(-N@L*-1,0,1)*0.0)
    sh=np.clip(N@L,0,1);col=(60+180*sh).astype(int)
    dep=D[F].mean(1);o=np.argsort(-dep);img=np.full((H,W,3),30,np.uint8)
    for i in o:
        if not vis[i]:continue
        p=np.stack([X[F[i]],Y[F[i]]],1).astype(np.int32);c=int(col[i]);cv2.fillConvexPoly(img,p,(c,c,c))
    return img
if __name__=='__main__':
    m=trimesh.load(sys.argv[1]);cv2.imwrite(sys.argv[2],np.hstack([render(m,float(sys.argv[i]),float(sys.argv[i+1])) for i in range(3,len(sys.argv),2)]))
