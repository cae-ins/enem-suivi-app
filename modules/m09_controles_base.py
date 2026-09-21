"""Contrôles de base de la collecte (âges et sexes manquants, ZD, GPS, individus non classables).

Code d'origine : Code_suivi_collecte.do, sections 5 à 9 (décision CO4).
"""

from __future__ import annotations

import pandas as pd

from enem_core import donnees as D
from enem_core.execution import ModuleBase
from enem_core.parametres import Booleen, Entier, Liste

from ._communs import (charger_individus, charger_menage, colonnes_export, num, p_fichier_menage, p_sortie,
                       p_trimestre, p_versions_menage, statut_residence)
from enem_core.trimestre import Trimestre

VARS_EMPLOI = "SE1 SE2 SE3 SE4 SE5 SE7 SE8 SE9 SE9A SE9B SE10 SE11"
VARS_CHOMAGE = "SRH1 SRH2 SRH2A SRH11"
VARS_GPS = ("interview__key HH01 HH0 HH2A HH1 HH2 HH3 HH4 HH6 HH8 HH8A HH7 HH7B HH8B rghab rgmen V1MODINTR "
            "trimestreencours mois_en_cours annee Date1 Date2 Reference HH12 nom_CE HH13 nom_agent HH9 HH9_1")


class ControlesBase(ModuleBase):
    id = "controles_base"
    nom = "Contrôles de base de la collecte"
    nom_court = "Contrôles de base"
    description = ("Âges et sexes manquants (terrain / téléopérateurs), ZD de 12 ménages ou plus, export GPS pour "
                   "les géomaticiens et individus non classables en emploi ou en chômage.")
    equipe = "Terrain et téléopérateurs"
    frequence_jours = 7
    frequence_libelle = "Hebdomadaire"
    couleur = "#9C5A1E"
    entrees = "ENEM_AAAATq.dta + membres.dta (versions)"
    sorties = "AGE_missing, SEXE_missing, ZD_taille, GPS_menage_ZD (.csv), classement_emploi / chomage"
    code_origine = ["Code_preparation_CITP_CIAP/Code_suivi_collecte.do"]
    mots_cles = "âge sexe manquant GPS non classable emploi chômage contrôle"
    ordre = 55
    sous_dossier = "Coordination"

    @property
    def parametres(self):
        return [
            p_trimestre(),
            p_versions_menage(),
            p_fichier_menage(),
            Booleen("c_age", "Âges manquants", True, groupe="Contrôles"),
            Booleen("c_sexe", "Sexes manquants", True, groupe="Contrôles"),
            Booleen("c_zd", "ZD atteignant le seuil de ménages", True, groupe="Contrôles"),
            Entier("seuil_zd", "Seuil de ménages par ZD (≥)", 12, groupe="Contrôles", mini=1, maxi=500),
            Booleen("c_gps", "Export GPS (CSV séparateur « ; »)", True, groupe="Contrôles"),
            Booleen("c_classement", "Individus non classables (emploi / chômage)", True, groupe="Contrôles"),
            Entier("age_pat", "Âge minimal de la population en âge de travailler", 15, groupe="Contrôles",
                   mini=0, maxi=99),
            Liste("vars_emploi", "Variables du classement emploi", VARS_EMPLOI, groupe="Variables"),
            Liste("vars_chomage", "Variables du classement chômage", VARS_CHOMAGE, groupe="Variables"),
            p_sortie(),
        ]

    def _deux_equipes(self, ctx, df, cond, cols, nom, t, source, libelle):
        rg = num(df, "rgmen")
        feuilles = {}
        for eq, masque in (("terrain", rg == 1), ("tele", rg != 1)):
            sel = df[cond & masque]
            feuilles[eq] = D.appliquer_libelles(sel[colonnes_export(sel, cols)], source=source)
            ctx.indicateur(f"{nom}_{eq}", len(sel))
            if len(sel):
                ctx.alerte(f"Équipe {eq}", f"{len(sel)} individu(s) : {libelle}", "Moyenne")
        ctx.exporter(f"{nom}_{t.code}.xlsx", {f"{nom}_terrain": feuilles["terrain"], f"{nom}_tele": feuilles["tele"]},
                     titre=f"{libelle} – {t.libelle}")

    def executer(self, ctx, p):
        t = Trimestre.depuis(p["trimestre"])
        ctx.progression(5, "Lecture et fusion ménage × membres")
        ind = charger_individus(ctx, p)
        res = statut_residence(ind)
        if p["c_age"]:
            ctx.progression(30, "Âges manquants")
            self._deux_equipes(ctx, ind, D.manquant(ind["AgeAnnee"]) & res if "AgeAnnee" in ind.columns
                               else pd.Series(False, index=ind.index),
                               "interview__key membres__id M0__0 M6_A M6_J M6_M M7 AgeAnnee HH2 HH12 HH13 M5 rgmen".split(),
                               "AGE_missing", t, ind, "âge manquant")
        if p["c_sexe"]:
            ctx.progression(40, "Sexes manquants")
            self._deux_equipes(ctx, ind, D.manquant(ind["M5"]) & res if "M5" in ind.columns
                               else pd.Series(False, index=ind.index),
                               "interview__key membres__id M0__0 HH2 HH12 HH13 M5 rgmen".split(),
                               "SEXE_missing", t, ind, "sexe manquant")
        if p["c_zd"] or p["c_gps"]:
            men = charger_menage(ctx, p)
            terr = men[num(men, "rgmen") == 1]
            if p["c_zd"]:
                ctx.progression(55, "Taille des ZD")
                cle = D.colonnes_presentes(terr, ["HH2", "HH8A", "HH8B", "HH8"])
                zd = terr.groupby(cle, dropna=False).size().rename("nb_menages").reset_index()
                zd = zd[zd["nb_menages"] >= p["seuil_zd"]].sort_values("nb_menages", ascending=False)
                ctx.exporter(f"ZD_taille_superieure_{p['seuil_zd']}_{t.code}.xlsx",
                             {"ZD": D.appliquer_libelles(zd, source=men)},
                             titre=f"ZD de {p['seuil_zd']} ménages ou plus")
                ctx.indicateur("zd_seuil_atteint", len(zd))
            if p["c_gps"]:
                ctx.progression(65, "Export GPS")
                gps = terr.copy()
                cols = []
                for c in ("Latitude", "Longitude", "Accuracy", "Altitude"):
                    src = f"GPS__{c}"
                    if src in gps.columns:
                        gps[f"gps__{c}_str"] = gps[src].map(lambda v: "" if pd.isna(v) else repr(float(v)))
                        cols.append(f"gps__{c}_str")
                if not cols:
                    ctx.alerte("GPS", "Variables GPS__Latitude / GPS__Longitude absentes : export ignoré", "Basse")
                else:
                    vars_gps = VARS_GPS.split()
                    sel = ["interview__key"] + cols + D.colonnes_presentes(gps, ["GPS__Timestamp"]) + \
                        [c for c in colonnes_export(gps, vars_gps) if c != "interview__key"]
                    ctx.exporter_csv(f"GPS_menage_ZD_{t.code}.csv", D.appliquer_libelles(gps[sel], source=men))
                    ctx.indicateur("menages_avec_gps", int(gps["GPS__Latitude"].notna().sum())
                                   if "GPS__Latitude" in gps.columns else 0)
        if p["c_classement"]:
            ctx.progression(80, "Individus non classables")
            pat = num(ind, "M4Confirm") >= p["age_pat"]
            ctx.indicateur("pat", int(pat.sum()))
            for nom, variables in (("emploi", p["vars_emploi"]), ("chomage", p["vars_chomage"])):
                presentes = D.colonnes_presentes(ind, variables)
                if not presentes:
                    ctx.alerte(f"Classement {nom}", "Aucune variable du classement trouvée", "Basse")
                    continue
                vide = pd.concat([D.manquant(ind[c]) for c in presentes], axis=1).all(axis=1)
                sel = ind[vide & res].assign(**{f"classement_{nom}": "Inclassable"})
                cols = colonnes_export(sel, ["interview__key", "membres__id", "M0__0", "HH2", "HH12", "HH13",
                                             f"classement_{nom}", "rgmen"])
                ctx.exporter(f"classement_{nom}_{t.code}.xlsx",
                             {f"Inclassables_{nom}": D.appliquer_libelles(sel[cols], source=ind)},
                             titre=f"Individus non classables ({nom}) – toutes les variables vides")
                ctx.indicateur(f"inclassables_{nom}", len(sel))
                if len(sel):
                    ctx.alerte(f"Classement {nom}", f"{len(sel)} individu(s) non classable(s)", "Moyenne")
        ctx.resultat.resume = f"Contrôles de base terminés – {len(ctx.resultat.alertes)} alerte(s)"


MODULE = ControlesBase()
