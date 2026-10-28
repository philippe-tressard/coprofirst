<!--
  ConsignesArrivant.svelte — les consignes imprimées sur la fiche arrivant,
  éditables par le conseil syndical (#1727).

  ## Pourquoi

  Elles étaient écrites en dur dans `api/app/utils/fiche_arrivant.py` : jours de
  collecte des encombrants par rue, nom du syndic. Changer un jour de collecte
  demandait une livraison, et une autre copropriété aurait imprimé les nôtres.

  ## Du texte, jamais du HTML

  La fiche est une page servie à tout utilisateur connecté, et le serveur échappe
  ce qu'on écrit ici. Deux conventions seulement, rappelées sous le formulaire :
  `**gras**`, et `{syndic}` pour le nom du syndic — lu dans le contrat au moment
  d'imprimer, jamais recopié : il périmerait au premier changement de syndic.

  ## Le geste

  Lecture, puis le crayon : le formulaire prend la place de la lecture, comme
  l'en-tête du syndic juste en dessous (`EnteteSyndic`). Une rubrique se retire
  tant qu'il en reste une ; le serveur en borne le nombre et la longueur.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import {
		consignesArrivant as consignesApi,
		type ConsigneArrivant,
		type ConsignesArrivant,
	} from '#lib/api/index.ts';
	import EtatListe from '#lib/components/EtatListe.svelte';
	import EtoileRequis from '#lib/components/EtoileRequis.svelte';
	import Icon from '#lib/components/Icon.svelte';
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';
	import { toast } from '#lib/components/Toast.svelte';
	import { messageErreur } from '#lib/erreurs.ts';

	/** Le serveur en refuse davantage (`utils/consignes_arrivant.Consignes`). */
	const MAX_RUBRIQUES = 12;

	let lues: ConsignesArrivant | null = null;
	let chargement = true;
	let erreur = '';
	let edition = false;
	let enregistrement = false;
	let saisie: ConsigneArrivant[] = [];

	$: incomplete = saisie.some((c) => !c.titre.trim() || !c.contenu.trim());

	onMount(async () => {
		try {
			lues = await consignesApi.lire();
		} catch (e) {
			erreur = messageErreur(e);
		} finally {
			chargement = false;
		}
	});

	function modifier() {
		saisie = (lues?.consignes ?? []).map((c) => ({ ...c }));
		edition = true;
	}

	async function enregistrer() {
		enregistrement = true;
		try {
			lues = await consignesApi.enregistrer(
				saisie.map((c) => ({ titre: c.titre.trim(), contenu: c.contenu.trim() })),
			);
			edition = false;
			toast('success', 'Consignes enregistrées');
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			enregistrement = false;
		}
	}
</script>

<EtatListe {chargement} {erreur} vide={!lues?.consignes.length}>
	{#if edition}
		<form on:submit|preventDefault={enregistrer}>
			{#each saisie as _rubrique, i (_rubrique)}
				<div class="rubrique">
					<label class="field">
						<span>Titre<EtoileRequis vide={!saisie[i].titre.trim()} /></span>
						<input type="text" maxlength="120" bind:value={saisie[i].titre} />
					</label>
					<label class="field">
						<span>Texte<EtoileRequis vide={!saisie[i].contenu.trim()} /></span>
						<textarea rows="5" maxlength="4000" bind:value={saisie[i].contenu}></textarea>
					</label>
					{#if saisie.length > 1}
						<button
							type="button"
							class="btn btn-sm btn-outline btn-retirer"
							aria-label="Retirer cette rubrique"
							on:click={() => (saisie = saisie.filter((_, j) => j !== i))}>− Retirer</button
						>
					{/if}
				</div>
			{/each}
			{#if saisie.length < MAX_RUBRIQUES}
				<button
					type="button"
					class="btn btn-sm btn-outline"
					on:click={() => (saisie = [...saisie, { titre: '', contenu: '' }])}
					>+ Nouvelle rubrique</button
				>
			{/if}
			<p class="consignes-aide">
				Une ligne par consigne. <code>**texte**</code> s’imprime en gras ;
				<code>{'{syndic}'}</code> est remplacé par le nom du syndic du contrat en cours.
			</p>
			<PiedFormulaire
				enCours={enregistrement}
				desactive={incomplete}
				on:annule={() => (edition = false)}
			/>
		</form>
	{:else if lues}
		<div>
			{#if !lues.personnalisees}
				<p class="consignes-aide">
					Modèle générique : la résidence n’a pas encore écrit les siennes.
				</p>
			{/if}
			{#each lues.consignes as rubrique (rubrique)}
				<div class="rubrique">
					<strong>{rubrique.titre}</strong>
					<p class="rubrique-texte">{rubrique.contenu}</p>
				</div>
			{/each}
			<button
				type="button"
				class="btn-icon btn-icon-edit"
				aria-label="Modifier les consignes"
				title="Modifier les consignes"
				on:click={modifier}><Icon name="pencil" size={13} /></button
			>
		</div>
	{/if}
</EtatListe>

<style>
	/*  Une rubrique : un cadre, pour qu'on voie où elle commence et où elle
	    s'arrête — la même lecture que les contacts d'un prestataire. */
	.rubrique {
		border: 1px solid var(--color-border);
		border-radius: 6px;
		padding: 0.6rem;
		margin: 0.5rem 0;
	}
	/*  Le texte se relit comme il s'imprimera : une ligne par consigne. */
	.rubrique-texte {
		margin: 0.3rem 0 0;
		white-space: pre-wrap;
		overflow-wrap: anywhere;
	}
	.consignes-aide {
		color: var(--color-text-muted);
		font-size: var(--fs-sm);
	}
</style>
