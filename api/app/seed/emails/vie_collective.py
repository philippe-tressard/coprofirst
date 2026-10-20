"""Modèles d'e-mail de la vie collective : ce qui est publié et partagé.

Publications, calendrier, documents, boîte à idées, annonces de hall. Tous annoncent quelque chose que le destinataire peut aussi voir dans l'application : l'e-mail est un rappel, pas le canal principal.

Corps riche, sans `<html>` ni `<body>` : la mise en forme et sa règle (jamais un
`<table>` réécrit ici) sont dans l'en-tête de `fragments.py` (#959).
"""

from app.seed.emails.fragments import (
    BLEU,
    CREME,
    GRIS,
    HISTORIQUE_DISCRET,
    HISTORIQUE_SOBRE,
    MARGE_BOUTON_SELON_COMMENTAIRE,
    MARGE_SELON_COMMENTAIRE,
    OR,
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

#: Le lien vers le calendrier, employé par la création ET le suivi.
_BOUTON_CALENDRIER = bouton("{{ app.url }}/calendrier", "Voir le calendrier")

#: L'encart qui présente un événement — la date en or, le titre en bleu. Les
#: deux modèles du calendrier le portaient à l'identique.
_ENCART_EVENEMENT = encart(
    f'<p style="margin:0 0 4px;font-size:13px;color:{OR};font-weight:600">{{{{ evenement.date }}}}</p>'
    f'<p style="margin:0;font-weight:700;font-size:16px;color:{BLEU}">{{{{ evenement.titre }}}}</p>'
)


#: Le corps d'une publication dans son encart — commun aux deux modèles qui la
#: transmettent, à la ligne « Publication initiale » près (conditionnelle pour
#: le syndic, toujours présente pour un destinataire externe).
def _encart_publication(*, initiale_conditionnelle: bool) -> str:
    initiale = f'<p style="margin:0 0 4px;font-size:13px;color:{GRIS}">Publication initiale — {{{{ date_publication }}}}</p>'
    if initiale_conditionnelle:
        return encart(
            "{% if is_commentaire %}"
            + initiale
            + "{% endif %}"
            + '<p style="margin:0 0 {% if is_commentaire %}8{% else %}12{% endif %}px;'
            f'font-weight:700;font-size:16px;color:{BLEU}">{{{{ publication.titre }}}}</p>'
            + contenu_riche("publication.contenu"),
            marge=MARGE_SELON_COMMENTAIRE,
        )
    return encart(
        initiale
        + f'<p style="margin:0 0 8px;font-weight:700;font-size:16px;color:{BLEU}">{{{{ publication.titre }}}}</p>'
        + contenu_riche("publication.contenu"),
        marge=MARGE_SELON_COMMENTAIRE,
    )


#: Le fil des évolutions d'une publication, sous garde.
_FIL_EVOLUTIONS = (
    "{% if is_commentaire and evolutions %}"
    "{% for e in evolutions %}" + entree_historique("e") + "{% endfor %}"
    "{% endif %}"
)


def _modele_publication_transmise(
    code: str,
    nom: str,
    objet: str,
    titre_creation: str,
    phrase_creation: str,
    phrase_commentaire: str,
) -> tuple:
    """Une publication (ou son commentaire) adressée par courriel : `publication_syndic` et sa copie à l'auteur.

    Même corps, mêmes variables — seuls l'objet, le titre et les deux phrases changent
    (`publication_copie_auteur`, 03/10/2026 : la copie cochée SEULE).
    """
    return (
        code,
        nom,
        #  Mêmes deux règles que `ticket_syndic`, où elles sont expliquées. Ici la
        #  branche « commentaire » nommait déjà la publication ; c'est celle de la
        #  création qui annonçait « Nouvelle publication » sans dire laquelle.
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
        #  ⚠️ Pas de périmètre ici : `PublicationEvolution` n'en porte AUCUN, là où
        #  `TicketEvolution` a `perimetre_cible`. Ce n'est pas une divergence entre
        #  deux copies — c'est une différence de modèle, et le paramètre absent la
        #  déclare (#959).
        + "{% if is_commentaire %}"
        + cadre_commentaire()
        + HISTORIQUE_DISCRET
        + "{% endif %}"
        + _encart_publication(initiale_conditionnelle=True)
        + _FIL_EVOLUTIONS
        + bouton(
            "{{ app.url }}{{ publication.lien }}",
            "Voir la publication",
            marge=MARGE_BOUTON_SELON_COMMENTAIRE,
        ),
        True,
    )


MODELES = [
    _modele_publication_transmise(
        "publication_syndic",
        "Publication transmise au syndic",
        "{% if is_commentaire %}{{ prefixe_copro }}💬 Commentaire sur «\xa0{{ publication.titre }}\xa0»{% else %}{{ prefixe_copro }}Nouvelle publication — {{ publication.titre }}{% endif %} — {{ residence.nom }}",
        "📢 Publication du conseil syndical",
        "Une publication a été transmise à votre attention par le conseil syndical de <strong>{{ residence.nom }}</strong>{% if reference_copro %} — réf. {{ reference_copro }}{% endif %}.",
        "Un nouveau commentaire a été ajouté sur la publication <strong>{{ publication.titre }}</strong> par {{ auteur.affiche }}{% if reference_copro %} — réf. {{ reference_copro }}{% endif %}.",
    ),
    #  La copie de l'auteur cochée SEULE : pas de référence de copropriété, le
    #  message ne va pas au syndic.
    _modele_publication_transmise(
        "publication_copie_auteur",
        "Copie de votre publication",
        "{% if is_commentaire %}💬 Commentaire sur «\xa0{{ publication.titre }}\xa0»{% else %}Copie de votre publication — {{ publication.titre }}{% endif %} — {{ residence.nom }}",
        "📢 Copie de votre publication",
        "Voici une copie de la publication <strong>{{ publication.titre }}</strong> qui vous concerne, publiée sur le site de <strong>{{ residence.nom }}</strong>.",
        "Un nouveau commentaire a été ajouté sur la publication <strong>{{ publication.titre }}</strong> qui vous concerne, par {{ auteur.affiche }}.",
    ),
    (
        "publication_externe",
        "Notification publication (email externe)",
        #  Même raison que `ticket_externe` : l'adresse est saisie à la main et peut
        #  être celle du syndic.
        "{% if is_commentaire %}{{ prefixe_copro }}Relance {{ publication.titre }}{% else %}{{ prefixe_copro }}{{ publication.titre }} — {{ residence.nom }}{% endif %}",
        titre(
            "{% if is_commentaire %}💬 Nouveau commentaire{% else %}📢 Publication{% endif %} : {{ publication.titre }}"
        )
        + "{% if is_commentaire %}"
        + cadre_commentaire(voir_pj=True)
        #  ⚠️ Le titre « Historique » de ce modèle n'est PAS celui du précédent :
        #  14px/gris contre 13px/gris clair. Les deux existaient déjà, dans les deux
        #  fichiers ; les fondre changerait le texte de modèles en base, donc
        #  exigerait une migration. Nommés distinctement, au moins le choix est vu.
        + HISTORIQUE_SOBRE
        + "{% endif %}"
        + _encart_publication(initiale_conditionnelle=False)
        + _FIL_EVOLUTIONS
        + SEPARATEUR
        + PIED_OUVRE
        + SIGNATURE_CS,
        False,
    ),
    (
        "calendrier_evenement_cree",
        "Événement calendrier créé",
        "Nouvel événement : {{ evenement.titre }} — {{ residence.nom }}",
        titre("📅 Nouvel événement") + _ENCART_EVENEMENT + _BOUTON_CALENDRIER,
        True,
    ),
    #  ⚠️ Modèle du SUIVI, distinct de la création (18/08/2026). Réutiliser
    #  « Nouvel événement » pour un commentaire aurait annoncé une création à
    #  chaque entrée d'Historique — le message aurait été faux, pas seulement
    #  maladroit.
    (
        "calendrier_evenement_suivi",
        "Événement calendrier — suivi",
        "Suivi : {{ evenement.titre }} — {{ residence.nom }}",
        titre("🔄 Suivi d’un événement")
        + _ENCART_EVENEMENT
        + '{% if suivi.etat %}<p style="margin:0 0 12px"><strong>État :</strong> {{ suivi.etat }}</p>{% endif %}'
        '{% if suivi.commentaire %}<div style="margin:0 0 20px">{{ suivi.commentaire|safe }}</div>{% endif %}'
        #  Le pied qui annonce les pieces : meme forme que `ticket_nouveau_message`
        #  et `ticket_externe`. Il manquait ici, et les pieces elles-memes n'etaient
        #  pas attachees (elles l'etaient depuis l'evenement, jamais depuis l'entree)
        #  -- signale a l'ecran le 18/08/2026.
        #  ⚠️ `fichiers` est calcule sur la liste REELLEMENT attachee, jamais sur
        #  l'intention : ce que le courriel annonce doit etre ce qu'il transporte.
        + f'{{% if fichiers %}}<p style="margin:0 0 16px;font-size:13px;color:{GRIS}">📎 Pièces jointes ci-dessous.</p>{{% endif %}}'
        + _BOUTON_CALENDRIER,
        True,
    ),
    (
        "document_publie",
        "Document publié",
        "Nouveau document disponible — {{ residence.nom }}",
        titre("📄 Nouveau document")
        + '<p style="margin:0 0 16px">Un nouveau document a été publié sur l’espace de votre résidence :</p>'
        + encart(
            f'<p style="margin:0;font-weight:700;font-size:16px;color:{BLEU}">{{{{ document.titre }}}}</p>'
            #  La DESCRIPTION sous le titre, quand elle existe (09/09/2026, migration
            #  0185). Le titre NOMME le document, elle dit ce qu'il couvre — sans elle,
            #  le destinataire doit ouvrir le fichier pour savoir s'il le concerne.
            "{% if document.description %}"
            f'<p style="margin:8px 0 0;font-size:14px;color:{GRIS}">{{{{ document.description }}}}</p>'
            "{% endif %}"
        )
        # `/documents` n'a jamais existé côté front : chaque document s'affiche là
        # où il est rattaché. Le bouton menait donc à un 404 — le même que celui
        # signalé depuis un PV d'AG le 26/07/2026, resté ici parce que ce modèle
        # n'était envoyé par personne. Le lien vient de `app/utils/liens.py`.
        #  🔴 Le bouton n'existe QUE s'il mène quelque part (09/09/2026). Sept des
        #  dix catégories de documents n'ont pas de rubrique sur /residence :
        #  `lien_document` rend alors `None`, et sans cette garde le lien devenait
        #  « <site>/None ». Un bouton absent vaut mieux qu'un bouton qui ment.
        + "{% if document.lien %}"
        + bouton("{{ app.url }}{{ document.lien }}", "Consulter le document", fond="#3D6B4F")
        + "{% endif %}",
        True,
    ),
    (
        "reponse_communaute",
        "Nouvelle réponse (Communauté)",
        "💬 Nouvelle réponse sur {{ reponse.rubrique_label }} — {{ residence.nom }}",
        titre("💬 Nouvelle réponse")
        + '<p style="margin:0 0 16px">{{ reponse.auteur }} a répondu à {{ reponse.rubrique_label }} <strong>« {{ reponse.sujet }} »</strong> :</p>'
        + encart(f'<p style="margin:0;font-size:14px;color:{TEXTE}">{{{{ reponse.extrait }}}}</p>')
        + bouton("{{ reponse.lien }}", "Voir et répondre"),
        True,
    ),
    (
        "idee_statut",
        "Idée soutenue — changement de statut",
        "💡 L'idée « {{ idee.titre }} » est {{ idee.statut_label }} — {{ residence.nom }}",
        titre("💡 Une idée que vous avez soutenue avance")
        + '<p style="margin:0 0 16px">Bonne nouvelle : l\'idée <strong>« {{ idee.titre }} »</strong>, que vous avez soutenue, est désormais <strong>{{ idee.statut_label }}</strong>.</p>'
        + bouton("{{ idee.lien }}", "Voir la boîte à idées"),
        True,
    ),
    (
        "annonce_hall",
        "Annonce hall (PDF à afficher)",
        "📄 Annonce à afficher — {{ annonce.titre }} — {{ residence.nom }}",
        titre("📄 Annonce à afficher dans le hall")
        + '<p style="margin:0 0 16px">{{ auteur.affiche }} a préparé une annonce pour <strong>{{ annonce.perimetre }}</strong>. '
        "Le PDF est en pièce jointe, prêt à imprimer au format <strong>{{ annonce.format }}</strong> et à afficher.</p>"
        + encart(
            f'<p style="margin:0 0 4px;font-size:13px;color:{GRIS}">{{{{ annonce.perimetre }}}} · Format {{{{ annonce.format }}}} · {{{{ annonce.date }}}}</p>'
            f'<p style="margin:0 0 8px;font-weight:700;font-size:17px;color:{BLEU}">{{{{ annonce.titre }}}}</p>'
            f'{{% if annonce.apercu %}}<p style="margin:0;font-size:14px;color:{GRIS}">{{{{ annonce.apercu }}}}</p>{{% endif %}}',
            fond=CREME,
            filet=OR,
        )
        + f'<p style="margin:0 0 20px;font-size:13px;color:{GRIS}">📎 Pièce jointe : <strong>{{{{ annonce.fichier }}}}</strong> '
        "— imprimer en couleur, sans mise à l’échelle (100 %).</p>"
        #  🔴 Le bouton pointe l'ACTUALITÉ d'origine, et n'apparaît que s'il y en
        #  a une (`annonce.lien`, cf. `annonces_hall_courriels.lien_affiche`).
        #  Il visait `/espace-cs`, que le front réserve au conseil syndical : depuis
        #  que le syndic reçoit ce courriel (#480), il y était renvoyé au tableau de
        #  bord. C'était le seul modèle du site à viser une route à accès restreint.
        + "{% if annonce.lien %}"
        + bouton("{{ app.url }}{{ annonce.lien }}", "Voir l’actualité d’origine")
        + "{% endif %}",
        True,
    ),
    #  Le compte rendu d'un point CS / Syndic à valider (#2042) : envoyé à chaque
    #  présent joignable du conseil et du syndic, jamais à un invité, avec SON
    #  lien. Ouvrir le lien ne valide rien (`standards/03` §5 bis) : la page
    #  montre le CR, et seul « Je valide » valide. Les textes arrivent ÉCHAPPÉS
    #  (`points_conseil_validation._contexte_courriel`) ; un CR « Conseil seul »
    #  n'y figure pas.
    (
        "point_conseil_validation",
        "Compte rendu d’un point CS / Syndic à valider",
        "{{ prefixe_copro }}Compte rendu du point CS / Syndic du {{ point.date }} — à valider",
        titre("📝 Compte rendu à valider")
        + '<p style="margin:0 0 16px">Voici le compte rendu du point entre le conseil syndical '
        "et le syndic auquel vous avez participé. Relisez-le, puis validez-le — ou envoyez un "
        "commentaire si quelque chose est à corriger.</p>"
        + encart(
            f'<p style="margin:0 0 4px;font-size:13px;color:{GRIS}">{{{{ point.date }}}} · {{{{ point.lieu }}}}</p>'
            f'<p style="margin:0;font-size:14px;color:{TEXTE}">Présents : {{{{ point.presents }}}}</p>'
        )
        + "{% for a in affaires %}"
        + f'<p style="margin:0 0 4px;font-weight:700;color:{BLEU}">{{{{ a.numero }}}} · {{{{ a.titre }}}}{{{{ a.marque | default('') }}}}</p>'
        + f'<p style="margin:0 0 14px;color:{TEXTE}">{{{{ a.texte }}}}</p>'
        + "{% endfor %}"
        + "{% if non_traitees %}"
        + f'<p style="margin:0 0 20px;font-size:13px;color:{GRIS}">Non traitées : {{{{ non_traitees }}}}</p>'
        + "{% endif %}"
        + bouton("{{ app.url }}/point-cs/{{ jeton }}", "Je valide ou je commente", marge="0 0 16px")
        + f'<p style="margin:0;font-size:13px;color:{GRIS}">Sans réponse de votre part, le compte '
        "rendu sera validé automatiquement le <strong>{{ echeance }}</strong>. Ce lien vous est "
        "personnel.</p>",
        True,
    ),
    #  Le CR VALIDÉ, son PDF en pièce jointe (#2082) : aux présents du conseil et
    #  du syndic qui ont une adresse — jamais aux invités.
    (
        "point_conseil_valide",
        "Compte rendu validé d’un point CS / Syndic",
        "{{ prefixe_copro }}Compte rendu validé du point CS / Syndic du {{ point.date }}",
        titre("✅ Compte rendu validé")
        + '<p style="margin:0 0 16px">Le compte rendu du point entre le conseil syndical et '
        "le syndic auquel vous avez participé est validé. Vous le trouverez en pièce jointe, "
        "au format PDF.</p>"
        + encart(
            f'<p style="margin:0;font-size:13px;color:{GRIS}">{{{{ point.date }}}} · {{{{ point.lieu }}}}</p>'
        ),
        True,
    ),
]
