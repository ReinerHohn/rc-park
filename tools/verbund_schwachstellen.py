#!/usr/bin/env python3
"""verbund_schwachstellen.py [--db <db>] [--modell <sparse> ...] [--aus radar.json] [--teil N=<sparse> ...]   (22.11.2026, Recherche duenne Bruecken Methode 6)

SCHWACHSTELLEN-RADAR IM BILD-/SPURGRAPHEN: wo haengt ein Modell (oder der Bildverbund der Datenbank) nur an wenigen Bildern/Spuren?
WARUM: der globale Mapper ueber die 1122-Durchblick-Bruecke knickte um 16 Grad - die Bruecke waren 5 Spuren ueber EIN Bild (IMG_20261106_113937). Das sieht
man im Graphen sofort, nachher am Modell nur muehsam. Das Radar ist der AUSLOESER fuer Gegenmassnahmen (Nachmatchen, gefuehrtes Matchen, Lot-Kopplung,
seiten_eck_koppeln) - es misst nur, es aendert nichts.
GRAPH: Knoten = Bilder. Kante i-j mit Gewicht
  - Modell (--modell): Zahl gemeinsamer 3D-Punkte (Kovisibilitaet; images.bin direkt gelesen, ohne pycolmap -> laeuft in jeder Umgebung),
  - Datenbank (--db): verifizierte Inlier (two_view_geometries.rows >= DB_MIN_INLIER).
  Mehrere --modell = mehrere Teile: jeder Teil fuer sich + Zuordnung der Seiten zu Teilen; mit --db zusaetzlich der Verbund ueber alle Bilder.
MESSUNG je Zusammenhangsstueck (>= 2 x MIN_SEITE Bilder):
  1. GELENKBILDER (Artikulationspunkte, Tarjan): Bild, ohne das >= MIN_SEITE Bilder abfallen.
  2. BRUECKENKANTEN: Kante, ohne die >= MIN_SEITE Bilder abfallen.
  3. SCHWAECHSTER AUSGEWOGENER SCHNITT: Fiedler-Vektor der normierten Laplace-Matrix (Gewicht log(1 + w): ein einzelnes Paar mit 500 Inliern soll keine
     Bruecke "stark" machen), Schnittsuche ueber die Reihenfolge (kleinster Leitwert = Schnittgewicht / kleineres Volumen, beide Seiten >= MIN_SEITE).
     Am Schnitt: Kanten quer, Spuren quer (3D-Punkte mit Beobachtern auf beiden Seiten; nur Modell), Inlier quer (nur DB), KNOTEN-DISJUNKTE Wege
     (= kleinste Zahl Bilder, deren Wegfall trennt; Max-Fluss mit Knotenteilung) samt diesen Bildern, KANTEN-DISJUNKTE Wege. Dann rekursiv in beiden Seiten
     (Tiefe TIEFE), damit auch eine zweite Schwachstelle auftaucht.
  4. ALGEBRAISCHE KONNEKTIVITAET (Fiedler-Wert) je Stueck.
URTEIL je Schwachstelle (GRENZEN unten, an Daten begruendet):
  zu_duenn: knoten_disjunkt <= GELENK_MAX (das ganze Stueck haengt an einem Bild) oder spuren_quer < SPUREN_ZU_DUENN,
  duenn:    knoten_disjunkt <= DUENN_KNOTEN oder knoten_disjunkt / Bilder der kleineren Seite < DUENN_ANTEIL oder spuren_quer / Bilder der kleineren Seite < SPUREN_JE_BILD_DUENN,  sonst stark.
Ausgabe JSON (Format 'verbund_schwachstellen/1', stabil - andere Stufen lesen es, z. B. die Eskalationsleiter der Brueckenkopplung):
  {format, quelle{db, modelle}, art ('spuren'|'inlier'), stuecke[{stueck, bilder, kanten, fiedler}], urteil ('stark'|'duenn'|'zu_duenn'|'kein_graph'),
   ausloeser [ids der Schwachstellen mit urteil != stark, schlimmste zuerst] - DAS lesen Ausloeser-Stufen,
   schwachstellen[{id, stueck, art ('gelenk'|'schnitt'|'bruecke'), urteil, grund, bilder (trennende Bilder), seiten [n_a, n_b], seite_klein (<= 40 Namen),
                   staerke{spuren_quer, inlier_quer, kanten_quer, knoten_disjunkt, kanten_disjunkt, leitwert}, teile{a{teil: n}, b{teil: n}} }],
   grenzen{...}, zeile}
Exit: 0 stark, 2 duenn, 3 zu_duenn, 4 kein Graph. Synthetischer Test: tools/test_verbund_schwachstellen.py."""
import os, sys, json, struct, sqlite3, argparse
import numpy as np

