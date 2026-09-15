# 0004 - Journal d'audit en ajout seul, garanti par PostgreSQL

- Statut : accepté
- Date : 2026-09-15

## Contexte

Le dossier EC01 annonce une table `audit_log` « en ajout seul pour toute action
d'administration ». Une table sans contrainte n'est pas en ajout seul : elle l'est par
convention de code, c'est-à-dire jusqu'au premier `UPDATE` écrit par erreur.

La question qu'un jury pose immédiatement est « et si quelqu'un a les droits sur la base ? ».
Elle mérite une réponse honnête plutôt qu'une parade.

## Décision

Deux déclencheurs PL/pgSQL sur `audit_log`, posés par la révision Alembic qui crée la table :

- `BEFORE UPDATE OR DELETE ... FOR EACH ROW`
- `BEFORE TRUNCATE ... FOR EACH STATEMENT`

Le second n'est pas redondant : `TRUNCATE` ne passe pas par les déclencheurs de ligne. Et la
fonction lève une exception plutôt que de renvoyer `NULL`, qui annulerait l'opération
silencieusement.

`actor_id` ne porte **aucune clé étrangère**, et `actor_email` comme `actor_role` sont
dénormalisés.

Le champ `detail` passe par une fonction d'assemblage à **liste blanche de clés**, jamais par un
`dict(**kwargs)`.

## Pourquoi pas de clé étrangère sur l'acteur

Une contrainte `ON DELETE SET NULL` déclencherait un `UPDATE` que le déclencheur d'ajout seul
refuserait : la suppression d'un compte échouerait. Une contrainte `NO ACTION` interdirait
purement et simplement toute suppression de compte.

Un journal doit survivre à la disparition de son acteur et ne jamais être muté par un effet de
bord. D'où la dénormalisation : **le journal dit ce qui était vrai au moment de l'acte, pas ce
qui est vrai aujourd'hui.**

## Ce qui entre, et ce qui n'entre pas

| | `audit_log` | `login_attempt` et journaux applicatifs |
|---|---|---|
| Question | qui a fait quoi, à qui, quand | que se passe-t-il en ce moment |
| Volume | faible | élevé |
| Rétention | longue, non purgeable par ligne | courte, purgeable |
| Piloté par l'attaquant | **jamais** | possiblement |

Conséquence non négociable, et c'est le point où une contrainte technique dicte une décision de
conception : **on n'écrit jamais dans `audit_log` un volume que l'attaquant contrôle.** Une
force brute y inscrirait des millions de lignes indestructibles. Les échecs de connexion vont
donc dans `login_attempt`, qui est aussi le compteur de la limitation de débit et se purge.

La seule exception est `auth.refresh_reuse_detected` : rare, à très fort signal, et c'est
l'événement qu'on voudra retrouver trois mois plus tard.

Corollaire : `audit_log` n'est **pas** une hypertable. Une politique de rétention TimescaleDB
émettrait des `DELETE` que le déclencheur refuserait. Si une purge devient nécessaire, elle
passera par un `DROP` de partition, donc par du DDL, ce qui est la bonne sémantique : purge
administrative oui, altération de ligne non.

## Ce que cette garantie couvre, et ce qu'elle ne couvre pas

Le déclencheur défend contre le code de l'équipe et contre l'accident. Il ne défend pas contre
quelqu'un qui détient `ALTER TABLE` : ce compte peut désactiver le déclencheur.

La réponse honnête à « et si quelqu'un a les droits sur la base ? » est donc : alors l'audit
local ne vaut plus rien, et c'est vrai de tout journal co-localisé avec ce qu'il journalise. Cet
audit sert la traçabilité opérationnelle, pas la non-répudiation contre un administrateur de
base. Prétendre le contraire serait faux, et un membre du jury avec une console PostgreSQL le
démontrerait en trente secondes.

Le palier suivant est double, et il est assumé comme dette :

1. **Séparation de privilèges** : `REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM
   enervision_app`. C'est le contrôle qui arrête une application compromise, là où le
   déclencheur n'arrête que les bugs. Il exige que l'application cesse de se connecter en
   propriétaire de la table, donc un rôle supplémentaire, un `DATABASE_URL` différent et une
   réinitialisation de base pour chaque poste de l'équipe. Reporté pour cette raison.
2. **Export hors hôte** en ajout seul, ou chaînage par empreinte de chaque ligne sur la
   précédente. C'est le seuil au-delà duquel on peut parler de non-répudiation.

## Conséquences

- Les tests d'intégration ne peuvent pas nettoyer `audit_log` derrière eux, et doivent donc
  filtrer sur leur propre `target_id` plutôt que supposer une table vide.
- Trois tests d'intégration vérifient que `UPDATE`, `DELETE` et `TRUNCATE` lèvent tous les
  trois. Ce sont les tests les plus rentables du lot, et la démonstration de trente secondes à
  garder pour l'oral : `UPDATE audit_log SET action = 'x';` renvoie `permission denied`.
- L'adresse IP est une donnée personnelle. `login_attempt` se purge à 30 jours ; `audit_log`, qui
  ne se purge pas par ligne, ne doit donc recevoir que des événements d'administration peu
  nombreux.

## Alternatives écartées

- **Convention de code seule** : c'est la formulation du dossier EC01, et elle ne tient pas. Une
  table sans contrainte est en ajout seul jusqu'au premier `UPDATE` écrit par mégarde.
- **Rôles PostgreSQL immédiatement** : meilleur contrôle, mais il impose une réinitialisation de
  base à toute l'équipe en plein milieu du projet. Le déclencheur d'abord, les privilèges
  ensuite.
- **`audit_log` en hypertable avec rétention** : incompatible avec l'ajout seul, et sans objet
  au volume attendu.
