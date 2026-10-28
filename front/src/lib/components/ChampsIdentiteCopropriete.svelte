<!--
  ChampsIdentiteCopropriete.svelte — les champs d'identité de la copropriété,
  écrits UNE fois (#779, 01/10/2026).

  Admin › Fiche copropriété et la fiche de la page Résidence les saisissaient
  chacune à sa façon, et la copie de Résidence ne savait pas EFFACER un nombre :
  un champ vidé n'était pas envoyé, l'ancienne valeur restait. La version de
  l'administration — libellés de la fiche ANAH, nom obligatoire, vide envoyé à
  `null` — fait foi (`standards/02` §4 bis : la plus juste, à égalité de
  déploiement). 🔒 `npm run lint:identite-copropriete` refuse une troisième copie.

  🔴 Le composant porte SA DISPOSITION (02/10/2026, maquette B arbitrée à
  l'écran). Posés nus dans la `.form-grid` de l'écran, les six champs y
  prenaient chacun une colonne de 220 px : l'adresse était tronquée, et les
  deux libellés ANAH, plus longs, passaient sur deux lignes — leurs saisies
  tombaient plus bas que leurs voisines. Désormais :
    · nom (1/3) et adresse (2/3) ;
    · les deux décomptes réunis sous « Nombre de lots (fiche ANAH) », libellés
      courts et précision en `.aide`, puis année et numéro sur la même rangée.
  Le bloc occupe la ligne entière (`champ-large`) : l'écran garde sa grille
  pour ce qui lui est propre (la Résidence y ajoute l'aide sur l'assurance).
-->
<script context="module" lang="ts">
	import { nombreOuNull } from '#lib/utils.ts';

	/** Ce que `CoproprieteUpdate` accepte de l'identité ; un nombre vide vaut `''`
	 *  ou `null` le temps de la saisie (cf. `chargeIdentite`). */
	export type IdentiteCopropriete = {
		nom: string;
		adresse: string;
		nb_lots_total: string | number | null;
		nb_lots_principaux: string | number | null;
		annee_construction: string | number | null;
		numero_immatriculation: string;
		/** Le mois (1 à 12) où commence l'exercice comptable (#1643). */
		mois_debut_exercice: string | number | null;
	};

	const NUMERIQUES = [
		'nb_lots_total',
		'nb_lots_principaux',
		'annee_construction',
		'mois_debut_exercice',
	] as const;

	/** Le formulaire pré-rempli depuis la fiche lue (ou vide, sans fiche). */
	export function identiteDepuis(
		fiche: Partial<Record<keyof IdentiteCopropriete, unknown>> | null,
	) {
		const v = (k: keyof IdentiteCopropriete) => (fiche?.[k] ?? '') as string;
		return {
			nom: v('nom'),
			adresse: v('adresse'),
			nb_lots_total: v('nb_lots_total'),
			nb_lots_principaux: v('nb_lots_principaux'),
			annee_construction: v('annee_construction'),
			numero_immatriculation: v('numero_immatriculation'),
			//  Janvier par défaut — l'année civile, comme au serveur : la liste n'a
			//  pas de choix vide, qu'une saisie ne saurait d'ailleurs pas effacer.
			mois_debut_exercice: v('mois_debut_exercice') || 1,
		} satisfies IdentiteCopropriete;
	}

	/** Le formulaire tel que le serveur l'attend. Un nombre vide part à `null`,
	 *  jamais à `''` — Pydantic refuse la chaîne vide sur un `Optional[int]` — ni
	 *  omis : omis, il ne s'effacerait pas. Les autres clés passent telles quelles.
	 *
	 *  La règle du vide est celle de `nombreOuNull` (#1516) : `''` ET `null`. */
	export function chargeIdentite<T extends IdentiteCopropriete>(valeurs: T) {
		const charge: Record<string, unknown> = { ...valeurs };
		for (const champ of NUMERIQUES) {
			charge[champ] = nombreOuNull(valeurs[champ]);
		}
		return charge;
	}
</script>

<script lang="ts">
	import EtoileRequis from '#lib/components/EtoileRequis.svelte';
	import LibelleGroupe from '#lib/components/LibelleGroupe.svelte';
	import { NOMS_MOIS } from '#lib/date.ts';

	export let valeurs: IdentiteCopropriete;
</script>

<div class="identite champ-large">
	<div class="identite-nom">
		<label class="field">
			<span>Nom de la résidence<EtoileRequis vide={!valeurs.nom} /></span>
			<input bind:value={valeurs.nom} required />
			<!--  Le seul champ du nom (#2056) : il venait d’avoir un jumeau sous le même
			      libellé dans Paramétrage site, et c’était celui-là que tout le site lisait. -->
			<span class="aide"
				>Affiché sur la page de connexion, dans le menu, en tête des courriels et sous l’icône de
				l’application installée sur le téléphone.</span
			>
		</label>
		<label class="field">
			<span>Adresse</span>
			<input bind:value={valeurs.adresse} />
		</label>
	</div>
	<!--  Les DEUX décomptes de la fiche du registre national (ANAH). Un seul champ
	      obligeait à choisir lequel perdre, et le chiffre saisi ne disait pas lequel
	      il était : 195 ou 63 pour la même résidence. Le libellé de la fiche reste
	      lisible en entier : le titre du groupe la nomme, l'aide et le survol
	      donnent ce qu'elle compte. Le titre et le groupe que rend `LibelleGroupe`
	      sont deux enfants DIRECTS de cette grille — c'est ce qui aligne les
	      saisies des décomptes sur celles de l'année et du numéro. -->
	<div class="identite-lots">
		<LibelleGroupe titre="Nombre de lots (fiche ANAH)" id="identite-lots" classe="lots-champs">
			<label
				class="field"
				title="Le « Nombre de lots » de la fiche d'immatriculation : tous les lots, caves et parkings compris."
			>
				<span>Total</span>
				<input type="number" min="1" bind:value={valeurs.nb_lots_total} />
				<span class="aide">Caves et parkings compris.</span>
			</label>
			<label
				class="field"
				title="Le décompte qui porte les seuils réglementaires, et qui dit combien de foyers vivent ici."
			>
				<span>Dont lots principaux</span>
				<input type="number" min="1" bind:value={valeurs.nb_lots_principaux} />
				<span class="aide">Habitation, commerces et bureaux.</span>
			</label>
		</LibelleGroupe>
		<label class="field champ-annee">
			<span>Année de construction</span>
			<input type="number" min="1800" max="2100" bind:value={valeurs.annee_construction} />
		</label>
		<label class="field champ-numero">
			<span>N° immatriculation (ANAH)</span>
			<input bind:value={valeurs.numero_immatriculation} placeholder="ex : D75010800001" />
		</label>
	</div>
	<!--  L'exercice comptable voté en AG (#1643) : il borne la moyenne à laquelle
	      la synthèse d'une affaire close se compare. Douze mois : une liste. -->
	<div class="identite-exercice">
		<label class="field">
			<span>Début de l'exercice comptable</span>
			<select bind:value={valeurs.mois_debut_exercice}>
				{#each NOMS_MOIS as nom, i (nom)}
					<option value={i + 1}>{nom}{i === 0 ? ' (année civile)' : ''}</option>
				{/each}
			</select>
			<span class="aide"
				>La synthèse d'une affaire close se compare aux affaires de cet exercice.</span
			>
		</label>
	</div>
</div>

<style>
	/*  Les écarts sont ceux de `.form-grid` (0,75 rem) : le bloc se lit comme la
	    grille qui l'accueille. Le `margin-bottom` de `.field` y est neutralisé
	    pour la même raison que dans `.form-grid` — le `gap` porte l'interligne. */
	.identite {
		display: grid;
		gap: 0.75rem;
	}
	.identite :global(.field) {
		margin-bottom: 0;
	}
	.identite-exercice {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.75rem;
	}
	.identite-nom {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(0, 2fr);
		gap: 0.75rem;
	}
	/*  Quatre colonnes : le groupe des lots en prend deux (titre au-dessus), l'année
	    et le numéro les deux autres, sur la rangée des saisies. */
	.identite-lots {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 0.75rem;
		align-items: start;
	}
	/*  `:global()` borné par l'enveloppe : le titre et le groupe appartiennent au
	    balisage de `LibelleGroupe` (cf. sa prop `classe`). Le filet sous le titre
	    dit ce que le groupe couvre — les deux décomptes, et eux seuls. */
	.identite-lots :global(.libelle-groupe) {
		grid-column: 1 / 3;
		grid-row: 1;
		padding-bottom: 0.25rem;
		border-bottom: 1px solid var(--color-border);
	}
	.identite-lots :global(.lots-champs) {
		grid-column: 1 / 3;
		grid-row: 2;
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.75rem;
	}
	.champ-annee {
		grid-column: 3;
		grid-row: 2;
	}
	.champ-numero {
		grid-column: 4;
		grid-row: 2;
	}

	/*  Tablette : le groupe des lots prend la ligne, l'année et le numéro passent
	    dessous ; le nom et l'adresse s'empilent au seuil de `.form-grid` (767 px).
	    Téléphone : une colonne partout. */
	@media (max-width: 767px) {
		.identite-nom,
		.identite-exercice {
			grid-template-columns: minmax(0, 1fr);
		}
	}
	@media (max-width: 900px) {
		.identite-lots {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
		.identite-lots :global(.libelle-groupe),
		.identite-lots :global(.lots-champs) {
			grid-column: 1 / -1;
		}
		.champ-annee {
			grid-column: 1;
			grid-row: 3;
		}
		.champ-numero {
			grid-column: 2;
			grid-row: 3;
		}
	}
	@media (max-width: 480px) {
		.identite-lots,
		.identite-lots :global(.lots-champs) {
			grid-template-columns: minmax(0, 1fr);
		}
		.champ-numero {
			grid-column: 1;
			grid-row: 4;
		}
	}
</style>
