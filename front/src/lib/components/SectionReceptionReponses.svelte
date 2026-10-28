<!--
  SectionReceptionReponses.svelte — la relève de la boîte, dans l'écran SMTP.

  Sortie d'`OngletSmtp.svelte` le 05/09/2026, sur refus du contrôle de
  modularité : ajouter la seconde adresse d'expédition (`contact@`) faisait
  passer l'écran de 500 à 521 lignes. Le découpage n'est pas qu'arithmétique —
  **envoyer** et **relever** sont deux sens de circulation, avec deux
  connexions, deux mots de passe et deux boutons de test.

  Ce qui les lie reste vrai, et c'est pourquoi les deux vivent dans le même
  onglet : c'est la MÊME boîte, chez le même hébergeur, avec les mêmes
  identifiants. D'où le bouton « Reprendre les paramètres d'envoi », qui reçoit
  ici en propriétés ce qu'il recopiait dans l'état voisin.

  🔴 CET ÉCRAN MANQUAIT AVANT LE 03/09/2026, et son absence rendait la fonction
  inexistante : la v3.73.0 a livré la relève, les clés `imap_*` et la tâche
  planifiée, mais AUCUN endroit pour les renseigner — *« IMAP : je ne vois pas
  quoi faire »*.
-->
<script lang="ts">
	import { messageErreur } from '#lib/erreurs.ts';
	import ChampSecret from '#lib/components/ChampSecret.svelte';
	import { createEventDispatcher, onMount } from 'svelte';
	import SectionFormulaire from '#lib/components/SectionFormulaire.svelte';
	import { config as configApi } from '#lib/api/index.ts';
	import EtatListe from '#lib/components/EtatListe.svelte';
	import { essayer, TITRE_PARAMETRAGE_ILLISIBLE } from '#lib/chargement.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import EtatService from '#lib/components/EtatService.svelte';

	/** Le serveur d'envoi, pour le bouton « Reprendre les paramètres d'envoi ». */
	export let serveurSmtp = '';
	/** L'identifiant d'envoi, même usage. */
	export let identifiantSmtp = '';

	//  L'écran parent relit la configuration après un enregistrement : les deux
	//  moitiés partagent la même table de clés, et une valeur enregistrée ici
	//  peut changer ce qu'il affiche.
	const dispatch = createEventDispatcher<{ enregistre: void }>();

	//  ── Réception des réponses (IMAP) — #703 ────────────────────────────────
	//
	//  🔴 CET ÉCRAN MANQUAIT, et son absence rendait la fonction inexistante :
	//  la v3.73.0 a livré la relève, les clés `imap_*` et la tâche planifiée,
	//  mais AUCUN endroit pour les renseigner. Un réglage qu'on ne peut pas
	//  atteindre n'est pas un réglage — signalé à l'écran le 03/09/2026 :
	//  *« IMAP : je ne vois pas quoi faire »*.
	//
	//  Il vit dans l'onglet SMTP parce que c'est la MÊME boîte, chez le même
	//  hébergeur, avec les mêmes identifiants : les séparer aurait obligé à
	//  saisir deux fois ce qui ne fait qu'un.
	let imapConfig = {
		enabled: false,
		server: '',
		port: 993,
		username: '',
		password: '',
		dossier: 'INBOX',
		plancher: '2026-09-02',
		//  Combien de messages l'onglet Espace CS › Courriels en montre (20 par défaut).
		affiches: 20 as number | null,
	};
	let imapSaving = false;
	let imapPasswordSet = false;
	let imapTesting = false;
	let imapResultat = '';

	function reprendreDuSmtp() {
		imapConfig.server = serveurSmtp.replace(/^smtp\./, 'ssl0.').trim();
		imapConfig.username = identifiantSmtp;
		//  🔴 « Copié » et non « repris — le mot de passe reste à saisir » : la
		//  première rédaction annonçait ce qui MANQUAIT, sur un ton indiscernable
		//  d'une erreur. Elle est apparue à quelqu'un qui venait justement de
		//  saisir son mot de passe, et a été lue comme un échec (03/09/2026).
		//  Un message de confirmation dit ce qui a été FAIT ; ce qui reste à faire
		//  est déjà écrit sous les champs concernés.
		toast('success', 'Serveur et identifiant copiés depuis la configuration d’envoi.');
	}

	async function saveImapConfig() {
		imapSaving = true;
		try {
			//  L'activation n'y est pas : elle se coche dans Admin › Services, seule
			//  case qui l'écrit — la renvoyer rétablirait un service qu'on vient de couper.
			const payload: Record<string, string> = {
				imap_server: imapConfig.server.trim(),
				imap_port: String(imapConfig.port),
				imap_username: imapConfig.username.trim(),
				imap_dossier: imapConfig.dossier.trim() || 'INBOX',
				imap_plancher: imapConfig.plancher,
				//  Vide = la valeur par défaut du serveur, jamais « null » écrit en base.
				courriels_affiches: imapConfig.affiches == null ? '' : String(imapConfig.affiches),
			};
			//  Le mot de passe n'est envoyé QUE s'il a été saisi : l'API renvoie un
			//  marqueur à sa place, et le réexpédier l'écraserait par des points.
			if (imapConfig.password) payload['imap_password'] = imapConfig.password;
			await configApi.save(payload);
			imapConfig.password = '';
			await relire();
			dispatch('enregistre');
			toast('success', 'Réception des réponses enregistrée.');
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			imapSaving = false;
		}
	}

	async function testerImap() {
		imapTesting = true;
		imapResultat = '';
		try {
			const r = await configApi.testerImap();
			imapResultat = r.message;
			toast('success', 'Connexion à la boîte réussie.');
		} catch (e) {
			imapResultat = messageErreur(e);
			toast('error', imapResultat);
		} finally {
			imapTesting = false;
		}
	}

	/**
	 * Ce que la lecture a rapporté d'un échec. Sans elle, la section restait un
	 * formulaire de valeurs PAR DÉFAUT avec son « Enregistrer » actif — de quoi
	 * écraser la configuration réelle —, et l'échec partait en exception non
	 * rattrapée (#1475).
	 */
	let erreurLecture = '';

	async function relire() {
		const [lues, erreur] = await essayer(configApi.admin(), null);
		erreurLecture = erreur;
		if (!lues) return;
		imapConfig.enabled = lues['imap_enabled'] === '1';
		imapConfig.server = lues['imap_server'] ?? '';
		imapConfig.port = parseInt(lues['imap_port'] ?? '993') || 993;
		imapConfig.username = lues['imap_username'] ?? '';
		imapConfig.dossier = lues['imap_dossier'] || 'INBOX';
		imapConfig.plancher = lues['imap_plancher'] || '2026-09-02';
		imapConfig.affiches = parseInt(lues['courriels_affiches'] ?? '') || 20;
		imapPasswordSet = !!lues['imap_password'];
	}

	onMount(relire);
