"""Le vocabulaire visuel des courriels — chaque notion écrite UNE fois (#959).

## Le cadre commun à tous les fichiers du paquet

Le gabarit commun (`email._wrap_email`) enveloppe chaque contenu : pas de `<html>`
ni de `<body>` dans un modèle, seulement le corps riche. La mise en forme — encarts,
cadre de commentaire, boutons, titres — vient d'ici, jamais d'un `<table>` réécrit
dans `tickets.py` ou `vie_collective.py` : ajouter un paramètre ici.

## Ce que ce module remplace

Un relevé mécanique du 15/09/2026 a trouvé **17 lignes de gabarit écrites à
l'identique** dans plusieurs fichiers de ce paquet — le cadre d'un commentaire,
les encarts, le séparateur, « Bonjour … », la signature du conseil syndical.
`tickets.py` et `vie_collective.py` en partageaient l'essentiel, bordures,
couleurs et espacements au pixel près.

🔴 **Et elles avaient déjà divergé** : DEUX versions du même `<h3>Historique</h3>`
coexistaient — `font-size:13px;color:#8A8FA0` et `font-size:14px;color:#5A6070` —
et les **deux** fichiers portaient les deux. Personne ne compare deux courriels
reçus à trois jours d'écart ; c'est précisément ce qui rend ce genre de dérive
invisible jusqu'à ce qu'on la mesure.

## Des fonctions paramétrées, pas des constantes plates

Dix-sept constantes auraient supprimé la duplication sans nommer la notion. Ici
un **encart** est un encart, et ses variantes sont des paramètres : le fond, la
bordure, la marge. Une famille de plus s'obtient en passant un argument, pas en
recopiant un `<table>` de deux cent cinquante caractères.

C'est ce qui distingue factoriser de découper : on ne déplace pas du texte, on
donne un nom à ce qu'il signifie, et l'appelant hérite du reste.

## ⚠️ La règle qui tient ce module

**Le texte produit ne doit pas bouger d'un caractère.** Les vingt-sept modèles
vivent EN BASE : un octet de différence et il faudrait une migration pour les
réécrire tous (cf. 0192, et le modèle BOUCHON qui a envoyé « Notification. »
pendant des mois). L'identité du rendu est donc vérifiée par
`test_fragments_identiques.py`, qui compare le texte composé ici à l'empreinte
figée de chaque modèle.

Une évolution de style **volontaire** se fait donc ici *et* dans une migration —
jamais ici seul.
"""

from __future__ import annotations

from typing import Optional

# ── La palette de la charte, telle que les gabarits l'emploient ───────────────
#  Elle n'est PAS une seconde définition de `utils/pdf_theme` : les documents
#  imprimables et les courriels ne partagent ni moteur, ni contexte de rendu
#  (WeasyPrint hors requête d'un côté, HTML en ligne chez un client de
#  messagerie de l'autre). Ce sont les mêmes valeurs, employées par deux
#  chaînes qui n'ont aucun fichier en commun — et un client de messagerie
#  n'accepte que du style en ligne.
BLEU = "#1E3A5F"
BLEU_CLAIR = "#EEF2F7"
CREME = "#F2EFE9"
BLANC = "#FFFFFF"
BORD = "#D0D8E4"
OR = "#C9983A"
TEXTE = "#1A1A2E"
GRIS = "#5A6070"
GRIS_CLAIR = "#8A8FA0"

BORDURE_FINE = f"1px solid {BORD}"
BORDURE_ACCENT = f"2px solid {BLEU}"

#: La marge d'un encart qui se resserre quand il suit un commentaire. Elle était
#: écrite telle quelle dans les deux fichiers — un `{% if %}` recopié est un
#: `{% if %}` qui se corrige à moitié.
MARGE_SELON_COMMENTAIRE = "0 0 {% if is_commentaire %}8{% else %}20{% endif %}px"


