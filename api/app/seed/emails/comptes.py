"""Modèles d'e-mail liés au compte et à son accès.

Ils partent hors de toute session ouverte — invitation, vérification, mot de passe oublié — et sont les seuls que reçoit quelqu'un qui n'est pas encore entré dans l'application. Un défaut ici empêche l'accès, il ne le dégrade pas.

Le gabarit commun (`email._wrap_email`) enveloppe ces contenus : pas de
`<html>` ni de `<body>` ici, seulement le corps riche.
"""

from app.seed.emails.fragments import BONJOUR, GRIS, bouton, titre

MODELES = [
    (
        "reinitialisation_mdp",
        "Réinitialisation mot de passe",
        "Réinitialisation de votre mot de passe — {{ residence.nom }}",
        '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">Réinitialisation de votre mot de passe</h2>'
        '<p style="margin:0 0 12px">Bonjour {{ destinataire.prenom }},</p>'
        '<p style="margin:0 0 24px">Une demande de réinitialisation a été effectuée pour votre compte. Cliquez sur le bouton ci-dessous pour choisir un nouveau mot de passe.</p>'
        '<p style="text-align:center;margin:0 0 16px"><a href="{{ lien }}" style="display:inline-block;background:#C9983A;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Réinitialiser mon mot de passe</a></p>'
        '<p style="margin:0;font-size:13px;color:#5A6070">Ce lien est valable <strong>1 heure</strong>. Si vous n’avez pas fait cette demande, ignorez cet e-mail.</p>',
        False,
    ),
    (
        "verification_email",
        "Vérification e-mail",
        "Vérifiez votre adresse e-mail — {{ residence.nom }}",
        '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">Vérification de votre adresse e-mail</h2>'
        '<p style="margin:0 0 12px">Bonjour {{ prenom }},</p>'
        '<p style="margin:0 0 24px">Cliquez sur le bouton ci-dessous pour confirmer votre adresse e-mail.</p>'
        '<p style="text-align:center;margin:0 0 16px"><a href="{{ lien }}" style="display:inline-block;background:#C9983A;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Vérifier mon adresse</a></p>'
        '<p style="margin:0;font-size:13px;color:#5A6070">Ce lien est valable <strong>{{ expire_heures }} heures</strong>. Si vous n’êtes pas à l’origine de cette demande, ignorez ce message.</p>',
        False,
    ),
    (
        #  L'avis à l'ANCIENNE adresse quand l'adresse d'un compte va changer (#1549) :
        #  c'est elle qu'un détournement ferait taire, c'est donc elle qu'on prévient.
        #  Il ne contient AUCUN lien : il n'y a rien à cliquer pour qui n'a rien
        #  demandé, et un courriel d'alerte qui porte un bouton ressemble à
        #  l'hameçonnage qu'il dénonce.
        "adresse_changement_avis",
        "Changement d’adresse demandé",
        "Changement d’adresse demandé pour votre compte — {{ residence.nom }}",
        '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">Changement d’adresse demandé</h2>'
        '<p style="margin:0 0 12px">Bonjour {{ destinataire.prenom }},</p>'
        '<p style="margin:0 0 12px">Une demande a été faite pour que l’adresse de votre compte sur <strong>{{ residence.nom }}</strong> devienne <strong>{{ nouvelle_adresse }}</strong>.'
        "{% if par_un_administrateur %} Elle vient d’un administrateur du site.{% endif %}</p>"
        '<p style="margin:0 0 12px">Rien ne change tant que ce changement n’est pas confirmé par le lien envoyé à cette nouvelle adresse : d’ici là, vous continuez à vous connecter avec l’adresse qui reçoit ce message.</p>'
        '<p style="margin:0;font-size:13px;color:#5A6070">Si vous n’êtes pas à l’origine de cette demande, changez votre mot de passe sans attendre et prévenez le conseil syndical.</p>',
        False,
    ),
    (
        "compte_en_attente",
        "Compte en attente",
        "Nouvelle demande de compte — {{ residence.nom }}",
        '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">Nouvelle demande de compte</h2>'
        '<p style="margin:0 0 12px">Un nouveau résident souhaite rejoindre la résidence\u202f:</p>'
        '<table role="presentation" style="margin:0 0 20px;border-left:4px solid #C9983A;padding-left:16px"><tr><td>'
        '<p style="margin:0 0 4px;font-weight:600;font-size:16px">{{ utilisateur.affiche }}</p>'
        '<p style="margin:0;color:#5A6070">{{ utilisateur.email }}</p>'
        "</td></tr></table>"
        # `/admin/utilisateurs` n'existe pas : la page `/admin` s'ouvre d'elle-même
        # sur l'onglet « Comptes en attente », et ne lit pas `?onglet=`. Ce bouton
        # ouvrait un 404 depuis l'origine, dans un e-mail réellement envoyé.
        '<p style="text-align:center;margin:0"><a href="{{ app.url }}/admin" style="display:inline-block;background:#1E3A5F;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Valider le compte</a></p>',
        True,
    ),
    (
        "compte_active",
        "Compte activé",
        "Votre compte est activé — {{ residence.nom }}",
        '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">Votre compte est activé\u202f!</h2>'
        '<p style="margin:0 0 12px">Bonjour {{ destinataire.prenom }},</p>'
        '<p style="margin:0 0 24px">Votre compte sur <strong>{{ residence.nom }}</strong> est maintenant actif. Vous pouvez dès à présent accéder à l’ensemble des services de votre résidence.</p>'
        '<p style="text-align:center;margin:0"><a href="{{ app.url }}" style="display:inline-block;background:#3D6B4F;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Accéder à l’application</a></p>',
        True,
    ),
    (
        "compte_refuse",
        "Compte refusé",
        "Votre demande de compte — {{ residence.nom }}",
        '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">Demande de compte non acceptée</h2>'
        '<p style="margin:0 0 12px">Bonjour {{ destinataire.prenom }},</p>'
        '<p style="margin:0 0 12px">Votre demande de création de compte sur <strong>{{ residence.nom }}</strong> n’a pas pu être acceptée.</p>'
        '<p style="margin:0;color:#5A6070">Si vous pensez qu’il s’agit d’une erreur, n’hésitez pas à contacter le conseil syndical.</p>',
        True,
    ),
    (
        #  L'avertissement avant la purge d'un compte inactif (#1580). Il dit QUAND,
        #  et ce qu'il suffit de faire : se connecter. Aucun lien à usage unique —
        #  la page de connexion, rien d'autre : un lien ouvert par un antivirus de
        #  messagerie ne doit rien déclencher (`standards/03` §5 bis).
        #  Non désactivable : sans lui, la purge ne supprime rien (aucun
        #  avertissement daté), et la durée annoncée redeviendrait fictive.
        "compte_inactif_avertissement",
        "Compte inactif — suppression prochaine",
        "Votre compte sera supprimé faute d’utilisation — {{ residence.nom }}",
        titre("Votre compte va être supprimé")
        + BONJOUR
        + '<p style="margin:0 0 12px">Votre compte sur <strong>{{ residence.nom }}</strong> '
        "n’a pas été utilisé depuis le {{ derniere_activite }}.</p>"
        '<p style="margin:0 0 12px">Comme l’annonce la politique de confidentialité du site, '
        "un compte resté deux ans sans connexion est supprimé, avec les données qui lui sont "
        "rattachées. Le vôtre le sera <strong>à partir du {{ date_suppression }}</strong>.</p>"
        '<p style="margin:0 0 24px">Pour le conserver, <strong>il suffit de vous connecter</strong> '
        "avant cette date : la suppression est alors annulée.</p>"
        + bouton("{{ app.url }}/auth/connexion", "Me connecter", marge="0 0 16px")
        + f'<p style="margin:0;font-size:13px;color:{GRIS}">Mot de passe oublié ? La page de '
        "connexion permet d’en choisir un nouveau. Si vous ne souhaitez plus utiliser ce compte, "
        "vous n’avez rien à faire.</p>",
        False,
    ),
    (
        #  L'accusé de réception d'une demande de suppression de compte (#2699). Il
        #  part sans `destinataire_id` — aucune préférence ne le coupe : sur un compte
        #  volé, c'est lui qui prévient le titulaire. Aucun lien à usage unique : la
        #  demande se retire depuis le profil, après connexion.
        "suppression_compte_demandee",
        "Suppression de compte demandée",
        "Votre demande de suppression de compte — {{ residence.nom }}",
        titre("Demande de suppression reçue")
        + BONJOUR
        + '<p style="margin:0 0 12px">Nous avons bien reçu votre demande de suppression de '
        "votre compte sur <strong>{{ residence.nom }}</strong>. L’administration de la "
        "résidence la traite sous <strong>{{ delai_jours }} jours</strong> au plus.</p>"
        '<p style="margin:0 0 12px">Tant qu’elle n’est pas traitée, vous pouvez la retirer '
        "depuis <strong>Mon profil</strong>.</p>"
        f'<p style="margin:0;font-size:13px;color:{GRIS}">Si vous n’êtes pas à l’origine de '
        "cette demande, retirez-la, changez votre mot de passe sans attendre et prévenez le "
        "conseil syndical.</p>",
        False,
    ),
    (
        #  Le dernier courriel (#2699) : le compte n'existe plus, l'adresse a été lue
        #  avant la purge et n'est gardée nulle part ensuite.
        "suppression_compte_effectuee",
        "Compte supprimé",
        "Votre compte a été supprimé — {{ residence.nom }}",
        titre("Votre compte a été supprimé")
        + BONJOUR
        + '<p style="margin:0 0 12px">Comme vous l’avez demandé, votre compte sur '
        "<strong>{{ residence.nom }}</strong> et vos données personnelles ont été effacés. "
        "Ce que vous avez écrit dans la vie collective de la résidence reste, sans votre "
        "nom.</p>"
        f'<p style="margin:0;font-size:13px;color:{GRIS}">Pour toute question sur vos '
        "données, la politique de confidentialité du site indique à qui écrire.</p>",
        False,
    ),
]
