/**
 *  Ce que le contrôle de la palette sombre MESURE (#2174, lot S3, 29/10/2026) —
 *  la table déclarée, séparée de la mécanique (`check-palette-sombre.mjs`).
 *
 *  ## Les paires
 *
 *  Un texte ou un trait, posé sur un fond, tels que les écrans les emploient —
 *  reprises de la maquette arbitrée (58 paires), étendues aux jetons du lot S2.
 *  `[usage, avant-plan, fond, seuil]` : 4,5 pour un texte, 3 pour un pictogramme,
 *  un liseré ou la bordure d'un champ (WCAG 1.4.3 et 1.4.11). Les deux plans
 *  sont des expressions CSS (`var()`, `color-mix`, `rgba`) résolues dans les
 *  jetons du thème mesuré. Les badges de `composants.css` sont mesurés en plus,
 *  par leurs propres règles, sans être recopiés ici.
 *
 *  Chaque paire se mesure dans LES DEUX thèmes. Une paire qui échoue déjà au
 *  clair le dit dans son cinquième champ — la raison, et le ticket qui la suit ;
 *  le contrôle échoue si elle cesse d'échouer (l'écart se retire alors d'ici).
 *  Au sombre, aucun écart n'est admis.
 */

const T = 4.5;
const M = 3;
/** Le ticket qui suit les contrastes du thème CLAIR sous l'AA. */
const CLAIR = '#2296';

const serie = (i, clair) => [
	`Série ${i} sur carte`,
	`var(--serie-${i})`,
	'var(--color-surface)',
	M,
	clair,
];
const palier = (i, clair) => [
	`Palier ${i} sur carte`,
	`var(--palier-${i})`,
	'var(--color-surface)',
	M,
	clair,
];
const FILS = [
	'rouge',
	'ambre',
	'olive',
	'vert',
	'sarcelle',
	'cyan',
	'indigo',
	'violet',
	'fuchsia',
	'rose',
	'inconnu',
];
/** Une étape du kanban : son texte sur sa teinte à 10,2 % (`kanban.css`, `.kb-col-count`). */
const etape = (nom, clair) => [
	`Étape « ${nom} » du kanban`,
	`var(--kanban-${nom})`,
	`color-mix(in srgb, var(--kanban-${nom}) 10.2%, var(--color-surface))`,
	T,
	clair,
];
const enDessousAuClair = `les séries et les paliers clairs portent leur information par la légende et le nombre (socle.css) — ${CLAIR}`;

