"""Modèles d'e-mail du circuit des tickets, du signalement à la relance.

C'est le seul circuit qui sort de la copropriété : `ticket_syndic`, `ticket_externe` et `relance_syndic` s'adressent au syndic ou à un tiers, et leur ton engage le conseil syndical. Ils changent quand ce circuit change.

Corps riche seulement, mis en forme par `fragments.py` : voir son en-tête pour le
gabarit commun et la règle « ne pas réécrire un `<table>` ici » (#959, #1564).
"""

from app.seed.emails.fragments import (
    BLEU,
    BORD,
    CREME,
    GRIS,
    GRIS_CLAIR,
    HISTORIQUE_DISCRET,
    HISTORIQUE_SOBRE,
    HISTORIQUE_TITRE,
    MARGE_BOUTON_SELON_COMMENTAIRE,
    MARGE_SELON_COMMENTAIRE,
    PIED_OUVRE,
    SEPARATEUR,
    SIGNATURE_CS,
    TEXTE,
    bouton,
    cadre_commentaire,
    contenu_riche,
    encart,
    entree_historique,
    titre,
)

#: Le rouge des alertes — il ne sert QUE au signalement de bug, et c'est pour
#: cela qu'il n'est pas dans la palette de `fragments` : celle-ci porte la charte
#: du site, pas la couleur d'un cas particulier.
ROUGE = "#c0392b"


#: Le lien vers un ticket, employé par cinq modèles.
def _bouton_ticket(libelle: str = "Consulter l’affaire", **kw) -> str:
    return bouton("{{ app.url }}/tickets/{{ ticket.id }}", libelle, **kw)


#: La ligne de méta d'un ticket — numéro, catégorie, et ce que l'appelant ajoute.
def _meta_ticket(suffixe: str = "") -> str:
    return (
        f'<p style="margin:0 0 4px;font-size:13px;color:{GRIS}">Affaire #{{{{ ticket.numero }}}}'
        "{% if ticket.categorie %} · {{ ticket.categorie }}{% endif %}"
        f"{suffixe}</p>"
    )


#: Le titre d'un ticket dans son encart.
_TITRE_TICKET = f'<p style="margin:0 0 8px;font-weight:700;font-size:16px;color:{BLEU}">{{{{ ticket.titre }}}}</p>'

#: Le fil des messages d'un ticket, sous garde.
#:
#: ⚠️ Le périmètre est passé ICI et pas dans `vie_collective` : un
#: `TicketEvolution` porte `perimetre_cible`, un `PublicationEvolution` n'en a
#: aucun. Différence de modèle, pas divergence de copies (#959).
_FIL_MESSAGES = (
    "{% if is_commentaire and messages %}"
    "{% for m in messages %}" + entree_historique("m", perimetre="m.perimetre") + "{% endfor %}"
    "{% endif %}"
)

#: Le fil des messages SANS périmètre — `ticket_externe` ne le montre pas à un
#: tiers : le découpage interne de la copropriété ne le regarde pas.
_FIL_MESSAGES_EXTERNE = (
    "{% if is_commentaire and messages %}"
    "{% for m in messages %}" + entree_historique("m") + "{% endfor %}"
    "{% endif %}"
)


def _tableau_historique(source: str, *, marge: str = "0 0 20px") -> str:
    """Le tableau du fil d'activité : deux colonnes zébrées, date puis libellé.

    Écrit une fois pour deux emplois — l'historique de l'affaire et celui de
    chaque affaire liée — qui ne diffèrent que par la liste parcourue. Le texte
    produit pour `historique` n'a pas bougé d'un caractère (`test_fragments_identiques`).
    """
    return (
        f'<table role="presentation" style="border-collapse:collapse;width:100%;font-size:.88rem;margin:{marge};border:1px solid {BORD};border-radius:8px;overflow:hidden">'
        "{% for h in " + source + " %}"
        f'<tr style="background:{{% if loop.index is odd %}}{CREME}{{% else %}}#FFFFFF{{% endif %}}">'
        f'<td style="padding:.35rem .75rem;border-bottom:1px solid {BORD};white-space:nowrap;color:{GRIS};font-size:.82rem">{{{{ h.date }}}}</td>'
        f'<td style="padding:.35rem .75rem;border-bottom:1px solid {BORD};color:{TEXTE}">{{{{ h.label }}}}</td>'
        "</tr>{% endfor %}"
        "</table>"
    )


