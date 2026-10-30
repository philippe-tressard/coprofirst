<!--
  L'avertissement légal des affaires marquées « 🚨 Urgent ».

  POURQUOI CE COMPOSANT EXISTE. Extrait de `tickets/+page.svelte` le 16/08/2026,
  quand cette page a franchi les 500 lignes du rang 1 en accueillant la boîte de
  création (`standards/02` §6). Le découpage se fait « au fil de l'eau » : on sort
  du fichier ce qui s'en détache le plus proprement, et c'est ce bloc-ci.

  C'est un gain de STRUCTURE, pas un artifice pour faire baisser un compteur
  (`standards/02` §6, règle du 16/08/2026) : ce bloc a sa propre responsabilité —
  un texte juridique — son propre état d'ouverture, et aucune dépendance à la
  logique des tickets. Il ne partage avec la page ni donnée ni comportement. Son
  nom se justifie seul, et sa raison de changer lui est propre : elle est
  réglementaire, pas fonctionnelle. C'est le critère du §6 pour qu'un découpage
  vaille quelque chose.

  ⚠️ AUCUN mot de ce texte n'a été modifié en le déplaçant, et son état
  d'ouverture reste replié par défaut : le comportement est identique à l'octet
  près. Ce qui disparaît en premier dans une extraction, ce sont les choses qui ne
  se voient pas au rendu nominal — ici, il n'y a ni gestion d'erreur ni appel, mais
  la règle de relecture côte à côte s'applique quand même (`standards/02` §6).

  Le contenu engage la responsabilité du syndicat des copropriétaires : toute
  reformulation est une décision juridique, pas une retouche de style.

  ## 🔴 Deux mots ont changé le 21/09/2026 (#1123), et le FOND n'a pas bougé

  Signalé à l'écran : *« Dans la page affaire : remplacer Ticket par Affaire »*.
  Le titre disait encore « Tickets de type Urgence » — deux fois périmé :

  1. **« ticket »** est le nom du MODÈLE ; l'écran dit « affaire » depuis
     v2.0.0. Aucun contrôle ne le voyait : `lint:vocabulaire-ecran` ne lisait
     que les **attributs**, et ce texte-ci vit dans un `<span>` et un `<p>`.
     C'est cette porte manquante qui fait l'objet de #1123.
  2. **« de type Urgence »** décrivait une CATÉGORIE retirée le 07/09/2026
     (migration 0177). L'urgence est une **case** — 🚨 Urgent —, précisément
     pour qu'on n'ait plus à choisir entre dire *ce que c'est* et dire *que ça
     presse*. Le texte renvoyait donc à un classement qui n'existe plus.

  ⚠️ Ce qui engage la responsabilité — traçabilité et non alerte des secours,
  numéros d'urgence, délai de déclaration à l'assureur, clause de
  non-responsabilité — est inchangé **au mot près**. Seul l'objet nommé change.
-->
<script lang="ts">
	import { GLYPHE_URGENCE } from '#lib/options-publication.ts';
	//  Replié par défaut : l'avertissement doit être accessible en permanence sans
	//  occuper l'écran de quelqu'un qui vient consulter ses affaires.
	let disclaimerOpen = false;
</script>

<div class="urgence-disclaimer" role="note" aria-label="Avertissement affaires urgentes">
	<button
		class="urgence-disclaimer-toggle"
		on:click={() => (disclaimerOpen = !disclaimerOpen)}
		aria-expanded={disclaimerOpen}
	>
		<span class="urgence-disclaimer-title"
			>{GLYPHE_URGENCE} Affaires urgentes — Avertissement légal</span
		>
		<span class="urgence-disclaimer-chevron">{disclaimerOpen ? '▲' : '▼'}</span>
	</button>
	{#if disclaimerOpen}
		<p>
			Le dépôt d'une affaire marquée <strong>{GLYPHE_URGENCE} Urgent</strong> dans cette application
			a pour seul objet la
			<strong>traçabilité de votre signalement</strong>. Il ne constitue ni un moyen d'alerte des
			secours, ni un engagement de prise en charge dans un délai déterminé, ni une garantie de
			résultat de la part du conseil syndical ou du syndicat des copropriétaires.
		</p>
		<p class="urgence-disclaimer-steps">
			<strong
				>En cas de danger pour les personnes ou de sinistre, vous devez impérativement :</strong
			>
		</p>
		<ul>
			<li>
				&#x1F4DE; <strong>Alerter les secours</strong> — 15 (SAMU) · 17 (Police secours) · 18 (Sapeurs-pompiers)
				· 112 (urgences européennes)
			</li>
			<li>
				&#x1F3E2; <strong>Prévenir le syndic</strong> via ses coordonnées d'urgence (voir
				<a href="/annuaire">Annuaire</a>)
			</li>
			<li>
				&#x1F4CB; <strong>Déclarer le sinistre à votre assureur</strong> dans les délais prévus au contrat
				(généralement 5 jours ouvrés à compter de la connaissance du sinistre — art. L113-2 Code des Assurances)
			</li>
		</ul>
		<p class="urgence-disclaimer-legal">
			La responsabilité du syndicat des copropriétaires, du conseil syndical et de l'administrateur
			de la plateforme ne saurait être engagée en cas de préjudice résultant de l'absence de
			signalement par les voies officielles ci-dessus.
		</p>
	{/if}
