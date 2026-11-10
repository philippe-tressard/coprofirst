<!--
  Les gestes de rôle d'un compte (Admin › Comptes) : donner ou retirer le
  conseil syndical, l'administration et l'opérateur de la plateforme.

  🔴 La règle n'est plus ici (#2618, 10/11/2026) : l'API la SERT avec chaque
  compte (`gestes_roles`, `utils/gestes_roles`) — « + CS » et « + Admin » aux
  copropriétaires, jamais retirés à leur dernier titulaire actif, l'opérateur à
  un administrateur et hors instance commune. L'app iOS lit la même chose ;
  l'écran recomposait la règle (`gestesAdminOperateur`, `compterTitulaires`).
  Le geste lui-même — la confirmation, puis l'appel — reste à l'onglet, qui le
  reçoit par `demander`.
-->
<script lang="ts">
	import type { UtilisateurAdmin } from '#lib/api/index.ts';
	import { aRole } from '#lib/stores/auth.ts';
	import { configStore } from '#lib/stores/pageConfig.ts';
	import { CLE_OPERATEUR_PAR_EXPLOITANT } from '#lib/portee.ts';

	export let u: UtilisateurAdmin;
	export let demander: (u: UtilisateurAdmin, role: string, action: 'ajouter' | 'retirer') => void;

	//  Ce que l'écran DIT, pas ce qu'il offre : l'opérateur désigné par l'exploitant.
	$: parExploitant = $configStore[CLE_OPERATEUR_PAR_EXPLOITANT] === '1';
	//  Sans gestes servis (une réponse d'avant #2618), aucun : un défaut FERMÉ,
	//  l'écran n'offre jamais un geste que la route n'a pas annoncé.
	$: g = u.gestes_roles ?? { conseil_syndical: null, admin: null, operateur: null };
</script>

{#if !u.actif}
	<span class="muted inactif">Compte inactif</span>
{:else}
	<div class="action-row">
		{#if g.conseil_syndical === 'ajouter'}
			<button
				class="btn btn-outline btn-sm ajouter-cs"
				on:click={() => demander(u, 'conseil_syndical', 'ajouter')}
			>
				+ CS
			</button>
		{:else if g.conseil_syndical === 'retirer'}
			<button
				class="btn btn-outline btn-sm retirer"
				on:click={() => demander(u, 'conseil_syndical', 'retirer')}
			>
				– CS
			</button>
		{/if}
		{#if g.admin === 'ajouter'}
			<button
				class="btn btn-outline btn-sm ajouter-admin"
				on:click={() => demander(u, 'admin', 'ajouter')}
			>
				+ Admin
			</button>
		{:else if g.admin === 'retirer'}
			<button
				class="btn btn-outline btn-sm retirer"
				on:click={() => demander(u, 'admin', 'retirer')}
			>
				– Admin
			</button>
		{/if}
		{#if g.operateur === 'ajouter'}
			<button
				class="btn btn-outline btn-sm ajouter-operateur"
				on:click={() => demander(u, 'operateur', 'ajouter')}
			>
				+ Opérateur
			</button>
		{:else if g.operateur === 'retirer'}
			<button
				class="btn btn-outline btn-sm retirer"
				on:click={() => demander(u, 'operateur', 'retirer')}
			>
				– Opérateur
			</button>
		{:else if parExploitant && aRole(u, 'operateur')}
			<span class="muted">Opérateur désigné par l’exploitant</span>
		{/if}
	</div>
{/if}

<style>
	.inactif {
		font-size: var(--fs-sm);
	}
	/*  Qualifiés par `.btn-outline` : posées seules, ces teintes perdraient contre
	    `.btn-outline:hover` (0,2,0) — que l'attribut `style` d'origine, lui, battait. */
	.btn-outline.ajouter-cs {
		color: var(--color-info);
		border-color: var(--color-info);
	}
	.btn-outline.ajouter-admin {
		color: var(--color-orange);
		border-color: var(--color-orange);
	}
	.btn-outline.ajouter-operateur {
		color: var(--color-violet);
		border-color: var(--color-violet);
	}
	.btn-outline.retirer {
		color: var(--color-danger);
		border-color: var(--color-danger);
	}
</style>
