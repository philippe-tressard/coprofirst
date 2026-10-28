<!--
  Une actualité dans une liste : le conteneur dépliable, sa ligne d'en-tête,
  son aperçu replié et son corps déplié.

  🔴 Elle lit une AFFAIRE depuis le 23/09/2026 — une actualité en est la
  catégorie « Actualité » (#1091, lot 4). Elle garde son allure, que le
  résident reconnaît : pas de numéro, pas d'état de suivi, l'urgence en bord
  rouge. C'est `ListeTickets` qui la choisit pour une actualité.

  Pourquoi ce composant (#356) : la page Actualités rendait la MÊME carte à deux
  endroits — le fil principal et l'Historique. Le lot #351 a dû y appliquer
  quatre modifications au lieu de deux (ordre photos/texte, puis vignette, deux
  fois chacune), et c'est le genre d'écart qui finit par diverger le jour où l'on
  ne pense qu'à l'un des deux.

  ⚠️ Le balisage part AVEC ses règles CSS (`.pub-row*`, `.pub-body`,
  `.pin-badge`…). Svelte scope les styles au composant : les laisser derrière
  reproduirait la régression du 14/08/2026 (#344), où le balisage était parti
  dans un composant et les règles étaient restées dans la page.

  Ce que la page garde chez elle : ses formulaires et son fil d'évolutions,
  passés en slots — ils sont écrits dans la page, donc leurs styles y restent.
-->
<script lang="ts">
	import CarteListe from '#lib/components/CarteListe.svelte';
	import IconeAction from '#lib/components/IconeAction.svelte';
	import BadgeNouveau from '#lib/components/BadgeNouveau.svelte';
	import { nomProprietaire } from '#lib/saisi-pour.ts';
	import { createEventDispatcher } from 'svelte';
	import ApercuCarte from '#lib/components/ApercuCarte.svelte';
	import ExtraitRecherche from '#lib/components/ExtraitRecherche.svelte';
	import EnteteCarte from '#lib/components/EnteteCarte.svelte';
	import PastillesAffaire from '#lib/components/PastillesAffaire.svelte';
	import BoutonLien from '#lib/components/BoutonLien.svelte';
	import PiecesJointes from '#lib/components/PiecesJointes.svelte';
	import {
		documents as docsApi,
		type CorrespondanceAffaire,
		type Document,
		type Ticket,
	} from '#lib/api/index.ts';
	import { safeHtml } from '#lib/sanitize.ts';
	import { attributsNature, gouttiereAffaire, lienTicket, ticketUrgent } from '#lib/tickets.ts';
	//  Glyphes et intitulés des quatre options : source unique. Ils étaient
	//  écrits ici ET dans les cases du formulaire, et avaient divergé.
	import { optionPublication } from '#lib/options-publication.ts';
	import { fmtDateLong } from '#lib/date.ts';

	export let pub: Ticket;
	//  À QUI l'actualité appartient — le « Saisi pour » s'il existe, l'auteur
	//  sinon (#1104). C'est le même nom sur la carte et dans le corps déplié.
	$: proprietaireNom = nomProprietaire(pub);
	//  Photos et documents, en URLs comme toute affaire.
	$: pieces = [...(pub.photos_urls ?? []), ...(pub.fichiers_urls ?? [])];
	export let expanded = false;
	/**  `fil` : la liste principale. `historique` : les archives — atténuées, et
	 *   sans épingle ni « New », qui n'ont plus de sens sur une publication rangée. */
	export let variante: 'fil' | 'historique' = 'fil';
	/** Aperçu replié — la page le masque quand la liste devient longue. */
	export let apercu = true;
	/**  Les documents des ANCIENNES publications — des entités `Document`, que
	 *   la 0210 a rattachées à l'affaire. Une actualité récente n'en a pas : ses
	 *   documents sont dans `fichiers_urls`. */
	export let documents: Document[] = [];
	/**  Le geste qui retire l'un d'eux (#1178) — `null` : pas de 🗑️ (hors conseil). */
	export let onRetirerDocument: ((doc: { id: number }) => void) | null = null;
	/**  Vrai quand la page affiche un formulaire à la place du contenu (édition,
	 *   ajout d'évolution). Explicite, et non déduit de `$$slots` : un slot
	 *   fourni mais vide masquerait le corps en permanence. */
	export let formulaireOuvert = false;
	/** Ce qui l'a fait trouver, quand la liste est une recherche (27/09/2026). */
	export let correspondance: CorrespondanceAffaire | null = null;
	/** Précharger ce que le dépliage affichera, quand la main s'approche (#1861) —
	 *  relayé tel quel à `CarteListe`, qui en porte la règle. */
	export let onApprocher: (() => unknown) | null = null;

	const dispatch = createEventDispatcher<{ toggle: void }>();
	const basculer = () => dispatch('toggle');

	$: estFil = variante === 'fil';

	//  L'ancre est `ticket-<id>`, celle de toute affaire : la liste l'emploie pour
	//  les liens profonds (`?open=`), et une actualité y est une affaire. Les
	//  anciens liens `/actualites#pub-<id>` passent par la redirection de
	//  `routes/(app)/actualites`, qui mène à la fiche.
</script>

<!--  QUAND puis QUOI, dans la colonne de gauche (maquette B, 10/10/2026) : la
      date n'est donc plus passée à l'en-tête — un seul fait, une place. -->
<CarteListe
	id="ticket-{pub.id}"
	{...gouttiereAffaire(pub)}
	{expanded}
	urgent={ticketUrgent(pub)}
	archive={!estFil}
	onDeplier={basculer}
	{onApprocher}
	{...attributsNature(pub)}
>
	{#if estFil && pub.epingle}
		{@const o = optionPublication('epingle')}
		<span class="pin-badge" title={o?.aide} aria-label={o?.etat}>{o?.glyphe}</span>
	{/if}

	<!--  Titre sur sa propre ligne, puis tags à gauche / date + actions à droite :
	      la norme de toutes les cartes du site depuis le 18/08/2026. Elle vit dans
	      `EnteteCarte`, pas ici — chaque carte qui recomposait son en-tête avait sa
	      propre façon de mal se replier, et sur téléphone le titre disparaissait. -->
	<!--  Le geste de dépliage vit dans `EnteteCarte` : le TITRE plie, avec un
	      survol qui le dit (18/08/2026). Le conteneur ne porte plus
	      `role="button"` — il interceptait la sélection de texte, et obligeait
	      chaque bouton d'action à un `stopPropagation` pour qu'un clic sur ✏️ ne
	      déplie pas la carte au même instant. -->
	<EnteteCarte titre={pub.titre} basculable on:toggle={basculer}>
		<svelte:fragment slot="titre-suffixe">
			<BadgeNouveau le={pub.cree_le} si={estFil} />
		</svelte:fragment>
		<svelte:fragment slot="tags">
			<!--  La MÊME ligne que la carte d'affaire (27/09/2026) : une actualité est
			      une affaire. La pastille de lecture y remplace toujours les badges
			      🛡️ et 🔒 (lot 1, 25/09/2026). -->
			<PastillesAffaire affaire={pub} auteur={proprietaireNom} />
		</svelte:fragment>
		<svelte:fragment slot="actions">
			<BoutonLien chemin={lienTicket(pub.id)} quoi="l'actualité" />
			<slot name="actions" />
		</svelte:fragment>
		<!--  🔴 L'aperçu passe par l'EN-TÊTE (18/09/2026) : c'est ce qui permet aux
		      pastilles de descendre en dernière ligne, comme sur le fil d'activité.
		      Rendu après `</EnteteCarte>`, il était le FRÈRE de l'en-tête — aucun
		      ordre CSS ne fait passer un élément sous le frère d'un autre parent. -->
		<svelte:fragment slot="apercu">
			{#if !expanded && apercu}
				<ApercuCarte contenu={pub.description} photos={pub.photos_urls ?? []} dansLigne />
			{/if}
			{#if !expanded && correspondance}
				<ExtraitRecherche {correspondance} archivee={pub.archivee} />
			{/if}
		</svelte:fragment>
	</EnteteCarte>

	{#if expanded}
		<!--  Le corps ne referme pas la carte : on referme par l'en-tête. Sans cela,
		      impossible de sélectionner du texte, et un clic sur une photo ou un
		      formulaire referme ce qu'on lisait (ux-patterns §3). -->
		<div
			class="carte-corps pub-body"
			role="presentation"
			on:click|stopPropagation
			on:keydown|stopPropagation
		>
			{#if formulaireOuvert}
				<slot name="formulaire" />
			{:else}
				<!--  Texte AVANT les photos : une image en tête poussait le premier mot sous la ligne de flottaison. -->
				<div class="rich-content description-actualite">
					{@html safeHtml(pub.description)}
				</div>
				{#if pieces.length}
					<PiecesJointes urls={pieces} format="grand" />
				{/if}
				{#if documents.length > 0}
					<div class="pub-attachments">
						{#each documents as doc (doc.id)}
							<a
								href={docsApi.downloadUrl(doc.id)}
								target="_blank"
								rel="noopener"
								class="pub-attachment-link"
							>
								📎 {doc.titre || doc.fichier_nom}
							</a>
							{#if onRetirerDocument}
								<button
									type="button"
									class="btn-icon"
									aria-label="Supprimer le document {doc.titre || doc.fichier_nom}"
									on:click|stopPropagation={() => onRetirerDocument?.(doc)}
									><IconeAction icone="trash-2" /></button
								>
							{/if}
						{/each}
					</div>
				{/if}
				<small class="text-muted-sm">
					{#if pub.mis_a_jour_le}Mise à jour le {fmtDateLong(pub.mis_a_jour_le)}{:else}Publié le {fmtDateLong(
							pub.cree_le,
						)}{/if}{#if proprietaireNom}
						· {proprietaireNom}{/if}
				</small>
				<slot name="apres-corps" />
			{/if}
		</div>
	{/if}
</CarteListe>

<style>
	/*  Conteneur, survol, urgence et espacement : `.carte-liste` (app.css). Ne
	    reste ici que ce qui est propre à la publication. */
	.pin-badge {
		position: absolute;
		top: -9px;
		left: 8px;
		display: inline-flex;
		align-items: center;
		background: var(--color-primary-plein);
		color: var(--color-sur-plein);
		font-size: var(--fs-2xs);
		padding: 0.1rem 0.35rem;
		border-radius: 8px;
		line-height: 1.6;
		z-index: 1;
		pointer-events: none;
	}

	/*  L'en-tête vit dans `EnteteCarte` — titre, tags, date, actions et leur repli.
	    Ne reste ici que ce qui est propre à une publication. */

	.pub-body {
		padding: 0.75rem 1rem 1rem;
		border-top: 1px solid var(--color-border);
	}
	.pub-attachments {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		margin: 0.5rem 0 0.25rem;
	}
	.pub-attachment-link {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		font-size: var(--fs-md);
		padding: 0.25rem 0.55rem;
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		border-radius: 4px;
		color: var(--color-primary);
		text-decoration: none;
	}
	@media (hover: hover) and (pointer: fine) {
		.pub-attachment-link:hover {
			background: var(--color-border);
		}
	}

	.description-actualite {
		font-size: var(--fs-base);
		line-height: 1.6;
		margin-bottom: 0.5rem;
	}
</style>
