# Project TODO

- [x] Intégrer l’application Flask scolaire et ses dépendances Python dans le projet.
- [x] Servir la page de connexion Flask comme point d’entrée par défaut à la racine.
- [x] Conserver les routes applicatives Flask et leurs ressources statiques.
- [x] Préserver l’authentification et les sessions Flask existantes.
- [x] Configurer le proxy Node vers Flask avec `LTT_FLASK_ENABLED` activé par défaut.
- [x] Permettre l’affichage explicite de l’interface React uniquement avec `LTT_FLASK_ENABLED=0`.
- [x] Ajouter un Dockerfile reproductible avec Node, Python, gunicorn et les dépendances Flask.
- [x] Rendre la compilation propre avec suppression préalable de `dist`.
- [x] Utiliser `pnpm-lock.yaml` pour une installation déterministe.
- [x] Exclure les dépendances, artefacts locaux et anciens bundles de la construction Docker.
- [x] Ajouter ou mettre à jour les tests Vitest du routage Flask et du mode React de secours.
- [x] Compiler le client et le serveur avec succès.
- [x] Vérifier visuellement la page de connexion et les états responsive desktop/mobile.
- [x] Sauvegarder un checkpoint final avant livraison.

- [x] Réinitialiser uniquement le mot de passe du compte Flask `proviseur` sans supprimer ni modifier les autres données.

- [x] Vérifier la portée exacte de la réinitialisation complète confirmée.
- [x] Supprimer toutes les données scolaires et tous les comptes applicatifs de la base Flask active.
- [x] Recréer uniquement le compte fondateur `proviseur` pour la nouvelle configuration.
- [x] Vérifier que l’instance redémarre vide et que la connexion du fondateur fonctionne.
- [x] Sauvegarder un checkpoint après la réinitialisation complète.

- [x] Localiser toutes les occurrences de « Made with Manus » dans les modèles, styles et scripts d’impression.
- [x] Supprimer cette mention des documents imprimés et des exports PDF sans altérer leur contenu.
- [x] Vérifier les tests, la compilation et le rendu d’impression après correction.
- [x] Sauvegarder un checkpoint et publier la correction.

- [x] Localiser toutes les occurrences de « Made with Manus » dans les modèles, styles et scripts d’impression.
- [x] Supprimer cette mention des documents imprimés et des exports PDF sans altérer leur contenu.
- [x] Vérifier les tests, la compilation et le rendu d’impression après correction.
- [x] Sauvegarder un checkpoint et publier la correction.

- [x] Analyser les filtres actuels du module Bulletins et leur portée par rôle.
- [x] Ajouter un menu déroulant Filière dans le module Bulletins.
- [x] Filtrer côté serveur les classes selon la filière sélectionnée.
- [x] Mettre à jour dynamiquement la liste des classes lors du changement de filière.
- [x] Conserver la filière et la classe sélectionnées dans l’URL et les actions liées aux bulletins.
- [x] Ajouter des tests du filtrage Filière → Classes.
- [x] Vérifier le rendu desktop et mobile du nouveau filtre.
- [x] Sauvegarder un checkpoint et publier la fonctionnalité.

- [x] Diagnostiquer le flux d’importation CSV/XLSX des élèves.
- [x] Corriger la détection des colonnes, encodages et séparateurs.
- [x] Corriger l’association des élèves aux classes et la validation des références.
- [x] Gérer les doublons et les lignes invalides sans interrompre inutilement tout l’import.
- [x] Améliorer le rapport d’erreurs et le retour utilisateur après importation.
- [x] Mettre à jour le modèle d’importation des élèves.
- [x] Ajouter des tests CSV/XLSX, cas limites et non-régression.
- [x] Compiler, vérifier et publier la correction de l’importation.

- [x] Ajouter la date de naissance au formulaire de modification des élèves.
- [x] Enregistrer et valider la date de naissance modifiée.
- [x] Réafficher la date enregistrée dans le formulaire et ajouter un test de non-régression.
- [x] Compiler, vérifier et publier la correction.

- [x] Sauvegarder un checkpoint après l’ajout du champ « Date de naissance » dans la modification des élèves.
- [x] Publier ou livrer explicitement la correction de la date de naissance après validation finale.

- [x] Ajouter la date de naissance dans la prévisualisation de l’import élèves.
- [x] Aligner l’affichage de la date avec la validation et l’enregistrement réels.
- [x] Tester les dates CSV/XLSX, les dates vides et les dates invalides dans l’aperçu.
- [x] Compiler et publier la correction de la prévisualisation d’import.

