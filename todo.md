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
