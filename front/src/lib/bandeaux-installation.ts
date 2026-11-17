/**
 * Le texte du bandeau « installation suspendue » (Registre R6, #1882) — une seule écriture.
 *
 * Le site le rend dans `BandeauInstallation` quand `GET /config` sert
 * `installation_suspendue` = `'1'` ; les apps le lisent dans la release au lieu d'en
 * garder une copie (#2840). Le titre se compose `titre` + `SEPARATEUR.tiret` +
 * `precision` + « . », en gras, suivi du `texte`.
 *
 * 🔒 Table PUBLIÉE aux clients (`bandeauSuspendue`) — littérale, entière.
 */
export const BANDEAU_SUSPENDUE = {
	titre: 'Installation suspendue',
	precision: 'lecture seule',
	texte:
		'Tout reste consultable, mais rien ne peut être ajouté ni modifié. ' +
		'L’administrateur de la copropriété peut en exporter les données ; ' +
		'l’opérateur de l’installation s’adresse à la référence pour la rétablir.',
} as const;