def encart(
    contenu: str,
    *,
    marge: str = "0 0 20px",
    bordure: str = BORDURE_FINE,
    fond: str = CREME,
    padding: str = "16px",
    filet: Optional[str] = None,
    style_cellule: str = "",
) -> str:
    """Le cadre arrondi qui porte un contenu — la brique la plus employée.

    `role="presentation"` est ce qui empêche un lecteur d'écran d'annoncer « tableau
    de 1 ligne, 1 colonne » : la mise en page en tableau est imposée par les
    clients de messagerie, elle n'a aucun sens pour qui écoute.

    :param filet: la couleur d'un liseré à gauche, quand l'encart doit accrocher
        l'œil sans changer de fond (l'annonce de hall emploie l'or de la charte).
    :param style_cellule: du style ajouté tel quel à la cellule — la porte de
        sortie pour ce qui dépend d'une **condition Jinja**, comme le liseré
        rouge d'un ticket urgent, qui n'est pas une couleur mais un
        `{% if urgent %}`. Réservé à ce cas : une couleur fixe passe par
        `filet`, qui dit ce qu'elle est.
    """
    liseré = f";border-left:4px solid {filet}" if filet else ""
    return (
        f'<table role="presentation" style="width:100%;margin:{marge};'
        f'border:{bordure};border-radius:8px;overflow:hidden"><tr>'
        f'<td style="background:{fond};padding:{padding}{liseré}{style_cellule}">'
        f"{contenu}"
        "</td></tr></table>"
    )


def titre(contenu: str, *, couleur: str = BLEU) -> str:
    """Le titre d'ouverture du message. Georgia : la serif de la charte.

    :param couleur: le bleu de la charte, sauf pour ce qui alerte — le
        signalement de bug ouvre en rouge, et c'est la seule exception.
    """
    return (
        f'<h2 style="margin:0 0 16px;font-family:Georgia,serif;'
        f'font-size:20px;color:{couleur}">{contenu}</h2>'
    )


def bouton(href: str, libelle: str, *, marge: str = "0", fond: str = BLEU) -> str:
    """L'appel à l'action, centré.

    ⚠️ Toujours un `<a>` stylé, jamais un `<button>` : un client de messagerie
    n'exécute rien, et un bouton sans formulaire n'est pas cliquable.
    """
    return (
        f'<p style="text-align:center;margin:{marge}">'
        f'<a href="{href}" style="display:inline-block;background:{fond};'
        f"color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;"
        f'border-radius:6px;text-decoration:none">{libelle}</a></p>'
    )


#: La marge du bouton qui suit un commentaire — même raison que
#: `MARGE_SELON_COMMENTAIRE`, et elle était recopiée dans les deux fichiers.
MARGE_BOUTON_SELON_COMMENTAIRE = "{% if is_commentaire %}16{% else %}0{% endif %}px 0 0"


def ligne_auteur(
    variable: str = "auteur.affiche",
    date: str = "date_commentaire",
    *,
    perimetre: Optional[str] = None,
    petite: bool = False,
) -> str:
    """« Qui, et quand » — la ligne qui coiffe tout contenu rédigé par quelqu'un.

    :param perimetre: la variable qui porte le périmètre du commentaire, si ce
        type d'objet en a un. **Un ticket en a un, une publication non** :
        `TicketEvolution` porte `perimetre_cible`, `PublicationEvolution` n'a
        aucun champ de périmètre. Ce n'est donc pas une divergence entre deux
        copies — c'est une différence de modèle, et le paramètre la rend
        explicite au lieu de la laisser deviner.
    :param petite: le rendu discret des entrées d'historique (12px, gris clair),
        par opposition à celui du commentaire courant (13px, semi-gras).
    """
    suffixe = (
        "{%% if %s %%} — 🔹 {{ %s }}{%% endif %%}" % (perimetre, perimetre) if perimetre else ""
    )
    if petite:
        return (
            f'<p style="margin:0 0 4px;font-size:12px;color:{GRIS_CLAIR}">'
            f"{{{{ {variable} }}}} — {{{{ {date} }}}}{suffixe}</p>"
        )
    return (
        f'<p style="margin:0 0 6px;font-size:13px;color:{GRIS};font-weight:600">'
        f"{{{{ {variable} }}}} — {{{{ {date} }}}}{suffixe}</p>"
    )


def contenu_riche(variable: str) -> str:
    """Le corps d'un message, rendu tel quel.

    🔴 Ce commentaire disait : *« `| safe` est sans danger ici, le texte est
    assaini à l'écriture côté front »*. C'était faux (#2150) : l'API
    n'assainissait rien, et n'importe quel compte peut l'appeler sans l'écran.
    Dans un courriel, `| safe` ASSAINIT désormais (`utils/html_sur.filtre_safe`,
    branché par `utils/email/rendu`) — y compris dans un modèle réécrit depuis
    Admin → Emails.
    """
    return f'<div style="font-size:14px;color:{TEXTE}">{{{{ {variable} | safe }}}}</div>'


