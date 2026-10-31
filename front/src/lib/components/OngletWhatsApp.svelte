<script lang="ts">
	import EncartDemo from '#lib/components/EncartDemo.svelte';
	import { messageErreur } from '#lib/erreurs.ts';
	//  Onglet « WhatsApp » de l'administration — extrait de `admin/+page.svelte`
	//  le 14/08/2026 : la page dépassait 2 200 lignes et la règle de modularité
	//  impose de découper le fichier quand on y touche. L'onglet est autonome
	//  (son état, ses appels, son rendu) ; seul le pied de message reste au
	//  parent, parce qu'il vit dans la configuration du site partagée avec
	//  les onglets Fonctionnement et Connexion (« Paramétrage site » avant #2062).
	import { onMount } from 'svelte';
	import {
		config as configApi,
		type JournalEnvoiWhatsApp,
		type MessagePlanifieWhatsApp,
	} from '#lib/api/index.ts';
	import { configStore } from '#lib/stores/pageConfig.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import { essayer } from '#lib/chargement.ts';
	import EncartAvertissement from '#lib/components/EncartAvertissement.svelte';
	import Icon from '#lib/components/Icon.svelte';
	import SectionFormulaire from '#lib/components/SectionFormulaire.svelte';
	import MessagesPlanifiesWhatsApp from '#lib/components/MessagesPlanifiesWhatsApp.svelte';
	import HistoriqueEnvoisWhatsApp from '#lib/components/HistoriqueEnvoisWhatsApp.svelte';
	import EtatService from '#lib/components/EtatService.svelte';
	import { SEPARATEUR } from '#lib/separateurs.ts';

	/** Configuration publique déjà chargée par la page (préremplit le formulaire). */
	export let cfgPublique: Record<string, string> = {};
	/** Pied de message — appartient à `siteConfig`, d'où le `bind:`. */
	export let footer = '';
	export let footerSaving = false;
	/** Enregistrement du pied de message, porté par la page. */
	export let onSaveFooter: () => unknown = () => {};

	//  Pas de clé d'API ici (#1596) : elle se définit dans `.env`
	//  (`WHATSAPP_API_KEY`), seule source, lue par l'API et par le bridge.
	let waConfig = { enabled: false, group_name: '', api_url: '', group_jid: '' };
	let waSaving = false;
	let waTestMessage =
		'\u{1F9EA} Test WhatsApp — si vous recevez ce message, la configuration est correcte ✅';
	let waTesting = false;
	let waStatus: { state: string; hasQR: boolean } | null = null;
	let waStatusLoading = false;
	let waQrTimestamp = Date.now();
	let waScheduled: MessagePlanifieWhatsApp[] = [];
	let waScheduledSaving: Record<number, boolean> = {};
	let waLogs: JournalEnvoiWhatsApp[] = [];

	//  La page charge sa configuration en asynchrone : l'onglet peut être monté
	//  avant qu'elle arrive. On recopie dès qu'elle est là, une seule fois, pour
	//  ne pas écraser une saisie en cours.
	let prerempli = false;
	$: if (!prerempli && Object.keys(cfgPublique).length) {
		waConfig.enabled = cfgPublique['whatsapp_enabled'] === '1';
		waConfig.group_name = cfgPublique['whatsapp_group_name'] ?? '';
		waConfig.api_url = cfgPublique['whatsapp_api_url'] ?? '';
		waConfig.group_jid = cfgPublique['whatsapp_group_jid'] ?? '';
		prerempli = true;
	}

	onMount(() => {
		loadWaScheduled();
		loadWaLogs();
	});

	//  Un échec se DIT à la place de la liste : « aucun message » serait faux (#1459).
	let erreurPlanifies = '';
	let erreurJournaux = '';
	async function loadWaScheduled() {
		[waScheduled, erreurPlanifies] = await essayer(configApi.whatsappPlanifies(), []);
	}
	async function loadWaLogs() {
		[waLogs, erreurJournaux] = await essayer(configApi.whatsappJournaux(), []);
	}

	async function saveWaScheduledItem(item: MessagePlanifieWhatsApp) {
		waScheduledSaving = { ...waScheduledSaving, [item.id]: true };
		try {
			await configApi.modifierWhatsappPlanifie(item.id, {
				label: item.label,
				message: item.message,
				cron_rule: item.cron_rule,
				enabled: item.enabled,
			});
			toast('success', `Message « ${item.label} » enregistré.`);
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			waScheduledSaving = { ...waScheduledSaving, [item.id]: false };
		}
	}

	async function sendWaTest() {
		if (!waTestMessage.trim()) return;
		waTesting = true;
		try {
			await configApi.testerWhatsapp(waTestMessage);
			toast('success', 'Message de test envoyé sur le groupe WhatsApp.');
		} catch (e) {
			//  Le serveur répond 502 quand le bridge n'a pas acquitté : ce n'est pas
			//  un échec, et surtout ce n'est pas une invitation à recliquer.
			toast('error', messageErreur(e, "Échec de l'envoi"));
		} finally {
			waTesting = false;
			loadWaLogs();
		}
	}

	async function checkWaStatus() {
		waStatusLoading = true;
		try {
			waStatus = await configApi.whatsappStatut();
			if (waStatus?.state === 'waiting_qr') waQrTimestamp = Date.now();
		} catch (e) {
			waStatus = null;
			toast('error', messageErreur(e, 'Impossible de joindre le bridge'));
		} finally {
			waStatusLoading = false;
		}
	}

	function refreshWaQr() {
		waQrTimestamp = Date.now();
	}

	async function saveWaConfig() {
		waSaving = true;
		try {
			//  L'activation n'y est pas : elle se coche dans Admin › Services, seule
			//  case qui l'écrit — la renvoyer rétablirait un service qu'on vient de couper.
			const payload: Record<string, string> = {
				whatsapp_group_name: waConfig.group_name,
				whatsapp_api_url: waConfig.api_url,
				whatsapp_group_jid: waConfig.group_jid,
			};
			await configApi.save(payload);
			configStore.update((c: Record<string, string>) => ({
				...c,
				whatsapp_group_name: waConfig.group_name,
				whatsapp_api_url: waConfig.api_url,
				whatsapp_group_jid: waConfig.group_jid,
			}));
			toast('success', 'Configuration WhatsApp enregistrée.');
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			waSaving = false;
		}
	}
