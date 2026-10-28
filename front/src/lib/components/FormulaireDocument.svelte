<!--
  L'OBJET « formulaire de document » — titre, périmètre, fichier(s), et le cadre
  qui va avec le geste.

  ## Pourquoi il existe (31/08/2026)

  L'écran Résidence portait **six** formulaires — plan, règlement, CR d'AG,
  rapport de diagnostic, et les deux éditions — tous bâtis du même vocabulaire :
  un titre, parfois un périmètre, un fichier, et deux boutons. Ils avaient été
  écrits l'un après l'autre, par copie, et la copie s'était déjà payée :

  🔴 **La modale « Ajouter un plan » liait son sélecteur de périmètre à
  `newCrAgPerimetre`** — la variable du CR d'AG. Choisir un périmètre sur un plan
  ne faisait donc rien pour le plan (`addPlan` envoyait `newPlanPerimetre`, un
  reliquat que plus aucun contrôle ne modifiait depuis #470) et **pré-remplissait
  en douce le formulaire d'AG**. Rien ne levait : les deux variables existaient,
  les deux types concordaient, `svelte-check` était vert.

  C'est la duplication qui produit ce défaut-là, et lui seul : deux formulaires
  distincts n'auraient pas pu échanger leur état.

  ## Ce qu'il porte, et dans l'ordre du cadre

  1. **Titre** — et lui seul (`ux-patterns` §0) ;
  2. `<slot name="specifiques" />` — ce qui qualifie CE document (année et date
     d'AG, date de diagnostic) ;
  4. **Périmètre**, par `PerimetrePicker` — jamais un sélecteur écrit à la main ;
  6. `<slot name="description" />` — la synthèse d'un rapport ;
  8. **Fichier(s)** à la création ; **Pièces jointes** en édition, quand la fiche
     en porte (`PiecesJointesFiche` : une seule liste, le fichier de la fiche en
     tête, dix en tout — 11/10/2026).

  ⚠️ Les numéros sautent parce que ce sont ceux du cadre : un document n'a ni
  workflow, ni destinataires, ni diffusion. Les garder rend l'ordre vérifiable.

  ## Le cadre suit le GESTE, et c'est le composant qui le pose

  Création → `FormulaireCreation` (la boîte dans la page, #367) ·
  Édition → `Modale` (#640). Le choix du cadre vit dans `CadreFormulaire`, écrit
  une fois pour les six formulaires concernés (02/09/2026) ; ici on ne déclare que
  le GESTE, par `edition`.

  ⚠️ Ce fichier passait `fermetureAuFond={false}` avec un commentaire d'incident.
  C'était **redondant** : `Modale` l'impose dès que `edition` est posé
  (`fondFermant = fermetureAuFond && !edition && …`).
-->
<script lang="ts" context="module">
	/** Compteur d'instances — voir `uid` plus bas : il remplace `Math.random()`. */
	let compteur = 0;
</script>

<script lang="ts">
	import { createEventDispatcher } from 'svelte';

	import CadreFormulaire from '#lib/components/CadreFormulaire.svelte';
	import SectionFormulaire from '#lib/components/SectionFormulaire.svelte';
	import SectionPerimetre from '#lib/components/SectionPerimetre.svelte';
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';
	import FichiersUpload from '#lib/components/FichiersUpload.svelte';
	import PiecesJointesFiche, { type PiecesFiche } from '#lib/components/PiecesJointesFiche.svelte';
	import { MAX_FICHIERS } from '#lib/fichiers.ts';

	/** L'intitulé du formulaire — en-tête de la boîte, ou titre de la modale. */
	export let intitule: string;
	/**  Le geste : `false` on crée (boîte dans la page), `true` on corrige un
	 *   objet existant (modale). C'est la seule chose qui change de cadre. */
	export let edition = false;

	/** Section 1 — le titre, et lui seul. */
	export let titre = '';
	export let libelleTitre = 'Titre';
	/**  Un titre facultatif se marque en ne mettant PAS d'astérisque, et en
	 *   disant ce qui se passe sans lui — jamais « (optionnel) » (cadre R3). */
	export let titreRequis = true;
	export let placeholderTitre = '';
	export let aideTitre = '';

	/** Section 4 — `[]` signifie « toute la copropriété », ce qui est valide ici. */
	export let avecPerimetre = false;
	export let perimetre: string[] = [];

	/** Section 8 — un fichier, ou plusieurs. */
	export let avecFichier = true;
	export let multiple = false;
	/**  Les `File` retenus : `FichiersUpload` en mode DIFFÉRÉ — le document
	 *   n'existe pas encore, l'appelant les envoie à l'enregistrement. */
	export let fichiers: File[] = [];
	export let libelleFichier = 'Fichier';

	/**  Section 8 « Pièces jointes » d'une fiche de Ma résidence : le fichier
	 *   principal et les annexes. `null` = la section n'existe pas pour ce
	 *   formulaire (le dépôt d'un document, qui porte déjà son « Fichier »). */
	export let piecesJointes: PiecesFiche | null = null;
	/**  Les annexes choisies AVANT que la fiche existe (une règle qu'on crée) :
	 *   l'appelant les attache après l'enregistrement (`attacherApres`). */
	export let annexesEnAttente: File[] = [];
	/**  Facultative, donc PLIÉE — la règle du cadre (`ux-patterns` §0, « obligatoire
	 *   → déplié · facultatif → plié »). Un document n'a pas de déclaration
	 *   d'entité où la lire (`check-pliage-transmis`, HORS_CADRE) : elle s'écrit ici,
	 *   et `valeurModifiee` la rouvre dès qu'un fichier y est. */
	const PIECES_JOINTES_PLIEES = true;
	//  ⚠️ Plus de liste `accept` écrite ici (27/09/2026) : elle disait « PDF et
	//  images » quand le serveur accepte aussi Word, Excel et texte (famille
	//  `document_prive`). Le mode `mixte` lit `ACCEPT_FICHIERS` dans `#lib/fichiers`,
	//  comme les documents des contrats et des affaires — même route serveur.

	/** L'enregistrement est-il en cours, et peut-on l'engager ? */
	export let enregistrement = false;
	export let complet = true;

	const dispatch = createEventDispatcher<{ annuler: void; enregistrer: void }>();

	//  Un identifiant propre à CHAQUE instance : deux formulaires ouverts sur la
	//  même page partageraient sinon le `for` de leurs libellés, et cliquer sur
	//  l'un donnerait le focus à l'autre — ce que `lint:labels` ne voit pas,
	//  puisque chaque `for` a bien sa cible.
	//
	//  ⚠️ Un compteur, pas `Math.random()` : le rendu serveur et le rendu client
	//  doivent produire le MÊME identifiant, sinon l'hydratation se plaint et
	//  remplace le nœud — un champ en cours de saisie y perdrait son contenu.
	const uid = `fd-${++compteur}`;
</script>

<CadreFormulaire {edition} titre={intitule} on:fermer={() => dispatch('annuler')}>
	<!--  🔴 Les SECTIONS du cadre (#1329) : titre, périmètre, fichier étaient des
	      champs à plat, le périmètre dans un `.field` qui réécrivait sa section. -->
	<SectionFormulaire
		titre={libelleTitre}
		requis={titreRequis}
		rempli={!!titre.trim()}
		pour="{uid}-titre"
		premiere
	>
		<div class="field">
			<input id="{uid}-titre" type="text" bind:value={titre} placeholder={placeholderTitre} />
			{#if aideTitre}<span class="aide">{aideTitre}</span>{/if}
		</div>
	</SectionFormulaire>

	<slot name="specifiques" />

	{#if avecPerimetre}
		<!--  🔴 `PerimetrePicker`, l'objet du site — plus un sélecteur écrit à la
		      main (#470). `requis={false}` : un document qui concerne toute la
		      copropriété ne cible rien, et l'absence est ici une réponse valide. -->
		<SectionPerimetre idPrefixe={uid} bind:perimetre />
	{/if}

	<slot name="description" />

	{#if avecFichier}
		<SectionFormulaire
			titre={libelleFichier}
			requis
			rempli={fichiers.length > 0}
			pour="{uid}-fichier"
		>
			<!--  🔴 `FichiersUpload`, le sélecteur du site (27/09/2026, #1329) : c'était
			      le dernier `<input type="file">` nu — « Parcourir… » du navigateur à
			      côté du bouton 📎 et des pastilles de tous les autres dépôts. Le mode
			      DIFFÉRÉ retient les fichiers ; le nom choisi s'affiche en pastille, et
			      se retire d'un clic. 🔒 `npm run lint:fichiers`. -->
			<div class="field">
				<FichiersUpload
					id="{uid}-fichier"
					titre=""
					mode="mixte"
					differe
					max={multiple ? MAX_FICHIERS : 1}
					bind:fichiers
				/>
			</div>
		</SectionFormulaire>
	{/if}

	{#if piecesJointes}
		<PiecesJointesFiche
			idPrefixe={uid}
			pliable={PIECES_JOINTES_PLIEES}
			{...piecesJointes}
			bind:fichiersEnAttente={annexesEnAttente}
		/>
	{/if}

	<!--  ⚠️ `soumission={false}` : pas de `<form>` ici non plus. -->
	<PiedFormulaire
		enCours={enregistrement}
		desactive={!complet}
		soumission={false}
		on:annule={() => dispatch('annuler')}
		on:enregistre={() => dispatch('enregistrer')}
	/>
</CadreFormulaire>
