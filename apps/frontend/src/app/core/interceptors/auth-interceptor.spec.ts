import { TestBed } from '@angular/core/testing';
import {
  HttpClient,
  HttpHandlerFn,
  HttpHeaders,
  HttpRequest,
  provideHttpClient,
  withInterceptors
} from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { Router } from '@angular/router';
import { of, throwError } from 'rxjs';
import { vi } from 'vitest';
import { authInterceptor } from './auth-interceptor';
import { AuthService } from '../services/auth.service';

describe('authInterceptor', () => {
  let http: HttpClient;
  let httpMock: HttpTestingController;
  let authMock: { getAccessToken: ReturnType<typeof vi.fn>; clearSession: ReturnType<typeof vi.fn>; refreshShared: ReturnType<typeof vi.fn> };
  let routerMock: { navigate: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    authMock = {
      getAccessToken: vi.fn().mockReturnValue('fake-token'),
      clearSession: vi.fn(),
      refreshShared: vi.fn(),
    };
    routerMock = { navigate: vi.fn() };

    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
        { provide: AuthService, useValue: authMock },
        { provide: Router, useValue: routerMock },
      ],
    });

    http = TestBed.inject(HttpClient);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
    vi.restoreAllMocks();
  });

  it('ajoute le header Authorization quand un token est disponible', () => {
    http.get('/api/v1/stats/summary').subscribe();
    const req = httpMock.expectOne('/api/v1/stats/summary');
    expect(req.request.headers.get('Authorization')).toBe('Bearer fake-token');
    req.flush({});
  });

  it("n'ajoute pas le header Authorization sur /auth/login", () => {
    http.post('/api/v1/auth/login', {}).subscribe();
    const req = httpMock.expectOne('/api/v1/auth/login');
    expect(req.request.headers.has('Authorization')).toBe(false);
    req.flush({});
  });

  it('ajoute withCredentials sur les routes /auth/*', () => {
    http.post('/api/v1/auth/login', {}).subscribe();
    const req = httpMock.expectOne('/api/v1/auth/login');
    expect(req.request.withCredentials).toBe(true);
    req.flush({});
  });

  it('redirige vers /change-password sur un 403 avec ce detail précis', () => {
    http.get('/api/v1/dashboard').subscribe({ error: () => {} });
    const req = httpMock.expectOne('/api/v1/dashboard');
    req.flush({ detail: 'password_change_required' }, { status: 403, statusText: 'Forbidden' });
    expect(routerMock.navigate).toHaveBeenCalledWith(['/change-password']);
  });

  it('ne redirige pas sur un 403 avec un autre detail', () => {
    http.get('/api/v1/dashboard').subscribe({ error: () => {} });
    const req = httpMock.expectOne('/api/v1/dashboard');
    req.flush({ detail: 'Droits insuffisants' }, { status: 403, statusText: 'Forbidden' });
    expect(routerMock.navigate).not.toHaveBeenCalled();
  });

  it('déconnecte et redirige vers /login sur un 401 avec error="invalid_token"', () => {
    http.get('/api/v1/dashboard').subscribe({ error: () => {} });
    const req = httpMock.expectOne('/api/v1/dashboard');
    req.flush(
      {},
      { status: 401, statusText: 'Unauthorized', headers: new HttpHeaders({ 'WWW-Authenticate': 'Bearer error="invalid_token"' }) }
    );
    expect(authMock.clearSession).toHaveBeenCalled();
    expect(routerMock.navigate).toHaveBeenCalledWith(['/login']);
  });

  it('déconnecte directement sur un 401 provenant de /auth/refresh, sans tenter de rafraîchir', () => {
    http.post('/api/v1/auth/refresh', {}).subscribe({ error: () => {} });
    const req = httpMock.expectOne('/api/v1/auth/refresh');
    req.flush({}, { status: 401, statusText: 'Unauthorized' });
    expect(authMock.clearSession).toHaveBeenCalled();
    expect(routerMock.navigate).toHaveBeenCalledWith(['/login']);
  });

  it("ne redirige pas vers /login sur un 401 de /auth/refresh si on est déjà sur /reset-password", () => {
    vi.spyOn(window, 'location', 'get').mockReturnValue({
      pathname: '/reset-password',
    } as Location);

    http.post('/api/v1/auth/refresh', {}).subscribe({ error: () => {} });
    const req = httpMock.expectOne('/api/v1/auth/refresh');
    req.flush({}, { status: 401, statusText: 'Unauthorized' });

    expect(authMock.clearSession).toHaveBeenCalled();
    expect(routerMock.navigate).not.toHaveBeenCalled();
  });

  it('rafraîchit puis rejoue la requête sur un 401 avec error="expired"', () => {
    authMock.refreshShared.mockReturnValue(of({ access_token: 'new-token' }));
    authMock.getAccessToken.mockReturnValueOnce('old-token').mockReturnValue('new-token');

    let result: unknown;
    http.get('/api/v1/dashboard').subscribe((r) => (result = r));

    const firstReq = httpMock.expectOne('/api/v1/dashboard');
    firstReq.flush({}, { status: 401, statusText: 'Unauthorized', headers: new HttpHeaders({ 'WWW-Authenticate': 'Bearer error="expired"' }) });

    const retriedReq = httpMock.expectOne('/api/v1/dashboard');
    expect(retriedReq.request.headers.get('Authorization')).toBe('Bearer new-token');
    retriedReq.flush({ ok: true });

    expect(result).toEqual({ ok: true });
  });

  it('déconnecte si le rafraîchissement échoue après un 401 "expired"', () => {
    authMock.refreshShared.mockReturnValue(throwError(() => new Error('refresh failed')));

    http.get('/api/v1/dashboard').subscribe({ error: () => {} });
    const req = httpMock.expectOne('/api/v1/dashboard');
    req.flush({}, { status: 401, statusText: 'Unauthorized', headers: new HttpHeaders({ 'WWW-Authenticate': 'Bearer error="expired"' }) });

    expect(authMock.clearSession).toHaveBeenCalled();
    expect(routerMock.navigate).toHaveBeenCalledWith(['/login']);
  });

  it("propage l'erreur telle quelle si ce n'est pas une HttpErrorResponse", () => {
  const req = new HttpRequest('GET', '/api/v1/dashboard');
  const boom = new Error('erreur inattendue, pas HTTP');
  const next: HttpHandlerFn = () => throwError(() => boom);

  let captured: unknown;
  TestBed.runInInjectionContext(() => {
    authInterceptor(req, next).subscribe({ error: (e) => (captured = e) });
  });

  expect(captured).toBe(boom);
});

it('propage un 401 sur /auth/login sans tenter de rafraîchir ni déconnecter', () => {
  http.post('/api/v1/auth/login', {}).subscribe({ error: () => {} });
  const req = httpMock.expectOne('/api/v1/auth/login');
  req.flush({}, { status: 401, statusText: 'Unauthorized' });

  expect(authMock.refreshShared).not.toHaveBeenCalled();
  expect(authMock.clearSession).not.toHaveBeenCalled();
});

it("propage un 401 dont le WWW-Authenticate ne correspond à aucun cas connu", () => {
  http.get('/api/v1/dashboard').subscribe({ error: () => {} });
  const req = httpMock.expectOne('/api/v1/dashboard');
  req.flush(
    {},
    { status: 401, statusText: 'Unauthorized', headers: new HttpHeaders({ 'WWW-Authenticate': 'Bearer error="unknown_case"' }) }
  );

  expect(authMock.refreshShared).not.toHaveBeenCalled();
  expect(authMock.clearSession).not.toHaveBeenCalled();
});
});
