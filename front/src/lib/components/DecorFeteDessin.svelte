<!--  Le DESSIN fixe du décor de fête (#2312) — ses couleurs et ses animations
      sont dans la feuille de `DecorFete`, qui l'enveloppe. -->
<script lang="ts">
	import type { CodeFete } from '#lib/fetes.ts';
	import { FANIONS, ONDE, PORTEE, SERPENTIN } from '#lib/decor-fetes.ts';

	export let fete: CodeFete;
</script>

<svg class="fond-decor" viewBox="0 0 130 130" fill="none" stroke-linecap="round">
	<defs>
		<symbol id="fete-coeur" viewBox="0 0 24 24">
			<path
				d="M12 21C5 15 2 11 2 7.5A4.5 4.5 0 0 1 12 5a4.5 4.5 0 0 1 10 2.5C22 11 19 15 12 21Z"
				fill="currentColor"
				fill-opacity=".2"
				stroke="currentColor"
				stroke-width="1.4"
				stroke-linejoin="round"
			/>
		</symbol>
		<symbol id="fete-oeuf" viewBox="0 0 20 24">
			<path class="plein" d="M10 1C4 1 1 10 1 15a9 9 0 0 0 18 0C19 10 16 1 10 1Z" />
			<path
				class="bleu"
				d="M1.6 13l3-2 3 2 4-2 3 2 3.6-2.2"
				stroke="currentColor"
				stroke-width="1.2"
			/>
		</symbol>
	</defs>

	{#if fete === 'nouvel-an'}
		<path class="or" stroke="currentColor" stroke-width="1.6" d={SERPENTIN} />
		<path
			class="bleu"
			stroke="currentColor"
			stroke-width="1.3"
			d="M130 0C118 34 96 34 102 62S120 100 108 124"
		/>
		<g fill="currentColor">
			<rect class="or" x="80" y="20" width="4" height="7" rx="1" transform="rotate(-25 82 23)" />
			<rect class="bleu" x="112" y="76" width="4" height="7" rx="1" transform="rotate(30 114 79)" />
			<circle class="rouge" cx="70" cy="70" r="2" />
			<circle class="or" cx="118" cy="44" r="1.6" />
		</g>
	{:else if fete === 'saint-valentin'}
		<g class="rouge" stroke="currentColor">
			<path stroke-width="1" d="M30 0Q78 52 130 34" />
			<path stroke-width=".8" d="M54 22v10M104 39v10" />
			<use href="#fete-coeur" x="46" y="31" width="16" height="16" />
			<use href="#fete-coeur" x="96" y="48" width="16" height="16" />
			<g class="balance">
				<path stroke-width=".8" d="M79 34.5v16" />
				<use href="#fete-coeur" x="68" y="49" width="22" height="22" />
			</g>
		</g>
	{:else if fete === 'premier-avril'}
		<g class="bleu" stroke="currentColor" stroke-width="1">
			<path d="M94 0A36 36 0 0 0 130 36" />
			<path d={ONDE} stroke-dasharray="4 4" />
			<path d="M38 0A92 92 0 0 0 130 92" />
		</g>
	{:else if fete === 'paques'}
		<path class="ambre" stroke="currentColor" stroke-width="1.6" d="M130 4C104 14 84 30 58 58" />
		<path
			class="vert"
			stroke="currentColor"
			stroke-width="1.1"
			d="M112 9q-2-8 6-10M96 18q-8-2-8 6M76 36q-8 0-8 7M66 46q2-8 9-8"
		/>
		<g fill="currentColor">
			<circle class="or" cx="118" cy="6" r="2.2" />
			<circle class="or" cx="80" cy="30" r="2" />
			<circle class="rouge" cx="62" cy="52" r="1.8" />
		</g>
		<path class="rouge" stroke="currentColor" stroke-width=".8" d="M104 14v14" />
		<use class="or" href="#fete-oeuf" x="97" y="27" width="14" height="17" />
		<path class="bleu" stroke="currentColor" stroke-width=".8" d="M70 44v12" />
		<use class="or" href="#fete-oeuf" x="63" y="55" width="14" height="17" />
		<g class="balance or">
			<path stroke="currentColor" stroke-width=".8" d="M86 27v18" />
			<use href="#fete-oeuf" x="77" y="44" width="18" height="22" />
		</g>
	{:else if fete === 'fete-musique'}
		<path class="bleu" stroke="currentColor" stroke-width=".8" d={PORTEE.join('')} />
	{:else if fete === 'quatorze-juillet'}
		<path class="bleu" stroke="currentColor" stroke-width=".9" d="M24 0Q76 60 130 44" />
		{#each FANIONS as [x, y, teinte], i (i)}
			<path class="fanion {teinte} delai-{i}" d="M{x} {y}h12l-6 14Z" />
		{/each}
		<g class="scintille" stroke-width="1.2">
			<path class="bleu" stroke="currentColor" d="M70 86v6M70 104v6M58 98h6M76 98h6" />
			<path class="rouge" stroke="currentColor" d="M62 90l3 3M75 103l3 3M78 90l-3 3M65 103l-3 3" />
		</g>
	{:else if fete === 'halloween'}
		<g class="bleu" stroke="currentColor" stroke-width=".8">
			<path d="M130 0L0 130M130 0L43 130M130 0L0 43M130 0L87 130M130 0L0 87" />
			<path d="M101 0Q104 26 130 29M72 0Q78 52 130 58M43 0Q52 78 130 87M14 0Q26 104 130 116" />
		</g>
	{:else if fete === 'noel'}
		<g class="vert" stroke="currentColor">
			<path stroke-width="2" d="M130 2C108 10 88 24 66 50" />
			<path
				stroke-width="1.1"
				d="M122 4l-4-6M122 4l2 7M112 8l-5-5M112 8l1 7M102 13l-5-4M102 13l0 7M92 19l-5-3M92 19l-1 7M82 27l-6-2M82 27l-2 6M73 38l-6-1M73 38l-3 6"
			/>
			<path
				stroke-width="1"
				fill="currentColor"
				fill-opacity=".15"
				d="M128 14q-10 2-12 10q8-1 12-10ZM128 14q-1 10 5 14"
			/>
		</g>
		<g class="rouge" fill="currentColor">
			<circle cx="124" cy="22" r="2" />
			<circle cx="120" cy="25" r="2" />
		</g>
		<path class="or" stroke="currentColor" stroke-width=".8" d="M108 9v12M78 32v12" />
		<circle class="boule rouge" cx="108" cy="27" r="6" />
		<circle class="boule bleu" cx="78" cy="50" r="6" />
		<g class="balance or">
			<path stroke="currentColor" stroke-width=".8" d="M92 19v18" />
			<rect x="90" y="35" width="4" height="3" fill="currentColor" />
			<circle class="boule" cx="92" cy="46" r="8" />
		</g>
	{/if}
</svg>
