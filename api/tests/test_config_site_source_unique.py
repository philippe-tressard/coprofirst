"""Le nom et l'adresse du site se lisent à UN endroit (18/09/2026, #779).

## Ce que ce contrôle protège

`config_site` lisait les clés `site_nom` / `site_url` depuis
`routers/tickets/commun.py` — chez un appelant, et dans le module d'un domaine
qui n'a rien à voir avec la configuration. Deux conséquences, toutes deux
observées :

- `main.py` l'importait **au milieu d'une fonction**, pour éviter le cycle que
  provoquerait un import de routeur depuis le démarrage ;
- **huit autres endroits** relisaient le couple eux-mêmes — `routers/auth.py`
  deux fois, `auth_mot_de_passe`, `documents`, `publications/courriels` deux
  fois, `health_monitor`, `annonces_hall` — et l'une de ces copies avait dérivé :
  elle rendait `""` là où l'originale rend `None`.

C'est `standards/02` §4 sexies : une règle rangée chez un appelant oblige le
suivant à un détour ou à une copie. Le corps vit désormais dans
`utils/config_site`, que personne n'a de raison d'éviter.

## 🔴 La portée est la NOTION, pas la table

Lire `ConfigSite` est banal : quinze modules le font pour les réglages SMTP,
WhatsApp ou LLM, et c'est leur droit. Ce qui s'écrit à un endroit est la lecture
du **couple** `site_nom` / `site_url` — le nom et l'adresse de la résidence, qui
alimentent chaque courriel et chaque document. Une portée qui viserait la table
crierait sur du légitime, et serait désarmée dans la semaine
(`standards/04` §40).

## 🔴 Lu en AST, et non ligne à ligne (#1273, 25/09/2026)

Le contrôle cherchait `ConfigSite` et les deux clés **sur une même ligne**. Le
formatage de l'API (#1261) a révélé une recopie qu'il ne voyait pas :
`utils/email/__init__.py` relisait le couple dans une compréhension écrite sur
six lignes — `select(ConfigSite)` sur l'une, les clés sur une autre. Il n'avait
jamais regardé que la forme du code, pas ce qu'il fait.

Une lecture est désormais une INSTRUCTION dont les expressions nomment
l'identifiant `ConfigSite` et portent les deux chaînes, où qu'elles tombent.
La prose sort d'elle-même : un commentaire n'existe pas dans l'AST, et une
docstring n'y est qu'une chaîne — elle ne nomme pas l'identifiant.
"""

from __future__ import annotations

import ast

from tests.aides_adresse import poser_adresse_du_site
from tests.aides_sources import module_app, modules_app

SOURCE = "utils/config_site.py"

#: Les deux clés qui, ENSEMBLE, désignent la lecture mutualisée.
COUPLE = ("site_nom", "site_url")


def _expressions_propres(instruction: ast.stmt) -> list[ast.AST]:
    """Les expressions d'une instruction, SANS les instructions qu'elle contient.

    Sans cette coupe, une fonction entière serait « une instruction » qui nomme
    `ConfigSite` quelque part et les deux clés ailleurs — deux lectures
    distinctes et légitimes y passeraient pour une recopie.
    """
    propres = []
    for _, valeur in ast.iter_fields(instruction):
        for noeud in valeur if isinstance(valeur, list) else [valeur]:
            if isinstance(noeud, ast.AST) and not isinstance(noeud, ast.stmt):
                propres.append(noeud)
    return propres


def lectures_du_couple(source: str) -> list[int]:
    """Les lignes où une instruction relit le couple elle-même. PURE."""
    trouvees = []
    for instruction in ast.walk(ast.parse(source)):
        if not isinstance(instruction, ast.stmt):
            continue
        noms, chaines = set(), set()
        for expression in _expressions_propres(instruction):
            for noeud in ast.walk(expression):
                if isinstance(noeud, ast.Name):
                    noms.add(noeud.id)
                elif isinstance(noeud, ast.Attribute):
                    noms.add(noeud.attr)
                elif isinstance(noeud, ast.Constant) and isinstance(noeud.value, str):
                    chaines.add(noeud.value)
        if "ConfigSite" in noms and all(cle in chaines for cle in COUPLE):
            trouvees.append(instruction.lineno)
    return sorted(trouvees)


def _lecteurs() -> dict[str, list[int]]:
    """Les modules qui lisent le couple eux-mêmes — hors source, hors prose."""
    trouves: dict[str, list[int]] = {}
    for module in modules_app():
        rel = module.rel
        if rel == SOURCE:
            continue
        lignes = lectures_du_couple(module.source)
        if lignes:
            trouves[rel] = lignes
    return trouves


