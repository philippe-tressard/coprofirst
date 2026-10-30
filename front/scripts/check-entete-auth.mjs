#!/usr/bin/env node
/**
 *  L'en-tête d'un écran sans session ne s'écrit que par `EnteteAuthentification`
 *  (#2357, 30/10/2026).
 *
 *  Demandé au contrôle visuel de #2313 : « la page d'inscription doit ressembler
 *  à la connexion ». Huit écrans écrivaient l'en-tête à la main — logo de la
 *  charte sur trois, émoji 🏢 🔑 📧 sur quatre, aucun sur le dernier — et le nom
 *  de la résidence y était titre ou sous-titre selon la page.
 *
 *  La FORME d'une copie : la classe `auth-header` ou `auth-logo`, dans un écran
 *  (`.svelte`) comme dans une feuille (`.css`) — une règle de feuille rouvrirait
 *  le style que le composant porte seul.
 *
 *  Lancer : node scripts/check-entete-auth.mjs [--selftest]
 */
import { controler, lignesPortant } from './lib-source-unique.mjs';

const COPIE = /\bauth-(?:header|logo)\b/;

process.exit(
	controler({
		extensions: ['.svelte', '.css'],
		temoin: 'src/lib/components/EnteteAuthentification.svelte',
		fautes: lignesPortant(COPIE),
		cas: [
			['\t\t<div class="auth-header">', 1],
			['\t<span class="auth-logo">&#x1F3E2;</span>', 1],
			['\t\t<header class="auth-header">', 1],
			['.auth-logo {\n\tfont-size: var(--fs-picto-xl);\n}', 1],
			['.auth-header h1 {', 1],
			//  La forme voulue, jamais signalée.
			['\t\t<EnteteAuthentification sousTitre="Créer un compte" />', 0],
			//  Les classes voisines du squelette restent à la feuille commune.
			['<div class="auth-page">\n\t<div class="auth-card card">', 0],
			['\t<p class="auth-consigne">', 0],
			//  Un commentaire qui cite la forme refusée.
			['\t<!-- jadis un <div class="auth-header"> ici -->', 0],
			['/*  `.auth-logo` : retiré le 30/10/2026. */', 0],
		],
		ok: 'En-tête des écrans sans session : tous passent par `EnteteAuthentification`',
		ko: 'en-tête(s) d’authentification écrit(s) hors de `EnteteAuthentification`',
		conseil:
			'Employer `<EnteteAuthentification sousTitre="…" />` (`#lib/components/EnteteAuthentification.svelte`) : logo, nom de la résidence, phrase.',
	}),
);
