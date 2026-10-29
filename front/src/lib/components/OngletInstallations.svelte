<!--
  Administration › Installations — le REGISTRE des installations CoproFirst, vu
  de la référence (R4 #1880, spec §4.11). Réservé à l'opérateur ; la page masque
  l'onglet hors de la référence, et le serveur dit « éteint » ailleurs.

  Une carte par installation, au standard du site (page Affaires) : recherche en
  tête, filtre par état — le compteur sur la pastille retenue —, cartes datées par
  leur dernier signe de vie. Une seule carte ouverte (`#lib/accordeon`) ; sa fiche
  se charge au premier dépliage.

  L'état et les appels réseau vivent ici (`svelte-patterns`, famille `Onglet<Nom>`) :
  la fiche dispatche un geste, l'onglet demande le motif (`#lib/saisie`), appelle
  le serveur, et range la fiche qu'il rend.
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import CarteRegistreInstallation from '#lib/components/CarteRegistreInstallation.svelte';
	import ChampRecherche from '#lib/components/ChampRecherche.svelte';
	import { contientTousLesMots } from '#lib/texte.ts';
	import ChoixPastilles from '#lib/components/ChoixPastilles.svelte';
	import EtatListe from '#lib/components/EtatListe.svelte';
	import ReglagesListe from '#lib/components/ReglagesListe.svelte';
	import VersionsPubliees from '#lib/components/VersionsPubliees.svelte';
	import { toast } from '#lib/components/Toast.svelte';
	import {
		registre as registreApi,
		type FicheInstallation,
		type GesteRegistre,
		type RegistreLu,
		type ReglageDistribution,
	} from '#lib/api/index.ts';
	import { basculer } from '#lib/accordeon.ts';
	import { messageErreur } from '#lib/erreurs.ts';
	import { demander } from '#lib/saisie.ts';
	import { ETATS_REGISTRE, GESTES_REGISTRE } from '#lib/registre-installations.ts';

	let lu: RegistreLu | null = null;
	let chargement = true;
	let erreur = '';

	let recherche = '';
	let etat = '';
	let ouvert: string | null = null;
	let fiches: Record<string, FicheInstallation> = {};
	let erreursFiche: Record<string, string> = {};
	let enCours: string | null = null;

	onMount(async () => {
		try {
			lu = await registreApi.installations();
		} catch (e) {
			erreur = messageErreur(e);
		} finally {
			chargement = false;
		}
	});

	$: installations = lu?.installations ?? [];
	$: affichees = installations.filter(
		(i) =>
			(!etat || i.etat === etat) &&
			contientTousLesMots(
				[i.identifiant, i.administrateur, i.version_logicielle, i.canal],
				recherche,
			),
	);

	async function ouvrir(identifiant: string) {
		ouvert = basculer(ouvert, identifiant);
		if (ouvert !== identifiant || fiches[identifiant]) return;
		try {
			fiches = { ...fiches, [identifiant]: await registreApi.fiche(identifiant) };
		} catch (e) {
			erreursFiche = { ...erreursFiche, [identifiant]: messageErreur(e) };
		}
	}

	/** Range la fiche rendue par le serveur, et son résumé dans la liste. */
	function ranger(fiche: FicheInstallation) {
		fiches = { ...fiches, [fiche.identifiant]: fiche };
		if (lu) {
			lu = {
				...lu,
				installations: lu.installations.map((i) =>
					i.identifiant === fiche.identifiant ? { ...i, ...fiche } : i,
				),
			};
		}
	}

	async function appliquer(
		identifiant: string,
		appel: () => Promise<FicheInstallation>,
		ok: string,
	) {
		enCours = identifiant;
		try {
			ranger(await appel());
			toast('success', ok);
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			enCours = null;
		}
	}

	/** Supprimée : la carte quitte la liste, comme au prochain chargement. */
	function retirer(identifiant: string) {
		ouvert = null;
		if (lu) {
			lu = {
				...lu,
				installations: lu.installations.filter((i) => i.identifiant !== identifiant),
			};
		}
	}

	async function supprimer(identifiant: string, motif: string) {
		enCours = identifiant;
		try {
			await registreApi.supprimer(identifiant, motif);
			retirer(identifiant);
			toast('success', `${identifiant} supprimée. Son contrat reste archivé jusqu’à son échéance.`);
		} catch (e) {
			toast('error', messageErreur(e));
		} finally {
			enCours = null;
		}
	}

	async function geste(identifiant: string, g: GesteRegistre) {
		const declare = GESTES_REGISTRE[g];
		const motif = await demander({
			titre: `${declare.libelle} ${identifiant}`,
			message: declare.effet,
			libelle: 'Motif',
			placeholder: 'Ce qui motive la décision — il s’inscrit au journal.',
			libelleValider: declare.libelle,
			requis: true,
		});
		if (!motif?.trim()) return;
		if (g === 'supprimer') return supprimer(identifiant, motif.trim());
		await appliquer(
			identifiant,
			() => registreApi.decider(identifiant, g, motif.trim()),
			`${declare.libelle} : décision enregistrée. Elle part dans le prochain bail de ${identifiant}.`,
		);
	}

	async function distribution(identifiant: string, reglage: ReglageDistribution) {
		const motif = await demander({
			titre: `Canal et version de ${identifiant}`,
			message: 'La version cible qui en découle part dans le prochain bail de l’installation.',
			libelle: 'Motif',
			placeholder: 'Ce qui motive le réglage — il s’inscrit au journal.',
			libelleValider: 'Enregistrer',
			requis: true,
		});
		if (!motif?.trim()) return;
		await appliquer(
			identifiant,
			() => registreApi.distribuer(identifiant, reglage, motif.trim()),
			`Réglage enregistré. La version cible part dans le prochain bail de ${identifiant}.`,
		);
	}

	async function services(identifiant: string, choisis: string[]) {
		const motif = await demander({
			titre: `Services accordés à ${identifiant}`,
			message: 'Ils partent dans le prochain bail de l’installation.',
			libelle: 'Motif',
			placeholder: 'Ce qui motive le changement — il s’inscrit au journal.',
			libelleValider: 'Enregistrer',
			requis: true,
		});
		if (!motif?.trim()) return;
		await appliquer(
			identifiant,
			() => registreApi.accorderServices(identifiant, choisis, motif.trim()),
			`Services enregistrés. Ils partent dans le prochain bail de ${identifiant}.`,
		);
	}
</script>

{#if lu && !lu.actif}
	<p class="aide">
		Le registre des installations n’est servi que par l’installation de référence, quand sa base et
		son nom dédié sont déclarés.
	</p>
{:else}
	{#if lu}
		<VersionsPubliees versions={lu.versions} vagues={lu.vagues} />
	{/if}

	<ReglagesListe>
		<ChampRecherche
			id="admin-recherche-installation"
			bind:valeur={recherche}
			placeholder="CF-000003, Durand, 2.144…"
			dans="identifiant, administrateur, version et canal"
		/>
		<ChoixPastilles
			options={ETATS_REGISTRE}
			bind:valeur={etat}
			tous="Toutes"
			compte={affichees.length}
			libelle="État"
			libelleDevant
		/>
	</ReglagesListe>

	<EtatListe
		{chargement}
		{erreur}
		vide={affichees.length === 0}
		titreVide="Aucune installation"
		messageVide={installations.length
			? 'Aucune installation ne répond à ces réglages.'
			: 'Aucune installation ne s’est encore inscrite au registre.'}
	>
		{#each affichees as i (i.identifiant)}
			<CarteRegistreInstallation
				installation={i}
				ouvert={ouvert === i.identifiant}
				fiche={fiches[i.identifiant] ?? null}
				erreurFiche={erreursFiche[i.identifiant] ?? ''}
				accordables={lu?.services_accordables ?? []}
				versions={lu?.versions}
				vagues={lu?.vagues ?? []}
				enCours={enCours === i.identifiant}
				on:basculer={() => ouvrir(i.identifiant)}
				on:geste={(e) => geste(i.identifiant, e.detail)}
				on:services={(e) => services(i.identifiant, e.detail)}
				on:distribution={(e) => distribution(i.identifiant, e.detail)}
			/>
		{/each}
	</EtatListe>
{/if}
