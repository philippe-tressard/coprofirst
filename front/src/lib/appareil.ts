/**
 * Reconnaître l'appareil qui ouvre le site — pour lui proposer l'application iOS.
 *
 * Fonctions PURES, qui reçoivent ce qu'elles lisent : un test les juge sans
 * navigateur (`appareil.test.ts`), et l'appelant seul touche à `navigator`.
 */

/** Ce qu'on lit du navigateur — un sous-ensemble de `Navigator`, pour pouvoir le fournir. */
export interface LectureNavigateur {
	userAgent: string;
	maxTouchPoints?: number;
	/** `true` quand le site est ouvert depuis l'écran d'accueil (iOS seulement). */
	standalone?: boolean;
}

/**
 * Un iPhone, un iPad ou un iPod : les appareils sur lesquels l'App Store existe.
 *
 * ⚠️ Un iPad récent (iPadOS 13+) se présente comme un Mac : son agent dit
 * « Macintosh ». Ce qui le trahit, c'est l'écran tactile — un Mac n'en a pas.
 */
export function estAppareilApple(nav: LectureNavigateur): boolean {
	if (/iPhone|iPad|iPod/.test(nav.userAgent)) return true;
	return /Macintosh/.test(nav.userAgent) && (nav.maxTouchPoints ?? 0) > 1;
}

/**
 * Le site est-il ouvert depuis l'écran d'accueil (la PWA installée) ? Alors
 * l'appareil l'a déjà installé : lui proposer une autre installation serait une
 * redite. `standalone` est propre à Safari ; `display-mode` est le standard.
 */
export function estEcranAccueil(nav: LectureNavigateur, plein: boolean): boolean {
	return nav.standalone === true || plein;
}

/** L'encart « installer l'application iOS » doit-il s'afficher ? */
export function proposerAppliIos(nav: LectureNavigateur, plein: boolean): boolean {
	return estAppareilApple(nav) && !estEcranAccueil(nav, plein);
}
