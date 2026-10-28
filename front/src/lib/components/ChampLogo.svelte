<!--
  Le logo de la résidence, dans Admin › Paramétrage (#1728).

  Un GESTE immédiat, pas un champ du formulaire : le fichier part au serveur dès
  qu'il est choisi, comme la photo de profil (`ImageUpload`, le même composant).
  C'est pourquoi il vit à part de `siteConfig`, que la page enregistre d'un bloc :
  le serveur seul pose `site_logo` (`PUT /config` le refuse), après avoir
  contrôlé le fichier, et ce composant reporte son nom dans le `configStore` —
  le menu, l'écran de connexion et l'onglet changent aussitôt.
-->
<script lang="ts">
	import ImageUpload from '#lib/components/ImageUpload.svelte';
	import { config as configApi } from '#lib/api/index.ts';
	import { configStore } from '#lib/stores/pageConfig.ts';
	import { tenter } from '#lib/erreurs.ts';
	import { confirmer } from '#lib/confirmation.ts';
	import { NOM_PLATEFORME } from '#lib/plateforme.ts';

	let envoi = false;
	$: logo = $configStore['site_logo'] ?? '';

	function poser(valeur: string | null) {
		configStore.update((c) => {
			const suite = { ...c };
			if (valeur) suite['site_logo'] = valeur;
			else delete suite['site_logo'];
			return suite;
		});
	}

	async function televerser(e: CustomEvent<File>) {
		envoi = true;
		await tenter(
			async () => poser((await configApi.televerserLogo(e.detail)).site_logo),
			'Logo enregistré',
			'Logo refusé',
		);
		envoi = false;
	}

	async function retirer() {
		const oui = await confirmer({
			titre: 'Retirer le logo',
			message: `Le logo de la résidence sera supprimé, et celui de ${NOM_PLATEFORME} reprendra sa place partout.`,
			libelleConfirmer: 'Retirer',
		});
		if (!oui) return;
		await tenter(async () => {
			await configApi.supprimerLogo();
			poser(null);
		}, 'Logo neutre rétabli');
	}
</script>

<div class="field champ-large">
	<label for="logo-residence">Logo de la résidence</label>
	<!--  Une RANGÉE, alignée à gauche : `.field` empile et étire ses enfants, et
	      le bouton s'étalait sur toute la largeur comme un champ. -->
	<div class="logo-gestes">
		<!--  Recréé quand le logo change : l'aperçu local d'un fichier choisi ne
		      doit pas survivre à son retrait. -->
		{#key logo}
			<ImageUpload
				id="logo-residence"
				currentUrl={configApi.logoUrl(256, logo)}
				label="Changer le logo"
				accept="image/png,image/jpeg"
				previewSize="96px"
				uploading={envoi}
				on:change={televerser}
			/>
		{/key}
		{#if logo}
			<button type="button" class="btn btn-outline btn-sm" on:click={retirer}
				>Revenir au logo neutre</button
			>
		{/if}
	</div>
	<span class="aide"
		>PNG ou JPEG, 2 Mo au plus, carré de préférence (512 px). Il remplace l’icône du menu et de
		l’écran de connexion, devient l’icône de l’onglet et de l’application installée, et figure sur
		les documents et en tête des courriels. Sans logo, celui de {NOM_PLATEFORME}.</span
	>
</div>

<style>
	.logo-gestes {
		display: flex;
		align-items: center;
		gap: 1rem;
		flex-wrap: wrap;
	}
</style>
