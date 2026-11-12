<!--
  ChoixAffaire.svelte — chercher une affaire et la choisir, par son numéro ou
  les mots de son titre.

  Extrait de `SectionAffairesLiees` le 30/09/2026 (#1482) : « réaffecter un
  transfert » demandait le même geste, et une seconde recherche d'affaire
  aurait divergé à la première retouche. Chaque affaire se RECONNAÎT à son
  titre, dans la liste proposée — un numéro seul ne dit rien (#1342).

  - la liste (`GET /tickets/choix`) ne contient que ce que le lecteur peut LIRE ;
    elle se charge au focus, pas au montage ;
  - champ vide, les affaires ENCORE OUVERTES les plus récentes ; une frappe
    cherche dans toutes — closes comprises, sauf `sansCloses`.

  🔴 La liste se replie APRÈS le geste, jamais pendant (12/11/2026). Elle est dans
  le flux : repliée au moment où le focus la quitte — l'appui sur un bouton placé
  dessous —, elle faisait remonter ce bouton sous le pointeur, et le clic tombait
  à côté. Invisible tant que l'appelant ne posait rien sous elle ; les transferts
  de courriel y posent désormais leur bouton principal. Elle se replie aussi dès
  qu'une affaire est choisie : rien ne reste ouvert au-dessus du bouton qui conclut.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { tickets as ticketsApi } from '#lib/api/index.ts';
	import type { AffaireLiee } from '#lib/api/types.ts';
	import { estTicketActif, idAffaireDepuisLien, termeAffaire } from '#lib/tickets.ts';

	/** L'`id` du champ — le titre de section de l'appelant peut s'y associer. */
	export let id: string;
	/** Le libellé du champ, quand aucun titre de section ne le porte. */
	export let libelle = '';
	/** Les affaires à ne pas proposer : celle qu'on édite, celles déjà retenues. */
	export let exclure: number[] = [];
	/** Une affaire close ne reçoit plus rien : ne pas la proposer. */
	export let sansCloses = false;

	const dispatch = createEventDispatcher<{ choisir: AffaireLiee }>();

	/** Combien de propositions à la fois : au-delà, on affine la recherche. */
	const PROPOSITIONS_MAX = 8;

	let recherche = '';
	let choix: AffaireLiee[] | null = null;
	let echec = false;
	/** La liste est-elle déroulée ? Le focus l'ouvre, sa sortie la referme. */
	let deroulee = false;
	let zone: HTMLElement;

	async function charger() {
		if (choix !== null) return;
		try {
			choix = await ticketsApi.choix();
		} catch {
			//  Une liste absente n'empêche pas le reste de l'écran : on le dit.
			echec = true;
			choix = [];
		}
	}

	//  « #TK-237133 » se colle tel qu'il s'écrit à l'écran : le dièse ne se tape pas.
	$: terme = termeAffaire(recherche).toLowerCase();
	//  Un lien collé (« …/tickets/465?src=whatsapp ») désigne une affaire par son id.
	$: idLien = idAffaireDepuisLien(recherche);
	$: ecartees = new Set(exclure);
	//  `choix` arrive du plus récent au plus ancien : les premières sont les dernières.
	$: propositions = deroulee
		? (choix ?? [])
				.filter(
					(a) =>
						!ecartees.has(a.id) &&
						!(sansCloses && a.close) &&
						(idLien !== null
							? a.id === idLien
							: terme
								? `${a.numero} ${a.titre}`.toLowerCase().includes(terme)
								: estTicketActif(a.statut)),
				)
				.slice(0, PROPOSITIONS_MAX)
		: [];

	function ouvrir() {
		deroulee = true;
		void charger();
	}

	/** Un appui est-il en cours ? Le replier attend qu'il finisse. */
	let appui = false;

	function replierSiSortie() {
		if (!zone?.contains(document.activeElement)) deroulee = false;
	}

	/** Le focus quitte la zone (champ + liste) : la liste se referme — après l'appui. */
	function sortie(e: FocusEvent) {
		if (zone?.contains(e.relatedTarget as Node | null)) return;
		//  Hors appui (Tab), tout de suite après l'événement : un clic synthétisé
		//  au doigt arrive dans la même tâche que le changement de focus.
		if (!appui) setTimeout(replierSiSortie);
	}

	function finAppui() {
		appui = false;
		//  Après le `click` qui suit, dans la même tâche : le bouton visé l'a reçu.
		setTimeout(replierSiSortie);
	}

	function choisir(a: AffaireLiee) {
		dispatch('choisir', a);
		recherche = '';
		deroulee = false;
	}
</script>

<svelte:window
	on:pointerdown={() => (appui = true)}
	on:pointerup={finAppui}
	on:pointercancel={finAppui}
/>

<div bind:this={zone} on:focusout={sortie}>
	<div class="field">
		{#if libelle}<label for={id}>{libelle}</label>{/if}
		<input
			{id}
			type="search"
			placeholder="Numéro ou mots du titre"
			autocomplete="off"
			bind:value={recherche}
			on:focus={ouvrir}
			on:input={ouvrir}
			on:keydown={(e) => e.key === 'Escape' && (deroulee = false)}
		/>
	</div>
	{#if propositions.length > 0}
		{#if !terme}<p class="aide">Les plus récentes encore ouvertes :</p>{/if}
		<ul class="propositions" aria-label="Affaires proposées">
			{#each propositions as a (a.id)}
				<li>
					<button type="button" class="proposition" on:click={() => choisir(a)}>
						<span class="numero">{a.numero}</span>
						<span class="titre">{a.titre}</span>
					</button>
				</li>
			{/each}
		</ul>
	{:else if deroulee && choix !== null}
		<!--  Rien à proposer n'empêche jamais de chercher : on le dit. -->
		<p class="aide">
			{echec
				? 'La liste des affaires n’a pas pu être chargée.'
				: terme
					? 'Aucune affaire ne correspond.'
					: 'Aucune affaire ouverte récente : tapez un numéro ou un mot du titre pour chercher parmi toutes.'}
		</p>
	{/if}
</div>

<style>
	.propositions {
		list-style: none;
		margin: 0.25rem 0 0;
		padding: 0;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		overflow: hidden;
	}
	.propositions li + li {
		border-top: 1px solid var(--color-border);
	}
	/*  Une ligne entière cliquable, à hauteur de pouce (`standards/11` §10). */
	.proposition {
		display: flex;
		gap: 0.5rem;
		align-items: baseline;
		width: 100%;
		min-height: 44px;
		padding: 0.5rem 0.75rem;
		border: none;
		background: var(--color-surface);
		text-align: left;
		cursor: pointer;
		font: inherit;
	}
	.proposition:focus-visible {
		outline: 2px solid var(--color-primary);
		outline-offset: -2px;
	}
	@media (hover: hover) and (pointer: fine) {
		.proposition:hover .titre {
			color: var(--color-primary);
		}
	}
	.numero {
		flex-shrink: 0;
		font-size: var(--fs-sm);
		font-weight: 700;
		color: var(--color-text-muted);
	}
	.titre {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
</style>
