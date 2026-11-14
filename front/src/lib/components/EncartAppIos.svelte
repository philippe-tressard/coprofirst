<!--
  « Installer l'application iPhone » — l'encart de la page de connexion.

  Rien ne s'affiche hors d'un iPhone ou d'un iPad ouvert dans le navigateur : ni
  sur ordinateur, ni sur Android, ni depuis l'écran d'accueil (la PWA est déjà
  installée). Le choix est lu après le montage — le serveur ne connaît pas
  l'appareil, et un rendu côté serveur afficherait l'encart à tout le monde.

  « Plus tard » le retient sur l'appareil (`localStorage`) : l'encart ne revient pas
  à chaque ouverture. Le stockage peut manquer (navigation privée) ; l'encart
  s'affiche alors et se ferme pour la page seulement.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { proposerAppliIos } from '#lib/appareil.ts';
	import { APPLI_IOS, NOM_PLATEFORME } from '#lib/plateforme.ts';

	const CLE = 'appli_ios_encart_ferme';
	let visible = false;

	onMount(() => {
		const plein = window.matchMedia?.('(display-mode: standalone)').matches ?? false;
		const nav = {
			userAgent: navigator.userAgent,
			maxTouchPoints: navigator.maxTouchPoints,
			standalone: (navigator as Navigator & { standalone?: boolean }).standalone,
		};
		let ferme = false;
		try {
			ferme = localStorage.getItem(CLE) === '1';
		} catch {
			ferme = false;
		}
		visible = !ferme && proposerAppliIos(nav, plein);
	});

	function plusTard() {
		visible = false;
		try {
			localStorage.setItem(CLE, '1');
		} catch {
			/* stockage indisponible : fermé pour cette page seulement */
		}
	}
</script>

{#if visible}
	<aside class="encart-appli-ios" aria-label="Application iPhone">
		<p>
			<strong>L'application {NOM_PLATEFORME} existe sur iPhone.</strong>
			Installez-la depuis l'App Store.
		</p>
		<div class="actions">
			<a class="btn btn-primary btn-sm" href={APPLI_IOS} rel="noopener"
				>Télécharger sur l'App Store</a
			>
			<button type="button" class="btn btn-outline btn-sm" on:click={plusTard}>Plus tard</button>
		</div>
	</aside>
{/if}

<style>
	.encart-appli-ios {
		margin-top: 1.25rem;
		padding: 0.75rem 0.9rem;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-bg);
		font-size: var(--fs-md);
		line-height: 1.45;
		text-align: center;
	}
	.encart-appli-ios p {
		margin: 0 0 0.6rem;
	}
	.actions {
		display: flex;
		flex-wrap: wrap;
		justify-content: center;
		gap: 0.5rem;
	}
</style>
