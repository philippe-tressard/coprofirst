"""Hygiène du dépôt public — ce que l'audit du 02/10/2026 a trouvé, et qui revient seul.

Trois écarts de la même famille : un fichier que tout le monde lit et que rien ne
vérifie (#1582, #1601, #1607).

- `SECURITY.md` annonçait « 1.x suivie » pour un produit en 2.91 : la page que
  lit d'abord qui veut signaler une faille disait une version que personne ne
  sert. Il ne cite plus de version ; s'il en recite une, ce sera la majeure
  servie (`front/package.json`).
- `front/svelte_errors.txt`, un vidage d'erreurs en UTF-16, était versionné
  depuis le premier commit public. Les sorties d'outils se rangent hors du
  dépôt (`.gitignore`), jamais à la racine de `front/`.
- Les `.py` de `scripts/poste/` s'appellent par `python …` (ci.yml) : deux
  étaient en 100755, deux en 100644. Un mode se lit dans l'index, pas sur le
  poste — Windows avale `chmod` (`standards/08` §3).
- Un script exécutable sans `set -u` tait une variable vide : il continue avec
  un chemin tronqué. Les exceptions sont NOMMÉES, et la liste ne fait que
  baisser ; une exception qui ne sert plus fait échouer le test.
"""

import json
import re
import subprocess

from tests.conftest import racine_depot

RACINE = racine_depot()

#: Exécutables sans `set -u`, chacun avec sa raison. Ne fait que baisser.
SANS_SET_U = {
    "boot-role-guard.sh": "relais pur : une seule ligne, `exec` du vrai script",
    "api/start.sh": "démarrage du conteneur de production — à durcir dans un lot "
    "qui le redémarre en conditions réelles, pas en passant",
    "scripts/exploitation/MaJ-Hostachy.sh": "reprise en main manuelle — à durcir "
    "avec une répétition sur le standby",
    ".claude/cloud/garde-git.sh": "hook de session cloud — lit des variables "
    "d'environnement facultatives",
}


def _index(*motifs: str) -> list[tuple[str, str]]:
    """(mode, chemin) des fichiers SUIVIS — l'index, pas le disque du poste."""
    sortie = subprocess.run(
        ["git", "ls-files", "-s", "--", *motifs],
        cwd=RACINE,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [(ligne.split()[0], ligne.split("\t")[1]) for ligne in sortie.splitlines()]


def test_security_md_ne_cite_que_la_majeure_servie():
    version = json.loads((RACINE / "front" / "package.json").read_text(encoding="utf-8"))
    majeure = version["version"].split(".")[0]
    assert majeure.isdigit(), "version de front/package.json illisible — cas zéro"
    texte = (RACINE / "SECURITY.md").read_text(encoding="utf-8")
    citees = set(re.findall(r"\b(\d+)\.x\b", texte))
    assert citees <= {majeure}, (
        f"SECURITY.md cite la ou les versions {sorted(citees)}.x, le produit est en "
        f"{majeure}.x — ne pas recopier de version, ou citer celle qui est servie"
    )


def test_aucune_sortie_d_outil_versionnee_a_la_racine_du_front():
    fichiers = [c for _, c in _index("front/*.txt", "front/*.log") if c.count("/") == 1]
    assert not fichiers, (
        f"Sortie d'outil versionnée à la racine de front/ : {fichiers} — la retirer "
        "et l'ajouter au .gitignore"
    )


def test_les_py_de_poste_ne_sont_pas_executables():
    fichiers = _index("scripts/poste/*.py")
    assert len(fichiers) >= 3, "aucun .py de poste lu — le motif ne voit plus rien"
    executables = [c for mode, c in fichiers if mode != "100644"]
    assert not executables, (
        f"{executables} : un .py de poste s'appelle par `python …` — "
        "`git update-index --chmod=-x <fichier>`"
    )


def test_tout_executable_porte_set_u_ou_se_declare():
    executables = [c for mode, c in _index("*.sh") if mode == "100755"]
    assert len(executables) >= 10, "trop peu d'exécutables lus — cas zéro"
    sans = {
        c
        for c in executables
        if not re.search(r"^\s*set -[a-z]*u", (RACINE / c).read_text(encoding="utf-8"), re.M)
    }
    assert sans <= SANS_SET_U.keys(), (
        f"Exécutable sans `set -u` : {sorted(sans - SANS_SET_U.keys())} — "
        "ajouter `set -uo pipefail`, ou le déclarer dans SANS_SET_U avec sa raison"
    )
    perimees = SANS_SET_U.keys() - sans
    assert not perimees, f"Exception qui ne sert plus, à retirer de SANS_SET_U : {perimees}"


def _ignore(chemin: str) -> bool:
    """`.gitignore` écarte-t-il ce nom ? `--no-index` : la règle, pas l'état du suivi."""
    r = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", chemin],
        cwd=RACINE,
        capture_output=True,
    )
    assert r.returncode in (0, 1), f"git check-ignore a échoué : {r.stderr!r}"
    return r.returncode == 0


