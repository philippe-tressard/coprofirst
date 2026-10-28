<!--
  L'onglet **Descriptif pages** de l'administration : l'icône, le libellé de
  navigation, le titre et la description de chaque page — et leur ordre dans le
  menu.

  ## Pourquoi ce composant (11/09/2026)

  `admin/+page.svelte` était à 1 724 lignes, et le garde-fou de modularité
  (rang 1) a refusé les huit lignes qu'ajoutait le nouvel onglet « Assistant IA ».
  Les trois réponses possibles sont : découper, remonter la règle d'un cran,
  **jamais raboter**. Celle-ci est un découpage franc — un onglet entier, son
  état et ses appels réseau, rien de partagé avec le reste de la page.

  C'est aussi la priorité annoncée par l'issue #779 : *un onglet, un composant*.

  Même forme qu'`OngletSmtp` et `OngletIA` : les valeurs lues une fois par la
  page arrivent en `valeurs`, tout le reste vit ici.
-->
<script lang="ts">
	import IconeAction from '#lib/components/IconeAction.svelte';
	import { messageErreur } from '#lib/erreurs.ts';
	import { onMount } from 'svelte';
	import { config as configApi } from '#lib/api/index.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import { configStore } from '#lib/stores/pageConfig.ts';
	import Icon from '#lib/components/Icon.svelte';
	import ChampIcone from '#lib/components/ChampIcone.svelte';
	import RichEditor from '#lib/components/RichEditor.svelte';
	//  ⚠️ `stripHtml` et non une copie locale : la page portait un
	//  `stripHtmlPreview` maison qui ne décodait pas les entités HTML
	//  (`&nbsp;`, `&amp;`). La version partagée fait plus, et elle est déjà
	//  employée par tous les aperçus du site.
	import { stripHtml } from '#lib/utils.ts';
	import { PAGES, configDepuisPage, ordonnerPages, type PageDef } from '#lib/pages.ts';
	import { fusionnerSurcharge } from '#lib/pages-surcharge.ts';

	/** La configuration complète, lue une fois par la page (`adminCfg`). */
	export let valeurs: Record<string, string> = {};

	/**
	 * La page telle qu'elle s'affiche : les DÉFAUTS d'abord, la surcharge
	 * enregistrée par-dessus.
	 *
	 * 🔴 L'ordre est tout le correctif de #1105 (21/09/2026). Cette fonction
	 * partait de `{...saved}` et n'y réimposait que `id` et `href` — or ce qui
	 * est enregistré est `PageConfig`, et **`nom` n'en fait pas partie** :
	 * il n'est pas administrable. Toute page déjà éditée perdait donc son nom
	 * à l'affichage, et trois d'entre elles s'y voyaient.
	 *
	 * ⚠️ `id` et `href` restent forcés depuis les défauts : ils sont l'IDENTITÉ
	 * de la page, jamais une valeur. Les reprendre de l'enregistrement donnait
	 * deux pages homonymes et un `each_key_duplicate` — écran figé (16/09/2026).
	 *
	 * Le repli et les rattrapages d'onglets vivent dans `#lib/pages-surcharge`,
	 * avec ceux du store : ils y étaient recopiés au caractère près.
	 */
	function pageAffichee(saved: unknown, defauts: PageDef): PageDef {
		const config = fusionnerSurcharge(defauts.id, saved, configDepuisPage(defauts));
		return {
			...defauts,
			titre: config.titre,
			descriptif: config.descriptif,
			navLabel: config.navLabel,
			icone: config.icone ?? defauts.icone,
			onglets: defauts.onglets?.map((o) => ({
				...o,
				label: config.onglets?.[o.id]?.label ?? o.label,
				descriptif: config.onglets?.[o.id]?.descriptif ?? o.descriptif,
			})),
		};
	}

	const pagesDefaults: PageDef[] = PAGES;
	let pagesConfig: PageDef[] = pagesDefaults.map((pg) => ({ ...pg }));
	// Seules les pages du menu s'ordonnent : « Mon profil » et « Notifications » sont
	// atteignables sans entrée de navigation. Elles portaient pourtant des flèches, et
	// leur déplacement était enregistré puis écarté en silence par le menu (#401).
	$: indicesMenu = pagesConfig.map((p, i) => (p.href !== null ? i : -1)).filter((i) => i >= 0);
	let expandedPages = new Set<string>();
	function togglePage(id: string) {
		expandedPages = expandedPages.has(id) ? new Set() : new Set([id]);
	}
	async function savePageConfig(pg: PageDef) {
		// Conversion partagée avec `defautsDePage` (`#lib/pages.ts`, #420) ; `pg` et non son id : ce sont les valeurs ÉDITÉES qui partent.
		const val = JSON.stringify(configDepuisPage(pg));
		try {
			await configApi.save({ [`page_config_${pg.id}`]: val });
			configStore.update((c: Record<string, string>) => ({ ...c, [`page_config_${pg.id}`]: val }));
			toast('success', 'Configuration enregistrée.');
		} catch (e) {
			toast('error', messageErreur(e, 'Erreur lors de la sauvegarde.'));
		}
	}
	async function movePage(i: number, dir: number) {
		const arr = [...pagesConfig];
		// On échange avec la page de menu voisine, pas avec la ligne voisine : une page
		// sans entrée de navigation ne participe pas à l'ordre et ne doit pas s'intercaler.
		const rang = indicesMenu.indexOf(i);
		const j = indicesMenu[rang + dir];
		if (rang < 0 || j === undefined) return;
		[arr[i], arr[j]] = [arr[j], arr[i]];
		pagesConfig = arr;
		// `pages_order` ne porte que les pages du menu : y écrire des identifiants que le
		// menu ne connaît pas, c'était fabriquer l'incohérence que `Nav` signale désormais.
		const ordered = JSON.stringify(pagesConfig.filter((p) => p.href !== null).map((p) => p.id));
		configStore.update((c: Record<string, string>) => ({ ...c, pages_order: ordered }));
		try {
			await configApi.save({ pages_order: ordered });
			// Cet écran enregistre au fil de l'eau, sans bouton : jusqu'ici seul l'ÉCHEC
			// parlait, et l'absence de retour laissait croire que rien n'était enregistré.
			toast('success', 'Ordre enregistré.');
		} catch (e) {
			toast('error', messageErreur(e, "Erreur lors de la sauvegarde de l'ordre."));
		}
	}
	//  L'onglet s'amorce SEUL à partir des valeurs reçues : la page n'a plus à
	//  préparer `pagesConfig` avant de le rendre, ce qui était la moitié du
	//  couplage que cette extraction supprime.
	let amorce = false;
	$: if (!amorce && valeurs && Object.keys(valeurs).length) {
		amorce = true;
		hydrater(valeurs);
	}

	onMount(() => {
		if (!amorce && Object.keys(valeurs).length === 0) hydrater({});
	});

	function hydrater(cfg: Record<string, string>) {
		pagesConfig = pagesDefaults.map((pg) => {
			const s = cfg[`page_config_${pg.id}`];
			if (!s) return { ...pg };
			try {
				return pageAffichee(JSON.parse(s), pg);
			} catch {
				return { ...pg };
			}
		});
		const savedOrder = cfg['pages_order'];
		if (savedOrder) {
			try {
				pagesConfig = ordonnerPages(pagesConfig, JSON.parse(savedOrder));
			} catch {
				/* un ordre illisible laisse l'ordre par défaut — il ne bloque rien */
			}
		}
	}
