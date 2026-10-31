<!--
  ChampsContrat.svelte — les champs d'un contrat d'entretien, écrits UNE fois.

  ## Pourquoi (30/08/2026, #453 · #491)

  `prestataires/+page.svelte` rendait ce formulaire **deux fois** : dans la
  modale « Nouveau / Modifier contrat », et dans l'édition en ligne au sein de la
  carte du contrat. Quatre-vingt-dix lignes chacune, à l'indentation près.

  Le garde-fou de modularité a refusé un ajout de quatorze lignes à ce fichier.
  Il ne disait pas « il est trop long », il disait **« le code est au mauvais
  endroit »** (#453, la troisième des trois réponses possibles).

  ## 🔴 Les quatre divergences que la copie avait fabriquées

  Comparées ligne à ligne, indentation retirée — aucune n'est une décision :

  | | Modale | Édition en ligne |
  |---|---|---|
  | **Équipement** | présent | **ABSENT** — on ne pouvait pas le changer là |
  | Libellé | `champ-large` | `field` nu, donc écrasé dans un tiers de grille |
  | Notes, pour un lecteur d'écran | `ariaLabelledby` | **rien** — groupe sans nom |
  | Aide des notes | « Notes sur le contrat… » | « Notes… » |

  La première est un **champ manquant** : le type d'équipement appartient au
  contrat, il se saisit dans les deux rendus ou dans aucun. Le cadre #430 pose la
  question ainsi — *devant un écart entre deux états, lequel des deux a tort ?* —
  et ici c'est l'édition en ligne.

  Ce n'est pas de l'inattention : **c'est la duplication du rendu qui le
  produit**, mécaniquement, comme le crayon et la corbeille du fil de tickets
  (#431) qui avaient divergé deux fois dans les deux sens.

  ## Ce qui reste dans l'écran

  Le bloc **Documents** : sa source d'identifiant diffère (`editContratId` dans
  la modale, `c.id` dans la carte) et son enveloppe aussi (`.contrat-section`).
  Le passer ici demanderait de faire voyager la table des documents et son
  téléversement — un autre lot, et il est nommé dans #390.
-->
<script context="module" lang="ts">
	import ChoixPastilles from '#lib/components/ChoixPastilles.svelte';
	import { pliageDe, requisDe } from '#lib/pliage.ts';
	let compteur = 0;
</script>

<script lang="ts">
	import type { Prestataire } from '#lib/api/index.ts';
	import type { FormulaireContratData } from '#lib/prestataires.ts';
	import { SECTIONS_LIBELLE } from '#lib/entites/types.ts';
	import SectionEquipement from './SectionEquipement.svelte';
	import SectionPerimetre from './SectionPerimetre.svelte';
	import SectionDescription from './SectionDescription.svelte';
	import SectionFormulaire from './SectionFormulaire.svelte';
	import SectionTitre from '#lib/components/SectionTitre.svelte';
	import EtoileRequis from '#lib/components/EtoileRequis.svelte';
	import ChampFrequence from '#lib/components/ChampFrequence.svelte';
	import { CONTRAT } from '#lib/entites/contrat.ts';
	import { sectionPresente, type Etat } from '#lib/entites/types.ts';
	import { SEPARATEUR } from '#lib/separateurs.ts';

	/** Le formulaire lié — l'écran porte l'état et l'enregistre. */
	export let contratForm: FormulaireContratData;
	/** Les prestataires proposables. */
	export let prestataires: Prestataire[] = [];
	/** La table des équipements (`{ val, label }`). */
	export let equipements: readonly { val: string; label: string }[] = [];
	/**  Création ou correction — c'est la DÉCLARATION qui en tire les sections
	 *   présentes, jamais une condition écrite ici (`lint:etats`). */
	export let etat: Etat = 'creation';

	//  Un identifiant par instance : les deux rendus coexistent dans la même page,
	//  et deux `id` identiques feraient pointer les deux `aria-labelledby` sur le
	//  premier — un défaut qui ne se voit qu'au lecteur d'écran.
	const idNotes = `contrat-notes-${++compteur}`;
	const UNITES_DUREE = [
		{ val: 'mois', label: 'mois' },
		{ val: 'ans', label: 'ans' },
	];
</script>

<!--  ══ 1. TITRE ══ Le titre SEUL (§0, arbitré le 18/08/2026 : ce qui qualifie
      l'objet est en section 2). Le champ s'appelait « Libellé » — signalé à
      l'écran le 12/09 : c'est « Titre » sur les huit autres entités, et un même
      objet porte le même libellé partout (R3).

      🔴 La section n'a PAS de titre, et le champ porte le sien (12/09/2026,
      second signalement). `titre="Titre" requis` rendait « TITRE* » en petites
      capitales — une troisième forme pour le même champ, et l'astérisque collé.
      Mesuré : DIX écrans sur onze emploient `<SectionFormulaire premiere>` avec
      un `.field champ-large` qui porte `Titre *`. L'exception, c'était moi. -->
<SectionTitre id="{idNotes}-titre" bind:valeur={contratForm.libelle} />

<!--  🔴 LES SECTIONS STANDARD (24/09/2026, signalé à l'écran : « Prendre exemple
      sur l'UX d'Affaires »). Tout vivait dans une section « Le contrat » que le
      cadre ne connaît pas : prestataire, équipement, dates et numéro, sans
      distinguer l'obligatoire du facultatif. Chaque groupe rejoint la section
      qui le nomme sur les affaires — Équipement, Quand, Intervenant —, et le
      numéro, seul facultatif, la section 2 (« Référence »), pliée. -->

<!--  ══ 2. RÉFÉRENCE ══ Le numéro du contrat, facultatif : plié. -->
{#if sectionPresente(CONTRAT, etat, 'nature')}
	<SectionFormulaire
		titre="Référence"
		pliable={pliageDe(CONTRAT, 'nature')}
		valeurModifiee={!!contratForm.numero_contrat}
		resume={contratForm.numero_contrat || 'aucune'}
		pour="{idNotes}-numero"
	>
		<div class="field">
			<input
				id="{idNotes}-numero"
				type="text"
				bind:value={contratForm.numero_contrat}
				placeholder="N° du contrat"
			/>
		</div>
	</SectionFormulaire>
{/if}

<!--  ══ 3. ÉQUIPEMENT ══ Ce que le contrat entretient — il le DÉFINIT. -->
{#if sectionPresente(CONTRAT, etat, 'equipement')}
	<!--  `SectionEquipement`, la section de l'affaire et du prestataire (#1329). -->
	<SectionEquipement
		idPrefixe={idNotes}
		options={equipements}
		pliable={pliageDe(CONTRAT, 'equipement')}
		requis={requisDe(CONTRAT, 'equipement')}
		aide=""
		bind:equipement={contratForm.type_equipement}
	/>
{/if}

<!--  ══ 5. QUAND ══ Depuis quand, pour combien de temps, à quel rythme. -->
{#if sectionPresente(CONTRAT, etat, 'quand')}
	<SectionFormulaire
		titre={SECTIONS_LIBELLE.quand}
		pliable={pliageDe(CONTRAT, 'quand')}
		requis={requisDe(CONTRAT, 'quand')}
		rempli={!!contratForm.date_debut}
	>
		<div class="form-grid">
			<label class="field"
				><span>Début<EtoileRequis vide={!contratForm.date_debut} /></span><input
					type="date"
					bind:value={contratForm.date_debut}
					required
				/></label
			>
			<!--  Un `<div>` et non un `<label>` : l'unité est un groupe de pastilles,
			      et des boutons dans un label lui voleraient son clic (#1329). -->
			<div class="field">
				<label for="{idNotes}-duree">Durée initiale</label>
				<div class="duo">
					<input
						id="{idNotes}-duree"
						type="number"
						min="1"
						placeholder="Ex. 12"
						bind:value={contratForm.duree_initiale_valeur}
					/>
					<ChoixPastilles
						options={UNITES_DUREE}
						bind:valeur={contratForm.duree_initiale_unite}
						tous={false}
						libelle="Unité de la durée"
						radio="{idNotes}-unite"
						defilante={false}
					/>
				</div>
			</div>
			<label class="field"
				>Prochaine visite<input type="date" bind:value={contratForm.prochaine_visite} /></label
			>
		</div>
		<!--  La fréquence SOUS la rangée des dates, comme sur une affaire d'entretien
		      (`FormulaireTicket`) : posée dans une cellule de la grille, sa propre
		      grille et sa marge la décalaient d'une demi-ligne (#1230). -->
		<ChampFrequence
			bind:frequenceType={contratForm.frequence_type}
			bind:frequenceValeur={contratForm.frequence_valeur}
		/>
	</SectionFormulaire>
{/if}

<!--  ══ 6. INTERVENANT ══ Le prestataire qui signe — la section qui le nomme
      sur les affaires. -->
{#if sectionPresente(CONTRAT, etat, 'intervenant')}
	<SectionFormulaire
		titre={SECTIONS_LIBELLE.intervenant}
		pliable={pliageDe(CONTRAT, 'intervenant')}
		requis={requisDe(CONTRAT, 'intervenant')}
		rempli={!!contratForm.prestataire_id}
		pour="{idNotes}-prestataire"
	>
		<div class="field">
			<select id="{idNotes}-prestataire" bind:value={contratForm.prestataire_id} required>
				<option value="">— Sélectionner —</option>
				{#each prestataires as pr (pr.id)}<option value={String(pr.id)}>{pr.nom}</option>{/each}
			</select>
		</div>
	</SectionFormulaire>
{/if}

<!--  ══ 7. PÉRIMÈTRE ══ `SectionPerimetre`, la section de toutes les entités
      (#1329). Elle était réécrite ici, et son titre se rattachait (`for`,
      `aria-labelledby`) à un identifiant qui n'existait pas.

      🔴 Le périmètre n'existait PAS avant le 10/09/2026 : `batiment_id` figurait
      dans la charge utile sans que rien ne le remplisse, donc tous les contrats
      portaient `NULL` et le carnet d'entretien ne pouvait filtrer sur rien. -->
{#if sectionPresente(CONTRAT, etat, 'perimetre')}
	<SectionPerimetre
		idPrefixe={idNotes}
		pliable={pliageDe(CONTRAT, 'perimetre')}
		requis={requisDe(CONTRAT, 'perimetre')}
		bind:perimetre={contratForm.perimetre_cible}
	>
		<p class="aide" slot="aidePerimetre">
			Ce que ce contrat entretient. Il apparaîtra dans le carnet d’entretien de ce périmètre{SEPARATEUR.tiret}et
			dans celui de chacun des espaces qu’il contient.
		</p>
	</SectionPerimetre>
{/if}

<!--  ══ 8. DESCRIPTION ══ C'est ici qu'atterrit la synthèse proposée par
      l'assistant IA (#899), relue et corrigée avant enregistrement.
      `SectionDescription`, à la hauteur de toutes les autres (#1329) : elle
      était réécrite ici, à 60 px, liée à un identifiant inexistant. -->
{#if sectionPresente(CONTRAT, etat, 'description')}
	<SectionDescription
		idPrefixe={idNotes}
		pliable={pliageDe(CONTRAT, 'description')}
		placeholder="Ce que couvre le contrat, ses points d’attention…"
		bind:valeur={contratForm.notes}
	/>
{/if}

<style>
	/*  Les deux contrôles d'une durée — un nombre et son unité — sur une ligne.
	    Ils étaient posés par un `style=` en ligne, donc invisibles à
	    `lint:styles` et impossibles à ajuster ailleurs. */
	.duo {
		display: flex;
		gap: 0.4rem;
	}
	.duo input {
		flex: 1;
	}
</style>
