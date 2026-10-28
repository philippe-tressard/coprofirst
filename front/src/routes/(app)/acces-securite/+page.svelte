<!--
  `/acces-securite` — l'adresse HISTORIQUE des accès.

  ## Pourquoi elle subsiste (12/09/2026, #928)

  Les accès sont désormais deux sous-onglets de **« Mes lots & accès »**
  (`/mon-lot/badges`, `/mon-lot/telecommandes`). Cette adresse-ci n'est plus dans
  le menu — mais elle est citée par **treize liens internes**, par la FAQ, et par
  des courriels déjà partis que personne ne peut rappeler.

  🔴 Elle redirige donc, elle ne rend pas une 404. Un lien qu'on a envoyé est un
  engagement : le rompre au motif qu'on a réorganisé le menu fait porter à
  l'utilisateur le coût de notre rangement.

  ⚠️ `replaceState: true` — la redirection ne laisse pas d'entrée dans
  l'historique : « Retour » doit ramener d'où l'on venait, pas rejouer la
  redirection en boucle.
-->
<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { routeOnglet } from '#lib/routes-onglets.ts';

	onMount(() => {
		//  La cible vient de la TABLE, jamais écrite ici : `lint:pages` refuse une
		//  route en dur, et une adresse recopiée survivrait au renommage.
		goto(routeOnglet('mon-lot', 'badges'), { replaceState: true });
	});
</script>

<p class="muted">Redirection vers vos accès…</p>
