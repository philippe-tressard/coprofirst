/**
 * **Une table d'états se déclare une fois** — ses colonnes s'en déduisent.
 *
 * ## 🔴 Pourquoi ce module (15/09/2026)
 *
 * Un relevé a comparé, dans chaque fichier, les `Record<string, string>` dont
 * les clés se recouvrent. Résultat : **dix fichiers** énuméraient le même
 * ensemble d'états deux ou trois fois de suite — un libellé ici, une classe de
 * pastille là, parfois une aide contextuelle en troisième.
 *
 * Ce n'est pas la même ligne recopiée : c'est le même **ensemble de clés**.
 * Ajouter un état demande alors de le poser dans chaque table, et **rien ne
 * signale l'oubli** : la table incomplète rend `undefined`, donc une pastille
 * sans couleur, ou un badge vide. Les deux passent la compilation, les tests et
 * la relecture.
 *
 * ⚠️ Au moment de l'écrire, **aucune divergence n'existait** : les dix fichiers
 * étaient d'accord avec eux-mêmes. C'est précisément l'état dans lequel se
 * trouvaient les quatre copies des statuts de ticket avant #415 — « chacune
 * était cohérente avec elle-même ; c'est ce qui les rendait invisibles à la
 * relecture » (`#lib/tickets`). On ne factorise pas ici un bug, on retire
 * l'endroit où il naît.
 *
 * ## La règle déployée, généralisée — pas une invention
 *
 * `#lib/tickets` fait déjà exactement cela depuis le 17/08/2026 : une liste de
 * `{ value, label, emoji, badge }`, et les tables plates **dérivées** par
 * `Object.fromEntries`. `#lib/idees` l'applique à moitié — ses libellés sont
 * dérivés, sa table de pastilles est écrite à la main sur les quatre mêmes
 * états. C'est cette règle-là qu'on étend, pas une nouvelle.
 *
 * ## Ce que le typage garantit
 *
 * Les attributs sont **inférés de l'ensemble des entrées**. Un état auquel il
 * manque une colonne ne compile pas : `svelte-check` le refuse en CI, avant la
 * relecture et avant la production. C'est la différence entre une convention et
 * un garde-fou — la première tient tant qu'on y pense.
 *
 * ⚠️ Les colonnes rendues sont en revanche des `Record<string, string>`, et non
 * des tables à clés étroites : un écran interroge la table avec le statut
 * **reçu de l'API**, donc une chaîne quelconque. Fermer l'index ici obligerait
 * chaque appelant à affirmer un type qu'il ne connaît pas — c'est le contrat
 * d'ENTRÉE qui porte la garantie, pas celui de sortie.
 *
 * ```ts
 * export const { libelle: STATUT_LABELS, badge: STATUT_BADGE } = parAttribut({
 *     publie:   { libelle: 'Publié',  badge: 'badge-blue' },
 *     en_cours: { libelle: 'En cours', badge: 'badge-orange' },
 * });
 * ```
 */

/**
 * Bascule une table « un état → ses attributs » en « un attribut → sa table ».
 *
 * Les noms d'export ne changent pas au passage : les écrans continuent de lire
 * `STATUT_LABELS[statut]`. Ce qui change est l'endroit où l'ensemble des états
 * s'écrit — une fois.
 */
export function parAttribut<Etat extends string, Attribut extends string>(
	etats: Record<Etat, Record<Attribut, string>>,
): Record<Attribut, Record<string, string>> {
	const colonnes: Record<string, Record<string, string>> = {};
	for (const [etat, attributs] of Object.entries(etats)) {
		for (const [nom, valeur] of Object.entries(attributs as Record<string, string>)) {
			(colonnes[nom] ??= {})[etat] = valeur;
		}
	}
	return colonnes as Record<Attribut, Record<string, string>>;
}

/**
 * La même bascule, depuis une **liste ordonnée** plutôt qu'une table.
 *
 * L'ordre du cycle de vie est lui-même une donnée — c'est celui des boutons et
 * des listes déroulantes. `#lib/tickets` et `#lib/idees` déclarent donc leurs
 * états en liste ; cette fonction leur rend les mêmes colonnes sans qu'ils
 * réécrivent `Object.fromEntries` une fois par attribut.
 *
 * @param cle Le champ qui porte l'identifiant de l'état (`value` partout).
 */
export function parAttributDepuisListe<T extends object, C extends keyof T & string>(
	etats: readonly T[],
	cle: C,
): Record<Exclude<keyof T, C> & string, Record<string, string>> {
	//  ⚠️ `T extends object` et non `Record<string, string>` : une liste déclarée
	//  par une INTERFACE (`TypeEvenement`) n'a pas de signature d'index, et se
	//  voyait refusée là où le même objet écrit en littéral passait. Contraindre
	//  la forme aurait poussé à retirer l'interface — donc à perdre le typage
	//  pour satisfaire l'outil qui devait le servir.
	const colonnes: Record<string, Record<string, string>> = {};
	for (const etat of etats) {
		const brut = etat as Record<string, unknown>;
		const identifiant = String(brut[cle]);
		for (const [nom, valeur] of Object.entries(brut)) {
			if (nom === cle) continue;
			(colonnes[nom] ??= {})[identifiant] = String(valeur);
		}
	}
	return colonnes as Record<Exclude<keyof T, C> & string, Record<string, string>>;
}
