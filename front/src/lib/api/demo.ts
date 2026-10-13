/**
 * La DÉMO PUBLIQUE (spec `specs/architecture/mode-demo.md`, #1906) : ses
 * personnages, et l'adresse qui ouvre la session de l'un d'eux.
 *
 * Les personnages vivent au serveur (`app/demo/personnages.py`) : la page de
 * connexion les LIT, elle ne recopie ni leurs libellés ni leurs descriptions.
 */

import { api, BASE } from './client';

/** `GET /demo/personnages` — liste vide hors démo. */
export interface PersonnageDemo {
	code: string;
	libelle: string;
	description: string;
}

export const demo = {
	personnages: () => api.get<PersonnageDemo[]>('/demo/personnages'),
	/** Un LIEN, pas un appel : la route pose les cookies de session et renvoie à
	 *  l'accueil (303). C'est aussi l'adresse des boutons de la page d'accueil. */
	urlEntree: (code: string): string => `${BASE}/demo/entrer/${encodeURIComponent(code)}`,
};
