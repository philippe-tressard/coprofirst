<script lang="ts">
	/**
	 * Le badge « 🔹 périmètre » d'une carte — **une seule écriture**.
	 *
	 * Neuf copies du même bloc l'avaient précédé ; il les a remplacées, puis il a
	 * cessé de COMPOSER le lieu (#2633, 11/11/2026) : le libellé est SERVI avec
	 * chaque contenu (`perimetre_libelle`, `api/app/utils/perimetres/servi.py`), que
	 * l'app iOS lit aussi. Il valait `""` pour le périmètre par défaut, que le badge
	 * tait. Les écueils d'avant — l'arbre arrivé après la carte, `relire()` (#947) —
	 * ne se posent plus : il n'y a plus rien à recalculer ici.
	 */

	/** Le libellé SERVI (`perimetre_libelle`) — `""` : le badge se tait. */
	export let libelle: string | null | undefined = undefined;

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

	$: texte = libelle ?? '';
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
