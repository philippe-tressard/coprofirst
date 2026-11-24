"""Le code de `app/` ne se recopie pas d'un module à l'autre (#2949, `standards/02` §1 ter).

Deux relevés sur l'AST, à côté des clones exacts de jscpd (`scripts/ci/clones_python.py`,
cinquante jetons au moins), qui ne voient ni une fonction RENOMMÉE ni un message court :

1. **Une phrase écrite dans deux modules** — une chaîne littérale de plus de vingt-cinq
   caractères qui porte une espace (une phrase, pas un nom) — est une notion recopiée,
   sauf HOMONYMIE déclarée ci-dessous avec sa raison. Une chaîne SANS espace est un nom
   (clé de réglage, code de gabarit, geste du journal, route, type MIME, adresse) : elle
   désigne une entrée de son registre, que ce registre tient (`test_reglages_*`,
   `test_email_templates`, `test_journal_securite`…). Les messages rassemblés ont leur
   porte dans `test_messages_source_unique.py`.
2. **Deux fonctions au corps identique** dans deux modules (empreinte d'AST, docstring
   retirée, dès trois instructions) — l'une appelle l'autre. Mesuré à 0 le 24/11/2026,
   après #3063 ; `COPIES_ADMISES` est vide et ne fait que rester vide.

Le relevé de l'audit du 23/11/2026 comptait 65 phrases à v3.122.2 ; #3063 en a rassemblé
une partie, la v3.125.0 en comptait 52 (noms compris), et ce lot 40 — dont 13 phrases, toutes
déclarées ci-dessous. Une déclaration qui ne se répète plus échoue : elle ne survit pas à
son objet.
"""

from __future__ import annotations

import ast
import collections

from tests.aides_sources import chaines_du_code, empreinte_du_corps, modules_app

LONGUEUR_MIN = 25
INSTRUCTIONS_MIN = 3

#: Même texte, autre règle — ou mise en forme qui n'est pas une règle. Chaque entrée dit
#: pourquoi elle reste écrite à deux endroits. Liste qui ne fait que BAISSER.
HOMONYMES = {
    "Dernière sauvegarde réussie il y a ": (
        "deux règles : un retard en JOURS au registre des installations (`registre/alertes`), "
        "au-delà de 25 HEURES sur le nœud (`health_monitor`)"
    ),
    "</strong> vient d'emménager": (
        "deux rendus d'un fait (`standards/11` §14) : l'annonce de hall (lieu et succession) "
        "et la fiche de l'affaire de l'arrivant (démarches)"
    ),
    "<h2>Propriété intellectuelle</h2>": (
        "le même intitulé dans deux textes légaux différents : la démo et la copropriété"
    ),
    #  Mise en forme des gabarits de courriel du seed — du style, pas une règle. Les
    #  rassembler dans `seed/emails/fragments.py` est une dette (le texte livré en base ne
    #  change pas) : chaque entrée qui part fait baisser la liste.
    '<p style="margin:0 0 4px;font-size:13px;color:': "mise en forme des gabarits de courriel",
    '<p style="margin:0;font-size:13px;color:': "mise en forme des gabarits de courriel",
    '<p style="margin:0 0 20px;font-size:13px;color:': "mise en forme des gabarits de courriel",
    '<p style="margin:0 0 12px">Bonjour {{ destinataire.prenom }},</p>': (
        "mise en forme des gabarits de courriel"
    ),
    ';border-radius:8px;overflow:hidden"><tr><td style="background:': (
        "mise en forme des gabarits de courriel"
    ),
    '<p style="margin:0 0 8px;font-weight:700;font-size:16px;color:': (
        "mise en forme des gabarits de courriel"
    ),
    '<p style="margin:0;font-size:14px;color:': "mise en forme des gabarits de courriel",
    '<p style="margin:0 0 16px">': "mise en forme des gabarits de courriel",
    "{% if is_commentaire %}💬 Nouveau commentaire{% else %}": (
        "mise en forme des gabarits de courriel (le sujet commun aux deux familles d'affaires)"
    ),
}

#: Fonctions au corps identique admises dans deux modules, avec leur raison. Vide.
COPIES_ADMISES: dict[frozenset[str], str] = {}


