"""Une commande hors requête nomme sa copropriété sur une installation commune (#2053).

- **le comportement** : sans `--copropriete`, une installation commune refuse (code 2)
  sans rien ouvrir ; avec, la commande tourne dans le contexte de CELLE-LÀ ; un nom
  inconnu est refusé ; une installation propre ne demande rien, comme avant ;
- **la portée** : chaque module de `app/` qui se lance (`if __name__ == "__main__"`)
  passe par `utils/commande`, ou se déclare dans `SANS_COPROPRIETE` avec sa raison.
  Une déclaration qui ne sert plus fait échouer (cas zéro du relevé).
"""

from __future__ import annotations

import ast

import pytest

from app import contexte
from app.utils import commande
from tests.aides_installation_commune import installation_commune
from tests.aides_sources import modules_app

#: Les modules qui se lancent sans travailler pour une copropriété, et pourquoi.
SANS_COPROPRIETE = {
    "installation_commune/verifier.py": "lit la DÉCLARATION, aucune base de copropriété",
    "installation_commune/creer.py": "CRÉE une copropriété : il la nomme en argument, "
    "et ne lit la base d'aucune autre",
    "registre/migrer.py": "la base `plateforme` du registre des installations",
    "registre/sauvegarde.py": "la base `plateforme` du registre des installations",
    "registre/versions.py": "règle PURE, sans base : `scripts/ci/purge-paquets.sh` l'exécute en CI",
    "utils/preparer_bases.py": "prépare TOUTES les bases, chacune nommée dans sa ligne",
    "utils/attendre_base.py": "outil de `DATABASE_URL`, appelé par `start.sh` avant #2053",
    "utils/revision_base.py": "outil de `DATABASE_URL`, appelé par `start.sh` avant #2053",
    "utils/schema_initial.py": "outil de `DATABASE_URL` (restauration, démo) : une URL, pas un contexte",
    "utils/corrections.py": "auto-test pur, sans base",
    "utils/corrections_texte.py": "auto-test pur, sans base",
    "utils/perimetre_fil.py": "auto-test pur, sans base",
    "utils/recherche_affaires.py": "auto-test pur, sans base",
    "utils/suivi_fil.py": "auto-test pur, sans base",
}


def _se_lance(arbre: ast.AST) -> bool:
    for n in ast.walk(arbre):
        if isinstance(n, ast.If) and isinstance(n.test, ast.Compare):
            gauche = n.test.left
            if isinstance(gauche, ast.Name) and gauche.id == "__name__":
                return True
    return False


def _passe_par_la_commande(arbre: ast.AST) -> bool:
    return any(
        isinstance(n, ast.ImportFrom)
        and n.module == "app.utils"
        and any(a.name == "commande" for a in n.names)
        for n in ast.walk(arbre)
    )


def test_chaque_commande_nomme_sa_copropriete_ou_se_declare():
    lancables = {m.rel: m for m in modules_app(minimum=300) if _se_lance(m.arbre)}
    assert len(lancables) >= 10, "cas zéro : le relevé ne voit plus les commandes"
    fautes = [
        rel
        for rel, m in lancables.items()
        if rel not in SANS_COPROPRIETE
        and rel != "utils/commande.py"
        and not _passe_par_la_commande(m.arbre)
    ]
    assert not fautes, (
        "Commande qui travaillerait pour « la » copropriété de la configuration (#2053) — "
        "la faire passer par `utils/commande.lancer`, ou la déclarer dans "
        f"SANS_COPROPRIETE avec sa raison : {fautes}"
    )
    mortes = sorted(set(SANS_COPROPRIETE) - set(lancables))
    assert not mortes, f"SANS_COPROPRIETE déclare des modules qui ne se lancent plus : {mortes}"


def test_une_installation_propre_ne_demande_rien():
    vu = []
    assert (
        commande.lancer(lambda reste: vu.append((contexte.courante().identifiant, reste)), []) == 0
    )
    assert vu == [(contexte.IDENTIFIANT_UNIQUE, [])]
    assert commande.lancer(lambda _r: 0, ["--copropriete", contexte.IDENTIFIANT_UNIQUE]) == 0
    assert commande.lancer(lambda _r: 0, ["--copropriete", "tilleuls"]) == 2


def test_une_installation_commune_exige_le_nom(tmp_path, monkeypatch, capsys):
    vu = []
    with installation_commune(tmp_path, monkeypatch):
        #  Sans nom : refus, et RIEN n'a tourné — ni repli sur la configuration.
        assert commande.lancer(lambda _r: vu.append("lancée"), ["--force"]) == 2
        assert vu == []
        assert "--copropriete" in capsys.readouterr().err
        with pytest.raises(contexte.HorsCopropriete):
            contexte.courante()
        #  Un nom inconnu : refus.
        assert commande.lancer(lambda _r: vu.append("lancée"), ["--copropriete", "x"]) == 2
        assert vu == []
        #  Témoin : nommée, elle tourne dans SON contexte, et l'option est retirée.
        lancer = commande.lancer(
            lambda reste: vu.append((contexte.courante().identifiant, reste)),
            ["--force", "--copropriete", "chenes"],
        )
        assert lancer == 0
        assert vu == [("chenes", ["--force"])]
