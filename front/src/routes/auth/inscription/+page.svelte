<script lang="ts">
	import { onMount } from 'svelte';
	import { auth as authApi } from '#lib/api/index.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { essayer } from '#lib/chargement.ts';
	import ChargementPartiel from '#lib/components/ChargementPartiel.svelte';
	import { getSiteNom } from '#lib/stores/pageConfig.ts';
	import ChampMotDePasse from '#lib/components/ChampMotDePasse.svelte';
	import LibelleGroupe from '#lib/components/LibelleGroupe.svelte';
	import EtoileRequis from '#lib/components/EtoileRequis.svelte';
	import EnteteAuthentification from '#lib/components/EnteteAuthentification.svelte';

	import { SEPARATEUR } from '#lib/separateurs.ts';

	const _siteNom = getSiteNom();

	let nom = '';
	let prenom = '';
	let email = '';
	let telephone = '';
	let societe = '';
	let fonction = '';
	let password = '';
	let nom_proprietaire = '';
	let nom_aide = '';
	let prenom_aide = '';
	let statut = 'copropriétaire_résident';
	let batiment_id: number | null = null;
	/**  L'étage — FACULTATIF, et le formulaire le dit en toutes lettres.
	 *
	 *   ⚠️ Couplé au bâtiment, l'étage approche l'identification du logement.
	 *   Le laisser vide doit rester sans conséquence : c'est pourquoi il n'y a
	 *   ni `required`, ni astérisque, ni valeur par défaut. */
	let etage: number | null = null;
	let batiments: { id: number; numero: string }[] = [];
	let consentement_rgpd = false;
	let error = '';
	let success = false;
	let loading = false;

	const statuts = [
		{ value: 'copropriétaire_résident', label: 'Copropriétaire résident' },
		{ value: 'copropriétaire_bailleur', label: 'Copropriétaire bailleur' },
		{ value: 'locataire', label: 'Locataire' },
		{ value: 'syndic', label: 'Syndic' },
		{ value: 'mandataire', label: 'Mandataire' },
		{ value: 'aidant', label: 'Aidant (proche)' },
	];

	$: isProfessional = statut === 'syndic' || statut === 'mandataire';
	$: isAidant = statut === 'aidant';
	$: isAidantOrMandataire = statut === 'aidant' || statut === 'mandataire';
	$: isLocataire = statut === 'locataire';
	$: showBatiment = batiments.length > 0 && !isProfessional && !isAidant;

	//  🔴 Un échec taisait le champ Bâtiment, et le compte naissait sans (#1459).
	let erreurBatiments = '';
	onMount(async () => {
		[batiments, erreurBatiments] = await essayer(authApi.batiments(), []);
	});

	async function submit() {
		if (!consentement_rgpd) {
			error = 'Vous devez accepter la politique de confidentialité pour continuer.';
			return;
		}
		error = '';
		loading = true;
		email = email.trim().toLowerCase();
		try {
			await authApi.register({
				nom,
				prenom,
				email,
				telephone,
				societe: societe || null,
				fonction: fonction || null,
				password,
				statut,
				batiment_id: showBatiment ? batiment_id : null,
				//  `null` et non `undefined` quand le champ est vide : le serveur
				//  distingue « pas renseigné » de « absent du corps », et c'est la
				//  même convention que `batiment_id` juste au-dessus.
				etage: showBatiment && etage !== null ? etage : null,
				consentement_rgpd,
				nom_proprietaire: isLocataire ? nom_proprietaire : null,
				nom_aide: isAidantOrMandataire ? nom_aide : null,
				prenom_aide: isAidantOrMandataire ? prenom_aide : null,
			});
			success = true;
		} catch (e) {
			error = messageErreur(e, 'Erreur lors de la création du compte');
		} finally {
			loading = false;
		}
	}
</script>

<svelte:head><title>Créer un compte — {_siteNom}</title></svelte:head>

