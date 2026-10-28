<!--
  Le FIL D'ARIANE d'une page de détail — « où suis-je, et comment je remonte ».

  ## Pourquoi ce composant (#365, arbitré le 19/08/2026)

  Les deux pages de détail du site — un ticket, un sondage — n'avaient pas
  d'en-tête, contrairement à tous les autres écrans. Elles portaient un simple
  lien de retour, et il divergeait déjà : « ← Retour aux tickets » d'un côté,
  « ← Communauté » de l'autre. Ni l'un ni l'autre ne dit dans quelle rubrique on
  se trouve.

  🔴 **Ces pages sont très majoritairement atteintes par un LIEN PROFOND** — une
  notification, un e-mail, le fil d'activité. On y arrive donc sans être passé par
  la liste, sans savoir d'où l'on vient ni comment remonter. C'est ce qui a fait
  préférer un fil d'Ariane à un titre de rubrique : il répond à la question que se
  pose vraiment le lecteur.

      5Hostachy › Communauté › Faut-il installer des bornes de recharge ?

  ## Ce qui a été écarté, et pourquoi

  L'**en-tête complet** des pages de liste (titre de rubrique + sous-titre
  configurable) : sur un écran de détail, il repousse le contenu vers le bas pour
  redire ce que le titre de l'objet dit déjà, deux lignes plus bas.

  ## Trois règles d'écriture

  1. **Le dernier segment n'est pas un lien** — c'est la page courante. Il porte
     `aria-current="page"`, que les lecteurs d'écran annoncent.
  2. **C'est le TITRE DE L'OBJET qui est tronqué**, jamais la rubrique : sur un
     téléphone, savoir qu'on est dans « Communauté » vaut mieux que de lire trois
     mots de plus d'une question qu'on a sous les yeux juste en dessous.
  3. **Le fil tient sur une ligne**, quelle que soit la largeur. Il ne passe pas à
     la ligne et ne déborde pas : c'est un repère, pas un contenu.

  ## Il remplace `.back-link`

  Cette classe était définie **trois fois à l'identique** (`tickets/[id]`,
  `sondages/[id]`, `notifications`) — même défaut que `.filters` avant #446, et
  personne ne l'avait vu parce que les trois copies étaient d'accord. Deux d'entre
  elles disparaissent ici.
-->
<script lang="ts">
	import { siteNomStore } from '#lib/stores/pageConfig.ts';

	/**
	 * Les étapes AVANT la page courante, de la plus générale à la plus proche.
	 * Le nom du site est ajouté automatiquement en tête — ne pas le passer.
	 */
	export let segments: { libelle: string; href: string }[] = [];

	/** Le titre de la page courante : dernier segment, jamais un lien. */
	export let courant: string;
</script>

<nav class="fil" aria-label="Fil d'Ariane">
	<a class="fil-lien fil-site" href="/tableau-de-bord">{$siteNomStore}</a>
	{#each segments as s (s.href)}
		<span class="fil-sep" aria-hidden="true">›</span>
		<a class="fil-lien" href={s.href}>{s.libelle}</a>
	{/each}
	<span class="fil-sep" aria-hidden="true">›</span>
	<span class="fil-courant" aria-current="page">{courant}</span>
</nav>

<style>
	.fil {
		display: flex;
		align-items: center;
		gap: 0.35rem;
		margin-bottom: 0.75rem;
		font-size: var(--fs-md);
		color: var(--color-text-muted);
		/*  Une seule ligne, toujours : un repère qui se plie sur trois lignes
		    n'est plus un repère. */
		white-space: nowrap;
		overflow: hidden;
	}

	.fil-lien {
		color: var(--color-text-muted);
		text-decoration: none;
		flex-shrink: 0; /*  les rubriques ne se compriment jamais */
	}
	@media (hover: hover) and (pointer: fine) {
		.fil-lien:hover {
			color: var(--color-primary);
			text-decoration: underline;
		}
	}
	/*  Le focus au clavier n'est pas un survol : il reste hors du média souris. */
	.fil-lien:focus-visible {
		color: var(--color-primary);
		text-decoration: underline;
	}

	.fil-sep {
		flex-shrink: 0;
		opacity: 0.55;
	}

	/*  C'est le TITRE qui cède la place, jamais la rubrique (règle 2). */
	.fil-courant {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		min-width: 0;
	}

	/*  Sur un écran étroit, le nom du site est le segment le moins utile : on
	    sait sur quel site on est. La rubrique et le titre restent. */
	@media (max-width: 480px) {
		.fil-site,
		.fil-site + .fil-sep {
			display: none;
		}
	}
</style>
