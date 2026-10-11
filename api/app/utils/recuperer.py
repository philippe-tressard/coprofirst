"""**Récupérer une entité, ou dire qu'elle n'existe pas.**

## 🔴 Pourquoi ce module (15/09/2026)

Un relevé mécanique a compté **90 occurrences** de ces trois lignes, dans
**37 fichiers** :

    objet = session.get(Modele, objet_id)
    if not objet:
        raise HTTPException(404, "Chose introuvable")

C'est la duplication la plus répandue du dépôt. Aucune de ces écritures n'est
fausse ; c'est leur nombre qui pose problème — le jour où l'on veut y ajouter
quelque chose (une trace, une distinction entre « supprimé » et « jamais
existé », un identifiant dans le message), il faut le faire quatre-vingt-dix
fois, et on en manquera.

⚠️ Et elles avaient déjà commencé à diverger sur le LIBELLÉ : neuf
« Utilisateur introuvable », mais aussi « Compte introuvable » ailleurs pour la
même table. Le suffixe est désormais composé ici, donc identique partout.

## Ce que cette fonction NE fait pas

**Elle ne décide d'aucun droit.** Rendre 404 sur un objet qu'on n'a pas le droit
de voir est une décision d'autorisation — elle vit dans `auth/deps` et dans les
fonctions de visibilité, jamais ici. Cette fonction répond à « existe-t-il ? »,
pas à « puis-je le voir ? ».

⚠️ Les deux questions se ressemblent et se confondent vite : un contrôle qui
rendrait 404 « pour ne pas révéler l'existence » relève de la sécurité, et doit
être écrit là où les autres règles d'accès le sont — sinon il y a deux endroits
où lire les droits (`standards/03` §1).
"""

from __future__ import annotations

import os
from typing import Mapping, Optional, Type, TypeVar

from fastapi import HTTPException
from sqlmodel import Session, select

T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")


def ou_404(
    session: Session, modele: Type[T], identifiant, libelle: str, *, sous: Optional[dict] = None
) -> T:
    """L'objet, ou un **404** qui le nomme.

    :param libelle: le nom de l'entité *au singulier*, sans le mot
        « introuvable » — il est composé ici. C'est ce qui garantit que les
        quatre-vingt-dix messages du produit disent la même chose de la même
        façon.
    :param sous: les champs que l'objet doit porter — son PARENT, le plus
        souvent (`{"ticket_id": 7}`) : un objet d'une autre affaire que celle
        de l'adresse se lit comme absent, sinon l'identifiant valide d'un autre
        parent passerait le contrôle d'accès de l'URL (#1482).

    ⚠️ `identifiant` peut valoir `None` — un chemin d'API le donne parfois ainsi.
    `session.get(Modele, None)` rend `None` sans lever : le 404 est alors la
    bonne réponse, et c'est ce qui se passe.
    """
    objet: Optional[T] = session.get(modele, identifiant)
    if not objet or any(getattr(objet, k, None) != v for k, v in (sous or {}).items()):
        raise HTTPException(404, f"{libelle} introuvable")
    return objet


def fichier_ou_404(chemin: Optional[str], libelle: str = "Fichier") -> str:
    """Le chemin d'un fichier **présent sur le disque**, ou un **404** qui le nomme.

    L'enregistrement existe mais son fichier a disparu du volume : la question
    n'est plus « existe-t-il en base ? » (`ou_404`) mais « est-il encore là ? ».
    Écrite quatre fois à la main (documents, diagnostics, compteurs, affiches),
    avec le même message — le jour où l'on veut tracer ces absences, une seule
    ligne à changer (#1571).

    `chemin` peut valoir `None` ou `""` (colonne vide) : le 404 est alors la bonne
    réponse. `isfile`, et non `exists` : un répertoire n'est pas servable.
    """
    if not chemin or not os.path.isfile(chemin):
        raise HTTPException(404, f"{libelle} introuvable sur le serveur")
    return chemin


def premier_ou_404(session: Session, modele: Type[T], detail: str) -> T:
    """La **ligne unique** d'une table de réglage, ou un 404 qui dit `detail`.

    Pour une table qui n'a qu'une ligne (la copropriété) : il n'y a pas
    d'identifiant à passer à `ou_404`, et l'absence veut dire « pas encore
    configurée » plutôt que « introuvable » — d'où le `detail` libre, écrit par
    l'appelant, qui connaît le genre et le mot. Écrit trois fois à l'identique
    dans `copropriete.py` (#1571).
    """
    objet: Optional[T] = session.exec(select(modele)).first()
    if not objet:
        raise HTTPException(404, detail)
    return objet


