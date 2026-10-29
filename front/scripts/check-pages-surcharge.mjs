/**
 * Auto-test de `#lib/pages-surcharge.ts` — le repli d'une surcharge de page.
 *
 * 🔴 POURQUOI (#1105, 21/09/2026). Trois entrées de **Descriptif pages**
 * s'affichaient sans nom. La règle « une surcharge absente retombe sur la
 * source » vivait **deux fois** — le store et l'écran d'administration —, avec
 * les mêmes rattrapages historiques recopiés, et **rien ne l'éprouvait** : le
 * front n'a pas de lanceur de tests.
 *
 * Deux copies d'une règle, c'est deux occasions de la corriger à moitié : l'une
 * repliait sur les défauts, l'autre non, et c'est celle de l'écran qui ne le
 * faisait pas.
 *
 * ⚠️ Le cas subtil, celui qu'on recopie sans le relire : **une clé absente et
 * une chaîne vide ne veulent pas dire la même chose**. L'absence dit « jamais
 * saisi » et doit retomber sur la source ; la chaîne vide dit « vidé exprès »
 * et doit être respectée. Les confondre efface un nom, ou empêche d'effacer un
 * descriptif — et ni l'un ni l'autre ne se voit pendant une relecture.
 *
 * Le pattern est celui de `check-liste-depliable.mjs` : fonction PURE +
 * `--selftest`, sur le module que le site embarque, pas une copie.
 *
 * Usage : node scripts/check-pages-surcharge.mjs --selftest
 */
import { fusionnerSurcharge } from '../src/lib/pages-surcharge.ts';

const echecs = [];
//  Compté, jamais écrit en dur : un nombre recopié dans le message de succès
//  devient faux au premier cas ajouté.
let cas = 0;
const verifier = (nom, obtenu, attendu) => {
	cas++;
	const a = JSON.stringify(obtenu);
	const b = JSON.stringify(attendu);
	if (a !== b) echecs.push(`  ✗ ${nom}\n      attendu ${b}\n      obtenu  ${a}`);
};

const DEFAUTS = {
	titre: 'Tableau de bord',
	descriptif: 'Votre espace numérique de résidence.',
	navLabel: 'Accueil',
	icone: 'layout-dashboard',
};

// ── Le défaut du 21/09 : ce que l'écran enregistrait réellement ──────────────
//  `configDepuisPage` n'écrit PAS `nom` — il n'est pas administrable. Partir de
//  l'enregistrement perdait donc le nom de toute page déjà éditée.
verifier(
	'une surcharge partielle ne perd aucun champ',
	fusionnerSurcharge('tableau-de-bord', { titre: 'Accueil perso' }, DEFAUTS),
	{ ...DEFAUTS, titre: 'Accueil perso', onglets: undefined },
);

verifier(
	'aucune surcharge → les défauts, entiers',
	fusionnerSurcharge('tableau-de-bord', {}, DEFAUTS),
	{ ...DEFAUTS, onglets: undefined },
);

verifier(
	'une surcharge illisible ne vide rien',
	fusionnerSurcharge('tableau-de-bord', null, DEFAUTS),
	{ ...DEFAUTS, onglets: undefined },
);

// ── 🔴 Absent ≠ vide — le cas qui distingue les deux ────────────────────────
verifier(
	'une chaîne VIDE est un choix, et elle est respectée',
	fusionnerSurcharge('tableau-de-bord', { descriptif: '' }, DEFAUTS),
	{ ...DEFAUTS, descriptif: '', onglets: undefined },
);

verifier(
	'une clé à `undefined` n’est PAS une saisie',
	fusionnerSurcharge('tableau-de-bord', { navLabel: undefined }, DEFAUTS),
	{ ...DEFAUTS, onglets: undefined },
);

// ── Les onglets ─────────────────────────────────────────────────────────────
const AVEC_ONGLETS = {
	...DEFAUTS,
	onglets: { fiche: { label: 'Fiche', descriptif: 'La fiche.' } },
};

verifier(
	'onglets absents → ceux des défauts',
	fusionnerSurcharge('residence', {}, AVEC_ONGLETS).onglets,
	AVEC_ONGLETS.onglets,
);

verifier(
	'forme historique : le libellé seul, le descriptif vient des défauts',
	fusionnerSurcharge('residence', { onglets: { fiche: 'Ma fiche' } }, AVEC_ONGLETS).onglets,
	{ fiche: { label: 'Ma fiche', descriptif: 'La fiche.' } },
);

verifier(
	'un onglet surchargé à moitié complète l’autre moitié',
	fusionnerSurcharge('residence', { onglets: { fiche: { label: 'Ma fiche' } } }, AVEC_ONGLETS)
		.onglets,
	{ fiche: { label: 'Ma fiche', descriptif: 'La fiche.' } },
);

// ── Les rattrapages historiques, écrits une seule fois ──────────────────────
verifier(
	'onglet RENOMMÉ : la valeur se reporte, l’ancienne clé part',
	fusionnerSurcharge(
		'prestataires',
		{ onglets: { consommation: { label: 'Conso', descriptif: 'd' } } },
		DEFAUTS,
	).onglets,
	{ consommations: { label: 'Conso', descriptif: 'd' } },
);

verifier(
	'onglet DISPARU : retiré, et jamais réinjecté depuis les défauts',
	fusionnerSurcharge(
		'prestataires',
		{ onglets: { devis: { label: 'Devis', descriptif: 'd' } } },
		{ ...DEFAUTS, onglets: { devis: { label: 'Devis', descriptif: 'd' } } },
	).onglets,
	{},
);

verifier(
	'valeur FIGÉE par une ancienne version : reprise aux défauts',
	fusionnerSurcharge(
		'espace-cs',
		{ onglets: { validations: { label: '✅ Validations', descriptif: 'gardé' } } },
		{ ...DEFAUTS, onglets: { validations: { label: 'Validations', descriptif: 'défaut' } } },
	).onglets,
	{ validations: { label: 'Validations', descriptif: 'gardé' } },
);

verifier(
	'une valeur RÉELLEMENT saisie n’est pas reprise',
	fusionnerSurcharge(
		'espace-cs',
		{ onglets: { validations: { label: 'À valider', descriptif: 'à moi' } } },
		{ ...DEFAUTS, onglets: { validations: { label: 'Validations', descriptif: 'défaut' } } },
	).onglets,
	{ validations: { label: 'À valider', descriptif: 'à moi' } },
);

// ── Un rattrapage ne déborde pas sur une autre page ─────────────────────────
verifier(
	'le rattrapage des prestataires ne touche pas une autre page',
	fusionnerSurcharge(
		'residence',
		{ onglets: { devis: { label: 'Devis', descriptif: 'd' } } },
		DEFAUTS,
	).onglets,
	{ devis: { label: 'Devis', descriptif: 'd' } },
);

if (echecs.length) {
	console.error(`\n✗ Repli des surcharges de page : ${echecs.length} cas sur ${cas} en échec.\n`);
	for (const e of echecs) console.error(e);
	console.error(
		'\n  🔴 Une surcharge absente doit retomber sur la SOURCE, jamais effacer.' +
			'\n  C’est le défaut #1105 : `nom` n’étant pas administrable, il ne figure' +
			'\n  pas dans l’enregistrement — et partir de l’enregistrement le perdait' +
			'\n  pour toute page déjà éditée.\n',
	);
	process.exit(1);
}

console.log(`✓ Repli des surcharges de page : ${cas} cas, tous vérifiés.`);