#: La recopie que la lecture ligne à ligne a laissé passer, telle qu'elle était
#: écrite dans `utils/email/__init__.py` avant #1261.
_RECOPIE_SUR_SIX_LIGNES = """
lignes = {
    r.cle: r.valeur
    for r in session.exec(
        select(ConfigSite).where(
            ConfigSite.cle.in_(
                ("site_nom", "site_url", "email_footer", "reference_copro")
            )
        )
    ).all()
}
"""


def test_le_detecteur_voit_une_lecture_sur_plusieurs_lignes():
    """Cas zéro : la forme qui a échappé au contrôle ligne à ligne est refusée."""
    assert lectures_du_couple(_RECOPIE_SUR_SIX_LIGNES) == [2]
    assert lectures_du_couple(
        'x = session.exec(select(ConfigSite).where(ConfigSite.cle.in_(["site_nom", "site_url"])))'
    ) == [1]


def test_le_detecteur_ne_crie_pas_sur_ce_qui_n_est_pas_une_lecture():
    """La prose, une seule clé, deux instructions distinctes : rien à signaler."""
    prose = '''
def f():
    """Relit ConfigSite site_nom et site_url — ceci est une docstring."""
    # ConfigSite "site_nom" "site_url" dans un commentaire
    return 1
'''
    une_cle = 'x = session.get(ConfigSite, "site_nom")'
    deux_instructions = """
def f(session):
    a = session.get(ConfigSite, "smtp_host")
    b = {"site_nom": 1, "site_url": 2}
"""
    assert lectures_du_couple(prose) == []
    assert lectures_du_couple(une_cle) == []
    assert lectures_du_couple(deux_instructions) == []


def test_cas_zero_la_source_nomme_bien_les_deux_cles():
    """Sans quoi le motif ne reconnaîtrait plus rien, et ne refuserait plus rien."""
    #  Depuis #2058, `site_url` ne se lit plus en base (`test_base_site.py`) : la
    #  source ne nomme plus que `site_nom`, et le détecteur se prouve sur les
    #  extraits forgés ci-dessus.
    source = module_app(SOURCE).source
    assert "site_nom" in source, f"`{SOURCE}` ne nomme plus `site_nom`"
    assert len(modules_app()) > 50, "le parcours ne décrit plus `app/`"


def test_personne_ne_RECOPIE_la_lecture_du_couple():
    """🔴 Aucune exception, et c'est délibéré.

    Ce contrôle est posé APRÈS que le compte soit tombé à zéro — huit recopies
    converties dans le même lot. Il n'a donc rien à tolérer. Le jour où une
    exception paraîtra nécessaire, la vraie question sera : que manque-t-il à
    `config_site` ? Elle accepte déjà des clés SUPPLÉMENTAIRES, ce qui a suffi
    aux deux lecteurs qui demandaient le couple ET d'autres clés.
    """
    fautifs = _lecteurs()
    assert not fautifs, (
        f"Ces modules relisent `site_nom` / `site_url` eux-mêmes : {fautifs}. "
        "Employer `config_site(session)` de `app.utils.config_site` — et "
        '`config_site(session, "autre_cle")` si d\'autres clés sont nécessaires.'
    )


def test_la_lecture_partagee_rend_bien_les_deux_cles(session, monkeypatch):
    """Le fait, pas la forme : la fonction lit ce qu'elle promet.

    Un contrôle qui n'interdirait que la recopie resterait vert si la source
    cessait de rendre l'une des deux clés — et chaque appelant retomberait alors
    sur le repli de `nom_site` / `base_site`, sans que rien ne le dise.
    """
    from app.models.core import ConfigSite
    from app.utils.config_site import config_site, contexte_site

    session.add(ConfigSite(cle="site_nom", valeur="Résidence 5 Hostachy"))
    session.add(ConfigSite(cle="autre", valeur="ignorée"))
    session.commit()

    cfg = config_site(session)
    assert cfg == {"site_nom": "Résidence 5 Hostachy"}, cfg  # l'adresse : le contexte (#2058)

    #  Les clés supplémentaires arrivent EN PLUS, jamais à la place.
    elargi = config_site(session, "autre")
    assert elargi["autre"] == "ignorée"
    assert elargi["site_nom"] == "Résidence 5 Hostachy"

    poser_adresse_du_site(monkeypatch, "https://5hostachy.fr")
    ctx = contexte_site(cfg)
    assert ctx["residence"]["nom"] == "Résidence 5 Hostachy"
    assert ctx["app"]["url"].startswith("https://5hostachy.fr")
