<!--
  L'onglet **Télémétrie** de l'administration : qui utilise quoi, et quand.

  POURQUOI CE COMPOSANT (19/08/2026). Les sept écrans d'administration qui
  vivaient sur leur propre route sont devenus des onglets — pour qu'on n'en sorte
  plus, donc sans bouton « ← Retour ». Leur aiguillage ajoutait 53 lignes à
  `admin/+page.svelte`, déjà à 1 786, et le garde-fou de modularité (rang 1) l'a
  refusé. Troisième extraction du même patron, après `OngletWhatsApp` et `OngletSmtp`.

  ## Quatre vues, quatre sections, un filtre (03/10/2026)

  - **Vues** : Jour · Mois (30 j) · Année (12 derniers mois) · Total (par année,
    10 ans). « Année (10 ans) » est devenue Total ; Année lit douze mois.
  - **Sections pliables**, un seul dépliée à la fois — l'accordéon natif des
    `<details>` (`#lib/accordeon`, posé par le layout) replie les autres et
    ramène le haut de la section ouverte à l'écran. L'état vit ICI
    (`sectionOuverte`), comme dans `OngletIA` : il survit au changement de vue,
    qui recharge tout. À l'arrivée : **Indicateurs et fréquentation** (nombres
    clés, graphe, top pages, utilisateurs actifs). Une section VIDE ne se déplie pas (`PanneauTelemetrie`).
  - **« Qui vient » suit la vue** : aujourd'hui, 30 jours, 12 mois ; en Total,
    personne ne sait plus qui est venu, la section est vide.
  - **Filtre « sans le gestionnaire du site »** : une case à cocher, sur la même
    ligne que les vues, proposée par le serveur seulement s'il changerait quelque chose
    (`filtre_gestionnaire.propose`) ; décochée à l'ouverture. Quand c'est faute de
    gestionnaire désigné, une ligne le dit — la seule cause qu'on peut corriger.
    Les erreurs et les durées, sans compte, ne bougent pas.
