<!--
  Compte.svelte — LE nombre d'objets, en vignette : le badge Bleu Seine qu'on
  lit à droite d'un bandeau d'Archives, d'une année d'archives, et dans la
  pastille retenue d'un filtre des Affaires.

  🔴 Il était écrit DEUX fois, à l'identique ou presque (`.sr-compte` de
  `SectionRepliee`, `.archives-compte` d'`ArchivesParAnnee` — l'un en `--fs-xs`,
  l'autre en `--fs-2xs`), et la troisième écriture arrivait avec les filtres
  d'Affaires (10/10/2026, maquette B arbitrée à l'écran : « normalise la
  vignette sur ce qui se fait par ailleurs, comme Archives »). Le style voyage
  avec son balisage — c'est la leçon de `Pastille` (v2.67.11) : un badge
  emprunté au composant d'un autre part nu en production.

  ⚠️ Les chiffres sont à CHASSE FIXE (`tabular-nums`) : un compte qui passe de
  9 à 12 sous le doigt ne doit pas faire trembler la rangée. Et il ne s'anime
  PAS — il change à chaque clic de filtre (`emil-design-eng` : ce qu'on voit
  des dizaines de fois par jour ne s'anime pas). Seule sa couleur suit celle de
  la pastille qui le porte, à la même durée qu'elle.
-->
<script lang="ts">
	/** Le nombre affiché. */
	export let n: number;
	/**  Posé sur un APLAT Bleu Seine — une pastille retenue : les couleurs
	 *   s'inversent, sinon le badge s'y noierait. */
	export let surAplat = false;
</script>

<span class="compte" class:sur-aplat={surAplat}>{n}</span>

<style>
	.compte {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		background: var(--color-primary-plein);
		color: var(--color-sur-plein);
		font-size: var(--fs-xs);
		font-weight: 700;
		line-height: 1.2;
		padding: 0.15rem 0.5rem;
		border-radius: 12px;
		min-width: 1.5rem;
		font-variant-numeric: tabular-nums;
		transition:
			color var(--duree-geste),
			background-color var(--duree-geste);
	}
	.sur-aplat {
		background: var(--color-surface);
		color: var(--color-primary);
	}
</style>
