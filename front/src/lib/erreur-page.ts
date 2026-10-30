/**
 * **Ce que dit la page d'erreur**, par statut (#2304, 30/10/2026).
 *
 * Le dépôt n'avait ni `+error.svelte` ni `error.html` : une adresse inconnue
 * rendait la page de SvelteKit, « 404 » puis « Not Found », en anglais, sans
 * carte ni chemin de retour.
 *
 * Deux usages, une table :
 *  - le TITRE de la page (`routes/+error.svelte`) ;
 *  - la PHRASE qui remplace le message anglais du framework (« Not Found »,
 *    « Internal Error ») — posée par les deux hooks `handleError`, serveur et
 *    navigateur. Une erreur levée par l'application (`error(404, '…')`,
 *    `kind: 'app'`) garde la sienne : elle est déjà en français, et plus
 *    précise que celle-ci.
 *
 * Le message d'une erreur imprévue n'est jamais montré : il peut porter un
 * chemin ou un détail interne (`standards/03` §4).
 */

export interface ErreurDePage {
	titre: string;
	phrase: string;
}

const PAR_STATUT: Record<number, ErreurDePage> = {
	401: {
		titre: 'Session expirée',
		phrase: 'Reconnectez-vous pour continuer.',
	},
	403: {
		titre: 'Accès refusé',
		phrase: 'Votre profil ne donne pas accès à cette page.',
	},
	404: {
		titre: 'Page introuvable',
		phrase:
			'Cette adresse ne correspond à aucune page. Le lien est peut-être ancien, ou mal recopié.',
	},
};

/** Au-delà de 500 : le serveur n'a pas pu répondre — on peut réessayer. */
const SERVEUR: ErreurDePage = {
	titre: 'Une erreur est survenue',
	phrase: 'La page n’a pas pu s’afficher. Réessayez dans un instant.',
};

/** Un statut client que la table ne nomme pas (400, 410…). */
const DEMANDE: ErreurDePage = {
	titre: 'Demande impossible',
	phrase: 'Cette page ne peut pas répondre à cette demande.',
};

/** Le titre et la phrase d'un statut. PURE. */
export function erreurDePage(statut: number): ErreurDePage {
	return PAR_STATUT[statut] ?? (statut >= 500 ? SERVEUR : DEMANDE);
}

/** Vrai quand réessayer a un sens : le serveur, pas la demande, a échoué. PURE. */
export function erreurDuServeur(statut: number): boolean {
	return statut >= 500;
}

/**
 * Ce que les hooks `handleError` rendent : la phrase française à la place de
 * celle du framework ; rien pour une erreur de l'application, qui garde la
 * sienne. PURE.
 */
export function messageDErreur(kind: string, statut: number): { message: string } | undefined {
	if (kind === 'app') return undefined;
	return { message: erreurDePage(statut).phrase };
}