def test_une_copie_du_env_ne_se_versionne_pas_mais_le_gabarit_si():
    """Les copies manuelles du `.env` (`.env.avant-1109`…) portent SECRET_KEY et SMTP.

    Elles traînaient `??` dans `git status` (#1609) : un `git add -A` les publiait,
    dans un dépôt PUBLIC. `.env.*` les écarte, `.env.example` — le gabarit
    d'installation, lu par `test_env_exemple_coherent` — reste suivi.
    """
    #  Cas zéro : la vérification sait dire « ignoré » (règle ancienne) et « suivi ».
    assert _ignore(".env"), "cas zéro : `.env` doit être ignoré — la sonde ne mesure rien"
    assert not _ignore("README.md"), "cas zéro : un fichier ordinaire n'est pas ignoré"
    for copie in (".env.avant-1109", ".env.avant-120min-20260918", ".env.prod", ".env.bak"):
        assert _ignore(copie), f"{copie} n'est pas ignoré — une copie du .env se publierait"
    assert not _ignore(".env.example"), (
        "`.env.example` est ignoré : le gabarit d'installation ne serait plus versionné"
    )
    assert ".env.example" in _index(".env.example")[0][1], "`.env.example` n'est plus suivi"


#: Fournisseurs de messagerie publics : une adresse de test sur l'un d'eux peut
#: désigner une boîte réelle (#1581). `exemple.test` / `example.org` existent pour ça.
FOURNISSEURS_REELS = (
    "gmail",
    "icloud",
    "yahoo",
    "hotmail",
    "outlook",
    "live",
    "orange",
    "wanadoo",
    "free",
    "sfr",
    "laposte",
    "protonmail",
    "aol",
    "msn",
)
_BOITE_REELLE = re.compile(
    r"@(?:" + "|".join(FOURNISSEURS_REELS) + r")\.(?:com|fr|net|org)\b", re.I
)
CE_FICHIER = "api/tests/test_hygiene_depot.py"


def _boites_reelles(texte: str) -> list[str]:
    return [m.group(0) for m in _BOITE_REELLE.finditer(texte)]


def test_la_sonde_de_boites_reelles_distingue_le_reel_du_fictif():
    assert _boites_reelles("jean@gmail.com et p@iCloud.com") == ["@gmail.com", "@iCloud.com"]
    assert _boites_reelles("jean@exemple.test, a@example.org, b@copro-orange.fr") == []
    assert _boites_reelles("") == []  # cas zéro


def test_aucune_adresse_de_test_sur_un_fournisseur_reel():
    fichiers = [
        chemin
        for _, chemin in _index("api/tests", "front/e2e")
        if chemin.endswith((".py", ".ts", ".mjs", ".json", ".html", ".txt", ".eml"))
        and chemin != CE_FICHIER
    ]
    #  Cas zéro : un balayage qui ne lit aucun fichier ne prouve rien.
    assert len(fichiers) > 100, f"{len(fichiers)} fichier(s) lu(s) — la liste ne correspond plus"
    trouvees = {}
    for chemin in fichiers:
        contenu = (RACINE / chemin).read_text(encoding="utf-8", errors="replace")
        if hits := _boites_reelles(contenu):
            trouvees[chemin] = sorted(set(hits))
    assert not trouvees, (
        f"adresse(s) sur un fournisseur réel dans les tests : {trouvees}. "
        "Une boîte peut exister derrière : écrire `…@exemple.test`."
    )


