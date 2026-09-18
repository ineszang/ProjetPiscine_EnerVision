# 0002 - Authentification par JWT d'accès et jeton de rafraîchissement opaque

- Statut : accepté
- Date : 2026-09-15

## Contexte

L'école n'impose aucun mécanisme d'authentification : les choix techniques sont libres et
doivent être justifiés. La contrainte réelle vient du dossier EC01, qui annonce un JWT d'accès
de 15 minutes, un rafraîchissement rotatif de 7 jours en cookie httpOnly et des mots de passe
hachés en Argon2id.

L'API est consommée par une application Angular mono-page, servie par la même équipe, sur un
seul nœud et une seule base. Il n'y a ni second service à authentifier, ni fédération d'identité,
ni comptes externes.

## Décision

**Jeton d'accès : JWT signé en HS256**, 15 minutes, porté par l'en-tête `Authorization`, gardé
en mémoire JavaScript et jamais persisté côté navigateur.

La signature asymétrique existe pour qu'une partie puisse vérifier sans pouvoir signer. Ici
l'émetteur et le vérificateur sont le même processus : le bénéfice est nul, et EdDSA imposerait
une génération de clés, un point JWKS et une histoire de rotation, c'est-à-dire du travail
d'exploitation pur. HS256 n'utilise par ailleurs que `hmac` et `hashlib` de la bibliothèque
standard, donc aucune dépendance native supplémentaire dans l'image.

Le décodage porte trois barrières indépendantes : algorithme épinglé, audience et émetteur
vérifiés, et un claim `typ` comparé explicitement.

**Jeton de rafraîchissement : chaîne opaque de 256 bits, jamais un JWT.** Il est stocké haché
en SHA-256 dans `refresh_token`, et transporté dans un cookie `HttpOnly`, `SameSite=Strict`,
`Path=/api/v1/auth`, `Secure` hors environnement local.

Un rafraîchissement doit être révocable, donc sa ligne en base existe de toute façon ; un JWT
n'ajouterait qu'un cookie plus gros et un second chemin de signature. Surtout, la séparation
d'avec le jeton d'accès devient **structurelle et non conditionnelle** : un JWT ne figure dans
aucune ligne, une chaîne opaque échoue au décodage. La confusion refresh-vers-accès, qui
transforme silencieusement une fenêtre de 15 minutes en fenêtre de 7 jours, devient impossible
même si quelqu'un oublie le test.

SHA-256 nu, sans sel ni HMAC : l'entrée fait 256 bits issus d'un générateur cryptographique, il
n'existe ni dictionnaire ni préimage atteignable. Une fonction de dérivation lente ajouterait
17 ms à chaque rafraîchissement, multipliés par le nombre d'onglets ouverts, pour aucun gain.

**Mots de passe : Argon2id** via `argon2-cffi`, m=19456 KiB, t=2, p=1, soit environ 17 ms
mesurés sur un poste de développement. Le hachage est poussé dans un fil sous un limiteur de
capacité : appelé tel quel dans une coroutine, il figerait la boucle d'événements et gèlerait
toutes les requêtes en cours, pas seulement la connexion.

**Rotation avec détection de réutilisation.** Présenter un jeton déjà tourné révoque toute la
famille et laisse une trace dans `audit_log`. Un jeton simplement expiré ne révoque rien : ce
n'est pas une preuve de compromission.

**Pas de verrouillage de compte.** Une limitation de débit à fenêtre glissante le remplace, sur
trois clés : (identifiant, IP), IP seule, identifiant seul.

## Pourquoi la rotation seule ne suffit pas

Avec rotation sans détection, l'attaquant qui a volé le cookie le fait tourner en boucle. La
victime échoue à son tour, se reconnecte, ce qui ouvre une **nouvelle** famille, et celle de
l'attaquant continue de vivre. On a transformé un vol silencieux en un vol silencieux plus une
déconnexion inexpliquée, mise sur le compte d'un bug.

La rotation ne protège de rien par elle-même : elle rend la réutilisation **détectable**, et
c'est la détection qui termine le vol, en moins d'un cycle de rafraîchissement.

Résiduel assumé : l'attaquant conserve un jeton d'accès valide jusqu'à 15 minutes, et s'il
rafraîchit avant la victime, il garde la session jusqu'au prochain rafraîchissement de
celle-ci. Borné, pas nul.

