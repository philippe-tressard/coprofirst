#!/usr/bin/env node
/**
 *  Le lien vers les **consignes de la copropriété** se rend par un seul
 *  composant, `LienConsignes` (#779, 01/10/2026).
 *
 *  🔴 Il était écrit TROIS fois — l'accueil, l'annuaire, l'onglet Annuaire de
 *  l'Espace CS — et les copies avaient divergé :
 *
 *  | | Accueil | Annuaire · Espace CS |
 *  |---|---|---|
 *  | libellé | « Consignes **de la** copropriété » | « Consignes **de** copropriété » |
 *  | icône | 📋 | 📄 |
 *  | style | carte, feuille du composant | bouton, `style="…"` en ligne |
 *
 *  Le libellé retenu est celui du manuel et du courriel d'arrivée
 *  (`routers/admin/arrivants.py`) : c'est le nom sous lequel l'arrivant les
 *  reçoit. Les deux FORMES restent — une pastille au bout des raccourcis de
 *  l'accueil (#2397), un bouton au pied d'un annuaire — et se choisissent par
 *  la prop `forme`.
 *
 *  Ce contrôle refuse la quatrième copie : l'adresse de la fiche écrite hors du
 *  composant.
 *
 *  02/10/2026 (#1578) : l'adresse elle-même a quitté le composant pour le client
 *  d'API (`admin.ficheArrivantUrl`, `lib/api/administration.ts`), seule porte de
 *  l'API — `lint:client-api` refuse désormais toute route écrite dans un écran.
 *  Ce contrôle garde ce qui lui est propre : seul `LienConsignes` appelle la
 *  méthode, et la route ne s'écrit nulle part ailleurs que dans le client.
 *
 *  Lancer : node scripts/check-lien-consignes.mjs [--selftest]
 */
import { controler, lignesPortant } from './lib-source-unique.mjs';

/**  L'adresse de la fiche, quelle que soit la façon de l'écrire — ou l'appel de
 *   la méthode du client qui la rend. */
const COPIE = /\/admin\/fiche-arrivant\b|\bficheArrivantUrl\b/;

process.exit(
	controler({
		extensions: ['.svelte', '.ts'],
		sources: ['src/lib/api/administration.ts'],
		temoin: 'src/lib/components/LienConsignes.svelte',
		fautes: lignesPortant(COPIE),
		cas: [
			['\t\thref="/api/admin/fiche-arrivant"', 1],
			["\tconst url = '/api/admin/fiche-arrivant';", 1],
			['\t<a href={`/api/admin/fiche-arrivant`} target="_blank">', 1],
			//  La méthode du client appelée par un autre écran que `LienConsignes`.
			['\t<a href={adminApi.ficheArrivantUrl()} target="_blank">', 1],
			//  La forme voulue, jamais signalée.
			['\t<LienConsignes forme="bouton" />', 0],
			//  Une autre route d'administration des arrivants : hors portée.
			["\tawait api.post('/admin/arrivants/accueil', corps);", 0],
		],
		ok: 'Consignes de la copropriété : liées par LienConsignes seul',
		ko: 'lien(s) vers la fiche des consignes écrit(s) à la main',
		conseil: 'Employer `<LienConsignes forme="pastille" | "bouton" />`.',
	}),
);
