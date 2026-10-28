<!--
  Une petite annonce : bandeau replié, détails dépliés, réponses.

  ## Réécrite sur la norme du site le 18/08/2026

  Signalé à l'écran, capture à l'appui : *« Petites annonces ne respecte pas le
  visuel de l'UX standard de la liste »*. Quatre écarts, une seule cause — cette
  carte **précède** la norme et recomposait donc son propre en-tête :

  | Écart | Correction |
  |---|---|
  | pastilles AVANT le titre | `EnteteCarte` : titre sur sa ligne, tags en dessous |
  | rien à modifier depuis la liste | ✏️ dans le slot `actions`, comme partout |
  | replié = le titre seul | `ApercuCarte` : quatre lignes, et le dégradé s'il est coupé |
  | vignette à GAUCHE | `ApercuCarte` la met à droite — la gauche porte le bord coloré |
  | on ne déplie qu'en visant ▼ | le **titre** plie, avec un survol qui le dit — `EnteteCarte` |

  ⚠️ **Aucun de ces cinq points n'a été corrigé ici** : ils viennent de composants
  qui les portaient déjà pour les actualités, les tickets et le calendrier. Une
  carte qui recompose son en-tête a sa propre façon de mal se replier — c'est
  très exactement ce que #430 R1 dit, et cette carte en était la dernière preuve.

  ## Ce qui reste propre à l'annonce

  Le prix, la gestion des photos (l'endpoint exige l'identifiant, cf. la dette
  `api` déclarée dans `#lib/entites/annonce`), et le raccourci de workflow.

  Le composant ne connaît ni l'API ni les magasins : tout ce qui écrit passe par
  un callback. C'est ce qui permet à l'onglet de garder la main sur la liste.

  Le vocabulaire — types, catégories, états et leurs rendus — vit dans
  `#lib/annonces.ts` : la carte le rend, l'onglet en fait ses filtres.
-->
<script lang="ts">
	import Badge from '#lib/components/Badge.svelte';
	import type { PetiteAnnonce } from '#lib/api/index.ts';
	import CarteListe from '#lib/components/CarteListe.svelte';
	import BadgeNouveau from '#lib/components/BadgeNouveau.svelte';
	import MarqueIA from '#lib/components/MarqueIA.svelte';
	import { nomAffiche } from '#lib/noms.ts';
	import EnteteCarte from './EnteteCarte.svelte';
	import IconeAction from './IconeAction.svelte';
	import BoutonLien from './BoutonLien.svelte';
	import ApercuCarte from './ApercuCarte.svelte';
	import FichiersUpload from './FichiersUpload.svelte';
	import PiecesJointes from './PiecesJointes.svelte';
	import Reponses from './Reponses.svelte';
	import WorkflowPastilles from './WorkflowPastilles.svelte';
	import { safeHtml } from '#lib/sanitize.ts';
	import { fmtMontant } from '#lib/utils.ts';
	import BadgePerimetre from '#lib/components/BadgePerimetre.svelte';
	import PastilleLecture from '#lib/components/PastilleLecture.svelte';
	import AuteurCarte from '#lib/components/AuteurCarte.svelte';
	import {
		MAX_PHOTOS_ANNONCE,
		OPTIONS_STATUT_ANNONCE,
		categorieAnnonceLabel,
		classementAnnonce,
		statutAnnonceClass,
		statutAnnonceLabel,
	} from '#lib/annonces.ts';

	export let annonce: PetiteAnnonce;
	/** L'annonce est-elle dépliée ? */
	export let expanded = false;
	/**  Vrai quand la page affiche un formulaire À LA PLACE du contenu (#787).
	 *
	 *   🔴 Le formulaire de correction s'ouvrait EN BAS DE PAGE, hors de la carte
	 *   : « c'est tout en bas, et on ne voit pas », signalé le 06/09/2026 — la
	 *   seconde fois que le même geste est signalé muet, après le 29/08 sur les
	 *   contrats. `FormulaireCreation` se ramène bien à l'écran, mais ramener une
	 *   boîte posée après toute la liste n'est pas la même chose que corriger là
	 *   où l'on a cliqué.
	 *
	 *   La carte d'actualité porte ce slot depuis longtemps ; celle-ci ne l'avait
	 *   pas. Il ne fallait rien inventer, seulement le reprendre.
	 *
	 *   Explicite, et non déduit de `$$slots` : un slot fourni mais vide
	 *   masquerait le corps en permanence. */
	export let formulaireOuvert = false;
	/** L'auteur a-t-il ouvert la zone de gestion des photos ? */
	export let gestionOuverte = false;
	export let estCS = false;
	export let estAdmin = false;
	export let currentUserId: number | undefined = undefined;
	export let onToggle: () => void;
	export let onToggleGestion: () => void;
	export let onUpload: (f: File) => Promise<string>;
	export let onRemove: (url: string) => Promise<string[] | void>;
	export let onStatut: (statut: string) => void;
	export let onSupprimer: () => void;
	export let onModifier: () => void;
	export let onRepondre: (contenu: string) => void;
	export let onSupprimerReponse: (id: number) => void;
	export let onSignalerAnnonce: () => void;
	export let onSignalerReponse: (id: number) => void;

	//  ⚠️ Le serveur refait ce contrôle (`_can_manage`) : ce qui suit n'est qu'un
	//  confort d'écran. Une interface qui cache un bouton n'a jamais protégé quoi
	//  que ce soit (`standards/03` §1).
	$: peutModifier = annonce.est_auteur;
	$: peutSupprimer = annonce.est_auteur || estCS || estAdmin;
