"""Aucun script versionné n'ouvre `app.db` pendant que l'API tourne.

POURQUOI CE TEST — trois incidents, une seule cause :

Un process TIERS qui ouvre `app.db` alors que l'API tourne casse la base. Les
connexions du pool SQLAlchemy sont ouvertes mais **sans verrou** quand elles sont
idle : le process tiers se croit donc dernière connexion, checkpointe, puis `unlink`
les fichiers WAL et SHM sous le pool. L'API écrit ensuite dans des inodes orphelins —
writes invisibles, `disk I/O error` en rafales, 503, puis perte des données au
prochain arrêt. Corruptions `telemetry_event` des 05 et 17/06/2026, panne de connexion
du 17/07/2026 (~12 h d'écritures perdues).

Ces trois incidents ont été corrigés **au cas par cas** : le contrôle fautif de
`check-reliability.sh` a été supprimé, UNE purge de `maintenance.sh` (1d) est
passée in-process — et ce paragraphe affirmait « la purge », au singulier défini,
alors que cinq autres ouvraient encore la base chaque dimanche par `docker exec
… python` (#1232, 24/09/2026). Le test ne les voyait pas : il ne cherchait que
`sqlite3`. Personne n'avait corrigé la **classe** — et le 04/08/2026 on a retrouvé
dans `setup-rpi5.sh` un installeur qui posait un cron `sqlite3 … ".backup"` côté hôte
à 03:00. Il datait de l'époque mono-RPi, il était encore inscrit dans `/etc/crontab`
de rpi1, et il n'était inoffensif que parce que le script appelé avait disparu.
Un piège armé, en attente d'une réinstallation.

CE QUE CE TEST NE FAIT PAS : interdire `sqlite3`. Trois usages sont légitimes et
nécessaires — sur une **copie**, ou sur la base **au repos, API arrêtée**. Un garde-fou
qui les interdirait serait contourné dès la semaine suivante, donc inutile. Il les
inscrit à la place dans une liste d'exceptions **justifiées**, vérifiée dans les deux
sens : une exception qui ne correspond plus à rien fait échouer le test, sinon la
liste grossit à chaque cas et finit par tout couvrir (même règle que
`test_endpoints_orphelins.py`).
"""

import re
from pathlib import Path

from tests.conftest import scripts_shell_versionnes

RACINE = Path(__file__).resolve().parents[2]

#: Ouvertures de `app.db` autorisées, avec la raison qui les rend sûres.
#: Clé = (fichier, motif exact attendu dans la ligne). Toute autre ouverture
#: échoue ; toute entrée devenue introuvable échoue aussi.
EXCEPTIONS_JUSTIFIEES = {
    (
        "bascule.sh",
        "/tmp/sync_app_data/app.db",
    ): "copie fraîchement rsyncée sur le peer, dont AUCUNE API ne tient les fichiers "
    "ouverts (conteneurs du peer arrêtés en phase 0) — c'est le contrôle d'intégrité "
    "qui précède l'installation dans le volume",
    (
        "maintenance.sh",
        "$DB_DIR/app.db",
    ): "VACUUM hebdomadaire, exécuté API STOPPÉE (0 writer) — la seule façon sûre de "
    "compacter, et la raison pour laquelle la maintenance arrête la pile d'abord",
    (
        "export-hors-site.sh",
        "$TMP/app.db",
    ): "copie extraite d'une archive .tar.gz sur le POSTE, jamais la base de "
    "production — aucun process ne la tient ouverte",
    #  Vue le 14/10/2026 seulement (#1965) : `deploiement/` échappait au relevé.
    (
        "mise-a-jour.sh",
        "'app_data/app.db",  # l'apostrophe ouvrante fait partie de la cible lue
    ): "mise à jour nocturne d'une RÉPLIQUE sous SQLite : intégrité de la COPIE extraite "
    "de la sauvegarde, dans /tmp d'un conteneur jetable, API arrêtée juste avant "
    "(`compose stop api`) — jamais le fichier du volume",
}

