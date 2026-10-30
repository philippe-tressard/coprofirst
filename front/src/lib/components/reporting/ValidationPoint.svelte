<!--
  La VALIDATION du compte rendu d'un point CS / Syndic, vue du conseil (#2042).

  - **À valider** : combien de présents ont validé, l'échéance de la validation
    d'office (7 jours), ou qu'elle est suspendue par un commentaire ; les
    commentaires reçus ; « Renvoyer aux présents » (après une correction, les
    validations repartent de zéro) et « Valider en l'état ».
  - **Validé** : la date, et le PDF — celui qui a été rangé et envoyé aux
    présents (#2082).
  - **La dérogation** (#2082) : pour un présent qui n'a pas validé mais a donné
    son accord, l'administrateur — lui seul — « Valide pour lui », avec un
    commentaire facultatif. C'est journalisé, et dit dans les validations du PDF.

  Les règles — qui reçoit, quand c'est validé — vivent au serveur
  (`utils/points_conseil_validation`) ; ce bloc ne fait que les montrer.
-->
<script lang="ts">
	import IconeAction from '#lib/components/IconeAction.svelte';
	import EncartAvertissement from '#lib/components/EncartAvertissement.svelte';
	import { toast } from '#lib/components/Toast.svelte';
	import { confirmer } from '#lib/confirmation.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { enregistrerFichier } from '#lib/fichiers.ts';
	import { pointsConseil, type CompteRenduPoint, type PresentPoint } from '#lib/api/index.ts';
	import { fmtDate, fmtDatetime, jourIso } from '#lib/date.ts';
	import { nomPresent } from '#lib/points-conseil.ts';
	import { isAdmin } from '#lib/stores/auth.ts';
	import { demander } from '#lib/saisie.ts';

	export let compteRendu: CompteRenduPoint;
	/** Relire le point après un geste. */
	export let onChange: () => Promise<void>;

	let enCours = false;

	$: point = compteRendu.point;
	$: v = compteRendu.validation;
	$: destinataires = compteRendu.presents.filter((p) => p.destinataire);

	async function geste(action: () => Promise<unknown>, succes: string, echec: string) {
		enCours = true;
		try {
			await action();
			await onChange();
			toast('success', succes);
		} catch (e) {
			toast('error', messageErreur(e, echec));
		} finally {
			enCours = false;
		}
	}

	async function renvoyer() {
		const ok = await confirmer({
			titre: 'Renvoyer aux présents',
			message:
				'Le compte rendu, tel qu’il est maintenant, repart aux présents : leurs validations repartent de zéro, et les 7 jours aussi.',
			libelleConfirmer: 'Renvoyer',
		});
		if (ok)
			await geste(
				() => pointsConseil.renvoyer(point.id),
				'Compte rendu renvoyé aux présents',
				'Renvoi impossible',
			);
	}

	async function valider() {
		const ok = await confirmer({
			titre: 'Valider le compte rendu',
			message:
				'Le compte rendu sera validé en l’état : chaque affaire abordée reçoit le sien, et le fil l’annonce au conseil et au syndic.',
			libelleConfirmer: 'Valider',
		});
		if (ok)
			await geste(
				() => pointsConseil.valider(point.id),
				'Compte rendu validé',
				'Validation impossible',
			);
	}

	async function deroger(present: PresentPoint) {
		const accord = await demander({
			titre: `Valider pour ${nomPresent(present)}`,
			message:
				'Le présent a donné son accord sans pouvoir valider lui-même. Dites comment, s’il y a lieu : c’est journalisé et cité au compte rendu.',
			libelle: 'Accord recueilli (facultatif)',
			libelleValider: 'Valider pour ce présent',
			requis: false,
		});
		if (accord === null) return;
		await geste(
			() => pointsConseil.derogation(point.id, present.id, accord || null),
			'Validation enregistrée pour ce présent',
			'Validation impossible',
		);
	}

	async function pdf() {
		enCours = true;
		try {
			enregistrerFichier(
				await pointsConseil.pdf(point.id),
				`compte-rendu-point-cs-syndic-${jourIso(point.debut)}.pdf`,
			);
		} catch (e) {
			toast('error', messageErreur(e, 'Export PDF impossible'));
		} finally {
			enCours = false;
		}
	}
</script>

<div class="validation">
	{#if point.etat === 'a_valider'}
		<p class="etat">
			Envoyé aux présents —
			<strong>{v.valides} sur {v.destinataires}</strong>
			{v.destinataires > 1 ? 'ont validé' : 'a validé'}.
			{#if v.suspendue}
				<span class="alerte">Un commentaire attend : la validation automatique est suspendue.</span>
			{:else if v.echeance}
				Sans réponse, il sera validé le {fmtDate(v.echeance)}.
			{/if}
		</p>
		{#if destinataires.length}
			<ul class="presents">
				{#each destinataires as p (p.id)}
					<li class:valide={p.valide_le}>
						<IconeAction icone={p.valide_le ? 'check' : 'clock'} />
						{nomPresent(p)}{#if p.par_derogation}<span class="derogation"
								>&nbsp;(par dérogation)</span
							>{/if}
						{#if $isAdmin && !p.valide_le}
							<button
								type="button"
								class="btn btn-sm btn-outline"
								disabled={enCours}
								on:click={() => deroger(p)}
							>
								Valider pour lui
							</button>
						{/if}
					</li>
				{/each}
			</ul>
		{/if}
		{#each compteRendu.commentaires as c, i (i)}
			<EncartAvertissement compact class="commentaire">
				<p class="qui">
					{c.auteur || 'Un présent'} · {fmtDatetime(c.cree_le)}{#if c.par_derogation}&nbsp;· accord
						écrit par l’administration{/if}
				</p>
				<p>{c.contenu}</p>
			</EncartAvertissement>
		{/each}
		<div class="rangee-gestes">
			<button type="button" class="btn btn-sm btn-outline" disabled={enCours} on:click={renvoyer}>
				<IconeAction icone="mail" /> Renvoyer aux présents
			</button>
			<button type="button" class="btn btn-sm btn-primary" disabled={enCours} on:click={valider}>
				<IconeAction icone="check" /> Valider en l’état
			</button>
		</div>
	{:else if point.etat === 'valide'}
		<p class="etat">
			Validé le {fmtDate(point.valide_le)} : chaque affaire abordée porte son compte rendu.
		</p>
		<div class="rangee-gestes">
			<button type="button" class="btn btn-sm btn-primary" disabled={enCours} on:click={pdf}>
				<IconeAction icone="file-text" /> Exporter en PDF
			</button>
		</div>
	{/if}
</div>

<style>
	.validation {
		margin-top: 0.5rem;
		padding-top: 0.5rem;
		border-top: 1px solid var(--color-border);
	}
	.etat {
		margin: 0 0 0.35rem;
		font-size: var(--fs-sm);
	}
	.alerte {
		color: var(--color-warning-texte);
	}
	.presents {
		list-style: none;
		margin: 0 0 0.35rem;
		padding: 0;
		display: flex;
		flex-wrap: wrap;
		gap: 0.25rem 0.9rem;
		font-size: var(--fs-sm);
		color: var(--color-text-muted);
	}
	.presents li {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
	}
	.presents li.valide {
		color: var(--color-success-texte);
	}
	.derogation {
		color: var(--color-text-muted);
	}
	:global(.encart-avertissement.commentaire) {
		margin: 0 0 0.4rem;
		font-size: var(--fs-sm);
	}
	:global(.encart-avertissement.commentaire) p {
		margin: 0;
		white-space: pre-line;
	}
	.qui {
		color: var(--color-text-muted);
		font-size: var(--fs-xs);
		margin-bottom: 0.15rem;
	}
</style>
