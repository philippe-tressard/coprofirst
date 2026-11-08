"""Aucun conteneur ne sert en root — et le contrôle regarde le FAIT, pas le mot.

## Le défaut (#769, audit du 05/09/2026)

`api/Dockerfile` et `front/Dockerfile` ne posaient aucun `USER` : les deux
conteneurs s'exécutaient en **root**. Un défaut d'exécution — rendu PDF,
dépendance compromise, désérialisation — donnait alors root sur le volume de
données. Le confinement Docker ne sépare rien quand le processus est root.

🔴 Le front CRÉAIT DÉJÀ l'utilisateur (`adduser -S app`) et ne s'en servait
jamais. C'est le pire des trois états : un `grep adduser` rassurait, et rien ne
protégeait. Un compte créé mais jamais endossé ne donne que l'air.

## Ce que ce test vérifie, et pourquoi pas simplement « USER est présent »

L'API ne PEUT PAS poser `USER` dans son Dockerfile : ses trois volumes sont
écrits par root sur les deux nœuds, et un conteneur qui démarrerait directement
en `app` ne pourrait plus y écrire. Elle bascule donc dans `start.sh`,
après avoir repris les propriétés.

Exiger le mot `USER` aurait donc refusé la seule solution qui marche, et poussé
à la contourner. Le test demande le FAIT — « ce conteneur finit-il par quitter
root ? » — et accepte les deux formes, en vérifiant pour chacune ce qui la rend
vraie.
"""

from __future__ import annotations

import pathlib
import re

_RACINE = pathlib.Path(__file__).resolve().parents[2]


def _lire(chemin: str) -> str:
    fichier = _RACINE / chemin
    assert fichier.exists(), f"{chemin} introuvable — le contrôle a perdu sa portée"
    return fichier.read_text(encoding="utf-8")


def test_le_front_endosse_l_utilisateur_qu_il_cree():
    """`adduser` sans `USER` : le compte existe, le serveur reste root."""
    source = _lire("front/Dockerfile")
    assert re.search(r"\badduser\b", source), (
        "l'utilisateur applicatif du front a disparu du Dockerfile"
    )
    assert re.search(r"^\s*USER\s+app\s*$", source, re.M), (
        "front/Dockerfile crée un utilisateur `app` mais ne l'endosse pas : "
        "le serveur SSR tourne en root. Ajouter `USER app` avant `CMD`."
    )


def test_l_api_bascule_hors_de_root_avant_d_ecrire():
    """L'API ne peut pas poser `USER` — elle doit donc basculer dans `start.sh`.

    Trois choses sont exigées, et chacune répare une moitié du geste :

    1. l'utilisateur existe (`useradd`) ;
    2. `start.sh` reprend les propriétés des volumes — sans quoi le processus
       non-root ne pourrait pas écrire dans des volumes écrits par root ;
    3. il se relance en `app` **avant** Alembic : ce qui s'exécute ensuite ne
       tourne jamais en root.
    """
    dockerfile = _lire("api/Dockerfile")
    assert re.search(r"\buseradd\b.*\bapp\b", dockerfile), (
        "api/Dockerfile ne crée plus d'utilisateur applicatif"
    )

    start = _lire("api/start.sh")
    assert "chown -R app:app" in start, (
        "start.sh ne reprend plus les propriétés des volumes : un conteneur "
        "non-root ne pourra pas écrire dans ses volumes, écrits par root."
    )
    bascule = re.search(r"^\s*exec setpriv .*--reuid=app\b.*$", start, re.M)
    assert bascule, (
        "start.sh ne bascule plus hors de root : l'API sert en root, ce que #769 corrigeait."
    )
    #  Les migrations de CHAQUE base passent par `utils/preparer_bases` (#2053).
    alembic = re.search(r"^BASES=\$\(python -m app\.utils\.preparer_bases\)$", start, re.M)
    assert alembic, "start.sh ne lance plus les migrations"
    assert bascule.start() < alembic.start(), (
        "les migrations tournent AVANT la bascule : elles s'exécuteraient en root."
    )


