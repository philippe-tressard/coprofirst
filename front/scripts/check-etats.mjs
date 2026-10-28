/**
 * Garde-fou R4 — **une divergence entre deux états se déclare, avec son motif.**
 *
 * ## Pourquoi (cadre #430, lot #431, 17/08/2026)
 *
 * Le relevé des 42 couples menu/entité a mesuré que **13 éditions sur 23**
 * réinventaient un motif que la création portait déjà, et que **5 seulement**
 * portaient une raison écrite. Les cinq étaient dans `FormulaireTicket`, en
 * commentaires — donc invisibles à tout contrôle, et libres de mentir dès le lot
 * suivant. C'est exactement ce qui est arrivé le 17/08 au matin : le commentaire
 * disait « l'état se change depuis le fil, pour qu'il y laisse une trace », un
 * motif (`trace`) que le cadre n'a jamais reconnu.
 *
 * R4 est la clé de voûte du cadre, et la seule règle que l'utilisateur n'avait
 * pas demandée : **sans elle, les cinq autres s'érodent en silence.**
 *
 * ## Ce que ce contrôle REFUSE
 *
 *   1. une entité dont les sections ne sont pas **toutes, dans l'ordre** ;
 *   2. une section qui ne dit ni ce qu'elle porte (`objet`) ni pourquoi l'entité
 *      ne la porte pas (`sansObjet`) ;
 *   3. **une divergence sans motif**, ou avec un motif hors des trois admis ;
 *   4. **un motif `api` sans ticket** — c'est un marqueur de dette, pas un choix
 *      de conception : il doit citer l'issue qui la fera tomber ;
 *   5. une section rendue **hors déclaration** : dans un écran qui consomme une
 *      entité, `avecPerimetre`, `avecPhotos`… doivent être gouvernés par
 *      `sectionPresente(…)` et par rien d'autre. Une condition en dur
 *      (`{!modeEdition}`) rouvre très exactement la divergence silencieuse que
 *      le cadre supprime ;
 *   6. un **intitulé de section** qui n'est ni le libellé de la section ni celui
 *      que la déclaration annonce (`titreEcran`) — R3 : le même libellé d'un
 *      formulaire à l'autre.
 *
 *   7. **une prop d'`EvolForm` qui ouvre une section hors déclaration** — l'état
 *      `evolution`, ajouté le 28/08/2026 (#463). Voir `lib-etats-evolution.mjs`.
 *
 * ## Ce que ce paragraphe disait, et qui était devenu FAUX
 *
 * Il annonçait : *« `EvolForm.svelte` n'est pas un consommateur (…) l'état
 * `evolution` est donc déclaré et vérifié en tant que déclaration, pas encore
 * confronté à son rendu »*. C'était exact quand il a été écrit — et c'est resté
 * là après que six entités eurent déclaré l'état, sans que rien ne le confronte.
 *
 * 🔴 La portée du contrôle était plus étroite que la règle qu'il défend, et il
 * rendait **vert**. Même faiblesse que #562, à l'autre bout du dépôt
 * (`standards/05` §9 et §9 ter). Le relevé a trouvé **onze** props hors
 * déclaration dans **six** écrans, dont un écart que personne ne voyait : l'espace
 * CS ne propose aucune diffusion sur un commentaire de ticket là où la carte de
 * ticket la propose au même utilisateur.
 *
 * ⚠️ R5 interdisant de brancher les cinq écrans d'un coup, le relevé est **figé
 * en tolérances nommées** : il vit dans le code, ne peut que décroître, et le
 * contrôle échoue dès qu'une entrée cesse de servir. Le message de succès **dit**
 * ce qui reste — un contrôle qui tait sa dette se lit « tout est branché ».
 *
 * Le contrôle s'auto-contrôle : plus de types, plus d'entité, plus de
 * consommateur, une entité que personne ne consomme, un littéral qu'il n'arrive
 * pas à lire → il ÉCHOUE au lieu de conclure au vert
 * (`standards/04-fiabilite-des-controles.md` §2, cas zéro).
 */
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, relative } from 'node:path';
import {
	analyserEvolForm,
	tolerancesMortes,
	ENTITE_REQUISE,
	EVOLFORM_TOLEREES,
} from './lib-etats-evolution.mjs';
import { neutraliserCommentaires as sansCommentaires } from './lib-commentaires.mjs';
import { extraire, preludePartage } from './lib-lecture-source.mjs';

