<script lang="ts">
	import type { Document, Prestataire } from '#lib/api/index.ts';
	import type { FormulaireContratData } from '#lib/prestataires.ts';
	/**
	 * Le formulaire d'un contrat d'entretien — **un seul rendu**, deux enveloppes.
	 *
	 * ## Pourquoi ce composant (#640, 30/08/2026)
	 *
	 * `prestataires/+page.svelte` rendait ce formulaire **deux fois**, à 110 lignes
	 * d'écart : une fois en boîte de page, une fois déplié dans la carte du
	 * contrat. Les deux montaient `ChampsContrat` puis `DocumentsRattaches` — donc
	 * la même intention, écrite deux fois.
	 *
	 * 🔴 **Et les deux avaient déjà divergé**, sans que personne l'ait décidé :
	 *
	 * | | boîte de page | déplié dans la carte |
	 * |---|---|---|
	 * | barre d'actions | `.form-actions` (à droite, `ux-patterns` §9 quinquies) | un flex écrit à la main, **à gauche** |
	 * | taille des boutons | normale | `btn-sm` |
	 * | intitulé | titre du formulaire | « Infos contrat » |
	 *
	 * C'est le mécanisme ordinaire de la duplication : personne n'a choisi que le
	 * même geste aurait deux apparences, ce sont les deux copies qui l'ont produit.
	 *
	 * ⚠️ **Le second rendu était en outre INATTEIGNABLE** — du code mort. Sa garde
	 * demandait `contratFormPrestId !== -1`, et `startEditContrat()` posait
	 * `contratFormPrestId = -1` à la ligne suivant `editContratId = c.id`. Aucun
	 * chemin ne pouvait donc l'afficher. Rien ne le signalait : un bloc `{#if}`
	 * toujours faux compile, se formate et passe `svelte-check` sans un mot.
	 *
	 * ## Ce que ce composant décide, et ce qu'il laisse à l'appelant
	 *
	 * Il porte **le formulaire** : les champs, les documents, la barre d'actions et
	 * leurs libellés. Il ne porte **pas son cadre** — c'est le geste qui le choisit,
	 * et c'est la règle `ux-patterns` §14 bis :
	 *
	 * - **créer** → `<FormulaireCreation>`, la boîte dans la page, en tête de liste ;
	 * - **corriger** → `<FormulaireCreation encadre={false}>` DANS la carte de
	 *   l'objet, à la place de son corps — le motif des tickets (`ux-patterns` §14 ter).
	 *
	 * 🔴 La seconde ligne disait `<Modale edition>` jusqu'au 10/09/2026, et c'était
	 * une consigne PÉRIMÉE : l'écran des contrats ne l'employait déjà plus. Un
	 * commentaire qui enseigne un motif supprimé le fait réapparaître — c'est déjà
	 * arrivé à `renderDesc` dans `svelte-patterns`. `lint:geste-edition` règle E
	 * refuse désormais l'un comme l'autre.
	 *
	 * Mettre le cadre ici obligerait le composant à connaître le geste pour
	 * choisir son enveloppe — alors que c'est l'écran qui sait lequel il déclenche.
	 */
	import ChampsContrat from './ChampsContrat.svelte';
	import DocumentsRattaches from './DocumentsRattaches.svelte';
	import SectionFormulaire from './SectionFormulaire.svelte';
	import { CONTRAT } from '#lib/entites/contrat.ts';
	import { SECTIONS_LIBELLE } from '#lib/entites/types.ts';
	import { pliageDe } from '#lib/pliage.ts';
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';

	/** L'état du formulaire, lié dans les deux sens par l'appelant. */
	export let contratForm: FormulaireContratData;
	export let prestataires: Prestataire[] = [];

	/**
	 * L'identifiant du contrat édité, ou `null` en création.
	 *
	 * 🔴 Il décide du RÉGIME de la rubrique Documents, non de sa présence
	 * (corrigé le 12/09/2026) : `null` fait attendre les fichiers, un identifiant
	 * les envoie aussitôt. La section, elle, est rendue dans les deux cas.
	 *
	 * ⚠️ Jamais un booléen de plus : un drapeau séparé pourrait dire « avec
	 * documents » sans identifiant, et `DocumentsRattaches` recevrait alors
	 * `contratId={0}` — c'est ce que l'ancien code écrivait
	 * (`contratId={editContratId ?? 0}`), un repli qui ne désignait aucun
	 * contrat. `null` le dit, `0` le cachait.
	 */
	export let contratId: number | null = null;

	/**  Les fichiers choisis AVANT que le contrat existe. L'écran les lit après
	 *   l'enregistrement et les attache par `attacherA('contrat', …)` — la même
	 *   fonction que les actualités.
	 *
	 *   ⚠️ Ils restent ici et non dans l'écran : c'est le formulaire qui les
	 *   collecte, et un état partagé par une prop liée se lit dans les deux sens
	 *   sans qu'un des deux côtés invente sa copie. */
	export let fichiersEnAttente: File[] = [];
	export let documents: Document[] = [];
	export let onSupprimer: (contratId: number, docId: number) => void = () => {};
	export let onAjoute: (contratId: number) => void = () => {};

	/** Envoi en cours — le bouton le dit, et se verrouille. */
	export let submitting = false;

	export let onAnnuler: () => void;
	/** Appelé à la soumission du `<form>` — donc aussi sur la touche Entrée. */
	export let onEnregistrer: () => void;
