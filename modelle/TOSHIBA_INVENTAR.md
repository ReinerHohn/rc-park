# Toshiba-Auslagerung: Inventar (Stand 2026-11-08 14:30)

## ZWEI Toshiba-Platten (beide Label "TOSHIBA EXT", beide NTFS, gleicher Mountpunkt `/media/oem/TOSHIBA EXT`!)
Das Skript `tools/auslagern.sh` prueft mit `AUSLAGERN_UUID`, dass die richtige Platte haengt. Immer UUID setzen!

| | Platte A (alt, 466 GB) | Platte B (neu, 931 GB) |
|---|---|---|
| UUID | `10B8430EB842F1B0` | `84B82792B82781B2` |
| Modell / Seriennr. | MQ01ABF050 / Y3CUCH8FT | MQ04UBF100 / X817TFPTT |
| Ordner mit unseren Daten | `rc-park_auslagern/` (51 GB, siehe unten) | `rc-park_auslagern2/` (ab 8.11. 14:2x) |
| Stand | voll (1,2 MB frei), 8.11. abgezogen | 173 GB frei vor dem Auslagern |
| Symlinks im Repo/`/media/oem/scan` | zeigen auf `.../TOSHIBA EXT/rc-park_auslagern/...`: **tot, solange A nicht haengt** | zeigen auf `.../TOSHIBA EXT/rc-park_auslagern2/...` |

Hinweis: Die Symlinks zu Platte A sind seit dem Anstecken von B tot (gleicher Pfad, andere Platte). Platte A anstecken, dann sind sie wieder gueltig; haengen A und B gleichzeitig, bekommt eine den Mountpunkt `TOSHIBA EXT1` und die Symlinks passen nicht mehr: dann Symlinks per `ln -sfn` umsetzen.
Auf B liegen ebenfalls private Daten des Nutzers (Familienvideos, ca. 760 GB): nichts davon anfassen oder auflisten.

## Platte B: `rc-park_auslagern2/` (neu)
Ausgelagert am 8.11. (alle kalt, Originale ersetzt durch Symlink):
`rc-park_null/` : `diffpar` (16 G, alte Diff-Jagd), `lo_fus` (5,1 G), `wettbewerb_kh` (3,6 G), `kreislauf` (0,5 G), `gschleife_alles`, `gschleife_stufe1`, `gschleife_bog` (je ~0,3 G), `limap` (0,3 G), `wettbewerb_kh17_V3` (0,2 G).
Weitere Auslagerungen: Ordner hier anhaengen (Stand pruefen mit `ls /media/oem/TOSHIBA\ EXT/rc-park_auslagern2/*`).

## Platte A (alt): Inhalt

## RC-Park-Daten: `rc-park_auslagern/` (51 GB)
Originalpfad = Pfad unter `rc-park_auslagern/` ersetzt durch `/media/oem/scan/`. Die Beschreibung stammt aus Ordnernamen und Projektnotizen, nicht jede Datei wurde geöffnet.

### `rc-park_daten/` (9,9 GB)
| Ordner | Größe | Inhalt |
|---|---|---|
| `martinstor/` | 8,0 G | **Alles zum Martinstor**: `sfm` 1,0 G, `video_sfm` 1,8 G, `videos` 1,3 G, `video_frames` 0,8 G, `fotos_eingang` 1,0 G, `export` 1,2 G, `fotos`, `commons_neu`, `mapillary_neu`, `wolkenmodell`, `modell_sicherung_2026-11-03` |
| `freiburg_stadt/` | 1,6 G | Stadt-Freiburg-Quellen: `lod2` 1,5 G, `mesh`, `fehlerbudget` (Lizenz laut `QUELLEN_REGISTER.md`) |
| `test_fd_2026-11-06/` | 0,3 G | foto_diff-Tests Kaufhaus/Martinstor |

### `rc-park_null/` (41 GB, Nullstart-Läufe und Altversuche)
| Ordner | Größe | Inhalt / Wert |
|---|---|---|
| `kaufhaus_handy3/` | 20 G | Handyfoto-Lauf Kaufhaus: `dicht_neu` 15 G (dichte Wolke), `dicht_neu_probe` 2,9 G, `a_m`, `npq` |
| `kaufhaus_video/` | 4,7 G | dichte Wolke aus Video (`dicht`) |
| `martinstor_lod2/` | 3,0 G | Martinstor-Nullstart mit LoD2: `sfm` 2,8 G, audit, messprotokoll, himmelsmaske |
| `gs_kh2/` | 2,0 G | Gaussian-Splatting-Versuch V1-V3 (laut Register: schlecht) |
| `martinstor_null/` | 1,3 G | Martinstor-Nullstart: `sfm` 1,1 G, hybrid, torbau |
| `wettbewerb_kh2 ... kh19` | ca. 8,5 G | Wolke-zu-Netz-Wettbewerb Kaufhaus (Poisson/OpenMVS/Varianten), je `p1`,`p2`,`masken` |
| `kaufhaus_null4/` | 0,7 G | Kaufhaus-Nullstart v4 (audit, sfm) |
| `qualitaetsstufen_kaufhaus_null5/6` | 0,3 / 0,7 G | Stufenmessungen s1-s4 |
| `s9`, `s10`, `kanten_vektor`, `beweis_ansatz` | 0,2-0,6 G | Beweis-/Kantenversuche |
| `diffpar/` | 82 MB | **Rest eines abgebrochenen Kopierversuchs** (Plattenfehler "No space"), Original liegt auf `/media/oem/scan` bzw. rcstick; löschbar |

### Sonstiges
`nubia_sortierung/` 0,4 G (Sortierlisten/Sichtblätter der Nubia-Fotos).

## Zugehörige zweite Auslagerung
Rcstick `/media/oem/rcstick/rc-park_auslagern/` (ca. 44 GB, UUID siehe `lsblk`), vom Platzwächter `tools/platz_waechter.sh` befüllt; enthält zuletzt `diffpar`, `lo_fus`, `wettbewerb_kh` (kopiert, noch nicht alle fertig).

## Neu erstellen
`tools/toshiba_inventar.sh [MOUNT]` schreibt `modelle/TOSHIBA_INVENTAR_roh.txt` (nur Lesen; HDD langsam, im Hintergrund starten). Rohdatei enthält auch private Ordnernamen und gehört nicht ins Repo.
- 2026-11-10: `/media/oem/scan/venv-limap` (6,3 GB, LIMAP-Umgebung der verworfenen Linienfeinlage BS3e) -> Platte B `rc-park_auslagern2/venv-limap`, Symlink. Hinweis: auslagern.sh erwartet AUSLAGERN_ZIEL relativ zum Mountpunkt (absoluter Pfad ergab verschachtelten Ordner, korrigiert).
