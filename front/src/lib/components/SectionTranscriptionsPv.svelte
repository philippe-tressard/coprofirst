<!--
  Ma résidence › Règlement — la section « Transcription des PV d'AG » (29/10/2026).

  Pour l'administration seule. Chaque PV déposé dans la Fiche (rubrique
  Comptes-rendus d'AG) se transcrit par l'assistant : ses RÉSOLUTIONS, sans nom de
  personne. Un PV récent l'est d'office chaque matin ; un plus ancien par
  « Transcrire ». La transcription attend sa relecture : « Relire » l'ouvre DANS
  sa ligne (le geste est là, `ux-patterns` §14 ter), on la corrige, et « Enregistrer »
  la valide : elle entre dans les décisions d'AG que les questions lisent.

  🔴 Rien n'entre sans cette relecture : le code vérifie qu'une citation figure
  dans le texte lu, pas que ce texte dit ce que dit le PV
  (`utils/question_reglement/transcription`).
-->
<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import Badge from '#lib/components/Badge.svelte';
	import EtatListe from '#lib/components/EtatListe.svelte';
	import IconeAction from '#lib/components/IconeAction.svelte';
	import IconeIA from '#lib/components/IconeIA.svelte';
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';
	import { toast } from '#lib/components/Toast.svelte';
	import {
		reglement as reglementApi,
		type EtatTranscriptions,
		type PvTranscrit,
	} from '#lib/api/index.ts';
	import { confirmer } from '#lib/confirmation.ts';
	import { fmtDate } from '#lib/date.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { TEINTE_TRANSCRIPTION } from '#lib/reglement.ts';

	/** Une transcription validée change le texte que l'onglet décrit. */
	export let onValidee: () => Promise<void>;

	/** Relue toutes les cinq secondes tant qu'une transcription est en cours. */
	const RELECTURE_MS = 5000;

	let etat: EtatTranscriptions | null = null;
	let chargement = true;
	let erreur = '';
	let lancement: number | null = null;
	/** La transcription ouverte en relecture — une à la fois. */
	let relue: number | null = null;
	let contenu = '';
	let validation = false;
	let minuterie: ReturnType<typeof setTimeout> | null = null;

	onMount(lire);
	onDestroy(() => {
		if (minuterie) clearTimeout(minuterie);
	});

	async function lire() {
		try {
			etat = await reglementApi.transcriptions();
			erreur = '';
		} catch (e) {
			erreur = messageErreur(e);
		} finally {
			chargement = false;
		}
		if (minuterie) clearTimeout(minuterie);
		minuterie = etat?.pvs?.some((p) => p.transcription?.statut === 'en_cours')
			? setTimeout(lire, RELECTURE_MS)
			: null;
	}

	/** On transcrit un PV qui n'a rien en attente : jamais transcrit, validé ou rejeté. */
	function transcriptible(pv: PvTranscrit): boolean {
		const statut = pv.transcription?.statut;
		return !statut || statut === 'validee';
	}

	async function transcrire(pv: PvTranscrit) {
		lancement = pv.pv_id;
		try {
			await reglementApi.transcrire(pv.pv_id);
			await lire();
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			lancement = null;
		}
	}

	function basculerRelecture(pv: PvTranscrit) {
		const t = pv.transcription;
		if (!t) return;
		relue = relue === t.id ? null : t.id;
		contenu = t.contenu ?? '';
	}

	async function valider() {
		if (relue === null) return;
		validation = true;
		try {
			await reglementApi.validerTranscription(relue, contenu);
			relue = null;
			toast('success', "Décisions d'AG validées : l'assistant les lira.");
			await Promise.all([lire(), onValidee()]);
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			validation = false;
		}
	}

	async function rejeter(pv: PvTranscrit) {
		const t = pv.transcription;
		if (!t) return;
		if (
			!(await confirmer({
				titre: `Rejeter la transcription de « ${pv.titre} » ?`,
				message: 'Elle est effacée ; le PV pourra être transcrit à nouveau.',
				libelleConfirmer: 'Rejeter',
				danger: true,
			}))
		)
			return;
		try {
			await reglementApi.rejeterTranscription(t.id);
			if (relue === t.id) relue = null;
			await lire();
		} catch (e) {
			toast('error', messageErreur(e));
		}
	}