## Pourquoi pas de verrouillage de compte

Le verrouillage est un vecteur de déni de service trivial : cinq mots de passe faux suffisent à
mettre un administrateur dehors, et la boucle se répète indéfiniment. Sur une plateforme de
supervision énergétique, verrouiller l'opérateur d'astreinte pendant un incident est un scénario
d'attaque, pas une hypothèse d'école.

Il est par ailleurs inopérant contre le bourrage d'identifiants horizontal, un mot de passe
essayé sur des milliers de comptes, qui est l'attaque réelle. Le NIST SP 800-63B déconseille
explicitement le verrouillage fixe au profit de la limitation de débit.

Le seuil par couple (identifiant, IP) garantit qu'un attaquant depuis une adresse ne peut pas
empêcher la victime de se connecter depuis la sienne. Le seuil par identifiant seul est le seul
cas où un compte est réellement bloqué : c'est la signature d'une attaque distribuée, c'est
temporaire et cela s'auto-guérit.

## Conséquences

- Le rechargement de page perd le jeton d'accès. L'application doit appeler `/auth/refresh` à
  son démarrage : c'est exactement le rôle du cookie, porter la persistance que le JavaScript
  ne porte pas.
- L'intercepteur HTTP doit garantir **un seul rafraîchissement en vol**. Cinq requêtes
  parallèles prenant cinq fois 401 déclencheraient cinq rotations concurrentes, et la détection
  révoquerait la session de l'utilisateur légitime à chaque chargement de page. Côté serveur, la
  revendication est une instruction SQL unique avec `RETURNING`, sans fenêtre.
- `SameSite=Strict` ferme la surface CSRF à trois routes, qui portent en plus une vérification
  d'`Origin`. Le jour où un flux OIDC arrive, il faudra repasser à `Lax`.
- Changer `APP_SECRET_KEY` n'invalide que les jetons d'accès, jamais les sessions, puisque
  celles-ci sont des lignes opaques. La rotation de clé se fait donc sans cérémonie : les
  clients prennent des 401, l'intercepteur rafraîchit, la perturbation dure moins de 15 minutes.
- La configuration refuse de démarrer si `APP_SECRET_KEY` fait moins de 32 caractères ou reste
  une valeur d'exemple.

## Alternatives écartées

- **Keycloak ou un fournisseur OIDC** : un serveur d'identité se justifie par la **fédération**,
  c'est-à-dire plusieurs applications, du SSO, des comptes externes. Il y a une application et
  des comptes internes. Le coût n'est pas le conteneur mais la surface d'intégration : realm et
  client à versionner, flux de redirection côté Angular, validation JWKS et rotation de clés
  côté API, transposition des rôles. Deux à trois jours sur un budget de dix.
  **Critère de bascule** : l'exigence de SSO d'un client pilote. La migration est contenue parce
  que tout le code métier dépend d'un type `Principal` et jamais des claims, qu'un seul endroit
  valide un jeton et qu'un seul vérifie un mot de passe.
- **Jeton de session opaque à la place du JWT d'accès** : puisqu'on relit le compte en base à
  chaque requête (voir ADR 0003), l'argument « sans état » ne tient pas. Un jeton opaque serait
  défendable. Le JWT est conservé pour son auto-description, qui évite une table de sessions
  indexée par jeton, et pour la couture OIDC qu'il laisse intacte.
- **Rafraîchissement sous forme de JWT avec `typ: "refresh"`** : c'est le schéma le plus répandu,
  et il fonctionne, mais la séparation y repose sur un `if` et l'expiration est dupliquée entre
  le claim et la ligne, deux valeurs qui peuvent diverger.
- **Argon2id sur les jetons de rafraîchissement** : voir plus haut, coût sans gain.
- **Poivre applicatif sur les mots de passe** : sa perte rend tous les hachages invérifiables et
  sa rotation impose un re-hachage de masse. Sur deux semaines, le risque dépasse le gain.
- **`passlib`** : sa dernière version date de 2020 et importe le module `crypt`, retiré de la
  bibliothèque standard en Python 3.13. Éliminatoire sur Python 3.14.
- **`python-jose`** : maintenance erratique et CVE en 2024. `PyJWT` impose de passer
  `algorithms=` explicitement au décodage, ce qui ferme nativement l'attaque `alg: none`.
