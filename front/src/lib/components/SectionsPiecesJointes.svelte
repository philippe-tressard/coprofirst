<!--
  La section **Pièces jointes** du cadre, écrite une fois.

  Elle l'était deux fois : `ChampsCommuns` (six formulaires de création) et
  `EvolForm` (le fil de quatre entités), à l'identique au caractère près.

  ## 🔴 UNE section depuis le 21/09/2026 (#1095), deux auparavant

  Le cadre #430 disait, en rouge : *« Deux sections, jamais une seule […] les
  fusionner créerait une dixième section que rien ne déclare. »* **L'utilisateur
  a tranché l'inverse le 20/09/2026** : une seule section, photos et/ou
  documents.

  ⚠️ Et la clause du cadre a été réécrite dans le MÊME lot (`entites/types.ts`),
  sinon elle réclamerait encore la séparation qu'on vient d'abandonner — et
  quelqu'un la rétablirait de bonne foi. Ce n'est pas la règle qui s'assouplit,
  c'est la TABLE qui a changé : la fusion se déclare, donc elle se contrôle.

  ## Une section, deux réservoirs — et c'est le serveur qui l'impose

  Le régime de téléversement est un **paramètre de l'objet** : une publication
  manipule des `Document` avec un identifiant (l'écran fournit alors son propre
  contrôle par le créneau `documents`), une évolution ne connaît qu'une liste
  d'URLs. Le modèle distingue `photos_urls` et les `Document`, et ce lot ne
  touche pas au modèle.

  Ce qui s'uniformise est la SECTION — son rang, son intitulé unique, et le fait
  que **tout fichier y porte un nom affiché**.

  ## 🔴 UN SEUL contrôle, et dix pièces jointes indifféremment (21/09/2026)

  La première livraison fusionnait la section et gardait **deux boutons** —
  « Ajouter une photo », « Ajouter un document » — avec deux compteurs `0/10`.
  Signalé à l'écran : *« on ne peut pas ajouter 10 PJ de photos ou docs
  indifféremment »*. C'était juste : une section unique avec deux portes n'est
  pas une section unique, c'est deux sections sans titre.

  ⚠️ **Les deux réservoirs restent**, parce que le serveur les distingue. Mais
  ils ne se voient plus : `separerFichiers` (`#lib/fichiers`, qui existait déjà)
  range chaque URL selon son type, et les appelants continuent de recevoir
  `photos` et `documents` sans rien changer.

  🔴 Le plafond est celui de la SECTION — `MAX_FICHIERS`, dix au total — et non
  dix par réservoir. C'est ce que « indifféremment » veut dire.

  🔴 **Le gain demandé** (20/09/2026) : le champ « nom affiché » vaut désormais
  pour une photo comme pour un PDF. Il ne coûte aucune migration — `avecLibelle`
  renomme le FICHIER avant l'envoi (`FichiersUpload.renommer`), il ne dépend
  d'aucune colonne.
