"""Les balises que la consigne demande sont celles que le FRONT accepte (#992).

## Pourquoi ce contrôle

La consigne de la synthèse impose une grammaire HTML au modèle. Ce n'est pas un
choix de style : le texte est déposé dans un champ enrichi qui traverse deux
filtres, et chacun jette ce qu'il ne connaît pas.

| Filtre | Ce qu'il fait d'une balise inconnue |
|---|---|
| `#lib/sanitize.ts` (DOMPurify) | la retire, en gardant son texte |
| le schéma de l'éditeur (ProseMirror) | l'aplatit au premier chargement |

Trois listes doivent donc parler des mêmes balises : la consigne, la liste
blanche de l'assainisseur, et les nœuds déclarés à l'éditeur. **Trois listes qui
se recopient divergent au premier ajout** — et la divergence ne se verrait qu'à
l'écran, sur un extrait aplati après enregistrement.

## 🔴 Ce que ce test aurait attrapé

Le 17/09/2026, demander des blocs dépliables au modèle aurait suffi à produire
un texte correct… et aplati à l'enregistrement, faute des deux nœuds Tiptap.
Rien, dans le code Python, n'aurait signalé que la consigne demandait une balise
que le front refuse.

⚠️ Il lit les fichiers du front depuis les tests de l'API. Les contextes de
*build* sont séparés (`./api` et `./front`), pas la lecture : c'est déjà ce que
fait `test_liens_front.py`, et c'est le seul moyen de tenir un contrat qui
traverse les deux.
"""

from __future__ import annotations

import pathlib
import re

from app.utils.description_format import CONSIGNE_DEFAUT
from app.utils.synthese_format import CONSIGNE

#: 🔴 Les prompts qui NOMMENT des balises — tous, pas seulement le premier.
#:
#: Ce contrôle ne lisait que la consigne de la synthèse, parce qu'elle était
#: la seule à imposer une grammaire HTML quand il a été écrit. Le prompt de
#: l'usage « description » en impose une depuis le 18/09/2026 — les mises en
#: valeur autorisées à l'assistant — et il serait passé sous le radar : une
#: balise qu'il demanderait et que l'assainisseur refuse arriverait aplatie à
#: l'écran, sans un mot.
#:
#: ⚠️ Un contrôle dont la PORTÉE est une valeur unique se périme au deuxième
#: cas ; une portée qui décrit la notion, non (`standards/04` §40).
PROMPTS = {
    "synthèse de contrat": CONSIGNE,
    "description (assistant)": CONSIGNE_DEFAUT,
}

_API_DIR = pathlib.Path(__file__).resolve().parents[1]
_RACINE = _API_DIR.parent
_SANITIZE = _RACINE / "front" / "src" / "lib" / "sanitize.ts"
_BLOC_DEPLIABLE = _RACINE / "front" / "src" / "lib" / "blocDepliable.ts"
_EDITEUR = _RACINE / "front" / "src" / "lib" / "components" / "RichEditor.svelte"

#: Les balises que StarterKit apporte d'office : elles n'ont pas de nœud déclaré
#: dans le dépôt, et exiger qu'on les y trouve serait un faux rouge.
_FOURNIES_PAR_STARTERKIT = {
    "p",
    "br",
    "b",
    "i",
    "u",
    "s",
    "strong",
    "em",
    "ul",
    "ol",
    "li",
    "blockquote",
    "pre",
    "code",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "a",
    "img",
    "hr",
    "span",
    "div",
}


def _balises_de_la_consigne(texte: str | None = None) -> set[str]:
    """Les balises qu'un prompt NOMME, entre accents graves — `<details>`.

    On lit le prompt plutôt qu'une liste écrite ici : une liste recopiée
    serait la quatrième, et la première à se périmer.
    """
    source = chr(10).join(PROMPTS.values()) if texte is None else texte
    trouvees = set()
    for brut in re.findall(r"`<([a-z][a-z0-9]*)>`", source):
        trouvees.add(brut)
    #  La forme imbriquée du bloc dépliable — `<details><summary>` — n'est pas
    #  captée par le motif ci-dessus : elle est nommée telle qu'on l'écrit.
    for brut in re.findall(r"<([a-z][a-z0-9]*)>", source):
        trouvees.add(brut)
    #  `<html>` et `<body>` sont nommés pour être INTERDITS : les exiger dans la
    #  liste blanche inverserait la consigne.
    return trouvees - {"html", "body"}


def _liste_blanche_du_front() -> set[str]:
    source = _SANITIZE.read_text(encoding="utf-8")
    bloc = re.search(r"const ALLOWED_TAGS = \[(.*?)\];", source, re.DOTALL)
    assert bloc, "ALLOWED_TAGS introuvable dans sanitize.ts — contrôle inapplicable"
    balises = set(re.findall(r"'([a-z][a-z0-9]*)'", bloc.group(1)))
    #  Cas zéro (`standards/04` §2) : une liste vide ferait passer ce test sur
    #  tout, et conclurait « rien à signaler » sur un fichier illisible.
    assert len(balises) >= 10, f"liste blanche suspecte : {balises}"
    return balises


def test_la_consigne_nomme_des_balises_et_le_contrôle_les_voit():
    """Le contrôle s'auto-vérifie : sans balise lue, il ne mesure rien."""
    balises = _balises_de_la_consigne()
    assert len(balises) >= 5, balises
    assert "details" in balises and "summary" in balises


def test_toute_balise_de_la_consigne_est_AUTORISÉE_par_l_assainisseur():
    """Sinon l'assainisseur la retire, et le texte arrive aplati sans un mot."""
    manquantes = sorted(_balises_de_la_consigne() - _liste_blanche_du_front())
    assert not manquantes, (
        "La consigne demande au modèle des balises que `front/src/lib/sanitize.ts` "
        f"refuse : {manquantes}. Les ajouter à `ALLOWED_TAGS`, ou les retirer de "
        "la consigne — un texte que l'assainisseur mutile est pire qu'un texte plus pauvre."
    )


def test_les_balises_HORS_StarterKit_ont_un_nœud_déclaré_à_l_éditeur():
    """🔴 Le filtre que l'assainisseur ne remplace pas.

    DOMPurify décide de ce qui S'AFFICHE ; le schéma de l'éditeur décide de ce
    qui SURVIT à une correction. Le texte de l'assistant traverse le formulaire
    avant d'être enregistré : une balise autorisée mais inconnue du schéma
    disparaît au premier passage, et personne ne le voit avant l'écran.
    """
    propres = _balises_de_la_consigne() - _FOURNIES_PAR_STARTERKIT
    if not propres:
        return
    declare = _BLOC_DEPLIABLE.read_text(encoding="utf-8")
    monte = _EDITEUR.read_text(encoding="utf-8")
    for balise in sorted(propres):
        assert f"name: '{balise}'" in declare, (
            f"La consigne demande `<{balise}>` sans nœud déclaré dans "
            "`front/src/lib/blocDepliable.ts` : ProseMirror l'aplatira."
        )
    #  Déclarer ne suffit pas : le nœud doit être MONTÉ dans l'éditeur. C'est la
    #  leçon des contrôles qui existaient sans s'exécuter — écrire et brancher
    #  sont deux gestes (`standards/05`).
    for nom in ("BlocDepliable", "ResumeDepliable"):
        assert nom in monte, f"{nom} n'est pas monté dans RichEditor.svelte"