const RACINE = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const DOSSIER_ENTITES = join(RACINE, 'lib', 'entites');
const TYPES = join(DOSSIER_ENTITES, 'types.ts');

//  🔴 `categorie` est entré le 21/09/2026 (#1095) : une section que la CATÉGORIE
//  de l'objet n'appelle pas — l'Équipement et l'Intervenant ne concernent que le
//  bâti. Distinct de `sansObjet` (« cet objet ne porte jamais la notion ») et
//  d'`api` (« on ne sait pas encore le faire », donc une dette avec son ticket).
const MOTIFS_ADMIS = ['geste', 'hérité', 'categorie', 'api'];

/**  Les six sections que `ChampsCommuns` sait rendre, et le nom de la prop qui
 *   les ouvre. Ce sont elles qui doivent passer par `sectionPresente`. */
const PROPS_SECTION = {
	avecPerimetre: 'perimetre',
	avecDestinataires: 'destinataires',
	avecDescription: 'description',
	//  Deux props pour UNE section depuis #1095 : l'objet garde deux réservoirs
	//  — des URLs de photos, des entités `Document` — parce que le SERVEUR les
	//  distingue, mais l'écran n'en rend qu'une section. Les deux doivent donc
	//  passer par `sectionPresente('pieces_jointes')`.
	avecPhotos: 'pieces_jointes',
	avecDocuments: 'pieces_jointes',
	avecDiffusion: 'diffusion',
};

const erreurs = [];
const echec = (m) => erreurs.push(m);

/** Sortie de cas zéro : on dit AUSSI ce qu'on avait déjà relevé, sinon le
 *  diagnostic s'arrête au symptôme (« 0 section lue ») sans sa cause. */
function casZero(message) {
	console.error(`✗ Cas zéro : ${message}`);
	for (const e of erreurs) console.error(`  • ${e}`);
	console.error("Le contrôle n'a rien pu établir ; ne pas lire ceci comme un succès.");
	process.exit(1);
}

//  ── Cas zéro : de quoi ce contrôle a besoin pour contrôler quoi que ce soit ──
if (!existsSync(TYPES)) {
	casZero(`${TYPES} est introuvable — le cadre n'a plus de types, contrôle inopérant.`);
}
const srcTypes = readFileSync(TYPES, 'utf8');
//  Les divergences PARTAGÉES que `types.ts` déclare, injectées dans le contexte
//  d'évaluation de chaque entité. Une entité ne peut citer que ce que le cadre
//  déclare — et le lecteur, lui, n'exécute jamais le fichier qu'il lit.
const PARTAGE = preludePartage(srcTypes);
for (const fonction of ['sectionPresente', 'sectionsDe']) {
	if (!new RegExp(`export function ${fonction}\\b`).test(srcTypes)) {
		casZero(
			`\`${fonction}\` n'est plus exportée par types.ts. Le contrat a changé — ` +
				'mettre ce contrôle à jour, sinon il laisse passer les sections rendues hors déclaration.',
		);
	}
}

