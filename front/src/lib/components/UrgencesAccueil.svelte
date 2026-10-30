<!--
  **Les urgences de l'accueil** — au plus trois cartes rouges au-dessus du fil.

  ## Pourquoi ce composant (#779, 30/09/2026)

  Extrait de `tableau-de-bord/+page.svelte` (890 lignes) : un bloc qui a sa
  propre responsabilité — signaler ce qui brûle —, son propre calcul (la
  progression d'une coupure en cours) et ses propres styles, et qui ne partage
  avec la page que la liste qu'elle lui passe. La page garde le choix des
  éléments (`estUrgent`) et l'entrée en fondu.

  ## 🔴 Un lien, pas un `<fieldset role="link">`

  La carte était un `<fieldset>` porteur de `role="link"`, `tabindex` et d'un
  `keydown` recopié : un élément non interactif ne peut pas prendre un rôle
  interactif (`a11y_no_noninteractive_element_to_interactive_role`, déclaré
  dans `check-a11y` depuis le 28/08/2026). La déclaration prescrivait de
  refaire le rendu en `<div>` ; ce n'est pas nécessaire. Le `<fieldset>` reste
  ce qu'il est — un CADRE, dont seule la `<legend>` sait chevaucher la bordure —
  et le geste passe à un vrai `<a href>` sur le titre, **étiré** sur la carte
  par un pseudo-élément. Le clavier et les lecteurs d'écran reçoivent un lien
  natif (Entrée, ouverture dans un onglet, adresse annoncée), et le rendu ne
  bouge pas.

  ## 🔴 Le texte riche, pas l'extrait (24/10/2026)

  Le bandeau rendait `detail` : un extrait que le serveur a déjà dépouillé de
  son HTML (`strip_html`). Le gras d'une actualité urgente — « le code 0753 » —
  disparaissait ici alors que le fil, juste dessous, le rendait. Quand le
  serveur envoie le texte d'origine (`meta.full_html`), c'est lui qui se rend,
  assaini par `safeDescription` et borné à trois lignes comme l'aperçu d'une
  carte ; `detail` reste le repli des éléments qui n'en ont pas.
-->
<script lang="ts">
	import type { FluxItem } from '#lib/api/index.ts';
	import { fmtTime } from '#lib/date.ts';
	import { cleFluxItem, typeCouleur, typeFond, typeLibelle, typeLink } from '#lib/flux.ts';
	import { safeDescription } from '#lib/sanitize.ts';

	/** Les urgences à montrer, déjà choisies et bornées par la page. */
	export let items: FluxItem[] = [];

	function progression(item: FluxItem): { pct: number; label: string; active: boolean } | null {
		const debut = item.meta?.debut as string | undefined;
		const fin = item.meta?.fin as string | undefined;
		if (!debut || !fin) return null;
		const dStart = new Date(debut).getTime();
		const dEnd = new Date(fin).getTime();
		const now = Date.now();
		if (now < dStart) return { pct: 0, label: 'À venir', active: false };
		if (now > dEnd) return { pct: 100, label: 'Terminé', active: false };
		const pct = Math.round(((now - dStart) / (dEnd - dStart)) * 100);
		// `fmtTime` épingle Europe/Paris ; les `toLocaleTimeString` qui étaient ici
		// n'indiquaient aucun fuseau et suivaient donc celui du navigateur — juste
		// par coïncidence pour un résident en France, faux en déplacement.
		return { pct, label: `En cours (${fmtTime(debut)}–${fmtTime(fin)})`, active: true };
	}
</script>

{#each items as u (cleFluxItem(u))}
	{@const progress = progression(u)}
	{@const lien = typeLink(u)}
	<fieldset class="urgence-fieldset">
		<legend class="urgence-legend"
			>🔴 URGENCE
			<span
				class="flux-type-chip"
				style="background:{typeFond(u.type)};color:{typeCouleur(u.type)}"
			>
				{typeLibelle(u.type)}
			</span>
		</legend>
		<div class="urgence-content">
			<div class="urgence-title-row">
				<span class="urgence-icon">{u.icon}</span>
				<div class="urgence-title-col">
					{#if lien}
						<a class="urgence-lien" href={lien}><strong class="urgence-titre">{u.titre}</strong></a>
					{:else}
						<strong class="urgence-titre">{u.titre}</strong>
					{/if}
					{#if u.meta?.perimetre}<span class="urgence-perimetre">— {u.meta.perimetre}</span>{/if}
				</div>
			</div>
			{#if u.meta?.debut && u.meta?.fin}
				<p class="urgence-horaire">
					Aujourd'hui {fmtTime(String(u.meta.debut))} → {fmtTime(String(u.meta.fin))}
					{#if u.meta?.prestataire}
						· {u.meta.prestataire}{/if}
				</p>
			{:else if u.meta?.full_html}
				<div class="urgence-horaire urgence-texte rich-content clamp-3">
					{@html safeDescription(String(u.meta.full_html))}
				</div>
			{:else if u.detail}
				<p class="urgence-horaire">{u.detail}</p>
			{/if}
			{#if u.meta?.concerne_mon_batiment}
				<p class="urgence-concerne">🔹 Concerne votre bâtiment</p>
			{/if}
			{#if progress}
				<div class="urgence-progress-wrap">
					<div class="urgence-progress-track">
						<div
							class="urgence-progress-bar"
							class:urgence-active={progress.active}
							style="width:{progress.pct}%"
						></div>
					</div>
					<span class="urgence-progress-label">{progress.label}</span>
				</div>
			{/if}
		</div>
	</fieldset>
{/each}

<style>
	.urgence-fieldset {
		border: 2px solid var(--color-danger);
		border-radius: var(--radius);
		padding: 1rem 1.15rem 0.9rem;
		margin-bottom: 1rem;
		background: var(--color-danger-fond);
		position: relative;
		transition:
			box-shadow var(--duree-geste),
			background var(--duree-geste),
			transform var(--duree-geste) var(--ease-out);
	}
	/*  Le survol suit le LIEN, pas le cadre : la légende, qui déborde sur la
	    bordure, n'est pas couverte par le lien étiré — elle ne doit pas promettre
	    un clic qui n'aura pas lieu. Sans `:has()`, pas de survol : rien ne ment. */
	@media (hover: hover) and (pointer: fine) {
		.urgence-fieldset:has(.urgence-lien:hover) {
			/*  Un cran plus soutenu que le fond : les deux nuances de Tailwind
			    (#fef2f2, #fee2e2) sont devenues le même jeton (#1055). */
			background: color-mix(in srgb, var(--color-danger) 12%, var(--color-surface));
			box-shadow: 0 2px 8px color-mix(in srgb, var(--color-danger) 15%, transparent);
		}
	}
	/*  L'appui se sent (`emil-design-eng` : un élément pressable répond au
	    doigt) — un cran à peine, l'accueil est vu plusieurs fois par jour. */
	.urgence-fieldset:has(.urgence-lien:active) {
		transform: scale(0.99);
	}
	@media (prefers-reduced-motion: reduce) {
		.urgence-fieldset:has(.urgence-lien:active) {
			transform: none;
		}
	}
	.urgence-lien {
		color: inherit;
		text-decoration: none;
	}
	/*  Le lien étiré : il couvre la carte, sous la légende. */
	.urgence-lien::after {
		content: '';
		position: absolute;
		inset: 0;
		border-radius: var(--radius);
	}
	.urgence-lien:focus-visible {
		outline: none;
	}
	.urgence-lien:focus-visible::after {
		outline: 2px solid var(--color-danger);
		outline-offset: 2px;
	}
	.urgence-legend {
		font-size: var(--fs-2xs);
		font-weight: 700;
		letter-spacing: 0.06em;
		color: var(--color-danger);
		background: var(--color-danger-fond);
		padding: 0 0.5rem;
		text-transform: uppercase;
	}
	.urgence-content {
		display: flex;
		flex-direction: column;
		gap: 0.45rem;
	}
	.urgence-title-row {
		display: flex;
		align-items: center;
		gap: 0.6rem;
	}
	.urgence-icon {
		font-size: var(--fs-picto-sm);
		flex-shrink: 0;
	}
	.urgence-title-col {
		display: flex;
		align-items: baseline;
		gap: 0.35rem;
		flex-wrap: wrap;
	}
	.urgence-titre {
		font-size: var(--fs-lg);
		color: var(--color-text);
	}
	.urgence-perimetre {
		font-size: var(--fs-md);
		color: var(--color-text-muted);
	}
	.urgence-horaire {
		font-size: var(--fs-md);
		color: var(--color-text-muted);
		margin: 0;
	}
	/*  Le texte riche garde l'allure de la ligne : ses paragraphes ne
	    s'écartent que d'un souffle, comme dans l'aperçu d'une carte. */
	.urgence-texte :global(p) {
		margin: 0 0 0.12em;
	}
	.urgence-concerne {
		font-size: var(--fs-md);
		color: var(--color-primary);
		font-weight: 500;
		margin: 0;
	}
	.urgence-progress-wrap {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		margin-top: 0.15rem;
	}
	.urgence-progress-track {
		flex: 1;
		height: 6px;
		border-radius: 3px;
		background: var(--color-border);
		overflow: hidden;
	}
	.urgence-progress-bar {
		height: 100%;
		border-radius: 3px;
		background: var(--color-text-muted);
		transition: width var(--duree-apparition) var(--ease-out);
	}
	.urgence-progress-bar.urgence-active {
		background: var(--color-danger);
	}
	.urgence-progress-label {
		font-size: var(--fs-xs);
		color: var(--color-text-muted);
		white-space: nowrap;
	}
</style>
