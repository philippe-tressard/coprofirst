<!--
  La section **Pièces jointes** d'une fiche de « Ma résidence » — un plan, un
  règlement, un CR d'AG, un rapport de diagnostic, une règle.

  ## Pourquoi (11/10/2026)

  Signalé : *« L'édition (modification, ajout, suppression) de nouvelles pièces
  jointes dans les Fiches de Ma résidence n'est pas possible. Ajoutez la
  catégorie standard Pièces jointes à l'édition. »* Les formulaires de ces fiches
  passaient `avecFichier={false}` à `FormulaireDocument` : une fois déposé, un
  document ne pouvait plus changer de fichier, ni rien porter d'autre.

  ## UNE liste, l'objet standard (11/10/2026, le soir même)

  La première version montrait deux blocs : le fichier de la fiche (1/1, « pour
  le remplacer, retirez-le… »), puis « Annexes — jusqu'à dix ». Signalé, capture
  à l'appui : *« ne pas mettre Annexes — utilise l'objet PJ standard une seule
  fois en principal ; on pourra joindre jusqu'à 10 fichiers »*, puis *« ne
  réinvente pas cet objet, il doit être standard »*.

  La section est donc UN `DocumentsRattaches` — le composant des pièces de
  contrat, celui des tickets à l'œil — où le fichier de la fiche est la première
  pastille (`principal`) et ses annexes les suivantes : dix en tout, le plafond
  du site. Une règle, qui n'a pas de fichier, n'a que la liste.

  ⚠️ **Une fiche garde toujours un fichier.** La croix de la première pastille
  le retire, et la pièce suivante prend sa place (`utils/annexes`) ; seule, elle
  est refusée par le serveur, dont le message dit quoi faire : déposer le
  nouveau, puis retirer l'ancien.
-->
<script context="module" lang="ts">
	import type { Document, PorteurAnnexes } from '#lib/api/index.ts';

	/** Le fichier qui EST la fiche — absent pour une règle. */
	export interface FichierPrincipal {
		url: string;
		nom: string;
		/** Le retrait côté serveur ; rend ce qu'il faut afficher ensuite. */
		retirer: () => Promise<{ url: string; nom: string }>;
	}

	/** Ce que `FormulaireDocument` reçoit pour monter la section. */
	export interface PiecesFiche {
		cible: PorteurAnnexes;
		/** `null` pendant la création : les pièces attendent l'enregistrement. */
		objetId: number | null;
		principal?: FichierPrincipal | null;
		/** Prévenu à chaque ajout ou retrait : la rubrique rafraîchit ses cartes. */
		onChange?: (annexes: Document[]) => void;
	}
</script>

<script lang="ts">
	import { onMount } from 'svelte';
	import DocumentsRattaches, {
		type PiecePrincipale,
	} from '#lib/components/DocumentsRattaches.svelte';
	import SectionFormulaire from '#lib/components/SectionFormulaire.svelte';
	import { documents as docsApi } from '#lib/api/index.ts';
	import { essayer } from '#lib/chargement.ts';
	import { confirmerPuis, SUPPRESSION } from '#lib/confirmation.ts';
	import { supprimerDocument } from '#lib/gestes-document.ts';
	import { SECTIONS_LIBELLE } from '#lib/entites/types.ts';

	export let idPrefixe: string;
	/** Le pliage, transmis par l'appelant (`lint:pliage-transmis`). */
	export let pliable = false;
	export let cible: PorteurAnnexes;
	export let objetId: number | null;
	export let principal: FichierPrincipal | null = null;
	export let onChange: (annexes: Document[]) => void = () => {};
	/** Les pièces choisies pendant la création — l'appelant les attache ensuite. */
	export let fichiersEnAttente: File[] = [];

	let annexes: Document[] = [];
	let erreur = '';

	async function recharger() {
		if (objetId === null) return;
		[annexes, erreur] = await essayer(docsApi.listPour(cible, objetId), annexes);
		if (!erreur) onChange(annexes);
	}
	onMount(recharger);

	/**  Retirer une annexe SUPPRIME le fichier : le geste de toute suppression de
	 *   document, confirmation comprise (`#lib/gestes-document`). */
	const supprimer = (_objetId: number, docId: number) =>
		supprimerDocument(docId, 'Cette pièce jointe', recharger);

	//  Le fichier de la fiche : la première pastille. Son retrait est une
	//  suppression du point de vue de qui le fait — même confirmation.
	let tete: PiecePrincipale | null = principal && {
		url: principal.url,
		nom: principal.nom,
		retirer: () =>
			confirmerPuis(SUPPRESSION('Ce fichier'), 'Fichier retiré', async () => {
				const suivant = await principal!.retirer();
				tete = { ...tete!, ...suivant };
				await recharger();
			}),
	};

	$: total = annexes.length + fichiersEnAttente.length + (tete ? 1 : 0);
</script>

<SectionFormulaire
	titre={SECTIONS_LIBELLE.pieces_jointes}
	{pliable}
	valeurModifiee={total > 0}
	resume={total ? `${total} fichier${total > 1 ? 's' : ''}` : 'Aucune'}
	pour="{idPrefixe}-pieces"
>
	<div class="field champ-large">
		<DocumentsRattaches
			{cible}
			{objetId}
			mode="mixte"
			principal={tete}
			documents={annexes}
			onSupprimer={supprimer}
			onAjoute={recharger}
			bind:fichiersEnAttente
			idChamp="{idPrefixe}-pieces"
		/>
		{#if erreur}<span class="aide">{erreur}</span>{/if}
	</div>
</SectionFormulaire>