const ORDRE = extraire(srcTypes, 'SECTIONS_ORDRE', relative(RACINE, TYPES), { echec });
const LIBELLES = extraire(srcTypes, 'SECTIONS_LIBELLE', relative(RACINE, TYPES), { echec });
//  🔴 QUATORZE depuis le 26/09/2026 : « Affaires liées » (#1342), après les
//  Pièces jointes. TREIZE depuis le 21/09/2026 (#1095) : l'ancienne section « Champs
//  spécifiques » est scindée en Nature · Au nom de · Mise en avant, et
//  l'Équipement, l'Intervenant et le Suivi la rejoignent. Elles étaient neuf le
//  matin même (Photos + Documents fusionnées), dix la veille (#1092).
//
//  ⚠️ La scission n'est pas cosmétique : une section à trois intitulés rendait
//  INDÉCLARABLE une divergence qui n'en concernait qu'un — c'est la limite que
//  #436 décrivait, et `ticket.ts` la portait en commentaire, invisible ici.
//
//  Le nombre reste FIGÉ, et c'est tout l'intérêt : il oblige à passer ici quand
//  le cadre bouge, au lieu de laisser une section entrer — ou disparaître —
//  sans que personne le décide. Le remplacer par `ORDRE.length > 0` rendrait ce
//  cas zéro aveugle à une table tronquée, ce qu'il existe précisément pour
//  attraper. C'est bien ce qui vient de se passer : la fusion a dû passer ici.
if (!Array.isArray(ORDRE) || ORDRE.length !== 14) {
	casZero(`SECTIONS_ORDRE devrait porter les QUATORZE sections (${ORDRE?.length ?? 0} lue(s)).`);
}
if (!LIBELLES || ORDRE.some((id) => !LIBELLES[id])) {
	casZero('SECTIONS_LIBELLE ne nomme pas toutes les sections de SECTIONS_ORDRE.');
}

const fichiersEntites = existsSync(DOSSIER_ENTITES)
	? readdirSync(DOSSIER_ENTITES).filter((n) => n.endsWith('.ts') && n !== 'types.ts')
	: [];
if (fichiersEntites.length === 0) {
	casZero(`aucune entité déclarée dans ${DOSSIER_ENTITES}. Ce contrôle n'a rien à garder.`);
}

//  ── Les déclarations ────────────────────────────────────────────────────────
const entites = [];
for (const nomFichier of fichiersEntites) {
	const chemin = join(DOSSIER_ENTITES, nomFichier);
	const source = readFileSync(chemin, 'utf8');
	const court = relative(RACINE, chemin);
	const m = source.match(/export\s+const\s+([A-Z][A-Z0-9_]*)\s*:\s*EntiteDeclaree\b/);
	if (!m) {
		echec(`${court} — aucune \`export const <NOM>: EntiteDeclaree\` : entité illisible.`);
		continue;
	}
	const nom = m[1];
	const decl = extraire(source, nom, court, { partage: PARTAGE, echec });
	if (!decl) continue;
	entites.push({ nom, decl, court });

	const ids = (decl.sections ?? []).map((s) => s.id);
	if (ids.length !== ORDRE.length || ids.some((id, i) => id !== ORDRE[i])) {
		echec(
			`${court} (${nom}) — les sections ne sont pas celles de SECTIONS_ORDRE, dans son ordre.\n` +
				`      déclarées : ${ids.join(' · ') || '(aucune)'}\n` +
				`      attendues : ${ORDRE.join(' · ')}`,
		);
		continue;
	}

	for (const s of decl.sections) {
		const ou = `${court} (${nom} › ${s.id})`;
		if (!s.objet && !s.sansObjet) {
			echec(`${ou} — ni \`objet\` ni \`sansObjet\` : on ne sait pas ce que porte la section.`);
		}
		if (s.sansObjet && s.absente) {
			echec(
				`${ou} — \`sansObjet\` ET \`absente\` : une notion que l'entité n'a pas ne diverge de rien. ` +
					'Choisir.',
			);
		}
		for (const [etat, div] of Object.entries(s.absente ?? {})) {
			if (!div || typeof div !== 'object') {
				echec(`${ou} — divergence illisible pour l'état « ${etat} ».`);
				continue;
			}
			if (!div.motif) {
				echec(
					`${ou} — ABSENTE en « ${etat} » SANS MOTIF. R4 : toute divergence entre deux états ` +
						`se déclare avec son motif (${MOTIFS_ADMIS.join(' · ')}).`,
				);
				continue;
			}
			if (!MOTIFS_ADMIS.includes(div.motif)) {
				echec(
					`${ou} — motif « ${div.motif} » inconnu pour l'état « ${etat} ». ` +
						`Quatre motifs, quatre seulement : ${MOTIFS_ADMIS.join(' · ')}.`,
				);
			}
			if (!div.explication || !String(div.explication).trim()) {
				echec(
					`${ou} — divergence en « ${etat} » sans \`explication\` : un motif nu ne se relit pas.`,
				);
			}
			if (div.motif === 'api' && !/^#\d+$/.test(String(div.ticket ?? ''))) {
				echec(
					`${ou} — motif \`api\` en « ${etat} » SANS TICKET. C'est un marqueur de DETTE, jamais ` +
						"de conception : il doit citer l'issue qui la fera tomber (forme « #431 »).",
				);
			}
		}
	}
}