MAXID = 2147483647
DB_MIN_INLIER = 15        # wie COLMAPs min_num_inliers (verifizierte Paare)
MIN_SEITE = 5             # Bilder: kleinere abfallende Stuecke sind Randbilder, keine Schwachstelle des Verbunds
TIEFE = 2
GELENK_MAX = 1
DUENN_KNOTEN = int(os.environ.get("RCPARK_RADAR_DUENN_KNOTEN", "3"))
SPUREN_ZU_DUENN = int(os.environ.get("RCPARK_RADAR_SPUREN_ZU_DUENN", "30"))
SPUREN_JE_BILD_DUENN = float(os.environ.get("RCPARK_RADAR_SPUREN_JE_BILD", "10"))
DUENN_ANTEIL = float(os.environ.get("RCPARK_RADAR_DUENN_ANTEIL", "0.15"))   # knotendisjunkte Wege / Bilder der kleineren Seite
MIN_STUECK_ANTEIL = 0.05  # Zusammenhangsstuecke unter 5 % des groessten (Fremdgruppen der Datenbank) werden nur gezaehlt, nicht untersucht
GRENZEN_BELEG = (
    "Eichung 22.11.2026 (/media/oem/rcdaten/tmp/selbsttest2/radar/): KNICK 1122 global (16 Grad): Schnitt 5 Spuren quer, 1 knotendisjunkter Weg, Gelenk "
    "IMG_20261106_113937 (Seiten 129/398) -> zu_duenn; innerer Schnitt der geknickten Haelfte 133 Spuren / 32 Bilder = 4,2 je Bild. GUTE Modelle "
    "(martinstor_gk, kaufhaus_gk, 1122 teil0_a/teil1_a): kleinster Wert 34 Spuren je Bild (Martinstor: 6 Videobilder, 202 Spuren, 5 Wege), ausgewogene "
    "Schnitte >= 64 je Bild und >= 10 Wege. Grenzen: zu_duenn bei <= 1 Weg oder < 30 Spuren (Knick 5, gut >= 202); duenn bei <= 3 Wegen (= Selbsttest-Bruecke k = 3, "
    "dort koppelt es noch mit 0,2-0,8 Grad Fehler) oder < 10 Spuren je Bild (zwischen 4,2 und 34, Faktor 3 Abstand zu beiden) oder Wege/Bilder der kleineren Seite < 0,15 (SELBSTTEST DB-Graph, "
    "A-B-Paare geloescht, nur Modellbilder: Martinstor/Kaufhaus k = 3/5/10 -> der kuenstliche Schnitt ist jedesmal der schwaechste, Wege 3/5/11 bzw. 3/5/10, "
    "Leitwert 0,014-0,070 gegen >= 0,13 innen; k = 10 hat 0,11 Wege je Bild und koppelt nicht besser als k = 5 (Stufe 1: 0,72 gegen 0,68 Grad); gute Modelle "
    "ausgewogen >= 0,32).")
UNGUELTIG = 2 ** 64 - 1


