"""Un prompt SEMÉ ne suit pas le code — il faut une migration, et rien ne le disait.

## Ce qui est arrivé deux fois sans que personne le voie (#1059, 19/09/2026)

Le prompt de chaque usage de l'assistant est **semé** par la migration 0194 :
la valeur en base fait foi ensuite, et le code n'en est plus propriétaire
(`standards/06` §4). C'est voulu — l'administrateur relit et adapte ces
consignes depuis *Admin → Assistant IA*.

La conséquence, elle, ne l'était pas : **réécrire `prompt_defaut` dans le code
ne change plus rien à une installation en service.**

| Lot | Ce qu'il apportait | Effet en production |
|---|---|---|
| v1.44.0 (#1003) | « l'assistant peut mettre en valeur ce qui compte » | **aucun** |
| v1.44.4 (#1007) | « la mise en valeur était permise, elle n'était pas obtenue » | **aucun** |

Deux lots relus et déployés, sans effet sur l'assistant réellement employé. Le
code disait une chose, la base en servait une autre, et **aucun contrôle ne les
rapprochait** — c'est la définition d'un écart qui ne se découvre jamais.

## Ce que ce test fait, et ce qu'il ne fait pas

Il ne vérifie **pas** le contenu d'un prompt : ce contenu appartient à
l'administrateur, et le figer reviendrait à lui retirer ce que l'écran lui
donne. Il ne regarde pas non plus la base.

Il pose un **cliquet** sur la valeur d'ORIGINE : changer `prompt_defaut` sans
écrire la migration qui porte ce changement jusqu'aux installations existantes
fait échouer la CI, avec la marche à suivre. C'est le seul moment où quelqu'un
peut encore y penser.

⚠️ Un usage AJOUTÉ échoue ici aussi, et c'est voulu : il lui faut une migration
pour semer son prompt, sans quoi il démarrerait sur une clé absente.
"""

import hashlib

from app.utils.llm_usages import USAGES

#: Empreinte SHA-256 du prompt d'origine de chaque usage, telle qu'une migration
#: l'a portée en base. Mettre à jour une ligne ici est le DERNIER geste d'un lot
#: qui change un prompt — jamais le premier.
#:
#: | Usage | Migration qui a posé la valeur courante |
#: |---|---|
#: | `description` | 0197 (19/09/2026) — remplace les trois consignes antérieures |
#: | `synthese_contrat` | 0194 (17/09/2026) — ⚠️ voir l'écart connu ci-dessous |
#: | `reponse_courriel` | 0224 (25/09/2026) — le troisième usage, semé à sa création (#1322) |
#: | `tarif_modele` | 0240 (30/09/2026) — le quatrième usage, semé à sa création |
#: | `synthese_affaire` | 0255 (03/10/2026) — le cinquième usage, semé à sa création (#1643) |
#: | `question_reglement` | 0256 (03/10/2026) — le sixième usage, semé à sa création |
#: | `synthese_affaires_en_cours` | 0289 (16/10/2026, #2035) — le résumé de CHAQUE affaire remplace la synthèse d'ensemble ; né sans semis (la clé absente retombe sur l'origine, `config_llm`), la 0289 remplace une valeur enregistrée si elle est intacte |
#: | `fusion_affaires` | aucune (20/10/2026, #2083) — né sans semis, comme le précédent : la clé absente retombe sur l'origine (`config_llm`) |
#: | `lecture_etat_descriptif` | 0315 (25/10/2026, #2251) — né sans semis (#2218) ; la 0315 remplace une valeur enregistrée intacte quand la consigne demande l'« objet » de chaque clé |
#: | `transcription_pv_ag` | aucune (29/10/2026) — né sans semis, comme `fusion_affaires` : la clé absente retombe sur l'origine (`config_llm`) |
EMPREINTES_SEMEES = {
    "description": "a6bca9c941ff52c7b5f90108eccf8c0d0a1dbe2ced37f9ca41d621953b84528e",
    "synthese_contrat": "35d2cc4c13b269dbfa80bb197fec7ade1b27278dc7152b4c3acbf21b2036f097",
    "reponse_courriel": "43458295fafa66bddf159851d93c5854a26053b7a764aad682efd19dee6c51e2",
    "tarif_modele": "28c905d1d9d27fd7120e92f663a30be9c3c4ebb70cbb2f743775d57f407c3e8d",
    "synthese_affaire": "4c3731e49d70c7ecc87be0cf738963557edc6671694c661b4c7eaf10f323407c",
    "question_reglement": "00e271b332d102aa58d6c548e06cd36dd5d8c662894d720aef2d61fea692bfe2",
    "synthese_affaires_en_cours": "4ad57e8196cc222c81278d1ec0661cb7517d552b365b4f2da27303ba81c9a24d",
    "fusion_affaires": "9378f0059fff3f1370dba2bda2633ed0d3f439c391383070f9db867687fd75f8",
    "lecture_etat_descriptif": "9834ce6fc6cb2977e0ffc396e91302b477893806ada224cbd7229d6008490196",
    "transcription_pv_ag": "7f1a1f87c35ace0c364880b2253bd09b01a5ed1c15c7a94909d92bdde13f7170",
}

