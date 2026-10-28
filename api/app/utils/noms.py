"""Comment le nom d'une personne S'AFFICHE — une seule écriture pour tout le site.

## La règle, arbitrée à l'écran le 31/08/2026

> *« L'affichage devrait être Prénom NOM => Nom en majuscule »*

Signalé sur une carte du fil qui rendait **« Jean-Baptiste ForT »** : la casse
telle qu'elle avait été tapée, avec un « T » final resté majuscule. Le prénom
garde sa casse, le nom passe en capitales — c'est l'usage administratif français,
et surtout c'est ce qui rend la lecture homogène quand la saisie ne l'est pas.

## 🔴 Pourquoi une fonction et pas un `f"…"` de plus

`f"{x.prenom} {x.nom}"` est écrit **31 fois** dans `app/`. Chacune est correcte,
et toutes ensemble forment la seule chose qu'on ne peut pas corriger : une règle
d'affichage qui n'existe nulle part. Uniformiser la casse demandait donc trente
et une modifications, dont on aurait manqué au moins une — c'est exactement la
duplication que `standards/02` §2 décrit, sur la notion la plus banale du site.

⚠️ **Ne pas confondre avec `_nom_presentable`** (`utils/destinataires.py`), qui
fait l'INVERSE : « DUPONT » → « Dupont ». Elle sert à s'ADRESSER à quelqu'un —
« Madame Dupont » dans un courriel — où la capitale crierait. Ici on IDENTIFIE
une personne dans une liste. Deux besoins opposés, deux fonctions, et les
confondre donnerait des courriels qui hurlent ou des annuaires illisibles.

## Ce que la fonction ne fait pas

Elle ne touche **ni à la donnée, ni au prénom**. Le nom reste enregistré tel
qu'il a été saisi : c'est un rendu, pas une normalisation. Une particule
(« de La Tour ») passe donc en capitales à l'affichage, ce qui est l'usage.
"""

from __future__ import annotations

from typing import Optional

from app.utils.valeurs import valeur


def nom_affiche(prenom: Optional[str], nom: Optional[str], civilite=None) -> str:
    """« Jean-Baptiste », « ForT » → « Jean-Baptiste FORT ».

    Tolère l'absence de l'un ou de l'autre : une personne dont on ne connaît que
    le nom doit s'afficher quand même, et sans espace en trop.

    `civilite` (« Mr », « Mme »… — `GenreCivilite` ou sa valeur) se place
    devant : « Mr Jean-Baptiste FORT ». C'est la forme de la carte d'un membre
    d'annuaire (`CarteMembre`), reprise par le fil le 09/10/2026 — sans elle,
    un membre saisi sans prénom n'y était plus qu'un nom de famille.
    """
    civilite = (valeur(civilite) or "").strip()
    prenom = (prenom or "").strip()
    nom = (nom or "").strip().upper()
    return " ".join(p for p in (civilite, prenom, nom) if p)


def nom_abrege(prenom: Optional[str], nom: Optional[str]) -> str:
    """« Jean-Baptiste », « fort » → « Jean-Baptiste F. » — la forme PUBLIQUE.

    Celle d'un avis sur l'application (#2075), qui peut paraître sur le site
    vitrine : on y nomme quelqu'un sans l'identifier. L'initiale suit la règle
    d'affichage (capitale), et une personne sans prénom se réduit à son
    initiale plutôt qu'à son nom entier.

    ⚠️ Serveur seul : l'écran reçoit le nom déjà rendu, il ne le compose pas —
    il n'y a donc pas de jumeau dans `#lib/noms.ts`.
    """
    prenom = (prenom or "").strip()
    nom = (nom or "").strip()
    initiale = f"{nom[0].upper()}." if nom else ""
    return " ".join(p for p in (prenom, initiale) if p)


#: Le nom de l'auteur d'un contenu dont le compte a été supprimé (#1688). Le
#: contenu collectif — une affaire, son fil, ses messages — reste, sans nom.
#: Trois replis coexistaient (« ? », « Utilisateur supprimé », vide) : une seule
#: chose à dire, une seule façon de la dire.
ANCIEN_RESIDENT = "Ancien résident"

#: Ce que dit d'un auteur DÉTACHÉ par la conservation des affaires (#2014) la
#: qualité qu'il avait à l'échéance (`auteur_qualite`) : son compte existe peut-être
#: encore, mais l'affaire ne dit plus qui il était.
QUALITES_AUTEUR = {"resident": "Un résident", "conseil": "Le conseil syndical"}


def nom_auteur(auteur, qualite: str | None = None) -> str:
    """Le nom affiché d'un auteur — sa qualité s'il a été détaché d'une affaire
    conservée, « Ancien résident » quand son compte n'existe plus."""
    if auteur:
        return nom_affiche(auteur.prenom, auteur.nom)
    return QUALITES_AUTEUR.get(qualite or "", ANCIEN_RESIDENT)


def contexte_personne(personne, **extras) -> dict:
    """Ce qu'un COURRIEL sait d'une personne — avec le nom **déjà rendu**.

    ## Pourquoi cette fonction existe (#959, 15/09/2026)

    La règle « Prénom NOM » s'appliquait partout **sauf** là où le nom sort de
    l'application et arrive chez quelqu'un : dix-sept points d'envoi passaient
    le nom brut…

        "auteur": {"prenom": user.prenom, "nom": user.nom}

    …et le gabarit Jinja le composait lui-même :

        {{ auteur.prenom }} {{ auteur.nom }}

    Le destinataire lisait donc le nom **tel qu'il a été tapé à l'inscription** —
    « Jean-Baptiste ForT », le défaut arbitré le 31/08/2026, sur la surface la
    plus visible du produit.

    🔴 **Composer dans le gabarit, c'est composer dix-sept fois.** Un gabarit ne
    peut pas appeler `nom_affiche` : il est stocké en base et rendu par Jinja. La
    seule place où la règle peut s'appliquer est donc **ici**, avant l'envoi.

    ## `affiche` s'ajoute, `prenom` et `nom` ne disparaissent pas

    ⚠️ Les modèles sont **administrables** : ils vivent en base, et un gabarit
    personnalisé peut employer `{{ auteur.nom }}`. Retirer la clé le ferait
    échouer à l'envoi — sans erreur visible, exactement le défaut du modèle
    BOUCHON (mémoire `project_modele_email_bouchon`). On ajoute donc une clé,
    on n'en retire aucune.

    Ce sont les gabarits **du dépôt** qui emploient `affiche`, et
    `test_email_templates.py` refuse qu'un seul d'entre eux recompose un nom.

    ## Ne pas confondre avec s'ADRESSER à quelqu'un

    `{{ destinataire.prenom }}` — « Bonjour Jean, » — n'est pas concerné : on ne
    l'identifie pas, on lui parle. C'est la distinction que l'en-tête de ce
    module pose entre `nom_affiche` et `_nom_presentable`, et la respecter est ce
    qui évite des courriels qui hurlent « Bonjour DUPONT ».

    :param extras: les clés propres à ce courriel — `email`, `statut`… Elles
        passent telles quelles : la fonction dit comment un nom s'affiche, pas ce
        qu'un message a le droit de savoir.
    """
    return {
        "prenom": personne.prenom or "",
        "nom": personne.nom or "",
        "affiche": nom_affiche(personne.prenom, personne.nom),
        **extras,
    }