def est_une_phrase(texte: str) -> bool:
    """Une chaîne qui compte : assez longue, et qui porte une espace — un nom n'en porte pas."""
    propre = texte.strip()
    return len(propre) > LONGUEUR_MIN and " " in propre


def phrases_recopiees(modules) -> dict[str, set[str]]:
    """Chaque phrase écrite dans au moins deux modules → les `module:ligne`. PURE."""
    vues: dict[str, set[str]] = collections.defaultdict(set)
    for m in modules:
        for noeud in chaines_du_code(m.arbre):
            if est_une_phrase(noeud.value):
                vues[noeud.value].add(f"{m.rel}:{noeud.lineno}")
    return {
        texte: lieux
        for texte, lieux in vues.items()
        if len({lieu.rsplit(":", 1)[0] for lieu in lieux}) >= 2
    }


def fonctions_recopiees(modules) -> list[frozenset[str]]:
    """Les groupes de fonctions (`module:nom`) au corps identique dans deux modules. PURE."""
    par_corps: dict[str, set[str]] = collections.defaultdict(set)
    for m in modules:
        for noeud in ast.walk(m.arbre):
            if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
                empreinte = empreinte_du_corps(noeud)
                if empreinte and empreinte.count("|") + 1 >= INSTRUCTIONS_MIN:
                    par_corps[empreinte].add(f"{m.rel}:{noeud.name}")
    return [
        frozenset(groupe)
        for groupe in par_corps.values()
        if len({f.split(":")[0] for f in groupe}) >= 2
    ]


class _Faux:
    def __init__(self, rel: str, source: str):
        self.rel, self.arbre = rel, ast.parse(source)


def test_le_releve_sait_REFUSER_et_laisse_les_noms():
    phrase = "Cette phrase dit une règle, et elle est recopiée"
    corps = "    x = 1\n    y = x + 1\n    return y\n"
    a = _Faux(
        "a.py", f'MSG = "{phrase}"\nCLE = "une_cle_de_reglage_assez_longue_ici"\ndef f():\n{corps}'
    )
    b = _Faux(
        "b.py",
        f'def g():\n    raise ValueError("{phrase}")\n'
        f'CLE = "une_cle_de_reglage_assez_longue_ici"\ndef h():\n{corps}',
    )
    assert set(phrases_recopiees([a, b])) == {phrase}  # le nom sans espace n'est pas relevé
    assert fonctions_recopiees([a, b]) == [frozenset({"a.py:f", "b.py:h"})]
    #  Une docstring raconte : elle peut citer la phrase sans la recopier.
    c = _Faux("c.py", f'def k():\n    """{phrase}"""\n')
    assert phrases_recopiees([a, c]) == {}


def test_aucune_phrase_recopiee_hors_homonymie_declaree():
    recopiees = phrases_recopiees(modules_app(minimum=100))
    neuves = {t: sorted(lieux) for t, lieux in recopiees.items() if t not in HOMONYMES}
    assert not neuves, (
        "Phrase écrite dans plusieurs modules — si c'est la même règle, une constante dans le "
        "module de la notion (et sa porte dans `test_messages_source_unique.py`) ; sinon une "
        "HOMONYMIE déclarée avec sa raison :\n"
        + "\n".join(f"  « {t[:80]} » : {', '.join(lieux)}" for t, lieux in neuves.items())
    )
    perimees = sorted(set(HOMONYMES) - set(recopiees))
    assert not perimees, f"homonymie déclarée qui ne se répète plus — la retirer : {perimees}"


def test_aucune_fonction_recopiee_d_un_module_a_l_autre():
    groupes = fonctions_recopiees(modules_app(minimum=100))
    neufs = [sorted(g) for g in groupes if g not in COPIES_ADMISES]
    assert not neufs, (
        "Fonction(s) au corps identique dans plusieurs modules de `app/` — l'une appelle "
        "l'autre :\n" + "\n".join(f"  • {', '.join(g)}" for g in neufs)
    )
    perimees = [sorted(g) for g in COPIES_ADMISES if g not in groupes]
    assert not perimees, f"copie admise qui n'existe plus — la retirer : {perimees}"
