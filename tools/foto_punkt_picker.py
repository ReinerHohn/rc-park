#!/usr/bin/env python3
"""foto_punkt_picker.py — erzeugt eine eigenständige HTML-Seite zum PRÄZISEN Markieren von
Modell-Passpunkten in einem Foto (Handy/Desktop). Du klickst die bekannten Bauwerks-Punkte
(Bogen-Scheitel, Kämpfer …), die Seite kennt deren 3D-Koordinaten → gibt eine fertige
Overlay-Config aus. tools/foto_modell_overlay.py rendert damit das 3D-Modell halbtransparent.

Lupe + Zoom/Pan für Pixel-Genauigkeit; Schema zeigt, WELCHEN Punkt du gerade klickst.

  python3 tools/foto_punkt_picker.py --foto <jpg> --f-mm 10 --sensor-mm 22.3 \
      --stl modelle/ravenna/ravenna_viadukt_echt.stl --out picker.html
Dann picker.html öffnen, Punkte klicken, am Ende JSON kopieren → als Config speichern.
"""
import argparse, base64, json, io
import numpy as np, cv2

L, N, PP, R, ZS = 224.0, 9, 224.0/9, 10.0, 36*0.61
def xc(k): return -L/2 + (k+0.5)*PP


def viaduct_landmarks():
    """Reihenfolge = Klick-Reihenfolge. Jeder: name, 3D (mx,my,mz), schema-x(0..1), schema-y(0..1)."""
    lm = []
    sx = lambda x: (x + L/2) / L                       # modell-x → schema 0..1
    for k in range(N):
        c = xc(k)
        lm.append(dict(name=f"Bogen {k+1}: Scheitel (oben Mitte)", mx=c, my=0, mz=31.96,
                       sx=sx(c), sy=0.22))
        lm.append(dict(name=f"Bogen {k+1}: Kämpfer LINKS (Bogen trifft Pfeiler)", mx=c-R, my=0, mz=21.96,
                       sx=sx(c-R), sy=0.5))
        lm.append(dict(name=f"Bogen {k+1}: Kämpfer RECHTS", mx=c+R, my=0, mz=21.96,
                       sx=sx(c+R), sy=0.5))
    return lm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--foto", required=True)
    ap.add_argument("--stl", default="modelle/ravenna/ravenna_viadukt_echt.stl")
    ap.add_argument("--f-mm", type=float, required=True)
    ap.add_argument("--sensor-mm", type=float, required=True)
    ap.add_argument("--emb-w", type=int, default=1600, help="eingebettete Bildbreite (Klick-Raum)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    img = cv2.imread(a.foto); H0, W0 = img.shape[:2]
    ew = a.emb_w; eh = int(H0*ew/W0)
    small = cv2.resize(img, (ew, eh))
    ok, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 85])
    b64 = base64.b64encode(buf).decode()
    LM = viaduct_landmarks()

    cfg_head = dict(foto=a.foto, stl=a.stl, f_mm=a.f_mm, sensor_mm=a.sensor_mm, emb_w=ew)
    HTML = f"""<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1,maximum-scale=4">
<title>Passpunkte markieren — Ravennaviadukt</title>
<style>
 body{{margin:0;background:#111;color:#eee;font-family:system-ui;overflow:hidden;touch-action:none}}
 #bar{{position:fixed;top:0;left:0;right:0;background:#1b2430;padding:8px 10px;z-index:9;font-size:14px}}
 #bar b{{color:#7cf}} #hint{{color:#fd6}}
 #schema{{position:fixed;right:8px;top:54px;width:150px;height:60px;background:#0008;border:1px solid #345;z-index:9}}
 #wrap{{position:absolute;top:50px;bottom:0;left:0;right:0}}
 canvas{{position:absolute;left:0;top:0}}
 #loupe{{position:fixed;width:150px;height:150px;border:2px solid #7cf;border-radius:50%;
   pointer-events:none;display:none;z-index:20;box-shadow:0 0 8px #000}}
 .btn{{display:inline-block;background:#2a3a4a;border:1px solid #456;border-radius:6px;
   padding:5px 10px;margin:2px;cursor:pointer}} .btn:active{{background:#3a5a7a}}
 #out{{position:fixed;left:8px;right:8px;bottom:8px;height:70px;z-index:9;display:none}}
 textarea{{width:100%;height:60px;font-family:monospace;font-size:11px}}
</style></head><body>
<div id=bar>
 <b id=cnt></b> · <span id=task></span> <span id=hint></span><br>
 <span class=btn onclick=skip()>⛔ nicht sichtbar</span>
 <span class=btn onclick=undo()>↶ zurück</span>
 <span class=btn onclick=finish()>✔ fertig → JSON</span>
 <span class=btn onclick=zin()>＋</span><span class=btn onclick=zout()>－</span>
 <span class=btn onclick=reset()>⟳</span>
</div>
<canvas id=schema></canvas>
<div id=wrap><canvas id=cv></canvas></div>
<canvas id=loupe width=150 height=150></canvas>
<div id=out><textarea id=ta readonly></textarea></div>
<script>
const IMGW={ew}, IMGH={eh};
const LM={json.dumps(LM)};
const HEAD={json.dumps(cfg_head)};
const img=new Image(); img.src="data:image/jpeg;base64,{b64}";
const cv=document.getElementById('cv'), cx=cv.getContext('2d');
const lp=document.getElementById('loupe'), lx=lp.getContext('2d');
const sc=document.getElementById('schema'), sx=sc.getContext('2d');
let scale=1, ox=0, oy=0, i=0, picks=[]; // picks: idx,u,v in image space
function fit(){{const W=innerWidth,H=innerHeight-50;cv.width=W;cv.height=H;
  scale=Math.min(W/IMGW,H/IMGH);ox=(W-IMGW*scale)/2;oy=(H-IMGH*scale)/2;draw();}}
function draw(){{cx.setTransform(1,0,0,1,0,0);cx.clearRect(0,0,cv.width,cv.height);
  cx.setTransform(scale,0,0,scale,ox,oy);cx.drawImage(img,0,0);
  for(const p of picks){{cx.fillStyle='#f33';cx.beginPath();cx.arc(p.u,p.v,5/scale,0,7);cx.fill();
    cx.fillStyle='#fff';cx.font=(14/scale)+'px sans';cx.fillText(p.idx+1,p.u+7/scale,p.v);}}
  updbar();drawschema();}}
function updbar(){{document.getElementById('cnt').textContent=picks.length+' Punkte';
  document.getElementById('task').textContent = i<LM.length? ('➤ '+LM[i].name) : 'alle Punkte durch';
  document.getElementById('hint').textContent = i<LM.length? '(Klick ins Foto, Lupe hilft)':'';}}
function drawschema(){{const W=150,Hh=60;sc.width=W;sc.height=Hh;sx.clearRect(0,0,W,Hh);
  sx.strokeStyle='#8ab';sx.fillStyle='#8ab';
  // 9 Bögen schematisch
  for(let k=0;k<9;k++){{const bx=(k+0.5)/9*W;sx.beginPath();
    sx.arc(bx,Hh*0.55,W/9*0.42,Math.PI,0);sx.stroke();}}
  sx.strokeRect(2,Hh*0.2,W-4,Hh*0.75);
  if(i<LM.length){{sx.fillStyle='#f33';sx.beginPath();
    sx.arc(LM[i].sx*W,LM[i].sy*Hh*0.9+Hh*0.12,4,0,7);sx.fill();}}
}}
function toImg(ev){{const r=cv.getBoundingClientRect();const px=ev.clientX-r.left,py=ev.clientY-r.top;
  return {{u:(px-ox)/scale, v:(py-oy)/scale, px, py}};}}
let dragged=false,lastX,lastY,down=false;
cv.addEventListener('pointerdown',e=>{{down=true;dragged=false;lastX=e.clientX;lastY=e.clientY;}});
cv.addEventListener('pointermove',e=>{{
  const t=toImg(e);
  if(down){{const dx=e.clientX-lastX,dy=e.clientY-lastY;if(Math.abs(dx)+Math.abs(dy)>3){{dragged=true;
    ox+=dx;oy+=dy;lastX=e.clientX;lastY=e.clientY;draw();}}}}
  // Lupe
  if(t.u>=0&&t.u<IMGW&&t.v>=0&&t.v<IMGH){{lp.style.display='block';
    lp.style.left=(e.clientX-75)+'px';lp.style.top=(e.clientY-165)+'px';
    lx.clearRect(0,0,150,150);lx.save();lx.beginPath();lx.arc(75,75,75,0,7);lx.clip();
    const z=6;lx.drawImage(img,t.u-75/z,t.v-75/z,150/z,150/z,0,0,150,150);
    lx.strokeStyle='#7cf';lx.beginPath();lx.moveTo(75,60);lx.lineTo(75,90);lx.moveTo(60,75);lx.lineTo(90,75);lx.stroke();lx.restore();}}
  else lp.style.display='none';
}});
cv.addEventListener('pointerup',e=>{{down=false;lp.style.display='none';
  if(!dragged && i<LM.length){{const t=toImg(e);
    if(t.u>=0&&t.u<IMGW&&t.v>=0&&t.v<IMGH){{picks.push({{idx:i,u:t.u,v:t.v}});i++;draw();}}}}}});
cv.addEventListener('wheel',e=>{{e.preventDefault();const t=toImg(e);const f=e.deltaY<0?1.2:1/1.2;
  scale*=f;ox=e.clientX-(cv.getBoundingClientRect().left)-t.u*scale;oy=(e.clientY-cv.getBoundingClientRect().top)-t.v*scale;draw();}},{{passive:false}});
function zin(){{scale*=1.3;draw();}} function zout(){{scale/=1.3;draw();}} function reset(){{fit();}}
function skip(){{if(i<LM.length){{i++;draw();}}}}
function undo(){{if(picks.length&&picks[picks.length-1].idx==i-1){{picks.pop();}}if(i>0)i--;draw();}}
function finish(){{const corr=picks.map(p=>[+LM[p.idx].mx.toFixed(2),LM[p.idx].my,+LM[p.idx].mz.toFixed(2),
    Math.round(p.u),Math.round(p.v)]);
  const cfg=Object.assign({{}},HEAD,{{corr}});
  const ta=document.getElementById('ta');document.getElementById('out').style.display='block';
  ta.value=JSON.stringify(cfg,null,1);ta.select();
  try{{const b=new Blob([ta.value],{{type:'application/json'}});const a=document.createElement('a');
    a.href=URL.createObjectURL(b);a.download='overlay_config.json';a.click();}}catch(e){{}}
}}
img.onload=fit; window.addEventListener('resize',fit);
</script></body></html>"""
    open(a.out, "w").write(HTML)
    print(f"-> {a.out} ({len(HTML)//1024} kB)  — im Browser öffnen, {len(LM)} Punkte klickbar")
    print("  Nicht sichtbare Bögen einfach überspringen (⛔). Min. ~6 Punkte, gut verteilt.")


if __name__ == "__main__":
    main()
