<!--
  PhraseModeSaisie.svelte — la phrase discrète en tête du formulaire d'une affaire :
  elle dit la saisie en cours (Essentielle ou Complète) et où la changer (#2595).

  Discrète exprès : une ligne d'aide, pas une bannière. Le réglage est un choix fait
  une fois dans le Profil ; on le rappelle, on ne le réclame pas.

  Le lien s'ouvre dans un nouvel onglet : changer de page en pleine saisie ferait
  perdre ce qui est déjà écrit. Le mode se lit sur le compte
  (`saisie_affaire_effective`, calculé par l'API) ; sans lui, rien ne s'affiche.
-->
<script lang="ts">
	import { currentUser } from '#lib/stores/auth.ts';
	import { LIBELLE_MODE } from '#lib/saisie-affaire.ts';

	$: mode = $currentUser?.saisie_affaire_effective;
</script>

{#if mode}
	<p class="aide phrase-mode-saisie">
		{LIBELLE_MODE[mode]}{mode === 'essentielle'
			? ' — les autres sections sont dans « Plus de détails »'
			: ''}.
		<a href="/profil" target="_blank" rel="noopener">À changer dans votre profil</a>
		<span class="sr-only">(s’ouvre dans un nouvel onglet)</span>
	</p>
{/if}

<style>
	/*  `.aide`, `.sr-only` : la charte porte tout (composants.css, normes.css). */
	.phrase-mode-saisie {
		margin: 0 0 1rem;
	}
</style>
