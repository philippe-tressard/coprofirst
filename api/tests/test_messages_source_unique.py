"""Un refus qui porte la même règle s'écrit une fois (#2949).

L'audit du 23/11/2026 a relevé des messages recopiés mot pour mot d'un module à
l'autre. Qualifiés un à un : ceux qui disent la MÊME règle vivent dans une
constante du module de la notion, importée par les autres. Ce contrôle refuse
qu'un de ces textes se réécrive en littéral — `standards/02` §1 ter.

Les homonymies — même texte, règle différente — restent écrites à leur place ;
elles se déclarent, avec leur raison, dans `HOMONYMES` de
`test_copies_de_code_api.py`, qui refuse toute autre phrase recopiée.

Lu sur l'AST : une chaîne littérale ou le morceau constant d'une f-string ; les
docstrings et les commentaires ne comptent pas.
"""

from __future__ import annotations

import ast

from tests.aides_sources import docstrings, modules_app

#: Le texte, et le seul module qui a le droit de l'écrire.
MESSAGES = {
    "Le modèle n'a pas répondu dans le format attendu": "utils/description_format.py",
    "Réponse de l'assistant illisible": "utils/description_format.py",
    "Type invalide (commentaire ou etat)": "utils/evolutions.py",
    "nouveau_statut requis pour un changement d'état": "utils/evolutions.py",
    "Mot de passe actuel incorrect.": "utils/mots_de_passe.py",
    "Périmètre parent inconnu": "routers/patrimoine.py",
    #  Second relevé (#2949, 24/11/2026) — chacun dit la même règle à ses deux endroits.
    "Cette catégorie est réservée au conseil syndical": "auth/gestes_affaire.py",
    "Impossible de lire l'image.": "utils/images.py",
    "Aucun règlement n'est versé (Ma résidence › Règlement).": "utils/etat_descriptif_ia.py",
    "contrôle d'intégrité en échec": "utils/backup.py",
    "Supprimer les imports en_attente avant ré-import": "utils/import_xlsx.py",
    "Ignoré automatiquement (hors résidents)": "utils/import_xlsx.py",
    "est close : elle ne reçoit plus rien": "utils/versement_transfert.py",
    "Le service n'a pas pu être joint.": "utils/llm_modeles.py",
    "installation d'essai : la référence n'est pas appelée": "inscription/constat.py",
    #  Des noms, sans espace : le relevé général (`test_copies_de_code_api.py`) ne les
    #  voit pas, leur porte est ici.
    "https://api.github.com/repos/": "utils/installation.py",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "utils/fichiers.py",
    "SELECT version_num FROM alembic_version": "utils/revision_base.py",
}


def ecritures(arbre: ast.AST, texte: str) -> list[int]:
    """Les lignes où une chaîne du code contient `texte`. PURE."""
    exclues = docstrings(arbre)
    return sorted(
        n.lineno
        for n in ast.walk(arbre)
        if isinstance(n, ast.Constant)
        and isinstance(n.value, str)
        and id(n) not in exclues
        and texte in n.value
    )


def test_le_controle_sait_REFUSER():
    source = 'raise HTTPException(422, f"Périmètre parent inconnu : {code}")\n'
    assert ecritures(ast.parse(source), "Périmètre parent inconnu") == [1]
    assert ecritures(ast.parse('"""Périmètre parent inconnu."""'), "Périmètre parent inconnu") == []


def test_chaque_message_s_ecrit_une_fois():
    modules = modules_app(minimum=100)
    fautes, vus = [], set()
    for texte, porte in MESSAGES.items():
        for m in modules:
            lignes = ecritures(m.arbre, texte)
            if m.rel == porte:
                if len(lignes) == 1:
                    vus.add(texte)
                else:
                    fautes.append(f"{porte} : « {texte} » écrit {len(lignes)} fois (attendu : 1)")
            else:
                fautes += [
                    f"{m.rel}:{ligne} recopie « {texte} » — importer la constante de {porte}"
                    for ligne in lignes
                ]
    assert not fautes, "\n".join(fautes)
    assert vus == set(MESSAGES), f"message disparu de sa porte : {set(MESSAGES) - vus}"
