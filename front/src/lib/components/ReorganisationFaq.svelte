<!--
  Le mode « Réorganiser » de la FAQ : l'ordre des questions dans chaque
  catégorie, au glisser-déposer ou aux flèches ↑↓, enregistré d'un geste.

  Extrait de `routes/(app)/faq/+page.svelte` le 28/09/2026 (#779, modularité) :
  il travaille sur une COPIE des questions et ne rend la liste à la page qu'une
  fois l'ordre enregistré — `fermer` porte alors les questions réordonnées, ou
  `null` si rien n'a changé ou si l'on annule.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { faq as faqApi, type EntreeFaq } from '#lib/api/index.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import { messageErreur } from '#lib/erreurs.ts';
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';
	import IconeAction from '#lib/components/IconeAction.svelte';
	import { grouperParCategorie, normalizeCategorieLabel } from '#lib/faq.ts';

	export let items: EntreeFaq[];

	const dispatch = createEventDispatcher<{ fermer: EntreeFaq[] | null }>();

	let copie: EntreeFaq[] = items.map((i) => ({ ...i }));
	let dragItem: EntreeFaq | null = null;
	let dragOverItem: EntreeFaq | null = null;
	let dragCategory: string | null = null;
	let enregistrement = false;

	$: groupes = grouperParCategorie(copie);

	function finGlisser() {
		dragItem = null;
		dragOverItem = null;
		dragCategory = null;
	}

	//  Le seul endroit où une catégorie reçoit son nouvel ordre : le glisser et
	//  les flèches le recopiaient chacun (#779).
	//
	//  ⚠️ Les questions reprennent les places de LEUR catégorie dans la liste.
	//  Les deux copies la reconstruisaient en `[...autres, ...catégorie]` : le
	//  regroupement suivant l'ordre d'apparition, déplacer une question envoyait
	//  toute sa catégorie en bas de l'écran (trouvé par `faq-reorganiser.spec`).
	function remplacerCategorie(category: string, ordonnes: EntreeFaq[]) {
		ordonnes.forEach((it, idx) => {
			it.ordre = idx;
		});
		let k = 0;
		copie = copie.map((i) =>
			normalizeCategorieLabel(i.categorie) === category ? ordonnes[k++] : i,
		);
	}

	function handleDragStart(item: EntreeFaq, category: string) {
		dragItem = item;
		dragCategory = category;
	}

	function handleDragOver(e: DragEvent, item: EntreeFaq, category: string) {
		if (dragCategory !== category) return;
		e.preventDefault();
		dragOverItem = item;
	}

	function handleDrop(e: DragEvent, category: string) {
		e.preventDefault();
		if (!dragItem || !dragOverItem || dragCategory !== category) return;
		const catItems = groupes[category];
		if (!catItems) return;
		const depart = dragItem.id;
		const arrivee = dragOverItem.id;
		const fromIndex = catItems.findIndex((i) => i.id === depart);
		const toIndex = catItems.findIndex((i) => i.id === arrivee);
		if (fromIndex === -1 || toIndex === -1 || fromIndex === toIndex) return;
		const ordonnes = [...catItems];
		const [moved] = ordonnes.splice(fromIndex, 1);
		ordonnes.splice(toIndex, 0, moved);
		remplacerCategorie(category, ordonnes);
		finGlisser();
	}

	function moveItem(category: string, item: EntreeFaq, direction: -1 | 1) {
		const catItems = groupes[category];
		if (!catItems) return;
		const idx = catItems.findIndex((i) => i.id === item.id);
		const targetIdx = idx + direction;
		if (targetIdx < 0 || targetIdx >= catItems.length) return;
		const ordonnes = [...catItems];
		[ordonnes[idx], ordonnes[targetIdx]] = [ordonnes[targetIdx], ordonnes[idx]];
		remplacerCategorie(category, ordonnes);
	}

	async function enregistrer() {
		enregistrement = true;
		try {
			const changes = copie
				.filter((ri) => {
					const orig = items.find((i) => i.id === ri.id);
					return orig && orig.ordre !== ri.ordre;
				})
				.map((ri) => ({ id: ri.id, ordre: ri.ordre }));
			if (!changes.length) {
				dispatch('fermer', null);
				return;
			}
			await faqApi.reorder(changes);
			toast('success', 'Ordre mis à jour.');
			dispatch(
				'fermer',
				copie.map((i) => ({ ...i })),
			);
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			enregistrement = false;
		}
	}
</script>

<div class="reorder-bar">
	<span class="reorder-aide"
		>Glissez les questions pour les réorganiser, ou utilisez les flèches ↑↓</span
	>
	<PiedFormulaire
		enCours={enregistrement}
		soumission={false}
		on:annule={() => dispatch('fermer', null)}
		on:enregistre={enregistrer}
	/>
</div>
{#each Object.entries(groupes) as [categorie, catItems] (categorie)}
	<!--  Le titre de catégorie est celui de la page, qui le style : un slot plutôt
	      qu'une règle `.categorie-title` recopiée ici. -->
	<slot name="titre" {categorie} />
	{#each catItems as item, idx (item.id)}
		<div
			class="card reorder-item"
			class:drag-over={dragOverItem?.id === item.id}
			draggable="true"
			on:dragstart={() => handleDragStart(item, categorie)}
			on:dragover={(e) => handleDragOver(e, item, categorie)}
			on:drop={(e) => handleDrop(e, categorie)}
			on:dragend={finGlisser}
			role="listitem"
		>
			<div class="reorder-handle" title="Glisser pour réorganiser">⠿</div>
			<span class="reorder-question">{item.question}</span>
			<div class="reorder-arrows">
				<button
					class="btn-icon-edit"
					disabled={idx === 0}
					on:click={() => moveItem(categorie, item, -1)}
					title="Monter"
					aria-label="Monter"><IconeAction icone="arrow-up" /></button
				>
				<button
					class="btn-icon-edit"
					disabled={idx === catItems.length - 1}
					on:click={() => moveItem(categorie, item, 1)}
					title="Descendre"
					aria-label="Descendre"><IconeAction icone="arrow-down" /></button
				>
			</div>
		</div>
	{/each}
{/each}

<style>
	.reorder-bar {
		display: flex;
		justify-content: space-between;
		align-items: center;
		flex-wrap: wrap;
		gap: 0.5rem;
		padding: 0.75rem 1rem;
		margin-bottom: 0.5rem;
		background: var(--color-neutre-fond);
		border-radius: var(--radius);
		border: 1px dashed var(--color-border);
	}
	.reorder-aide {
		font-size: var(--fs-base);
		color: var(--color-text-muted);
	}
	/*  Le pied est posé DANS la barre, à droite de la consigne : la marge haute
	    qu'il porte sous un formulaire l'y décalerait vers le bas. Et il prend la
	    place restante, sans quoi la pleine largeur que `normes.css` donne à ses
	    boutons sous 480 px ne mesurerait que lui. */
	.reorder-bar :global(.form-actions) {
		flex: 1 1 auto;
		margin-top: 0;
	}
	.reorder-item {
		/*  L'espacement venait de `.faq-item`, partie avec la carte dans
		    `CarteFaq.svelte` : une ligne de réorganisation n'est pas une carte de
		    question, elle n'a que son interligne en commun. */
		margin-bottom: 0.35rem;
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 0.75rem;
		cursor: grab;
		user-select: none;
	}
	.reorder-item:active {
		cursor: grabbing;
	}
	.reorder-handle {
		font-size: var(--fs-picto-sm);
		color: var(--color-text-muted);
		cursor: grab;
		flex-shrink: 0;
	}
	.reorder-question {
		flex: 1;
		font-size: var(--fs-base);
	}
	.reorder-arrows {
		display: flex;
		gap: 0.15rem;
		flex-shrink: 0;
	}
	.drag-over {
		outline: 2px dashed var(--color-primary);
		outline-offset: -2px;
		background: var(--color-neutre-fond);
	}
</style>
