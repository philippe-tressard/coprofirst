"""La description d'une skill dit ce que `CLAUDE.md` lui confie (#2938).

## 🔴 Pourquoi

La DESCRIPTION est ce qui déclenche le chargement d'une skill : le harnais la lit
pour décider. Le 23/11/2026, `CLAUDE.md` confiait les « tests Playwright » à
`svelte-patterns`, les « scripts d'infra en CI » à `infra-rpi`, la « checklist
front avant commit » à `ux-patterns` — et aucune de leurs descriptions n'en disait
un mot. Une tâche sur un test de navigateur n'appelait donc pas la skill qui en
porte les règles. Quatre descriptions sur sept retardaient sur la table.

## Ce que ce contrôle vérifie

Pour chaque ligne de la table « Skills du projet » de `CLAUDE.md`, chaque terme de
la colonne « Tâche » (séparés par une virgule, deux-points, tiret long, « et »,
« ou ») figure dans la description de la skill nommée — sans casse ni balisage.
La table est la source : une tâche qu'on y ajoute doit entrer dans la description.
"""

from __future__ import annotations

import pathlib
import re

_RACINE = pathlib.Path(__file__).resolve().parents[2]
_SKILLS = _RACINE / ".claude" / "skills"

#: Les skills dont la description n'est pas tenue ici, et pourquoi. Une entrée
#: qui ne sert plus (la description couvre la table) fait échouer le contrôle.
EXCEPTIONS = {
    "security-audit": (
        "description en anglais, à réécrire par le lot de l'audit de sécurité du "
        "23/11/2026, qui tient cette skill"
    ),
}


def _table() -> list[tuple[str, str]]:
    """(tâche, skill) de chaque ligne de la table « Skills du projet »."""
    texte = (_RACINE / "CLAUDE.md").read_text(encoding="utf-8")
    section = re.search(r"^## Skills du projet\n(.*?)(?=^## |^---)", texte, re.M | re.S)
    assert section, "section « Skills du projet » introuvable dans CLAUDE.md"
    return re.findall(r"^\| (.+?) \| `([a-z-]+)` \|$", section.group(1), re.M)


def _normal(texte: str) -> str:
    return re.sub(r"[*`]", "", texte).lower()


def _termes(tache: str) -> list[str]:
    morceaux = re.split(r",|:|—| et | ou ", _normal(tache))
    return [m.strip() for m in morceaux if m.strip()]


def _description(skill: str) -> str:
    entete = (_SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
    m = re.search(r"^description:\s*\"(.*)\"\s*$", entete, re.M)
    assert m, f"{skill} : pas de ligne `description:` lisible"
    return _normal(m.group(1))


def _absents(skill: str, tache: str) -> list[str]:
    description = _description(skill)
    return [t for t in _termes(tache) if t not in description]


def test_chaque_description_couvre_sa_ligne_de_claude_md():
    fautes, inutiles = [], []
    for tache, skill in _table():
        absents = _absents(skill, tache)
        if skill in EXCEPTIONS:
            if not absents:
                inutiles.append(skill)
            continue
        if absents:
            fautes.append(f"  {skill} — absents de sa description : {', '.join(absents)}")
    assert not inutiles, f"exceptions qui ne servent plus (à retirer) : {inutiles}"
    assert not fautes, (
        "La description d'une skill ne dit pas ce que CLAUDE.md lui confie — "
        "elle ne sera pas chargée pour ces tâches :\n" + "\n".join(fautes)
    )


def test_la_table_est_lue_et_le_controle_sait_refuser():
    """Cas zéro : la table compte ses sept skills, et un terme absent est vu."""
    table = _table()
    assert len(table) >= 7, table
    assert all((_SKILLS / s / "SKILL.md").exists() for _t, s in table), table
    assert set(EXCEPTIONS) <= {s for _t, s in table}, "exception sur une skill absente"
    assert _termes("Page ou composant SvelteKit, tests **Playwright**") == [
        "page",
        "composant sveltekit",
        "tests playwright",
    ]
    assert _absents("svelte-patterns", "terme jamais écrit") == ["terme jamais écrit"]
