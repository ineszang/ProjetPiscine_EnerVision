import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { catchError, EMPTY, Observable } from 'rxjs';
import {Badge, BadgeTone} from '../../../shared/components/ui/badge/badge';
import {Card} from '../../../shared/components/ui/card/card';
import {Alert} from '../../../shared/components/ui/alert/alert';
import {Brand} from '../../../shared/components/ui/brand/brand';
import {SensorsService} from '../../../core/services/sensors.service';
import {SensorDiagnostic, SensorStatusResponse} from '../../../shared/models/sensor-status.model';
import { DatePipe } from '@angular/common';

const UNAVAILABLE_MESSAGE = 'État des capteurs indisponible, réessayez plus tard.';

const SENSOR_LABELS: Record<string, string> = {
  consumption: 'Consommation',
  electrical: 'Électrique',
  temperature: 'Température',
  humidity: 'Humidité',
  network: 'Réseau',
};

const TON_PAR_OVERALL: Record<string, BadgeTone> = {
  ok: 'success',
  degraded: 'warning',
  critical: 'critical',
};

@Component({
  selector: 'app-sensor-status',
  standalone: true,
  imports: [RouterLink, Card, Alert, Badge, Brand, DatePipe],
  templateUrl: './sensor-status.html',
  styleUrl: './sensor-status.scss',
})
export class SensorStatusView implements OnInit {
  private sensorsService = inject(SensorsService);

  data = signal<SensorStatusResponse | null>(null);
  error = signal<string | null>(null);

  readonly sensorEntries = Object.entries(SENSOR_LABELS);

  ngOnInit(): void {
    this.sensorsService
      .getStatus()
      .pipe(catchError(() => this.reportUnavailable()))
      .subscribe((response) => {
        this.error.set(null);
        this.data.set(response);
      });
  }

  sensorOf(sensors: Record<string, SensorDiagnostic>, key: string): SensorDiagnostic {
    return sensors[key];
  }

  badgeToneForOverall(overall: string): BadgeTone {
    return TON_PAR_OVERALL[overall] ?? 'neutral';
  }

  private reportUnavailable(): Observable<never> {
    this.error.set(UNAVAILABLE_MESSAGE);
    return EMPTY;
  }
}