#: Une invocation de sqlite3 sur un fichier .db (pas une simple mention du mot).
OUVERTURE = re.compile(r"sqlite3\s+\"?(\$?[^\s\"]*\.db)")


#: Une ouverture de base en **Python** — `sqlite3.connect("…/app.db")`.
#:
#: Le motif shell ci-dessus ne pouvait pas la voir, et le scan ne regardait que
#: les `*.sh` : deux fichiers Python versionnés à la racine ouvraient
#: `/app/data/app.db` en direct depuis des mois (`debug_cc.py`,
#: `_query_events.py`, supprimés le 15/08/2026). Le contrôle qui existe pour
#: empêcher la corruption de base ne les voyait ni par son motif, ni par sa
#: portée — « la portée du contrôle fait partie du contrôle »
#: (standards/05 §9).
OUVERTURE_PY = re.compile(r"sqlite3\.connect\(\s*\"?([^\s\"\)]*\.db)")


def scripts_versionnes() -> list[Path]:
    """Tout ce qu'un humain peut lancer À CÔTÉ de l'API, quel que soit le langage.

    `api/` en est exclu : ce code s'exécute DANS le process de l'application, où
    l'accès passe par le pool SQLAlchemy — c'est un autre régime, couvert
    ailleurs. Ce test-ci vise les process **tiers**.
    """
    fichiers = list(scripts_shell_versionnes())
    #  Les `.py` lancés à la main comptent autant que les `.sh` : deux d'entre eux
    #  ouvraient la base en direct sans que ce test les regarde.
    fichiers += sorted(RACINE.glob("*.py"))
    fichiers += sorted(RACINE.glob("scripts/**/*.py"))
    fichiers += sorted(RACINE.glob("infra/**/*.py"))
    return sorted(set(fichiers))


def lignes_de_code(chemin: Path):
    """Rend (numéro, ligne) en ignorant commentaires et lignes vides.

    Un motif cité dans un commentaire explicatif — il y en a, et ils sont utiles —
    n'est pas une ouverture de base.
    """
    for numero, ligne in enumerate(chemin.read_text(encoding="utf-8").splitlines(), 1):
        nue = ligne.strip()
        if nue and not nue.startswith("#"):
            yield numero, ligne


def test_le_detecteur_voit_quelque_chose():
    """Garde-fou du garde-fou : un scan qui ne trouve aucun script rendrait tout vert.

    C'est le « cas zéro » de standards/04 §2 appliqué à ce test-ci : sans cette
    vérification, un chemin de base faux le rendrait vert à vide, pour toujours.
    """
    scripts = scripts_versionnes()
    for portee in (scripts_versionnes, scripts_shell_versionnes):
        trouves = portee()
        assert len(trouves) >= 10, (
            f"`{portee.__name__}` : seulement {len(trouves)} script(s) trouvé(s) — "
            "chemin de scan cassé ?"
        )
    assert any(OUVERTURE.search(s.read_text(encoding="utf-8")) for s in scripts), (
        "aucune ouverture de base détectée nulle part : le motif de détection ne "
        "fonctionne plus, et ce test ne protège donc plus de rien"
    )


def test_aucune_ouverture_de_base_non_justifiee():
    """Toute ouverture d'`app.db` doit figurer dans la liste des exceptions."""
    trouvees = set()
    fautes = []
    for script in scripts_versionnes():
        for numero, ligne in lignes_de_code(script):
            for cible in OUVERTURE.findall(ligne) + OUVERTURE_PY.findall(ligne):
                cle = (script.name, cible)
                if cle in EXCEPTIONS_JUSTIFIEES:
                    trouvees.add(cle)
                else:
                    fautes.append(
                        f"{script.name}:{numero} ouvre « {cible} ».\n"
                        f"    {ligne.strip()}\n"
                        f"    Si l'API tourne, cela CASSE la base (règle d'or, cf. "
                        f"CLAUDE.md et .claude/skills/infra-rpi).\n"
                        f"    À chaud, passer par les endpoints in-process : "
                        f"POST /admin/db/checkpoint, GET /admin/db/integrite.\n"
                        f"    Si l'accès est réellement sûr (copie, ou API arrêtée), "
                        f"l'inscrire dans EXCEPTIONS_JUSTIFIEES avec sa raison."
                    )
    assert not fautes, "\n\n".join(fautes)

    # Sens inverse : une exception qui ne correspond plus à rien doit disparaître.
    obsoletes = set(EXCEPTIONS_JUSTIFIEES) - trouvees
    assert not obsoletes, (
        "exception(s) devenue(s) sans objet, à retirer de EXCEPTIONS_JUSTIFIEES — "
        "une liste qu'on ne nettoie pas finit par tout autoriser : "
        + ", ".join(f"{f} → {c}" for f, c in sorted(obsoletes))
    )