</div>

<style>
	/*  Ces règles suivent le balisage : Svelte scope les styles au composant, et
	    les laisser dans la page en aurait fait des sélecteurs orphelins — c'est
	    exactement la régression #344 (balisage parti, règles restées derrière). */
	/*  🔴 REPLIÉ, IL NE TIENT QU'UNE LIGNE SERRÉE (27/09/2026).
	    Signalé à l'écran : *« Affaires urgentes prend trop de place, divise par
	    2 ou 3 l'espace en hauteur »*. Replié, le bandeau faisait ~70 px (padding
	    0,7 rem, titre 0,95 rem en interligne 1,6, marge basse 1,25 rem) — plus
	    que la première carte d'affaire. Il en fait ~30 à la souris.
	    ⚠️ Seul l'ENCOMBREMENT change : le texte juridique est intact, et au
	    doigt la ligne garde ses 44 px (`standards/11` §10, même règle que
	    `.section-pliee`) — sans quoi l'avertissement ne s'ouvrirait plus au
	    pouce, et rien ne le dirait. */
	.urgence-disclaimer {
		background: var(--color-orange-fond);
		border: 1px solid var(--color-orange-bordure);
		border-left: 3px solid var(--color-orange);
		border-radius: var(--radius);
		padding: 0;
		margin-bottom: 0.5rem;
		font-size: var(--fs-sm);
		line-height: 1.5;
		color: var(--color-text);
		overflow: hidden;
	}
	.urgence-disclaimer-toggle {
		display: flex;
		justify-content: space-between;
		align-items: center;
		width: 100%;
		background: none;
		border: none;
		padding: 0.2rem 0.75rem;
		cursor: pointer;
		text-align: left;
		gap: 0.5rem;
		line-height: 1.3;
	}
	@media (pointer: coarse) {
		.urgence-disclaimer-toggle {
			min-height: 44px;
		}
	}
	@media (hover: hover) and (pointer: fine) {
		.urgence-disclaimer-toggle:hover {
			background: color-mix(in srgb, var(--color-orange-bordure) 27%, transparent);
		}
	}
	.urgence-disclaimer-title {
		font-weight: 700;
		font-size: var(--fs-sm);
		color: var(--color-orange-texte);
	}
	.urgence-disclaimer-chevron {
		font-size: var(--fs-3xs);
		color: var(--color-orange-texte);
		flex-shrink: 0;
	}
	.urgence-disclaimer p {
		margin: 0 0 0.45rem;
		padding: 0 0.75rem;
	}
	.urgence-disclaimer p:first-of-type {
		padding-top: 0.2rem;
	}
	.urgence-disclaimer ul {
		margin: 0.3rem 0 0.45rem 0.75rem;
		padding: 0 0.75rem 0 0;
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}
	.urgence-disclaimer li {
		list-style: none;
	}
	.urgence-disclaimer a {
		color: var(--color-orange-texte);
		text-decoration: underline;
	}
	.urgence-disclaimer-steps {
		margin-top: 0.45rem !important;
	}
	.urgence-disclaimer-legal {
		font-size: var(--fs-sm);
		color: var(--color-orange-texte);
		font-style: italic;
		margin-top: 0.3rem !important;
		border-top: 1px solid var(--color-orange-bordure);
		padding: 0.45rem 0.75rem 0.6rem !important;
	}
</style>
