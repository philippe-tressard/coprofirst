"""Mentions légales et politique de confidentialité — GABARIT DU PRODUIT.

Servis tels quels tant que rien n'a été saisi en base ; `routers/config.py` les
lit en repli. Ils énoncent des obligations (RGPD, durées de conservation,
coordonnées de la CNIL) : toute modification est une décision juridique, pas
rédactionnelle — cf. `standards/14-conformite-juridique.md`.

## 🔴 LE SEED PORTE LE PRODUIT, LA BASE PORTE L'INSTANCE (03/09/2026)

Le logiciel (CoproFirst, `utils/plateforme`) peut être déployé ailleurs. Écrire ICI le nom
d'un éditeur ou d'un hébergeur les imposerait à tout autre déploiement, qui
publierait alors des mentions **fausses** — pire que des mentions vagues. Les
mentions de CETTE instance vivent en base (migration 0170).

Ce fichier reste donc générique. Mais il ne prétend plus être des mentions
valides : là où il disait « l'identité de l'éditeur correspond à la copropriété
ou au syndic bénévole qui gère cette instance », il dit **À RENSEIGNER**.

La différence n'est pas rédactionnelle. L'ancienne formulation décrivait ce
qu'il aurait fallu écrire, au lieu de l'écrire — et elle s'affichait sur une
page **publique** comme si elle était complète. Défaut sans symptôme : la page
se rend, elle a l'air finie, et personne ne la lit jusqu'à ce que quelqu'un
cherche qui contacter. La nôtre a vécu ainsi jusqu'à ce qu'un lecteur le voie.

## Les migrations citées ci-dessous

Une phrase dit la migration qui l'a portée dans le texte servi. Celles d'avant la
0286 ont été fondues dans le schéma initial (`0286_schema_initial.py`) : elles ne
lisent plus rien, et leur numéro ne dit que l'histoire de la phrase. Une constante
n'est gardée que tant qu'un lecteur l'emploie — le gabarit, une migration en
vigueur ou un test (🔒 `test_politique_durees.py`).

## Les durées

Chaque durée annoncée se compose de la constante qui l'applique, par
`dates_fr.duree_conservation` : recopiée en clair, elle divergerait au premier
changement de la purge (#2959).
"""

from app.seed.contenus_legaux_avis import AVIS_SITE_PRESENTATION
from app.seed.contenus_legaux_cookies import COOKIES
from app.seed.contenus_legaux_decisions_ag import DECISIONS_AG
from app.seed.contenus_legaux_destinataires import CONSERVATION_BAUX, PERSONNES_SANS_COMPTE
from app.seed.contenus_legaux_etat_descriptif import LECTURE_ETAT_DESCRIPTIF
from app.seed.contenus_legaux_canal import TELEMETRIE_ACCES
from app.seed.contenus_legaux_licence import PARAGRAPHE_LICENCE

#  La phrase du point 6 sur ce qu'un compte fait depuis son profil (#2699) : elle
#  vit à part, lue aussi par la migration 0332.
from app.seed.contenus_legaux_suppression import DROITS_DEPUIS_LE_PROFIL
from app.seed.contenus_legaux_notifications import (
    CONSERVATION_NOTIFICATIONS,
    NOTIFICATIONS_PUSH,
)
from app.seed.contenus_legaux_identite import (
    DESTINATAIRES,
    HEBERGEMENT,
    MARQUE_MODELE,
    MENTIONS_CONTACT,
    MENTIONS_IDENTITE,
    RESPONSABLE_TRAITEMENT,
)
from app.seed.contenus_legaux_conservation import JETONS_RAFRAICHISSEMENT
from app.utils.courriel_journal import CONSERVATION_RELEVES_JOURS
from app.utils.dates_fr import duree_conservation
from app.utils.erreurs_navigateur import CONSERVATION_JOURS as CONSERVATION_MESURES_JOURS
from app.utils.maintenance import CONSERVATION_COURRIELS_JOURS
from app.utils.telemetry_aggregation import (
    RETENTION_DAILY_JOURS,
    RETENTION_EVENEMENTS_JOURS,
    RETENTION_MONTHLY_JOURS,
)
from app.utils.purge_comptes.regles import (
    DELAI_ATTENTE_MOIS,
    DELAI_AVANT_SUPPRESSION_JOURS,
    DELAI_REFUS_JOURS,
    INACTIVITE_ANS,
)


