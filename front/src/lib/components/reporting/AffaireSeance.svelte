<!--
  OUVRIR UNE AFFAIRE EN SÉANCE, pendant un point CS / Syndic (#2084, demandé le
  19/10/2026 : « ajouter un point qui n'est pas une affaire non close, en fin
  des affaires, avec possibilité d'ouvrir une affaire en séance »).

  Sous le tableau, tant que le point est en cours : **Ouvrir une affaire en
  séance** déplie un formulaire court — titre, catégorie, description. L'affaire
  est créée, rejoint la liste du point et paraît en fin de tableau (la plus
  récente) ; son compte rendu se saisit comme les autres.

  Les catégories viennent du serveur (`categories_seance`) : celles du rapport,
  ni actualité ni bogue. Les points annexes, eux, ont leur affaire d'office
  (« Points annexes CS & Syndic »), créée à l'ouverture du point.
-->
<script lang="ts">
	import SectionDescription from '#lib/components/SectionDescription.svelte';
	import { TICKET } from '#lib/entites/ticket.ts';
	import { pliageDe } from '#lib/pliage.ts';
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';
	import EtoileRequis from '#lib/components/EtoileRequis.svelte';
	import IconeAction from '#lib/components/IconeAction.svelte';
	import { toast } from '#lib/components/Toast.svelte';
	import { messageErreur } from '#lib/erreurs.ts';
	import { pointsConseil, type CompteRenduPoint, type EtatValidation } from '#lib/api/index.ts';

	export let pointId: number;
	/** Les catégories proposées — la liste du serveur. */
	export let categories: EtatValidation[];
	/** L'affaire est ouverte : la vue reçoit le point à jour et relit le tableau. */
	export let onOuverte: (cr: CompteRenduPoint) => void;

	let ouvert = false;
	let titre = '';
	let categorie = '';
	let description = '';
	let enCours = false;

	function vider() {
		titre = '';
		categorie = '';
		description = '';
	}

	async function ouvrir() {
		if (!titre.trim() || !categorie) return;
		enCours = true;
		try {
			onOuverte(
				await pointsConseil.ouvrirAffaire(pointId, {
					titre: titre.trim(),
					categorie,
					description,
				}),
			);
			toast('success', 'Affaire ouverte en séance');
			vider();
			ouvert = false;
		} catch (e) {
			toast('error', messageErreur(e, 'Ouverture impossible'));
		} finally {
			enCours = false;
		}
	}
</script>

<div class="seance">
	{#if ouvert}
		<form class="formulaire" on:submit|preventDefault={ouvrir}>
			<div class="field">
				<label for="seance-titre-{pointId}"
					>Titre de l’affaire<EtoileRequis vide={!titre.trim()} /></label
				>
				<input id="seance-titre-{pointId}" type="text" maxlength="200" bind:value={titre} />
			</div>
			<div class="field">
				<label for="seance-categorie-{pointId}">Catégorie<EtoileRequis vide={!categorie} /></label>
				<select id="seance-categorie-{pointId}" bind:value={categorie}>
					<option value="" disabled>Choisir…</option>
					{#each categories as c (c.cle)}
						<option value={c.cle}>{c.libelle}</option>
					{/each}
				</select>
			</div>
			<SectionDescription
				pliable={pliageDe(TICKET, 'description')}
				idPrefixe="seance-{pointId}"
				hauteur="8rem"
				bind:valeur={description}
			/>
			<PiedFormulaire
				petit
				{enCours}
				desactive={!titre.trim() || !categorie}
				on:annule={() => {
					vider();
					ouvert = false;
				}}
			/>
		</form>
	{:else}
		<button type="button" class="btn btn-sm btn-outline" on:click={() => (ouvert = true)}>
			<IconeAction icone="plus" /> Ouvrir une affaire en séance
		</button>
	{/if}
</div>

<style>
	.seance {
		margin-top: 0.75rem;
	}
	.formulaire {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
</style>
