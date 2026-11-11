/*
 *  **L'étiquette des tests de MISE EN PAGE, joués aussi sous WebKit** (#2640, 11/11/2026).
 *
 *  La CI ne jouait que Chromium : un défaut propre à Safari — le navigateur de
 *  tous les iPhone — n'était vu par aucun contrôle. Le 10/11, la liste des heures
 *  de la sauvegarde faisait 22 px sous Safari contre 37 pour son voisin (#2639) :
 *  le spec passait sous Chromium, échouait sous WebKit, et c'est l'auteur qui l'a
 *  vu à l'écran.
 *
 *  Les profils `webkit-bureau` et `webkit-mobile` (`playwright.config.ts`) ne
 *  jouent que les tests qui portent cette étiquette : ceux qui MESURENT la mise en
 *  page — hauteurs, alignements, défilement horizontal, cibles tactiles. Un test
 *  qui mesure le défilement par `attendreSansDefilementHorizontal` la porte
 *  d'office : `npm run lint:defilement` le refuse sans elle.
 *
 *  Aucun import ici : la configuration de Playwright lit ce module, et elle ne
 *  doit pas charger les aides des tests.
 */

/**
 *  L'étiquette, écrite à la FIN du titre du test (`test('… @mise-en-page', …)`) :
 *  Playwright y lit les étiquettes. Passée en argument (`{ tag }`), elle forçait
 *  Prettier à réindenter le corps de chaque test — mille lignes de bruit pour 44.
 */
export const ETIQUETTE_MISE_EN_PAGE = '@mise-en-page';

/** Ce que les profils WebKit retiennent : les tests qui portent l'étiquette. */
export const RETENUS_SOUS_WEBKIT = new RegExp(`${ETIQUETTE_MISE_EN_PAGE}\\b`);
