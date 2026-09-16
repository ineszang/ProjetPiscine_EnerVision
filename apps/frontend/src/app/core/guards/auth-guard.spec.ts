import { TestBed } from '@angular/core/testing';
import { Router, ActivatedRouteSnapshot } from '@angular/router';
import { vi } from 'vitest';
import { authGuard } from './auth-guard';
import { AuthService } from '../services/auth.service';

describe('authGuard', () => {
  let authMock: { isAuthenticated: ReturnType<typeof vi.fn>; principal: ReturnType<typeof vi.fn> };
  let routerMock: { navigate: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    authMock = { isAuthenticated: vi.fn(), principal: vi.fn() };
    routerMock = { navigate: vi.fn() };

    TestBed.configureTestingModule({
      providers: [
        { provide: AuthService, useValue: authMock },
        { provide: Router, useValue: routerMock },
      ],
    });
  });

  it('redirige vers /login si non authentifié', () => {
    authMock.isAuthenticated.mockReturnValue(false);

    const result = TestBed.runInInjectionContext(() =>
      authGuard({ data: {} } as ActivatedRouteSnapshot, {} as any)
    );

    expect(result).toBe(false);
    expect(routerMock.navigate).toHaveBeenCalledWith(['/login']);
  });

  it('redirige vers /login si le rôle ne correspond pas', () => {
    authMock.isAuthenticated.mockReturnValue(true);
    authMock.principal.mockReturnValue({ role: 'lecteur' });

    const result = TestBed.runInInjectionContext(() =>
      authGuard({ data: { role: 'admin' } } as unknown as ActivatedRouteSnapshot, {} as any)
    );

    expect(result).toBe(false);
    expect(routerMock.navigate).toHaveBeenCalledWith(['/login']);
  });

  it('autorise si authentifié et rôle correspondant', () => {
    authMock.isAuthenticated.mockReturnValue(true);
    authMock.principal.mockReturnValue({ role: 'admin' });

    const result = TestBed.runInInjectionContext(() =>
      authGuard({ data: { role: 'admin' } } as unknown as ActivatedRouteSnapshot, {} as any)
    );

    expect(result).toBe(true);
  });

  it('autorise si authentifié et aucun rôle requis', () => {
    authMock.isAuthenticated.mockReturnValue(true);
    authMock.principal.mockReturnValue({ role: 'lecteur' });

    const result = TestBed.runInInjectionContext(() =>
      authGuard({ data: {} } as ActivatedRouteSnapshot, {} as any)
    );

    expect(result).toBe(true);
  });
});
