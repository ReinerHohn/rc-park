# Methode: Gebäude-Generator als Basisklasse (konkrete Gebäude = Konfiguration)

Ziel: EIN wiederverwendbares Grundgerüst, das die GEMEINSAME Gebäudestruktur parametrisch baut; ein
konkretes Gebäude (Kaufhaus, Nachbar Wentzingerhaus, …) ist nur eine KONFIG + optionale Overrides.
Entwickelt aus `tools/kaufhaus_measured.py` (hat alle Element-Funktionen schon — sie müssen nur von der
Modul-Konstante auf die Konfig umgestellt werden).

## Trennung: Daten/Konfig  ↔  Geometrie-Engine
Der teuerste Fehler dieser Session war, Massing/Details als Modul-Konstanten fest zu verdrahten. Die
Basisklasse trennt sauber:
- **Konfig je Gebäude** (JSON / Dataclass): Massing + Stückzahlen + Feature-Flags + Element-Parameter.
- **Engine (Basisklasse)**: parametrische Element-Methoden, die NUR aus der Konfig lesen.

## Basisklasse `Bauwerk`
```python
@dataclass
class BauwerkConfig:
    name: str
    # Massing (aus LOD2, amtlich):
    W: float; D: float; eave: float; ridge: float; dachtyp: str   # "satteldach"/"walmdach"/"flach"
    # Stückzahlen (aus Fotos/DOP, Grundwahrheit):
    n_arch: int = 0; n_window: int = 0; n_statue: int = 0
    dormer_rows: list = ()                                       # z.B. [3,2]; [] = keine
    # Feature-Flags (hat das Gebäude das Element?):
    has_arcade=False; has_balcony=False; has_oriels=False
    has_statues=False; has_dormers=False; has_treppengiebel=False
    # Element-Parameter (aus Foto-Messung; Defaults = neutral):
    win_shoulder=0.60; win_dip=0.05; win_keel=1.7; arc_bw=0.81
    colors: dict = field(default_factory=lambda: {"wand":[116,38,34], "dach":[96,108,74], "gold":[198,168,120]})

class Bauwerk:
    def __init__(self, cfg): self.cfg = cfg
    # --- parametrische Elemente (aus kaufhaus_measured.py übernehmen, cfg statt Konstante) ---
    def facade_wall(self): ...      # Wand + Fensterlöcher (measured_window Kielbogen)
    def roof(self): ...             # nach cfg.dachtyp
    def gables(self): ...
    def windows(self): ...          # Kielbogen (shoulder/dip/keel aus cfg), Pfosten/Kämpfer/Saddle-Bars
    def arcade(self): ...           # Pfeiler + Bögen + Archivolte (nur wenn has_arcade)
    def balcony(self): ...          # nur wenn has_balcony
    def oriels(self): ...           # Bucht + Spitzhelm + Geästel + Wappenschilde (nur wenn has_oriels)
    def dormers(self): ...          # Raster aus cfg.dormer_rows
    def statues(self): ...          # nur wenn has_statues
    def build(self):                # baut NUR die aktivierten Features → GLB + farbgetrennte STLs
        parts = {"waende": self.facade_wall(), "dach": self.roof(), ...}
        if self.cfg.has_arcade:  parts |= self.arcade()
        if self.cfg.has_oriels:  parts |= self.oriels()
        ...
```

## Konkrete Gebäude = Konfig
- **Kaufhaus** (voll detailliert): `BauwerkConfig(W=24.1, D=20, eave=9.7, ridge=21.4, dachtyp="satteldach",
  n_arch=4, n_window=5, n_statue=4, dormer_rows=[3,2], has_arcade=True, has_balcony=True, has_oriels=True,
  has_statues=True, has_dormers=True, has_treppengiebel=True, win_shoulder=0.6, win_dip=0.05, arc_bw=0.81)`
- **Wentzingerhaus (Nachbar, weniger Detail)**: eigene Konfig aus LOD2 (DEBW_0010007Tv9k, 21×17×19.5,
  Walm/Sattel) + Fotos; vermutlich `has_arcade=False, has_oriels=False, has_statues=False` → die Engine
  baut automatisch das schlichtere Gebäude. NUR die abweichenden Elemente überschreiben (Subclass).

## Pipeline je neues Gebäude (reproduzierbar, Low-Hanging-Fruit zuerst)
1. **LOD2**: `lod2_gebaeude.py --name "<Name>"` → W/D/Traufe/First/Dachtyp (amtlich) → Konfig-Massing.
   (Gebäude per `<gml:name>` wählen, NICHT blind per Koordinate — sonst Nachbar.)
2. **DOP**: Dachplan → Gauben-Lage/Anzahl, Umriss.
3. **Fotos**: Stückzahlen (Bögen/Fenster/Statuen) + Element-Parameter (Kielbogen-Schulter/-Dip via
   `shape_extract`, Arkade via Pfeiler-Detektion). Feature-Flags setzen (hat es Arkade/Erker/…?).
4. **build()** → GLB + Flachteile + 3D-HTML.
5. **Prüfen**: `kaufhaus_check_alle.py` (→ generisch `bauwerk_check.py`): Massing-vs-LOD2 + Degeneracy +
   Kanten-Gate + fenster_detail. Prioritätenliste abarbeiten. Detail GROSS selbst ansehen.
6. Iterieren bis Ratsche grün + Augen-PASS.

## Element-Bibliothek (schon vorhanden in kaufhaus_measured.py → in die Engine heben)
Kielbogen-Fenster (shoulder/dip/keel, parametrisch-gültig+Guard), gestufter Kämpfer, Saddle-Bars,
Arkade (Pfeiler+Archivolt-Ring, ARC_BW=lichte Weite/Pitch), Balkon, Erker (Bucht+Glockenhelm+Geästel+
Wappenschild), Gauben (versetztes Raster), Treppengiebel, Gesims/Konsolen, Statuen+Baldachin.
Jede Methode: Form parametrisch, Stückzahl aus Konfig, nie freie Multiplikatoren auf Messungen.

## Nächster Schritt
`tools/bauwerk_generator.py` anlegen (Basisklasse), die Element-Funktionen 1:1 aus kaufhaus_measured.py
übernehmen (Konstante→cfg), Kaufhaus-Konfig + Wentzingerhaus-Konfig als zwei JSONs. Siehe auch
METHODE_BAUWERK_AUS_DATEN.md (Daten-Pipeline) + FEHLER_ZUSAMMENFASSUNG.md (was die Checker abfangen).