def test_le_bridge_descend_vers_node_avant_de_servir():
    """Le bridge démarre en root le temps de rendre son état à `node` (#2368).

    Son conteneur est durci (`docker-compose.yml`) : root n'y garde que de quoi
    réaligner `auth_state` et changer d'identité. La descente doit donc avoir
    lieu, et AVANT que Baileys ou le serveur HTTP ne démarrent ; le compte vers
    lequel elle descend se vérifie à la construction de l'image.
    """
    index = _lire("whatsapp-bridge/index.js")
    descente = re.search(r"^\s*const descente = descendreDeRoot\(AUTH_DIR\);", index, re.M)
    assert descente, "index.js n'appelle plus descendreDeRoot : Baileys tourne en root"
    for premier_usage in ("useMultiFileAuthState(AUTH_DIR)", "app.listen("):
        assert premier_usage in index, f"repère introuvable dans index.js : {premier_usage}"
        assert descente.start() < index.index(premier_usage), (
            f"{premier_usage} précède la descente : il s'exécuterait en root"
        )
    dockerfile = _lire("whatsapp-bridge/Dockerfile")
    assert re.search(r"^COPY .*\bprivileges\.js\b", dockerfile, re.M), (
        "privileges.js n'est plus copié dans l'image : le bridge ne démarre pas"
    )
    assert '"$(id -u node):$(id -g node)" = "1000:1000"' in dockerfile, (
        "l'uid du compte node n'est plus vérifié à la construction (privileges.js le suppose)"
    )


#: Service durci qui DÉMARRE en root → le compte vers lequel son point d'entrée
#: descend. Confronté au compose et aux Dockerfile : la table ne se croit pas.
DESCENTE = {"api": "app", "whatsapp-bridge": "node"}

#: (fichier, service) → raison et ticket. Le test échoue si l'une cesse de servir.
#: Vide depuis #2547 : la restauration hors site installait ses fichiers en root.
#: Ses lanceurs `docker run` du banc, que ce contrôle ne lit pas (une image, pas un
#: service), sont tenus par `test_restauration_hors_site_durcie.py`.
EXCEPTIONS_COMPTE: dict[tuple[str, str], str] = {}


def _racines() -> dict[str, str]:
    from tests.aides_commandes_ponctuelles import demarrent_en_root
    from tests.aides_compose import COMPOSE, instructions_dockerfile, lire_yaml, services_construits

    images = {}
    for nom, (_contexte, dockerfile) in services_construits().items():
        users = [v for i, v in instructions_dockerfile(_lire(dockerfile)) if i == "USER"]
        images[nom] = users[-1].strip() if users else None
    return demarrent_en_root(lire_yaml(COMPOSE)["services"], images)


def _sources():
    """(chemin relatif, texte, est un script) : les scripts shell versionnés (hors
    commentaires), les documents d'exploitation et les docstrings du code."""
    from tests.conftest import scripts_shell_versionnes

    sources = [(s, True) for s in scripts_shell_versionnes()]
    for motif in ("deploiement/**/*.md", "docs/**/*.md", "api/app/**/*.py", "README.md"):
        sources += [(p, False) for p in _RACINE.glob(motif)]
    for chemin, est_script in sources:
        yield chemin.relative_to(_RACINE).as_posix(), chemin.read_text(encoding="utf-8"), est_script


def test_les_services_qui_demarrent_en_root_sont_ceux_de_la_table():
    """`DESCENTE` dit vers quel compte chacun descend : un service durci neuf qui
    démarre en root s'y déclare, et la règle ci-dessous le couvre d'elle-même."""
    assert set(_racines()) == set(DESCENTE), (
        f"services durcis qui démarrent en root : {sorted(_racines())}, "
        f"déclarés dans DESCENTE : {sorted(DESCENTE)}"
    )


def test_une_commande_ponctuelle_nomme_son_compte():
    """`run`, `exec` ou `docker exec` sur un service qui démarre en root, sans `-u`.

    La commande saute le point d'entrée, donc sa descente : elle reste root, mais
    le root d'un conteneur durci n'a ni DAC_OVERRIDE ni FOWNER (#2368). Déclarer une
    copropriété échouait ainsi sur le banc du standby (`exec`) ; le 05/11/2026, la
    remise à zéro de la démo n'a pu supprimer aucun fichier (`run --entrypoint`),
    l'API arrêtée et la base vide, et la sauvegarde de `mise-a-jour.sh` était
    refusée chaque nuit (#2546). Sous `-u app` — ou le compte de qui lance le
    script, quand il écrit chez lui —, la commande a les droits qu'elle croit avoir.
    """
    from tests.aides_commandes_ponctuelles import commandes, fautes, lignes_logiques

    racines = _racines()
    conteneurs = {c: s for s, c in racines.items()}
    vues, trouvees, servies = 0, [], set()
    for chemin, texte, script in _sources():
        vues += sum(
            len(commandes(ligne, conteneurs)) for _n, ligne in lignes_logiques(texte, script=script)
        )
        for numero, service, compte in fautes(texte, racines, script=script):
            if (chemin, service) in EXCEPTIONS_COMPTE:
                servies.add((chemin, service))
                continue
            dit = f"en `{compte}`" if compte else "sans compte"
            trouvees.append(f"{chemin}:{numero} : `{service}` {dit} → `-u {DESCENTE[service]}`")
    #  Cas zéro : `creer-copropriete.sh`, `mise-a-jour.sh` et la remise à zéro en
    #  portent à eux trois plus de dix ; une portée cassée ne verrait rien.
    assert vues >= 10, f"{vues} commande(s) vue(s) seulement : portée ou découpage cassé"
    assert not trouvees, (
        "Commande ponctuelle dans un conteneur durci qui démarre en root, sans compte :\n"
        + "\n".join(trouvees)
    )
    assert servies == set(EXCEPTIONS_COMPTE), (
        f"exception(s) qui ne servent plus : {sorted(set(EXCEPTIONS_COMPTE) - servies)}"
    )


