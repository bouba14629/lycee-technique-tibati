# Sauvegarde et restauration sûres

## Principe obligatoire

Les identifiants, les mots de passe, les comptes et les données déjà saisies sont considérés comme des données protégées. Une correction de code ne doit jamais exécuter de suppression globale, de réinitialisation de compte ou de migration destructive sur la base active. Toute opération administrative destructive doit faire l’objet d’une demande explicite et d’une confirmation séparée.

## Identifier la base utilisée

L’application Flask utilise la variable `DATABASE_URL` lorsqu’elle est définie. Elle accepte une URL MySQL/TiDB fournie par l’environnement WebDev, ou utilise en développement le fichier SQLite `flask_app/instance/ltt.db` lorsqu’aucune URL n’est fournie. Ne copiez jamais une URL de production dans un test local.

La base gérée par le projet doit être consultée depuis le panneau **Database → Connection Info**. Les informations de connexion et les secrets ne doivent pas être ajoutés au dépôt Git, à un fichier `.env` publié ou à un rapport de test.

## Sauvegarde manuelle

Avant toute opération importante, exportez une sauvegarde complète de la base depuis l’outil d’administration correspondant au moteur utilisé. Pour MySQL/TiDB, utilisez un dump cohérent avec transaction et SSL activé, par exemple `mysqldump --single-transaction --ssl-mode=REQUIRED`, en saisissant le mot de passe de manière interactive. Pour SQLite local, copiez le fichier `flask_app/instance/ltt.db` lorsque l’application est arrêtée, ou utilisez la commande SQLite `.backup`.

La base ne suffit pas toujours à restaurer le site : conservez aussi les fichiers téléversés et les références de stockage S3, notamment les photos élèves. Les secrets de connexion, `DATABASE_URL`, `JWT_SECRET` et les mots de passe ne doivent pas être écrits dans le dépôt ; ils doivent être conservés séparément dans le gestionnaire de secrets.

En complément, utilisez la sauvegarde de tâche Manus pour conserver le code et les artefacts du projet. Une exportation Manus est une photo à un instant donné : elle n’inclut pas les nouvelles données saisies après sa création et ne remplace pas une sauvegarde SQL régulière.

## Restauration contrôlée

Ne restaurez jamais directement en production lors du premier essai. Créez une base SQLite temporaire ou une base de préproduction distincte, importez la sauvegarde, démarrez Flask localement et comparez les compteurs d’utilisateurs, élèves, classes, matières, cours, notes et emplois du temps. Vérifiez ensuite une connexion de chaque rôle avec des comptes de test dédiés.

Après validation, créez une nouvelle sauvegarde de la base active. Effectuez la restauration dans une fenêtre contrôlée, puis vérifiez à nouveau les compteurs et les connexions. Une restauration ancienne peut supprimer les données ajoutées après la date du dump ; elle ne doit donc être exécutée qu’après confirmation de la date et du contenu de la sauvegarde.

## Prépublication locale obligatoire

Le runner `local_prepublication.py` exécute chaque test Flask depuis `flask_app/`, avec une base SQLite temporaire distincte sous `/tmp/`. Il ne transmet pas l’URL de production et supprime chaque fichier temporaire avant son test. Le script `flask_app/local_preflight.py` vérifie également que `db.drop_all()` est accepté uniquement sur une SQLite temporaire et refusé sur une URL non locale.

L’exécution recommandée avant un checkpoint est :

```bash
python3 flask_app/local_preflight.py
python3 local_prepublication.py
python3 flask_app/schedule_extra_hours_feature_test.py
pnpm test -- --run
pnpm run check
pnpm run build
```

Les tests qui utilisent `db.drop_all()` doivent définir une `DATABASE_URL` SQLite sous `/tmp/` ou `:memory:`. Le garde-fou de `flask_app/models.py` bloque les suppressions globales sur une base active. La variable `LTT_ALLOW_DESTRUCTIVE_TEST_DB=1` est réservée à une opération administrative explicitement autorisée et ne doit jamais être configurée en production.

## Contrôle avant publication

Avant de créer un checkpoint, vérifier que le préflight local est terminé avec succès, que le type-check et le build sont réussis, et que les journaux ne signalent pas d’erreur de démarrage Flask. La base active ne doit être contrôlée qu’en lecture seule, sans `drop_all()`, `create_all()`, suppression, mise à jour de mot de passe ou réinitialisation de compte. Le contrôle automatisé prévu est : `LTT_READONLY_ACTIVE_DB=1 python3 flask_app/readonly_database_check.py`. Cette commande exige l’URL de base déjà fournie par l’environnement, n’exécute que `SELECT` et affiche uniquement des métadonnées et compteurs. La publication d’un changement de code ne doit pas modifier les données persistées.

## Références Manus

Pour les sauvegardes de tâches et la restauration d’un projet WebDev, consulter [How to Back Up Your Data](https://help.manus.im/en/articles/16147892-service-change-overview-how-to-back-up-your-data) et [How to Restore Your Data](https://help.manus.im/en/articles/16147895-service-change-overview-how-to-restore-your-data). Les exports Manus sont des instantanés fixes et la restauration doit être engagée uniquement après vérification des paquets et de leur date.
