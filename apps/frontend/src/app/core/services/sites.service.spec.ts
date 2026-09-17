import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { SitesService } from './sites.service';
import { environment } from '../../../environments/environment';

describe('SitesService', () => {
  let service: SitesService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(SitesService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('appelle le bon endpoint et retourne la liste des sites', () => {
    let result: unknown;
    service.getSites().subscribe((r) => (result = r));

    const req = httpMock.expectOne(`${environment.apiUrl}/sites`);
    expect(req.request.method).toBe('GET');

    req.flush([
      {
        site_id: 'SITE001',
        site_name: 'Site 1',
        site_type: 'industriel',
        location: 'Nantes',
        capacity_kw: 500,
        status: 'actif',
      },
    ]);

    expect((result as { site_id: string }[])[0].site_id).toBe('SITE001');
  });

  it('appelle le bon endpoint et retourne un site', () => {
    let result: unknown;
    service.getSite('SITE001').subscribe((r) => (result = r));

    const req = httpMock.expectOne(`${environment.apiUrl}/sites/SITE001`);
    expect(req.request.method).toBe('GET');

    req.flush({
      site_id: 'SITE001',
      site_name: 'Site 1',
      site_type: 'industriel',
      location: 'Nantes',
      capacity_kw: 500,
      status: 'actif',
    });

    expect((result as { site_id: string }).site_id).toBe('SITE001');
  });
});
