import { Service, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { environment } from '../../../environments/environment';
import {
  Recommendation,
  RecommendationGenerationReport,
} from '../../shared/models/recommendation.model';

@Service()
export class RecommendationsService {
  private http = inject(HttpClient);

  getRecommendations() {
    return this.http.get<Recommendation[]>(`${environment.apiUrl}/recommendations`);
  }

  getRecommendation(recommendationId: number) {
    return this.http.get<Recommendation>(
      `${environment.apiUrl}/recommendations/${recommendationId}`,
    );
  }

  generate(siteId?: string) {
    let params = new HttpParams();
    if (siteId) {
      params = params.set('site_id', siteId);
    }
    return this.http.post<RecommendationGenerationReport>(
      `${environment.apiUrl}/recommendations/generate`,
      null,
      { params },
    );
  }
}
