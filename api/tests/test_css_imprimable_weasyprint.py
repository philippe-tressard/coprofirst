"""Les CSS imprimables n'emploient que ce que WeasyPrint sait lire.

## L'incident (11/09/2026)

Le filet doré à gauche du bandeau de périmètre a été refait en dégradé, pour
supprimer une double barre. Il s'affichait dans l'aperçu HTML — et **disparaissait
du PDF**, fond beige compris.

La cause, lue dans la source de WeasyPrint 69 (`css/tokens.py::parse_color_stop`) :

    if len(tokens) == 1:   ... couleur seule
    elif len(tokens) == 2: ... couleur + position
    raise InvalidValues

L'arrêt écrit était `var(--gold) 0 1.2mm` — **trois** jetons, la syntaxe CSS
Images Level 4 à deux positions. WeasyPrint lève, la déclaration `background`
entière est jetée, et **rien ne le dit** : pas d'erreur, pas de journal, un fond
simplement absent.

## 🔴 Ce que ce contrôle protège vraiment

**L'aperçu et le PDF ne sont pas rendus par le même moteur.** L'aperçu est du HTML
dans un navigateur ; le PDF sort de WeasyPrint. Une propriété que le navigateur
accepte et que WeasyPrint refuse produit deux résultats différents pour le même
code — et c'est l'aperçu, celui qu'on regarde, qui ment.

Le poste de développement ne peut pas rendre de PDF (bibliothèques natives
absentes sous Windows). Ce contrôle est donc le seul moyen d'attraper la classe
d'erreur ici, avant la production : il lit la règle **dans la source de
WeasyPrint** plutôt que de la recopier, et l'applique aux CSS qu'on écrit.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from tests.aides_sources import modules_app

#: Une feuille de style imprimable vit dans un module `utils/<document>_css.py`.
_FEUILLE = re.compile(r"utils/[^/]+_css\.py")

#: Les sources que la portée DÉRIVÉE doit contenir — un plancher, pas la portée.
#:
#: 🔴 Jusqu'au 30/09/2026 (#1496), la portée ÉTAIT une liste écrite à la main, et
#: elle ne suivait plus le code : la feuille de la fiche arrivant était partie
#: dans `fiche_arrivant_css.py`, celle du manuel (`manuel_pdf_css.py`, un
#: `linear-gradient`) n'y était jamais entrée, et `if not f.exists(): continue`
#: faisait disparaître une source déplacée sans un mot. La portée se dérive
#: désormais ; cette liste ne sert qu'à dire que la dérivation voit encore ce
#: qu'elle voyait — une source qui en sort fait échouer le test, en la nommant.
ATTENDUES = frozenset(
    {
        "utils/pdf_theme.py",
        "utils/annonce_hall.py",
        "utils/manuel_pdf.py",
        "utils/fiche_arrivant_css.py",
        "utils/manuel_pdf_css.py",
    }
)


def _touche_html_to_pdf(arbre: ast.Module) -> bool:
    """Le module appelle `html_to_pdf` — ou le définit (`pdf_theme`, sa palette)."""
    for n in ast.walk(arbre):
        if isinstance(n, ast.FunctionDef) and n.name == "html_to_pdf":
            return True
        if isinstance(n, ast.Call):
            f = n.func
            nom = f.id if isinstance(f, ast.Name) else getattr(f, "attr", None)
            if nom == "html_to_pdf":
                return True
    return False


def _portee(modules) -> dict[str, str]:
    """Les feuilles `*_css.py` et les modules qui rendent un PDF : `{rel: source}`."""
    return {
        m.rel: m.source
        for m in modules
        if _FEUILLE.fullmatch(m.rel) or _touche_html_to_pdf(m.arbre)
    }


def _regle_weasyprint() -> int:
    """Le nombre maximal de jetons qu'un arrêt de couleur admet, LU dans WeasyPrint.

    Le recopier ferait de ce test une seconde source de vérité : le jour où
    WeasyPrint accepterait la syntaxe à deux positions, ce contrôle continuerait
    de la refuser sans raison.
    """
    import importlib.util

    spec = importlib.util.find_spec("weasyprint")
    if spec is None or spec.origin is None:
        pytest.skip("WeasyPrint absent de cet environnement")
    tokens = Path(spec.origin).parent / "css" / "tokens.py"
    #  Un ÉCHEC, plus un saut (#2952) : WeasyPrint est épinglé et monté par
    #  Dependabot — le jour où il se réorganise, ce contrôle se réécrit, il ne
    #  s'abstient pas en silence.
    assert tokens.exists(), (
        f"La source de WeasyPrint n'a plus `css/tokens.py` ({tokens}) : réécrire "
        "ce contrôle pour la nouvelle forme."
    )
    source = tokens.read_text(encoding="utf-8")
    corps = source[source.index("def parse_color_stop") :]
    corps = corps[: corps.index("\ndef ", 1)]
    longueurs = [int(n) for n in re.findall(r"len\(tokens\) == (\d+)", corps)]
    assert longueurs, "Cas zéro : `parse_color_stop` a changé de forme — contrôle inopérant."
    return max(longueurs)


def _arrets_de_couleur(css: str) -> list[tuple[str, str]]:
    """Les arrêts de chaque `linear-gradient(...)` trouvé, avec leur gradient."""
    arrets = []
    for gradient in re.findall(r"linear-gradient\(([^()]*(?:\([^()]*\)[^()]*)*)\)", css):
        morceaux = re.split(r",(?![^(]*\))", gradient)
        #  Le premier morceau est la DIRECTION (`to right`, `90deg`) quand il ne
        #  porte pas de couleur — il n'est pas un arrêt.
        for i, m in enumerate(morceaux):
            m = m.strip()
            if i == 0 and not re.search(r"#|var\(|rgb|[a-z]+\s*\d*%", m):
                continue
            if i == 0 and re.fullmatch(r"(to\s+\w+(\s+\w+)?|-?[\d.]+deg)", m):
                continue
            arrets.append((gradient.strip(), m))
    return arrets


def _fautes(sources: dict[str, str], maxi: int) -> tuple[list[str], int]:
    """Les arrêts de plus de `maxi` jetons, et le nombre d'arrêts lus."""
    fautes = []
    vus = 0
    for rel, css in sources.items():
        for gradient, arret in _arrets_de_couleur(css):
            vus += 1
            #  `var(--x)` compte pour UN jeton, comme dans tinycss2.
            jetons = re.sub(r"var\([^)]*\)", "VAR", arret).split()
            if len(jetons) > maxi:
                fautes.append(
                    f"{rel} — « {arret} » ({len(jetons)} jetons) dans « {gradient[:60]}… »"
                )
    return fautes, vus


