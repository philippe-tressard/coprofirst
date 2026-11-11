//  La durée d'un avis bref (le « toast »), sortie de `Toast.svelte` (#2634).
//
//  🔒 Table PUBLIÉE aux clients (`tables-clients.json`, #2634) : l'app iOS la lit
//  dans la release au lieu du code du site. Littérale — le registre la lit sans
//  rien exécuter ; la retirer ou en changer la forme s'annonce
//  (`npm run lint:tables-clients`).

/** Combien de temps un avis reste à l'écran, par défaut, en millisecondes. */
export const DUREE_TOAST_MS = 4000;
