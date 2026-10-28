"""Le HTML riche saisi par un utilisateur, assaini CÔTÉ SERVEUR — la seule porte.

## Pourquoi ce module existe (#2150, audit du 22/10/2026)

Le corps d'une affaire, d'une actualité ou d'un message est du HTML écrit par
l'éditeur riche. Jusqu'ici, le serveur le croyait propre : les courriels
l'inséraient par `| safe`, avec ce commentaire — *« le texte est assaini à
l'écriture, côté front, par `#lib/sanitize` »*. Or l'API n'assainissait rien, et
n'importe quel compte peut l'appeler sans passer par l'écran : un résident
envoyait au conseil et au syndic, depuis le domaine de la résidence et signé
DKIM, le HTML de son choix (faux bouton de connexion, formulaire, lien déguisé).

**Un assainissement côté client n'est pas une règle de sécurité côté serveur.**
Ce qui part du serveur passe par ici.

## La liste blanche

Elle est celle de `front/src/lib/sanitize.ts` — le même texte doit s'afficher de
la même façon à l'écran et dans un courriel. Les deux contextes de *build* sont
séparés (`./api`, `./front`) : la liste est donc écrite deux fois, et
🔒 `tests/test_html_sur.py` échoue si elles divergent. Une seule différence,
déclarée : `rel`, que `nh3` pose lui-même sur chaque lien
(`noopener noreferrer`) et refuse de recevoir en attribut permis.

Les schémas d'URL sont fermés (`http`, `https`, `mailto`, et le relatif) :
`javascript:` et `data:` ne passent jamais, quel que soit l'attribut.
"""

from __future__ import annotations

import nh3
from markupsafe import Markup

#: Les balises de `ALLOWED_TAGS` (`front/src/lib/sanitize.ts`).
BALISES = frozenset(
    {
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
        "details",
        "summary",
    }
)

#: Les attributs de `ALLOWED_ATTR`, `rel` excepté (voir l'en-tête).
ATTRIBUTS = frozenset({"href", "src", "alt", "title", "class", "target"})

#: Ce que `rel` devient sur chaque lien — posé par `nh3`, jamais lu du texte.
REL_DES_LIENS = "noopener noreferrer"

SCHEMAS_URL = frozenset({"http", "https", "mailto"})


def assainir_html(texte: str | None) -> str:
    """Le HTML riche réduit à la liste blanche ; un texte simple reste du texte.

    `nh3` analyse le HTML comme un navigateur (html5ever) : une balise coupée
    par une troncature (`contenu[:300]`) est refermée, jamais laissée ouverte.
    """
    if not texte:
        return ""
    return nh3.clean(
        str(texte),
        tags=set(BALISES),
        attributes={"*": set(ATTRIBUTS)},
        url_schemes=set(SCHEMAS_URL),
        link_rel=REL_DES_LIENS,
    )


def html_riche(texte: str | None) -> Markup:
    """Le HTML riche assaini, marqué sûr pour un gabarit qui échappe.

    C'est la forme à donner au contexte d'un courriel pour un champ riche
    (description, message, extrait) : le gabarit l'insère tel quel, et tout le
    reste du contexte est échappé.
    """
    return Markup(assainir_html(texte))


def filtre_safe(valeur) -> Markup:
    """Le filtre `| safe` des courriels : il ASSAINIT, il ne fait plus confiance.

    Les modèles vivent en base et se réécrivent depuis Admin → Emails : `| safe`
    peut y être écrit sur n'importe quelle variable. Redéfini ici, il ne peut
    plus laisser passer un HTML que personne n'a nettoyé. Une valeur déjà
    marquée sûre par le code (`html_riche`, un texte échappé) passe telle quelle.
    """
    if isinstance(valeur, Markup):
        return valeur
    return html_riche("" if valeur is None else str(valeur))
