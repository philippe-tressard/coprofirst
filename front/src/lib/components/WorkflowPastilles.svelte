<!--
  WorkflowPastilles.svelte — LA rangée d'états, écrite une fois.

  ## Pourquoi (18/08/2026)

  R3 exige que toute sélection se fasse par **pastilles arrondies, jamais un
  `<select>` nu** (#423). La règle a été posée sur les Tickets, constatée à
  l'écran, puis étendue le soir même aux Actualités, au Calendrier et aux Idées —
  et à la quatrième copie du même `{#each}` + `.wf-pastilles`, la duplication
  était devenue le vrai sujet (`standards/02`, rang 1).

  Le composant porte son balisage **et** son style. C'est la leçon de
  `Pastille.svelte` : une classe posée par un parent sur le balisage d'un enfant
  n'est pas atteinte par le `<style>` du parent, et les pastilles étaient parties
  nues en production (v2.67.11).

  ## Ce qu'il ne décide pas

  Ni la liste des états — elle vient de la source unique de chaque entité
  (`#lib/tickets`, `#lib/publications`…) —, ni le droit de la changer. L'appelant
  passe `lecture` quand le lecteur n'a pas la main : les pastilles se lisent
  alors, mais ne répondent pas. ⚠️ Le serveur refait le contrôle — ce que
  l'interface interdit n'est qu'un confort (`standards/03` §1).
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import Pastille from './Pastille.svelte';

	/** Les états proposables. Jamais écrits ici : ils viennent de l'entité. */
	export let options: { value: string; label: string }[] = [];
	/** L'état retenu. Une chaîne vide est un état comme un autre — c'est ce qui
	    permet au Calendrier d'offrir « — Pas de suivi Kanban » en première pastille. */
	export let valeur = '';
	/** Le lecteur peut-il changer l'état ? */
	export let lecture = false;
	/** Relie la rangée à son titre de section (les pastilles ne sont pas un
	    contrôle labelable : un `for` n'y associerait rien, et en silence). */
	export let idTitre = '';

	const dispatch = createEventDispatcher<{ choisir: string }>();
</script>

<div class="wf-pastilles" role="group" aria-labelledby={idTitre || undefined}>
	{#each options as o (o.value)}
		<Pastille
			active={valeur === o.value}
			on:click={() => {
				if (!lecture) dispatch('choisir', o.value);
			}}>{o.label}</Pastille
		>
	{/each}
</div>

<style>
	.wf-pastilles {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
</style>
