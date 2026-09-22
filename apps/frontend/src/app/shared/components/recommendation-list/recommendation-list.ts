import { Component, DestroyRef, computed, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { DatePipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { catchError, EMPTY, forkJoin, Observable, switchMap, tap } from 'rxjs';
import { AlertsService } from '../../../core/services/alerts.service';
import { RecommendationsService } from '../../../core/services/recommendations.service';
import { Alert, AlertSeverity, AlertType } from '../../models/alert.model';
import { Recommendation } from '../../models/recommendation.model';
import { Site } from '../../models/site.model';
import {
  LIBELLE_PAR_SEVERITE,
  LIBELLE_PAR_TYPE,
  TON_PAR_SEVERITE,
} from '../../models/alert-presentation';
import { libelleRegle, tonRegle } from '../../models/recommendation-presentation';
import { Card } from '../ui/card/card';
import { Badge, BadgeTone } from '../ui/badge/badge';
import { Alert as EvAlert } from '../ui/alert/alert';

const UNAVAILABLE_MESSAGE = 'Recommandations indisponibles, réessayez plus tard.';

export interface RecommendedAlertView {
  alert: Alert;
  siteName: string;
  recommendations: Recommendation[];
}

interface Chargement {
  alerts: Alert[];
  recommendations: Recommendation[];
}

// Pourquoi : une recommandation ne porte que alert_id, jamais site_id, et /recommendations n'a
// aucun filtre ; la jointure se fait ici, en O(alertes), acceptable à la taille du jeu de données.
export function joinByAlert(
  alerts: Alert[],
  recommendations: Recommendation[],
  siteNames: Map<string, string>,
): RecommendedAlertView[] {
  const parAlerte = new Map<number, Recommendation[]>();
  for (const recommandation of recommendations) {
    const liste = parAlerte.get(recommandation.alert_id) ?? [];
    liste.push(recommandation);
    parAlerte.set(recommandation.alert_id, liste);
  }
  return alerts
    .filter((alert) => parAlerte.has(alert.alert_id))
    .map((alert) => ({
      alert,
      siteName: siteNames.get(alert.site_id) ?? alert.site_id,
      recommendations: [...(parAlerte.get(alert.alert_id) ?? [])].sort(
        (a, b) => a.recommendation_id - b.recommendation_id,
      ),
    }))
    .sort((a, b) => Date.parse(b.alert.timestamp) - Date.parse(a.alert.timestamp));
}

@Component({
  selector: 'app-recommendation-list',
  standalone: true,
  imports: [DatePipe, RouterLink, Card, Badge, EvAlert],
  templateUrl: './recommendation-list.html',
  styleUrl: './recommendation-list.scss',
})
export class RecommendationList {
  private alertsService = inject(AlertsService);
  private recommendationsService = inject(RecommendationsService);
  private destroyRef = inject(DestroyRef);

  siteId = input<string | null>(null);
  alertId = input<number | null>(null);
  sites = input<Site[]>([]);

  private data = signal<Chargement | null>(null);
  private reloadTick = signal(0);
  loading = signal(true);
  error = signal<string | null>(null);

  private trigger = computed(() => ({ siteId: this.siteId(), tick: this.reloadTick() }));

  private siteNameById = computed(
    () => new Map(this.sites().map((site) => [site.site_id, site.site_name])),
  );

  hasData = computed(() => this.data() !== null);

  groups = computed<RecommendedAlertView[]>(() => {
    const data = this.data();
    return data ? joinByAlert(data.alerts, data.recommendations, this.siteNameById()) : [];
  });

  visibleGroups = computed(() => {
    const alertId = this.alertId();
    const groups = this.groups();
    return alertId === null ? groups : groups.filter((group) => group.alert.alert_id === alertId);
  });

  total = computed(() =>
    this.visibleGroups().reduce((somme, group) => somme + group.recommendations.length, 0),
  );

  emptyMessage = computed(() => {
    if (this.alertId() !== null) {
      return 'Aucune recommandation pour cette alerte.';
    }
    return this.siteId()
      ? 'Aucune recommandation pour ce site.'
      : 'Aucune recommandation pour le moment.';
  });

  constructor() {
    toObservable(this.trigger)
      .pipe(
        tap(() => this.loading.set(true)),
        switchMap(({ siteId }) =>
          forkJoin({
            alerts: this.alertsService.getAlerts(siteId ? { site_id: siteId } : {}),
            recommendations: this.recommendationsService.getRecommendations(),
          }).pipe(catchError(() => this.reportUnavailable())),
        ),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((data) => {
        this.loading.set(false);
        this.error.set(null);
        this.data.set(data);
      });
  }

  reload(): void {
    this.reloadTick.update((tick) => tick + 1);
  }

  toneFor(severity: AlertSeverity): BadgeTone {
    return TON_PAR_SEVERITE[severity];
  }

  severityLabel(severity: AlertSeverity): string {
    return LIBELLE_PAR_SEVERITE[severity];
  }

  typeLabel(type: AlertType): string {
    return LIBELLE_PAR_TYPE[type];
  }

  ruleLabel(reference: string): string {
    return libelleRegle(reference);
  }

  ruleTone(reference: string): BadgeTone {
    return tonRegle(reference);
  }

  // Piège : vider les données avec l'erreur ; une demi-jointure (alertes sans recommandations,
  // ou l'inverse) afficherait des groupes faux plutôt que rien.
  private reportUnavailable(): Observable<never> {
    this.loading.set(false);
    this.error.set(UNAVAILABLE_MESSAGE);
    this.data.set(null);
    return EMPTY;
  }
}