def test_le_decoupage_des_commandes_voit_et_ne_voit_que_elles():
    """Témoins : chaque forme employée dans le dépôt, et ce qui se laisse."""
    from tests.aides_commandes_ponctuelles import demarrent_en_root, fautes

    services = {
        "api": {"cap_drop": ["ALL"], "container_name": "hostachy_api"},
        "postgres": {
            "cap_drop": ["ALL"],
            "user": "postgres",
            "container_name": "hostachy_postgres",
        },
        "front": {"cap_drop": ["ALL"], "container_name": "hostachy_front"},
        "libre": {"image": "alpine"},
    }
    racines = demarrent_en_root(services, {"front": "app"})
    assert racines == {"api": "hostachy_api"}

    def n(texte: str) -> int:
        return len(fautes(texte, racines, script=True))

    refusees = (
        'P=("${COMPOSE[@]}" run --rm --no-deps -T --entrypoint sh api -c)',  # l'incident
        "docker compose run --rm --user root -v a:/b api x",
        "docker compose exec -u 0 api x",
        '"${COMPOSE[@]}" exec -T api python -m x',
        "docker compose exec api python -m app.seed --copropriete tilleuls",
        "docker exec -i hostachy_api python3 script.py",
        "docker exec hostachy_api curl -s http://localhost:8000/health",
        "docker compose run --rm \\\n    --entrypoint sh api -c x",
    )
    admises = (
        '"${COMPOSE[@]}" run --rm --no-deps -T -u app --entrypoint sh api -c',
        "docker compose run --rm --user app api python -V",
        "docker compose run --rm --user=app api python -V",
        "docker compose exec -uapp api python -V",
        "docker exec --user=app hostachy_api python x",
        '"${COMPOSE[@]}" run --rm -T -u "$(id -u):$(id -g)" -v "$S:/sortie" --entrypoint python api',
        "docker compose run --rm \\\n    -u app api python -V",
        '"${COMPOSE[@]}" exec -T postgres psql -c x',  # `user:` dans le compose
        "docker exec hostachy_front node -v",  # `USER` dans l'image
        'docker run --rm "$IMAGE" sh -c x',  # une image, pas un service
        "# docker compose run --entrypoint sh api",
        "echo run api ; make run api",
        "docker compose ps && run api",
        "docker compose logs api",
    )
    for ligne in refusees:
        assert n(ligne) == 1, f"devrait être refusée : {ligne}"
    for ligne in admises:
        assert n(ligne) == 0, f"devrait passer : {ligne}"
    assert fautes("docker compose run --rm \\\n  --entrypoint sh api", racines, script=True) == [
        (1, "api", None)
    ], "une ligne coupée se signale à sa première ligne"


def test_postgresql_tourne_en_postgres_sans_capacite():
    """PostgreSQL est durci (#2429) en tournant DIRECTEMENT sous `postgres`.

    L'image officielle démarre en root pour rendre `PGDATA` à `postgres`, puis
    descend par `gosu` ; durcie sans capacité, elle ne démarrerait plus (mesuré :
    `chown … Operation not permitted`). Perdre `user: postgres` ne se verrait donc
    qu'à la RECRÉATION de la base — la nuit, juste après la promotion de la
    bascule. Le socket local est sa seule écriture hors du volume : sans `tmpfs`,
    la racine en lecture seule l'empêche d'écouter.
    """
    from tests.aides_compose import COMPOSE, lire_yaml

    base = lire_yaml(COMPOSE)["services"]["postgres"]
    assert base.get("user") == "postgres", (
        "le service postgres ne tourne plus sous `postgres` : l'image repartirait en "
        "root, sans les capacités qu'il lui faudrait, et la base ne démarrerait pas"
    )
    assert base.get("cap_drop") == ["ALL"] and base.get("read_only") is True, (
        "le service postgres n'est plus durci (`<<: *conteneur_durci`)"
    )
    assert not base.get("cap_add"), "le service postgres n'a besoin d'aucune capacité"
    assert any(str(t).startswith("/var/run/postgresql:") for t in base.get("tmpfs", [])), (
        "plus de tmpfs sur /var/run/postgresql : le socket local ne peut plus s'y créer"
    )
    #  La reconstruction de la réplique hérite de ce compte : un `--user` la
    #  rendrait à root, qui n'a plus de quoi vider `PGDATA`.
    reconstruire = _lire("scripts/exploitation/reconstruire-replique.sh")
    runs = re.findall(r"docker compose run\b[^\n]*\bpostgres\b", reconstruire)
    assert runs, "le `docker compose run` de reconstruire-replique.sh n'est plus vu"
    assert not [r for r in runs if re.search(r"(?:^|\s)(?:-u|--user)\b", r)], (
        "reconstruire-replique.sh force un compte au `run` de la base : " + "; ".join(runs)
    )


