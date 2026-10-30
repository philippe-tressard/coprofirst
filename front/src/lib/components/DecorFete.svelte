<!--
  Le DÉCOR DES JOURS DE FÊTE (#2312) — maquettes arbitrées le 29/10/2026.

  Un décor fixe dans le coin haut droit de la colonne de contenu, et un seul petit
  élément qui bouge. Il passe DERRIÈRE le contenu (`z-index: -1`), ne capte aucun
  clic et reste muet pour un lecteur d'écran (`aria-hidden`) : c'est un ornement.

  - Les dates : `#lib/fetes` (la seule écriture), lues au jour de Paris.
  - L'interrupteur : le service « Décor des jours de fête » d'Admin › Services,
    que le serveur résume en une clé publique calculée, `decor_fetes` — puis
    celui de la personne, au Profil (`ChoixDecorFete`, `decor_fetes` du compte).
  - L'opacité : UNE valeur pour toutes les fêtes, `--decor-fete-opacite` (25 %).
  - Moins d'animations demandées : le décor reste, rien ne bouge.
  - Le message de fête, de temps en temps, à sa place fixe sous le décor et
    traversé d'un reflet : `DecorFeteMessage`, qui ne dépend pas du mouvement.

  Le jour se lit au montage, côté navigateur : le rendu serveur ne montre jamais
  de décor, donc rien ne change à l'hydratation.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { configStore } from '#lib/stores/pageConfig.ts';
	import { currentUser } from '#lib/stores/auth.ts';
	import { jourIso } from '#lib/date.ts';
	import { feteDuJour, type CodeFete } from '#lib/fetes.ts';
	import DecorFeteDessin from '#lib/components/DecorFeteDessin.svelte';
	import DecorFeteMouvement from '#lib/components/DecorFeteMouvement.svelte';
	import DecorFeteMessage from '#lib/components/DecorFeteMessage.svelte';

	let jour = '';
	onMount(() => {
		jour = jourIso();
	});

	//  Deux interrupteurs : la copropriété (le service), puis la personne (son
	//  Profil, sur le compte — vrai tant qu'elle n'y a pas touché).
	let fete: CodeFete | null = null;
	$: fete =
		jour && $configStore['decor_fetes'] === '1' && $currentUser?.decor_fetes !== false
			? feteDuJour(jour)
			: null;
</script>

{#if fete}
	<div class="decor-fete" aria-hidden="true" data-fete={fete}>
		<DecorFeteDessin {fete} />
		<DecorFeteMouvement {fete} />
		<DecorFeteMessage {fete} {jour} />
	</div>
{/if}
