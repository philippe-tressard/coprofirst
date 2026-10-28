<!--
  La liste des sondages — le `{#each}` et la carte, écrits **une seule fois**.

  ## Pourquoi ce composant existe (#515, 02/09/2026)

  L'onglet en rend maintenant **deux** : les sondages courants, et les Archives
  repliées — 30 jours après la date de clôture, règle du site portée par
  `app/utils/archivage.py`.

  🔴 Recopier le bloc `{#each}` sous la section repliée aurait fait soixante-dix
  lignes de carte en double. C'est ce que le rang 1 interdit, et ce qui est arrivé
  six fois au fil des tickets (#431). Troisième extraction de la même forme sur le
  même écran, après `ListeAnnonces` (18/08) et `ListeIdees` (ce jour) — les trois
  rubriques de Communauté ont enfin la même structure.

  ⚠️ Ce composant ne décide de RIEN : `s.cloture` et `s.archivee` sont tous deux
  calculés par le serveur. Le premier l'est depuis #468, après que la liste eut
  recalculé la clôture en JavaScript et divergé sur le fuseau ; le second l'est
  pour la même raison.

  Les gestes — arrêter, supprimer — restent chez le parent : c'est lui qui parle à
  l'API et recharge la liste.
-->
<script lang="ts">
	import type { Sondage } from '#lib/api/index.ts';
	import CarteListe from '#lib/components/CarteListe.svelte';
	import BadgeNouveau from '#lib/components/BadgeNouveau.svelte';
	import MarqueIA from '#lib/components/MarqueIA.svelte';
	import { fmtDateShort } from '#lib/date.ts';
	import BoutonLien from '#lib/components/BoutonLien.svelte';
	import EnteteCarte from '#lib/components/EnteteCarte.svelte';
	import IconeAction from '#lib/components/IconeAction.svelte';
	import ApercuCarte from '#lib/components/ApercuCarte.svelte';
	import BadgePerimetre from '#lib/components/BadgePerimetre.svelte';
	import PastilleLecture from '#lib/components/PastilleLecture.svelte';
	import { currentUser, isAdmin } from '#lib/stores/auth.ts';

	/** Les sondages à rendre, déjà filtrés par l'appelant. */
	export let sondages: Sondage[] = [];
	export let arreterSondage: (s: Sondage, e: Event) => void;
	export let supprimerSondage: (s: Sondage, e: Event) => void;
	/**  Corriger son sondage (#783). Même condition que « Stopper » : l'auteur
	 *   ou un admin, et **pas** un sondage clôturé — le serveur le refuse, et un
	 *   bouton qui déclencherait un refus serait pire qu'absent. */
	export let modifierSondage: (s: Sondage, e: Event) => void;
	/**  Le sondage en cours de correction, ou `null` (10/10/2026). Le
	 *   formulaire s'ouvre DANS sa carte, à la place de l'aperçu — le motif des
	 *   annonces et des idées (#787) ; la page le fournit par le slot
	 *   `formulaire`, elle seule tient l'état. */
	export let editId: number | null = null;
</script>

{#each sondages as s (s.id)}
	<!--  🗂️ LA CARTE DU STANDARD (10/10/2026, la page Affaires devenue celle du
	      site) : `.carte-liste`, la gouttière à gauche, l'aperçu dans l'en-tête et
	      les tags en dernière ligne. Un sondage n'a pas de CLASSEMENT — ni nature
	      ni type : la gouttière ne porte que sa date. Son état (Ouvert, Clôturé)
	      reste une capsule teintée de la dernière ligne, comme celui d'une affaire.

	      🔴 Un BLOC, et un lien qui en couvre la surface (#1329) : la carte était
	      un `<a>` qui contenait des boutons — HTML invalide, et un lecteur
	      d'écran y annonçait un lien géant. Le lien s'étire sous le contenu, les
	      boutons passent au-dessus.

	      ⚠️ Le lien est posé APRÈS la gouttière : elle est positionnée elle
	      aussi, et la dernière posée passe dessus — avant, un clic sur la date
	      n'aurait mené nulle part. -->
	<CarteListe class="sondage-card" quand={s.cree_le} expanded={editId === s.id}>
		<!--  Pendant la correction, la carte est OUVERTE (`expanded`) et son lien
		      se retire : il couvrirait les champs du formulaire. -->
		{#if editId !== s.id}
			<a class="lien-sondage" href="/sondages/{s.id}" aria-label="Ouvrir le sondage : {s.question}"
			></a>
		{/if}
		<!--  L'EN-TÊTE DU SITE (#794). `basculable` reste faux : la carte mène à la
		      fiche par son lien étiré ; un bouton de dépliage n'y aurait rien à
		      déplier. Sa date est dans la gouttière : un seul fait, une place. -->
		<EnteteCarte titre={s.question}>
			<svelte:fragment slot="titre-suffixe">
				<BadgeNouveau le={s.cree_le} />
			</svelte:fragment>
			<svelte:fragment slot="tags">
				<span class="badge" class:badge-gray={s.cloture} class:badge-green={!s.cloture}
					>{s.cloture ? '🔒 Clôturé' : 'Ouvert'}</span
				>
				<!--  État · 🔹 · qui le lit — l'ordre de la carte d'affaire (#1373) : le 🔹
				      n'est plus teinté en bleu, et la pastille de lecture a remplacé le
				      badge orange des destinataires. 🔴 PAS D'AUTEUR : un sondage reste
				      anonyme pour ses lecteurs (arbitré le 27/09/2026, `lint:pastilles`). -->
				<BadgePerimetre perimetre={s.perimetre_cible} />
				<PastilleLecture cible={s} masculin />
				{#if s.cloture_le && !s.cloture}
					<span class="badge badge-gray">Clôture le {fmtDateShort(s.cloture_le)}</span>
				{/if}
				<span class="badge badge-gray"
					>{s.nb_votants ?? 0} votant{(s.nb_votants ?? 0) !== 1 ? 's' : ''}</span
				>
				<MarqueIA assiste={s.assiste_ia} />
			</svelte:fragment>
			<svelte:fragment slot="actions">
				<!--  🔗 EN PREMIER : la seule action que TOUT le monde a. Sa position ne
				      doit pas dépendre des droits du lecteur. Même ordre que l'annonce
				      et l'idée. Un sondage a sa page : on copie SON adresse. -->
				<BoutonLien chemin="/sondages/{s.id}" quoi="le sondage" />
				{#if ($currentUser?.id === s.auteur_id || $isAdmin) && !s.cloture}
					<button
						class="btn-icon"
						aria-label="Modifier ce sondage"
						title="Modifier"
						aria-pressed={editId === s.id}
						on:click={(e) => modifierSondage(s, e)}><IconeAction icone="pencil" /></button
					>
					<button
						class="btn-icon-warn"
						aria-label="Stopper ce sondage"
						title="Stopper"
						on:click={(e) => arreterSondage(s, e)}><IconeAction icone="square" /></button
					>
				{/if}
				{#if $currentUser?.id === s.auteur_id || $isAdmin}
					<button
						class="btn-icon-danger"
						aria-label="Supprimer"
						title="Supprimer"
						on:click={(e) => supprimerSondage(s, e)}><IconeAction icone="trash-2" /></button
					>
				{/if}
			</svelte:fragment>
			<!--  L'aperçu passe par l'EN-TÊTE (18/09/2026) : c'est ce qui fait
			      descendre les tags en dernière ligne. Trois lignes, la typographie
			      de toutes les cartes (`ApercuCarte`). -->
			<svelte:fragment slot="apercu">
				{#if s.description && editId !== s.id}
					<ApercuCarte contenu={s.description} dansLigne />
				{/if}
			</svelte:fragment>
		</EnteteCarte>
		<!--  La correction ENTRE comme le corps d'une carte dépliée (`carte-corps`). -->
		{#if editId === s.id}
			<div class="carte-corps sondage-correction">
				<slot name="formulaire" />
			</div>
		{/if}
	</CarteListe>
{/each}

<style>
	/*  Conteneur, filet, survol, écart entre cartes et gouttière : `CarteListe`
	    (`normes.css`) — le survol y colore le titre et le liseré, ce qui dit
	    juste ici : toute la carte mène à la fiche. L'en-tête et ses tags :
	    `EnteteCarte`. L'aperçu : `ApercuCarte`. Ne reste ici que le lien étiré. */
	.lien-sondage {
		position: absolute;
		inset: 0;
		border-radius: inherit;
	}
	.lien-sondage:focus-visible {
		outline: 2px solid var(--color-primary);
		outline-offset: 2px;
	}
	.sondage-correction {
		padding: 0.75rem 1rem 1rem;
		border-top: 1px solid var(--color-border);
	}
	/*  Les gestes au-dessus du lien étiré : sinon il prendrait leurs clics.
	    `:global` : `.sondage-card` est posée sur le conteneur que `CarteListe`
	    rend — hors de la portée de ce fichier. */
	:global(.sondage-card button) {
		position: relative;
		z-index: 1;
	}
</style>
