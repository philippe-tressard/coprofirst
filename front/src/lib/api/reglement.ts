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
	/** Pour l'administration seule : la catégorie des décisions d'AG transcrites
	 *  (29/10/2026), que l'assistant lit après le règlement. */
	categorie_ag_id: number | null;
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
	/** L'acte (« LIVRE I ») qui le contient — ou l'AG (« Assemblée générale du … »). */
	acte: string | null;
	/** `reglement` ou `ag`, déduit de sa place dans le texte — `null` sans décision
	 *  d'AG jointe, ou s'il n'a pas été retrouvé. */
	source: 'reglement' | 'ag' | null;
}

/** Une question posée, et la réponse du juriste. */
export interface QuestionReglement {
	id: number;
	question: string;
	verdict: 'oui' | 'non' | 'sous_conditions' | 'non_prevu' | 'incertain';
	verdict_libelle: string;
	reponse: string;
	/** Les sections de l'avis (29/10/2026) — `null` dans un avis plus ancien. */
	selon_reglement: string | null;
	selon_ag: string | null;
	synthese: string | null;
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

/** La transcription d'un PV d'AG par l'assistant — `api/app/routers/reglement_transcriptions.py`. */
export interface TranscriptionPv {
	id: number;
	statut: 'en_cours' | 'a_relire' | 'validee' | 'echec';
	statut_libelle: string;
	/** Le Markdown rendu, puis tel que l'administration l'a relu. */
	contenu: string | null;
	erreur: string | null;
	cree_le: string;
	valide_le: string | null;
}

/** Un PV de la Fiche, et sa dernière transcription. */
export interface PvTranscrit {
	pv_id: number;
	titre: string;
	date_ag: string | null;
	transcription: TranscriptionPv | null;
}

/** Les PV et leurs transcriptions — administration seule. */
export interface EtatTranscriptions {
	/** L'usage « Transcription d'un PV » est-il prêt ? */
	disponible: boolean;
	pvs: PvTranscrit[];
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
	/** Les transcriptions des PV d'AG — administration seule (29/10/2026). */
	transcriptions: () => api.get<EtatTranscriptions>('/reglement/transcriptions'),
	transcrire: (pvId: number) =>
		api.post<TranscriptionPv>(`/reglement/transcriptions/pv/${pvId}`, {}),
	validerTranscription: (id: number, contenu: string) =>
		api.post<TranscriptionPv>(`/reglement/transcriptions/${id}/valider`, { contenu }),
	rejeterTranscription: (id: number) => api.delete(`/reglement/transcriptions/${id}`),
};
