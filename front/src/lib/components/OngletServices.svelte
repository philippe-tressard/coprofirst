<!--
  L'onglet **Services** de l'administration : les services de la copropriété sur
  un seul écran (#1718, premier lot du chantier multi-copropriétés).

  ## Rien n'est écrit ici

  La liste, les libellés, ce qu'on perd en coupant, l'onglet des réglages et
  l'icône viennent du registre `api/app/utils/services.py`, par
  `GET /config/services` — la forme de `llm-usages`. Ajouter un service, c'est une
  entrée du registre, pas une carte de plus dans cet écran.

  ## Un interrupteur, un seul endroit : ICI (14/10/2026)

  L'activation d'un service se coche ici et nulle part ailleurs. Son onglet de
  réglages (IA, WhatsApp, SMTP) en portait une seconde case, qui écrivait la même
  clé : il ne fait plus que DIRE l'état (`EtatService`) et renvoyer ici, et la
  rangée d'onglets grise celui d'un service coupé (`onglet_dedie`). Après une
  bascule, la page reçoit la nouvelle valeur (`apresBascule`) : l'onglet de
  réglages rouvert la lit, et la rangée se regrise.
  🔒 `test_services_registre.py` refuse une clé d'activation écrite ailleurs.

  L'envoi des courriels est une **infrastructure** : son état se montre, il ne
  se coupe pas d'ici — il porte les courriels de sécurité (mot de passe oublié,
  vérification d'adresse, alertes).
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { config as configApi, type ServiceCopropriete } from '#lib/api/index.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import Icon from '#lib/components/Icon.svelte';
	import EtatListe from '#lib/components/EtatListe.svelte';
	import BadgeEtatService from '#lib/components/BadgeEtatService.svelte';

	/**  La page tient la configuration lue au chargement : elle y reporte la bascule. */
	export let apresBascule: (cle: string, valeur: string) => void = () => {};

	let services: ServiceCopropriete[] = [];
	let chargement = true;
	let erreur = '';
	/**  Le service dont la bascule est en cours — son interrupteur attend. */
	let enCours = '';

	async function charger() {
		try {
			services = await configApi.services();
			erreur = '';
		} catch (e) {
			erreur = messageErreur(e);
		} finally {
			chargement = false;
		}
	}

	async function basculer(s: ServiceCopropriete, active: boolean) {
		if (!s.cle_actif) return;
		const valeur = active ? '1' : '0';
		enCours = s.code;
		try {
			await configApi.save({ [s.cle_actif]: valeur });
			apresBascule(s.cle_actif, valeur);
			toast('success', `${s.libelle} : ${active ? 'activé' : 'coupé'}.`);
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			//  L'état se RELIT : « incomplet » ne se devine pas au clic.
			await charger();
			enCours = '';
		}
	}

	onMount(charger);
</script>

<EtatListe {chargement} {erreur} vide={services.length === 0}>
	{#each services as s (s.code)}
		<section class="card config-section" data-service={s.code} aria-labelledby="service-{s.code}">
			<h2 class="config-section-title" id="service-{s.code}">
				<Icon name={s.icone} size={17} />{s.libelle}
				<BadgeEtatService etat={s.etat} />
			</h2>
			<p class="config-section-intro">{s.description}</p>
			{#if s.manque.length}
				<p class="manque">
					Il manque {s.manque.join(', ')} : le service est activé mais ne peut pas fonctionner.
				</p>
			{/if}
			<dl class="faits">
				<dt>Si on le coupe</dt>
				<dd>{s.perte}</dd>
				{#if s.plafond}
					<dt>Plafond</dt>
					<dd>{s.plafond}</dd>
				{/if}
			</dl>
			<div class="actions">
				{#if s.coupable}
					<label class="case">
						<input
							type="checkbox"
							checked={s.etat !== 'coupe'}
							disabled={enCours === s.code || (!s.autorise && s.etat === 'coupe')}
							on:change={(e) => basculer(s, e.currentTarget.checked)}
						/>
						Activé
					</label>
					{#if !s.autorise}
						<p class="aide refus">{s.refus}</p>
					{/if}
				{:else}
					<p class="aide">Ne se coupe pas d'ici.</p>
				{/if}
				<!--  Un service sans autre réglage que sa case (le décor des fêtes, #2312)
				      se règle ici même : un lien vers cet onglet ne mènerait nulle part. -->
				{#if s.onglet !== 'services'}
					<a class="reglages" href="/admin?onglet={s.onglet}">
						Réglages <Icon name="chevron-right" size={15} />
					</a>
				{/if}
			</div>
		</section>
	{/each}
</EtatListe>

<style>
	.config-section-title :global(.badge) {
		margin-left: auto;
	}
	.manque {
		margin: 0 0 0.75rem;
		color: var(--color-warning-texte);
		font-size: var(--fs-sm);
	}
	.faits {
		display: grid;
		grid-template-columns: max-content 1fr;
		gap: 0.25rem 0.75rem;
		margin: 0 0 0.75rem;
		font-size: var(--fs-sm);
	}
	.faits dt {
		color: var(--color-text-muted);
	}
	.faits dd {
		margin: 0;
	}
	.actions {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
		flex-wrap: wrap;
	}
	.refus {
		margin: 0;
		flex: 1;
		color: var(--color-warning-texte);
	}
	.reglages {
		display: inline-flex;
		align-items: center;
		gap: 0.2rem;
		min-height: 44px;
		font-weight: 600;
	}
	@media (max-width: 480px) {
		.faits {
			grid-template-columns: 1fr;
		}
		.faits dd {
			margin-bottom: 0.35rem;
		}
	}
</style>
