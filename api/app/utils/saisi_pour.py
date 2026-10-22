"""**« Saisi pour »** — au nom de qui une entrée est ouverte, et par qui.

## La notion

Le conseil syndical enregistre ce qu'un résident a signalé par téléphone, ou ce
qu'un intervenant extérieur a rapporté. L'**auteur** est alors celui qui a tapé ;
le **propriétaire** est celui que ça concerne.

Trois champs, et ils vont **toujours ensemble** :

| champ | ce qu'il porte |
|---|---|
| `saisi_pour_user_id` | un résident **inscrit** — nom et adresse à jour |
| `saisi_pour_nom` | une personne **extérieure** — ce que le rédacteur a saisi |
| `saisi_pour_email` | son adresse, **facultative** |

## 🔴 Pourquoi ce module (15/09/2026)

La notion vivait dans le seul circuit des tickets, écrite en quatre endroits —
le modèle, la création, la correction, la lecture. La demande de l'étendre aux
**actualités** et aux **événements** en aurait fait douze.

> « As-tu réalisé l'évolution d'ajout de la section “SAISI POUR” aux actualités
>   et Événements ? »

⚠️ Et la logique n'a rien d'évident : elle porte deux distinctions que trois
copies auraient perdues à des moments différents.

1. **Les trois champs voyagent ensemble, y compris à `null`.** C'est leur
   *présence* dans la charge utile qui dit d'écrire (`model_fields_set`), et
   c'est ce qui permet de revenir à « En mon nom » : sans elles, un `None`
   serait indistinguable d'un champ non transmis, et le choix resterait sans
   effet — en silence.
2. **La PRÉSENCE décide d'écrire, la COMPARAISON décide d'annoncer**
   (18/08/2026). Les deux étaient confondues : le formulaire envoyant toujours
   les trois champs, « Saisi pour modifié » apparaissait à chaque
   enregistrement, même quand personne n'y avait touché.

## Ce que ce module ne porte pas

**Qui est le propriétaire** — `utils/copie_auteur.proprietaire()`, déjà
générique : elle lit `saisi_pour_*` par `getattr` et retombe sur l'auteur pour
les objets qui n'en ont pas. Elle n'avait pas besoin de changer, et c'est le
signe qu'elle était juste.

**Qui a le droit** — `auth/deps`. Le filtre `est_cs` ci-dessous n'est pas une
autorisation : c'est la traduction d'une règle métier déjà tranchée par la
dépendance qui protège la route. Un résident qui enverrait ces champs les voit
simplement ignorés.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from sqlmodel import Field, Session, SQLModel

from app.utils.corrections_texte import saisi_pour as saisi_pour_texte


#: Les trois champs, nommés une fois — les parcourir plutôt que les énumérer.
CHAMPS = ("saisi_pour_user_id", "saisi_pour_nom", "saisi_pour_email")


class SaisiPourMixin(SQLModel):
    """Les trois colonnes, héritées plutôt que recopiées.

    ⚠️ **`saisi_pour_user_id` ne déclare PAS `foreign_key` ici**, et ce n'est
    pas un oubli : la base de production porte la colonne sans contrainte. Si le
    modèle la déclarait, une base **neuve** (`create_all`) et la base de
    production porteraient deux schémas différents, et rien ne le dirait.

    `Ticket` **redéclare** ce champ avec sa clé étrangère : sa colonne existe en
    base depuis l'origine, avec la contrainte. Le mixin décrit donc le socle, et
    l'entité qui en sait plus l'enrichit — sans que les trois autres aient à
    connaître ce détail.
    """

    saisi_pour_user_id: Optional[int] = Field(default=None)
    saisi_pour_nom: Optional[str] = None
    saisi_pour_email: Optional[str] = None


def valeurs(body, *, autorise: bool) -> dict:
    """Ce qu'il faut poser à la CRÉATION — les trois champs, ou trois `None`.

    :param autorise: le rédacteur a-t-il le droit de saisir pour autrui (le
        conseil syndical, l'administration) ? Sinon les trois valeurs sont
        ignorées — ce n'est pas le contrôle d'accès, qui vit dans `auth/deps`,
        mais sa traduction sur ces trois champs.
    """
    return {c: (getattr(body, c, None) if autorise else None) for c in CHAMPS}


def nom_saisi(session: Session, objet) -> Optional[str]:
    """La personne NOMMÉE par « Saisi pour », ou `None` si l'objet est à son auteur.

    Distinct de `proprietaire()` : celui-ci retombe sur l'auteur, et une
    correction doit pouvoir dire « de nouveau au nom de son auteur » plutôt que
    de nommer l'auteur comme s'il venait d'être désigné.
    """
    # Import différé — le même cycle que `noms_derives` (modèles ⇄ ce module).
    from app.utils.copie_auteur import proprietaire

    if not (getattr(objet, "saisi_pour_user_id", None) or getattr(objet, "saisi_pour_nom", None)):
        return None
    return proprietaire(session, objet)[0]


def corriger(objet, body, envoye, session: Session) -> list[str]:
    """Applique une CORRECTION, et dit s'il y a lieu de l'annoncer.

    :param envoye: `lambda body, champ: …` — le prédicat de l'appelant qui dit
        si un champ figure dans la charge utile reçue. Il reste chez lui : la
        façon de lire `model_fields_set` dépend du schéma, pas de cette notion.
    :param session: pour NOMMER la personne : la ligne d'historique dit pour qui,
        pas seulement qu'il y a eu un changement.
    :returns: la liste des évolutions à tracer — vide si rien n'a changé.

    🔴 Les deux règles de l'en-tête sont ICI, et nulle part ailleurs : la
    présence décide d'écrire, la comparaison décide d'annoncer.
    """
    if not any(envoye(body, c) for c in CHAMPS):
        return []
    avant = tuple(getattr(objet, c) for c in CHAMPS)
    apres = tuple(getattr(body, c, None) for c in CHAMPS)
    if avant == apres:
        return []
    nom_avant = nom_saisi(session, objet)
    for champ, valeur in zip(CHAMPS, apres):
        setattr(objet, champ, valeur)
    return [saisi_pour_texte(nom_avant, nom_saisi(session, objet))]


def adresse_lisible(objet, lecteur) -> Optional[str]:
    """L'adresse de la personne « saisie pour », telle que CE lecteur la reçoit.

    Le conseil seul la lit — l'écran ne la montre qu'à lui (`CorpsCarteTicket`).
    Elle partait pourtant dans le JSON de toute lecture de l'affaire, si bien que
    tout copropriétaire qui lisait une Panne saisie pour une personne sans compte
    recevait son adresse (22/10/2026, #2140). Une donnée personnelle d'un tiers se
    retient au SERVEUR, pas au rendu. Le nom, lui, est lu de tous : il signe la
    carte (`proprietaire_nom`). L'identifiant d'un résident aussi : il fonde ses
    droits sur l'objet (`peutEditer`).

    Sans lecteur connu, rien : on ne révèle pas à qui l'on ne sait pas.
    """
    # Import différé — `auth.deps` importe les modèles, qui importent ce module.
    from app.auth.deps import est_moderateur

    if lecteur is None or not est_moderateur(lecteur):
        return None
    return getattr(objet, "saisi_pour_email", None)


def noms_derives(session: Session, objet) -> tuple[Optional[str], Optional[str]]:
    """Les **deux** noms dérivés d'un objet, en un seul calcul.

    :returns: `(proprietaire_nom, saisi_pour_affichage)`.

    ## 🔴 Pourquoi les rendre ensemble (21/09/2026, #1104)

    Ils viennent de la MÊME question — « à qui cet objet appartient-il ? » — et
    ne diffèrent que par le cas où personne n'est nommé : le propriétaire
    retombe sur l'auteur, l'affichage reste vide.

    Ils étaient pourtant composés à trois endroits et de deux façons : le ticket
    appelait `proprietaire()` puis en dérivait l'affichage, tandis que
    l'actualité et l'événement appelaient `affichage()`, qui refait le même
    appel. Résultat — **seul le ticket exposait `proprietaire_nom`**, et les
    cartes d'actualité et d'événement n'avaient aucun moyen d'afficher autre
    chose que le rédacteur. C'est la moitié serveur de #1104.

    ⚠️ La nuance entre les deux se lit ici, une fois. La répartir entre trois
    routeurs, c'est trois occasions de l'oublier — et elle l'a été deux fois.
    """
    #  🔴 Import DIFFÉRÉ, et c'est un cycle réel : `copie_auteur` a besoin des
    #  modèles, et les modèles ont besoin du mixin de ce fichier. Le poser en
    #  tête ferait échouer le DÉMARRAGE de l'API, pas un test.
    from app.utils.copie_auteur import proprietaire

    nom, _ = proprietaire(session, objet)
    nomme = bool(
        getattr(objet, "saisi_pour_user_id", None) or getattr(objet, "saisi_pour_nom", None)
    )
    return nom, (nom if nomme else None)


class SaisiPourEntree(BaseModel):
    """Ce qu'un formulaire ENVOIE — hérité par les schémas de création et de
    correction des trois entités.

    ⚠️ **Les trois champs sont `Optional` et sans valeur par défaut autre que
    `None`**, y compris à la création : c'est leur PRÉSENCE dans la charge utile
    qui dit d'écrire (`model_fields_set`), et c'est ce qui permet de revenir à
    « En mon nom ». Un défaut « intelligent » ici rendrait ce retour impossible.
    """

    saisi_pour_user_id: Optional[int] = None
    saisi_pour_nom: Optional[str] = None
    saisi_pour_email: Optional[str] = None


class SaisiPourSortie(BaseModel):
    """Ce qu'un écran REÇOIT — les trois champs, plus le nom déjà composé.

    ⚠️ `saisi_pour_affichage` n'est pas une redite des deux autres : il vaut
    `None` quand personne n'est nommé, là où `proprietaire()` retombe sur
    l'auteur. C'est lui qui décide si l'écran affiche « Saisi pour X » — le
    composer côté client demanderait de relire la règle des trois cas dans
    chaque écran.
    """

    saisi_pour_user_id: Optional[int] = None
    saisi_pour_nom: Optional[str] = None
    saisi_pour_email: Optional[str] = None
    saisi_pour_affichage: Optional[str] = None
    #  🔴 À QUI l'objet appartient — le « Saisi pour » s'il existe, l'auteur
    #  sinon. Déclaré ICI depuis le 21/09/2026 (#1104) : il ne vivait que dans
    #  `TicketRead`, si bien que l'actualité et l'événement ne pouvaient pas
    #  afficher autre chose que leur rédacteur. Les trois héritent déjà de cette
    #  classe — c'est ce qui rend la règle vraie partout d'une seule ligne.
    proprietaire_nom: Optional[str] = None