-->
<script lang="ts">
	import { admin as adminApi } from '#lib/api/index.ts';
	import type { FiltreGestionnaire, PorteeTelemetrie, TableauTelemetrie } from '#lib/api/index.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { fmtDate } from '#lib/date.ts';
	import Icon from '#lib/components/Icon.svelte';
	import FrequentationTelemetrie from '#lib/components/FrequentationTelemetrie.svelte';
	import ErreursNavigateur from '#lib/components/ErreursNavigateur.svelte';
	import DureesAffichage from '#lib/components/DureesAffichage.svelte';
	import QuiVient from '#lib/components/QuiVient.svelte';
	import RetourComptes from '#lib/components/RetourComptes.svelte';
	import GestesAboutis from '#lib/components/GestesAboutis.svelte';
	import ArriveesNotification from '#lib/components/ArriveesNotification.svelte';
	import Pastille from '#lib/components/Pastille.svelte';
	import EtatListe from '#lib/components/EtatListe.svelte';

	let telemetryData: TableauTelemetrie | null = null;
	let telemetryLoading = true;
	/**  🔴 Non vide = on n'a PAS pu regarder (#816).
	 *
	 *   Le `catch` de cette fonction faisait `telemetryData = null` : une session
	 *   expirée, un 500 ou une coupure réseau produisaient EXACTEMENT l'écran
	 *   d'une résidence que personne ne consulte — « Les données apparaîtront
	 *   après les premières visites ». C'est le `.catch(() => [])` de #519 mot
	 *   pour mot, sur le seul écran qui sert à savoir si le site est lu. */
	let telemetryErreur = '';
	let tlScope: PorteeTelemetrie = 'jour';
	let filtre: FiltreGestionnaire = 'avec';

	const VUES: { code: PorteeTelemetrie; libelle: string }[] = [
		{ code: 'jour', libelle: 'Jour' },
		{ code: 'mois', libelle: 'Mois (30 j)' },
		{ code: 'annee', libelle: 'Année (12 mois)' },
		{ code: 'total', libelle: 'Total (10 ans)' },
	];
	/** Ce que couvrent les panneaux tirés du détail (erreurs, durées) : le jour
	 *  même, sinon leurs 30 jours de conservation — l'année n'en a pas plus. */
	$: periodeDetail = tlScope === 'jour' ? 'aujourd’hui' : '30 derniers jours';
	$: libelleVues =
		tlScope === 'jour'
			? "Pages vues aujourd'hui"
			: tlScope === 'mois'
				? 'Pages vues (30 j)'
				: tlScope === 'annee'
					? 'Pages vues (12 mois)'
					: 'Pages vues (total)';

	//  L'ACCORDÉON : une section dépliée à la fois, l'état tenu ici (cf. OngletIA).
	//  « frequentation » à l'arrivée : c'est ce qu'on vient lire le plus souvent.
	type Section =
		'frequentation' | 'erreurs' | 'qui-vient' | 'retour' | 'gestes' | 'arrivees' | 'durees';
	let sectionOuverte: Section | null = 'frequentation';
	function basculerSection(code: Section, ouvert: boolean) {
		if (ouvert) sectionOuverte = code;
		else if (sectionOuverte === code) sectionOuverte = null;
	}

	export async function loadTelemetry() {
		telemetryLoading = true;
		telemetryErreur = '';
		try {
			telemetryData = await adminApi.telemetryDashboard(tlScope, filtre);
			//  Le serveur peut avoir appliqué « avec » à un « sans » qui ne
			//  changerait rien : les pastilles disent ce qui est APPLIQUÉ.
			filtre = telemetryData.filtre_gestionnaire.applique;
		} catch (e) {
			//  La donnée précédente est écartée : l'afficher sous un onglet dont
			//  la portée vient de changer la ferait passer pour la nouvelle.
			telemetryData = null;
			telemetryErreur = messageErreur(e, 'Statistiques indisponibles pour le moment.');
		} finally {
			telemetryLoading = false;
		}
	}

	function switchTlScope(s: PorteeTelemetrie) {
		tlScope = s;
		loadTelemetry();
	}

	//  Le serveur ne PROPOSE « sans » que s'il écarterait quelque chose.
	$: filtrePropose = telemetryData?.filtre_gestionnaire.propose ?? false;

	function switchFiltre(f: FiltreGestionnaire) {
		filtre = f;
		loadTelemetry();
	}

	//  L'onglet ne se rend que lorsqu'il est choisi : charger au montage suffit, et
	//  évite à la page d'avoir à déclencher l'appel depuis son bouton.
	loadTelemetry();
</script>

