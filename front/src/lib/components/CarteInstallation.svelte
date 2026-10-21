<!--
  Le bloc **Installation** d'Administration › Exploitation › Installation (#1761, onglet propre depuis #2062) : le rôle de cette
  installation dans la distribution CoproFirst, et l'écart de sa version.

  Exigence de l'auteur, 08/10/2026 : « savoir si l'instance est le master
  (git => main) ou une réplique (git => replica) ».

  - Le rôle vient du SERVEUR (`ROLE_INSTALLATION`), jamais d'une déduction de
    l'écran : un rôle absent s'affiche « Inconnu », jamais « Référence ».
  - L'écart se MESURE contre le dépôt, par le service « Vérification de la
    version », coupé par défaut (rien ne sort sans accord, §4.10 règle 9) ; coupé
    ou injoignable, il dit « non vérifié », jamais « à jour ».
  - Ce rôle n'est pas celui d'un nœud dans la haute disponibilité : les deux
    Raspberry Pi sont ENSEMBLE la référence ; le nœud qui sert se lit au pied de page.

  **Inscription au registre** (R2 #1878, arbitrage du 13/10/2026 : ici, à l'opérateur) :
  l'état de l'installation auprès de la référence — limitée, active, suspendue — et
  sa raison, CONSTATÉS : rien ne les applique encore (R6, #1882). L'opérateur y saisit
  le contact de l'administrateur d'installation et accepte les conditions EN VIGUEUR,
  dont le texte se lit ici même : on ne s'engage pas sur un texte qu'on n'a pas vu.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import pkg from '../../../package.json';
	import SectionFormulaire from './SectionFormulaire.svelte';
	import EtatListe from './EtatListe.svelte';
	import EtoileRequis from './EtoileRequis.svelte';
	import {
		instance,
		type ConditionsInscription,
		type EtatInstallation,
		type InscriptionInstallation,
	} from '$lib/api';
	import { toast } from '$lib/components/Toast.svelte';
	import { messageErreur } from '$lib/erreurs';
	import { fmtDatetime } from '$lib/date';
	import { nomAffiche } from '$lib/noms';
	import { lienSource } from '$lib/plateforme';
	import TexteMarkdown from '$lib/components/TexteMarkdown.svelte';

	let etat: EtatInstallation | null = null;
	let chargement = true;
	let erreur = '';

	let inscription: InscriptionInstallation | null = null;
	let chargementInscription = true;
	let erreurInscription = '';
	let conditions: ConditionsInscription | null = null;
	let formulaireOuvert = false;
	let envoi = false;
	let renouvellement = false;
	let prenom = '';
	let nom = '';
	let courriel = '';
	let telephone = '';
	let accepte = false;

	onMount(async () => {
		try {
			etat = await instance.installation();
		} catch (e) {
			erreur = messageErreur(e);
		} finally {
			chargement = false;
		}
		try {
			inscription = await instance.inscription();
		} catch (e) {
			erreurInscription = messageErreur(e);
		} finally {
			chargementInscription = false;
		}
	});

	/** L'état constaté, dit en clair — `reference` et `essai` ne sont jamais limités. */
	const LIBELLES_INSCRIPTION: Record<InscriptionInstallation['etat'], string> = {
		reference: 'Référence',
		essai: 'Essai',
		limitee: 'Limitée',
		active: 'Active',
		suspendue: 'Suspendue',
	};

	async function ouvrirFormulaire() {
		formulaireOuvert = !formulaireOuvert;
		if (!formulaireOuvert) return;
		const c = inscription?.contact;
		prenom = c?.prenom ?? '';
		nom = c?.nom ?? '';
		courriel = c?.courriel ?? '';
		telephone = c?.telephone ?? '';
		accepte = false;
		try {
			conditions = await instance.conditionsInscription();
		} catch (e) {
			toast('error', messageErreur(e));
		}
	}

	async function inscrire() {
		if (!conditions) return;
		envoi = true;
		try {
			inscription = await instance.inscrire({
				prenom,
				nom,
				courriel,
				telephone: telephone.trim() || null,
				conditions_acceptees: conditions.version,
				accepte,
			});
			formulaireOuvert = false;
			toast('success', `Installation inscrite : ${inscription.identifiant ?? ''}`.trim());
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			envoi = false;
		}
	}

	async function renouveler() {
		renouvellement = true;
		try {
			inscription = await instance.renouvelerBail();
			toast('success', 'Bail demandé à la référence.');
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			renouvellement = false;
		}
	}

	/** La ligne « À jour ? », dite en clair — la mesure, ou pourquoi il n'y en a pas. */
	function ecart(e: EtatInstallation): { texte: string; ton: 'ok' | 'alerte' | 'neutre' } {
		if (e.etat === 'a_jour') return { texte: `À jour sur ${e.branche}`, ton: 'ok' };
		if (e.etat === 'en_retard')
			return { texte: `${e.retard} commit(s) de retard sur ${e.branche}`, ton: 'alerte' };
		if (e.etat === 'ecart') return { texte: `Écart : ${e.detail}`, ton: 'alerte' };
		return { texte: `Non vérifié — ${e.detail}`, ton: 'neutre' };
	}
</script>

<section class="card config-section">
	<SectionFormulaire titre="Installation" icone="layers" />
	<EtatListe {chargement} {erreur} vide={!etat}>
		{#if etat}
			{@const e = ecart(etat)}
			<dl class="installation">
				<dt>Rôle</dt>
				<dd>
					<strong>{etat.libelle}</strong>
					{#if etat.branche}— suit <code>{etat.branche}</code>{/if}
					{#if etat.role === 'inconnu'}
						<p class="aide">
							<code>ROLE_INSTALLATION</code> n’est pas déclaré dans le <code>.env</code> de
							l’installation : <code>reference</code> ou <code>replique</code>.
						</p>
					{/if}
				</dd>
				<dt>Version</dt>
				<dd>
					v{pkg.version}{#if etat.empreinte}&nbsp;·&nbsp;<a
							href={lienSource(etat.empreinte)}
							target="_blank"
							rel="noopener noreferrer"><code>{etat.empreinte}</code></a
						>{/if}
				</dd>
				<dt>En service depuis</dt>
				<dd>{fmtDatetime(etat.demarree_le)}</dd>
				<dt>À jour&nbsp;?</dt>
				<dd class:ton-ok={e.ton === 'ok'} class:ton-alerte={e.ton === 'alerte'}>
					{e.texte}
					{#if !etat.verification_active && etat.branche}
						<p class="aide">
							Le service « Vérification de la version » s’active dans Administration › Services :
							seul le commit de l’image part vers le dépôt public.
						</p>
					{/if}
				</dd>
			</dl>
		{/if}
	</EtatListe>

	<SectionFormulaire titre="Inscription au registre" icone="shield-check" />
	<EtatListe chargement={chargementInscription} erreur={erreurInscription} vide={!inscription}>
		{#if inscription}
			{@const i = inscription}
			<dl class="installation">
				<dt>État</dt>
				<dd
					class:ton-ok={i.etat === 'active' || i.etat === 'reference'}
					class:ton-alerte={i.etat === 'limitee' || i.etat === 'suspendue'}
				>
					<strong>{LIBELLES_INSCRIPTION[i.etat]}</strong> — {i.raison}
					<p class="aide">
						Constaté seulement — sauf les services&nbsp;: une réplique n’allume que ceux que la
						référence autorise.
					</p>
				</dd>
				{#if i.identifiant}
					<dt>Identifiant</dt>
					<dd>
						<code>{i.identifiant}</code>{#if i.canal}&nbsp;· canal <code>{i.canal}</code>{/if}
					</dd>
				{/if}
				{#if i.services}
					<dt>Services autorisés</dt>
					<dd>{i.services.length ? i.services.join(', ') : 'aucun'}</dd>
				{/if}
				{#if i.echeance}
					<dt>Bail jusqu’au</dt>
					<dd>{fmtDatetime(i.echeance)}</dd>
				{/if}
				{#if i.dernier_renouvellement_le}
					<dt>Renouvelé le</dt>
					<dd class:ton-alerte={i.renouvellement_en_retard}>
						{fmtDatetime(i.dernier_renouvellement_le)}
					</dd>
				{/if}
				{#if i.dernier_rapport_le}
					<dt>Dernier rapport</dt>
					<dd>{fmtDatetime(i.dernier_rapport_le)}</dd>
				{/if}
				{#if i.derniere_erreur}
					<dt>Dernière erreur</dt>
					<dd class="ton-alerte">{i.derniere_erreur}</dd>
				{/if}
				{#if i.contact}
					<dt>Administrateur</dt>
					<dd>{nomAffiche(i.contact)} — {i.contact.courriel}</dd>
				{/if}
			</dl>
			{#if i.essai_refuse}
				<p class="aide">
					<code>INSTALLATION_ESSAI</code> est posé mais refusé&nbsp;: il n’est admis que pour un hôte
					local ou une base en mémoire.
				</p>
			{/if}

			{#if i.peut_s_inscrire}
				<div class="gestes-inscription">
					<button
						class="btn"
						type="button"
						aria-expanded={formulaireOuvert}
						on:click={ouvrirFormulaire}
					>
						{i.identifiant ? 'Mettre à jour le contact' : 'Inscrire l’installation'}
					</button>
					{#if i.identifiant}
						<button class="btn" type="button" on:click={renouveler} disabled={renouvellement}>
							{renouvellement ? 'Demande…' : 'Renouveler le bail'}
						</button>
					{/if}
				</div>

				{#if formulaireOuvert}
					<form class="inscription" on:submit|preventDefault={inscrire}>
						<p class="aide">
							Le contact de l’administrateur de l’installation part à la référence ({i.registre_url}),
							qui l’archive avec les conditions acceptées. Aucune donnée de résident n’en fait
							partie.
						</p>
						<div class="field">
							<label for="ins-prenom">Prénom<EtoileRequis vide={!prenom.trim()} /></label>
							<input id="ins-prenom" type="text" maxlength="80" bind:value={prenom} required />
						</div>
						<div class="field">
							<label for="ins-nom">Nom<EtoileRequis vide={!nom.trim()} /></label>
							<input id="ins-nom" type="text" maxlength="80" bind:value={nom} required />
						</div>
						<div class="field">
							<label for="ins-courriel">Courriel<EtoileRequis vide={!courriel.trim()} /></label>
							<input id="ins-courriel" type="email" bind:value={courriel} required />
						</div>
						<div class="field">
							<label for="ins-telephone">Téléphone</label>
							<input id="ins-telephone" type="tel" maxlength="30" bind:value={telephone} />
						</div>
						{#if conditions}
							<TexteMarkdown
								texte={conditions.texte}
								libelle="Conditions d’inscription, version {conditions.version}"
							/>
							<label class="case">
								<input type="checkbox" bind:checked={accepte} />
								<span>J’accepte les conditions d’inscription (version {conditions.version})</span>
							</label>
						{/if}
						<div class="form-actions">
							<button
								class="btn btn-primary"
								type="submit"
								disabled={envoi ||
									!accepte ||
									!conditions ||
									!prenom.trim() ||
									!nom.trim() ||
									!courriel.trim()}
							>
								{envoi ? 'Enregistrement…' : 'Enregistrer'}
							</button>
						</div>
					</form>
				{/if}
			{/if}
		{/if}
	</EtatListe>
</section>

<style>
	.installation {
		display: grid;
		grid-template-columns: max-content 1fr;
		gap: 0.4rem 1rem;
		margin: 0;
	}
	.installation dt {
		color: var(--color-text-muted);
	}
	.installation dd {
		margin: 0;
	}
	.ton-ok {
		color: var(--color-success-texte);
	}
	.ton-alerte {
		color: var(--color-warning-texte);
	}
	.gestes-inscription {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		margin-top: 0.75rem;
	}
	.inscription {
		margin-top: 0.75rem;
	}
	@media (max-width: 480px) {
		.installation {
			grid-template-columns: 1fr;
		}
		.installation dd {
			margin-bottom: 0.4rem;
		}
	}
</style>
