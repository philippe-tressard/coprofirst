<!--
  SyntheseFil.svelte — la synthèse d'une affaire close, côté FIL (#1643).

  Ce que le fil d'une affaire close demande au serveur — la synthèse lisible,
  et si l'on peut en produire une —, puis ce qu'il en montre au-dessus de
  l'Historique : le bouton « 🧾 Produire la synthèse » (le conseil, affaire
  close sans synthèse — toute catégorie depuis le 21/10/2026) ou la mention qu'elle est en préparation.

  🔴 Il est monté par les DEUX rendus du fil, la fiche (`HistoriqueTicket`) et la
  carte dépliée de la liste (`CarteTicket`), qui ne partagent pas leur câblage.
  Livré d'abord dans la seule fiche (v2.99.0), le bouton manquait à la liste et
  la Suite y paraissait vide — trouvé à l'écran par l'utilisateur, pas par un
  contrôle.

  🧾 Il rend AUSSI la synthèse elle-même, en bloc au-dessus du fil (15/10/2026,
  maquette A de la carte dépliée). Elle se rendait dans le créneau `synthese` de
  `RubriqueHistorique`, à la date de sa Suite — câblé deux fois, à l'identique,
  par la carte et par la fiche. Le fil ne raconte plus cette Suite sans texte
  (`entreesDuFil`) : elle est la conclusion de l'affaire, pas une étape.
-->
<script lang="ts">
	import IconeIA from '#lib/components/IconeIA.svelte';
	import { createEventDispatcher } from 'svelte';
	import {
		syntheses,
		type EtatSynthese,
		type SyntheseAffaire as SyntheseLue,
		type Ticket,
	} from '#lib/api/index.ts';
	import { fmtDate } from '#lib/date.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { isCS } from '#lib/stores/auth.ts';
	import { fmtJours } from '#lib/synthese.ts';
	import { estTicketClos } from '#lib/tickets.ts';
	import EtatListe from './EtatListe.svelte';
	import RubriqueEtape from './RubriqueEtape.svelte';
	import SyntheseAffaire from './SyntheseAffaire.svelte';
	import { toast } from './Toast.svelte';

	export let ticket: Pick<Ticket, 'id' | 'statut'> | null;
	/** Le fil : relu à chaque écriture, il fait relire la synthèse avec lui. */
	export let evolutions: unknown[] = [];
	/** La rubrique est-elle dépliée ? L'accordéon est tenu par la carte. */
	export let ouverte = false;
	export let onBasculer: () => void;
	/** L'état lu : la synthèse lisible, et ce que le conseil peut en faire. */
	let etat: EtatSynthese | null = null;

	const dispatch = createEventDispatcher<{ change: void }>();

	let erreur = '';
	let enCours = false;
	$: cle = ticket && estTicketClos(ticket.statut) ? `${ticket.id}:${evolutions.length}` : null;
	$: if (cle) recharger();
	$: if (!cle) etat = null;

	async function recharger() {
		if (!ticket) return;
		erreur = '';
		try {
			etat = await syntheses.lire(ticket.id);
		} catch (e) {
			etat = null;
			erreur = messageErreur(e);
		}
	}

	$: produisible = $isCS && !!etat?.produisible;
	$: enAttente = $isCS && !produisible && !!etat?.en_attente;
	$: visible = !!etat?.synthese || produisible || enAttente;
	$: resume = resumeSynthese(etat?.synthese ?? null, produisible, enAttente);

	/** PURE. La ligne de la rubrique pliée : l'état, jamais l'invitation. */
	function resumeSynthese(s: SyntheseLue | null, aProduire: boolean, attendue: boolean): string {
		if (s?.statut === 'validee') {
			const duree = s.metriques?.duree_totale;
			return [
				s.validee_le ? `Validée le ${fmtDate(s.validee_le)}` : 'Validée',
				duree != null ? `affaire close en ${fmtJours(duree)}` : '',
			]
				.filter(Boolean)
				.join(' · ');
		}
		if (s) return 'Brouillon à relire, puis valider';
		if (attendue) return 'En préparation';
		return aProduire ? 'À produire' : '';
	}

	async function produire() {
		if (!ticket) return;
		enCours = true;
		try {
			await syntheses.produire(ticket.id);
			dispatch('change');
			toast('success', 'Synthèse produite — à relire, puis valider');
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			enCours = false;
		}
	}
</script>

<EtatListe compact {erreur} />
<!--  🧾 La DERNIÈRE rubrique de la carte (maquette G, 16/10/2026) : la conclusion
      de l'affaire se lit après ce qui s'y est passé. Pliée, elle dit son état
      sur une ligne — validée et en combien de jours, ou ce qui reste à faire. -->
{#if visible}
	<RubriqueEtape titre="La synthèse" icone="file-text" ton="succes" {resume} {ouverte} {onBasculer}>
		{#if produisible}
			<div class="synthese-fil">
				<button
					class="btn btn-outline btn-sm"
					disabled={enCours}
					aria-busy={enCours}
					on:click={produire}
					><IconeIA {enCours} />
					{enCours ? 'Rédaction…' : 'Produire la synthèse'}</button
				>
			</div>
		{:else if enAttente}
			<p class="aide">
				La synthèse de l’affaire est en préparation : elle paraîtra ici sous quarante minutes.
			</p>
		{/if}
		{#if etat?.synthese}
			<SyntheseAffaire
				synthese={etat.synthese}
				gestes={$isCS}
				titre={false}
				on:change={recharger}
			/>
		{/if}
	</RubriqueEtape>
{/if}

<style>
	.synthese-fil {
		display: flex;
		justify-content: flex-end;
	}
</style>
