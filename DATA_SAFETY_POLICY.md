# Politique de protection des données

Cette application protège par défaut les identifiants, les mots de passe, les comptes et toutes les données déjà saisies. Une modification fonctionnelle ne doit jamais réinitialiser, supprimer, remplacer ou migrer ces éléments sans demande explicite de l’utilisateur et confirmation séparée.

Tous les tests qui utilisent `db.drop_all()` ou recréent des données doivent définir `DATABASE_URL` vers une base SQLite temporaire sous `/tmp/` ou vers `:memory:`. L’exécution de `db.drop_all()` est bloquée automatiquement sur la base active. La variable `LTT_ALLOW_DESTRUCTIVE_TEST_DB=1` est réservée aux opérations administratives explicitement autorisées et ne doit jamais être ajoutée à la configuration de production.

Avant chaque checkpoint, la validation doit être réalisée localement sur une base temporaire. La base active doit uniquement être contrôlée en lecture seule : nombre de comptes, présence des tables et état du service. Aucun script de test ne doit écrire dans la base active.
