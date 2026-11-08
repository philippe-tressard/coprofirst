<!--
  ChoixSaisieAffaire.svelte — la saisie d'une affaire, Essentielle ou Complète,
  dans le Profil (#2595, 08/11/2026).

  Trois entrées, comme le thème : « Selon mon rôle » (cochée tant qu'on n'a rien
  choisi), « Essentielle » et « Complète ». Le défaut se calcule côté serveur
  (`UserRead.saisie_affaire_effective`) : la phrase d'aide dit ce qui s'applique
  AUJOURD'HUI, elle ne le dérive pas.

  Le choix vit sur le COMPTE, pour tous les appareils — au contraire du thème
  (cookie) : la saisie ne doit pas différer entre le téléphone et l'ordinateur.

  Il s'applique sur-le-champ, comme le décor des fêtes : le compte en mémoire
  change d'abord, puis la requête part ; un refus remet le choix où il était.
-->
<script lang="ts">
	import ChoixPastilles from '#lib/components/ChoixPastilles.svelte';
	import { currentUser } from '#lib/stores/auth.ts';
	import {
		enregistrerSaisie,
		LIBELLE_MODE,
		OPTIONS_SAISIE,
		type ChoixSaisie,
	} from '#lib/saisie-affaire.ts';

	$: choisi = ($currentUser?.saisie_affaire ?? 'role') as ChoixSaisie;
	$: effectif = $currentUser?.saisie_affaire_effective ?? 'essentielle';

	//  `valeur` suit les pastilles ; `vu` est ce qui a déjà été relu du compte ou envoyé.
	let valeur = '';
	let vu = '';
	$: valeur = vu = choisi;

	/*  Pas de boucle : `vu` est posé AVANT l'envoi, donc la condition tombe aussitôt ; un refus
	    ramène la pastille au compte. Le contrôle ne voit pas que `enregistrerSaisie` est externe. */
	/* eslint-disable svelte/infinite-reactive-loop */
	$: if (valeur !== vu) {
		vu = valeur;
		void enregistrerSaisie(valeur as ChoixSaisie).then((ok) => {
			if (!ok) valeur = vu = choisi;
		});
	}
	/* eslint-enable svelte/infinite-reactive-loop */
</script>

{#if $currentUser}
	<section class="card carte-saisie">
		<h2 class="section-title">Saisie d’une affaire</h2>
		<ChoixPastilles
			options={OPTIONS_SAISIE}
			bind:valeur
			tous={false}
			radio="saisie-affaire"
			libelle="Saisie d’une affaire"
			libelleVisible
			defilante={false}
			avecDetail
		/>
		<p class="aide" aria-live="polite">
			{LIBELLE_MODE[effectif === 'complete' ? 'complete' : 'essentielle']} aujourd’hui. En saisie essentielle,
			les autres sections se rangent dans « Plus de détails », avec leur valeur par défaut. Ce choix vaut
			pour votre compte, sur tous vos appareils.
		</p>
	</section>
{/if}

<style>
	/*  `.section-title`, `.aide` : la charte porte tout (composants.css). */
	.carte-saisie {
		margin-bottom: 1.5rem;
	}
</style>
