"""`.env.example` est le gabarit d'installation — il doit démarrer la stack.

## L'incident (#1029, audit du 19/09/2026)

`scripts/installation/setup-rpi5.sh` était **le** script d'installation d'un nœud
neuf. Il générait son propre `.env`, et ce `.env` ne pouvait pas démarrer la
stack :

| Ce qu'il écrivait | Le réel |
|---|---|
| `MAIL_TLS`, `APP_ENV`, `PI_IP`, `DOMAIN` | aucun champ correspondant dans `Settings` |
| — | **`WHATSAPP_API_KEY` absente**, et `docker-compose.yml` la rend obligatoire (`:?`) → `docker compose up` **refuse de démarrer** |

Le script a été supprimé et `docs/restauration-complete.md` est désormais la
seule procédure. Mais supprimer ne protège de rien : le défaut n'était pas le
script, c'était que **personne ne confrontait le gabarit d'installation à ce que
le code lit réellement**. Trois fichiers écrivent des noms de variables —
`.env.example`, `config.py`, `docker-compose.yml` — et aucun langage ne les
compare.

## Ce que ces tests verrouillent

1. une variable **obligatoire** de compose figure dans le gabarit (sinon
   l'installation échoue au premier `up`) ;
2. une variable du gabarit est **lue par quelqu'un** (sinon elle promet une
   capacité qui n'existe pas — c'est ainsi que quatre clés `APPLE_*` y
   annonçaient un OAuth Apple jamais écrit) ;
3. tout réglage de `Settings` est **visible** de l'exploitant, ou déclaré hors
   gabarit avec sa raison — `INSTANCE_ID` ne l'était nulle part, et le pied de
   page restait muet sur le nœud servant ;
4. `DATABASE_URL` désigne le service `postgres` de compose, avec **sa** base et
   **son** utilisateur — et son mot de passe, que le gabarit déclare ;
5. aucun script versionné ne **regénère** un `.env` ou un `Caddyfile` — c'est le
   geste exact qui a produit l'incident, et rien n'empêchait de le réintroduire ;
6. les deux réglages qui dépendent du **rôle** du nœud (`ORIGIN`,
   `COOKIE_SECURE`) ne s'écrivent que dans `scripts/lib/lib-env-role.sh` — ils
   l'étaient quatre fois dans trois scripts (#1077) ;
7. ce module porte son `--selftest`, et la CI le lance : sans lui, le point 6
   serait creux — on peut appeler la bonne fonction et qu'elle écrive n'importe
   quoi.

⚠️ Le point 3 porte une liste d'exceptions **déclarée** : trois champs de
`Settings` n'ont volontairement pas leur place dans le gabarit. Le test échoue
aussi quand l'une d'elles cesse de servir — sinon la liste grossit jusqu'à tout
couvrir (`standards/05` §2).
"""

import re
from pathlib import Path

import yaml

from tests.aides_sources import modules_app
from tests.conftest import scripts_shell_versionnes

RACINE = Path(__file__).resolve().parents[2]
EXEMPLE = RACINE / ".env.example"
COMPOSE_TXT = (RACINE / "docker-compose.yml").read_text(encoding="utf-8")
CONFIG_TXT = (RACINE / "api" / "app" / "config.py").read_text(encoding="utf-8")

#: Champs de `Settings` qui n'ont PAS à figurer dans le gabarit, et pourquoi.
#: Une entrée devenue fausse fait échouer `test_les_exceptions_servent_encore`.
HORS_GABARIT = {
    "algorithm": "l'algorithme JWT n'est pas un réglage d'exploitant : le changer "
    "invaliderait tous les jetons en circulation",
    "uploads_dir": "chemin INTERNE au conteneur, fixé par le volume "
    "`uploads:/app/uploads` — le déclarer dans .env laisserait croire qu'on peut "
    "le déplacer sans toucher au volume",
    "cache_manuel_dir": "chemin INTERNE au conteneur, dans le volume `app_data:/app/data` "
    "— le déplacer hors du volume perdrait le cache à chaque recréation",
    "git_hash": "posé par la CONSTRUCTION de l'image (`ARG GIT_HASH`, api/Dockerfile) : "
    "c'est le commit qu'elle contient, pas un réglage d'exploitant (#1761)",
    "wa_photo_budget_ko": "posé par l'ancre `x-budget-photo-whatsapp` de "
    "docker-compose.yml, lue des DEUX côtés (API et bridge) ; une seconde source "
    "les ferait diverger (#1057)",
}


