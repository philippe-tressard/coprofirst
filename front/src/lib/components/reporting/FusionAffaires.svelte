<!--
  FUSIONNER des affaires liées du Suivi des affaires (#2083) — au point comme
  entre deux points, et depuis la correction d'une affaire (#2173, monté tel
  quel par `ModaleFusionAffaires`).

  S'ouvre DANS le tableau, sous l'en-tête du groupe (la correction s'ouvre à la
  place de l'objet, `ux-patterns` §14 ter). Trois temps :

  1. **Vérifier qui lirait quoi** (`POST /suivi-affaires/fusions/conciliation`) —
     la fusion verse les Suites des autres dans la principale, donc dans les yeux
     de tous ses lecteurs. Rien ne s'affiche si tout est possible.
  2. **Concilier** les affaires refusées pour fuite de lecture (27/10/2026) :
     l'écart, puis laisser hors de la fusion, inverser (l'autre absorbe),
     restreindre ou élargir — ces deux derniers confirmés par le nom de chaque
     personne concernée (`ConciliationFusion`). Sans affaire refusée, cette étape
     n'existe pas.
  3. À l'ouverture de la fusion, l'assistant propose le titre et la description de
     l'affaire qui absorbe les autres (`POST /suivi-affaires/fusions/proposition`)
     — ✨ puis ⏳ qui clignote pendant l'appel ; sans assistant prêt, le serveur
     compose la proposition sans lui. Le conseil relit, corrige, puis **Fusionner**.

  Arbitré le 20/10/2026 : **la plus ancienne absorbe** — elle garde son numéro et
  reste ouverte ; les autres lui sont rattachées (Suites, pièces jointes,
  courriels). Seule la conciliation « inverser » en décide autrement. Une fusion
  ne se défait pas : la boîte le dit.
-->
<script lang="ts">
	import { onMount, tick } from 'svelte';
	import SectionDescription from '#lib/components/SectionDescription.svelte';
	import EtapeConciliationFusion from './EtapeConciliationFusion.svelte';
	import { TICKET } from '#lib/entites/ticket.ts';
	import { pliageDe } from '#lib/pliage.ts';
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';
	import EtoileRequis from '#lib/components/EtoileRequis.svelte';
	import EtatListe from '#lib/components/EtatListe.svelte';
	import IconeIA from '#lib/components/IconeIA.svelte';
	import { toast } from '#lib/components/Toast.svelte';
	import { messageErreur } from '#lib/erreurs.ts';
	import { suiviAffaires, type CandidateFusion } from '#lib/api/index.ts';
	import {
		choixPourServeur,
		conciliable,
		decisionIncomplete,
		decisionPrete,
		principaleInversee,
		type Decisions,
	} from '#lib/fusion-conciliation.ts';
	import type { AffaireAFusionner, FusionFaite } from '#lib/fusion-affaires.ts';

	/**  Les affaires du groupe, la plus ancienne en tête : elle absorbe. Une
	 *   affaire du Suivi, ou une affaire liée depuis sa correction (#2173). */
	export let affaires: AffaireAFusionner[];
	/**  La fusion est faite : la vue relit le suivi — la correction, elle, lit
	 *   la principale, l'affaire corrigée ayant pu être absorbée. */
	export let onFusionne: (r: FusionFaite) => void;
	export let onAnnule: () => void;

	let titre = '';
	let description = '';
	let assisteIA = false;
	let proposition = true;
	let enCours = false;
	let etape: 'verification' | 'conciliation' | 'fusion' = 'verification';
	/** Le verdict du serveur sur chaque autre affaire du groupe. */
	let verdicts: CandidateFusion[] = [];
	let decisions: Decisions = {};

	const verdictDe = (id: number) => verdicts.find((v) => v.id === id);
	/** Celles que le serveur n'a pas jugées (closes, déjà absorbées…) vont au serveur, qui tranchera. */
	$: autres = affaires.slice(1);
	$: refusees = verdicts.filter((v) => !v.fusionnable && conciliable(v));
	$: horsFusion = verdicts.filter((v) => !v.fusionnable && !conciliable(v));
	$: retenues = autres.filter((a) => {
		const v = verdictDe(a.id);
		return !v || v.fusionnable || decisionPrete(v, decisions[a.id]);
	});
	$: inverseeId = principaleInversee(refusees, decisions);
	$: membres = inverseeId
		? [
				affaires.find((a) => a.id === inverseeId)!,
				affaires[0],
				...retenues.filter((a) => a.id !== inverseeId),
			]
		: [affaires[0], ...retenues];
	$: ids = membres.map((a) => a.id);
	$: principale = membres[0];
	$: incomplet = refusees.some((v) => decisionIncomplete(v, decisions[v.id]));
	$: assez = membres.length >= 2;

	async function proposer() {
		proposition = true;
		try {
			const p = await suiviAffaires.fusions.proposer(ids);
			titre = p.titre;
			description = p.description;
			assisteIA = p.assiste_ia;
		} catch (e) {
			toast('error', messageErreur(e, 'Proposition impossible'));
			titre ||= membres.map((a) => a.titre).join(' / ');
		} finally {
			proposition = false;
		}
	}

	/**  Qui lirait quoi : un contrôle qui ne peut pas s'exécuter ne vaut pas « tout va
	 *   bien » — sans verdict, on ne propose pas de fusionner. */
	async function verifier() {
		try {
			verdicts = await suiviAffaires.fusions.conciliation(affaires.map((a) => a.id));
		} catch (e) {
			toast('error', messageErreur(e, 'Impossible de vérifier qui lirait ces affaires'));
			onAnnule();
			return;
		}
		if (verdicts.every((v) => v.fusionnable)) await ouvrirFusion();
		else etape = 'conciliation';
	}

	async function ouvrirFusion() {
		etape = 'fusion';
		await tick(); // `ids` suit les décisions et les verdicts : la proposition lit les derniers
		await proposer();
	}

	async function fusionner() {
		if (!titre.trim()) return;
		enCours = true;
		try {
			const r = await suiviAffaires.fusions.fusionner(ids, titre.trim(), description, {
				...(inverseeId ? { principale_id: inverseeId } : {}),
				conciliations: choixPourServeur(refusees, decisions),
			});
			toast('success', `${membres.length} affaires fusionnées dans ${principale.numero}`);
			onFusionne(r);
		} catch (e) {
			toast('error', messageErreur(e, 'Fusion impossible'));
		} finally {
			enCours = false;
		}
	}

	onMount(verifier);
