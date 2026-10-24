/**
 *  L'historique d'une tâche planifiée : ses colonnes, et de quoi les remplir.
 *
 *  🔴 Sorti de `TachesPlanifiees.svelte` le 07/09/2026, qui dépassait son
 *  plafond de modularité. Ce qui part ici est de la DONNÉE et du calcul sur la
 *  donnée — quelles colonnes existent, laquelle a quelque chose à montrer,
 *  comment se lit un nombre d'octets. Ça bouge quand une tâche nouvelle
 *  rapporte un champ nouveau ; le tableau, lui, bouge pour d'autres raisons.
 *
 *  ⚠️ La table était déclarée DEUX fois dans le balisage : une condition
 *  `aValeur(lignes, …)` pour l'en-tête, la même pour la cellule, neuf fois de
 *  suite. Une colonne ajoutée d'un seul côté décalait tout le tableau — un
 *  `<th>` de plus que de `<td>` ne lève rien, il déplace les valeurs d'une
 *  case, et le lecteur voit une durée sous « Taille ».
 */
import type { ExecutionTache, ExecutionTelemetrie } from '$lib/api';
import { fmtDatetime } from '$lib/date';
import { champDe, fmtOctets } from '$lib/utils';

//  Taille DB et Détail ne sont renseignés que par la maintenance applicative.
//  Ils ne sont PAS structurellement vides : ils l'étaient parce qu'aucun
//  rapport de maintenance n'arrivait. La colonne apparaît donc dès qu'une
//  ligne la renseigne, et disparaît sinon — plutôt que d'être supprimée, ce
//  qui aurait effacé une donnée à cause d'un défaut de remontée.
//  Étendu le 11/08/2026 au NŒUD et à la DURÉE : `historique_sauvegarde` et
//  `historique_telemetrie` n'ont ni l'une ni l'autre de ces colonnes, et le
//  tableau affichait donc quatre tirets alignés — l'utilisateur les a lus
//  comme un historique « incomplet », ce qui est exactement ce qu'une colonne
//  vide raconte. Une colonne qu'aucune ligne ne renseigne ne s'affiche pas.
export const aValeur = (lignes: readonly object[], champ: string) =>
	lignes.some((l) => {
		const v = champDe(l, champ);
		return v !== null && v !== undefined && v !== '';
	});

//  Colonnes propres à la sauvegarde et à l'agrégation. Elles vivaient dans les
//  deux cartes supprimées avec #299, et la ligne dépliée ne savait pas les
//  rendre : la taille des archives, le déclencheur, le volume agrégé et les
//  lignes purgées avaient donc disparu de l'écran. Signalé par l'utilisateur
//  le 11/08/2026 — la compensation portait sur la PROFONDEUR de l'historique
//  et j'avais manqué sa LARGEUR.
//
//  Chacune suit la même règle que Taille DB et Détail : présente dès qu'une
//  ligne la renseigne, absente sinon. Une tâche ne montre donc que les
//  colonnes que sa table sait remplir.
export const CHAMPS_PURGE = ['events_purges', 'daily_purges', 'monthly_purges'] as const;

//  0 est une valeur, pas une absence : `aValeur` ne retient que null, undefined
//  et la chaîne vide. Une purge qui n'a rien eu à purger doit s'afficher « 0 ».
export const aPurges = (lignes: readonly object[]) => CHAMPS_PURGE.some((c) => aValeur(lignes, c));

export const totalPurges = (l: ExecutionTache): number =>
	CHAMPS_PURGE.reduce((somme, c) => somme + (Number(champDe(l, c)) || 0), 0);

//  « 1 jour · 0 mois » — le pluriel suit le nombre de JOURS, comme dans la
//  carte d'origine ; les mois gardent leur forme courte.
export const fmtAgrege = (l: ExecutionTelemetrie): string =>
	`${l.jours_agreges} jour${l.jours_agreges > 1 ? 's' : ''} · ${l.mois_agreges} mois`;

/**
 *  Les clés du « Détail » que l'écran sait dire en français — celles des
 *  contrôles de fiabilité. Une clé inconnue s'affiche telle quelle (bascule,
 *  mise à jour…) : ce tableau ne décide pas de ce que les autres tâches écrivent.
 *  `fail: 0 · warn: 0` se lisait pareil pour 74 contrôles verts et pour aucun.
 */
const LIBELLES_DETAIL: Record<string, string> = {
	ok: 'contrôles OK',
	fail: 'échecs',
	warn: 'avertissements',
	constats: 'constats du nœud',
	communs: 'constats communs',
	porte_communs: 'porte les communs',
};

