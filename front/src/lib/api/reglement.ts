/**
 *  Les questions au règlement de copropriété — Ma résidence › Règlement.
 *
 *  Le serveur décide de tout : si l'assistant peut répondre (`disponible`), quel
 *  texte est en vigueur, et quels extraits ont été RETROUVÉS dans ce texte
 *  (`verifie`, `page`, `acte` — calculés par le code, jamais par le modèle).
 *  L'écran ne recompose rien.
 *
 *  Routes : `api/app/routers/reglement.py` — copropriétaires (si l'usage leur est
 *  ouvert), conseil et admin. Un copropriétaire ne reçoit que SES questions, sans
 *  modèle ni coût, et le texte sans sa fiche technique : les champs concernés
 *  arrivent `null`.
 */
import { api } from './client';

/** Une version du texte du règlement chargée par l'administration. */
export interface TexteReglement {
	id: number;
	titre: string;
	/** La fiche technique — `null` pour un copropriétaire. */
	nom_fichier: string | null;
	nb_caracteres: number | null;
	charge_par: string | null;
	cree_le: string;
}

/** Un acte de la bibliothèque montré à côté du texte, et où CE lecteur l'ouvre. */
export interface DocumentReglement {
	id: number;
	titre: string;
	lien: string;
}

/** Un document que l'administration peut lier au texte. */
export interface DocumentCandidatReglement {
	id: number;
	titre: string;
	categorie: string;
}

/** Ce que l'onglet lit en arrivant. */
export interface EtatReglement {
	disponible: boolean;
	texte: TexteReglement | null;
	nb_versions: number;
	documents: DocumentReglement[];
	/** Pour l'administration seule — `null` pour les autres. */
	documents_candidats: DocumentCandidatReglement[] | null;
	documents_ids: number[] | null;
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
	texte_charge_le: string | null;
	auteur_nom: string | null;
	modele: string | null;
	cout_usd: string | null;
	faq_item_id: number | null;
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
	charger: (nom_fichier: string, contenu: string) =>
		api.post<TexteReglement>('/reglement/textes', { nom_fichier, contenu }),
	/** Les actes montrés à côté du texte, dans l'ordre d'affichage (admin). */
	choisirDocuments: (ids: number[]) => api.put<number[]>('/reglement/documents', { ids }),
	questions: () => api.get<QuestionReglement[]>('/reglement/questions'),
	poser: (question: string) => api.post<QuestionReglement>('/reglement/questions', { question }),
	publierDansLaFaq: (id: number, corps: PublicationFaq) =>
		api.post<QuestionReglement>(`/reglement/questions/${id}/faq`, corps),
	supprimerQuestion: (id: number) => api.delete(`/reglement/questions/${id}`),
};