</script>

<EncartDemo />
<section class="card config-section">
	<h2 class="config-section-title">
		<Icon name="whatsapp" size={18} />
		Configuration WhatsApp
	</h2>
	<SectionFormulaire premiere icone="settings" titre="Connexion au bridge">
		<div class="largeur-saisie">
			<EtatService actif={waConfig.enabled}>
				Activé, ce qui est coché « Partager sur le groupe » part au groupe WhatsApp.
			</EtatService>
		</div>
		<div class="form-grid largeur-saisie">
			<label class="field">
				Nom du canal
				<input type="text" bind:value={waConfig.group_name} placeholder="Groupe WhatsApp" />
				<span class="aide">Nom affiché dans l'interface (informatif).</span>
			</label>
			<label class="field">
				URL du bridge WhatsApp
				<input type="url" bind:value={waConfig.api_url} placeholder="http://whatsapp-bridge:8090" />
			</label>
			<label class="field">
				Group JID
				<input type="text" bind:value={waConfig.group_jid} placeholder="1234567890@g.us" />
				<span class="aide">Identifiant du groupe WhatsApp (format : 123...@g.us).</span>
			</label>
		</div>
		<p class="aide largeur-saisie">
			La clé d'accès au bridge ne se saisit pas ici : elle se définit sur le serveur, dans le
			fichier <code>.env</code> (<code>WHATSAPP_API_KEY</code>), et sert à la fois au site et au
			bridge.
		</p>
		<div class="largeur-saisie form-actions">
			<button class="btn btn-primary" on:click={saveWaConfig} disabled={waSaving}>
				{waSaving ? 'Enregistrement…' : 'Enregistrer'}
			</button>
		</div>
	</SectionFormulaire>

	<SectionFormulaire icone="activity" titre="Tester la configuration">
		<div class="largeur-saisie">
			<div class="etat-bridge">
				<button
					class="btn btn-outline btn-mini"
					on:click={checkWaStatus}
					disabled={waStatusLoading}
				>
					{waStatusLoading ? '...' : '\u{1F504} Statut'}
				</button>
				{#if waStatus}
					<span
						style="font-size:var(--fs-sm);padding:.1rem .5rem;border-radius:4px;{waStatus.state ===
						'open'
							? 'background:var(--color-success-fond);color:var(--color-success)'
							: 'background:var(--color-danger-fond);color:var(--color-danger)'}"
					>
						{waStatus.state === 'open'
							? '✅ Connecté'
							: waStatus.state === 'waiting_qr'
								? '\u{1F4F1} En attente du QR'
								: '❌ ' + waStatus.state}
					</span>
				{/if}
			</div>
			{#if waStatus?.state === 'waiting_qr'}
				<div class="qr-attente">
					<EncartAvertissement>
						<p class="titre-qr">
							&#x26A0;&#xFE0F; Bridge déconnecté{SEPARATEUR.tiret}scannez ce QR code avec WhatsApp
						</p>
						<p class="consigne-qr">
							WhatsApp{SEPARATEUR.fleche}Appareils connectés{SEPARATEUR.fleche}Connecter un appareil
						</p>
						<img src={configApi.whatsappQrUrl(waQrTimestamp)} alt="QR code WhatsApp" class="qr" />
						<div class="actions-qr">
							<button class="btn btn-outline btn-mini" type="button" on:click={refreshWaQr}>
								&#x1F504; Rafraîchir le QR
							</button>
							<button class="btn btn-outline btn-mini" type="button" on:click={checkWaStatus}>
								&#x2705; Vérifier la connexion
							</button>
						</div>
					</EncartAvertissement>
				</div>
			{/if}
			<div class="ligne-test">
				<div class="field champ-en-ligne champ-essai">
					<textarea
						bind:value={waTestMessage}
						rows="2"
						placeholder="Message de test..."
						class="message-test"></textarea>
				</div>
				<button
					class="btn btn-outline btn-test"
					on:click={sendWaTest}
					disabled={waTesting || !waTestMessage.trim()}
				>
					{waTesting ? 'Envoi...' : '\u{1F4E8} Envoyer le test'}
				</button>
			</div>
			<p class="note-essai">Envoie le message ci-dessus sur le groupe WhatsApp configuré.</p>
		</div>
	</SectionFormulaire>

	<!-- Messages planifiés -->
	<SectionFormulaire icone="calendar-days" titre="Messages planifiés (envoi automatique)">
		<MessagesPlanifiesWhatsApp
			messages={waScheduled}
			erreur={erreurPlanifies}
			enregistrement={waScheduledSaving}
			enregistrer={saveWaScheduledItem}
		/>
	</SectionFormulaire>

	<!-- Footer des messages -->
	<SectionFormulaire icone="pencil" titre="Footer des messages">
		<div class="largeur-saisie">
			<label class="field">
				<textarea
					bind:value={footer}
					rows="2"
					placeholder="— Le Conseil Syndical"
					class="saisie-gabarit"></textarea>
				<span class="aide"
					>Texte qui finalise chaque message (markdown WhatsApp autorisé : *gras*, _italique_,
					~barré~).</span
				>
			</label>
		</div>

		<div class="largeur-saisie form-actions">
			<button class="btn btn-primary" on:click={onSaveFooter} disabled={footerSaving}>
				{footerSaving ? 'Enregistrement…' : 'Enregistrer'}
			</button>
		</div>
	</SectionFormulaire>

	<!-- Historique des envois -->
	<SectionFormulaire icone="clipboard-list" titre="Historique des envois (6 derniers)">
		<HistoriqueEnvoisWhatsApp journaux={waLogs} erreur={erreurJournaux} recharger={loadWaLogs} />
	</SectionFormulaire>
</section>

<style>
	/*  Le QR en attente : un encart (#1455), étroit pour que le QR et ses deux
	    lignes se lisent d'un bloc. */
	.qr-attente {
		margin-top: 0.75rem;
		max-width: 360px;
	}
	.etat-bridge {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin-bottom: 0.5rem;
	}
	.btn-mini {
		font-size: var(--fs-xs);
		padding: 0.15rem 0.5rem;
	}
	.titre-qr {
		margin: 0 0 0.5rem;
		font-weight: 600;
	}
	.consigne-qr {
		margin: 0 0 0.75rem;
		font-size: var(--fs-sm);
	}
	.qr {
		display: block;
		width: 220px;
		height: 220px;
		border-radius: 4px;
		border: 1px solid var(--color-warning);
	}
	.actions-qr {
		display: flex;
		gap: 0.5rem;
		margin-top: 0.5rem;
		align-items: center;
	}
	.ligne-test {
		display: flex;
		gap: 0.5rem;
		align-items: start;
		flex-wrap: wrap;
	}
	.message-test {
		resize: vertical;
	}
	.btn-test {
		white-space: nowrap;
	}
</style>