def test_caddy_sert_sous_son_compte_sans_capacite():
    """Caddy ne sert plus en root (#2430) — et sans descente : sous `USER caddy`.

    L'image officielle n'a pas de compte : Caddy tournait en uid 0, sans autre
    capacité que `NET_BIND_SERVICE`. Ses volumes d'avant, écrits par root, ne
    s'ouvrent pas à un autre compte sans `DAC_OVERRIDE` ; les lui rendre au
    démarrage (la descente de l'API) casserait le retour à l'image d'avant, qui ne
    les ouvrirait plus non plus (mesuré sur le banc du standby : sortie 1,
    « opening log writer »). Ses volumes sont donc NEUFS, et naissent au compte de
    l'image : Docker recopie le point de montage, propriétaire compris. Ce test
    tient les trois moitiés du geste :

    1. le compte existe à un uid FIXE, vérifié à la construction, et l'image
       l'endosse — ses trois dossiers d'écriture lui appartenant dans l'image ;
    2. le compose ne lui rend ni root (`user:`) ni capacité, et ouvre :80 par le
       sysctl de son espace réseau ;
    3. ses volumes ne sont plus ceux d'avant : remonter `caddy_data` ou
       `caddy_logs` le ferait tomber au premier déploiement (« permission denied »).
    """
    from tests.aides_compose import COMPOSE, lire_yaml

    dockerfile = _lire("Dockerfile.caddy")
    finale = dockerfile.rsplit("\nFROM ", 1)[-1]
    assert re.search(r"\badduser\b.*-u 10002\b.*\bcaddy\s*\\?$", finale, re.M), (
        "Dockerfile.caddy ne crée plus le compte `caddy` (uid 10002) dans l'image servie"
    )
    assert '[ "$(id -u caddy):$(id -g caddy)" = "10002:10002" ]' in finale, (
        "l'uid du compte caddy n'est plus vérifié à la construction"
    )
    assert re.search(r"chown -R caddy:caddy /data /config /var/log/caddy\b", finale), (
        "les dossiers d'écriture de Caddy ne sont plus rendus à `caddy` dans l'image : "
        "un volume neuf naîtrait à root, et Caddy ne pourrait pas y écrire"
    )
    users = re.findall(r"^\s*USER\s+(\S+)\s*$", finale, re.M)
    assert users and users[-1] == "caddy", (
        "Dockerfile.caddy n'endosse plus le compte `caddy` (`USER caddy`) : Caddy sert en root"
    )

    caddy = lire_yaml(COMPOSE)["services"]["caddy"]
    assert "user" not in caddy, (
        "le compose impose un compte à Caddy : c'est l'image qui le porte (`USER caddy`)"
    )
    assert caddy.get("cap_drop") == ["ALL"] and caddy.get("read_only") is True, (
        "le service caddy n'est plus durci (`<<: *conteneur_durci`)"
    )
    assert not caddy.get("cap_add"), (
        "Caddy n'a besoin d'aucune capacité : :80 s'ouvre par le sysctl, et rien ne "
        "se réaligne au démarrage"
    )
    assert "net.ipv4.ip_unprivileged_port_start=80" in (caddy.get("sysctls") or []), (
        "plus de seuil des ports privilégiés à 80 dans l'espace réseau de Caddy"
    )
    montes = {str(v).split(":")[0]: str(v).split(":")[1] for v in (caddy.get("volumes") or [])}
    for ancien in ("caddy_data", "caddy_config", "caddy_logs"):
        assert ancien not in montes, (
            f"le volume {ancien}, écrit par root, est remonté dans Caddy : `caddy` ne "
            "l'ouvrirait pas — un volume neuf naît à son compte"
        )
    for neuf, cible in (
        ("caddy_donnees", "/data"),
        ("caddy_configuration", "/config"),
        ("caddy_journal", "/var/log/caddy"),
    ):
        assert montes.get(neuf) == cible, f"le volume {neuf} n'est plus monté sur {cible}"
