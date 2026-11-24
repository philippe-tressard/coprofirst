/**
 * Le `detail` d'une réponse en erreur, en une phrase LISIBLE (#1327).
 *
 * FastAPI rend un refus de validation (422) sous la forme d'une LISTE :
 * `[{ "type": "value_error", "loc": ["body", "contacts"], "msg": "Value error,
 * un contact au moins…", "input": … }]`. Le client la recopiait telle quelle
 * (`JSON.stringify`), et l'écran affichait ce JSON dans un toast — signalé à
 * l'écran le 25/09/2026 sur « Nouveau prestataire ».
 *
 * On garde le MESSAGE de chaque erreur, sans le préfixe technique de Pydantic
 * (« Value error, ») ; plusieurs erreurs se séparent par « ; ». Un `detail` d'une
 * autre forme retombe sur le repli : mieux vaut une phrase générique qu'un
 * fragment de structure.
 *
 * Un refus qui porte un MOTIF (`{ code, message }`, le mot de passe temporaire #3019 ;
 * `{ message, promu_en_affaire }`, le 410 d'une actualité devenue affaire) se lit par
 * son `message` : le code est pour le client, la phrase pour la personne.
 *
 * 🔒 `npm run lint:detail-erreur` l'exécute sur les formes réelles.
 */
export function detailLisible(detail: unknown, repli: string): string {
	if (typeof detail === 'string') return detail || repli;
	if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
		const message = (detail as { message?: unknown }).message;
		return typeof message === 'string' && message.trim() !== '' ? message : repli;
	}
	if (!Array.isArray(detail)) return repli;
	const messages = detail
		.map((e) => (e && typeof e === 'object' ? (e as { msg?: unknown }).msg : undefined))
		.filter((m): m is string => typeof m === 'string' && m.trim() !== '')
		.map((m) => m.replace(/^(Value|Assertion) error,\s*/i, '').trim())
		.map((m) => m.charAt(0).toUpperCase() + m.slice(1));
	return messages.length ? [...new Set(messages)].join(' ; ') : repli;
}
