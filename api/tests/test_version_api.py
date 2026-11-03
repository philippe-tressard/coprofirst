"""Garde-fou : la version publiée par `/health` est une constante unique, et elle
ne divulgue PAS la version de l'application.

POURQUOI. `main.py` portait `"0.2.0"` **en dur deux fois** — dans la construction de
`FastAPI(version=...)` et dans la réponse de `/health` — donc rien ne garantissait
que les deux restent d'accord. C'est le défaut de factorisation relevé le 03/08/2026
par la skill `mep-precheck`, mis de côté à l'époque parce qu'il fallait décider
*quoi* publier avant de décider *où* l'écrire, et corrigé le 06/08/2026.

Deux tests, et le second est le plus important.

Le premier interdit la **duplication** de revenir : aucun littéral de version dans
`main.py`. Depuis #2456, c'est la version du CONTRAT de l'API (`app/contrat`), lue
dans `app/contrat/reference.json` et calculée par son générateur — jamais écrite à
la main ; `test_contrat_api.py` en tient les règles.

Le second verrouille une **décision de sécurité**, pas un détail de style. `/health`
est public et non authentifié. Faire pointer sa version vers `front/package.json`
donnerait un post-check P3 en une ligne — c'est tentant, et c'est précisément le
piège : cela divulguerait publiquement la version déployée, donc la liste des
vulnérabilités connues applicables, sans qu'aucun besoin ne l'impose. Le post-check
lit la version servie dans le bundle du front, ce qui n'expose rien de plus.

Sans ce test, la « correction » consistant à publier la vraie version paraîtrait un
progrès à qui n'a pas l'historique — et personne ne verrait passer la régression.
"""

import json
import pathlib
import re

_API_DIR = pathlib.Path(__file__).resolve().parents[1]
_RACINE = _API_DIR.parent
_MAIN = _API_DIR / "app" / "main.py"
_REFERENCE = _API_DIR / "app" / "contrat" / "reference.json"
_PACKAGE_JSON = _RACINE / "front" / "package.json"

#  Un numéro de version sémantique entre guillemets, tel qu'on l'écrirait par
#  distraction dans un littéral. On ne cherche pas les versions de dépendances :
#  la recherche est bornée à `main.py`.
_LITTERAL_VERSION = re.compile(r"""["'](\d+\.\d+\.\d+)["']""")


def _version_api() -> str:
    """Lit la version du contrat dans sa référence, sans importer l'application."""
    return json.loads(_REFERENCE.read_text(encoding="utf-8"))["version"]


def test_aucun_litteral_de_version_dans_main():
    """La version n'est pas écrite dans `main.py` : elle y vient de `app/contrat`.

    Deux littéraux identiques ne se contredisent pas le jour où on les écrit — ils
    se contredisent le jour où l'un des deux est modifié.
    """
    source = _MAIN.read_text(encoding="utf-8")
    trouves = [
        (n, ligne.strip())
        for n, ligne in enumerate(source.splitlines(), start=1)
        if _LITTERAL_VERSION.search(ligne) and not ligne.lstrip().startswith("#")
    ]
    assert not trouves, (
        "La version de l'API vient de `contrat.VERSION_CONTRAT`, jamais d'un littéral. "
        f"Littéraux trouvés dans main.py : {trouves}"
    )
    assert "version=contrat.VERSION_CONTRAT" in source


def test_health_ne_divulgue_pas_la_version_applicative():
    """`/health` est public : sa version ne doit pas être celle de l'application.

    Ce n'est pas une préférence de forme. Publier la version déployée sur un
    endpoint non authentifié revient à publier la liste des vulnérabilités connues
    qui s'y appliquent. Si le besoin d'un P3 « en une ligne » revient sur la table,
    c'est une décision à prendre explicitement — et ce test est là pour qu'elle
    **soit** prise, au lieu d'être introduite comme une amélioration évidente.
    """
    version_app = json.loads(_PACKAGE_JSON.read_text(encoding="utf-8"))["version"]
    assert _version_api() != version_app, (
        f"La version du contrat ({_version_api()}) est devenue égale à celle de "
        f"l'application ({version_app}) : `/health`, qui est PUBLIC et non "
        "authentifié, divulgue désormais la version déployée. Le post-check P3 lit "
        "la version dans le bundle du front, il n'a pas besoin de celle-ci."
    )


def test_la_version_publiee_est_bien_la_constante():
    """La réponse de `/health` réutilise `contrat.VERSION_CONTRAT`, sans la réécrire.

    Vérifié par le source plutôt qu'en appelant l'endpoint : le contrat testé ici
    est « il n'y a qu'une source de vérité », pas « le serveur démarre » — ce
    dernier est déjà couvert par `test_demarrage.py`.
    """
    source = _MAIN.read_text(encoding="utf-8")
    assert len(re.findall(r'"version":\s*contrat\.VERSION_CONTRAT', source)) == 2, (
        "La réponse de `/health` doit réutiliser `contrat.VERSION_CONTRAT` et non un littéral."
    )
