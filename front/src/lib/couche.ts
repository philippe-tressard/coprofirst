/**
 * Une couche superposée — modale, visionneuse — emprunte deux biens communs du
 * document : son DÉFILEMENT et la touche ÉCHAP. Ce module est la seule porte
 * vers l'un et l'autre (#1042, 24/09/2026 ; `npm run lint:couches`).
 *
 * Pourquoi un module et non deux composants soigneux : `Modale` tenait un
 * compteur partagé, `Lightbox` un booléen à elle. Ouverte depuis une modale, la
 * visionneuse rendait le défilement en se fermant — la page défilait derrière
 * une modale encore ouverte. Et chacune écoutait Échap sur `window` : une
 * pression fermait les deux couches d'un coup, saisie comprise.
 *
 * Mutation d'état global (`standards/11-interface-et-ux.md` §12) : la
 * restitution est IDEMPOTENTE et l'appelant la lance depuis chaque sortie —
 * fermeture ET démontage, car on peut naviguer ailleurs sans fermer.
 */

/** Combien de couches tiennent le défilement. État du document, pas d'une instance. */
let verrous = 0;

/** Les couches ouvertes, la plus haute en dernier : Échap ne ferme qu'elle. */
const pileEchap: Array<() => void> = [];

function surTouche(e: KeyboardEvent) {
	if (e.key !== 'Escape' || pileEchap.length === 0) return;
	pileEchap[pileEchap.length - 1]();
}

/**
 * Pose une réponse à Échap SEULE, sans toucher au défilement : une bulle ancrée
 * (`Infobulle`) se ferme à Échap sans figer la page. Elle entre dans la même
 * pile que les couches — ouverte dans une modale, Échap ferme la bulle, pas la
 * modale sous elle (15/10/2026).
 *
 * @returns la fonction qui la retire — idempotente, à appeler à la fermeture
 *          ET au démontage.
 */
export function poserEchap(surEchap: () => void): () => void {
	if (typeof window === 'undefined') return () => {};

	if (pileEchap.length === 0) window.addEventListener('keydown', surTouche);
	pileEchap.push(surEchap);

	let retiree = false;
	return () => {
		if (retiree) return;
		retiree = true;
		//  Retirée par identité, pas par position : une couche du dessous peut se
		//  démonter la première (navigation), et la pile doit rester juste.
		const i = pileEchap.lastIndexOf(surEchap);
		if (i >= 0) pileEchap.splice(i, 1);
		if (pileEchap.length === 0) window.removeEventListener('keydown', surTouche);
	};
}

/**
 * Pose une couche : bloque le défilement du fond et fait de `surEchap` la
 * réponse à Échap tant que la couche est au-dessus.
 *
 * @returns la fonction qui retire la couche — idempotente, à appeler à la
 *          fermeture ET au démontage (`onDestroy`).
 */
export function poserCouche(surEchap: () => void): () => void {
	if (typeof document === 'undefined') return () => {};

	verrous += 1;
	document.body.style.overflow = 'hidden';
	const retirerEchap = poserEchap(surEchap);

	let retiree = false;
	return () => {
		if (retiree) return;
		retiree = true;
		verrous = Math.max(0, verrous - 1);
		if (verrous === 0) document.body.style.overflow = '';
		retirerEchap();
	};
}
