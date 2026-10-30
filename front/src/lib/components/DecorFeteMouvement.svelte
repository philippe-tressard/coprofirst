<!--  Ce qui BOUGE dans le décor de fête (#2312) : un seul élément par fête, qui
      suit un tracé du dessin (`#lib/decor-fetes`). Feuille : celle de `DecorFete`. -->
<script lang="ts">
	import type { CodeFete } from '#lib/fetes.ts';
	import { ETOILE, NOTE, ONDE, PORTEE, SERPENTIN, TOILE, chemin } from '#lib/decor-fetes.ts';

	export let fete: CodeFete;

	/** Les deux notes : la ligne de portée suivie, leur largeur, et la seconde décalée. */
	const NOTES: readonly (readonly [number, number, string])[] = [
		[2, 14, ''],
		[3, 12, 'seconde'],
	];
</script>

{#if fete === 'nouvel-an'}
	<svg
		class="mobile glisse or"
		style:offset-path={chemin(SERPENTIN)}
		viewBox="0 0 24 24"
		width="22"
		height="22"
	>
		<path
			class="scintille"
			d={ETOILE}
			fill="currentColor"
			fill-opacity=".4"
			stroke="currentColor"
			stroke-width="1.3"
		/>
	</svg>
{:else if fete === 'premier-avril'}
	<svg
		class="mobile nage bleu"
		style:offset-path={chemin(ONDE)}
		viewBox="0 0 32 15"
		width="34"
		height="16"
	>
		<g stroke="currentColor" stroke-width="1.1" stroke-linejoin="round">
			<path d="M2 7.5Q10-1 22 7.5Q10 16 2 7.5Z" fill="currentColor" fill-opacity=".15" />
			<path d="M22 7.5l8-6v12Z" fill="none" />
		</g>
		<circle cx="6" cy="6.5" r="1" fill="currentColor" />
	</svg>
	<svg class="mobile bulle bleu" viewBox="0 0 12 12" width="9" height="9">
		<circle cx="6" cy="6" r="5" fill="none" stroke="currentColor" />
	</svg>
	<svg class="mobile bulle seconde bleu" viewBox="0 0 12 12" width="7" height="7">
		<circle cx="6" cy="6" r="5" fill="none" stroke="currentColor" />
	</svg>
{:else if fete === 'fete-musique'}
	{#each NOTES as [ligne, taille, classe] (ligne)}
		<svg
			class="mobile parcourt bleu {classe}"
			style:offset-path={chemin(PORTEE[ligne])}
			viewBox="0 0 16 24"
			width={taille}
			height={Math.round(taille * 1.5)}
		>
			<path d={NOTE} fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" />
			<ellipse
				cx="4.5"
				cy="19.5"
				rx="3.6"
				ry="2.7"
				fill="currentColor"
				transform="rotate(-20 4.5 19.5)"
			/>
		</svg>
	{/each}
{:else if fete === 'halloween'}
	<svg
		class="mobile glisse bleu"
		style:offset-path={chemin(TOILE)}
		viewBox="0 0 20 16"
		width="22"
		height="18"
	>
		<path
			d="M7 6L2 2M7 8L1 7M7 10L2 13M7 11L4 15M13 6l5-4M13 8l6-1M13 10l5 3M13 11l3 4"
			fill="none"
			stroke="currentColor"
			stroke-width="1.2"
		/>
		<ellipse cx="10" cy="9" rx="3.4" ry="4" fill="currentColor" />
	</svg>
{:else if fete === 'noel'}
	<svg class="mobile flocon bleu" viewBox="0 0 18 18" width="14" height="14">
		<path
			d="M9 1v16M2 5l14 8M2 13l14-8M7 2l2 2 2-2M7 16l2-2 2 2"
			fill="none"
			stroke="currentColor"
			stroke-width="1.1"
		/>
	</svg>
{/if}
