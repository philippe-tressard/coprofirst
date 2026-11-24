"""Le FORMAT de l'usage « description » — ce qu'on demande, et comment on relit.

## Pourquoi ce fichier est séparé d'`assistant_description.py` (17/09/2026)

Même ligne de coupe que `synthese_format.py` / `synthese_contrat.py` : **ici on
décrit ce qu'on attend du modèle et on relit sa réponse**, là-bas on lit une
configuration et on passe l'appel. Ce fichier ne connaît ni la base, ni le
réseau : ce sont des chaînes et un `dict`, vérifiables sans rien monter.

## 🔴 Deux textes, deux propriétaires

| Texte | Qui le tient | Où |
|---|---|---|
| `CONSIGNE_DEFAUT` | **l'administrateur** — c'est le prompt de l'usage, modifiable dans Admin → Assistant IA | en base, initialisé une fois depuis ici (migration 0194) |
| `FORMAT_REPONSE` | **le code** — il impose la forme JSON que `lire_reponse` sait relire | ajouté à l'appel, jamais exposé à l'édition |

Séparer les deux est ce qui permet à l'administrateur de réécrire librement le
ton, la langue ou les interdits sans pouvoir casser la lecture de la réponse :
un prompt qui aurait perdu la phrase « rends du JSON » ferait échouer chaque
appel, sans qu'aucun écran ne dise pourquoi.
"""

from __future__ import annotations

import json
import re

#: Le prompt d'ORIGINE de l'usage — celui que l'administrateur relit et adapte.
#: Rédigé le 17/09/2026 sur les quatre consignes de Philippe : langage simple,
#: législation française, réponse synthétique, destinée aux copropriétaires et
#: locataires.
CONSIGNE_DEFAUT = """Tu retravailles le titre et la description d'une publication destinée aux
copropriétaires et aux locataires d'une copropriété.

- Rédige dans un langage simple, courtois et neutre, sans être offensant.
- Respecte la législation française relative aux contenus publiés : aucune
  mise en cause nominative, aucune donnée personnelle qui n'était pas déjà
  dans le texte, aucun propos diffamatoire ou discriminatoire.
- La réponse est synthétique et compréhensible par tous.
- Conserve tous les faits, dates, montants, lieux et noms fournis ; n'en
  invente aucun et n'en supprime aucun.
- Si le titre manque, propose-en un court à partir de la description. Si la
  description manque, propose-en une à partir du titre seul.
- Le contexte transmis (catégorie, périmètre, état, date…) sert à comprendre
  le texte ; il ne se réécrit pas et ne se recopie pas dans la description.

MISE EN FORME DE LA DESCRIPTION

La description est du HTML simple. Tu disposes de ces balises, et d'aucune
autre :

- `<p>` pour un paragraphe, `<br>` pour un retour à la ligne ;
- `<strong>` pour ce qu'il ne faut pas manquer, `<em>` pour une nuance,
  `<u>` pour un souligné ;
- `<ul><li>` pour une énumération, `<ol><li>` quand l'ordre ou le nombre
  d'étapes compte ;
- `<blockquote>` pour citer un texte reçu — message, courrier, extrait de
  règlement.

🔴 TU METS EN VALEUR, ce n'est pas une option. Une description sans aucune mise
en valeur n'est pas une proposition aboutie : le résident doit trouver en un
coup d'œil ce qui le concerne. Passe en `<strong>` :

- toute date, heure ou échéance ;
- tout montant ;
- tout lieu de rendez-vous, de dépôt ou d'intervention ;
- toute action attendue du résident, et toute interdiction ;
- toute interruption de service — eau, électricité, ascenseur, chauffage,
  parking — et sa durée.

Mets en valeur la DONNÉE, pas la phrase entière :
« les travaux commenceront le <strong>3 mars</strong> », et non
« <strong>les travaux commenceront le 3 mars</strong> ».

Quand la description porte plusieurs informations pratiques — une date, un lieu,
une consigne —, présente-les en `<ul><li>` plutôt qu'en un paragraphe continu :
une liste se parcourt, un paragraphe se lit en entier.

`<em>` sert aux nuances et aux réserves (« sous réserve de la météo »), `<u>`
au mot qu'il ne faut vraiment pas manquer — et à lui seul.

🔴 La retenue, sans laquelle tout ce qui précède ne vaut rien : ce qui est mis
en valeur reste MINORITAIRE. Moins d'un quart du texte, jamais un paragraphe
entier, rien de souligné qui soit déjà en gras. Si tout est en gras, plus rien
ne ressort et le lecteur ne trouve plus la date.

⚠️ Et si le texte ne porte AUCUNE de ces informations — une annonce purement
informative, sans date, sans montant, sans action attendue —, n'en invente pas
pour avoir quelque chose à mettre en gras. Une description sobre vaut mieux
qu'une mise en valeur mensongère.

N'écris ni titre `<h1>` à `<h6>`, ni tableau, ni Markdown (`**gras**`) : la
barre d'outils de l'éditeur ne sait ni les produire ni les retirer, et l'auteur
ne pourrait pas corriger ta proposition.

Le titre est du texte brut : aucune balise, aucun astérisque.

COMMENTAIRE : LE RAPPEL DE L'AFFAIRE, À LA DEMANDE

Quand la publication est un COMMENTAIRE et que l'auteur demande un rappel du
contexte, commence la description par UNE phrase, et une seule, qui résume
l'affaire — puis enchaîne sur le commentaire lui-même :

    <blockquote>Pour rappel : la porte gauche des boîtes aux lettres ne ferme
    plus depuis le 12 septembre.</blockquote>

- Une phrase au maximum, dans un `<blockquote>`, placée AVANT le reste du
  texte. Deux phrases, ce n'est plus un rappel, c'est un résumé qui noie le
  message.
- Elle se tire de ce que le contexte donne — titre de l'objet, description,
  état — et de rien d'autre. Tu ne sais pas ce qui s'est dit dans le fil : un
  rappel inventé est pire que pas de rappel.
- Si le contexte ne suffit pas à dire de quoi il s'agit, n'écris pas de rappel
  plutôt que d'en fabriquer un.
- Sans demande de l'auteur, aucun rappel : un fil de discussion n'a pas besoin
  qu'on lui répète son sujet à chaque message."""