#: Les affaires liées, sous l'historique : chacune avec le sien, de la plus
#: ancienne à la plus récente (l'ordre est celui du contexte, pas du gabarit).
_AFFAIRES_LIEES = (
    "{% if affaires_liees %}"
    f'<h3 style="margin:12px 0 8px;font-size:15px;color:{BLEU}">Affaires liées</h3>'
    "{% for a in affaires_liees %}"
    + encart(
        f'<p style="margin:0 0 4px;font-size:13px;color:{GRIS}">Affaire #{{{{ a.numero }}}} · créée le {{{{ a.date_creation }}}}</p>'
        f'<p style="margin:0 0 8px;font-weight:700;font-size:15px;color:{BLEU}">{{{{ a.titre }}}}</p>'
        + _tableau_historique("a.historique", marge="0"),
        marge="0 0 12px",
    )
    + "{% endfor %}{% endif %}"
)


def _modele_ticket_transmis(
    code: str,
    nom: str,
    objet: str,
    titre_creation: str,
    phrase_creation: str,
    phrase_commentaire: str,
) -> tuple:
    """Une affaire (ou son commentaire) adressée par courriel : `ticket_syndic` et sa copie à l'auteur.

    Même corps, mêmes variables — seuls l'objet, le titre et les deux phrases changent. Le
    second modèle (`ticket_copie_auteur`, 03/10/2026) est celui d'un auteur qui coche
    SEULE la copie : « Affaire transmise au syndic » lui mentait.
    """
    return (
        code,
        nom,
        #  `{{ prefixe_copro }}` ouvre les DEUX branches — il ne manquait qu'à celle
        #  du commentaire, donc un échange sur un ticket déjà transmis arrivait sans
        #  référence. La règle et sa forme unique : `seed/emails/__init__.py`.
        #
        #  Le **titre** passe avant le nom de la résidence : un client de messagerie
        #  n'affiche qu'une soixantaine de caractères, et sur ces quatre
        #  informations, celle que le destinataire ne connaît pas encore est le
        #  titre. La résidence est ce qu'on accepte de perdre.
        objet,
        titre(
            "{% if is_commentaire %}💬 Nouveau commentaire{% else %}"
            + titre_creation
            + "{% endif %}"
        )
        + '<p style="margin:0 0 16px">'
        + "{% if is_commentaire %}"
        + phrase_commentaire
        + "{% else %}"
        + phrase_creation
        + "{% endif %}"
        + "</p>"
        + "{% if is_commentaire %}"
        + cadre_commentaire(perimetre="commentaire_perimetre")
        + HISTORIQUE_DISCRET
        + "{% endif %}"
        + encart(
            _meta_ticket(
                "{% if ticket.perimetre %} · 🔹 {{ ticket.perimetre }}{% endif %}"
                "{% if is_commentaire %} — Soumis le {{ date_creation }}{% endif %}"
            )
            + _TITRE_TICKET
            + "{% if ticket.description %}"
            + contenu_riche("ticket.description")
            + "{% endif %}"
            + f'{{% if not is_commentaire %}}<p style="margin:8px 0 0;font-size:14px;color:{GRIS}">Soumis par {{{{ auteur.affiche }}}}</p>{{% endif %}}',
            marge=MARGE_SELON_COMMENTAIRE,
        )
        + _FIL_MESSAGES
        #  🔴 Le tableau du fil d'activité, réservé à la CRÉATION : sur un
        #  commentaire, l'historique est déjà rendu par les messages ci-dessus.
        #  Sa forme (deux colonnes zébrées) n'est employée QUE là, d'où un encart
        #  écrit ici plutôt qu'un fragment partagé — le factoriser pour un seul
        #  appelant nommerait une notion qui n'existe pas.
        + "{% if not is_commentaire and historique and historique|length > 1 %}"
        + HISTORIQUE_TITRE
        + _tableau_historique("historique")
        + "{% endif %}"
        #  🔴 Les affaires liées, SOUS l'historique — sur une création comme sur un
        #  commentaire (05/10/2026). Elles ont leur bloc et non une ligne de plus :
        #  c'est l'historique de CHACUNE qu'on veut lire, dans l'ordre où les
        #  affaires ont été ouvertes (`historique_courriel`).
        + _AFFAIRES_LIEES
        + _bouton_ticket(marge=MARGE_BOUTON_SELON_COMMENTAIRE),
        True,
    )


