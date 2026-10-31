/**
 * À quel titre agit-on dans l'administration — la PORTÉE, écrite une fois.
 *
 * Trois niveaux (spec `multi-coproprietes.md` §4.7) :
 *   • l'**administrateur** gère UNE copropriété — ses comptes, ses réglages ;
 *   • l'**opérateur** supervise l'INSTANCE — santé, tâches, base, inscription —,
 *     sans lire les données des résidents ;
 *   • l'**exploitant** tient le serveur et sa configuration : ce n'est pas un
 *     compte, et sur une instance COMMUNE c'est lui qui désigne l'opérateur
 *     (`api/app/auth/operateur.py`, clé publique `operateur_par_exploitant`).
 *
 * Un compte qui cumule Admin et Opérateur passait d'un onglet sur sa résidence à
 * un onglet sur toute l'instance sans que rien ne le dise (31/10/2026) :
 * `PorteeOnglet` le dit, `LegendeRoles` explique les deux rôles.
 */
import { PAGES } from '#lib/pages.ts';

/** La clé que `GET /config` calcule : l'opérateur est-il désigné par l'exploitant ? */
export const CLE_OPERATEUR_PAR_EXPLOITANT = 'operateur_par_exploitant';

/** Ce qu'on dit d'un réglage que l'exploitant tient dans la configuration du serveur. */
export const REGLE_PAR_L_EXPLOITANT = 'Réglé par l’exploitant du serveur, dans sa configuration.';

export type Portee = 'operateur' | 'administrateur';

/**
 * La portée d'un onglet d'administration pour ce compte, ou `null` quand elle
 * va sans dire — un administrateur qui n'est pas opérateur n'a qu'un titre.
 */
export function porteeOnglet(
	ongletId: string,
	droits: { administrateur: boolean; operateur: boolean },
): Portee | null {
	const def = PAGES.find((p) => p.id === 'admin')?.onglets?.find((o) => o.id === ongletId);
	if (!def || !droits.operateur) return null;
	//  Un onglet partagé (Maintenance) se lit, pour l'opérateur, comme une
	//  supervision de l'instance — pas comme un réglage de sa copropriété.
	if (def.reserve === 'operateur' || def.ouvertOperateur) return 'operateur';
	return droits.administrateur ? 'administrateur' : null;
}

/** Ce que chaque portée dit, le nom de la copropriété servie en paramètre. */
export function phrasePortee(portee: Portee, nomCopropriete: string): string {
	//  Le nom entre guillemets : « de Les Tilleuls » ne se dit pas, et un nom de
	//  résidence commence souvent par un article.
	const copropriete = `la copropriété « ${nomCopropriete} »`;
	return portee === 'operateur'
		? `Vous agissez comme opérateur de l’instance : ce que vous réglez ici vaut pour toute l’installation, pas seulement pour ${copropriete}.`
		: `Vous agissez comme administrateur de ${copropriete} : ce que vous réglez ici ne vaut que pour elle.`;
}