//  ── Les consommateurs : ce qui est rendu doit venir de la déclaration ───────
function svelte(dir) {
	const sortie = [];
	for (const nom of readdirSync(dir)) {
		const chemin = join(dir, nom);
		if (statSync(chemin).isDirectory()) sortie.push(...svelte(chemin));
		else if (nom.endsWith('.svelte')) sortie.push(chemin);
	}
	return sortie;
}

/** Retire commentaires et balisage commenté : expliquer la règle ne l'enfreint pas. */

const tousSvelte = svelte(RACINE);
if (tousSvelte.length === 0) {
	casZero("aucun composant analysé — l'arborescence a changé.");
}

const nomsEntites = new Set(entites.map((e) => e.nom));
const entitesConsommees = new Set();
let consommateurs = 0;

//  Les intitulés qu'une section peut porter à l'écran : son libellé générique, ou
//  celui que la déclaration annonce quand la section n'a qu'un champ (le titre EST
//  alors le libellé du champ — `SectionFormulaire`).
const titresAdmis = new Set(Object.values(LIBELLES));
for (const { decl } of entites) {
	//  `titreEcran` peut être une LISTE : une section qui groupe plusieurs champs
	//  nommés en porte un par champ (la section 2 du ticket : « Catégorie » et
	//  « Saisi pour »). Une section reste une section — c'est son contenu qui a
	//  plusieurs noms, pas elle qui se scinde.
	for (const s of decl.sections ?? []) {
		for (const t of [s.titreEcran ?? []].flat()) titresAdmis.add(t);
	}
}