#: Écritures dans `.env` qui ne sont PAS une regénération. Vide depuis le
#: 20/09/2026 : la seule qui s'y trouvait — `bascule.sh` ajoutant
#: `COOKIE_SECURE=false` — est passée par `lib-env-role.sh`, et le test
#: `test_les_reglages_de_role_ne_s_ecrivent_qu_une_fois` la couvre désormais.
#: Elle est restée déclarée le temps d'un lot, avec sa réserve écrite, plutôt
#: que tolérée en silence : c'est la différence entre une exception et un oubli.
AJUSTEMENTS_DECLARES: dict[tuple[str, str], str] = {
    #  Le self-test des notes de version (#1754) bâtit un dépôt JETABLE (`mktemp`)
    #  pour éprouver la lecture des réglages ajoutés et retirés : il n'écrit le
    #  `.env.example` d'aucune installation.
    ("notes-de-version.sh", "printf 'A=1\\nC=3\\n' > .env.example"): (
        "self-test : version 1 du gabarit, dans un dépôt jetable"
    ),
    ("notes-de-version.sh", "printf 'A=1\\nB=2\\n' > .env.example"): (
        "self-test : version 2 du gabarit, dans un dépôt jetable"
    ),
    #  La bascule des données (DI-7c, #1782) et son retour changent UNE ligne,
    #  `DATABASE_URL`, sur les deux nœuds — et gardent l'ancienne en commentaire
    #  daté. Un ajustement de la base servie, jamais une régénération du `.env`.
    ("lib-env-base.sh", '"$t" > "$REPO/.env"'): (
        "DATABASE_URL de ce nœud (bascule des données DI-7c et son retour)"
    ),
    #  L'essai de la mise à jour nocturne (DI-4) remplit le `.env` d'une
    #  installation JETABLE, sur un runner de CI, comme un exploitant le ferait.
    ("essai-mise-a-jour.sh", '"$1" "$2" >> .env'): (
        "essai de bout en bout : le .env d'une installation jetable, tirée de .env.example"
    ),
    ("lib-env-base.sh", "cat > /opt/5hostachy/.env.tmp"): (
        "DATABASE_URL du pair, réécrit en 600 (bascule des données DI-7c et son retour)"
    ),
    #  Vue le 14/10/2026 seulement (#1965) : `deploiement/` échappait au relevé.
    #  La mise à jour nocturne d'une RÉPLIQUE (#1756) pose UNE ligne, la version
    #  d'image à servir, après avoir gardé le `.env` d'avant dans `.precedent` pour
    #  le retour arrière.
    #  Ajouter une copropriété à une installation commune (#2053) AJOUTE ses deux
    #  variables — l'URL de sa base, son secret —, après avoir refusé si elles y sont.
    ("creer-copropriete.sh", "} >> .env"): (
        "l'URL de la base et le secret d'une copropriété neuve, ajoutés, jamais réécrits"
    ),
    ("mise-a-jour.sh", 'echo "COPROFIRST_VERSION=$CIBLE" >> .env'): (
        "version d'image cible d'une réplique, l'ancien .env gardé pour le retour arrière"
    ),
}


def _cles_du_gabarit() -> list[str]:
    return [
        m.group(1)
        for m in re.finditer(r"(?m)^([A-Z][A-Z0-9_]*)=", EXEMPLE.read_text(encoding="utf-8"))
    ]


def _champs_de_settings() -> set[str]:
    """Les champs déclarés par `Settings` — l'indentation de 4 les distingue."""
    return {m.group(1) for m in re.finditer(r"(?m)^\s{4}([a-z][a-z0-9_]*)\s*:", CONFIG_TXT)}


def _sources_python() -> str:
    return " ".join(m.source for m in modules_app())


