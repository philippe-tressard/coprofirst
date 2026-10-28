/**
 * **Les champs d'un locataire sur un bail** — saisis à la création, corrigés
 * ensuite.
 *
 * ## 🔴 Pourquoi ce module (15/09/2026)
 *
 * `mon-lot/+page.svelte` énumérait ces champs **quatre fois** : la déclaration
 * du bail neuf, sa remise à zéro après enregistrement, la déclaration de
 * l'édition, et son remplissage depuis un bail existant.
 *
 * Ce n'est pas quatre fois la même ligne, c'est **deux structures écrites deux
 * fois chacune** — et ajouter un champ demandait de le poser aux quatre
 * endroits. Un champ manqué à l'un des quatre donne un formulaire qui
 * enregistre à la création et oublie à la correction, **en silence** : une clé
 * absente d'un objet JavaScript ne lève rien.
 *
 * ## Les deux structures, et ce qui les sépare
 *
 * `date_entree` ne figure que dans le bail **neuf**. Ce n'est pas un oubli :
 * elle se saisit à l'entrée du locataire et ne se corrige pas depuis cet
 * écran — la déplacer demanderait de décaler un bail, pas de rectifier une
 * coordonnée. La différence est donc **déclarée** par la forme des deux
 * fonctions, au lieu d'être devinée en comparant deux listes.
 */

import { parAttribut } from '#lib/table-statuts.ts';
import { nomAffiche } from '#lib/noms.ts';

/** Ce qui identifie et joint un locataire — commun aux deux gestes. */
export interface ChampsLocataire {
	locataire_nom: string;
	locataire_prenom: string;
	locataire_email: string;
	locataire_telephone: string;
	date_sortie_prevue: string;
	notes: string;
}

/** Un bail qu'on CRÉE : les champs du locataire, plus sa date d'entrée. */
export interface ChampsBailNeuf extends ChampsLocataire {
	date_entree: string;
}

/** Ce qu'un bail existant porte de son locataire — vide s'il n'y en a pas. */
type SourceBail = Partial<Record<keyof ChampsLocataire, string | null>> | null | undefined;

/**
 * Les champs du locataire, repris d'un bail ou vides.
 *
 * ⚠️ Tous présents, y compris vides : ce sont eux que le formulaire lie, et une
 * clé absente ferait un champ non contrôlé — Svelte lie alors `undefined`, et
 * l'`<input>` passe en non-contrôlé sans que rien ne le dise.
 */
export function champsLocataire(bail?: SourceBail): ChampsLocataire {
	return {
		locataire_nom: bail?.locataire_nom ?? '',
		locataire_prenom: bail?.locataire_prenom ?? '',
		locataire_email: bail?.locataire_email ?? '',
		locataire_telephone: bail?.locataire_telephone ?? '',
		date_sortie_prevue: bail?.date_sortie_prevue ?? '',
		notes: bail?.notes ?? '',
	};
}

/** Un bail NEUF, vierge. */
export function bailVierge(): ChampsBailNeuf {
	return { ...champsLocataire(), date_entree: '' };
}

/*  ══════════════════════════════════════════════════════════════════════════
    L'ÉTAT d'un bail — trois états, trois attributs, une seule déclaration

    🔴 Il était écrit en TROIS FORMES DIFFÉRENTES (15/09/2026) :

      * la **teinte**, en ternaire imbriqué, deux fois dans `OngletGestionLocative` ;
      * le **libellé**, dans une table déclarée au milieu d'un écran (`mon-lot`),
        puis passée en prop au composant qui l'affiche ;
      * la **question** « ce bail court-il encore ? », écrite `statut === 'actif'
        || statut === 'en_cours_sortie'` à **trois** endroits.

    Trois attributs de la même notion, trois endroits, et aucun qui se voie
    depuis les autres. Ajouter un quatrième état — une reconduction, une
    résiliation contestée — demandait de le poser partout, et l'oublier dans le
    ternaire donnait un badge gris : lisible, donc invisible.

    La contrepartie serveur est `StatutBail` (`api/app/models/core.py`).
    ══════════════════════════════════════════════════════════════════════════ */

const ETAT = parAttribut({
	actif: { libelle: 'Actif', badge: 'badge-green' },
	en_cours_sortie: { libelle: 'En cours de sortie', badge: 'badge-yellow' },
	termine: { libelle: 'Terminé', badge: 'badge-gray' },
});

/** « en_cours_sortie » → « En cours de sortie ». Valeur brute à défaut : un
 *  libellé manquant doit se voir, pas s'effacer. */
export const LIBELLE_STATUT_BAIL: Record<string, string> = ETAT.libelle;

/** La teinte du même état. */
export const BADGE_STATUT_BAIL: Record<string, string> = ETAT.badge;

/**
 * Ce bail court-il encore ? — la seule écriture de cette question.
 *
 * ⚠️ `en_cours_sortie` compte comme **en cours**, et ce n'est pas une
 * approximation : le préavis n'a pas encore pris fin, le locataire est là, ses
 * accès fonctionnent. Le jour où un écran voudra les distinguer, il le dira en
 * appelant l'état par son nom — pas en réécrivant la condition.
 */
export function bailEnCours(bail: { statut?: string | null } | null | undefined): boolean {
	return bail?.statut === 'actif' || bail?.statut === 'en_cours_sortie';
}

/**
 *  Le nom du locataire d'un bail — ou « Locataire non renseigné ».
 *
 *  Écrit une fois le 30/09/2026 (#779) : `mon-lot` le portait en fonction
 *  locale, `OngletAcces` en expression recopiée dans son balisage.
 */
export function nomLocataire(bail: {
	locataire_prenom?: string | null;
	locataire_nom?: string | null;
}): string {
	if (bail.locataire_prenom || bail.locataire_nom) {
		return nomAffiche(bail.locataire_prenom, bail.locataire_nom);
	}
	return 'Locataire non renseigné';
}
