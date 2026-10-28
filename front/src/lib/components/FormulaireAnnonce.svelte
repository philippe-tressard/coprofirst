<!--
  Le formulaire d'une petite annonce — celui qu'on remplit pour la DÉPOSER, et
  celui qu'on rouvre pour la CORRIGER. Un seul fichier pour les deux gestes.

  Extrait de `sondages/+page.svelte` le 16/08/2026 (plafond de modularité), rendu
  **paramétrable** le 18/08/2026 sur demande : *« pour les petites annonces tu
  peux ajouter le périmètre et il manque le mode édition »*.

  ## Le mode édition n'existait pas du tout

  Une fois l'annonce déposée, on pouvait changer son statut, gérer ses photos, la
  supprimer — mais **pas corriger une faute de frappe, ni baisser un prix**. Le
  seul recours était supprimer et redéposer, ce qui perdait les réponses des
  voisins.

  Ce n'était pas une contrainte serveur : `PATCH /annonces/{id}` existait, avec
  ses sept champs, **et personne ne l'appelait**.

  ## Le périmètre : une absence de notion qu'un ÉCRAN avait décrétée

  L'en-tête de ce fichier disait, jusqu'à aujourd'hui :

  > « L'annonce n'a ni périmètre ni destinataires : elle s'adresse à tous les
  >   résidents par nature. »

  🔴 C'est ce que `sansObjet` sert à dire, et **ça se déclare dans l'entité, pas
  dans un commentaire de formulaire** : un commentaire n'est lu par aucun
  contrôle. Le périmètre est ouvert (migration 0151) ; les destinataires, eux,
  restent `sansObjet` — et cette fois c'est écrit là où `lint:etats` le lit.

  ## Ce qui n'est PAS gouverné par `modeEdition`

  Aucune section. Les six props de `ChampsCommuns` passent par
  `sectionPresente(ANNONCE, etat, …)`, et `npm run lint:etats` refuse qu'on
  remette une condition en dur. Le mode ne décide plus que du **geste** : `POST`
  ou `PATCH`, et l'intitulé de la boîte.

  ⚠️ **Les PHOTOS ne sont pas ici, et c'est une dette déclarée** (motif `api`,
  #441) : `POST /annonces/{id}/photo` exige l'identifiant de l'annonce. Elles se
  gèrent depuis la carte, dans les deux gestes — la rouvrir ici en correction
  donnerait deux chemins concurrents vers la même liste.
