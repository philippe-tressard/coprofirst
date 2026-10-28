/**
 * **Lire le pliage d'une section** — et rien d'autre (#1095).
 *
 * Une ligne, mais elle a sa place ici plutôt que dans un écran : le pliage se
 * LIT dans la déclaration, il ne se décide pas. Un second écran qui en aurait
 * besoin recopierait sinon le `?.pliee` et le repli à `false` — et c'est ainsi
 * qu'une règle se met à diverger.
 *
 * ⚠️ `pliable` ne suffit jamais seul : il va avec `valeurModifiee`, la
 * moitié que la table ne peut pas porter puisqu'elle dépend de ce que l'objet
 * CONTIENT. Les séparer laisserait une section pliée cacher une valeur saisie.
 *
 * 🔴 Et cette seconde moitié se calcule contre le DÉFAUT, jamais contre le
 * vide : le périmètre porte toujours « Copropriété entière », les destinataires
 * « Tous ». Tester leur présence rouvrait la section à chaque
 * fois, et rien ne pliait — constaté à l'écran le 21/09/2026, « Visu sans
 * pliages ». `estPerimetreParDefaut` et `concerneTousLesResidents` savent, eux,
 * ce qu'est le défaut.
 */
import { section, type EntiteDeclaree, type IdSection } from '#lib/entites/types.ts';

/** La section est-elle repliée par défaut ? `false` sans déclaration. */
export function pliageDe(entite: EntiteDeclaree | null, id: IdSection): boolean {
	return entite ? !!section(entite, id)?.pliee : false;
}

/**
 * La section porte-t-elle l'astérisque du requis ?
 *
 * 🔴 Elle se LIT ici pour la même raison que le pliage — et parce qu'elle
 * lui est liée : *obligatoire ⇒ déplié*. Deux composants porteurs l'écrivaient
 * en dur (`SectionDestinataires`, `ChampSaisiPour`), si bien que la déclaration
 * ne savait pas que la section était obligatoire — et `lint:etats`, qui calcule
 * le pliage à partir d'elle, ne pouvait pas voir la contradiction.
 *
 * Résultat à l'écran : « DESTINATAIRES* » sur une ligne pliée, ce que la règle
 * interdit. Signalé deux fois (22/09/2026).
 *
 * ⚠️ Et une troisième, par une autre porte (#1186, 24/09/2026) : `ChampsCommuns`
 * portait `perimetreRequis = true`, et la Boîte à idées affichait « PÉRIMÈTRE* »
 * pliée. `lint:pliage-transmis` refuse désormais une prop `requis` vraie par
 * défaut dans un composant porteur.
 */
export function requisDe(entite: EntiteDeclaree | null, id: IdSection): boolean {
	return entite ? !!section(entite, id)?.requis : false;
}
