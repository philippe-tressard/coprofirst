<!--
  `/espace-cs/reglement` — une ADRESSE, plus un onglet (11/10/2026).

  « ⚖️ Règlement » a quitté l'Espace CS pour Ma résidence, où il s'ouvre aux
  copropriétaires. L'adresse reste, parce qu'elle a été COPIÉE : chaque carte de
  question porte un lien `#question-reglement-N` (🔗), que le conseil a pu
  s'envoyer. Le `#` n'arrive jamais au serveur — seul le navigateur le lit —,
  d'où une page et non une redirection côté serveur (même parti que `/actualites`).
-->
<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import EtatListe from '#lib/components/EtatListe.svelte';
	import { routeOnglet } from '#lib/routes-onglets.ts';

	onMount(() => {
		goto(routeOnglet('residence', 'reglement') + window.location.hash, { replaceState: true });
	});
</script>

<EtatListe chargement messageChargement="Redirection vers Ma résidence › Règlement…" />
