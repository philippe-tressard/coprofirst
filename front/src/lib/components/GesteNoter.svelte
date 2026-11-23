<!--
  Le geste « ⭐ Noter » d'un prestataire — un seul composant pour deux entrées
  (14/11/2026) : la carte d'un CONTRAT (rattaché à lui) et la FICHE d'un prestataire
  (une intervention, avec ou sans contrat). Il sert aussi à CORRIGER son propre avis
  (`notation` renseigné) : seul l'auteur le voit ouvert, le serveur le refuse sinon.

  On note le couple prestataire / affaire : on choisit l'affaire (`ChoixAffaireAvis`),
  celles du prestataire d'abord, puis les autres, avec la recherche détaillée de la page
  Affaires. Si le prestataire n'y figure pas, il faut confirmer son ajout à l'affaire —
  sans cette case, l'avis ne part pas.

  Réservé au conseil syndical et à l'administration, comme le serveur.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { prestataires as prestApi, type AffaireAvis, type Notation } from '#lib/api/index.ts';
	import { essayer } from '#lib/chargement.ts';
	import { nombreOuNull } from '#lib/utils.ts';
	import { tenter } from '#lib/erreurs.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import type { Etat } from '#lib/notations.ts';
	import ChoixAffaireAvis from './ChoixAffaireAvis.svelte';
	import FormulaireNotation from './FormulaireNotation.svelte';
	import GesteEnPlace from './GesteEnPlace.svelte';
	import IconeAction from './IconeAction.svelte';

	/** Le prestataire noté, et son nom — pour la confirmation de l'ajout à une affaire. */
	export let prestataireId: number;
	export let prestataireNom = '';
	/** Le contrat auquel la note se rattache — absent hors contrat. */
	export let contratId: number | undefined = undefined;
	/** L'avis qu'on corrige ; absent pour un nouvel avis. */
	export let notation: Notation | null = null;

	const dispatch = createEventDispatcher<{ cree: Notation; modifie: Notation }>();

	const cle = `${prestataireId}-${contratId ?? 'sans-contrat'}-${notation?.id ?? 'nouveau'}`;

	let ouvert = false;
	let etat: Etat | null = notation?.etat ?? null;
	let commentaire = notation?.commentaire ?? '';
	let enCours = false;
	let affaires: AffaireAvis[] = [];
	let affaireId = notation?.ticket_id ? String(notation.ticket_id) : '';
	let confirmeAjout = false;

	/** L'affaire choisie, et si le prestataire n'y figure pas encore. */
	$: choisie = affaires.find((a) => String(a.id) === affaireId) ?? null;
	$: ajoutRequis = choisie !== null && !choisie.intervient;

	async function ouvrir() {
		ouvert = true;
		if (!notation) {
			etat = null;
			commentaire = '';
			affaireId = '';
		}
		confirmeAjout = false;
		[affaires] = await essayer(prestApi.affairesAnoter(prestataireId), []);
	}

	async function enregistrer() {
		if (!etat) {
			toast('error', "Choisissez l'état : Mauvais, Neutre ou Excellent");
			return;
		}
		if (etat === 'mauvais' && !commentaire.trim()) {
			toast('error', 'Un avis « Mauvais » doit être justifié par un commentaire');
			return;
		}
		if (ajoutRequis && !confirmeAjout) {
			toast('error', `Confirmez l'ajout de ${prestataireNom} à l'affaire choisie`);
			return;
		}
		//  Capturés AVANT le rappel : à l'intérieur, rien ne garantit qu'ils n'ont pas changé.
		const choisi = etat;
		const texte = commentaire.trim() || undefined;
		const affaire = nombreOuNull(affaireId) ?? undefined;
		enCours = true;
		if (notation) {
			await tenter(async () => {
				const m = await prestApi.updateNotation(notation.id, {
					etat: choisi,
					commentaire: texte ?? null,
					ticket_id: affaire ?? null,
					confirmer_ajout: confirmeAjout,
				});
				ouvert = false;
				dispatch('modifie', m);
			}, 'Avis modifié');
		} else {
			await tenter(async () => {
				const n = await prestApi.createNotation({
					prestataire_id: prestataireId,
					etat: choisi,
					commentaire: texte,
					contrat_id: contratId,
					ticket_id: affaire,
					confirmer_ajout: confirmeAjout,
				});
				ouvert = false;
				dispatch('cree', n);
			}, 'Notation enregistrée');
		}
		enCours = false;
	}
</script>

<div class="geste-noter">
	{#if !notation}
		<button
			type="button"
			class="btn btn-sm btn-outline"
			aria-pressed={ouvert}
			on:click|stopPropagation={() => (ouvert ? (ouvert = false) : ouvrir())}
		>
			⭐ Noter
		</button>
	{:else}
		<button
			type="button"
			class="btn-icon-edit"
			aria-label="Modifier cet avis"
			title="Modifier cet avis"
			aria-pressed={ouvert}
			on:click|stopPropagation={() => (ouvert ? (ouvert = false) : ouvrir())}
		>
			<IconeAction icone="pencil" />
		</button>
	{/if}
	{#if ouvert}
		<div role="presentation" on:click|stopPropagation on:keydown|stopPropagation>
			<GesteEnPlace {enCours} onAnnuler={() => (ouvert = false)} onValider={enregistrer}>
				<ChoixAffaireAvis id="affaire-{cle}" {affaires} {prestataireNom} bind:affaireId />
				{#if ajoutRequis}
					<label class="confirmer-ajout">
						<input type="checkbox" bind:checked={confirmeAjout} />
						<span>
							Ajouter {prestataireNom} comme intervenant de « {choisie?.titre} » (son avis y sera rattaché)
						</span>
					</label>
				{/if}
				<FormulaireNotation
					id="notation-{cle}"
					bind:etat
					bind:commentaire
					initial={notation?.commentaire ?? ''}
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
	.confirmer-ajout {
		display: flex;
		align-items: flex-start;
		gap: 0.5rem;
	}
	.confirmer-ajout input {
		margin-top: 0.2rem;
	}
</style>
