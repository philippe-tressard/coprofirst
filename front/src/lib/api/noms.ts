//  Le nom d'une personne en cours de SAISIE, rendu par le serveur (#2633) —
//  `routers/noms.py`. Un objet ENREGISTRÉ sert le sien (`nom_affiche`).
import { api } from './client';

/**  `NomRendu` : « Prénom NOM » (`utils/noms.nom_affiche`), vide si l'un et l'autre manquent. */
export interface NomRendu {
	nom_affiche: string;
}

/**  Ce que la saisie dit de la personne. */
export interface NomSaisi {
	prenom?: string | null;
	nom?: string | null;
}

export const noms = {
	/**  L'aperçu d'une saisie (`#lib/apercu-nom`). */
	affiche: (personne: NomSaisi) =>
		api.post<NomRendu>('/noms/affiche', {
			prenom: personne.prenom ?? null,
			nom: personne.nom ?? null,
		}),
};