# ---------- Lesen ----------
def bilder_bin(pfad):
    """images.bin (COLMAP-Binaerformat, auch 4.x) -> {name: np.array(point3D_ids)} nur registrierte Bilder mit Punkten."""
    f = open(os.path.join(pfad, "images.bin"), "rb"); n = struct.unpack("<Q", f.read(8))[0]; aus = {}
    for _ in range(n):
        f.read(4 + 32 + 24); f.read(4); name = b""
        while True:
            c = f.read(1)
            if c == b"\x00": break
            name += c
        k = struct.unpack("<Q", f.read(8))[0]; d = np.frombuffer(f.read(24 * k), dtype=np.dtype([("x", "<f8"), ("y", "<f8"), ("p", "<u8")]))
        ids = d["p"][d["p"] != UNGUELTIG]; aus[name.decode("utf-8", "replace")] = ids.astype(np.int64)
    return aus


def graph_modell(bilder):
    """{name: point3D_ids} -> (namen, kanten {(i, j): gemeinsame Punkte}, punkt_bilder {pid: array(i)})."""
    namen = sorted(bilder); idx = {n: i for i, n in enumerate(namen)}; pi, ii = [], []
    for n in namen: p = np.unique(bilder[n]); pi.append(p); ii.append(np.full(len(p), idx[n]))
    P = np.concatenate(pi) if pi else np.zeros(0, np.int64); I = np.concatenate(ii) if ii else np.zeros(0, np.int64); o = np.argsort(P, kind="stable"); P, I = P[o], I[o]
    grenzen = np.flatnonzero(np.r_[True, P[1:] != P[:-1], True]); kanten = {}; pb = {}
    for a, b in zip(grenzen[:-1], grenzen[1:]):
        if b - a < 2: continue
        g = I[a:b]; pb[int(P[a])] = g
        for x in range(len(g)):
            for y in range(x + 1, len(g)):
                k = (int(min(g[x], g[y])), int(max(g[x], g[y]))); kanten[k] = kanten.get(k, 0) + 1
    return namen, kanten, pb


