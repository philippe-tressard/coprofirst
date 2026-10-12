/**
 *  Les questions au règlement de copropriété — Ma résidence › Règlement.
 *
 *  Le serveur décide de tout : si l'assistant peut répondre (`disponible`), si
 *  un texte est joint, et quels extraits ont été RETROUVÉS dans ce texte
 *  (`verifie`, `page`, `acte` — calculés par le code, jamais par le modèle).
 *  L'écran ne recompose rien.
 *
 *  Routes : `api/app/routers/reglement.py` — copropriétaires (si l'usage leur est
 *  ouvert), conseil et admin. Un copropriétaire ne reçoit que SES questions, sans
 *  modèle ; le coût d'un appel n'est rendu à personne. Les FICHIERS du règlement passent par le client des documents
 *  (catégorie réservée à l'administration).
 */
import { api } from './client';

/** Ce que l'onglet lit en arrivant. */
export interface EtatReglement {
	disponible: boolean;
	/** Un fichier Markdown lisible est-il joint ? — sans lui, pas de question. */
	texte_disponible: boolean;
	/** Le règlement publié dans la Fiche — `null` pour l'administration. */
	lien_reglement: string | null;
	/** Pour l'administration seule : la catégorie où joindre les fichiers
	 *  (`documents.uploadPour('categorie', …)`). */
	categorie_id: number | null;
	/** Pour l'administration seule : d'où vient le texte (« la numérisation du RCP… »). */
	provenance: string | null;
}

/** Un extrait cité par l'assistant, et ce que le code en a vérifié. */
export interface ExtraitReglement {
	citation: string;
	/** La référence DONNÉE par le modèle. */
	reference: string;
	apport: string;
	/** Retrouvé mot pour mot dans le texte chargé. */
	verifie: boolean;
	/** Le repère de page qui le précède dans le texte — s'il a été retrouvé. */
	page: string | null;
	/** L'acte (« LIVRE I ») qui le contient. */
	acte: string | null;
}

/** Une question posée, et la réponse du juriste. */
export interface QuestionReglement {
	id: number;
	question: string;
	verdict: 'oui' | 'non' | 'sous_conditions' | 'non_prevu' | 'incertain';
	verdict_libelle: string;
	reponse: string;
	reserves: string | null;
	extraits: ExtraitReglement[];
	texte_id: number;
	/** Faux : la réponse a lu une version remplacée depuis. */
	texte_en_vigueur: boolean;
	/** D'où vient le texte lu — celle de la question, sinon l'actuelle. */
	provenance: string | null;
	auteur_nom: string | null;
	modele: string | null;
	faq_item_id: number | null;
	/** Son auteur et l'administration — la corbeille s'affiche d'après lui. */
	peut_supprimer: boolean;
	cree_le: string;
}

/** Une entrée de FAQ, telle que le conseil l'a relue. */
export interface PublicationFaq {
	categorie: string;
	question: string;
	reponse: string;
	ordre?: number;
}

export const reglement = {
	/** L'onglet se montre-t-il ? — faux pour un copropriétaire tant que
	 *  l'administration ne lui a pas ouvert l'usage. */
	acces: () => api.get<{ acces: boolean }>('/reglement/acces'),
	etat: () => api.get<EtatReglement>('/reglement'),
	questions: () => api.get<QuestionReglement[]>('/reglement/questions'),
	poser: (question: string) => api.post<QuestionReglement>('/reglement/questions', { question }),
	publierDansLaFaq: (id: number, corps: PublicationFaq) =>
		api.post<QuestionReglement>(`/reglement/questions/${id}/faq`, corps),
	supprimerQuestion: (id: number) => api.delete(`/reglement/questions/${id}`),
	/** Administration seule — rend l'état de l'onglet relu. */
	modifierProvenance: (provenance: string) =>
		api.put<EtatReglement>('/reglement/provenance', { provenance }),
};