</script>

<SectionFormulaire icone="message-square-text" titre="Réception des réponses aux affaires">
	{#if erreurLecture}
		<EtatListe erreur={erreurLecture} titreErreur={TITRE_PARAMETRAGE_ILLISIBLE} />
	{:else}
		<div class="largeur-saisie">
			<p class="aide intro-reception">
				Quand le syndic répond à un e-mail d'affaire, sa réponse arrive dans la boîte d'envoi et
				personne ne la voit. Activée, cette relève la dépose dans le fil de l'affaire concernée,
				toutes les 10 minutes.
			</p>
		</div>
		<div class="largeur-saisie">
			<EtatService actif={imapConfig.enabled}>
				Coupé, rien n'est relevé — vous pouvez régler et tester sans conséquence.
			</EtatService>
		</div>
		<div class="form-grid largeur-saisie">
			<label class="field">
				Serveur IMAP
				<input type="text" bind:value={imapConfig.server} placeholder="ssl0.ovh.net" />
			</label>
			<label class="field champ-court">
				Port
				<input type="number" bind:value={imapConfig.port} min="1" max="65535" placeholder="993" />
			</label>
			<label class="field">
				Nom d'utilisateur
				<input type="text" bind:value={imapConfig.username} placeholder="noreply@exemple.fr" />
				<span class="aide">Le même compte que l'envoi, chez le même hébergeur.</span>
			</label>
			<!--  Le motif du secret déjà posé vit dans `ChampSecret` (11/09/2026) : il
		      était écrit ICI et dans `OngletSmtp`, à l'identique, et la clé d'API de
		      l'assistant en aurait fait une troisième copie. -->
			<ChampSecret
				libelle="Mot de passe"
				bind:valeur={imapConfig.password}
				pose={imapPasswordSet}
				placeholder="Mot de passe de la boîte"
				aide="Requis pour relever les réponses."
			/>
			<label class="field champ-court">
				Dossier
				<input type="text" bind:value={imapConfig.dossier} placeholder="INBOX" />
			</label>
			<label class="field champ-court">
				Ne rien relever avant le
				<input type="date" bind:value={imapConfig.plancher} />
				<span class="aide"> Évite de rejouer d'anciens messages à la première relève. </span>
			</label>
			<label class="field champ-court">
				Messages affichés dans Espace CS › Courriels
				<input type="number" bind:value={imapConfig.affiches} min="1" max="100" placeholder="20" />
				<span class="aide">Les plus récents ; de 1 à 100.</span>
			</label>
		</div>
		<div class="largeur-saisie form-actions">
			<button class="btn btn-outline btn-sm" type="button" on:click={reprendreDuSmtp}>
				Reprendre les paramètres d'envoi
			</button>
			<button class="btn btn-primary" on:click={saveImapConfig} disabled={imapSaving}>
				{imapSaving ? 'Enregistrement…' : 'Enregistrer'}
			</button>
		</div>
		<div class="largeur-saisie bloc-test">
			<button class="btn btn-outline" on:click={testerImap} disabled={imapTesting}>
				{imapTesting ? 'Connexion…' : '📥 Tester la connexion'}
			</button>
			{#if imapResultat}
				<p class="imap-resultat">{imapResultat}</p>
			{/if}
			<p class="aide note-test">
				Se connecte avec ce qui est <strong>enregistré</strong>, compte les messages non lus, et ne
				traite rien. Enregistrez d'abord.
			</p>
		</div>
	{/if}
</SectionFormulaire>

<style>
	.imap-resultat {
		margin: 0.6rem 0 0;
		padding: 0.55rem 0.7rem;
		background: var(--color-bg);
		border-left: 3px solid var(--color-primary);
		border-radius: 0 var(--radius) var(--radius) 0;
		font-size: var(--fs-md);
		white-space: pre-wrap;
	}
	.intro-reception {
		margin-bottom: 0.75rem;
	}
	.bloc-test {
		margin-top: 0.75rem;
	}
	.note-test {
		margin-top: 0.3rem;
	}
</style>
