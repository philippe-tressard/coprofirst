"""Modèles des courriels ENTRANTS — répondre à un ticket par e-mail (#703).

Extrait de `core.py` le 03/09/2026, pour la raison écrite dans
`models/__init__.py` : ce fichier dépasse largement 500 lignes, et la règle de
modularité (rang 1) refuse qu'il grossisse pour une nouvelle fonctionnalité. Le
contrôle l'a refusé, à juste titre.

⚠️ Ce n'est pas un découpage arbitraire : la réception de courriels est un
domaine à part — `utils/courriel_entrant`, `utils/courriel_ingestion`,
`utils/courriel_boite` — et son modèle n'a pas plus sa place dans le « cœur » que
sa décision.
"""

from app.utils import horloge
from typing import Optional

from sqlmodel import Field, SQLModel
from pydantic import NaiveDatetime


class RelanceCourriel(SQLModel, table=True):
    """Un envoi de relance groupée au syndic, et les tickets qu'il portait.

    🔴 La relance est un envoi **groupé** : un seul message pour N dossiers, donc
    aucun jeton de ticket — et la réponse du syndic arrivait dans la boîte sans
    rien pour la rattacher. Ignorée EN SILENCE : le seul cas où l'on perdait une
    information qu'on avait soi-même sollicitée.

    ⚠️ Elle ne se VENTILE PAS dans les fils. « Pour le TK-123 on intervient
    jeudi, le TK-456 est clos » recopié dans quatre fils serait faux dans trois
    d'entre eux ; aucune machine ne peut décider quelle phrase vise quel dossier.
    Elle va au conseil syndical, avec la liste des dossiers concernés.

    Le jeton **ne s'épuise pas** : le syndic peut répondre plusieurs fois — un
    message par dossier, une précision le lendemain —, chaque réponse retrouve la
    même relance et produit sa propre notification.

    Le pourquoi complet est dans la migration 0172.
    """

    __tablename__ = "relance_courriel"

    id: Optional[int] = Field(default=None, primary_key=True)
    #: Même forme et même tirage que `Ticket.jeton_courriel` — 128 bits, donc
    #: jamais en collision : le jeton dit à lui seul de quoi il parle, et on
    #: cherche dans les deux tables sans avoir besoin d'un préfixe distinct.
    jeton: str = Field(index=True, unique=True)
    #: Les tickets relancés, en JSON. Figée à l'envoi : elle dit ce que le
    #: message CONTENAIT, pas ce que les tickets sont devenus.
    tickets_json: str = "[]"
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)


class ReponseRelance(SQLModel, table=True):
    """Une réponse du syndic à une relance groupée — CONSERVÉE, pas seulement notifiée.

    🔴 POURQUOI CETTE TABLE EXISTE (04/09/2026), et c'est une correction.

    La première version se contentait d'une notification portant le texte. Elle
    répondait à « le conseil est-il prévenu ? » et pas à « où le relit-on ? ».
    Une notification se lit une fois puis descend dans la pile ; passé quelques
    jours, la réponse du syndic était en base — dans un champ `corps` — et
    introuvable.

    ⚠️ C'est le défaut même que tout ce lot prétendait corriger : *« une réponse
    arrive et personne ne la voit »*. Je l'avais déplacé de la boîte aux lettres
    vers une table de notifications, ce qui n'est pas la même chose que le
    résoudre. Relevé à l'écran : *« où sera affiché le retour syndic ? »*.

    Elle s'affiche désormais sous la relance qui l'a provoquée — Espace CS →
    Reporting → Relance syndic —, là où le conseil regarde déjà.

    ⚠️ Plusieurs réponses par relance : le jeton ne s'épuise pas. Le syndic peut
    répondre un dossier à la fois, ou préciser le lendemain. Chaque réponse est
    une ligne, jamais un écrasement de la précédente.
    """

    __tablename__ = "reponse_relance"

    id: Optional[int] = Field(default=None, primary_key=True)
    relance_id: int = Field(index=True)
    #: L'adresse telle qu'elle figurait dans le `From:` — après quoi
    #: l'authentification a été vérifiée. On conserve la forme brute : c'est ce
    #: qu'un humain reconnaît, et le nom affiché fait partie de l'information.
    expediteur: str = ""
    #: Le texte SANS la citation du message précédent : sans quoi chaque échange
    #: recopierait tout l'échange.
    contenu: str = ""
    recue_le: NaiveDatetime = Field(default_factory=horloge.maintenant)


