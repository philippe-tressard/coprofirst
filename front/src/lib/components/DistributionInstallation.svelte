<!--
  « Canal et version » — ce que la mise à jour nocturne d'une installation installera
  (#2210, spec §4.11 règle 6). Une section de `FicheRegistreInstallation`, sous les
  services accordés.

  Deux réglages, et la version cible qui en découle — calculée par le SERVEUR
  (`registre/canaux.version_cible`) et relue après chaque enregistrement ; l'écran
  n'en tient pas de seconde règle :
  - le **canal** suivi : Urgence (la dernière version publiée), ou une version
    choisie parmi les publiées — une liste construite sur les données, donc une
    liste déroulante (`ux-patterns`, seuil des listes courtes) ;
  - la **vague** : Urgence, Pilote ou Standard avec le canal Urgence ; Fixe avec
    une version choisie. Seules les vagues du canal retenu s'offrent.

  Comme les services, le réglage dispatche (`distribution`) et l'onglet demande le
  motif : il s'inscrit au journal, et part dans le prochain bail.
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

	let canal = '';
	let vague = '';
	/** Repartir de ce que la fiche porte — à l'ouverture, et après un enregistrement. */
	function reprendre(f: FicheInstallation) {
		canal = f.canal;
		vague = String(f.vague);
	}
	$: reprendre(fiche);

	//  La version que la fiche suit reste offerte, même sortie de la liste proposée.
	$: optionsCanal = [
		{ val: CANAL_URGENCE, label: 'Urgence — la dernière version publiée' },
		...versions.proposees.map((v) => ({
			val: v.version,
			label: `v${v.version} — publiée le ${fmtDate(v.publiee_le)}`,
		})),
		...(fiche.canal !== CANAL_URGENCE && !versions.proposees.some((v) => v.version === fiche.canal)
			? [{ val: fiche.canal, label: `v${fiche.canal} — hors des versions proposées` }]
			: []),
	];
	$: offertes = vagues.filter((v) => v.avec_urgence === (canal === CANAL_URGENCE));
	$: optionsVague = offertes.map((v) => ({
		val: String(v.code),
		label: v.libelle,
		desc: v.cible ? `${v.detail} : v${v.cible.version}` : v.detail,
	}));
	//  Changer de canal ramène la vague à une vague de ce canal : la sienne par défaut.
	function ajusterVague(possibles: VagueLue[]) {
		if (possibles.some((v) => String(v.code) === vague)) return;
		const retenue = possibles.find((v) => v.defaut) ?? possibles[0];
		vague = retenue ? String(retenue.code) : '';
	}
	$: ajusterVague(offertes);
	$: modifie = canal !== fiche.canal || vague !== String(fiche.vague);

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
	<div class="field">
		<label for="canal-{fiche.identifiant}">Canal suivi</label>
		<select id="canal-{fiche.identifiant}" bind:value={canal} disabled={enCours}>
			{#each optionsCanal as o (o.val)}<option value={o.val}>{o.label}</option>{/each}
		</select>
	</div>
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
</div>
<p class="aide">
	{#if canal === CANAL_URGENCE}
		Le canal Urgence suit les versions publiées, jamais en arrière : Urgence prend la dernière
		aussitôt, Pilote et Standard attendent ses 7 jours.
	{:else}
		Une version choisie se suit en vague Fixe : elle s’installe 7 jours après sa sortie{SEPARATEUR.tiret}plus
		ancienne que celle qui tourne, c’est un ordre d’y revenir, sûr une version à la fois, les
		migrations n’étant compatibles qu’avec la précédente.
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
