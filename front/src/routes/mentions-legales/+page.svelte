<script lang="ts">
	import PageLegale from '#lib/components/PageLegale.svelte';
	import {
		LICENCE_NOM,
		LICENCE_SPDX,
		LICENCE_URL,
		NOM_PLATEFORME,
		lienSource,
	} from '#lib/plateforme.ts';

	//  La version qui TOURNE (AGPLv3 §13) — le pied de page de l'application
	//  pointe au même endroit, par la même fonction (#1725).
	const sourceEnService = lienSource(import.meta.env.VITE_GIT_HASH);
</script>

<PageLegale titre="Mentions légales" cle="mentions_legales">
	<!--  « Logiciel libre », et c'est exact depuis le 08/10/2026 (#1726) : la
	      licence est l'AGPL-3.0-or-later, sans condition additionnelle. Du
	      07/09 au 07/10/2026, elle portait une clause commerciale, et cette
	      section disait « code source accessible » — `standards/14`. -->
	<section class="oss-section">
		<h2>Logiciel libre</h2>
		<p>
			Ce site est propulsé par <strong>{NOM_PLATEFORME}</strong>, une application de gestion de
			copropriété distribuée sous la
			<a href={LICENCE_URL} target="_blank" rel="noopener noreferrer">{LICENCE_NOM}</a>
			({LICENCE_SPDX}).
		</p>
		<p>
			Chacun peut l’utiliser, l’étudier, le modifier et le redistribuer, y compris à titre
			commercial, à condition de publier ses modifications sous la même licence — y compris
			lorsqu’il le fait fonctionner comme service en ligne. Le code de la version en service est
			disponible sur
			<a href={sourceEnService} target="_blank" rel="noopener noreferrer">GitHub&nbsp;→</a>
		</p>
	</section>

	<svelte:fragment slot="pied">
		&nbsp;·&nbsp;
		<a href={sourceEnService} target="_blank" rel="noopener noreferrer">{NOM_PLATEFORME}</a>
	</svelte:fragment>
</PageLegale>

<style>
	/*  Ce qui est PROPRE aux mentions légales : la section « Logiciel
	    libre ». Le squelette vit dans `#lib/components/PageLegale.svelte`,
	    le reste dans `styles/legal.css` (#583).

	    🔴 Les sélecteurs ne peuvent PAS partir de `.legal-page` : cette classe
	    appartient au composant, et Svelte ne pose sa marque de portée que sur les
	    éléments écrits ICI. Un `.legal-page h2` ne correspondrait à rien, en
	    silence — c'est la section qui sert d'ancre. */
	.oss-section {
		margin-top: 2rem;
		margin-bottom: 1.5rem;
		padding-top: 1.25rem;
		border-top: 1px solid var(--color-border);
	}
	.oss-section h2 {
		font-size: 1rem;
		font-weight: 600;
		margin-bottom: 0.5rem;
	}
	.oss-section a {
		color: var(--color-primary);
	}
</style>
