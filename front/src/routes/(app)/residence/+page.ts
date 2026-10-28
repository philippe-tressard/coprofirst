//  L'onglet vit dans le CHEMIN, pas dans un paramètre : ce `load` le résout, et
//  lui seul. Le composant reçoit un onglet déjà validé.
//
//  `/residence` et `/residence/carnet` arrivent toutes deux ici — c'est `reroute`
//  (`src/hooks.ts`) qui les y envoie, sans qu'aucun écran ne soit déplacé ni
//  dupliqué. Un chemin non déclaré n'est pas traduit, donc SvelteKit rend une
//  404 : se replier sur le premier onglet ferait passer `/residence/carnett`
//  pour une adresse valide, et le lien cassé survivrait.
import { resoudreOnglet } from '#lib/deepLink.ts';

export const load = ({ url }) => resoudreOnglet('residence', url);
