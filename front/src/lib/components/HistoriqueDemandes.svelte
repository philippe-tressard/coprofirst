<!--
  **L'historique des demandes de modification de profil** — replié par défaut.

  ## Pourquoi ce composant (#522)

  Extrait de `profil/+page.svelte` quand le garde-fou de modularité a refusé que
  la page grossisse en recevant le bandeau de chargement partiel (690 → 705
  lignes). Le refus disait vrai : cette table n'appartient pas à la page qui
  affiche un profil, elle affiche le **suivi d'une démarche**.

  ## Ce qu'il emporte, et pourquoi

  🔴 Les deux tables de libellés sont d'abord venues avec lui — et j'ai cassé la
  page, qui s'en sert AUSSI pour la demande en cours, quarante lignes plus haut.
  Elles vivent désormais dans `#lib/demandes.ts`, lues par les deux : recopier
  aurait donné deux vocabulaires d'accord le jour même et divergents au premier
  libellé ajusté (c'est la panne des statuts de ticket, #415).

  ⚠️ `statutLabels` — le type d'occupant souhaité — **reste** dans la page :
  elle s'en sert aussi pour afficher le statut courant du compte. C'est pourquoi
  il arrive ici en `prop` plutôt que d'être recopié : deux tables du même
  vocabulaire divergeraient au premier libellé ajusté.
-->
<script lang="ts">
	import Badge from '#lib/components/Badge.svelte';
	import type { MaDemandeProfil } from '#lib/api/index.ts';
	import { fmtDateShort as fmtDate } from '#lib/date.ts';
	import { STATUT_DEMANDE_BADGE, STATUT_DEMANDE_LABEL } from '#lib/demandes.ts';

	export let demandes: MaDemandeProfil[] = [];
	/** Vrai tant que la donnée n'est pas arrivée : on ne montre rien. */
	export let chargement = false;
	/** Le vocabulaire des types d'occupant — porté par la page (voir l'en-tête). */
	export let statutLabels: Record<string, string> = {};
</script>

{#if !chargement && demandes.length > 0}
	<details class="hd-bloc">
		<summary class="hd-resume">Historique des demandes ({demandes.length})</summary>
		<div class="table-wrap">
			<table class="table hd-table">
				<thead>
					<tr><th>Date</th><th>Changement demandé</th><th>Statut</th><th>Motif refus</th></tr>
				</thead>
				<tbody>
					{#each demandes as d (d.id)}
						<tr>
							<td>{fmtDate(d.cree_le)}</td>
							<td>
								{#if d.statut_souhaite}{statutLabels[d.statut_souhaite] ?? d.statut_souhaite}{/if}
								{#if d.statut_souhaite && d.batiment_nom_souhaite}&nbsp;/
								{/if}
								{#if d.batiment_nom_souhaite}{d.batiment_nom_souhaite}{/if}
							</td>
							<td
								><Badge teinte={STATUT_DEMANDE_BADGE[d.statut_demande] ?? 'badge-gray'}
									>{STATUT_DEMANDE_LABEL[d.statut_demande] ?? d.statut_demande}</Badge
								></td
							>
							<td class="hd-motif">{d.motif_refus ?? '—'}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</details>
{/if}

<style>
	/*  Les styles étaient EN LIGNE dans la page (`style="…"`). Les nommer en les
	    déplaçant est ce qui les rend modifiables sans relire le balisage — et
	    `lint:styles-nus` refuse désormais un sélecteur d'élément nu dans un
	    composant, ce qui impose de les nommer de toute façon. */
	.hd-bloc {
		margin-top: 1rem;
	}
	.hd-resume {
		cursor: pointer;
		font-size: var(--fs-md);
		color: var(--color-text-muted);
	}
	.hd-table {
		font-size: var(--fs-md);
		margin-top: 0.5rem;
	}
	.hd-motif {
		color: var(--color-text-muted);
	}
</style>
