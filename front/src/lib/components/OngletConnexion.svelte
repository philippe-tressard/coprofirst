<!--
  L'onglet **Présentation › Connexion et pied de page** de l'administration.

  Né du rangement par niveau (21/10/2026, #2062) : « Paramétrage site » mêlait
  ce qui règle la copropriété (délais, alertes — `OngletFonctionnement`) et ce
  qui règle la façon dont le site se PRÉSENTE. Les deux réglages de présentation
  viennent ici, chacun avec son bouton — une section, ses clés (#2057).

  `siteConfig` est LIÉ et `saveSiteConfig` arrive en callback, comme pour
  `OngletFonctionnement` : la page parle seule à l'API.
-->
<script lang="ts">
	import Icon from '#lib/components/Icon.svelte';
	import type { ConfigSite, SectionSite } from '#lib/configSite.ts';
	import ReglagePiedDePage from '#lib/components/ReglagePiedDePage.svelte';

	/** Lié : la page porte l'état et l'enregistre. */
	export let siteConfig: ConfigSite;
	export let siteSaving = false;
	/** Enregistre UNE section — ses clés seules (#2057). */
	export let saveSiteConfig: (section: SectionSite) => void;
</script>

<section class="card config-section">
	<h2 class="config-section-title"><Icon name="key-round" size={17} />Page de connexion</h2>
	<div class="form-grid largeur-saisie">
		<label class="field champ-double">
			Sous-titre de la page de connexion
			<input
				type="text"
				bind:value={siteConfig.login_sous_titre}
				placeholder="Votre espace numérique de résidence"
			/>
			<span class="aide">Affiché sous le nom du site sur la page de connexion.</span>
		</label>
	</div>
	<div class="form-actions largeur-saisie">
		<button
			class="btn btn-primary"
			on:click={() => saveSiteConfig('connexion')}
			disabled={siteSaving}
		>
			{siteSaving ? 'Enregistrement…' : 'Enregistrer'}
		</button>
	</div>
</section>

<ReglagePiedDePage
	bind:reglage={siteConfig.pied_de_page}
	{siteSaving}
	saveSiteConfig={() => saveSiteConfig('pied_de_page')}
/>