def connu_ou_404(table: Mapping[K, V], cle: K, detail: str) -> V:
    """La valeur de `cle` dans une **table déclarée**, ou un 404 qui dit `detail`.

    Une adresse qui nomme une entrée d'un registre du code (un type de source
    d'affiche, une section de contrat) : l'entrée inconnue n'existe pas. Écrite
    deux fois à la main (#1571). ⚠️ Pas pour une liste blanche d'ACCÈS — celle-là
    décide d'un droit et reste chez la route qui la porte (`compteurs.py`).
    """
    if cle not in table:
        raise HTTPException(404, detail)
    return table[cle]


def present_ou_404(valeur: Optional[T], detail: str) -> T:
    """`valeur`, ou un 404 qui dit `detail` quand elle vaut `None`.

    Pour un résultat que l'appelant a déjà calculé — une requête filtrée, une
    résolution — et dont l'absence se dit en 404. `is None`, jamais un test de
    vérité : un dictionnaire vide ou un 0 sont des résultats. Écrite trois fois
    à la main (#1571).
    """
    if valeur is None:
        raise HTTPException(404, detail)
    return valeur


def ou_rien(session: Session, modele: Type[T], ident: Optional[int]) -> Optional[T]:
    """La ligne `ident` de `modele`, ou `None` — sans rien demander quand `ident` est vide.

    Pour une référence FACULTATIVE, dont l'absence est un cas normal : l'auteur
    d'un contenu dont le compte a été supprimé (#1688, #1821). `session.get` avec
    une clé vide rend `None` mais avertit (« may raise an error in a future
    release ») : quinze lectures d'auteur auraient cassé le jour de la montée.
    """
    return session.get(modele, ident) if ident is not None else None


def precharger(session: Session, modele: Type[T], idents) -> list[T]:
    """Charge d'UNE requête les lignes `idents` de `modele` dans la session (#1838).

    `session.get` (et donc `ou_rien`) lit d'abord la carte d'identité de la
    session : une ligne déjà chargée ne coûte plus de requête. Une liste qui
    lirait l'auteur de chaque affaire par `ou_rien` paie donc une requête par
    affaire — sauf si ces auteurs ont été préchargés ici, en une fois. Les
    lectures unitaires restent écrites comme pour un objet seul.

    Les identifiants vides sont ignorés ; un identifiant inconnu ne lève rien
    (`ou_rien` rendra `None`, comme avant).

    🔴 **Garder la liste rendue tant que les lectures durent.** La carte
    d'identité ne retient ses lignes que FAIBLEMENT : une liste jetée aussitôt
    est libérée aussitôt, et chaque `session.get` repart en base — le
    préchargement aurait coûté une requête de plus, sans rien épargner.
    """
    voulus = {i for i in idents if i is not None}
    return list(session.exec(select(modele).where(modele.id.in_(voulus))).all()) if voulus else []


#: La FENÊTRE d'un historique d'exploitation : on ne lit que les derniers
#: rapports. Au-delà, ils n'apprennent plus rien — la santé d'une tâche se lit
#: sur ses dernières exécutions, pas sur un an d'archives.
DERNIERS_RAPPORTS = 10


def derniers_rapports(session: Session, modele: Type[T], combien: int = DERNIERS_RAPPORTS):
    """Les N derniers rapports d'un historique, du plus récent au plus ancien.

    🔴 Écrit **trois fois** avant le 16/09/2026 — courriels, télémétrie,
    sauvegardes —, avec le `10` recopié à chaque fois. Trois écrans lisent la
    même fenêtre ; le jour où l'un l'élargit, les deux autres restent en
    arrière sans que rien ne le dise, et l'administrateur compare des
    profondeurs différentes en croyant comparer des tables.

    ⚠️ Comme `ou_404`, cette fonction **ne décide d'aucun droit** : les trois
    routes qui l'emploient portent `require_admin`, et c'est là que la
    décision se prend.
    """
    return session.exec(select(modele).order_by(modele.cree_le.desc()).limit(combien)).all()
