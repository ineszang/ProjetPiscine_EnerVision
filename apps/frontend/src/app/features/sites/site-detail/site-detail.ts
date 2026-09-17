import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable, toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { catchError, EMPTY, filter, map, Observable, switchMap } from 'rxjs';
import { SitesService } from '../../../core/services/sites.service';
import { ReadingsService } from '../../../core/services/readings.service';
import { Site } from '../../../shared/models/site.model';
import { Reading } from '../../../shared/models/reading.model';
import { Card } from '../../../shared/components/ui/card/card';
import { Alert } from '../../../shared/components/ui/alert/alert';
import { Badge, BadgeTone } from '../../../shared/components/ui/badge/badge';
import { Brand } from '../../../shared/components/ui/brand/brand';
import { ConsumptionGauge } from '../../../shared/components/consumption-gauge/consumption-gauge';
import { ReadingHistoryChart } from '../../../shared/components/reading-history-chart/reading-history-chart';

const UNAVAILABLE_MESSAGE = 'Détail du site indisponible, réessayez plus tard.';
const HISTORY_WINDOW_MS = 24 * 60 * 60 * 1000;

const TON_PAR_STATUT: Record<string, BadgeTone> = {
  actif: 'success',
  maintenance: 'warning',
  hors_service: 'danger',
};

type MetricKey =
  | 'consumption_kw'
  | 'voltage_v'
  | 'current_a'
  | 'power_factor'
  | 'temperature_celsius'
  | 'humidity_percent';

interface MetricDef {
  key: MetricKey;
  label: string;
  format: (value: number) => string;
}

const METRIC_DEFS: MetricDef[] = [
  { key: 'consumption_kw', label: 'Consommation', format: (v) => `${v.toFixed(1)} kW` },
  { key: 'voltage_v', label: 'Tension', format: (v) => `${v.toFixed(1)} V` },
  { key: 'current_a', label: 'Courant', format: (v) => `${v.toFixed(1)} A` },
  { key: 'power_factor', label: 'Cos φ', format: (v) => v.toFixed(2) },
  { key: 'temperature_celsius', label: 'Température', format: (v) => `${v.toFixed(1)} °C` },
  { key: 'humidity_percent', label: 'Humidité', format: (v) => `${v.toFixed(0)} %` },
];

// Contrainte : miroir de `RAISON_VERS_CAPTEUR`/`CHAMPS_PAR_CAPTEUR` côté backend
// (apps/backend/app/services/sensor.py) - `null_reasons` porte le code de panne du capteur,
// jamais le nom du champ.
const RAISONS_PAR_CHAMP: Record<MetricKey, string[]> = {
  consumption_kw: ['consumption_sensor_failure', 'network_loss'],
  voltage_v: ['electrical_sensor_failure', 'network_loss'],
  current_a: ['electrical_sensor_failure', 'network_loss'],
  power_factor: ['electrical_sensor_failure', 'network_loss'],
  temperature_celsius: ['temperature_sensor_failure', 'network_loss'],
  humidity_percent: ['humidity_sensor_failure', 'network_loss'],
};

const LIBELLE_PAR_RAISON: Record<string, string> = {
  consumption_sensor_failure: 'capteur de consommation en panne',
  electrical_sensor_failure: 'capteur électrique en panne',
  temperature_sensor_failure: 'capteur de température en panne',
  humidity_sensor_failure: 'capteur d\'humidité en panne',
  network_loss: 'perte réseau',
};

export interface MetricView {
  key: MetricKey;
  label: string;
  value: string | null;
  reason: string;
}

@Component({
  selector: 'app-site-detail',
  standalone: true,
  imports: [RouterLink, Card, Alert, Badge, Brand, ConsumptionGauge, ReadingHistoryChart],
  templateUrl: './site-detail.html',
  styleUrl: './site-detail.scss',
})
export class SiteDetail {
  private route = inject(ActivatedRoute);
  private sitesService = inject(SitesService);
  private readingsService = inject(ReadingsService);
  private destroyRef = inject(DestroyRef);

  siteId = toSignal(this.route.paramMap.pipe(map((params) => params.get('siteId') ?? '')));

  site = signal<Site | null>(null);
  latestReading = signal<Reading | null>(null);
  history = signal<Reading[]>([]);
  error = signal<string | null>(null);

  metrics = computed<MetricView[]>(() => {
    const reading = this.latestReading();
    return METRIC_DEFS.map((def) => {
      const valeur = reading ? reading[def.key] : null;
      return {
        key: def.key,
        label: def.label,
        value: valeur != null ? def.format(valeur) : null,
        reason: valeur == null ? this.reasonFor(def.key, reading) : '',
      };
    });
  });

  constructor() {
    toObservable(this.siteId)
      .pipe(
        filter((siteId): siteId is string => !!siteId),
        // Piège : switchMap sur le flux externe annule le chargement en cours dès qu'un
        // nouveau siteId arrive, sinon une réponse en retard peut écraser le site affiché.
        switchMap((siteId) => this.load(siteId)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((result) => {
        this.error.set(null);
        this.site.set(result.site);
        this.latestReading.set(result.latest);
        this.history.set(result.history);
      });
  }

  badgeToneForStatus(status: string | null): BadgeTone {
    return status ? (TON_PAR_STATUT[status] ?? 'neutral') : 'neutral';
  }

  private load(siteId: string) {
    return this.sitesService.getSite(siteId).pipe(
      switchMap((site) =>
        this.readingsService.getLatest(siteId).pipe(map((latest) => ({ site, latest }))),
      ),
      switchMap(({ site, latest }) => {
        // Piège : le dataset historique se termine bien avant « maintenant ». Ancrer la
        // fenêtre sur la dernière mesure connue plutôt que sur l'horloge évite un historique
        // vide dès que le jeu de données n'est plus récent.
        const end = latest?.timestamp;
        const start = end
          ? new Date(new Date(end).getTime() - HISTORY_WINDOW_MS).toISOString()
          : undefined;
        return this.readingsService
          .getHistory(siteId, start, end)
          .pipe(map((history) => ({ site, latest, history })));
      }),
      catchError(() => this.reportUnavailable()),
    );
  }

  private reasonFor(field: MetricKey, reading: Reading | null): string {
    const raisons = RAISONS_PAR_CHAMP[field];
    const trouvees = (reading?.null_reasons ?? [])
      .filter((raison) => raisons.includes(raison))
      .map((raison) => LIBELLE_PAR_RAISON[raison] ?? raison);
    return trouvees.length > 0 ? trouvees.join(', ') : 'cause inconnue';
  }

  private reportUnavailable(): Observable<never> {
    this.error.set(UNAVAILABLE_MESSAGE);
    return EMPTY;
  }
}
