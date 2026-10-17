"""Garde-fou : la connexion SMTP se construit à un seul endroit (08/08/2026).

Les dix-sept lignes qui composent `ConnectionConfig` depuis la configuration en
base — avec repli sur le `.env` champ par champ — étaient écrites **trois fois** :
deux dans `app/utils/email.py` (envoi simple, envoi groupé) et une dans
`app/routers/config.py`, pour le bouton « tester la configuration SMTP ».

C'est la duplication la plus coûteuse qui soit sur ce chemin. Un bouton de test
n'a d'intérêt que s'il emprunte **exactement** la même construction que les
envois réels : trois écritures, c'est trois occasions de tester autre chose que
ce qui part vraiment, et de conclure « SMTP OK » pendant que les e-mails
échouent. Personne ne l'aurait vu — un e-mail qui ne part pas ne fait pas de
bruit.
"""

import ast
import pathlib

from tests.aides_sources import modules_app

_APP = pathlib.Path(__file__).resolve().parents[1] / "app"

#: Le seul module autorisé à instancier la connexion.
_MODULE_AUTORISE = "utils/smtp.py"


def test_la_connexion_smtp_n_est_construite_qu_a_un_endroit():
    porteurs = {
        module.rel
        for module in modules_app()
        for n in ast.walk(module.arbre)
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "ConnectionConfig"
    }
    assert porteurs == {_MODULE_AUTORISE}, (
        "`ConnectionConfig(...)` ne doit être construit que dans "
        f"`app/{_MODULE_AUTORISE}` (`connexion_smtp`). Modules fautifs : "
        f"{sorted(porteurs - {_MODULE_AUTORISE})}. Un envoi qui compose sa propre "
        "connexion peut viser un autre serveur que celui que le bouton de test "
        "vérifie."
    )


def test_les_envois_passent_par_le_helper_partage():
    """Cas zéro : si plus personne n'appelle `connexion_smtp`, le test ci-dessus
    resterait vert en ne surveillant rien — un ensemble vide est égal à lui-même
    seulement quand le helper existe et sert (`standards/04` §2)."""
    appelants = {
        module.rel
        for module in modules_app()
        for n in ast.walk(module.arbre)
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "connexion_smtp"
    }
    assert len(appelants) >= 2, (
        f"`connexion_smtp` n'est appelé que depuis {sorted(appelants)} — il en "
        "desservait 2 modules (envois et bouton de test) au moment du "
        "regroupement. Un chemin d'envoi a-t-il repris une construction à la main ?"
    )


def test_la_connexion_d_une_copropriete_ne_lit_que_sa_base():
    """Plus de repli sur le `.env` (#2058, 17/10/2026) : chaque clé se lit en base.

    Le repli champ par champ faisait d'une configuration à moitié en base et à moitié
    dans `MAIL_*` la règle, sans que l'écran le montre. L'amorce (`smtp.amorcer`) a
    recopié dans chaque base ce qu'il produisait ; `connexion_smtp` ne lit plus que
    la base — `tests/test_reglages_un_seul_niveau.py` en éprouve le comportement.
    """
    source = (_APP / "utils" / "smtp.py").read_text(encoding="utf-8")
    arbre = ast.parse(source)
    fonction = next(
        n for n in ast.walk(arbre) if isinstance(n, ast.FunctionDef) and n.name == "connexion_smtp"
    )
    corps = ast.unparse(fonction)
    for cle in (
        "smtp_server",
        "smtp_port",
        "smtp_from",
        "smtp_from_name",
        "smtp_username",
        "smtp_password",
        "smtp_starttls",
        "smtp_ssl_tls",
    ):
        assert cle in corps, f"`{cle}` n'est plus lu par connexion_smtp"
    assert "settings" not in corps, "connexion_smtp relit le .env : deux sources (#2058)"
    #  Une case décochée vaut « 0 » : le booléen se lit par égalité à « 1 ».
    for booleen in ("smtp_starttls", "smtp_ssl_tls"):
        assert f"smtp_cfg.get('{booleen}') == '1'" in corps, booleen
