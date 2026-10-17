#!/usr/bin/env python3
"""light_prep.py — schneidet automatisch LICHT-GEOMETRIE in ein Druckmodell:
  - LED-Taschen (Durchmesser/Tiefe) MIT Ausrichtung (Lichtkegel zeigt in dir)
  - Kabelkanäle von der Tasche zur Basis
  - Glasfaser-Bohrungen von Oberflächenpunkten zu einem Sammel-Schacht
  - Sammel-Schacht (dort treffen Faserbündel + Einspeise-LED)
→ Beleuchtung ist nach dem Druck quasi nur noch „LED/Faser reinstecken".

Lichtliste als JSON (--lights) oder im Code. Boolean via manifold3d.
"""
import argparse, json, numpy as np, trimesh

def _cyl(p0, p1, r):
    return trimesh.creation.cylinder(radius=r, segment=np.array([p0, p1], float), sections=24)

def _oriented_box(center, size, zdir):
    """Quader `size`=(x,y,z), lokale +Z-Achse auf `zdir` gedreht, Mittelpunkt = center."""
    b = trimesh.creation.box(extents=size)
    zdir = np.asarray(zdir, float); zdir /= (np.linalg.norm(zdir) + 1e-9)
    T = trimesh.geometry.align_vectors([0, 0, 1.0], zdir)
    b.apply_transform(T)
    b.apply_translation(np.asarray(center, float))
    return b

def led0402_socket(pos, direction=(0, 0, 1), tol=0.15, body=(1.0, 0.5),
                   seat_depth=0.7, wire_d=0.9, wire_len=14.0, wire_dir=None):
    """0402-SMD-Steckschlitz, gekippt entlang `direction` (= Lichtaustritt, zeigt NACH AUSSEN).

    - pos      : Punkt auf der Außenfläche = Schlitzmund.
    - body     : LED-Maße (1.0 x 0.5 mm). +tol Spiel, damit NUR eine 0402 reinpasst/klemmt.
    - seat_depth: Sitztiefe; LED sitzt bündig, Lichtaustrittsfläche zeigt in `direction`.
    - Mikro-Kabelkanal Ø wire_d vom Taschenboden `wire_len` weiter nach innen
      → bricht in den (hohlen) Innenraum durch, Kabel laufen nach innen.
    Rückgabe = Schneidkörper (per difference aus dem Modell schneiden).
    """
    d = np.asarray(direction, float); d /= (np.linalg.norm(d) + 1e-9)
    pos = np.asarray(pos, float)
    bx, by = body
    # Tasche: Mund 0.3 über Fläche (sauberer Durchbruch), reicht seat_depth nach innen
    seat_center = pos - d * (seat_depth / 2) + d * 0.15
    seat = _oriented_box(seat_center, (bx + tol, by + tol, seat_depth + 0.3), d)
    # Kabelkanal vom Taschenboden Richtung Hohlraum. Default = −Lichtrichtung,
    # oder explizit wire_dir (z.B. nach innen/unten, damit Kabel in den Innenraum bricht).
    wd = np.asarray(wire_dir, float) if wire_dir is not None else -d
    wd /= (np.linalg.norm(wd) + 1e-9)
    ch0 = pos - d * seat_depth
    ch1 = ch0 + wd * wire_len
    return trimesh.util.concatenate([seat, _cyl(ch0, ch1, wire_d / 2)])

def ring_uplights(n, center_xy, z, radius, tilt_in_deg=20.0, phase_deg=0.0, **kw):
    """n LED-Schlitze im Kreis (Trommelkranz). Lichtkegel nach OBEN, um tilt_in_deg
    nach INNEN (zur Achse) gekippt — wie echte Flutlichter am Kuppelfuß."""
    out = []
    t = np.radians(tilt_in_deg)
    for i in range(n):
        a = 2 * np.pi * i / n + np.radians(phase_deg)
        px = center_xy[0] + radius * np.cos(a)
        py = center_xy[1] + radius * np.sin(a)
        radial = np.array([np.cos(a), np.sin(a), 0.0])     # nach außen
        d = np.array([0, 0, 1.0]) * np.cos(t) - radial * np.sin(t)  # hoch + nach innen
        wdir = -radial - np.array([0, 0, 1.2])             # Kabel: nach innen + runter → Hohlraum
        out.append({"type": "led0402", "pos": [px, py, z], "dir": list(d),
                    "wire_dir": list(wdir), **kw})
    return out

def row_uplights(pts, face_normal, up_tilt_deg=25.0, **kw):
    """LED-Schlitze auf einer Linie (Fassadenfuß). Lichtkegel nach OBEN, um up_tilt_deg
    IN die Wand gekippt (face_normal = Außennormale der Wand)."""
    out = []
    n = np.asarray(face_normal, float); n /= (np.linalg.norm(n) + 1e-9)
    t = np.radians(up_tilt_deg)
    d = np.array([0, 0, 1.0]) * np.cos(t) - n * np.sin(t)   # hoch + in die Wand
    for p in pts:
        out.append({"type": "led0402", "pos": list(p), "dir": list(d), **kw})
    return out

