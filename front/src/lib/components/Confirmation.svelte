<!--
  Confirmation.svelte — « êtes-vous sûr ? », dans la charte du site.

  ## Le défaut qu'il retire (#605, 29/08/2026)

  Quarante gestes du site demandaient confirmation avec `confirm()` — la boîte
  NATIVE du navigateur. Elle a trois défauts, et aucun n'est cosmétique :

  1. **elle bloque le fil d'exécution** du navigateur entier, onglet compris ;
  2. **elle ignore la charte** : ni la couleur du danger, ni le libellé des
     boutons, ni la casse du site. Sur mobile elle s'affiche en haut de l'écran,
     loin du pouce, avec « OK / Annuler » en anglais selon la langue du système ;
  3. **elle ne dit pas la gravité.** Archiver et supprimer définitivement y ont
     exactement le même aspect — or l'un se défait et l'autre non.

  ⚠️ Ce composant s'emploie par `confirmer()` (`#lib/confirmation.ts`), jamais
  directement : c'est l'appel impératif qui rend la conversion des quarante
  sites tenable, et qui garde les appelants à une ligne.
-->
<script lang="ts">
	import Modale from './Modale.svelte';

	export let titre: string;
	export let message: string;
	export let libelleConfirmer = 'Confirmer';
	export let libelleAnnuler = 'Annuler';
	/** `true` = geste irréversible : le bouton passe en rouge et le dit. */
	export let danger = false;
	export let onReponse: (ok: boolean) => void;
</script>

<!--  🔴 Le corps et le pied dans `.modal-body` / `.modal-footer` (01/10/2026,
      #779) : la boîte `.modal` porte son padding dans ces deux blocs, pas sur
      elle-même. Posés à nu, le message et les boutons touchaient les bords de
      la boîte — dans les quarante confirmations du site, au bureau comme au
      téléphone. Les modales écrites à la main, elles, avaient leur marge : c'est
      en leur faisant prendre CE composant que l'écart est apparu.
      ⚠️ Le pied garde `.form-actions` : c'est elle que `lint:soumission` lit pour
      exiger « Annuler » avant l'action, et elle donne la cible de 44 px au doigt. -->
<Modale {titre} on:fermer={() => onReponse(false)}>
	<div class="modal-body">
		<p class="confirmation-message">{message}</p>
	</div>
	<!--  « Annuler » AVANT la validation — la norme du 18/08/2026, vérifiée par
	      `lint:soumission` sur les formulaires. La même main, le même ordre. -->
	<div class="modal-footer form-actions">
		<button type="button" class="btn btn-outline" on:click={() => onReponse(false)}>
			{libelleAnnuler}
		</button>
		<button
			type="button"
			class="btn"
			class:btn-danger={danger}
			class:btn-primary={!danger}
			on:click={() => onReponse(true)}
		>
			{libelleConfirmer}
		</button>
	</div>
</Modale>

<style>
	.confirmation-message {
		margin: 0;
		font-size: var(--fs-lg);
		line-height: 1.5;
		white-space: pre-line;
	}
</style>
