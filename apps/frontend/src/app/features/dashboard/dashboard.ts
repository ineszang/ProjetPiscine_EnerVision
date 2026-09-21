import { Component, OnInit, inject, signal, DestroyRef, WritableSignal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { timer, switchMap, catchError, EMPTY, Observable } from 'rxjs';
import { DecimalPipe, DatePipe } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { StatsService } from '../../core/services/stats.service';
import { ConsumptionGauge } from '../../shared/components/consumption-gauge/consumption-gauge';
import { SiteLoadChart } from '../../shared/components/site-load-chart/site-load-chart';
import { AlertsService } from '../../core/services/alerts.service';
import { PredictionsService } from '../../core/services/predictions.service';
import { AuthService } from '../../core/services/auth.service';
import { StatsSummary } from '../../shared/models/stats.model';
import { Alert, AlertSeverity } from '../../shared/models/alert.model';
import { PredictionStatus, SitePredictionSummary } from '../../shared/models/prediction.model';
import { Card } from '../../shared/components/ui/card/card';
import { Alert as EvAlert } from '../../shared/components/ui/alert/alert';
import { Badge, BadgeTone } from '../../shared/components/ui/badge/badge';
import { Brand } from '../../shared/components/ui/brand/brand';
import { Button } from '../../shared/components/ui/button/button';

const REFRESH_INTERVAL_MS = 10000;
const UNAVAILABLE_MESSAGE =
  'Données indisponibles, les valeurs affichées datent du dernier relevé.';

const TON_PAR_SEVERITE: Record<AlertSeverity, BadgeTone> = {
  low: 'success',
  medium: 'warning',
  high: 'danger',
  critical: 'critical',
};

// `error` n'a pas de précédent dans les fixtures ou l'API à ce jour, mais figure dans le
// domaine du schéma backend (`ck_prediction_status`) : mieux vaut une couleur définie que
// tomber sur `undefined` si ce statut apparaît un jour.
const TON_PAR_STATUT_PREDICTION: Record<PredictionStatus, BadgeTone> = {
  available: 'success',
  insufficient_data: 'warning',
  error: 'danger',
};

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    DecimalPipe,
    DatePipe,
    RouterLink,
    ConsumptionGauge,
    SiteLoadChart,
    Card,
    EvAlert,
    Badge,
    Brand,
    Button,
  ],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.scss',
})
export class Dashboard implements OnInit {
  private statsService = inject(StatsService);
  private alertsService = inject(AlertsService);
  public auth = inject(AuthService);
  private predictionsService = inject(PredictionsService);
  private router = inject(Router);
  private destroyRef = inject(DestroyRef);

  stats = signal<StatsSummary | null>(null);
  alerts = signal<Alert[]>([]);
  predictions = signal<SitePredictionSummary[]>([]);

  // Un signal par flux, pas un seul `error` partagé : sinon le tick suivant de `timer` (stats)
  // efface silencieusement un message d'échec des prévisions ou des alertes après 10s au plus,
  // sans retry ni indication pour l'utilisateur que la section correspondante est restée vide.
  statsError = signal<string | null>(null);
  alertsError = signal<string | null>(null);
  predictionsError = signal<string | null>(null);

  ngOnInit(): void {
    this.alertsService
      .getAlerts()
      .pipe(catchError(() => this.reportUnavailable(this.alertsError)))
      .subscribe((alerts) => {
        this.alertsError.set(null);
        this.alerts.set(alerts);
      });

    // Les prévisions viennent d'un scoring hors ligne, pas d'un calcul à la demande : un seul
    // chargement au démarrage suffit, pas besoin du rafraîchissement périodique de `stats`.
    this.predictionsService
      .getPredictions()
      .pipe(catchError(() => this.reportUnavailable(this.predictionsError)))
      .subscribe((summary) => {
        this.predictionsError.set(null);
        this.predictions.set(summary.sites);
      });

    // Piège : le catchError porte sur l'observable interne. Sur le flux externe il
    // terminerait le timer, et le rafraîchissement ne repartirait jamais.
    timer(0, REFRESH_INTERVAL_MS)
      .pipe(
        switchMap(() =>
          this.statsService.getSummary().pipe(catchError(() => this.reportUnavailable(this.statsError))),
        ),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((stats) => {
        this.statsError.set(null);
        this.stats.set(stats);
      });
  }

  badgeToneForSeverity(severity: AlertSeverity): BadgeTone {
    return TON_PAR_SEVERITE[severity];
  }

  badgeToneForPredictionStatus(status: PredictionStatus): BadgeTone {
    return TON_PAR_STATUT_PREDICTION[status];
  }

  onLogout(): void {
    this.auth.logout().subscribe({
      next: () => this.router.navigate(['/login']),
      error: () => {
        // Même si l'appel réseau échoue, on considère l'utilisateur déconnecté localement.
        this.auth.clearSession();
        this.router.navigate(['/login']);
      },
    });
  }

  private reportUnavailable(target: WritableSignal<string | null>): Observable<never> {
    target.set(UNAVAILABLE_MESSAGE);
    return EMPTY;
  }
}
