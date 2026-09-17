import { TestBed } from '@angular/core/testing';
import { ReactiveFormsModule } from '@angular/forms';
import { ActivatedRoute, convertToParamMap, Router } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { of, throwError } from 'rxjs';
import { vi } from 'vitest';
import { ResetPassword } from './reset-password';
import { AuthService } from '../../../core/services/auth.service';

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
  it("signale un lien incomplet quand le jeton est absent de l'URL", async () => {
    await configure(null);
    const fixture = TestBed.createComponent(ResetPassword);

    expect(fixture.componentInstance.hasToken).toBe(false);
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

  it('affiche un message dédié quand le lien est invalide ou expiré', async () => {
    await configure('un-secret-perime');
    const fixture = TestBed.createComponent(ResetPassword);
    const component = fixture.componentInstance;
    const auth = TestBed.inject(AuthService) as unknown as { resetPassword: ReturnType<typeof vi.fn> };
    component.form.setValue({ new_password: 'Un-nouveau-mot-de-passe1!' });
    auth.resetPassword.mockReturnValue(throwError(() => new HttpErrorResponse({ status: 400 })));

    component.onSubmit();

    expect(component.errorMessage()).toContain('invalide');
  });
});
