/**
 * Hooks du navigateur — une erreur d'un chargement ou d'une navigation (#1631).
 *
 * Ces erreurs-là, SvelteKit les rattrape pour afficher sa page d'erreur : elles
 * n'atteignent jamais les écouteurs `error` et `unhandledrejection` posés par
 * `initTelemetry`. Sans ce hook, un écran qui ne se charge plus ne laisserait
 * aucune trace côté serveur — c'est ce que #1631 vient fermer.
 *
 * Ne sont PAS signalées : une 404 — une adresse inconnue n'est pas une panne
 * d'écran —, et une erreur « attendue » levée par `error()` (`kind: 'app'`).
 * SvelteKit 3 passe au hook TOUTES les erreurs, étiquetées par `kind` ; SvelteKit 2
 * ne lui donnait que les imprévues et les adresses inconnues (#2205).
 *
 * Il rend aussi la phrase de la page d'erreur à la place du message anglais du
 * framework (#2304) — la même que le hook du serveur, par `#lib/erreur-page`.
 */
import type { HandleClientError } from '@sveltejs/kit/hooks';
import { codeErreur, signalerErreur } from '#lib/telemetry.ts';
import { messageDErreur } from '#lib/erreur-page.ts';

export const handleError: HandleClientError = ({ kind, error }) => {
	if (kind === 'app') return;
	const statut = kind === 'framework' ? error.status : 500;
	if (statut !== 404) signalerErreur(codeErreur(error));
	return messageDErreur(kind, statut);
};
