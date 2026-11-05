<!--
  Le badge NEW d'une carte, à côté de son titre — le même sur tout le site.

  🔴 Il était écrit CINQ fois (#1329) — affaire, actualité, annonce, idée,
  sondage — puis unifié en « Nouveau » gris ; le fil d'activité, lui, gardait
  son propre « NEW » rouge. Arbitré à l'écran le 26/09/2026 : **un seul badge,
  le NEW rouge du fil**. Le fil l'emploie désormais aussi.

  La règle de fraîcheur est au SERVEUR (`utils/nouveaute.est_nouveau`, 48 h) : chaque
  objet sert son `nouveau` (idées, annonces, sondages #2506, affaires #2508), que le
  badge reçoit par `si` ; le fil passe le verdict de `isNew` (`#lib/flux`). Il ne
  calcule plus rien — `isNouveau` a quitté `#lib/date`.

  Fixe, sans pulsation : le fil le faisait battre en continu. Une animation
  permanente sur une liste parcourue plusieurs fois par jour fatigue sans rien
  apprendre (`emil-design-eng` : ce qu'on voit souvent ne s'anime pas).
-->
<script lang="ts">
	/** Le verdict servi (`nouveau`), et ce que l'écran y ajoute (une annonce archivée
	 *  n'est plus nouvelle). Défaut FERMÉ : sans verdict, pas de badge. */
	export let si = false;

	$: visible = si;
</script>

{#if visible}<span class="badge-nouveau">NEW</span>{/if}

<style>
	.badge-nouveau {
		display: inline-block;
		margin-left: 0.45em;
		padding: 0.1rem 0.35rem;
		border-radius: 0.2rem;
		background: var(--color-danger-plein);
		color: var(--color-sur-plein);
		font-size: var(--fs-3xs);
		font-weight: 700;
		letter-spacing: 0.06em;
		line-height: 1.4;
		vertical-align: middle;
		flex-shrink: 0;
	}
</style>