#: Motifs interdits SANS exception possible — (motif, portée, message). Chacun
#: désigne la base d'un nœud en fonctionnement, ou le geste qui la cassera. La
#: portée est celle que `conftest` partage : une portée recopiée diverge — celle
#: du cron balayait `scripts/**/*.sh` et ne voyait ni la racine ni les hooks.
INTERDITS_SANS_EXCEPTION = (
    #  `docker exec … sqlite3` et `docker exec … PRAGMA` visent toujours un nœud
    #  vivant : c'est exactement la commande qui figurait dans le pré-check
    #  jusqu'au 17/07/2026, et qui a produit l'incident qu'elle devait prévenir.
    (
        re.compile(r"docker\s+exec[^\n]*(?:sqlite3|PRAGMA)"),
        scripts_versionnes,
        "accès à la base par `docker exec` — l'API tourne forcément dans ce conteneur",
    ),
    #  Un script shell n'importe jamais `app.database` (#1232, 24/09/2026) :
    #  `maintenance.sh` purgeait cinq tables chaque dimanche à 03:00 par
    #  `docker exec hostachy_api python -c "from app.database import engine …"`,
    #  API en marche. Même conteneur, autre PID, autre pool : un process TIERS
    #  aussi sûrement qu'un `sqlite3` hôte, que ce fichier ne voyait pas parce
    #  qu'il ne cherchait que `sqlite3`.
    (
        re.compile(r"\bapp\.database\b"),
        scripts_shell_versionnes,
        "la base ouverte par le code de l'API, depuis un process tiers — à chaud, "
        "passer par une route in-process (`POST /admin/maintenance/purges`, "
        "`/admin/db/checkpoint`…)",
    ),
    #  Aucun interpréteur Python lancé DANS le conteneur de l'API par un script
    #  (#1562). Le dernier survivant lisait seulement la TAILLE du fichier
    #  (`os.path.getsize`), sans ouvrir la base — mais c'est la forme que #1232 a
    #  bannie, et un motif qu'on tolère « parce que celui-ci est inoffensif »
    #  est celui où le prochain ajoutera une requête. La taille d'un fichier se lit
    #  depuis l'hôte (`rapport_taille_fichier`, `lib-rapport.sh`) ; le reste passe
    #  par une route in-process.
    (
        re.compile(r"docker\s+(?:compose\s+)?exec\b[^\n#]*\bpython\d*\b"),
        scripts_shell_versionnes,
        "interpréteur Python lancé dans le conteneur de l'API depuis un process "
        "tiers — lire la taille du fichier depuis l'hôte (`rapport_taille_fichier`), "
        "le reste par une route in-process",
    ),
    #  Aucune migration relancée dans le conteneur en marche (#1683, 04/10/2026).
    #  `auto-deploy.sh` le faisait à CHAQUE déploiement, après `up -d` — ce test
    #  le citait comme geste « permis », parce que le motif Python ne le voyait
    #  pas. `api/start.sh` migre déjà avant uvicorn, sous `set -e` : la relance
    #  n'apportait rien, sinon un process tiers sur la base vivante.
    (
        re.compile(r"docker\s+(?:compose\s+)?exec\b[^\n#]*\balembic\b"),
        scripts_shell_versionnes,
        "Alembic lancé dans le conteneur de l'API en marche — `start.sh` migre au "
        "démarrage ; la révision appliquée se lit dans les journaux de l'API",
    ),
    #  Aucune sauvegarde côté hôte : retirée de `setup-rpi5.sh` le 04/08/2026, où
    #  elle avait survécu à la haute disponibilité parce que personne n'avait
    #  relu ce fichier depuis mars 2026. ⚠️ Ce contrôle ne visait QUE ce script
    #  jusqu'au 20/09/2026 (#1029) — supprimé, le test est mort avec lui sur un
    #  `FileNotFoundError` : une protection attachée à un NOM de fichier ne
    #  survit pas au fichier. La sauvegarde est in-process depuis la v2.18
    #  (`api/app/utils/backup.py`), avec `PRAGMA quick_check` préalable.
    (
        re.compile(r"scripts/backup\.sh|5?hostachy-backup"),
        scripts_shell_versionnes,
        'sauvegarde côté hôte réintroduite — un `sqlite3 ".backup"` lancé depuis '
        "l'hôte pendant que l'API tourne casse la base",
    ),
)


