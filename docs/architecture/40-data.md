# Données

PostgreSQL 17 avec l'extension TimescaleDB. Le choix, ses alternatives et ses conséquences sont
dans l'[ADR 0001](../adr/0001-postgresql-timescaledb.md), qui fait foi. Ce document décrit le
système qui en découle.

## Avertissement

**Aucune table applicative n'existe à ce jour.** `Base.metadata` est vide, `app/models/` ne
contient qu'un commentaire, l'unique révision Alembic ne crée aucune table, et aucune hypertable
n'a été déclarée. Tout ce qui suit sous le statut `Cible` est une proposition de structure, pas un
relevé du code. Le modèle sera arrêté au jalon J2.

## Trois emplacements, trois rôles

C'est la règle que l'ADR 0001 existe surtout pour fixer. La confondre coûte cher : un script placé
au mauvais endroit ne s'exécute jamais, ou s'exécute deux fois.

| Emplacement | Contenu | Quand ça s'exécute |
|---|---|---|
| `db/init/` | Extensions, bases annexes | **Une seule fois**, à la première initialisation du conteneur, quand `PGDATA` est vide. Ne rejoue jamais |
| `db/migrations/` | SQL versionné qui ne découle pas du schéma applicatif : rétention, compression | À la main, aujourd'hui vide |
| `apps/backend/alembic/` | Le schéma exposé par l'API, et lui seul | `alembic upgrade head`, c'est `Base.metadata` qui fait foi |

Une hypertable relève des deux derniers : **Alembic crée la table, et le `create_hypertable()`
vit dans la même révision**. Les séparer rendrait le schéma irreproductible depuis un seul
`alembic upgrade head`.

Détail de `db/init/` et du piège de montage : [`db/README.md`](../../db/README.md).

## Ce qui existe

Statut : `Fait`.

- `db/init/100-extensions.sql` crée l'extension `timescaledb`.
- `db/init/110-test-database.sql` crée `enervision_test`, dont le nom est attendu en dur par
  `apps/backend/tests/conftest.py`.
- Une révision Alembic, `5353c0e4f094`, qui **ne crée aucune table**. Elle établit
  `alembic_version` et refuse de s'appliquer si l'extension manque :

```sql
IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
    RAISE EXCEPTION 'extension timescaledb absente, voir db/init et db/README.md';
END IF;
```

Cette garde forme paire avec le 503 de `/api/v1/health/ready`. Un bootstrap sauté ne se voit pas
au démarrage de l'API : ces deux gardes le rendent visible tôt, des deux côtés.

## Cycle de vie d'une mesure

Statut : `Cible`. Aucun de ces maillons n'existe.

```mermaid
flowchart LR
  src["Source de mesures"] -.-> ing["Ingestion Airflow"]
  ing -.-> hy[("Hypertable mesure")]
  hy -.-> agg[("Agrégat continu")]
  hy -.-> comp["Compression"]
  hy -.-> ret["Rétention"]
  agg -.-> api["API FastAPI"]
  agg -.-> graf["Grafana"]
```

Les lectures de l'API et de Grafana visent l'agrégat continu, pas la table brute : c'est tout
l'intérêt de TimescaleDB, et cela doit rester vrai quand les volumes augmenteront.

## Modèle

Statut : `Cible`. Les entités ci-dessous sont des **candidates**, à valider en J2. Elles
s'appuient sur les gabarits de [`apps/backend/TESTING.md`](../../apps/backend/TESTING.md), qui
évoquent déjà un modèle `Site`, un `SiteRepository` et un `ConsumptionService` exposant un
`total_kwh(site_id)`.

```mermaid
erDiagram
  SITE ||--o{ POINT_DE_MESURE : porte
  POINT_DE_MESURE ||--o{ MESURE : produit

  SITE {
    int id PK
    string nom
  }
  POINT_DE_MESURE {
    int id PK
    int site_id FK
    string libelle
    string unite
  }
  MESURE {
    timestamptz horodatage PK
    int point_id PK
    double valeur
  }
```

`MESURE` est la table destinée à devenir une hypertable, partitionnée sur `horodatage`. Sa clé
primaire doit inclure la colonne de temps : TimescaleDB l'exige, une clé sur le seul identifiant
de point serait refusée.

## Gabarit de révision créant une hypertable

Conforme à la règle de l'ADR 0001 : table et hypertable dans la même révision.

```python
def upgrade() -> None:
    op.create_table(
        "mesure",
        sa.Column("horodatage", sa.DateTime(timezone=True), nullable=False),
        sa.Column("point_id", sa.Integer(), sa.ForeignKey("point_de_mesure.id"), nullable=False),
        sa.Column("valeur", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("horodatage", "point_id"),
    )
    op.execute("SELECT create_hypertable('mesure', by_range('horodatage'))")


def downgrade() -> None:
    op.drop_table("mesure")
```

`drop_table` suffit au retour arrière : supprimer la table supprime l'hypertable et ses partitions.

## Conventions

- **Noms au singulier**, en minuscules, sans préfixe de table.
- **Toute colonne de temps en `timestamptz`.** Jamais de `timestamp` nu : une mesure sans fuseau
  devient ininterprétable dès le premier changement d'heure.
- **La colonne de partitionnement s'appelle `horodatage`** et entre dans la clé primaire.
- **Les politiques de rétention et de compression** vont dans `db/migrations/`, pas dans Alembic :
  elles ne découlent pas du schéma applicatif.
- **Tout modèle doit être importé dans `app/models/__init__.py`**, sans quoi
  `alembic revision --autogenerate` ne le voit pas et génère un `drop` de sa table.

## Questions ouvertes

Elles relèvent du jalon J2, « valider le périmètre retenu », et bloquent le modèle définitif.

- **Quelles sources de mesures**, et selon quel protocole elles sont collectées.
- **Quelle granularité** à l'ingestion : la seconde, la minute, le quart d'heure.
- **Quels agrégats continus**, et sur quelles fenêtres.
- **Quelle profondeur de rétention** en données brutes, et à partir de quand on compresse.
- **Quelles unités** sont manipulées, et si une même table les mélange.
- **Multi-tenant ou non** : un site appartient-il à un client, et faut-il cloisonner les lectures.
