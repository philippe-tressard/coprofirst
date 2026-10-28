<!--
  La liste des idées — le `{#each}` et la carte, écrits **une seule fois**.

  ## Pourquoi ce composant existe (#515, 02/09/2026)

  L'onglet en rend maintenant **deux** : les idées courantes, et les Archives
  repliées — 30 jours après la décision (retenue, réalisée ou rejetée), règle du
  site portée par `app/utils/archivage.py`.

  🔴 Le premier réflexe est de recopier le bloc `{#each}` sous la section
  repliée : soixante-dix lignes de carte. C'est exactement ce que le rang 1
  interdit, et l'histoire du projet dit pourquoi — le fil des tickets a été rendu
  à la main six fois, et les copies avaient divergé sur les pièces jointes, la
  marge et jusqu'au libellé des boutons (#431).

  Même patron que `ListeAnnonces`, extrait le 18/08 pour la même raison, sur la
  rubrique voisine du même écran.

  ## Ce qui reste chez le parent

  **Le rendu part, les gestes restent.** Voter, changer un état, supprimer,
  répondre : tout cela touche l'API et l'état partagé de la page. Les passer en
  callbacks garde un seul endroit qui parle au serveur.

  ⚠️ Ce composant ne décide PAS de ce qui est archivé : `idee.archivee` est
  calculé par le serveur. Refaire la règle ici en ferait une seconde, et les deux
  trancheraient différemment le jour où le délai change — c'est le bug du
  17/07/2026 sur les actualités, un élément visible dans une vue et pas dans
  l'autre.
-->
<script lang="ts">
	import Badge from '#lib/components/Badge.svelte';
	import CarteListe from '#lib/components/CarteListe.svelte';
	import BadgeNouveau from '#lib/components/BadgeNouveau.svelte';
	import MarqueIA from '#lib/components/MarqueIA.svelte';
	import EnteteCarte from '#lib/components/EnteteCarte.svelte';
	import IconeAction from '#lib/components/IconeAction.svelte';
	import ApercuCarte from '#lib/components/ApercuCarte.svelte';
	import BoutonLien from '#lib/components/BoutonLien.svelte';
	import WorkflowPastilles from '#lib/components/WorkflowPastilles.svelte';
	import Reponses from '#lib/components/Reponses.svelte';
	import BadgePerimetre from '#lib/components/BadgePerimetre.svelte';
	import PastilleLecture from '#lib/components/PastilleLecture.svelte';
	import { STATUTS_IDEE, STATUT_IDEE_LABELS } from '#lib/idees.ts';
	import type { Idee } from '#lib/api/index.ts';

	/** Les idées à rendre, déjà filtrées et triées par l'appelant. */
	import { peutEditer } from '#lib/droits.ts';

	export let idees: Idee[] = [];
	export let currentUserId: number | undefined = undefined;
	export let estCS = false;
	export let estAdmin = false;
	export let statutClass: (s: string) => string;

	export let onVoter: (id: number) => void;
	export let onChangerStatut: (id: number, statut: string) => void;
	export let onSupprimer: (id: number) => void;
	/**  Corriger son idée (#783). Comme sur la petite annonce, le geste est
	 *   réservé à l'AUTEUR — le conseil syndical décide du statut, il ne réécrit
	 *   pas la proposition de quelqu'un (`peut_editer` côté serveur). */
	export let onModifier: (idee: Idee) => void;
	/**  L'identifiant de l'idée en cours de correction, ou `null` (#787).
	 *
	 *   🔴 Le formulaire s'ouvrait EN BAS DE PAGE : « c'est tout en bas, et on ne
	 *   voit pas ». Il remplace désormais la description, DANS la carte — la carte
	 *   d'actualité porte ce slot depuis longtemps, celle-ci ne l'avait pas.
	 *
	 *   ⚠️ Une idée ne se déplie pas (« elle montre tout ») : il n'y a donc pas de
	 *   corps à ouvrir, seulement une description à remplacer. */
	export let editId: number | null = null;
	export let onSignaler: (cibleType: string, cibleId: number) => void;
	export let onRepondre: (id: number, contenu: string) => Promise<void> | void;
	export let onSupprimerReponse: (id: number, reponseId: number) => void;
</script>