def test_les_variables_obligatoires_de_compose_sont_dans_le_gabarit():
    """`${X:?…}` fait échouer `docker compose up` — le gabarit doit la porter.

    C'est le défaut exact qui rendait `setup-rpi5.sh` inapplicable : il écrivait
    un `.env` sans `WHATSAPP_API_KEY`, et l'installation s'arrêtait au démarrage
    des conteneurs, après toute la préparation du système.
    """
    obligatoires = set(re.findall(r"\$\{([A-Z0-9_]+):\?", COMPOSE_TXT))
    assert obligatoires, (
        "aucune variable obligatoire trouvée dans docker-compose.yml : le motif "
        "`${X:?…}` a changé de forme, et ce test ne mesure plus rien"
    )
    manquantes = obligatoires - set(_cles_du_gabarit())
    assert not manquantes, (
        f"docker-compose.yml exige {sorted(manquantes)} (`:?`) mais .env.example ne "
        f"la/les déclare pas : une installation faite depuis le gabarit ne démarrera pas"
    )


def test_aucune_variable_du_gabarit_n_est_morte():
    """Une clé du gabarit doit être lue par `Settings`, compose, ou `os.getenv`.

    Une clé que personne ne lit n'est pas inoffensive : elle annonce une capacité.
    Quatre clés `APPLE_*` y promettaient une connexion Apple qui n'a jamais été
    écrite, et `DOMAIN` survivait à l'époque où Caddy servait un nom de domaine
    local — aujourd'hui le TLS est chez Cloudflare et le Caddyfile écoute `:80`.
    """
    champs = {c.upper() for c in _champs_de_settings()}
    lues_par_compose = set(re.findall(r"\$\{([A-Z0-9_]+)", COMPOSE_TXT))
    #  `os.environ.get` autant qu'`os.getenv` : `main.py` lit `LOG_LEVEL` par la
    #  première, et ce motif ne voyait que la seconde (#1050).
    motif_getenv = r"(?:getenv|environ\.get)\(\s*[\"']([A-Z0-9_]+)"
    lues_par_getenv = set(re.findall(motif_getenv, _sources_python()))
    mortes = [
        c
        for c in _cles_du_gabarit()
        if c not in champs and c not in lues_par_compose and c not in lues_par_getenv
    ]
    assert not mortes, (
        f".env.example déclare {mortes} que personne ne lit — ni `Settings` "
        f"(api/app/config.py), ni docker-compose.yml, ni un `os.getenv`. Soit le "
        f"code a perdu la variable, soit le gabarit promet ce qui n'existe pas"
    )


def test_tout_champ_de_settings_est_dans_le_gabarit_ou_declare_hors():
    """L'autre sens : un réglage que l'exploitant ne voit pas n'est pas réglable.

    `INSTANCE_ID` en était l'exemple : lue par compose, par `config.py`, par
    `utils/noeud.py` et affichée au pied de page, déclarée **nulle part** — le
    nœud s'annonçait donc vide sur toute installation neuve.
    """
    cles = {c.lower() for c in _cles_du_gabarit()}
    absents = sorted(_champs_de_settings() - cles - set(HORS_GABARIT))
    assert not absents, (
        f"`Settings` déclare {absents}, que .env.example ne montre pas : ajoutez-les "
        f"au gabarit, ou inscrivez-les dans HORS_GABARIT avec la raison qui les en exclut"
    )


def test_tout_champ_de_settings_est_lu_par_le_code():
    """Un champ que rien ne lit fait passer une clé morte pour une clé vivante.

    Le trou que ce test ferme (#1050) : les tests ci-dessus confrontent le
    gabarit à `Settings`, jamais `Settings` au CODE. `BACKUP_FREQUENCY`,
    `BACKUP_DAY_OF_WEEK` et `GOOGLE_CLIENT_ID/SECRET` y ont donc survécu : ils
    étaient déclarés des deux côtés, et aucune ligne de l'API ne les lisait. Un
    exploitant qui réglait la fréquence des sauvegardes croyait la changer — la
    sauvegarde tourne chaque jour, à l'heure de la configuration du site.
    """
    sources = " ".join(m.source for m in modules_app() if m.chemin.name != "config.py")
    jamais_lus = sorted(c for c in _champs_de_settings() if not re.search(rf"\.{c}\b", sources))
    assert not jamais_lus, (
        f"`Settings` déclare {jamais_lus}, qu'aucune ligne de api/app/ ne lit : "
        f"le réglage ne fait rien. Retirer le champ, et sa clé de .env.example"
    )


