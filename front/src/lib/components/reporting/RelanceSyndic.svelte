<!--
  Le mode « Relancer le syndic » du Suivi des affaires (#2035, maquette 3b).

  Il a remplacé la vue « Relance syndic » du reporting, qui listait les mêmes
  affaires sous une autre règle (elle en comptait cinq de moins), par cartes,
  sans âge, sans date d'ouverture ni résumé — et sans dire quand les relances
  précédentes étaient parties.

  - **À relancer** : les affaires sans avancée depuis le délai réglé, cochées
    d'office, la plus ancienne en tête ;
  - **Moins de N jours sans avancée** : pliée, rien de coché ;
  - **l'aperçu** de ce que le courriel dira de chaque affaire cochée, puis l'envoi ;
  - au-dessus, les **réponses du syndic** aux relances précédentes.

  La liste est celle du Suivi : le parent la charge (`GET /suivi-affaires`) et la
  recharge après l'envoi. La règle « à relancer » vient du serveur (`a_relancer`).
-->
<script lang="ts">
	import { tickets as ticketsApi, type SuiviAffaires } from '#lib/api/index.ts';
	import { confirmer } from '#lib/confirmation.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { toast } from '#lib/components/Toast.svelte';
	import SectionRepliee from '#lib/components/SectionRepliee.svelte';
	import TableauAffaires from './TableauAffaires.svelte';
	import ApercuRelance from './ApercuRelance.svelte';
	import ReponsesSyndic from './ReponsesSyndic.svelte';
	import { SEPARATEUR } from '#lib/separateurs.ts';

	export let suivi: SuiviAffaires;
	/** Appelé après un envoi réussi : le parent recharge la liste. */
	export let onEnvoyee: () => void;

	let choisies: Set<number> = new Set();
	let envoi = false;

	$: aRelancer = suivi.affaires.filter((a) => a.a_relancer);
	$: enAttente = suivi.affaires.filter((a) => !a.a_relancer);
	//  Cochées d'office à chaque relevé : un rechargement après l'envoi repart de
	//  la règle, pas de la sélection d'avant.
	$: choisies = new Set(suivi.affaires.filter((a) => a.a_relancer).map((a) => a.id));
	$: cochees = suivi.affaires.filter((a) => choisies.has(a.id));
	$: delai = suivi.delai_jours;

	async function envoyer() {
		const ids = cochees.map((a) => a.id);
		if (!ids.length) return;
		if (!(await confirmer(`Envoyer la relance au syndic pour ${ids.length} affaire(s) ?`))) return;
		envoi = true;
		try {
			const res = await ticketsApi.envoiRelance(ids);
			toast('success', `✅ Relance envoyée à ${res.relance_to}`);
			onEnvoyee();
		} catch (e) {
			toast('error', messageErreur(e, 'Erreur envoi relance'));
			//  Le serveur refuse une affaire close, archivée ou fusionnée depuis
			//  l'ouverture de l'écran : la liste rechargée ne la propose plus.
			onEnvoyee();
		} finally {
			envoi = false;
		}
	}
</script>

<div class="relance">
	<ReponsesSyndic />

	<section class="report-card groupe" aria-labelledby="titre-a-relancer">
		<h3 id="titre-a-relancer" class="groupe-titre">
			À relancer{SEPARATEUR.tiret}{aRelancer.length} affaire{aRelancer.length > 1 ? 's' : ''} sans avancée
			depuis
			{delai} jours ou plus
		</h3>
		{#if aRelancer.length}
			<TableauAffaires affaires={aRelancer} relance bind:choisies />
		{:else}
			<p class="vide">Aucune affaire ne dépasse le délai de {delai} jours pour l’instant.</p>
		{/if}
	</section>

	{#if enAttente.length}
		<SectionRepliee titre="Moins de {delai} jours sans avancée" compte={enAttente.length} enSerie>
			<TableauAffaires affaires={enAttente} relance bind:choisies />
		</SectionRepliee>
	{/if}

	<ApercuRelance affaires={cochees} {envoi} onEnvoyer={envoyer} />
</div>

<style>
	.relance {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}
	.groupe {
		background: var(--color-surface);
	}
	.groupe-titre {
		font-family: inherit;
		font-size: var(--fs-base);
		margin: 0 0 0.5rem;
	}
	.vide {
		margin: 0;
		color: var(--color-text-muted);
	}
</style>
