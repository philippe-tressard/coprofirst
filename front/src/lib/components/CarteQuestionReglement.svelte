<!--
  UNE question posée au règlement de copropriété, et l'avis du juriste.

  La carte suit le modèle commun (`ux-patterns` §3) : repliée, toute la carte
  ouvre ; dépliée, seul le titre referme. Repliée, on lit la question, le
  verdict et l'aperçu de la réponse ; dépliée, la réponse entière, les extraits
  et les réserves — sous la mention de l'avis, en tête et en italique.

  ## 🔴 Un extrait se lit avec ce que le CODE en a vérifié

  Le serveur recherche chaque citation dans le texte chargé (`verifie`), et en
  déduit la page et l'acte. Un extrait retrouvé montre ce repère ; un extrait
  NON retrouvé le dit en clair, avec la référence que le modèle a donnée — un
  avis dont une citation est fausse a l'air vérifiable, et c'est le pire cas.

  La publication dans la FAQ s'ouvre DANS la carte (créneau `formulaire`) : le
  geste est sur la question, la boîte aussi (`ux-patterns` §14 ter).
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import CarteListe from '#lib/components/CarteListe.svelte';
	import ApercuCarte from '#lib/components/ApercuCarte.svelte';
	import AuteurCarte from '#lib/components/AuteurCarte.svelte';
	import BadgeVerdict from '#lib/components/BadgeVerdict.svelte';
	import BoutonLien from '#lib/components/BoutonLien.svelte';
	import EnteteCarte from '#lib/components/EnteteCarte.svelte';
	import ExtraitsReglement from '#lib/components/ExtraitsReglement.svelte';
	import IconeAction from '#lib/components/IconeAction.svelte';
	import type { QuestionReglement } from '#lib/api/index.ts';
	import { fmtDatetime } from '#lib/date.ts';
	import { safeHtml } from '#lib/sanitize.ts';
	import { isCS } from '#lib/stores/auth.ts';

	export let q: QuestionReglement;
	/** La carte est-elle dépliée ? L'état vit dans l'onglet : une seule ouverte. */
	export let ouvert = false;
	/** La boîte « Publier dans la FAQ » est-elle ouverte sur cette carte ? */
	export let publication = false;

	const dispatch = createEventDispatcher<{ basculer: void; publier: void; supprimer: void }>();

	$: verifies = q.extraits.filter((e) => e.verifie).length;
	$: extraitsAg = q.extraits.filter((e) => e.source === 'ag');
	$: extraitsReglement = q.extraits.filter((e) => e.source !== 'ag');
</script>

<!--  La GOUTTIÈRE de la page Affaires, standard du site (10/10/2026) : la date
      de la question, et RIEN dessous. Une question n'a pas de rubrique ; son
      verdict est un ÉTAT — teinté, il se lit en capsule sur la dernière ligne,
      comme l'état d'une affaire. Le ranger dans la colonne qui CLASSE en ferait
      une nature, et la gouttière prendrait sa teinte au lieu de celle de la
      charte. L'heure, que la gouttière n'écrit pas, passe au pied de l'avis
      (« Posée le … »). -->
<CarteListe
	id="question-reglement-{q.id}"
	quand={q.cree_le}
	expanded={ouvert || publication}
	onDeplier={() => dispatch('basculer')}
