<!--
  **Corriger un document de la page Résidence** — plan, règlement ou CR d'AG.

  ## Pourquoi ce composant (#852, 08/09/2026)

  Signalé à l'écran : *« l'édition est en bas de page et non dans la section
  sélectionnée […] quand on édite on ne se retrouve pas en bas de page mais à
  l'endroit où on édite (faire de même que la référence Actualité ou ticket) »*.

  Les sept formulaires de Résidence étaient rendus à la **fin** du fichier, après
  toutes les sections. Cliquer ✏️ sur un plan ouvrait donc une boîte quatre cents
  pixels plus bas, sous les diagnostics — hors de l'écran, et sans rapport visible
  avec le geste qu'on venait de faire.

  🔴 **Les ramener dans leur section a fait apparaître le vrai problème** : le
  formulaire d'édition est **un seul** pour **trois** sections, discriminé par
  `editingDocMode`. Le recopier trois fois l'aurait fait diverger au premier champ
  ajouté — c'est-à-dire tout de suite, puisque le même lot en ajoute trois. Un
  objet, monté trois fois, sous la condition de sa section.

  ⚠️ Et `svelte-check` l'a dit avant moi : dans la copie de « Plans », le
  sous-bloc « Année / Date d'AG » comparait `'plan'` à `'ag'` — *« this comparison
  appears to be unintentional »*. Une branche morte que la relecture laissait
  passer, parce qu'elle est correcte partout ailleurs.

  ## Ce qu'il rend, et dans l'ordre du cadre

  1. **Titre** · 2. **Année et date d'AG**, pour les CR d'AG seulement ·
  4. **Périmètre** · 6. **Description** · 8. **Pièces jointes** — une seule liste,
  le fichier en tête puis les autres, dix en tout (11/10/2026 ; il n'y avait jusque-là rien à cette
  place : un document déposé ne changeait plus de fichier).

  Les numéros sautent : ce sont ceux du cadre (`ux-patterns` §0), et un document
  n'a ni workflow, ni destinataires, ni diffusion. Les garder rend l'ordre
  vérifiable d'un coup d'œil.
-->
<script context="module" lang="ts">
	/**  La section d'où vient le document. Seul `ag` porte l'année et la date —
	 *   les deux autres n'en ont pas, et les afficher promettrait un champ que le
	 *   serveur ignore pour eux. */
	export type ModeDocument = 'plan' | 'reglement' | 'ag';

	/**
	 *  Ce qu'on est en train de corriger — **un objet, pas sept variables**.
	 *
	 *  🔴 Il en fallait sept (`editingDocId`, `…Mode`, `…Titre`, `…Annee`,
	 *  `…Date`, `…Perimetre`, `…Description`), et les TROIS montages de ce
	 *  formulaire les reliaient une à une : douze lignes recopiées trois fois,
	 *  dans un fichier de neuf cents. Un champ ajouté au formulaire, c'était
	 *  trois `bind:` de plus à ne pas oublier — et rien pour le rappeler.
	 *
	 *  Avec l'objet, un champ ajouté ici n'exige RIEN des appelants : ils lient
	 *  `bind:correction` et ne connaissent plus la liste.
	 *
	 *  ⚠️ Il s'appelle `correction` et non `edition` : `FormulaireDocument` emploie
	 *  déjà ce mot pour le MODE (créer ou corriger), et `npm run lint:cadre-geste`
	 *  reconnaît un formulaire qui connaît son geste à `export let edition`. Deux
	 *  sens pour un mot, c'est la confusion que ce dépôt refuse ailleurs — le
	 *  contrôle l'a signalé avant qu'elle ne s'installe.
	 */
	export interface CorrectionDocument {
		/** `null` = aucune correction en cours. C'est ce qui monte le formulaire. */
		id: number | null;
		mode: ModeDocument;
		titre: string;
		annee: string | number;
		dateAg: string;
		/** La date du document — un règlement (`ChampDateDocument`). */
		dateDocument: string;
		/** Section 4 — `[]` signifie « toute la copropriété », valide ici. */
		perimetre: string[];
		/** Section 6 — ajoutée le 08/09/2026, elle n'existait sur aucun document. */
		description: string;
	}

	/** L'objet au repos — écrit ici, pour que « annuler » et « fermer » soient le même geste. */
	export function correctionVide(): CorrectionDocument {
		return {
			id: null,
			mode: 'plan',
			titre: '',
			annee: '',
			dateAg: '',
			dateDocument: '',
			perimetre: [],
			description: '',
		};
	}
</script>

<script lang="ts">
	import { createEventDispatcher } from 'svelte';

	import ChampDateDocument from '#lib/components/ChampDateDocument.svelte';
	import ChampsCrAg from '#lib/components/ChampsCrAg.svelte';
	import FormulaireDocument from '#lib/components/FormulaireDocument.svelte';
	import type { PiecesFiche } from '#lib/components/PiecesJointesFiche.svelte';

	const dispatch = createEventDispatcher<{ annuler: void; enregistrer: void }>();

	/** Le document en cours de correction — lié par `bind:correction`. */
	export let correction: CorrectionDocument;
	export let enregistrement = false;
	/** Section 8 — le fichier du document et les autres pièces, en une liste. */
	export let piecesJointes: PiecesFiche | null = null;
</script>

<FormulaireDocument
	edition
	intitule="Modifier le document"
	bind:titre={correction.titre}
	avecPerimetre
	bind:perimetre={correction.perimetre}
	avecFichier={false}
	{piecesJointes}
	{enregistrement}
	complet={!!correction.titre.trim() &&
		(correction.mode !== 'reglement' || !!correction.dateDocument)}
	on:annuler={() => dispatch('annuler')}
	on:enregistrer={() => dispatch('enregistrer')}
>
	<svelte:fragment slot="specifiques">
		{#if correction.mode === 'ag'}
			<ChampsCrAg
				idPrefixe="edit-doc"
				bind:annee={correction.annee}
				bind:dateAg={correction.dateAg}
			/>
		{:else if correction.mode === 'reglement'}
			<ChampDateDocument idPrefixe="edit-doc" bind:valeur={correction.dateDocument} />
		{/if}
	</svelte:fragment>

	<label class="field" for="edit-doc-description" slot="description">
		Description
		<textarea
			id="edit-doc-description"
			bind:value={correction.description}
			placeholder="Ce que ce document couvre, d'où il vient, ce qu'il ne dit pas…"
			rows="3"></textarea>
	</label>
</FormulaireDocument>
