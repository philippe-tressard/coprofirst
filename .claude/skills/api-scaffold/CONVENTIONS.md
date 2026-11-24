# api-scaffold — §8 — conventions du backend : les portes uniques, le détail (CLAUDE.md en garde la liste courte)

Annexe de `SKILL.md`, chargée à la demande (#2910) : le sommaire est dans `SKILL.md`.
Les titres et numéros de section sont ceux de toujours : un renvoi se lit au sommaire.

## 8. Conventions du backend — le détail (`CLAUDE.md` en garde la liste courte)

Venu de `CLAUDE.md` (#2709). Chaque règle nomme sa porte et le test qui la tient.

### Modèles
- Un module neuf de `app/models/` s'importe dans `models/__init__.py` : c'est ce qui
  enregistre la table (oublié, elle manque à `create_all` sans un mot). `core.py`
  **ré-exporte** les modèles extraits (imports `# noqa: E402`) : `alembic/env.py`
  n'importe que `core`, et c'est par eux qu'Alembic voit la moitié des tables — pas un
  doublon à nettoyer (#1157). 🔒 `test_modeles_enregistres.py`, `test_core_sans_modele_neuf.py`
  (sa liste — l'utilisateur et ce qui lui est attaché — est close depuis #2316).
- Déplacer une classe change l'ordre des `DELETE` d'un même flush entre deux tables sans
  `Relationship` (SQLAlchemy trie par nom qualifié, #2316) : supprimer l'enfant, `flush()`,
  puis le parent.
- `__tablename__` en snake_case français ; champs français (`statut_validation`) ;
  FK `{modele}_id = Field(default=None, foreign_key="table.id")` ; enums
  `class MonEnum(str, Enum)` à slugs français en minuscules.
- Horodatage : suffixe `_le`, valeur `horloge.maintenant()` (UTC **naïf**), annoté
  `NaiveDatetime` — jamais `datetime` (sqlmodel ≥ 0.0.45 en fait une colonne consciente du
  fuseau qui refuse la date naïve, #1412), jamais `datetime.utcnow()` (Ruff `DTZ003`).
- Le **jour** du résident : `horloge.aujourd_hui()` (jour de Paris) ; celui d'un instant de la
  base : `horloge.jour_civil(x)`, son heure murale `horloge.a_paris(x)`, le fuseau
  `horloge.TZ_PARIS`. Jamais `date.today()`, `datetime.now()` sans fuseau ni
  `maintenant.date()` (faux d'un jour entre 0 h et 2 h, #1565). 🔒 `test_horloge.py`
  (`default_factory` compris), Ruff `DTZ005/011`.
- **Archiver, pas une colonne `actif`** : les objets qui quittent les listes se déclarent dans
  `utils/archivage.REGLES`. 🔒 `test_archivage_colonnes_booleennes.py` (toute colonne
  `actif`/`active`/`archivee` couverte par `REGLES` ou déclarée référentiel, #1568).
- Deux tables qui portent le même objet (Vigik/Télécommande et leurs stagings) : une classe de
  base non-table (`models/acces._ObjetAcces`). Un import xlsx déclare son `_traiter_rows` et
  nomme ses importeurs par `import_xlsx.importeurs`.

### Une copropriété (`app/contexte.py`, #1744)
`contexte.nouvelle_session()` hors requête (une route prend `get_session`),
`contexte.moteur()`, `contexte.courante()` (`url_base`, `racine_fichiers`, `secret`,
`expediteur`, `nom_expediteur`) — jamais `engine`, `SessionLocal` ni
`settings.database_url|secret_key|uploads_dir|mail_from`. Un cache ou un quota en mémoire :
`contexte.etat("nom")`, jamais une variable de module. La copropriété d'une requête se
résout à son entrée (`contexte.ResolutionCopropriete`) ; une tâche hors requête la reçoit de
`contexte.dans(copro)`. Une installation commune déclare ses copropriétés dans
`COPROPRIETES_FICHIER`, lu par `installation_commune/declaration` seul (#1894) ; hors
requête elle n'a pas de copropriété courante (`contexte.HorsCopropriete`) : une commande
`python -m app…` la nomme par `utils/commande` (`--copropriete`), le dossier des sauvegardes
se demande à `contexte.dossier_des_sauvegardes()` (#2053).
🔒 `test_commandes_nomment_leur_copropriete.py`, `test_contexte_source_unique.py`,
`test_etat_module_par_copropriete.py` (`A_INDEXER` vide), `test_etancheite_coproprietes.py`
(deux bases aux identifiants identiques, aucune réponse de l'une ne porte les données de
l'autre, #1746).

### Lots (#2212, spec `specs/architecture/lots-et-perimetres.md`)
Nature : `utils/designation_lot` (`nature_du_lot`, `est_annexe`), jamais `lot.nature` (vide
tant que l'état descriptif n'est pas importé). Périmètres (*situé dans*, *desservi par*)
dérivés par `utils/perimetres/lots`, rangés dans `lot_perimetre`. Une annexe (cave, place)
n'apporte pas son bâtiment à « mes bâtiments » : ce qui la concerne passe par
`mes_batiments.perimetres_desservis` (`perimetre_visible`, #2214).
🔒 `test_nature_lot_source_unique.py`, `test_annexes_hors_mes_batiments.py`, `test_mes_perimetres.py`.

### Lire, refuser, rendre
- `utils/recuperer.ou_404(session, Modele, id, "libellé")` — jamais `session.get` puis
  `raise HTTPException(404)` ni un alias. Les 404 écrits à la main se déclarent un par un dans
  `EXCEPTIONS` de `test_recuperer_source_unique.py` (#1571). Un objet qui doit porter son
  parent : `sous={"bail_id": …}`. Même module : `fichier_ou_404(chemin, "PDF")`,
  `premier_ou_404(session, Modele, "…non configurée")` (ligne unique d'une table de réglage),
  `connu_ou_404(TABLE, cle, "Section inconnue")` (clé d'un registre du code, jamais une liste
  blanche d'accès), `present_ou_404(valeur, "…")`.
- Lire puis refuser en 403 si le prédicat de l'entité dit non :
  `auth/appartenance.exiger_objet_autorise` (#1564).
- Valeur d'une énumération : `utils/valeurs.valeur(x)`, jamais `str(x)` ni
  `getattr(x, "value", x)` (🔒 `test_valeur_source_unique`). Écrite POUR UNE PERSONNE (titre de
  notification, `context=` d'un courriel) : son libellé, jamais `x.type` ni
  `valeur(x.statut)` (`libelle_statut`,
  `libelle_categorie`, `libelle_priorite`, `libelle_type_acces`, `libelle_type_lot`).
  🔒 `test_enumerations_en_clair.py`.
- Rendre un objet : `Schema.model_validate(objet)`, ou `utils/lecture.lire_objet(Schema,
  objet, **dérivés)` — jamais une recopie colonne par colonne (#1563).
  🔒 `test_lecture_colonne_par_colonne`, `test_lectures_rendent_le_modele`.

### Schémas Pydantic
Trois formes par entité exposée : `EntiteCreate` (sans id ni horodatage), `EntiteRead`
(`class Config: from_attributes = True`), `EntiteUpdate` (tout `Optional`). Ils vivent dans
le `schemas_<domaine>.py` de l'entité, que `schemas.py` ré-exporte ; un schéma propre à un
routeur vit à côté de lui, celui qu'un utilitaire calcule à côté de cet utilitaire (§2).
`schemas_communs.py` n'importe RIEN du projet (cycle `schemas` ⇄ `schemas_tickets`).
Un nom de classe déjà pris dans `app/` se qualifie de son module dans `openapi.json`, que
l'app iOS génère (`app__schemas_communaute__MessageRead`) : un schéma neuf prend un nom neuf.

### Nommage, contrat, tables publiées
- Français, tables, routes et tags compris. Les noms anglais existants sont **figés
  définitivement** (`TABLES_FIGEES`, `ROUTES_FIGEES` de `test_nommage_francais.py`, décision du
  30/10/2026, #2314) ; un nom figé renommé sort de la liste. Tag OpenAPI en minuscules à
  tirets (`carnet-entretien`), préfixe de routeur au pluriel (#1056).
- **Le contrat de l'API ne recule pas sans annonce** (#2456) : l'app iOS génère son client
  depuis `openapi.json`, joint à chaque release (`scripts/ci/lib-contrat-version.sh`), jamais
  servi par le site. `api/app/contrat/reference.json` est GÉNÉRÉE par `python
  scripts/ci/exporter_openapi.py --ecrire-reference` (elle calcule `version_contrat`, servie
  par `GET /config`). Retirer une route ou un champ : `deprecated` + une entrée dans
  `app/contrat/retraits.RETRAITS` (version V), puis le retrait dans une version ultérieure.
  L'`operationId` vient du chemin (`contrat.identifiant_operation`). 🔒 `test_contrat_api.py`.
- **Ni tant qu'une version publiée d'une app s'en sert** (#2744) : `app/contrat/circulation.py`
  déclare les versions en circulation (`EN_CIRCULATION`), leur contrat est figé dans
  `app/contrat/circulation/<app>-<version>.json` (la référence à leur plancher), et chaque
  PR est jugée contre eux par `inventaire.comparer`. Une dérogation se déclare datée, avec
  son échéance (`DEROGATIONS`). Une version publiée (piste de test comprise) : entrée, étiquette, contrat figé ; publication, sortie et `inventaire.LIMITES` : la docstring.
  🔒 `test_contrat_versions_en_circulation.py`, `test_contrat_limites.py`, `test_versions_minimales.py` ; CI : `scripts/check_versions_en_circulation.py`.
- **Tables du site que l'app iOS lit** (#2634) : `front/tables-clients.json`, GÉNÉRÉE par
  `node front/scripts/tables-clients.mjs --ecrire` depuis `tables-clients.registre.mjs`
  (constantes LITTÉRALES de `#lib`, lues dans l'arbre syntaxique), jointe à la release. Une
  table que l'app lit vit dans `#lib` en constante NOMMÉE (`parAttribut(ATTRIBUTS_ROLE)`), et
  le code qui la sert la LIT (`aRole($u, ...ROLES_DU_DROIT.cs)`) ; jetons de la charte et
  palettes se publient par leur règle CSS (`<feuille>.css@<sélecteur>`) ; une table CALCULÉE depuis d'autres (`derivee: true`, `palettesResolues`, #2754) vit dans `tables-clients.derivees.mjs`, jugée contre le rendu du site par `e2e/palettes-resolues.spec.ts`. Retirer ou changer de
  forme s'annonce dans `RETRAITS`. 🔒 `npm run lint:tables-clients`.
- **Constantes de l'API que les apps compilent** (une note, un défaut, une longueur minimale,
  #2686) : `api/app/contrat/constantes-clients.json`, GÉNÉRÉE par `python
  scripts/ci/exporter_openapi.py --ecrire-constantes` depuis le registre `CONSTANTES` de
  `app/contrat/constantes_clients.py` (une constante NOMMÉE de son module, lue, jamais
  recopiée), jointe à la release. Un retrait s'annonce dans `RETRAITS_CONSTANTES`.
  🔒 `test_constantes_clients.py`.
- **Une règle d'affichage que le site ET l'app montrent se calcule dans l'API** (#2501,
  `standards/09` §8) : dans `app/utils/` (ou un prédicat d'`auth/`), servie en champ que le
  front LIT. Chacune se déclare dans `front/scripts/check-regles-partagees.regles.mjs` ; celles
  que le front calcule encore y portent leur ticket de migration OUVERT. 🔒 `npm run
  lint:regles-partagees`, point 25 du pré-check (#2633).

### Documents imprimables (PDF)
Thème commun `app/utils/pdf_theme.py` (logo, palette, data-URI, `html_to_pdf()`) — jamais une
palette, un logo ou un moteur ailleurs. HTML autonome (CSS dans `<style>`, images en
data-URI) ; le moteur n'ouvre que le data-URI — une image `http(s)` ou `file://` est refusée, jamais
récupérée par le serveur (`pdf_rendu.PROTOCOLES_ADMIS`, #1908, 🔒
`test_pdf_hors_reseau.py`). `@page { size: A4|A5 }` ; pas d'emoji dans les affiches.
Documents : `fiche_arrivant.py`, `annonce_hall.py`, `manuel_pdf.py`. Le rendu s'exécute
**hors du process de l'API** (`app/utils/pdf_rendu.py`), dans un enfant `spawn` — jamais
`fork`, qui hériterait des connexions à la base ; coût assumé +1,5 à 2 s.
🔒 `test_weasyprint_appel_unique.py` (aucun appel au moteur ailleurs — c'est aussi la porte de
la dérogation GHSA-jf6q-chmf-3h3v), `test_pdf_hors_process.py`. La mécanique de l'enfant :
`app/utils/process_isole.py`, partagée avec les images (#2396).

### Destinataires (`app/utils/destinataires.py`, source unique)

| Ce qu'on vise | Fonction | Employée par |
|---|---|---|
| le CS **concerné par un périmètre** | `membres_cs_notifiables(session, batiment_ids)` (+ `batiments_du_perimetre()`) | nouvel arrivant, annonces de hall |
| le CS **par le rôle**, sans périmètre | `membres_cs_avec_email(session)` | publications, sondages, calendrier, tickets |
| le **syndic principal** | `syndic_principal(session)` | ci-dessous, fiche copropriété, arrivants |
| le **gestionnaire du site** — un administrateur, ou personne (#1505) | `site_manager_user_id(session)` | ce qui renvoie à `/admin` : comptes, alertes, bogues |
| « cette personne gère-t-elle le site ? » — le désigné, sinon tout administrateur | `est_gestionnaire_du_site(session, user)` | répondre aux avis, les retenir et les exporter (#2075) |
| **syndic puis CS, dédoublonnés** | `destinataires_syndic_cs(session, syndic=…, cs=…)` | les quatre entités qui cochent « envoyer au syndic / au CS » |
| **gestionnaire du site puis CS, dédoublonnés** | `gestionnaire_puis_cs(session)` | la synthèse d'une affaire close à valider (#1643) |

🔒 `test_destinataires_source_unique.py`. Il laisse passer les notifications in-app, qui
visent « CS ou admin » et rendent des `Utilisateur` — autre destinataire.

### Diffuser, couper un service
- Prévenir le groupe de la résidence : `utils/diffusion` — `config_diffusion(session)` (`None`
  si le canal est éteint) puis `diffuser(background_tasks, config, titre, contenu, …)`. Le
  registre `CANAUX` n'a qu'un canal (WhatsApp, dont le bridge est l'adaptateur) ; les clés
  `whatsapp_*` et `whatsapp_log` gardent leur nom jusqu'au second (#1060).
  🔒 `test_diffusion_canal.py`.
- « Ce service est-il activé ? » : `utils/services` — `service_actif(cfg, SERVICE_…)`,
  `cle_actif(SERVICE_…)` —, jamais une lecture de `llm_actif`, `whatsapp_enabled` ou
  `imap_enabled` (#1718). Le registre `SERVICES` est la seule liste ; l'onglet Admin ›
  Services s'en déduit (`GET /config/services`). Les courriels de sécurité ne sont pas un
  service (`COURRIELS_DE_SECURITE`). Un modèle d'e-mail `desactivable=False`
  (`seed.emails.NON_DESACTIVABLES`) part même décoché, et le `PATCH` refuse de le décocher
  (#2054). 🔒 `test_services_registre.py`, `test_courriels_securite_hors_service.py`,
  `test_modeles_non_desactivables.py`.

### Tâches planifiées de l'API
Elles tournent dans le process et se déclarent dans `app/utils/taches.TACHES_PERMANENTES`,
avec ce qu'on perd si elle cesse. Chacune s'enregistre par copropriété :
`scheduler.add_job(contexte.pour_chaque_copropriete(tache, "id"), …, id="id")` ; une tâche de
la plateforme se déclare dans `TACHES_DE_LA_PLATEFORME` avec sa raison (#1745). Le démarrage
journalise tout écart en `WARNING` ; 🔒 `test_taches_planifiees_declarees.py` le vérifie en
CI, dans les deux sens.
