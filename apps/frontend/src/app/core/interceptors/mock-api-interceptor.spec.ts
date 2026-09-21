import { TestBed } from '@angular/core/testing';
import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { mockApiInterceptor } from './mock-api-interceptor';
import { environment } from '../../../environments/environment';
import { STATS_SUMMARY_FIXTURE } from '../mocks/stats-summary.fixture';

describe('mockApiInterceptor', () => {
  let http: HttpClient;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([mockApiInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    http = TestBed.inject(HttpClient);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    environment.useMockFixtures = true;
    httpMock.verify();
  });

  it('renvoie la fixture sans appel réseau quand useMockFixtures est activé', () => {
    environment.useMockFixtures = true;
    let result: unknown;

    http.get(`${environment.apiUrl}/stats/summary`).subscribe((r) => (result = r));

    httpMock.expectNone(`${environment.apiUrl}/stats/summary`);
    expect((result as typeof STATS_SUMMARY_FIXTURE).total_sites).toBe(
      STATS_SUMMARY_FIXTURE.total_sites,
    );
  });

  it('laisse passer la vraie requête quand useMockFixtures est désactivé', () => {
    environment.useMockFixtures = false;

    http.get(`${environment.apiUrl}/stats/summary`).subscribe();

    const req = httpMock.expectOne(`${environment.apiUrl}/stats/summary`);
    req.flush({});
  });

  it("laisse passer une requête qui ne correspond à aucune route connue de l'interceptor", () => {
    environment.useMockFixtures = true;

    http.get('/api/v1/autre-chose').subscribe();

    const req = httpMock.expectOne('/api/v1/autre-chose');
    req.flush({});
  });

  it('renvoie la fixture des alertes sans appel réseau quand useMockFixtures est activé', () => {
    environment.useMockFixtures = true;
    let result: unknown;

    http.get(`${environment.apiUrl}/alerts`).subscribe((r) => (result = r));

    httpMock.expectNone(`${environment.apiUrl}/alerts`);
    expect((result as unknown[]).length).toBeGreaterThan(0);
  });

  it('laisse toujours passer /predictions vers le réseau, même avec useMockFixtures activé', () => {
    environment.useMockFixtures = true;

    http.get(`${environment.apiUrl}/predictions`).subscribe();

    const req = httpMock.expectOne(`${environment.apiUrl}/predictions`);
    req.flush({ timestamp: '2026-09-18T09:00:00Z', sites: [] });
  });
});
