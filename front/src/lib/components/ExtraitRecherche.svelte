<!--
  ExtraitRecherche.svelte — ce qui a fait trouver une affaire : « Trouvé dans une
  suite », et le passage, mots surlignés.

  Rendu dans l'aperçu d'une carte d'affaire ou d'actualité, seulement quand la
  liste est une RECHERCHE (27/09/2026, maquette A avec l'extrait de la C).

  ⚠️ Les segments viennent du serveur en TEXTE, jamais en HTML : `<mark>` est posé
  ici, par le gabarit — il n'y a rien à assainir, et donc aucun `{@html}`.
-->
<script lang="ts">
	import type { CorrespondanceAffaire } from '#lib/api/index.ts';
	import { fmtDate } from '#lib/date.ts';
	import { SOURCE_DATEE, TROUVE_DANS } from '#lib/recherche-affaires.ts';

	export let correspondance: CorrespondanceAffaire;
	/** L'affaire est aux Archives : la recherche les montre quand on le demande. */
	export let archivee = false;

	$: source = SOURCE_DATEE[correspondance.ou];
	//  La clé d'un segment est sa POSITION dans le passage : deux segments peuvent
	//  porter le même texte, jamais commencer au même caractère.
	$: morceaux = correspondance.extrait.map((segment, i, tous) => ({
		...segment,
		debut: tous.slice(0, i).reduce((n, s) => n + s.texte.length, 0),
	}));
	$: origine = source
		? [`${source} du ${fmtDate(correspondance.date)}`, correspondance.auteur]
				.filter(Boolean)
				.join(' · ')
		: '';
</script>

<div class="extrait-recherche">
	<div class="trouve">
		<span class="pastille-trouve">Trouvé dans {TROUVE_DANS[correspondance.ou]}</span>
		{#if archivee}<span class="badge badge-gray">Archivée</span>{/if}
	</div>
	{#if correspondance.extrait.length}
		<p class="passage">
			{#if origine}<span class="origine">{origine}</span>{/if}
			{#each morceaux as segment (segment.debut)}{#if segment.surligne}<mark>{segment.texte}</mark
					>{:else}{segment.texte}{/if}{/each}
		</p>
	{/if}
</div>

<style>
	.extrait-recherche {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		margin-top: 0.3rem;
	}
	.trouve {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
		align-items: center;
	}
	.pastille-trouve {
		font-size: var(--fs-xs);
		padding: 0.1rem 0.55rem;
		border-radius: 999px;
		background: color-mix(in srgb, var(--color-accent) 16%, var(--color-surface));
		border: 1px solid color-mix(in srgb, var(--color-accent) 45%, var(--color-surface));
		color: var(--color-text);
	}
	.passage {
		margin: 0;
		font-size: var(--fs-xs);
		line-height: 1.35;
		color: var(--color-text-muted);
		padding: 0.3rem 0.55rem;
		border-radius: var(--radius);
		background: var(--color-bg);
	}
	.origine {
		display: block;
		font-size: var(--fs-2xs);
	}
	mark {
		background: color-mix(in srgb, var(--color-accent) 35%, var(--color-surface));
		color: var(--color-text);
		border-radius: 3px;
		padding: 0 0.1rem;
	}
</style>
