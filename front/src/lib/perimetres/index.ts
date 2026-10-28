/**
 * `#lib/perimetres` — l'arborescence des périmètres et leurs libellés.
 *
 * Paquet depuis le 10/09/2026 : le fichier unique avait franchi les 500 lignes.
 * La césure reprend celle du serveur — `arbre` décrit la STRUCTURE, `libelles`
 * dit comment elle s'ÉCRIT.
 *
 * Rien d'autre n'a bougé : tout ce que ce paquet réexporte s'importait déjà
 * depuis `#lib/perimetres`, et continue de s'importer ainsi.
 */
export * from './arbre';
export * from './libelles';
