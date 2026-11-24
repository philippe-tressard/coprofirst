"""Chaque arbre npm du dépôt est audité, en CI et dans la veille de nuit (#2962).

`README.md` promettait « `npm audit` sur tout l'arbre » ; seul le front l'était
(`front/scripts/check-audit.mjs`, lancé dans `front`). Le bridge WhatsApp n'avait
que Trivy sur son image, la nuit, aux seuils CRITICAL et HIGH — ses deux alertes
hautes de #2148 n'ont été vues qu'à la lecture d'un message de `git push`.

La liste des arbres n'est pas recopiée : c'est celle des manifestes que
`front/scripts/check-licence-manifestes.mjs` connaît déjà.
"""

import re

from tests.conftest import racine_depot

RACINE = racine_depot()
WORKFLOWS = RACINE / ".github" / "workflows"


def _dossiers_npm() -> list[str]:
    texte = (RACINE / "front" / "scripts" / "check-licence-manifestes.mjs").read_text(
        encoding="utf-8"
    )
    m = re.search(r"const MANIFESTES = \[([^\]]+)\]", texte)
    assert m, "MANIFESTES introuvable : contrôle impossible"
    dossiers = [p.split("/")[0] for p in re.findall(r"'([^']+/package\.json)'", m.group(1))]
    assert {"front", "whatsapp-bridge"} <= set(dossiers), dossiers  # cas zéro
    return dossiers


def _audite(workflow: str, dossier: str) -> bool:
    texte = (WORKFLOWS / workflow).read_text(encoding="utf-8")
    if dossier == "front":
        return "lint:audit" in texte
    #  Une étape lancée DANS le dossier, qui audite ce dossier.
    etapes = re.split(r"\n\s+- (?:name|uses):", texte)
    return any(
        re.search(rf"working-directory:\s*{re.escape(dossier)}\s*\n", e)
        and "check-audit.mjs --dossier ." in e
        for e in etapes
    )


def test_chaque_arbre_npm_est_audite_en_ci_et_la_nuit():
    manque = [
        f"{w} : {d}"
        for d in _dossiers_npm()
        for w in ("ci.yml", "veille-securite.yml")
        if not _audite(w, d)
    ]
    assert not manque, "arbre npm sans `npm audit` :\n" + "\n".join(manque)
