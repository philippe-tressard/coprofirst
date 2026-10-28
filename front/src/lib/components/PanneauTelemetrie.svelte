<script lang="ts">
	/**
	 * **Un panneau de l'onglet Télémétrie** — sa carte, son intitulé, sa période,
	 * son pied de notes. Écrit une fois (03/10/2026, #1628 #1632).
	 *
	 * 🔴 L'intitulé d'un panneau était écrit DEUX fois au caractère près —
	 * `.tl-section-title` dans `OngletTelemetrie`, `.titre-panneau` dans `TopPages`
	 * (#495 : un style scopé ne passe pas dans un composant enfant, d'où la copie).
	 * Les panneaux « Qui vient » et « Durées d'affichage » en auraient fait une
	 * troisième et une quatrième : ils passent tous par ici, et les deux copies
	 * sont parties.
	 *
	 * ## Deux niveaux (03/10/2026, demandé : « met les sections en pliable »)
	 *
	 * - `niveau="section"` (défaut) : une SECTION pliable de l'onglet — un
	 *   `<details>`, un seul déplié à la fois (l'accordéon natif du layout,
	 *   `#lib/accordeon.unSeulDetailsOuvert`, qui ramène aussi le haut du bloc
	 *   ouvert à l'écran). L'onglet tient l'état (`ouvert`) et reçoit `basculer`,
	 *   comme `OngletIA` avec ses blocs d'usage : il le garde quand la portée change.
	 *   Une section VIDE ne se déplie pas : son intitulé reste, suivi du libellé
	 *   de vide, et le chevron s'efface — ouvrir un bloc sans rien dedans se
	 *   lit « c'est cassé ».
	 * - `niveau="bloc"` : un BLOC dans une section (le graphe, les top pages, les
	 *   utilisateurs actifs de « Fréquentation ») : même intitulé, sans carte ni
	 *   pliage.
	 *
	 * Le contenu (tableaux, notes) est écrit par l'appelant ; les paragraphes du
	 * pied sont stylés ICI. Une cellule chiffrée prend `.nombre` et un texte
	 * discret `.text-muted-sm`, tous deux partagés (`src/styles/`) : un style
	 * posé ici pour les cellules de l'appelant ne le suivrait pas (#562).
	 */
	import { createEventDispatcher } from 'svelte';

	/** Avec son pictogramme : « ⚠️ Erreurs vues par les résidents ». */
	export let titre: string;
	/** Ce que couvrent les chiffres (« aujourd’hui », « 30 derniers jours »). */
	export let periode = '';
	export let niveau: 'section' | 'bloc' = 'section';
	/** Section : dépliée ? Décidé par l'onglet, qui tient l'accordéon. */
	export let ouvert = false;
	/** Section : rien à montrer — elle ne se déplie pas, et dit `videLibelle`. */
	export let vide = false;
	export let videLibelle = 'aucune donnée sur la période';

	const dispatch = createEventDispatcher<{ basculer: boolean }>();
</script>

{#if niveau === 'bloc'}
	<div class="bloc">
		<h4 class="titre">
			{titre}
			{#if periode}<span class="periode">{periode}</span>{/if}
		</h4>
		<slot />
		{#if $$slots.pied}
			<div class="pied"><slot name="pied" /></div>
		{/if}
	</div>
{:else if vide}
	<!--  Le même intitulé que le `<summary>`, sans chevron : un `<h3>` prendrait
	      la police de titre du site, et la section vide aurait l'air d'une autre chose. -->
	<div class="card panneau panneau-vide" aria-disabled="true">
		<div class="titre" role="heading" aria-level="3">
			{titre}
			<span class="periode">{periode ? `${periode} — ` : ''}{videLibelle}</span>
		</div>
	</div>
{:else}
	<details
		class="card panneau"
		open={ouvert}
		on:toggle={(e) => dispatch('basculer', e.currentTarget.open)}
	>
		<summary class="titre">
			{titre}
			{#if periode}<span class="periode">{periode}</span>{/if}
		</summary>
		<slot />
		{#if $$slots.pied}
			<div class="pied"><slot name="pied" /></div>
		{/if}
	</details>
{/if}

<style>
	.panneau {
		margin-top: 1rem;
	}
	.titre {
		font-size: var(--fs-lg);
		font-weight: 600;
		margin: 0 0 0.75rem;
		padding: 0.75rem 1rem 0;
	}
	summary.titre {
		cursor: pointer;
		list-style: none;
		display: flex;
		align-items: baseline;
		gap: 0.4rem;
		flex-wrap: wrap;
		padding-bottom: 0.75rem;
		margin-bottom: 0;
		user-select: none;
	}
	summary.titre::-webkit-details-marker {
		display: none;
	}
	/*  Le chevron, à droite : la seule marque de pliage, et il tourne. */
	summary.titre::after {
		content: '▾';
		margin-left: auto;
		color: var(--color-text-muted);
		transition: transform var(--duree-apparition) var(--ease-out);
	}
	details[open] > summary.titre::after {
		transform: rotate(180deg);
	}
	details[open] > summary.titre {
		border-bottom: 1px solid var(--color-border);
		margin-bottom: 0.75rem;
	}
	.panneau-vide .titre {
		padding-bottom: 0.75rem;
		margin-bottom: 0;
		color: var(--color-text-muted);
	}
	.bloc {
		margin-top: 0.5rem;
	}
	.bloc .titre {
		font-size: var(--fs-md);
		padding-top: 0.25rem;
	}
	.periode {
		font-size: var(--fs-sm);
		font-weight: 400;
		color: var(--color-text-muted);
		margin-left: 0.4rem;
	}
	.pied :global(p) {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
		line-height: 1.5;
		margin: 0.5rem 1rem 0.75rem;
	}
</style>
