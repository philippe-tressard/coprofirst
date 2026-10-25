/**
 * L'état descriptif du RÈGLEMENT — l'atelier d'import qui dit ce qu'est chaque lot
 * (nature, circulation qui le dessert, tantièmes), `routers/lots_etat_descriptif.py` (#2213).
 *
 * Module à part de `patrimoine` : celui-ci passait 500 lignes (modularité, rang 1).
 */
import { api, postFormData, BASE } from './client';

/** Un constat du patrimoine — `Constat` (`utils/constats.py`) : état descriptif, onglet Lots. */
export interface ConstatPatrimoine {
	code: string;
	gravite: 'bloquant' | 'inconnu' | 'avertissement' | 'information';
	message: string;
	lots: string[];
}

/** Une ligne de l'état descriptif, telle que le fichier l'écrit — `LigneLue`. */
export interface LigneEtatDescriptif {
	rang: number;
	lot: string;
	batiment: string | null;
	nature: string | null;
	/** La nature reconnue, `null` si la mention est illisible. */
	nature_lue: string | null;
	numero_usage: string | null;
	niveau: string | null;
	circulation: string | null;
	lot_origine: string | null;
	source: string | null;
	/** Tantièmes par code de clé. */
	quotes: Record<string, number>;
}

/** L'atelier de l'état descriptif — `EtatDescriptifLu`. */
export interface EtatDescriptif {
	importe_le: string | null;
	applique_le: string | null;
	cles: { code: string; libelle: string; denominateur: number }[];
	lignes: LigneEtatDescriptif[];
	constats: ConstatPatrimoine[];
	lettres_citees: string[];
	batiments: { id: number; libelle: string; lettre_rcp: string | null }[];
	applicable: boolean;
	/** L'assistant peut-il lire le règlement ? (usage activé, clé, modèle — #2218) */
	ia_disponible: boolean;
	/** L'issue de la lecture qui remplit l'import ; `null` pour un fichier téléversé. */
	lecture_ia: 'en_cours' | 'terminee' | 'echec' | null;
	erreur_ia: string | null;
}

/** Le bilan d'une application de l'état descriptif — `Application`. */
export interface BilanEtatDescriptif {
	lots: number;
	cles_creees: number;
	quotes_modifiees: number;
	perimetres_modifies: number;
}

export const etatDescriptif = {
	lire: () => api.get<EtatDescriptif>('/lots/admin/etat-descriptif'),
	televerser: (file: File) => postFormData<EtatDescriptif>('/lots/admin/etat-descriptif', { file }),
	saisirLettres: (correspondances: { batiment_id: number; lettre_rcp: string | null }[]) =>
		api.put<EtatDescriptif>('/lots/admin/etat-descriptif/lettres', { correspondances }),
	appliquer: () => api.post<BilanEtatDescriptif>('/lots/admin/etat-descriptif/appliquer', {}),
	/** L'assistant lit le règlement versé, en tâche de fond : rend l'état « en cours ». */
	lireReglement: () => api.post<EtatDescriptif>('/lots/admin/etat-descriptif/lire-reglement', {}),
	gabaritUrl: (): string => `${BASE}/lots/admin/etat-descriptif/gabarit`,
};
