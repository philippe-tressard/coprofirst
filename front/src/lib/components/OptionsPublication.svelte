<!--
  OptionsPublication.svelte — les options qui DÉCRIVENT une actualité :
  épinglage, urgence, brouillon. **Section 2 du cadre #430**
  (champs spécifiques), rendue à la création comme à l'édition.

  Extrait de `routes/(app)/actualites/+page.svelte` le 15/08/2026 (la rangée de
  cases y était écrite DEUX fois, sans que rien n'oblige les deux à rester
  d'accord), puis **amputé de sa moitié « acte » le 18/08/2026** (#433).

  ## Pourquoi la coupure (#433)

  Ce composant portait aussi les canaux de notification et l'affiche de hall,
  sous un drapeau `complet` qui les réservait à la création. Le cadre a rendu ce
  drapeau intenable : **les sections 1 à 8 décrivent l'entité, la 9 est un acte**,
  et la 9 est absente de l'édition (*une correction n'est pas une nouvelle*). Un
  composant à cheval sur les deux ne pouvait donc plus être rendu nulle part sans
  mentir — dans la section 2 il aurait glissé des canaux là où on décrit ;
  dans la 9, il aurait emporté avec lui les quatre options **et supprimé le seul
  chemin qui permet de publier un brouillon**.

  Ce qui part : `CanauxNotification` et l'affiche de hall → `DiffusionPublication`.
  Ce qui reste : ce qui se corrige.

  ## 🔒 La case « visible du seul périmètre » est partie (23/09/2026, #1096)

  Elle vit dans `CaseReservePerimetre`, en tête de la section Périmètre.

  🔴 Ce composant la rendait encore VERROUILLÉE, cochée sans que la valeur liée
  change (`confidentielAcquis`) : c'est la mécanique qui a montré une affaire
  réservée et l'a envoyée `false` (22/10/2026). Retirée avec son option
  `'confidentiel'` le 23/10/2026 (#2144) : il n'y a plus ici de case de réserve,
  donc plus de seconde case liée au mauvais champ.
-->
<script lang="ts">
	import AlerteEpinglage from './AlerteEpinglage.svelte';
	//  Glyphes et libellés : la table est la source unique (`#lib/options-publication`).
	//  Ils étaient écrits ici ET dans les badges de `CarteActualite`, et avaient
	//  divergé — l'épinglage n'avait pas de glyphe ici et 📌 là-bas.
	import {
		actionOption,
		optionPublication,
		type CleOptionPublication,
	} from '#lib/options-publication.ts';

	/** Épingler en tête du fil. */
	export let epingle = false;
	/** Marquer urgent (bord gauche rouge, pas de badge texte). */
	export let urgente = false;
	/** Brouillon : invisible pour les résidents, ne déclenche aucun envoi. */
	export let brouillon = false;
	/** L'élément édité était-il DÉJÀ épinglé ? (évite un double comptage) */
	export let dejaEpingle = false;
	/**  🔒 Le motif pour lequel l'épinglage est IMPOSSIBLE sur cet objet, ou vide.
	 *
	 *   Ce n'est PAS une case montrée cochée sans l'être : la valeur liée est
	 *   décochée avec elle (ci-dessous), et l'infobulle dit pourquoi. Un événement absent du fil
	 *   d'activité ne peut pas y être épinglé. Le
	 *   calendrier écrivait sa propre case d'épinglage — glyphe compris — dans la
	 *   section Diffusion, et cette dépendance était la seule raison invoquée
	 *   (12/09/2026). Elle n'en est plus une : la case vit où vivent les options,
	 *   et elle dit pourquoi elle est inerte.
	 *
	 *   ⚠️ Une case inerte SANS explication laisse croire à un bug
	 *   (`standards/11`, accessibilité). C'est le motif qui fait la différence
	 *   entre une contrainte et une panne. */
	export let epingleInterdit = '';

	/**  Le nom de l'objet décrit — « publication », « ticket ». Il entre dans les
	 *   libellés qui le nomment (« Visibilité du **ticket** au seul conseil
	 *   syndical ») : la même case sert deux entités, et « ce truc-là » ne se dit
	 *   pas. */
	export let objet = 'actualité';

	/**  Les options RENDUES, dans l'ordre de la table. Toutes par défaut — une
	 *   affaire n'en porte que deux (`OPTIONS_TICKET`). */
	export let options: CleOptionPublication[] = ['epingle', 'urgente', 'brouillon'];
	$: rendue = (cle: CleOptionPublication) => options.includes(cle);

	//  Les options, lues UNE fois dans la table. Constantes de module et
	//  non `{@const}` de balisage : Svelte ne l'admet pas comme enfant direct
	//  d'un `<div>`, et ces valeurs ne dépendent d'aucun état.
	const optEpingle = optionPublication('epingle');
	const optUrgente = optionPublication('urgente');
	const optBrouillon = optionPublication('brouillon');
	//  Même règle pour l'épinglage : décocher « Afficher dans le fil » après avoir
	//  épinglé laisserait partir un épinglage sur un objet absent du fil.
	$: if (epingleInterdit && epingle) epingle = false;
</script>

<div class="cases">
	<!--  Les glyphes et les intitulés viennent de la table, jamais du balisage :
	      c'est ce qui garantit qu'une case et le badge correspondant montrent la
	      même chose. Les LIAISONS, elles, restent explicites — `bind:checked` a
	      besoin d'une variable nommée, et une boucle générique obligerait à un
	      objet intermédiaire que l'hôte devrait ensuite redéfaire. -->
	{#if rendue('epingle')}
		<label
			class="checkbox-field"
			class:desactivee={epingleInterdit}
			title={epingleInterdit || optEpingle?.aide}
		>
			<input type="checkbox" bind:checked={epingle} disabled={!!epingleInterdit} />
			{optEpingle?.glyphe}
			{optEpingle && actionOption(optEpingle, objet)}
		</label>
	{/if}
	{#if rendue('urgente')}
		<label class="checkbox-field" title={optUrgente?.aide}>
			<input type="checkbox" bind:checked={urgente} />
			{optUrgente?.glyphe}
			{optUrgente && actionOption(optUrgente, objet)}
		</label>
	{/if}
	{#if rendue('brouillon')}
		<label class="checkbox-field" title={optBrouillon?.aide}>
			<input type="checkbox" bind:checked={brouillon} />
			{optBrouillon?.glyphe}
			{optBrouillon && actionOption(optBrouillon, objet)}
		</label>
	{/if}
</div>

<AlerteEpinglage coche={epingle} {dejaEpingle} />

<style>
	.cases {
		display: flex;
		gap: 1.5rem;
		flex-wrap: wrap;
		margin-bottom: 1rem;
	}
	/*  🔴 `.checkbox-field` A DÉMÉNAGÉ dans `styles/composants.css` (02/09/2026),
	    et c'est une correction. La règle qui vivait ici ne s'appliquait qu'à
	    l'intérieur de `.cases` — or HUIT fichiers emploient la classe (profil,
	    inscription, notifications, diffusion, formulaire de ticket…), et partout
	    ailleurs la case se rendait NUE, sans alignement ni curseur.
	    ⚠️ Le commentaire qui était ici affirmait que `.checkbox-field` était
	    « une classe partagée du thème ». C'était faux, et jamais vérifié : il
	    décrivait ce qu'on croyait avoir fait. `lint:classes-nues` l'a vu au 9e
	    usage, pas avant. */
	/*  Une case grisée doit se VOIR grisée, pas seulement refuser le clic. */
	.cases .desactivee {
		opacity: 0.5;
		cursor: not-allowed;
	}
	/*  Sous 480 px, les cases passent en colonne et gagnent une cible tactile
	    de 44 px (socle 11 §10) — même règle que `CanauxNotification`. */
	@media (max-width: 480px) {
		.cases {
			flex-direction: column;
			gap: 0.25rem;
		}
		.cases :global(.checkbox-field) {
			min-height: 44px;
		}
	}
</style>
