"""Tableaux d'indicateurs du bulletin (bloc « Simulation indicateur », étape 2).

À partir de la base de travail produite par le module « Pondération simulée » (empilée, le cas
échéant, avec les bases de travail d'autres trimestres), ce module reproduit l'ensemble des
tableaux du bulletin et les écrit dans la maquette Excel
``Tableaux_Indicateurs_ENEM_template_DG.xlsx`` → ``Tableaux_Indicateurs_ENEM_DG.xlsx``.

Codes d'origine :
    1_Tabulation_DG_Bulletin_version_amélioré_sim.do  (liste des tableaux, onglets et cellules)
    1_1_Var_objectives_lower.do / 1_2_Indicateur_Bulletin_To_Run.do / Revision_CISE_12112024.do
    programme_master_simple.do / programme_master_simple_ANNUEL.do
    programme_repartition_horiz_FINAL_total.do / programme_repartition_horiz_CORRIGE_ANNUEL.do
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from enem_core import donnees as D
from enem_core import indicateurs as I
from enem_core.execution import ModuleBase
from enem_core.parametres import Booleen, Colonne, Fichier, Liste, Tableau, Texte, TrimestreP
from enem_core.trimestre import Trimestre

from ._communs import G_BASES, p_sortie, p_trimestre

DESAG = ["milieu_resid2", "sexe", "groupe_age4", "niv_inst_ag3"]
DESAG_CISE = ["milieu_resid2", "sexe", "niv_inst_ag3", "branche1"]
ANNEES_ANNUEL = (2024, 2025, 2026, 2027, 2028, 2029, 2030, 2031, 2032, 2033, 2034, 2035, 2036, 2037, 2038, 2039, 2040, 2041, 2042, 2043, 2044, 2045, 2046, 2047, 2048, 2049, 2050)


# ---------------------------------------------------------------------------
# Variables construites dans le do-file de tabulation lui-même
# ---------------------------------------------------------------------------
def variables_tabulation(df: pd.DataFrame) -> pd.DataFrame:
    c = lambda n: I.col(df, n)  # noqa: E731
    pat, mo, cise = c("PAT"), c("MO"), c("CISE_18_new")
    emploi_mo = I.inlist(mo, 1, 2)

    df["var_unitaire"] = 1.0

    # 16. situation de handicap
    h = pd.Series(0.0, index=df.index)
    for var, valeurs in (("dif1a", (2, 3, 4)), ("dif2a", (2, 3, 4)), ("dif3_1", (1,)), ("dif3_2", (1,)),
                         ("dif3_3", (1,)), ("dif3_4", (1,)), ("dif3_5", (1,)), ("dif3_6", (1,)),
                         ("dif3b", (2, 3, 4)), ("dif3d", (2, 3, 4)), ("dif5", (2, 3, 4))):
        h = I.poser(h, I.inlist(c(var), *valeurs), 1)
    if "dif3_aut" in df.columns:
        h = I.poser(h, I.texte(df, "dif3_aut") != "", 1)
    df["sit_handicap"] = h

    # 3. taux de salarisation
    ts = I.poser(pd.Series(np.nan, index=df.index, dtype=float), I.eq(pat, 1) & emploi_mo, 0)
    ts = I.poser(ts, I.eq(pat, 1) & I.eq(cise, 4) & I.eq(mo, 1), 1)
    df["taux_salarisation"] = ts

    # 3. taux d'emploi / 4. taux d'activité
    statut = c("statut_MO")
    te = I.poser(pd.Series(np.nan, index=df.index, dtype=float), emploi_mo, 0)
    te = I.poser(te, emploi_mo & I.eq(statut, 1), 1)
    df["taux_emploi"] = te
    ta = I.poser(pd.Series(np.nan, index=df.index, dtype=float), I.eq(pat, 1), 0)
    ta = I.poser(ta, I.eq(pat, 1) & (I.eq(statut, 1) | I.eq(statut, 2)), 1)
    df["taux_act"] = ta

    # 9. formalité de l'emploi
    inf_emp = c("CISE_18_informel_Emp")
    fe = I.poser(pd.Series(np.nan, index=df.index, dtype=float), I.present(inf_emp), 0)
    fe = I.poser(fe, I.eq(inf_emp, 2), 1)
    df["form_empEP"] = fe

    # 16. NEETs 16-40
    age, pop_emp = c("age"), c("pop_emp")
    dans = I.inrange(age, 16, 40)
    n = I.poser(pd.Series(np.nan, index=df.index, dtype=float), dans, 0)
    n = I.poser(n, (~I.inlist(pop_emp, 1, 2) & I.eq(c("no_education"), 1)
                    & I.eq(c("no_formation"), 1)) & dans, 1)
    df["NEETs_16_40"] = n
    df["groupe_age_16_40"] = (1 * I.inrange(age, 16, 19) + 2 * I.inrange(age, 20, 24)
                              + 3 * I.inrange(age, 25, 29) + 4 * I.inrange(age, 30, 34)
                              + 5 * I.inrange(age, 35, 40)).astype(float)
    return df


# ---------------------------------------------------------------------------
# Liste des tableaux (onglet, cellule, variable, désagrégations, filtre)
# ---------------------------------------------------------------------------
def _f(df, **_):
    return pd.Series(True, index=df.index)


def _pat(d):
    return I.eq(I.col(d, "PAT"), 1)


def _mo_present(d):
    return I.present(I.col(d, "MO"))


def _annuel(d):
    return I.col(d, "annee").isin(ANNEES_ANNUEL)


def _moe12(d):
    return _pat(d) & I.inlist(I.col(d, "MOE"), 1, 2)


TABLEAUX = [
    # --- annuels -----------------------------------------------------------
    dict(titre="Personnes en situation de handicap", feuille="Nbre_hancicap", cellule="B6",
         var="sit_handicap", desag=["milieu_resid2", "sexe", "groupe_age4"], effectifs=True,
         periode="annee", poids="var_unitaire",
         filtre=lambda d: _annuel(d) & I.eq(I.col(d, "rgmen"), 1)),
] + [
    dict(titre=f"Sous-utilisation annuelle {v} ({'taux' if tx else 'effectifs'})",
         feuille="chomage_Annuel", cellule=cel, var=v, desag=DESAG, taux=tx, effectifs=not tx,
         periode="annee", filtre=flt)
    for v, cel, tx, flt in [
        ("SU1", "B7", True, lambda d: _annuel(d) & _mo_present(d)),
        ("SU2", "D7", True, lambda d: _annuel(d) & _pat(d) & _mo_present(d)),
        ("SU3", "F7", True, lambda d: _annuel(d) & _moe12(d)),
        ("SU4", "H7", True, lambda d: _annuel(d) & _moe12(d)),
        ("SU1", "J7", False, lambda d: _annuel(d) & _mo_present(d)),
        ("SU2", "L7", False, lambda d: _annuel(d) & _pat(d) & _mo_present(d)),
        ("SU3", "N7", False, lambda d: _annuel(d) & _moe12(d)),
        ("SU4", "P7", False, lambda d: _annuel(d) & _moe12(d)),
    ]
] + [
    # --- trimestriels ------------------------------------------------------
    dict(titre="Taux de pluriactivité", feuille="Taux_pluriactivite", cellule="B6",
         var="pluriactivite", desag=DESAG, taux=True, effectifs=True,
         filtre=lambda d: _pat(d) & I.eq(I.col(d, "MO"), 1) & I.present(I.col(d, "pluriactivite"))),
    dict(titre="Taux de salarisation", feuille="Taux_salarisation", cellule="B6",
         var="taux_salarisation", desag=DESAG, taux=True, effectifs=True,
         filtre=lambda d: I.present(I.col(d, "taux_salarisation"))),
    dict(titre="Population en âge de travailler", feuille="PAT", cellule="B6", var="PAT",
         desag=["milieu_resid2", "sexe", "niv_inst_ag3"], taux=True, effectifs=True),
    dict(titre="Répartition de la PAT (taux)", feuille="Repartition_PAT", cellule="B6",
         var="statut_MO", desag=DESAG, taux=True, moteur="horiz", filtre=_pat),
    dict(titre="Répartition de la PAT (effectifs)", feuille="Repartition_PAT", cellule="AL6",
         var="statut_MO", desag=DESAG, effectifs=True, moteur="horiz", filtre=_pat),
    dict(titre="Taux d'emploi", feuille="Taux_emploi", cellule="B6", var="taux_emploi", desag=DESAG,
         taux=True, effectifs=True, filtre=lambda d: _pat(d) & _mo_present(d)),
    dict(titre="Taux d'activité", feuille="Taux_activite", cellule="B6", var="taux_act", desag=DESAG,
         taux=True, effectifs=True, filtre=_pat),
    dict(titre="Taux de chômage", feuille="Taux_chomage", cellule="B6", var="SU1", desag=DESAG,
         taux=True, effectifs=True, filtre=_mo_present),
    dict(titre="Main d'œuvre potentielle", feuille="MOP", cellule="B6", var="MOPOT_bis", desag=DESAG,
         taux=True, effectifs=True, filtre=lambda d: I.eq(I.col(d, "statut_MO"), 3)),
    dict(titre="Décomposition de la MOP (taux)", feuille="Decompo_MOP", cellule="B6", var="MOPOT",
         desag=DESAG, taux=True, moteur="horiz",
         filtre=lambda d: I.eq(I.col(d, "MOPOT_bis"), 1)),
    dict(titre="Décomposition de la MOP (effectifs)", feuille="Decompo_MOP", cellule="AC6", var="MOPOT",
         desag=DESAG, effectifs=True, moteur="horiz",
         filtre=lambda d: I.eq(I.col(d, "MOPOT_bis"), 1)),
] + [
    dict(titre=f"Sous-utilisation {v} ({'taux' if tx else 'effectifs'})", feuille="Sous_utilisation_MO",
         cellule=cel, var=v, desag=DESAG, taux=tx, effectifs=not tx, filtre=flt)
    for v, cel, tx, flt in [
        ("SU1", "B7", True, _mo_present),
        ("SU2", "K7", True, lambda d: _pat(d) & _mo_present(d)),
        ("SU3", "T7", True, _moe12),
        ("SU4", "AC7", True, _moe12),
        ("SU1", "AL7", False, _mo_present),
        ("SU2", "AU7", False, lambda d: _pat(d) & _mo_present(d)),
        ("SU3", "BD7", False, _moe12),
        ("SU4", "BM7", False, _moe12),
    ]
] + [
    dict(titre="Formalité de l'emploi", feuille="Formalite_emploi", cellule="B6", var="form_empEP",
         desag=DESAG, taux=True, effectifs=True,
         filtre=lambda d: I.present(I.col(d, "CISE_18_informel_Emp"))),
    dict(titre="Emploi vulnérable", feuille="Emploi_vulnerable", cellule="B6", var="emp_vul",
         desag=DESAG, taux=True, effectifs=True, filtre=lambda d: I.present(I.col(d, "emp_vul"))),
    dict(titre="Pluriactivité", feuille="Pluriactivite", cellule="B6", var="pluriactivite",
         desag=DESAG, taux=True, effectifs=True,
         filtre=lambda d: I.present(I.col(d, "pluriactivite"))),
    dict(titre="CISE – autorité", feuille="CISE_autorite", cellule="B6", var="pop_emp_dich",
         desag=["sit_empEP_Autorite"], taux=True, effectifs=True),
    dict(titre="CISE – risque économique (taux)", feuille="CISE_risque", cellule="B6",
         var="CISE_18_new", desag=DESAG_CISE, taux=True, moteur="horiz",
         filtre=lambda d: I.present(I.col(d, "CISE_18_new"))),
    dict(titre="CISE – risque économique (effectifs)", feuille="CISE_risque", cellule="BD6",
         var="CISE_18_new", desag=DESAG_CISE, effectifs=True, moteur="horiz",
         filtre=lambda d: I.present(I.col(d, "CISE_18_new"))),
    dict(titre="CISE – 10 modalités (taux)", feuille="CISE_risque_10", cellule="B6",
         var="CISE_18_niv2", desag=DESAG_CISE, taux=True, moteur="horiz",
         filtre=lambda d: I.present(I.col(d, "CISE_18_niv2"))),
    dict(titre="CISE – 10 modalités (effectifs)", feuille="CISE_risque_10", cellule="CW6",
         var="CISE_18_niv2", desag=DESAG_CISE, effectifs=True, moteur="horiz",
         filtre=lambda d: I.present(I.col(d, "CISE_18_niv2"))),
    dict(titre="Branche d'activité (taux)", feuille="Branche_activite", cellule="B6", var="branche1",
         desag=DESAG, taux=True, moteur="horiz",
         filtre=lambda d: I.present(I.col(d, "branche1")) & I.ne(I.col(d, "groupe_age4"), 0)),
    dict(titre="Branche d'activité (effectifs)", feuille="Branche_activite", cellule="AU6",
         var="branche1", desag=DESAG, effectifs=True, moteur="horiz",
         filtre=lambda d: I.present(I.col(d, "branche1")) & I.ne(I.col(d, "groupe_age4"), 0)),
    dict(titre="NEETs 16-40 ans", feuille="NEETs", cellule="B6", var="NEETs_16_40",
         desag=["milieu_resid2", "sexe", "groupe_age_16_40", "niv_inst_ag3"], taux=True, effectifs=True,
         filtre=lambda d: I.present(I.col(d, "NEETs_16_40"))),
]


class TableauxBulletin(ModuleBase):
    id = "tableaux_bulletin"
    nom = "Simulation indicateur – 2. Tableaux du bulletin"
    nom_court = "Tableaux bulletin"
    description = ("Calcule les indicateurs du bulletin (PAT, emploi, chômage, sous-utilisation, CISE 18, "
                   "NEETs…) à partir de la base de travail pondérée et les écrit dans la maquette Excel "
                   "Tableaux_Indicateurs_ENEM_DG.xlsx.")
    equipe = "Coordination"
    frequence_jours = 90
    frequence_libelle = "Chaque trimestre"
    couleur = "#2E86AB"
    entrees = ("Base de travail du trimestre en cours (sortie du module « Pondération simulée ») + bases de "
               "travail des trimestres à empiler + maquette Excel")
    sorties = ("Tableaux_Indicateurs_ENEM_DG.xlsx (maquette renseignée), "
               "Recapitulatif_tableaux_<T>.xlsx (journal des tableaux produits)")
    code_origine = ["Simulation_Indicateur/1_Tabulation_DG_Bulletin_version_amélioré_sim.do",
                    "Simulation_Indicateur/1_1_Var_objectives_lower.do",
                    "Simulation_Indicateur/1_2_Indicateur_Bulletin_To_Run.do",
                    "Simulation_Indicateur/Revision_CISE_12112024.do",
                    "Simulation_Indicateur/programme_master_simple.do",
                    "Simulation_Indicateur/programme_master_simple_ANNUEL.do",
                    "Simulation_Indicateur/programme_repartition_horiz_FINAL_total.do",
                    "Simulation_Indicateur/programme_repartition_horiz_CORRIGE_ANNUEL.do"]
    mots_cles = "bulletin indicateurs tabulation chômage emploi CISE NEETs maquette excel"
    ordre = 76
    sous_dossier = "Simulation_Indicateur"

    @property
    def parametres(self):
        base = Fichier("base_courante", "Base de travail du trimestre en cours (.dta)", "", groupe=G_BASES,
                       types=[("Stata", "*.dta")],
                       aide="Sortie du module « Pondération simulée » : Base_Travail_BT_vf_26T3.dta.")
        base.note = ("Les tableaux sont calculés sur la base empilée (trimestre en cours + trimestres "
                     "ajoutés ci-dessous). Les colonnes de la maquette suivent l'ordre des valeurs de la "
                     "variable « trimestre » (et « annee » pour les tableaux annuels).")
        return [
            p_trimestre(),
            base,
            Tableau("bases_empilees", "Bases de travail à empiler (append)", [], groupe=G_BASES,
                    colonnes=[Colonne("fichier", "Base de travail d'un autre trimestre (.dta)", "fichier", 46)],
                    maxi_lignes=12,
                    aide="Ex. Base_Travail_BT_vf_26T1.dta. Chaque base ajoute ses trimestres aux colonnes "
                         "des tableaux."),
            Texte("var_ponderation", "Variable de pondération trimestrielle", "pmencor_ind", groupe=G_BASES),
            Texte("var_ponderation_annuelle", "Variable de pondération annuelle", "pmencor_ind_annuel",
                  groupe=G_BASES,
                  aide="Créée à partir de la pondération trimestrielle si elle est absente ; divisée par 4 "
                       "pour les trimestres listés ci-dessous."),
            Liste("trimestres_quart", "Trimestres dont la pondération annuelle est divisée par 4",
                  "25T1 25T2 25T3 25T4", groupe=G_BASES, obligatoire=False),
            Texte("var_trimestre", "Variable identifiant le trimestre", "trimestre", groupe=G_BASES),
            Texte("var_annee", "Variable identifiant l'année", "annee", groupe=G_BASES),
            Booleen("reconstruire", "Reconstruire les variables du bulletin (1_1, 1_2, CISE)", False,
                    groupe="Traitement",
                    aide="À cocher si les bases empilées ne contiennent pas encore les variables "
                         "(PAT, MO, SU1…, CISE_18_new)."),
            Fichier("maquette", "Maquette Excel des tableaux", "", groupe="Sortie",
                    types=[("Excel", "*.xlsx")],
                    aide="Tableaux_Indicateurs_ENEM_template_DG.xlsx (dossier Resultats_Tab)."),
            Texte("nom_resultat", "Nom du fichier de résultats", "Tableaux_Indicateurs_ENEM_DG.xlsx",
                  groupe="Sortie"),
            p_sortie(),
        ]

    # ------------------------------------------------------------------
    def executer(self, ctx, p):
        t = Trimestre.depuis(p["trimestre"])
        var_p, var_pa = p["var_ponderation"], p["var_ponderation_annuelle"]
        var_t, var_a = p["var_trimestre"], p["var_annee"]

        ctx.progression(5, "Lecture des bases de travail")
        base = I.normaliser_noms(D.lire_dta(p["base_courante"]))
        ctx.journal(f"Base du trimestre en cours : {len(base):,} ligne(s)".replace(",", " "))
        morceaux = [base]
        for ligne in p["bases_empilees"]:
            chemin = (ligne.get("fichier") or "").strip()
            if not chemin:
                continue
            autre = I.normaliser_noms(D.lire_dta(chemin))
            ctx.journal(f"  + {chemin} : {len(autre):,} ligne(s)".replace(",", " "))
            morceaux.append(autre)
        if len(morceaux) > 1:
            base = D.empiler(morceaux)
        base = base.reset_index(drop=True)
        ctx.verifier_arret()

        for c in (var_p, var_t):
            if c not in base.columns:
                raise D.ErreurDonnees(f"Variable « {c} » absente de la base empilée.")
        if var_a not in base.columns:
            raise D.ErreurDonnees(f"Variable « {var_a} » absente : elle est nécessaire aux tableaux annuels.")

        if p["reconstruire"]:
            ctx.progression(20, "Construction des variables du bulletin")
            base = I.construire_variables(base, journal=ctx.journal)
        base = variables_tabulation(base)

        # niv_inst_ag3 : la modalité 0 est mise à manquant (do-file de tabulation)
        if "niv_inst_ag3" in base.columns:
            n3 = I.col(base, "niv_inst_ag3")
            base["niv_inst_ag3"] = n3.where(~I.eq(n3, 0))

        # pondération annuelle
        if var_pa not in base.columns:
            base[var_pa] = I.col(base, var_p)
            ctx.journal(f"  Variable « {var_pa} » absente : initialisée à « {var_p} »")
        quarts = [str(x).strip().upper() for x in p["trimestres_quart"]]
        if quarts:
            masque = I.texte(base, var_t).str.upper().isin(quarts)
            base.loc[masque, var_pa] = I.col(base, var_p)[masque] / 4
            ctx.journal(f"  Pondération annuelle divisée par 4 pour {int(masque.sum()):,} ligne(s) "
                        f"({', '.join(quarts)})".replace(",", " "))

        trimestres = I.niveaux(base[var_t])
        annees = I.niveaux(base[var_a])
        ctx.journal(f"  Trimestres présents : {', '.join(str(x) for x in trimestres)}")
        ctx.journal(f"  Années présentes    : {', '.join(str(x) for x in annees)}")
        ctx.journal(f"  ⚠ Les colonnes de la maquette sont remplies dans cet ordre, sans laisser de trou : "
                    f"empilez toutes les bases de travail des trimestres qui figurent dans l'en-tête des "
                    f"onglets ({len(trimestres)} trimestre(s) et {len(annees)} année(s) disponibles ici).")

        # --- maquette
        ctx.progression(30, "Préparation de la maquette")
        destination = I.preparer_maquette(p["maquette"], ctx.chemin(p["nom_resultat"]))
        classeur = I.Classeur(destination)
        feuilles_dispo = set(classeur.feuilles())

        # --- tableaux
        recap, produits, ignores = [], 0, 0
        total = len(TABLEAUX)
        for k, spec in enumerate(TABLEAUX, start=1):
            ctx.verifier_arret()
            ctx.progression(30 + int(60 * k / total), f"Tableau {k}/{total} : {spec['titre']}")
            periode = spec.get("periode", "trimestre")
            var_periode = var_a if periode == "annee" else var_t
            poids = spec.get("poids") or (var_pa if periode == "annee" else var_p)
            manquantes = [v for v in [spec["var"]] + list(spec["desag"])
                          if v not in base.columns or base[v].dropna().empty]
            raison = ""
            if spec["feuille"] not in feuilles_dispo:
                raison = "onglet absent de la maquette"
            elif manquantes:
                raison = "variable(s) absente(s) ou vide(s) : " + ", ".join(manquantes)
            if raison:
                ignores += 1
                ctx.journal(f"  ⊘ {spec['titre']} ({spec['feuille']}!{spec['cellule']}) : {raison}")
                recap.append({"Tableau": spec["titre"], "Onglet": spec["feuille"], "Cellule": spec["cellule"],
                              "Variable": spec["var"], "Périodicité": periode, "Statut": "non produit",
                              "Détail": raison})
                continue
            sous = base
            if spec.get("filtre"):
                sous = base[spec["filtre"](base).fillna(False)]
            if sous.empty:
                ignores += 1
                ctx.journal(f"  ⊘ {spec['titre']} : aucune observation après filtrage")
                recap.append({"Tableau": spec["titre"], "Onglet": spec["feuille"], "Cellule": spec["cellule"],
                              "Variable": spec["var"], "Périodicité": periode, "Statut": "non produit",
                              "Détail": "aucune observation après filtrage"})
                continue
            if spec.get("moteur") == "horiz":
                matrice = I.repartition_horiz(sous, spec["var"], list(spec["desag"]), var_periode,
                                              effectifs=spec.get("effectifs", False),
                                              taux=spec.get("taux", False), poids=poids,
                                              lignes_corrigees=(periode == "annee"))
            else:
                matrice = I.indicateur_simple(sous, spec["var"], list(spec["desag"]), var_periode,
                                              effectifs=spec.get("effectifs", False),
                                              taux=spec.get("taux", False), poids=poids)
            classeur.ecrire(spec["feuille"], spec["cellule"], matrice)
            produits += 1
            ctx.journal(f"  ✓ {spec['titre']} → {spec['feuille']}!{spec['cellule']} "
                        f"({matrice.shape[0]}×{matrice.shape[1]}, {len(sous):,} obs.)".replace(",", " "))
            recap.append({"Tableau": spec["titre"], "Onglet": spec["feuille"], "Cellule": spec["cellule"],
                          "Variable": spec["var"], "Périodicité": periode,
                          "Statut": "produit", "Détail": f"{matrice.shape[0]} lignes × {matrice.shape[1]} "
                                                         f"colonnes, {len(sous)} observations"})
        classeur.sauver()
        ctx.fichier_produit(destination)
        ctx.journal(f"  ✓ Maquette renseignée : {destination.name}")

        # --- récapitulatif et indicateurs de contrôle
        ctx.progression(93, "Récapitulatif")
        recapitulatif = pd.DataFrame(recap)
        controle = self._controle(base, var_t, var_p)
        ctx.exporter(f"Recapitulatif_tableaux_{t.code}.xlsx",
                     {"Tableaux": recapitulatif, "Controle": controle},
                     titre=f"Tableaux du bulletin – {t.libelle} (pondération simulée, estimations provisoires)")
        if ignores:
            ctx.alerte("Tableaux", f"{ignores} tableau(x) non produit(s) : voir la feuille « Tableaux » du "
                                   "récapitulatif", "Moyenne")
        for _, ligne in controle.iterrows():
            ctx.indicateur("taux_chomage", float(ligne["Taux de chômage (%)"]),
                           niveau="trimestre", cle=str(ligne["Trimestre"]))
            ctx.indicateur("taux_emploi", float(ligne["Taux d'emploi (%)"]),
                           niveau="trimestre", cle=str(ligne["Trimestre"]))
        ctx.graphique("Taux de chômage et d'emploi par trimestre", "Controle", "Trimestre",
                      ["Taux de chômage (%)", "Taux d'emploi (%)"], "bar", etiquettes=True)
        ctx.resultat.resume = (f"{produits}/{total} tableaux écrits dans {destination.name}"
                               + (f" – {ignores} non produit(s)" if ignores else ""))

    # ------------------------------------------------------------------
    @staticmethod
    def _controle(base: pd.DataFrame, var_t: str, var_p: str) -> pd.DataFrame:
        """Quelques indicateurs de synthèse par trimestre, pour vérification rapide."""
        lignes = []
        poids = pd.to_numeric(base[var_p], errors="coerce").fillna(0)
        mo, su1, te = I.col(base, "MO"), I.col(base, "SU1"), I.col(base, "taux_emploi")
        pat = I.col(base, "PAT")
        for t in I.niveaux(base[var_t]):
            m = base[var_t] == t
            pop_mo = poids[m & I.inlist(mo, 1, 2)].sum()
            chom = poids[m & I.eq(su1, 1)].sum()
            denom_e = poids[m & I.eq(pat, 1) & I.present(mo)].sum()
            emploi = poids[m & I.eq(pat, 1) & I.eq(te, 1)].sum()
            lignes.append({
                "Trimestre": t,
                "Observations": int(m.sum()),
                "Population pondérée": round(float(poids[m].sum()), 0),
                "Main d'œuvre": round(float(pop_mo), 0),
                "Taux de chômage (%)": round(100 * chom / pop_mo, 2) if pop_mo else 0.0,
                "Taux d'emploi (%)": round(100 * emploi / denom_e, 2) if denom_e else 0.0,
            })
        return pd.DataFrame(lignes)


MODULE = TableauxBulletin()