<div class="auth-page">
	<div class="auth-card card">
		<EnteteAuthentification sousTitre="Créer un compte" />

		{#if success}
			<div class="alert alert-success">
				<strong>Demande envoyée !</strong><br />
				Un e-mail de vérification vous a été envoyé à <strong>{email}</strong>.<br />
				Cliquez sur le lien dans l'e-mail pour confirmer votre adresse (valable 24h).<br /><br />
				Après vérification, votre compte sera soumis à validation par le conseil syndical.
			</div>
			<div class="btn-wrapper">
				<a href="/auth/connexion" class="btn btn-outline">Retour à la connexion</a>
			</div>
		{:else}
			{#if error}
				<div class="alert alert-error">{error}</div>
			{/if}

			<ChargementPartiel
				erreur={erreurBatiments}
				consequence="Le choix du bâtiment manque : rechargez la page avant de créer le compte."
			/>
			<form on:submit|preventDefault={submit}>
				<div class="field-row">
					<div class="field">
						<label for="prenom">Prénom<EtoileRequis vide={!prenom} /></label>
						<input id="prenom" type="text" bind:value={prenom} required />
					</div>
					<div class="field">
						<label for="nom">NOM<EtoileRequis vide={!nom} /></label>
						<input
							id="nom"
							type="text"
							bind:value={nom}
							required
							class="en-capitales"
							on:input={() => (nom = nom.toUpperCase())}
						/>
					</div>
				</div>

				<div class="field">
					<label for="email">Email<EtoileRequis vide={!email} /></label>
					<input id="email" type="email" bind:value={email} required autocomplete="email" />
				</div>

				<div class="field">
					<label for="telephone">Téléphone</label>
					<input id="telephone" type="tel" bind:value={telephone} />
				</div>

				<div class="field">
					<label for="statut">Profil d'utilisateur<EtoileRequis vide={!statut} /></label>
					<select id="statut" bind:value={statut} required>
						{#each statuts as s (s.value)}
							<option value={s.value}>{s.label}</option>
						{/each}
					</select>
				</div>

				{#if isProfessional}
					<div class="field">
						<label for="societe">Société<EtoileRequis vide={!societe} /></label>
						<input
							id="societe"
							type="text"
							bind:value={societe}
							required
							placeholder="Cabinet de gestion, agence…"
						/>
					</div>
					<div class="field">
						<label for="fonction">Fonction<EtoileRequis vide={!fonction} /></label>
						<input
							id="fonction"
							type="text"
							bind:value={fonction}
							required
							placeholder="Gestionnaire, Mandataire…"
						/>
					</div>
				{/if}

				{#if isLocataire}
					<div class="field">
						<label for="nom-proprietaire"
							>Nom du propriétaire<EtoileRequis vide={!nom_proprietaire} /></label
						>
						<input
							id="nom-proprietaire"
							type="text"
							bind:value={nom_proprietaire}
							required
							placeholder="Nom du propriétaire bailleur"
						/>
						<p class="aide">Permet au conseil syndical de rattacher votre compte au bon lot.</p>
					</div>
				{/if}

				{#if isAidantOrMandataire}
					<!--  ⚠️ `.grille-champs` enveloppe, et la grille est `:global()` IMBRIQUÉ.
					      La classe passée en prop `classe=` est appliquée par `LibelleGroupe`
					      sur SON balisage : elle y prend le scope de `LibelleGroupe`, jamais
					      celui d'ici. `.field-row` écrit à plat ne l'atteignait pas — les deux
					      champs s'empilaient au lieu de se ranger côte à côte, et ce depuis
					      toujours (trouvé le 01/09/2026 en extrayant `FormulaireBail`). -->
					<div class="grille-champs">
						<LibelleGroupe
							titre="Copropriétaire aidé"
							requis
							vide={!prenom_aide.trim() || !nom_aide.trim()}
							id="coproprietaire-aide"
							classe="field-row"
						>
							<div class="field">
								<input
									id="prenom-aide"
									type="text"
									bind:value={prenom_aide}
									required
									placeholder="Prénom"
								/>
							</div>
							<div class="field">
								<input
									id="nom-aide"
									type="text"
									bind:value={nom_aide}
									required
									placeholder="NOM"
									class="en-capitales"
									on:input={() => (nom_aide = nom_aide.toUpperCase())}
								/>
							</div>
						</LibelleGroupe>
					</div>
					<p class="aide">
						Permet au conseil syndical de rattacher votre compte au bon copropriétaire.
					</p>
				{/if}

				{#if showBatiment}
					<div class="field">
						<label for="batiment">Bâtiment<EtoileRequis vide={!batiment_id} /></label>
						<select id="batiment" bind:value={batiment_id} required>
							<option value={null}>-- Sélectionnez votre bâtiment --</option>
							{#each batiments as b (b.id)}
								<option value={b.id}>Bâtiment {b.numero}</option>
							{/each}
						</select>
					</div>

					<!--  🔴 Pas d'astérisque, pas de `required` : l'absence de ` *` SUFFIT à
					      dire qu'un champ est facultatif (`ux-patterns` §9), et écrire
					      « (optionnel) » ajouterait un second vocabulaire pour la même
					      information — `lint:champs` le refuse.

					      ⚠️ L'indication dit à quoi il SERT. Un champ facultatif dont on
					      ignore l'usage ne se remplit pas, et celui-ci sert une chose
					      précise : situer la personne dans l'annonce de bienvenue. Le taire
					      reviendrait à demander une donnée sans dire pourquoi.

					      🔴 Elle dit AUSSI la CONVENTION de saisie, depuis le 09/09/2026 :
					      rien n'annonçait que `0` vaut rez-de-chaussée , et l'exemple en
					      montre la forme — c'est la seule chose qu'un champ « Étage » ne dit pas
					      tout seul, et un compte de test l'a saisi sans savoir ce qu'il
					      déclarait. Le mot « Facultatif » qui ouvrait la phrase, lui, a
					      disparu : l'absence d'astérisque l'énonce déjà (`ux-patterns` §9).
					      Le même texte est sous le champ du profil (`ChampsEtage`). -->
					<div class="field">
						<label for="etage">Étage</label>
						<input
							id="etage"
							type="number"
							bind:value={etage}
							min="-2"
							max="50"
							placeholder="Ex. 3"
						/>
						<p class="aide">
							0 = rez-de-chaussée, 2 = 2ème étage. Sert à vous situer auprès de vos voisins dans
							l’annonce de bienvenue publiée à votre arrivée ; votre e-mail et votre téléphone n’y
							figurent jamais.
						</p>
					</div>
				{/if}

				<ChampMotDePasse
					id="password"
					libelle="Mot de passe"
					bind:valeur={password}
					autocomplete="new-password"
					longueurMini={8}
					robustesse
				/>

				<div class="rgpd-box">
					<p class="rgpd-info">
						<strong>Responsable du traitement :</strong> l’administrateur de {_siteNom} (CS de la copropriété).<br
						/>
						<strong>Finalité :</strong> Gestion de la copropriété (Art. 6.1.b RGPD).<br />
						<strong>Conservation :</strong> Durée de résidence + 3 ans.<br />
						<a href="/politique-de-confidentialite" target="_blank" rel="noopener"
							>Voir la politique complète</a
						>{SEPARATEUR.point}<a href="/mentions-legales" target="_blank" rel="noopener"
							>Mentions légales</a
						>
					</p>

					<label class="checkbox-field">
						<input type="checkbox" bind:checked={consentement_rgpd} required />
						J'ai lu et j'accepte la
						<a
							href="/politique-de-confidentialite"
							target="_blank"
							rel="noopener"
							on:click|stopPropagation>politique de confidentialité</a
						>*
					</label>

					<!--  🔴 La case « J'accepte de recevoir les notifications par e-mail »
					      a été RETIRÉE le 10/09/2026 (#873, arbitrage de Philippe).

					      Elle était écrite en base et lue nulle part : quelqu'un qui la
					      laissait décochée recevait quand même tous les e-mails de son
					      bâtiment. On lui demandait son accord, il le refusait, et rien
					      ne changeait — et il ne pouvait pas non plus le retirer, ce qui
					      est un défaut de conformité (RGPD art. 7.3).

					      Le consentement se donne et se retire désormais au SEUL endroit
					      où il s'exerce : Profil → Notifications. Une seule notion, un
					      seul geste. Ne pas remettre de case ici sans brancher ce
					      qu'elle promet. -->
				</div>

				<div class="btn-wrapper">
					<button class="btn btn-primary" type="submit" disabled={loading}>
						{loading ? 'Création…' : 'Créer mon compte'}
					</button>
				</div>
			</form>

			<div class="auth-links">
				Déjà un compte ? <a href="/auth/connexion">Se connecter</a>
			</div>
		{/if}
	</div>
</div>

<style>
	/*  Le formulaire d'inscription est LONG : il s'aligne en haut au lieu d'etre
	    centre, respire davantage, et sa carte est plus large que les 400 px de la
	    charte. Variations assumees ; le reste vient de `composants.css` (#607). */
	.auth-page {
		align-items: flex-start;
		padding: 2rem 1rem;
	}
	.auth-card {
		max-width: 480px;
	}

	/*  L'en-tête — et le logo réduit de #607 — sont partis dans
	    `EnteteAuthentification` (#2357, 30/10/2026) : la page ressemble à la connexion. */

	.grille-champs :global(.field-row) {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.75rem;
	}

	.rgpd-box {
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		padding: 0.75rem;
		margin-bottom: 1rem;
	}

	.rgpd-info {
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
		margin-bottom: 0.5rem;
		line-height: 1.5;
	}

	/*  Seule divergence conservée, avec son motif : le libellé des conditions
	    tient sur plusieurs lignes, et la case doit s'aligner sur la PREMIÈRE,
	    pas se centrer sur le bloc. Le reste vient de la charte. */
	.checkbox-field {
		align-items: flex-start;
	}

	.auth-links {
		text-align: center;
		margin-top: 1rem;
		font-size: var(--fs-base);
		color: var(--color-text-muted);
	}

	/*  Seule la marge basse est propre à cet écran : le pied du formulaire est
	    suivi des liens « déjà un compte ? », qui ont besoin d'un peu d'air. Le
	    reste vient de la charte depuis le 09/09/2026. */
	.btn-wrapper {
		margin-bottom: 0.25rem;
	}
	.btn-wrapper .btn {
		padding-left: 2.5rem;
		padding-right: 2.5rem;
	}
	.en-capitales {
		text-transform: uppercase;
	}
</style>
