//  L'onglet vit dans le CHEMIN, pas dans un paramètre : ce `load` le résout, et
//  lui seul. Le composant reçoit un onglet déjà validé — il n'a plus à lire l'URL,
//  ni à se demander quoi faire d'une valeur inconnue.
//
//  Cette page répond à PLUSIEURS adresses (`/espace-cs`, et une par onglet) : c'est
//  `reroute` (`src/hooks.ts`) qui les lui envoie, sans qu'aucun fichier ne soit
//  dupliqué. `url` reste l'adresse demandée — c'est ce qui permet de la lire ici.
import { resoudreOnglet } from '#lib/deepLink.ts';

export const load = ({ url }) => resoudreOnglet('espace-cs', url);
