//  Trois adresses, un écran : `/sondages`, `/idees` et `/annonces` sont rendues
//  par cette route — `reroute` (`src/hooks.ts`) leur envoie les deux dernières.
//  `url` reste l'adresse demandée, et c'est elle qui dit la rubrique.
import { resoudreOnglet } from '#lib/deepLink.ts';

export const load = ({ url }) => resoudreOnglet('communaute', url);
