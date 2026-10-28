<!--
  La section **3. Workflow** du cadre : l'intitulé, l'état courant en badge, et
  la rangée de pastilles.

  Elle était écrite au mot près dans `FormulaireTicket` et `EvolForm` — le
  commentaire de ce dernier le disait lui-même : *« Même forme que la section
  Workflow de `FormulaireTicket`, au mot près »*. Une duplication déclarée reste
  une duplication : la déclarer dit qu'on l'a vue, pas qu'elle est saine.
  Extraite le 01/09/2026, sur refus de modularité.

  🔴 **PASTILLES, jamais un `<select>` nu** (cadre R3, #423). L'état courant est
  actif à l'ouverture : on voit où en est l'objet, et en changer est un clic.

  🔴 **Section à UN champ : le titre EST le libellé** (`ux-patterns` §9 septies),
  et il porte l'état actuel en badge à droite (§9 quater) — la même forme que la
  carte, deux centimètres plus haut.

  ⚠️ `lecture` n'est **qu'un confort** : ce que l'interface interdit, le serveur
  le refait (liste blanche CS). Ne jamais s'en servir comme d'un droit.
-->
<script lang="ts">
	import SectionFormulaire from '#lib/components/SectionFormulaire.svelte';
	//  🔴 L'intitulé vient de la TABLE, jamais écrit ici : il disait encore
	//  « Workflow » deux lots après que le cadre l'eut renommé « Suivi »
	//  (#1094), parce qu'aucun contrôle ne lisait ce fichier — il ne consomme
	//  aucune entité déclarée. `lint:vocabulaire-ecran` le voit désormais.
	import { SECTIONS_LIBELLE } from '#lib/entites/types.ts';
	import WorkflowPastilles from '#lib/components/WorkflowPastilles.svelte';

	/** Identifiant du titre — c'est lui qui labellise la rangée. */
	export let idTitre: string;
	export let options: { value: string; label: string }[] = [];
	export let valeur = '';
	/** L'état actuel, en badge à droite de l'intitulé. Vide : pas de badge. */
	export let badge = '';

	/**  Le pliage, transmis par l'appelant (#1093, 22/09/2026).
	 *
	 *   « Suivi » est obligatoire, donc dépliée dans toutes les entités : cette
	 *   prop vaut `false` partout aujourd'hui. Elle existe pour que le chemin
	 *   existe — sans elle, un `pliee: true` posé demain dans la table ne
	 *   changerait rien à l'écran, et personne ne saurait pourquoi. */
	export let pliable = false;

	/**  Reçu, jamais écrit en dur : la déclaration gouverne le requis comme elle
	 *   gouverne le pliage, et les deux doivent s'accorder (22/09/2026). */
	export let requis = false;
	/** Première section rendue : elle ne porte pas de filet au-dessus. */
	export let premiere = false;
	/** Rangée en lecture seule — confort d'interface, jamais un droit. */
	export let lecture = false;
	/**  Le motif d'une section éteinte (`inactivePour`) — relayé tel quel.
	 *   Il manquait : l'affaire écrivait donc son Suivi à la main (#1329). */
	export let inactive = '';
</script>

<!--  `rempli` : l'étoile s'éteint dès qu'un état est choisi — elle restait
      rouge à vie sur l'affaire, qui ne le transmettait pas (#1329). -->
<SectionFormulaire
	{premiere}
	titre={SECTIONS_LIBELLE.suivi}
	{pliable}
	{requis}
	rempli={!!valeur}
	{badge}
	{idTitre}
	{inactive}
>
	<div class="field champ-large">
		<WorkflowPastilles {options} {valeur} {lecture} {idTitre} on:choisir />
	</div>
	<!--  Ce que l'hôte ajoute au Suivi (l'aide, le kanban d'une affaire). -->
	<slot />
</SectionFormulaire>
