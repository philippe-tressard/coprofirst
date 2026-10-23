/**
 * Le mouvement, côté script — ce que le CSS ne peut pas dire seul (#2169).
 *
 * Les durées et les courbes vivent dans la charte (`styles/socle.css`,
 * `lint:mouvement`) : un script ne les écrit jamais. Il pose une classe ou une
 * valeur, le CSS anime, et le script ATTEND ce que le navigateur déclare —
 * jamais une durée recopiée dans un `setTimeout`.
 */

/** La personne a demandé moins de mouvement (réglage du système). */
export function mouvementReduit(): boolean {
	return (
		typeof window !== 'undefined' &&
		!!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
	);
}

/**
 * Attend la fin — ou l'annulation — des animations et transitions en cours sur
 * `el`, sans ses descendants. À appeler APRÈS le changement de style qui les
 * lance (une classe posée, puis `tick()` si Svelte la pose).
 *
 * 🔴 Pourquoi pas `transitionend` : une transition qui ne démarre pas — valeur
 * déjà atteinte, durée nulle, animation d'entrée encore en cours — n'en émet
 * aucun, et l'élément attendait pour toujours. Un toast fermé pendant son
 * entrée restait ainsi invisible dans la pile (#2168, `e2e/toast.spec.ts`).
 */
export async function finDesAnimations(el: Element): Promise<void> {
	await Promise.allSettled(el.getAnimations().map((a) => a.finished));
}
