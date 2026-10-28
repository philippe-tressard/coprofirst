/**
 * Le garde de démarrage — une page qui ne se dessine pas se recharge, puis le dit (#1993).
 *
 * Le 15/10/2026, au premier chargement après trois MEP, la page de connexion
 * d'un Chrome qui avait déjà la PWA est restée BLANCHE et figée ; le second
 * chargement était normal. La cause exacte n'a pas été reproduite (trois bancs :
 * service worker d'une version aux commandes d'une autre, Chromium sans tête puis
 * Chrome réel). Ce qui est sûr : une page rendue par le serveur ne reste blanche
 * que si une ressource qui bloque le premier dessin — une feuille de `<head>` —
 * ne répond pas, ou si le démarrage ne s'exécute pas. Rien, alors, ne le disait :
 * ni la page, ni le bandeau de mise à jour (`MajDisponible`), qui vit DANS
 * l'application et ne tourne donc pas quand elle ne démarre pas.
 *
 * Le garde (`src/garde-demarrage.js`) est servi inline, premier script de
 * `<head>` (`hooks.server.ts` remplace son repère dans `app.html`) : il
 * s'exécute avant les feuilles et le code de l'application, donc même quand eux
 * ne viennent pas. Deux constats, mesurés tant que l'onglet est VISIBLE — un
 * onglet caché ne dessine rien, et ce n'est pas une panne :
 *
 *  1. rien n'est dessiné après 10 s (`first-contentful-paint` absent) →
 *     recharger, une fois par tranche de cinq minutes, en désinscrivant le
 *     service worker : c'est le geste de Ctrl+Maj+R, le contournement qui avait
 *     marché. Si le rechargement n'y suffit pas, lâcher les feuilles qui ne
 *     répondent pas — ce qui rend le dessin possible — et dire quoi faire ;
 *  2. dessinée, mais l'application n'a pas démarré après 20 s → le dire, sans
 *     recharger d'autorité : le champ d'adresse marche sans l'application, et
 *     une saisie en cours serait perdue ;
 *  3. dessinée SANS sa feuille principale (24/10/2026 : une tablette rouverte le
 *     lendemain affichait la page brute d'avant une MEP, dont les feuilles aux
 *     noms hachés n'existaient plus) → recharger, comme au 1, puis le dire.
 *     Jugé au chargement complet, au retour sur l'onglet et à la restauration
 *     depuis le cache de navigation, démarrée ou non : la variable témoin
 *     `--feuille-principale` de `styles/socle.css` manque au style calculé.
 *
 * Il apprend que tout va bien par ce marqueur, posé depuis le `onMount` du
 * layout racine : quand il est là, le code de l'application a tourné. Le
 * message, s'il est déjà affiché, se retire alors de lui-même.
 *
 * 🔒 `e2e/garde-demarrage.spec.ts` (les trois cas, et le silence d'une page
 * saine) · `api/tests/test_pwa_maj.py` (le branchement).
 *
 * ⚠️ Le garde lit ce même nom et cette même valeur : il est inline, donc ne peut
 * rien importer. `api/tests/test_pwa_maj.py` vérifie que les deux concordent.
 */
import { version } from '../../package.json';
import { envoyerMaintenant, signalerErreur } from '#lib/telemetry.ts';

export const ATTRIBUT_DEMARRAGE = 'data-application';
export const VALEUR_DEMARREE = 'demarree';

/**
 * **Mesurer ce qu'on n'a pas su reproduire** (arbitré par la coordination le
 * 17/10/2026, sur délégation de Philippe). Avant un rechargement de secours —
 * automatique ou par son bouton —, le garde note son MOTIF dans l'onglet ; la
 * page qui démarre ensuite le signale UNE fois au journal des erreurs du
 * navigateur (`api/app/utils/erreurs_navigateur.py`, Admin › Télémétrie,
 * « Erreurs vues par les résidents ») : `garde-demarrage:<motif>:v<version>`.
 * Ni adresse ni saisie — la page, le code, le jour, comme toute erreur.
 * ⚠️ La clé et les motifs sont écrits aussi dans le garde (inline) :
 * `api/tests/test_pwa_maj.py` les compare.
 */
export const CLE_MOTIF = 'garde-demarrage-motif';
export const MOTIFS = ['non-dessinee', 'non-demarree', 'non-stylee'] as const;
export const PREFIXE_CODE = 'garde-demarrage';

/** Le code d'un rechargement de secours, ou `null` s'il n'y en a pas eu. */
export function codeRechargementDeSecours(motif: string | null): string | null {
	if (!motif || !(MOTIFS as readonly string[]).includes(motif)) return null;
	return `${PREFIXE_CODE}:${motif}:v${version}`;
}

function signalerRechargementDeSecours() {
	let motif: string | null;
	try {
		motif = sessionStorage.getItem(CLE_MOTIF);
		sessionStorage.removeItem(CLE_MOTIF);
	} catch {
		return; // stockage refusé : le garde n'a rien pu noter
	}
	const code = codeRechargementDeSecours(motif);
	if (!code) return;
	signalerErreur(code);
	envoyerMaintenant();
}

/** Pose le marqueur, signale un rechargement de secours. Rend la fonction qui retire le marqueur. */
export function signalerDemarrage(): () => void {
	if (typeof document === 'undefined') return () => {};
	document.documentElement.setAttribute(ATTRIBUT_DEMARRAGE, VALEUR_DEMARREE);
	signalerRechargementDeSecours();
	return () => document.documentElement.removeAttribute(ATTRIBUT_DEMARRAGE);
}
