/**
 * Un compte au mot de passe TEMPORAIRE ne fait que le changer (#3019).
 *
 * Les deux comptes initiaux d'une installation neuve naissent avec un mot de passe
 * écrit au journal du conteneur. L'API sert `mot_de_passe_a_changer` sur le compte
 * (`GET /auth/me`, la connexion) et refuse tout le reste — 403,
 * `detail.code === MOTIF_MOT_DE_PASSE_A_CHANGER` — sauf lire son profil et changer
 * son mot de passe (`api/app/auth/mot_de_passe_a_changer.py`).
 *
 * L'écran suit le CHAMP : la connexion et le squelette `(app)` mènent à
 * `CHEMIN_MOT_DE_PASSE_TEMPORAIRE`. Le refus, s'il arrive quand même (un onglet
 * resté ouvert, une page montée avant que le compte soit lu), y mène aussi, par le
 * client (`api/client.ts`).
 *
 * Le motif est une copie de celui de l'API — front et API ne partagent aucun
 * fichier (#335) : 🔒 `api/tests/test_mot_de_passe_a_changer.py` les compare.
 */

import { cheminCourant, estCibleInterne } from '#lib/redirection.ts';

export const MOTIF_MOT_DE_PASSE_A_CHANGER = 'mot_de_passe_a_changer';

/** L'écran du changement — hors du squelette `(app)`, qui charge ce que l'API refuse. */
export const CHEMIN_MOT_DE_PASSE_TEMPORAIRE = '/auth/mot-de-passe-temporaire';

/** Ce `detail` d'une réponse en erreur est-il le refus du mot de passe temporaire ? */
export function estRefusMotDePasseTemporaire(detail: unknown): boolean {
	return (
		!!detail &&
		typeof detail === 'object' &&
		(detail as { code?: unknown }).code === MOTIF_MOT_DE_PASSE_A_CHANGER
	);
}

/**
 * Mène au changement, en gardant la destination : le `?next=` de la mire, ou la page
 * demandée. Après lui, on reprend où l'on allait (`destinationApresConnexion`). Une
 * navigation COMPLÈTE : ce que la page quittée avait chargé ne la suit pas.
 */
export function menerAuChangement(): void {
	if (typeof window === 'undefined') return;
	const ici = window.location.pathname;
	if (ici === CHEMIN_MOT_DE_PASSE_TEMPORAIRE) return;
	const destination = cheminCourant();
	const suite = ici.startsWith('/auth/')
		? window.location.search
		: estCibleInterne(destination)
			? `?next=${encodeURIComponent(destination)}`
			: '';
	window.location.assign(CHEMIN_MOT_DE_PASSE_TEMPORAIRE + suite);
}
