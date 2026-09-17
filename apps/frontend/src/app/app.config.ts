import {ApplicationConfig, inject, provideAppInitializer, provideBrowserGlobalErrorListeners} from '@angular/core';
import { provideRouter } from '@angular/router';
import { routes } from './app.routes';
import { mockApiInterceptor } from './core/interceptors/mock-api-interceptor';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import {catchError, firstValueFrom, of} from 'rxjs';
import {AuthService} from './core/services/auth.service';
import {authInterceptor} from './core/interceptors/auth-interceptor';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    provideHttpClient(withInterceptors([authInterceptor, mockApiInterceptor])),
    provideAppInitializer(() => {
      const auth = inject(AuthService);
      // Un 401 ici est normal : ça veut juste dire qu'il n'y a pas de session.
      return firstValueFrom(auth.refreshShared().pipe(catchError(() => of(null))));
    }),
  ],
};
