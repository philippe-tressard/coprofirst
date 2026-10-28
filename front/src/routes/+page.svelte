<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { auth } from '#lib/api/index.ts';
	import { setUser } from '#lib/stores/auth.ts';
	import { CHEMIN_CONNEXION } from '#lib/redirection.ts';
	import EtatListe from '#lib/components/EtatListe.svelte';

	onMount(async () => {
		try {
			const user = await auth.me();
			setUser(user);
			//  L'étiquette d'une notification suit (#1634) : `(app)` la lit à l'arrivée.
			goto(`/tableau-de-bord${window.location.search}`);
		} catch {
			goto(CHEMIN_CONNEXION);
		}
	});
</script>

<div class="attente-accueil">
	<EtatListe chargement />
</div>

<style>
	.attente-accueil {
		display: flex;
		align-items: center;
		justify-content: center;
		height: 100vh;
	}
</style>
