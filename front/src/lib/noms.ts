/**
 * Comment on CLASSE des personnes — `comparerParNom`, pendant de
 * `utils/noms.cle_de_classement` côté serveur.
 *
 * ## Le nom AFFICHÉ n'est plus ici (#2633)
 *
 * « Prénom NOM » (le prénom garde sa casse, le nom passe en capitales — arbitré à
 * l'écran le 31/08/2026) est SERVI par l'API avec la personne : `nom_affiche`
 * (`utils/noms.nom_affiche`, mêlé aux schémas par `schemas_nom_servi.NomServi`),
 * `locataire_nom_affiche`, `bailleur_nom_affiche`, `nom_aide_affiche`. Le site et
 * l'app iOS LISENT le même champ ; une personne en cours de SAISIE est nommée par
 * le serveur aussi (`#lib/apercu-nom`, `POST /noms/affiche`).
 *
 * 🔒 `npm run lint:noms` refuse qu'un écran recompose « Prénom NOM », et
 * `npm run lint:regles-partagees` qu'une fonction du front le recalcule.
 */

/** Ce dont on a besoin pour CLASSER quelqu'un — et rien de plus. */
export interface Nommable {
	prenom?: string | null;
	nom?: string | null;
}

/**
 * **Comment on CLASSE des personnes** — par le nom de famille, puis le prénom.
 *
 * ## 🔴 Pourquoi ici (15/09/2026)
 *
 * Signalé à l'écran :
 *
 * > « Le classement des badges & télécommandes par Nom doit se faire sur le nom
 * >   et pas le prénom. »
 *
 * La table triait sur `porteur_nom`, qui vaut « **Alain** FAURE » : la chaîne
 * commence par le prénom, donc le classement aussi. Et `FormulaireTicket`
 * comparait littéralement `` `${prenom} ${nom}` ``.
 *
 * ⚠️ **La règle juste existait déjà, écrite trois fois** — `admin`, `annuaire`,
 * `espace-cs`, plus `utils/annuaire.py` côté serveur. C'est la règle la plus
 * déployée ; ces deux écrans-là ne la suivaient pas. Elle est donc reprise ici
 * telle quelle, et c'est elle qui s'applique partout.
 *
 * ## Les trois décisions qu'elle porte
 *
 * 1. **Le nom d'abord** — c'est ainsi qu'on cherche quelqu'un dans une liste ;
 * 2. **le prénom en départage** — deux FAURE se rangent entre eux, sinon leur
 *    ordre dépendrait de l'ordre d'arrivée en base, donc de rien ;
 * 3. **`'fr'` et `sensitivity: 'base'`** — « Ébert » se range après « Dupont » et
 *    non en fin de liste, et « MOREL » vaut « Morel ». La casse ne doit pas
 *    classer : le nom AFFICHÉ (`nom_affiche`) est justement en capitales.
 *
 * ⚠️ Un nom absent se range **à la fin** plutôt qu'au début : une ligne
 * incomplète n'a pas à ouvrir la liste.
 */
export function comparerParNom(
	a: Nommable | null | undefined,
	b: Nommable | null | undefined,
): number {
	const nomA = (a?.nom ?? '').trim();
	const nomB = (b?.nom ?? '').trim();
	//  Sans nom → à la fin, dans les deux sens de tri : c'est le seul rang où une
	//  ligne incomplète ne prétend pas être la première.
	if (!nomA !== !nomB) return nomA ? -1 : 1;
	const parNom = nomA.localeCompare(nomB, 'fr', { sensitivity: 'base' });
	if (parNom !== 0) return parNom;
	return (a?.prenom ?? '').localeCompare(b?.prenom ?? '', 'fr', { sensitivity: 'base' });
}