-->
<script lang="ts">
	import FichiersUpload from '#lib/components/FichiersUpload.svelte';
	import SectionFormulaire from '#lib/components/SectionFormulaire.svelte';
	import { SECTIONS_LIBELLE } from '#lib/entites/types.ts';
	import { ACCEPT_PHOTOS, MAX_FICHIERS, separerFichiers } from '#lib/fichiers.ts';

	/** Préfixe des identifiants — l'écran en ouvre parfois plusieurs à la fois. */
	export let idPrefixe: string;

	/**
	 *  🔴 Le PLIAGE, transmis par l'appelant (22/09/2026, signalé deux fois à
	 *  l'écran : *« PJ toujours déplié »*).
	 *
	 *  Ce composant porte sa `SectionFormulaire` : le pliage déclaré dans la
	 *  table ne l'atteignait donc pas, et la section restait ouverte quoi que
	 *  dise `pliee: true`. C'est l'angle mort des composants **porteurs** — le
	 *  même qui avait rendu l'ordre des sections incontrôlable (#1124).
	 *
	 *  ⚠️ `valeurModifiee` n'est pas une option : une section pliée qui
	 *  cacherait des pièces déjà jointes serait pire que dépliée.
	 */
	export let pliable = false;

	export let avecPhotos = false;
	export let photos: string[] = [];

	export let avecDocuments = false;
	export let documents: string[] = [];
	/**  `'interne'` : la liste d'URLs ci-dessus · `'slot'` : l'écran fournit son
	 *   propre contrôle (documents d'une publication, qui ont un identifiant). */
	export let documentsControle: 'interne' | 'slot' = 'interne';
	/** Téléversement différé — les fichiers attendent que l'objet existe, et
	 *  l'écran les téléverse après création. Il vaut pour la SECTION, photos
	 *  comme documents : il s'appelait `documentsDifferes`, sans aucun appelant,
	 *  et la petite annonce en a eu besoin pour ses PHOTOS (#1186). */
	export let differes = false;
	export let fichiersDifferes: File[] = [];
	/** Plafond de la section — `MAX_FICHIERS` sauf quand l'objet en fixe un plus bas. */
	export let max: number = MAX_FICHIERS;
	/**  Le libellé que l'auteur donne au document — vide, c'est le nom du fichier
	 *   qui sert. L'appelant le lit au moment d'envoyer (même règle de repli que
	 *   les contrats : `libelle.trim() || fichier.name`). */
	export let documentsLibelle = '';
	/**  Le même, pour une photo (#1095). **Distinct** de `documentsLibelle` et ce
	 *   n'est pas un détail : partagé, taper un nom pour une photo écraserait
	 *   celui d'un document en attente, dans la même section et sous les yeux de
	 *   l'auteur. */
	export let photosLibelle = '';
	/**  Le suffixe d'identifiant des documents. ⚠️ Il diffère entre les deux
	 *   appelants (`-documents` et `-docs`) : le figer casserait le `for` d'un
	 *   libellé existant, ce que `lint:labels` refuse à juste titre. */
	export let idDocuments = 'documents';

	/**  UN seul contrôle dès que les deux réservoirs sont gérés ICI. Le cas
	 *   `slot` garde ses deux portes : l'écran y fournit son propre contrôle de
	 *   `Document` (avec identifiants), et le fondre demanderait de faire passer
	 *   les images par `POST /documents` — un changement de circuit, pas
	 *   d'affichage. Il ne concerne que l'ÉDITION d'une actualité. */
	$: unSeulControle = avecPhotos && avecDocuments && documentsControle === 'interne';

	//  Ce que la section annonce quand elle est pliée : un nombre, pas un mot
	//  vide. « Aucune » se lit d'un coup d'œil et évite de déplier pour rien.
	$: nbFichiers = photos.length + documents.length;
	$: resumeFichiers =
		nbFichiers === 0 ? 'Aucune' : `${nbFichiers} fichier${nbFichiers > 1 ? 's' : ''}`;

	/**  La liste que l'auteur voit : photos et documents mêlés, dans l'ordre où
	 *   il les a posés. */
	let toutes: string[] = [];
	let amorce = false;
	$: if (!amorce && unSeulControle) {
		amorce = true;
		toutes = [...photos, ...documents];
	}
	//  🔴 La répartition vers les deux réservoirs du serveur, par
	//  `separerFichiers` — qui existait déjà dans `#lib/fichiers`.
	//
	//  ⚠️ Les gardes d'égalité ne sont pas décoratives : sans elles, réaffecter
	//  `photos` relance ce bloc, qui réaffecte `photos`… Svelte boucle jusqu'à
	//  l'erreur « infinite loop detected ».
	$: if (unSeulControle) repartir(toutes);
	function repartir(liste: string[]) {
		const { photos: p, documents: d } = separerFichiers(liste);
		if (p.join('|') !== photos.join('|')) photos = p;
		if (d.join('|') !== documents.join('|')) documents = d;
	}
</script>

<!--  ⚠️ L'intitulé ne s'écrit PAS ici : il vient de `SECTIONS_LIBELLE`, où la
      table le déclare une fois. L'écrire en dur rouvrirait la divergence que
      `lint:etats` existe pour refuser.

      Le `pour` vise les photos quand elles sont là, les documents sinon : un
      libellé de section pointe le PREMIER champ qu'il introduit. -->
{#if avecPhotos || avecDocuments}
	<SectionFormulaire
		titre={SECTIONS_LIBELLE.pieces_jointes}
		{pliable}
		valeurModifiee={photos.length > 0 || documents.length > 0}
		resume={resumeFichiers}
		pour="{idPrefixe}-{avecPhotos ? 'photos' : idDocuments}"
	>
		{#if unSeulControle}
			<!--  🔴 UN contrôle, dix pièces jointes indifféremment (#1095, 21/09).
			      La répartition entre les deux réservoirs du serveur est faite ici
			      par `separerFichiers` — les appelants reçoivent `photos` et
			      `documents` comme avant, sans rien savoir de la fusion. -->
			<div class="field champ-large">
				<FichiersUpload
					id="{idPrefixe}-pieces"
					bind:urls={toutes}
					mode="mixte"
					titre=""
					avecLibelle
					bind:libelleFichier={photosLibelle}
					differe={differes}
					bind:fichiers={fichiersDifferes}
					{max}
					size={80}
				/>
			</div>
		{:else}
			{#if avecPhotos}
				<div class="field champ-large">
					<FichiersUpload
						id="{idPrefixe}-photos"
						bind:urls={photos}
						titre=""
						label="Ajouter une photo"
						accept={ACCEPT_PHOTOS}
						avecLibelle
						bind:libelleFichier={photosLibelle}
						differe={differes}
						bind:fichiers={fichiersDifferes}
						{max}
						size={80}
					/>
				</div>
			{/if}
			{#if avecDocuments}
				<div class="field champ-large">
					{#if documentsControle === 'slot'}
						<slot name="documents" />
					{:else}
						<!--  `avecLibelle` : le champ que les CONTRATS portaient seuls jusqu'au
				      11/09/2026, remonté dans `FichiersUpload` et rendu à tous ses
				      appelants. Un document de ticket ne portait que le nom que son
				      auteur lui avait donné sur son disque. -->
						<FichiersUpload
							id="{idPrefixe}-{idDocuments}"
							mode="documents"
							titre=""
							avecLibelle
							bind:libelleFichier={documentsLibelle}
							differe={differes}
							bind:urls={documents}
							bind:fichiers={fichiersDifferes}
						/>
					{/if}
				</div>
			{/if}
		{/if}
	</SectionFormulaire>
{/if}
