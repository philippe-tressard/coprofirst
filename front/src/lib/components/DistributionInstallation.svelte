<!--
  « Canal et version » — ce que la mise à jour nocturne d'une installation installera
  (R5 #1881, spec §4.11 règle 6). Une section de `FicheRegistreInstallation`, sous les
  services accordés.

  Trois réglages, et la version cible qui en découle — calculée par le SERVEUR
  (`registre/canaux.version_cible`) et relue après chaque enregistrement ; l'écran
  n'en tient pas de seconde règle :
  - le **canal** suivi : `replica`, ou un canal spécial ;
  - la **vague** : quand la version du canal lui parvient ;
  - l'**épinglage** : une version imposée — plus ancienne, c'est l'ordre de revenir.

  Comme les services, le réglage dispatche (`distribution`) et l'onglet demande le
  motif : il s'inscrit au journal, et part dans le prochain bail.
-->
<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import ChoixPastilles from '$lib/components/ChoixPastilles.svelte';
	import PiedFormulaire from '$lib/components/PiedFormulaire.svelte';
	import type {
		CanalDistribution,
		FicheInstallation,
		ReglageDistribution,
		VagueLue,
	} from '$lib/api';
	import { libelleVersionCible } from '$lib/registre-installations';

	export let fiche: FicheInstallation;
	export let canaux: CanalDistribution[] = [];
	export let vagues: VagueLue[] = [];
	export let enCours = false;

	const dispatch = createEventDispatcher<{ distribution: ReglageDistribution }>();

	let canal = '';
	let vague = '';
	let epinglee = '';
	/** Repartir de ce que la fiche porte — à l'ouverture, et après un enregistrement. */
	function reprendre(f: FicheInstallation) {
		canal = f.canal;
		vague = String(f.vague);
		epinglee = f.version_epinglee ?? '';
	}
	$: reprendre(fiche);

	//  `replica` existe toujours, même avant sa première lecture : c'est le canal
	//  par défaut de toute inscription.
	$: optionsCanal = [
		{ val: 'replica', label: 'replica' },
		...canaux.filter((c) => c.nom !== 'replica').map((c) => ({ val: c.nom, label: c.nom })),
	].map((o) => {
		const lu = canaux.find((c) => c.nom === o.val);
		return { ...o, desc: lu?.version ? `v${lu.version}` : 'version pas encore lue' };
	});
	$: optionsVague = vagues.map((v) => ({ val: String(v.code), label: v.libelle }));
	$: modifie =
		canal !== fiche.canal ||
		vague !== String(fiche.vague) ||
		epinglee.trim() !== (fiche.version_epinglee ?? '');

	function enregistrer() {
		dispatch('distribution', {
			canal,
			vague: Number(vague),
			version_epinglee: epinglee.trim() || null,
		});
	}
</script>

<h4 class="intertitre">Canal et version</h4>
<p class="cible">
	Version cible du prochain bail : <strong>{libelleVersionCible(fiche.version_cible)}</strong>
</p>
<!--  `section-formulaire` : les libellés des trois réglages se lisent un cran SOUS
      l'intitulé « Canal et version » (`champs.css`), pas au-dessus. -->
<div class="reglages section-formulaire">
	<ChoixPastilles
		options={optionsCanal}
		bind:valeur={canal}
		tous={false}
		radio="canal-{fiche.identifiant}"
		libelle="Canal suivi"
		libelleVisible
		avecDetail
		defilante={false}
	/>
	<ChoixPastilles
		options={optionsVague}
		bind:valeur={vague}
		tous={false}
		radio="vague-{fiche.identifiant}"
		libelle="Vague"
		libelleVisible
		defilante={false}
	/>
	<div class="field">
		<label for="epinglee-{fiche.identifiant}">Version épinglée</label>
		<input
			id="epinglee-{fiche.identifiant}"
			type="text"
			inputmode="decimal"
			placeholder="Vide : suivre le canal"
			bind:value={epinglee}
			disabled={enCours}
		/>
	</div>
</div>
<p class="aide">
	Une version épinglée s’installe quel que soit le canal — plus ancienne que celle qui tourne, c’est
	un ordre de revenir : une version à la fois reste sûr, les migrations n’étant compatibles qu’avec
	la précédente. Seule une version promue s’installe : elle a son archive de déploiement.
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