#: 🔴 Le FORMAT — tenu par le code, jamais par le prompt. `lire_reponse` en
#: dépend : la clé du titre et celle de la description sont celles-ci, et une
#: réponse qui ne les porte pas est un échec lisible, pas un texte tronqué.
FORMAT_REPONSE = """Réponds UNIQUEMENT par un objet JSON, sans texte avant ni après, sans bloc de
code, avec exactement ces deux clés :
{"titre": "<le titre, texte brut, ou null si aucun titre n'est demandé>",
 "description": "<la description, HTML simple>"}"""

#: Ce que l'écran peut envoyer au plus. Un texte au-delà n'est pas une
#: description, et il coûte des jetons pour rien.
MAX_CARACTERES_DESCRIPTION = 20_000
MAX_CARACTERES_CONTEXTE = 500
MAX_CARACTERES_PRECISION = 500


def construire_message(
    *,
    entite: str,
    titre: str | None,
    description: str | None,
    contexte: dict[str, str],
    precision: str | None,
    avec_titre: bool,
) -> str:
    """Le message posé au modèle — la matière, jamais la consigne.

    Chaque élément est ANNONCÉ par son nom : sans cela, le modèle lit une seule
    masse de texte et ne peut pas savoir que « bât. 2 » est un périmètre et non
    une phrase de la description.

    ⚠️ Le contexte est déclaré « à ne pas réécrire » ici aussi, pas seulement
    dans le prompt : le prompt est modifiable, et l'administrateur peut en
    retirer la phrase sans savoir qu'elle protégeait ce point.
    """
    blocs = [f"Nature de la publication : {entite}."]
    if contexte:
        lignes = "\n".join(f"- {k} : {v}" for k, v in contexte.items() if v)
        if lignes:
            blocs.append("Contexte, à comprendre et à ne pas réécrire ni recopier :\n" + lignes)
    if avec_titre:
        blocs.append("Titre actuel :\n" + (titre.strip() if titre and titre.strip() else "(aucun)"))
    else:
        blocs.append('Aucun titre n\'est demandé : réponds avec "titre": null.')
    blocs.append(
        "Description actuelle :\n"
        + (description.strip() if description and description.strip() else "(aucune)")
    )
    if precision and precision.strip():
        blocs.append("Précision demandée par l'auteur pour cette réécriture : " + precision.strip())
    return "\n\n".join(blocs)


