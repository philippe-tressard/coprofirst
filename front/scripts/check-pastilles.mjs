#!/usr/bin/env node
/**
 *  La dernière ligne d'une carte est la MÊME partout (27/09/2026).
 *
 *  ## Pourquoi
 *
 *  Arbitré à l'écran : la ligne de la carte d'affaire fait la norme, et le fil
 *  d'activité comme la carte d'actualité la rendent à l'identique. Elles
 *  différaient sur neuf points — catégorie en texte ou en emoji, état absent du
 *  fil, périmètre en tête ou après l'état, « urgent » rouge contre « ⚡ Urgente »
 *  orange, numéro en badge ou en texte, auteur avec ou sans ✍️, lecteurs et ✨
 *  absents du fil. Trois écritures d'une ligne, trois occasions de diverger.
 *
 *  ## Ce qu'il refuse
 *
 *  1. Une des trois cartes qui ne rend pas `<PastillesAffaire` ;
 *  2. ✍️ écrit ailleurs que dans `AuteurCarte` — l'auteur a UNE forme ;
 *  3. une pastille de la ligne recomposée hors de `PastillesAffaire` : la forme
 *     brève de la priorité, l'emoji de catégorie ;
 *  4. (#1373) une carte de liste de la COMMUNAUTÉ — annonce, idée, sondage —
 *     sans `PastilleLecture` (elle a remplacé le badge orange des
 *     destinataires), avec un 🔹 teinté, ou un ✨ placé avant la pastille de
 *     lecture (il ferme la ligne, il n'accompagne pas le titre) ;
 *  5. un AUTEUR sur la carte d'une idée ou d'un sondage — arbitré le
 *     27/09/2026 : ils restent anonymes pour leurs lecteurs, aucune API ne
 *     l'expose, et l'afficher serait une décision de données personnelles.
 *
 *  Lancer : node scripts/check-pastilles.mjs [--selftest]
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, sep } from 'node:path';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

const CARTES = [
	'lib/components/CarteTicket.svelte',
	'lib/components/CarteActualite.svelte',
	'lib/components/FluxCard.svelte',
];
/** Les cartes de liste de la communauté (#1373) : même ordre, leurs pastilles. */
const CARTES_CIBLEES = [
	'lib/components/AnnonceCard.svelte',
	'lib/components/ListeIdees.svelte',
	'lib/components/ListeSondages.svelte',
];
/** …dont celles qui ne nomment PAS leur auteur — déclaré, avec sa raison. */
const SANS_AUTEUR = {
	'lib/components/ListeIdees.svelte': 'une idée reste anonyme pour ses lecteurs (27/09/2026)',
	'lib/components/ListeSondages.svelte': 'un sondage reste anonyme pour ses lecteurs (27/09/2026)',
};
const SOURCE_LIGNE = 'lib/components/PastillesAffaire.svelte';
/** Le squelette du pied (catégorie, numéro, fin), commun aux cartes d'affaire ET au
 *  carnet d'entretien (24/10/2026) : le n° TK y avait sa propre ligne. */
const SOURCE_PIED = 'lib/components/PiedCarte.svelte';
/** Ce qui rend un pied d'affaire : il passe par `PiedCarte`, jamais recomposé. */
const PORTEURS_DU_PIED = [SOURCE_LIGNE, 'lib/components/CarnetEntretien.svelte'];
const SOURCE_AUTEUR = 'lib/components/AuteurCarte.svelte';