/** Une liste se compte (ses lignes se lisent dans leur propre carte), un booléen se dit. */
const valeurDetail = (v: unknown): string =>
	Array.isArray(v) ? String(v.length) : typeof v === 'boolean' ? (v ? 'oui' : 'non') : String(v);

/**
 *  Les colonnes de l'historique d'une tâche — **une seule écriture**.
 *
 *  🔴 Elles étaient déclarées DEUX fois : une condition `aValeur(lignes, …)`
 *  pour l'en-tête, la même pour la cellule, neuf fois de suite. Une colonne
 *  ajoutée d'un seul côté aurait décalé tout le tableau — un `<th>` de plus
 *  que de `<td>` ne lève rien, il déplace les valeurs d'une case, et le
 *  lecteur voit une durée sous « Taille ».
 *
 *  ⚠️ « Statut » n'a pas de `valeur` : sa cellule porte un badge et une
 *  infobulle d'erreur, rendus à part dans le balisage. Elle reste dans la
 *  table pour tenir sa PLACE dans l'ordre — la retirer la ferait disparaître
 *  de l'en-tête, ce qui est exactement le décalage qu'on supprime.
 */
export const COLONNES: {
	titre: string;
	visible?: (lignes: ExecutionTache[]) => boolean;
	valeur?: (l: ExecutionTache) => string;
	style?: string;
}[] = [
	{ titre: 'Date', valeur: (l) => fmtDatetime(l.cree_le) },
	{
		titre: 'Nœud',
		visible: (lg) => aValeur(lg, 'noeud'),
		valeur: (l) => (l.noeud ? l.noeud.toUpperCase() : '—'),
	},
	{
		titre: 'Déclenchement',
		visible: (lg) => aValeur(lg, 'declenchee_par'),
		valeur: (l) => l.declenchee_par ?? '—',
		style: 'color:var(--color-text-muted)',
	},
	{ titre: 'Statut' },
	{
		titre: 'Événements agrégés',
		visible: (lg) => aValeur(lg, 'jours_agreges'),
		valeur: (l) => ('jours_agreges' in l ? fmtAgrege(l) : '—'),
		style: 'color:var(--color-text-muted)',
	},
	{
		titre: 'Purges',
		visible: (lg) => aPurges(lg),
		valeur: (l) => `${totalPurges(l)} lignes`,
		style: 'color:var(--color-text-muted)',
	},
	{
		titre: 'Durée',
		visible: (lg) => aValeur(lg, 'duree_secondes'),
		valeur: (l) =>
			'duree_secondes' in l && l.duree_secondes != null ? `${l.duree_secondes} s` : '—',
	},
	{
		titre: 'Taille',
		visible: (lg) => aValeur(lg, 'taille_octets'),
		valeur: (l) => fmtOctets('taille_octets' in l ? l.taille_octets : null),
	},
	{
		titre: 'Taille DB',
		visible: (lg) => aValeur(lg, 'taille_db_octets'),
		valeur: (l) => fmtOctets('taille_db_octets' in l ? l.taille_db_octets : null),
	},
	{
		titre: 'Détail',
		visible: (lg) => aValeur(lg, 'details'),
		valeur: (l) =>
			'details' in l && l.details
				? Object.entries(l.details)
						//  Une LISTE se compte ici : les constats des contrôles de
						//  fiabilité se lisent en entier dans leur propre carte.
						.map(([k, v]) => `${LIBELLES_DETAIL[k] ?? k} : ${valeurDetail(v)}`)
						.join(' · ')
				: '—',
		style: 'font-size:.72rem;color:var(--color-text-muted)',
	},
];

/**
 *  Le MOTIF d'un échec, quelle que soit la table qui l'a écrit (#1681).
 *
 *  🔴 La sauvegarde le porte dans `message_erreur`, la maintenance et
 *  l'agrégation dans `erreur` : l'écran ne lisait que le second, et le ⚠️ ne
 *  s'affichait jamais sous une sauvegarde échouée — celle dont on veut
 *  justement savoir pourquoi. Normalisé ICI, sur l'union du client, une fois.
 */
export const motifEchec = (l: ExecutionTache): string | null =>
	('message_erreur' in l ? l.message_erreur : l.erreur) ?? null;

/** Celles qui ont quelque chose à montrer pour ce jeu de lignes. */
export const colonnesVisibles = (lignes: ExecutionTache[]) =>
	COLONNES.filter((c) => !c.visible || c.visible(lignes));
