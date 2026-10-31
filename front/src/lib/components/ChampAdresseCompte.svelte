<!--
  L'adresse e-mail d'un compte — et ce que la CHANGER demande (#1549).

  ## Pourquoi un composant (02/10/2026)

  Changer l'adresse d'un compte remplaçait l'ancienne sur-le-champ, sans mot de
  passe ni re-vérification : une session volée suffisait à détourner le compte.
  Désormais le serveur exige le mot de passe de QUI AGIT, et la nouvelle adresse
  ne remplace l'ancienne qu'une fois confirmée par le lien qu'elle reçoit.

  Deux écrans saisissent cette adresse — le profil (le titulaire) et
  l'administration (pour un autre compte) — et doivent dire la même chose : le
  champ, puis, dès que l'adresse diffère, le mot de passe et ce qui va se
  passer. Écrit une fois ici, l'un ne peut pas oublier ce que l'autre annonce.

  Le mot de passe n'apparaît que pour un vrai changement (`adresseChangee`) :
  réenregistrer un profil ne le demande pas.
-->
<script lang="ts">
	import ChampMotDePasse from './ChampMotDePasse.svelte';
	import EtoileRequis from './EtoileRequis.svelte';
	import { adresseChangee } from '#lib/comptes.ts';
	import { SEPARATEUR } from '#lib/separateurs.ts';

	/** Identifiant du champ d'adresse ; celui du mot de passe en dérive. */
	export let id: string;
	export let adresse = '';
	/** L'adresse du compte aujourd'hui — celle qui reste tant que rien n'est confirmé. */
	export let adresseActuelle = '';
	export let motDePasse = '';
	/** Le mot de passe de QUI AGIT : le sien sur le profil, celui de l'administrateur ailleurs. */
	export let libelleMotDePasse = 'Mot de passe actuel';
	/** L'administrateur change l'adresse d'un autre : c'est le titulaire qui confirmera. */
	export let parUnTiers = false;

	$: changee = adresseChangee(adresse, adresseActuelle);
</script>

<div class="field">
	<label for={id}>Adresse e-mail<EtoileRequis vide={!adresse} /></label>
	<input {id} type="email" bind:value={adresse} required autocomplete="email" />
</div>
{#if changee}
	<ChampMotDePasse
		id="{id}-mdp"
		libelle={libelleMotDePasse}
		bind:valeur={motDePasse}
		autocomplete="current-password"
	/>
	<p class="aide">
		{#if parUnTiers}
			Un lien de confirmation partira à la nouvelle adresse et un avis à l’actuelle, qui reste celle
			du compte jusqu’à ce que son titulaire clique sur le lien.
		{:else}
			Un lien de confirmation partira à la nouvelle adresse et un avis à l’actuelle, qui reste celle
			de votre compte{SEPARATEUR.tiret}connexion comprise{SEPARATEUR.tiret}jusqu’à ce que vous
			cliquiez sur le lien.
		{/if}
	</p>
{/if}
