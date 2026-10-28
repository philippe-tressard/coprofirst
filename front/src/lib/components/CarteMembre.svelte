<!--
  **La fiche modifiable d'une personne de l'annuaire** — conseil syndical et
  syndic, écrite une fois.

  ## Pourquoi ce composant (18/09/2026, #779)

  `espace-cs/+page.svelte` rendait DEUX fois la même fiche : le membre du conseil
  syndical, et celui du syndic. Trois cent vingt lignes de balisage pour ne varier
  que sur les champs propres à chacun — l'identité, le lien vers un inscrit, le
  geste de dépliage et la barre d'actions étaient recopiés au caractère près.

  C'est la troisième couche d'une même extraction : `ActionsMembre` a pris la
  barre d'actions (07/09), `#lib/listeDepliable` la mécanique déplier/éditer
  (#640, 01/09) — et il restait la fiche elle-même.

  ## 🔴 Et les deux copies avaient DIVERGÉ, chacune dans son coin

  | Ce qui différait | CS | Syndic |
  |---|---|---|
  | pied du formulaire (Enregistrer / Annuler) | oui | **non** |
  | ordre : champs propres ↔ lien inscrit | lien AU MILIEU | lien à la fin |
  | vue dépliée non éditée | localisation + lien | fonction, e-mail, téléphones |

  Aucune de ces différences n'était voulue : elles sont le produit mécanique de
  deux recopies. La première — un formulaire ouvert dont on ne peut sortir que
  par le crayon — est un vrai défaut d'usage, et c'est celle qui se voit le
  moins. Ce composant rend le pied dans les deux cas.

  Seule la troisième ligne reste une différence, et elle est maintenant
  **explicite** : deux appels, deux contenus de `<slot>` — relayés depuis le
  02/10/2026 par `AnnuaireMembres`, qui porte la liste (#1539).

  ## 🔴 La fiche est une CARTE DE LISTE, comme les onze autres du site

  Elle rendait son en-tête à la main, avec les deux défauts que `EnteteCarte`
  existe pour supprimer, et que `CarteContrat` et `CartePrestataire` portaient
  encore le mois dernier (12/09) :

  • le TITRE partageait sa ligne avec le badge et quatre icônes. Sur un
    téléphone, la ligne étant en `flex`, les éléments de largeur fixe gagnent et
    le nom se réduit à trois points — on lit un annuaire sans savoir de qui il
    parle. C'est **R1** : la responsivité appartient au squelette.
  • le geste était SYMÉTRIQUE (`role="button"` sur le conteneur). La norme du
    18/08 est asymétrique : repliée, toute la carte ouvre ; dépliée, seul le
    titre referme, pour qu'on puisse lire et copier son corps — et ici, saisir
    dans son formulaire sans qu'un clic le replie.

  `normes.css` nommait d'ailleurs cet écran (#453) parmi les listes « qui portent
  ENCORE leur propre balisage de ligne, en attendant leur découpage ».

  ## Ce que le composant porte, et ce qu'il laisse

  | Porté ici | Laissé à l'appelant |
  |---|---|
  | la carte, son en-tête, le geste asymétrique, l'accent de bordure | les champs propres, par les `<slot>` |
  | l'identité — civilité, prénom, NOM — et sa saisie | ce qu'on fait du NOM saisi (`on:nom`) |
  | le lien vers un inscrit : « Inscrit lié », « Délier », « Aucun inscrit » | qui est lié, par `membre.user_id` |
  | le pied Enregistrer / Annuler | ce que « enregistrer » veut dire, par `on:enregistrer` |

  ⚠️ `nomAffiche` n'est PAS recopié ici : il vient de `#lib/noms`, comme partout
  ailleurs (`npm run lint:noms` le refuse).
-->
<script context="module" lang="ts">
	import CarteListe from '#lib/components/CarteListe.svelte';
	import ChoixPastilles from '#lib/components/ChoixPastilles.svelte';
	/**
	 *  Ce que TOUT membre d'annuaire porte, quel que soit son côté.
	 *
	 *  🔴 Exporté depuis le module — même raison qu'`ActionsMembre` et
	 *  `CarteContact` : l'appelant s'en sert pour DÉRIVER ses propres formes
	 *  (`interface MembreCSForm extends MembreBase`). Deux définitions d'une même
	 *  chose divergeraient au premier champ ajouté ; ici, un champ ajouté à la
	 *  base arrive dans les deux.
	 */
	export interface MembreBase {
		genre: string;
		prenom: string;
		nom: string;
		/** L'inscrit rapproché de ce membre, ou `null` s'il n'en a pas. */
		user_id: number | null;
	}

	/**  Les civilités proposées, dans leur ordre.
	 *
	 *   Écrites ici et non dans chaque appel : les deux copies les listaient, et
	 *   une troisième fiche les aurait listées une troisième fois. */
	export const CIVILITES = ['Mme', 'Mlle', 'Mr'] as const;
</script>

<script lang="ts">
	import { createEventDispatcher } from 'svelte';

	import ActionsMembre, { type Geste } from '#lib/components/ActionsMembre.svelte';
	import EnteteCarte from '#lib/components/EnteteCarte.svelte';
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';
	import { nomAffiche } from '#lib/noms.ts';

	/** Le membre édité — lié par `bind:membre` pour que la saisie remonte. */
	export let membre: MembreBase;
	//  Le nom du groupe radio de la civilité, propre à CETTE carte : plusieurs
	//  cartes peuvent être en édition à la fois.
	const idCivilite = `membre-civilite-${Math.random().toString(36).slice(2, 8)}`;
	/** La carte est dépliée. */
	export let ouvert = false;
	/** La carte est dépliée ET en édition : le formulaire remplace le détail. */
	export let edite = false;
	/** Un enregistrement est en cours pour CE membre. */
	export let enregistrement = false;
	/** Gestes propres à l'écran, rendus avant le trio commun (ordre du syndic). */
	export let gestes: Geste[] = [];
	/**
	 *  La couleur de la bordure gauche, quand ce membre a un rôle particulier.
	 *  Deux valeurs, et pas une de plus : président du CS, interlocuteur
	 *  principal du syndic. Un troisième rôle s'ajoute ICI, pas dans une page.
	 */
	export let accent: 'president' | 'principal' | null = null;
	/**
	 *  Le détail déplié a son contenu PROPRE (emplacement `detail`) ; sinon la
	 *  fiche dépliée montre son résumé.
	 *
	 *  Une prop, et non `$$slots.detail` (#1539) : la fiche est montée par
	 *  `AnnuaireMembres`, qui RELAIE ses emplacements — un emplacement relayé
	 *  est toujours « rempli » aux yeux de l'enfant, même vide. C'est la liste,
	 *  qui voit ce que son appelant a écrit, qui le dit.
	 */
	export let detailPropre = false;

	const dispatch = createEventDispatcher<{
		basculer: void;
		editer: void;
		supprimer: void;
		enregistrer: void;
		annuler: void;
		/** Le NOM vient d'être saisi : l'appelant y rapproche ce qu'il sait. */
		nom: void;
		delier: void;
	}>();

	/**  « Aucun inscrit avec ce NOM » ne s'affiche qu'à partir de deux lettres :
	 *   en dessous, l'absence de correspondance ne dit rien. Le seuil était écrit
	 *   dans les deux copies, avec la même valeur. */
	$: sansCorrespondance = !membre.user_id && membre.nom.trim().length >= 2;
</script>

<!--  `role="presentation"` et non `role="button"` : le conteneur n'est plus
      interactif, c'est le TITRE qui l'est (cf. l'en-tête du fichier). Replié, un
      clic n'importe où déplie ; déplié, seul le titre referme. -->
<CarteListe
	class="carte-membre"
	data-accent={accent}
	expanded={ouvert}
	onDeplier={() => dispatch('basculer')}
>
	<EnteteCarte
		titre={`${membre.genre} ${nomAffiche(membre) || '…'}`}
		basculable
		on:toggle={() => dispatch('basculer')}
	>
		<!--  🔴 Le résumé occupe la LIGNE DE MÉTA de l'en-tête, il ne s'écrit pas en
		      dessous (signalé à l'écran le 18/09/2026 : « trop d'espace perdu »).
		      Posé sous l'en-tête, il faisait une TROISIÈME ligne — nom, ligne de
		      méta vide avec les seules actions, puis résumé — là où la fiche
		      précédente en tenait deux. `EnteteCarte` a cette ligne pour ça :
		      tags à gauche, actions à droite, sur la même. -->
		<svelte:fragment slot="tags">
			<slot name="badge" />
			{#if !ouvert}<slot name="resume" />{/if}
		</svelte:fragment>
		<svelte:fragment slot="actions">
			<ActionsMembre
				{gestes}
				enEdition={edite}
				{enregistrement}
				onEnregistrer={() => dispatch('enregistrer')}
				onModifier={() => dispatch('editer')}
				onSupprimer={() => dispatch('supprimer')}
			/>
		</svelte:fragment>
	</EnteteCarte>

	{#if ouvert}
		<div class="carte-corps carte-membre-corps">
			{#if edite}
				<div class="form-grid">
					<ChoixPastilles
						options={CIVILITES.map((c) => ({ val: c, label: c }))}
						bind:valeur={membre.genre}
						tous={false}
						libelle="Civilité"
						libelleVisible
						radio={idCivilite}
						defilante={false}
					/>
					<label class="field">
						Prénom
						<input type="text" bind:value={membre.prenom} placeholder="Prénom" />
					</label>
					<label class="field">
						NOM
						<input
							type="text"
							bind:value={membre.nom}
							placeholder="NOM"
							class="input-nom"
							on:input={() => dispatch('nom')}
						/>
					</label>
					<!--  Les champs propres à l'entité prennent place dans la MÊME grille :
					      une seconde grille en dessous aurait décalé leurs colonnes. -->
					<slot name="champs" />
				</div>

				<!--  Ce qui ne tient pas dans la grille — les téléphones du syndic, la
				      localisation et le rôle d'un membre du CS. -->
				<slot name="edition" />

				<div class="user-link-indicator">
					{#if membre.user_id}
						<span class="user-linked">
							<span>&#x1F517; Inscrit lié</span>
							<button type="button" class="btn-unlink" on:click={() => dispatch('delier')}>
								Délier
							</button>
						</span>
					{:else if sansCorrespondance}
						<span class="user-no-match">Aucun inscrit avec ce NOM</span>
					{/if}
				</div>

				<!--  🔴 Le pied est rendu pour les DEUX côtés. Le syndic n'en avait pas :
				      son formulaire ne se quittait que par le crayon, et « Annuler »
				      n'existait pas. C'est la divergence la moins visible des trois, et
				      la seule qui coûtait quelque chose à l'usage. -->
				<div class="carte-membre-pied">
					<PiedFormulaire
						enCours={enregistrement}
						soumission={false}
						petit
						on:enregistre={() => dispatch('enregistrer')}
						on:annule={() => dispatch('annuler')}
					/>
				</div>
			{:else}
				<!--  Faute de détail propre, la fiche montre son RÉSUMÉ. Ce n'est pas un
				      repli paresseux : la fiche du syndic avait exactement le même
				      contenu replié et déplié-non-édité, écrit DEUX fois. L'un des
				      deux serait tôt ou tard passé à côté d'un champ ajouté. -->
				{#if detailPropre}
					<slot name="detail" />
				{:else}
					<div class="membre-summary"><slot name="resume" /></div>
				{/if}

				<!--  Le lien vers un inscrit se dit AUSSI en lecture, et des deux côtés :
				      les deux copies l'affichaient, chacune avec son balisage. -->
				{#if membre.user_id}
					<div class="user-link-indicator">
						<span class="user-linked">&#x1F517; Inscrit lié</span>
					</div>
				{/if}
			{/if}
		</div>
	{/if}
</CarteListe>

<style>
	/*  ⚠️ Le composant porte son balisage ET son style — leçon de `Pastille.svelte`
	    (v2.67.11) : un style laissé dans la page hôte n'atteint pas le balisage
	    d'un enfant, et le composant part nu en production. */

	/*  `.carte-liste` (normes.css) donne déjà le fond, l'ombre, le rayon, la
	    bordure gauche et son survol. Ne restent ici que les DIFFÉRENCES d'une
	    fiche de membre : son fond propre, et l'accent de rôle. `:global` : ces
	    classes sont posées sur le conteneur que `CarteListe` rend, hors de la
	    portée de ce fichier ; bornées à `.carte-liste`, elles ne valent que là. */
	:global(.carte-liste.carte-membre) {
		background: var(--color-neutre-fond);
		border: 1px solid var(--color-border);
		border-left-width: 3px;
	}
	:global(.carte-liste.carte-membre[data-accent='president']) {
		border-left-color: var(--color-warning);
	}
	:global(.carte-liste.carte-membre[data-accent='principal']) {
		border-left-color: var(--color-accent);
	}

	/*  Le corps a son propre retrait : `EnteteCarte` porte le sien, et deux
	    padding superposés décaleraient le formulaire par rapport au titre. */
	/*  Le NOM s'affiche en capitales — la règle suit le balisage qu'elle habille,
	    et ce balisage vit ici désormais. */
	.input-nom {
		text-transform: uppercase;
	}

	.carte-membre-corps {
		padding: 0 0.9rem 0.75rem;
	}
	.carte-membre-pied {
		margin-top: 0.75rem;
	}

	.user-link-indicator {
		margin-top: 0.5rem;
	}
	.user-no-match {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
		font-style: italic;
	}
	.user-linked {
		display: inline-flex;
		align-items: center;
		gap: 0.6rem;
		font-size: var(--fs-sm);
		color: var(--color-success);
		background: var(--color-success-fond);
		border-radius: var(--radius);
		padding: 0.3rem 0.6rem;
		border: 1px solid var(--color-success-bordure);
	}
	.btn-unlink {
		font-size: var(--fs-xs);
		background: none;
		border: none;
		cursor: pointer;
		color: var(--color-text-muted);
		text-decoration: underline;
		padding: 0;
	}
	@media (hover: hover) and (pointer: fine) {
		.btn-unlink:hover {
			color: var(--color-danger);
		}
	}

	/*  Le repli du détail sur le résumé, carte DÉPLIÉE et non éditée. Repliée, le
	    résumé vit dans la ligne de méta de l'en-tête et n'a pas de conteneur ici. */
	.membre-summary {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.4rem;
	}

	@media (max-width: 480px) {
		.carte-membre-corps {
			padding-left: 0.7rem;
			padding-right: 0.7rem;
		}
	}
</style>
