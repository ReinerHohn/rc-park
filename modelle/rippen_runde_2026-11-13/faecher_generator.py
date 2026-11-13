import json, math, numpy as np
f="modelle/kaufhaus_grob3/objekt.json"; o=json.load(open(f))
AC=12.27   # Achteckmitte n: n_front 13.84 - Apothem 1.3/2/tan(22.5 Grad)
ZT, ZF = 8.12, 6.45
nsurf=lambda z: float(np.interp(z,[6.45,6.9,7.2,7.4,7.6,7.8,8.12],[12.55,12.70,13.00,13.25,13.43,13.63,13.78]))
W=lambda z: 0.30+(0.665-0.30)*(z-ZF)/(ZT-ZF)       # halbe Facettenbreite top 0.665 (gemessen 1.33/2), Fuss 0.30 (ANNAHME)
def rippe(a0,a1,form,um,theta,N=26):
    pts=[]
    for h in np.linspace(0,1,N):
        z=ZT-(ZT-ZF)*h
        g={"aussen":h**1.6,"kreuz":h*h*(3-2*h),"mitte":h}[form]
        s=a0+(a1-a0)*g
        du=W(z)*s; rho=nsurf(z)-AC; th=math.radians(theta)
        pts.append([round(um+rho*math.sin(th)+du*math.cos(th),3), round(AC+rho*math.cos(th)-du*math.sin(th),3), round(z,3)])
    nrm=[round(0.796*math.sin(th),3),round(0.796*math.cos(th),3),-0.605]
    return {"pfad":pts,"normale":nrm}
RIB=[(-1,0.8,"kreuz"),(1,-0.8,"kreuz"),(0,0,"mitte"),(0,-0.7,"kreuz"),(0,0.7,"kreuz"),(-1,-0.85,"aussen")]
for b in o["bauteile"]:
    if not b["typ"].startswith("erker_polygon"): continue
    um=b["u_mitte"]; r=b["unterbau"]["rippen_pfade"]; liste=[]
    for th in (0,45,-45):
        for a0,a1,fm in RIB: liste.append(rippe(a0,a1,fm,um,th))
    liste.append(rippe(1,0.85,"aussen",um,-45))       # rechter Rand der letzten Flaeche
    r["pfade"]=[liste[2]["pfad"]]; r["normale"]=liste[2]["normale"]; r["pfade_ohne_spiegel"]=liste[:2]+liste[3:]
    r["spiegel_u"]=None
    r["quelle_faecher"]="13.11.2026 ANNAHME-FAECHER (Nutzerwahl 'Faecher aus Messpunkten'): je Flaeche 6 Rippen (2 Kreuzbogen, Mittelrippe, 2 Mittelknauf-Boegen, linker Randbogen) + rechter Randbogen der letzten Flaeche, Flaeche 0/+45/-45 Grad um die Achteckmitte (u_mitte, n 12,27). Gemessen: Fuss u15,81 n12,48 z6,47 und Knaeufe vorn u16,20/14,87 n13,8 z8,12 (Triangulation K-6261/K-6162, Strahlabstand 3-9 cm); n(z) der Kegelflaeche aus den bisherigen gemessenen Pfaden (z6,45 12,55 ... z8,12 13,75; oben 4 cm zurueck wegen Abnahme Reichweite z8,0 <= 1,48). ANNAHME: Rippenzahl (Sichtzaehlung K-6162 ~7, nicht im Zaehlprotokoll), Bogenformen, Fussbreite 0,30 m. Ersetzt die 24 Fragmentpfade."
    r["quelle"]=r["quelle"]+" || 13.11. ersetzt durch Faecher, siehe quelle_faecher"
    print(b["u_mitte"],len(r["pfade_ohne_spiegel"])+1,"Rippen")
json.dump(o,open(f,"w"),indent=1,ensure_ascii=False)
