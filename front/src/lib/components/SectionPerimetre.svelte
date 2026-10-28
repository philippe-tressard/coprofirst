<!--
  La section **Périmètre** du cadre — *de quoi* il s'agit, et qui peut le voir.

  Extraite de `ChampsCommuns` le 22/09/2026, au fil de l'eau, pour la même
  raison que `SectionDestinataires` : neuf sections sur onze avaient déjà leur
  composant, et les deux dernières écrites en ligne bloquaient le fichier.

  🔴 Le sélecteur se tait (`titre=""`) : c'est la SECTION qui nomme. Les
  pastilles ne sont pas un contrôle labelable — `for` n'y associerait rien —,
  d'où le couple `id` sur le titre / `aria-labelledby` sur le groupe.
-->
<script lang="ts">
	import CaseReservePerimetre from '#lib/components/CaseReservePerimetre.svelte';
	import PerimetrePicker from '#lib/components/PerimetrePicker.svelte';
	import SectionFormulaire from '#lib/components/SectionFormulaire.svelte';
	import { SECTIONS_LIBELLE } from '#lib/entites/types.ts';
	import {
		estPerimetreParDefaut,
		perimetreLabelUn,
		perimetreParDefaut,
	} from '#lib/perimetres/index.ts';
	import { perimetresStore } from '#lib/stores/perimetres.ts';
	import { relire } from '#lib/utils.ts';

	/** Préfixe des identifiants — l'écran en ouvre parfois plusieurs à la fois. */
	export let idPrefixe: string;

	export let premiere = false;

	/** Repliée par défaut — la valeur vient de la déclaration (#1095). */
	export let pliable = false;

	export let perimetre: string[] = [];
	export let mode: 'multi' | 'single' = 'multi';
	/**  Lu dans la déclaration par l'appelant (`requisDe`) — jamais vrai d'office (#1186). */
	export let requis = false;

	/** Un badge imposé par l'appelant — sinon celui du périmètre par défaut. */
	export let badgeImpose: string | null = null;

	/**  🔒 La réserve au périmètre, EN TÊTE de la section (25/09/2026) — elle
	 *   était sous les pastilles depuis #1096. Cochable pour une actualité comme
	 *   pour une affaire (22/10/2026) : cochée d'office et verrouillée, elle
	 *   partait `false` et ne protégeait rien. */
	export let reservable = false;
	export let reserve = false;
	/** Le nom de l'objet, que l'aide de la case nomme. */
	export let reserveObjet = 'actualité';
	/** Le motif qui la rend sans objet — « Confidentielle » cochée. */
	export let reserveSansObjet = '';

	/**  Le badge du TITRE de section. Il ne recalcule rien :
	 *   `estPerimetreParDefaut` est la fonction qu'emploie déjà le sélecteur.
	 *
	 *   ⚠️ `$perimetresStore` n'est pas lu pour sa valeur : il dit à Svelte que ce
	 *   calcul dépend de l'arbre, que les fonctions lisent dans un état de
	 *   MODULE. Sans lui, le badge annonçait le code brut sur un formulaire
	 *   ouvert avant l'arbre (#947). */
	$: badgeCalcule = relire($perimetresStore, () =>
		estPerimetreParDefaut(perimetre) ? perimetreLabelUn(perimetreParDefaut() ?? '') : '',
	);
	/** Le motif d'extinction de la section, ou `''` (`inactivePour`, #1191). */
	export let inactive = '';
	/*  « Rempli » compte le défaut ACTIF (27/09/2026) : la liste vide vaut
	    « aucune restriction », et le sélecteur l'affiche comme choisie — même
	    règle que Destinataires. 🔒 `e2e/etoile-valeur-defaut.spec.ts`. */
</script>

<SectionFormulaire
	{premiere}
	{pliable}
	titre={SECTIONS_LIBELLE.perimetre}
	{inactive}
	{requis}
	rempli={perimetre.length > 0 || estPerimetreParDefaut(perimetre)}
	badge={badgeImpose ?? badgeCalcule}
	valeurModifiee={!estPerimetreParDefaut(perimetre)}
	idTitre="{idPrefixe}-perimetre-titre"
>
	{#if reservable}
		<CaseReservePerimetre
			bind:coche={reserve}
			perimetreCible={perimetre}
			objet={reserveObjet}
			sansObjet={reserveSansObjet}
		/>
	{/if}
	<div class="field champ-large" role="group" aria-labelledby="{idPrefixe}-perimetre-titre">
		<PerimetrePicker bind:value={perimetre} {mode} titre="" />
		<!--  🔴 Un SLOT et non une prop de texte : l'aide porte du balisage (un
		      `<strong>`), et une prop obligerait à un `{@html}` — donc à un
		      assainisseur, pour du contenu qui n'est pas de la donnée mais du
		      gabarit. Le slot laisse le balisage chez l'appelant : rien à
		      assainir, rien à faire confiance.

		      Vide par défaut : l'aide n'existe que là où le geste n'est pas
		      évident. Sur une évolution, « laissé vide, le périmètre du ticket ne
		      bouge pas » ne se déduit pas du champ. -->
		<slot name="aidePerimetre" />
	</div>
</SectionFormulaire>
