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
