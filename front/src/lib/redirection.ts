/**
 * Conserver la destination pendant l'authentification.
 *
 * Un lien profond partagé — `https://5hostachy.fr/actualites#pub-22` — envoie
 * l'utilisateur sur l'écran de connexion s'il n'a pas de session ouverte. Sans
 * mémoire de la cible, il se connecte et atterrit sur le tableau de bord : le lien
 * qu'on lui a envoyé est perdu, il doit retrouver l'actualité à la main. Signalé le
 * 26/07/2026, aggravé par les ancres ajoutées en v2.25.0 — plus les liens sont
 * précis, plus les perdre coûte cher.
 *
 * La destination voyage dans `?next=`, et n'est suivie que si elle pointe vers ce
 * site : sinon l'écran de connexion deviendrait un tremplin vers un site tiers
 * (« open redirect »), la faille classique de ce mécanisme.
 */

export const APRES_CONNEXION_PAR_DEFAUT = '/tableau-de-bord';

/**
 * Chemin interne du même site ?
 *
 * Accepté : `/actualites#pub-22`. Refusé : `//exemple.test` et `/\exemple.test` (que les
 * navigateurs traitent comme des URL absolues), `https://exemple.test`, et tout ce qui
 * ramène vers l'authentification — une cible `/auth/…` boucle sur elle-même.
 */
export function estCibleInterne(chemin: string | null | undefined): boolean {
	if (!chemin) return false;
	if (!/^\/(?![/\\])/.test(chemin)) return false;
	return !chemin.startsWith('/auth/');
}

/** Chemin courant, fragment compris — c'est lui qui porte l'élément visé. */
export function cheminCourant(): string {
	if (typeof window === 'undefined') return APRES_CONNEXION_PAR_DEFAUT;
	return window.location.pathname + window.location.search + window.location.hash;
}

/**
 *  L'adresse de la mire, **écrite une seule fois** (#1083, 22/09/2026).
 *
 *  Elle l'était six fois, dont trois en clair — et les trois perdaient la page
 *  demandée. Un lien reçu ramenait donc où l'on allait, ou sur le tableau de
 *  bord, selon la porte par laquelle on était entré.
 *
 *  ⚠️ À n'employer que là où il n'y a **rien à conserver** : une déconnexion
 *  volontaire, ou la racine du site qui n'est pas une destination. Partout
 *  ailleurs, `urlDeConnexion()` — qui garde le chemin courant par défaut.
 */
export const CHEMIN_CONNEXION = '/auth/connexion';

/** URL de l'écran de connexion qui saura revenir sur `cible`. */
export function urlDeConnexion(cible?: string): string {
	const destination = cible ?? cheminCourant();
	return estCibleInterne(destination)
		? `${CHEMIN_CONNEXION}?next=${encodeURIComponent(destination)}`
		: CHEMIN_CONNEXION;
}

/**
 * Où aller après une connexion réussie.
 *
 * Le fragment (`#pub-22`) ne franchit pas une redirection 302 : le serveur ne le
 * reçoit jamais, le navigateur le recolle sur l'URL d'arrivée. On le récupère donc
 * depuis l'écran de connexion lui-même quand `next` n'en porte pas.
 */
export function destinationApresConnexion(): string {
	if (typeof window === 'undefined') return APRES_CONNEXION_PAR_DEFAUT;
	const brut = new URLSearchParams(window.location.search).get('next');
	if (!brut) return APRES_CONNEXION_PAR_DEFAUT;
	const cible = !brut.includes('#') && window.location.hash ? brut + window.location.hash : brut;
	return estCibleInterne(cible) ? cible : APRES_CONNEXION_PAR_DEFAUT;
}
