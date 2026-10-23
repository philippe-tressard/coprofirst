<!--
  SectionAffairesLiees.svelte — « Affaires liées » (#1342, 26/09/2026).

  Les affaires qui parlent de la même chose : une fuite et la tache qu'elle a
  faite au plafond du dessous. Chaque affaire se RECONNAÎT à son titre, dans la
  liste proposée comme une fois retenue — c'était la demande : un numéro seul
  ne dit rien.

  ## Une affaire retenue est une LIGNE (#2173, 23/10/2026)

  Demandé : « en plus du N° et du titre, le suivi et la date de création ». La
  pastille « TK-12: titre × » n'y suffisait plus ; chaque affaire est une ligne
  — numéro, titre, puis son suivi (`BadgeEtatAffaire`, le badge de sa carte) et
  « créée le … ». Pas de tableau : au téléphone la ligne passe sur deux rangs
  (numéro et titre, puis suivi et date), la croix reste une cible de 44 px.
  Une ligne qu'on vient de retenir entre en fondu (le corps d'une carte) ;
  celles qui étaient là à l'ouverture ne bougent pas.

  ## Fusionner, depuis la correction (#2173)

  Quand la section sert la CORRECTION d'une affaire (`affaire`), le conseil peut
  fusionner ses affaires liées enregistrées : le geste du Suivi des affaires
  (#2083), monté tel quel — `fusionnerLiees` dit lesquelles, `ModaleFusionAffaires`
  pourquoi une fenêtre. La fusion faite, la section rend l'affaire relue à
  l'appelant (`fusionnee`) : la correction se referme sans enregistrer, et la
  principale s'ouvre (`apresFusion`).

  ## Ce que le serveur décide, et que cet écran ne rejoue pas

  - la liste proposée (`GET /tickets/choix`) ne contient que ce que le lecteur
    peut LIRE ; une affaire liée qu'il ne peut pas lire ne lui est pas rendue ;
  - le lien est réciproque ; une Suite ajoute sans retirer
    (`api/app/utils/affaires_liees.py`) ;
  - ce qui se fusionne, et ce qui s'y refuse (`utils/fusion_affaires`).

  La recherche elle-même — chargement au focus, affaires ouvertes récentes
  quand le champ est vide — est `ChoixAffaire`, partagée avec la réaffectation
  d'un transfert de courriel (#1482).
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import type { AffaireLiee } from '$lib/api/types';
	import BadgeEtatAffaire from '$lib/components/BadgeEtatAffaire.svelte';
	import ChoixAffaire from '$lib/components/ChoixAffaire.svelte';
	import IconeAction from '$lib/components/IconeAction.svelte';
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import { SECTIONS_LIBELLE } from '$lib/entites/types';
	import { fmtDate } from '$lib/date';
	import type { Ticket } from '$lib/api';
	import {
		apresFusion,
		fusionPossible,
		fusionnerLiees,
		type AffaireCorrigee,
	} from '$lib/fusion-affaires';
	import { isCS } from '$lib/stores/auth';

	/** Les affaires retenues — lié : l'appelant en envoie les `id`. */
	export let liees: AffaireLiee[] = [];
	/** L'affaire qu'on édite : elle ne se propose pas à elle-même. */
	export let exclure: number | null = null;
	/**  L'affaire qu'on CORRIGE, telle qu'enregistrée — c'est elle qui ouvre la
	 *   fusion. Absente à la création et dans une Suite. */
	export let affaire: AffaireCorrigee | null = null;
	export let idPrefixe = 'ticket';
	/** Relayé depuis la déclaration (`lint:pliage-transmis`). */
	export let pliable = false;
	export let inactive = '';

	//  La fusion faite, l'affaire corrigée RELUE : l'appelant la rend comme une
	//  correction enregistrée (`apresFusion` ouvre ensuite la principale).
	const dispatch = createEventDispatcher<{ fusionnee: Ticket }>();

	$: ecartees = [...(exclure === null ? [] : [exclure]), ...liees.map((l) => l.id)];
	//  Les lignes retenues PENDANT la saisie : elles seules entrent en fondu.
	let ajoutees: number[] = [];

	function retenir(a: AffaireLiee) {
		liees = [...liees, a];
		ajoutees = [...ajoutees, a.id];
	}

	function retirer(id: number) {
		liees = liees.filter((l) => l.id !== id);
	}

	$: resume = liees.length === 0 ? 'aucune' : liees.map((l) => l.numero).join(', ');

	$: fusionOfferte = $isCS && fusionPossible(affaire);
	let fusionEnCours = false;

	async function fusionner() {
		if (!affaire) return;
		fusionEnCours = true;
		try {
			const r = await fusionnerLiees(affaire);
			const relue = r && (await apresFusion(affaire.id, r));
			if (relue) dispatch('fusionnee', relue);
		} finally {
			fusionEnCours = false;
		}
	}
</script>

<SectionFormulaire
	titre={SECTIONS_LIBELLE.affaires_liees}
	{pliable}
	{inactive}
	rempli={liees.length > 0}
	{resume}
	valeurModifiee={liees.length > 0}
	pour="{idPrefixe}-affaires-liees"
>
	{#if liees.length > 0}
		<ul class="liees" aria-label="Affaires retenues">
			{#each liees as l (l.id)}
				<li class="liee" class:entree={ajoutees.includes(l.id)}>
					<span class="liee-numero">{l.numero}</span>
					<span class="liee-titre clamp-2">{l.titre}</span>
					<span class="liee-meta">
						<span class="liee-suivi"
							><BadgeEtatAffaire statut={l.statut} fusionnee={l.fusionnee} compact /></span
						>
						<span class="liee-date">créée le {fmtDate(l.cree_le)}</span>
					</span>
					<button
						type="button"
						class="btn-icon liee-retirer"
						title="Retirer ce lien"
						aria-label="Retirer le lien avec {l.numero} — {l.titre}"
						on:click={() => retirer(l.id)}
					>
						<IconeAction icone="x" />
					</button>
				</li>
			{/each}
		</ul>
	{/if}
	{#if fusionOfferte}
		<div class="liees-fusion">
			<button
				type="button"
				class="btn btn-sm btn-outline"
				disabled={fusionEnCours}
				aria-busy={fusionEnCours}
				on:click={fusionner}
			>
				Fusionner
			</button>
			<p class="aide">
				Celle-ci et ses affaires liées enregistrées, si elles portent le même besoin.
			</p>
		</div>
	{/if}
	<ChoixAffaire
		id="{idPrefixe}-affaires-liees"
		exclure={ecartees}
		on:choisir={(e) => retenir(e.detail)}
	/>
	<p class="aide">Le lien vaut dans les deux sens : l’autre affaire citera celle-ci.</p>
</SectionFormulaire>

<style>
	/*  La liste a l'allure de celle que `ChoixAffaire` propose juste dessous :
	    filet, rayon, séparateurs — on retient dans la forme où l'on a choisi.
	    Elle porte les COLONNES, et chaque ligne les reprend (`subgrid`) : les
	    numéros, les suivis et les dates s'alignent d'une ligne à l'autre, sans
	    largeur écrite. */
	.liees {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr) auto auto auto;
		list-style: none;
		margin: 0 0 0.5rem;
		padding: 0;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		overflow: hidden;
		background: var(--color-surface);
	}
	.liees li + li {
		border-top: 1px solid var(--color-border);
	}
	/*  Une ligne : numéro · titre (il prend la place) · suivi · date · croix.
	    Sans `subgrid`, la ligne garde ses colonnes à elle : seul l'alignement
	    d'une ligne à l'autre se perd. */
	.liee {
		grid-column: 1 / -1;
		display: grid;
		grid-template-columns: auto minmax(0, 1fr) auto auto auto;
		grid-template-columns: subgrid;
		grid-template-areas: 'numero titre suivi date retirer';
		align-items: center;
		column-gap: 0.75rem;
		min-height: 44px;
		padding: 0.25rem 0.25rem 0.25rem 0.75rem;
	}
	.liee.entree {
		animation: carte-entree var(--duree-apparition) var(--ease-out);
	}
	@media (prefers-reduced-motion: reduce) {
		.liee.entree {
			animation: none;
		}
	}
	.liee-numero {
		grid-area: numero;
		font-size: var(--fs-sm);
		font-weight: 700;
		color: var(--color-text-muted);
		font-variant-numeric: tabular-nums;
	}
	/*  Deux lignes au plus (`.clamp-2`, le titre d'une carte) : un titre se
	    reconnaît à ses mots, et la ligne s'élargit plutôt que de les couper. */
	.liee-titre {
		grid-area: titre;
	}
	/*  Au bureau, le suivi et la date sont deux colonnes de la grille : leur
	    enveloppe s'efface. Au téléphone, elle en refait une rangée. */
	.liee-meta {
		display: contents;
	}
	.liee-suivi {
		grid-area: suivi;
		justify-self: start;
	}
	.liee-date {
		grid-area: date;
		white-space: nowrap;
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
		font-variant-numeric: tabular-nums;
	}
	/*  La croix : 44 px au doigt comme à la souris (`standards/11` §10). */
	.liee-retirer {
		grid-area: retirer;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 44px;
		height: 44px;
	}
	.liees-fusion {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.25rem 0.75rem;
		margin: 0 0 0.75rem;
	}
	.liees-fusion .aide {
		margin: 0;
	}
	/*  Au téléphone, deux rangs : numéro et titre, puis le suivi et la date en
	    une rangée — un badge large ne pousse pas le titre ; la croix reste à
	    droite, sur les deux. */
	@media (max-width: 480px) {
		.liees {
			display: block;
		}
		.liee {
			grid-template-columns: auto minmax(0, 1fr) auto;
			grid-template-areas:
				'numero titre retirer'
				'meta meta retirer';
			row-gap: 0.15rem;
			padding-block: 0.4rem;
		}
		.liee-meta {
			grid-area: meta;
			display: flex;
			align-items: center;
			gap: 0.5rem;
		}
	}
</style>