#: 🔴 Écart connu, tracé et non corrigé ici.
#:
#: La consigne de `synthese_contrat` a changé en v1.43.0 (#993) après avoir été
#: semée par la 0194 : les installations en service portent donc la version
#: antérieure. Ce test verrouille l'empreinte du CODE pour que l'écart cesse de
#: grandir ; le rattrapage en base demande une migration à part, parce que cette
#: consigne est composée de fragments et que ses empreintes historiques ne se
#: relisent pas aussi sûrement que celles de `description`.
#:
#: Le déclarer ici plutôt que de le taire : une exception non écrite n'est pas
#: une exception, c'est un oubli qui ressemble à une décision.
ECART_CONNU = ("synthese_contrat",)


def _empreinte(texte: str) -> str:
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()


def test_chaque_usage_declare_l_empreinte_de_son_prompt_d_origine():
    """Un usage sans empreinte déclarée n'a pas de migration qui sème son prompt."""
    manquants = sorted(set(USAGES) - set(EMPREINTES_SEMEES))
    assert not manquants, (
        f"Usage(s) sans empreinte déclarée : {manquants}. Un prompt d'origine ne "
        "parvient à une installation que par une migration — en ajouter un ici sans "
        "elle laisserait l'usage démarrer sur une clé absente."
    )
    orphelines = sorted(set(EMPREINTES_SEMEES) - set(USAGES))
    assert not orphelines, (
        f"Empreinte(s) déclarée(s) pour un usage qui n'existe plus : {orphelines}."
    )


def test_un_prompt_d_origine_ne_change_pas_sans_migration():
    """🔴 Le cliquet. Ce test échoue EXPRÈS quand on améliore un prompt.

    Ce n'est pas un faux positif : c'est le rappel que l'amélioration s'arrête
    au code si personne ne la porte en base.
    """
    for code, attendue in EMPREINTES_SEMEES.items():
        obtenue = _empreinte(USAGES[code].prompt_defaut)
        assert obtenue == attendue, (
            f"Le prompt d'origine de l'usage « {code} » a changé.\n"
            "    Les installations en service gardent l'ancien EN BASE : sans "
            "migration, ce lot n'aura aucun effet en production (c'est arrivé deux "
            "fois, #1059).\n"
            "    Marche à suivre :\n"
            "      1. écrire une migration qui remplace la valeur stockée SI elle "
            "porte encore une empreinte écrite par le code (motif de la 0197) ;\n"
            "      2. ajouter l'empreinte précédente à la liste de cette migration ;\n"
            f'      3. mettre à jour cette ligne : "{code}": "{obtenue}".'
        )