def test_aucun_arret_de_couleur_ne_depasse_ce_que_weasyprint_lit():
    maxi = _regle_weasyprint()
    sources = _portee(modules_app())
    manquantes = sorted(ATTENDUES - set(sources))
    assert sources and not manquantes, (
        f"Cas zéro : la portée dérivée ne voit plus {manquantes or 'rien'} — une "
        "feuille a changé de place, ou `html_to_pdf` de nom. Le contrôle ne "
        "mesurerait plus ce qu'il croit mesurer."
    )
    fautes, vus = _fautes(sources, maxi)

    assert vus > 0, (
        "Cas zéro : aucun dégradé trouvé dans les feuilles imprimables — "
        "l'extraction est cassée, ou les CSS ont changé de place."
    )
    assert not fautes, (
        f"WeasyPrint n'accepte qu'un arrêt de {maxi} jetons au plus "
        "(`css/tokens.py::parse_color_stop`) ; au-delà il lève et jette la "
        "déclaration ENTIÈRE, en silence :\n  "
        + "\n  ".join(fautes)
        + "\n\n  L'aperçu HTML continuerait de l'afficher — c'est ce qui a fait "
        "disparaître le filet du bandeau de périmètre le 11/09/2026."
    )


def test_le_controle_refuse_l_arret_a_deux_positions():
    """Cas zéro du MOTIF : l'arrêt du 11/09/2026, forgé, doit être refusé."""
    maxi = _regle_weasyprint()
    fautif = "background: linear-gradient(90deg, var(--gold) 0 1.2mm, transparent 0);"
    admis = "background: linear-gradient(90deg, var(--gold) 0%, transparent 1.2mm);"
    assert _fautes({"forge_css.py": fautif}, maxi)[0], "l'arrêt à trois jetons passe"
    assert _fautes({"forge_css.py": admis}, maxi) == ([], 2)
