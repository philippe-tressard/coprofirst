<!--
  Une RÉPARTITION en barres découpées selon l'autre axe (#2043, arbitré le
  17/10/2026) — « Par catégorie » découpée par bâtiment, « Par bâtiment »
  découpée par catégorie. Un composant pour les deux : seules changent les
  barres et la teinte de leurs tranches (`teinte`).

  - La longueur d'une barre est son nombre, rapporté à la plus grande ; ses
    tranches la remplissent, chacune à sa part, séparées d'un filet de 2 px.
  - Le nombre s'écrit en bout de barre ; la légende dessous nomme chaque
    tranche ; le survol (et le titre lu au lecteur d'écran) donne « Bât. A : 3 ».
    La couleur ne porte jamais l'information seule (skill dataviz).
  - Les teintes : jetons `--serie-*` et `--palier-*` de la charte ; CHOISIES
    par le serveur (`TrancheRepartition.teinte`, #2082) — une teinte suit
    l'entité, jamais son rang, et le PDF peint la même. Elle se pose
    en `data-teinte`, jamais en classe calculée : `lint:css-orphelin` ne verrait
    plus les classes du fichier.
-->
<script lang="ts">
	import type { BarreRepartition } from '#lib/api/index.ts';
	import { legende } from '#lib/repartition.ts';

	export let titre: string;
	export let barres: BarreRepartition[];

	const id = `rep-${Math.random().toString(36).slice(2, 8)}`;
	$: plusGrand = Math.max(1, ...barres.map((b) => b.nombre));
	$: tranchesLegende = legende(barres.map((b) => b.tranches));
</script>

<section class="report-card repartition" aria-labelledby="{id}-titre">
	<h3 id="{id}-titre" class="intitule">{titre}</h3>
	<ul class="barres">
		{#each barres as b (b.cle)}
			<li>
				<span>{b.libelle}</span>
				<span
					class="piste"
					role="img"
					aria-label="{b.libelle} : {b.nombre} — {b.tranches
						.map((t) => `${t.libelle} ${t.nombre}`)
						.join(', ')}"
				>
					<span class="remplie" style="width:{(100 * b.nombre) / plusGrand}%">
						{#each b.tranches as t (t.cle)}
							<span
								class="tranche"
								data-teinte={t.teinte}
								style="flex-grow:{t.nombre}"
								title="{t.libelle} : {t.nombre}"
							></span>
						{/each}
					</span>
				</span>
				<span class="nombre">{b.nombre}</span>
			</li>
		{/each}
	</ul>
	{#if tranchesLegende.length}
		<ul class="legende" aria-label="Légende">
			{#each tranchesLegende as t (t.cle)}
				<li>
					<span class="pastille" data-teinte={t.teinte} aria-hidden="true"></span>{t.libelle}
				</li>
			{/each}
		</ul>
	{/if}
</section>

<style>
	.repartition {
		display: flex;
		flex-direction: column;
	}
	.intitule {
		font-size: var(--fs-xs);
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--color-text-muted);
		margin: 0 0 0.5rem;
	}
	.barres {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		grid-template-columns: max-content 1fr 2.5ch;
		gap: 0.4rem 0.6rem;
		align-items: center;
		font-size: var(--fs-sm);
	}
	.barres li {
		display: contents;
	}
	.piste {
		background: var(--color-neutre-fond);
		border-radius: var(--radius);
		height: 0.6rem;
		overflow: hidden;
	}
	.remplie {
		display: flex;
		gap: 2px;
		height: 100%;
	}
	.tranche {
		display: block;
		height: 100%;
		flex-basis: 0;
	}
	.tranche:first-child {
		border-radius: var(--radius) 0 0 var(--radius);
	}
	.tranche:last-child {
		border-radius: 0 var(--radius) var(--radius) 0;
	}
	.tranche:only-child {
		border-radius: var(--radius);
	}
	.nombre {
		text-align: right;
		font-weight: 700;
	}
	.legende {
		list-style: none;
		margin: auto 0 0;
		padding: 0.5rem 0 0;
		display: flex;
		flex-wrap: wrap;
		gap: 0.25rem 0.75rem;
		font-size: var(--fs-xs);
		color: var(--color-text-muted);
	}
	.legende li {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
	}
	.pastille {
		width: 0.6rem;
		height: 0.6rem;
		border-radius: 2px;
		display: inline-block;
	}
	[data-teinte='s1'] {
		background: var(--serie-1);
	}
	[data-teinte='s2'] {
		background: var(--serie-2);
	}
	[data-teinte='s3'] {
		background: var(--serie-3);
	}
	[data-teinte='s4'] {
		background: var(--serie-4);
	}
	[data-teinte='s5'] {
		background: var(--serie-5);
	}
	[data-teinte='s6'] {
		background: var(--serie-6);
	}
	[data-teinte='s7'] {
		background: var(--serie-7);
	}
	[data-teinte='s8'] {
		background: var(--serie-8);
	}
	[data-teinte='autre'] {
		background: var(--color-text-muted);
	}
	[data-teinte='p1'] {
		background: var(--palier-1);
	}
	[data-teinte='p2'] {
		background: var(--palier-2);
	}
	[data-teinte='p3'] {
		background: var(--palier-3);
	}
	[data-teinte='p4'] {
		background: var(--palier-4);
	}
	[data-teinte='plusieurs'] {
		background: repeating-linear-gradient(
			45deg,
			var(--palier-2) 0 2px,
			var(--color-neutre-fond) 2px 5px
		);
	}
</style>
