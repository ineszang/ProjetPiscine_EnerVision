import { Component, OnInit, inject, signal, DestroyRef, WritableSignal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { timer, switchMap, catchError, EMPTY, Observable } from 'rxjs';
import { DecimalPipe, DatePipe } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { StatsService } from '../../core/services/stats.service';
import { ConsumptionGauge } from '../../shared/components/consumption-gauge/consumption-gauge';
import { SiteLoadChart } from '../../shared/components/site-load-chart/site-load-chart';
import { AlertFeed } from '../../shared/components/alert-feed/alert-feed';
import { PredictionsService } from '../../core/services/predictions.service';
import { AuthService } from '../../core/services/auth.service';
import { StatsSummary } from '../../shared/models/stats.model';
import { PredictionStatus, SitePredictionSummary } from '../../shared/models/prediction.model';
import { Card } from '../../shared/components/ui/card/card';
import { Alert as EvAlert } from '../../shared/components/ui/alert/alert';
import { Badge, BadgeTone } from '../../shared/components/ui/badge/badge';
import { Brand } from '../../shared/components/ui/brand/brand';
import { Button } from '../../shared/components/ui/button/button';

const REFRESH_INTERVAL_MS = 10000;
const UNAVAILABLE_MESSAGE =
  'Données indisponibles, les valeurs affichées datent du dernier relevé.';

// `error` n'a pas encore de précédent côté API mais figure dans `ck_prediction_status` :
// mieux vaut un ton défini que `undefined` le jour où ce statut apparaît.
const TON_PAR_STATUT_PREDICTION: Record<PredictionStatus, BadgeTone> = {
  available: 'success',
  insufficient_data: 'warning',
  error: 'danger',
};

const SEUIL_CHARGE_SOUTENUE = 70;
const SEUIL_CHARGE_CRITIQUE = 90;

export type LoadTone = 'success' | 'warning' | 'danger';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    DecimalPipe,
    DatePipe,
    RouterLink,
    ConsumptionGauge,
    SiteLoadChart,
    AlertFeed,
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
  public auth = inject(AuthService);
  private predictionsService = inject(PredictionsService);
  private router = inject(Router);
  private destroyRef = inject(DestroyRef);

  stats = signal<StatsSummary | null>(null);
  predictions = signal<SitePredictionSummary[]>([]);

  // Piège : un signal d'erreur par flux, sinon le tick suivant de `timer` (stats) efface en
  // silence l'échec des prévisions après 10 s au plus, sans retry ni indication à l'utilisateur.
  statsError = signal<string | null>(null);
  predictionsError = signal<string | null>(null);

  ngOnInit(): void {
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
          this.statsService
            .getSummary()
            .pipe(catchError(() => this.reportUnavailable(this.statsError))),
        ),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((stats) => {
        this.statsError.set(null);
        this.stats.set(stats);
      });
  }

  badgeToneForPredictionStatus(status: PredictionStatus): BadgeTone {
    return TON_PAR_STATUT_PREDICTION[status];
  }

  loadTone(percent: number): LoadTone {
    if (percent >= SEUIL_CHARGE_CRITIQUE) {
      return 'danger';
    }
    return percent >= SEUIL_CHARGE_SOUTENUE ? 'warning' : 'success';
  }

  loadHint(percent: number): string {
    switch (this.loadTone(percent)) {
      case 'danger':
        return 'Proche de la capacité du parc';
      case 'warning':
        return 'Charge soutenue';
      default:
        return 'Marge confortable';
    }
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
