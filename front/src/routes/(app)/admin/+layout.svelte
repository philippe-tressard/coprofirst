<script lang="ts">
	import { goto } from '$app/navigation';
	import { isAdminOuOperateur, authResolue } from '#lib/stores/auth.ts';

	//  Ce garde décidait dans un `onMount`, donc AVANT que `(app)/+layout.svelte`
	//  ait fini de charger l'utilisateur : `$isAdmin` valait encore false, et toute
	//  adresse `/admin/**` ouverte directement — lien partagé, favori, F5 —
	//  renvoyait au tableau de bord, y compris pour un administrateur. En navigation
	//  interne l'utilisateur était déjà chargé, d'où un défaut invisible depuis
	//  toujours (trouvé le 12/08/2026 en vérifiant `/admin/patrimoine`).
	//
	//  Il attend désormais de SAVOIR : `authResolue` distingue « pas connecté » de
	//  « on ne sait pas encore », que `isAuthenticated` confondait. On ne refuse que
	//  sur un « non » avéré, jamais sur un « pas encore ».
	//  L'opérateur qui n'est pas administrateur entre aussi (#2029) : la page ne
	//  lui ouvre que sa supervision (`#lib/onglets-ouverts`).
	$: if ($authResolue && !$isAdminOuOperateur) {
		goto('/tableau-de-bord');
	}
</script>

{#if $isAdminOuOperateur}
	<slot />
{/if}
