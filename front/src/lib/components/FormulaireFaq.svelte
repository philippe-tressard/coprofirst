<!--
  Le formulaire d'une question de la FAQ.

  Extrait de `faq/+page.svelte` le 31/08/2026, quand le contrôle de modularité a
  refusé que la page grossisse pour recevoir son cadre. Ce n'est pas un découpage
  de confort : les six autres entités du site ont chacune leur objet
  `Formulaire<Entité>` — actualité, annonce, contrat, idée, sondage, ticket — et
  la FAQ écrivait le sien à même la page. C'était le dernier écart de cette
  famille.

  ## Ce que ce composant décide, et ce qu'il laisse à la page

  Il porte **le formulaire ET son cadre**, parce qu'il reçoit le geste
  (`modeEdition`) : c'est la règle `ux-patterns` §14 bis — *le cadre se pose là
  où le geste est connu.* La page garde l'état et la décision d'enregistrer.

  🔴 L'écran ouvrait une **modale pour la création** aussi, ce que #367 a supprimé
  après trois signalements. Il a survécu parce que `lint:formulaires` cherchait un
  `<form>` : cette modale n'en a jamais porté, seulement des `.field` et un
  éditeur riche. Le contrôle compte les champs depuis ce lot.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';

	import CadreFormulaire from '#lib/components/CadreFormulaire.svelte';
	import EtoileRequis from '#lib/components/EtoileRequis.svelte';
	import EtatListe from '#lib/components/EtatListe.svelte';
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';
	import SectionTitre from '#lib/components/SectionTitre.svelte';
	import SectionFormulaire from '#lib/components/SectionFormulaire.svelte';
	import SectionDescription from '#lib/components/SectionDescription.svelte';
	import { categorieSaisie, NOUVELLE_CATEGORIE, type SaisieFaq } from '#lib/faq.ts';
	import { FAQ } from '#lib/entites/faq.ts';

	const dispatch = createEventDispatcher<{ annule: void }>();

	/**  Corrige-t-on une question existante, ou en crée-t-on une ? La page le sait
	 *   (`editingItem`), le formulaire non — il reçoit les mêmes champs dans les
	 *   deux cas. C'est le seul discriminant du cadre. */
	export let modeEdition = false;

	/**  Ce qui RAMÈNE le formulaire à l'écran quand il est rendu loin du geste
	 *   qui l'ouvre — un pied de gabarit, sous une longue liste. Relayé jusqu'à
	 *   `FormulaireCreation`, qui ne défile que si le cadre est hors de la bande
	 *   visible : un formulaire ouvert sous les yeux ne fait pas sauter la page.
	 *
	 *   ⚠️ Cette prop existait dans `FormulaireCreation` et `CadreFormulaire`, et
	 *   AUCUN des onze formulaires qui les enveloppent ne la relayait : une prop
	 *   non relayée prend sa valeur par défaut, et le comportement manque en
	 *   silence. `check-geste-edition` règle F le refuse désormais (13/09/2026). */
	export let cle: unknown = undefined;
	/** Les champs, liés dans les deux sens : la page porte leur cycle de vie. */
	export let form: SaisieFaq;
	/** Les catégories déjà en service, proposées avant d'en inventer une. */
	export let categories: string[] = [];
	/** Non vide = les catégories n'ont pas pu être lues : sans ce mot, on en recrée une (#1459). */
	export let erreurCategories = '';
	export let enregistrement = false;
	/** Appelé à la soumission. La page garde la décision d'enregistrer. */
	export let onEnregistrer: () => void;

	//  Les mots de l'entité viennent de sa déclaration (#1329) — jamais réécrits ici.
	$: titreCadre = modeEdition ? FAQ.libelleModifier : FAQ.libelleNouveau;

	//  ⚠️ Le champ se vide quand on CHOISIT « nouvelle catégorie », pour repartir
	//  d'une saisie propre — et non quand on revient à une catégorie existante.
	//  L'inverse paraît symétrique et ne l'est pas : il effacerait le nom qu'on
	//  vient de taper au premier aller-retour dans la liste.
	function surChangementCategorie() {
		form.estNouvelleCategorie = form.categorie === NOUVELLE_CATEGORIE;
		if (form.estNouvelleCategorie) form.nouvelleCategorie = '';
	}
</script>

<!--
	Un seul montage du formulaire, deux cadres possibles — et le CHOIX du cadre
	n'est plus écrit ici. `CadreFormulaire` le porte pour les six formulaires qui
	en ont besoin : il s'y écrivait cinq fois, et les copies avaient commencé à
	diverger (02/09/2026).

	Ce qui reste ici : `edition`, qui déclare le GESTE. Ce n'est pas décoratif —
	`lint:formulaires` l'exige, et c'est lui qui distingue « créer » de
	« corriger », ce que rien dans le balisage ne permettrait de deviner.
-->
<!--  🔴 Les SECTIONS du cadre (#1329), dans l'ordre de toutes les entités :
      la question (le titre), sa catégorie, la réponse. C'était une grille de
      champs à plat, catégorie d'abord, avec une grille locale qui surchargeait
      la charte et un reste de `.modal-body`. En correction, la carte est déjà
      le cadre (`encadre`). -->
<CadreFormulaire
	edition={modeEdition}
	encadre={!modeEdition}
	titre={titreCadre}
	{cle}
	on:fermer={() => dispatch('annule')}
>
	<SectionTitre id="faq-question" libelle="Question" bind:valeur={form.question} />

	<SectionFormulaire titre="Catégorie" requis rempli={!!categorieSaisie(form)} pour="faq-categorie">
		<div class="field">
			<select id="faq-categorie" bind:value={form.categorie} on:change={surChangementCategorie}>
				<option value="" disabled>— Choisir une catégorie —</option>
				{#each categories as cat (cat)}
					<option value={cat}>{cat}</option>
				{/each}
				<option value={NOUVELLE_CATEGORIE}>➕ Nouvelle catégorie…</option>
			</select>
			<EtatListe compact erreur={erreurCategories} />
		</div>
		{#if form.estNouvelleCategorie}
			<label class="field"
				><span
					>Nom de la nouvelle catégorie<EtoileRequis vide={!form.nouvelleCategorie.trim()} /></span
				><input
					type="text"
					bind:value={form.nouvelleCategorie}
					placeholder="Ex : 🗑️ Tri des déchets"
				/></label
			>
		{/if}
	</SectionFormulaire>

	<SectionDescription
		idPrefixe="faq"
		titre="Réponse"
		requis
		placeholder="La réponse…"
		bind:valeur={form.reponse}
	/>
	<!--  `.form-actions` d'`app.css` : Annuler en `btn-outline` PUIS la soumission
	      en `btn-primary`. Un ordre qui change d'un écran à l'autre fait cliquer
	      de travers par mémoire du geste (`lint:soumission`). -->
	<!--  ⚠️ `soumission={false}` : cette modale n'a jamais porté de `<form>` (voir
	      son en-tête). C'est aussi le seul des neuf pieds qui figeait « Annuler »
	      pendant l'enregistrement — le composant l'a généralisé. -->
	<PiedFormulaire
		enCours={enregistrement}
		soumission={false}
		on:annule
		on:enregistre={onEnregistrer}
	/>
</CadreFormulaire>