- [x] Ajouter un test de prévisualisation couvrant CSV date vide, CSV date invalide et XLSX avec date affichée.
- [x] Sauvegarder un checkpoint spécifique après la correction de la prévisualisation et livrer cette version.

- [x] Sauvegarder un nouveau checkpoint après la correction de la prévisualisation d’import des élèves.
- [x] Livrer explicitement la version contenant la date de naissance dans la prévisualisation d’import.

- [x] Localiser les blocs « Total des points » et « Moyenne classe » dans les bulletins.
- [x] Afficher « Total des points » avant « Moyenne classe » à l’écran.
- [x] Appliquer le même ordre aux impressions et exports PDF.
- [x] Ajouter les tests de non-régression, compiler et publier la correction.

- [x] Sauvegarder un nouveau checkpoint après la permutation « Total des points » / « Moyenne classe ».
- [x] Livrer explicitement la version publiée contenant cette permutation.

- [x] Permuter Moyenne du dernier avec Moyenne trimestrielle dans la synthèse des bulletins.
- [x] Permuter Moyennes ≥ 10 avec Rang dans la synthèse des bulletins.
- [x] Permuter Taux réussite avec Éval.1 dans la synthèse des bulletins.
- [x] Afficher Éval.2 sous Éval.1 dans la synthèse des bulletins.
- [x] Remplacer « PROFIL DE LA CLASSE » par « TRAVAIL DE L’ÉLÈVE ».
- [x] Permettre à tous les rôles de modifier leur propre mot de passe avec validation de l’ancien mot de passe.
- [x] Ajouter les tests de permutations et de changement de mot de passe multi-rôles.
- [x] Compiler, sauvegarder et publier les corrections.

- [x] Sauvegarder un nouveau checkpoint après les permutations de synthèse et l’ouverture du changement de mot de passe à tous les rôles.
- [x] Livrer explicitement la version publiée contenant ces corrections.

- [x] Remplacer « Moyenne classe » par « Moyenne Générale de la classe » dans les bulletins.
- [x] Ajouter « PROFIL DE LA CLASSE » au-dessus de cet indicateur sur la même ligne que « TRAVAIL DE L’ÉLÈVE ».
- [x] Permettre au conseiller d’orientation de consulter les emplois du temps par classe.
- [x] Garantir que le conseiller reste en lecture seule pour les emplois du temps.
- [x] Ajouter les tests de libellé, mise en page et permission de consultation.
- [x] Compiler, sauvegarder et publier les corrections.

- [x] Mettre à jour les deux modèles PDF annuels avec « Moyenne Générale de la classe » et les titres de synthèse demandés.
- [x] Étendre les tests aux modèles annuels sur le libellé et la structure des titres.
- [x] Sauvegarder un nouveau checkpoint après ces corrections et livrer la version publiée correspondante.

- [x] Sauvegarder un nouveau checkpoint après la mise à jour des modèles PDF annuels et l’extension des tests.
- [x] Livrer explicitement la version publiée correspondante avec le nouveau checkpoint.

- [x] Diagnostiquer pourquoi la photo de l’élève ne se charge pas dans Modifier.
- [x] Corriger le chemin ou l’URL de stockage de la photo élève.
- [x] Préremplir et afficher correctement la photo existante dans le formulaire Modifier.
- [x] Vérifier le remplacement, l’absence de photo et les formats acceptés.
- [x] Ajouter les tests photo, compiler, sauvegarder et publier la correction.

- [x] Diagnostiquer les formats de photo et les chemins réellement stockés pour un élève.
- [x] Corriger la résolution des URL locales et `/manus-storage/` dans Modifier.
- [x] Ajouter un aperçu fiable, un remplacement de photo et un repli vers l’image par défaut.
- [x] Tester les formats JPG, JPEG, PNG et WEBP ainsi que l’absence de photo.
- [x] Compiler, sauvegarder et publier la correction du chargement photo.
- [x] Implémenter un endpoint Node persistant pour téléverser les photos élèves vers le stockage S3.
- [x] Normaliser les URL photo Flask et ajouter un aperçu avec repli dans le formulaire Modifier.
- [x] Ajouter un test ciblé de l’upload et de la résolution des photos élèves.
- [x] Vérifier les tests de régression, le type-check et le build après la correction.
- [x] Enregistrer et publier la correction photo vérifiée.
- [x] Ajouter des tests explicites pour JPEG, PNG et WEBP, en plus du cas JPG et du cas sans photo.
- [x] Ajouter un test d’intégration de l’endpoint Node `/api/ltt/media` avec authentification, type et réponse contrôlés.
- [x] Ajouter des tests de résolution pour les chemins legacy, statiques et `/manus-storage/`.