for (const chemin of tousSvelte) {
	const brut = readFileSync(chemin, 'utf8');
	//  `import type` ne consomme rien : seul un import de VALEUR fait de ce
	//  fichier un rendu gouverné par la déclaration.
	const importe = [
		...brut.matchAll(/import\s+(?!type\b)\{([^}]*)\}\s+from\s+'#lib\/entites\/[^']+'/g),
	];
	if (importe.length === 0) continue;
	consommateurs += 1;
	const court = relative(RACINE, chemin);
	const texte = sansCommentaires(brut);

	for (const m of importe) {
		for (const nom of m[1].split(',').map((s) => s.trim())) {
			if (nomsEntites.has(nom)) entitesConsommees.add(nom);
		}
	}

	//  🔴 `EvolForm` est le POINT D'ENTRÉE du quatrième état, pas un écran (#463,
	//  02/09/2026) : il REÇOIT l'entité et lit la déclaration lui-même, son
	//  `sectionPresente(entite, …)` ne peut donc nommer aucune entité littérale.
	//  Ce qu'on lui demande est vérifié plus bas, chez ses appelants. Sans cette
	//  exception, le contrôle refuserait la centralisation qu'il réclame.
	const estPointEntree = court.replace(/\\/g, '/').endsWith('lib/components/EvolForm.svelte');

	// 5. les six sections de `ChampsCommuns` passent par `sectionPresente`
	for (const [prop, id] of Object.entries(estPointEntree ? {} : PROPS_SECTION)) {
		//  🔴 Un fichier qui DÉCLARE la prop ne la pose pas : il la reçoit, et c'est
		//  son appelant qui doit la gouverner — vérifié chez lui, comme pour le
		//  point d'entrée ci-dessus.
		//
		//  ⚠️ Sans cette règle, `SectionsPiecesJointes` a été refusé le 21/09/2026
		//  pour ses PROPRES `{#if avecPhotos}`, le jour où il a importé
		//  `SECTIONS_LIBELLE` — donc le jour où il a CESSÉ de recopier un libellé
		//  que la table déclare. Le contrôle punissait la centralisation qu'il
		//  réclame. C'est la forme générale de l'exception d'`EvolForm` : elle se
		//  lit dans le fichier, et ne nomme personne.
		if (texte.includes('export let ' + prop)) continue;
		const re = new RegExp(`\\b${prop}\\b(\\s*=\\s*\\{([^}]*)\\})?`, 'g');
		let m;
		while ((m = re.exec(texte))) {
			if (!m[1]) {
				echec(
					`${court} — \`${prop}\` est posée en dur (section toujours rendue). ` +
						`Elle doit être gouvernée par la déclaration : ${prop}={sectionPresente(…, '${id}')}.`,
				);
				continue;
			}
			const expr = m[2];
			if (!expr.includes('sectionPresente(') || !expr.includes(`'${id}'`)) {
				echec(
					`${court} — \`${prop}\` est gouvernée par « ${expr.trim()} », hors déclaration. ` +
						`R4 : la présence d'une section se DÉCLARE, avec son motif — ` +
						`attendu \`sectionPresente(<ENTITE>, <état>, '${id}')\`.`,
				);
			}
		}
	}

	// 7. l'état et la section cités doivent exister
	for (const m of texte.matchAll(
		/sectionPresente\(\s*([A-Za-z_$][\w$]*)\s*,\s*([^,]+),\s*'([^']+)'\s*\)/g,
	)) {
		if (!ORDRE.includes(m[3])) {
			echec(`${court} — \`sectionPresente(…, '${m[3]}')\` : section inconnue du cadre.`);
		}
		if (!estPointEntree && nomsEntites.size && !nomsEntites.has(m[1])) {
			echec(`${court} — \`sectionPresente(${m[1]}, …)\` : ce n'est pas une entité déclarée.`);
		}
	}

	// 6. les intitulés de section
	//  ⚠️ `SectionDescription` (prop `titre`) et `SectionTitre` (prop `libelle`)
	//  n'étaient PAS lus jusqu'au 27/09/2026 : en déclarant la FAQ, un intitulé
	//  « Réponse » falsifié passait au vert (#1329). Les deux composants portent
	//  pourtant une section du cadre, et leur intitulé est aussi libre qu'ailleurs.
	const intitules = [
		...texte.matchAll(/<Section(?:Formulaire|Lecture|Description)\b[^>]*?\btitre="([^"]*)"/g),
		...texte.matchAll(/<SectionTitre\b[^>]*?\blibelle="([^"]*)"/g),
	];
	for (const m of intitules) {
		const titre = m[1].trim();
		if (titre && !titresAdmis.has(titre)) {
			echec(
				`${court} — intitulé de section « ${titre} » absent de la déclaration. ` +
					"R3 : le libellé est le même d'un formulaire à l'autre — le nommer dans " +
					'`SECTIONS_LIBELLE` ou dans le `titreEcran` de la section.',
			);
		}
	}
}

