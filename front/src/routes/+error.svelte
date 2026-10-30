<!--
  La page d'erreur du site (#2304, 30/10/2026) — adresse inconnue, accès
  refusé, panne d'un chargement.

  Il n'y en avait aucune : SvelteKit rendait la sienne, « 404 » puis « Not
  Found », en anglais, sans carte ni chemin de retour.

  Elle prend le squelette des écrans d'authentification (`authentification.css`) :
  une adresse inconnue ne correspond à aucune route, donc à aucun squelette
  `(app)` — c'est la racine qui la rend, sans menu, connecté ou non. Le titre
  vient de `#lib/erreur-page`, la phrase de l'erreur elle-même : les hooks y ont
  mis la phrase française du statut, ou l'application la sienne.

  « Retour à l'accueil » vise `/`, qui trie : le tableau de bord pour un compte
  connecté, la connexion sinon. 🔒 `e2e/page-erreur.spec.ts`
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import EnteteAuthentification from '#lib/components/EnteteAuthentification.svelte';
	import { loadSiteConfig, siteNomStore } from '#lib/stores/pageConfig.ts';
	import { erreurDePage, erreurDuServeur } from '#lib/erreur-page.ts';

	//  Le nom et le logo, si le rendu serveur ne les a pas apportés — comme
	//  à la connexion : la configuration est publique.
	onMount(loadSiteConfig);
</script>

<svelte:head><title>{erreurDePage(page.status).titre} — {$siteNomStore}</title></svelte:head>

<div class="auth-page">
	<div class="auth-card card">
		<EnteteAuthentification
			titre={erreurDePage(page.status).titre}
			sousTitre={page.error?.message || erreurDePage(page.status).phrase}
		/>
		<div class="btn-wrapper">
			<a href="/" class="btn btn-primary">Retour à l’accueil</a>
			{#if erreurDuServeur(page.status)}
				<button type="button" class="btn btn-outline" on:click={() => location.reload()}>
					Réessayer
				</button>
			{/if}
		</div>
		<p class="code-erreur">{$siteNomStore} · erreur {page.status}</p>
	</div>
</div>

<style>
	/*  Le code, pour qui le signale — discret, sous les gestes. */
	.code-erreur {
		margin-top: 1.5rem;
		text-align: center;
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
	}
</style>
