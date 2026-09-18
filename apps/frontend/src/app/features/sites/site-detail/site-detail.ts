import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable, toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { catchError, EMPTY, filter, map, Observable, of, switchMap } from 'rxjs';
import { SitesService } from '../../../core/services/sites.service';
import { ReadingsService } from '../../../core/services/readings.service';
import { Site } from '../../../shared/models/site.model';
import { Reading, ReadingDataQuality } from '../../../shared/models/reading.model';
import { SiteCurrent } from '../../../shared/models/site-current.model';
import { Card } from '../../../shared/components/ui/card/card';
import { Alert } from '../../../shared/components/ui/alert/alert';
import { Badge, BadgeTone } from '../../../shared/components/ui/badge/badge';
import { Brand } from '../../../shared/components/ui/brand/brand';
import { ConsumptionGauge } from '../../../shared/components/consumption-gauge/consumption-gauge';
import { ReadingHistoryChart } from '../../../shared/components/reading-history-chart/reading-history-chart';

const UNAVAILABLE_MESSAGE = 'Détail du site indisponible, réessayez plus tard.';
const NO_MEASUREMENT_MESSAGE = 'Aucune mesure remontée pour ce site.';
const HISTORY_WINDOW_MS = 24 * 60 * 60 * 1000;

const TON_PAR_STATUT: Record<string, BadgeTone> = {
  actif: 'success',
  maintenance: 'warning',
  hors_service: 'danger',
};

const TON_PAR_QUALITE: Record<ReadingDataQuality, BadgeTone> = {
  good: 'success',
  partial: 'warning',
  degraded: 'danger',
  critical: 'critical',
};

const LIBELLE_PAR_QUALITE: Record<ReadingDataQuality, string> = {
  good: 'Données complètes',
  partial: 'Données partielles',
  degraded: 'Données dégradées',
  critical: 'Données critiques',
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

// Contrainte : miroir de RAISON_VERS_CAPTEUR et CHAMPS_PAR_CAPTEUR (backend, services/sensor.py) ;
// `null_reasons` porte le code de panne du capteur, jamais le nom du champ resté vide.
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
  humidity_sensor_failure: "capteur d'humidité en panne",
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

  readonly noMeasurementMessage = NO_MEASUREMENT_MESSAGE;

  siteId = toSignal(this.route.paramMap.pipe(map((params) => params.get('siteId') ?? '')));

  site = signal<Site | null>(null);
  current = signal<SiteCurrent | null>(null);
  history = signal<Reading[]>([]);
  error = signal<string | null>(null);

  hasMeasurement = computed(() => this.current()?.timestamp != null);

  qualityLabel = computed(() => {
    const quality = this.current()?.data_quality;
    return quality ? LIBELLE_PAR_QUALITE[quality] : null;
  });

  qualityTone = computed<BadgeTone>(() => {
    const quality = this.current()?.data_quality;
    return quality ? TON_PAR_QUALITE[quality] : 'neutral';
  });

  metrics = computed<MetricView[]>(() => {
    const current = this.current();
    return METRIC_DEFS.map((def) => {
      const valeur = current ? current[def.key] : null;
      return {
        key: def.key,
        label: def.label,
        value: valeur != null ? def.format(valeur) : null,
        reason: valeur == null ? this.reasonFor(def.key, current) : '',
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
        this.current.set(result.current);
        this.history.set(result.history);
      });
  }

  badgeToneForStatus(status: string | null): BadgeTone {
    return status ? (TON_PAR_STATUT[status] ?? 'neutral') : 'neutral';
  }

  private load(siteId: string) {
    return this.sitesService.getSite(siteId).pipe(
      switchMap((site) =>
        this.sitesService.getCurrent(siteId).pipe(map((current) => ({ site, current }))),
      ),
      switchMap(({ site, current }) =>
        this.loadHistory(siteId, current).pipe(map((history) => ({ site, current, history }))),
      ),
      catchError(() => this.reportUnavailable()),
    );
  }

  private loadHistory(siteId: string, current: SiteCurrent): Observable<Reading[]> {
    // Piège : le jeu de données s'arrête bien avant « maintenant » ; ancrer la fenêtre sur la
    // dernière mesure connue plutôt que sur l'horloge évite un historique systématiquement vide.
    const end = current.timestamp;
    if (end === null) {
      return of([]);
    }
    const start = new Date(new Date(end).getTime() - HISTORY_WINDOW_MS).toISOString();
    return this.readingsService.getHistory(siteId, start, end);
  }

  private reasonFor(field: MetricKey, current: SiteCurrent | null): string {
    const raisons = RAISONS_PAR_CHAMP[field];
    const trouvees = (current?.null_reasons ?? [])
      .filter((raison) => raisons.includes(raison))
      .map((raison) => LIBELLE_PAR_RAISON[raison] ?? raison);
    return trouvees.length > 0 ? trouvees.join(', ') : 'cause inconnue';
  }

  private reportUnavailable(): Observable<never> {
    this.error.set(UNAVAILABLE_MESSAGE);
    return EMPTY;
  }
}
