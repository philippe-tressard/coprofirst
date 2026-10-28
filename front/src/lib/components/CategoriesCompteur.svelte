<!--
  Les CATÉGORIES de compteur (onglet Consommations) : la rangée qui choisit la
  catégorie affichée, son fournisseur, l'ajout et la suppression d'une catégorie.

  Sorti d'`OngletConsommations` le 26/09/2026 (#1329) : ses deux petits
  formulaires — fournisseur, nouvelle catégorie — avaient leurs boutons écrits à
  la main, « Ajouter » avant « Annuler » et « … » pendant l'enregistrement. Ils
  passent par `PiedFormulaire`, et le fichier hôte dépassait alors 500 lignes.
  Le composant porte son état et ses gestes ; la page ne lui confie que la liste
  et la catégorie choisie, liées.

  🗂️ **Les réglages de la page Affaires** (10/10/2026, devenue le standard du
  site) : la rangée de boutons qui choisit le compteur FILTRE les relevés — elle
  passe par `ChoixPastilles` dans `ReglagesListe`, son libellé devant, dans la
  colonne de la gouttière des cartes de relevé, et sa pastille retenue dit
  combien de relevés la liste montre (`compte`, `ux-patterns` §5). Pas d'entrée
  « Tous » : les relevés d'un compteur ne se mêlent pas à ceux d'un autre. Le
  fournisseur et « + Catégorie » viennent dessous, dans la colonne des champs.
-->
<script lang="ts">
	import { nombreOuNull } from '#lib/utils.ts';
	import {
		prestataires as prestApi,
		type CompteurConfig,
		type Prestataire,
	} from '#lib/api/index.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { slug } from '#lib/texte.ts';
	import { isCS } from '#lib/stores/auth.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import { SUPPRESSION, confirmerPuis } from '#lib/confirmation.ts';
	import EtoileRequis from '#lib/components/EtoileRequis.svelte';
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';
	import ChoixPastilles from '#lib/components/ChoixPastilles.svelte';
	import ReglagesListe from '#lib/components/ReglagesListe.svelte';
	import IconeAction from '#lib/components/IconeAction.svelte';

	/** Les catégories de compteur, liées : la page les charge et les lit. */
	export let compteurConfigs: CompteurConfig[] = [];
	/** La catégorie affichée, liée. */
	export let typeCompteur = '';
	/** L'annuaire des prestataires, déjà chargé par la page. */
	export let prestataires: Prestataire[] = [];
	/** Combien de relevés la liste montre — porté par la pastille retenue. */
	export let compte: number | null = null;

	$: optionsCompteurs = compteurConfigs.map((c) => ({ val: c.type_compteur, label: c.label }));

	let editCompteurId: number | null = null;
	let editCompteurPrestId = '';
	let showAddCompteur = false;
	let newCompteurLabel = '';
	let addCompteurSaving = false;

	$: currentCompteur = compteurConfigs.find((c) => c.type_compteur === typeCompteur) ?? null;

	function startEditCompteur(cfg: CompteurConfig) {
		editCompteurId = cfg.id;
		editCompteurPrestId = cfg.prestataire_id ? String(cfg.prestataire_id) : '';
	}

	async function saveCompteurPrestataire(cfg: CompteurConfig) {
		try {
			const updated = await prestApi.updateCompteurConfig(cfg.id, {
				prestataire_id: nombreOuNull(editCompteurPrestId),
			});
			compteurConfigs = compteurConfigs.map((c) => (c.id === cfg.id ? updated : c));
			editCompteurId = null;
			toast('success', 'Fournisseur mis à jour');
		} catch (e) {
			toast('error', messageErreur(e));
		}
	}

	async function addCompteurConfig() {
		if (!newCompteurLabel.trim()) return;
		addCompteurSaving = true;
		const code = slug(newCompteurLabel, '_');
		try {
			const created = await prestApi.createCompteurConfig({
				type_compteur: code,
				label: newCompteurLabel.trim(),
				ordre: compteurConfigs.length,
			});
			compteurConfigs = [...compteurConfigs, created];
			newCompteurLabel = '';
			showAddCompteur = false;
			typeCompteur = created.type_compteur;
			toast('success', 'Catégorie ajoutée');
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			addCompteurSaving = false;
		}
	}

	async function deleteCompteurConfig(cfg: CompteurConfig) {
		await confirmerPuis(
			SUPPRESSION(`La catégorie « ${cfg.label} »`),
			'Catégorie supprimée',
			async () => {
				await prestApi.deleteCompteurConfig(cfg.id);
				compteurConfigs = compteurConfigs.filter((c) => c.id !== cfg.id);
				if (typeCompteur === cfg.type_compteur)
					typeCompteur = compteurConfigs[0]?.type_compteur ?? '';
			},
		);
	}