MODELES = [
    (
        "ticket_bug_admin",
        "Affaire de type Bug — notification admin site",
        "Bug signalé via les Affaires — {{ ticket.titre }} — {{ residence.nom }}",
        titre("⚠ Bug signalé", couleur=ROUGE)
        + '<p style="margin:0 0 12px">Une affaire de type <strong style="color:#c0392b">Bug</strong> a été soumis par <strong>{{ auteur.affiche }}</strong>{% if auteur.email %} (<a href="mailto:{{ auteur.email }}" style="color:#1E3A5F">{{ auteur.email }}</a>){% endif %}.</p>'
        + encart(
            f'<p style="margin:0 0 4px;font-weight:700;font-size:16px;color:{TEXTE}">{{{{ ticket.titre }}}}</p>'
            f'<p style="margin:0;font-size:14px;color:{GRIS}">{{{{ ticket.description }}}}</p>',
            fond="#FDF0F0",
            filet=ROUGE,
        )
        + _bouton_ticket("Traiter le bug", fond=ROUGE),
        True,
    ),
    _modele_ticket_transmis(
        "ticket_syndic",
        "Affaire transmise au syndic",
        "{% if is_commentaire %}{{ prefixe_copro }}💬 Commentaire — Affaire #{{ ticket.numero }} — {{ ticket.titre }} — {{ residence.nom }}{% else %}{{ prefixe_copro }}Affaire #{{ ticket.numero }} — {{ ticket.titre }} — {{ residence.nom }}{% endif %}",
        "📋 Affaire transmise par le conseil syndical",
        "Une affaire a été transmise à votre attention par le conseil syndical de <strong>{{ residence.nom }}</strong>{% if reference_copro %} — réf. {{ reference_copro }}{% endif %}.",
        "Un nouveau commentaire a été ajouté sur l’affaire <strong>#{{ ticket.numero }} — {{ ticket.titre }}</strong> par {{ auteur.affiche }}{% if reference_copro %} — réf. {{ reference_copro }}{% endif %}.",
    ),
    #  🔴 LA COPIE DE L'AUTEUR, cochée SEULE (03/10/2026). Pas de `prefixe_copro` : le
    #  message ne s'adresse pas au syndic, la référence de copropriété n'a rien à
    #  faire dans l'objet d'un résident. « Information » : rien n'est attendu.
    _modele_ticket_transmis(
        "ticket_copie_auteur",
        "Copie de votre affaire",
        "{% if is_commentaire %}💬 Commentaire — Affaire #{{ ticket.numero }} — {{ ticket.titre }} — {{ residence.nom }}{% else %}Copie de votre affaire #{{ ticket.numero }} — {{ ticket.titre }} — {{ residence.nom }}{% endif %}",
        "📋 Copie de votre affaire",
        "Voici une copie de l’affaire <strong>#{{ ticket.numero }} — {{ ticket.titre }}</strong> qui vous concerne, déposée sur le site de <strong>{{ residence.nom }}</strong>.",
        "Un nouveau commentaire a été ajouté sur l’affaire <strong>#{{ ticket.numero }} — {{ ticket.titre }}</strong> qui vous concerne, par {{ auteur.affiche }}.",
    ),
    (
        "ticket_statut_change",
        "Statut d’affaire modifié",
        "Affaire #{{ ticket.numero }} mise à jour — {{ ticket.titre }} — {{ residence.nom }}",
        titre("Mise à jour de votre affaire")
        + '<p style="margin:0 0 12px">Bonjour {{ destinataire.prenom }},</p>'
        + '<p style="margin:0 0 16px">Le statut de votre affaire a été mis à jour :</p>'
        + encart(
            f'<p style="margin:0 0 4px;font-size:13px;color:{GRIS}">Affaire #{{{{ ticket.numero }}}}</p>'
            + _TITRE_TICKET
            + '<p style="margin:0"><span style="display:inline-block;background:#3D6B4F;color:#fff;padding:4px 12px;border-radius:4px;font-size:13px;font-weight:600">{{ ticket.statut }}</span></p>'
        ),
        True,
    ),
    #  🔴 LE CS N’ÉTAIT PAS PRÉVENU PAR COURRIEL (08/09/2026, demandé à l’écran).
    #
    #  `_notifier_cs_creation` ne posait qu’une notification DANS l’application,
    #  et sa docstring le disait. Un conseiller qui n’ouvre pas le site ne voyait
    #  donc jamais passer un signalement — et c’est le seul moment où quelqu’un
    #  attend une réaction.
    #
    #  ⚠️ Il vise le CS du PÉRIMÈTRE, pas tout le conseil : la notification in-app
    #  allait à tout le monde, ce qui est tolérable dans une liste et ne l’est pas
    #  dans une boîte aux lettres. `membres_cs_notifiables(session, batiments)` est
    #  la fonction prévue pour ça (cf. le tableau « Destinataires CS » de CLAUDE.md).
    (
        "ticket_nouveau_cs",
        "Nouvelle affaire — notification du conseil syndical",
        "🎫 Affaire #{{ ticket.numero }} — {{ ticket.titre }} — {{ residence.nom }}",
        titre("🎫 Nouvelle affaire") + '<p style="margin:0 0 16px">Une affaire vient d'
        "'"
        "être déposé par <strong>{{ auteur.affiche }}</strong>.</p>"
        + encart(
            _meta_ticket(
                "{% if ticket.perimetre %} · 🔹 {{ ticket.perimetre }}{% endif %}"
                '{% if urgent %} · <strong style="color:#c0392b">URGENT</strong>{% endif %}'
            )
            + _TITRE_TICKET
            + "{% if ticket.description %}"
            + contenu_riche("ticket.description")
            + "{% endif %}",
            #  Le liseré rouge dépend d'une CONDITION, pas d'une couleur : il ne peut
            #  donc pas passer par `filet`, qui attend une valeur.
            style_cellule="{% if urgent %};border-left:4px solid #c0392b{% endif %}",
        )
        + _bouton_ticket(),
        True,
    ),
    (
        "ticket_nouveau_message",
        "Nouveau message sur une affaire",
        "Nouveau message — Affaire #{{ ticket.numero }} — {{ ticket.titre }} — {{ residence.nom }}",
        titre("💬 Nouveau message sur votre affaire")
        + '<p style="margin:0 0 16px">Un nouveau message a été ajouté sur l’affaire <strong>#{{ ticket.numero }} — {{ ticket.titre }}</strong> par {{ auteur_action.affiche }} :</p>'
        + encart(f'<p style="margin:0;font-size:14px;color:{TEXTE}">{{{{ message.contenu }}}}</p>')
        + _bouton_ticket("Voir l’affaire"),
        True,
    ),
    (
        "relance_syndic",
        "Relance des affaires syndic non résolues",
        "{{ prefixe_copro }}Relance d’affaire(s) sans avancée depuis {{ anciennete }}",
        titre("🔔 Relance d’affaire(s) sans avancée depuis {{ anciennete }}")
        + '<p style="margin:0 0 20px">{{ interlocuteurs }},</p>'
        # Préambule partenarial (choisi le 01/08/2026) : poser l’ancienneté réelle
        # et le mécontentement qu’elle nourrit, sans mettre le gestionnaire en
        # accusation — la relance reste un outil de travail, pas un grief.
        + '<p style="margin:0 0 16px">Le Conseil Syndical de la copropriété <strong>{{ residence.nom }}</strong> '
        "se permet de revenir vers vous concernant les affaires ci-dessous, transmises au syndic "
        "et toujours <strong>sans avancée après {{ anciennete }}</strong>.</p>"
        '<p style="margin:0 0 16px">Nous mesurons la charge qui pèse sur la gestion d’un '
        "portefeuille de copropriétés. C’est précisément pour vous éviter des "
        "sollicitations répétées que nous regroupons ici l’ensemble des dossiers "
        "en attente. Leur ancienneté commence toutefois à nourrir un mécontentement "
        "que nous préférerions désamorcer ensemble.</p>"
        '<p style="margin:0 0 20px">Un simple point d’étape, même succinct, sur chacun '
        "d’eux nous permettrait de rassurer les résidents.</p>"
        + "{% for item in tickets %}"
        #  ⚠️ Cet encart ouvre sur `<tr><td …>` en DEUX balises séparées, là où
        #  `encart()` les colle. La différence est invisible au rendu mais pas au
        #  texte, et ces modèles vivent en base : on le laisse tel quel plutôt que
        #  d'exiger une migration pour un espace.
        + f'<table role="presentation" style="width:100%;margin:0 0 24px;border:1px solid {BORD};border-radius:8px;overflow:hidden">'
        f'<tr><td style="background:{CREME};padding:16px">'
        f'<p style="margin:0 0 8px;font-weight:700;font-size:15px;color:{BLEU}">'
        "{{ item.numero }} — {{ item.titre }}"
        "{% if item.relance_count > 0 %}"
        ' <span style="background:#DC2626;color:#fff;font-size:11px;font-weight:700;padding:2px 8px;border-radius:99px;margin-left:8px">'
        #  `relance_count` compte les relances PRÉCÉDENTES : celle qui part est la
        #  suivante. Le modèle disait « n°1 » à la deuxième (#2035, migration 0288).
        "Relance n°{{ item.relance_count + 1 }}</span>"
        "{% else %}"
        ' <span style="background:#F59E0B;color:#fff;font-size:11px;font-weight:700;padding:2px 8px;border-radius:99px;margin-left:8px">'
        "1ère relance</span>"
        "{% endif %}"
        "</p>"
        '<p style="margin:0 0 6px;font-size:12px;color:#4B5563">'
        "Catégorie : {{ item.categorie | capitalize }} · Priorité : {{ item.priorite | capitalize }}"
        "{% if item.perimetre %} · Périmètre : {{ item.perimetre }}{% endif %}"
        "</p>"
        #  Le résumé de l'assistant, quand le conseil l'a fait rédiger depuis le
        #  Suivi des affaires — sinon la description (#2035, migration 0288).
        "{% if item.resume %}"
        '<p style="margin:0 0 10px;font-size:13px;font-weight:600;color:#374151">Point de situation :</p>'
        '<div style="font-size:13px;color:#1A1A2E;white-space:pre-line">{{ item.resume | e }}</div>'
        "{% else %}"
        '<p style="margin:0 0 10px;font-size:13px;font-weight:600;color:#374151">Description :</p>'
        '<div style="font-size:13px;color:#1A1A2E;white-space:pre-line">{{ item.description }}</div>'
        "{% endif %}"
        '<p style="margin:12px 0 6px;font-size:13px;font-weight:600;color:#374151">Historique :</p>'
        '<ul style="margin:0;padding-left:1.2em;font-size:12px;color:#374151">'
        "{% for h in item.historique %}"
        '<li style="margin-bottom:3px">{{ h.date }} — {{ h.label }}</li>'
        "{% endfor %}"
        "</ul>"
        "</td></tr></table>"
        "{% endfor %}"
        '<p style="margin:24px 0 0">Nous vous remercions de bien vouloir nous tenir informés '
        "des actions engagées sur ces dossiers.</p>"
        # Signature sans le nom de la résidence : « Le Conseil Syndical de
        # {{ residence.nom }} » rendait « … de Les Hostachy ». L'article du nom
        # propre ne se contracte pas, et le destinataire sait déjà de quelle
        # copropriété il s'agit — le préambule le dit, l'objet aussi.
         + '<p style="margin:8px 0 0">Cordialement,<br>'
        "<strong>Le Conseil Syndical</strong></p>",
        False,
    ),
    (
        "ticket_externe",
        "Notification d’affaire (email externe)",
        #  Ce canal vise « le syndic ou un tiers » (cf. l'en-tête de ce module) :
        #  l'adresse est saisie à la main et rien ne dit laquelle des deux. Il porte
        #  donc la référence lui aussi — inoffensive pour un prestataire,
        #  indispensable pour le syndic, et c'est la seule façon de tenir « sans
        #  exception » sur un destinataire que le code ne peut pas identifier.
        "{% if is_commentaire %}{{ prefixe_copro }}Relance — Affaire #{{ ticket.numero }} — {{ ticket.titre }}{% else %}{{ prefixe_copro }}Affaire #{{ ticket.numero }} — {{ ticket.titre }}{% endif %}",
        titre(
            "{% if is_commentaire %}💬 Nouveau commentaire{% else %}🔧 Affaire{% endif %} : {{ ticket.titre }}"
        )
        + "{% if is_commentaire %}"
        + cadre_commentaire(voir_pj=True)
        + HISTORIQUE_SOBRE
        + "{% endif %}"
        + encart(
            _meta_ticket(" — {{ date_creation }}")
            + _TITRE_TICKET
            + contenu_riche("ticket.description"),
            marge=MARGE_SELON_COMMENTAIRE,
        )
        + _FIL_MESSAGES_EXTERNE
        + SEPARATEUR
        + PIED_OUVRE
        + SIGNATURE_CS,
        False,
    ),
    #  🔗 Une affaire TRANSMISE par un résident à une adresse qu'il saisit
    #  (#1357, option E des maquettes du 26/09/2026). Titre, numéro et lien —
    #  jamais la description ni les pièces : le destinataire se connecte, et ne
    #  lit l'affaire que s'il en a le droit.
    (
        "ticket_partage",
        "Affaire transmise par un résident",
        "{{ auteur_action.affiche }} vous transmet l’affaire #{{ ticket.numero }} — {{ ticket.titre }}",
        titre("🔗 Une affaire vous est transmise")
        + '<p style="margin:0 0 16px">{{ auteur_action.affiche }} vous transmet l’affaire '
        "<strong>#{{ ticket.numero }} — {{ ticket.titre }}</strong> de la résidence "
        "{{ residence.nom }}.</p>"
        + f'<p style="margin:0 0 20px;font-size:13px;color:{GRIS}">Le lien demande de vous '
        "connecter : vous ne verrez l’affaire que si votre compte peut la lire.</p>"
        + _bouton_ticket("Voir l’affaire"),
        True,
    ),
    #  🔗 Tout AUTRE objet transmis (#1357) : ce qu'il est et le lien, sans titre
    #  — voir `utils/liens.OBJETS_TRANSMISSIBLES`.
    (
        "lien_partage",
        "Lien transmis par un résident",
        "{{ auteur_action.affiche }} vous transmet {{ objet.quoi }} — {{ residence.nom }}",
        titre("🔗 Un lien vous est transmis")
        + '<p style="margin:0 0 16px">{{ auteur_action.affiche }} vous transmet '
        "{{ objet.quoi }} de la résidence {{ residence.nom }}.</p>"
        + f'<p style="margin:0 0 20px;font-size:13px;color:{GRIS}">Le lien demande de vous '
        "connecter : vous ne verrez la page que si votre compte peut la lire.</p>"
        + bouton("{{ app.url }}{{ objet.lien }}", "Ouvrir"),
        True,
    ),
    #  La synthèse d'une affaire close à relire (#1643) — au gestionnaire du site
    #  et au conseil, « le temps que la fonction soit stabilisée ». Un envoi par
    #  production (`synthese_affaire.production.envoyer_avis`).
    (
        "synthese_a_valider",
        "Synthèse d’une affaire close à valider",
        "Synthèse à valider — Affaire #{{ ticket.numero }} — {{ ticket.titre }} — {{ residence.nom }}",
        titre("🧾 Synthèse à valider")
        + '<p style="margin:0 0 16px">L’affaire ci-dessous est {{ issue }}. '
        "{% if synthese.vide %}L’assistant n’a pas pu en rédiger la synthèse : elle est à "
        "rédiger depuis la Suite « Synthèse de l’affaire ».{% else %}Sa synthèse a été "
        "rédigée par l’assistant : relisez-la, modifiez-la ou relancez-la, puis validez-la "
        "pour qu’elle soit lue des copropriétaires et versée au carnet d’entretien."
        "{% endif %}</p>"
        + encart(
            f'<p style="margin:0 0 4px;font-size:13px;color:{GRIS}">Affaire #{{{{ ticket.numero }}}}</p>'
            + _TITRE_TICKET
        )
        + _bouton_ticket("Relire la synthèse"),
        True,
    ),
]

#  `GRIS_CLAIR` est importé pour `entree_historique`, qui s'en sert : le laisser
#  hors de la liste d'import ferait croire qu'il n'est plus employé ici.
_ = GRIS_CLAIR