/** Ce que seule la ligne commune a le droit de rendre — et par quel fichier. */
const RENDUS_DE_LA_LIGNE = [
	{ motif: /\bPRIORITE_BREVE\b/, source: SOURCE_LIGNE },
	{ motif: /\bcategorieTicketEmoji\(/, source: SOURCE_PIED },
];

/** Les écarts d'une source, pour un fichier donné. PURE. */
export function ecarts(rel, source) {
	const s = neutraliserCommentaires(source);
	const sortie = [];
	if (CARTES.includes(rel) && !/<PastillesAffaire\b/.test(s))
		sortie.push('ne rend pas <PastillesAffaire> : sa dernière ligne diverge');
	if (rel !== SOURCE_AUTEUR && /✍️|✍/.test(s))
		sortie.push('✍️ écrit hors de AuteurCarte : l’auteur a une forme');
	if (CARTES_CIBLEES.includes(rel)) {
		const lecture = s.search(/<PastilleLecture\b/);
		if (lecture < 0) sortie.push('ne rend pas <PastilleLecture> : qui la lit ne se dit pas');
		if (/<BadgePerimetre\b[^>]*\bton=/.test(s)) sortie.push('🔹 teinté : il a une couleur');
		const ia = s.search(/<MarqueIA\b/);
		if (ia >= 0 && lecture >= 0 && ia < lecture)
			sortie.push('✨ avant la pastille de lecture : il ferme la ligne');
	}
	if (rel in SANS_AUTEUR && /<AuteurCarte\b/.test(s))
		sortie.push(`nomme son auteur — ${SANS_AUTEUR[rel]}`);
	if (PORTEURS_DU_PIED.includes(rel) && !/<PiedCarte\b/.test(s))
		sortie.push('ne rend pas <PiedCarte> : son pied (catégorie, n° d’affaire) diverge');
	if (rel.endsWith('.svelte'))
		for (const { motif, source } of RENDUS_DE_LA_LIGNE)
			if (rel !== source && motif.test(s))
				sortie.push(`${motif.source} hors de ${source.split('/').pop()}`);
	return sortie;
}

if (process.argv.includes('--selftest')) {
	let ko = 0;
	const t = (libelle, attendu, obtenu) => {
		const ok = attendu === obtenu;
		console.log(`${ok ? 'PASS' : 'FAIL'}  ${libelle} → ${obtenu}`);
		if (!ok) ko = 1;
	};
	const F = 'lib/components/FluxCard.svelte';
	//  🔴 La forme du 27/09/2026 : le fil composait sa ligne à la main.
	t('fil sans la ligne commune', 1, ecarts(F, '<span class="flux-auteur">x</span>').length);
	t('fil avec la ligne commune', 0, ecarts(F, '<PastillesAffaire {affaire} />').length);
	t('✍️ recopié', 1, ecarts('lib/components/X.svelte', '<span>✍️ {nom}</span>').length);
	t('✍️ en commentaire ignoré', 0, ecarts('lib/components/X.svelte', '<!-- ✍️ -->').length);
	t('priorité recomposée', 1, ecarts('lib/components/X.svelte', '{PRIORITE_BREVE[p]}').length);
	//  🔴 La forme du 24/10/2026 : le carnet disait la catégorie en texte et le n° TK
	//  sur une ligne à lui, au lieu du pied commun.
	const C = 'lib/components/CarnetEntretien.svelte';
	t('carnet sans le pied commun', 1, ecarts(C, '<span class="badge">{cat}</span>').length);
	t('carnet avec le pied commun', 0, ecarts(C, '<PiedCarte categorie={c} numero={n} />').length);
	t('emoji de catégorie recomposé', 1, ecarts(C, '<PiedCarte />{categorieTicketEmoji(c)}').length);
	t(
		'emoji de catégorie dans le pied',
		0,
		ecarts(SOURCE_PIED, '{categorieTicketEmoji(categorie)}').length,
	);
	const I = 'lib/components/ListeIdees.svelte';
	const ligne = '<BadgePerimetre perimetre={p} /><PastilleLecture cible={i} /><MarqueIA />';
	t('idée conforme', 0, ecarts(I, ligne).length);
	//  🔴 La forme d'avant #1373 : badge orange, ✨ à côté du titre.
	t(
		'idée sans pastille de lecture',
		1,
		ecarts(I, '<MarqueIA /><span class="badge-orange">').length,
	);
	t('✨ avant la lecture', 1, ecarts(I, '<MarqueIA /><PastilleLecture cible={i} />').length);
	t('🔹 teinté', 1, ecarts(I, ligne.replace('perimetre={p}', 'perimetre={p} ton="blue"')).length);
	t('auteur d’une idée', 1, ecarts(I, ligne + '<AuteurCarte nom={n} />').length);
	t(
		'auteur d’une annonce admis',
		0,
		ecarts('lib/components/AnnonceCard.svelte', ligne + '<AuteurCarte nom={n} />').length,
	);
	console.log(ko ? '== ÉCHECS ==' : '== TOUS OK ==');
	process.exit(ko);
}

function fichiers(dir, acc = []) {
	for (const e of readdirSync(dir)) {
		const p = join(dir, e);
		if (statSync(p).isDirectory()) fichiers(p, acc);
		else if (e.endsWith('.svelte')) acc.push(p);
	}
	return acc;
}

const fautifs = [];
const lus = new Set();
for (const f of fichiers('src')) {
	const rel = f
		.split(sep)
		.join('/')
		.replace(/^src\//, '');
	lus.add(rel);
	for (const e of ecarts(rel, readFileSync(f, 'utf8'))) fautifs.push(`${rel} — ${e}`);
}
const absents = [
	...CARTES,
	...CARTES_CIBLEES,
	...PORTEURS_DU_PIED,
	SOURCE_LIGNE,
	SOURCE_PIED,
	SOURCE_AUTEUR,
].filter((f) => !lus.has(f));
if (absents.length) {
	console.error(`\n✗ INCONNU : introuvable(s) — ${absents.join(', ')}.\n`);
	process.exit(2);
}
if (fautifs.length) {
	console.error(`\n✗ Dernière ligne de carte hors de la norme :\n\n  ${fautifs.join('\n  ')}\n`);
	process.exit(1);
}
console.log(
	`✓ Pastilles : ${CARTES.length} cartes rendent la même ligne, ${CARTES_CIBLEES.length} cartes ` +
		`de la communauté disent qui les lit, ${Object.keys(SANS_AUTEUR).length} restent anonymes, ✍️ a une forme.`,
);