</script>

<!--  🗂️ QUAND puis QUOI, dans la colonne de gauche — la carte d'affaire est le
      standard du site (10/10/2026). Le TYPE (vente, don, recherche) est ce qui
      classe une annonce : il quitte donc la ligne des tags, et la date n'est
      plus passée à l'en-tête — un seul fait, une place. Sa teinte se lit sur
      `data-type-annonce` (`normes.css`). -->
<CarteListe
	id="annonce-{annonce.id}"
	quand={annonce.cree_le}
	classe={classementAnnonce(annonce.type_annonce)}
	{expanded}
	archive={annonce.archivee}
	onDeplier={onToggle}
	data-type-annonce={annonce.type_annonce}
>
	<!--  Titre sur sa propre ligne, l'aperçu, puis les tags : la norme de toutes
	      les cartes du site. Elle vit dans `EnteteCarte`. -->
	<EnteteCarte titre={annonce.titre} basculable on:toggle={onToggle}>
		<svelte:fragment slot="titre-suffixe">
			<BadgeNouveau le={annonce.cree_le} si={!annonce.archivee} />
		</svelte:fragment>

		<svelte:fragment slot="tags">
			<Badge teinte={statutAnnonceClass(annonce.statut)}>{statutAnnonceLabel(annonce.statut)}</Badge
			>
			<span class="badge badge-gray">{categorieAnnonceLabel(annonce.categorie)}</span>
			<!--  🔹 puis QUI LA LIT — l'ordre de la carte d'affaire (#1373). La
			      pastille bleue a remplacé le badge orange des destinataires, arbitré
			      par l'utilisateur le 27/09/2026 ; elle se tait quand tout le monde lit. -->
			<BadgePerimetre perimetre={annonce.perimetre_cible} />
			<PastilleLecture cible={annonce} />
			{#if annonce.prix !== null && annonce.prix !== undefined}
				<span class="annonce-prix"
					>{fmtMontant(annonce.prix)}{#if annonce.negotiable}&nbsp;<span
							class="badge badge-gray annonce-nego">Négociable</span
						>{/if}</span
				>
			{:else if annonce.type_annonce === 'don'}
				<span class="annonce-prix annonce-gratuit">Gratuit</span>
			{/if}
			<!--  ✍️ puis ✨ en fin de ligne, comme partout. Le nom est celui que
			      l'API sert déjà à tout lecteur (le contact, lui, reste au corps). -->
			<AuteurCarte nom={nomAffiche(annonce.auteur_prenom, annonce.auteur_nom)} />
			<MarqueIA assiste={annonce.assiste_ia} />
		</svelte:fragment>

		<!--  ✏️ AVANT 🗑️ — l'ordre des icônes est celui des tickets, qui sert de
		      référence au site. Elles vivent dans l'EN-TÊTE et non dans le corps :
		      une action qu'il faut déplier pour trouver n'existe pas (signalé à
		      l'écran le 18/08/2026, alors que l'édition venait d'être livrée).
		      `stopPropagation` est conservé par prudence : il ne sert plus depuis que
		      le geste est le titre, mais il ne coûte rien et protégerait d'un futur
		      conteneur redevenu cliquable. -->
		<svelte:fragment slot="actions">
			<!--  🔗 EN PREMIER, et c'est délibéré : c'est la seule action que TOUT le
			      monde a. Placée entre ✏️ et 🗑️, sa position dépendrait des droits du
			      lecteur — elle sauterait d'un cran selon qu'on peut modifier ou non. -->
			<BoutonLien ancre="annonce-{annonce.id}" quoi="l'annonce" />
			{#if peutModifier}
				<button
					class="btn-icon"
					title="Modifier"
					aria-label="Modifier l'annonce"
					aria-pressed={formulaireOuvert}
					on:click|stopPropagation={onModifier}><IconeAction icone="pencil" /></button
				>
			{/if}
			{#if peutSupprimer}
				<button
					class="btn-icon-danger"
					title="Supprimer"
					aria-label="Supprimer l'annonce"
					on:click|stopPropagation={onSupprimer}><IconeAction icone="trash-2" /></button
				>
			{/if}
		</svelte:fragment>

		<!--  🔴 L'aperçu passe par l'EN-TÊTE (18/09/2026) : c'est ce qui permet aux
		      pastilles de descendre en dernière ligne, comme sur le fil d'activité.
		      Rendu après `</EnteteCarte>`, il était le FRÈRE de l'en-tête — aucun
		      ordre CSS ne fait passer un élément sous le frère d'un autre parent. -->
		<svelte:fragment slot="apercu">
			{#if !expanded}
				<!--  Quatre lignes d'aperçu et la vignette à DROITE — le composant partagé
				      des actualités et des tickets. La carte n'affichait que son titre. -->
				<ApercuCarte contenu={annonce.description} photos={annonce.photos ?? []} dansLigne />
			{/if}
		</svelte:fragment>
	</EnteteCarte>

	{#if expanded}
		<!--  Le corps ne referme pas la carte : on referme par l'en-tête. Sans cela,
		      impossible de sélectionner du texte, et un clic sur une photo ou un
		      formulaire referme ce qu'on lisait (ux-patterns §3). -->
		<div
			class="carte-corps annonce-body"
			role="presentation"
			on:click|stopPropagation
			on:keydown|stopPropagation
		>
			{#if formulaireOuvert}
				<slot name="formulaire" />
			{:else}
				<div class="rich-content annonce-texte">{@html safeHtml(annonce.description)}</div>

				<!-- Les photos en grand, pour TOUT LE MONDE — auteur compris. Elles lui
				     étaient refusées (`&& !annonce.est_auteur`) : il n'avait que la grille
				     d'édition ci-dessous, des vignettes faites pour ajouter et retirer, pas
				     pour regarder. Deuxième fois que ce bloc privait quelqu'un de ses
				     photos : la condition précédente (`> 1 || est_auteur`) privait le
				     LECTEUR d'une annonce à une seule photo. Le défaut avait changé de
				     victime, pas disparu. `npm run lint:fichiers` échoue désormais sur une
				     galerie conditionnée à l'identité. -->
				{#if annonce.photos?.length}
					<PiecesJointes urls={annonce.photos} format="grand" />
				{/if}

				<!-- L'édition des photos, sur geste explicite : c'est le pattern du
				     produit. Elle reste ICI et non dans le formulaire — l'endpoint exige
				     l'identifiant de l'annonce, dette `api` déclarée et suivie (#441).
				     La rouvrir dans le formulaire donnerait deux chemins concurrents. -->
				{#if annonce.est_auteur}
					<button
						class="btn btn-sm btn-outline annonce-gerer"
						aria-expanded={gestionOuverte}
						on:click={onToggleGestion}
					>
						<!--  Le chevron `›` du site, qui TOURNE — pas `▲/▼`, qui SAUTE
						      d'un glyphe à l'autre et que toutes les autres cartes ont
						      abandonné (ux-patterns §3). -->
						<span
							class="chevron annonce-gerer-chevron"
							class:open={gestionOuverte}
							aria-hidden="true">›</span
						>
						Gérer les photos{annonce.photos?.length ? ` (${annonce.photos.length})` : ''}
					</button>
					{#if gestionOuverte}
						<FichiersUpload
							urls={annonce.photos ?? []}
							max={MAX_PHOTOS_ANNONCE}
							mode="photos"
							upload={onUpload}
							remove={onRemove}
						/>
					{/if}
				{/if}

				<div class="annonce-contact">
					{#if annonce.auteur_email}
						<small
							>&#x1F4EC; <a href="mailto:{annonce.auteur_email}"
								>{nomAffiche(annonce.auteur_prenom, annonce.auteur_nom)}</a
							></small
						>
					{:else}
						<small>&#x1F464; {nomAffiche(annonce.auteur_prenom, annonce.auteur_nom)}</small>
					{/if}
				</div>

				<!--  Le raccourci de workflow : des PASTILLES, jamais un `<select>` nu
				      (R3 / #423). Le `<select>` d'origine était le dernier du site.
				      Il double le formulaire de correction, et c'est assumé : changer
				      l'état est le geste le plus fréquent sur une annonce, il ne doit
				      pas coûter l'ouverture d'un formulaire. Les deux chemins écrivent
				      le MÊME fait, et le serveur l'horodate d'une seule façon. -->
				{#if annonce.est_auteur}
					<div class="annonce-workflow">
						<span class="annonce-workflow-titre" id="wf-annonce-{annonce.id}"
							>Où en est cette annonce ?</span
						>
						<WorkflowPastilles
							options={OPTIONS_STATUT_ANNONCE}
							valeur={annonce.statut}
							idTitre="wf-annonce-{annonce.id}"
							on:choisir={(e) => onStatut(e.detail)}
						/>
					</div>
				{/if}

				{#if !annonce.est_auteur}
					<div class="annonce-signaler">
						<button
							class="signaler-inline"
							title="Signaler cette annonce au conseil syndical"
							aria-label="Signaler cette annonce"
							on:click={onSignalerAnnonce}>&#x1F6A9; Signaler l'annonce</button
						>
					</div>
				{/if}

				<Reponses
					reponses={annonce.reponses ?? []}
					{currentUserId}
					isCS={estCS}
					placeholder="Une question sur cette annonce ?"
					onSubmit={onRepondre}
					onDelete={onSupprimerReponse}
					onReport={onSignalerReponse}
				/>
			{/if}
		</div>
	{/if}
</CarteListe>

<style>
	/*  Conteneur, gouttière, survol, archive et la TEINTE du type : `CarteListe`
	    et `normes.css`. L'en-tête, ses tags et leur repli : `EnteteCarte`.
	    L'aperçu et sa vignette : `ApercuCarte`. Ne reste ici que ce qui est
	    propre à une annonce. */
	.annonce-prix {
		font-weight: 700;
		color: var(--color-primary);
		white-space: nowrap;
	}
	.annonce-gratuit {
		color: var(--color-success);
	}
	.annonce-nego {
		font-weight: 500;
	}

	.annonce-body {
		padding: 0.75rem 1rem 1rem;
		border-top: 1px solid var(--color-border);
	}
	/*  L'entrée du corps (`.carte-corps`) et la rotation du chevron vivent dans
	    la charte depuis leur généralisation (24/09/2026) : ne reste ici que la
	    taille du chevron, posé dans un bouton et non dans un en-tête. */
	.annonce-gerer-chevron {
		font-size: 1rem;
		color: inherit;
	}
	.annonce-texte {
		font-size: var(--fs-base);
		line-height: 1.6;
		margin-bottom: 0.5rem;
	}
	.annonce-gerer {
		margin: 0.25rem 0 0.5rem;
	}
	.annonce-contact {
		margin: 0.6rem 0;
	}
	.annonce-contact a {
		color: var(--color-primary);
	}

	.annonce-workflow {
		margin-top: 0.75rem;
	}
	.annonce-workflow-titre {
		display: block;
		font-size: var(--fs-sm);
		font-weight: 600;
		color: var(--color-text-muted);
		margin-bottom: 0.35rem;
	}

	.annonce-signaler {
		margin-top: 0.4rem;
	}
</style>