#: Une durée, l'espace insécable entre le nombre et l'unité.
def _duree(jours: int) -> str:
    return duree_conservation(jours, "\xa0")


#: La conservation des comptes (#1580, arbitrée le 04/10/2026). L'ancienne phrase
#: annonçait une durée qu'aucun code n'appliquait ; elle reste écrite ici pour que
#: la migration 0263 la remplace EXACTEMENT (`utils/textes_livres`). La nouvelle
#: se compose des constantes de la purge (`utils/purge_comptes/regles`) : la durée
#: annoncée ne peut pas diverger de celle qui est appliquée.
CONSERVATION_COMPTES_ANCIEN = "Données de compte actif\xa0: durée de la relation + 2 ans."
CONSERVATION_COMPTES = (
    "Données de compte\xa0: un compte qui permet de se connecter et reste "
    f"<strong>{INACTIVITE_ANS}\xa0ans sans connexion</strong> reçoit un avertissement par "
    f"courriel, puis il est <strong>supprimé {DELAI_AVANT_SUPPRESSION_JOURS}\xa0jours plus "
    "tard</strong> avec les données qui lui sont rattachées, sauf s'il s'est reconnecté "
    "entre-temps. Les comptes d'administration ne sont pas supprimés automatiquement\xa0; "
)
#: Les comptes FERMÉS ou jamais décidés (#1822, arbitrage du 10/10/2026) : la phrase
#: d'avant ne disait aucune durée ; celle-ci se compose des constantes de la purge.
COMPTES_FERMES = (
    f"un compte refusé est supprimé <strong>{DELAI_REFUS_JOURS} jours</strong> après le "
    f"refus, un compte désactivé <strong>{INACTIVITE_ANS} ans</strong> après sa "
    "désactivation, et une inscription restée sans réponse de l'administration "
    f"<strong>{DELAI_ATTENTE_MOIS} mois</strong> après la demande — sans avertissement "
    "par courriel, puisqu'aucun de ces comptes ne permet de se connecter."
)
CONSERVATION_COMPTES += COMPTES_FERMES
#: Ce que la suppression d'un compte GARDE (#1688, #1821 — arbitrages du
#: 10/10/2026) : le contenu collectif, sans nom. Posée juste après
#: `CONSERVATION_COMPTES` par la migration des auteurs facultatifs, qui la retire
#: au retour arrière. La liste exacte : `utils/suppression_compte.CONTENUS_GARDES`.
ANONYMISATION_CONTENUS = (
    " Supprimer un compte, automatiquement ou à la demande, ne supprime pas ce qu'il "
    "a apporté à la vie commune — affaires et leur suivi, documents, règles, sondages "
    "et votes, idées, réponses de la Communauté, notes des prestataires : ils "
    "restent à la copropriété, son nom remplacé par « Ancien résident ». Ses "
    "petites annonces, ses délégations et ses demandes partent avec lui. Les textes "
    "ne sont pas réécrits ; pour faire retirer un passage qui vous identifie, "
    "écrivez à l'adresse indiquée au point 1."
)


#: La conservation de l'historique des envois (#1073, 24/09/2026). Il disait
#: « aucune purge automatique n'est en place à ce jour » — c'était FAUX : la
#: purge à 90 jours existait (maintenance hebdomadaire), le relevé qui avait
#: conclu à son absence cherchait le nom du modèle et non celui de la table.
#: Portée dans le texte servi par la migration 0218.
CONSERVATION_COURRIELS = (
    "<li>Historique des envois de courriels\xa0: conservé "
    f"<strong>{_duree(CONSERVATION_COURRIELS_JOURS)}</strong> "
    "pour le suivi des notifications, puis <strong>supprimé automatiquement</strong>. "
    "L'effacement anticipé s'obtient sur demande à l'adresse du point\xa01."
)

