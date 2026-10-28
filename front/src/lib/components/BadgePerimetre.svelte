<script lang="ts">
	/**
	 * Le badge « 🔹 périmètre » d'une carte — **une seule écriture**.
	 *
	 * ## Ce qu'il remplace
	 *
	 * Neuf copies du même bloc, identiques à la classe du badge près : annonce,
	 * actualité, événement, ticket, idée, sondage, fiche de lecture, rangée de
	 * calendrier, document de résidence. Toutes disaient la même chose —
	 * *« affiche le périmètre, sauf quand c'est celui par défaut »* — et toutes
	 * ont hérité du même défaut, ci-dessous.
	 *
	 * 🔴 **Le défaut, signalé à l'écran le 13/09/2026 (#947)** : sur le kanban du
	 * calendrier, les pastilles affichaient `résidence`, `aful`,
	 * `cheminements/portillon` — les **codes bruts**. Pas toujours : parfois les
	 * libellés sortaient correctement, sur les mêmes cartes.
	 *
	 * `perimetreLabel()` et `estPerimetreParDefaut()` lisent `carte`, un objet de
	 * portée **module** que `definirPerimetres()` remplit quand la requête revient.
	 * Svelte ne surveille pas cet objet : il ne réévalue une expression que si
	 * l'une de ses dépendances **réactives** change. Un écran rendu avant l'arrivée
	 * de l'arbre gardait donc son repli — le code tel quel — et **plus rien ne
	 * venait le repeindre**.
	 *
	 * Le repli était conçu comme transitoire ; ce qui manquait, c'est ce qui
	 * revient le corriger.
	 *
	 * ## `relire()`, et pas une invention
	 *
	 * 🔴 La règle existait déjà, et son propre tableau nommait cette cause :
	 *
	 * > *« Sélecteur de périmètre | le périmètre par défaut | `perimetreParDefaut()`
	 * >   lit un état de module posé au chargement de l'arbre : avant lui, `null`,
	 * >   et pour toujours »* — `#lib/utils`, `relire()`, 29/08/2026 (#549).
	 *
	 * Elle avait été appliquée aux **deux sélecteurs** de périmètre, et à eux
	 * seuls. Les neuf badges lisaient le même état de module, dans le même piège,
	 * sans que rien ne les rattache à la règle. Une règle posée sur deux de ses
	 * occurrences n'est pas déployée, elle est commencée.
	 *
	 * ⚠️ `$perimetresStore` n'est pas lu par le calcul : il dit à Svelte de quoi
	 * ce calcul dépend. Le citer **est** le geste.
	 */
	import { estPerimetreParDefaut, perimetreLabel } from '#lib/perimetres/index.ts';
	import { perimetresStore } from '#lib/stores/perimetres.ts';
	import { relire } from '#lib/utils.ts';

	/** Les codes à rendre — la liste (`perimetre_cible`) ou la chaîne (`perimetre`). */
	export let perimetre: string | string[] | null | undefined = null;

	/**
	 * La couleur du badge, telle que la charte la nomme.
	 *
	 * ⚠️ Elle varie d'un écran à l'autre — `gray` sur les cartes, `blue` sur les
	 * sondages et le calendrier, `purple` sur les documents — et cette divergence
	 * est **antérieure** à ce composant : elle est reprise telle quelle plutôt
	 * qu'uniformisée en passant. Uniformiser les couleurs est une décision d'UX,
	 * pas un effet de bord de factorisation. Elle est désormais VISIBLE en un
	 * endroit, ce qui est le préalable pour la trancher.
	 */
	export let ton: 'gray' | 'blue' | 'purple' = 'gray';

	/**
	 * Dire la portée MÊME quand c'est celle par défaut — le carnet d'entretien :
	 * un contrat qui couvre toute la résidence apparaît sous « Bât. 3 », et sans
	 * sa portée il s'y lirait comme propre à ce bâtiment. Ce n'est pas un second
	 * badge : c'est le même, qui ne tait plus le défaut.
	 */
	export let toujours = false;

	//  Un seul calcul, une seule dépendance : le libellé, ou la chaîne vide quand
	//  il n'y a rien à dire — ni périmètre, ni autre chose que celui par défaut.
	$: texte = relire($perimetresStore, () =>
		perimetre && (toujours || !estPerimetreParDefaut(perimetre)) ? perimetreLabel(perimetre) : '',
	);
</script>

{#if texte}
	<!--  ⚠️ `class:` et non une classe INTERPOLÉE (`badge-{ton}`) : une seule
	      interpolation rend Svelte incapable de signaler les sélecteurs inutilisés
	      pour TOUT le fichier, et `lint:css-orphelin` y devient aveugle sans le
	      dire. Les trois valeurs sont connues, elles s'écrivent donc.
	      `badge-perimetre` est la prise stable par laquelle un écran positionne le
	      badge — en `:global()` borné, puisqu'il est rendu par CE composant. -->
	<span
		class="badge badge-perimetre"
		class:badge-gray={ton === 'gray'}
		class:badge-blue={ton === 'blue'}
		class:badge-purple={ton === 'purple'}>&#x1F539; {texte}</span
	>
{:else}
	<!--  Ce qu'un écran veut montrer À LA PLACE quand il n'y a pas de périmètre à
	      nommer. La plupart ne montrent rien — c'est le cas par défaut, un slot
	      vide. La liste des documents de la résidence, elle, affiche « Copropriété »
	      plutôt qu'un blanc : la règle d'affichage lui appartient, la décision
	      d'afficher ou non reste ici. -->
	<slot />
{/if}
