<!--
  UNE question posée au règlement de copropriété, et l'avis du juriste.

  La carte suit le modèle commun (`ux-patterns` §3) : repliée, toute la carte
  ouvre ; dépliée, seul le titre referme. Repliée, on lit la question, le
  verdict et l'aperçu de la réponse ; dépliée, la réponse entière, les extraits
  et les réserves.

  ## 🔴 Un extrait se lit avec ce que le CODE en a vérifié

  Le serveur recherche chaque citation dans le texte chargé (`verifie`), et en
  déduit la page et l'acte. Un extrait retrouvé montre ce repère ; un extrait
  NON retrouvé le dit en clair, avec la référence que le modèle a donnée — un
  avis dont une citation est fausse a l'air vérifiable, et c'est le pire cas.

  La publication dans la FAQ s'ouvre DANS la carte (créneau `formulaire`) : le
  geste est sur la question, la boîte aussi (`ux-patterns` §14 ter).
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import CarteListe from '$lib/components/CarteListe.svelte';
	import ApercuCarte from '$lib/components/ApercuCarte.svelte';
	import AuteurCarte from '$lib/components/AuteurCarte.svelte';
	import BoutonLien from '$lib/components/BoutonLien.svelte';
	import EnteteCarte from '$lib/components/EnteteCarte.svelte';
	import IconeAction from '$lib/components/IconeAction.svelte';
	import type { QuestionReglement } from '$lib/api';
	import { fmtDatetime } from '$lib/date';
	import { safeHtml } from '$lib/sanitize';
	import { isAdmin } from '$lib/stores/auth';

	export let q: QuestionReglement;
	/** La carte est-elle dépliée ? L'état vit dans l'onglet : une seule ouverte. */
	export let ouvert = false;
	/** La boîte « Publier dans la FAQ » est-elle ouverte sur cette carte ? */
	export let publication = false;

	const dispatch = createEventDispatcher<{ basculer: void; publier: void; supprimer: void }>();

	$: verifies = q.extraits.filter((e) => e.verifie).length;
</script>

<!--  La GOUTTIÈRE de la page Affaires, standard du site (10/10/2026) : la date
      de la question, et RIEN dessous. Une question n'a pas de rubrique ; son
      verdict est un ÉTAT — teinté, il se lit en capsule sur la dernière ligne,
      comme l'état d'une affaire. Le ranger dans la colonne qui CLASSE en ferait
      une nature, et la gouttière prendrait sa teinte au lieu de celle de la
      charte. L'heure, que la gouttière n'écrit pas, passe au pied de l'avis
      (« Posée le … »). -->
<CarteListe
	id="question-reglement-{q.id}"
	quand={q.cree_le}
	expanded={ouvert || publication}
	onDeplier={() => dispatch('basculer')}