-->
<script lang="ts">
	import ChoixPastilles from '#lib/components/ChoixPastilles.svelte';
	import { contexteAssistant, perimetreContexte } from '#lib/assistant.ts';
	import { createEventDispatcher } from 'svelte';
	import CadreFormulaire from '#lib/components/CadreFormulaire.svelte';
	import SectionFormulaire from '#lib/components/SectionFormulaire.svelte';
	import SectionTitre from '#lib/components/SectionTitre.svelte';
	import ChampsCommuns from '#lib/components/ChampsCommuns.svelte';
	import SectionWorkflow from '#lib/components/SectionWorkflow.svelte';
	import {
		CATEGORIES_ANNONCE,
		MAX_PHOTOS_ANNONCE,
		OPTIONS_STATUT_ANNONCE,
		TYPES_ANNONCE,
		categorieAnnonceLabel,
		typeAnnonceLabel,
	} from '#lib/annonces.ts';
	import { annonces as annoncesApi, type PetiteAnnonce } from '#lib/api/index.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import { perimetreDefautListe, nombreOuNull } from '#lib/utils.ts';
	import type { Etat } from '#lib/entites/types.ts';
	import { sectionPresente } from '#lib/entites/types.ts';
	import { pliageDe, requisDe } from '#lib/pliage.ts';
	import { ANNONCE } from '#lib/entites/annonce.ts';
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';

	/**  L'annonce à CORRIGER, avec ses valeurs déjà saisies. `null` (défaut) =
	 *   dépôt. Le mode ne change pas pendant la vie du composant : l'appelant la
	 *   remonte à neuf (`{#key}`) quand il passe d'une annonce à l'autre — même
	 *   contrat que `FormulaireActualite` et `FormulaireTicket`. */
	export let annonce: PetiteAnnonce | null = null;

	const modeEdition = annonce !== null;

	/**  L'état du cadre #430 que ce formulaire rend. C'est LUI qui décide des
	 *   sections — voir `#lib/entites/annonce`, qui porte chaque divergence avec
	 *   son motif. */
	const etat: Etat = modeEdition ? 'edition' : 'creation';

	const dispatch = createEventDispatcher<{
		cree: PetiteAnnonce;
		modifie: PetiteAnnonce;
		annule: void;
	}>();

	//  ── 1. Titre ────────────────────────────────────────────────────────────
	let titre = annonce?.titre ?? '';

	//  ── 2. Champs spécifiques : ce qui décrit l'objet ───────────────────────
	let typeAnnonce = annonce?.type_annonce ?? 'vente';
	let categorie = annonce?.categorie ?? 'divers';
	let prix = annonce?.prix !== null && annonce?.prix !== undefined ? String(annonce.prix) : '';
	let negotiable = annonce?.negotiable ?? false;

	//  ── 3. Workflow ─────────────────────────────────────────────────────────
	//  Absent à la CRÉATION (motif `geste`) : une annonce qu'on dépose est en
	//  cours par construction. La déclaration le dit, ce fichier ne le décide pas.
	let statut: string = annonce?.statut ?? 'en_cours';

	//  ── 4 à 9 ───────────────────────────────────────────────────────────────
	//  Copie défensive du périmètre : le tableau vient de l'annonce affichée dans
	//  la liste. Lié tel quel, une sélection abandonnée resterait visible sur la
	//  carte alors que rien n'a été enregistré.
	let perimetreCible: string[] = [...(annonce?.perimetre_cible ?? perimetreDefautListe())];
	//  Section 5 (#782). Vide = tous les résidents, des DEUX côtés : c'est ce
	//  que `concerneTousLesResidents` lit ici et `public_cible_visible` côté
	//  serveur. Ne pas initialiser à une liste de codes « par défaut » —
	//  ce serait choisir un ciblage à la place de l'auteur.
	let publicCible: string[] = [...(annonce?.public_cible ?? [])];
	let description = annonce?.description ?? '';
	//  Vrai dès qu'une proposition de l'assistant IA a été appliquée (#985).
	let assisteIA = false;
	//  Ce que l'assistant IA reçoit pour COMPRENDRE le texte — à ne pas réécrire
	//  (#985) : type, catégorie, périmètre.
	$: assistant = contexteAssistant('petite annonce', {
		Type: typeAnnonceLabel(typeAnnonce),
		Catégorie: categorieAnnonceLabel(categorie),
		Périmètre: perimetreContexte(perimetreCible),
	});
	let contactVisible = annonce?.contact_visible ?? true;

	//  ── 8. Pièces jointes, au DÉPÔT (#1186) ─────────────────────────────────
	//  `POST /annonces/{id}/photo` réclame l'identifiant : les photos attendent
	//  ici (mode différé de `FichiersUpload`) et partent APRÈS la création, par
	//  l'endpoint qui les réduit et les compte. Aucune seconde porte d'écriture.
	let photosEnAttente: File[] = [];

	let submitting = false;

	const titreBoite = modeEdition ? ANNONCE.libelleModifier : ANNONCE.libelleNouveau;

	function reinitialiser() {
		titre = '';
		description = '';
		typeAnnonce = 'vente';
		categorie = 'divers';
		prix = '';
		negotiable = false;
		contactVisible = true;
		perimetreCible = perimetreDefautListe();
		photosEnAttente = [];
	}

	/**  Téléverse les photos retenues, une à une, sur l'annonce qui vient
	 *   d'exister. Rend la liste que le SERVEUR tient — pas celle qu'on croit
	 *   avoir envoyée — et dit combien ont échoué : l'annonce est publiée, une
	 *   photo refusée ne doit pas le faire croire annulé. */
	async function envoyerPhotos(id: number): Promise<{ photos: string[] | null; echecs: number }> {
		let photos: string[] | null = null;
		let echecs = 0;
		for (const fichier of photosEnAttente) {
			try {
				photos = (await annoncesApi.uploadPhoto(id, fichier)).photos;
			} catch (e) {
				echecs++;
				toast('error', messageErreur(e));
			}
		}
		return { photos, echecs };
	}

	async function enregistrer() {
		if (!titre.trim() || !description) {
			toast('error', 'Titre et description obligatoires');
			return;
		}
		//  Le prix ne concerne que la vente : le champ disparaît pour un don ou une
		//  recherche, et la valeur doit disparaître avec lui. Sans cette remise à
		//  zéro, passer une vente en don garderait le montant en base — la carte
		//  n'afficherait plus « Gratuit » mais l'ancien prix.
		const prixEnvoye = typeAnnonce === 'vente' ? nombreOuNull(prix) : null;
		submitting = true;
		try {
			const charge = {
				titre: titre.trim(),
				description,
				assiste_ia: assisteIA || undefined,
				type_annonce: typeAnnonce,
				categorie,
				prix: prixEnvoye,
				negotiable: typeAnnonce === 'vente' ? negotiable : false,
				contact_visible: contactVisible,
				perimetre_cible: perimetreCible,
				public_cible: publicCible,
				//  L'état ne part QU'EN correction : à la création, la section est
				//  absente et le serveur pose le défaut. L'envoyer quand même ferait
				//  écrire un `statut_change_le` pour une transition qui n'a pas eu lieu.
				...(modeEdition ? { statut } : {}),
			};
			if (annonce) {
				const maj = await annoncesApi.update(annonce.id, charge);
				toast('success', 'Annonce mise à jour');
				dispatch('modifie', maj);
				return;
			}
			const cree = await annoncesApi.create(charge);
			const { photos, echecs } = await envoyerPhotos(cree.id);
			if (photos) cree.photos = photos;
			reinitialiser();
			toast(
				'success',
				echecs
					? `Annonce publiée — ${echecs} photo${echecs > 1 ? 's' : ''} non jointe${echecs > 1 ? 's' : ''}, à ajouter depuis la carte`
					: 'Annonce publiée !',
			);
			dispatch('cree', cree);
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			submitting = false;
		}
	}