//  ── 8. `EvolForm` — le quatrième état, confronté à son rendu (#463) ─────────
//
//  Ce contrôle ne regardait QUE les six props de `ChampsCommuns`. `EvolForm`
//  compose ses sections avec `SectionFormulaire` directement, et lui échappait
//  ENTIÈREMENT : l'état `evolution` était déclaré par six entités et confronté à
//  son rendu par aucune. La décision et son relevé vivent dans
//  `lib-etats-evolution.mjs`, avec leur `--selftest`.
//
//  ⚠️ La passe est SÉPARÉE de la boucle ci-dessus, et c'est le point : celle-ci
//  ne visite que les fichiers qui importent une déclaration. Trois des cinq
//  écrans qui rendent `EvolForm` n'en importent aucune — les mettre dans la même
//  boucle les aurait laissés hors de portée une seconde fois.
const evolformServies = [];
for (const chemin of tousSvelte) {
	//  Chemin NORMALISÉ : sur ce poste Windows `relative()` rend des `\`, et une
	//  clé de tolérance écrite avec des `/` ne correspondrait alors jamais — le
	//  contrôle serait vert par accident, pas par mérite.
	const court = relative(RACINE, chemin).replace(/\\/g, '/');
	const texteEvol = sansCommentaires(readFileSync(chemin, 'utf8'));
	const { ecarts, servies } = analyserEvolForm(court, texteEvol);
	for (const e of ecarts) echec(e);
	evolformServies.push(...servies);

	//  🔴 LE CONTRAT QUI REMPLACE LES QUATRE PROPS (02/09/2026). Les props que ce
	//  contrôle surveillait — `avecPerimetre`, `showPhotos`… — n'existent plus.
	//  ⚠️ Sans ce test il serait vert **en ne mesurant plus rien** : un écran
	//  pourrait rendre le fil sans déclaration, et plus aucune prop ne trahirait
	//  une section hors cadre. Un contrôle dont la cible a disparu ne se relit pas.
	if (court !== 'lib/components/EvolForm.svelte' && ENTITE_REQUISE.test(texteEvol)) {
		//  ⚠️ Une FENÊTRE après la balise, et non `[^>]*` : les attributs d'un
		//  `<EvolForm>` contiennent des fonctions fléchées, et `=>` coupait le motif
		//  avant l'attribut cherché. Le contrôle refusait alors les quatre écrans qui
		//  passent pourtant l'entité — un contrôle qui crie sur du légitime finit
		//  désarmé.
		const debut = texteEvol.search(ENTITE_REQUISE);
		const fenetre = texteEvol.slice(debut, debut + 2000);
		const entiteCitee = /\bentite=\{([A-Za-z_$][\w$]*)\}/.exec(fenetre);
		if (!entiteCitee) {
			echec(
				`${court} — rend <EvolForm> sans lui passer entite={…}. Le quatrième état ` +
					'serait gouverné par cet écran et non par la déclaration (#463).',
			);
		} else if (nomsEntites.size && !nomsEntites.has(entiteCitee[1])) {
			echec(`${court} — <EvolForm entite={${entiteCitee[1]}}> : ce n'est pas une entité déclarée.`);
		}
	}
}
for (const m of tolerancesMortes(evolformServies)) {
	echec(
		`tolérance \`EVOLFORM_TOLEREES\` devenue inutile : ${m}. La retirer — une dérogation ` +
			"oubliée est une porte qu'on croit fermée, et cette liste ne peut que DÉCROÎTRE.",
	);
}

if (consommateurs === 0) {
	casZero(
		"aucun écran ne consomme une déclaration d'entité. Une déclaration que personne ne lit " +
			'est décorative — et ce contrôle vert ne prouverait rien.',
	);
}
for (const { nom, court } of entites) {
	if (!entitesConsommees.has(nom)) {
		echec(
			`${court} — l'entité \`${nom}\` n'est consommée par aucun écran. Une déclaration ` +
				'que personne ne lit diverge du produit sans que rien ne le dise.',
		);
	}
}

//  ── Verdict ────────────────────────────────────────────────────────────────
if (erreurs.length) {
	console.error("✗ Cadre d'interface (#430) — R4 : une divergence sans motif est refusée.\n");
	for (const e of erreurs) console.error(`  • ${e}`);
	console.error(
		"\nLes trois motifs, et il n'y en a pas d'autre :\n" +
			"  geste  — la section est un ACTE qui n'a pas lieu dans cet état\n" +
			"  hérité — la valeur vient de l'objet porteur\n" +
			'  api    — DETTE, jamais conception : doit citer un ticket\n',
	);
	process.exit(1);
}