#: Exception assumée (#1581, arbitrage de Philippe du 06/10/2026, `security-audit` §8) :
#: l'identifiant SSH d'exploitation et les IP du LAN restent dans le dépôt PUBLIC — LAN
#: non routable, accès par clé. Elle n'est pas un oubli : elle est CIRCONSCRITE.
_IDENTIFIANTS_EXPLOITATION = re.compile(r"ptressard|192\.168\.1\.22[23]")
#: Les seuls endroits où ils vivent : l'exploitation, jamais l'application.
ZONES_EXPLOITATION = ("scripts/", "infra/", "docs/", ".claude/")
FICHIERS_RACINE_EXPLOITATION = ("CLAUDE.md", "boot-role-guard.sh")
#: Nombre de fichiers suivis qui les portent. Échoue dans les deux sens : un de plus
#: est une propagation à relire, un de moins est une valeur à baisser.
#: 42 depuis DI-7b (#1781) : `infra/postgresql/pg_hba.conf` admet la réplication
#: depuis l'IP de l'autre nœud ; `reconstruire-replique.sh` et `lib-promotion.sh`
#: lisent le rôle de la base du pair par SSH.
#: 45 avec DI-7c (#1782), puis 42 : les trois outils lancés à la main disaient
#: « en ptressard », ils disent « en root (sudo) » (v2.129.1). `lib-env-base.sh`,
#: qui réécrit le `.env` du pair par SSH, reste compté.
#: 43 avec #1917 : `scripts/installation/durcir-noeud.sh` nomme le compte dont il
#: compte les clés autorisées avant de couper le mot de passe SSH.
#: 42 avec #2004 : les scripts de la bascule des données, devenus sans objet, sont retirés.
#: 45 avec l'audit de sécurité nocturne (30/10/2026) : `lib-audit-comptes.sh` déclare
#: le compte d'exploitation admis avec un shell et dans les groupes docker/sudo ;
#: les autotests de `lib-audit-persistance.sh` et `lib-audit-conteneurs.sh` le citent.
FICHIERS_EXPLOITATION_ATTENDUS = 45


def _fichiers_avec_identifiants_exploitation() -> list[str]:
    chemins = []
    for _, chemin in _index():
        if chemin == CE_FICHIER:
            continue
        contenu = (RACINE / chemin).read_text(encoding="utf-8", errors="replace")
        if _IDENTIFIANTS_EXPLOITATION.search(contenu):
            chemins.append(chemin)
    return chemins


def test_la_sonde_des_identifiants_d_exploitation_distingue_le_reel_du_neutre():
    assert _IDENTIFIANTS_EXPLOITATION.search("ssh ptressard@192.168.1.222")
    assert _IDENTIFIANTS_EXPLOITATION.search("ip 192.168.1.223")
    assert not _IDENTIFIANTS_EXPLOITATION.search("philippe-tressard, 192.168.1.50")
    assert not _IDENTIFIANTS_EXPLOITATION.search("")  # cas zéro


def test_identifiant_ssh_et_ip_du_lan_restent_dans_l_exploitation():
    trouves = _fichiers_avec_identifiants_exploitation()
    #  Cas zéro : un balayage qui ne trouve rien ne prouve pas l'absence.
    assert trouves, "cas zéro : aucun fichier d'exploitation ne porte l'identifiant — sonde morte"
    hors = [
        c
        for c in trouves
        if not c.startswith(ZONES_EXPLOITATION) and c not in FICHIERS_RACINE_EXPLOITATION
    ]
    assert not hors, (
        f"L'identifiant SSH ou une IP du LAN sort de l'exploitation : {hors}. "
        "L'exception de #1581 ne couvre que scripts/, infra/, docs/, .claude/ "
        "(`security-audit` §8) — pas l'application."
    )
    assert len(trouves) == FICHIERS_EXPLOITATION_ATTENDUS, (
        f"{len(trouves)} fichier(s) portent l'identifiant (attendu "
        f"{FICHIERS_EXPLOITATION_ATTENDUS}) : relire l'ajout, ou baisser la valeur "
        "si un fichier a été nettoyé."
    )


def test_l_exception_est_declaree_dans_la_skill_de_securite():
    skill = (RACINE / ".claude" / "skills" / "security-audit" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "Exception assumée : l'identifiant SSH d'exploitation" in skill, (
        "l'exception de #1581 n'est plus déclarée dans security-audit §8 — "
        "une exception non écrite est un oubli qui ressemble à une décision"
    )
