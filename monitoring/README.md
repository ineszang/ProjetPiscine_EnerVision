# Monitoring

Prometheus, Grafana et Alertmanager. Non initialise, voir le ticket dedie.

- `prometheus` : configuration de collecte et regles d'alerte.
- `grafana/provisioning` : sources de donnees et fournisseurs de dashboards.
- `grafana/dashboards` : dashboards versionnes au format JSON.
- `alertmanager` : routage et inhibition des alertes.

Le backend expose deja ses metriques sur `/metrics` au format Prometheus.
