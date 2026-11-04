<!--
  « Canal et version » — ce que la mise à jour nocturne d'une installation installera
  (#2210, spec §4.11 règle 6). Une section de `FicheRegistreInstallation`, sous les
  services accordés.

  Un seul réglage, la **vague**, et la version cible qui en découle — calculée par le
  SERVEUR (`registre/canaux.version_cible`) et relue après chaque enregistrement ;
  l'écran n'en tient pas de seconde règle :
  - **Urgence** : la dernière version publiée, aussitôt ;
  - **Standard** : le dernier correctif de 7 jours de la mineure précédente ;
  - **Fixe** : une version choisie parmi les publiées — une liste construite sur les
    données, donc une liste déroulante (`ux-patterns`, seuil des listes courtes).

  Le canal n'est plus un réglage : il en découle (Urgence, ou la version choisie en
  Fixe) et part tel quel au serveur. Comme les services, le réglage dispatche
  (`distribution`) et l'onglet demande le motif : il s'inscrit au journal, et part
  dans le prochain bail.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import ChoixPastilles from '#lib/components/ChoixPastilles.svelte';
	import PiedFormulaire from '#lib/components/PiedFormulaire.svelte';
	import type {
		FicheInstallation,
		ReglageDistribution,
		VagueLue,
		VersionsPubliees,
	} from '#lib/api/index.ts';
	import { fmtDate } from '#lib/date.ts';
	import { CANAL_URGENCE, libelleVersionCible } from '#lib/registre-installations.ts';
	import { SEPARATEUR } from '#lib/separateurs.ts';

	export let fiche: FicheInstallation;
	export let versions: VersionsPubliees = { proposees: [], lues_le: null };
	export let vagues: VagueLue[] = [];
	export let enCours = false;

	const dispatch = createEventDispatcher<{ distribution: ReglageDistribution }>();

	let vague = '';
	let version = '';
	/** Repartir de ce que la fiche porte — à l'ouverture, et après un enregistrement. */
	function reprendre(f: FicheInstallation) {
		vague = String(f.vague);
		version = f.canal === CANAL_URGENCE ? '' : f.canal;
	}
	$: reprendre(fiche);

	//  Fixe est la seule vague qui ne suit pas le canal Urgence (`avec_urgence`).
	$: estFixe = vagues.some((v) => !v.avec_urgence && String(v.code) === vague);
	//  La version que la fiche suit reste offerte, même sortie de la liste proposée.
	$: optionsVersion = [
		...versions.proposees.map((v) => ({
			val: v.version,
			label: `v${v.version} — publiée le ${fmtDate(v.publiee_le)}`,
		})),
		...(fiche.canal !== CANAL_URGENCE && !versions.proposees.some((v) => v.version === fiche.canal)
			? [{ val: fiche.canal, label: `v${fiche.canal} — hors des versions proposées` }]
			: []),
	];
	//  Passer en Fixe propose d'abord la version la plus récente.
	$: if (estFixe && !version && optionsVersion.length) version = optionsVersion[0].val;
	$: optionsVague = vagues.map((v) => ({
		val: String(v.code),
		label: v.libelle,
		desc: v.cible ? `${v.detail} : v${v.cible.version}` : v.detail,
	}));
	$: canal = estFixe ? version : CANAL_URGENCE;
	$: modifie = canal !== '' && (canal !== fiche.canal || vague !== String(fiche.vague));

	function enregistrer() {
		dispatch('distribution', { canal, vague: Number(vague) });
	}
</script>

<h4 class="intertitre">Canal et version</h4>
<p class="cible">
	Version cible du prochain bail : <strong>{libelleVersionCible(fiche.version_cible)}</strong>
</p>
<!--  `section-formulaire` : les libellés des réglages se lisent un cran SOUS
      l'intitulé « Canal et version » (`champs.css`), pas au-dessus. -->
<div class="reglages section-formulaire">
	<ChoixPastilles
		options={optionsVague}
		bind:valeur={vague}
		tous={false}
		radio="vague-{fiche.identifiant}"
		libelle="Vague"
		libelleVisible
		avecDetail
		defilante={false}
	/>
	{#if estFixe}
		<div class="field">
			<label for="version-{fiche.identifiant}">Version fixée</label>
			<select id="version-{fiche.identifiant}" bind:value={version} disabled={enCours}>
				{#each optionsVersion as o (o.val)}<option value={o.val}>{o.label}</option>{/each}
			</select>
		</div>
	{/if}
</div>
<p class="aide">
	{#if estFixe}
		Une version fixée s’installe 7 jours après sa sortie{SEPARATEUR.tiret}plus ancienne que celle
		qui tourne, c’est un ordre d’y revenir, sûr une version à la fois, les migrations n’étant
		compatibles qu’avec la précédente.
	{:else}
		Urgence et Standard suivent les versions publiées, jamais en arrière : Urgence prend la dernière
		aussitôt, Standard attend ses 7 jours.
	{/if}
	Seule une version publiée s’installe : elle a son archive de déploiement.
</p>
{#if modifie}
	<PiedFormulaire
		soumission={false}
		{enCours}
		on:annule={() => reprendre(fiche)}
		on:enregistre={enregistrer}
	/>
{/if}

<style>
	.cible {
		margin: 0 0 0.5rem;
		font-size: var(--fs-sm);
	}
	.reglages {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
	}
</style>