</script>

<section class="card config-section">
	<h3 class="config-section-title">Transcription des PV d'AG</h3>
	<p class="aide">
		L'assistant transcrit les résolutions d'un PV déposé dans la Fiche, sans nom de personne —
		d'office chaque matin pour un PV déposé depuis moins de deux mois. Relisez-la, corrigez-la au
		besoin : validée, elle rejoint les décisions d'AG lues par l'assistant.
	</p>
	<EtatListe
		{chargement}
		{erreur}
		vide={!!etat && !etat.pvs.length}
		titreVide="Aucun PV d'AG"
		messageVide="Les PV se déposent dans la Fiche, rubrique Comptes-rendus d'AG."
	>
		{#if etat && !etat.disponible}
			<p class="aide">
				L'assistant n'est pas activé pour la transcription des PV (Admin › Assistant IA).
			</p>
		{/if}
		{#if etat}
			<ul class="pvs">
				{#each etat.pvs as pv (pv.pv_id)}
					{@const t = pv.transcription}
					<li>
						<div class="ligne">
							<span class="titre">{pv.titre}</span>
							{#if pv.date_ag}<span class="aide date">AG du {fmtDate(pv.date_ag)}</span>{/if}
							{#if t}
								<Badge teinte={TEINTE_TRANSCRIPTION[t.statut]}>{t.statut_libelle}</Badge>
							{/if}
							<span class="gestes">
								{#if etat.disponible && transcriptible(pv)}
									<button
										class="btn btn-outline btn-sm"
										type="button"
										disabled={lancement !== null}
										aria-busy={lancement === pv.pv_id}
										on:click={() => transcrire(pv)}
									>
										<IconeIA enCours={lancement === pv.pv_id} />
										{t ? 'Transcrire à nouveau' : 'Transcrire'}
									</button>
								{/if}
								{#if t?.statut === 'a_relire'}
									<button
										class="btn-icon-edit"
										type="button"
										aria-label="Relire la transcription"
										title="Relire la transcription"
										aria-pressed={relue === t.id}
										on:click={() => basculerRelecture(pv)}><IconeAction icone="pencil" /></button
									>
								{/if}
								{#if t?.statut === 'a_relire' || t?.statut === 'echec'}
									<button
										class="btn-icon-danger"
										type="button"
										aria-label="Rejeter la transcription"
										title="Rejeter la transcription"
										on:click={() => rejeter(pv)}><IconeAction icone="x" /></button
									>
								{/if}
							</span>
						</div>
						{#if t?.statut === 'echec' && t.erreur}
							<p class="aide alerte">{t.erreur}</p>
						{/if}
						{#if t && relue === t.id}
							<form class="relecture" on:submit|preventDefault={valider}>
								<label class="field">
									<span>Résolutions transcrites</span>
									<textarea bind:value={contenu} rows="16" spellcheck="true"></textarea>
									<span class="aide"
										>Vérifiez chaque résolution contre le PV, et qu'aucun nom de personne ne reste.</span
									>
								</label>
								<PiedFormulaire enCours={validation} on:annule={() => (relue = null)} />
							</form>
						{/if}
					</li>
				{/each}
			</ul>
		{/if}
	</EtatListe>
</section>

<style>
	.pvs {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
	}
	.ligne {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem;
	}
	.titre {
		font-weight: 600;
	}
	.date {
		margin: 0;
	}
	.gestes {
		margin-left: auto;
		display: flex;
		align-items: center;
		gap: 0.35rem;
	}
	.relecture {
		margin-top: 0.5rem;
	}
	.alerte {
		color: var(--color-warning-texte);
	}
</style>