</script>

<p class="muted intro-pages">
	Personnalisez l'icône, le label de navigation, le titre et la description de chaque page. Cliquer
	sur une entrée pour la modifier ; les autres se referment automatiquement.
</p>
<div class="ref-list">
	{#each pagesConfig as pg, i (pg.id)}
		<div class="ref-item" class:expanded={expandedPages.has(pg.id)}>
			<div class="page-row">
				<div class="order-btns">
					{#if pg.href !== null}
						<button
							type="button"
							class="btn-order"
							disabled={indicesMenu[0] === i}
							on:click={() => movePage(i, -1)}
							aria-label="Monter {pg.nom} dans le menu"><IconeAction icone="arrow-up" /></button
						>
						<button
							type="button"
							class="btn-order"
							disabled={indicesMenu[indicesMenu.length - 1] === i}
							on:click={() => movePage(i, 1)}
							aria-label="Descendre {pg.nom} dans le menu"
							><IconeAction icone="arrow-down" /></button
						>
					{:else}
						<span
							class="hors-menu"
							title="Cette page n'a pas d'entrée de menu : son ordre n'a pas de sens.">—</span
						>
					{/if}
				</div>
				<button class="page-row-btn" on:click={() => togglePage(pg.id)} type="button">
					<span class="page-row-icon"><Icon name={pg.icone || 'help-circle'} size={16} /></span>
					<span class="page-nom">{pg.nom}</span>
					<span class="ref-desc muted">{stripHtml(pg.descriptif)}</span>
					<span class="chevron" class:open={expandedPages.has(pg.id)}>›</span>
				</button>
			</div>
			{#if expandedPages.has(pg.id)}
				<div class="ref-body">
					<div class="pages-form-grid">
						<div class="pages-form-section">
							<div class="pages-form-section-title">Navigation (barre de menu)</div>
							<ChampIcone bind:valeur={pg.icone} id="page-icone-{pg.id}" />
							<label class="field">
								Label menu
								<input type="text" bind:value={pg.navLabel} />
								<span class="aide">Texte affiché dans la barre de navigation.</span>
							</label>
						</div>
						<div class="pages-form-section">
							<div class="pages-form-section-title">Page</div>
							<label class="field">
								Titre de la page
								<input type="text" bind:value={pg.titre} />
								<span class="aide"
									>Titre de Page avec reprise de l'icône (de navigation du menu associé).</span
								>
							</label>
							<label class="field">
								Description
								<RichEditor bind:value={pg.descriptif} minHeight="80px" />
								<span class="aide"
									>Sous-titre affiché sous le titre de page. Mise en forme riche supportée (gras,
									italique, listes, liens).</span
								>
							</label>
						</div>
						{#if pg.onglets && pg.onglets.length > 0}
							<div class="pages-form-section section-pleine">
								<div class="pages-form-section-title">Onglets</div>
								<div class="onglets-cards">
									{#each pg.onglets as o (o.id)}
										<div class="onglet-card">
											<label class="field">
												Label « {o.id} »
												<input type="text" bind:value={o.label} />
											</label>
											<label class="field">
												Descriptif
												<RichEditor bind:value={o.descriptif} minHeight="56px" />
											</label>
										</div>
									{/each}
								</div>
								<span class="aide"
									>Labels et descriptifs de chaque onglet. Le descriptif apparaît sous les onglets
									quand l'onglet est actif.</span
								>
							</div>
						{/if}
					</div>
					<div class="form-actions">
						<button class="btn btn-primary btn-sm" on:click={() => savePageConfig(pg)}
							>Enregistrer</button
						>
					</div>
				</div>
			{/if}
		</div>
	{/each}
</div>

<style>
	/*  🔴 Ces règles ont SUIVI le balisage (11/09/2026). Svelte scope les styles
	    au fichier : les laisser dans la page les rendait inertes ici et
	    orphelines là-bas. C'est la régression de #562, attrapée par
	    `lint:classes-nues` — la relecture, elle, ne l'avait pas vue. */
	.ref-list {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}
	.page-row {
		width: 100%;
		display: flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.4rem 0.5rem 0.4rem 0.75rem;
	}
	@media (hover: hover) and (pointer: fine) {
		.page-row:hover {
			background: var(--color-bg);
		}
	}
	.page-row-btn {
		flex: 1;
		display: flex;
		align-items: center;
		gap: 0.5rem;
		background: none;
		border: none;
		cursor: pointer;
		text-align: left;
		font-size: var(--fs-base);
		padding: 0.25rem 0.25rem;
		min-width: 0;
	}
	.page-row-icon {
		flex: 0 0 18px;
		display: flex;
		align-items: center;
		color: var(--color-text-muted);
	}
	.page-nom {
		flex: 0 0 20%;
		min-width: 80px;
		max-width: 180px;
		font-weight: 600;
		font-size: var(--fs-base);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.pages-form-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 1.25rem;
	}
	.pages-form-section {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.pages-form-section-title {
		font-size: var(--fs-2xs);
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.07em;
		color: var(--color-text-muted);
		padding-bottom: 0.3rem;
		border-bottom: 1px solid var(--color-border);
		margin-bottom: 0.1rem;
	}
	.ref-desc {
		font-size: var(--fs-sm);
		flex: 1;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		min-width: 0;
	}
	.order-btns {
		display: flex;
		flex-direction: column;
		gap: 1px;
		flex-shrink: 0;
	}
	.btn-order {
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 3px;
		cursor: pointer;
		font-size: 0.6rem;
		padding: 1px 4px;
		line-height: 1.5;
		color: var(--color-text-muted);
	}
	@media (hover: hover) and (pointer: fine) {
		.btn-order:hover:not(:disabled) {
			border-color: var(--color-primary);
			color: var(--color-primary);
			background: var(--color-bg);
		}
	}
	.btn-order:disabled {
		opacity: 0.3;
		cursor: default;
	}
	.hors-menu {
		color: var(--color-text-muted);
		opacity: 0.4;
		font-size: var(--fs-2xs);
		line-height: 1.5;
		cursor: help;
	}
	.ref-item {
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		overflow: hidden;
		background: var(--color-surface);
	}
	.ref-item.expanded {
		border-color: var(--color-primary);
	}
	.ref-body {
		padding: 0.75rem 1rem;
		border-top: 1px solid var(--color-border);
		background: var(--color-bg);
	}
	.onglets-cards {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(min(240px, 100%), 1fr));
		gap: 0.75rem;
	}
	.onglet-card {
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		border-radius: 8px;
		padding: 0.75rem;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.intro-pages {
		margin-bottom: 1.25rem;
	}
	.section-pleine {
		grid-column: 1/-1;
	}
</style>