- [x] Réinitialiser uniquement le mot de passe du compte proviseur avec la valeur fournie, sans modifier les données ni les autres comptes.
- [x] Vérifier la connexion du proviseur et publier la mise à jour ciblée.

- [x] Conserver le nouveau compte proviseur confirmé par l’utilisateur sans supprimer les données scolaires.
- [x] Vérifier la connexion du compte proviseur et enregistrer la mise à jour ciblée.
- [x] Sauvegarder un checkpoint et publier la conservation du nouveau compte proviseur.

- [x] Réinitialiser complètement les données et comptes de l’instance.
- [x] Recréer uniquement le compte proviseur avec son mot de passe actuel.
- [x] Vérifier que la base est vide hors compte proviseur et publier la version réinitialisée.

- [x] Analyser le flux d’importation des enseignants et le rapport actuel des erreurs.
- [x] Afficher les problèmes d’importation par ligne, champ, cause et correction recommandée.
- [x] Gérer clairement doublons, classes/filières introuvables, champs obligatoires et formats invalides.
- [x] Ajouter les tests du rapport d’importation des enseignants et vérifier l’interface.
- [x] Compiler, sauvegarder et publier la correction du rapport d’importation.
- [x] Ajouter les erreurs de fichier CSV/XLSX invalide ou non pris en charge au rapport des enseignants.
- [x] Tester les doublons enseignants par email et par identifiant généré.
- [x] Ajouter un test Flask de doublon d’email avec rapport détaillé ligne/champ/cause/correction.
- [x] Tester la collision de nom et la génération d’un identifiant enseignant suffixé.
- [x] Enregistrer le checkpoint après validation réelle des doublons enseignants.
- [x] Enregistrer un checkpoint après la correction complète du rapport enseignants.

- [x] Analyser la construction actuelle des emplois du temps et les classes STT par niveau.
- [x] Ajouter les troncs communs aux classes STT de même niveau.
- [x] Valider les conflits de salle, enseignant et créneau pour les troncs communs.
- [x] Afficher clairement les troncs communs dans les emplois du temps concernés.
- [x] Ajouter les tests STT, compiler, sauvegarder et publier la correction.
- [x] Corriger la fixture du test de regroupement d’emploi du temps pour fournir le code attendu des classes.
- [x] Ajouter un test Flask intégré d’un POST de tronc commun STT valide entre deux classes du même niveau.
- [x] Refuser les matières rattachées à une seule classe dans un tronc commun multi-classes, ou résoudre une matière compatible par classe cible.
- [x] Tester le refus des groupes hors STT, hors niveau et les conflits enseignant/salle/créneau.
- [x] Sauvegarder et publier un checkpoint après validation intégrée complète.

- [x] Vérifier l’interface censeur d’élaboration des emplois du temps et le bloc des troncs communs.
- [x] Permettre aux censeurs de sélectionner et créer un tronc commun entre classes compatibles.
- [x] Contrôler les sections, niveaux, matières, salles, enseignants et créneaux pour les censeurs.
- [x] Ajouter un test Flask d’intégration de création de tronc commun côté censeur.
- [x] Compiler, sauvegarder et publier la correction pour les censeurs.
- [x] Sauvegarder et publier explicitement la correction des troncs communs côté censeur.

- [x] Analyser la règle actuelle des troncs communs et les contraintes de niveau et de section.
- [x] Permettre la création de troncs communs entre classes compatibles de même niveau.
- [x] Valider la compatibilité de la matière avec chaque classe cible d’un tronc commun inter-sections.
- [x] Ajouter un test intégré de matière incompatible et de matière partagée compatible entre classes cibles.
- [x] Sauvegarder et publier la généralisation après validation finale.
- [x] Adapter l’interface de sélection et les messages de validation.
- [x] Tester les classes de même section et de sections différentes, ainsi que les conflits.
- [x] Compiler, sauvegarder et publier la généralisation des troncs communs.
- [x] Mettre à jour le test statique des troncs communs pour refléter la règle générale du même niveau.

- [x] Vérifier le mode Autoscale et les conditions du déploiement permanent.
- [x] Ajouter dans Matières et filières côté censeur l’option Tronc commun.
- [x] Afficher une liste multi-sélectionnée des classes de même niveau.
- [x] Autoriser une matière de tronc commun à être programmée simultanément dans les classes choisies sans conflit.
- [x] Tester les matières partagées, les classes de niveaux différents et les conflits de créneau, salle et enseignant.
- [x] Compiler, sauvegarder et publier la correction.
- [x] Enregistrer et publier explicitement la correction Tronc commun de Matières et filières.

