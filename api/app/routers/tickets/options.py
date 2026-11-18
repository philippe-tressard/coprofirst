"""Les options d'un ticket — ce que pose la case, et qui a le droit de la cocher.

Extrait de `commun.py` le 10/10/2026, que la case « Activer le suivi » d'une
actualité faisait passer au-dessus du plafond de modularité (rang 1,
`standards/02` §6). La table et les deux sens du pont — écrire, relire — partent
ensemble : séparés, l'un oublierait l'option que l'autre porte. `commun.py` les
ré-exporte.
"""

from app.models.core import Ticket
from app.utils.suivi_actualite import poser_suivi
from app.utils.valeurs import valeur


#: Les options de publication d'un ticket, et la colonne que chacune pilote.
#:
#: 🔴 **Une écriture, trois chemins.** La création, la correction (`PATCH`) et le
#: commentaire portent tous les trois ces options depuis le 05/09/2026, demandé à
#: l'écran :
#:
#: > « tous les autres options de publication doivent être aussi conservé dans
#: >   l'objet pour les tickets en édition et commentaire »
#:
#: Écrite trois fois, la règle aurait divergé au premier ajout — c'est ce qui
#: était arrivé aux destinataires (quatre copies, cf. l'en-tête de ce module).
#:
#: ⚠️ **Les clés ne sont pas les colonnes**, et c'est voulu :
#:
#: | Option (écran) | Ce qu'elle écrit |
#: |---|---|
#: | `epingle` | `ticket.epingle` |
#: | `urgente` | `ticket.priorite` — `haute` / `normale`, ce que fait déjà la catégorie « Urgence » |
#: | `confidentiel` | `ticket.confidentiel` (🛡️ « au seul conseil syndical ») |
#:
#: Il n'y a pas de quatrième ligne pour 🔒 « visible du seul périmètre » : un
#: ticket l'est DÉJÀ (`ticket_visible` n'ouvre pas à la copropriété, #339).
#: | `suivi_kanban` | `ticket.suivi_kanban` — le ticket paraît au tableau (#833) |
#: | `suivre_actualite` | `ticket.suivi_actualite` — « ouvert » coché, vide décoché (10/10/2026) |
OPTIONS_TICKET = ("epingle", "urgente", "confidentiel", "suivi_kanban", "suivre_actualite")

#: Les options qui appartiennent au CONSEIL, pas à l'auteur.
#:
#: `confidentiel` décide qui a le droit de lire — un auteur corrige son texte, il
#: ne décide pas de son audience (#710). `epingle` ordonne la liste du conseil.
#:
#: 🔴 `urgente` EN EST SORTIE le 07/09/2026, et c'est la réparation d'une
#: régression que j'avais livrée le matin même.
#:
#: La catégorie « Urgence » a été retirée (migration 0177) au profit de cette
#: option — sauf que la catégorie était ouverte à TOUT LE MONDE et que l'option
#: était réservée au conseil. Un résident face à une inondation ne pouvait donc
#: plus dire que ça pressait : ni case à l'écran, ni acceptation côté serveur.
#: Le conseil n'était plus prévenu en urgence, l'avertissement « 15 · 17 · 18 »
#: ne s'affichait plus, et le message WhatsApp partait en ordinaire.
#:
#: ⚠️ Le motif écrit ici disait « épingler et marquer urgent ordonnent la liste
#: du conseil : même nature ». C'était vrai TANT QUE la catégorie portait le
#: signalement en parallèle. En retirant la catégorie, j'ai fait de cette option
#: le seul moyen de décrire sa propre situation — et une description de sa
#: situation appartient à l'auteur, pas au conseil.
#:
#: Le risque d'abus est réel mais il n'est pas NOUVEAU : la catégorie
#: « Urgence » était cochable par n'importe qui depuis toujours. On ne fait que
#: rendre ce qui existait.
#: 🔴 `suivi_kanban` y entre (08/09/2026) : le tableau ordonne le TRAVAIL du
#: conseil, comme l'épinglage ordonne sa liste. Un résident décrit sa situation
#: — c'est le sens d'`urgente` —, il n'inscrit pas une carte au tableau de suivi
#: de quelqu'un d'autre.
#: `suivre_actualite` aussi (10/10/2026) : « activable uniquement par le CS ».
OPTIONS_RESERVEES_AU_CS = ("epingle", "confidentiel", "suivi_kanban", "suivre_actualite")


def appliquer_options(ticket: Ticket, body, *, est_cs: bool) -> list[str]:
    """Pose sur le ticket les options que `body` déclare. Rend celles qui ont changé.

    `None` veut dire « ce corps ne dit rien de cette option » : le ticket garde
    la sienne. C'est la même convention que `perimetre_cible`, et c'est elle qui
    permet au même code de servir un `POST` complet et un commentaire qui ne
    touche qu'une case.

    ⚠️ **Le contrôle de droit est ICI**, pas dans les trois appelants : une règle
    d'autorisation recopiée ne se durcit pas, on en corrige deux sur trois
    (`standards/03-securite.md` §1). Un non-CS qui envoie ces champs les voit
    simplement ignorés — l'écran ne les lui propose pas.
    """
    changees: list[str] = []
    for option in OPTIONS_TICKET:
        demande = getattr(body, option, None)
        if demande is None:
            continue
        if option in OPTIONS_RESERVEES_AU_CS and not est_cs:
            continue
        if option == "urgente":
            #  Pas de colonne `urgente` : l'urgence d'un ticket EST sa priorité.
            nouvelle = "haute" if demande else "normale"
            #  `valeur`, jamais `str` : relue de la base, la priorité est une
            #  énumération, et `str` rendait « PrioriteTicket.haute » — le geste ⚡
            #  passait pour changé à chaque enregistrement (#2789).
            if valeur(ticket.priorite) != nouvelle:
                ticket.priorite = nouvelle
                changees.append(option)
            continue
        if option == "suivre_actualite":
            #  Pas de colonne booléenne : la case pose l'ÉTAT du suivi, et la
            #  décocher l'efface (`utils/suivi_actualite`).
            if poser_suivi(ticket, demande):
                changees.append(option)
            continue
        if getattr(ticket, option) != demande:
            setattr(ticket, option, demande)
            changees.append(option)
    return changees


def options_du_ticket(ticket: Ticket) -> dict[str, bool]:
    """L'état courant des options — ce que l'écran doit REPRENDRE à l'ouverture.

    Le pendant en lecture d'`appliquer_options` : les deux sens de la même table,
    au même endroit, pour qu'aucun ne puisse oublier une option que l'autre écrit.
    """
    return {
        "epingle": bool(ticket.epingle),
        "urgente": valeur(ticket.priorite) == "haute",
        "confidentiel": bool(ticket.confidentiel),
        "suivi_kanban": bool(ticket.suivi_kanban),
        "suivre_actualite": bool(ticket.suivi_actualite),
    }
