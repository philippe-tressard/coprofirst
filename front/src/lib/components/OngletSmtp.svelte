<!--
  L'onglet **SMTP** de l'administration : serveur d'envoi, test, signature des
  e-mails, référence copropriété.

  POURQUOI CE COMPOSANT (19/08/2026). `admin/+page.svelte` dépassait 1 950 lignes,
  et le garde-fou de modularité (rang 1) a refusé les huit lignes qu'ajoutait la
  mise au motif `SectionFormulaire` de ses sous-sections. La règle est « on
  découpe QUAND on y touche » — et #453 dit ce qui se passe quand on y répond en
  tassant des attributs au lieu de découper : le garde-fou devient une formalité.

  Même geste et même forme qu'`OngletWhatsApp.svelte`, extrait avant lui : l'état
  et les appels réseau vivent ici, la page ne garde que le choix de l'onglet.

  ⚠️ `email_footer` et `reference_copro` appartiennent à `siteConfig`, pas à la
  configuration SMTP — ils sont pourtant enregistrés par le même bouton, parce
  qu'ils ne concernent que les e-mails. Ils sont donc passés en `bind:`, et c'est
  la page qui reste propriétaire de `siteConfig`.
-->
<script lang="ts">
	import EncartDemo from '#lib/components/EncartDemo.svelte';
	import { messageErreur } from '#lib/erreurs.ts';
	import Icon from '#lib/components/Icon.svelte';
	import { config as configApi } from '#lib/api/index.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import SectionFormulaire from '#lib/components/SectionFormulaire.svelte';
	import SectionReceptionReponses from '#lib/components/SectionReceptionReponses.svelte';
	import ChampSecret from '#lib/components/ChampSecret.svelte';
	import { SEPARATEUR } from '#lib/separateurs.ts';

	/** Signature ajoutée en bas de chaque e-mail — appartient à `siteConfig`. */
	export let emailFooter = '';
	/** Valeurs lues au chargement par la page (`adminCfg`). */
	export let valeurs: Record<string, string> = {};

	let smtpConfig = {
		enabled: false,
		server: '',
		port: 587,
		from: '',
		from_reponse: '',
		from_affaires: '',
		from_name: '',
		username: '',
		password: '',
		starttls: true,
		ssl_tls: false,
	};
	let smtpSaving = false;
	let smtpPasswordSet = false;
	let smtpTestEmail = '';
	let smtpTesting = false;

	//  🔴 HYDRATER UNE SEULE FOIS, PUIS RELIRE — correctif du 03/09/2026.
	//
	//  Les valeurs arrivent APRÈS le montage : ce `$:` les reprend dès qu'elles
	//  changent, là où une affectation au montage figerait des champs vides.
	//
	//  Mais il RÉÉCRIVAIT le formulaire à chaque ré-exécution, avec le `valeurs`
	//  du montage. Signalé à l'écran : *« quand je fais enregistrer ça efface les
	//  champs Nom et password »* — la saisie partait bien vers le serveur, puis
	//  l'écran la remplaçait par ce qu'il avait lu au chargement, c'est-à-dire
	//  rien. On voyait un formulaire vidé, et on en concluait un échec.
	//
	//  Deux gestes, et il faut les deux :
	//    • cette garde — un formulaire ne s'hydrate qu'une fois, à l'arrivée des
	//      données, jamais par-dessus une saisie en cours ;
	//    • `relire()` après chaque enregistrement — sinon la garde figerait
	//      l'écran sur l'état du montage, et le prochain aller-retour entre
	//      onglets réafficherait des champs vides sur une base renseignée.
	let hydrate = false;
	$: if (!hydrate && valeurs && Object.keys(valeurs).length) {
		hydrate = true;
		hydrater(valeurs);
	}

	function hydrater(lues: Record<string, string>) {
		smtpConfig.enabled = lues['smtp_enabled'] === '1';
		smtpConfig.server = lues['smtp_server'] ?? '';
		smtpConfig.port = parseInt(lues['smtp_port'] ?? '587') || 587;
		smtpConfig.from = lues['smtp_from'] ?? '';
		smtpConfig.from_reponse = lues['smtp_from_reponse'] ?? '';
		smtpConfig.from_affaires = lues['smtp_from_affaires'] ?? '';
		smtpConfig.from_name = lues['smtp_from_name'] ?? '';
		smtpConfig.username = lues['smtp_username'] ?? '';
		smtpConfig.starttls = lues['smtp_starttls'] !== '0';
		smtpConfig.ssl_tls = lues['smtp_ssl_tls'] === '1';
		smtpPasswordSet = !!lues['smtp_password'];
	}

	/** Relit ce que le serveur a RETENU, et remet le formulaire dessus.
	 *
	 * 🔴 Relire plutôt que recopier ce qu'on vient d'envoyer : c'est la seule
	 * façon de montrer l'état réel. Une clé refusée, tronquée ou normalisée
	 * côté serveur se verrait ici — alors qu'un `{ ...valeurs, ...payload }`
	 * afficherait la saisie en la faisant passer pour un enregistrement.
	 *
	 * ⚠️ Et c'est ce qui rend l'aller-retour entre onglets juste : le composant
	 * est détruit puis recréé, donc réhydraté depuis `valeurs` — qui date du
	 * montage de la PAGE. Sans cette relecture, les champs reparaîtraient vides
	 * après un changement d'onglet, alors que la base est renseignée.
	 */
	async function relire() {
		try {
			valeurs = await configApi.admin();
			hydrater(valeurs);
		} catch {
			//  Muet à dessein : l'enregistrement a réussi, seul l'affichage est en
			//  retard. Un second message d'erreur ferait douter d'un succès réel.
		}
	}

	/** Reprend les paramètres d'envoi : même compte, même hébergeur. */

	async function saveSmtpConfig() {
		smtpSaving = true;
		try {
			const payload: Record<string, string> = {
				smtp_enabled: smtpConfig.enabled ? '1' : '0',
				smtp_server: smtpConfig.server,
				smtp_port: String(smtpConfig.port),
				smtp_from: smtpConfig.from,
				smtp_from_reponse: smtpConfig.from_reponse,
				smtp_from_affaires: smtpConfig.from_affaires,
				smtp_from_name: smtpConfig.from_name,
				smtp_username: smtpConfig.username,
				smtp_starttls: smtpConfig.starttls ? '1' : '0',
				smtp_ssl_tls: smtpConfig.ssl_tls ? '1' : '0',
				email_footer: emailFooter,
			};
			if (smtpConfig.password) payload['smtp_password'] = smtpConfig.password;
			await configApi.save(payload);
			smtpConfig.password = '';
			await relire();
			toast('success', 'Configuration SMTP enregistrée.');
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			smtpSaving = false;
		}
	}

	async function sendSmtpTest() {
		if (!smtpTestEmail) return;
		smtpTesting = true;
		try {
			//  Le serveur dit CE QU'IL A FAIT — un envoi par adresse d'expédition
			//  configurée. Réécrire le message ici le figerait à un seul envoi, et
			//  l'écran annoncerait autre chose que ce qui est parti.
			const r = await configApi.testerSmtp(smtpTestEmail);
			toast('success', r?.message ?? `E-mail de test envoyé à ${smtpTestEmail}`);
		} catch (e) {
			toast('error', messageErreur(e, "Échec de l'envoi"));
		} finally {
			smtpTesting = false;
		}
	}
