/**
 *  Les FORMULATIONS périmées de `check-consignes.mjs` — une phrase qui décrit un
 *  état défait, avec ce qui est vrai à la place.
 *
 *  Séparées du script le 24/11/2026 : la détection (lui) et la table (ici) ne
 *  grossissent pas au même rythme — la table s'allonge à chaque consigne
 *  rattrapée, et c'est elle qui faisait passer le script au-dessus de son
 *  plafond de modularité. Le motif de `check-libelles-soumission.regles.mjs`.
 *
 *  Une entrée par défaut constaté, jamais un mot isolé : le motif porte la phrase
 *  fautive, pour ne pas punir celle qui raconte l'histoire.
 */
export const FORMULATIONS = [
	{
		motif: /pr[ée]-?check[^.\n]{0,40}\bavant (?:le|tout) `?(?:git )?push/giu,
		vrai: "le pré-check se passe après la CI de la PR, avant `conduire-mep.sh` (CLAUDE.md, « Ordre d'un lot », #2908)",
	},
	{
		motif: /\bAPI_VERSION\b/gu,
		vrai: 'la constante est partie : `/api/health` rend `contrat.VERSION_CONTRAT`, `GET /config` publie `version_logicielle` (#2934)',
	},
	{
		//  Un compte de tests se périme au premier test ajouté (« 5 tests » pour huit).
		motif: /\(\s*\d+ tests?\b|\b\d+ tests?,? CI\b/gu,
		vrai: 'nommer le fichier de tests, sans son compte (#2934)',
	},
	//  Les quatre suivantes : consignes rattrapées après l'audit du 23/11/2026, chacune
	//  la phrase d'avant le lot qui l'a rendue fausse.
	{
		motif: /S608`\s+sur\s+`api\/app\/`(?!\s+et\b)/gu,
		vrai: 'S608 couvre aussi les deux chaînes de migrations (`api/ruff.toml`, #2948)',
	},
	{
		motif: /limitation de débit \(slowapi\) sur `\/auth\/\*`(?!\s+et\b)/gu,
		vrai: 'toute route qui éprouve un secret porte sa limite, une constante de `utils/limiter` (`test_limites_debit_auth.py`)',
	},
	{
		motif: /pour tout geste de\s+`GESTES_SENSIBLES`/gu,
		vrai: 'toute fonction qui écrit au journal est déclarée dans `GESTES_SENSIBLES` (`aides_gestes_sensibles.py`), et l’inverse (#2941)',
	},
	{
		motif: /sha court de HEAD/gu,
		vrai: 'le sha de HEAD, court ou complet, se compare par préfixe (`lib-parite.memes_hachages`, #2967)',
	},
];
