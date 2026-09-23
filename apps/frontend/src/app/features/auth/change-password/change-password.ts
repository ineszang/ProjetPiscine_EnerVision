import { Component, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { AuthService } from '../../../core/services/auth.service';
import { Button } from '../../../shared/components/ui/button/button';
import { Card } from '../../../shared/components/ui/card/card';
import { Alert } from '../../../shared/components/ui/alert/alert';
import { Brand } from '../../../shared/components/ui/brand/brand';
import { PasswordRequirementsChecklist } from '../../../shared/components/password-requirements/password-requirements';
import { passwordValidators, PASSWORD_HINT } from '../../../shared/validators/password.validator';

@Component({
  selector: 'app-change-password',
  standalone: true,
  imports: [ReactiveFormsModule, Button, Card, Alert, Brand, PasswordRequirementsChecklist],
  templateUrl: './change-password.html',
  styleUrl: './change-password.scss',
})
export class ChangePassword {
  private fb = inject(FormBuilder);
  private auth = inject(AuthService);
  private router = inject(Router);

  private provisionalPassword = this.auth.takeProvisionalPassword();

  errorMessage = signal<string | null>(null);
  isLoading = signal(false);
  asksCurrentPassword = signal(this.provisionalPassword === null);
  email = this.auth.principal()?.email ?? '';

  form = this.fb.nonNullable.group({
    current_password: [this.provisionalPassword ?? '', Validators.required],
    new_password: ['', passwordValidators],
  });

  newPassword = toSignal(this.form.controls.new_password.valueChanges, { initialValue: '' });

  onSubmit(): void {
    if (this.form.invalid) return;
    this.isLoading.set(true);
    this.errorMessage.set(null);

    this.auth.changePassword(this.form.getRawValue()).subscribe({
      next: () => {
        this.router.navigate(['/dashboard']);
      },
      error: (error: HttpErrorResponse) => {
        this.isLoading.set(false);
        this.errorMessage.set(this.explique(error));
        if (error.status === 401) {
          this.form.controls.current_password.reset('');
          this.asksCurrentPassword.set(true);
        }
      },
    });
  }

  private explique(error: HttpErrorResponse): string {
    if (error.status === 401) {
      return 'Mot de passe actuel incorrect : saisissez le mot de passe provisoire qui vous a été transmis.';
    }
    if (error.status === 422) {
      return `Nouveau mot de passe refusé (${PASSWORD_HINT}).`;
    }
    return 'Le changement de mot de passe a échoué, réessayez dans un instant.';
  }
}
