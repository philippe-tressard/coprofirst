<!--
  Le bloc **Installation** d'Administration › Maintenance (#1761) : le rôle de cette
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
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import pkg from '../../../package.json';
	import SectionFormulaire from './SectionFormulaire.svelte';
	import EtatListe from './EtatListe.svelte';
	import { instance, type EtatInstallation } from '$lib/api';
	import { messageErreur } from '$lib/erreurs';
	import { fmtDatetime } from '$lib/date';
	import { lienSource } from '$lib/plateforme';

	let etat: EtatInstallation | null = null;
	let chargement = true;
	let erreur = '';

	onMount(async () => {
		try {
			etat = await instance.installation();
		} catch (e) {
			erreur = messageErreur(e);
		} finally {
			chargement = false;
		}
	});

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
	@media (max-width: 480px) {
		.installation {
			grid-template-columns: 1fr;
		}
		.installation dd {
			margin-bottom: 0.4rem;
		}
	}
</style>
