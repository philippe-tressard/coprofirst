import type { RequestHandler } from './$types';
import { config as configApi } from '#lib/api/index.ts';
import { NOM_SITE_PAR_DEFAUT } from '#lib/configSite.ts';
import { lireConfigServeur } from '#lib/server/config-site.ts';

/**
 * Le manifeste de l'application installée — servi, et non plus généré au build.
 *
 * 🔴 Il portait « 5Hostachy » en dur (`vite.config.ts`) : le nom de CETTE
 * résidence, sur l'écran d'accueil du téléphone de toute autre. Arbitré le
 * 07/10/2026 (#1725) : l'application installée porte le nom de la RÉSIDENCE,
 * celui que l'administration saisit (`site_nom`), pas celui de la plateforme.
 * Un même code servant plusieurs domaines (phase 2 du chantier multi-copropriétés)
 * ne pourrait de toute façon pas en figer un au build.
 *
 * ⚠️ `Cache-Control: no-cache`, comme le pose Caddy sur cette adresse : un nom
 * changé doit atteindre le navigateur à sa prochaine visite.
 */
export const GET: RequestHandler = async ({ url }) => {
	const cfg = await lireConfigServeur(url.host);
	const nom = (cfg['site_nom'] ?? '').trim() || NOM_SITE_PAR_DEFAUT;
	//  Les icônes (#1728) : le logo de la résidence s'il a été téléversé,
	//  redimensionné par l'API ; sinon les icônes neutres du dossier statique.
	const logo = cfg['site_logo'] ?? '';
	const icone = (taille: number) => ({
		src: logo ? configApi.logoUrl(taille, logo) : `/icons/icon-${taille}.png`,
		sizes: `${taille}x${taille}`,
		type: 'image/png',
	});
	const manifeste = {
		name: nom,
		short_name: nom,
		description: 'Application de gestion de copropriété',
		//  Les couleurs du navigateur autour de l'application installée : celles
		//  de la charte (`--color-primary`, fond de page), que le manifeste ne
		//  peut pas lire par une variable CSS.
		theme_color: '#1E3A5F',
		background_color: '#ffffff',
		display: 'standalone',
		start_url: '/',
		icons: [icone(192), icone(512)],
	};
	return new Response(JSON.stringify(manifeste), {
		headers: {
			'Content-Type': 'application/manifest+json; charset=utf-8',
			'Cache-Control': 'no-cache, must-revalidate',
		},
	});
};
