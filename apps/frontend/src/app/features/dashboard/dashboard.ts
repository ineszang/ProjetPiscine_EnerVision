import { Component, OnInit, inject, signal, DestroyRef } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { timer, switchMap, catchError, EMPTY, Observable } from 'rxjs';
import { DecimalPipe } from '@angular/common';
import { StatsService } from '../../core/services/stats.service';
import { ConsumptionGauge } from '../../shared/components/consumption-gauge/consumption-gauge';
import { SiteLoadChart } from '../../shared/components/site-load-chart/site-load-chart';
import { AlertsService } from '../../core/services/alerts.service';
import { StatsSummary } from '../../shared/models/stats.model';
import { Alert } from '../../shared/models/alert.model';

const REFRESH_INTERVAL_MS = 10000;
const UNAVAILABLE_MESSAGE =
  'Données indisponibles, les valeurs affichées datent du dernier relevé.';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [DecimalPipe, ConsumptionGauge, SiteLoadChart],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.scss',
})
export class Dashboard implements OnInit {
  private statsService = inject(StatsService);
  private alertsService = inject(AlertsService);
  private destroyRef = inject(DestroyRef);

  stats = signal<StatsSummary | null>(null);
  alerts = signal<Alert[]>([]);
  error = signal<string | null>(null);

  ngOnInit(): void {
    this.alertsService
      .getAlerts()
      .pipe(catchError(() => this.reportUnavailable()))
      .subscribe((alerts) => this.alerts.set(alerts));

    // Piège : le catchError porte sur l'observable interne. Sur le flux externe il
    // terminerait le timer, et le rafraîchissement ne repartirait jamais.
    timer(0, REFRESH_INTERVAL_MS)
      .pipe(
        switchMap(() =>
          this.statsService.getSummary().pipe(catchError(() => this.reportUnavailable()))
        ),
        takeUntilDestroyed(this.destroyRef)
      )
      .subscribe((stats) => {
        this.error.set(null);
        this.stats.set(stats);
      });
  }

  private reportUnavailable(): Observable<never> {
    this.error.set(UNAVAILABLE_MESSAGE);
    return EMPTY;
  }
}