def graph_db(db, namen_filter=None, min_inlier=DB_MIN_INLIER):
    c = sqlite3.connect(f"file:{db}?immutable=1", uri=True); nm = {i: n for i, n in c.execute("select image_id, name from images")}
    roh = [(nm.get(p // MAXID), nm.get(p % MAXID), r) for p, r in c.execute("select pair_id, rows from two_view_geometries where rows >= ?", (min_inlier,))]
    roh = [(a, b, r) for a, b, r in roh if a and b and (namen_filter is None or (a in namen_filter and b in namen_filter))]
    namen = sorted({x for a, b, _ in roh for x in (a, b)}); idx = {n: i for i, n in enumerate(namen)}; kanten = {}
    for a, b, r in roh: k = (min(idx[a], idx[b]), max(idx[a], idx[b])); kanten[k] = max(kanten.get(k, 0), int(r))
    return namen, kanten


# ---------- Graphwerkzeuge (ohne networkx: die Kette laeuft auch in venv-colmap) ----------
def nachbarliste(n, kanten):
    nb = [[] for _ in range(n)]
    for (i, j), w in kanten.items(): nb[i].append((j, w)); nb[j].append((i, w))
    return nb


def stuecke(n, kanten, knoten=None):
    knoten = range(n) if knoten is None else knoten; ks = set(knoten); nb = nachbarliste(n, kanten); gesehen = set(); aus = []
    for s in knoten:
        if s in gesehen: continue
        st, comp = [s], []; gesehen.add(s)
        while st:
            v = st.pop(); comp.append(v)
            for u, _ in nb[v]:
                if u in ks and u not in gesehen: gesehen.add(u); st.append(u)
        aus.append(sorted(comp))
    return sorted(aus, key=len, reverse=True)


def gelenke_bruecken(knoten, kanten):
    """Tarjan iterativ auf dem Teilgraphen 'knoten'. -> (gelenke {v: [Groessen der abfallenden Teile]}, bruecken [(u, v, Groesse der kleineren Seite)])."""
    ks = set(knoten); nb = {v: [] for v in knoten}
    for (i, j), w in kanten.items():
        if i in ks and j in ks: nb[i].append(j); nb[j].append(i)
    disc, low, groesse = {}, {}, {}; gel = {}; br = []; t = 0; N = len(ks)
    for wurzel in knoten:
        if wurzel in disc: continue
        disc[wurzel] = low[wurzel] = t; t += 1; groesse[wurzel] = 1; st = [(wurzel, -1, iter(nb[wurzel]))]; kinder_w = 0
        while st:
            v, p, it = st[-1]; weiter = False
            for u in it:
                if u not in disc:
                    disc[u] = low[u] = t; t += 1; groesse[u] = 1; st.append((u, v, iter(nb[u]))); weiter = True
                    if v == wurzel: kinder_w += 1
                    break
                elif u != p: low[v] = min(low[v], disc[u])
            if weiter: continue
            st.pop()
            if p != -1:
                low[p] = min(low[p], low[v]); groesse[p] += groesse[v]
                if low[v] > disc[p]: br.append((p, v, min(groesse[v], N - groesse[v])))
                if p != wurzel and low[v] >= disc[p]: gel.setdefault(p, []).append(groesse[v])
                if p == wurzel and kinder_w >= 2: gel.setdefault(p, []).append(groesse[v])
    return gel, br


def max_fluss(n, kanten_kap, quelle, senke):
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import maximum_flow
    if not kanten_kap: return 0
    r = np.array([k[0] for k in kanten_kap]); c = np.array([k[1] for k in kanten_kap]); v = np.array([k[2] for k in kanten_kap], np.int32)
    M = csr_matrix((v, (r, c)), shape=(n, n)); M.sum_duplicates(); return int(maximum_flow(M, quelle, senke).flow_value)


def disjunkte_wege(S, T, kanten):
    """Zahl kanten- und knotendisjunkter Wege zwischen den Mengen S und T (Max-Fluss; Knotenteilung, Seitenknoten unbegrenzt) + trennende Bilder (min. Knotenschnitt)."""
    S, T = set(S), set(T); alle = sorted(S | T); ix = {v: i for i, v in enumerate(alle)}; n = len(alle); q, s = 2 * n, 2 * n + 1; gross = 10 ** 6
    ke = [(ix[i], ix[j], 1) for (i, j) in kanten if i in ix and j in ix] ; ke += [(b, a, 1) for a, b, _ in list(ke)]
    # Kanten-disjunkt: Quelle -> alle S-Knoten, T-Knoten -> Senke (unbegrenzt)
    ke_ = ke + [(n, ix[v], gross) for v in S] + [(ix[v], n + 1, gross) for v in T]
    kd = max_fluss(n + 2, ke_, n, n + 1)
    # Knoten-disjunkt: jeder Knoten v -> (v_ein = v, v_aus = v + n) Kapazitaet 1; Kanten v_aus -> u_ein unbegrenzt
    kk = [(i, i + n, 1) for i in range(n)] + [(a + n, b, gross) for a, b, _ in ke] + [(q, ix[v], gross) for v in S] + [(ix[v] + n, s, gross) for v in T]
    vd = max_fluss(2 * n + 2, kk, q, s)
    return kd, vd


def knotenschnitt(S, T, kanten, vd):
    """Bilder, die S von T trennen (bei kleinem vd): Randbilder am Schnitt, nach Querkantenzahl - fuer vd <= 3 exakt per Einzel-/Paarprobe."""
    S, T = set(S), set(T); quer = [(i, j) for (i, j) in kanten if (i in S and j in T) or (i in T and j in S)]
    rand = {}
    for i, j in quer: rand[i] = rand.get(i, 0) + 1; rand[j] = rand.get(j, 0) + 1
    kand = sorted(rand, key=lambda v: -rand[v])[:12]
    if vd <= 2:
        import itertools
        for r in range(1, vd + 1):
            for wahl in itertools.combinations(kand, r):
                w = set(wahl); rest = {k: 1 for k in kanten if k[0] not in w and k[1] not in w}
                if disjunkte_wege(S - w, T - w, rest)[1] == 0: return list(wahl)
    return kand[:max(vd, 1)]


def fiedler(knoten, kanten):
    """-> (Fiedler-Wert der normierten Laplace-Matrix, Fiedler-Vektor / sqrt(Grad)) mit Gewicht log(1 + w)."""
    ix = {v: i for i, v in enumerate(knoten)}; n = len(knoten)
    if n < 3: return 0.0, np.zeros(n)
    W = np.zeros((n, n))
    for (i, j), w in kanten.items():
        if i in ix and j in ix: W[ix[i], ix[j]] = W[ix[j], ix[i]] = np.log1p(w)
    d = W.sum(1); d[d == 0] = 1e-12; Dm = 1 / np.sqrt(d); L = np.eye(n) - Dm[:, None] * W * Dm[None, :]
    if n <= 2500: ev, V = np.linalg.eigh(L)
    else:
        from scipy.sparse import csr_matrix
        from scipy.sparse.linalg import eigsh
        ev, V = eigsh(csr_matrix(L), k=3, sigma=-1e-3, which="LM"); o = np.argsort(ev); ev, V = ev[o], V[:, o]
    return float(ev[1]), V[:, 1] * Dm


def bester_schnitt(knoten, kanten):
    """Sweep ueber den Fiedler-Vektor -> (S, T, leitwert, fiedlerwert) oder None."""
    if len(knoten) < 2 * MIN_SEITE: return None
    lam, f = fiedler(knoten, kanten); o = [knoten[i] for i in np.argsort(f)]; pos = {v: i for i, v in enumerate(o)}; n = len(o)
    wl = {}; vol = np.zeros(n)
    for (i, j), w in kanten.items():
        if i in pos and j in pos: x = np.log1p(w); vol[pos[i]] += x; vol[pos[j]] += x; wl.setdefault(pos[i], []).append((pos[j], x)); wl.setdefault(pos[j], []).append((pos[i], x))
    tot = vol.sum(); cut = 0.0; vS = 0.0; best = None
    for k in range(n - 1):
        for u, x in wl.get(k, []): cut += -x if u < k else x                           # Knoten k wechselt nach S
        vS += vol[k]
        if k + 1 >= MIN_SEITE and n - k - 1 >= MIN_SEITE:
            phi = cut / max(min(vS, tot - vS), 1e-12)
            if best is None or phi < best[0]: best = (phi, k)
    if best is None: return None
    return o[:best[1] + 1], o[best[1] + 1:], float(best[0]), lam


# ---------- Urteil ----------
def urteil(knoten_disjunkt, spuren_quer, n_klein):
    if knoten_disjunkt <= GELENK_MAX: return "zu_duenn", f"haengt an {knoten_disjunkt} Bild(ern) (Gelenk)"
    if spuren_quer is not None and spuren_quer < SPUREN_ZU_DUENN: return "zu_duenn", f"nur {spuren_quer} Spuren quer (< {SPUREN_ZU_DUENN})"
    if knoten_disjunkt <= DUENN_KNOTEN: return "duenn", f"nur {knoten_disjunkt} knotendisjunkte Wege (<= {DUENN_KNOTEN})"
    if knoten_disjunkt / max(n_klein, 1) < DUENN_ANTEIL: return "duenn", f"{knoten_disjunkt} Wege fuer {n_klein} Bilder der kleineren Seite (< {DUENN_ANTEIL:.0%})"
    if spuren_quer is not None and spuren_quer / max(n_klein, 1) < SPUREN_JE_BILD_DUENN:
        return "duenn", f"nur {spuren_quer / max(n_klein, 1):.1f} Spuren quer je Bild der kleineren Seite (< {SPUREN_JE_BILD_DUENN})"
    return "stark", "viele unabhaengige Wege"


def analysieren(namen, kanten, punkt_bilder=None, teil_von=None, stueck_name="verbund"):
    """Kern. -> (stuecke [dict], schwachstellen [dict])."""
    n = len(namen); st_aus, sw = [], []; spur = None
    if punkt_bilder:                                                                  # flach: Bildindizes aller Spuren hintereinander + Startindizes (fuer reduceat)
        gs = list(punkt_bilder.values()); spur = (np.concatenate(gs), np.r_[0, np.cumsum([len(g) for g in gs])[:-1]])
    alle_st = stuecke(n, kanten); gross = len(alle_st[0]) if alle_st else 0
    for si, comp in enumerate(alle_st):
        if len(comp) < max(2 * MIN_SEITE, MIN_STUECK_ANTEIL * gross): continue
        lam, _ = fiedler(comp, kanten); st_aus.append(dict(stueck=f"{stueck_name}/{si}", bilder=len(comp), kanten=sum(1 for (i, j) in kanten if i in set(comp)), fiedler=round(lam, 5)))
        gel, br = gelenke_bruecken(comp, kanten)
        for v, gr in gel.items():
            ab = sorted(gr)[:-1] if len(gr) > 1 else gr; klein = sum(g for g in gr if g < len(comp) / 2)
            if max(gr) >= MIN_SEITE and len(comp) - 1 - max(gr) >= MIN_SEITE:
                sw.append(dict(stueck=f"{stueck_name}/{si}", art="gelenk", bilder=[namen[v]], seiten=[int(max(gr)), int(len(comp) - 1 - max(gr))],
                               staerke=dict(knoten_disjunkt=1), urteil="zu_duenn", grund=f"ohne {namen[v]} fallen {max(gr)} von {len(comp)} Bildern ab"))
        for u, v, kl in br:
            if kl >= MIN_SEITE:
                sw.append(dict(stueck=f"{stueck_name}/{si}", art="bruecke", bilder=[namen[u], namen[v]], seiten=[int(kl), int(len(comp) - kl)],
                               staerke=dict(kanten_disjunkt=1, gewicht=int(kanten.get((min(u, v), max(u, v)), 0))), urteil="zu_duenn", grund="eine einzige Kante traegt"))
        offen = [(comp, 0)]
        while offen:
            kn, tiefe = offen.pop(0); bs = bester_schnitt(kn, kanten)
            if bs is None: continue
            S, T_, phi, lam_ = bs; sS, sT = set(S), set(T_)
            quer = [(i, j) for (i, j) in kanten if (i in sS and j in sT) or (i in sT and j in sS)]
            sub = {k: w for k, w in kanten.items() if k[0] in sS | sT and k[1] in sS | sT}
            kd, vd = disjunkte_wege(S, T_, sub); trenn = knotenschnitt(S, T_, sub, vd)
            spq = None
            if spur is not None:                                                     # Spuren quer: 3D-Punkte mit Beobachtern auf beiden Seiten
                seite = np.full(n, -1); seite[list(sS)] = 0; seite[list(sT)] = 1; s_ = seite[spur[0]]
                hatS = np.add.reduceat((s_ == 0).astype(np.int32), spur[1]) > 0; hatT = np.add.reduceat((s_ == 1).astype(np.int32), spur[1]) > 0; spq = int((hatS & hatT).sum())
            klein = S if len(S) <= len(T_) else T_; u, grund = urteil(vd, spq, len(klein))
            z = dict(stueck=f"{stueck_name}/{si}", art="schnitt", tiefe=tiefe, bilder=[namen[v] for v in trenn], seiten=[len(S), len(T_)], seite_klein=[namen[v] for v in klein][:40],
                     staerke=dict(spuren_quer=spq, inlier_quer=None if punkt_bilder is not None else int(sum(kanten[k] for k in quer)), kanten_quer=len(quer),
                                  knoten_disjunkt=int(vd), kanten_disjunkt=int(kd), leitwert=round(phi, 5), fiedler=round(lam_, 5)), urteil=u, grund=grund)
            if teil_von:
                z["teile"] = dict(a=_zaehl([namen[v] for v in S], teil_von), b=_zaehl([namen[v] for v in T_], teil_von))
            sw.append(z)
            if tiefe + 1 < TIEFE: offen += [(sorted(S), tiefe + 1), (sorted(T_), tiefe + 1)]
    return st_aus, sw


def _zaehl(ns, teil_von):
    z = {}
    for n in ns: t = teil_von.get(n, "-"); z[str(t)] = z.get(str(t), 0) + 1
    return z


def radar(db=None, modelle=(), teile=None, min_inlier=DB_MIN_INLIER, db_filter=None):
    """-> Bericht (Format verbund_schwachstellen/1). db_filter: Liste von sparse-Modellen - Datenbankgraph nur ueber deren registrierte Bilder (sonst verbinden
    nicht registrierte Bilder/Videobilder, was im Modell getrennt ist; Selbsttest: A-B-Paare geloescht, aber Nicht-Modellbilder hielten den DB-Graphen zusammen)."""
    teil_von = {}
    for t, p in (teile or {}).items():
        for nme in bilder_bin(p): teil_von.setdefault(nme, t)
    st, sw = [], []; art = None
    for mi, m in enumerate(modelle):
        namen, kanten, pb = graph_modell(bilder_bin(m)); a_, b_ = analysieren(namen, kanten, pb, teil_von, f"modell{mi}"); st += a_; sw += b_; art = "spuren"
    if db:
        nf = set().union(*[set(bilder_bin(p)) for p in db_filter]) if db_filter else None
        namen, kanten = graph_db(db, nf, min_inlier=min_inlier); a_, b_ = analysieren(namen, kanten, None, teil_von, "db"); st += a_; sw += b_; art = "inlier" if art is None else "spuren+inlier"
    rang = dict(stark=0, duenn=1, zu_duenn=2)
    for i, z in enumerate(sw): z["id"] = i
    gesamt = "kein_graph" if not st else max((z["urteil"] for z in sw), key=lambda x: rang[x], default="stark")
    schlimm = sorted(sw, key=lambda z: (-rang[z["urteil"]], z["staerke"].get("knoten_disjunkt", 99)))[:3]
    txt = "; ".join(f"{z['art']} {z['stueck']} {z['urteil']}: {z['grund']} [{', '.join(z['bilder'][:3])}] Seiten {z['seiten']}" for z in schlimm)
    ausl = [z["id"] for z in sorted(sw, key=lambda z: (-rang[z["urteil"]], z["staerke"].get("knoten_disjunkt", 99))) if z["urteil"] != "stark"]
    return dict(format="verbund_schwachstellen/1", quelle=dict(db=db, modelle=list(modelle)), art=art, stuecke=st, urteil=gesamt, ausloeser=ausl, schwachstellen=sw,
                grenzen=dict(min_seite=MIN_SEITE, gelenk_max=GELENK_MAX, duenn_knoten=DUENN_KNOTEN, duenn_anteil=DUENN_ANTEIL, spuren_zu_duenn=SPUREN_ZU_DUENN, spuren_je_bild_duenn=SPUREN_JE_BILD_DUENN,
                             db_min_inlier=min_inlier, beleg=GRENZEN_BELEG),
                zeile=f"RADAR {gesamt.upper()}: " + (txt or "keine Schwachstelle"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0]); ap.add_argument("--db"); ap.add_argument("--modell", action="append", default=[])
    ap.add_argument("--teil", action="append", default=[], help="N=<sparse> (Zuordnung der Seiten zu Teilen)"); ap.add_argument("--db-filter", action="append", default=[], help="sparse: DB-Graph nur ueber dessen Bilder"); ap.add_argument("--aus"); ap.add_argument("--min-inlier", type=int, default=DB_MIN_INLIER)
    a = ap.parse_args(argv)
    if not a.db and not a.modell: ap.error("--db und/oder --modell")
    b = radar(a.db, a.modell, {x.split("=", 1)[0]: x.split("=", 1)[1] for x in a.teil}, a.min_inlier, a.db_filter); print(b["zeile"])
    if a.aus: os.makedirs(os.path.dirname(os.path.abspath(a.aus)), exist_ok=True); json.dump(b, open(a.aus, "w"), indent=1, ensure_ascii=False)
    return dict(stark=0, duenn=2, zu_duenn=3).get(b["urteil"], 4)


if __name__ == "__main__": sys.exit(main())
