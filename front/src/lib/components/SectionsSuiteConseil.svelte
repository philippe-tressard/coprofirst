<!--
  SectionsSuiteConseil.svelte — ce que le CONSEIL pose dans une Suite 🔄, APRÈS
  le Suivi : Quand, Intervenant, et la planification qu'il envoie.

  ## Pourquoi (#1207, arbitré le 24/09/2026)

  Un membre du conseil qui n'est pas administrateur n'avait AUCUN chemin
  d'écran pour dater l'affaire d'un résident, désigner son intervenant ou son
  équipement : le crayon ne lui est pas montré (`droits.peutEditer`), et le
  serveur refuse qu'il réécrive le texte d'un autre. Ces sections sont pourtant
  les siennes (`inactivePour.resident`). Arbitré : « via la Suite » — chaque
  changement laisse sa trace au fil de l'affaire.

  ## Découpé à son rang (#1326, 25/09/2026)

  Il rendait aussi l'Équipement et la Mise en avant, d'un bloc, dans le créneau
  `specifiques` : l'Équipement passait après le Suivi, la Mise en avant avant le
  Périmètre. L'Équipement est désormais `SuiteConseilEquipement` (créneau
  `avant_suivi`), la Mise en avant `OptionsEvolutionTicket` (créneau
  `mise_en_avant`), et l'état qu'ils partagent vit dans `#lib/suite-conseil`.

  Les règles serveur sont celles de la correction (`utils/intervenant`,
  `_appliquer_quand`), appliquées par `add_evolution`.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import type { Writable } from 'svelte/store';
	import { prestataires as prestatairesApi, type Ticket } from '#lib/api/index.ts';
	import { essayer } from '#lib/chargement.ts';
	import { depuisChampLocal } from '#lib/date.ts';
	import { intervenantPropose } from '#lib/formulaire-affaire.ts';
	import type { ContratEnCours } from '#lib/prestataires.ts';
	import { isCS } from '#lib/stores/auth.ts';
	import { conseilDansLaSuite, equipementDansLaSuite, etatSuite } from '#lib/suite-conseil.ts';
	import SectionIntervenant from './SectionIntervenant.svelte';
	import SectionQuand from './SectionQuand.svelte';
	import { pliageDe } from '#lib/pliage.ts';
	import { TICKET } from '#lib/entites/ticket.ts';

	export let ticket: Ticket;
	export let premiere = false;
	export let partage: Writable<Record<string, unknown>>;
	/** Les options de la Suite : cette section n'y pose que `planification` — ce
	 *  qu'`optionsVersTicket` fait voyager. Le serveur ne change que ce qui diffère
	 *  de l'affaire : renvoyer une valeur inchangée est muet. Vide hors conseil. */
	export let options: {
		epingle: boolean;
		urgente: boolean;
		brouillon: boolean;
		suiviKanban: boolean;
		suiviActualite?: boolean;
		etatSuivi?: string | null;
		planification?: Record<string, unknown>;
	};

	const etat = etatSuite(partage, ticket);

	$: conseil = conseilDansLaSuite(ticket, $isCS);
	$: bati = equipementDansLaSuite(ticket, $isCS);

	let prestataires: { id: number; nom: string; actif?: boolean; specialite?: string | null }[] = [];
	let contrats: ContratEnCours[] = [];
	let erreur = '';

	onMount(async () => {
		if (!bati) return;
		[prestataires, erreur] = await essayer(prestatairesApi.list(), []);
		[contrats] = await essayer(prestatairesApi.contrats(), []);
	});

	//  L'équipement PROPOSE l'intervenant sous contrat, comme dans le formulaire.
	let equipementVu = $etat.equipement;
	$: if ($etat.equipement !== equipementVu) {
		equipementVu = $etat.equipement;
		const propose = intervenantPropose(
			$etat.equipement,
			contrats,
			prestataires,
			$etat.prestataireId,
		);
		if (propose)
			[$etat.prestataireId, $etat.contratId] = [propose.prestataireId, propose.contratId];
	}

	$: options.planification = !conseil
		? {}
		: {
				debut: depuisChampLocal($etat.debut),
				fin: depuisChampLocal($etat.fin),
				...(bati
					? {
							equipement: $etat.equipement || null,
							prestataire_id: $etat.prestataireId,
							contrat_id: $etat.contratId,
						}
					: {}),
			};
</script>

{#if conseil}
	<SectionQuand
		idPrefixe="suite-{ticket.id}-quand"
		{premiere}
		pliable={pliageDe(TICKET, 'quand')}
		bind:debut={$etat.debut}
		bind:fin={$etat.fin}
	/>
	{#if bati}
		<SectionIntervenant
			idPrefixe="suite-{ticket.id}"
			pliable={pliageDe(TICKET, 'intervenant')}
			equipement={$etat.equipement}
			{erreur}
			bind:prestataires
			bind:prestataireId={$etat.prestataireId}
			{contrats}
			bind:contratId={$etat.contratId}
		/>
	{/if}
{/if}
