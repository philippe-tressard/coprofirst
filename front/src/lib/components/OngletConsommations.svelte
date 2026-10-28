<!--
  L'onglet **Consommations** de l'écran Prestataires : les compteurs de la
  résidence, leurs relevés, et la saisie d'un nouveau relevé.

  ## Pourquoi ce composant (11/09/2026)

  `prestataires/+page.svelte` était à 1 528 lignes, et le garde-fou de modularité
  (rang 1) a refusé les lignes qu'ajoutait le geste ✨ de synthèse d'un contrat.
  Trois réponses possibles : découper, remonter la règle d'un cran, **jamais
  raboter**. Celle-ci est un découpage franc — un onglet entier, son état et ses
  appels réseau, rien de partagé avec les contrats ni l'annuaire.

  C'est la dette n° 2 de l'issue #779, après l'administration.

  Même forme que les onglets d'administration : l'état vit ici, la page ne garde
  que le choix de l'onglet.

  🗂️ **Les relevés sont des cartes de liste** (10/10/2026, la page Affaires
  devenue le standard du site) : `.carte-liste` à gouttière — la date du relevé
  en tête de la colonne de gauche —, `EnteteCarte` pour le titre (l'index) et
  les actions, dessinées au trait. Une carte de relevé ne se déplie pas : elle
  montre tout — la note en aperçu, la photo dessous. Le compteur n'a pas de
  pictogramme : la gouttière ne porte que la date, et la rangée des réglages dit
  de quel compteur il s'agit.
-->
<script lang="ts">
	import { fmtNombre, nombreOuNull } from '#lib/utils.ts';
	import {
		prestataires as prestApi,
		type CompteurConfig,
		type Prestataire,
		type ReleveCompteur,
	} from '#lib/api/index.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { isCS } from '#lib/stores/auth.ts';
	import CarteListe from '#lib/components/CarteListe.svelte';
	import { toast } from '#lib/components/Toast.svelte';
	import { SUPPRESSION, confirmerPuis } from '#lib/confirmation.ts';
	import FichiersUpload from '#lib/components/FichiersUpload.svelte';
	import FormulaireCreation from '#lib/components/FormulaireCreation.svelte';
	import EtoileRequis from '#lib/components/EtoileRequis.svelte';
	import CategoriesCompteur from '#lib/components/CategoriesCompteur.svelte';
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';
	import EnteteCarte from '#lib/components/EnteteCarte.svelte';
	import IconeAction from '#lib/components/IconeAction.svelte';
	import IntertitreGroupe from '#lib/components/IntertitreGroupe.svelte';

	/** L'annuaire des prestataires — la page le charge déjà, on ne le recharge pas. */
	export let prestataires: Prestataire[] = [];

	// ── Consommations ─────────────────────────────────────────────
	let compteurConfigs: CompteurConfig[] = [];
	let typeCompteur = '';
	let releves: ReleveCompteur[] = [];
	let releveLoading = false;
	/**  🔴 L'action primaire d'un onglet est rendue par l'EN-TÊTE DE PAGE, pas par
	 *   l'onglet (`ux-patterns` R1 : le squelette porte titre et action primaire).
	 *   L'onglet, lui, possède l'ÉTAT du formulaire — c'est lui qui sait ce qu'on
	 *   saisit. Les deux se rejoignent par un `bind:`, comme `OngletSmtp` remonte
	 *   la signature des e-mails à sa page.
	 *
	 *   ⚠️ Ne pas déplacer le bouton ici : il serait alors au-dessus du contenu et
	 *   plus dans la barre, et les six autres écrans qui suivent R1 deviendraient
	 *   la minorité. */
	export let showReleveForm = false;
	/** Le libellé que le bouton de page affiche — il nomme le compteur choisi. */
	export let libelleBouton = 'Nouveau relevé';
	let editReleveId: number | null = null;
	let releveForm = { date_releve: new Date().toISOString().slice(0, 10), index: '', note: '' };
	let relevePhotoFichiers: File[] = [];
	//  ⚠️ `relevePhotoKey` a disparu (#370) : la clé de remontage n'existait que
	//  pour vider un `<input type="file">` nu, qu'aucune affectation ne remet à
	//  zéro. `FichiersUpload` se vide en vidant sa liste.
	$: relevePhotoFile = relevePhotoFichiers[0] ?? null;
	let releveSaving = false;

	$: currentCompteur = compteurConfigs.find((c) => c.type_compteur === typeCompteur) ?? null;
	$: libelleBouton = currentCompteur
		? `Nouveau relevé — ${currentCompteur.label}`
		: 'Nouveau relevé';

	$: relevesByYear = (() => {
		const map = new Map<number, ReleveCompteur[]>();
		for (const r of releves) {
			const yr = new Date(r.date_releve).getFullYear();
			if (!map.has(yr)) map.set(yr, []);
			map.get(yr)!.push(r);
		}
		return [...map.entries()].sort((a, b) => b[0] - a[0]);
	})();

	//  🔴 CAS ZÉRO : sans compteur, `compteurConfigs.length === 0` restait vraie
	//  après l'appel et l'onglet rappelait l'API sans fin (#549). Le drapeau dit
	//  « DEMANDÉ », pas « reçu » : posé avant, jamais relevé.
	let compteursDemandes = false;

	async function loadCompteurConfigs() {
		compteursDemandes = true;
		try {
			compteurConfigs = await prestApi.compteurConfigs();
			if (compteurConfigs.length > 0 && !typeCompteur)
				typeCompteur = compteurConfigs[0].type_compteur;
		} catch {
			toast('error', 'Erreur chargement compteurs');
		}
	}

	async function loadReleves() {
		if (!typeCompteur) return;
		releveLoading = true;
		try {
			releves = await prestApi.releves(typeCompteur);
		} catch {
			toast('error', 'Erreur chargement relevés');
		} finally {
			releveLoading = false;
		}
	}

	//  L'onglet s'amorce SEUL : il n'est monté que lorsqu'on l'ouvre, la
	//  condition sur le nom de l'onglet n'a donc plus lieu d'être. C'est un des
	//  gains de l'extraction — la page n'a plus à dire à l'onglet qu'il est
	//  visible.
	import { onMount } from 'svelte';
	import EtatListe from '#lib/components/EtatListe.svelte';
	onMount(() => {
		if (!compteursDemandes) loadCompteurConfigs();
	});
	$: if (typeCompteur) loadReleves();

	function resetReleveForm() {
		releveForm = { date_releve: new Date().toISOString().slice(0, 10), index: '', note: '' };
		relevePhotoFichiers = [];
		editReleveId = null;
		showReleveForm = false;
	}

	function startEditReleve(r: ReleveCompteur) {
		releveForm = {
			date_releve: r.date_releve,
			index: r.index != null ? String(r.index) : '',
			note: r.note ?? '',
		};
		relevePhotoFichiers = [];
		editReleveId = r.id;
		showReleveForm = true;
	}

	async function saveReleve() {
		if (!releveForm.date_releve) return;
		releveSaving = true;
		try {
			const payload = {
				type_compteur: typeCompteur,
				date_releve: releveForm.date_releve,
				index: nombreOuNull(releveForm.index),
				note: releveForm.note.trim() || null,
				prestataire_id: currentCompteur?.prestataire_id ?? null,
			};
			let saved: ReleveCompteur;
			if (editReleveId) {
				saved = await prestApi.updateReleve(editReleveId, payload);
				releves = releves.map((r) => (r.id === editReleveId ? saved : r));
			} else {
				saved = await prestApi.createReleve(payload);
				releves = [saved, ...releves];
			}
			if (relevePhotoFile) {
				try {
					const updated = await prestApi.uploadRelevePhoto(saved.id, relevePhotoFile);
					releves = releves.map((r) => (r.id === saved.id ? updated : r));
				} catch {
					toast('error', 'Photo non enregistrée');
				}
			}
			toast('success', editReleveId ? 'Relevé modifié' : 'Relevé ajouté');
			resetReleveForm();
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			releveSaving = false;
		}
	}

	async function deleteReleve(id: number) {
		await confirmerPuis(SUPPRESSION('Ce relevé'), 'Relevé supprimé', async () => {
			await prestApi.deleteReleve(id);
			releves = releves.filter((r) => r.id !== id);
		});
	}

	/**  Le titre d'une carte de relevé : ce qu'on est venu lire, l'index. Sa date
	 *   est dans la gouttière ; un relevé sans index (une note seule) le dit. */
	function titreReleve(r: ReleveCompteur): string {
		return r.index != null ? `Index ${fmtNombre(r.index)}` : 'Relevé sans index';
	}
</script>

<!--  Les catégories de compteur et leur fournisseur — `CategoriesCompteur`,
      sorti le 26/09/2026 (#1329) quand ses deux petits formulaires ont reçu le
      pied commun : le fichier passait 500 lignes. -->
<CategoriesCompteur
	bind:compteurConfigs
	bind:typeCompteur
	{prestataires}
	compte={releveLoading ? null : releves.length}
/>

{#if showReleveForm && $isCS}
	<FormulaireCreation
		cle={editReleveId}
		titre={editReleveId
			? 'Modifier le relevé'
			: currentCompteur
				? `Nouveau relevé — ${currentCompteur.label}`
				: 'Nouveau relevé'}
	>
		<form on:submit|preventDefault={saveReleve}>
			<div>
				<div class="form-grid">
					<label class="field"
						><span>Date du relevé<EtoileRequis vide={!releveForm.date_releve} /></span><input
							type="date"
							bind:value={releveForm.date_releve}
							required
						/></label
					>
					<label class="field"
						>Index (m³)<input
							type="number"
							min="0"
							bind:value={releveForm.index}
							placeholder="Ex. 47047"
						/></label
					>
				</div>
				<div class="field champ-suivant">
					<label for="releve-note">Note</label>
					<input
						id="releve-note"
						type="text"
						bind:value={releveForm.note}
						placeholder="Ex. Changement compteur"
						class="note-releve"
					/>
				</div>
				<div class="field champ-suivant">
					<span class="libelle-groupe">Photo du relevé</span>
					<!--  Différé : la photo part par `prestApi.uploadRelevePhoto`,
						      une fois le relevé créé. -->
					<FichiersUpload
						id="releve-photo"
						mode="photos"
						differe
						max={1}
						label="Choisir une photo"
						bind:fichiers={relevePhotoFichiers}
					/>
				</div>
			</div>
			<PiedFormulaire enCours={releveSaving} on:annule={resetReleveForm} />
		</form>
	</FormulaireCreation>
{/if}

{#if releveLoading}
	<EtatListe chargement />
{:else if releves.length === 0}
	<div class="empty-state card">
		<h3>Aucun relevé</h3>
		<p>Ajoutez le premier relevé via le bouton ci-dessus.</p>
	</div>
{:else}
	{#each relevesByYear as [year, yearReleves] (year)}
		<IntertitreGroupe libelle={String(year)} />
		{#each yearReleves as r (r.id)}
			<CarteListe id="releve-{r.id}" quand={r.date_releve}>
				<EnteteCarte titre={titreReleve(r)}>
					<svelte:fragment slot="actions">
						{#if $isCS}
							<button
								class="btn-icon-edit"
								aria-label="Modifier"
								title="Modifier"
								on:click={() => startEditReleve(r)}><IconeAction icone="pencil" /></button
							>
							<button
								class="btn-icon-danger"
								aria-label="Supprimer"
								title="Supprimer"
								on:click={() => deleteReleve(r.id)}><IconeAction icone="trash-2" /></button
							>
						{/if}
					</svelte:fragment>
					<svelte:fragment slot="apercu">
						{#if r.note}<p class="releve-note">{r.note}</p>{/if}
					</svelte:fragment>
				</EnteteCarte>
				{#if r.photo_url}
					<!--  La photo est le CORPS de la carte, toujours montré : une carte de
					      relevé ne se déplie pas. -->
					<div class="carte-corps releve-corps">
						<a href={r.photo_url} target="_blank" rel="noopener">
							<img src={r.photo_url} alt="Relevé de compteur" class="releve-photo-thumb" />
						</a>
					</div>
				{/if}
			</CarteListe>
		{/each}
	{/each}
{/if}

<style>
	/*  La carte de relevé : `.carte-liste` à gouttière (`normes.css`) porte le
	    conteneur, la colonne et l'espacement — seules restent ici la note et la
	    photo. `.releve-row`, `.releve-main`, `.releve-date`, `.releve-index`,
	    `.releve-actions` et `.releve-year` sont parties avec la rangée écrite à
	    la main (10/10/2026). */
	.releve-note {
		margin: 0;
		font-size: var(--fs-md);
		color: var(--color-text-muted);
		font-style: italic;
	}
	.releve-corps {
		padding: 0 1rem 0.85rem;
	}
	.releve-photo-thumb {
		width: 56px;
		height: 56px;
		object-fit: cover;
		border-radius: var(--radius);
		border: 1px solid var(--color-border);
		margin-top: 0.2rem;
		display: block;
	}
	.champ-suivant {
		margin-top: 0.6rem;
	}
	.note-releve {
		width: 100%;
	}
</style>