</script>

{#if etape === 'verification'}
	<EtatListe chargement messageChargement="Vérification de qui lirait ces affaires…" />
{:else if etape === 'conciliation'}
	<EtapeConciliationFusion
		numeroPrincipale={affaires[0].numero}
		{refusees}
		{horsFusion}
		bind:decisions
		{incomplet}
		{assez}
		onContinuer={ouvrirFusion}
		{onAnnule}
	/>
{:else}
	<form class="fusion" on:submit|preventDefault={fusionner}>
		<p class="aide">
			Fusionnez seulement les affaires qui portent le <strong>même besoin</strong>.
			<strong>{principale.numero}</strong>{inverseeId ? '' : ', la plus ancienne,'} absorbe
			{membres
				.slice(1)
				.map((a) => a.numero)
				.join(', ')} : leurs suites, pièces jointes et courriels la rejoignent, et elle reste ouverte.
			Une fusion ne se défait pas.
		</p>
		{#if proposition}
			<EtatListe chargement messageChargement="L’assistant propose un titre et une description…" />
		{:else}
			<div class="field">
				<label for="fusion-titre-{principale.id}"
					>Titre de l’affaire fusionnée<EtoileRequis vide={!titre.trim()} /></label
				>
				<input id="fusion-titre-{principale.id}" type="text" maxlength="200" bind:value={titre} />
			</div>
			<SectionDescription
				pliable={pliageDe(TICKET, 'description')}
				idPrefixe="fusion-{principale.id}"
				hauteur="14rem"
				bind:valeur={description}
				{assisteIA}
			/>
			<div class="rangee">
				<button
					type="button"
					class="btn btn-sm btn-outline"
					disabled={proposition}
					aria-busy={proposition}
					on:click={proposer}
				>
					<IconeIA enCours={proposition} /> Nouvelle proposition
				</button>
			</div>
		{/if}
		<PiedFormulaire petit {enCours} desactive={proposition || !titre.trim()} on:annule={onAnnule} />
	</form>
{/if}

<style>
	.fusion {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		padding: 0.5rem 0 0.25rem;
	}
	.rangee {
		display: flex;
		justify-content: flex-start;
	}
</style>