def test_les_exceptions_servent_encore():
    """Une exception qui ne correspond plus à rien fait échouer le contrôle."""
    champs = _champs_de_settings()
    perimees = sorted(set(HORS_GABARIT) - champs)
    assert not perimees, (
        f"HORS_GABARIT retient {perimees}, qui n'existe(nt) plus dans `Settings` : "
        f"retirez l'entrée, sinon la liste protège un champ disparu"
    )
    dans_les_deux = sorted(set(HORS_GABARIT) & {c.lower() for c in _cles_du_gabarit()})
    assert not dans_les_deux, (
        f"{dans_les_deux} est à la fois déclaré hors gabarit et présent dans "
        f".env.example : l'une des deux décisions est fausse"
    )


def test_la_base_de_l_exemple_est_le_service_postgres_du_compose():
    """`DATABASE_URL` du gabarit vise le serveur que compose démarre, tel qu'il s'initialise.

    Une base, un utilisateur ou un hôte qui ne seraient pas ceux du service
    `postgres` : la stack démarre, et l'API ne se connecte jamais.
    """
    gabarit = EXEMPLE.read_text(encoding="utf-8")
    exemple = re.search(r"(?m)^DATABASE_URL=(.+)$", gabarit)
    assert exemple, ".env.example ne déclare plus DATABASE_URL"
    pg = yaml.safe_load(COMPOSE_TXT)["services"]["postgres"]
    env = dict(e.split("=", 1) for e in pg["environment"])
    attendu = re.compile(
        rf"^postgresql\+psycopg://{env['POSTGRES_USER']}:<POSTGRES_PASSWORD>"
        rf"@postgres:5432/{env['POSTGRES_DB']}$"
    )
    assert attendu.match(exemple.group(1).strip()), (
        f"DATABASE_URL du gabarit ({exemple.group(1).strip()}) ne désigne pas le service "
        f"`postgres` de docker-compose.yml (utilisateur {env['POSTGRES_USER']}, base "
        f"{env['POSTGRES_DB']}, mot de passe POSTGRES_PASSWORD)"
    )
    assert "POSTGRES_PASSWORD" in _cles_du_gabarit(), (
        "le mot de passe de la base n'a pas sa ligne dans le gabarit : sans lui, "
        "l'image refuse d'initialiser la base"
    )


def test_les_reglages_de_role_ne_s_ecrivent_qu_une_fois():
    """`ORIGIN` et `COOKIE_SECURE` dépendent du rôle — et d'un seul module.

    Ces deux réglages étaient écrits **quatre fois** dans trois scripts
    (#1077) : `bascule.sh` pour promouvoir le peer puis pour se rétrograder,
    `health-watch.sh` au failover, `boot-role-guard.sh` à la promotion au
    démarrage. Le commentaire de ce dernier disait « identique à bascule.sh
    phase 5 et health-watch.sh failover » : la copie était **connue et
    documentée**, jamais supprimée — un commentaire qui décrit une copie note
    seulement qu'elle existe.

    Elle avait déjà coûté : le « gap .env du 15/07 » que ce même commentaire
    cite est le jour où une promotion hors bascule n'a pas appliqué ces `sed`,
    servant le public avec `ORIGIN` sur une IP locale.

    ⚠️ Ce qui rend la chose sérieuse, c'est l'asymétrie des deux gestes :
    l'actif **retire** la ligne `COOKIE_SECURE` (pour que le défaut sûr de
    `config.py` s'applique) quand le standby la **pose à false**. Un quatrième
    appelant qui recopierait le mauvais des deux servirait le public sans
    drapeau `Secure`, et rien ne le dirait.
    """
    module = "lib-env-role.sh"
    fautes = []
    for script in scripts_shell_versionnes():
        if script.name == module:
            continue
        for numero, ligne in enumerate(
            script.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
        ):
            nue = ligne.strip()
            if nue.startswith("#"):
                continue
            #  Une ÉCRITURE du réglage : un `sed` qui le remplace ou le
            #  supprime, un `echo` qui l'ajoute. Le lire (`grep '^ORIGIN='`)
            #  reste permis — un script a le droit de constater.
            if re.search(r"(sed|echo|printf).*\b(ORIGIN|COOKIE_SECURE)=", nue):
                fautes.append(f"{script.relative_to(RACINE)}:{numero} : {nue[:90]}")
    assert not fautes, (
        "`ORIGIN` ou `COOKIE_SECURE` écrit hors de scripts/lib/"
        + module
        + " :\n"
        + "\n".join(fautes)
        + '\n\nAppeler `env_role_appliquer "$REPO/.env" actif|standby [ip]`. Les deux '
        "gestes sont asymétriques — l'actif RETIRE la ligne, le standby la pose à "
        "false — et une copie qui prend le mauvais des deux sert le public sans "
        "drapeau Secure."
    )


