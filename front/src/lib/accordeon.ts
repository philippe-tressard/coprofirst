/**
 * L'ACCORDÉON — déplier un bloc replie les autres. Écrit une fois (30/09/2026).
 *
 * ## Demandé
 *
 * > « quand on déplie une section Admin/IA ça replie les autres (c'est une bonne
 * >   pratique de pliage / dépliage qui doit s'appliquer sans exception) »
 *
 * Arbitré le même jour : **partout, formulaires compris**.
 *
 * ## 🔴 Pourquoi un module
 *
 * L'audit du 30/09/2026 a trouvé sept listes déjà en accordéon, et **cinq
 * écritures différentes** de « un seul ouvert » (`string|null`, `number|null`,
 * `Set` remis à un élément, `Record` remis à une clé, `EtatDepliable`) — et
 * autant d'écrans où plusieurs blocs s'ouvraient ensemble, faute d'y avoir
 * pensé. Trois formes, ici, couvrent tous les cas :
 *
 * | Le bloc… | Forme |
 * |---|---|
 * | est un élément d'une liste que tient UN composant | `basculer(ouvert, id)` — un identifiant, jamais un `Set` |
 * | vit dans un composant qui ne connaît pas ses voisins (section de formulaire, réponses) | `membre(groupe, replier)` |
 * | est une carte d'une `listeDepliable` que d'autres listes côtoient (annuaires) | `listeMembre(groupe, lire, ecrire)` |
 * | est un `<details>` natif (message d'origine, extraits d'un contenu riche) | `unSeulDetailsOuvert()`, posé une fois par le layout |
 *
 * ## Les deux exceptions ARBITRÉES — et elles seules
 *
 * - **Une section de formulaire dont la valeur n'est plus celle du défaut** reste
 *   ouverte : `SectionFormulaire` ne replie jamais ce qui cache une saisie. Seules
 *   les sections restées au défaut se replient quand on en ouvre une autre.
 * - **Une carte en correction** reste ouverte à côté de celle qu'on lit
 *   (prestataires, contrats, FAQ, périmètres, annuaires) : replier abandonnerait
 *   la saisie.
 */
import { tick } from 'svelte';
import { writable, type Writable } from 'svelte/store';
//  ⚠️ `import type` seulement : l'autotest charge ce module sous Node, sans
//  l'alias `$lib` (`scripts/check-accordeon.mjs`).
import type { EtatDepliable } from '$lib/listeDepliable';
import { mouvementReduit } from '$lib/mouvement';

/**
 * Ramène le HAUT d'un bloc à l'écran s'il n'y est plus.
 *
 * 🔴 Le complément obligé de l'accordéon (30/09/2026, signalé dans Admin › IA :
 * « quand tu ouvres une section, tu te trouves à la fin de la section ouverte »).
 * Replier le bloc ouvert AU-DESSUS remonte tout ce qui suit de sa hauteur : la
 * fenêtre, restée où elle était, tombe dans le bas de celui qu'on vient d'ouvrir.
 *
 * « Visible » = le haut est dans la fenêtre, sous l'en-tête fixe du téléphone —
 * la marge est celle que le CSS pose (`scroll-margin-top`, `normes.css`), pour
 * qu'une seule valeur dise où s'arrête le défilement. Exiger que le bloc tienne
 * en entier ferait défiler sur tout bloc long, y compris celui qu'on regarde.
 * Écrit d'abord pour `FormulaireCreation` (10/09/2026), qui l'emploie aussi.
 */
export function amenerEnVue(el: Element | null | undefined): void {
	if (!el || typeof window === 'undefined') return;
	const r = el.getBoundingClientRect();
	const marge = parseFloat(getComputedStyle(el).scrollMarginTop) || 0;
	if (r.top >= marge && r.top <= window.innerHeight - 80) return;
	const doux = !mouvementReduit();
	el.scrollIntoView({ behavior: doux ? 'smooth' : 'auto', block: 'start' });
}

/**
 * Place le HAUT d'un bloc en haut de l'écran, sous l'en-tête fixe — TOUJOURS,
 * qu'il soit visible ou non (#2082).
 *
 * Le pendant d'`amenerEnVue` pour un geste qui OUVRE le bloc suivant : après
 * l'enregistrement du CR d'une affaire, l'affaire suivante se déplie et son
 * titre doit se trouver en haut de l'écran — *« c'est très perturbant de perdre
 * le fil des affaires »*. À appeler APRÈS le rendu (`tick`) : le repli du bloc
 * précédent déplace tout ce qui suit.
 */
