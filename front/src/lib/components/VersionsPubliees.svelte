<!--
  Les VERSIONS PUBLIÉES, en tête de l'onglet « Installations » (#2210).

  Une version est publiée quand son tag a sa release et l'archive de déploiement
  (workflow « Images ») ; la référence relit ces releases chaque nuit
  (`registre/canaux.relire_versions`). C'est d'ici que se choisit le canal d'une
  installation — Urgence, ou l'une des versions proposées —, et ce que chaque vague
  du canal Urgence installe se lit sur la première ligne. Rien ne se règle ici :
  le serveur décide (`registre/versions`), l'écran le dit.

  Repliée par défaut : ce qui qualifie la liste reste au-dessus d'elle (`ux-patterns`
  §0 ter), sans la repousser.
-->
<script lang="ts">
	import SectionRepliee from '#lib/components/SectionRepliee.svelte';
	import type { VagueLue, VersionPubliee, VersionsPubliees } from '#lib/api/index.ts';
	import { fmtDate, fmtDatetime } from '#lib/date.ts';

	export let versions: VersionsPubliees;
	export let vagues: VagueLue[] = [];

	let ouvert = false;

	$: cibles = vagues.filter((v) => v.avec_urgence);

	const date = (v: VersionPubliee) => `publiée le ${fmtDate(v.publiee_le)}`;
</script>

<SectionRepliee titre="Versions publiées" compte={versions.proposees.length} bind:ouvert>
	{#if versions.proposees.length}
		<ul class="cibles">
			{#each cibles as v (v.code)}
				<li>
					<strong>{v.libelle}</strong>
					<span>{v.cible ? `v${v.cible.version}` : 'aucune pour l’instant'}</span>
					<span class="aide-ligne">{v.detail}</span>
				</li>
			{/each}
		</ul>
		<ul class="versions">
			{#each versions.proposees as v (v.version)}
				<li><strong>v{v.version}</strong> <span class="aide-ligne">{date(v)}</span></li>
			{/each}
		</ul>
		<p class="aide">
			Les cinq dernières mineures, chacune à son dernier correctif : ce qu’une installation peut
			suivre en vague Fixe.{#if versions.lues_le}
				Relues le {fmtDatetime(versions.lues_le)}.{/if}
			Les versions et les images que plus aucune vague ne peut servir sont purgées chaque nuit.
		</p>
	{:else}
		<p class="aide">
			Aucune version publiée lue : la référence relit les releases du dépôt au démarrage, puis
			chaque nuit, avant le renouvellement des baux.
		</p>
	{/if}
</SectionRepliee>

<style>
	.cibles,
	.versions {
		list-style: none;
		margin: 0 0 0.75rem;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		font-size: var(--fs-sm);
	}
	.cibles li,
	.versions li {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 0.25rem 0.75rem;
	}
	.aide-ligne {
		color: var(--color-text-muted);
	}
</style>
