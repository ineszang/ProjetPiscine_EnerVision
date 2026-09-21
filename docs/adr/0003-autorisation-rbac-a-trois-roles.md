# 0003 - Autorisation RBAC à trois rôles, avec relecture du compte à chaque requête

- Statut : accepté
- Date : 2026-09-15

## Contexte

Le dossier EC01 annonce un RBAC à trois rôles, `admin`, `opérateur` et `lecteur`, et des comptes
machine à machine distincts pour l'ETL et le travail d'apprentissage. Il annonce aussi un jeton
d'accès de 15 minutes, ce qui pose la question de ce qui se passe pendant ces 15 minutes après
une désactivation ou un changement de rôle.

## Décision

**Trois rôles totalement ordonnés** : `lecteur < operateur < admin`. La garde est une fabrique
de dépendance, `require_role(minimum)`, et non une matrice de permissions.

Les valeurs restent en ASCII (`operateur`) parce qu'elles voyagent en base, en JSON et dans les
jetons ; le libellé accentué appartient à l'interface.

**Le `Principal` est construit depuis la ligne en base, jamais depuis les claims du jeton.**
`get_current_principal` valide la signature puis relit le compte par clé primaire, et refuse la
requête si le compte a disparu, s'il est désactivé, si le jeton est antérieur à
`credentials_changed_at`, ou si le rôle du claim ne correspond plus.

**Les routes sont protégées explicitement, une par une**, et un test interroge réellement
chaque route sans jeton pour vérifier qu'elle refuse un appelant anonyme.

**Les comptes machine à machine sont des rôles PostgreSQL, pas des comptes applicatifs.** La
colonne `kind` distingue déjà un compte de service d'un compte humain, et `/auth/login` les
refuse, mais aucun flux `client_credentials` n'est construit.

## Pourquoi relire la base plutôt que rester sans état

La propriété « sans état » achète la montée en charge horizontale entre des services qui ne
partagent pas de base. Il y a un service et une base : le bénéfice est nul.

Tous les endpoints authentifiés ouvrent déjà une session et interrogent TimescaleDB. Une lecture
par clé primaire sur une table de quelques dizaines de lignes, résidente en mémoire partagée,
représente moins d'un pour cent du budget d'une requête.

Ce qu'on achète en échange est la **révocation immédiate**. « Un opérateur licencié à 10h00
garde-t-il ses droits jusqu'à 10h15 ? » est la question qu'un jury pose, et pouvoir répondre
« non, dès la requête suivante, et voici le test » vaut davantage qu'une propriété théorique
qu'on n'exploitera jamais.

Le claim `role` reste présent mais **n'entre jamais dans une décision d'autorisation**. Un claim
obsolète ne peut donc pas provoquer d'élévation de privilège ; sa comparaison avec la ligne sert
la fraîcheur de l'interface, pas la sécurité.

Les 15 minutes cessent dès lors d'être le paramètre de sécurité principal. Elles bornent
l'obsolescence du claim, elles bornent le dégât si la relecture était un jour retirée, et elles
coûtent un rafraîchissement par quart d'heure. C'est une marge, pas une garantie.

## Pourquoi les comptes machine à machine sont des rôles PostgreSQL

Un travail d'ingestion de séries temporelles insère en masse, par `COPY` ou par insertions
groupées sur une connexion PostgreSQL, pas par des allers-retours REST : c'est deux ordres de
grandeur d'écart, et TimescaleDB a précisément été choisi pour cette charge.

Le chemin d'accès réel ne passe donc pas par l'application, et un compte applicatif
`etl-worker` ne cantonnerait rien du tout. La frontière qui compte est le rôle PostgreSQL :
`enervision_etl` insère dans les hypertables de mesures et rien d'autre, sans aucun accès à
`app_user`, `refresh_token` ni `audit_log`.

Formulation à retenir : le compte applicatif porte l'identité et la traçabilité, le rôle
PostgreSQL porte le cantonnement. Le premier sans le second serait du théâtre.

**Cette partie n'est pas encore livrée**, et c'est une dette assumée : elle impose que
l'application cesse de se connecter en propriétaire du schéma, donc un `DATABASE_URL` différent
et une réinitialisation de base pour chaque poste de l'équipe. À ouvrir en ticket avec l'équipe
chargée de l'ETL.

## Conséquences

- Un changement de rôle ou une désactivation révoque aussi les familles de jetons de la cible,
  sans quoi la révocation ne serait immédiate que sur le jeton d'accès.
- `credentials_changed_at` est comparé à la seconde entière, parce que `iat` est une date JWT et
  n'a pas de précision inférieure. Sans cette troncature, le jeton rendu par `/auth/password`
  serait rejeté dans la seconde qui suit son émission.
- Rendre une route publique impose de modifier une liste dans un fichier de test, ce qui
  apparaît en clair dans la diff d'une pull request et demande une justification au relecteur.
  Le garde-fou est social autant que technique.
- Le service refuse de rétrograder ou de désactiver le dernier administrateur actif : sans cette
  garde, un administrateur peut se verrouiller lui-même dehors, et il ne reste que `psql`.

## Alternatives écartées

- **Matrice de permissions explicites** (`measure.read`, `user.create`…) : c'est la bonne réponse
  à partir d'une dizaine de rôles. Ici, trois rôles totalement ordonnés se lisent en une ligne.
  **Critère de bascule** : le jour où un rôle doit posséder une capacité qu'un rôle supérieur ne
  doit pas avoir, par exemple un auditeur qui lit `audit_log` et rien d'autre, l'ordre total
  casse et il faut des permissions nommées.
- **Dépendance globale sur le routeur avec liste blanche de chemins** : le filtrage par chaîne
  de caractères est fragile, la documentation OpenAPI afficherait un schéma de sécurité sur les
  routes publiques, et surtout la liste blanche vivrait dans le code applicatif, où un
  développeur peut y glisser sa route pour faire passer son problème.
- **Portée par site** : c'est la limite connue de cette conception. Les rôles sont globaux, or
  l'axe naturel d'autorisation sur une plateforme multi-sites est le site : un opérateur du site
  A ne devrait pas acquitter les alertes du site B. En l'état, le risque BOLA reste ouvert. Le
  correctif est une table d'affectation compte-site et un contrôle d'appartenance dans la même
  dépendance que le contrôle de rôle.
- **Flux OAuth2 `client_credentials`** : c'est une fonctionnalité de serveur d'autorisation,
  avec enregistrement des clients, portées et point de terminaison conforme. Des jours de
  travail pour zéro consommateur HTTP actuel. Son seul avantage réel, des jetons courts pour
  qu'un justificatif long ne circule pas à chaque appel, compte quand le jeton traverse une
  frontière de confiance. Ici il n'en traverse aucune.
