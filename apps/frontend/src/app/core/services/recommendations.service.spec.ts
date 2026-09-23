import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { RecommendationsService } from './recommendations.service';
import { environment } from '../../../environments/environment';
import { Recommendation } from '../../shared/models/recommendation.model';

const RECOMMANDATION_API: Recommendation = {
  recommendation_id: 1,
  alert_id: 1,
  action: 'Vérifier la consommation',
  explanation: 'Pic détecté',
  rule_reference: 'spike-v1',
  created_at: '2024-01-01T00:00:00Z',
};

describe('RecommendationsService', () => {
  let service: RecommendationsService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(RecommendationsService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('liste les recommandations depuis le bon endpoint', () => {
    let result: Recommendation[] = [];
    service.getRecommendations().subscribe((r) => (result = r));

    const req = httpMock.expectOne(`${environment.apiUrl}/recommendations`);
    expect(req.request.method).toBe('GET');
    req.flush([RECOMMANDATION_API]);

    expect(result.length).toBe(1);
    expect(result[0].alert_id).toBe(1);
  });

  it('décrit une recommandation par son identifiant', () => {
    service.getRecommendation(42).subscribe();

    const req = httpMock.expectOne(`${environment.apiUrl}/recommendations/42`);
    expect(req.request.method).toBe('GET');
    req.flush({ ...RECOMMANDATION_API, recommendation_id: 42 });
  });

  it('déclenche la génération en POST avec le site en paramètre de requête', () => {
    let result: unknown;
    service.generate('SITE001').subscribe((r) => (result = r));

    const req = httpMock.expectOne(
      (r) => r.url === `${environment.apiUrl}/recommendations/generate` && r.method === 'POST',
    );
    expect(req.request.params.get('site_id')).toBe('SITE001');
    expect(req.request.body).toBeNull();
    req.flush({ alerts_examined: 2, recommendations_created: 3, already_present: 1 });

    expect(result).toEqual({ alerts_examined: 2, recommendations_created: 3, already_present: 1 });
  });

  it('génère pour tout le parc quand aucun site n’est donné', () => {
    service.generate().subscribe();

    const req = httpMock.expectOne(
      (r) => r.url === `${environment.apiUrl}/recommendations/generate` && r.method === 'POST',
    );
    expect(req.request.params.has('site_id')).toBe(false);
    req.flush({ alerts_examined: 0, recommendations_created: 0, already_present: 0 });
  });
});