</script>

<!--
	🔴 UN VRAI `<form>`, et ce n'est pas cosmétique.

	Les deux rendus précédents n'en avaient pas : des `<button on:click>` posés
	dans un `<div>`. Trois conséquences, dont la dernière est la plus coûteuse :

	1. la touche **Entrée** ne soumettait pas — dans un formulaire de dix champs,
	   c'est le geste attendu ;
	2. la validation native (`required`) n'avait aucun événement où s'accrocher ;
	3. 🔒 `lint:formulaires` ne regarde QUE les modales contenant un `<form>`.
	   Sans lui, la déclaration `edition` de la modale appelante n'était surveillée
	   par rien : on pouvait la retirer, `fermetureAuFond` redevenait vrai, et un
	   clic à côté effaçait une correction en cours — en silence. Le garde-fou et
	   la sémantique correcte sont ici la même chose.
-->
<form on:submit|preventDefault={onEnregistrer}>
	<ChampsContrat
		bind:contratForm
		{prestataires}
		etat={contratId === null ? 'creation' : 'edition'}
	/>
	<!--  ══ 8. DOCUMENTS ══ La section vient APRÈS la description, jamais avant :
	      l'ordre des sections ne se discute pas (R2), et Photos (7) et
	      Documents (8) ne fusionnent jamais.

	      🔴 Elle est désormais rendue AUSSI à la création (12/09/2026, #921). Elle
	      en était absente au motif qu'un document se rattache à un `contrat_id`
	      qui n'existe pas encore — vrai, mais la conclusion ne l'était pas : les
	      ACTUALITÉS le font depuis #531 en gardant les fichiers de côté et en les
	      attachant une fois l'objet enregistré. Aucun endpoint ne manquait, le
	      geste existait sur un autre écran. La dette déclarée était une dette
	      d'inattention. -->
	<!--  🔴 « Pièces jointes », le nom de la section 8 partout (#1095) : elle
	      s'appelait encore « Documents » ici, et ne suivait pas son pliage
	      déclaré (24/09/2026, signalé à l'écran). -->
	<SectionFormulaire
		titre={SECTIONS_LIBELLE.pieces_jointes}
		pliable={pliageDe(CONTRAT, 'pieces_jointes')}
		valeurModifiee={documents.length > 0 || fichiersEnAttente.length > 0}
		resume={documents.length + fichiersEnAttente.length
			? `${documents.length + fichiersEnAttente.length} fichier(s)`
			: 'aucune'}
		pour="contrat-{contratId ?? 'nouveau'}-doc"
	>
		<!--  `.field champ-large` : l'enveloppe que `SectionsPiecesJointes` pose
		      pour les tickets. Sans elle, le champ de nommage ne prend pas la
		      largeur de la boîte. -->
		<div class="field champ-large">
			<DocumentsRattaches
				cible="contrat"
				objetId={contratId}
				{documents}
				{onSupprimer}
				{onAjoute}
				bind:fichiersEnAttente
				idChamp="contrat-{contratId ?? 'nouveau'}-doc"
			/>
		</div>
	</SectionFormulaire>

	<!--
		`.form-actions` porte `justify-content: flex-end` (app.css) : le bouton
		primaire est à droite, partout. Le rendu déplié l'écrivait à la main, donc
		à gauche. Le libellé est celui de tout le site — `ux-patterns` §9 quinquies bis.
	-->
	<PiedFormulaire enCours={submitting} on:annule={onAnnuler} />
</form>

<style>
</style>
