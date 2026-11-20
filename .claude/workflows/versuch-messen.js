export const meta = {
  name: 'versuch-messen',
  description: 'Verbesserungsidee pruefen: Register/Lizenz-Vorpruefung, dann Messplan, dann unabhaengiger Skeptiker gegen den Messplan',
  whenToUse: 'Neue Methode/Werkzeug aus Recherche bevor Rechenzeit investiert wird. args = {idee, schritt, messgroesse}',
  phases: [{ title: 'Vorpruefung' }, { title: 'Plan' }, { title: 'Skeptiker' }],
}
const VOR = { type: 'object', properties: { schon_versucht: { type: 'boolean' }, fundstellen: { type: 'array', items: { type: 'string' } }, lizenz_verkauf_ok: { type: 'string' }, vram_8gb: { type: 'string' } }, required: ['schon_versucht', 'fundstellen', 'lizenz_verkauf_ok'] }
const PLAN = { type: 'object', properties: { basislauf: { type: 'string' }, versuchslauf: { type: 'string' }, messgroesse: { type: 'string' }, wiederholungen: { type: 'number' }, dauer_h: { type: 'number' }, befehle: { type: 'array', items: { type: 'string' } } }, required: ['basislauf', 'versuchslauf', 'messgroesse', 'befehle'] }
const KRITIK = { type: 'object', properties: { fair: { type: 'boolean' }, maengel: { type: 'array', items: { type: 'string' } } }, required: ['fair', 'maengel'] }
const { idee, schritt, messgroesse } = args || {}
if (!idee) { log('args braucht {idee, schritt, messgroesse}'); return null }
phase('Vorpruefung')
const vor = await agent(`Idee: ${idee}. Durchsuche per grep modelle/NICHTS_GEBRACHT.md, modelle/VERSUCHSREGISTER_MARTINSTOR.md, modelle/RECHERCHE_*.md, modelle/LOGBUCH_*.md, ob das schon versucht wurde (Fundstellen mit Datei:Zeile). Pruefe in modelle/LIZENZ_WERKZEUGE.md und an der Quelle (Code UND Gewichte), ob Verkauf der Ergebnisse erlaubt ist, und ob es auf 8 GB VRAM laeuft. Nichts aendern.`, { phase: 'Vorpruefung', schema: VOR })
if (!vor || (vor.schon_versucht && !/neu|anders/.test(idee))) return { vor, hinweis: 'schon versucht - nur mit benannter neuer Ursache wiederholen' }
phase('Plan')
const plan = await agent(`Erstelle einen fairen A/B-Messplan fuer: ${idee}, an Schritt ${schritt || '?'} der Kette, Messgroesse ${messgroesse || 'selbst waehlen'}. Basis = gleiche Eingabe mit heutigem Standard. Lauf-Streuung beachten (mind. 2 Laeufe je Seite bei globalem Mapper). Befehle nach Skill langer-job (tools/job_start.sh mit JOB_GPU_MB/JOB_RAM_MB). Nichts starten.`, { phase: 'Plan', schema: PLAN })
phase('Skeptiker')
const kritik = await agent(`Pruefe diesen Messplan kritisch auf Unfairness (andere Eingabe, Musterleck, Einzellauf, falsche Messgroesse, Zielwert aus derselben Quelle): ${JSON.stringify(plan)}`, { phase: 'Skeptiker', schema: KRITIK })
return { vor, plan, kritik }
