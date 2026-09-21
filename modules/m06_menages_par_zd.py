"""Nombre de ménages enquêtés par ZD (agents terrain).

Code d'origine : Nbre_MEN_ZD_T3_2026.do (et section 7 de Code_suivi_collecte.do)
Décisions : seuil haut modifiable, 12 par défaut (ZD1) ; clé au choix (ZD2) ;
ZD de moins de 5 ménages signalées (ZD3) ; tous les enregistrements (ZD4).
"""

from __future__ import annotations

from enem_core import donnees as D
from enem_core.execution import ModuleBase
from enem_core.parametres import Choix, Entier

from ._communs import (charger_menage, exiger, num, p_fichier_menage, p_sortie, p_trimestre,
                       p_versions_menage)
from enem_core.trimestre import Trimestre

CLES = {"HH2 HH8A HH8": ["HH2", "HH8A", "HH8"], "HH2 HH8A HH8B HH8": ["HH2", "HH8A", "HH8B", "HH8"]}


class MenagesParZD(ModuleBase):
    id = "menages_par_zd"
    nom = "Nombre de ménages par ZD"
    nom_court = "Ménages par ZD"
    description = ("Compte les ménages enquêtés par ZD (passage 1, agents terrain) et signale les ZD qui "
                   "dépassent le nombre maximal (12) ou qui comptent trop peu de ménages (moins de 5).")
    equipe = "Terrain"
    frequence_jours = 14
    frequence_libelle = "Toutes les 2 semaines"
    couleur = "#8A9A3B"
    entrees = "ENEM_AAAATq.dta (versions)"
    sorties = "Nbre_MEN_ZD_<T>.xlsx (toutes les ZD, ZD au-dessus du seuil, ZD sous le seuil bas)"
    code_origine = ["Nombre_men_ZD/Nbre_MEN_ZD_T3_2026.do", "Code_preparation_CITP_CIAP/Code_suivi_collecte.do"]
    mots_cles = "ZD ménages 12 seuil taille"
    ordre = 50
    sous_dossier = "Terrain"

    @property
    def parametres(self):
        return [
            p_trimestre(),
            p_versions_menage(),
            p_fichier_menage(),
            Entier("seuil_haut", "Nombre maximal de ménages par ZD", 12, groupe="Règle", mini=1, maxi=500,
                   aide="Une ZD est signalée si elle compte PLUS que ce nombre."),
            Entier("seuil_bas", "Signaler les ZD de moins de … ménages", 5, groupe="Règle", mini=0, maxi=500),
            Choix("cle", "Clé d'identification de la ZD", "HH2 HH8A HH8", groupe="Règle", options=list(CLES)),
            Entier("rgmen", "Valeur de rgmen des entretiens terrain", 1, groupe="Règle", mini=1, maxi=9),
            p_sortie(),
        ]

    def executer(self, ctx, p):
        t = Trimestre.depuis(p["trimestre"])
        ctx.progression(5, "Lecture de la base ménage")
        men = charger_menage(ctx, p)
        cle = CLES[p["cle"]]
        exiger(men, cle + ["rgmen", "interview__key"], "la base ménage")
        men = men[num(men, "rgmen") == p["rgmen"]]
        ctx.progression(50, "Comptage des ménages par ZD")
        info = D.colonnes_presentes(men, ["HH1", "HH3", "HH4", "HH6", "HH8B", "HH12"])
        info = [c for c in info if c not in cle]
        g = men.groupby(cle, dropna=False)
        zd = g["interview__key"].nunique().rename("Nbre_MEN_ZD").to_frame()
        for c in info:
            zd[c] = g[c].first()
        zd = zd.reset_index().sort_values("Nbre_MEN_ZD", ascending=False)
        zd = D.appliquer_libelles(zd, ["HH1", "HH2", "HH3", "HH4", "HH6", "HH12"], source=men)
        haut = zd[zd["Nbre_MEN_ZD"] > p["seuil_haut"]]
        bas = zd[zd["Nbre_MEN_ZD"] < p["seuil_bas"]]
        detail = men.assign(Nbre_MEN_ZD=men.groupby(cle, dropna=False)["interview__key"].transform("count"))
        detail = detail[detail.set_index(cle).index.isin(haut.set_index(cle).index)]
        detail = D.appliquer_libelles(detail[D.colonnes_presentes(detail, [
            "interview__key", "HH2", "HH8A", "HH8", "HH1", "HH3", "HH4", "HH8B", "HH12", "HH13", "Nbre_MEN_ZD"])],
            source=men)
        couleur = lambda r: ("ROUGE" if r["Nbre_MEN_ZD"] > p["seuil_haut"]
                             else "ORANGE" if r["Nbre_MEN_ZD"] < p["seuil_bas"] else None)
        ctx.exporter(f"Nbre_MEN_ZD_{t.code}.xlsx",
                     {"National_Nbre_MEN_ZD": zd, f"ZD_plus_de_{p['seuil_haut']}": haut,
                      f"ZD_moins_de_{p['seuil_bas']}": bas, "Menages_ZD_depassement": detail},
                     titre=f"Nombre de ménages par ZD – {t.libelle} (rgmen = {p['rgmen']})",
                     surlignage={"National_Nbre_MEN_ZD": couleur})
        for _, r in haut.iterrows():
            ctx.alerte(" / ".join(str(r[c]) for c in cle), f"{r['Nbre_MEN_ZD']} ménages (> {p['seuil_haut']})", "Haute")
        for _, r in bas.iterrows():
            ctx.alerte(" / ".join(str(r[c]) for c in cle), f"{r['Nbre_MEN_ZD']} ménage(s) (< {p['seuil_bas']})", "Basse")
        ctx.indicateur("nb_zd", len(zd))
        ctx.indicateur("nb_zd_depassement", len(haut))
        ctx.indicateur("nb_zd_sous_seuil", len(bas))
        par_region = zd.groupby("HH2").agg(Nb_ZD=("Nbre_MEN_ZD", "size"), Nb_menages=("Nbre_MEN_ZD", "sum")).reset_index()
        ctx.resultat.tables["Par_region"] = par_region
        ctx.graphique("Ménages et ZD par région", "Par_region", "HH2", ["Nb_ZD", "Nb_menages"], "barh")
        ctx.resultat.resume = (f"{len(zd)} ZD, {len(haut)} au-dessus de {p['seuil_haut']} ménages, "
                               f"{len(bas)} sous {p['seuil_bas']} ménages")


MODULE = MenagesParZD()
