<!--
  SectionOptionsPublication.svelte — la section 2 du cadre #430, telle qu'elle se
  rend partout : le titre « Options de publication » et les cases.

  ## Pourquoi (05/09/2026)

  Le couple « `SectionFormulaire` + `OptionsPublication` » était écrit quatre fois
  — création d'actualité, panneau d'options, commentaire d'actualité, et le
  ticket qui venait de le recevoir. Quatre écritures d'une même section, donc
  quatre occasions de diverger sur le titre, l'ordre ou le filet.

  Demandé à l'écran : *« Faire ces évolutions au niveau de l'objet pour ne pas
  dupliquer le code. Donc sur actualité et Ticket mettre la section Options de
  publication. »*

  ## Ce que ce composant N'EST PAS

  Il ne décide pas des options : c'est `options` qui le dit, et la table
  (`$lib/options-publication`) qui porte glyphes et libellés. Un ticket n'en rend
  qu'une — il n'a ni colonne d'épinglage ni colonne d'urgence.

  ⚠️ Les liaisons restent nommées (`bind:epingle`…) et non regroupées dans un
  objet : `bind:` a besoin d'une variable, et un objet intermédiaire obligerait
  chaque hôte à le défaire ensuite.
-->
<script lang="ts">
	import { SECTIONS_LIBELLE } from '$lib/entites/types';
	import { optionPublication } from '$lib/options-publication';
	import SectionFormulaire from '$lib/components/SectionFormulaire.svelte';
	import OptionsPublication from '$lib/components/OptionsPublication.svelte';
	import type { CleOptionPublication } from '$lib/options-publication';

	/** Le nom de l'objet décrit, pour les libellés qui le nomment. */
	export let objet = 'actualité';
	/** Les options rendues, dans l'ordre de la table. */
	export let options: CleOptionPublication[] = ['epingle', 'urgente', 'brouillon'];
	/** Première section du formulaire : pas de filet au-dessus. */
	export let premiere = false;

	export let epingle = false;
	export let urgente = false;
	export let brouillon = false;
	/** L'objet édité était-il DÉJÀ épinglé ? (évite un double comptage) */
	export let dejaEpingle = false;
	/** 🔒 Motif pour lequel l'épinglage est impossible — relayé tel quel. */
	export let epingleInterdit = '';

	/** Repliée par défaut — la valeur vient de la déclaration (#1095). */
	export let pliable = false;

	/**  Le résumé : ce qui est COCHÉ, ou le fait que rien ne l'est.
	 *
	 *   ⚠️ Les libellés viennent de `optionPublication`, jamais réécrits ici :
	 *   c'est la table qui nomme une option, et elle est déjà la source de ce
	 *   que les cases affichent. */
	$: actives = options.filter((c) => ({ epingle, urgente, brouillon })[c as 'epingle']);
	$: resume = actives.length
		? actives.map((c) => optionPublication(c)?.etat ?? c).join(' · ')
		: 'ni épinglée ni urgente';
	/** Le motif d'extinction de la section, ou `''` (`inactivePour`, #1191). */
	export let inactive = '';
</script>

<SectionFormulaire
	titre={SECTIONS_LIBELLE.mise_en_avant}
	{inactive}
	{premiere}
	{pliable}
	{resume}
	valeurModifiee={actives.length > 0}
	idTitre="{objet}-options-titre"
>
	<OptionsPublication
		{objet}
		{options}
		{dejaEpingle}
		{epingleInterdit}
		bind:epingle
		bind:urgente
		bind:brouillon
	/>
</SectionFormulaire>