class CourrielReleve(SQLModel, table=True):
    r"""Un message relevé dans la boîte des réponses, et ce qu'on en a fait (#1447).

    🔴 Le 28/09/2026, un message a été IGNORÉ sans qu'on puisse dire pourquoi :
    la relève ne gardait que des totaux, dans un journal de conteneur que deux
    MEP le même jour avaient effacé. Chaque verdict de `courriel_boite.traiter`
    laisse désormais sa ligne, écrite dans la MÊME transaction que lui — un
    message acquitté (`\Seen`) a donc toujours la sienne.

    ⚠️ Jamais le corps du message : accepté, il vit dans le fil de l'affaire ;
    refusé ou ignoré, il reste dans la boîte. L'adresse de l'expéditeur est une
    donnée personnelle : la ligne se purge (`courriel_journal`), et la politique
    de confidentialité le dit.
    """

    __tablename__ = "courriel_releve"

    id: Optional[int] = Field(default=None, primary_key=True)
    releve_le: NaiveDatetime = Field(default_factory=horloge.maintenant, index=True)
    #: La date d'ENVOI déclarée par le message (`Date:`), quand elle se lit.
    envoye_le: Optional[NaiveDatetime] = None
    #: Le `From:` tel quel — le nom affiché fait partie de ce qu'on reconnaît.
    expediteur: str = ""
    objet: str = ""
    #: `accepte` · `relance` · `refuse` · `ignore` (`courriel_ingestion`).
    decision: str
    #: Pourquoi — écrit pour un humain, jamais vide.
    motif: str
    #: L'affaire visée, sans clé étrangère : la ligne doit survivre à une
    #: affaire supprimée.
    ticket_id: Optional[int] = Field(default=None, index=True)
    affaire: Optional[str] = None


class FilCourriel(SQLModel, table=True):
    """Un fil de courriels transféré par le conseil, et l'affaire où il se verse.

    Demandé le 29/09/2026 : après le premier transfert — repère `TK-…` écrit, ou
    affaire créée —, les suivants du même fil y vont sans repère. Le fil se
    reconnaît à son objet d'origine, normalisé (`courriel_fil.cle_du_fil`).

    ⚠️ Le lien ne vaut que tant que l'affaire est OUVERTE : deux fils sans rapport
    peuvent porter le même objet, et une affaire close ne reçoit plus rien.
    `ticket_id` sans clé étrangère, comme `CourrielReleve` : une affaire supprimée
    laisse un lien mort, que la relève lit comme « pas de lien ».
    """

    __tablename__ = "fil_courriel"

    id: Optional[int] = Field(default=None, primary_key=True)
    cle: str = Field(index=True, unique=True)
    ticket_id: int = Field(index=True)
    mis_a_jour_le: NaiveDatetime = Field(default_factory=horloge.maintenant)


class MessageVerse(SQLModel, table=True):
    """Un message d'un fil transféré, déjà versé dans une affaire (29/09/2026).

    *« Si par erreur je renvoie une extraction ayant déjà été faite, alors elle
    n'est pas doublée »* : chaque message versé laisse son EMPREINTE
    (`courriel_fil.empreinte` — auteur et texte normalisé, jamais le texte).
    """

    __tablename__ = "message_verse"

    id: Optional[int] = Field(default=None, primary_key=True)
    ticket_id: int = Field(index=True)
    empreinte: str = Field(index=True)
    verse_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    #: Le transfert qui l'a versé, et la Suite qu'il est devenu (#1482) —
    #: `None` pour un message écarté, et pour celui qui DÉCRIT l'affaire créée.
    #: Colonnes simples, sans clé étrangère : 0239.
    versement_id: Optional[int] = Field(default=None, index=True)
    evolution_id: Optional[int] = None


class VersementCourriel(SQLModel, table=True):
    """Un transfert VERSÉ dans une affaire — et ce qu'il faut pour le défaire (#1482).

    *« En cas d'erreur, annuler ces ajouts en une fois, les réaffecter à une
    autre affaire, ou en créer une nouvelle ? »* (30/09/2026). Rien ne le
    permettait : une Suite ne savait pas de quel transfert elle venait, et le
    texte du courriel n'est pas conservé. Chaque Suite versée porte donc
    `versement_id`, et cette ligne garde ce que le versement a CHANGÉ autour
    d'elles — le statut d'avant, le lien du fil d'avant.

    Les gestes vivent dans `utils/versement_transfert`, leurs droits dans
    `auth/appartenance.exiger_auteur_du_versement`.
    """

    __tablename__ = "versement_courriel"

    id: Optional[int] = Field(default=None, primary_key=True)
    #: L'affaire où ses Suites sont AUJOURD'HUI — elle suit une réaffectation.
    ticket_id: int = Field(index=True)
    transfere_par_id: int
    #: Le versement a créé l'affaire : l'annuler l'archive.
    affaire_creee: bool = False
    #: Le statut de l'affaire avant le versement — une réponse du syndic la
    #: fait passer « En cours ». `None` pour une affaire créée.
    statut_avant: Optional[str] = None
    #: La clé du fil (`FilCourriel.cle`) et l'affaire qu'il désignait AVANT —
    #: `None` : aucun lien. L'annulation le rend tel qu'il était.
    cle_fil: Optional[str] = None
    fil_avant_id: Optional[int] = None
    #: La plus haute Suite du site au moment du versement : une Suite d'un
    #: AUTRE au-delà, et le geste n'est plus proposé (arbitré le 30/09/2026).
    seuil_evolution_id: int = 0
    #: L'objet d'origine — le titre d'une affaire qu'on en détache.
    objet: str = ""
    #: L'auteur du premier message versé : « Au nom de » d'une affaire qu'on
    #: en détache, comme à la création (`courriel_transfert._creer_affaire`).
    premier_nom: Optional[str] = None
    premier_adresse: Optional[str] = None
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    annule_le: Optional[NaiveDatetime] = None
    #: Confirmé au bon endroit (13/10/2026) : il ne s'offre plus au geste et
    #: quitte la liste. Colonnes simples, sans clé étrangère : 0286.
    valide_le: Optional[NaiveDatetime] = None
    valide_par_id: Optional[int] = None