#: Le journal des messages relevés dans la boîte des réponses (#1447, 28/09/2026) :
#: il garde l'adresse de l'expéditeur. Insérée dans le texte servi par la migration
#: 0234 ; les migrations 0326, 0327 et 0329 la lisent. La durée vient de la purge elle-même : la recopier la ferait mentir au premier
#: changement.
CONSERVATION_RELEVES = (
    "<li>Journal des réponses reçues par courriel : adresse de l'expéditeur, objet, date "
    "et suite donnée — ajoutée à l'affaire, refusée, écartée ou à classer —, <strong>jamais "
    "le texte du message</strong>, sauf pour un message authentifié d'un correspondant connu "
    "qu'aucune affaire ne désigne : il est gardé entier, pièces jointes comprises, "
    "jusqu'à ce que le conseil syndical le classe — dans une affaire ou à l'écart —, puis "
    f"effacé. Conservé <strong>{CONSERVATION_RELEVES_JOURS} jours</strong> pour "
    "vérifier qu'une réponse a bien été reçue, puis <strong>supprimé automatiquement</strong>."
    "</li>"
)

#: Ce que l'assistant transmet SANS geste. La politique a d'abord affirmé « rien ne
#: l'est automatiquement » (faux depuis la mise en forme des réponses par courriel,
#: #1322, migration 0223), puis « une seule transmission est automatique » (faux
#: depuis la synthèse d'une affaire close, #1643) : la migration 0255 a posé la
#: phrase ci-dessous, suivie de `SYNTHESE_AFFAIRE_CLOSE`.
ASSISTANT_DEUX_AUTOMATIQUES = (
    "Rien n'est transmis si l'assistant est désactivé. Deux transmissions sont "
    "automatiques, chacune seulement si l'administration en active l'usage. La "
    "première : la <strong>réponse reçue par courriel</strong> sur une affaire — sans "
    "le message qu'elle cite — est transmise pour en retirer la signature, les mentions "
    "légales et les lignes vides ; le texte reçu reste conservé tel quel dans l'affaire."
)
#: Ce que la synthèse dit d'AUTRES affaires (#1647, 04/10/2026) : leur numéro et leur
#: date de clôture, jamais leur contenu. Insérée dans le texte servi par la migration 0257.
SYNTHESE_RECIDIVE = (
    " — et, quand l'équipement a déjà fait l'objet d'au moins deux autres affaires "
    "résolues sur le même périmètre en 24 mois, le numéro et la date de clôture de "
    "celles-ci, jamais leur contenu —"
)
SYNTHESE_AFFAIRE_CLOSE = (
    " La seconde : la <strong>synthèse d'une affaire close</strong> du carnet "
    "d'entretien — une fois l'affaire résolue ou annulée, son titre, sa description, ses "
    "suites et relances datées et ses messages non réservés au conseil syndical, sans les "
    "pièces jointes ni les notes internes, les personnes désignées par leur rôle"
    + SYNTHESE_RECIDIVE
    + ", sont transmis pour en rédiger un bilan, que le conseil syndical relit et valide avant que "
    "les autres lecteurs de l'affaire le voient."
)

#: Les questions au règlement de copropriété (03/10/2026) : le texte ENTIER du
#: règlement part à chaque question — il nomme des personnes (notaires, vendeurs).
#: Insérée dans le texte servi par la migration 0256 ; ouverte aux copropriétaires le
#: 11/10/2026 (0279). Les migrations 0313 et 0318 la lisent.
QUESTION_REGLEMENT = (
    "Lorsqu'une <strong>question au règlement de copropriété</strong> est posée — par un "
    "membre du conseil syndical, ou par un copropriétaire si l'administrateur le permet —, "
    "la question et le texte entier du règlement chargé par l'administrateur — qui peut "
    "nommer les parties aux actes notariés — sont transmis, jamais le nom de qui la pose ni "
    "de la personne qu'elle concerne. La question et sa réponse restent dans l'application "
    "avec le nom de leur auteur, lisibles de lui seul, du conseil syndical et de "
    "l'administrateur\xa0; elles n'entrent dans la FAQ que relues par le conseil, sans "
    "auteur, et restent sans nom à la suppression du compte de leur auteur. "
)

