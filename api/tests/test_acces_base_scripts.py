"""Aucun script versionné n'ouvre une seconde porte sur la base de l'API.

POURQUOI CE TEST — la base se travaille DANS le process de l'API :

Purges, export, intégrité, migrations passent par l'application elle-même —
routes in-process (`POST /admin/maintenance/purges`, `POST
/admin/export-copropriete`, `GET /admin/db/integrite`) et `api/start.sh`, qui
migre avant uvicorn. C'est là que vivent le contexte de la copropriété servie
(`app/contexte.py`), le journal et les règles d'accès. Un script qui lance
l'interpréteur ou Alembic dans le conteneur ouvre une seconde porte sur la base,
hors de tout cela — et c'est arrivé : `maintenance.sh` purgeait cinq tables
chaque dimanche par `docker exec hostachy_api python -c "from app.database …"`
(#1232), `auto-deploy.sh` relançait Alembic dans le conteneur en marche à chaque
déploiement (#1683).

La base PostgreSQL, elle, sert ses lecteurs : `docker exec hostachy_postgres
psql` (C37, la taille de la base, la promotion) n'est pas visé ici.

Chaque motif garde un TÉMOIN — la ligne réelle qu'il a refusée a disparu avec
son correctif, et un motif qui ne voit plus rien rendrait le test vert à vide
(`standards/04` §2, le cas zéro).
"""

import re
from pathlib import Path

from tests.conftest import scripts_shell_versionnes

RACINE = Path(__file__).resolve().parents[2]


def lignes_de_code(chemin: Path):
    """Rend (numéro, ligne) en ignorant commentaires et lignes vides.

    Un motif cité dans un commentaire explicatif — il y en a, et ils sont utiles —
    n'est pas un geste.
    """
    for numero, ligne in enumerate(chemin.read_text(encoding="utf-8").splitlines(), 1):
        nue = ligne.strip()
        if nue and not nue.startswith("#"):
            yield numero, ligne


#: Motifs interdits SANS exception possible — (motif, message). Chacun désigne
#: une seconde porte sur la base de l'API. La portée est celle que `conftest`
#: partage : une portée recopiée diverge — celle du cron balayait
#: `scripts/**/*.sh` et ne voyait ni la racine ni les hooks.
INTERDITS_SANS_EXCEPTION = (
    #  Un script shell n'importe jamais `app.database` (#1232, 24/09/2026).
    (
        re.compile(r"\bapp\.database\b"),
        "la base ouverte par le code de l'API, depuis un process tiers — passer par "
        "une route in-process (`POST /admin/maintenance/purges`, "
        "`POST /admin/export-copropriete`…)",
    ),
    #  Aucun interpréteur Python lancé DANS le conteneur de l'API par un script
    #  (#1562) : un motif qu'on tolère « parce que celui-ci est inoffensif » est
    #  celui où le prochain ajoutera une requête.
    (
        re.compile(r"docker\s+(?:compose\s+)?exec\b[^\n#]*\bpython\d*\b"),
        "interpréteur Python lancé dans le conteneur de l'API depuis un process "
        "tiers — passer par une route in-process ; la taille de la base se demande "
        "à PostgreSQL (`pg_database_size`)",
    ),
    #  Aucune migration relancée dans le conteneur en marche (#1683, 04/10/2026) :
    #  `api/start.sh` migre déjà avant uvicorn, sous `set -e`.
    (
        re.compile(r"docker\s+(?:compose\s+)?exec\b[^\n#]*\balembic\b"),
        "Alembic lancé dans le conteneur de l'API en marche — `start.sh` migre au "
        "démarrage ; la révision appliquée se lit dans les journaux de l'API",
    ),
    #  Aucune sauvegarde côté hôte (#1029) : la sauvegarde est faite par l'API
    #  (`api/app/utils/backup.py`), qui l'éprouve avant de la dire réussie. Une
    #  protection attachée à un NOM de fichier ne survit pas au fichier : le motif
    #  vise le geste, où qu'il soit.
    (
        re.compile(r"scripts/backup\.sh|5?hostachy-backup"),
        "sauvegarde côté hôte réintroduite — la sauvegarde est faite et vérifiée "
        "par l'API (`api/app/utils/backup.py`) ; une seconde, à côté, ne serait "
        "vérifiée par rien",
    ),
)


def _motif(fragment: str):
    return next(m for m, msg in INTERDITS_SANS_EXCEPTION if fragment in msg)


def test_la_portee_voit_les_scripts():
    """Cas zéro : un scan qui ne trouve aucun script rendrait tout vert."""
    trouves = scripts_shell_versionnes()
    assert len(trouves) >= 10, (
        f"seulement {len(trouves)} script(s) trouvé(s) — chemin de scan cassé ?"
    )


def test_aucun_geste_interdit_sans_exception():
    """Chaque motif de `INTERDITS_SANS_EXCEPTION` ; l'échec les liste TOUS."""
    fautes = []
    for motif, message in INTERDITS_SANS_EXCEPTION:
        for script in scripts_shell_versionnes():
            for numero, ligne in lignes_de_code(script):
                trouve = motif.search(ligne)
                if trouve:
                    fautes.append(
                        f"{script.relative_to(RACINE).as_posix()}:{numero} "
                        f"(« {trouve.group(0)} ») : {message}\n    {ligne.strip()}"
                    )
    assert not fautes, "Geste interdit sans exception sur la base :\n" + "\n".join(fautes)


def test_motif_app_database_voit_et_ne_voit_que_lui():
    """Témoin du motif « code de l'API » (#1232)."""
    motif = _motif("code de l'API")
    assert motif.search('docker exec hostachy_api python -c "from app.database import engine"')
    assert not motif.search("source scripts/lib/lib-rapport.sh  # purges par l'API")


def test_motif_python_dans_le_conteneur_voit_et_ne_voit_que_lui():
    """Témoin du motif « interpréteur dans le conteneur » (#1562)."""
    motif = _motif("Python lancé")
    refuses = (
        "DB_SIZE=$(docker exec hostachy_api python -c \\",
        "docker exec -i hostachy_api python3 script.py",
        "docker compose exec api python -m app.x",
    )
    permis = (
        "docker exec hostachy_api curl -sf http://localhost:8000/health",
        "docker exec hostachy_api date",
        "docker stop hostachy_api",
        'docker exec hostachy_postgres psql -U coprofirst -d coprofirst -Atqc "select 1"',
    )
    for ligne in refuses:
        assert motif.search(ligne), f"le motif devrait refuser : {ligne}"
    for ligne in permis:
        assert not motif.search(ligne), f"le motif refuse à tort : {ligne}"


def test_motif_alembic_dans_le_conteneur_voit_et_ne_voit_que_lui():
    """Témoin du motif « Alembic dans le conteneur » (#1683) — la ligne réelle
    d'`auto-deploy.sh` a disparu avec le correctif : le témoin la garde ici."""
    motif = _motif("Alembic lancé")
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


def test_motif_sauvegarde_hote_voit_et_ne_voit_que_lui():
    """Témoin du motif « sauvegarde côté hôte » (#1029)."""
    motif = _motif("sauvegarde côté hôte")
    assert motif.search("0 3 * * * /opt/5hostachy/scripts/backup.sh")
    assert motif.search("cp hostachy-backup.timer /etc/systemd/system/")
    assert not motif.search("ls -1 /b/hostachy_backup_*.tar.gz")
