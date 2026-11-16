/**
 * Les règles d'un mot de passe, côté écran (#2763).
 *
 * ## La longueur minimale est celle du serveur
 *
 * Le serveur la porte une fois (`api/app/utils/mots_de_passe.py`), et la publie
 * aux apps (`constantes-clients.json`, `longueurMinMotDePasse`). Le site
 * l'écrivait en chiffres à neuf endroits — condition, message, critère de la
 * jauge, attribut `minlength` : la monter au serveur aurait laissé l'écran
 * annoncer l'ancienne valeur et accepter l'envoi que le serveur refuse.
 *
 * Front et API ne partagent aucun fichier (mémoire
 * `project_partage_front_api_impossible`) : cette copie est tenue par
 * `api/tests/test_longueur_mot_de_passe_front.py`, qui la compare au serveur et
 * refuse qu'un écran réécrive la valeur — seuil ou message.
 */

/** Le nombre de caractères qu'un mot de passe doit atteindre. */
export const LONGUEUR_MIN_MOT_DE_PASSE = 8;
