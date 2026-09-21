# Plan d'evolution de l'application ENEM Suivi

## Decision

L'application Tkinter reste l'interface officielle pour les prochaines versions. Les evolutions doivent
toutefois preparer une future interface web sans dupliquer ni reecrire les regles metier.

La cible envisagee est une application web interne avec :

- une API Python FastAPI ;
- PostgreSQL sur l'infrastructure interne pour les metadonnees applicatives ;
- MinIO pour les bases, fichiers de reference et resultats ;
- un ou plusieurs workers pour les traitements longs ;
- une interface web accessible depuis les postes autorises.

Ce plan ne constitue pas une decision de mise en production sur le serveur. Les adresses, comptes,
secrets et regles de securite devront etre valides avec l'equipe d'infrastructure.

## Principes directeurs

1. Conserver `enem_core` et `modules` independants de Tkinter et du futur framework web.
2. Maintenir une seule implementation des calculs metier.
3. Ne jamais enregistrer de secret ou de donnee d'enquete dans le depot Git.
4. Assurer la tracabilite de chaque fichier et de chaque execution.
5. Faire evoluer l'application par etapes reversibles.
6. Garder Tkinter utilisable tant que la solution web n'a pas ete recettee.

## Phase 0 - Stabilisation de la version Tkinter

Objectif : disposer d'une version de reference fiable avant toute migration.

- corriger les erreurs de chargement et les anomalies connues ;
- ajouter un fichier `.gitignore` couvrant profils, bases, resultats, journaux et secrets ;
- publier le code dans un depot dedie et versionne ;
- ajouter des tests unitaires pour les calculs critiques ;
- ajouter des tests de non-regression avec des donnees entierement fictives ;
- documenter l'installation, la configuration et la procedure de recette ;
- produire des versions identifiees (`v1.x`) et un journal des changements ;
- separer progressivement les grandes vues Tkinter en composants plus petits.

Critere de sortie : tous les modules se chargent, les tests de reference reussissent et une version
Tkinter reproductible peut etre installee sur un nouveau poste.

## Phase 1 - Decouplage technique

Objectif : rendre le moteur utilisable par Tkinter, une API ou une commande sans modifier les calculs.

- interdire les imports de `tkinter` dans `enem_core` et `modules` ;
- definir une couche de services pour lancer un module et suivre sa progression ;
- introduire une abstraction de stockage des fichiers ;
- introduire une abstraction de stockage de l'historique ;
- remplacer les chemins disperses par des identifiants et objets de configuration ;
- normaliser les resultats, erreurs, alertes et evenements de progression ;
- conserver des implementations locales compatibles avec Tkinter et SQLite.

Critere de sortie : le meme module peut etre execute depuis Tkinter et depuis un test ou une commande,
avec des resultats identiques.

## Phase 2 - Integration MinIO

Objectif : centraliser les fichiers sans changer encore l'interface utilisateur principale.

- definir les buckets et conventions de nommage ;
- stocker les entrees, references et resultats dans des espaces distincts ;
- enregistrer pour chaque objet son empreinte SHA-256, sa taille, son type et son auteur ;
- telecharger les entrees dans un repertoire temporaire propre a l'execution ;
- televerser les resultats uniquement apres une execution reussie ;
- utiliser des liens temporaires pour les telechargements ;
- definir les politiques de versionnement, retention et sauvegarde ;
- tester les reprises apres interruption ou indisponibilite du stockage.

Organisation indicative :

```text
enem-entrees/<trimestre>/<type>/<version>/...
enem-references/<categorie>/<version>/...
enem-resultats/<trimestre>/<module>/<execution-id>/...
```

Critere de sortie : une execution de test lit ses entrees depuis MinIO et y depose ses resultats avec
une tracabilite complete.

## Phase 3 - Migration vers PostgreSQL

Objectif : centraliser l'etat applicatif et permettre le travail multi-utilisateur.

PostgreSQL contiendra notamment :