</script>

<ReglagesListe>
	{#if compteurConfigs.length}
		<ChoixPastilles
			options={optionsCompteurs}
			bind:valeur={typeCompteur}
			tous={false}
			{compte}
			libelle="Compteur"
			libelleDevant
		/>
	{/if}

	{#if $isCS}
		<!--  Le fournisseur du compteur choisi, et l'ajout d'une catégorie : dans la
		      colonne des champs, sous la rangée qu'ils complètent. -->
		<div class="compteur-config-row ligne-config">
			{#if currentCompteur && editCompteurId === currentCompteur.id}
				<!--  Un petit formulaire STANDARD (#1329) : champ libellé, pied commun.
				      Les boutons étaient écrits à la main, sur la même ligne. -->
				<form
					class="compteur-edition"
					on:submit|preventDefault={() =>
						currentCompteur && saveCompteurPrestataire(currentCompteur)}
				>
					<div class="compteur-config-row">
						<label class="field compteur-champ"
							>Fournisseur<select bind:value={editCompteurPrestId}>
								<option value="">— Aucun —</option>
								{#each prestataires as p (p.id)}<option value={String(p.id)}>{p.nom}</option>{/each}
							</select></label
						>
						{#if compteurConfigs.length > 1}
							<button
								type="button"
								class="btn-icon-danger"
								aria-label="Supprimer la catégorie"
								title="Supprimer la catégorie"
								on:click={() => currentCompteur && deleteCompteurConfig(currentCompteur)}
								><IconeAction icone="trash-2" /></button
							>
						{/if}
					</div>
					<PiedFormulaire petit on:annule={() => (editCompteurId = null)} />
				</form>
			{:else if currentCompteur}
				{@const prest = currentCompteur.prestataire_id
					? prestataires.find((p) => p.id === currentCompteur?.prestataire_id)
					: null}
				{#if prest}
					<span class="badge badge-blue prestataire-compteur">🔧 {prest.nom}</span>
				{:else}
					<span class="text-muted-sm">Aucun fournisseur</span>
				{/if}
				<button
					class="btn-icon-edit"
					aria-label="Modifier le fournisseur"
					title="Modifier le fournisseur"
					on:click={() => currentCompteur && startEditCompteur(currentCompteur)}
					><IconeAction icone="pencil" /></button
				>
			{/if}
			<button
				class="btn btn-sm btn-outline ajout-categorie"
				on:click={() => {
					showAddCompteur = !showAddCompteur;
					newCompteurLabel = '';
				}}
				title="Ajouter une catégorie">+ Catégorie</button
			>
		</div>

		{#if showAddCompteur}
			<!--  Même forme : « Ajouter » AVANT « Annuler » et « … » en cours, c'était
			      l'inverse de tous les formulaires du site (#1329). -->
			<form class="compteur-edition ligne-config" on:submit|preventDefault={addCompteurConfig}>
				<label class="field"
					><span>Nouvelle catégorie<EtoileRequis vide={!newCompteurLabel.trim()} /></span><input
						type="text"
						bind:value={newCompteurLabel}
						placeholder="Ex. EDF Parking privé"
					/></label
				>
				<PiedFormulaire
					petit
					enCours={addCompteurSaving}
					desactive={!newCompteurLabel.trim()}
					on:annule={() => (showAddCompteur = false)}
				/>
			</form>
		{/if}
	{/if}
</ReglagesListe>

<style>
	.compteur-config-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
		font-size: var(--fs-md);
	}
	.compteur-edition {
		flex: 1 1 100%;
		margin-top: 0.5rem;
	}
	.compteur-champ {
		flex: 1;
		margin: 0;
	}
	/*  Dans la colonne des CHAMPS de `ReglagesListe` : la dernière ligne de
	    grille explicite — la seconde au bureau, la seule sous 768 px. */
	.ligne-config {
		grid-column: -2 / -1;
	}
	/*  « + Catégorie » au bout de la ligne, après le fournisseur. */
	.ajout-categorie {
		margin-left: auto;
	}
	.prestataire-compteur {
		font-size: var(--fs-sm);
	}
</style>
