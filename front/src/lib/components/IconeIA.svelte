<!--
  IconeIA.svelte — l'icône d'un geste qui LANCE un traitement de l'assistant IA :
  ✨ au repos, ⏳ qui clignote tant que le traitement tourne.

  ## Pourquoi (17/10/2026, demandé par l'utilisateur)

  > « il y a cet icone ✨ qui se transforme en ⏳ quand le traitement est en
  >   cours ; standardise partout le principe, est-il possible de le faire
  >   clignoter ? »

  Six gestes lancent l'assistant (description, synthèse de contrat, synthèse
  d'affaire, résumé des affaires en cours, tarif d'un modèle…), et chacun disait
  l'attente à sa façon : ✨ émoji qui devenait ⏳ émoji, étincelle au trait qui
  devenait sablier au trait, étincelle émoji qui pulsait, ou rien du tout — un
  appel de dix secondes ne se distinguait pas d'un clic perdu. Un appel à
  l'assistant dure plusieurs secondes et se FACTURE : on ne doit pas être tenté
  de cliquer deux fois.

  ## Ce que le composant porte, et ce qu'il laisse au bouton

  - le dessin, **au trait** comme toute action du site (`IconeAction`,
    `ux-patterns` §3) : `sparkles` au repos, `hourglass` pendant l'appel ;
  - le **clignotement** et la couleur Bleu Seine pendant l'appel — gris, un
    sablier de 16 px ne se remarquait pas ;
  - `prefers-reduced-motion` : le sablier reste, coloré, mais immobile.

  Le bouton garde ce qui est à lui : son libellé, `aria-busy={enCours}` (que
  `npm run lint:geste-ia` exige) et son `disabled`. ✨ hors bouton — la MARQUE
  « rédigé avec l'assistant » — reste `MarqueIA`, qui ne clignote jamais.
-->
<script lang="ts">
	import IconeAction from '#lib/components/IconeAction.svelte';

	/** Vrai pendant l'appel à l'assistant : ✨ devient ⏳, qui clignote. */
	export let enCours: boolean;
</script>

<span class="icone-ia" class:en-cours={enCours}>
	<IconeAction icone={enCours ? 'hourglass' : 'sparkles'} />
</span>

<style>
	.icone-ia {
		display: inline-flex;
	}
	/*  Le sablier prend la couleur de l'action, même sur un bouton désactivé : il
	    dit que le clic A été pris, pas que le bouton est indisponible. */
	.en-cours :global(.icone-action) {
		color: var(--color-primary);
	}
	/*  Dans un bouton qui PARLE (`.btn` : « Relancer », « Poser la question »),
	    l'icône prend la couleur de son texte — le gris d'`IconeAction` est fait
	    pour l'icône seule, et le Bleu Seine disparaîtrait sur `.btn-primary`. */
	:global(.btn) .icone-ia :global(.icone-action),
	:global(.btn) .en-cours :global(.icone-action) {
		color: inherit;
	}
	/*  L'attente se voit : le seul mouvement sans fin du produit qui dit « ça
	    travaille » pour l'assistant (`lint:animations-infinies`, ATTENTES). */
	.en-cours {
		animation: clignote-ia 1s ease-in-out infinite;
	}
	@keyframes clignote-ia {
		0%,
		100% {
			opacity: 1;
		}
		50% {
			opacity: 0.2;
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.en-cours {
			animation: none;
		}
	}
</style>
