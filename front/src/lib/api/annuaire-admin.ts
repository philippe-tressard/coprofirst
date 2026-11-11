//  Le client de l'ANNUAIRE de l'espace CS (`routers/admin/annuaire.py`) : ses routes,
//  et ce qu'elles rendent.
//
//  Sorti d'`administration.ts` et de `types-administration.ts` le 05/11/2026 (#2522),
//  qui touchaient tous deux le plafond de 500 lignes. Le serveur déclare désormais ces
//  réponses (`response_model`) : les types RECOPIENT le contrat, ils ne le devinent plus.
import { api, buildQuery } from './client';

/**  Un membre du conseil, tel que l'ADMINISTRATION le lit
 *   (`utils/annuaire.membres_du_conseil(pour_administration=True)`). */
export interface MembreConseilAdmin {
	id: number;
	genre: string;
	prenom: string;
	nom: string;
	/** « Prénom NOM », composé par le serveur. */
	nom_affiche: string;
	batiment_id: number | null;
	/** Le NUMÉRO du bâtiment (« A »), pas son libellé (« Bât. A »). */
	batiment_nom: string | null;
	etage: number | null;
	/** « RDC », « 2ème étage », `""` sans étage. */
	etage_libelle: string;
	est_gestionnaire_site: boolean;
	est_president: boolean;
	photo_url: string | null;
	ordre: number;
	user_id: number | null;
}

/**  `GET /admin/annuaire/cs` (`CompositionConseil`). */
export interface CompositionConseil {
	ag_annee: number | null;
	/** ISO « AAAA-MM-JJ », ou `null`. */
	ag_date: string | null;
	/** `""` quand aucun lien n'est posé — jamais `null` ici. */
	whatsapp_url: string;
	membres: MembreConseilAdmin[];
}

/**  Un interlocuteur du syndic, tel que l'ADMINISTRATION le lit
 *   (`utils/annuaire.membres_du_syndic(pour_administration=True)`). */
export interface MembreSyndicAdmin {
	id: number;
	genre: string;
	prenom: string;
	nom: string;
	nom_affiche: string;
	fonction: string | null;
	email: string | null;
	/** Plusieurs numéros séparés par des virgules, s'il y en a. */
	telephone: string | null;
	/** Les mêmes, découpés (`utils/telephones`). */
	telephones: string[];
	est_principal: boolean;
	photo_url: string | null;
	ordre: number;
	user_id: number | null;
}

/**  `GET /admin/annuaire/syndic` (`InfoSyndicAdmin`). Le nom vient du CONTRAT quand
 *   il y en a un (#535) : `nom_syndic_source` dit si la saisie sert encore. */
export interface InfoSyndicAdmin {
	nom_syndic: string;
	nom_syndic_source: 'contrat' | 'saisie' | 'aucune';
	adresse: string;
	site_web: string | null;
	membres: MembreSyndicAdmin[];
}

/**  `PUT /admin/annuaire/cs` : la composition ENREGISTRÉE, rapprochements compris. */
export interface ConseilEnregistre extends CompositionConseil {
	ok: true;
}

/**  `PUT /admin/annuaire/syndic`. */
export interface SyndicEnregistre extends InfoSyndicAdmin {
	ok: true;
}

/**  `GET /admin/annuaire/rapprochement` : ce qu'un NOM saisi désigne — l'inscrit
 *   actif de même nom, et son logement d'après le registre importé (#2522). */
export interface Rapprochement {
	user_id: number | null;
	batiment_id: number | null;
	/** Le NUMÉRO du bâtiment (« A »). */
	batiment_nom: string | null;
	etage: number | null;
	/** « RDC », « 2ème étage » — `""` sans étage, comme la fiche du membre (#2633). */
	etage_libelle: string;
}

export const annuaireAdmin = {
	getCS: () => api.get<CompositionConseil>('/admin/annuaire/cs'),
	putCS: (data: unknown) => api.put<ConseilEnregistre>('/admin/annuaire/cs', data),
	getSyndic: () => api.get<InfoSyndicAdmin>('/admin/annuaire/syndic'),
	putSyndic: (data: unknown) => api.put<SyndicEnregistre>('/admin/annuaire/syndic', data),
	/** Ce qu'un nom saisi désigne : l'inscrit, et (`localiser`) son logement (#2522). */
	rapprocher: (nom: string, localiser: boolean) =>
		api.get<Rapprochement>(
			`/admin/annuaire/rapprochement${buildQuery({ nom, localiser: String(localiser) })}`,
		),
};
