"""Préparation des fichiers de codification (professions CITP, activités, produits).

Code d'origine : Code_suivi_collecte.do, section 10.
Décisions : codification manuelle sans nomenclature (CO1), chaque fin de mois (CO2),
pas de filtre sur l'emploi secondaire (CO3), import des codes en option (CO5),
une seule fusion ménage × membres (CO6).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from enem_core import donnees as D
from enem_core.execution import ModuleBase
from enem_core.parametres import Booleen, Fichier, Liste, Texte

from ._communs import (charger_individus, colonnes_export, num, p_fichier_menage, p_sortie, p_trimestre,
                       p_versions_menage, statut_residence)
from enem_core.trimestre import Trimestre

LOC = "HH01 HH0 HH2A HH1 HH2 HH3 HH4 HH6 HH8 HH8A HH7 HH7B HH8B HH12 HH13"
IDS = "interview__key interview__id membres__id V1interviewkey V1interviewkey1er rgmen rghab Statut_Res EF3 EF4 EF4_3 M4Confirm"
EP = "EP1a EP1b EP1b1 EP2a1 EP2b EP2b1 EP2c EP2d EP2e EP3 EP13 EP13a EP2jb"
ES = "ES1a ES1b ES1b1 ES2a ES2b ES2b1 ES2c ES2d ES2e ES2g ES3 ES4"
PL = "interview__key interview__id membres__id r_activite_s__id PL3_B PL3_C PL3_D PL3_D1a PL3_E PL3_F PL3_F1a PL3_G PL3_G_Aut PL3_H"


class CodificationEmploi(ModuleBase):
    id = "codification_emploi"
    nom = "Fichiers de codification emploi (CITP / activités / produits)"
    nom_court = "Codification emploi"
    description = ("Extrait les informations d'emploi principal, d'emploi secondaire et de pluriactivité des "
                   "individus en emploi pour la codification manuelle, et peut réintégrer les fichiers codifiés.")
    equipe = "Coordination"
    frequence_jours = 30
    frequence_libelle = "Chaque fin de mois"
    couleur = "#6B8E4E"
    entrees = "ENEM_AAAATq.dta, membres.dta, r_activite_s.dta (versions)"
    sorties = "codification_emploi_principal, codification_emploi_secondaire, codification_autre_emploi (.xlsx)"
    code_origine = ["Code_preparation_CITP_CIAP/Code_suivi_collecte.do"]
    mots_cles = "codification CITP CITI activité produit emploi principal secondaire pluriactivité"
    ordre = 70
    sous_dossier = "Coordination"

    @property
    def parametres(self):
        return [
            p_trimestre(),
            p_versions_menage(),
            p_fichier_menage(),
            Texte("fichier_pluri", "Base de pluriactivité", "r_activite_s.dta", groupe="Bases de données"),
            Booleen("principal", "Extraire l'emploi principal", True, groupe="Extractions"),
            Booleen("secondaire", "Extraire l'emploi secondaire", True, groupe="Extractions"),
            Booleen("pluriactivite", "Extraire la pluriactivité (autre emploi)", True, groupe="Extractions"),
            Liste("vars_id", "Variables d'identification", IDS, groupe="Variables"),
            Liste("vars_ep", "Variables emploi principal", EP, groupe="Variables"),
            Liste("vars_es", "Variables emploi secondaire", ES, groupe="Variables"),
            Liste("vars_pl", "Variables pluriactivité", PL, groupe="Variables"),
            Liste("vars_loc", "Variables de localisation", LOC, groupe="Variables"),
            Booleen("importer", "Importer un fichier codifié (option)", False, groupe="Import des codes"),
            Fichier("fichier_codifie", "Fichier Excel codifié à réintégrer", "", groupe="Import des codes",
                    obligatoire=False, types=[("Excel", "*.xlsx")]),
            Liste("cles_import", "Clés d'appariement du fichier codifié", "interview__key membres__id",
                  groupe="Import des codes", obligatoire=False),
            p_sortie(),
        ]

    def executer(self, ctx, p):
        t = Trimestre.depuis(p["trimestre"])
        n = 0
        if p["principal"] or p["secondaire"]:
            ctx.progression(5, "Lecture et fusion ménage × membres")
            ind = charger_individus(ctx, p)
            en_emp = (num(ind, "EN_EMP") == 1) & statut_residence(ind)
            emp = ind[en_emp]
            ctx.journal(f"  Individus en emploi (résidents) : {len(emp)}")
            if p["principal"]:
                ctx.progression(40, "Emploi principal")
                cols = colonnes_export(emp, p["vars_id"] + p["vars_ep"] + p["vars_loc"])
                ctx.exporter(f"codification_emploi_principal_{t.code}.xlsx",
                             {"Emploi_principal": D.appliquer_libelles(emp[cols], source=ind)})
                n += 1
            if p["secondaire"]:
                ctx.progression(60, "Emploi secondaire")
                cols = colonnes_export(emp, p["vars_id"] + p["vars_ep"] + p["vars_es"] + p["vars_loc"])
                ctx.exporter(f"codification_emploi_secondaire_{t.code}.xlsx",
                             {"Emploi_secondaire": D.appliquer_libelles(emp[cols], source=ind)})
                n += 1
            ctx.indicateur("individus_en_emploi", len(emp))
        if p["pluriactivite"]:
            ctx.progression(75, "Pluriactivité")
            pl = D.lire_versions(p["versions_menage"], p["fichier_pluri"], obligatoire=False, journal=ctx.journal)
            if pl.empty:
                ctx.alerte("Pluriactivité", f"{p['fichier_pluri']} introuvable : extraction ignorée", "Basse")
            else:
                cols = colonnes_export(pl, p["vars_pl"])
                ctx.exporter(f"codification_autre_emploi_{t.code}.xlsx",
                             {"Autre_emploi": D.appliquer_libelles(pl[cols], source=pl)})
                n += 1
        if p["importer"]:
            ctx.progression(90, "Import du fichier codifié")
            f = p.get("fichier_codifie")
            if not f or not Path(f).is_file():
                raise D.ErreurDonnees("Import demandé : choisissez le fichier Excel codifié.")
            cod = pd.read_excel(f)
            cles = [c for c in p["cles_import"] if c in cod.columns]
            if not cles:
                raise D.ErreurDonnees("Les clés d'appariement sont absentes du fichier codifié.")
            chemin = ctx.chemin(f"codes_importes_{Path(f).stem}.dta")
            cod.attrs = {}
            D.sauver_dta(cod, chemin)
            ctx.fichier_produit(chemin)
            ctx.resultat.tables["Codes_importes"] = cod
            ctx.journal(f"  ✓ {len(cod)} ligne(s) codifiée(s) enregistrée(s) : {chemin.name} "
                        f"(à fusionner sur {', '.join(cles)})")
        ctx.resultat.resume = f"{n} fichier(s) de codification produit(s)"


MODULE = CodificationEmploi()
