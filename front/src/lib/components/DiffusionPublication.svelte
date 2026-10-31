<!--
  DiffusionPublication.svelte — ce qu'une actualité publie EN PLUS des trois
  canaux : l'affiche de hall. Une **option** de la section 9 du cadre #430, rendue
  dans le créneau `options` de `SectionDiffusion` — les canaux, eux, appartiennent
  à l'objet.

  Née le 18/08/2026 (#433) de la coupure d'`OptionsPublication`, qui portait à la
  fois ce qui décrit une publication (épinglage, urgence, brouillon,
  confidentialité) et ce qui l'envoie, sous un drapeau `complet` réservant le
  second à la création. Le cadre a rendu ce mélange intenable : *les sections 1 à 8
  décrivent l'entité, la 9 est un acte*, et l'édition n'a pas la 9 — parce qu'*une
  correction n'est pas une nouvelle*, et que rejouer un canal à chaque faute de
  frappe rattrapée est l'incident du triple envoi WhatsApp du 14/08/2026.

  Le drapeau a disparu avec la coupure, et c'est le point : tant qu'il existait,
  la question « cet écran est-il complet ? » se reposait à chaque appelant. Elle
  se lit maintenant dans la déclaration — `sectionPresente(PUBLICATION, etat,
  'diffusion')` —, une fois, avec son motif.

  ⚠️ **L'affiche de hall n'est pas un canal de notification** : elle produit un
  PDF punaisé dans un hall, lu sans connexion. Elle reste donc hors de
  `CanauxNotification`, dont le contrat est « qui est prévenu ? ».

  🔴 **Ce composant ne rend PLUS les canaux (#498, 28/08/2026).** Il les rendait
  lui-même, et `FormulaireActualite` passait `avecCanaux={false}` pour éviter le
  doublon : les actualités étaient donc DANS l'objet Diffusion, mais leurs canaux
  le court-circuitaient. Conséquence — toute capacité ajoutée à l'objet ne les
  atteignait jamais. C'est le mécanisme exact que #498 décrit : *« tant qu'ils
  appellent le canal sans passer par l'objet, ajouter une capacité à l'objet ne
  les atteindra jamais »*.

  Ce composant ne porte donc plus que **la différence de l'actualité** — l'affiche
  de hall —, et il la rend dans le créneau `options` de `SectionDiffusion`, qui
  est sa place : *les options décident de ce qui est PUBLIÉ, les canaux de qui en
  est prévenu*. Ce que l'actualité gagne au passage, sans une ligne : l'avertissement
  « les fichiers ne partent pas par WhatsApp », et l'aperçu le jour où la
  publication aura son endpoint de composition.

  ⚠️ **Une actualité RÉSERVÉE n'a pas d'affiche de hall**, et la case le montre :
  réservée au périmètre (🔒, section Périmètre) ou au conseil (Destinataires =
  « Conseil syndical » seul, #1096). La valeur arrive en lecture seule : la règle
  qui la fait retomber vit chez l'hôte (`FormulaireTicket`) — et elle est
  **aussi** tenue côté serveur (`visibility.hors_du_hall`), qui seul décide.
-->
<script lang="ts">
	import { SEPARATEUR } from '#lib/separateurs.ts';

	//  ⚠️ `whatsapp`, `syndic` et `cs` ont disparu avec le rendu des canaux (#498).
	//  Les laisser en props inertes aurait été pire que de les retirer : l'appelant
	//  aurait continué de les lier, en croyant que ce composant en fait quelque
	//  chose, et le jour où l'objet aurait divergé rien ne l'aurait dit.
	export let annonceHall = false;
	/** Lecture seule : décidée par l'Accès ou les Destinataires, elle ferme l'affiche ici. */
	export let reservee = false;

	const idAideHall = `aide-hall-${Math.random().toString(36).slice(2, 8)}`;
</script>

<div class="bloc-hall">
	<label
		class="checkbox-field"
		class:desactivee={reservee}
		title={reservee
			? 'Indisponible : une actualité réservée ne peut pas être affichée dans un hall.'
			: "Génère l'affiche PDF à afficher dans le hall et l'envoie au CS du périmètre"}
	>
		<input
			type="checkbox"
			bind:checked={annonceHall}
			disabled={reservee}
			aria-describedby={reservee ? idAideHall : undefined}
		/>
		<span class="ico">&#x1F4C4;</span>
		<span>Créer une annonce Hall</span>
	</label>
</div>

{#if reservee}
	<p class="aide" id={idAideHall}>
		&#x1F4C4; L'affiche de hall est indisponible sur une actualité réservée{SEPARATEUR.tiret}au
		périmètre ou au conseil syndical : une affiche est punaisée dans un hall et lue par n'importe
		qui, sans connexion.
	</p>
{:else if annonceHall}
	<p class="aide">
		&#x1F4C4; Une affiche PDF sera générée à partir du titre, du contenu, du périmètre et de l'image
		de cette actualité, puis envoyée aux membres du CS du périmètre. Elle sera consultable dans <strong
			>Espace CS{SEPARATEUR.fleche}Annonces Hall</strong
		>.
	</p>
{/if}

<style>
	/*  `:global` parce que `.checkbox-field` est une classe partagée du thème —
	    même raison que dans `CanauxNotification.svelte`. */
	.bloc-hall :global(.checkbox-field) {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		font-size: var(--fs-base);
		cursor: pointer;
	}
	/*  Une case grisée doit se VOIR grisée, pas seulement refuser le clic. */
	.bloc-hall .desactivee {
		opacity: 0.5;
		cursor: not-allowed;
	}
	.bloc-hall {
		margin-bottom: 1rem;
	}
	.ico {
		font-size: 1.1em;
		line-height: 1;
	}
	@media (max-width: 480px) {
		.bloc-hall :global(.checkbox-field) {
			min-height: 44px;
		}
	}
</style>
