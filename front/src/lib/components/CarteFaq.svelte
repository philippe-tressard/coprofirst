<!--
  CarteFaq.svelte — UNE question de la FAQ, avec sa réponse dépliable.

  ## Pourquoi ce fichier existe (05/09/2026)

  Le contrôle de modularité a refusé que `faq/+page.svelte` grossisse de cinq
  lignes : il faisait déjà 772 lignes. Les trois réponses possibles sont écrites
  dans `ux-patterns` — découper, remonter la règle d'un cran, ou raboter — et
  seule la dernière est mauvaise. Ici, l'ajout (l'icône de lien) est propre à la
  carte : c'est donc la carte qu'on sort.

  Le balisage part **avec ses règles CSS**, sans exception : Svelte scope les
  styles au composant, et une règle laissée dans la page n'habillerait plus rien
  (leçon de `Pastille.svelte`, v2.67.11, et de `CarteActualite` avant elle).

  ⚠️ La rangée d'actions n'est plus conditionnée au droit d'édition : elle porte
  désormais l'icône de lien, que **tout le monde** doit voir. Seuls les trois
  gestes d'édition restent réservés.
  ## Le modèle commun des cartes (26/09/2026, #1329)

  Elle était la seule carte dépliable du site hors de `.carte-liste` et
  d'`EnteteCarte` : conteneur `role="button"` (le geste symétrique abandonné le
  18/08 — la carte dépliée se refermait au moindre clic dans la réponse),
  chevron AVANT les actions, survol qui repeignait le fond au lieu du titre.
  Et la correction s'ouvrait en bas de page, loin de la question : elle s'ouvre
  désormais DANS la carte (créneau `formulaire`), comme partout ailleurs.

  ## Au standard de la page Affaires (10/10/2026)

  Actions au trait (`IconeAction`). PAS de gouttière : une question n'affiche
  aucune date, et sa catégorie est un texte libre, sans pictogramme — elle est
  déjà l'intertitre du groupe. Ce que l'objet n'a pas ne s'invente pas.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import CarteListe from '#lib/components/CarteListe.svelte';
	import BoutonLien from '#lib/components/BoutonLien.svelte';
	import EnteteCarte from '#lib/components/EnteteCarte.svelte';
	import IconeAction from '#lib/components/IconeAction.svelte';
	import { safeHtml } from '#lib/sanitize.ts';

	/** La question, telle que l'API la rend. */
	export let item: { id: number; question: string; reponse: string; actif: boolean };
	/** La réponse est-elle dépliée ? L'état vit dans la page : une seule ouverte. */
	export let ouvert = false;
	/** L'utilisateur peut-il modifier, masquer et supprimer ? */
	export let canEdit = false;
	/**  Cette question mène-t-elle à la demande d'accès ? La reconnaissance vit dans
	 *   la page, qui sait ce qu'est « la question du prix d'un badge ». */
	export let avecCta = false;
	/** La question est-elle en cours de correction ? Le formulaire vient du créneau. */
	export let enEdition = false;

	const dispatch = createEventDispatcher<{
		basculer: void;
		modifier: void;
		basculerActif: void;
		supprimer: void;
	}>();
</script>

<!--  Repliée, toute la carte ouvre ; dépliée, seul le titre referme (`ux-patterns` §3). -->
<!--  Une question RETIRÉE (`actif` faux) a l'allure de toute carte archivée
      (`CarteListe archive`) : elle était à 0,55 et ne revenait jamais à
      l'opacité pleine, même dépliée pour être corrigée (10/10/2026). -->
<CarteListe
	id="faq-{item.id}"
	expanded={ouvert || enEdition}
	archive={!item.actif}
	onDeplier={() => dispatch('basculer')}
>
	<EnteteCarte titre={item.question} basculable on:toggle={() => dispatch('basculer')}>
		<svelte:fragment slot="actions">
			<BoutonLien ancre="faq-{item.id}" quoi="la question" />
			{#if canEdit}
				<button
					class="btn-icon-edit"
					aria-label="Modifier"
					title="Modifier"
					aria-pressed={enEdition}
					on:click|stopPropagation={() => dispatch('modifier')}
					><IconeAction icone="pencil" /></button
				>
				<button
					class={item.actif ? 'btn-icon-warn' : 'btn-icon-edit'}
					aria-label={item.actif ? 'Masquer' : 'Afficher'}
					title={item.actif ? 'Masquer' : 'Afficher'}
					on:click|stopPropagation={() => dispatch('basculerActif')}
					><IconeAction icone={item.actif ? 'eye-off' : 'eye'} /></button
				>
				<button
					class="btn-icon-danger"
					aria-label="Supprimer"
					title="Supprimer"
					on:click|stopPropagation={() => dispatch('supprimer')}
					><IconeAction icone="trash-2" /></button
				>
			{/if}
		</svelte:fragment>
	</EnteteCarte>
	{#if enEdition}
		<!--  Le formulaire ne referme pas la carte qu'on corrige. -->
		<div
			class="carte-corps"
			role="presentation"
			on:click|stopPropagation
			on:keydown|stopPropagation
		>
			<slot name="formulaire" />
		</div>
	{:else if ouvert}
		<!--  Le corps ne referme pas la carte : on lit, on sélectionne, on copie. -->
		<div class="carte-corps faq-a rich-content" role="presentation" on:click|stopPropagation>
			{@html safeHtml(item.reponse)}
			{#if avecCta}
				<!--  🔴 L'ancre `#nouvelle-demande` a disparu avec la refonte (#928) : la
				      section « Faire une demande » est devenue un BOUTON en tête de page.
				      Un lien vers une ancre qui n'existe plus ne lève rien — il dépose
				      simplement le lecteur en haut de l'écran, sans qu'il sache
				      pourquoi. -->
				<div class="faq-cta-row">
					<a class="btn btn-primary btn-sm" href="/mon-lot/badges"
						>Faire une nouvelle demande d'accès</a
					>
					<a class="btn btn-outline btn-sm" href="/mon-lot/badges">Voir mes accès</a>
				</div>
			{/if}
		</div>
	{/if}
</CarteListe>

<style>
	.faq-a {
		font-size: var(--fs-base);
		color: var(--color-text-muted);
		line-height: 1.55;
	}
	.faq-cta-row {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
		margin-top: 0.8rem;
		padding-top: 0.75rem;
		border-top: 1px dashed var(--color-border);
	}
</style>