- [x] Diagnostiquer l’échec de connexion des identifiants existants après le dernier déploiement.
- [x] Vérifier l’instance de base et les comptes sans modifier les données ni les mots de passe.
- [x] Corriger uniquement la cause technique confirmée et tester les connexions.
- [x] Publier la correction d’accès après validation.
- [x] Isoler schedule_conflict_feature_test.py sur une base SQLite temporaire pour empêcher toute suppression de la base de production.
- [x] Rétablir l’accès au compte administrateur après confirmation de l’origine de l’échec, sans prétendre récupérer les comptes déjà supprimés.
- [x] Rétablir uniquement le compte proviseur avec le mot de passe confirmé.
- [x] Vérifier sa connexion et conserver les autres lignes existantes sans nouvelle suppression.
- [x] Publier la correction qui isole les tests de la base de production.

- [x] Auditer les scripts et tests capables de modifier ou supprimer la base active.
- [x] Interdire l’exécution des tests destructifs sur une base non locale ou non temporaire.
- [x] Ajouter une politique de projet protégeant identifiants, mots de passe et données déjà saisies.
- [x] Ajouter une validation locale avant publication avec contrôle de base en lecture seule.
- [x] Tester les garde-fous et publier la protection sans modifier les données existantes.
- [x] Corriger le runner de prépublication pour exécuter les tests Flask depuis leur répertoire attendu et éviter les faux échecs de chemin relatif.
- [x] Corriger la fixture du test export_smoke_test.py afin de créer l’élève requis dans sa base locale temporaire.
- [x] Corriger l’assertion obsolète du test founder_setup_flow_test.py pour le libellé actuel du tableau de bord.
- [x] Corriger la fixture du test life_school_feature_test.py afin de créer la correspondance attendue dans sa base temporaire.
- [x] Corriger la fixture du test module_smoke_test.py afin de créer le profil enseignant requis dans sa base temporaire.
- [x] Adapter production_smoke_test.py au mode local isolé et ne plus dépendre des identifiants de démonstration de production.
- [x] Mettre à jour l’attente de version du test pwa_feature_test.py pour le shell PWA actuel.

- [x] Identifier la base active et la méthode d’export sans modifier les données.
- [x] Documenter une sauvegarde complète incluant base, identifiants et fichiers stockés.
- [x] Documenter une restauration locale vérifiée avant toute remise en production.
- [x] Documenter les contrôles de conservation des comptes, mots de passe et données saisies.

- [x] Localiser tous les calculs et affichages des heures dues, faites et supplémentaires.
- [x] Appliquer max(0, heures faites - heures dues) dans les emplois du temps et exports concernés.
- [x] Tester les cas heures faites inférieures, égales et supérieures aux heures dues.
- [x] Vérifier en local puis publier la correction sans modifier les données existantes.
- [x] Corriger role_smoke_test.py pour utiliser des comptes et mots de passe temporaires compatibles avec la politique actuelle.
- [x] Corriger smoke_test.py pour initialiser son compte de test dans une SQLite temporaire et respecter l’authentification actuelle.
- [x] Ajouter un contrôle automatisé strictement en lecture seule de la base active avant publication et son test non destructif.
- [x] Enregistrer un checkpoint après les garde-fous, le runner local et la documentation de sauvegarde/restauration.

- [x] Analyser les permissions censeur pour l’insertion des matières de tronc commun dans les créneaux.
- [x] Autoriser l’insertion et la programmation simultanée des matières de tronc commun par les censeurs.
- [x] Contrôler les classes cibles, les créneaux, les salles et les conflits d’enseignants.
- [x] Ajouter un test local censeur sur l’insertion d’un tronc commun dans un créneau.
- [x] Exécuter le préflight local, puis enregistrer et publier la correction sans modifier les données existantes.
- [x] Mettre à jour l’assertion statique du test des troncs communs après le changement de libellé de l’interface.
- [x] Mettre à jour le test Vitest counselorScheduleAccess pour refléter l’autorisation des censeurs d’insérer les troncs communs.

- [x] Analyser les routes et interfaces de modification des créneaux d’emploi du temps.
- [x] Ajouter l’option Modifier pour les créneaux individuels et les troncs communs.
- [x] Préserver les permissions censeur et les contrôles de conflits lors de la modification.
- [x] Ajouter les tests locaux de modification de créneau et vérifier les régressions.
- [x] Enregistrer et publier la correction Modifier des emplois du temps.
