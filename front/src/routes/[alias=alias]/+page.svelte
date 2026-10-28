<!--
  `/<alias>` sur l'hôte commun d'une installation à plusieurs copropriétés (#1894) :
  un lien court vers une copropriété, `acces.example/75015-les-tilleuls`. Il ne sert
  rien — il REDIRIGE vers l'adresse de la copropriété (spec §4.1 bis, règle 2).

  L'alias passe par l'aiguillage du serveur, le même que celui de l'écran de
  connexion : même correspondance exacte, même plafond de tentatives, même message
  d'échec, et l'écran d'aiguillage s'affiche alors pour une saisie. Ailleurs que
  sur l'hôte commun, la route n'a rien à faire : elle renvoie à la connexion.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { aiguillage } from '#lib/api/index.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { CHEMIN_CONNEXION } from '#lib/redirection.ts';
	import AiguillageCopropriete from '#lib/components/AiguillageCopropriete.svelte';
	import EtatListe from '#lib/components/EtatListe.svelte';
	import LogoResidence from '#lib/components/LogoResidence.svelte';
	import { NOM_PLATEFORME } from '#lib/plateforme.ts';

	let echec = '';

	onMount(async () => {
		let commun = false;
		try {
			commun = (await aiguillage.etat()).hote_commun === true;
		} catch {
			commun = false;
		}
		if (!commun) {
			goto(CHEMIN_CONNEXION, { replaceState: true });
			return;
		}
		try {
			const { destination } = await aiguillage.aller({ alias: page.params.alias ?? '' });
			window.location.replace(destination);
		} catch (e) {
			echec = messageErreur(e);
		}
	});
</script>

<svelte:head><title>{NOM_PLATEFORME}</title></svelte:head>

<div class="auth-page">
	<div class="auth-card card">
		<div class="auth-header">
			<span class="auth-logo"><LogoResidence taille={48} /></span>
			<h1>{NOM_PLATEFORME}</h1>
		</div>
		{#if echec}
			<AiguillageCopropriete {echec} />
		{:else}
			<EtatListe chargement />
		{/if}
	</div>
</div>