_BLOC_CODE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


class ReponseIllisible(ValueError):
    """Le modèle n'a pas rendu le JSON attendu — l'appelant en fait une `ErreurLLM`."""


#: Ce que dit l'écran d'une `ReponseIllisible` changée en `ErreurLLM` — écrit une
#: fois (#2949) : quatre usages le recopiaient (description, fusion, résumé, tarif).
FORMAT_INATTENDU = "Le modèle n'a pas répondu dans le format attendu — réessayez."
#: Le même constat quand le détail de la lecture est montré (règlement, synthèse) :
#: `f"{ILLISIBLE} : {exc}"`.
ILLISIBLE = "Réponse de l'assistant illisible"


def lire_objet(texte: str) -> dict:
    """L'objet JSON que le modèle a rendu — sans rien présumer de ses clés.

    Tolère un bloc de code autour du JSON — beaucoup de modèles en posent un
    malgré la consigne — et du texte parasite avant ou après l'objet. Partagé
    par tout usage qui demande du JSON (`tarif_modele`) : chacun vérifie
    ensuite SES clés, la tolérance sur l'enveloppe ne s'écrit qu'ici.
    """
    brut = (texte or "").strip()
    m = _BLOC_CODE.match(brut)
    if m:
        brut = m.group(1)
    debut, fin = brut.find("{"), brut.rfind("}")
    if debut < 0 or fin <= debut:
        raise ReponseIllisible("Réponse du modèle sans objet JSON.")
    try:
        charge = json.loads(brut[debut : fin + 1])
    except ValueError as exc:
        raise ReponseIllisible("Réponse du modèle illisible — JSON invalide.") from exc
    if not isinstance(charge, dict):
        raise ReponseIllisible("Réponse du modèle sans objet JSON.")
    return charge


def lire_reponse(texte: str) -> dict[str, str | None]:
    """Le titre et la description, relus dans ce que le modèle a rendu.

    Ne tolère PAS un objet sans `description` : c'est la seule clé qui ne peut
    pas manquer, et la remplacer par le texte brut ferait passer une réponse
    en prose pour une proposition.
    """
    charge = lire_objet(texte)
    if not isinstance(charge.get("description"), str):
        raise ReponseIllisible("Réponse du modèle sans description.")
    titre = charge.get("titre")
    if titre is not None and not isinstance(titre, str):
        titre = str(titre)
    return {
        "titre": titre.strip() if isinstance(titre, str) and titre.strip() else None,
        "description": charge["description"].strip(),
    }


def _normaliser(texte: str | None) -> str:
    """Pour dire si un champ a CHANGÉ : les espaces et les fins de ligne ne
    comptent pas, un éditeur riche en ajoute sans que personne les ait tapés."""
    return re.sub(r"\s+", " ", (texte or "")).strip()


def a_change(avant: str | None, apres: str | None) -> bool:
    return _normaliser(avant) != _normaliser(apres)


__all__ = [
    "CONSIGNE_DEFAUT",
    "FORMAT_REPONSE",
    "MAX_CARACTERES_CONTEXTE",
    "MAX_CARACTERES_DESCRIPTION",
    "MAX_CARACTERES_PRECISION",
    "ReponseIllisible",
    "a_change",
    "construire_message",
    "lire_objet",
    "lire_reponse",
]
