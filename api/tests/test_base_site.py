"""L'adresse du site est normalisée en UN endroit, et nulle part ailleurs.

## L'incident (11/09/2026, signalé à l'écran)

Un e-mail de ticket adressé au syndic portait le lien
`https://5hostachy.fr//tickets/34` — **double barre, 404**. La valeur en base
valait `https://5hostachy.fr/`, et tous les modèles écrivent
`{{ app.url }}/tickets/{{ ticket.id }}`.

## Pourquoi ce test, et pas juste un `rstrip` de plus

Le défaut n'était pas dans le modèle d'e-mail : `site_url` était lu à une
vingtaine d'endroits dans l'API, dont **onze** ne retiraient pas la barre finale.
Les autres le faisaient chacun dans leur coin, par un `rstrip("/")` recopié — la
forme canonique de la duplication. Corriger le chemin signalé aurait laissé les
dix autres, et le défaut serait revenu par celui qu'on n'a pas relu.

Ce test refusait donc qu'une douzième copie apparaisse : toute lecture de
`site_url` destinée à fabriquer une URL passait par `base_site`.

## Depuis le 17/10/2026 (#2058) : `site_url` ne se lit plus en base

L'adresse du site doublait `ORIGIN`. Arbitré (option A) : elle est DÉRIVÉE du
contexte — `liens.adresse_du_site()`, l'`ORIGIN` d'une installation propre, ou
l'adresse de la copropriété dans une installation commune. Le contrôle refuse
désormais TOUTE lecture de la clé en base, normalisée ou non ; `base_site` reste
la normalisation unique, que `adresse_du_site` emploie.

⚠️ Il ne regarde pas `rstrip` — un test qui cherche le REMÈDE passe à côté de la
douzième copie qui l'écrit autrement (`.strip('/')`, une f-string, un `removesuffix`).
Il regarde la LECTURE de la clé, qui est le geste commun à toutes les formes.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from app import contexte
from app.utils.liens import DEFAUT_SITE, adresse_du_site, base_site
from tests.aides_sources import modules_app

RACINE = Path(__file__).resolve().parents[1] / "app"

#: Les fichiers autorisés à lire `site_url` en base.
#:
#: Chacun a son motif, et un motif qui cesse d'être vrai fait échouer le test :
#: une exception reconduite « au cas où » protège un fichier qui n'en a plus
#: besoin et masque la prochaine vraie copie.
EXCEPTIONS: dict[str, str] = {
    #  🔴 VIDE, et c'est le but : `adresse_du_site` est le seul chemin. Le motif
    #  ci-dessous ne relève que les lectures de VALEUR, jamais les ensembles de
    #  clés à charger — il n'y avait donc pas de cas légitime à excuser.
    #  Si l'un apparaît, il s'écrit ici AVEC son motif : une exception non écrite
    #  n'est pas une exception, c'est un oubli qui ressemble à une décision.
    "demarrage.py": "le CONSTAT d'écart au démarrage (#2058) : l'ancienne valeur se compare "
    "à l'adresse servie et se journalise, elle ne fait jamais un lien",
}

#: Une lecture de VALEUR — `get("site_url")` ou `cfg["site_url"]`. Un ensemble de
#: clés à charger (`{"site_nom", "site_url"}`) n'en est pas une : c'est la requête
#: qui rapporte la ligne, et la valeur sera lue ailleurs. Viser la notion, pas la
#: chaîne (`standards/04` §40).
#: 🔴 DEUX formes de lecture, parce qu'une 23ᵉ copie s'est cachée derrière la
#: seconde : `session.get(ConfigSite, "site_url")` lit la même valeur que
#: `cfg.get("site_url")`, et `utils/reponses.py` y écrivait son propre `rstrip`.
#: Un contrôle qui ne connaît qu'une écriture de la notion laisse passer l'autre
#: (`standards/04` §40 — viser la NOTION, pas la forme déjà rencontrée).
#: ⚠️ Et quel que soit le nom de la session : `session\.get` laissait passer
#: `s.get(ConfigSite, "site_url")` — trouvé par l'extrait forgé du cas zéro (#1496).
LECTURE = re.compile(
    r"""(?:\.get\(|\[)\s*["']site_url["']|\.get\(\s*ConfigSite\s*,\s*["']site_url["']"""
)


def _portees(src: str):
    """Chaque fonction du module, avec son texte — la lecture et sa normalisation
    n'étant pas forcément sur la même LIGNE (`utils/reponses.py` lit la ligne de
    configuration puis appelle `base_site` deux lignes plus bas). Le module
    lui-même compte comme une portée, pour le code hors fonction."""
    arbre = ast.parse(src)
    lignes = src.splitlines()
    for n in ast.walk(arbre):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield n.name, ("\n").join(lignes[n.lineno - 1 : n.end_lineno]), n.lineno


def _lectures(sources) -> tuple[list[str], list[str]]:
    """Les lectures de `site_url` dans `sources` (`(rel, texte)`), en deux listes :
    celles qui ne passent pas par `base_site` (fautives), et toutes celles vues."""
    fautifs, vues = [], []
    for rel, src in sources:
        if rel in EXCEPTIONS:
            continue
        #  Les commentaires ne sont pas du code : ce fichier-ci en parle
        #  abondamment, et un contrôle qui lit son propre récit se déclenche sur
        #  lui-même (`standards/04` §39).
        for nom, corps, debut in _portees(src):
            code = ("\n").join(
                ligne for ligne in corps.splitlines() if not ligne.lstrip().startswith("#")
            )
            if not LECTURE.search(code):
                continue
            #  Une clause SQL qui SÉLECTIONNE la ligne de configuration n'est pas
            #  une lecture de valeur : c'est la requête qui la rapporte.
            code_utile = ("\n").join(
                ligne
                for ligne in code.splitlines()
                if "cle.in_" not in ligne and "ConfigSite.cle" not in ligne
            )
            if not LECTURE.search(code_utile):
                continue
            vues.append(rel)
            fautifs.append(f"{rel}:{debut}  fonction `{nom}`")
    return fautifs, vues


def test_site_url_ne_se_lit_plus_en_base():
    fautifs, _vues = _lectures((m.rel, m.source) for m in modules_app())
    assert not fautifs, (
        "site_url lu en base (#2058) — l'adresse du site est DÉRIVÉE : "
        "`liens.adresse_du_site()` :\n  " + ("\n  ").join(fautifs)
    )


def test_le_controle_VOIT_les_lectures():
    """Cas zéro (#1496) : sans lui, un `LECTURE` qui ne reconnaîtrait plus rien
    rendrait le contrôle ci-dessus vert sur tout `app/`. Le code n'a plus aucune
    lecture (#2058) : chacune des trois formes, sur un extrait FORGÉ, est refusée —
    même normalisée par `base_site`.
    """
    forges = [
        ("forge_a.py", 'def f(cfg):\n    return cfg.get("site_url").rstrip("/")\n'),
        ("forge_b.py", 'def f(s):\n    return s.get(ConfigSite, "site_url").valeur\n'),
        ("forge_c.py", "def f(s):\n    return session.get(ConfigSite, 'site_url').valeur\n"),
        ("forge_d.py", 'def f(cfg):\n    return base_site(cfg.get("site_url"))\n'),
    ]
    fautifs, _vues = _lectures(forges)
    assert [f.split(":")[0] for f in fautifs] == [r for r, _ in forges], (
        f"lectures forgées non refusées — seules celles-ci l'ont été : {fautifs}"
    )


def test_les_exceptions_declarees_servent_TOUTES():
    """Une exception qui ne sert plus se retire — sinon elle masque la suivante."""
    inutiles = []
    for rel, motif in EXCEPTIONS.items():
        f = RACINE / rel
        if not f.exists():
            inutiles.append(f"{rel} — le fichier a disparu ({motif})")
            continue
        if not LECTURE.search(f.read_text(encoding="utf-8")):
            inutiles.append(f"{rel} — ne lit plus site_url ({motif})")
    assert not inutiles, "Exceptions périmées :\n  " + "\n  ".join(inutiles)


@pytest.mark.parametrize(
    "valeur, attendu",
    [
        ("https://5hostachy.fr/", "https://5hostachy.fr"),
        ("https://5hostachy.fr", "https://5hostachy.fr"),
        ("https://5hostachy.fr///", "https://5hostachy.fr"),
        ("  https://5hostachy.fr/  ", "https://5hostachy.fr"),
        #  Un sous-chemin est légitime (le produit peut vivre sous /copro) : on
        #  n'enlève que la barre FINALE, jamais un segment.
        ("https://exemple.fr/copro/", "https://exemple.fr/copro"),
    ],
)
def test_la_barre_finale_disparait_sans_toucher_au_reste(valeur, attendu):
    assert base_site(valeur) == attendu


@pytest.mark.parametrize("vide", [None, "", "   ", "/", "///"])
def test_une_valeur_vide_rend_le_DEFAUT_jamais_une_chaine_vide(vide):
    """⚠️ Une chaîne vide produirait `"/tickets/34"` — un lien sans domaine, qui
    part quand même dans l'e-mail et n'ouvre rien. Une adresse manifestement
    fausse se voit ; un lien muet se clique."""
    assert base_site(vide) == DEFAUT_SITE


def test_le_lien_complet_ne_porte_JAMAIS_de_double_barre():
    """Le fait signalé, reproduit : c'est cette chaîne-là qui rendait 404."""
    lien = f"{base_site('https://5hostachy.fr/')}/tickets/34"
    assert lien == "https://5hostachy.fr/tickets/34"
    assert "//tickets" not in lien


def test_la_normalisation_est_branchee_a_l_ENREGISTREMENT():
    """Normaliser à la lecture suffit à réparer les liens, mais laisse la donnée
    sale en base — et le prochain lecteur qui l'oubliera repartira de là."""
    src = (RACINE / "routers" / "config.py").read_text(encoding="utf-8")
    arbre = ast.parse(src)
    noms = {
        n.targets[0].id
        for n in ast.walk(arbre)
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
    }
    assert "_NORMALISEURS" in noms
    assert "_NORMALISEURS[cle](valeur)" in src, "la table est déclarée mais jamais appliquée"


def test_l_adresse_est_celle_du_contexte_normalisee():
    """L'adresse vient de la copropriété servie — et la barre finale ne repasse pas."""
    from dataclasses import replace

    base = contexte.de_la_configuration()
    with contexte.dans(replace(base, adresse="https://residence-chenes.example/")):
        assert adresse_du_site() == "https://residence-chenes.example"
    with contexte.dans(replace(base, adresse="")):
        assert adresse_du_site() == DEFAUT_SITE


def test_l_adresse_se_lit_partout_par_adresse_du_site():
    """Témoin : la notion a un lecteur, et il sert — sans quoi « aucune lecture en
    base » serait vrai d'un code qui n'écrirait plus aucun lien."""
    appelants = {m.rel for m in modules_app() if "adresse_du_site()" in m.source}
    assert len(appelants) >= 15, f"adresse_du_site n'est appelée que par {sorted(appelants)}"


def test_l_ecran_lit_l_adresse_derivee_et_ne_peut_pas_l_ecrire(session, monkeypatch):
    """`GET /config` publie l'adresse du contexte ; `PUT /config` refuse de la saisir."""
    from fastapi import HTTPException

    from app.models.core import ConfigSite
    from app.routers import config as routeur
    from tests.aides_adresse import poser_adresse_du_site

    poser_adresse_du_site(monkeypatch, "https://residence.exemple/")
    #  Une valeur restée en base d'avant #2058 ne compte plus.
    session.add(ConfigSite(cle="site_url", valeur="https://ancienne.exemple"))
    session.commit()
    assert routeur.get_config(session)["site_url"] == "https://residence.exemple"
    with pytest.raises(HTTPException) as refus:
        routeur.save_config({"site_url": "https://ailleurs.exemple"}, user=None, session=session)
    assert refus.value.status_code == 422


@pytest.mark.parametrize(
    "origine",
    ["http://192.168.1.223", "http://localhost", "http://api:8000", "http://[::1]", ""],
)
def test_l_origin_d_un_standby_ne_fait_jamais_un_lien(monkeypatch, origine):
    """Condition de l'arbitrage (17/10/2026) : sur le standby, `ORIGIN` est l'IP locale
    du nœud — elle ne doit jamais partir dans un courriel. Le défaut la remplace."""
    from tests.aides_adresse import poser_adresse_du_site

    poser_adresse_du_site(monkeypatch, origine)
    assert adresse_du_site() == DEFAUT_SITE


def test_un_ecart_avec_l_ancienne_valeur_se_dit_au_demarrage(session, monkeypatch, caplog):
    """La base garde une autre `site_url` : un WARNING (jamais ERROR, point 6 du
    pré-check) ; la même valeur, à la barre près, ne dit rien (cas zéro)."""
    import logging

    from sqlmodel import SQLModel

    from app import demarrage
    from app.database import engine
    from app.models.core import ConfigSite
    from tests.aides_adresse import poser_adresse_du_site

    SQLModel.metadata.create_all(engine)
    poser_adresse_du_site(monkeypatch, "https://5hostachy.fr")
    with contexte.nouvelle_session() as s:
        ligne = s.get(ConfigSite, "site_url") or ConfigSite(cle="site_url", valeur="")
        ligne.valeur = "https://5hostachy.fr/"
        s.add(ligne)
        s.commit()
        assert demarrage.ecart_d_adresse() is None
        ligne.valeur = "https://ancien.exemple"
        s.add(ligne)
        s.commit()
    assert demarrage.ecart_d_adresse() == "https://ancien.exemple"
    with caplog.at_level(logging.WARNING, logger="hostachy.api"):
        monkeypatch.setattr("app.seed.seed", lambda: None)
        demarrage.preparer_la_copropriete()
    ecarts = [r for r in caplog.records if "la base garde" in r.getMessage()]
    assert [r.levelname for r in ecarts] == ["WARNING"]