>
	<EnteteCarte titre={q.question} basculable on:toggle={() => dispatch('basculer')}>
		<svelte:fragment slot="actions">
			<BoutonLien ancre="question-reglement-{q.id}" quoi="la question" />
			<!--  Le conseil seul publie (11/10/2026) : le copropriétaire lit sa réponse,
			      il ne la verse pas à la FAQ. Le serveur refuse aussi. -->
			{#if $isCS && !q.faq_item_id}
				<button
					class="btn-icon-edit"
					aria-label="Publier dans la FAQ"
					title="Publier dans la FAQ"
					aria-pressed={publication}
					on:click|stopPropagation={() => dispatch('publier')}
					><IconeAction icone="book-open-check" /></button
				>
			{/if}
			<!--  Son auteur et l'administration (11/10/2026) — le serveur le dit. -->
			{#if q.peut_supprimer}
				<button
					class="btn-icon-danger"
					aria-label="Supprimer la question"
					title="Supprimer la question et sa réponse"
					on:click|stopPropagation={() => dispatch('supprimer')}
					><IconeAction icone="trash-2" /></button
				>
			{/if}
		</svelte:fragment>
		<svelte:fragment slot="apercu">
			{#if !ouvert && !publication}
				<ApercuCarte contenu={q.reponse} />
			{/if}
		</svelte:fragment>
		<svelte:fragment slot="tags">
			<BadgeVerdict verdict={q.verdict} libelle={q.verdict_libelle} />
			{#if q.extraits.length}
				<span class:alerte={verifies < q.extraits.length}
					>{verifies}/{q.extraits.length} extrait{q.extraits.length > 1 ? 's' : ''} vérifié{verifies >
					1
						? 's'
						: ''}</span
				>
			{/if}
			{#if !q.texte_en_vigueur}
				<span class="alerte">Texte remplacé depuis</span>
			{/if}
			{#if q.faq_item_id}
				<span>📚 Dans la FAQ</span>
			{/if}
			<AuteurCarte nom={q.auteur_nom} />
		</svelte:fragment>
	</EnteteCarte>

	{#if publication}
		<!--  Le formulaire ne referme pas la carte qu'on publie. -->
		<div
			class="carte-corps corps"
			role="presentation"
			on:click|stopPropagation
			on:keydown|stopPropagation
		>
			<slot name="formulaire" />
		</div>
	{:else if ouvert}
		<!--  Le corps ne referme pas la carte : on lit, on sélectionne, on copie. -->
		<div class="carte-corps corps lecture" role="presentation" on:click|stopPropagation>
			<!--  La mention en TÊTE, en italique (arbitré sur maquette le 11/10/2026) :
			      on sait ce qu'on lit avant de le lire. Ni le coût — l'exploitation
			      se lit dans Admin › Assistant IA —, ni la date de chargement des
			      fichiers, qui ne disait pas QUELS actes ont été lus : la provenance
			      saisie par l'administration le dit (`provenance`). -->
			<p class="aide mention">
				Posée le {fmtDatetime(q.cree_le)}. Avis indicatif, qui ne se substitue pas aux actes
				authentiques.
				{#if q.modele && q.provenance}Rédigé par {q.modele}, d'après {q.provenance}.
				{:else if q.modele}Rédigé par {q.modele}.
				{:else if q.provenance}Rédigé d'après {q.provenance}.{/if}
			</p>
			<div class="rich-content">{@html safeHtml(q.reponse)}</div>

			<!--  En SECTIONS depuis le 29/10/2026 : d'après le règlement, d'après les
			      AG, la synthèse des deux. Un avis plus ancien n'a que sa réponse, et
			      se lit comme avant. Un extrait va sous la source où le CODE l'a
			      retrouvé (`source`) — un extrait non retrouvé reste avec le règlement. -->
			{#if q.selon_reglement}
				<h4 class="intertitre">D'après le règlement</h4>
				<div class="rich-content">{@html safeHtml(q.selon_reglement)}</div>
			{/if}
			<ExtraitsReglement titre="Extraits du règlement" extraits={extraitsReglement} />
			{#if q.selon_ag}
				<h4 class="intertitre">D'après les assemblées générales</h4>
				<div class="rich-content">{@html safeHtml(q.selon_ag)}</div>
			{/if}
			<ExtraitsReglement titre="Extraits des décisions d'AG" extraits={extraitsAg} />
			{#if q.synthese}
				<h4 class="intertitre">Synthèse</h4>
				<div class="rich-content">{@html safeHtml(q.synthese)}</div>
			{/if}

			{#if q.reserves}
				<h4 class="intertitre">Réserves</h4>
				<div class="rich-content">{@html safeHtml(q.reserves)}</div>
			{/if}
		</div>
	{/if}
</CarteListe>

<style>
	/*  Le retrait de l'en-tête (`EnteteCarte`, 0,7 rem) : le corps s'aligne sur le titre. */
	.corps {
		padding: 0 0.7rem 0.75rem;
	}
	/*  La phrase grise est `.aide` (`ux-patterns` §9 bis bis) ; en tête, elle
	    prend l'italique et sa marge passe dessous. */
	.mention {
		margin: 0 0 0.6rem;
		font-style: italic;
	}
	.lecture {
		font-size: var(--fs-base);
		line-height: 1.55;
	}
	.alerte {
		color: var(--color-warning-texte);
	}
</style>
