import { TestBed } from '@angular/core/testing';
import { ReactiveFormsModule } from '@angular/forms';
import { ActivatedRoute, convertToParamMap, Router } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { of, throwError } from 'rxjs';
import { vi } from 'vitest';
import { ResetPassword } from './reset-password';
import { AuthService } from '../../../core/services/auth.service';
import { MOTIF_LIEN_RESET_INVALIDE } from '../../../shared/models/auth-redirect-reason';

function configure(token: string | null) {
  return TestBed.configureTestingModule({
    imports: [ResetPassword, ReactiveFormsModule],
    providers: [
      { provide: AuthService, useValue: { resetPassword: vi.fn() } },
      { provide: Router, useValue: { navigate: vi.fn() } },
      {
        provide: ActivatedRoute,
        useValue: { snapshot: { queryParamMap: convertToParamMap(token ? { token } : {}) } },
      },
    ],
  }).compileComponents();
}

describe('ResetPassword', () => {
  it("redirige vers /login avec le motif standard quand le jeton est absent de l'URL", async () => {
    await configure(null);
    const fixture = TestBed.createComponent(ResetPassword);
    const router = TestBed.inject(Router) as unknown as { navigate: ReturnType<typeof vi.fn> };

    fixture.detectChanges();

    expect(fixture.componentInstance.hasToken).toBe(false);
    expect(router.navigate).toHaveBeenCalledWith(['/login'], {
      queryParams: { motif: MOTIF_LIEN_RESET_INVALIDE },
    });
  });

  it('ne soumet pas si le mot de passe ne respecte pas la politique de complexité', async () => {
    await configure('un-secret-opaque');
    const fixture = TestBed.createComponent(ResetPassword);
    const component = fixture.componentInstance;
    const auth = TestBed.inject(AuthService) as unknown as { resetPassword: ReturnType<typeof vi.fn> };
    component.form.setValue({ new_password: 'trop-simple' });

    component.onSubmit();

    expect(auth.resetPassword).not.toHaveBeenCalled();
  });

  it('redirige vers /dashboard après une réinitialisation réussie', async () => {
    await configure('un-secret-opaque');
    const fixture = TestBed.createComponent(ResetPassword);
    const component = fixture.componentInstance;
    const auth = TestBed.inject(AuthService) as unknown as { resetPassword: ReturnType<typeof vi.fn> };
    const router = TestBed.inject(Router) as unknown as { navigate: ReturnType<typeof vi.fn> };
    component.form.setValue({ new_password: 'Un-nouveau-mot-de-passe1!' });
    auth.resetPassword.mockReturnValue(of({ principal: { role: 'operateur' } }));

    component.onSubmit();

    expect(auth.resetPassword).toHaveBeenCalledWith({
      token: 'un-secret-opaque',
      new_password: 'Un-nouveau-mot-de-passe1!',
    });
    expect(router.navigate).toHaveBeenCalledWith(['/dashboard']);
  });

  it('redirige vers /login avec le motif standard quand le lien est invalide ou expiré', async () => {
    await configure('un-secret-perime');
    const fixture = TestBed.createComponent(ResetPassword);
    const component = fixture.componentInstance;
    const auth = TestBed.inject(AuthService) as unknown as { resetPassword: ReturnType<typeof vi.fn> };
    const router = TestBed.inject(Router) as unknown as { navigate: ReturnType<typeof vi.fn> };
    component.form.setValue({ new_password: 'Un-nouveau-mot-de-passe1!' });
    auth.resetPassword.mockReturnValue(throwError(() => new HttpErrorResponse({ status: 400 })));

    component.onSubmit();

    expect(router.navigate).toHaveBeenCalledWith(['/login'], {
      queryParams: { motif: MOTIF_LIEN_RESET_INVALIDE },
    });
  });

  it('affiche un message générique sur une erreur inattendue (pas 400)', async () => {
    await configure('un-secret-opaque');
    const fixture = TestBed.createComponent(ResetPassword);
    const component = fixture.componentInstance;
    const auth = TestBed.inject(AuthService) as unknown as { resetPassword: ReturnType<typeof vi.fn> };
    component.form.setValue({ new_password: 'Un-nouveau-mot-de-passe1!' });
    auth.resetPassword.mockReturnValue(throwError(() => new HttpErrorResponse({ status: 500 })));

    component.onSubmit();

    expect(component.errorMessage()).toContain('invalide');
  });
});
