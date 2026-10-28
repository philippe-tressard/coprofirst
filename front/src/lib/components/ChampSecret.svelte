<!--
  Un champ qui porte un SECRET déjà enregistré — mot de passe SMTP, mot de passe
  IMAP, clé d'API.

  ## Pourquoi ce composant (11/09/2026)

  Le motif était écrit DEUX fois, à l'identique : `OngletSmtp` et
  `SectionReceptionReponses`. La clé d'API de l'assistant en aurait fait une
  troisième — et c'est le moment où l'on factorise, pas après.

  ## Ce qu'il porte, et pourquoi ce n'est pas qu'un `<input type="password">`

  Un secret déjà posé ne se relit JAMAIS : l'API rend un marqueur, pas la valeur
  (`routers/config._SECRETS`, 03/09/2026 — `smtp_password` voyageait en clair
  dans la réponse HTTP alors que l'écran ne l'affichait pas ; la protection était
  dans le rendu, c'est-à-dire nulle part).

  Le champ doit donc dire trois choses à la fois :

  * **il existe un secret** — sinon on croit devoir le saisir à chaque visite ;
  * **on ne peut pas le lire** — le champ est désactivé, pas vide ;
  * **on peut le remplacer** — « Changer » vide le champ et rend la main.

  ⚠️ `valeur` reste vide tant qu'on ne saisit rien : l'appelant n'envoie la clé
  au serveur que si elle est **non vide**. Envoyer une chaîne vide effacerait le
  secret enregistré — c'est le défaut que ce contrat évite, et il n'a pas de
  symptôme visible avant le prochain envoi d'e-mail.
-->
<script lang="ts">
	import EtoileRequis from '#lib/components/EtoileRequis.svelte';
	/** Le libellé du champ — « Mot de passe SMTP », « Clé d'API »… */
	export let libelle: string;

	/**  Ce secret est-il OBLIGATOIRE ? L'astérisque était écrite dans le
	 *   libellé par l'appelant — donc jamais rouge, jamais collée (#1121). */
	export let requis = false;
	/** Le secret est-il posé ou saisi ? */
	export let rempli = false;
	/** La saisie. Vide = on ne touche pas au secret enregistré. */
	export let valeur = '';
	/** Un secret est-il DÉJÀ enregistré côté serveur ? */
	export let pose = false;
	/** Ce qu'on écrit quand rien n'est encore enregistré. */
	export let placeholder = '';
	/** Aide affichée quand il n'y a pas encore de secret. */
	export let aide = '';

	let enEdition = false;

	$: masque = pose && !enEdition;
</script>

<label class="field">
	<span
		>{libelle}{#if requis}<EtoileRequis vide={!rempli} />{/if}</span
	>
	<div class="champ-secret">
		<input
			type="password"
			bind:value={valeur}
			autocomplete="new-password"
			disabled={masque}
			placeholder={masque ? 'Valeur masquée' : placeholder}
		/>
		{#if masque}
			<button
				class="btn btn-outline btn-sm"
				type="button"
				on:click={() => {
					enEdition = true;
					valeur = '';
				}}
			>
				Changer
			</button>
		{/if}
	</div>
	<span class="aide">
		{#if pose && enEdition}
			Saisissez la nouvelle valeur puis cliquez sur Enregistrer.
		{:else if pose}
			Déjà enregistrée. Cliquez sur « Changer » pour la remplacer.
		{:else}
			{aide}
		{/if}
	</span>
</label>

<style>
	.champ-secret {
		display: flex;
		gap: 0.5rem;
		align-items: center;
		flex-wrap: wrap;
	}
	.champ-secret input {
		flex: 1 1 0;
		min-width: 220px;
	}
</style>
