"""Le front et l'API donnent la MÊME icône à un type d'évolution.

## Pourquoi ce garde-fou (19/08/2026, signalé à l'écran)

> *« Pourquoi mon commentaire sur un ticket a une icône de type relance et non
> commentaire ? »*

La même notion était écrite **quatre fois, avec trois valeurs** :

| Où | `commentaire` | `reponse` |
|---|---|---|
| le bouton qui ouvre le formulaire | 💬 | — |
| le fil (`RubriqueHistorique`) | 📝 | 💬 |
| le fil recomposé à la main dans `espace-cs` | 📝 | 💬 |
| le flux d'activité (`flux/tickets.py`) | 🔧 | 💬 |

On cliquait « 💬 Commenter » et l'entrée s'affichait en 📝 — un mémo, lu comme une
relance. Chacune de ces tables était cohérente **avec elle-même** : c'est ce qui
les rendait invisibles à la relecture (#415, #413).

Les trois écritures du front ont été réunies dans `#lib/evolutions.ts`. La
quatrième ne peut pas les rejoindre : **les contextes de build sont `./api` et
`./front`**, rien de la racine n'entre dans les images (mémoire projet du
14/08/2026). Deux écritures sont donc inévitables.

🔴 **Ce qui est inévitable se surveille, il ne se promet pas.** C'est ce test —
même remède que pour le motif de crontab, écrit deux fois lui aussi et divergent
pendant quatre jours (`lib-verdicts` / `lib-collecte`, corrigé le même jour).

⚠️ Le **libellé** n'est PAS comparé, et c'est délibéré : « Mise à jour » décrit
une carte de flux, « commentaire » une entrée de fil. Deux rendus du même fait
peuvent porter des mots différents — seul le **signe** doit être commun, parce
que c'est lui qu'on reconnaît sans lire.
"""

from __future__ import annotations

import re
from pathlib import Path

_RACINE = Path(__file__).resolve().parents[2]
_FRONT = _RACINE / "front" / "src" / "lib" / "evolutions.ts"
_API = _RACINE / "api" / "app" / "routers" / "flux" / "tickets.py"


def _icones_front() -> dict[str, str]:
    """`EVOLUTION_ICONE` de `#lib/evolutions.ts`, lu comme du texte.

    Les échappements `\\u{1F4AC}` sont résolus : le front les écrit ainsi parce
    qu'un emoji hors BMP survit mal aux allers-retours d'encodage sous Windows
    (`standards/10`), alors que le Python les écrit littéralement. Comparer les
    deux formes sans les normaliser ferait échouer ce test sur une différence
    d'écriture, pas de valeur.
    """
    source = _FRONT.read_text(encoding="utf-8")
    #  ⚠️ La borne est la ligne `};`, PAS la première accolade fermante : les
    #  valeurs contiennent des échappements `\u{...}`, donc un `\{(.*?)\}` non
    #  gourmand s'arrête au milieu de la première. Attrapé en exécutant ce test,
    #  pas en le relisant — troisième motif d'extraction incapable de
    #  correspondre dans la même journée (cf. `crontab_scripts`, et le `Z` ISO
    #  du 11/08).
    bloc = re.search(r"EVOLUTION_ICONE.*?=\s*\{(.*?)^\};", source, re.S | re.M)
    assert bloc, (
        "`EVOLUTION_ICONE` est introuvable dans evolutions.ts — ce test "
        "surveillait une table qui n'existe plus, il ne surveillait donc rien."
    )
    table = {}
    for cle, valeur in re.findall(r"(\w+)\s*:\s*'([^']*)'", bloc.group(1)):
        table[cle] = re.sub(r"\\u\{([0-9A-Fa-f]+)\}", lambda m: chr(int(m.group(1), 16)), valeur)
    return table


def _icones_api() -> dict[str, str]:
    """`_MISES_A_JOUR` de `flux/tickets.py` : (type, préfixe, libellé, icône)."""
    source = _API.read_text(encoding="utf-8")
    bloc = re.search(r"_MISES_A_JOUR\s*=\s*\((.*?)\n\)", source, re.S)
    assert bloc, "`_MISES_A_JOUR` est introuvable dans flux/tickets.py."
    return {
        t: icone
        for t, _prefixe, _libelle, icone in re.findall(
            r'\("([^"]+)",\s*"([^"]+)",\s*"([^"]+)",\s*"([^"]+)"\)', bloc.group(1)
        )
    }


def test_les_deux_tables_sont_lisibles():
    """Un test qui ne trouve pas ses tables échoue — il ne passe pas au vert.

    `standards/04` §1 : un contrôle qui ne peut pas mesurer rend INCONNU, jamais
    OK. Ici, INCONNU vaut échec.
    """
    front, api = _icones_front(), _icones_api()
    assert front, "table du front vide"
    assert api, "table de l'API vide"
    assert "commentaire" in front and "commentaire" in api


def test_les_icones_communes_sont_identiques():
    """🔴 Le cas exact du 19/08 : `commentaire` valait 📝 ici et 🔧 là.

    Seuls les types présents **des deux côtés** sont comparés : l'API ne rend pas
    de carte pour un changement d'état (`etat` a son propre libellé de flux), et
    exiger la symétrie complète interdirait à chaque écran d'avoir ses propres
    types.
    """
    front, api = _icones_front(), _icones_api()
    ecarts = {t: (front[t], api[t]) for t in set(front) & set(api) if front[t] != api[t]}
    assert not ecarts, (
        "Le front et l'API ne donnent pas la même icône à ces types : "
        + ", ".join(f"{t} → front={f!r} api={a!r}" for t, (f, a) in sorted(ecarts.items()))
        + ".\nUn utilisateur reconnaît un dessin, il ne relit pas une table : "
        "le geste et son résultat doivent porter le même signe."
    )


def test_le_commentaire_porte_la_bulle():
    """La valeur elle-même, pas seulement l'accord entre les deux.

    Deux tables d'accord sur une valeur fausse resteraient vertes au test
    précédent. Celui-ci fixe le fait constaté à l'écran : le bouton dit
    « 💬 Commenter », donc l'entrée qu'il produit porte 💬.
    """
    bulle = "💬"
    assert _icones_front().get("commentaire") == bulle
    assert _icones_api().get("commentaire") == bulle