def test_le_module_de_role_porte_son_autotest():
    """Le cas ZÉRO : un module sans self-test rendrait le test ci-dessus creux.

    Il suffirait d'appeler `env_role_appliquer` partout et de casser la
    transformation pour que tout reste vert : le contrôle ne regarde que les
    points d'écriture, pas ce qu'ils écrivent. Le self-test est l'autre moitié,
    et le job CI `test-scripts` l'exécute.
    """
    module = RACINE / "scripts" / "lib" / "lib-env-role.sh"
    assert module.exists(), "scripts/lib/lib-env-role.sh a disparu"
    contenu = module.read_text(encoding="utf-8")
    assert "--selftest" in contenu, "le module de rôle n'expose plus `--selftest`"
    ci = (RACINE / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "lib-env-role.sh" in ci and "--selftest" in ci, (
        "`lib-env-role.sh --selftest` n'est pas lancé par la CI : un contrôle "
        "écrit et jamais exécuté ne sert à rien"
    )


def test_aucun_script_ne_regenere_env_ni_caddyfile():
    """Le geste qui a produit l'incident : un script qui réécrit la configuration.

    Un installeur qui génère son `.env` et son `Caddyfile` fabrique une seconde
    vérité, qui dérive en silence — celle de `setup-rpi5.sh` posait des en-têtes
    de sécurité plus faibles que le Caddyfile versionné (`SAMEORIGIN` au lieu de
    `DENY`, ni HSTS, ni CSP, ni Permissions-Policy) et un Caddyfile que compose ne
    montait même pas.

    La référence unique est le dépôt : `.env.example` pour les secrets,
    `Caddyfile` à la racine pour le service.
    """
    fautes = []
    restants = dict(AJUSTEMENTS_DECLARES)
    for script in scripts_shell_versionnes():
        for numero, ligne in enumerate(
            script.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
        ):
            nue = ligne.strip()
            if nue.startswith("#"):
                continue
            #  Une REDIRECTION vers .env ou un Caddyfile — pas une simple lecture
            #  (`source .env`, `grep … .env`), qui reste légitime.
            if not re.search(r">\s*[\"']?\S*(\.env\b|Caddyfile)", nue):
                continue
            declare = next(
                (cle for cle in restants if cle[0] == script.name and cle[1] in nue), None
            )
            if declare:
                restants.pop(declare)
            else:
                fautes.append(f"{script.relative_to(RACINE)}:{numero} : {nue[:90]}")
    assert not fautes, (
        "un script versionné réécrit la configuration, au lieu de s'en remettre au "
        "dépôt :\n"
        + "\n".join(fautes)
        + "\n\nSi c'est un AJUSTEMENT de rôle et non une regénération, déclarez-le "
        "dans AJUSTEMENTS_DECLARES avec sa raison."
    )
    assert not restants, (
        f"AJUSTEMENTS_DECLARES retient {sorted(restants)}, qu'aucun script n'écrit "
        f"plus : une exception qui ne sert plus finit par couvrir autre chose"
    )