export function amenerEnHaut(el: Element | null | undefined): void {
	if (!el || typeof window === 'undefined') return;
	const doux = !mouvementReduit();
	el.scrollIntoView({ behavior: doux ? 'smooth' : 'auto', block: 'start' });
}

/** PURE. Le bloc ouvert après un clic sur `id` : lui, ou plus rien s'il l'était. */
export function basculer<T>(ouvert: T | null, id: T): T | null {
	return ouvert === id ? null : id;
}

//  Les groupes nommés : les membres d'un même groupe ne se connaissent pas, ils
//  partagent seulement QUI est ouvert. ⚠️ État de module, donc partagé côté
//  serveur entre les requêtes : il ne porte qu'une identité d'objet, posée par
//  un clic — jamais au rendu serveur —, et rendue à la destruction du membre.
const groupes = new Map<string, Writable<object | null>>();

function groupe(nom: string): Writable<object | null> {
	let g = groupes.get(nom);
	if (!g) {
		g = writable(null);
		groupes.set(nom, g);
	}
	return g;
}

/** Les groupes connus — un nom recopié à la main dans un composant ne
 *  rejoindrait personne, en silence. */
export type NomGroupe = 'sections-formulaire' | 'reponses' | 'annuaires';

export interface Membre {
	/** À l'ouverture de CE bloc : les autres membres se replient, et `el` —
	 *  le bloc ouvert — est ramené à l'écran une fois le rendu fait. */
	prendre(el?: Element | null): void;
	/** À sa destruction (`onDestroy`) : il cesse d'écouter et rend la main. */
	liberer(): void;
}

/**
 * Inscrit un bloc dans un groupe. `replier` est appelé quand un AUTRE membre
 * s'ouvre — au composant d'y dire ce que replier veut dire pour lui (une
 * section modifiée, une carte en correction ne se replient pas).
 */
export function membre(nom: NomGroupe, replier: () => void): Membre {
	const g = groupe(nom);
	const moi = {};
	const desabonner = g.subscribe((ouvert) => {
		if (ouvert !== null && ouvert !== moi) replier();
	});
	return {
		prendre: (el) => {
			g.set(moi);
			if (el) tick().then(() => amenerEnVue(el));
		},
		liberer: () => {
			desabonner();
			g.update((ouvert) => (ouvert === moi ? null : ouvert));
		},
	};
}

/**
 * Tous les `<details>` natifs de la page : en ouvrir un referme les autres —
 * sauf ceux qui le CONTIENNENT (on ne replie pas le bloc dans lequel on lit).
 *
 * ⚠️ Écouté en CAPTURE : `toggle` ne remonte pas, mais la capture le voit
 * passer. Un `<details>` piloté par son parent (`BlocUsageIA`) reçoit alors
 * son propre `toggle` et en informe le parent, comme pour un clic.
 *
 * Rend la fonction de retrait — pour `onMount`.
 */
export function unSeulDetailsOuvert(): () => void {
	function surBascule(e: Event) {
		const ouvert = e.target;
		if (!(ouvert instanceof HTMLDetailsElement) || !ouvert.open) return;
		let replie = false;
		for (const autre of document.querySelectorAll('details[open]')) {
			if (autre !== ouvert && !autre.contains(ouvert)) {
				(autre as HTMLDetailsElement).open = false;
				replie = true;
			}
		}
		if (replie) amenerEnVue(ouvert);
	}
	document.addEventListener('toggle', surBascule, true);
	return () => document.removeEventListener('toggle', surBascule, true);
}

/**
 * Une liste dépliable MEMBRE d'un accordéon qui la dépasse (30/09/2026) — les
 * deux annuaires de l'Espace CS n'ont qu'une carte ouverte à eux deux.
 *
 * `ouvrir` remplace les affectations directes de l'état pour tout geste qui
 * OUVRE une carte (déplier, éditer, ajouter) : c'est là que la liste prend la
 * main. Quand une autre liste la prend, celle-ci se replie — sauf une carte en
 * correction, qui reste ouverte (exception arbitrée : la saisie serait perdue).
 */
export function listeMembre(
	nom: NomGroupe,
	lire: () => EtatDepliable,
	ecrire: (etat: EtatDepliable) => void,
): { ouvrir(etat: EtatDepliable): void; liberer(): void } {
	const m = membre(nom, () => {
		const etat = lire();
		if (etat.edite === null && etat.ouvert !== null) ecrire({ ...etat, ouvert: null });
	});
	return {
		ouvrir(etat) {
			ecrire(etat);
			if (etat.ouvert !== null) m.prendre();
		},
		liberer: m.liberer,
	};
}
