<!--
  Le POINT CONSEIL SYNDICAL / SYNDIC d'un mode du Suivi des affaires (#2041,
  maquette A1) : le bandeau du Quand, du Où et du Qui, au-dessus du tableau.

  - Sans point : « Ouvrir un point CS / Syndic ». Le formulaire part de la
    REPRISE quand un point d'un autre mode a été ouvert il y a moins de deux
    heures (le serveur la propose), sinon de maintenant, sur place.
  - Point en cours : le bandeau en deux lignes, ✏️ pour le corriger, puis
    « Terminer le point » (le CR passe à valider, les non traitées se figent)
    ou « Abandonner » (ouvert par erreur).
  - Point à valider ou validé : le bandeau, sa validation (`ValidationPoint`,
    #2042), et « Ouvrir un nouveau point ».
  - L'ancre `point-cs-N` est celle du fil : il y mène, une fois le CR validé.
  - Le PDF du point se tire par « Exporter en PDF » de la barre d'outils, à
    tout instant (#2089 : l'« Aperçu PDF » du bandeau est retiré).

  Le compte rendu de chaque affaire se saisit dans le tableau
  (`SaisieCrAffaire`) ; ce composant tient le point et le rend à la vue par
  `compteRendu`, qu'elle lit pour le tableau et le CR global.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import Badge from '#lib/components/Badge.svelte';
	import Icon from '#lib/components/Icon.svelte';
	import IconeAction from '#lib/components/IconeAction.svelte';
	import EtatListe from '#lib/components/EtatListe.svelte';
	import FormulairePoint from './FormulairePoint.svelte';
	import ValidationPoint from './ValidationPoint.svelte';
	import { toast } from '#lib/components/Toast.svelte';
	import { confirmer } from '#lib/confirmation.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import {
		pointsConseil,
		type CompteRenduPoint,
		type ModePoint,
		type ParticipantsPoint,
		type PointEntree,
		type ReprisePoint,
	} from '#lib/api/index.ts';
	import { champLocalMaintenant, fmtDatetime, fmtTime } from '#lib/date.ts';
	import { ETATS_POINT, entreesDepuisPresents, moyenDe, nomPresent } from '#lib/points-conseil.ts';

	export let mode: ModePoint;
	/** Le point du mode et son CR global — lu par la vue (tableau, CR global). */
	export let compteRendu: CompteRenduPoint | null = null;
	/** L'annuaire, les lieux et les états à la validation — lus aussi par la saisie d'un CR. */
	export let participants: ParticipantsPoint | null = null;
	let reprise: ReprisePoint | null = null;
	let chargement = true;
	let erreur = '';
	let formulaire: 'ouvrir' | 'corriger' | null = null;
	let enCours = false;

	$: point = compteRendu?.point ?? null;
	$: enSaisie = point?.etat === 'en_cours';

	async function charger() {
		try {
			const [courant, annuaire] = await Promise.all([
				pointsConseil.courant(mode),
				pointsConseil.participants(),
			]);
			compteRendu = courant.compte_rendu;
			reprise = courant.reprise;
			participants = annuaire;
		} catch (e) {
			erreur = messageErreur(e, 'Chargement impossible');
		} finally {
			chargement = false;
		}
	}

	/** Relire le point après un geste de validation. */
	async function relire() {
		compteRendu = (await pointsConseil.courant(mode)).compte_rendu;
	}

	/** Ce que le formulaire propose à l'ouverture : la reprise, sinon maintenant. */
	function proposition(): PointEntree {
		if (reprise)
			return {
				debut: reprise.debut,
				fin: reprise.fin,
				moyen: moyenDe(reprise),
				lieu: reprise.lieu,
				presents: entreesDepuisPresents(reprise.presents),
			};
		return {
			debut: champLocalMaintenant(),
			fin: null,
			moyen: participants?.moyens[0]?.cle ?? 'sur_place',
			lieu: participants?.lieux[0]?.adresse ?? null,
			presents: [],
		};
	}

	function actuel(): PointEntree {
		const cr = compteRendu as CompteRenduPoint;
		return {
			debut: cr.point.debut,
			fin: cr.point.fin,
			moyen: moyenDe(cr.point),
			lieu: cr.point.lieu,
			presents: entreesDepuisPresents(cr.presents),
		};
	}

	async function enregistrer(entree: PointEntree) {
		enCours = true;
		try {
			compteRendu =
				formulaire === 'corriger' && point
					? await pointsConseil.corriger(point.id, entree)
					: await pointsConseil.ouvrir(mode, entree);
			formulaire = null;
		} catch (e) {
			toast('error', messageErreur(e, 'Enregistrement impossible'));
		} finally {
			enCours = false;
		}
	}

	async function terminer() {
		if (!point) return;
		const n = compteRendu?.non_traitees.length ?? 0;
		const ok = await confirmer({
			titre: 'Terminer le point',
			message:
				(n
					? `${n} affaire${n > 1 ? 's' : ''} sans compte rendu ${n > 1 ? 'seront listées' : 'sera listée'} comme non traitée${n > 1 ? 's' : ''}. `
					: '') +
				'Le compte rendu part aux présents du conseil et du syndic pour validation ; sans réponse de tous, il sera validé dans 7 jours.',
			libelleConfirmer: 'Terminer',
		});
		if (!ok) return;
		try {
			compteRendu = await pointsConseil.terminer(point.id);
		} catch (e) {
			toast('error', messageErreur(e, 'Impossible de terminer le point'));
		}
	}

	async function abandonner() {
		if (!point) return;
		const ok = await confirmer({
			titre: 'Abandonner le point',
			message: 'Le point et les comptes rendus déjà saisis seront effacés.',
			libelleConfirmer: 'Abandonner',
			danger: true,
		});
		if (!ok) return;
		try {
			await pointsConseil.abandonner(point.id);
			compteRendu = null;
		} catch (e) {
			toast('error', messageErreur(e, 'Impossible d’abandonner le point'));
		}
	}

	onMount(charger);
</script>

<section
	class="report-card point"
	id="point-cs-{point ? point.id : 'aucun'}"
	aria-labelledby="titre-point-{mode}"
>
	{#if chargement || erreur || !participants}
		<EtatListe
			{chargement}
			{erreur}
			messageChargement="Chargement du point…"
			titreErreur="Impossible d’afficher le point CS / Syndic"
		/>
	{:else}
		<div class="tete">
			<h3 id="titre-point-{mode}"><Icon name="users" size={16} /> Point CS / Syndic</h3>
			{#if point && formulaire !== 'ouvrir'}
				<Badge teinte={ETATS_POINT[point.etat].teinte}>{ETATS_POINT[point.etat].libelle}</Badge>
			{/if}
			<span class="actions">
				{#if enSaisie}
					<button
						type="button"
						class="btn-icon"
						aria-pressed={formulaire === 'corriger'}
						aria-label="Corriger le quand, le où et le qui"
						on:click={() => (formulaire = formulaire === 'corriger' ? null : 'corriger')}
						><IconeAction icone="pencil" /></button
					>
				{/if}
			</span>
		</div>

		{#if formulaire}
			<FormulairePoint
				idPrefixe="point-{mode}"
				{participants}
				initial={formulaire === 'corriger' ? actuel() : proposition()}
				reprise={formulaire === 'ouvrir' && reprise
					? `Repris du point de ${fmtTime(reprise.debut)}, ouvert il y a moins de deux heures : même réunion, à corriger si besoin.`
					: ''}
				{enCours}
				onEnregistre={enregistrer}
				onAnnule={() => (formulaire = null)}
			/>
		{:else if point && compteRendu}
			<p class="ligne">
				<Icon name="calendar" size={14} />
				{fmtDatetime(point.debut)}{#if point.fin}&nbsp;→ {fmtTime(point.fin)}{/if}
				<span class="sep">·</span>
				<Icon name={point.a_distance ? 'globe' : 'building-2'} size={14} />
				{point.ou}
			</p>
			<p class="ligne">
				<Icon name="users" size={14} />
				{#each compteRendu.presents as p, i (p.id)}{i ? ', ' : ''}{nomPresent(p)}{/each}
				{#if !compteRendu.presents.length}<span class="muet">Aucun présent indiqué</span>{/if}
			</p>
			{#if !enSaisie}
				<ValidationPoint {compteRendu} onChange={relire} />
			{/if}
			<div class="gestes">
				{#if enSaisie}
					<span class="muet">Ouvrez une affaire du tableau pour en saisir le compte rendu.</span>
					<button type="button" class="btn btn-sm btn-outline" on:click={abandonner}>
						Abandonner
					</button>
					<button type="button" class="btn btn-sm btn-primary" on:click={terminer}>
						<IconeAction icone="check" /> Terminer le point
					</button>
				{:else}
					<button
						type="button"
						class="btn btn-sm btn-outline"
						on:click={() => (formulaire = 'ouvrir')}
					>
						<IconeAction icone="plus" /> Ouvrir un nouveau point
					</button>
				{/if}
			</div>
		{:else}
			<div class="gestes">
				<span class="muet">
					Pendant une réunion avec le syndic, prenez le compte rendu en direct, affaire par affaire.
				</span>
				<button
					type="button"
					class="btn btn-sm btn-primary"
					on:click={() => (formulaire = 'ouvrir')}
				>
					<IconeAction icone="plus" /> Ouvrir un point CS / Syndic
				</button>
			</div>
		{/if}
	{/if}
</section>

<style>
	.point {
		margin-bottom: 0.75rem;
	}
	.tete {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
	}
	.tete h3 {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		margin: 0;
	}
	.actions {
		margin-left: auto;
	}
	.ligne {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.3rem;
		margin: 0 0 0.25rem;
		font-size: var(--fs-sm);
	}
	.sep,
	.muet {
		color: var(--color-text-muted);
	}
	.gestes {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: flex-end;
		gap: 0.5rem;
		margin-top: 0.5rem;
	}
	.gestes .muet {
		margin-right: auto;
		font-size: var(--fs-sm);
	}
</style>
