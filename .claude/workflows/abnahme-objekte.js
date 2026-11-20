export const meta = {
  name: 'abnahme-objekte',
  description: 'Abnahme mehrerer RC-Park-Objekte parallel (bauen_abnehmen + Bilder ansehen), dann je Objekt unabhaengige Gegenpruefung der Fehlerliste',
  whenToUse: 'Nach Werkzeug- oder Generatoraenderungen, die mehrere Objekte betreffen. args = ["martinstor", "kaufhaus_gk2", ...]',
  phases: [{ title: 'Abnahme' }, { title: 'Gegenprobe' }],
}
const ERG = { type: 'object', properties: {
  objekt: { type: 'string' }, bestanden: { type: 'boolean' }, rot: { type: 'array', items: { type: 'string' } },
  fehlerliste: { type: 'array', items: { type: 'string' } }, bilder: { type: 'array', items: { type: 'string' } }, realitaet_prozent: { type: 'number' } },
  required: ['objekt', 'bestanden', 'fehlerliste', 'bilder'] }
const GEGEN = { type: 'object', properties: { uebersehen: { type: 'array', items: { type: 'string' } }, schoengeredet: { type: 'array', items: { type: 'string' } } },
  required: ['uebersehen', 'schoengeredet'] }
const objekte = Array.isArray(args) ? args : []
if (!objekte.length) { log('keine Objekte uebergeben (args = Liste von Objektnamen)'); return [] }
return await pipeline(objekte,
  o => agent(`Fuehre fuer das RC-Park-Objekt "${o}" den Skill abnahme aus (.claude/skills/abnahme/SKILL.md): bash tools/bauen_abnehmen.sh ${o}, dann die Pruefwerkzeuge, dann audit/seiten.jpg und audit/neben_*.jpg mit dem Read-Tool ANSEHEN. Aendere keinen Generator und keine Sollwerte, committe nichts. Liefere Fehlerliste je Teil (was am Bild nicht zum Foto passt) und die angesehenen Bildpfade.`, { label: `abnahme:${o}`, phase: 'Abnahme', schema: ERG }),
  (r, o) => r && agent(`Gegenpruefung der Abnahme von "${o}". Sieh dir diese Bilder selbst an: ${r.bilder.join(', ')}. Die erste Pruefung meldete: ${JSON.stringify(r.fehlerliste)}. Suche Abweichungen Modell gegen Foto, die NICHT in der Liste stehen, und Punkte, die schoengeredet wurden. Nichts aendern.`, { label: `gegen:${o}`, phase: 'Gegenprobe', schema: GEGEN }).then(g => ({ ...r, gegenprobe: g })))
