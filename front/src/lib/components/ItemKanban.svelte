<script lang="ts">
	/**
	 * Une **brique de kanban** — la même au tableau de bord et sur `/calendrier/kanban`.
	 *
	 * ## Pourquoi ce composant (13/09/2026), et ce qu'il est devenu (19/09/2026)
	 *
	 * Il est né d'une duplication : dix-sept lignes écrites DEUX fois dans
	 * `tableau-de-bord/+page.svelte`, une fois pour les colonnes larges, une fois
	 * pour la vue étroite qui n'en montre qu'une à la fois.
	 *
	 * 🔴 Mais il rendait sa PROPRE brique — titre, puis une ligne icône +
	 * périmètre — là où `/calendrier/kanban` en rendait une autre : pastilles de
	 * périmètre en haut, titre en gras, type en pied. **Deux dessins pour un même
	 * objet**, sur deux écrans qui montrent les mêmes dossiers. Demandé à
	 * l'écran : *« utilise le même UX des briques que Calendrier/kanban »*.
	 *
	 * Ce fichier rend donc la brique du calendrier, avec ses classes `.kanban-*`
	 * — qui sont **globales** (`styles/composants.css`) et n'ont rien à recopier.
	 * Le rendu suit la règle la plus déployée ; c'est le tableau de bord qui
	 * rejoint le calendrier, et non l'inverse.
	 *
	 * ⚠️ Ce qui reste propre au tableau de bord : la brique y est un LIEN (elle
	 * ouvre le dossier dans le calendrier) et ne porte ni glisser-déposer, ni
	 * dépliage en place, ni boutons d'action. Une brique condensée est une brique
	 * sans gestes, pas une autre brique.
	 */
	import { goto } from '$app/navigation';
	import { categorieTicketLabel, lienTicket } from '#lib/tickets.ts';
	import { perimetreTags } from '#lib/perimetres-pastilles.ts';
	import { perimetresStore } from '#lib/stores/perimetres.ts';
	import { relire } from '#lib/utils.ts';

	/** L'affaire rendue (un événement jusqu'au 23/09/2026, #1092) — on n'en lit
	 *  que l'identifiant, la catégorie, le titre et le périmètre. */
	export let item: {
		id: number;
		categorie: string;
		titre: string;
		perimetre_cible?: string[] | null;
	};

	$: lien = lienTicket(item.id);

	//  ⚠️ `$perimetresStore` n'est pas lu : il dit à Svelte que ce calcul dépend de
	//  l'arbre, que `perimetreTags` lit dans un état de MODULE. Sans lui, un
	//  tableau de bord affiché avant l'arrivée de l'arbre gardait le code brut, et
	//  rien ne revenait le corriger (#947) — le calendrier a exactement la même
	//  ligne, pour la même raison.
	$: pastilles = relire($perimetresStore, () => perimetreTags);
</script>

<div
	class="kanban-card card"
	role="button"
	tabindex="0"
	on:click={() => goto(lien)}
	on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && goto(lien)}
>
	<div class="kanban-card-tags">
		{#each pastilles((item.perimetre_cible ?? []).join(',')) as tag (tag.code)}
			<span class="kb-tag" style="background:{tag.color}">{tag.label}</span>
		{/each}
	</div>
	<strong class="kanban-card-titre">{item.titre}</strong>
	<div class="kanban-card-footer">
		<span class="kanban-card-type">{categorieTicketLabel(item.categorie)}</span>
	</div>
</div>
