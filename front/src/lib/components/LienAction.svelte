<!--
  LienAction.svelte — une ACTION AU TRAIT qui est un lien : télécharger un
  fichier, ouvrir la fiche d'où vient une ligne.

  ## Pourquoi (10/10/2026, la page Affaires devenue le standard du site)

  Les actions d'une carte sont au trait — gris, Bleu Seine au survol
  (`IconeAction`). `IconeAction` ne dessine que le pictogramme : le bouton reste
  celui de son composant, et la règle de survol vise un `<button>`. Une action qui
  MÈNE quelque part n'est pas un bouton, c'est un lien — il garde le clic du
  milieu, l'ouverture dans un onglet, l'adresse au survol. Trois écrans en
  avaient besoin (documents de la résidence, rapports de diagnostic, carnet
  d'entretien) : la forme du lien s'écrit ici, une fois.

  Le MOT, quand l'action en a un (`mot`), reste au bureau : télécharger est
  l'action principale d'un document, et une flèche seule ne la dit pas aussi
  bien qu'un crayon dit « modifier ». Il ne disparaît qu'au téléphone
  (≤ 480 px), où la ligne du titre n'a plus la place — le nom accessible
  (`libelle`), lui, le dit toujours.

  Le clic ne remonte pas : dans une carte, suivre le lien ne la déplie pas.
-->
<script lang="ts">
	import IconeAction from './IconeAction.svelte';

	/** L'adresse — rendue par le client d'API ou le serveur, jamais composée ici. */
	export let href: string;
	/** Le pictogramme au trait (`#lib/icones-svg.json`). */
	export let icone: string;
	/** Le nom accessible, complet : « Télécharger le rapport », « Ouvrir le contrat ». */
	export let libelle: string;
	/** L'infobulle, courte (« Télécharger », « Ouvrir ») ; le libellé sinon. */
	export let titre = '';
	/** Le mot affiché à côté du pictogramme, au bureau ; rien = l'icône seule. */
	export let mot = '';
	/** Le lien TÉLÉCHARGE un fichier : nouvel onglet, attribut `download`. */
	export let telecharger = false;
</script>

<a
	class="lien-action"
	{href}
	target={telecharger ? '_blank' : undefined}
	rel={telecharger ? 'noopener' : undefined}
	download={telecharger ? '' : undefined}
	title={titre || libelle}
	aria-label={libelle}
	on:click|stopPropagation
	><IconeAction {icone} />{#if mot}<span class="mot">{mot}</span>{/if}</a
>

<style>
	/*  La hauteur des actions d'une carte (26 px, 32 au doigt — `EnteteCarte`) :
	    le lien se range dans la même rangée sans ouvrir de blanc sous le titre. */
	.lien-action {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 0.25rem;
		height: 26px;
		min-width: 26px;
		padding: 0 0.3rem;
		border-radius: var(--radius);
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
		text-decoration: none;
		white-space: nowrap;
		transition: color var(--duree-geste) var(--ease-out);
	}
	@media (hover: hover) and (pointer: fine) {
		.lien-action:hover,
		.lien-action:hover :global(.icone-action) {
			color: var(--color-primary);
		}
	}
	.lien-action:focus-visible {
		outline: 2px solid var(--color-primary);
		outline-offset: 2px;
	}
	@media (max-width: 480px) {
		.lien-action {
			height: 32px;
			min-width: 32px;
		}
		.mot {
			display: none;
		}
	}
</style>
