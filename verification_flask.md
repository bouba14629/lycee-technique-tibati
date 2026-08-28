# Vérification Flask

La passerelle Node démarre Gunicorn sur le port interne configuré et le serveur principal écoute sur `process.env.PORT`. La route `/health` répond avec un statut `200` lorsque `LTT_INITIAL_ADMIN_PASSWORD` est configuré avec au moins 12 caractères.

La page `/login` a été vérifiée visuellement sur un viewport desktop de 1280 × 720. Le rendu final présente le logo du Lycée Technique de Tibati, le panneau de connexion, la palette bleu marine et or, ainsi que les photographies des ateliers. Les ressources sont servies depuis les chemins `/manus-storage/` persistants du projet.

Une première prévisualisation non corrigée affichait du HTML sans style parce que les anciens identifiants d’assets n’existaient pas dans le nouveau stockage. Les URLs ont été remappées après téléversement des 15 ressources et une nouvelle capture desktop confirme le rendu restauré.

La vérification mobile et les tests de routes protégées restent à effectuer avant le checkpoint final.

La page `/login` a aussi été vérifiée sur un viewport mobile de 375 × 812. Le formulaire reste lisible, les boutons sont accessibles, le panneau s’adapte à la largeur et les éléments techniques restent visibles sans débordement horizontal.

Les routes `/`, `/login`, `/health` et `/manifest.webmanifest` répondent correctement via le serveur Node/Flask. Les ressources CSS et SVG du stockage renvoient une redirection de stockage valide. Un smoke test isolé sur SQLite temporaire confirme la création du fondateur, la connexion, l’accès à `/dashboard` et la déconnexion sans modifier la base de production.