def backlight(pos, out_normal, wire_len=14.0, wire_d=0.9, **kw):
    """Fenster-Hinterleuchtung: LED sitzt INNEN direkt hinter der Fensteröffnung,
    strahlt nach AUSSEN (out_normal). Kabelkanal nach innen."""
    return {"type": "led0402", "pos": list(pos), "dir": list(out_normal),
            "wire_len": wire_len, "wire_d": wire_d, **kw}

def through_bore(pos, direction=(0, 0, 1), d=3.5, through=22.0, overshoot=1.2):
    """Echte runde DURCHBOHRUNG durch die Wand in den Hohlraum (0%-Infill).

    - pos       : Punkt auf der Außenfläche = Lochmund (klar sichtbares rundes Loch).
    - direction : Bohrrichtung = Lichtaustritt, zeigt NACH AUSSEN (Außennormale).
    - d         : Lochdurchmesser (Ø3–4 mm). 0805-LED wird von INNEN reingesteckt.
    - through   : wie weit nach innen gebohrt wird (muss in den Hohlraum durchbrechen).
    - overshoot : wie weit der Schneider nach außen übersteht (sauberer Durchbruch).
    Rückgabe = Schneidzylinder (per difference aus dem Modell schneiden).
    """
    d_ = np.asarray(direction, float); d_ /= (np.linalg.norm(d_) + 1e-9)
    pos = np.asarray(pos, float)
    p_out = pos + d_ * overshoot          # knapp außerhalb der Fläche
    p_in = pos - d_ * through             # tief innen (im Hohlraum)
    return _cyl(p_out, p_in, d / 2)


def led_seat(pos, direction=(0, 0, 1), led=(2.0, 1.25), tol=0.5, seat_depth=1.0,
             bore_d=1.8, through=6.0, overshoot=1.0):
    """Selbst-ausrichtende LED-SITZTASCHE (Senkung) + Lichtloch dahinter.

    - pos       : Punkt auf der Außenfläche = Taschenmund.
    - led       : 0805-Maße (2.0×1.25 mm). +tol Klebespiel.
    - seat_depth: flache Tasche, Boden SENKRECHT zu `direction` → LED fällt plan
                  rein und sitzt automatisch gerade (kein Ausrichten, nur kleben).
    - bore_d/through: kleineres Loch vom Taschenboden `through` mm nach innen in den
                  Hohlraum (Licht tritt aus + Kabel laufen durch).
    Rückgabe = Schneidkörper.
    """
    d = np.asarray(direction, float); d /= (np.linalg.norm(d) + 1e-9)
    pos = np.asarray(pos, float)
    lx, ly = led
    box_h = seat_depth + overshoot
    center = pos + d * (overshoot / 2.0) - d * (seat_depth / 2.0)
    seat = _oriented_box(center, (lx + tol, ly + tol, box_h), d)
    b0 = pos - d * (seat_depth - 0.3)      # knapp über dem Taschenboden (sauberer Durchbruch)
    b1 = pos - d * through                  # tief innen (Hohlraum)
    bore = _cyl(b0, b1, bore_d / 2)
    return trimesh.util.concatenate([seat, bore])


def led_pocket(pos, direction, led_d=3.2, depth=5.0, wire_d=1.8, base_z=0.0):
    """Tasche: LED sitzt am Boden, Lichtkegel zeigt in 'direction'. + Kabelkanal zur Basis."""
    d = np.array(direction, float); d = d/ (np.linalg.norm(d)+1e-9)
    pos = np.array(pos, float)
    mouth = pos                      # Öffnung an der Oberfläche
    bottom = pos - d*depth           # LED-Boden (entgegen Lichtrichtung)
    pocket = _cyl(mouth + d*0.5, bottom, led_d/2)     # etwas über Oberfläche für sauberen Durchbruch
    wire = _cyl(bottom, [bottom[0], bottom[1], base_z-1], wire_d/2)   # Kanal gerade runter zur Basis
    return trimesh.util.concatenate([pocket, wire])

def fiber_bore(surf, collector, d=1.1):
    """Dünne Bohrung vom Oberflächenpunkt zum Sammel-Schacht."""
    return _cyl(np.array(surf,float), np.array(collector,float), d/2)

def window(pos, axis='y', w=5.0, h=6.0, depth=6.0):
    """Echte Fenster-/Tür-ÖFFNUNG durch die Wand (Licht tritt NUR hier aus)."""
    if axis=='y':   ext=[w, depth, h]
    elif axis=='x': ext=[depth, w, h]
    else:           ext=[w, h, depth]
    b=trimesh.creation.box(extents=ext); b.apply_translation(pos); return b

