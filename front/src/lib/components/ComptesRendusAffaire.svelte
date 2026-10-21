<!--
  La rubrique « COMPTES RENDUS » d'une affaire dépliée — maquette B4, arbitrée
  le 17/10/2026 (#2042) : tous les points CS / Syndic où l'affaire a été
  abordée, le plus récent en tête.

  - Elle n'existe qu'une fois un compte rendu VALIDÉ : rien ne paraît ici avant
    (`GET /points-conseil/affaires/{id}`, qui ne rend que ceux-là, et tait au
    lecteur ce qui est « Conseil seul »). Sans compte rendu, pas de rubrique.
  - Elle ne se corrige PAS ici : la correction vit dans le Reporting, tant que
    l'affaire n'est ni close ni annulée. Le conseil peut seulement réserver un
    compte rendu au conseil et aux présents (« CS et présents », #2082), ou le
    rouvrir.
  - Sur une affaire lue du SEUL conseil, chaque compte rendu porte le lien vers
    le PDF du point, celui qui a été rangé et envoyé aux présents (demandé le
    20/10/2026, précisé le 21/10 : « pour les affaires en visibilité exclusive du
    CS ; les autres n'auront pas ce lien car ils n'y auront pas accès »). Le
    serveur le dit (`pdf_disponible`) ; l'écran ne le recalcule pas.
  - Une étape du rail (`RubriqueEtape`), entre la suite et la synthèse ;
    l'accordéon reste tenu par la carte (`ouverte`, `onBasculer`).
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import RubriqueEtape from './RubriqueEtape.svelte';
	import Badge from './Badge.svelte';
	import IconeAction from './IconeAction.svelte';
	import { toast } from './Toast.svelte';
	import { pointsConseil, type CrPublie } from '$lib/api';
	import { fmtDate, fmtDatetime } from '$lib/date';
	import { messageErreur } from '$lib/erreurs';
	import { safeHtml } from '$lib/sanitize';
	import { isCS } from '$lib/stores/auth';
	import { enregistrerFichier } from '$lib/fichiers';
	import { jourIso } from '$lib/date';
	import { LIBELLE_CS_ET_PRESENTS } from '$lib/points-conseil';

	export let ticketId: number;
	export let ouverte = false;
	export let onBasculer: () => void;

	let crs: CrPublie[] = [];

	async function charger() {
		try {
			crs = await pointsConseil.crsAffaire(ticketId);
		} catch (e) {
			toast('error', messageErreur(e, 'Comptes rendus indisponibles'));
		}
	}

	async function basculerConfidentialite(cr: CrPublie) {
		try {
			await pointsConseil.confidentialite(cr.cr_id, !cr.conseil_seul);
			await charger();
		} catch (e) {
			toast('error', messageErreur(e, 'Modification impossible'));
		}
	}

	/** Le PDF du compte rendu du point — rangé à la validation, envoyé aux présents. */
	let pdfEnCours: number | null = null;
	async function telechargerPdf(cr: CrPublie) {
		pdfEnCours = cr.cr_id;
		try {
			enregistrerFichier(
				await pointsConseil.pdf(cr.point_id),
				`compte-rendu-point-cs-syndic-${jourIso(cr.debut)}.pdf`,
			);
		} catch (e) {
			toast('error', messageErreur(e, 'PDF indisponible'));
		} finally {
			pdfEnCours = null;
		}
	}

	onMount(charger);
</script>

{#if crs.length}
	<RubriqueEtape
		titre="Comptes rendus"
		icone="users"
		compte={crs.length}
		resume="Dernier point CS / Syndic le {fmtDate(crs[0].debut)}"
		{ouverte}
		{onBasculer}
	>
		{#each crs as cr (cr.cr_id)}
			<article class="cr">
				<p class="tete">
					<strong>Point CS / Syndic du {fmtDatetime(cr.debut)}</strong>
					<span class="lieu">· {cr.ou}</span>
					{#if cr.conseil_seul}<Badge teinte="badge-purple" compact>{LIBELLE_CS_ET_PRESENTS}</Badge
						>{/if}
					<span class="gestes">
						{#if cr.pdf_disponible}
							<button
								type="button"
								class="btn btn-sm btn-outline"
								disabled={pdfEnCours === cr.cr_id}
								aria-busy={pdfEnCours === cr.cr_id}
								on:click={() => telechargerPdf(cr)}
								><IconeAction icone="file-text" /> Compte rendu du point (PDF)</button
							>
						{/if}
						{#if $isCS}
							<button
								type="button"
								class="btn-icon"
								aria-pressed={cr.conseil_seul}
								aria-label={cr.conseil_seul
									? 'Rendre ce compte rendu lisible de qui lit l’affaire'
									: 'Réserver ce compte rendu au conseil syndical et aux présents'}
								title={cr.conseil_seul ? 'Rouvrir à qui lit l’affaire' : LIBELLE_CS_ET_PRESENTS}
								on:click={() => basculerConfidentialite(cr)}
								><IconeAction icone="shield-check" /></button
							>
						{/if}
					</span>
				</p>
				<div class="contenu">{@html safeHtml(cr.contenu)}</div>
			</article>
		{/each}
	</RubriqueEtape>
{/if}

<style>
	.cr + .cr {
		margin-top: 0.6rem;
		padding-top: 0.6rem;
		border-top: 1px solid var(--color-border);
	}
	.tete {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.35rem;
		margin: 0 0 0.25rem;
		font-size: var(--fs-sm);
	}
	.lieu {
		color: var(--color-text-muted);
	}
	.gestes {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		margin-left: auto;
	}
	.contenu {
		font-size: var(--fs-sm);
	}
</style>
