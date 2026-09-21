"""Cohérence inter-passages : sexe (M5) ou statut dans l'emploi (EN_EMP).

Codes d'origine : Correction_between_sexe.do, Correction_between_Emploi.do
Décisions : un seul module avec liste déroulante (V6), signalement sans modifier la base
(CP1), les deux sens (CP2), résidents uniquement (CP2, CP4), passage de référence choisi
par l'utilisateur (CP3), destinataires téléopérateurs (CP5), rapport des doublons (CP6),
dossier daté par exécution (CP7), cohortes saisies par l'utilisateur (T6).
"""

from __future__ import annotations

import pandas as pd

from enem_core import donnees as D
from enem_core.execution import ModuleBase
from enem_core.parametres import Booleen, Choix, Entier, Texte
from enem_core.trimestre import Trimestre

from ._communs import (charger_individus, exiger, num, p_cohortes, p_fichier_menage, p_sortie, p_trimestre,
                       p_versions_menage, statut_residence)

VARIABLES = {
    "SEXE (M5)": {"var": "M5", "libelles": {1: "Masculin", 2: "Féminin"}},
    "EMPLOI (EN_EMP)": {"var": "EN_EMP", "libelles": {1: "En emploi", 0: "Pas en emploi"}},
}


class CoherencePassages(ModuleBase):
    id = "coherence_passages"
    nom = "Cohérence inter-passages (sexe / emploi)"
    nom_court = "Cohérence sexe / emploi"
    description = ("Compare, pour les ménages réinterrogés par les téléopérateurs, le sexe ou le statut dans "
                   "l'emploi renseigné ce trimestre avec la valeur renseignée lors du passage de référence "
                   "(passage 1 terrain). Produit la liste des incohérences à vérifier, sans modifier la base.")
    equipe = "Téléopérateurs"
    frequence_jours = 7
    frequence_libelle = "Hebdomadaire"
    couleur = "#3E8E7E"
    entrees = "Base du trimestre en cours (ménage + membres) et bases des trimestres d'origine des cohortes"
    sorties = "rapport_cohorte_<n>.xlsx, rapport_consolide.xlsx (par cohorte, par téléopérateur), doublons"
    code_origine = ["Code_status_sexe/Correction_between_sexe.do",
                    "Code_status_emploi/Correction_between_Emploi.do"]
    mots_cles = "sexe emploi EN_EMP M5 cohorte réinterrogation téléopérateur incohérence"
    ordre = 40
    sous_dossier = "Teleoperateur"

    @property
    def parametres(self):
        return [
            p_trimestre(),
            Choix("variable", "Variable à contrôler", "SEXE (M5)", groupe="Général", options=list(VARIABLES)),
            p_versions_menage("Dossiers des versions de la base du trimestre en cours"),
            p_fichier_menage(),
            self._cohortes(),
            Entier("rgmen_reference", "Passage de référence dans les bases d'origine (rgmen)", 1, groupe="Cohortes",
                   mini=1, maxi=9, aide="1 = passage terrain (par défaut)."),
            Texte("cle_menage_ref", "Variable clé ménage du passage de référence", "V1interviewkey",
                  groupe="Appariement"),
            Texte("cle_membre_ref", "Variable clé individu du passage de référence", "membre_id_v1",
                  groupe="Appariement"),
            Booleen("filtre_residence", "Restreindre aux résidents (Statut_Res == 1)", True, groupe="Appariement"),
            p_sortie(),
        ]

    @staticmethod
    def _cohortes():
        param = p_cohortes()
        param.note = ("Il s'agit de préciser les dossiers du 1er passage des trimestres d'origine : "
                      "pour chaque cohorte réinterrogée ce trimestre, indiquez son trimestre d'origine, "
                      "la valeur de rgmen qui lui correspond dans la base en cours, puis le dossier "
                      "contenant la base de son 1er passage (bouton « Parcourir… »).")
        return param

    def _base_reference(self, ctx, ligne, var, p):
        dossier = ligne.get("dossier")
        if not dossier:
            raise D.ErreurDonnees(f"Cohorte {ligne.get('libelle')} : dossier des bases non renseigné.")
        t = Trimestre.depuis(ligne["libelle"])
        men = D.lire_versions([dossier], t.fichier_menage, journal=ctx.journal)
        mem = D.lire_versions([dossier], "membres.dta", journal=ctx.journal)
        ref = D.fusion_menage_membres(men, mem)
        exiger(ref, ["rgmen", var, "membres__id"], f"la base {t.fichier_menage}")
        ref = ref[num(ref, "rgmen") == p["rgmen_reference"]]
        ref = ref.assign(**{f"{var}_ref": num(ref, var)})
        ref = ref[ref[f"{var}_ref"].notna()]
        ref = ref.rename(columns={"interview__key": "cle_menage", "membres__id": "cle_membre"})
        ref["cle_membre"] = pd.to_numeric(ref["cle_membre"], errors="coerce")
        ref["cle_menage"] = ref["cle_menage"].astype(str).str.strip()
        garder = ["cle_menage", "cle_membre", f"{var}_ref"] + (["M0"] if "M0" in ref.columns else [])
        ref = ref[garder].drop_duplicates(["cle_menage", "cle_membre"])
        return ref.rename(columns={"M0": "M0_ref"})

    def executer(self, ctx, p):
        t = Trimestre.depuis(p["trimestre"])
        choix = VARIABLES[p["variable"]]
        var, libs = choix["var"], choix["libelles"]
        cohortes = p["cohortes"]
        if not cohortes:
            raise D.ErreurDonnees("Ajoutez au moins une cohorte de réinterrogation.")
        ctx.progression(5, "Lecture de la base du trimestre en cours")
        base = charger_individus(ctx, p)
        cm, ci = p["cle_menage_ref"], p["cle_membre_ref"]
        exiger(base, ["rgmen", var, cm, ci], "la base du trimestre en cours")
        # doublons (CP6)
        cles_dup = D.colonnes_presentes(base, ["interview__id", "membres__id", "M0"])
        doublons = base[base.duplicated(cles_dup, keep=False)][cles_dup + D.colonnes_presentes(
            base, ["interview__key", "rgmen", "HH2", "HH13"])]
        if p["filtre_residence"]:
            avant = len(base)
            base = base[statut_residence(base)]
            ctx.journal(f"  Résidents conservés : {len(base):,} / {avant:,}".replace(",", " "))
        base = base.assign(cle_menage=base[cm].astype(str).str.strip(),
                           cle_membre=pd.to_numeric(base[ci], errors="coerce"))
        rapports = []
        for k, ligne in enumerate(cohortes):
            ctx.progression(15 + 65 * k / len(cohortes), f"Cohorte rgmen={ligne['rgmen']} ({ligne['libelle']})")
            cur = base[num(base, "rgmen") == ligne["rgmen"]]
            cur = cur.assign(**{f"{var}_trimestre_actuel": num(cur, var)})
            cur = cur[cur["cle_membre"].notna() & cur[f"{var}_trimestre_actuel"].notna()]
            cur = cur.drop_duplicates(["cle_menage", "cle_membre"])
            ref = self._base_reference(ctx, ligne, var, p)
            m = cur.merge(ref, on=["cle_menage", "cle_membre"], how="inner")
            inc = m[m[f"{var}_ref"] != m[f"{var}_trimestre_actuel"]].copy()
            ctx.journal(f"  Apparié(s) : {len(m)} ; incohérence(s) : {len(inc)}")
            inc["cohorte"] = ligne["rgmen"]
            inc["trimestre_reference"] = ligne["libelle"]
            inc["valeur_reference"] = inc[f"{var}_ref"].map(libs)
            inc["valeur_trimestre_actuel"] = inc[f"{var}_trimestre_actuel"].map(libs)
            inc["type_ecart"] = inc["valeur_reference"].astype(str) + " → " + inc["valeur_trimestre_actuel"].astype(str)
            inc["action"] = f"Vérifier {var} auprès du ménage (valeur au passage de référence : " + \
                inc[f"{var}_ref"].astype("Int64").astype(str) + ")"
            cols = D.colonnes_presentes(inc, [
                "cohorte", "trimestre_reference", "interview__key", "membres__id", "M0", "M0_ref",
                "cle_menage", "cle_membre", f"{var}_ref", f"{var}_trimestre_actuel", "valeur_reference",
                "valeur_trimestre_actuel", "type_ecart", "action", "HH2", "HH12", "HH13"])
            out = D.appliquer_libelles(inc[cols], ["HH2", "HH12", "HH13"], source=base)
            out = out.rename(columns={"cle_menage": "interview__key_ref", "cle_membre": "membres__id_ref",
                                      "HH13": "Teleoperateur"})
            ctx.exporter(f"rapport_{var}_cohorte_{ligne['rgmen']}.xlsx", {"Incoherences": out}, afficher=False)
            rapports.append(out)
            ctx.indicateur(f"incoherences_{var}", len(out), "cohorte", ligne["libelle"])
            ctx.indicateur(f"apparies_{var}", len(m), "cohorte", ligne["libelle"])
        ctx.progression(85, "Consolidation")
        cons = pd.concat(rapports, ignore_index=True) if rapports else pd.DataFrame()
        if not cons.empty:
            cons = cons.drop_duplicates(["interview__key_ref", "membres__id_ref"])
        resume = (cons.groupby(["cohorte", "trimestre_reference", "type_ecart"]).size()
                  .rename("Nombre").reset_index()) if not cons.empty else pd.DataFrame()
        if not resume.empty:
            resume.insert(0, "Cohorte_ecart", resume["trimestre_reference"] + " : " + resume["type_ecart"])
        par_type = (cons.groupby("type_ecart").size().rename("Nombre").reset_index()
                    if not cons.empty else pd.DataFrame())
        feuilles = {"Consolide": cons, "Resume": resume, "Par_type_ecart": par_type}
        if not cons.empty and "Teleoperateur" in cons.columns:
            par_tele = cons.groupby("Teleoperateur").size().rename("Nb_incoherences").reset_index()
            feuilles["Par_teleoperateur"] = par_tele.sort_values("Nb_incoherences", ascending=False)
            for _, r in par_tele.iterrows():
                ctx.alerte(str(r["Teleoperateur"]), f"{r['Nb_incoherences']} incohérence(s) de {var} à vérifier")
            for tele, sub in cons.groupby("Teleoperateur"):
                feuilles[f"T_{tele}"[:31]] = sub
        feuilles["Doublons"] = doublons
        ctx.exporter(f"rapport_consolide_{var}_{t.code}.xlsx", feuilles,
                     afficher=["Consolide", "Resume", "Par_type_ecart", "Par_teleoperateur", "Doublons"],
                     titre=f"Incohérences de {var} entre passages – {t.libelle} (signalement, base non modifiée)")
        if not resume.empty:
            ctx.graphique(f"Incohérences de {var} par type d'écart", "Par_type_ecart", "type_ecart", "Nombre",
                          "bar", etiquettes=True)
            ctx.graphique(f"Incohérences de {var} par cohorte et type d'écart", "Resume", "Cohorte_ecart",
                          "Nombre", "bar", etiquettes=True)
        if len(doublons):
            ctx.alerte("Base du trimestre", f"{len(doublons)} ligne(s) en double (interview__id, membres__id, M0)",
                       "Basse")
        ctx.resultat.resume = f"{len(cons)} incohérence(s) de {var} sur {len(cohortes)} cohorte(s)"


MODULE = CoherencePassages()