def mention_pieces_jointes(*, voir: bool = False) -> str:
    """« Il y a des pièces jointes » — sous garde, car il n'y en a pas toujours.

    Les deux formulations existaient (« disponibles ci-dessous » et « Voir les
    pièces jointes ci-dessous ») ; elles sont conservées telles quelles, le
    texte d'un modèle en base ne pouvant pas changer sans migration.
    """
    phrase = (
        "📎 Voir les pièces jointes ci-dessous."
        if voir
        else "📎 Pièces jointes disponibles ci-dessous."
    )
    return (
        "{% if fichiers %}"
        f'<p style="margin:8px 0 0;font-size:13px;color:{GRIS}">{phrase}</p>'
        "{% endif %}"
    )


def cadre_commentaire(*, perimetre: Optional[str] = None, voir_pj: bool = False) -> str:
    """Le commentaire qui MOTIVE l'envoi — encart accentué, en tête du message.

    C'est le bloc qui était recopié à l'identique entre `tickets.py` et
    `vie_collective.py`, au pixel près, à la seule différence du périmètre.
    """
    return encart(
        ligne_auteur(perimetre=perimetre)
        + contenu_riche("commentaire")
        + mention_pieces_jointes(voir=voir_pj),
        bordure=BORDURE_ACCENT,
        fond=BLEU_CLAIR,
    )


def entree_historique(prefixe: str, *, perimetre: Optional[str] = None) -> str:
    """Une entrée du fil, dans sa boîte compacte — le corps d'une boucle `{% for %}`.

    :param prefixe: la variable de boucle (`m` pour un message de ticket, `e`
        pour une évolution de publication).
    """
    return encart(
        ligne_auteur(f"{prefixe}.auteur_nom", f"{prefixe}.date", perimetre=perimetre, petite=True)
        + contenu_riche(f"{prefixe}.contenu"),
        marge="0 0 8px",
        fond=BLANC,
        padding="12px 16px",
    )


#: 🔴 DEUX versions de ce titre coexistaient, et les deux fichiers portaient les
#: deux. Elles sont conservées **distinctes et nommées** : les fondre changerait
#: le texte de modèles déjà en base, donc exigerait une migration — et ce lot
#: s'interdit de toucher au rendu. Les nommer rend au moins le choix conscient,
#: et la prochaine correction de style saura qu'il y en a deux à traiter.
HISTORIQUE_DISCRET = (
    f'<h3 style="margin:0 0 12px;font-size:13px;font-weight:600;color:{GRIS_CLAIR};'
    'text-transform:uppercase;letter-spacing:.5px">Historique</h3>'
)
HISTORIQUE_SOBRE = (
    f'<h3 style="margin:0 0 12px;font-size:14px;font-weight:600;color:{GRIS};'
    'text-transform:uppercase;letter-spacing:.5px">Historique</h3>'
)
HISTORIQUE_TITRE = f'<h3 style="margin:0 0 8px;font-size:15px;color:{BLEU}">Historique</h3>'

#: L'adresse au destinataire. ⚠️ Le PRÉNOM seul, jamais `nom_affiche` : ici on
#: s'adresse à quelqu'un, on ne l'identifie pas — « Bonjour DUPONT » crierait.
#: C'est la distinction posée par `utils/noms` (#959).
BONJOUR = '<p style="margin:0 0 12px">Bonjour {{ destinataire.prenom }},</p>'
BONJOUR_LARGE = '<p style="margin:0 0 16px">Bonjour {{ destinataire.prenom }},</p>'

SEPARATEUR = f'<hr style="border:none;border-top:1px solid {BORD};margin:20px 0 16px">'

#: Le pied de message, en petit et centré.
PIED_OUVRE = f'<p style="margin:0;font-size:13px;color:{GRIS};text-align:center">'
SIGNATURE_CS = (
    "Ce message vous a été transmis par le Conseil Syndical de la copropriété "
    "<strong>{{ residence.nom }}</strong>.</p>"
)