//  ════════════════════════════════════════════════════════════════════════════
//  LE PLIAGE — un 3e état de présence, et sa règle (#1095, 21/09/2026)
//  ════════════════════════════════════════════════════════════════════════════
//
//  🔴 La règle est CALCULÉE, pas déclarée :
//
//      obligatoire → déplié   ·   facultatif → plié
//
//  Un pliage conforme n'a donc rien à écrire. Un pliage qui s'en écarte exige
//  `exceptionPliage`, et l'on refuse dans les DEUX sens : une exception qui ne
//  sert plus est aussi grave qu'une exception qui manque — c'est ainsi qu'une
//  liste de justifications devient une liste de passe-droits.
const fautesPliage = [];
for (const { nom, decl } of entites) {
	for (const sec of decl.sections ?? []) {
		if (sec.sansObjet) continue;
		const conforme = sec.requis ? !sec.pliee : !!sec.pliee;
		const exception = String(sec.exceptionPliage ?? '').trim();
		if (!conforme && !exception) {
			fautesPliage.push(
				`${nom} · ${sec.id} — ${sec.requis ? 'obligatoire mais PLIÉE' : 'facultative mais DÉPLIÉE'}, ` +
					'sans `exceptionPliage`. La règle est : obligatoire → déplié, facultatif → plié.',
			);
		}
		if (conforme && exception) {
			fautesPliage.push(
				`${nom} · ${sec.id} — \`exceptionPliage\` déclarée alors que le pliage SUIT la règle. ` +
					'Une exception qui ne sert plus couvre le défaut suivant : la retirer.',
			);
		}
	}
}
if (fautesPliage.length) {
	console.error('\n✗ Cadre d’interface — le PLIAGE s’écarte de la règle sans le dire :\n');
	for (const f of fautesPliage) console.error(`  • ${f}`);
	console.error(
		'\n  🔴 IL N’Y A PLUS AUCUNE EXCEPTION (22/09/2026).' +
			'\n    Trois étaient prévues le 20/09 — « Au nom de », « Destinataires »,' +
			'\n    « Pièces jointes ». Les trois sont tombées à l’usage, chacune signalée' +
			'\n    à l’écran : une section marquée d’une astérisque qui arrive fermée' +
			'\n    demande de l’ouvrir pour constater qu’il n’y a rien à y faire.' +
			'\n    Demandé explicitement : « pour éviter toute exception ».' +
			'\n    En ajouter une se déclare ICI, avec sa date et sa raison — et ce message' +
			'\n    doit alors cesser de dire qu’il n’y en a aucune.' +
			'\n\n  ⚠️ Une valeur autre que le défaut rouvre la section d’office — cette' +
			'\n  partie-là vit dans le rendu, pas dans la table : elle dépend de ce que' +
			'\n  l’objet PORTE, pas de ce que la déclaration dit.\n',
	);
	process.exit(1);
}

console.log(
	`✓ Cadre d'interface : ${entites.length} entité(s) déclarée(s) sur les ${ORDRE.length} sections, ` +
		`${consommateurs} écran(s) gouverné(s) par la déclaration, toutes divergences motivées.`,
);
//  🔴 Le vert DIT ce qu'il ne couvre pas encore. Un contrôle qui tait sa dette
//  se lit « tout est branché », et le chantier s'endort — `standards/04` §12.
if (evolformServies.length) {
	console.log(
		`  ⏳ État \`evolution\` : ${new Set(evolformServies).size} prop(s) d'EvolForm encore hors ` +
			`déclaration dans ${Object.keys(EVOLFORM_TOLEREES).length} écran(s), tolérées et suivies en #463.`,
	);
}
