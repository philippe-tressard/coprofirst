# api-scaffold — §9 — tests de l'API : ce que la suite pytest tient

Annexe de `SKILL.md`, chargée à la demande (#2910) : le sommaire est dans `SKILL.md`.
Les titres et numéros de section sont ceux de toujours : un renvoi se lit au sommaire.

## 9. Tests de l'API — ce que la suite tient

> 📖 `standards/05-tests-et-garde-fous.md`. Lancer : `cd api && pytest tests/ -q -n 8`, ou
> toute la suite comme la CI : `bash ../scripts/ci/mesure-postgresql.sh`.

- **Gabarits de courriel** : `test_email_templates.py` verrouille les variables Jinja2
  (`EXPECTED_VARS`, dans `tests/aides_contrats_email.py`). Changer les variables d'un gabarit
  (`seed.EMAIL_TEMPLATES`) = mettre à jour `EXPECTED_VARS` ET vérifier que le
  `send_email(code=...)` les fournit — sinon échec silencieux à l'envoi.
- **Migrations** : `test_migrations.py` (head unique, base unique, révisions uniques).
- **Licences tierces** (#1542, #1543) : `scripts/ci/licences_tierces.py` juge chaque
  dépendance de `front/`, `whatsapp-bridge/` et `api/` contre une liste blanche. Une licence
  hors liste = une exception NOMMÉE avec son motif dans `scripts/ci/licences_politique.py`
  (une exception qui ne sert plus fait échouer) ; `--ecrire` régénère
  `docs/licences-tierces.md`. Un contenu repris d'un tiers se déclare dans `CONTENUS_TIERS` et
  `REUSE.toml` (`contenus_tiers.py`). Ce que pip ne voit pas (paquet Debian d'une image, roue
  qui embarque un binaire interdit — `pillow-heif` porte x265, GPLv2, #2389) :
  `BIBLIOTHEQUES_SYSTEME`, `INTERDITS_DANS_LES_IMAGES`, `ROUES_A_COMPILER`, confrontés aux
  Dockerfile par `licences_image.py` ; l'image construite : `api/scripts/verifier_heif.py`.
- **Le code de test ne se recopie pas** (#1495) : les aides et ce qu'elles remplacent dans
  `MOTIFS` de `test_aides_de_tests_source_unique.py`. Une aide partagée vit dans un
  `tests/aides_*.py`, jamais dans un fichier de tests ; seuls `test_*.py`, `aides_*.py` et
  `conftest` vivent dans `tests/` (`test_nommage_modules_de_tests.py`). Une
  `Session(moteur_de_test())` jamais fermée, un patrimoine vidé à la main sont refusés.
  Au-delà des motifs, deux fonctions de niveau module (fixtures comprises) au corps identique
  dans deux fichiers de `tests/` échouent — empreinte d'AST, docstring retirée, dès trois
  instructions (`COPIES_ADMISES`, liste qui ne fait que baisser, #2950).
- **Aucun état mutable de module de plus** (#1743) : `test_etat_module_par_copropriete.py`
  (conteneur modifié depuis une fonction, `global`, `@lru_cache`) ; un état neuf va en base,
  ou dans `DU_PROCESSUS` avec sa raison ; un état de copropriété passe par `contexte.etat(nom)`,
  la seule porte (`PAR_COPROPRIETE`).
- **La suite passe sur PostgreSQL** (#1747, check requis) : un schéma neuf par test sur le
  PostgreSQL de `TESTS_BASE_URL` (`tests/aides_base`). En parallèle et dans un ordre tiré au
  sort (#2223) : `pytest -n` (`--dist load`, `scripts/ci/mesure-postgresql.sh` ; workers
  `PYTEST_WORKERS` sinon `workers_suite`) et pytest-randomly, dont la graine se rejoue
  (`PYTEST_GRAINE=<n>`). En `load`, les tests d'un même fichier se répartissent entre
  workers : rejouer un ordre demande la même graine ET le même nombre de workers. Chaque
  worker pose son schéma (`tests/aides_processus`), chaque fichier le trouve neuf
  (`aides_purge.remettre_a_neuf`). Les schémas jetables portent heure et créateur ; la suite
  retire ceux d'un créateur mort ou de plus de 6 h (`dialecte.schemas_jetables_a_retirer`,
  #2399). Base injoignable : `SERVEUR_INJOIGNABLE`.
- **Verrous** (#2279) : aucune transaction de la suite ne tient plus de verrous qu'un worker
  n'en a. Pose des tables en AUTOCOMMIT (`aides_base.creer_les_tables`), retrait par lots de
  `dialecte.TABLES_PAR_LOT` (`instructions_de_retrait`) — jamais `create_all` sur un schéma
  jetable ni `DROP SCHEMA` en direct. 🔒 `test_verrous_par_transaction.py`.
- **La langue du moteur vit dans `app/dialecte.py`** (intégrité, compactage, `dialecte.jour`,
  `dialecte.mois`, base jetable). Une base neuve reçoit le schéma courant d'un coup, marqué à
  la tête (`utils/schema_initial`, appelé par `start.sh`).
- `test_routeurs_nommes_par_un_test.py` : un routeur qu'aucun test ne nomme est refusé (#1569).
  « Nommé » veut dire l'import du module, son chemin `routers/…` ou l'une de ses URL montées
  écrite comme chaîne — jamais le seul nom de fichier, qu'un homonyme couvrait (#2914). Portée :
  les modules qui portent une route montée.
- **Un module s'importe seul** (#2241) : `test_imports_sans_cycle.py` ; un cycle se coupe par
  un import dans la fonction qui s'en sert.
- **Clones Python** (#1564) : `scripts/ci/clones_python.py` (jscpd épinglé) échoue dans les
  deux sens — un clone ajouté, ou un retiré sans baisser `PLAFOND_CLONES`. Sous jscpd,
  `test_copies_de_code_api.py` (#2949) : une phrase de plus de 25 caractères écrite dans deux
  modules de `app/` est une règle recopiée — une constante au module de la notion, sa porte dans
  `MESSAGES` de `test_messages_source_unique.py` —, sinon une homonymie déclarée avec sa raison
  (`HOMONYMES`, qui ne fait que baisser) ; deux fonctions au corps identique (empreinte d'AST,
  dès trois instructions) échouent (`COPIES_ADMISES` vide).
- Un contrôle front « une notion, une source » s'écrit sur `front/scripts/lib-source-unique.mjs`
  (cas zéro, témoin, exceptions déclarées) (#779).
- Un test sauté sur le poste (`@besoin_weasyprint`) est NOMMÉ par le rejeu (#1734) : seule la
  CI de la PR le joue.
