<!--
  La VIGNETTE Public / Privé d'une affaire du rapport (#2082, arbitrée le
  20/10/2026) : « Privé = CS & Syndic / Public = tout autre cas ». Le serveur
  décide (`prive`, `utils/lecteurs_du_conseil`) ; ce composant ne fait que le
  dire — au tableau, au CR global, sur la page de relecture. Le texte porte
  l'information, la teinte l'accompagne.
-->
<script lang="ts">
	import Badge from '$lib/components/Badge.svelte';
	import { VIGNETTES } from '$lib/points-conseil';

	export let prive: boolean;

	$: v = VIGNETTES[prive ? 'prive' : 'public'];
</script>

<Badge teinte={v.teinte} compact title={v.aide}>{v.libelle}</Badge>
