/**
 * L'AIGUILLAGE d'une installation commune à plusieurs copropriétés (#1894) —
 * `installation_commune/routeur.py`. L'hôte commun ne fait que rediriger : il
 * demande à quelle copropriété on veut se connecter (code postal + nom), puis
 * renvoie le navigateur à son adresse.
 *
 * Ailleurs — sous l'adresse d'une copropriété, ou sur une installation propre à
 * une copropriété —, `etat` répond `{ hote_commun: false }` (jamais une erreur :
 * l'écran de connexion le demande à chaque visite) et `aller` répond 404.
 */

import { api } from './client';

/** Ce que l'aiguillage reçoit : code postal et nom, ou l'alias d'un chemin `/<alias>`. */
export type DemandeAiguillage = { code_postal: string; nom: string } | { alias: string };

export const aiguillage = {
	/** `{ hote_commun: true }` sur l'hôte commun ; `false` partout ailleurs. */
	etat: () => api.get<{ hote_commun: boolean }>('/plateforme/aiguillage'),
	/** L'adresse de la copropriété ; 404 (toujours le même message) si aucune ne correspond. */
	aller: (demande: DemandeAiguillage) =>
		api.post<{ destination: string }>('/plateforme/aiguillage', demande),
};
