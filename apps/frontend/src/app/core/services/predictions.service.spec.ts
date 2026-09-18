import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { PredictionsService } from './predictions.service';
import { environment } from '../../../environments/environment';

describe('PredictionsService', () => {
  let service: PredictionsService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(PredictionsService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('appelle le bon endpoint et retourne un résumé de prévisions', () => {
    let result: unknown;
    service.getPredictions().subscribe((r) => (result = r));

    const req = httpMock.expectOne(`${environment.apiUrl}/predictions`);
    expect(req.request.method).toBe('GET');

    req.flush({
      timestamp: '2026-09-18T09:00:00Z',
      sites: [{ site_id: 'SITE001', site_name: 'Test', prediction: null }],
    });

    expect((result as { sites: unknown[] }).sites.length).toBe(1);
  });
});
