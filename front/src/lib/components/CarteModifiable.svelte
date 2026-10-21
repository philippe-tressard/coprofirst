<!--
  **Une carte de liste qui se CORRIGE EN PLACE** — sa ligne de titre, ses
  actions 🔗 ✏️ 📦, son détail déplié, et le formulaire qui prend la place du
  corps quand on la corrige.

  ## 🔴 Pourquoi ce composant (#1539, 02/10/2026)

  `CarteContrat` (10/09) et `CartePrestataire` (11/09) ont été extraites de
  `prestataires/+page.svelte` à un jour d'intervalle, sur le même signalement,
  et la seconde a recopié le squelette de la première : le conteneur
  `.carte-liste` et son geste asymétrique, `EnteteCarte`, le lien, le crayon à
  `aria-pressed`, la corbeille, le corps qui cède la place à
  `FormulaireCreation` sans bordure, le `stopPropagation` qui empêche un clic
  dans le formulaire de replier la carte. Trente-six lignes sur cent
  cinquante, et le même jeu de props.

  ⚠️ Les deux copies avaient déjà DIVERGÉ, sur les cas limites :

  | | Contrat | Prestataire | Retenu |
  |---|---|---|---|
  | titre cliqué pendant la correction | sans effet (règle écrite) | repliait un état invisible | **sans effet** |
  | nom du crayon | « Modifier ce contrat », fixe | dit le mode (« Annuler la correction ») | **les deux** : le mode, et l'objet |
  | titre de la boîte | écrit à la main | écrit à la main | `entite.libelleModifier` |

  Le contrat gagnait sur le premier point parce qu'il en donnait la raison :
  « basculer un état invisible ferait croire à un geste mort ».

  ## Ce que la carte porte, et ce que chaque objet déclare

  | Porté ici | Déclaré par l'appelant |
  |---|---|
  | le conteneur, son ancre, le geste asymétrique, l'urgence, la gouttière — par `CarteListe` | `ancreId`, `urgent`, `quand`, `classe` |
  | l'en-tête (`EnteteCarte`) | `titre`, et les emplacements `tags`, `apercu` |
  | 🔗 puis ✏️ puis 📦, dans cet ordre (`ux-patterns` §3), au trait | `quoi` ; un geste de plus par `gestes` (✨ du contrat) |
  | aux Archives : ↩️ à la place de 📦, ✏️ et les gestes se taisent, la carte s'atténue | `archive`, et où l'objet revient (`titreRestaurer`) |
  | le corps : formulaire en correction, détail sinon | les emplacements `edition` et `detail` |
  | le fond du corps | `teinte` — le contrat le teinte, le prestataire non |

  `teinte` est la seule divergence de RENDU conservée : les deux corps
  différaient (fond secondaire et retrait haut d'un côté, ni l'un ni l'autre
  de l'autre), et rien ne disait si c'était voulu. Elle est déclarée ici, en
  attendant d'être arbitrée à l'écran — plutôt que tranchée en silence.

  ## 🗂️ La gouttière (10/10/2026, la page Affaires devenue le standard)

  Les deux cartes qui montent ce squelette sont des cartes de LISTE : elles
  prennent la colonne de gauche de la carte d'affaire — la date de l'objet,
  puis ce qui le classe (`Gouttiere`). La date n'est donc plus passée à
  `EnteteCarte` : une seule date par carte, et la prop `date` est partie avec
  elle. Les actions sont dessinées au trait (`IconeAction`).
-->
<script lang="ts">
	import type { EntiteDeclaree } from '$lib/entites/types';
	import BoutonLien from './BoutonLien.svelte';
	import EnteteCarte from './EnteteCarte.svelte';
	import CarteListe from './CarteListe.svelte';
	import FormulaireCreation from './FormulaireCreation.svelte';
	import IconeAction from './IconeAction.svelte';
	import type { ClasseGouttiere } from '$lib/gouttiere';

	/** L'objet : son `libelleModifier` titre la boîte et nomme le crayon. */
	export let entite: EntiteDeclaree;
	/** L'id du conteneur, vers lequel pointe le lien 🔗 (le carnet y renvoie). */
	export let ancreId: string;
	/** Ce que le lien copie, pour son nom accessible : « le contrat ». */
	export let quoi: string;
	export let titre: string;
	/** La date qui SITUE l'objet (ISO), en tête de la gouttière — ou rien. */
	export let quand: string | null = null;
	/** Ce qui le classe, sous la date — ou rien. */
	export let classe: ClasseGouttiere | null = null;
	export let expanded = false;
	/** Cette carte est celle qu'on corrige : son corps cède la place au formulaire. */
	export let enEdition = false;
	export let urgent = false;
	export let peutModifier = false;
	/**  📦 sans ✏️ : qui RETIRE sans corriger — le gestionnaire du site devant un
	 *   avis (#2075). Absent, c'est `peutModifier`, comme avant. */
	export let peutArchiver: boolean | null = null;
	/** ↩️ : qui ressort l'objet des Archives. Absent, c'est `peutModifier`. */
	export let peutRestaurer: boolean | null = null;
	$: archivable = peutArchiver ?? peutModifier;
	$: restaurable = peutRestaurer ?? peutModifier;
	/** Le corps sur fond secondaire, avec son retrait haut (cf. l'en-tête). */
	export let teinte = false;
	/**  Rendue aux Archives : ↩️ y remplace 📦, et les gestes de correction se
	 *   taisent — on ressort un objet avant de le corriger (#1538). */
	export let archive = false;
	/** L'infobulle de ↩️ : où l'objet revient (« la fiche revient dans l'annuaire »). */
	export let titreRestaurer = 'Restaurer';

	export let onBasculer: () => void = () => {};
	export let onModifier: () => void = () => {};
	export let onAnnuler: () => void = () => {};
	/** 📦 `true` range l'objet, `false` le ressort des Archives. */
	export let onArchiver: (archivee: boolean) => void = () => {};
</script>

<CarteListe
	id={ancreId}
	{quand}
	{classe}
	expanded={expanded || enEdition}
	{urgent}
	{archive}
	onDeplier={onBasculer}
>
	<!--  ⚠️ Pendant la correction, la ligne de titre ne replie pas : le corps
	      montre le formulaire quoi qu'il arrive, et basculer un état invisible
	      ferait croire à un geste mort. On sort par le crayon ou par
	      « Annuler ». -->
	<EnteteCarte {titre} basculable on:toggle={() => !enEdition && onBasculer()}>
		<svelte:fragment slot="tags"><slot name="tags" /></svelte:fragment>

		<svelte:fragment slot="actions">
			<BoutonLien ancre={ancreId} {quoi} />
			{#if peutModifier && !archive}
				<!--  Du moins destructeur au plus : ce que l'objet ajoute (✨ du
				      contrat) vient avant la correction, qui vient avant l'archivage. -->
				<slot name="gestes" />
				<!--  Le mode se lit sur l'icône qui a ouvert le formulaire, jamais sur
				      un titre au-dessus (`ux-patterns` §13 bis). -->
				<button
					class="btn-icon-edit"
					aria-label={enEdition ? 'Annuler la correction' : entite.libelleModifier}
					title={enEdition ? 'Annuler la correction' : 'Modifier'}
					aria-pressed={enEdition}
					on:click|stopPropagation={() => (enEdition ? onAnnuler() : onModifier())}
					><IconeAction icone="pencil" /></button
				>
			{/if}
			{#if archivable && !archive}
				<!--  📦 et non 🗑️ (#1538) : la corbeille disait « supprimer » pour un
				      geste qui range — et l'objet se retrouve aux Archives. -->
				<button
					class="btn-icon"
					aria-label="Archiver"
					title="Archiver — rejoint les Archives, en bas de la liste"
					on:click|stopPropagation={() => onArchiver(true)}><IconeAction icone="archive" /></button
				>
			{:else if archive}
				{#if restaurable}
					<button
						class="btn-icon"
						aria-label="Restaurer"
						title={titreRestaurer}
						on:click|stopPropagation={() => onArchiver(false)}
						><IconeAction icone="undo-2" /></button
					>
				{/if}
				<!--  Aux Archives seulement : ce qui s'y fait de plus (🗑️ d'un avis). -->
				<slot name="gestes-archive" />
			{/if}
		</svelte:fragment>

		<svelte:fragment slot="apercu"><slot name="apercu" /></svelte:fragment>
	</EnteteCarte>

	{#if enEdition}
		<!--  Le corps ne referme pas la carte : sans `stopPropagation`, un clic dans
		      le formulaire remonterait à la ligne de titre et replierait ce qu'on est
		      en train de corriger (`ux-patterns` §3). -->
		<div
			class="carte-corps carte-modifiable-corps"
			class:teinte
			role="presentation"
			on:click|stopPropagation
			on:keydown|stopPropagation
		>
			<!--  `encadre={false}` : la carte EST le cadre, et sa ligne de titre en est
			      l'en-tête. Une carte dans une carte, c'est deux bordures pour un seul
			      objet (#425). -->
			<FormulaireCreation titre={entite.libelleModifier} encadre={false}>
				<slot name="edition" />
			</FormulaireCreation>
		</div>
	{:else if expanded}
		<div class="carte-corps carte-modifiable-corps" class:teinte>
			<slot name="detail" />
		</div>
	{/if}
</CarteListe>

<style>
	/*  Les valeurs des deux corps d'origine : `.prest-body` (sans teinte) et
	    `.contrat-detail-body` (teinte). Elles suivent le balisage qu'elles
	    habillent, qui vit ici désormais. */
	.carte-modifiable-corps {
		padding: 0.25rem 1rem 1rem;
		border-top: 1px solid var(--color-border);
	}
	.carte-modifiable-corps.teinte {
		padding-top: 0.75rem;
		background: var(--color-neutre-fond);
	}
</style>