def collector(pos, d=12.0, h=9.0):
    """Sammel-Schacht (Zylinder) an der Basis: Faserbündel + 1 LED."""
    pos=np.array(pos,float)
    return _cyl(pos+[0,0,h], pos+[0,0,-1], d/2)

def prep(mesh, lights, base_z=0.0):
    cutters=[]
    coll_pos=None
    for L in lights:
        t=L["type"]
        if t=="collector":
            coll_pos=L["pos"]; cutters.append(collector(L["pos"], L.get("d",12), L.get("h",9)))
    for L in lights:
        t=L["type"]
        if t=="led":
            cutters.append(led_pocket(L["pos"], L.get("dir",[0,0,1]), L.get("led_d",3.2),
                                      L.get("depth",5), L.get("wire_d",1.8), base_z))
        elif t=="fiber":
            tgt=L.get("to", coll_pos)
            cutters.append(fiber_bore(L["pos"], tgt, L.get("d",1.1)))
        elif t=="window":
            cutters.append(window(L["pos"], L.get("axis",'y'), L.get("w",5), L.get("h",6), L.get("depth",6)))
        elif t=="led0402":
            cutters.append(led0402_socket(L["pos"], L.get("dir",[0,0,1]), L.get("tol",0.15),
                                          tuple(L.get("body",[1.0,0.5])), L.get("seat_depth",0.7),
                                          L.get("wire_d",0.9), L.get("wire_len",14.0), L.get("wire_dir")))
        elif t=="bore":
            cutters.append(through_bore(L["pos"], L.get("dir",[0,0,1]), L.get("d",3.5),
                                        L.get("through",22.0), L.get("overshoot",1.2)))
        elif t=="seat":
            cutters.append(led_seat(L["pos"], L.get("dir",[0,0,1]), tuple(L.get("led",[2.0,1.25])),
                                    L.get("tol",0.5), L.get("seat_depth",1.0), L.get("bore_d",1.8),
                                    L.get("through",6.0), L.get("overshoot",1.0)))
        elif t=="port":
            # Kabel-Austritt an der Basis (senkrechter Kanal nach unten raus)
            p=np.array(L["pos"],float)
            cutters.append(_cyl(p+[0,0,L.get("up",6)], p+[0,0,-1.5], L.get("d",3.0)/2))
    cut=trimesh.util.concatenate(cutters)
    out=mesh.difference(cut)            # manifold3d
    return out

def demo_house():
    """Hohles Häuschen 40x30x35 (Wand 1.6) mit LED-Uplight + 4 Fenster-Fasern + Sammel-Schacht."""
    outer=trimesh.creation.box(extents=[40,30,35]); outer.apply_translation([20,15,17.5])
    inner=trimesh.creation.box(extents=[40-3.2,30-3.2,35]); inner.apply_translation([20,15,17.5+1.6])
    shell=outer.difference(inner)
    lights=[
        {"type":"collector","pos":[20,15,0],"d":12,"h":9},
        {"type":"led","pos":[20,15,8],"dir":[0,0,1],"led_d":5.4,"depth":8},   # Boden-Uplight (5mm), offen zur Basis
        # echte FENSTER-Öffnungen (Licht tritt nur hier aus)
        {"type":"window","pos":[11,0.8,22],"axis":"y","w":5,"h":7},
        {"type":"window","pos":[29,0.8,22],"axis":"y","w":5,"h":7},
        {"type":"window","pos":[11,0.8,11],"axis":"y","w":5,"h":7},
        {"type":"window","pos":[29,0.8,11],"axis":"y","w":5,"h":7},
        {"type":"window","pos":[20,0.8,8],"axis":"y","w":7,"h":12},           # Tür
        {"type":"window","pos":[0.8,15,20],"axis":"x","w":6,"h":7},           # Seitenfenster
        {"type":"window","pos":[39.2,15,20],"axis":"x","w":6,"h":7},
    ]
    return prep(shell, lights, base_z=0.0), lights

def main():
    p=argparse.ArgumentParser()
    p.add_argument("input", nargs="?")
    p.add_argument("--lights", help="JSON-Datei mit Lichtliste")
    p.add_argument("--out", default="/tmp/light_prepped.stl")
    p.add_argument("--demo", action="store_true")
    a=p.parse_args()
    if a.demo:
        m,lights=demo_house()
    else:
        m=trimesh.load(a.input, force="mesh")
        lights=json.load(open(a.lights))
        m=prep(m, lights)
    m.export(a.out)
    print(f"watertight={m.is_watertight} faces={len(m.faces):,} -> {a.out}")

if __name__=="__main__":
    main()
