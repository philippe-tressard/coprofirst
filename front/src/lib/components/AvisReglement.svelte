<!--
  L'AVIS d'une question au règlement, en synthèse courte et sections pliées
  (08/11/2026, #2597).

  Demandé : *« la réponse est trop longue et confuse ; il est indispensable de
  justifier avec les § — une courte synthèse, et des sections pliables du RCP et
  d'une autre pour les AG »*. L'avis se lit donc de haut en bas, par profondeur :

  1. la SYNTHÈSE — verdict (dans la capsule de la carte) et trois ou quatre
     phrases, dont chaque affirmation porte son renvoi [R2], [AG1] ;
  2. « Ce qui fonde l'avis » — une ligne par renvoi, TOUJOURS visible : l'acte, la
     rubrique (chapitre, section ou résolution) et la page, déduits du texte par le
     code, jamais crus du modèle. Un clic ouvre la section et amène à l'extrait ;
  3. trois sections PLIÉES, une seule ouverte à la fois (`#lib/accordeon`) : le
     règlement, les assemblées générales, les réserves — le raisonnement en puces
     puis les extraits mot pour mot.

  Un avis d'avant (sans `renvoi`) ne passe pas par ici : la carte le rend comme
  avant. Le recueil n'a pas d'articles numérotés — le « § » est le chemin des
  titres, rien d'autre (`extraits.Index.rubrique_de`).
-->
<script lang="ts">
	import { tick } from 'svelte';
	import ExtraitsReglement from '#lib/components/ExtraitsReglement.svelte';
	import SectionRepliee from '#lib/components/SectionRepliee.svelte';
	import type { ExtraitReglement, QuestionReglement } from '#lib/api/index.ts';
	import { basculer } from '#lib/accordeon.ts';
	import { revelerCible } from '#lib/deepLink.ts';
	import { safeHtml } from '#lib/sanitize.ts';
	import { SEPARATEUR } from '#lib/separateurs.ts';

	export let q: QuestionReglement;

	type Section = 'reglement' | 'ag' | 'reserves';
	let ouverte: Section | null = null;

	$: extraitsReglement = q.extraits.filter((e) => e.source !== 'ag');
	$: extraitsAg = q.extraits.filter((e) => e.source === 'ag');
	//  Les AG d'abord ? Non : le règlement passe avant, comme dans le texte lu.
	$: fondements = [...extraitsReglement, ...extraitsAg];
	$: idExtrait = (e: ExtraitReglement) => `extrait-${q.id}-${e.renvoi}`;

	/** Où se trouve l'extrait : l'acte, la rubrique, la page — sinon la référence du modèle. */
	function lieu(e: ExtraitReglement): string {
		const trouve = [e.acte, e.rubrique, e.page].filter(Boolean).join(SEPARATEUR.tiret);
		return trouve || e.reference;
	}

	async function aller(e: ExtraitReglement) {
		ouverte = e.source === 'ag' ? 'ag' : 'reglement';
		await tick();
		revelerCible(idExtrait(e));
	}
</script>

<div class="rich-content">{@html safeHtml(q.reponse)}</div>

{#if fondements.length}
	<h4 class="intertitre">Ce qui fonde l'avis</h4>
	<ul class="fondements">
		{#each fondements as e (e.renvoi)}
			<li>
				<button type="button" class="fondement" on:click={() => aller(e)}>
					<span class="renvoi">{e.renvoi}</span>
					<span class="lieu">{lieu(e)}</span>
					{#if e.verifie}
						<span class="verifie" aria-label="Retrouvé dans le texte">✓</span>
					{:else}
						<span class="alerte">⚠️ Non retrouvé</span>
					{/if}
				</button>
			</li>
		{/each}
	</ul>
	{#if q.renvois_sans_extrait.length}
		<p class="aide alerte">
			Renvoi sans extrait{q.renvois_sans_extrait.length > 1 ? 's' : ''}{SEPARATEUR.tiret}à
			vérifier&nbsp;: {q.renvois_sans_extrait.join(', ')}.
		</p>
	{/if}
{/if}

{#if q.selon_reglement || extraitsReglement.length}
	<SectionRepliee
		enSerie
		titre="Le règlement de copropriété"
		compte={extraitsReglement.length}
		ouvert={ouverte === 'reglement'}
		surBascule={() => (ouverte = basculer(ouverte, 'reglement'))}
	>
		<div class="detail">
			{#if q.selon_reglement}
				<div class="rich-content">{@html safeHtml(q.selon_reglement)}</div>
			{/if}
			<ExtraitsReglement extraits={extraitsReglement} idPrefixe="extrait-{q.id}" />
		</div>
	</SectionRepliee>
{/if}

{#if q.selon_ag || extraitsAg.length}
	<SectionRepliee
		enSerie
		titre="Les assemblées générales"
		compte={extraitsAg.length}
		ouvert={ouverte === 'ag'}
		surBascule={() => (ouverte = basculer(ouverte, 'ag'))}
	>
		<div class="detail">
			{#if q.selon_ag}
				<div class="rich-content">{@html safeHtml(q.selon_ag)}</div>
			{/if}
			<ExtraitsReglement extraits={extraitsAg} idPrefixe="extrait-{q.id}" />
		</div>
	</SectionRepliee>
{/if}

{#if q.reserves}
	<SectionRepliee
		enSerie
		titre="Réserves"
		ouvert={ouverte === 'reserves'}
		surBascule={() => (ouverte = basculer(ouverte, 'reserves'))}
	>
		<div class="detail">
			<div class="rich-content">{@html safeHtml(q.reserves)}</div>
		</div>
	</SectionRepliee>
{/if}

<style>
	/*  Le contenu d'une section dépliée se détache de son bandeau. */
	.detail {
		padding: 0.7rem 0.25rem 0.25rem;
	}
	.fondements {
		list-style: none;
		margin: 0 0 0.4rem;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}
	/*  Une ligne = une cible : 44 px au doigt (`standards/11` §10). */
	.fondement {
		display: flex;
		align-items: baseline;
		gap: 0.6rem;
		width: 100%;
		min-height: 2rem;
		padding: 0.2rem 0.4rem;
		background: none;
		border: none;
		border-radius: var(--radius);
		color: var(--color-text);
		font: inherit;
		font-size: var(--fs-md);
		text-align: left;
		cursor: pointer;
	}
	@media (pointer: coarse) {
		.fondement {
			min-height: 2.75rem;
			align-items: center;
		}
	}
	@media (hover: hover) and (pointer: fine) {
		.fondement:hover {
			background: var(--color-bg);
		}
	}
	.renvoi {
		flex: none;
		min-width: 2.2rem;
		font-weight: 600;
		color: var(--color-primary);
	}
	.lieu {
		flex: 1;
		min-width: 0;
	}
	.verifie {
		flex: none;
		color: var(--color-success-texte);
	}
	.alerte {
		color: var(--color-warning-texte);
	}
</style>
