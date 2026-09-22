import { Component, DestroyRef, computed, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable, toSignal } from '@angular/core/rxjs-interop';
import { DatePipe, DecimalPipe } from '@angular/common';
import { catchError, EMPTY, Observable, of, switchMap, tap, timer } from 'rxjs';
import { AlertFilters, AlertsService } from '../../../core/services/alerts.service';
import { SitesService } from '../../../core/services/sites.service';
import { Alert, AlertMetric, AlertSeverity, AlertType } from '../../models/alert.model';
import { Site } from '../../models/site.model';
import {
  LIBELLE_PAR_SEVERITE,
  LIBELLE_PAR_TYPE,
  SEVERITES,
  TON_PAR_SEVERITE,
  UNITE_PAR_METRIQUE,
} from '../../models/alert-presentation';
import { Badge, BadgeTone } from '../ui/badge/badge';
import { Button } from '../ui/button/button';
import { Alert as EvAlert } from '../ui/alert/alert';
import { Icon } from '../ui/icon/icon';

// Le DAG de détection tourne toutes les heures : une minute suffit largement pour suivre le flux.
const REFRESH_INTERVAL_MS = 60_000;
const PAGE_SIZE = 10;
const UNAVAILABLE_MESSAGE = 'Alertes indisponibles, la liste affichée date du dernier chargement.';

@Component({
  selector: 'app-alert-feed',
  standalone: true,
  imports: [DatePipe, DecimalPipe, Badge, Button, EvAlert, Icon],
  templateUrl: './alert-feed.html',
  styleUrl: './alert-feed.scss',
})
export class AlertFeed {
  private alertsService = inject(AlertsService);
  private sitesService = inject(SitesService);
  private destroyRef = inject(DestroyRef);

  siteId = input<string | null>(null);

  readonly severites = SEVERITES;
  severity = signal<AlertSeverity | null>(null);
  siteFilter = signal<string | null>(null);

  alerts = signal<Alert[]>([]);
  loading = signal(true);
  error = signal<string | null>(null);
  visibleCount = signal(PAGE_SIZE);

  sites = toSignal(this.sitesService.getSites().pipe(catchError(() => of([] as Site[]))), {
    initialValue: [] as Site[],
  });

  private filters = computed<AlertFilters>(() => ({
    site_id: this.siteId() ?? this.siteFilter() ?? undefined,
    severity: this.severity() ?? undefined,
  }));

  private siteNameById = computed(
    () => new Map(this.sites().map((site) => [site.site_id, site.site_name])),
  );

  visibleAlerts = computed(() => this.alerts().slice(0, this.visibleCount()));
  hiddenCount = computed(() => Math.max(this.alerts().length - this.visibleCount(), 0));

  constructor() {
    toObservable(this.filters)
      .pipe(
        tap(() => {
          this.loading.set(true);
          this.visibleCount.set(PAGE_SIZE);
        }),
        // Piège : catchError sur l'observable interne ; sur le flux externe il terminerait le
        // timer et le rafraîchissement ne repartirait jamais.
        switchMap((filters) =>
          timer(0, REFRESH_INTERVAL_MS).pipe(
            switchMap(() =>
              this.alertsService
                .getAlerts(filters)
                .pipe(catchError(() => this.reportUnavailable())),
            ),
          ),
        ),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((alerts) => {
        this.loading.set(false);
        this.error.set(null);
        this.alerts.set(alerts);
      });
  }

  onSiteChange(event: Event): void {
    this.siteFilter.set((event.target as HTMLSelectElement).value || null);
  }

  onSeverityChange(event: Event): void {
    const value = (event.target as HTMLSelectElement).value;
    this.severity.set(value ? (value as AlertSeverity) : null);
  }

  showMore(): void {
    this.visibleCount.update((count) => count + PAGE_SIZE);
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

  siteName(siteId: string): string {
    return this.siteNameById().get(siteId) ?? siteId;
  }

  unitFor(metric: AlertMetric | null): string {
    return metric ? UNITE_PAR_METRIQUE[metric] : '';
  }

  private reportUnavailable(): Observable<never> {
    this.loading.set(false);
    this.error.set(UNAVAILABLE_MESSAGE);
    return EMPTY;
  }
}
