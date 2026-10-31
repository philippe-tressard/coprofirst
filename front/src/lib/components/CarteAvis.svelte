<!--
  La carte d'un AVIS sur l'application (#2075) — montée sur `CarteModifiable`,
  le squelette des cartes qui se corrigent en place.

  | Geste | Qui | Où |
  |---|---|---|
  | 🔗 copier le lien | tout le monde | en-tête |
  | ✏️ corriger | l'auteur | en-tête ; le formulaire prend la place du corps |
  | 📦 retirer | l'auteur, le gestionnaire du site | en-tête |
  | ↩️ ressortir, 🗑️ supprimer | ↩️ selon `restaurable` ; 🗑️ l'auteur et l'administrateur | en-tête, aux Archives |
  | répondre, retenir pour le site vitrine | le gestionnaire du site | corps déplié |

  ⚠️ Les droits viennent du SERVEUR (`est_auteur`, `restaurable`, et
  `gestionnaire` de la liste) : l'écran ne les recompose pas.
-->
<script lang="ts">
	import CarteModifiable from './CarteModifiable.svelte';
	import ApercuCarte from './ApercuCarte.svelte';
	import AuteurCarte from './AuteurCarte.svelte';
	import Badge from './Badge.svelte';
	import IconeAction from './IconeAction.svelte';
	import ChargementDiffere from './ChargementDiffere.svelte';
	import ReponseAvis from './ReponseAvis.svelte';
	import EncartAvertissement from './EncartAvertissement.svelte';
	import { AVIS } from '#lib/entites/avis.ts';
	import { VITRINE, auteurAvis, classeNote } from '#lib/avis.ts';
	import { safeDescription } from '#lib/sanitize.ts';
	import type { Avis } from '#lib/api/index.ts';
	import { SEPARATEUR } from '#lib/separateurs.ts';

	export let avis: Avis;
	/** Le lecteur gère le site — servi par `GET /avis` (`gestionnaire`). */
	export let gestionnaire = false;
	export let estAdmin = false;
	export let expanded = false;
	export let enEdition = false;

	export let onBasculer: () => void = () => {};
	export let onModifier: () => void = () => {};
	export let onAnnuler: () => void = () => {};
	export let onArchiver: (archivee: boolean) => void = () => {};
	export let onSupprimer: () => void = () => {};
	/** L'avis tel que le serveur l'a rendu après un geste (correction, réponse, retenue). */
	export let onMisAJour: (avis: Avis) => void = () => {};
	export let onRetenir: (validee: boolean) => void = () => {};
</script>

<CarteModifiable
	entite={AVIS}
	ancreId="avis-{avis.id}"
	quoi="l'avis"
	titre={avis.titre}
	quand={avis.cree_le}
	classe={classeNote(avis.note)}
	{expanded}
	{enEdition}
	peutModifier={avis.est_auteur}
	peutArchiver={avis.est_auteur || gestionnaire}
	peutRestaurer={avis.restaurable}
	archive={avis.archivee}
	titreRestaurer="Restaurer — l'avis redevient lisible de tous"
	{onBasculer}
	{onModifier}
	{onAnnuler}
	{onArchiver}
>
	<svelte:fragment slot="tags">
		{#if !avis.lu_de_tous}
			<!--  Sans l'accord de son auteur, l'avis ne se lit que de lui et du
			      conseil (arbitrage du 18/10/2026) : la carte le dit à ceux qui le voient. -->
			<span class="badge badge-gray">Auteur et conseil seulement</span>
		{/if}
		{#if avis.publication_validee}
			<Badge teinte="badge-green">Retenu pour {VITRINE}</Badge>
		{/if}
		<AuteurCarte nom={auteurAvis(avis)} />
	</svelte:fragment>

	<svelte:fragment slot="gestes-archive">
		{#if avis.est_auteur || estAdmin}
			<button
				class="btn-icon-danger"
				aria-label="Supprimer définitivement l'avis"
				title="Supprimer définitivement"
				on:click|stopPropagation={onSupprimer}><IconeAction icone="trash-2" /></button
			>
		{/if}
	</svelte:fragment>

	<svelte:fragment slot="apercu">
		{#if !expanded && !enEdition}
			<ApercuCarte contenu={avis.description} dansLigne />
		{/if}
	</svelte:fragment>

	<svelte:fragment slot="edition">
		<!--  Différé : il ne s'ouvre qu'au geste ✏️ (`svelte-patterns`). -->
		{#key avis.id}
			<ChargementDiffere charger={() => import('#lib/components/FormulaireAvis.svelte')}>
				{#snippet contenu(FormulaireAvis)}
					<FormulaireAvis
						{avis}
						cadre={false}
						on:modifie={(e) => onMisAJour(e.detail)}
						on:annule={onAnnuler}
					/>
				{/snippet}
			</ChargementDiffere>
		{/key}
	</svelte:fragment>

	<svelte:fragment slot="detail">
		<div class="avis-description">{@html safeDescription(avis.description)}</div>
		{#if avis.remarque}
			<!--  Ne sort qu'à l'auteur et au gestionnaire : le serveur la tait aux autres. -->
			<div class="avis-remarque">
				<EncartAvertissement compact role="note">
					<strong>Ce qui a manqué</strong>{SEPARATEUR.tiret}{avis.remarque}
				</EncartAvertissement>
			</div>
		{/if}
		<ReponseAvis {avis} {gestionnaire} {onMisAJour} />
		{#if gestionnaire && avis.publiable}
			<div class="avis-vitrine">
				<label class="case">
					<input
						type="checkbox"
						checked={avis.publication_validee}
						on:change={(e) => onRetenir(e.currentTarget.checked)}
					/>
					<span>Retenir cet avis pour {VITRINE}</span>
				</label>
				<p class="aide sous-case">
					Son auteur accepte qu'il paraisse sur le site. Retenu, il part dans le prochain export.
				</p>
			</div>
		{/if}
	</svelte:fragment>
</CarteModifiable>

<style>
	/*  La typographie de l'aperçu (`ApercuCarte`) : déplier ne change pas de voix. */
	.avis-description {
		color: var(--color-text);
		font-size: var(--fs-md);
		line-height: 1.5;
	}
	.avis-remarque {
		margin-top: 0.75rem;
	}
	.avis-vitrine {
		margin-top: 0.75rem;
	}
</style>
