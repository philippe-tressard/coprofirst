/**
 * Les services de la copropriété — le type de `GET /config/services` (#1718).
 *
 * À part d'`administration.ts`, qui porte le client `config.services()` mais
 * atteignait le plafond de 500 lignes : comme `UsageIA` dans `assistant.ts`,
 * le type du domaine vit dans son module.
 */

/**  Un service de la copropriété (`GET /config/services`, #1718) — décrit par le
 *   registre `utils/services`, seule liste. `cle_actif` est `null` pour une
 *   infrastructure (l'envoi des courriels), qui ne se coupe pas. */
export interface ServiceCopropriete {
	code: string;
	libelle: string;
	description: string;
	/**  Ce qu'on perd quand il est coupé. */
	perte: string;
	plafond: string;
	/**  L'onglet d'administration de ses réglages détaillés. */
	onglet: string;
	/**  L'onglet ne règle que ce service : coupé, il se grise dans la rangée. */
	onglet_dedie: boolean;
	/**  Son tracé, du catalogue `#lib/icones-svg.json` (vérifié côté serveur). */
	icone: string;
	coupable: boolean;
	cle_actif: string | null;
	etat: 'actif' | 'coupe' | 'incomplet';
	/**  Les réglages qui lui manquent pour fonctionner, nommés. */
	manque: string[];
	/**  La référence l'autorise-t-elle ici ? Toujours vrai hors d'une réplique (#1880). */
	autorise: boolean;
	/**  Pourquoi il ne s'allume pas, quand la référence ne l'autorise pas. */
	refus: string;
}