export const PAIRES = [
	['Texte courant sur la page', 'var(--color-text)', 'var(--color-bg)', T],
	['Texte courant sur une carte', 'var(--color-text)', 'var(--color-surface)', T],
	['Texte atténué sur la page', 'var(--color-text-muted)', 'var(--color-bg)', T],
	['Texte atténué sur une carte', 'var(--color-text-muted)', 'var(--color-surface)', T],
	['Texte atténué sur encart neutre', 'var(--color-text-muted)', 'var(--color-neutre-fond)', T],
	['Lien sur une carte', 'var(--color-primary)', 'var(--color-surface)', T],
	['Lien sur la page', 'var(--color-primary)', 'var(--color-bg)', T],
	['Lien sur encart neutre', 'var(--color-primary)', 'var(--color-neutre-fond)', T],
	['Entrée de navigation active', 'var(--color-primary)', 'var(--color-primary-light)', T],
	['Toast info (texte appuyé)', 'var(--color-primary-dark)', 'var(--color-primary-light)', T],
	['Bouton primaire', 'var(--color-sur-plein)', 'var(--color-primary-plein)', T],
	['Bouton primaire (survol)', 'var(--color-sur-plein)', 'var(--color-primary-plein-survol)', T],
	['Bouton danger', 'var(--color-sur-plein)', 'var(--color-danger-plein)', T],
	['Aplat succès', 'var(--color-sur-plein)', 'var(--color-success-plein)', T],
	['Aplat succès (survol)', 'var(--color-sur-plein)', 'var(--color-success-plein-survol)', T],
	['Aplat info', 'var(--color-sur-plein)', 'var(--color-info-plein)', T],
	['Aplat sarcelle', 'var(--color-sur-plein)', 'var(--color-sarcelle-plein)', T],
	[
		'Aplat or (avatar, médaillon, pastille)',
		'var(--color-sur-accent)',
		'var(--color-accent-plein)',
		T,
	],
	['En-tête d’accueil : titre', 'var(--color-text-inverse)', 'var(--color-primary-plein)', T],
	[
		'En-tête d’accueil : mention',
		'var(--color-sur-plein-discret)',
		'var(--color-primary-plein)',
		T,
	],
	['Badge succès', 'var(--color-success-texte)', 'var(--color-success-fond)', T],
	[
		'Toast succès',
		'var(--color-success)',
		'var(--color-success-fond)',
		T,
		`4,44 : le toast écrit le jeton d'état, pas son dérivé -texte — ${CLAIR}`,
	],
	['Badge avertissement', 'var(--color-warning-texte)', 'var(--color-warning-fond)', T],
	['Toast erreur', 'var(--color-danger)', 'var(--color-danger-fond)', T],
	['Message d’erreur de champ', 'var(--color-danger)', 'var(--color-surface)', T],
	['Badge info (conseil)', 'var(--color-info)', 'var(--color-info-fond)', T],
	['Badge violet', 'var(--color-violet)', 'var(--color-violet-fond)', T],
	['Badge sarcelle', 'var(--color-sarcelle)', 'var(--color-sarcelle-fond)', T],
	['Badge orange (urgence)', 'var(--color-orange-texte)', 'var(--color-orange-fond)', T],
	['Badge jaune (en cours)', 'var(--color-jaune-texte)', 'var(--color-jaune-fond)', T],
	['Tuile d’import « rattaché »', 'var(--color-import-lie)', 'var(--color-surface)', T],
	['Bordure de champ sur carte', 'var(--color-border-champ)', 'var(--color-surface)', M],
	['Bordure de champ sur son fond', 'var(--color-border-champ)', 'var(--color-bg)', M],
	['Focus : bordure du champ', 'var(--color-primary)', 'var(--color-bg)', M],
	['Liseré d’avertissement', 'var(--color-warning)', 'var(--color-surface)', M],
	['Liseré de succès', 'var(--color-success)', 'var(--color-surface)', M],
	['Liseré de danger', 'var(--color-danger)', 'var(--color-surface)', M],
	['Liseré d’info', 'var(--color-info)', 'var(--color-surface)', M],
	['Icône vert Parc', 'var(--color-secondary)', 'var(--color-surface)', M],
	[
		'Icône or',
		'var(--color-accent)',
		'var(--color-surface)',
		M,
		`2,61 : l'or de la charte — ${CLAIR}`,
	],
	serie(1),
	serie(2),
	serie(3, enDessousAuClair),
	serie(4, enDessousAuClair),
	serie(5, enDessousAuClair),
	serie(6),
	serie(7),
	serie(8),
	palier(1),
	palier(2),
	palier(3, enDessousAuClair),
	palier(4, enDessousAuClair),
	...FILS.map((f) => [`Fil : ${f}`, `var(--fil-${f})`, `var(--fil-${f}-fond)`, T]),
	etape('ag', `la teinte du périmètre n°6 en texte — ${CLAIR}`),
	etape('cs', `la teinte du périmètre n°2 en texte — ${CLAIR}`),
	etape('syndic', `la teinte du périmètre n°4 en texte — ${CLAIR}`),
	etape('fournisseur', `la teinte du périmètre n°5 en texte — ${CLAIR}`),
	etape('termine', `la teinte du périmètre n°3 en texte — ${CLAIR}`),
	etape('annule', `un gris clair en texte — ${CLAIR}`),
];

/**
 *  Les jetons de THÈME : ceux que le bloc sombre doit couvrir. Un jeton de
 *  `:root` dont la valeur est une couleur hors de ces familles fait échouer —
 *  une famille neuve ne passe pas sous le contrôle sans un mot.
 */
export const FAMILLES = [
	'--color-',
	'--serie-',
	'--palier-',
	'--fil-',
	'--teinte-',
	'--kanban-',
	'--shadow',
];

/**
 *  Les jetons qui gardent leur valeur au sombre, et pourquoi. Le contrôle échoue
 *  si l'un d'eux est aussi redéfini dans le bloc sombre, ou n'existe plus.
 */
const APLAT_DE_PERIMETRE =
	'aplat de pastille sous un texte --color-sur-plein : le couple ne dépend pas du thème';
export const IDENTIQUES = {
	'--color-accent': 'l’or de la charte tient 6,1:1 sur la surface sombre',
	'--color-text-inverse': 'texte clair sur l’aplat primaire, qui reste foncé',
	'--color-sur-plein': 'texte sur un aplat, qui reste foncé au sombre',
	'--color-sur-voile': 'texte sur un voile noir, sombre dans les deux thèmes',
	'--color-sur-accent': 'texte sur l’or, qui ne change pas',
	...Object.fromEntries(
		[...Array.from({ length: 12 }, (_, i) => `--teinte-${i + 1}`), '--teinte-copropriete'].map(
			(n) => [n, APLAT_DE_PERIMETRE],
		),
	),
	'--kanban-annule': 'gris moyen : 6,3:1 sur la carte sombre, sans retouche',
};
