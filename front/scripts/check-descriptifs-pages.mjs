#!/usr/bin/env node
/**
 * Garde-fou : le descriptif par défaut d'un écran ne contredit pas l'écran (#2921).
 *
 * ## Le défaut (audit du 23/11/2026)
 *
 * `lint:pages` garde l'UNICITÉ de la table des pages, pas sa VÉRITÉ. Cinq
 * descriptifs servis par défaut contredisaient l'écran qu'ils coiffent :
 *
 *   - Espace CS › Badges se disait « Vue de consultation » au-dessus d'un bouton
 *     « Enregistrer un accès » ;
 *   - Admin › À traiter énumérait trois files quand l'écran en porte quatre — la
 *     quatrième (les suppressions de compte, #2699) est venue après le texte ;
 *   - Admin › Imports énumérait trois sources quand l'écran en propose quatre —
 *     l'état descriptif (#2213) est venu après le texte.
 *
 * Les deux autres (Mes lots & accès, Admin › Maintenance) disaient faux sans
 * énumérer ni affirmer de lecture seule : ce contrôle ne les voit pas, et ne
 * prétend pas les voir (voir « Ce qui n'est pas vérifié »).
 *
 * ## Ce qui est vérifié
 *
 * 1. **Une énumération est complète ou n'est pas.** Pour chaque écran déclaré dans
 *    `ECRANS` avec une liste, le contrôle LIT la liste dans le composant (les
 *    titres des `SectionRepliee`, les `label` de `SOURCES`) ; un descriptif qui en
 *    cite au moins deux les cite toutes. Une phrase d'usage — qui n'en cite qu'une,
 *    ou aucune — passe : c'est la forme à préférer (#2921 : un libellé nomme
 *    l'usage, pas son contenu). Chaque élément a son mot-clé déclaré : une
 *    section ajoutée sans mot-clé, ou un mot-clé qui ne désigne plus rien, échoue.
 * 2. **Un descriptif n'affirme pas la lecture seule d'un écran qui écrit.** Une
 *    affirmation de lecture seule (`LECTURE_SEULE`) n'est admise que sur un écran
 *    déclaré dans `ECRANS`, dont le composant ne porte aucun geste de création
 *    (`GESTE_CREATION`) ; ailleurs elle est refusée, faute de pouvoir la vérifier.
 *    « à consulter », « consultations » (les votes) ne sont pas des affirmations.
 *
 * ## Ce qui n'est pas vérifié
 *
 * Une phrase d'usage trop étroite (Maintenance) ou un public mal nommé (« les
 * copropriétaires mandataires » pour un onglet ouvert au bailleur) : le contrôle ne
 * sait pas ce qu'un écran montre selon le rôle. Aucun garde-fou automatique
 * raisonnable n'existe pour ces cas — la relecture de l'audit les trouve.
 *
 * Usage : node scripts/check-descriptifs-pages.mjs [--selftest]
 * (lancé par `npm run lint:pages`)
 */
import { neutraliserCommentaires } from './lib-commentaires.mjs';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { lecteur, Refus } from './tables-clients.lecture.mjs';

const FRONT = fileURLToPath(new URL('../', import.meta.url));

/** Ce qu'un descriptif affirme quand il dit qu'on n'écrit pas sur l'écran. */
const LECTURE_SEULE = /lecture seule|vue de consultation|consultation seule/i;
/** Un geste de création sur l'écran : son bouton, ou le libellé qu'il prend. */
const GESTE_CREATION = /<BoutonNouveau\b|\blibelleNouveau\b/;

/**
 * Les écrans dont le descriptif se confronte au composant, avec ce qu'on y lit.
 *
 * `liste` : `sections` (titres des `SectionRepliee`) ou `sources` (`label` de la
 * constante `SOURCES`). `motsCles` : pour chaque élément lu, le mot qui le désigne
 * dans une phrase — les titres d'écran ne sont pas les mots de la prose
 * (« Comptes en attente » se dit « comptes à valider »).
 */
const ECRANS = [
	{
		onglet: 'espace-cs/badges',
		composant: 'src/lib/components/BadgesCopropriete.svelte',
	},
	{
		onglet: 'admin/a_traiter',
		composant: 'src/lib/components/OngletATraiter.svelte',
		liste: 'sections',
		motsCles: {
			'Comptes en attente': 'compte',
			"Commandes d'accès": 'commande',
			'Demandes de profil': 'profil',
			'Suppressions de compte': 'suppression',
		},
	},
	{
		onglet: 'admin/imports',
		composant: 'src/lib/components/OngletImports.svelte',
		liste: 'sources',
		motsCles: {
			Lots: 'lot',
			Télécommandes: 'télécommande',
			Vigik: 'vigik',
			'État descriptif': 'état descriptif',
		},
	},
];

const texteSeul = (html) => html.replace(/<[^>]+>/g, ' ');

