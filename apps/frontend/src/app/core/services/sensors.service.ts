import { Service, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../environments/environment';
import {SensorStatusResponse} from '../../shared/models/sensor-status.model';

@Service()
export class SensorsService {
  private http = inject(HttpClient);

  getStatus() {
    return this.http.get<SensorStatusResponse>(`${environment.apiUrl}/sensors/status`);
  }
}
