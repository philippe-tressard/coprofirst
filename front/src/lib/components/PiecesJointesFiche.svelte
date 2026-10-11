<!--
  La section **Pièces jointes** d'une fiche de « Ma résidence » — un plan, un
  règlement, un CR d'AG, un rapport de diagnostic, une règle.

  ## Pourquoi (11/10/2026)

  Signalé : *« L'édition (modification, ajout, suppression) de nouvelles pièces
  jointes dans les Fiches de Ma résidence n'est pas possible. Ajoutez la
  catégorie standard Pièces jointes à l'édition. »* Les formulaires de ces fiches
  passaient `avecFichier={false}` à `FormulaireDocument` : une fois déposé, un
  document ne pouvait plus changer de fichier, ni rien porter d'autre.

  Arbitré avec l'utilisateur : le fichier PRINCIPAL reste, et se remplace ; la
  fiche reçoit en plus jusqu'à dix ANNEXES (migration 0278, `utils/annexes` côté
  API). Une règle, qui n'a pas de fichier, n'a que des annexes.

  ## Ce qu'il réutilise, et rien d'autre

  - l'intitulé vient de `SECTIONS_LIBELLE` — jamais écrit ici ;
  - les annexes sont des `Document` rattachés à un objet existant :
    `DocumentsRattaches`, le composant des pièces de contrat, paramétré par la
    cible — même dépôt immédiat, même croix, même pastille ;
  - le fichier principal passe par `FichiersUpload`, le seul sélecteur du site.

  ⚠️ **Le fichier principal se REMPLACE, il ne se retire pas.** Sa croix ne
  supprime rien : elle libère la place, et c'est le dépôt du suivant qui
  remplace l'ancien côté serveur. Fermer sans rien déposer laisse l'ancien en
  place — l'aide le dit, pour que l'écran ne promette pas une suppression.
-->
<script context="module" lang="ts">
	import type { Document, PorteurAnnexes } from '$lib/api';

	/** Le fichier qui EST la fiche — absent pour une règle. */
	export interface FichierPrincipal {
		url: string;
		nom: string;
		/** Le dépôt qui remplace le fichier ; rend ce qu'il faut afficher ensuite. */
		remplacer: (file: File) => Promise<{ url: string; nom: string }>;
	}

	/** Ce que `FormulaireDocument` reçoit pour monter la section. */
	export interface PiecesFiche {
		cible: PorteurAnnexes;
		/** `null` pendant la création : les annexes attendent l'enregistrement. */
		objetId: number | null;
		principal?: FichierPrincipal | null;
		/** Prévenu à chaque ajout ou retrait : la rubrique rafraîchit ses cartes. */
		onChange?: (annexes: Document[]) => void;
	}
</script>

<script lang="ts">
	import { onMount } from 'svelte';
	import DocumentsRattaches from '$lib/components/DocumentsRattaches.svelte';
	import FichiersUpload from '$lib/components/FichiersUpload.svelte';
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import { documents as docsApi } from '$lib/api';
	import { essayer } from '$lib/chargement';
	import { supprimerDocument } from '$lib/gestes-document';
	import { SECTIONS_LIBELLE } from '$lib/entites/types';

	export let idPrefixe: string;
	/** Le pliage, transmis par l'appelant (`lint:pliage-transmis`). */
	export let pliable = false;
	export let cible: PorteurAnnexes;
	export let objetId: number | null;
	export let principal: FichierPrincipal | null = null;
	export let onChange: (annexes: Document[]) => void = () => {};
	/** Les annexes choisies pendant la création — l'appelant les attache ensuite. */
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
	 *   document, confirmation comprise (`$lib/gestes-document`). */
	const supprimer = (_objetId: number, docId: number) =>
		supprimerDocument(docId, 'Cette pièce jointe', recharger);

	//  Le fichier principal : une pastille, une place.
	let urlsPrincipal = principal ? [principal.url] : [];
	let nomsPrincipal: Record<string, string> = principal
		? { [principal.url]: principal.nom }
		: {};

	async function remplacerPrincipal(file: File): Promise<string> {
		const nouveau = await principal!.remplacer(file);
		nomsPrincipal = { ...nomsPrincipal, [nouveau.url]: nouveau.nom };
		return nouveau.url;
	}

	$: total = annexes.length + fichiersEnAttente.length + (principal ? 1 : 0);
</script>

<SectionFormulaire
	titre={SECTIONS_LIBELLE.pieces_jointes}
	{pliable}
	valeurModifiee={total > 0}
	resume={total ? `${total} fichier${total > 1 ? 's' : ''}` : 'Aucune'}
	pour="{idPrefixe}-{principal ? 'principal' : 'annexes'}"
>
	{#if principal}
		<div class="field champ-large">
			<FichiersUpload
				id="{idPrefixe}-principal"
				mode="mixte"
				titre=""
				max={1}
				bind:urls={urlsPrincipal}
				noms={nomsPrincipal}
				upload={remplacerPrincipal}
				remove={async () => []}
			/>
			<span class="aide"
				>Le fichier du document. Pour le remplacer, retirez-le puis déposez le nouveau ; sans
				nouveau dépôt, il est conservé.</span
			>
		</div>
	{/if}
	<div class="field champ-large">
		{#if principal}<span class="aide">Annexes — jusqu’à dix, photos ou documents.</span>{/if}
		<DocumentsRattaches
			{cible}
			{objetId}
			mode="mixte"
			documents={annexes}
			onSupprimer={supprimer}
			onAjoute={recharger}
			bind:fichiersEnAttente
			idChamp="{idPrefixe}-annexes"
		/>
		{#if erreur}<span class="aide">{erreur}</span>{/if}
	</div>
</SectionFormulaire>
