<!--
  ASSOCIER UN COMPTE DU SITE à une saisie libre — recherche, suggestions, dissociation.

  ## Pourquoi c'est un objet à part (01/09/2026, #672)

  Extrait de `FormulaireBail` sur refus du contrôle de modularité, qui a rendu le
  fichier neuf à 553 lignes. Comme les neuf refus précédents, il désignait un
  **placement** : « qui est le locataire » est une question autonome — elle a son
  état, ses trois gestes (chercher, retenir, dissocier) et ses styles, et elle ne
  parle ni de lots, ni de dates, ni de notes.

  ⚠️ **Elle était écrite DEUX fois** avant ce lot — une dans le formulaire de
  création d'un bail, une dans celui d'édition —, avec six variables d'état en
  double et trois fonctions recopiées. Les deux copies avaient déjà divergé : les
  **suggestions** n'existaient que du côté édition. Ici, elles servent les deux.

  ## Le contrat

  Le composant renseigne l'identifiant du compte, le nom et le prénom, et prévient
  l'hôte par `associe` — qui verrouille alors ces deux champs : ils décrivent une
  personne enregistrée, que ce formulaire n'a pas à renommer.

  🔴 L'ADRESSE n'est plus recopiée du compte (#2153) : le serveur la rend masquée,
  pour que la recherche ne soit pas l'annuaire de la résidence. Elle est reprise
  de la saisie quand on a cherché par adresse exacte — on la connaissait —, et
  sinon laissée au bailleur, qui la saisit s'il la connaît.
-->
<script lang="ts">
	import { onMount } from 'svelte';

	import { bailleur as bailApi, type LocataireTrouve } from '$lib/api';
	import { nomAffiche } from '$lib/noms';

	/** Racine des identifiants — l'hôte la fournit, il en a déjà une. */
	export let uid: string;

	/** Le compte retenu, ou `null` si l'identité est saisie à la main. */
	export let locataireId: number | null = null;
	export let nom = '';
	export let prenom = '';
	export let email = '';
	/**  Un compte est-il associé ? Lié, parce que l'hôte en dépend : il verrouille
	 *   ses champs d'identité tant que c'est vrai. */
	export let associe = false;

	//  🔴 Les SUGGESTIONS — les locataires ayant déclaré ce bailleur, proposés
	//  avant même de chercher. Elles n'existaient que dans le formulaire d'édition ;
	//  la création obligeait à taper un nom pour retrouver quelqu'un que le site
	//  connaissait déjà. Une seule écriture, donc les deux gestes en profitent — et
	//  c'est à la création qu'elles servent le plus.
	let suggestions: LocataireTrouve[] = [];
	let suggestionsChargees = false;
	let recherche = '';
	let trouve: LocataireTrouve | null = null;
	let resultats: LocataireTrouve[] = [];
	let cherchant = false;
	let rechercheFaite = false;
	/** La recherche lancée, si c'était une adresse : la seule qu'on connaisse en entier. */
	let adresseCherchee = '';

	$: associe = trouve !== null;

	onMount(async () => {
		//  Silencieux en cas d'échec : une suggestion absente n'empêche pas de
		//  chercher, et un message d'erreur pour une aide facultative serait du
		//  bruit sur un formulaire qu'on vient d'ouvrir.
		try {
			suggestions = await bailApi.locatairesSuggeres();
		} catch {
			suggestions = [];
		} finally {
			suggestionsChargees = true;
		}
	});

	function selectionner(l: LocataireTrouve, adresse = '') {
		trouve = l;
		locataireId = l.id;
		email = adresse;
		nom = l.nom;
		prenom = l.prenom;
		resultats = [];
	}

	function reinitialiser() {
		trouve = null;
		locataireId = null;
		resultats = [];
		rechercheFaite = false;
		recherche = '';
		email = '';
		nom = '';
		prenom = '';
	}

	async function chercher() {
		if (!recherche.trim()) return;
		cherchant = true;
		trouve = null;
		resultats = [];
		adresseCherchee = recherche.includes('@') ? recherche.trim() : '';
		try {
			const rs = await bailApi.searchLocataire(recherche.trim());
			rechercheFaite = true;
			//  Un seul résultat : on le retient. Faire cliquer sur l'unique ligne
			//  d'une liste d'un élément est un geste pour rien.
			if (rs.length === 1) selectionner(rs[0], adresseCherchee);
			else {
				resultats = rs;
				locataireId = null;
			}
		} catch {
			//  L'échec de la recherche n'empêche PAS de continuer : l'identité se
			//  saisit à la main. On le dit, on ne bloque pas.
			rechercheFaite = true;
			locataireId = null;
		} finally {
			cherchant = false;
		}
	}
</script>

<fieldset class="search-locataire-box">
	<!--  🔴 « (optionnel) » EST légitime ici, et c'est déclaré dans
	      `check-champs.mjs`. La règle « l'absence de `*` suffit » vaut pour un
	      CHAMP, qui peut porter un astérisque ; un GROUPE entier facultatif n'a
	      pas cette marque, et rien d'autre ne dirait qu'on peut le laisser vide.
	      L'arbitrage est écrit — ne pas le refaire à l'envers en passant. -->
	<legend>Associer un compte existant <span class="optional-hint">(optionnel)</span></legend>
	{#if trouve}
		<div class="locataire-selected">
			<div class="locataire-selected-info">
				<span class="locataire-selected-name">✓ {nomAffiche(trouve)}</span>
				<span class="locataire-selected-email">{trouve.email_masque}</span>
				{#if !trouve.actif}
					<span class="badge badge-yellow en-attente">En attente d'activation</span>
				{/if}
			</div>
			<button class="btn btn-xs btn-outline" on:click={reinitialiser} title="Changer de locataire"
				>✕ Changer</button
			>
		</div>
	{:else}
		{#if suggestionsChargees && suggestions.length > 0}
			<p class="suggestion-intro">Locataires ayant déclaré votre nom :</p>
			<ul class="locataire-resultats suggestion-liste">
				{#each suggestions as sug (sug.id)}
					<li>
						<button class="locataire-resultat-btn" on:click={() => selectionner(sug)}>
							<span class="lr-name">{nomAffiche(sug)}</span>
							<span class="lr-email">{sug.email_masque}</span>
							{#if !sug.actif}<span class="badge badge-yellow en-attente">En attente</span>{/if}
						</button>
					</li>
				{/each}
			</ul>
			<p class="suggestion-intro">Ou recherchez un autre compte :</p>
		{/if}
		<div class="search-locataire-row">
			<div class="field champ-en-ligne">
				<input
					type="search"
					id="{uid}-recherche"
					placeholder="Nom, prénom ou email…"
					bind:value={recherche}
					on:keydown={(e) => e.key === 'Enter' && chercher()}
					autocomplete="off"
				/>
			</div>
			<button class="btn btn-sm" disabled={cherchant || !recherche.trim()} on:click={chercher}>
				{cherchant ? '…' : '🔍 Chercher'}
			</button>
		</div>
		{#if rechercheFaite && resultats.length === 0 && !cherchant}
			<p class="search-no-result">Aucun compte trouvé — renseignez manuellement ci-dessous.</p>
		{:else if resultats.length > 1}
			<ul class="locataire-resultats">
				{#each resultats as r (r.id)}
					<li>
						<button
							class="locataire-resultat-btn"
							on:click={() => selectionner(r, adresseCherchee)}
						>
							<span class="lr-name">{nomAffiche(r)}</span>
							<span class="lr-email">{r.email_masque}</span>
							{#if !r.actif}<span class="badge badge-yellow en-attente">En attente</span>{/if}
						</button>
					</li>
				{/each}
			</ul>
		{/if}
	{/if}
</fieldset>

<style>
	.search-locataire-box {
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		padding: 0.75rem 0.85rem;
		background: var(--color-neutre-fond);
		margin: 0;
	}
	.optional-hint {
		font-weight: 400;
		color: var(--color-text-muted);
	}
	.search-locataire-box legend {
		font-size: var(--fs-md);
		font-weight: 600;
		padding: 0 0.3rem;
		color: var(--color-text);
	}
	.search-locataire-row {
		display: flex;
		gap: 0.5rem;
		margin-top: 0.4rem;
	}
	.search-locataire-row .field {
		flex: 1;
	}
	/*  Les deux intitulés des suggestions. Ils étaient en `style=` en ligne dans la
	    page : nommés ici, ils cessent d'être à réécrire à chaque reprise. */
	.suggestion-intro {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
		margin: 0.4rem 0 0.35rem;
	}
	.suggestion-liste {
		margin-bottom: 0.65rem;
	}
	.search-no-result {
		font-size: var(--fs-md);
		color: var(--color-danger);
		margin-top: 0.45rem;
	}
	.locataire-resultats {
		list-style: none;
		margin: 0.5rem 0 0;
		padding: 0;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		overflow: hidden;
	}
	.locataire-resultats li + li {
		border-top: 1px solid var(--color-border);
	}
	.locataire-resultat-btn {
		width: 100%;
		text-align: left;
		background: var(--color-bg);
		border: none;
		padding: 0.5rem 0.75rem;
		cursor: pointer;
		display: flex;
		align-items: center;
		gap: 0.75rem;
		flex-wrap: wrap;
		transition: background var(--duree-geste);
	}
	@media (hover: hover) and (pointer: fine) {
		.locataire-resultat-btn:hover {
			background: color-mix(in srgb, var(--color-primary) 6%, var(--color-bg));
		}
	}
	.lr-name {
		font-weight: 600;
		font-size: var(--fs-base);
	}
	.lr-email {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
	}
	.locataire-selected {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		flex-wrap: wrap;
		margin-top: 0.4rem;
		padding: 0.45rem 0.6rem;
		background: color-mix(in srgb, var(--color-success) 8%, var(--color-bg));
		border: 1px solid color-mix(in srgb, var(--color-success) 35%, transparent);
		border-radius: var(--radius);
	}
	.locataire-selected-info {
		display: flex;
		flex-direction: column;
		gap: 0.1rem;
	}
	.locataire-selected-name {
		font-weight: 600;
		font-size: var(--fs-base);
	}
	.locataire-selected-email {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
	}
	.en-attente {
		font-size: var(--fs-2xs);
	}
</style>