#: Les courriels TRANSFÉRÉS par un membre du conseil à l'adresse des affaires
#: (29/09/2026) : ils deviennent une affaire réservée au conseil, avec le nom,
#: l'adresse et le texte de personnes qui n'ont rien envoyé au site elles-mêmes,
#: et chaque message passe par la mise en forme automatique. Insérée dans le texte
#: servi par la migration 0237.
COURRIELS_TRANSFERES = (
    " Il en va de même des <strong>courriels transférés</strong> par un membre du "
    "conseil syndical à l'adresse des affaires : chaque message du fil y est "
    "transmis séparément, puis versé avec le nom, l'adresse et la date de son auteur "
    "dans une affaire réservée au conseil syndical."
)

#: La mesure d'audience, telle que le code la collecte : RATTACHÉE AU COMPTE
#: (`telemetry_event.user_id`). Portées dans le texte servi par les migrations 0246
#: et 0247.
#:
#: ⚠️ La 0246 (#1545) les avait passées « sans identifiant » en retirant la
#: colonne ; la 0247 les rétablit le même jour avec elle — le retrait supprimait
#: les statistiques par utilisateur sans l'accord de l'utilisateur du produit.
#: Le texte doit dire ce que fait le code : rattachée au compte, refusable,
#: exportable et effaçable depuis le profil.
TELEMETRIE_COLLECTE = (
    "<li><strong>Mesure d'audience interne (télémétrie) :</strong> pages consultées et "
    "actions effectuées, rattachées à votre compte. Elle sert à savoir quels écrans servent, "
    "et à rien d'autre : elle n'alimente aucune publicité et ne quitte pas l'application. "
    "Vous pouvez la <strong>refuser</strong> et <strong>effacer</strong> votre historique "
    "depuis <em>Mon profil</em>, rubrique <em>Vos droits (RGPD)</em>.</li>"
)
#: Les erreurs vues dans le navigateur (#1631) : comptées par page, SANS
#: rattachement au compte (`utils/erreurs_navigateur`). Insérée dans le texte servi
#: par la migration 0251.
TELEMETRIE_ERREURS = (
    "<li><strong>Erreurs techniques rencontrées à l'écran\xa0:</strong> le type d'erreur et la "
    "page où elle survient, comptés par jour <strong>sans rattachement à votre compte</strong> "
    f"et conservés {_duree(CONSERVATION_MESURES_JOURS)}. Ils servent à corriger les pannes que personne ne signale. "
    "Votre refus de la mesure d'audience les coupe aussi.</li>"
)
#: Les durées d'affichage des écrans (#1632) : par page, SANS rattachement au
#: compte (`utils/mesures_affichage`). Insérée dans le texte servi par la migration
#: 0252 ; la 0282 y a ajouté l'affichage des données (#1846).
TELEMETRIE_PERFORMANCE = (
    "<li><strong>Durées d'affichage des écrans\xa0:</strong> le temps d'ouverture du site, "
    "de passage d'un écran à l'autre et d'affichage de ses données, par page, mesurés dans "
    "votre navigateur "
    "<strong>sans rattachement à votre compte</strong> et conservés "
    f"{_duree(CONSERVATION_MESURES_JOURS)}. Elles servent "
    "à savoir quels écrans sont lents. Votre refus de la mesure d'audience les coupe aussi.</li>"
)
#: Les arrivées par notification (#1634) : le canal (et le modèle d'un courriel)
#: lu dans le lien, joint à la vue de page — donc RATTACHÉ AU COMPTE comme elle.
#: Insérée dans le texte servi par la migration 0262, juste après
#: `TELEMETRIE_PERFORMANCE` ; la migration 0336 la lit.
TELEMETRIE_ARRIVEES = (
    "<li><strong>Notification qui vous amène\xa0:</strong> quand vous ouvrez le site depuis un "
    "courriel ou depuis le groupe WhatsApp de la résidence, le lien porte ce canal — et, pour "
    "un courriel, son type —, jamais votre adresse ni votre identité. Il est joint à la page "
    "consultée, comme le reste de la mesure d'audience rattachée à votre compte, et conservé "
    f"{_duree(RETENTION_EVENEMENTS_JOURS)}. Il sert à savoir quelles notifications font venir. Votre refus de la mesure "
    "d'audience le coupe aussi.</li>"
)
#: Les gestes aboutis (#1633) : ouvertures et envois des formulaires, comptés par
#: jour SANS rattachement au compte (`utils/gestes_formulaire`). Insérée dans le
#: texte servi par la migration 0261, juste après `TELEMETRIE_PERFORMANCE`.
TELEMETRIE_GESTES = (
    "<li><strong>Formulaires ouverts et envoyés\xa0:</strong> pour quelques formulaires (créer "
    "une affaire, répondre, voter, déposer un document), le nombre de fois où ils sont ouverts "
    "puis envoyés, compté par jour <strong>sans rattachement à votre compte</strong> et sans "
    f"rien de ce que vous y saisissez, conservé {_duree(CONSERVATION_MESURES_JOURS)}. Il sert à repérer les formulaires "
    "qui découragent. Votre refus de la mesure d'audience le coupe aussi.</li>"
)
#: Le journal de sécurité (#1580) : `utils/journal_securite` écrit, pour chaque geste
#: sensible, une ligne qui porte l'IDENTIFIANT du compte — jamais l'adresse ni un
#: secret. La politique ne le nommait pas. Sa durée n'est pas une durée choisie :
#: les lignes vivent dans les journaux du conteneur, renouvelés par taille et à
#: chaque déploiement (#1588) — le texte le dit au lieu d'annoncer un délai que
#: rien n'applique. Insérée dans le texte servi par la migration 0253.
JOURNAL_SECURITE = (
    "<li><strong>Journal de sécurité\xa0:</strong> les connexions refusées, les changements "
    "de mot de passe, d'adresse ou de rôle, les bannissements et les décisions sur un compte, "
    "avec l'<strong>identifiant</strong> du compte concerné — jamais son adresse ni un mot de "
    "passe. Il sert à retrouver l'origine d'un accès suspect. Il est écrit dans les journaux "
    "techniques du serveur, qui se renouvellent par taille et à chaque mise à jour de "
    "l'application.</li>"
)
#: Les services tiers de la section 4 (#1585). La politique en comptait TROIS qui
#: transmettent ; le code en a une quatrième, de RÉCEPTION (`utils/courriel_boite`
#: relève une boîte hébergée chez un tiers). Le nombre s'écrit une fois — le test de
#: la politique compare le mot au nombre d'éléments de la liste ; la migration 0329
#: lit la phrase.
FONCTIONS_TIERS = (
    "Cinq fonctions font passer des informations par un service tiers lorsqu'elles sont activées"
)
ACHEMINEMENT_COURRIELS = (
    "<li><strong>Acheminement des courriels</strong> — les notifications partent par un "
    "service d'envoi de courriels, qui traite donc l'adresse du destinataire et le contenu du "
    "message. <strong>À RENSEIGNER</strong>\xa0: lequel.</li>"
)
RECEPTION_COURRIELS = (
    "<li><strong>Réception des courriels</strong> — les réponses aux notifications et les "
    "courriels transférés au site arrivent dans une boîte hébergée chez un service de "
    "messagerie, que l'application relève régulièrement\xa0; ce service conserve les messages "
    "reçus selon ses propres règles. <strong>À RENSEIGNER</strong>\xa0: lequel.</li>"
)
TELEMETRIE_BASE_LEGALE = (
    "<li><strong>Mesure d'audience interne</strong> — base : intérêt légitime "
    "(art. 6-1-f) à savoir quels écrans servent et à qui ; vous pouvez vous y "
    "opposer et effacer votre historique depuis votre profil (art. 17 et 21).</li>"
)
#: La conservation, telle que le code la pratique. Jusqu'au 03/10/2026, après
#: les 30 jours d'évènements détaillés il ne restait que des agrégats sans
#: compte ; depuis la 0254, le seul fait « ce compte est venu ce mois-là »
#: (`PresenceMensuelle`) est gardé 12 mois, pour que la vue Année de
#: « Qui vient » existe. Le texte le dit depuis la migration 0254. Les durées sont
#: celles des purges de `utils/telemetry_aggregation` : la présence mensuelle et les
#: agrégats par jour partagent `RETENTION_DAILY_JOURS`.
TELEMETRIE_CONSERVATION = (
    "<li>Mesure d'audience\xa0: événements détaillés "
    f"<strong>{_duree(RETENTION_EVENEMENTS_JOURS)}</strong>\xa0; ensuite, "
    f"pendant <strong>{_duree(RETENTION_DAILY_JOURS)}</strong>, seulement les mois où "
    "votre compte est venu — ni page, ni heure —, et des agrégats sans compte, par jour "
    f"pendant {_duree(RETENTION_DAILY_JOURS)} et par mois pendant "
    f"{_duree(RETENTION_MONTHLY_JOURS)}. L'effacement demandé depuis votre profil est immédiat et porte sur "
    "le tout.</li>"
)
#: Le jour de la dernière visite (#1629) : `DerniereVisite`, un jour par compte,
#: pour repérer les comptes qui ne viennent plus, purgé avec les agrégats par jour.
#: Insérée dans le texte servi par la migration 0260, juste après
#: `TELEMETRIE_CONSERVATION`.
TELEMETRIE_DERNIERE_VISITE = (
    "<li>Jour de votre dernière visite\xa0: <strong>un seul jour</strong>, ni page ni heure, "
    "pour repérer les comptes qui ne viennent plus\xa0; effacé après "
    f"<strong>{duree_conservation(RETENTION_DAILY_JOURS)}</strong> "
    "sans visite. Il n'est pas tenu si vous refusez la mesure d'audience, et l'effacement "
    "demandé depuis votre profil l'emporte aussi.</li>"
)

