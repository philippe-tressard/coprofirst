<!--
  **« Saisi pour »** — au nom de qui le conseil syndical ouvre ce ticket : en son
  nom, pour un résident inscrit, ou pour une personne extérieure.

  Extrait de `FormulaireTicket.svelte` le 19/08/2026, au fil de l'eau : le
  garde-fou de modularité (rang 1) a refusé que le formulaire — déjà au-dessus de
  500 lignes — grossisse pour recevoir l'aperçu avant diffusion (#498). La règle
  est « on découpe le fichier QUAND on y touche ».

  ⚠️ **Les trois valeurs partent TOUJOURS ensemble vers l'API, y compris à `null`.**
  C'est leur *présence* qui dit au serveur d'écrire (`model_fields_set`), et c'est
  ce qui permet de revenir à « En mon nom » : sans elles, un `None` serait
  indistinguable d'un champ non envoyé, et le choix resterait sans effet — en
  silence. La composition du lot reste chez l'appelant, qui seul sait s'il crée ou
  corrige ; ce composant ne porte que la saisie.

  ⚠️ Le style voyage avec le balisage : `.saisi-pour-*` est défini ici — le
  choix, lui, vient de `ChoixPastilles` (#1160). Un style de page n'atteint pas un composant — c'est la panne des pastilles
  nues (v2.67.11), que `npm run lint:classes-nues` refuse depuis.
-->
<script lang="ts">
	import { SECTIONS_LIBELLE } from '#lib/entites/types.ts';
	import { nomAffiche } from '#lib/noms.ts';
	import SectionFormulaire from '#lib/components/SectionFormulaire.svelte';
	import ChoixPastilles from '#lib/components/ChoixPastilles.svelte';
	import EtoileRequis from '#lib/components/EtoileRequis.svelte';
	import EtatListe from '#lib/components/EtatListe.svelte';
	import type { ModeSaisiPour } from '#lib/saisi-pour.ts';

	/** Lié par l'appelant : lui seul sait ce que ces valeurs deviennent. */
	export let mode: ModeSaisiPour = 'moi';

	/**
	 *  🔴 Le PLIAGE, transmis par l'appelant (22/09/2026, signalé à l'écran).
	 *
	 *  Ce composant porte sa `SectionFormulaire` : le `pliee: true` de la table
	 *  ne l'atteignait pas, et « Au nom de » restait ouverte — alors que c'est
	 *  la seule section dont le pliage est une EXCEPTION déclarée (obligatoire
	 *  mais pliée, « en mon nom » étant juste presque toujours).
	 *
	 *  ⚠️ `valeurModifiee` se mesure contre le DÉFAUT, jamais contre le
	 *  vide : `mode` vaut toujours quelque chose, et tester sa présence
	 *  rouvrirait la section à chaque fois.
	 */
	export let pliable = false;

	/**  Reçu, jamais écrit en dur : la déclaration gouverne le requis comme elle
	 *   gouverne le pliage, et les deux doivent s'accorder (22/09/2026). */
	export let requis = false;

	//: Ce que la section annonce pliée — le choix fait, en trois mots.
	const RESUME_MODE: Record<string, string> = {
		moi: 'En mon nom',
		resident: 'Un résident inscrit',
		exterieur: 'Une personne extérieure',
	};
	//: Les trois réponses, dans l'ordre où on les rencontre.
	const OPTIONS_MODE: { val: ModeSaisiPour; label: string }[] = [
		{ val: 'moi', label: 'En mon nom' },
		{ val: 'resident', label: 'Résident inscrit' },
		{ val: 'exterieur', label: 'Personne extérieure' },
	];
	export let userId: number | null = null;
	export let nom = '';
	export let email = '';
	/** Résidents proposables — chargés par l'appelant, qui connaît ses droits. */
	export let residents: { id: number; prenom: string; nom: string; email: string }[] = [];
	/** Non vide = la liste n'a pas pu être lue : un menu vide ne doit pas le taire (#1459). */
	export let erreurResidents = '';
	/** Le motif d'extinction de la section, ou `''` (`inactivePour`, #1191). */
	export let inactive = '';
</script>

<!--  `rempli` : « En mon nom » EST une réponse — la section n'attend rien
      de plus, donc son astérisque n'est pas rouge (#1121). -->
<!--  🔴 L'intitulé se LIT dans la table (#1124) : la section s'appelle
      « Au nom de » depuis la recomposition du cadre (#1095), et cet écran affichait
      encore « Saisi pour ». Deux noms pour une section, dont un seul est
      déclaré — signalé à l'écran le 22/09/2026. -->
<SectionFormulaire
	titre={SECTIONS_LIBELLE.au_nom_de}
	{inactive}
	{requis}
	rempli={mode !== null && mode !== undefined}
	{pliable}
	valeurModifiee={mode !== 'moi'}
	resume={RESUME_MODE[mode] ?? ''}
>
	<div class="field champ-large">
		<!--  🔴 Le choix passe par `ChoixPastilles` (#1160, signalé à l'écran le
		      23/09/2026) : trois `.tab-btn` à coins carrés, dans un cadre que nulle
		      autre section n'a, réécrivaient ce que Suivi, Catégorie et Périmètre
		      font déjà — sans groupe accessible. -->
		<ChoixPastilles
			options={OPTIONS_MODE}
			bind:valeur={mode}
			tous={false}
			radio="au-nom-de"
			libelle={SECTIONS_LIBELLE.au_nom_de}
			defilante={false}
		/>
		{#if mode === 'resident'}
			<select bind:value={userId} class="saisi-pour-suite" aria-label="Résident concerné">
				<option value={null}>— Sélectionner un résident —</option>
				{#each residents as u (u.id)}
					<option value={u.id}>{nomAffiche(u)}{u.email ? ` (${u.email})` : ''}</option>
				{/each}
			</select>
			<EtatListe compact erreur={erreurResidents} />
		{:else if mode === 'exterieur'}
			<!--  🔴 `.form-grid-2` — la classe EXISTAIT (13/09/2026, #938). Ces deux
			      champs courts s'empilaient sur deux lignes pleine largeur, alors que
			      la charte porte déjà « deux champs qui vont par paire » depuis le
			      01/09/2026, avec son repassage à UNE colonne sur téléphone. Écrire
			      ici un `flex-direction: column` de plus, c'était la septième fois
			      qu'un composant existant n'était pas employé. -->
			<!--  🔴 Des champs LIBELLÉS (#1329) : ils n'avaient qu'un placeholder —
			      « Nom complet * », « Email (optionnel) » —, qui disparaît dès qu'on
			      tape, avec une étoile tapée et un « (optionnel) » que la charte
			      refuse. Les contacts d'un prestataire avaient été corrigés ainsi. -->
			<div class="form-grid form-grid-2 saisi-pour-suite">
				<label class="field">
					<span>Nom complet<EtoileRequis vide={!nom.trim()} /></span>
					<input type="text" bind:value={nom} required />
				</label>
				<label class="field">E-mail<input type="email" bind:value={email} /></label>
			</div>
		{/if}
	</div>
</SectionFormulaire>

<style>
	/*  Les deux champs de la personne extérieure. Le `style=` en ligne qu'ils
	    portaient dans le formulaire est devenu une classe en sortant : une règle
	    nommée se relit, se surcharge et se contrôle — un `style=` ne fait rien de
	    tout cela (`lint:styles`). */
	/*  ⚠️ Ne reste que l'ÉCART : la disposition vient de `.form-grid-2`
	    (`styles/champs.css`), y compris son passage à une colonne sur téléphone.
	    Redéfinir `display` ou `gap` ici les ferait diverger au premier ajustement
	    de la charte — c'est ce que `lint:charte` refuse. */
	/*  L'espace sous les pastilles — la liste des résidents le portait en `style=`. */
	.saisi-pour-suite {
		margin-top: 0.5rem;
	}
</style>