def test_aucun_geste_interdit_sans_exception():
    """Chaque motif de `INTERDITS_SANS_EXCEPTION`, sur sa portée ; l'échec les liste TOUS."""
    fautes = []
    for motif, portee, message in INTERDITS_SANS_EXCEPTION:
        for script in portee():
            for numero, ligne in lignes_de_code(script):
                trouve = motif.search(ligne)
                if trouve:
                    fautes.append(
                        f"{script.relative_to(RACINE).as_posix()}:{numero} "
                        f"(« {trouve.group(0)} ») : {message}\n    {ligne.strip()}"
                    )
    assert not fautes, "Geste interdit sans exception sur la base :\n" + "\n".join(fautes)


def test_motif_python_dans_le_conteneur_voit_et_ne_voit_que_lui():
    """Cas zéro du motif « interpréteur dans le conteneur » (#1562).

    Le motif a été prouvé sur la ligne réelle qu'il devait refuser — elle a disparu
    avec le correctif, donc le test du dessus ne le prouverait plus. Il garde ici un
    témoin qui doit être refusé, et les gestes voisins, légitimes, qui ne le sont pas.
    """
    motif = next(m for m, _portee, msg in INTERDITS_SANS_EXCEPTION if "Python lancé" in msg)
    refuses = (
        "DB_SIZE=$(docker exec hostachy_api python -c \\",
        "docker exec -i hostachy_api python3 script.py",
        "docker compose exec api python -m app.x",
    )
    permis = (
        "docker exec hostachy_api curl -sf http://localhost:8000/health",
        "docker exec hostachy_api date",
        "docker stop hostachy_api",
    )
    for ligne in refuses:
        assert motif.search(ligne), f"le motif devrait refuser : {ligne}"
    for ligne in permis:
        assert not motif.search(ligne), f"le motif refuse à tort : {ligne}"


def test_motif_alembic_dans_le_conteneur_voit_et_ne_voit_que_lui():
    """Cas zéro du motif « Alembic dans le conteneur » (#1683) — la ligne réelle
    d'`auto-deploy.sh` a disparu avec le correctif : le témoin la garde ici."""
    motif = next(m for m, _portee, msg in INTERDITS_SANS_EXCEPTION if "Alembic lancé" in msg)
    refuses = (
        "docker exec hostachy_api sh -lc 'cd /app && alembic upgrade head' 2>/dev/null || true",
        "docker exec hostachy_api alembic current",
        "docker compose exec api alembic upgrade head",
    )
    permis = (
        "docker compose logs api 2>&1 | grep -i alembic",
        "alembic upgrade head",
    )
    for ligne in refuses:
        assert motif.search(ligne), f"le motif devrait refuser : {ligne}"
    for ligne in permis:
        assert not motif.search(ligne), f"le motif refuse à tort : {ligne}"
