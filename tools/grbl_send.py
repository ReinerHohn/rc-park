#!/usr/bin/env python3
"""grbl_send.py — GRBL-Laser-G-Code per CLI an den Sculpfun S9 streamen.

Sicher: wacht GRBL auf, entsperrt ($X), fährt zuerst den RAHMEN bei niedriger
Leistung (zum Ausrichten), fragt nach, streamt dann mit ok-Handshake. Strg-C =
sofort Soft-Reset (Laser AUS). Nullpunkt = aktuelle Kopfposition (G92 im G-Code).

  python3 tools/grbl_send.py /tmp/laser/layer_000.gcode            # Frame -> fragen -> schneiden
  python3 tools/grbl_send.py --frame-only /tmp/laser/layer_000.gcode
  python3 tools/grbl_send.py --no-frame  /tmp/laser/layer_000.gcode
  python3 tools/grbl_send.py --port /dev/ttyUSB0 --frame-power 2 ...
"""
import argparse, sys, time, re
try:
    import serial
except ImportError:
    sys.exit("pyserial fehlt -> bash tools/laser_setup.sh (oder pip install --user pyserial)")

MOVE = re.compile(r"[XY]-?\d+\.?\d*")


def bbox(path):
    xs, ys = [], []
    for ln in open(path):
        for m in re.findall(r"X(-?\d+\.?\d*)", ln): xs.append(float(m))
        for m in re.findall(r"Y(-?\d+\.?\d*)", ln): ys.append(float(m))
    return (min(xs), min(ys), max(xs), max(ys)) if xs else (0, 0, 0, 0)


def wake(ser):
    ser.write(b"\r\n\r\n"); time.sleep(2); ser.reset_input_buffer()


def cmd(ser, line):
    ser.write((line.strip() + "\n").encode())
    while True:
        r = ser.readline().decode(errors="ignore").strip()
        if r == "" :
            continue
        if r.lower().startswith("ok"):
            return r
        if r.lower().startswith("error"):
            print(f"  GRBL {r}  (bei: {line})")
            return r


def soft_reset(ser):
    try:
        ser.write(b"\x18"); time.sleep(0.5)       # Ctrl-X = sofort Stop + Reset
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gcode")
    ap.add_argument("--port", default="/dev/ttyUSB0")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--feed", type=float, default=2000, help="Frame-Vorschub mm/min")
    ap.add_argument("--frame-power", type=float, default=2.0, help="Frame-Leistung %% (sichtbar, schneidet nicht)")
    ap.add_argument("--frame-only", action="store_true")
    ap.add_argument("--no-frame", action="store_true")
    ap.add_argument("--yes", action="store_true", help="ohne ENTER-Rückfrage schneiden (für Hintergrund-Lauf)")
    ap.add_argument("--mark", action="store_true", help="ANZEICHNEN: Umrisse 1x bei niedriger Leistung, schneidet NICHT")
    ap.add_argument("--mark-power", type=float, default=12.0, help="Leistung %% fürs Anzeichnen")
    a = ap.parse_args()

    x0, y0, x1, y1 = bbox(a.gcode)
    print(f"Job: {a.gcode}")
    print(f"Fläche: {x1-x0:.0f} x {y1-y0:.0f} mm  (X {x0:.0f}..{x1:.0f}, Y {y0:.0f}..{y1:.0f})")
    print(f"Port: {a.port} @ {a.baud}")
    print(">>> Laserkopf JETZT an die vordere-linke Ecke des Materials fahren (das wird Nullpunkt).")

    ser = serial.Serial(a.port, a.baud, timeout=2)
    try:
        wake(ser)
        cmd(ser, "$X")                       # entsperren
        cmd(ser, "G21"); cmd(ser, "G90"); cmd(ser, "G92 X0 Y0")

        if not a.no_frame:
            S = int(round(a.frame_power * 10))
            print(f"-- Frame (Leistung {a.frame_power}% ) -- zum Ausrichten")
            cmd(ser, "M5")
            cmd(ser, f"G0 X{x0:.2f} Y{y0:.2f}")
            cmd(ser, f"M4 S{S}")
            for (X, Y) in [(x1,y0),(x1,y1),(x0,y1),(x0,y0)]:
                cmd(ser, f"G1 X{X:.2f} Y{Y:.2f} F{a.feed:.0f}")
            cmd(ser, "M5"); cmd(ser, "G0 X0 Y0")
            if a.frame_only:
                print("Frame fertig."); return
        if not a.yes and not a.mark:
            try:
                input("Material ausgerichtet? ENTER = schneiden,  Strg-C = Abbruch ... ")
            except (KeyboardInterrupt, EOFError):
                print("\nabgebrochen (kein ENTER / --yes fehlt)."); soft_reset(ser); return

        import re as _re
        print(f"-- ANZEICHNEN -- ({a.mark_power:.0f}% , 1x, schneidet NICHT)" if a.mark
              else "-- SCHNEIDEN -- (Strg-C = Not-Halt)")
        out = []
        for l in open(a.gcode):
            s = l.strip()
            if s.startswith("; CUT-PASS"):                   # Pass-Marker
                k = int(s.split()[2].split("/")[0]) if len(s.split()) > 2 else 1
                if a.mark and k >= 2: break                  # Anzeichnen: nach Pass 1 stoppen
                continue
            if not s or s.startswith(";"): continue
            if a.mark:                                       # Leistung auf Mark-Power zwingen
                m = _re.search(r"M4 S\d+", l)
                if m: l = l.replace(m.group(0), f"M4 S{int(a.mark_power*10)}")
            out.append(l)
        n = max(1, len(out))
        for i, ln in enumerate(out):
            cmd(ser, ln)
            if i % 50 == 0: print(f"  {100*i//n}%")
        print("ANGEZEICHNET — jetzt prüfen, dann cutten." if a.mark else "FERTIG. Laser aus.")
        cmd(ser, "M5 S0")
    except KeyboardInterrupt:
        print("\n!! NOT-HALT (Soft-Reset) !!"); soft_reset(ser)
    finally:
        try: ser.write(b"M5 S0\n"); time.sleep(0.2); ser.close()
        except Exception: pass


if __name__ == "__main__":
    main()