DEFAULT_LEGAL = {
    "mentions_legales": (
        MARQUE_MODELE
        + MENTIONS_IDENTITE
        + "<h2>Propriété intellectuelle</h2>"
        + PARAGRAPHE_LICENCE
        + "<p>Les contenus publiés dans l'application restent la propriété de leurs auteurs respectifs.</p>"
        "<h2>Responsabilité</h2>"
        "<p>L'éditeur s'efforce de fournir des informations exactes et à jour. Il ne saurait être tenu responsable "
        "des erreurs ou omissions dans les informations diffusées.</p>" + MENTIONS_CONTACT
    ),
    "politique_confidentialite": (
        MARQUE_MODELE
        + RESPONSABLE_TRAITEMENT
        + "<h2>2. Données collectées</h2><ul><li><strong>Données "
        "d'identification\xa0:</strong> nom, prénom, adresse e-mail, téléphone "
        "(facultatif).</li><li><strong>Données de résidence\xa0:</strong> lot(s) associé(s), bâtiment, "
        "tantièmes.</li><li><strong>Données d'usage\xa0:</strong> tickets soumis, messages échangés, "
        "documents téléchargés.</li><li><strong>Données techniques\xa0:</strong> tokens "
        "d'authentification (cookies HttpOnly), date de connexion.</li><li><strong>Photos et "
        "pièces jointes\xa0:</strong> images et documents que vous déposez sur un ticket, une actualité,"
        " une annonce ou un contrat. Les métadonnées de prise de vue (EXIF, dont la géolocalisation) "
        "sont <strong>retirées</strong> au téléversement.</li><li><strong>Objets d'accès\xa0:</strong> "
        "badges Vigik et télécommandes de parking, avec leur porteur et le lot auquel ils sont "
        "rattachés.</li>"
        + TELEMETRIE_COLLECTE
        + TELEMETRIE_ERREURS
        + TELEMETRIE_PERFORMANCE
        + TELEMETRIE_ARRIVEES
        + TELEMETRIE_ACCES
        + TELEMETRIE_GESTES
        + JOURNAL_SECURITE
        + PERSONNES_SANS_COMPTE
        + "</ul><h2>3. Finalités et bases légales</h2><ul><li><strong>Gestion de la copropriété</strong> — base\xa0: "
        "intérêt légitime (art.\xa06-1-f).</li><li><strong>Authentification et sécurité</strong> — "
        "base\xa0: intérêt légitime (art.\xa06-1-f).</li><li><strong>Communication résidents/CS</strong> — "
        "base\xa0: exécution du contrat (art.\xa06-1-b).</li><li><strong>E-mails transactionnels</strong> —"
        " base\xa0: intérêt légitime / consentement.</li>"
        + AVIS_SITE_PRESENTATION
        + TELEMETRIE_BASE_LEGALE
        + "</ul>"
        + DESTINATAIRES
        + "<p>Cette phrase vise la <strong>cession</strong> et la "
        "<strong>commercialisation</strong>\xa0: il n'y en a aucune. Elle ne signifie pas qu'aucune "
        "donnée ne quitte l'application — les <strong>sous-traitants techniques</strong> nommés "
        "ci-dessous en reçoivent, pour la seule exécution du service.</p>"
        + HEBERGEMENT
        + "<p><strong>Services tiers qui reçoivent des données.</strong> "
        + FONCTIONS_TIERS
        + " — elles le sont au cas par cas, par l'administrateur\xa0:</p><ul><li><strong>Diffusion sur une messagerie "
        "instantanée</strong> — lorsqu'une publication est diffusée au groupe de la résidence, son "
        "titre, son texte et, le cas échéant, <strong>une photo</strong> sont transmis au service qui"
        " héberge ce groupe (WhatsApp, service de Meta). Les conditions de ce service s'appliquent "
        "alors à ce message. <strong>À RENSEIGNER</strong> si cette diffusion est active sur cette "
        "instance, et vers quel groupe.</li><li><strong>Assistant de rédaction (modèle de "
        "langage)</strong> — lorsqu'un membre du conseil syndical demande une reformulation ou la "
        "synthèse d'un contrat, le texte concerné — et, pour un contrat, le <strong>contenu des "
        "documents joints</strong> — est transmis au service de modèle de langage configuré. "
        "<strong>À RENSEIGNER</strong>\xa0: lequel, et depuis quel pays il opère. "
        + QUESTION_REGLEMENT
        + DECISIONS_AG
        + LECTURE_ETAT_DESCRIPTIF
        + ASSISTANT_DEUX_AUTOMATIQUES
        + COURRIELS_TRANSFERES
        + SYNTHESE_AFFAIRE_CLOSE
        + "</li>"
        + ACHEMINEMENT_COURRIELS
        + RECEPTION_COURRIELS
        + NOTIFICATIONS_PUSH
        + "</ul><h2>5. Durée de conservation</h2><ul><li>"
        + CONSERVATION_COMPTES
        + ANONYMISATION_CONTENUS
        + "</li>"
        + JETONS_RAFRAICHISSEMENT
        + "<li>Sauvegardes\xa0: selon la configuration.</li></ul><ul>"
        + TELEMETRIE_CONSERVATION
        + TELEMETRIE_DERNIERE_VISITE
        + CONSERVATION_COURRIELS
        + "</li>"
        + CONSERVATION_RELEVES
        + CONSERVATION_NOTIFICATIONS
        + CONSERVATION_BAUX
        + "</ul><h2>6. Vos droits</h2><p>Conformément au RGPD vous disposez "
        "des droits d'accès (art.\xa015), rectification (art.\xa016), effacement (art.\xa017), portabilité "
        "(art.\xa020), opposition (art.\xa021) et retrait du consentement (art.\xa07-3). Pour les exercer, "
        "écrivez à l'adresse indiquée au point 1 — cette voie doit rester ouverte même sans compte, y"
        " compris après sa suppression. "
        + DROITS_DEPUIS_LE_PROFIL
        + " En cas de litige\xa0: <strong>CNIL</strong> — www.cnil.fr.</p><h2>7. Cookies</h2><p>"
        + COOKIES
        + " Aucun cookie publicitaire ou de traçage.</p>"
    ),
}
