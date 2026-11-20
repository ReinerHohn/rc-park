export const meta = {
  name: 'bauteil-runde',
  description: 'Bauteil-Runde im Worktree (Form aus Fotos, zaehlen, messen, generisches Bauteil, Abnahme), danach drei unabhaengige Pruefer gegen Fotos',
  whenToUse: 'Ein Bauteil fehlt oder ist falsch. args = {objekt, bauteil, befund}',
  phases: [{ title: 'Bauen' }, { title: 'Pruefen' }],
}
const BAU = { type: 'object', properties: { zweig: { type: 'string' }, worktree: { type: 'string' }, abnahme_bestanden: { type: 'boolean' },
  bilder: { type: 'array', items: { type: 'string' } }, belege: { type: 'array', items: { type: 'string' } }, annahmen: { type: 'array', items: { type: 'string' } } },
  required: ['zweig', 'abnahme_bestanden', 'bilder'] }
const URTEIL = { type: 'object', properties: { passt: { type: 'boolean' }, gruende: { type: 'array', items: { type: 'string' } } }, required: ['passt', 'gruende'] }
const { objekt, bauteil, befund } = args || {}
if (!objekt || !bauteil) { log('args braucht {objekt, bauteil, befund}'); return null }
phase('Bauen')
const bau = await agent(`Bauteil-Runde nach .claude/skills/bauteil-runde/SKILL.md und modelle/VORLAGE_BAUTEIL_RUNDE.md. Objekt ${objekt}, Bauteil ${bauteil}, Befund: ${befund || '-'}. Form aus >= 3 Fotos, zaehlen nur am Foto, messen nur foto_mass.py, Pruefung erst rot, Gestalt aus dem Wandbild als generische Funktion in tools/bauteile.py, dann bauen_abnehmen.sh und tools-pruefen. Committe im eigenen Zweig; NICHT nach main mergen. Liefere Zweig, Worktree-Pfad, angesehene Bilder (neben_*.jpg, seiten.jpg) und Belege/Annahmen.`, { label: `bau:${bauteil}`, phase: 'Bauen', schema: BAU, isolation: 'worktree' })
if (!bau) return null
phase('Pruefen')
const lenses = ['Gestalt/Umriss gegen Foto', 'Anzahl und Masse gegen Foto', 'Lage, Anschluss an Nachbarteile, Druckbarkeit']
const urteile = (await parallel(lenses.map(l => () => agent(`Pruefe das neue Bauteil "${bauteil}" am Objekt ${objekt} (Zweig ${bau.zweig}, Worktree ${bau.worktree || '?'}) unter dem Blickwinkel: ${l}. Sieh die Bilder selbst an: ${bau.bilder.join(', ')} und die Referenzfotos. Versuche zu WIDERLEGEN, dass es passt; im Zweifel passt=false. Nichts aendern.`, { label: `pruef:${l.split(' ')[0]}`, phase: 'Pruefen', schema: URTEIL })))).filter(Boolean)
return { ...bau, urteile, angenommen: bau.abnahme_bestanden && urteile.filter(u => u.passt).length >= 2 }
