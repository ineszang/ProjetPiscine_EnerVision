import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, catchError, switchMap, throwError } from 'rxjs';
import { AuthService } from '../services/auth.service';
import { TokenResponse } from '../../shared/models/auth.model';

function parseAuthError(response: HttpErrorResponse): string | null {
  const header = response.headers?.get('WWW-Authenticate') ?? '';
  const match = header.match(/error="([^"]+)"/);
  return match ? match[1] : null;
}

const ROUTES_INVITEES = ['/login', '/forgot-password', '/reset-password'];

// Piège : le rafraîchissement de session lancé au démarrage de l'app (provideAppInitializer)
// échoue silencieusement sans cookie valide. `window.location.pathname` (pas `router.url`,
// pas encore fiable à ce stade) évite qu'un 401 de fond écrase la navigation vers le lien de
// reset reçu par email.
function surRouteInvitee(): boolean {
  return ROUTES_INVITEES.some((chemin) => window.location.pathname.startsWith(chemin));
}

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const router = inject(Router);

  const isAuthRoute = req.url.includes('/auth/');
  let request = isAuthRoute ? req.clone({ withCredentials: true }) : req;

  const token = auth.getAccessToken();
  if (token && !req.url.endsWith('/auth/login')) {
    request = request.clone({ setHeaders: { Authorization: `Bearer ${token}` } });
  }

  return next(request).pipe(
    catchError((error: unknown) => {
      if (!(error instanceof HttpErrorResponse)) {
        return throwError(() => error);
      }

      if (error.status === 403) {
        const detail = (error.error as { detail?: string })?.detail;
        if (detail === 'password_change_required') {
          router.navigate(['/change-password']);
        }
        return throwError(() => error);
      }

      if (error.status !== 401 || req.url.endsWith('/auth/login')) {
        return throwError(() => error);
      }

      if (req.url.endsWith('/auth/refresh')) {
        auth.clearSession();
        if (!surRouteInvitee()) {
          router.navigate(['/login']);
        }
        return throwError(() => error);
      }

      const kind = parseAuthError(error);

      if (kind === 'invalid_token') {
        auth.clearSession();
        if (!surRouteInvitee()) {
          router.navigate(['/login']);
        }
        return throwError(() => error);
      }

      if (kind === 'expired' || kind === 'token_stale') {
        return (auth.refreshShared() as Observable<TokenResponse>).pipe(
          switchMap(() => {
            const retried = request.clone({
              setHeaders: { Authorization: `Bearer ${auth.getAccessToken()}` },
            });
            return next(retried);
          }),
          catchError((refreshError) => {
            auth.clearSession();
            if (!surRouteInvitee()) {
              router.navigate(['/login']);
            }
            return throwError(() => refreshError);
          })
        );
      }

      return throwError(() => error);
    })
  );
};
