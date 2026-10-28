/**
 * Les onglets d'une page qu'un utilisateur ouvre — la règle écrite UNE fois.
 *
 * `BarreOnglets` l'applique pour afficher la rangée et rediriger une adresse
 * refusée ; l'administration la relit pour résoudre son onglet actif, sans quoi
 * un opérateur arrivé sur `/admin` monterait d'abord « À traiter », dont les
 * files lui répondent 403 (#2029).
 *
 * Deux raisons de fermer un onglet, déclarées dans `#lib/pages` :
 *   • `reserve` — l'onglet exige un rôle ;
 *   • `reserveeAdmin` sur la PAGE — un compte qui n'est pas administrateur n'y
 *     voit que les onglets `ouvertOperateur`.
 *
 * ⚠️ Masquer ne protège rien : le serveur tranche.
 */
import { PAGES, type OngletDef } from '#lib/pages.ts';

/** Ce que l'utilisateur courant est — lu des dérivées de `#lib/stores/auth`. */
export interface DroitsOnglet {
	administrateur: boolean;
	operateur: boolean;
	proprioOuCS: boolean;
	locataire: boolean;
	/** Syndic ou mandataire — il gère, il n'habite pas. */
	gestionnaire: boolean;
}

function reserveAdmise(o: OngletDef, d: DroitsOnglet): boolean {
	return (
		!o.reserve ||
		(o.reserve === 'proprioOuCS' && d.proprioOuCS) ||
		(o.reserve === 'nonLocataire' && !d.locataire) ||
		(o.reserve === 'operateur' && d.operateur) ||
		(o.reserve === 'nonGestionnaire' && !d.gestionnaire)
	);
}

export function ongletsOuverts(pageId: string, d: DroitsOnglet): OngletDef[] {
	const page = PAGES.find((p) => p.id === pageId);
	return (page?.onglets ?? []).filter(
		(o) =>
			reserveAdmise(o, d) &&
			(!page?.reserveeAdmin || d.administrateur || (d.operateur && !!o.ouvertOperateur)),
	);
}
