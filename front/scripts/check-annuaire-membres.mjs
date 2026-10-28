#!/usr/bin/env node
/**
 *  Une liste de membres de l'annuaire se monte par **`AnnuaireMembres`**, seul
 *  composant à rendre `CarteMembre` (#1539, 02/10/2026).
 *
 *  🔴 `AnnuaireConseil` et `AnnuaireSyndic` montaient chacun `CarteMembre` dans
 *  leur propre boucle, avec les mêmes sept événements câblés, le même état
 *  dépliable, le même amorçage et le même bouton d'ajout — 60 lignes sur 182.
 *  La FICHE avait été factorisée (`CarteMembre`, 18/09) ; son câblage, non :
 *  c'est `standards/02` §4 quinquies, la duplication déplacée d'un cran.
 *
 *  Ce contrôle refuse un troisième montage de la fiche hors de la liste : ce
 *  qui manque à un annuaire (un ordre, un refus, un geste) s'y DÉCLARE en prop.
 *
 *  ⚠️ Il ne voit que le montage de la fiche. Une liste réécrite sans elle — un
 *  autre balisage, mêmes gestes — lui échappe : c'est `lint:identite-membre`
 *  qui refuse la saisie d'une identité hors de `CarteMembre`.
 *
 *  Lancer : node scripts/check-annuaire-membres.mjs [--selftest]
 */
import { controler, lignesPortant } from './lib-source-unique.mjs';

/**  Monter la fiche d'un membre. */
const COPIE = /<CarteMembre\b/;

process.exit(
	controler({
		temoin: 'src/lib/components/AnnuaireMembres.svelte',
		fautes: lignesPortant(COPIE),
		cas: [
			['\t\t<CarteMembre bind:membre={membresCS[i]} ouvert={cs.ouvert === i}', 1],
			['\t<CarteMembre', 1],
			//  La forme voulue, jamais signalée.
			['\t<AnnuaireMembres bind:membres={membresCS} {charger} {nouveau} {envoyer}>', 0],
			//  Importer le TYPE de la fiche n'est pas la monter.
			["\timport { type MembreBase } from '#lib/components/CarteMembre.svelte';", 0],
			//  Un nom qui commence pareil n'est pas la fiche.
			['\t<CarteMembreDetail />', 0],
		],
		ok: 'Annuaire : fiches montées par AnnuaireMembres seul',
		ko: 'fiche(s) `CarteMembre` montée(s) hors de la liste',
		conseil: 'Employer `<AnnuaireMembres>` ; ce qui manque à cet annuaire s’y déclare en prop.',
	}),
);
