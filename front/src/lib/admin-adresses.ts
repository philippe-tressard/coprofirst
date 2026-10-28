/**
 * Les anciennes adresses de l'administration — servies, jamais cassées (#2062).
 *
 * ## Pourquoi ce fichier
 *
 * Le rangement par niveau (21/10/2026) a fondu les trois onglets d'import en un
 * seul, et scindé « Paramétrage site » en Copropriété › Fonctionnement et
 * Présentation › Connexion et pied de page. Leurs clés (`?onglet=import_tc`…)
 * vivent pourtant ailleurs que dans le code : dans les courriels déjà envoyés —
 * le modèle « Arrivée d'un nouveau résident » renvoie à `import_tc` —, dans les
 * favoris, dans les notes de qui administre. Sans cette table, la page les lirait
 * comme une clé inconnue et ouvrirait son premier onglet, sans un mot.
 *
 * Les autres pages servent leurs anciennes adresses par `reroute` et
 * `resoudreOnglet` (`#lib/deepLink`) ; l'administration, restée sur `?onglet=`
 * (« sauf admin »), les sert ici, dans le `load` de sa page, en **308**.
 *
 * ⚠️ Une clé ne se retire JAMAIS de cette table : le courriel qui la porte a
 * peut-être six mois. 🔒 `e2e/admin-groupes.spec.ts` parcourt toutes les clés
 * d'avant le rangement et exige que chacune ouvre un onglet.
 */

/** Ancienne clé → l'adresse qui la sert désormais (paramètres compris). */
export const ANCIENNES_CLES_ADMIN: Readonly<Record<string, string>> = {
	//  « Paramétrage site » : sa section principale est devenue Fonctionnement.
	site: 'onglet=fonctionnement',
	import_lots: 'onglet=imports&source=lots',
	import_tc: 'onglet=imports&source=telecommandes',
	import_vigik: 'onglet=imports&source=vigik',
};

/**
 * PURE. L'adresse actuelle d'une ancienne adresse d'administration, ou `null`
 * si elle n'en est pas une. Les autres paramètres (`src=courriel:…`) suivent.
 */
export function adresseActuelleAdmin(url: URL): string | null {
	const cle = url.searchParams.get('onglet');
	const cible = cle ? ANCIENNES_CLES_ADMIN[cle] : undefined;
	if (!cible) return null;
	const params = new URLSearchParams(cible);
	for (const [k, v] of url.searchParams) if (k !== 'onglet' && !params.has(k)) params.append(k, v);
	return `${url.pathname}?${params.toString()}`;
}
