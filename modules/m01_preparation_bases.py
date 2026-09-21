"""Préparation des bases : empilement (append) des versions téléchargées de Survey Solutions.

Code d'origine : Code_evolution_ZD.do (boucle « foreach d of global datasets »).
"""

from __future__ import annotations

from pathlib import Path

from enem_core import donnees as D
from enem_core.execution import ModuleBase
from enem_core.parametres import Booleen, Choix, Dossier, Liste, Versions
from enem_core.trimestre import Trimestre

from ._communs import G_BASES, G_SORTIE, p_trimestre

BASES_DEFAUT = ("Activiteparent assignment__actions couts_biens disponibilite emigration interview__actions "
                "interview__diagnostics interview__errors membres {BASE} r_activite_s r_competence_quali "
                "r_revenu_h_emp Revenu Revenu_es VISITE_IND VISITE_ROOSTER")


class PreparationBases(ModuleBase):
    id = "preparation_bases"
    nom = "Préparation des bases (append des versions)"
    nom_court = "Préparation des bases"
    description = ("Empile les différentes versions téléchargées d'une même base (ménage/individuelle ou "
                   "dénombrement) et enregistre les bases fusionnées dans un ou plusieurs dossiers.")
    equipe = "Terrain et téléopérateurs"
    frequence_jours = 7
    frequence_libelle = "Avant chaque série de contrôles"
    couleur = "#5B7F6E"
    entrees = "Dossiers de versions ENEM_AAAATq_n_STATA_All (fichiers .dta)"
    sorties = "Bases .dta fusionnées (une par nom de base) + rapport Excel des lignes lues"
    code_origine = ["Code_suivi_ZD/Code_evolution_ZD.do"]
    mots_cles = "append versions fusion bases survey solutions"
    ordre = 1
    sous_dossier = "Preparation"

    @property
    def parametres(self):
        return [
            p_trimestre(),
            Choix("type_base", "Type de base", "Ménage / individuelle", groupe=G_BASES,
                  options=["Ménage / individuelle", "Dénombrement"]),
            Versions("versions", "Dossiers des versions à empiler", groupe=G_BASES,
                     aide="Un dossier par version (1 à 7)."),
            Booleen("toutes_bases", "Prendre automatiquement toutes les bases .dta communes", True, groupe=G_BASES,
                    aide="Si décoché, seules les bases de la liste ci-dessous sont empilées."),
            Liste("liste_bases", "Liste des bases (sans .dta ; {BASE} = ENEM_AAAATq)", BASES_DEFAUT,
                  groupe=G_BASES, obligatoire=False),
            Booleen("exclure_commentaires", "Exclure interview__comments (volumineuse)", True, groupe=G_BASES),
            Dossier("dossier_destination", "Dossier de destination des bases fusionnées", "", groupe=G_SORTIE,
                    doit_exister=False, aide="Par exemple ...\\Base\\Base_menage_individuel\\Base_brute"),
            Dossier("copie_1", "Copie supplémentaire n°1 (facultatif)", "", groupe=G_SORTIE,
                    obligatoire=False, doit_exister=False, aide="Ex. dossier Base_agent_teleoperateur"),
            Dossier("copie_2", "Copie supplémentaire n°2 (facultatif)", "", groupe=G_SORTIE,
                    obligatoire=False, doit_exister=False, aide="Ex. dossier Base_agent_terrain"),
            Dossier("dossier_sortie", "Dossier racine du rapport", "", groupe=G_SORTIE, globale="dossier_sortie",
                    doit_exister=False),
        ]

    def executer(self, ctx, p):
        t = Trimestre.depuis(p["trimestre"])
        versions = [Path(v) for v in p["versions"]]
        if p["toutes_bases"]:
            communs = None
            for v in versions:
                noms = {f.stem for f in v.glob("*.dta")}
                communs = noms if communs is None else communs | noms
            bases = sorted(communs or [])
        else:
            bases = [b.replace("{BASE}", t.nom_base) for b in p["liste_bases"]]
        if p["exclure_commentaires"]:
            bases = [b for b in bases if b.lower() != "interview__comments"]
        if not bases:
            raise D.ErreurDonnees("Aucune base .dta trouvée dans les dossiers indiqués.")
        destinations = [Path(d) for d in (p["dossier_destination"], p.get("copie_1"), p.get("copie_2")) if d]
        for d in destinations:
            d.mkdir(parents=True, exist_ok=True)
        rapport = []
        for i, b in enumerate(bases):
            ctx.progression(100 * i / len(bases), f"Base {b} ({i + 1}/{len(bases)})")
            ligne = {"Base": b}
            morceaux = []
            for v in versions:
                f = v / f"{b}.dta"
                if f.exists():
                    df = D.lire_dta(f)
                    ligne[v.name] = len(df)
                    morceaux.append(df)
                else:
                    ligne[v.name] = "absente"
            if not morceaux:
                ligne["Total"] = 0
                rapport.append(ligne)
                continue
            fus = D.empiler(morceaux)
            ligne["Total"] = len(fus)
            if "interview__key" in fus.columns:
                cles = [c for c in fus.columns if c == "interview__key" or c.endswith("__id")]
                ligne["Doublons de clé"] = int(fus.duplicated(subset=cles).sum())
            for d in destinations:
                D.sauver_dta(fus, d / f"{b}.dta")
            rapport.append(ligne)
        import pandas as pd
        rap = pd.DataFrame(rapport)
        ctx.exporter(f"Rapport_append_{t.code}.xlsx", {"Rapport": rap},
                     titre=f"Empilement des versions – {p['type_base']} – {t.libelle}")
        dup = int(pd.to_numeric(rap.get("Doublons de clé", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
        if dup:
            ctx.alerte("Bases", f"{dup} ligne(s) en double sur les clés après empilement", "Moyenne")
        ctx.indicateur("bases_fusionnees", len(bases))
        ctx.resultat.resume = f"{len(bases)} base(s) empilée(s) vers {len(destinations)} dossier(s)"


MODULE = PreparationBases()