</script>

<EncartDemo />
<section class="card config-section">
	<h2 class="config-section-title">
		<Icon name="message-square-text" size={17} />Configuration SMTP (notifications e-mail)
	</h2>
	<SectionFormulaire premiere icone="settings" titre="Serveur d’envoi">
		<div class="form-grid largeur-saisie">
			<label class="field champ-double">
				<span class="case">
					<input type="checkbox" bind:checked={smtpConfig.enabled} />
					Activer l'envoi d'e-mails
				</span>
				<span class="aide"
					>Si activé, les notifications (réinitialisation de mot de passe, etc.) seront envoyées par
					e-mail.</span
				>
			</label>
			<label class="field">
				Serveur SMTP
				<input type="text" bind:value={smtpConfig.server} placeholder="smtp.example.com" />
			</label>
			<label class="field champ-court">
				Port
				<input type="number" bind:value={smtpConfig.port} min="1" max="65535" placeholder="587" />
			</label>
			<label class="field">
				Adresse expéditeur{SEPARATEUR.tiret}messages SANS réponse attendue
				<input type="email" bind:value={smtpConfig.from} placeholder="noreply@example.com" />
				<span class="aide"
					>Employée pour ce qui informe seulement : compte activé, changement d'état, nouveau
					document. C'est la seule adresse qui peut s'appeler « noreply ».</span
				>
			</label>
			<label class="field">
				Adresse expéditeur{SEPARATEUR.tiret}messages qui APPELLENT une réponse
				<input
					type="email"
					bind:value={smtpConfig.from_reponse}
					placeholder="contact@example.com"
				/>
				<span class="aide"
					>Employée dès qu'on attend quelque chose du destinataire : affaire au syndic, relance,
					demande d'accès, annonce de hall. Une adresse qui s'annonce « ne répondez pas » décourage
					la réponse qu'on sollicite. <strong>Vide</strong> : tout part de l'adresse ci-dessus, comme
					avant.</span
				>
			</label>
			<label class="field">
				Adresse des affaires{SEPARATEUR.tiret}expédition ET réponses
				<input
					type="email"
					bind:value={smtpConfig.from_affaires}
					placeholder="affaire@example.com"
				/>
				<span class="aide"
					>Un courriel d'affaire (au syndic, au conseil) part de cette adresse, et la réponse y
					revient : elle se rattache à l'affaire par son numéro « Affaire #TK-… » dans l'objet. La
					boîte qui la reçoit doit être celle de la <strong>Réception des réponses</strong>
					ci-dessous (un alias qui y aboutit convient). <strong>Vide</strong> : l'adresse des messages
					qui appellent une réponse.</span
				>
			</label>
			<label class="field">
				Nom expéditeur
				<input type="text" bind:value={smtpConfig.from_name} placeholder="Résidence du Parc" />
			</label>
			<label class="field">
				Nom d'utilisateur SMTP
				<input type="text" bind:value={smtpConfig.username} placeholder="user@example.com" />
				<span class="aide">Laisser vide si le serveur ne requiert pas d'authentification.</span>
			</label>
			<!--  Le motif du secret déjà posé vit dans `ChampSecret` (11/09/2026) : il
			      était écrit ICI et dans `SectionReceptionReponses`, à l'identique — et
			      seule cette copie-ci portait l'aide « déjà enregistré », l'autre non.
			      Deux écritures d'un même motif, et elles avaient déjà divergé. -->
			<ChampSecret
				libelle="Mot de passe SMTP"
				bind:valeur={smtpConfig.password}
				pose={smtpPasswordSet}
				placeholder="Nouveau mot de passe SMTP"
				aide="Requis si le serveur exige une authentification."
			/>
			<label class="field champ-double chiffrement">
				<span>
					<span>
						<input type="checkbox" bind:checked={smtpConfig.starttls} class="case-chiffrement" />
						STARTTLS (port 587)
					</span>
					<span>
						<input type="checkbox" bind:checked={smtpConfig.ssl_tls} class="case-chiffrement" />
						SSL/TLS (port 465)
					</span>
				</span>
				<span class="aide"
					>STARTTLS et SSL/TLS sont mutuellement exclusifs. Décocher les deux pour connexion non
					chiffrée.</span
				>
			</label>
		</div>
		<div class="largeur-saisie form-actions">
			<button class="btn btn-primary" on:click={saveSmtpConfig} disabled={smtpSaving}>
				{smtpSaving ? 'Enregistrement…' : 'Enregistrer'}
			</button>
		</div>
	</SectionFormulaire>

	<SectionFormulaire icone="activity" titre="Tester la configuration">
		<div class="largeur-saisie">
			<div class="ligne-test">
				<div class="field champ-en-ligne champ-essai">
					<input type="email" bind:value={smtpTestEmail} placeholder="destinataire@example.com" />
				</div>
				<button
					class="btn btn-outline"
					on:click={sendSmtpTest}
					disabled={smtpTesting || !smtpTestEmail}
				>
					{smtpTesting ? 'Envoi...' : '📨 Envoyer un e-mail de test'}
				</button>
			</div>
			<p class="note-essai">
				Envoie un e-mail de test avec la configuration SMTP actuellement enregistrée en base,
				<strong>depuis chacune des deux adresses d'expédition</strong>{SEPARATEUR.tiret}celle qui
				n'attend pas de réponse et celle qui en attend une. Un serveur peut accepter l'une et
				refuser l'autre, surtout si la seconde est un <strong>alias</strong> : il faut recevoir les deux
				messages.
			</p>
		</div>
	</SectionFormulaire>

	<!--  🔴 RÉCEPTION DES RÉPONSES (#703). Placée APRÈS l'envoi et son test, parce
	      qu'elle en dépend : sans envoi, aucune réponse à recevoir. -->
	<SectionReceptionReponses
		serveurSmtp={smtpConfig.server}
		identifiantSmtp={smtpConfig.username || smtpConfig.from}
		on:enregistre={relire}
	/>

	<!--  Ce que la relève a fait de chaque message, et pourquoi (#1447) : depuis le
	      05/10/2026 le journal se lit dans Espace CS › Courriels, où le conseil qui
	      transfère les messages le voit — il était réservé à cet écran-ci. -->
	<SectionFormulaire icone="clipboard-list" titre="Messages relevés">
		<p class="aide largeur-saisie">
			Ce que la relève a fait de chaque message{SEPARATEUR.tiret}ajouté à une affaire, refusé ou
			ignoré, et pourquoi{SEPARATEUR.tiret}se lit dans
			<a href="/espace-cs/courriels">Espace CS › Courriels</a>. Le nombre de messages affichés se
			règle ci-dessus.
		</p>
	</SectionFormulaire>

	<SectionFormulaire icone="message-square-text" titre="Signature des e-mails">
		<div class="largeur-saisie">
			<label class="field">
				<textarea
					bind:value={emailFooter}
					rows="2"
					placeholder="— Le conseil syndical de la résidence"
					class="saisie-gabarit"></textarea>
				<span class="aide"
					>Texte ajouté automatiquement en bas de chaque e-mail envoyé par la plateforme.</span
				>
			</label>
		</div>
	</SectionFormulaire>

	<!--  🔴 « Référence copropriété » a REJOINT la fiche copropriété, section
	      Syndic (11/09/2026, signalé à l'écran). Elle décrit le dossier de la
	      copropriété chez son syndic — sa place est auprès du cabinet, du mandat
	      et de l'interlocuteur, pas dans un écran de serveur d'envoi.

	      L'en-tête de ce fichier justifiait sa présence ici par « elle ne concerne
	      que les e-mails ». C'était vrai de son USAGE et faux de sa NATURE : une
	      donnée se range là où elle se lit, pas là où elle sert. -->

	<div class="largeur-saisie form-actions">
		<button class="btn btn-primary" on:click={saveSmtpConfig} disabled={smtpSaving}>
			{smtpSaving ? 'Enregistrement…' : 'Enregistrer'}
		</button>
	</div>
</section>

<style>
	/*  Le résultat du test : un encadré, pas un `toast`. Un toast disparaît, et
	    c'est précisément ce message qu'on relit en corrigeant un paramètre. */
	/*  Les `span` restent SANS classe : `lint:casse-libelles` les lit comme du libellé,
	    dont ils gardent les capitales — le rendu d'avant, quand le style était en ligne. */
	.chiffrement > span:first-child {
		display: flex;
		align-items: center;
		gap: 1.5rem;
		flex-wrap: wrap;
	}
	.chiffrement > span:first-child > span {
		display: flex;
		align-items: center;
		gap: 0.4rem;
	}
	input[type='checkbox'].case-chiffrement {
		width: 1rem;
		height: 1rem;
	}
	.ligne-test {
		display: flex;
		gap: 0.5rem;
		align-items: center;
		flex-wrap: wrap;
	}
</style>