>
	<EnteteCarte titre={q.question} basculable on:toggle={() => dispatch('basculer')}>
		<svelte:fragment slot="actions">
			<BoutonLien ancre="question-reglement-{q.id}" quoi="la question" />
			{#if !q.faq_item_id}
				<button
					class="btn-icon-edit"
					aria-label="Publier dans la FAQ"
					title="Publier dans la FAQ"
					aria-pressed={publication}
					on:click|stopPropagation={() => dispatch('publier')}
					><IconeAction icone="book-open-check" /></button
				>
			{/if}
			{#if $isAdmin}
				<button
					class="btn-icon-danger"
					aria-label="Supprimer la question"
					title="Supprimer la question et sa réponse"
					on:click|stopPropagation={() => dispatch('supprimer')}
					><IconeAction icone="trash-2" /></button
				>
			{/if}
		</svelte:fragment>
		<svelte:fragment slot="apercu">
			{#if !ouvert && !publication}
				<ApercuCarte contenu={q.reponse} />
			{/if}
		</svelte:fragment>
		<svelte:fragment slot="tags">
			<!--  La teinte d'un verdict ne s'écrit qu'ici, en `class:` : une classe
			      interpolée rendrait le fichier aveugle à `lint:css-orphelin`. -->
			<span
				class="badge"
				class:badge-green={q.verdict === 'oui'}
				class:badge-red={q.verdict === 'non'}
				class:badge-orange={q.verdict === 'sous_conditions'}
				class:badge-gray={q.verdict === 'non_prevu'}
				class:badge-yellow={q.verdict === 'incertain'}>{q.verdict_libelle}</span
			>
			{#if q.extraits.length}
				<span class:alerte={verifies < q.extraits.length}
					>{verifies}/{q.extraits.length} extrait{q.extraits.length > 1 ? 's' : ''} vérifié{verifies >
					1
						? 's'
						: ''}</span
				>
			{/if}
			{#if !q.texte_en_vigueur}
				<span class="alerte">Texte remplacé depuis</span>
			{/if}
			{#if q.faq_item_id}
				<span>📚 Dans la FAQ</span>
			{/if}
			<AuteurCarte nom={q.auteur_nom} />
		</svelte:fragment>
	</EnteteCarte>

	{#if publication}
		<!--  Le formulaire ne referme pas la carte qu'on publie. -->
		<div
			class="carte-corps corps"
			role="presentation"
			on:click|stopPropagation
			on:keydown|stopPropagation
		>
			<slot name="formulaire" />
		</div>
	{:else if ouvert}
		<!--  Le corps ne referme pas la carte : on lit, on sélectionne, on copie. -->
		<div class="carte-corps corps lecture" role="presentation" on:click|stopPropagation>
			<div class="rich-content">{@html safeHtml(q.reponse)}</div>

			{#if q.extraits.length}
				<h4 class="intertitre">Extraits du règlement</h4>
				<ul class="extraits">
					{#each q.extraits as e, i (i)}
						<li>
							<blockquote>{e.citation}</blockquote>
							{#if e.verifie}
								<p class="repere">
									✓ {[e.acte, e.page].filter(Boolean).join(' — ') || e.reference}
								</p>
							{:else}
								<p class="repere alerte">
									⚠️ Non retrouvé mot pour mot dans le texte — à vérifier{e.reference
										? ` (référence donnée : ${e.reference})`
										: ''}
								</p>
							{/if}
							{#if e.apport}<p class="aide">{e.apport}</p>{/if}
						</li>
					{/each}
				</ul>
			{/if}

			{#if q.reserves}
				<h4 class="intertitre">Réserves</h4>
				<div class="rich-content">{@html safeHtml(q.reserves)}</div>
			{/if}

			<p class="aide">
				Posée le {fmtDatetime(q.cree_le)}. Avis indicatif, qui ne se substitue pas aux actes
				authentiques.
				{#if q.modele}Rédigé par {q.modele}{#if q.texte_charge_le}, d'après le texte chargé le {fmtDatetime(
							q.texte_charge_le,
						)}{/if}.{/if}
				{#if q.cout_usd}Coût : {q.cout_usd} $.{/if}
			</p>
		</div>
	{/if}
</CarteListe>

<style>
	/*  Le retrait de l'en-tête (`EnteteCarte`, 0,7 rem) : le corps s'aligne sur le titre. */
	.corps {
		padding: 0 0.7rem 0.75rem;
	}
	.lecture {
		font-size: var(--fs-base);
		line-height: 1.55;
	}
	.intertitre {
		margin: 1rem 0 0.4rem;
		font-size: var(--fs-sm);
		text-transform: uppercase;
		letter-spacing: 0.03em;
		color: var(--color-text-muted);
	}
	.extraits {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.7rem;
	}
	blockquote {
		margin: 0;
		padding: 0.4rem 0.7rem;
		border-left: 3px solid var(--color-primary);
		background: var(--color-bg);
		font-style: italic;
	}
	.repere {
		margin: 0.25rem 0 0;
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
	}
	.alerte {
		color: var(--color-warning-texte);
	}
</style>
