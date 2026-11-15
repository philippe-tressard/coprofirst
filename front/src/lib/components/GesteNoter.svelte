<!--
  Le geste « ⭐ Noter » d'un prestataire — un seul composant pour deux entrées
  (14/11/2026) : la carte d'un CONTRAT (le prestataire du contrat, rattaché à lui) et
  la FICHE d'un prestataire (une intervention hors contrat, sans rattachement).

  Il portait trois états et une API dans `OngletContrats` : le geste restait donc
  introuvable pour un prestataire sans contrat. Ici, il vit une fois ; l'appelant
  reçoit seulement la notation créée (`cree`) pour l'ajouter à sa liste.

  Réservé au conseil syndical et à l'administration, comme le serveur
  (`require_cs_or_admin`) : l'appelant le monte sous `peutModifier`.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { prestataires as prestApi, type AffaireANoter, type Notation } from '#lib/api/index.ts';
	import { essayer } from '#lib/chargement.ts';
	import { tenter } from '#lib/erreurs.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import type { Etat } from '#lib/notations.ts';
	import FormulaireNotation from './FormulaireNotation.svelte';
	import GesteEnPlace from './GesteEnPlace.svelte';

	/** Le prestataire noté. */
	export let prestataireId: number;
	/** Le contrat auquel la note se rattache — absent pour une intervention hors contrat. */
	export let contratId: number | undefined = undefined;

	const dispatch = createEventDispatcher<{ cree: Notation }>();

	let ouvert = false;
	let etat: Etat | null = null;
	let commentaire = '';
	let enCours = false;
	//  L'affaire jugée (15/11/2026) : on note le couple prestataire / affaire. Les affaires
	//  du prestataire se lisent à l'ouverture, pas avant ; « aucune » = un avis général.
	let affaires: AffaireANoter[] = [];
	let affaireId = '';

	async function ouvrir() {
		ouvert = true;
		etat = null;
		commentaire = '';
		affaireId = '';
		[affaires] = await essayer(prestApi.affaires(prestataireId), []);
	}

	async function enregistrer() {
		if (!etat) {
			toast('error', "Choisissez l'état : Mauvais, Neutre ou Excellent");
			return;
		}
		//  Un avis « Mauvais » se justifie : le serveur le refuse aussi, mais on le dit ici.
		if (etat === 'mauvais' && !commentaire.trim()) {
			toast('error', 'Un avis « Mauvais » doit être justifié par un commentaire');
			return;
		}
		//  Capturés AVANT le rappel : à l'intérieur, rien ne garantit qu'ils n'ont pas changé.
		const choisi = etat;
		enCours = true;
		await tenter(async () => {
			const n = await prestApi.createNotation({
				prestataire_id: prestataireId,
				etat: choisi,
				commentaire: commentaire.trim() || undefined,
				contrat_id: contratId,
				ticket_id: affaireId ? Number(affaireId) : undefined,
			});
			ouvert = false;
			dispatch('cree', n);
		}, 'Notation enregistrée');
		enCours = false;
	}
</script>

<div class="geste-noter">
	<button
		type="button"
		class="btn btn-sm btn-outline"
		aria-pressed={ouvert}
		on:click|stopPropagation={() => (ouvert ? (ouvert = false) : ouvrir())}>⭐ Noter</button
	>
	{#if ouvert}
		<div role="presentation" on:click|stopPropagation on:keydown|stopPropagation>
			<GesteEnPlace {enCours} onAnnuler={() => (ouvert = false)} onValider={enregistrer}>
				<label class="field" for="affaire-{prestataireId}-{contratId ?? 'sans-contrat'}">
					<span>Affaire concernée</span>
					<select id="affaire-{prestataireId}-{contratId ?? 'sans-contrat'}" bind:value={affaireId}>
						<option value="">Aucune — un avis général sur le prestataire</option>
						{#each affaires as a (a.id)}
							<option value={String(a.id)}>{a.titre}</option>
						{/each}
					</select>
				</label>
				<FormulaireNotation
					id="notation-{prestataireId}-{contratId ?? 'sans-contrat'}"
					bind:etat
					bind:commentaire
				/>
			</GesteEnPlace>
		</div>
	{/if}
</div>

<style>
	/*  Le bouton, puis le formulaire ouvert dessous : une colonne, que la carte soit
	    large ou étroite. */
	.geste-noter {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 0.5rem;
		margin-top: 0.5rem;
	}
	.geste-noter > :global(div) {
		align-self: stretch;
	}
</style>
