//  Le domaine **Courriels des affaires** : ce que la relève de la boîte des
//  réponses a fait de chaque message reçu à l'adresse des affaires (#1447).
//
//  Né le 05/10/2026 avec l'onglet Espace CS › Courriels. Le client de
//  l'administration (`administration.ts`) et ses types sont au plafond de
//  modularité : un domaine neuf a son propre fichier.
import { api } from './client';

/**  Un message relevé dans la boîte des réponses (`GET /courriels-affaires`).
 *   Jamais son texte : le journal dit ce qu'on a DÉCIDÉ (#1447). L'expéditeur est
 *   son adresse en entier pour l'administrateur, son nom seul pour le conseil. */
export interface CourrielReleve {
	id: number;
	releve_le: string;
	envoye_le: string | null;
	expediteur: string;
	objet: string;
	decision: 'accepte' | 'relance' | 'refuse' | 'ignore' | 'a_classer';
	motif: string;
	ticket_id: number | null;
	affaire: string | null;
	/**  Le message en attente de classement, s'il y en a un (#2555). */
	a_classer: CourrielAClasser | null;
}

/**  Une affaire OUVERTE proche d'un message à classer — une proposition, jamais un choix. */
export interface AffaireSuggeree {
	id: number;
	numero: string;
	titre: string;
}

/**  Un message authentifié d'un correspondant connu qu'aucune affaire ne désigne (#2555). */
export interface CourrielAClasser {
	id: number;
	statut: 'a_classer' | 'rattache' | 'cree' | 'ecarte';
	/**  Le début du texte, sans citation — vide une fois classé. */
	apercu: string;
	suggestions: AffaireSuggeree[];
}

/**  Ce qu'un geste de classement a fait. */
export interface Classement {
	bilan: string;
	ticket_id: number | null;
}

/**  Le journal tel que l'onglet Courriels le lit : `limite` est le paramètre du site. */
export interface JournalCourriels {
	limite: number;
	messages: CourrielReleve[];
}

export const courriels = {
	/**  Ce que la relève a fait des derniers messages, et pourquoi (#1447). */
	journal: (): Promise<JournalCourriels> => api.get<JournalCourriels>('/courriels-affaires'),
	/**  Verse le message au fil de l'affaire `numero` (« TK-… »), comme un transfert. */
	rattacher: (id: number, numero: string): Promise<Classement> =>
		api.post<Classement>(`/courriels-affaires/a-classer/${id}/rattacher`, { numero }),
	/**  Une affaire neuve, décrite par le message (Étude & travaux, conseil seul). */
	creerAffaire: (id: number): Promise<Classement> =>
		api.post<Classement>(`/courriels-affaires/a-classer/${id}/creer`),
	/**  Le message n'appelait pas de suite : rien n'est écrit. */
	ecarter: (id: number): Promise<Classement> =>
		api.post<Classement>(`/courriels-affaires/a-classer/${id}/ecarter`),
};