</script>

<!--
	Le cadre suit le GESTE (`ux-patterns` §14 bis) : boîte dans la page au dépôt,
	fenêtre à la correction. Le choix vit dans `CadreFormulaire`, écrit une fois
	pour les six formulaires concernés.

	🔴 Ce fichier était le SEPTIÈME écran de #640, et le seul jamais listé dans
	son « Reste » : il éditait DANS la carte, en remplaçant le corps de l'annonce.
	Le ticket citait deux écrans déjà conformes et oubliait celui-ci — c'est ce
	qui a décidé l'écriture de `lint:cadre-geste`, qui le recense désormais.
-->
<!--  `encadre` : la correction s'ouvre DANS la carte, qui est déjà le cadre —
      la carte dans la carte, relevée par l'audit (#1329, §14 ter). -->
<CadreFormulaire edition={modeEdition} encadre={!modeEdition} titre={titreBoite}>
	<form on:submit|preventDefault={enregistrer}>
		<!--  1. Titre. -->
		<SectionTitre
			id="annonce-titre-{annonce?.id ?? 'new'}"
			bind:valeur={titre}
			placeholder="Ex. Lave-linge Samsung presque neuf"
		/>

		<!--  2. Champs spécifiques de l'annonce. -->
		{#if sectionPresente(ANNONCE, etat, 'nature')}
			<SectionFormulaire
				titre="L'objet"
				requis={requisDe(ANNONCE, 'nature')}
				rempli={!!typeAnnonce && !!categorie}
			>
				<div class="form-grid">
					<!--  Trois valeurs : des pastilles, comme le filtre au-dessus (#1329). -->
					<ChoixPastilles
						options={TYPES_ANNONCE}
						bind:valeur={typeAnnonce}
						tous={false}
						libelle="Type"
						libelleVisible
						radio="annonce-type-{annonce?.id ?? 'new'}"
						defilante={false}
					/>
					<div class="field">
						<label for="annonce-categorie-{annonce?.id ?? 'new'}">Catégorie</label>
						<select id="annonce-categorie-{annonce?.id ?? 'new'}" bind:value={categorie}>
							{#each CATEGORIES_ANNONCE as c (c.val)}<option value={c.val}>{c.label}</option>{/each}
						</select>
					</div>
					{#if typeAnnonce === 'vente'}
						<div class="field">
							<label for="annonce-prix-{annonce?.id ?? 'new'}">Prix (€)</label>
							<input
								id="annonce-prix-{annonce?.id ?? 'new'}"
								type="number"
								min="0"
								step="0.01"
								bind:value={prix}
								placeholder="0.00"
							/>
						</div>
						<div class="field">
							<label class="case">
								<input type="checkbox" bind:checked={negotiable} />
								<span>Prix négociable</span>
							</label>
						</div>
					{/if}
				</div>
			</SectionFormulaire>
		{/if}

		<!--  3. Suivi — `SectionWorkflow`, la section de TOUTES les entités (#1329) :
		      elle s'appelait « Où en est cette annonce ? » et ignorait son pliage.
		      La liste vient de `#lib/annonces`, que la carte rend aussi. -->
		{#if sectionPresente(ANNONCE, etat, 'suivi')}
			<SectionWorkflow
				idTitre="annonce-{annonce?.id ?? 'new'}-suivi"
				options={OPTIONS_STATUT_ANNONCE}
				valeur={statut}
				pliable={pliageDe(ANNONCE, 'suivi')}
				requis={requisDe(ANNONCE, 'suivi')}
				on:choisir={(e) => (statut = e.detail)}
			/>
		{/if}

		<!--  4 à 9 : le composant partagé. Aucune de ces sections n'est gouvernée
		      par `modeEdition` — elles le sont par la DÉCLARATION, qui porte chaque
		      divergence avec son motif. -->
		<ChampsCommuns
			entite={ANNONCE}
			idPrefixe="annonce-{annonce?.id ?? 'new'}"
			avecPerimetre={sectionPresente(ANNONCE, etat, 'perimetre')}
			bind:perimetre={perimetreCible}
			avecDestinataires={sectionPresente(ANNONCE, etat, 'destinataires')}
			bind:destinataires={publicCible}
			avecDescription={sectionPresente(ANNONCE, etat, 'description')}
			descriptionRequise
			bind:description
			{assistant}
			bind:titreObjet={titre}
			bind:assisteIA
			descriptionPlaceholder="Décrivez l'objet, son état, conditions de remise…"
			avecPhotos={sectionPresente(ANNONCE, etat, 'pieces_jointes')}
			differes
			bind:fichiersDifferes={photosEnAttente}
			piecesMax={MAX_PHOTOS_ANNONCE}
			avecDiffusion={sectionPresente(ANNONCE, etat, 'diffusion')}
			avecCanaux={false}
		>
			<svelte:fragment slot="diffusion">
				<div class="field champ-large">
					<label class="case">
						<input type="checkbox" bind:checked={contactVisible} />
						<span>Afficher mes coordonnées aux autres résidents</span>
					</label>
				</div>
			</svelte:fragment>
		</ChampsCommuns>

		<!--  « Annuler » est À CÔTÉ d'« Enregistrer » — norme du 18/08/2026, posée
		      sur Tickets, constatée, puis étendue. L'en-tête de page ne porte plus
		      de seconde commande d'annulation (#367). -->
		<PiedFormulaire enCours={submitting} on:annule />
	</form>
</CadreFormulaire>

<style>
	.form-grid .field {
		margin-bottom: 0;
	}

	/*  La case et son libellé, côte à côte. Ce qui les séparait : la page portait
	    `input, textarea { width: 100% }`, un sélecteur d'ÉLÉMENT nu qui atteignait
	    aussi les cases à cocher — c'est `npm run lint:styles` qui refuse désormais
	    ce genre de sélecteur (v2.65.0). */
</style>
