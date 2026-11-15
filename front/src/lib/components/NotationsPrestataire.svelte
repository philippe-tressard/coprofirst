<!--
  **Les avis portés sur un prestataire** — la liste, et le geste qui en retire un.

  ## 🔴 Ce que le ticket disait, et ce qui était vrai (#807, 06/09/2026)

  Le ticket annonçait « un résident ne peut pas retirer sa propre notation ».
  C'était faux, et la lecture de l'endpoint l'a montré : **seul le conseil
  syndical ou l'administrateur peut noter** (`require_cs_or_admin` sur
  `POST /prestataires/notations`). Il n'y a donc pas de résident qui aurait noté
  par erreur — c'est un outil interne du CS.

  Le vrai défaut est plus simple, et il portait sur les mêmes personnes : le CS
  pouvait **poser** une note et pas la **retirer**. `DELETE
  /prestataires/notations/{id}` existait, réservé au CS, et aucun écran ne
  l'appelait. Un membre qui se trompe de prestataire, ou qui note deux fois la
  même intervention, n'avait aucun recours.

  ⚠️ Et il n'y avait nulle part où poser le bouton : l'écran n'affichait que la
  **moyenne**, dans un badge. Les avis individuels — qui, quand, quel
  commentaire — n'étaient visibles nulle part. Ajouter une suppression sans la
  liste aurait donné un geste sans cible.

  ## Le droit affiché est celui que le SERVEUR applique

  `require_cs_or_admin`, ni plus ni moins (`ux-patterns` §15). Le composant ne
  restreint pas la suppression à l'auteur de la note : l'endpoint ne le fait pas,
  et un écran plus étroit que le serveur rend une capacité introuvable — plus
  large, il produit un 403 sur un geste qu'il a lui-même proposé.

  ⚠️ **L'auteur est affiché**, lui, et c'est ce qui rend la modération
  responsable : on voit qui a noté avant de retirer.

  ## Le récapitulatif PAR INTERVENTION (maquette R3d, 15/11/2026)

  Un exercice par bloc, le plus récent ouvert : « Exercice 2026 · 5 interventions ·
  4 notées », et le compte des états. Dedans, une ligne par affaire du prestataire —
  sa date, son titre, le badge de chaque avis porté sur ce couple, « non notée » sinon —,
  puis les avis sans affaire. Un badge déplie l'avis : son auteur, son commentaire,
  la correction (l'auteur) et le retrait (le conseil), SOUS la ligne et sur toute la
  largeur. Le regroupement est servi par l'API (`GET /prestataires/{id}/interventions`) :
  l'exercice d'une affaire et la règle « notée » ne sont pas recopiés ici.
-->
<script lang="ts">
	import { fmtNombre } from '#lib/utils.ts';
	import { createEventDispatcher } from 'svelte';
	import {
		prestataires as prestApi,
		type ExerciceInterventions,
		type Notation,
	} from '#lib/api/index.ts';
	import { essayer } from '#lib/chargement.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import { confirmer } from '#lib/confirmation.ts';
	import { fmtDate } from '#lib/date.ts';
	import GesteNoter from './GesteNoter.svelte';
	import { ETATS, LIBELLE_ETAT, TEINTE_ETAT, etatDeMoyenne } from '#lib/notations.ts';
	import { basculer as basculerUn } from '#lib/accordeon.ts';
	import Badge from './Badge.svelte';
	import { SEPARATEUR } from '#lib/separateurs.ts';
	import IconeAction from './IconeAction.svelte';

	/** Les notations de CE prestataire, déjà filtrées par l'appelant. */
	export let notations: Notation[] = [];
	/** Vrai pour le conseil syndical et l'administration — ce que l'endpoint exige. */
	export let peutSupprimer = false;
	/**  `true` = le badge de moyenne (dans l'en-tête de la carte) · `false` = le
	 *   récapitulatif (dans le corps déplié). Deux vues de la même donnée, donc
	 *   un seul composant : les séparer aurait donné deux endroits où changer la
	 *   façon d'écrire une note. */
	export let resume = false;
	/**  La moyenne de ses avis et leur nombre, SERVIS par l'API avec le prestataire
	 *   (`note_moyenne`, `nb_notations`, #2507) — `null` sans avis, jamais 0. */
	export let moyenne: number | null = null;
	export let nbAvis = 0;

	const dispatch = createEventDispatcher<{ supprimee: number; modifiee: Notation }>();
	/** Le prestataire de ces avis — son récapitulatif, et corriger son propre avis. */
	export let prestataireId: number | undefined = undefined;
	export let prestataireNom = '';

	/** Le récapitulatif servi ; rechargé quand les avis changent (ajout, correction, retrait). */
	let exercices: ExerciceInterventions[] = [];
	let demande = 0;
	async function charger(id: number) {
		const numero = ++demande;
		const [lus] = await essayer(prestApi.interventions(id), []);
		if (numero === demande) exercices = lus;
	}
	$: if (!resume && prestataireId !== undefined) void (notations, charger(prestataireId));

	/** Les lignes d'un exercice : ses interventions, puis ses avis sans affaire. */
	function lignes(ex: ExerciceInterventions) {
		const l = ex.interventions.map((i) => ({
			cle: `t${i.ticket_id}`,
			date: i.date as string | null,
			ticketId: i.ticket_id as number | null,
			titre: i.titre,
			avis: i.avis,
		}));
		if (ex.avis_generaux.length)
			l.push({
				cle: 'generaux',
				date: null,
				ticketId: null,
				titre: 'Avis sans affaire',
				avis: ex.avis_generaux,
			});
		return l;
	}

	let exerciceOuvert: number | null | undefined = undefined;
	$: if (exerciceOuvert === undefined && exercices.length) exerciceOuvert = exercices[0].annee;

	/** L'avis déplié — un seul à la fois, sinon la liste s'allonge. */
	let ouvert: number | null = null;

	async function supprimer(n: Notation) {
		const ok = await confirmer({
			titre: 'Retirer cet avis',
			message:
				`État « ${LIBELLE_ETAT[n.etat]} » de ${n.auteur_nom ?? 'un membre du CS'}` +
				(n.commentaire ? ` — « ${n.commentaire} »` : '') +
				'\n\nLa suppression est définitive, et la moyenne du prestataire sera recalculée.',
			libelleConfirmer: 'Retirer l’avis',
			danger: true,
		});
		if (!ok) return;
		try {
			await prestApi.deleteNotation(n.id);
			toast('success', 'Avis retiré.');
			ouvert = null;
			dispatch('supprimee', n.id);
		} catch (e) {
			toast('error', messageErreur(e, 'Suppression impossible'));
		}
	}
</script>

{#if resume}
	<!--  Le BADGE de moyenne — il vivait dans la carte du prestataire avec ses
	      deux fonctions de calcul. Le rendre ici met la note et les avis qui la
	      composent au même endroit : c'est la même notion, vue de deux
	      distances. -->
	{#if moyenne !== null}
		<span class="not-badge badge" title="{fmtNombre(moyenne)}/5 ({nbAvis} avis)">
			{LIBELLE_ETAT[etatDeMoyenne(moyenne)]}{SEPARATEUR.point}{fmtNombre(moyenne)}/5
		</span>
	{/if}
{:else if exercices.length}
	<div class="not-liste">
		<span class="detail-label">Avis du conseil syndical ({notations.length})</span>
		{#each exercices as ex (ex.annee)}
			<div class="not-exercice">
				<button
					type="button"
					class="not-exercice-entete"
					aria-expanded={exerciceOuvert === ex.annee}
					on:click|stopPropagation={() =>
						(exerciceOuvert = basculerUn(exerciceOuvert ?? null, ex.annee))}
				>
					<span class="chevron" aria-hidden="true">{exerciceOuvert === ex.annee ? '▾' : '▸'}</span>
					<strong>Exercice {ex.libelle}</strong>
					<span class="not-exercice-nombre"
						>{fmtNombre(ex.nb_interventions)}
						{ex.nb_interventions > 1
							? 'interventions'
							: 'intervention'}{SEPARATEUR.point}{fmtNombre(ex.nb_notees)}
						{ex.nb_notees > 1 ? 'notées' : 'notée'}</span
					>
					<span class="not-exercice-compte">
						{#each ETATS as e (e)}
							{#if ex.compte[e]}
								<Badge teinte={TEINTE_ETAT[e]}>{fmtNombre(ex.compte[e])} {LIBELLE_ETAT[e]}</Badge>
							{/if}
						{/each}
					</span>
				</button>
				{#if exerciceOuvert === ex.annee}
					{#each lignes(ex) as l (l.cle)}
						<div class="not-item">
							<div class="not-entete">
								<span class="not-intervention">
									{#if l.date}<span class="not-date">{fmtDate(l.date)}</span>{SEPARATEUR.point}{/if}
									{#if l.ticketId !== null}
										<a href="/tickets/{l.ticketId}">{l.titre}</a>
									{:else}
										<span class="not-generaux">{l.titre}</span>
									{/if}
								</span>
								<span class="not-avis">
									{#each l.avis as n (n.id)}
										<button
											type="button"
											class="not-etat-bouton"
											aria-expanded={ouvert === n.id}
											aria-label="{LIBELLE_ETAT[n.etat]} — {ouvert === n.id
												? 'masquer'
												: 'afficher'} l’avis de {n.auteur_nom ?? 'un membre du CS'}"
											on:click|stopPropagation={() => (ouvert = basculerUn(ouvert, n.id))}
											><Badge teinte={TEINTE_ETAT[n.etat]}>{LIBELLE_ETAT[n.etat]}</Badge></button
										>
									{:else}
										<span class="not-non-notee">non notée</span>
									{/each}
								</span>
							</div>
							{#each l.avis as n (n.id)}
								{#if ouvert === n.id}
									<div class="not-detail">
										<div class="not-detail-entete">
											<span class="not-auteur">{n.auteur_nom ?? '—'}</span>
											<span class="not-date">{fmtDate(n.cree_le)}</span>
											{#if peutSupprimer}
												<button
													type="button"
													class="btn-icon-danger"
													title="Retirer cet avis"
													aria-label="Retirer l’avis de {n.auteur_nom ?? 'ce membre'}"
													on:click|stopPropagation={() => supprimer(n)}
													><IconeAction icone="trash-2" /></button
												>
											{/if}
										</div>
										{#if n.commentaire}
											<p class="not-commentaire">{n.commentaire}</p>
										{/if}
										{#if n.peut_modifier && prestataireId !== undefined}
											<GesteNoter
												{prestataireId}
												{prestataireNom}
												contratId={n.contrat_id ?? undefined}
												notation={n}
												on:modifie={(e) => dispatch('modifiee', e.detail)}
											/>
										{/if}
									</div>
								{/if}
							{/each}
						</div>
					{/each}
				{/if}
			</div>
		{/each}
	</div>
{/if}

<style>
	.not-badge {
		margin-left: 0.25rem;
		color: var(--color-warning-texte);
	}
	.not-liste {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		margin-top: 0.75rem;
	}
	.not-exercice {
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0 0.75rem;
	}
	.not-exercice-entete {
		width: 100%;
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 0.5rem;
		min-height: 44px;
		border: 0;
		background: none;
		padding: 0.4rem 0;
		text-align: left;
		color: inherit;
		font-family: inherit;
		cursor: pointer;
	}
	.not-exercice-nombre {
		color: var(--color-text-muted);
	}
	.not-exercice-compte {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem;
		margin-left: auto;
	}
	.not-item {
		border-top: 1px solid var(--color-border);
		padding: 0.4rem 0;
	}
	.not-entete {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
		font-size: var(--fs-md);
	}
	.not-intervention {
		flex: 1 1 12rem;
		min-width: 0;
	}
	.not-generaux {
		font-style: italic;
	}
	.not-avis {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem;
	}
	.not-etat-bouton {
		border: 0;
		background: none;
		padding: 0;
		cursor: pointer;
		min-height: 32px;
	}
	.not-non-notee {
		color: var(--color-text-muted);
	}
	.not-date {
		color: var(--color-text-muted);
		font-size: var(--fs-sm);
	}
	/*  L'avis déplié : SOUS sa ligne, sur toute la largeur — la correction s'y ouvre
	    sans se tasser entre la date et les boutons (15/11/2026). */
	.not-detail {
		margin-top: 0.4rem;
		padding: 0.5rem 0.75rem;
		border-radius: 0.5rem;
		background: var(--color-bg);
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
	}
	.not-detail-entete {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.not-detail-entete .not-date {
		margin-right: auto;
	}
	.not-auteur {
		font-weight: 600;
	}
	.not-commentaire {
		margin: 0;
		font-size: var(--fs-md);
		color: var(--color-text-muted);
		/*  Le commentaire vient d'un humain : les retours à la ligne comptent, et
		    il n'est PAS rendu en HTML — donc rien à assainir. */
		white-space: pre-wrap;
	}
</style>
