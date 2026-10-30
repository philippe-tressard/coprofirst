<!--
  **L'en-tête de l'accueil** — la salutation, le logement, les rôles qui
  ajoutent quelque chose, et le raccourci vers le profil.

  Extrait de `tableau-de-bord/+page.svelte` le 01/10/2026 (#779). C'est une
  DÉCOUPE, pas une factorisation : l'en-tête n'est écrit qu'ici. Il emporte ce
  qui ne parlait que de lui — la composition des rôles et le libellé du
  logement —, la page gardant le chargement.
-->
<script lang="ts">
	import { SEPARATEUR } from '#lib/separateurs.ts';
	import type { MonLot } from '#lib/api/index.ts';
	import Avatar from '#lib/components/Avatar.svelte';
	import Icon from '#lib/components/Icon.svelte';
	import { libelleLogement } from '#lib/utils.ts';
	import { libelleRole, libelleStatut, LIBELLES_STATUT } from '#lib/roles.ts';
	import { currentUser } from '#lib/stores/auth.ts';

	/**  Calculée par la page, qui la relit au chargement des données
	 *   (`relire`) : ici, elle serait figée au montage. */
	export let salutation: string;
	/** Les lots de l'utilisateur (`lots.mesList()`). */
	export let lots: MonLot[] = [];
	/** Vrai quand la page a chargé : l'en-tête entre alors en fondu. */
	export let visible = false;

	//  🔴 Les deux tables locales ont rejoint `#lib/roles` (#801) : elles étaient
	//  la troisième écriture front de la même notion, et la SEULE à écrire
	//  « Copropriétaire résident » — les deux autres écrans mettaient une
	//  capitale au second mot. C'est cette forme-ci qui a été retenue.
	//
	//  ⚠️ Ce qui reste ICI est la RÈGLE de composition, pas les libellés : on
	//  annonce le statut, puis les rôles qui ajoutent quelque chose (conseil
	//  syndical, admin), séparés par ` · `. `résident` et `propriétaire` n'y
	//  figurent pas — ils ne disent rien de plus que le statut déjà affiché.
	//
	//  Un séparateur ne finit jamais une ligne (#2356) : l'espace d'APRÈS lui est
	//  insécable, la ligne ne peut se couper qu'avant. Même règle dans le gabarit,
	//  où chaque bloc est précédé d'une espace — en tête de branche, Svelte 5 la
	//  retirerait (`npm run lint:espace-blocs`).
	$: roleLabels = (() => {
		const labels: string[] = [];
		const statut = $currentUser?.statut ?? '';
		if (LIBELLES_STATUT[statut]) labels.push(libelleStatut(statut));
		const allRoles = new Set([...($currentUser?.roles ?? []), $currentUser?.role ?? '']);
		for (const r of ['conseil_syndical', 'admin']) {
			if (allRoles.has(r)) labels.push(libelleRole(r));
		}
		return labels.join(SEPARATEUR.point);
	})();

	$: lotLabel = libelleLogement(lots, $currentUser);
</script>

<div class="hero" class:hero-visible={visible}>
	<div class="hero-accent"></div>
	<div class="hero-content">
		<div class="hero-top">
			<div>
				<h1 class="hero-greeting">
					{salutation}
					{$currentUser?.prenom}
					{#if lotLabel}<span class="hero-lot-inline">{SEPARATEUR.tiret}{lotLabel}</span>{/if}
					{#if roleLabels}<span class="hero-role-inline">{SEPARATEUR.point}{roleLabels}</span>{/if}
				</h1>
			</div>
			<!-- Raccourci vers le profil. Sans photo, la pastille porte un
			     crayon : c'est l'invitation à en déposer une, sans texte ni
			     bandeau qui encombrerait l'en-tête. -->
			<a
				class="hero-avatar"
				href="/profil"
				title={$currentUser?.photo_url ? 'Mon profil' : 'Mon profil — ajouter une photo'}
				aria-label={$currentUser?.photo_url
					? 'Mon profil'
					: 'Mon profil — ajouter une photo de profil'}
			>
				<Avatar
					photoUrl={$currentUser?.photo_url}
					prenom={$currentUser?.prenom}
					nom={$currentUser?.nom}
				/>
				{#if !$currentUser?.photo_url}
					<span class="hero-avatar-badge" aria-hidden="true"><Icon name="pencil" size={9} /></span>
				{/if}
			</a>
		</div>
	</div>
</div>

<style>
	/* ═══ HERO EN-TÊTE ═══════════════════════════════════════════════════ */
	.hero {
		margin: -1rem -1rem 0;
		padding: 1.5rem 1.25rem 1.25rem;
		background: linear-gradient(
			135deg,
			var(--color-primary-plein) 0%,
			color-mix(in srgb, var(--color-primary-plein) 85%, var(--color-sur-plein)) 100%
		);
		border-radius: 0 0 var(--radius) var(--radius);
		position: relative;
		overflow: hidden;
		opacity: 0;
		transform: translateY(-10px);
		transition:
			opacity var(--duree-apparition) var(--ease-out),
			transform var(--duree-apparition) var(--ease-out);
	}
	.hero.hero-visible {
		opacity: 1;
		transform: translateY(0);
	}
	.hero-accent {
		position: absolute;
		top: 0;
		left: 0;
		right: 0;
		height: 4px;
		background: linear-gradient(
			90deg,
			var(--color-accent) 0%,
			var(--color-secondary) 50%,
			var(--color-accent) 100%
		);
	}
	.hero-content {
		position: relative;
		z-index: 1;
	}
	.hero-top {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 0.75rem;
	}
	/* L'anneau clair détache la pastille du dégradé bleu. Les initiales gardent
	   l'aplat par défaut d'`Avatar` (blanc sur Bleu Seine, 11:1) : sur un voile
	   blanc translucide, le blanc n'en faisait que 2,8 au clair (#2296). */
	.hero-avatar {
		position: relative;
		flex-shrink: 0;
		/* Cible tactile ≥ 44 px (2,6 rem + l'anneau) — atteignable au pouce. */
		display: flex;
		align-items: center;
		justify-content: center;
		min-width: 44px;
		min-height: 44px;
		padding: 2px;
		border-radius: 50%;
		background: rgba(255, 255, 255, 0.3);
		text-decoration: none;
		transition:
			background var(--duree-geste),
			transform var(--duree-geste) var(--ease-out);
		--avatar-size: 2.6rem;
	}
	@media (hover: hover) and (pointer: fine) {
		.hero-avatar:hover {
			background: rgba(255, 255, 255, 0.6);
			transform: scale(1.04);
		}
	}
	.hero-avatar:focus-visible {
		outline: 2px solid var(--color-accent);
		outline-offset: 3px;
	}
	.hero-avatar-badge {
		position: absolute;
		right: -1px;
		bottom: -1px;
		width: 1.05rem;
		height: 1.05rem;
		border-radius: 50%;
		background: var(--color-accent-plein);
		color: var(--color-sur-accent);
		display: flex;
		align-items: center;
		justify-content: center;
		box-shadow: 0 0 0 2px var(--color-primary-plein);
	}
	.hero-greeting {
		font-size: var(--fs-titre-page);
		font-weight: 700;
		color: var(--color-text-inverse);
		margin: 0;
		line-height: 1.3;
	}
	.hero-lot-inline {
		font-size: var(--fs-md);
		font-weight: 400;
		color: rgba(255, 255, 255, 0.75);
	}
	.hero-role-inline {
		font-size: var(--fs-xs);
		font-weight: 400;
		color: var(--color-sur-plein-discret);
		letter-spacing: 0.02em;
	}

	/*  Mouvement réduit : l'en-tête apparaît en fondu, sans glisser. C'est l'écran
	    le plus vu — il ne doit pas bouger pour qui a demandé qu'on ne bouge pas
	    (`emil-design-eng` : garder l'opacité, retirer le déplacement). */
	@media (prefers-reduced-motion: reduce) {
		.hero {
			transform: none;
		}
	}

	@media (max-width: 767px) {
		.hero {
			margin: -0.75rem -0.75rem 0;
			padding: 1.25rem 1rem 1rem;
		}
	}
</style>
