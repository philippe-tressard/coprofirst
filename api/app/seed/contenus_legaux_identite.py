"""Les rubriques du gabarit légal qui NOMMENT quelqu'un — par des champs (#2065).

Une installation sert plusieurs syndicats de copropriétaires. Chacun est
**responsable** du traitement de ses données ; l'opérateur de l'installation est
son **sous-traitant** (RGPD art. 28). Ces rubriques ne nomment donc personne en
dur : elles portent des `[[champs]]`, que `utils/textes_legaux/champs.rendre`
remplit de l'identité de la copropriété servie — et rend « À RENSEIGNER » quand
elle manque.

⚠️ **Projet, à faire relire.** Ces formulations sont des choix d'ingénierie, pas
un avis juridique (`standards/14`) : soumises à l'accord de l'auteur, puis à un
juriste avant toute copropriété pilote. Notamment :
- le directeur de la publication d'un syndicat est son représentant légal, le
  syndic (loi n° 65-557 du 10 juillet 1965, art. 18) ;
- l'opérateur, sous-traitant, n'accède aux données que pour faire fonctionner le
  service (art. 28.3).

Séparé de `contenus_legaux.py`, qui atteint 500 lignes (modularité, rang 1).
"""

#: Le syndicat, nommé comme une personne morale : la copropriété EST le syndicat
#: de ses copropriétaires — le conseil syndical n'a pas la personnalité juridique.
SYNDICAT = (
    "le <strong>syndicat des copropriétaires de la résidence [[copropriete]]</strong>, "
    "[[adresse_copropriete]]"
)

MENTIONS_IDENTITE = (
    "<h2>Éditeur du service</h2>"
    f"<p>Ce site est édité par {SYNDICAT}, représenté par son syndic, [[syndic]] "
    "([[adresse_syndic]]).</p>"
    "<h2>Directeur de la publication</h2>"
    "<p>Le syndic, [[syndic]], en sa qualité de représentant légal du syndicat des "
    "copropriétaires.</p>"
    "<h2>Hébergeur</h2>"
    "<p>[[hebergeur]] — pays des données\xa0: [[pays_donnees]].</p>"
    "<p>Le service est exploité, pour le compte du syndicat, par [[operateur]] "
    "([[adresse_operateur]], [[contact_operateur]]), son sous-traitant au sens du RGPD — "
    "voir la politique de confidentialité.</p>"
)

MENTIONS_CONTACT = (
    "<h2>Contact</h2>"
    "<p>Pour toute question sur le site, son contenu ou vos données\xa0: [[contact]]. Les "
    "résidents inscrits peuvent aussi écrire depuis la messagerie de l'application.</p>"
)

RESPONSABLE_TRAITEMENT = (
    "<h2>1. Responsable du traitement</h2>"
    f"<p>Le responsable du traitement est {SYNDICAT}, représenté par son syndic, "
    "[[syndic]]. Toute demande relative à vos données s'adresse à [[contact]] — une "
    "adresse joignable <em>sans compte</em>, car un droit d'effacement s'exerce souvent "
    "après la suppression du compte.</p>"
    "<p><strong>Sous-traitant.</strong> L'application est hébergée et maintenue pour le "
    "compte du syndicat par [[operateur]] ([[adresse_operateur]]), en vertu d'un contrat "
    "de sous-traitance (art.\xa028 du RGPD). L'opérateur ne traite les données que sur "
    "instruction du syndicat et pour faire fonctionner le service — sauvegarde, sécurité, "
    "mise à jour, restauration —, n'y accède que lorsqu'une de ces opérations l'exige, et "
    "transmet au syndicat toute demande d'une personne concernée qui lui parviendrait.</p>"
)

DESTINATAIRES = (
    "<h2>4. Destinataires</h2><p>Les données "
    "sont accessibles uniquement aux membres du conseil syndical et à l'administrateur. "
    "L'opérateur nommé au point 1 et l'hébergeur n'y ont qu'un accès technique, pour la "
    "seule exécution du service. Elles ne "
    "sont ni cédées à des tiers, ni commercialisées, ni utilisées à des fins "
    "publicitaires.</p>"
)

HEBERGEMENT = (
    "<p><strong>Hébergement et "
    "acheminement.</strong> Les données sont stockées par [[hebergeur]] — pays des "
    "données\xa0: [[pays_donnees]]. <strong>À RENSEIGNER</strong> si un intermédiaire "
    "technique (CDN, proxy, résolveur DNS) relaie les connexions : nommez-le et dites d'où "
    "il opère, ou retirez cette phrase. Un relais hors UE traite au minimum les adresses IP "
    "des visiteurs, et le taire rendrait ce paragraphe inexact.</p>"
)
