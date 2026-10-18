//  Les AVIS sur l'application (#2075) — onglet « Avis » de la Communauté.
//
//  Un module à part, comme côté serveur (`routers/avis.py`) : l'avis parle de
//  l'application, pas de la résidence. Les types sont lus sur `avis_schemas.py`.
import { api, BASE } from './client';

/**  Un avis tel que CE lecteur a le droit de le lire (`AvisRead`).
 *   `remarque`, `consentement_publication`, `publiable` et `publication_validee`
 *   ne sont servis qu'à l'auteur et au gestionnaire du site — `null` / `false`
 *   pour tout autre lecteur : l'écran ne masque rien lui-même. */
export interface Avis {
	id: number;
	note: number;
	titre: string;
	description: string;
	/** « Prénom N. » — composé par le serveur (`utils/noms.nom_abrege`). */
	auteur_nom: string;
	auteur_role: string | null;
	est_auteur: boolean;
	reponse: string | null;
	reponse_le: string | null;
	cree_le: string;
	mis_a_jour_le: string | null;
	/** Retiré (📦) — ne se lit plus que de l'auteur et du gestionnaire. */
	archivee: boolean;
	/** Ce lecteur peut le ressortir (↩️). */
	restaurable: boolean;
	/** Tous le lisent (l'auteur l'a accepté) — sinon l'auteur et le conseil seuls. */
	lu_de_tous: boolean;
	remarque: string | null;
	consentement_publication: boolean | null;
	publiable: boolean;
	publication_validee: boolean;
}

/** `GET /avis` — la liste, et ce que le lecteur peut y faire. */
export interface AvisListe {
	avis: Avis[];
	/** Le lecteur gère le site : répondre, retenir pour coprofirst.fr, exporter. */
	gestionnaire: boolean;
	/** L'avis du lecteur, s'il en a donné un — retiré compris. */
	mon_avis_id: number | null;
}

/** Ce qu'on saisit — dépôt (`AvisCreate`) ou correction (`AvisUpdate`). */
export interface AvisSaisie {
	note: number;
	titre: string;
	description: string;
	remarque: string | null;
	consentement_publication: boolean | null;
}

export const avis = {
	list: () => api.get<AvisListe>('/avis'),
	create: (data: AvisSaisie) => api.post<Avis>('/avis', data),
	modifier: (id: number, data: Partial<AvisSaisie>) => api.patch<Avis>(`/avis/${id}`, data),
	//  📦 / ↩️ — un seul mot pour ranger et ressortir, comme les prestataires (#1538).
	archiver: (id: number, archivee: boolean) =>
		api.patch<void>(`/avis/${id}/archivage`, { archivee }),
	delete: (id: number) => api.delete(`/avis/${id}`),
	repondre: (id: number, reponse: string) => api.put<Avis>(`/avis/${id}/reponse`, { reponse }),
	retenir: (id: number, validee: boolean) =>
		api.patch<Avis>(`/avis/${id}/publication`, { validee }),
	/** Le fichier JSON des avis retenus, pour coprofirst.fr — un lien de téléchargement. */
	exportUrl: (): string => `${BASE}/avis/export`,
};
