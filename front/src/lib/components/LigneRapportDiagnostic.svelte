<!--
  **Un rapport de diagnostic** dans sa carte de type : son titre, sa date, sa
  synthèse dépliable, ses actions — et ses annexes (migration 0278).

  ## Pourquoi il est sorti de `SectionDiagnostics` (11/10/2026)

  Les annexes des fiches de Ma résidence devaient s'afficher ici, et
  `SectionDiagnostics` était à 492 lignes : les y ajouter passait le plafond de
  modularité (rang 1). La ligne d'un rapport est la notion qui s'en détache
  proprement — un objet, ses gestes remontés par rappel, aucun état à elle.

  ⚠️ Les styles voyagent AVEC le balisage (`.diag-rapport-block`, la synthèse) :
  laissés derrière, Svelte les aurait scopés à un composant qui ne rend plus ces
  éléments, et la ligne serait sortie nue (#344, #356).

  L'accordéon reste à la section — un seul bloc déplié dans toute la section
  (`#lib/accordeon`) : la ligne dit seulement si SA synthèse est ouverte.
-->
<script lang="ts">
	import Icon from '#lib/components/Icon.svelte';
	import BoutonLien from '#lib/components/BoutonLien.svelte';
	import IconeAction from '#lib/components/IconeAction.svelte';
	import LienAction from '#lib/components/LienAction.svelte';
	import ListeDocuments from '#lib/components/ListeDocuments.svelte';
	import {
		diagnostics as diagnosticsApi,
		type Document,
		type RapportDiagnostic,
	} from '#lib/api/index.ts';
	import { safeHtml } from '#lib/sanitize.ts';
	import { fmtDateShort as fmt } from '#lib/date.ts';

	export let rapport: RapportDiagnostic;
	export let peutModifier = false;
	/** La synthèse de CE rapport est-elle le bloc déplié de la section ? */
	export let ouvert = false;
	/** Ses annexes — toujours visibles : une ligne de rapport ne se replie pas. */
	export let annexes: Document[] = [];
	export let onBasculer: () => void;
	export let onModifier: () => void;
	export let onSupprimer: () => void;
</script>

<div class="diag-rapport-block" id="diag-{rapport.id}">
	<div class="doc-row">
		<div class="doc-info">
			<Icon name="file-text" size={16} />
			<span class="doc-titre">{rapport.titre}</span>
			{#if rapport.date_rapport}
				<span class="doc-date">{fmt(rapport.date_rapport)}</span>
			{/if}
			{#if rapport.synthese}
				<!--  Un bouton TEXTE : le mot reste, l'ampoule passe au
				      trait (10/10/2026) et prend la couleur du mot. -->
				<button
					class="synthese-toggle"
					aria-label="Afficher la synthèse"
					aria-expanded={ouvert}
					on:click={onBasculer}
					><Icon name="lightbulb" size={14} /> Synthèse {ouvert ? '▲' : '▼'}</button
				>
			{/if}
		</div>
		<div class="doc-actions">
			<BoutonLien ancre="diag-{rapport.id}" quoi="le rapport" />
			<LienAction
				href={diagnosticsApi.downloadUrl(rapport.id)}
				icone="arrow-down"
				mot="Télécharger"
				titre="Télécharger"
				libelle="Télécharger le rapport"
				telecharger
			/>
			{#if peutModifier}
				<button class="btn-icon-edit" aria-label="Modifier" title="Modifier" on:click={onModifier}
					><IconeAction icone="pencil" /></button
				>
				<button
					class="btn-icon-danger"
					aria-label="Supprimer"
					title="Supprimer"
					on:click={onSupprimer}><IconeAction icone="trash-2" /></button
				>
			{/if}
		</div>
	</div>
	{#if annexes.length}
		<div class="annexes"><ListeDocuments documents={annexes} /></div>
	{/if}
	{#if rapport.synthese && ouvert}
		<!--  `safeHtml` — la synthèse est du HTML riche saisi par le
		      conseil (`CLAUDE.md`, règle XSS). -->
		<div class="synthese-body rich-content">
			{@html safeHtml(rapport.synthese)}
		</div>
	{/if}
</div>

<style>
	.diag-rapport-block {
		border-bottom: 1px solid var(--color-border);
	}
	.diag-rapport-block:last-child {
		border-bottom: none;
	}
	.annexes {
		padding: 0 0.5rem 0.5rem;
	}
	.synthese-toggle {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		background: none;
		border: none;
		cursor: pointer;
		font-size: var(--fs-sm);
		color: var(--color-primary);
		padding: 0.1rem 0.3rem;
		border-radius: var(--radius);
		white-space: nowrap;
		flex-shrink: 0;
	}
	@media (hover: hover) and (pointer: fine) {
		.synthese-toggle:hover {
			background: var(--color-bg);
		}
	}
	.synthese-body {
		padding: 0.5rem 1rem 0.75rem;
		font-size: var(--fs-base);
		background: var(--color-bg);
		border-left: 3px solid var(--color-primary);
		margin: 0 0.5rem 0.35rem;
		border-radius: 0 var(--radius) var(--radius) 0;
	}
</style>