{#each idees as idee (idee.id)}
	<!--  🗂️ LA CARTE DU STANDARD (10/10/2026, la page Affaires devenue celle du
	      site) : `.carte-liste`, la gouttière à gauche, l'aperçu dans l'en-tête et
	      les tags en dernière ligne. Une idée n'a pas de CLASSEMENT — ni nature ni
	      type : la gouttière ne porte que sa date, puis son VOTE, qui tenait déjà
	      lieu de colonne gauche. Rien n'est inventé pour remplir la case. -->
	<CarteListe id="idee-{idee.id}" quand={idee.cree_le}>
		<svelte:fragment slot="gouttiere">
			<!--  Au trait, comme toutes les actions : le CŒUR VIDE dit « pas voté »,
			      le cœur PLEIN « voté ». `aria-pressed` le dit au lecteur d'écran, que
			      les deux émojis ❤️/🤍 laissaient sans état. -->
			<button
				type="button"
				class="vote-btn"
				class:voted={idee.mon_vote}
				aria-pressed={!!idee.mon_vote}
				aria-label="{idee.mon_vote
					? 'Retirer mon vote'
					: 'Voter pour cette idée'} — {idee.nb_votes} vote{idee.nb_votes > 1 ? 's' : ''}"
				title={idee.mon_vote ? 'Retirer mon vote' : 'Voter pour cette idée'}
				on:click={() => onVoter(idee.id)}
			>
				<IconeAction icone="heart" />
				<span class="vote-count">{idee.nb_votes}</span>
			</button>
		</svelte:fragment>
		<!--  🔴 L'EN-TÊTE DU SITE (18/08/2026, signalé à l'écran : « l'état sur une
		      2nde ligne après le titre »). `basculable` reste faux — une idée ne se
		      déplie pas, elle montre tout. Sa date est dans la gouttière : elle
		      n'est plus passée à l'en-tête — un seul fait, une place. -->
		<EnteteCarte titre={idee.titre}>
			<svelte:fragment slot="titre-suffixe">
				<BadgeNouveau le={idee.cree_le} />
			</svelte:fragment>
			<svelte:fragment slot="tags">
				<Badge teinte={statutClass(idee.statut)}
					>{STATUT_IDEE_LABELS[idee.statut] ?? idee.statut}</Badge
				>
				<!--  État · 🔹 · qui la lit · ✨ — l'ordre de la carte d'affaire (#1373).
				      🔴 PAS D'AUTEUR : arbitré le 27/09/2026, une idée reste anonyme
				      pour ses lecteurs — aucune API ne l'expose, et l'exposer serait
				      une décision de données personnelles. `lint:pastilles` le tient. -->
				<BadgePerimetre perimetre={idee.perimetre_cible} />
				<PastilleLecture cible={idee} />
				<MarqueIA assiste={idee.assiste_ia} />
			</svelte:fragment>
			<!--  TOUTES les actions dans l'en-tête, dans l'ordre de la carte d'affaire :
			      🔗 · ✏️ · 🚩 · 🗑️ (ux-patterns §3). Le 🚩 était posé seul entre la
			      description et les réponses, la corbeille de l'administrateur sous la
			      rangée de workflow : deux actions du même objet, deux autres endroits. -->
			<svelte:fragment slot="actions">
				<!--  🔗 EN PREMIER, et c'est délibéré : c'est la seule action que TOUT le
				      monde a. Placée après ✏️, sa position dépendrait des droits du lecteur
				      — elle sauterait d'un cran selon qu'on est l'auteur ou non. Même ordre
				      que la petite annonce. -->
				<BoutonLien ancre="idee-{idee.id}" quoi="l'idée" />
				{#if peutEditer(idee, currentUserId, estAdmin)}
					<button
						class="btn-icon"
						title="Modifier"
						aria-label="Modifier l'idée"
						aria-pressed={editId === idee.id}
						on:click|stopPropagation={() => onModifier(idee)}><IconeAction icone="pencil" /></button
					>
				{/if}
				{#if idee.auteur_id !== currentUserId}
					<button
						class="btn-icon"
						title="Signaler cette idée au conseil syndical"
						aria-label="Signaler cette idée"
						on:click|stopPropagation={() => onSignaler('idee', idee.id)}
						><IconeAction icone="flag" /></button
					>
				{/if}
				<!--  Réservée à l'administrateur, comme dans la rangée du conseil où elle
				      vivait (`$isCS` inclut l'admin : la condition était la même). -->
				{#if estAdmin}
					<button
						class="btn-icon-danger"
						aria-label="Supprimer cette idée"
						title="Supprimer cette idée"
						on:click|stopPropagation={() => onSupprimer(idee.id)}
						><IconeAction icone="trash-2" /></button
					>
				{/if}
			</svelte:fragment>
			<!--  L'aperçu passe par l'EN-TÊTE (18/09/2026) : c'est ce qui fait
			      descendre les tags en dernière ligne. Trois lignes, la typographie
			      de toutes les cartes (`ApercuCarte`). La correction le remplace. -->
			<svelte:fragment slot="apercu">
				{#if editId !== idee.id}
					<ApercuCarte contenu={idee.description} dansLigne />
				{/if}
			</svelte:fragment>
		</EnteteCarte>

		<div class="idee-suite">
			<!--  La correction remplace l'aperçu, DANS la carte (#787) — et elle
			      ENTRE comme le corps d'une carte dépliée (`carte-corps`). -->
			{#if editId === idee.id}
				<div class="carte-corps">
					<slot name="formulaire" {idee} />
				</div>
			{/if}

			{#if estCS}
				<!--  Workflow en PASTILLES, jamais un `<select>` nu (R3, #423). -->
				<div class="idee-actions">
					<WorkflowPastilles
						options={STATUTS_IDEE}
						valeur={idee.statut}
						on:choisir={(e) => onChangerStatut(idee.id, e.detail)}
					/>
				</div>
			{/if}

			<Reponses
				reponses={idee.reponses ?? []}
				{currentUserId}
				isCS={estCS}
				placeholder="Votre réponse à cette idée…"
				onSubmit={(c) => onRepondre(idee.id, c)}
				onDelete={(rid) => onSupprimerReponse(idee.id, rid)}
				onReport={(rid) => onSignaler('reponse', rid)}
			/>
		</div>
	</CarteListe>
{/each}

<style>
	/*  🔴 Ces règles VOYAGENT avec le balisage qu'elles habillent. Svelte scope
	    les styles au composant qui rend l'élément : les laisser dans la page
	    aurait livré les cartes NUES en production — c'est la panne des pastilles
	    de la v2.67.11, refaite deux fois depuis.

	    Conteneur, filet, survol, écart entre cartes et gouttière : `CarteListe`
	    (`normes.css`). L'en-tête et ses tags : `EnteteCarte`. L'aperçu :
	    `ApercuCarte`. Ne reste ici que ce qui est propre à une idée.

	    Une idée ne se DÉPLIE pas : `normes.css` ne lui pose ni curseur ni titre
	    coloré au survol (ils sont réservés à une carte dont le titre est un
	    bouton). */
	/*  Sous l'en-tête : le rembourrage horizontal est celui d'`EnteteCarte`, pour
	    que la rangée de workflow et les réponses partent du même bord que le
	    titre. */
	.idee-suite {
		padding: 0 1.1rem 0.75rem;
	}
	.idee-actions {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
		margin-top: 0.25rem;
	}

	/*  Le vote, dans la gouttière, sous la date. Le chiffre est en chasse fixe :
	    il change à chaque clic, la colonne ne doit pas bouger. Aucune animation
	    sur le cœur — un geste qu'on refait souvent ne s'anime pas
	    (`emil-design-eng`) ; seules les couleurs passent, en 200 ms. */
	.vote-btn {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.2rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		padding: 0.4rem 0.55rem;
		cursor: pointer;
		min-width: 3rem;
		color: var(--color-text-muted);
		transition:
			border-color var(--duree-geste) var(--ease-out),
			background-color var(--duree-geste) var(--ease-out),
			color var(--duree-geste) var(--ease-out);
	}
	@media (hover: hover) and (pointer: fine) {
		.vote-btn:hover {
			border-color: var(--color-primary);
		}
	}
	.vote-btn:focus-visible {
		outline: 2px solid var(--color-primary);
		outline-offset: 2px;
	}
	.vote-btn.voted {
		border-color: var(--color-primary);
		background: var(--color-primary-light);
		color: var(--color-primary);
	}
	/*  Voté : le cœur se REMPLIT. Au trait seul, « voté » et « pas voté » ne se
	    distinguaient plus que par la couleur — un état qui ne tient qu'à la
	    couleur n'existe pas pour tout le monde. */
	.vote-btn.voted :global(svg) {
		fill: currentColor;
	}
	.vote-count {
		font-size: var(--fs-md);
		font-weight: 700;
		color: var(--color-primary);
		font-variant-numeric: tabular-nums;
	}
	/*  Au pouce, la gouttière est une LIGNE au-dessus du titre : le vote s'y
	    couche, cœur et chiffre côte à côte, pour ne pas la rehausser. */
	@media (max-width: 480px) {
		.vote-btn {
			flex-direction: row;
			gap: 0.35rem;
			padding: 0.25rem 0.55rem;
			min-height: 32px;
		}
		.idee-suite {
			padding: 0 0.7rem 0.55rem;
		}
	}
</style>
