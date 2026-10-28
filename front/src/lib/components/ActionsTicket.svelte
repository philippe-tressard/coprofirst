<!--
  ActionsTicket.svelte — la rangée d'icônes d'une carte de ticket.

  ## Pourquoi (12/09/2026)

  `CarteTicket` a reçu le bouton d'options rapides, et le contrôle de modularité
  a refusé qu'elle grossisse — à raison. La bonne réponse n'était pas de raboter :
  cette rangée est **exactement** ce qu'`ActionsActualite` est aux actualités, et
  elle vivait encore dans la carte. Le voisin avait déjà la bonne forme ; il
  suffisait de s'aligner dessus.

  ⚠️ Elle ne décide de rien : chaque icône émet, la carte relaie, la page agit.
  Les DROITS arrivent calculés (`peutSuivre`, `peutEditer`, `peutAdministrer`) —
  les recalculer ici en ferait une seconde lecture de la même règle.

  🔴 L'ORDRE des icônes est celui de tout le site — 🔗 · 🔄 · ✏️ · options · 🗑️ —
  arbitré le 18/08/2026 sur cette carte précisément. 💬 Répondre (23/10/2026,
  *« cette icône doit être sur l'affaire »*) se range après 🔗 : les deux gestes
  qui mènent à la page de l'affaire, puis ceux qui la changent.
-->
<script lang="ts">
	import { SUITE } from '#lib/gestes.ts';
	import { gesteReponse } from '#lib/tickets.ts';
	import { isCS } from '#lib/stores/auth.ts';
	import { createEventDispatcher } from 'svelte';
	import BoutonLien from './BoutonLien.svelte';
	import BoutonOptions from './BoutonOptions.svelte';
	import IconeAction from './IconeAction.svelte';
	import type { Ticket } from '#lib/api/index.ts';

	export let ticket: Ticket;
	/** Le mode ouvert sur la carte — il inverse l'icône qui l'a ouvert. */
	export let mode: 'lecture' | 'edition' | 'evolution' | 'options' = 'lecture';
	export let peutSuivre = false;
	export let peutEditer = false;
	export let peutAdministrer = false;
	/** Rendue aux Archives : 🗑️ y remplace 📦 (`ux-patterns` §8). */
	export let archive = false;

	//  Qui peut répondre, et ce que le bouton dit : la règle du fil des messages.
	$: reponse = gesteReponse(ticket);

	const dispatch = createEventDispatcher<{
		repondre: void;
		evoluer_ouvrir: void;
		modifier: void;
		options_ouvrir: void;
		supprimer: void;
		archiver: void;
	}>();
</script>

<!--  UN point d'entrée (#426) : le formulaire porte les deux gestes.
	      L'ordre des icônes — 🔄 puis ✏️ puis 🗑️ — est celui de toutes les
	      cartes du site, arbitré le 18/08/2026 sur celle-ci. -->
<!--  `aria-pressed` : le MODE se lit sur l'icône qui l'a ouvert, pas sur un
	      titre au-dessus du formulaire (18/08/2026). Elle s'inverse et grossit —
	      style dans `app.css`, une seule fois pour tout le site. -->
<!--  Un ticket a sa PAGE : c'est elle qu'on envoie, pas l'ancre d'une carte
	      dans une liste que le destinataire n'a peut-être pas le droit de voir
	      en entier. Même adresse que `lien_ticket()` côté API. -->
<BoutonLien chemin="/tickets/{ticket.id}" quoi="l'affaire" />
{#if reponse}
	<button
		class="btn-icon"
		aria-label={reponse.libelle}
		title={reponse.libelle}
		on:click|stopPropagation={() => dispatch('repondre')}
		><IconeAction icone={reponse.icone} /></button
	>
{/if}
{#if peutSuivre}
	<button
		class="btn-icon"
		aria-pressed={mode === 'evolution'}
		aria-label={SUITE.libelle}
		title={SUITE.libelle}
		on:click|stopPropagation={() => dispatch('evoluer_ouvrir')}
		><IconeAction icone="refresh-cw" /></button
	>
{/if}
{#if peutEditer}
	<!--  « Modifier » tout court, comme l'actualité (21/09/2026, signalé à
	      l'écran) : l'infobulle disait « Modifier le ticket », le mot du
	      modèle. Nommer l'objet ici n'apprend rien — on est sur sa carte. -->
	<button
		class="btn-icon"
		aria-pressed={mode === 'edition'}
		aria-label="Modifier"
		title="Modifier"
		on:click|stopPropagation={() => dispatch('modifier')}><IconeAction icone="pencil" /></button
	>
{/if}
<!--  ⚠️ La corbeille NE SUIT PAS le droit d'édition : supprimer
	      définitivement est irréversible, et cela reste à l'administrateur.
	      Elle s'était retrouvée dans le bloc du crayon en une passe de
	      réécriture — trois lignes plus bas, et le geste changeait de main. -->
<!--  Les options ACTIVES, et le chemin court pour les changer. Le crayon
	      ouvre tout — périmètre, description, pièces jointes — là où
	      dépingler ne touche qu'une case. Même bouton qu'aux actualités. -->
{#if peutEditer}
	<BoutonOptions
		objet={{
			epingle: ticket.epingle ?? false,
			urgente: ticket.priorite === 'haute',
			brouillon: ticket.confidentiel ?? false,
		}}
		ouvert={mode === 'options'}
		onOuvrir={() => dispatch('options_ouvrir')}
	/>
{/if}
<!--  ⚠️ La corbeille NE SUIT PAS le droit d'édition : supprimer
	      définitivement est irréversible, et cela reste à l'administrateur.
	      🔴 Et seulement aux ARCHIVES (24/09/2026) : dans la liste, le conseil
	      ARCHIVE (📦) — un clic de trop n'y efface plus rien. -->
{#if !archive && $isCS}
	<button
		class="btn-icon"
		aria-label="Archiver"
		title="Archiver — rejoint l'onglet Archives"
		on:click|stopPropagation={() => dispatch('archiver')}><IconeAction icone="archive" /></button
	>
{:else if archive && peutAdministrer}
	<button
		class="btn-icon-danger"
		aria-label="Supprimer"
		title="Supprimer définitivement"
		on:click|stopPropagation={() => dispatch('supprimer')}><IconeAction icone="trash-2" /></button
	>
{/if}
