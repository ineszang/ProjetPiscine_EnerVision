import { Component, OnInit, inject, signal, DestroyRef } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { timer, switchMap, catchError, EMPTY, Observable } from 'rxjs';
import { DecimalPipe } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { StatsService } from '../../core/services/stats.service';
import { ConsumptionGauge } from '../../shared/components/consumption-gauge/consumption-gauge';
import { SiteLoadChart } from '../../shared/components/site-load-chart/site-load-chart';
import { AlertsService } from '../../core/services/alerts.service';
import { AuthService } from '../../core/services/auth.service';
import { StatsSummary } from '../../shared/models/stats.model';
import { Alert, AlertSeverity } from '../../shared/models/alert.model';
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

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    DecimalPipe,
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
  private router = inject(Router);
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
          this.statsService.getSummary().pipe(catchError(() => this.reportUnavailable())),
        ),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((stats) => {
        this.error.set(null);
        this.stats.set(stats);
      });
  }

  badgeToneForSeverity(severity: AlertSeverity): BadgeTone {
    return TON_PAR_SEVERITE[severity];
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

  private reportUnavailable(): Observable<never> {
    this.error.set(UNAVAILABLE_MESSAGE);
    return EMPTY;
  }
}
