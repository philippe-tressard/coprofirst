<!--
  Le logo de la résidence, dans Admin › Paramétrage (#1728).

  Un GESTE immédiat, pas un champ du formulaire : le fichier part au serveur dès
  qu'il est choisi, comme la photo de profil (`ImageUpload`, le même composant).
  C'est pourquoi il vit à part de `siteConfig`, que la page enregistre d'un bloc :
  le serveur seul pose `site_logo` (`PUT /config` le refuse), après avoir
  contrôlé le fichier, et ce composant reporte son nom dans le `configStore` —
  le menu, l'écran de connexion et l'onglet changent aussitôt.

  ## Le logo sur fond sombre (09/11/2026)

  Un second champ, dès qu'un logo existe : son aperçu montre, sur le bleu plein de
  la charte, CE QUI EST SERVI sur un fond sombre — le dessin téléversé pour lui,
  sinon le logo tel quel, avec son cadre blanc. L'administrateur voit donc le
  défaut avant de le corriger. Les deux champs partagent leurs gestes : seule la
  variante change.

  ## Côte à côte (10/11/2026)

  Demandé à l'écran : les deux logos sur UNE ligne, « fond normal » à gauche,
  « fond sombre » à droite — empilés, on ne les comparait pas d'un regard. Une
  grille à deux colonnes, qui retombe à une seule quand la place manque
  (téléphone). 🔒 `e2e/logo-menu.spec.ts`
-->
<script lang="ts">
	import ImageUpload from '#lib/components/ImageUpload.svelte';
	import { config as configApi, type CleLogo, type VarianteLogo } from '#lib/api/index.ts';
	import { configStore } from '#lib/stores/pageConfig.ts';
	import { tenter } from '#lib/erreurs.ts';
	import { confirmer } from '#lib/confirmation.ts';
	import { NOM_PLATEFORME } from '#lib/plateforme.ts';

	const CLES: Record<VarianteLogo, CleLogo> = { clair: 'site_logo', sombre: 'site_logo_sombre' };

	let envoi: VarianteLogo | null = null;
	$: logo = $configStore['site_logo'] ?? '';
	$: logoSombre = $configStore['site_logo_sombre'] ?? '';

	/** Reporte dans le store ce que le serveur vient d'écrire — retirer le logo retire sa variante. */
	function poser(variante: VarianteLogo, valeur: string | null) {
		configStore.update((c) => {
			const suite = { ...c };
			if (valeur) suite[CLES[variante]] = valeur;
			else delete suite[CLES[variante]];
			if (!valeur && variante === 'clair') delete suite[CLES.sombre];
			return suite;
		});
	}

	async function televerser(variante: VarianteLogo, fichier: File) {
		envoi = variante;
		await tenter(
			async () =>
				poser(
					variante,
					(await configApi.televerserLogo(fichier, variante))[CLES[variante]] ?? null,
				),
			'Logo enregistré',
			'Logo refusé',
		);
		envoi = null;
	}

	async function retirer(variante: VarianteLogo) {
		const oui = await confirmer(
			variante === 'clair'
				? {
						titre: 'Retirer le logo',
						message: `Le logo de la résidence sera supprimé, et celui de ${NOM_PLATEFORME} reprendra sa place partout.`,
						libelleConfirmer: 'Retirer',
					}
				: {
						titre: 'Retirer le logo sur fond sombre',
						message:
							'Ce dessin sera supprimé : sur un fond sombre, le logo de la résidence s’affichera de nouveau tel quel.',
						libelleConfirmer: 'Retirer',
					},
		);
		if (!oui) return;
		await tenter(
			async () => {
				await configApi.supprimerLogo(variante);
				poser(variante, null);
			},
			variante === 'clair' ? 'Logo neutre rétabli' : 'Logo sur fond sombre retiré',
		);
	}
</script>

<div class="champ-large logos">
	<div class="field">
		<!--  Seul, c'est « le logo » ; à côté de sa variante, on dit sur quel fond. -->
		<label for="logo-residence">{logo ? 'Logo sur fond normal' : 'Logo de la résidence'}</label>
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
					uploading={envoi === 'clair'}
					on:change={(e) => televerser('clair', e.detail)}
				/>
			{/key}
			{#if logo}
				<button type="button" class="btn btn-outline btn-sm" on:click={() => retirer('clair')}
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

	{#if logo}
		<div class="field">
			<label for="logo-residence-sombre">Logo sur fond sombre</label>
			<div class="logo-gestes">
				{#key `${logo}/${logoSombre}`}
					<ImageUpload
						id="logo-residence-sombre"
						currentUrl={configApi.logoUrl(256, logoSombre || logo, 'sombre')}
						label={logoSombre ? 'Changer le logo' : 'Ajouter un logo'}
						accept="image/png"
						previewSize="96px"
						fondSombre
						uploading={envoi === 'sombre'}
						on:change={(e) => televerser('sombre', e.detail)}
					/>
				{/key}
				{#if logoSombre}
					<button type="button" class="btn btn-outline btn-sm" on:click={() => retirer('sombre')}
						>Retirer</button
					>
				{/if}
			</div>
			<span class="aide"
				>Facultatif. Le même dessin en traits clairs, sur fond transparent (PNG, 2 Mo au plus). Il
				remplace le logo partout où le fond est sombre : le site au thème sombre, l’en-tête des
				courriels, de la fiche arrivant et des affiches de hall, le manuel.
				{#if !logoSombre}L’aperçu montre ce qui s’y affiche aujourd’hui : le logo tel quel, avec son
					fond.{/if}</span
			>
		</div>
	{/if}
</div>

<style>
	/*  Les deux logos côte à côte ; une seule colonne quand la place manque. */
	.logos {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, 17rem), 1fr));
		gap: 1rem 2rem;
		align-items: start;
	}
	.logo-gestes {
		display: flex;
		align-items: center;
		gap: 1rem;
		flex-wrap: wrap;
	}
</style>
