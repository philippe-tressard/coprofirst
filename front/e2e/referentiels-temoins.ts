/*
 *  Les tables d'une affaire telles que `GET /tickets/referentiels` les sert
 *  (`routers/tickets/referentiels`) — les ÉTATS seuls, que le site y lit : celui
 *  qui clôt une affaire propose la fusion de ses liées (#2511). Recopiés de
 *  `referentiels_pour` le 05/11/2026 ; catégories, colonnes et natures vides.
 */
import type { ReferentielsAffaires, StatutServi } from '../src/lib/api/referentiels-affaires';
import { reponseApercu as apercuLecture } from './apercus-lecture';
import { reponseNom } from './noms-servis';

//  Le compte simulé reçoit le `est_moderateur` que le serveur lui sert (#2633).
export { compteServi } from './comptes-servis';

const etat = (
	code: string,
	libelle: string,
	colonne_kanban: string | null,
	clos = false,
	proposable = true,
): StatutServi => ({ code, libelle, clos, colonne_kanban, proposable });

export const REFERENTIELS_TEMOINS: ReferentielsAffaires = {
	categories: [],
	statuts: [
		etat('ouvert', 'Ouvert', 'cs'),
		etat('en_ag', 'À l’AG', 'ag'),
		etat('en_cours', 'Chez le syndic', 'syndic'),
		etat('chez_prestataire', 'Chez le prestataire', 'fournisseur'),
		etat('résolu', 'Résolu', 'termine', true),
		etat('annulé', 'Annulé', 'annule', true),
		etat('fermé', 'Fermé', null, false, false),
		etat('publie', 'Publiée', null, false, false),
	],
	colonnes_kanban: [],
	natures: [],
};

//  Les aperçus d'une saisie — la pastille de lecture et le nom d'une personne : les
//  réponses du SERVEUR, rangées à part (`apercus-lecture.ts`, `noms-servis.ts`,
//  #2633) — réunies ici, que `simulerApi` lit déjà.
export function reponseApercu(chemin: string, requete: { postDataJSON(): unknown }): unknown {
	return apercuLecture(chemin, requete) ?? reponseNom(chemin, requete);
}