- utilisateurs, roles et autorisations ;
- fichiers et versions disponibles dans MinIO ;
- parametres globaux et parametres des modules ;
- executions, progression, erreurs et journaux ;
- indicateurs et alertes ;
- traces d'audit.

Les grosses bases d'enquete resteront dans MinIO. PostgreSQL n'en conservera que les metadonnees et
les cles d'objets.

Travaux prevus :

- concevoir et faire valider le schema ;
- ajouter les migrations de base de donnees ;
- migrer les donnees utiles de SQLite ;
- definir les sauvegardes et la restauration ;
- tester les acces concurrents et les transactions ;
- etablir une politique de conservation des journaux et alertes.

Critere de sortie : l'historique et les indicateurs sont partages entre plusieurs utilisateurs sans
perte de donnees ni doublon d'execution.

## Phase 4 - API et traitements asynchrones

Objectif : exposer les fonctions necessaires a une interface web sans executer les traitements lourds
dans le processus HTTP.

- creer l'API FastAPI ;
- ajouter l'authentification et le controle des roles ;
- exposer le catalogue des modules et leurs parametres ;
- permettre le depot et la selection des fichiers ;
- soumettre les traitements a une file de taches ;
- executer les modules dans des workers isoles ;
- exposer la progression, l'arret et les resultats ;
- ajouter des limites de taille, delais, quotas et controles de format ;
- journaliser les operations sensibles.

Critere de sortie : un client sans Tkinter peut lancer un module, suivre son execution et recuperer ses
resultats via l'API.

## Phase 5 - Prototype de l'interface web

Objectif : valider l'ergonomie et l'infrastructure sur un perimetre limite.

Le prototype couvrira de preference :

1. le tableau de bord ;
2. le catalogue des modules ;
3. un module simple ;
4. un module long avec progression et arret ;
5. l'historique et le telechargement des resultats.

Le prototype sera compare a Tkinter sur les points suivants : temps de traitement, facilite d'usage,
gestion des gros fichiers, securite, auditabilite et charge de maintenance.

Critere de sortie : recette fonctionnelle par un petit groupe d'utilisateurs et decision formelle sur
la generalisation.

## Phase 6 - Migration progressive des ecrans

Objectif : remplacer Tkinter module par module sans interrompre le service.

- migrer d'abord les ecrans transversaux ;
- migrer ensuite les modules par familles ;
- comparer les sorties Tkinter et web sur les memes jeux de test ;
- documenter les ecarts acceptes ;
- conserver Tkinter pendant une periode de coexistence ;
- geler l'ajout de nouvelles fonctions dans Tkinter lorsque leur equivalent web est valide.

Critere de sortie : tous les parcours necessaires sont disponibles et recetes dans l'interface web.

## Phase 7 - Bascule et retrait de Tkinter

Objectif : faire de l'interface web la version officielle.

- former les utilisateurs ;
- publier les procedures d'exploitation et d'assistance ;
- definir la supervision et les alertes techniques ;
- tester la restauration apres incident ;
- archiver une derniere version autonome de Tkinter ;
- retirer Tkinter uniquement apres validation metier et technique.

## Securite et depot public

Le depot public ne doit jamais contenir :

- adresse interne du serveur ou details de reseau ;
- identifiants PostgreSQL ou MinIO ;
- cles d'acces, jetons ou mots de passe ;
- profil utilisateur reel ;
- noms ou informations sur les agents ;
- bases d'enquete, resultats operationnels ou journaux reels.

La configuration de deploiement utilisera des variables d'environnement ou un gestionnaire de secrets.
Des fichiers d'exemple sans valeur reelle pourront etre conserves dans le depot.

## Priorites immediates

Pendant le maintien de Tkinter, l'ordre recommande est :

1. fiabiliser les calculs et les tests de non-regression ;
2. finaliser le depot et la procedure de publication ;
3. renforcer la separation entre interface et moteur ;
4. documenter les fichiers d'entree et de sortie de chaque module ;
5. concevoir les interfaces de stockage local/MinIO et SQLite/PostgreSQL ;
6. realiser ensuite un prototype technique limite, sans perturber la version Tkinter.
