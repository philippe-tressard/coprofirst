import { parAttribut } from '#lib/table-statuts.ts';
/**
 * Le vocabulaire d'une **demande de modification de profil** — écrit une fois.
 *
 * ## Pourquoi ce fichier (#522)
 *
 * Ces deux tables vivaient dans `profil/+page.svelte`. En extrayant la table
 * d'historique (`HistoriqueDemandes`), je les ai emportées avec elle — et cassé
 * la page, qui s'en sert **aussi** pour la demande en cours, quarante lignes
 * plus haut.
 *
 * Le réflexe suivant aurait été de les recopier des deux côtés. C'est
 * exactement ce que `standards/02` interdit, et le motif de la panne des statuts
 * de ticket (#415, quatre copies dont deux amputées) : deux tables du même
 * vocabulaire sont d'accord le jour où on les écrit, et divergent au premier
 * libellé ajusté — sans que rien ne le signale, puisque chacune est correcte
 * chez elle.
 *
 * ⚠️ Le pendant serveur est `StatutDemande` (`api/app/models/core.py`). Les
 * contextes de build sont `./api` et `./front` : le partage d'un fichier entre
 * les deux est impossible, seule la copie l'est.
 */

/** La classe de badge de chaque état d'une demande. */
const { libelle, badge } = parAttribut({
	en_attente: { libelle: 'En attente', badge: 'badge-yellow' },
	approuvee: { libelle: 'Approuvée', badge: 'badge-green' },
	rejetee: { libelle: 'Rejetée', badge: 'badge-red' },
});

export const STATUT_DEMANDE_BADGE: Record<string, string> = badge;

/** Ce que le résident lit. */
export const STATUT_DEMANDE_LABEL: Record<string, string> = libelle;
