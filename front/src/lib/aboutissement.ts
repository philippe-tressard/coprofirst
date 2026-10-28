/**
 * **Les gestes dont on mesure l'aboutissement** (#1633) — la liste FERMÉE,
 * déclarée ici et nulle part ailleurs.
 *
 * On savait qu'une page de formulaire avait été vue, pas si le geste avait
 * abouti. Chaque geste envoie deux événements par la mesure d'audience
 * (`trackEvent`, qui hérite du refus du profil) : son OUVERTURE quand le
 * formulaire s'ouvre, son ENVOI quand l'enregistrement a réussi. Le `detail` est
 * l'identifiant du geste — jamais un contenu saisi. Le serveur les compte, sans
 * compte ni page (`api/app/utils/gestes_formulaire.py`) ; l'onglet Télémétrie
 * lit ici leurs libellés.
 *
 * ⚠️ À ne pas confondre avec `#lib/gestes`, qui NOMME les gestes à l'écran
 * (« Ajouter une suite ») : celui-ci les MESURE.
 *
 * Un geste neuf : une ligne dans `GESTES_MESURES`, puis `ouvrirGeste` là où son
 * formulaire s'ouvre et `aboutirGeste` là où son envoi réussit — dans le
 * composant qui tient l'ouverture et l'envoi, pas écran par écran.
 */
import { trackEvent } from '#lib/telemetry.ts';

export const GESTES_MESURES = {
	'affaire.creer': 'Créer une affaire',
	'affaire.repondre': 'Répondre à une affaire',
	'sondage.voter': 'Voter à un sondage',
	'document.deposer': 'Déposer un document',
} as const;

export type GesteMesure = keyof typeof GESTES_MESURES;

/** ⚠️ Tenues à la main avec `ACTION_OUVERTURE` et `ACTION_ENVOI` de
 *  `api/app/utils/gestes_formulaire.py` : le front et l'API ne partagent aucun fichier. */
const ACTION_OUVERTURE = 'click';
const ACTION_ENVOI = 'submit';

function page(): string {
	return typeof window === 'undefined' ? '/' : window.location.pathname;
}

/** Le formulaire du geste vient de s'ouvrir. */
export function ouvrirGeste(geste: GesteMesure) {
	trackEvent(page(), ACTION_OUVERTURE, geste);
}

/** L'envoi du geste a réussi — à appeler APRÈS la réponse du serveur, jamais au clic. */
export function aboutirGeste(geste: GesteMesure) {
	trackEvent(page(), ACTION_ENVOI, geste);
}
