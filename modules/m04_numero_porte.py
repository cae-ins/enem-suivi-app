"""Vérification du numéro de porte (dénombrement et questionnaire ménage).

Code d'origine : Verif_numero_porte.do
Décisions : format fixe (NP1), hebdomadaire (NP2), versions multiples pour le
dénombrement (NP3), dossier de sortie au choix (NP5), code dérivé du trimestre (NP6).
"""

from __future__ import annotations

import pandas as pd

from enem_core import donnees as D
from enem_core.execution import ModuleBase
from enem_core.parametres import Booleen, Entier, Liste, Texte, Versions
from enem_core.trimestre import Trimestre

from ._communs import (G_BASES, charger_menage, colonnes_export, exiger, num, p_fichier_menage, p_sortie,
                       p_trimestre, p_versions_menage)


def extraire(serie: pd.Series, position: int, longueur: int) -> pd.Series:
    """substr(x, position, longueur) de Stata (position commence à 1)."""
    return serie.fillna("").astype(str).str.slice(position - 1, position - 1 + longueur)


class NumeroPorte(ModuleBase):
    id = "numero_porte"
    nom = "Vérification du numéro de porte"
    nom_court = "Numéro de porte"
    description = ("Contrôle que le numéro de porte renseigné par les agents contient bien le code du trimestre "
                   "en cours (ex. T32026), dans le questionnaire de dénombrement (adresse_menage) et dans le "
                   "questionnaire ménage (HH9_1).")
    equipe = "Terrain"
    frequence_jours = 7
    frequence_libelle = "Hebdomadaire"
    couleur = "#C0661A"
    entrees = "Dénombrement : menage, batiment, ilot, ENEM_AAAATq_DenomVF (versions) ; ménage : ENEM_AAAATq (versions)"
    sorties = "Verification_denombrement_numero_porte_<T>.xlsx, Verification_numero_porte_<T>.xlsx"
    code_origine = ["Code_suivi_numero_porte/Verif_numero_porte.do"]
    mots_cles = "numéro porte adresse dénombrement HH9_1"
    ordre = 30
    sous_dossier = "Terrain"

    @property
    def parametres(self):
        return [
            p_trimestre(),
            Booleen("controle_denombrement", "Contrôler le questionnaire de dénombrement", True, groupe=G_BASES),
            Versions("versions_denombrement", "Dossiers des versions du dénombrement", [""], groupe=G_BASES,
                     globale="versions_denombrement", obligatoire=False,
                     fichier_attendu="menage.dta, batiment.dta, ilot.dta, ENEM_AAAATq_DenomVF.dta"),
            Texte("fichier_denom", "Nom de la base finale du dénombrement (vide = automatique)", "", groupe=G_BASES,
                  obligatoire=False, aide="Par défaut : ENEM_AAAATq_DenomVF.dta"),
            Booleen("controle_menage", "Contrôler le questionnaire ménage (agents terrain)", True, groupe=G_BASES),
            p_versions_menage(),
            p_fichier_menage(),
            Entier("position", "Position du code dans le numéro de porte", 6, groupe="Règle", mini=1, maxi=100),
            Entier("longueur", "Longueur du code", 6, groupe="Règle", mini=1, maxi=20),
            Liste("tolerees", "Valeurs tolérées en plus du code (## = non applicable)", "##", groupe="Règle",
                  obligatoire=False),
            Booleen("vide_tolere_denom", "Dénombrement : numéro vide toléré", True, groupe="Règle"),
            Booleen("vide_tolere_menage", "Ménage : numéro vide toléré", False, groupe="Règle"),
            Booleen("par_region", "Ajouter une feuille par région", True, groupe="Sortie"),
            p_sortie(),
        ]

    def _anomalies(self, serie, code, p, vide_tolere):
        ext = extraire(serie, p["position"], p["longueur"])
        entier = serie.fillna("").astype(str).str.strip()
        ok = (ext == code) | ext.isin(p["tolerees"]) | entier.isin(p["tolerees"])
        if vide_tolere:
            ok |= (ext == "")
        return ext, ~ok

    def _feuilles(self, df, nom, p):
        feuilles = {nom: df}
        if p["par_region"] and "Region" in df.columns:
            for reg, sub in df.groupby("Region"):
                feuilles[str(reg)[:31]] = sub
        return feuilles

    def executer(self, ctx, p):
        t = Trimestre.depuis(p["trimestre"])
        code = t.code_porte
        ctx.journal(f"Code attendu : {code}")
        total = 0
        if p["controle_denombrement"]:
            dossiers = p.get("versions_denombrement") or []
            if not dossiers:
                raise D.ErreurDonnees("Indiquez les dossiers du dénombrement ou décochez ce contrôle.")
            ctx.progression(5, "Dénombrement : lecture des bases")
            men = D.lire_versions(dossiers, "menage.dta", journal=ctx.journal)
            bat = D.lire_versions(dossiers, "batiment.dta", journal=ctx.journal)
            ilot = D.lire_versions(dossiers, "ilot.dta", journal=ctx.journal)
            fvf = (p.get("fichier_denom") or t.fichier_denombrement).strip()
            fvf = fvf if fvf.endswith(".dta") else fvf + ".dta"
            vf = D.lire_versions(dossiers, fvf, journal=ctx.journal)
            ctx.progression(30, "Dénombrement : fusions")
            df = D.fusionner(men, bat, ["interview__key", "ilot__id", "batiment__id"],
                             ["gps__Latitude", "gps__Longitude", "gps__Accuracy", "gps__Altitude",
                              "gps__Timestamp", "adresse", "bat_habite", "nom__0", "nb_men_num_bat", "nb_men_a_num"])
            df = D.fusionner(df, ilot, ["interview__key", "ilot__id"], ["code_ilot"])
            df = D.fusionner(df, vf, ["interview__key"],
                             ["HH01", "HH0", "HH2A", "HH1", "HH2", "HH3", "HH4", "HH6", "HH8", "HH8A", "HH7",
                              "HH8B", "trimestreencours", "mois_en_cours", "HH12", "HH13"])
            exiger(df, ["adresse_menage"], "la base menage du dénombrement")
            ext, anom = self._anomalies(df["adresse_menage"], code, p, p["vide_tolere_denom"])
            df["numero_porte_str"] = ext
            res = df[anom].copy()
            res["commentaire"] = (f"Vous n'avez pas bien renseigné le numéro de la porte du ménage. Nous sommes sur "
                                  f"la collecte {t.libelle}. Veuillez corriger la question adresse_menage")
            cols = colonnes_export(res, ["interview__key", "interview__id", "HH2", "nom__0", "HH12", "HH13",
                                         "adresse_menage", "numero_porte_str", "commentaire"])
            sortie = D.appliquer_libelles(res[cols], source=df)
            sortie.insert(0, "Region", sortie["HH2"] if "HH2" in sortie.columns else "")
            ctx.exporter(f"Verification_denombrement_numero_porte_{t.code}.xlsx",
                         self._feuilles(sortie, "National_menage", p), afficher=["National_menage"],
                         titre=f"Dénombrement – numéros de porte non conformes (code attendu {code})")
            ctx.indicateur("anomalies_porte_denombrement", len(res))
            total += len(res)
            ctx.journal(f"  Dénombrement : {len(res)} anomalie(s) sur {len(df)} ménages")
        if p["controle_menage"]:
            ctx.progression(55, "Questionnaire ménage : lecture")
            men = charger_menage(ctx, p)
            exiger(men, ["HH9_1", "rgmen"], "la base ménage")
            men = men[num(men, "rgmen") == 1]
            ext, anom = self._anomalies(men["HH9_1"], code, p, p["vide_tolere_menage"])
            res = men[anom].copy()
            res["numero_porte_str"] = ext[anom]
            res["commentaire"] = (f"Vous n'avez pas bien renseigné le numéro de la porte du ménage. Nous sommes sur "
                                  f"la collecte {t.libelle}. Veuillez corriger la question HH9_1")
            cols = colonnes_export(res, ["interview__key", "interview__id", "HH2", "HH12", "HH13", "HH9_1",
                                         "numero_porte_str", "commentaire"])
            sortie = D.appliquer_libelles(res[cols], source=men)
            sortie.insert(0, "Region", sortie["HH2"] if "HH2" in sortie.columns else "")
            ctx.exporter(f"Verification_numero_porte_{t.code}.xlsx", self._feuilles(sortie, "National_menage", p),
                         afficher=["National_menage"], titre=f"Questionnaire ménage – numéros de porte non conformes (code attendu {code})")
            ctx.indicateur("anomalies_porte_menage", len(res))
            total += len(res)
            if "HH13" in res.columns:
                for agent, n in D.appliquer_libelles(res[["HH13"]], source=men)["HH13"].value_counts().items():
                    ctx.alerte(str(agent), f"{n} numéro(s) de porte à corriger (HH9_1)", "Moyenne")
            ctx.journal(f"  Ménage : {len(res)} anomalie(s) sur {len(men)} ménages terrain")
        if not (p["controle_denombrement"] or p["controle_menage"]):
            raise D.ErreurDonnees("Cochez au moins un des deux contrôles.")
        ctx.resultat.resume = f"{total} numéro(s) de porte non conforme(s) (code attendu {code})"


MODULE = NumeroPorte()
