import { Service, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../environments/environment';
import { PredictionSummary } from '../../shared/models/prediction.model';

@Service()
export class PredictionsService {
  private http = inject(HttpClient);

  getPredictions() {
    return this.http.get<PredictionSummary>(`${environment.apiUrl}/predictions`);
  }
}
