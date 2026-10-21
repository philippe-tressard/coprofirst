#!/usr/bin/env node
/**
 *  Garde-fou : la vignette qui dit un NOMBRE d'objets est `Compte.svelte`, et
 *  elle ne se redessine pas ailleurs (10/10/2026).
 *
 *  ## Pourquoi il existe
 *
 *  Le badge Bleu Seine des Archives était écrit deux fois — `.sr-compte`
 *  (`SectionRepliee`) et `.archives-compte` (`ArchivesParAnnee`) —, et les deux
 *  copies avaient déjà dérivé : `--fs-xs` contre `--fs-2xs`. La troisième
 *  arrivait avec les pastilles de filtre d'Affaires (maquette B, arbitrée à
 *  l'écran : « normalise la vignette sur ce qui se fait par ailleurs, comme
 *  Archives »). Les trois passent désormais par `Compte`.
 *
 *  `lint:css-duplique` ne pouvait rien voir : il compare des règles de MÊME
 *  nom, et une copie de badge prend toujours le nom de son écran.
 *
 *  ## Ce qu'il reconnaît
 *
 *  La SIGNATURE d'une vignette de compte, quel que soit son nom : un fond de
 *  couleur de la charte, un rayon de pastille et une graisse appuyée dans la
 *  MÊME règle. Une règle qui n'en porte que deux est autre chose (un bouton,
 *  un onglet actif).
 *
 *  Lancer : node scripts/check-vignette-compte.mjs [--selftest]
 */
import { controler } from './lib-source-unique.mjs';
import { neutraliserCommentaires } from './lib-commentaires.mjs';

/**  Écarts déclarés, avec leur raison. Une entrée qui ne sert plus fait échouer. */
const EXCEPTIONS = {
	'src/lib/components/SignalATraiter.svelte':
		'un SIGNAL en rouge (« à traiter »), pas un nombre d’objets : autre notion, autre couleur',
	'src/lib/components/RaccourcisRapides.svelte':
		'la vignette resserrée des raccourcis de l’accueil, avec ses tons urgent et orange — à réunir avec `Compte` si l’on en décide (sa taille changerait)',
};

const FOND = /background(?:-color)?:\s*var\(--color-(?:primary|danger|info|accent|secondary)\)/;
const RAYON = /border-radius:\s*(?:999px|9999px|12px|1rem|50%)/;
const GRAISSE = /font-weight:\s*(?:600|700|bold)/;

/** Les lignes d'ouverture des règles qui portent la signature. PURE. */
export function fautes(source) {
	const texte = neutraliserCommentaires(source);
	const trouvees = [];
	const regle = /\{([^{}]*)\}/g;
	let m;
	while ((m = regle.exec(texte))) {
		const corps = m[1];
		if (FOND.test(corps) && RAYON.test(corps) && GRAISSE.test(corps)) {
			trouvees.push(texte.slice(0, m.index).split('\n').length);
		}
	}
	return trouvees;
}

process.exit(
	controler({
		extensions: ['.svelte', '.css'],
		temoin: 'src/lib/components/Compte.svelte',
		exceptions: EXCEPTIONS,
		fautes,
		cas: [
			[
				'.archives-compte {\n\tbackground: var(--color-primary);\n\tborder-radius: 12px;\n\tfont-weight: 700;\n}',
				1,
			],
			[
				'.nb {\n\tfont-weight: 600;\n\tbackground-color: var(--color-info);\n\tborder-radius: 999px;\n}',
				1,
			],
			//  Un bouton plein : fond et rayon, sans graisse appuyée.
			['.btn {\n\tbackground: var(--color-primary);\n\tborder-radius: 999px;\n}', 0],
			//  Une pastille au repos : graisse et rayon, fond blanc.
			[
				'.p {\n\tbackground: var(--color-surface);\n\tborder-radius: 999px;\n\tfont-weight: 700;\n}',
				0,
			],
			//  Un commentaire qui cite la forme refusée.
			['/* .x { background: var(--color-primary); border-radius: 12px; font-weight: 700; } */', 0],
		],
		ok: 'Vignettes de compte : rendues par Compte.svelte seul',
		ko: 'vignette(s) de compte redessinée(s) hors de Compte.svelte',
		conseil:
			'Employer `<Compte n={…} />` (`$lib/components/Compte.svelte`) — `surAplat` sur un fond Bleu Seine — ou `compte` sur une `Pastille`.',
	}),
);