<section class="card config-section">
	<h2 class="config-section-title">
		<Icon name="bar-chart-3" size={17} />Télémétrie — Utilisation de l'application
	</h2>
	<p class="aide">Statistiques d'utilisation : qui utilise quoi et quand.</p>

	<!-- Sélecteur de vue (Jour / Mois / Année / Total) ET filtre gestionnaire, sur
	     la MÊME ligne au bureau (elle se replie sur mobile). Le filtre est UNE case
	     à cocher, pas deux pastilles : c'est un interrupteur, et deux pastilles
	     doublaient la largeur de la barre (03/10/2026). Il n'est là que si le serveur le propose — un
	     gestionnaire désigné, qui a des vues sur la vue consultée, et d'autres que
	     lui : sinon « sans » n'écarterait rien. -->
	<div class="tl-barre">
		<div class="tl-scope-switch">
			{#each VUES as v (v.code)}
				<Pastille active={tlScope === v.code} on:click={() => switchTlScope(v.code)}
					>{v.libelle}</Pastille
				>
			{/each}
		</div>
		{#if filtrePropose}
			<label class="checkbox-field tl-filtre">
				<input
					type="checkbox"
					checked={filtre === 'sans'}
					on:change={(e) => switchFiltre(e.currentTarget.checked ? 'sans' : 'avec')}
				/>
				Sans le gestionnaire du site
			</label>
		{/if}
	</div>
	{#if telemetryData && !telemetryData.filtre_gestionnaire.gestionnaire_designe}
		<p class="aide">
			Aucun gestionnaire du site n’est désigné (Copropriété › Fonctionnement) : le filtre « sans le
			gestionnaire du site » n’a donc rien à écarter.
		</p>
	{/if}
	{#if filtre === 'sans' && telemetryData}
		<p class="aide">
			Les vues du gestionnaire du site sont écartées des indicateurs, du graphe, des pages, des
			utilisateurs, de « Qui vient » et des arrivées par notification. Les erreurs, les gestes et
			les durées d’affichage, sans compte, ne changent pas.
			{#if telemetryData.filtre_gestionnaire.non_distingue_jusqu_au}
				Jusqu’au {fmtDate(telemetryData.filtre_gestionnaire.non_distingue_jusqu_au)}, les agrégats
				ne distinguaient pas le gestionnaire : ses vues y restent comptées.
			{/if}
		</p>
	{/if}

	<EtatListe
		chargement={telemetryLoading}
		erreur={telemetryErreur}
		vide={!telemetryData}
		messageChargement="Chargement des statistiques…"
		titreErreur="Impossible d’afficher les statistiques"
		titreVide="Aucune donnée de télémétrie"
		messageVide="Les données apparaîtront après les premières visites."
	>
		{#if telemetryData}
			<FrequentationTelemetrie
				donnees={telemetryData}
				{libelleVues}
				ouvert={sectionOuverte === 'frequentation'}
				on:basculer={(e) => basculerSection('frequentation', e.detail)}
			/>
			<ErreursNavigateur
				erreurs={telemetryData.erreurs}
				periode={periodeDetail}
				ouvert={sectionOuverte === 'erreurs'}
				on:basculer={(e) => basculerSection('erreurs', e.detail)}
			/>
			<QuiVient
				adoption={telemetryData.adoption}
				ouvert={sectionOuverte === 'qui-vient'}
				on:basculer={(e) => basculerSection('qui-vient', e.detail)}
			/>
			<RetourComptes
				retour={telemetryData.retour}
				ouvert={sectionOuverte === 'retour'}
				on:basculer={(e) => basculerSection('retour', e.detail)}
			/>
			<GestesAboutis
				gestes={telemetryData.gestes}
				periode={periodeDetail}
				ouvert={sectionOuverte === 'gestes'}
				on:basculer={(e) => basculerSection('gestes', e.detail)}
			/>
			<ArriveesNotification
				arrivees={telemetryData.arrivees}
				periode={periodeDetail}
				ouvert={sectionOuverte === 'arrivees'}
				on:basculer={(e) => basculerSection('arrivees', e.detail)}
			/>
			<DureesAffichage
				durees={telemetryData.performance}
				periode={periodeDetail}
				ouvert={sectionOuverte === 'durees'}
				on:basculer={(e) => basculerSection('durees', e.detail)}
			/>
		{/if}
	</EtatListe>
</section>

<style>
	/*  Les règles des indicateurs voyagent avec leur balisage (v2.95.0 : le
	    panneau est parti NU en production quand elles étaient restées dans la
	    page — `npm run lint:classes-nues` est né de là). Le graphe et les siennes
	    sont dans `FrequentationTelemetrie`. */
	.tl-barre {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem 1.5rem;
		margin: 0.75rem 0 0;
	}
	.tl-filtre {
		white-space: nowrap;
	}
	/*  Au doigt : une cible de 44 px (socle 11 §10). */
	@media (max-width: 480px) {
		.tl-filtre {
			min-height: 44px;
		}
	}
	.tl-scope-switch {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
</style>
