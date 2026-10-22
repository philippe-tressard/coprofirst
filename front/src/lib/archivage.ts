/**
 * Le délai d'archivage, côté écran — **une seule lecture** (#515 point 2).
 *
 * ## Pourquoi ce fichier
 *
 * Deux écrans calculaient l'archivage dans le navigateur, chacun avec sa propre
 * clé de configuration et son propre défaut (48 **heures** pour l'un, 30 **jours**
 * pour l'autre), pour la même question : « à partir de quand un contenu quitte les
 * listes actives ? »
 *
 * ## 🔴 Et aucune des deux clés n'était lue
 *
 * `configStore` est alimenté par `GET /config`, qui filtre par **liste blanche**
 * (`_PUBLIC_KEYS`, durcie le 26/07/2026 après une fuite de 31 clés). Aucune des deux
 * n'y figure — les deux lectures rendaient `undefined` depuis toujours, et les deux
 * écrans tournaient sur leur valeur en dur.
 *
 * Le réglage de l'administration n'a donc **jamais** gouverné le calendrier ni le
 * tableau de bord. Personne ne s'en est aperçu : un défaut qui vaut la même chose
 * que le réglage courant est indiscernable d'un réglage qui fonctionne.
 *
 * ## ✅ Le CALENDRIER n'appelle plus ce module (02/09/2026)
 *
 * Ce fichier annonçait sa propre sortie : *« la vraie sortie est que ces deux
 * écrans cessent de calculer l'archivage et lisent ce que l'API leur envoie »*.
 * C'est fait pour le calendrier — `evenementArchive()` a été **supprimée**, et
 * l'écran lit `e.archivee`, calculé par `app/utils/archivage.py`.
 *
 * Trois écarts sont tombés avec elle : l'annulation devient immédiate, l'épinglage
 * protège, et surtout **le réglage de l'administration gouverne enfin le
 * calendrier** — ce qu'il n'avait jamais fait, la clé n'étant pas publique.
 *
 * Le tableau de bord a suivi le 17/10/2026 (#2060) : son seuil « récent » est le
 * délai que l'API envoie avec le fil (`FluxResponse.delai_recent_jours`). Il
 * restait au défaut en dur, la clé n'étant pas publique — et la publier aurait
 * exposé un réglage de plus sur un endpoint anonyme pour un confort d'affichage.
 *
 * ⚠️ `DELAI_ARCHIVAGE_JOURS` est une **copie** de `ARCHIVAGE_DELAI_JOURS`
 * (`api/app/utils/archivage.py`). Les contextes de build sont `./api` et
 * `./front` : rien de la racine n'entre dans les images, le partage d'un fichier
 * est impossible, seule la copie l'est.
 */
/** Le défaut du site, en jours. Copie assumée de la valeur serveur. */
export const DELAI_ARCHIVAGE_JOURS = 30;

/**
 * Le délai en vigueur, en jours : `archivage_delai_jours` s'il est disponible,
 * sinon le défaut (même règle que `seuil_archivage_jours` côté API). L'ancien repli
 * sur `publie_visibilite_jours` est retiré (#2059).
 */
export function delaiArchivageJours(config: Record<string, string> | null | undefined): number {
	const unique = parseInt(config?.['archivage_delai_jours'] ?? '');
	if (Number.isFinite(unique) && unique > 0) return unique;
	return DELAI_ARCHIVAGE_JOURS;
}

/** Le seuil « récent » de l'accueil, en millisecondes : le délai que l'API envoie
 *  avec le fil (#2060) — le défaut tant que le fil n'est pas arrivé. */
export function seuilRecentMs(jours: number | null | undefined): number {
	return (jours && jours > 0 ? jours : DELAI_ARCHIVAGE_JOURS) * 86_400_000;
}
