<!--
  La CARTE d'un équipement (Admin › Copropriété › Équipements, #2442) — le
  squelette de `CarteModifiable`, comme le contrat et le prestataire : la
  gouttière dit son icône et son mot abrégé, ✏️ ouvre la fiche à la place du
  corps, 📦 le retire de la saisie, et aux Archives ↩️ le rend et 🗑️ le supprime.

  🔴 Un équipement SYSTÈME (assurance, syndic, autre) se corrige mais ne se
  retire pas : le code s'en sert (`utils/equipements.CODES_SYSTEME`), et c'est le
  SERVEUR qui le dit (`systeme`). La carte tait 📦 et porte un cadenas.

  🗑️ ne s'offre qu'aux Archives, et seulement quand rien ne le cite : le compteur
  d'usages est lu AVANT, la route refuserait de toute façon (409).
-->
<script lang="ts">
	import CarteModifiable from './CarteModifiable.svelte';
	import ChampsEquipement from './ChampsEquipement.svelte';
	import PiedFormulaire from './PiedFormulaire.svelte';
	import IconeAction from './IconeAction.svelte';
	import Icon from './Icon.svelte';
	import { EQUIPEMENT } from '#lib/entites/equipement.ts';
	import {
		classeEquipement,
		type Equipement,
		type FormulaireEquipement,
	} from '#lib/equipements.ts';
	import { perimetreLabel } from '#lib/perimetres/index.ts';
	import { perimetresStore } from '#lib/stores/perimetres.ts';
	import { relire, fmtNombre } from '#lib/utils.ts';
	import { SEPARATEUR } from '#lib/separateurs.ts';
	import type { UsagesEquipement } from '#lib/api/index.ts';

	export let equipement: Equipement;
	export let expanded = false;
	/** La fiche en cours de correction, liée — `null` quand ce n'est pas celle-ci. */
	export let enEdition = false;
	export let form: FormulaireEquipement;
	export let enregistrement = false;
	/** Ce qui le cite — lu par l'onglet quand la carte s'ouvre ; `null` : pas encore lu. */
	export let usages: UsagesEquipement | null = null;

	export let onBasculer: () => void = () => {};
	export let onModifier: () => void = () => {};
	export let onAnnuler: () => void = () => {};
	export let onEnregistrer: () => void = () => {};
	/** 📦 `true` le retire de la saisie, `false` l'y rend. */
	export let onArchiver: (retire: boolean) => void = () => {};
	export let onSupprimer: () => void = () => {};

	$: retire = !equipement.actif;
	$: classe = classeEquipement(equipement.code) ?? {
		icone: equipement.icone,
		libelle: equipement.libelle,
		abrege: equipement.code.toUpperCase(),
	};
	$: lieux = relire($perimetresStore, () =>
		equipement.perimetres.length ? perimetreLabel(equipement.perimetres) : '',
	);
	$: total = usages ? usages.contrats + usages.affaires + usages.prestataires : null;
</script>

<CarteModifiable
	entite={EQUIPEMENT}
	ancreId="equipement-{equipement.code}"
	quoi="l’équipement"
	titre={equipement.libelle}
	{classe}
	{expanded}
	{enEdition}
	peutModifier
	peutArchiver={!equipement.systeme}
	peutRestaurer
	archive={retire}
	titreRestaurer="Rendre à la saisie — l’équipement revient dans les sélecteurs"
	{onBasculer}
	{onModifier}
	{onAnnuler}
	{onArchiver}
>
	<svelte:fragment slot="tags">
		{#if equipement.systeme}
			<span class="badge badge-gray" title="Le code s’en sert : il ne se retire pas"
				><Icon name="lock" size={12} /> Système</span
			>
		{/if}
		{#if !equipement.pour_affaires}
			<span class="badge badge-gray">Contrats seulement</span>
		{/if}
		{#if lieux}<span class="badge badge-gray">{lieux}</span>{/if}
	</svelte:fragment>

	<svelte:fragment slot="gestes-archive">
		{#if total === 0}
			<button
				class="btn-icon-danger"
				aria-label="Supprimer l’équipement"
				title="Supprimer — plus rien ne le cite"
				on:click|stopPropagation={onSupprimer}><IconeAction icone="trash-2" /></button
			>
		{/if}
	</svelte:fragment>

	<svelte:fragment slot="edition">
		<form on:submit|preventDefault={onEnregistrer}>
			<ChampsEquipement bind:form etat="edition" code={equipement.code}>
				<p slot="usages" class="usages">
					<!--  La ligne est RÉSERVÉE pendant la lecture : la fiche ne saute pas
					      quand le compte arrive, et l'attente se dit. -->
					{#if !usages}
						Recherche de ce qui le cite…
					{:else}
						<strong>Utilisé par</strong>
						{fmtNombre(usages.contrats)} contrat(s){SEPARATEUR.point}{fmtNombre(usages.affaires)}
						affaire(s){SEPARATEUR.point}{fmtNombre(usages.prestataires)} prestataire(s)
					{/if}
				</p>
			</ChampsEquipement>
			<PiedFormulaire enCours={enregistrement} on:annule={onAnnuler} />
		</form>
	</svelte:fragment>

	<svelte:fragment slot="detail">
		{#if equipement.description}<p class="description">{equipement.description}</p>{/if}
		<p class="usages">
			Code <code>{equipement.code}</code>{#if usages}{SEPARATEUR.tiret}utilisé par
				{fmtNombre(usages.contrats)} contrat(s), {fmtNombre(usages.affaires)} affaire(s) et
				{fmtNombre(usages.prestataires)} prestataire(s).{/if}
		</p>
	</svelte:fragment>
</CarteModifiable>

<style>
	.usages,
	.description {
		margin: 0.3rem 0;
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
	}
	.description {
		color: var(--color-text);
		white-space: pre-line;
	}
</style>
