"""Fenêtre principale : en-tête ANSTAT, barre de navigation, zone des écrans."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from enem_core import RACINE_PROJET, VERSION
from enem_core.configuration import Profil
from enem_core.exports import lire_excel_toutes_feuilles
from enem_core.stockage import Stockage
from modules import charger_modules

from . import theme as T
from .vues import (Alertes, APropos, Catalogue, Evolution, FenetreResultats, Historique, ParametresGeneraux,
                   TableauDeBord, TachesGantt, VueModule)


class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"ANSTAT – Suivi de la collecte ENEM (v{VERSION})")
        self.geometry("1440x880")
        self.minsize(1100, 680)
        T.appliquer(self)
        try:
            self._icone = tk.PhotoImage(file=str(RACINE_PROJET / "assets" / "icone.png"))
            self.iconphoto(True, self._icone)
        except tk.TclError:
            pass
        self.profil = Profil()
        self.stockage = Stockage(self.profil.globaux.get("base_donnees")
                                 or RACINE_PROJET / "donnees_app" / "suivi_enem.sqlite")
        self.modules = charger_modules()
        self.vues: dict[str, ttk.Frame] = {}
        self.boutons: dict[str, tk.Label] = {}
        self.actif = None
        self._construire()
        self.afficher("accueil")
        self.protocol("WM_DELETE_WINDOW", self.quitter)

    def report_callback_exception(self, exc, val, tb):
        """Toute erreur d'interface est affichée et enregistrée dans donnees_app/erreurs.log."""
        import datetime as dt
        import traceback
        trace = "".join(traceback.format_exception(exc, val, tb))
        journal = RACINE_PROJET / "donnees_app" / "erreurs.log"
        try:
            journal.parent.mkdir(parents=True, exist_ok=True)
            with journal.open("a", encoding="utf-8") as f:
                f.write(f"\n--- {dt.datetime.now():%Y-%m-%d %H:%M:%S} ---\n{trace}")
        except OSError:
            pass
        messagebox.showerror("Erreur", f"{val}\n\nDétail enregistré dans {journal}")

    # ------------------------------------------------------------------
    def _construire(self):
        entete = tk.Frame(self, bg=T.BLANC, height=74)
        entete.pack(fill="x")
        try:
            self._logo = tk.PhotoImage(file=str(RACINE_PROJET / "assets" / "logo_anstat.png"))
            tk.Label(entete, image=self._logo, bg=T.BLANC).pack(side="left", padx=(14, 8), pady=4)
        except tk.TclError:
            tk.Label(entete, text="ANSTAT", bg=T.BLANC, fg=T.ORANGE, font=(T.POLICE, 22, "bold")).pack(side="left", padx=14)
        bloc = tk.Frame(entete, bg=T.BLANC)
        bloc.pack(side="left", padx=10)
        tk.Label(bloc, text="Suivi de la collecte ENEM", bg=T.BLANC, fg=T.VERT,
                 font=(T.POLICE, 18, "bold")).pack(anchor="w")
        tk.Label(bloc, text="Enquête Nationale sur l'Emploi auprès des Ménages – unification des codes de suivi",
                 bg=T.BLANC, fg=T.GRIS, font=(T.POLICE, 9)).pack(anchor="w")
        self.badge = tk.Label(entete, bg=T.ORANGE, fg=T.BLANC, font=(T.POLICE, 11, "bold"), padx=12, pady=4)
        self.badge.pack(side="right", padx=14)
        self.utilisateur = tk.Label(entete, bg=T.BLANC, fg=T.GRIS, font=(T.POLICE, 9))
        self.utilisateur.pack(side="right", padx=4)
        tk.Frame(self, bg=T.ORANGE, height=3).pack(fill="x")
        corps = tk.Frame(self, bg=T.FOND)
        corps.pack(fill="both", expand=True)
        self.nav = tk.Frame(corps, bg=T.VERT, width=270)
        self.nav.pack(side="left", fill="y")
        self.nav.pack_propagate(False)
        self.zone = tk.Frame(corps, bg=T.FOND)
        self.zone.pack(side="left", fill="both", expand=True)
        self._navigation()
        self.rafraichir_barre()

    def _titre_nav(self, texte):
        tk.Label(self.nav, text=texte.upper(), bg=T.VERT, fg="#BFD3C7", font=(T.POLICE, 8, "bold"),
                 anchor="w").pack(fill="x", padx=16, pady=(9, 1))

    def _bouton_nav(self, cle, texte, couleur=None):
        cadre = tk.Frame(self.nav, bg=T.VERT, cursor="hand2")
        cadre.pack(fill="x")
        pastille = tk.Frame(cadre, bg=couleur or T.VERT, width=6)
        pastille.pack(side="left", fill="y")
        lab = tk.Label(cadre, text=texte, bg=T.VERT, fg=T.BLANC, anchor="w", padx=12, pady=4,
                       font=(T.POLICE, 10), wraplength=235, justify="left")
        lab.pack(side="left", fill="x", expand=True)
        for w in (cadre, lab):
            w.bind("<Button-1>", lambda e, c=cle: self.afficher(c))
            w.bind("<Enter>", lambda e, l=lab, c=cle: c != self.actif and l.configure(bg=T.VERT_FONCE))
            w.bind("<Leave>", lambda e, l=lab, c=cle: c != self.actif and l.configure(bg=T.VERT))
        self.boutons[cle] = lab

    def _navigation(self):
        self._titre_nav("Accueil")
        self._bouton_nav("accueil", "🏠  Tableau de bord")
        self._bouton_nav("catalogue", "📚  Catalogue des codes")
        groupes = {"Préparation des données": [], "Suivi terrain": [], "Suivi téléopérateurs": [],
                   "Coordination": []}
        for m in self.modules:
            if m.id == "preparation_bases":
                groupes["Préparation des données"].append(m)
            elif m.sous_dossier == "Terrain":
                groupes["Suivi terrain"].append(m)
            elif m.sous_dossier == "Teleoperateur":
                groupes["Suivi téléopérateurs"].append(m)
            else:
                groupes["Coordination"].append(m)
        for g, mods in groupes.items():
            if mods:
                self._titre_nav(g)
                for m in mods:
                    self._bouton_nav(f"module:{m.id}", m.nom_court or m.nom, m.couleur)
        self._titre_nav("Suivi")
        self._bouton_nav("historique", "🕘  Historique")
        self._bouton_nav("alertes", "⚠  Alertes")
        self._bouton_nav("evolution", "📈  Évolution des indicateurs")
        self._titre_nav("Outils")
        self._bouton_nav("taches", "🗓  Tâches du Gantt")
        self._bouton_nav("parametres", "⚙  Paramètres généraux")
        self._bouton_nav("aide", "❔  Aide")

    # ------------------------------------------------------------------
    def module_par_id(self, mid):
        return next((m for m in self.modules if m.id == mid), None)

    def _creer(self, cle):
        fabriques = {"accueil": TableauDeBord, "catalogue": Catalogue, "historique": Historique,
                     "alertes": Alertes, "evolution": Evolution, "taches": TachesGantt,
                     "parametres": ParametresGeneraux, "aide": APropos}
        if cle.startswith("module:"):
            return VueModule(self.zone, self, self.module_par_id(cle.split(":", 1)[1]))
        return fabriques[cle](self.zone, self)

    def afficher(self, cle):
        if self.actif and self.actif in self.vues:
            self.vues[self.actif].pack_forget()
        if self.actif in self.boutons:
            self.boutons[self.actif].configure(bg=T.VERT, font=(T.POLICE, 10))
        if cle not in self.vues:
            try:
                self.vues[cle] = self._creer(cle)
            except Exception as e:  # une vue défaillante ne doit pas bloquer l'application
                import traceback
                messagebox.showerror("Erreur", f"Impossible d'ouvrir cet écran :\n{e}\n\n{traceback.format_exc()[-800:]}")
                if self.actif in self.vues:
                    self.vues[self.actif].pack(fill="both", expand=True)
                    if self.actif in self.boutons:
                        self.boutons[self.actif].configure(bg=T.ORANGE, font=(T.POLICE, 10, "bold"))
                return self.vues.get(self.actif)
        else:
            self.vues[cle].actualiser()
        self.vues[cle].pack(fill="both", expand=True)
        self.actif = cle
        if cle in self.boutons:
            self.boutons[cle].configure(bg=T.ORANGE, font=(T.POLICE, 10, "bold"))
        return self.vues[cle]

    def ouvrir_module(self, module):
        return self.afficher(f"module:{module.id}")

    def fermer_vues_modules(self):
        for cle in [k for k in self.vues if k.startswith("module:")]:
            vue = self.vues[cle]
            if getattr(vue, "thread", None) and vue.thread.is_alive():
                continue
            if cle == self.actif:
                continue
            vue.destroy()
            del self.vues[cle]

    def rafraichir_barre(self):
        g = self.profil.globaux
        self.badge.configure(text=f"Trimestre {g.get('trimestre', '?')}")
        n = self.stockage.nb_alertes_ouvertes_total()
        self.utilisateur.configure(text=f"👤 {g.get('utilisateur', '')}   ⚠ {n} alerte(s) ouverte(s)")
        if "alertes" in self.boutons:
            self.boutons["alertes"].configure(text=f"⚠  Alertes ({n})")

    def resultats_execution(self, execution: dict, module):
        fichiers = self.stockage.fichiers(int(execution["id"]))
        tables = {}
        for f in fichiers:
            if f.endswith(".xlsx") and Path(f).exists():
                try:
                    for nom, df in lire_excel_toutes_feuilles(f).items():
                        cle = nom if nom not in tables else f"{Path(f).stem[:15]}·{nom}"
                        tables[cle] = df
                except Exception:
                    pass
                if len(tables) > 40:
                    break
        if not tables and not fichiers:
            messagebox.showinfo("Résultats", "Aucun fichier enregistré pour cette exécution.")
            return
        FenetreResultats(self, module, tables, {}, [], fichiers)

    def quitter(self):
        en_cours = [v for v in self.vues.values() if getattr(v, "thread", None) and v.thread.is_alive()]
        if en_cours and not messagebox.askyesno("Quitter", "Un traitement est en cours. Quitter quand même ?"):
            return
        self.profil.sauver()
        self.destroy()