/** Les titres des `SectionRepliee` d'un composant, dans l'ordre. PURE. */
function titresSections(source) {
	const texte = neutraliserCommentaires(source);
	const titres = [];
	for (const m of texte.matchAll(/<SectionRepliee\b/g)) {
		const balise = texte.slice(m.index, texte.indexOf('>', texte.indexOf('titre', m.index)));
		const t = /\btitre=(?:"([^"]+)"|'([^']+)'|\{)/.exec(balise);
		if (!t) throw new Refus(`une SectionRepliee sans titre lisible (« ${balise.slice(0, 60)}… »)`);
		if (!t[1] && !t[2]) throw new Refus('un titre de SectionRepliee calculé ne se lit pas');
		titres.push(t[1] ?? t[2]);
	}
	return titres;
}

/** Les `label` de la constante `SOURCES` d'un composant. PURE. */
function labelsSources(source) {
	const debut = source.indexOf('const SOURCES');
	if (debut < 0) throw new Refus('constante SOURCES introuvable');
	const bloc = source.slice(debut, source.indexOf('];', debut));
	return [...bloc.matchAll(/\blabel:\s*(?:'([^']+)'|"([^"]+)")/g)].map((m) => m[1] ?? m[2]);
}

const LECTURES = { sections: titresSections, sources: labelsSources };

/** Le mot-clé figure-t-il dans le texte, en début de mot (pluriel compris) ? PURE. */
function cite(texte, mot) {
	const echappe = mot.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
	return new RegExp(`(?<!\\p{L})${echappe}`, 'iu').test(texte);
}

/**
 * Les refus d'un descriptif face à son écran. `ecran` : l'entrée d'`ECRANS` (ou
 * `null`), `elements` : la liste lue dans le composant, `composant` : sa source.
 * PURE.
 */
function refusDescriptif(lieu, descriptif, ecran, elements, composant) {
	const refus = [];
	const texte = texteSeul(descriptif ?? '');
	if (LECTURE_SEULE.test(texte)) {
		if (!ecran)
			refus.push(
				`${lieu} : affirme la lecture seule d'un écran non déclaré dans ECRANS — déclarer son composant pour que l'affirmation se vérifie`,
			);
		else if (GESTE_CREATION.test(composant ?? ''))
			refus.push(
				`${lieu} : affirme la lecture seule (« ${LECTURE_SEULE.exec(texte)[0]} ») d'un écran qui porte un geste de création (${ecran.composant})`,
			);
	}
	if (ecran?.liste) {
		const sansMot = elements.filter((e) => !(e in ecran.motsCles));
		const morts = Object.keys(ecran.motsCles).filter((e) => !elements.includes(e));
		for (const e of sansMot)
			refus.push(`${lieu} : « ${e} » n'a pas de mot-clé — le déclarer dans ECRANS.motsCles`);
		for (const e of morts)
			refus.push(`${lieu} : mot-clé déclaré pour « ${e} », absent de l'écran — le retirer`);
		const cites = elements.filter((e) => e in ecran.motsCles && cite(texte, ecran.motsCles[e]));
		if (cites.length >= 2 && cites.length < elements.length) {
			const manquent = elements.filter((e) => !cites.includes(e));
			refus.push(
				`${lieu} : énumère ${cites.length} des ${elements.length} ${ecran.liste} de l'écran et tait ${manquent.map((e) => `« ${e} »`).join(', ')} — compléter, ou dire l'usage sans énumérer`,
			);
		}
	}
	return refus;
}

/** Tous les descriptifs de la table, par lieu `page` ou `page/onglet`. PURE. */
function descriptifsDe(pages) {
	const sortie = new Map();
	for (const p of pages) {
		sortie.set(p.id, p.descriptif);
		for (const o of p.onglets ?? []) sortie.set(`${p.id}/${o.id}`, o.descriptif);
	}
	return sortie;
}

function selftest() {
	let echecs = 0;
	const verifier = (titre, obtenu, attendu) => {
		const ok = JSON.stringify(obtenu) === JSON.stringify(attendu);
		if (!ok) echecs++;
		console.log(`${ok ? '  ✓' : '  ✗'} ${titre}${ok ? '' : ` — obtenu ${JSON.stringify(obtenu)}`}`);
	};
	const [badges, aTraiter, imports] = ECRANS;
	const sections = Object.keys(aTraiter.motsCles);
	const sources = Object.keys(imports.motsCles);
	const n = (d, e, el = [], c = '') => refusDescriptif('x', d, e, el, c).length;

	//  Les textes d'avant #2921 : chacun rougit.
	verifier(
		'ancien À traiter (3 files sur 4) refusé',
		n(
			"Ce qui attend un geste de l'administrateur : comptes à valider, commandes d'accès, demandes de modification de profil.",
			aTraiter,
			sections,
		),
		1,
	);
	verifier(
		'ancien Imports (3 sources sur 4) refusé',
		n(
			'Charger un tableur du syndic — lots et copropriétaires, télécommandes ou badges Vigik — et le rapprocher des lots.',
			imports,
			sources,
		),
		1,
	);
	verifier(
		'ancien Badges (« Vue de consultation » sur un écran qui crée) refusé',
		n('Vue de consultation : un badge s’enregistre par l’import.', badges, [], '<BoutonNouveau />'),
		1,
	);
	//  Ce qui passe.
	verifier(
		'énumération complète admise',
		n('Comptes, commandes, profils et suppressions de compte.', aTraiter, sections),
		0,
	);
	verifier(
		'phrase d’usage qui cite un seul élément (« rapprocher des lots ») admise',
		n('Charger un fichier et le rapprocher des lots.', imports, sources),
		0,
	);
	verifier(
		'lecture seule sur un écran déclaré sans geste de création admise',
		n('Vue de consultation.', badges, [], '<table></table>'),
		0,
	);
	verifier(
		'« à consulter », « consultations » ne sont pas des affirmations',
		n('Synthèses à consulter ou à exporter. Votes et consultations.', null),
		0,
	);
	verifier('lecture seule sur un écran non déclaré refusée', n('En lecture seule.', null), 1);
	//  La déclaration elle-même.
	verifier('section sans mot-clé refusée', n('Rien.', aTraiter, [...sections, 'Nouvelle file']), 1);
	verifier('mot-clé sans section refusé', n('Rien.', aTraiter, sections.slice(1)), 1);
	//  Les lectures du composant.
	verifier(
		'titres lus, commentaire ignoré, attribut fléché après le titre',
		titresSections(
			'<!-- <SectionRepliee titre="Faux"> -->\n<SectionRepliee\n\ttitre="A"\n\tsurBascule={() => (x = 1)}\n>\n<SectionRepliee titre="B">',
		),
		['A', 'B'],
	);
	verifier(
		'labels de SOURCES lus',
		labelsSources(
			"const SOURCES = [\n\t{ val: 'a', label: 'A' },\n\t{ val: 'b', label: \"B\" },\n];",
		),
		['A', 'B'],
	);
	verifier(
		'texte HTML : les balises ne comptent pas',
		n('<a href="/lots">Voir</a> les télécommandes.', imports, sources),
		0,
	);
	if (echecs) {
		console.error(`\n✗ selftest : ${echecs} cas en échec.`);
		process.exit(1);
	}
	console.log('\n✓ selftest des descriptifs : tous les cas vérifiés.');
	process.exit(0);
}

if (process.argv.includes('--selftest')) selftest();

const lire = (chemin) => readFileSync(`${FRONT}${chemin}`, 'utf8');
let descriptifs;
try {
	descriptifs = descriptifsDe(lecteur(lire)('src/lib/pages.ts', 'PAGES', true));
} catch (e) {
	console.error(`✗ Cas zéro : table des pages illisible — ${e.message}`);
	process.exit(1);
}
if (descriptifs.size < 20) {
	console.error(`✗ Cas zéro : ${descriptifs.size} descriptif(s) lu(s), au moins 20 attendus.`);
	process.exit(1);
}

const refus = [];
const declares = new Map(ECRANS.map((e) => [e.onglet, e]));
for (const e of ECRANS) {
	if (!descriptifs.has(e.onglet)) refus.push(`${e.onglet} : déclaré dans ECRANS, absent de PAGES`);
	if (!existsSync(`${FRONT}${e.composant}`)) refus.push(`${e.onglet} : ${e.composant} introuvable`);
}
if (refus.length === 0) {
	for (const [lieu, descriptif] of descriptifs) {
		const ecran = declares.get(lieu) ?? null;
		const composant = ecran ? lire(ecran.composant) : '';
		let elements = [];
		if (ecran?.liste) {
			try {
				elements = LECTURES[ecran.liste](composant);
			} catch (e) {
				refus.push(`${lieu} : ${e.message}`);
				continue;
			}
			if (elements.length < 2) {
				refus.push(
					`${lieu} : cas zéro — ${elements.length} ${ecran.liste} lue(s) dans ${ecran.composant}, la lecture ne mesure plus rien`,
				);
				continue;
			}
		}
		refus.push(...refusDescriptif(lieu, descriptif, ecran, elements, composant));
	}
}

if (refus.length) {
	console.error('\n✗ Descriptif de page qui contredit son écran :\n');
	for (const r of refus) console.error(`   ${r}`);
	console.error(
		'\n  Un libellé nomme l’usage, pas son contenu (#2921) : une énumération partielle' +
			'\n  diverge au premier élément ajouté, et « consultation » se dément au premier bouton.\n',
	);
	process.exit(1);
}
console.log(
	`✓ ${descriptifs.size} descriptifs lus — ${ECRANS.length} écrans confrontés à leur composant, ` +
		'aucune énumération partielle ni lecture seule démentie.',
);
