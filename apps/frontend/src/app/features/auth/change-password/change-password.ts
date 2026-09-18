import { Component, inject, signal } from '@angular/core';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../../../core/services/auth.service';
import { Button } from '../../../shared/components/ui/button/button';
import { Card } from '../../../shared/components/ui/card/card';
import { Alert } from '../../../shared/components/ui/alert/alert';
import { Brand } from '../../../shared/components/ui/brand/brand';
import { passwordValidators, PASSWORD_HINT } from '../../../shared/validators/password.validator';

@Component({
  selector: 'app-change-password',
  standalone: true,
  imports: [ReactiveFormsModule, Button, Card, Alert, Brand],
  templateUrl: './change-password.html',
  styleUrl: './change-password.scss',
})
export class ChangePassword {
  private fb = inject(FormBuilder);
  private auth = inject(AuthService);
  private router = inject(Router);

  errorMessage = signal<string | null>(null);
  isLoading = signal(false);
  passwordHint = PASSWORD_HINT;

  form = this.fb.nonNullable.group({
    current_password: ['', Validators.required],
    new_password: ['', passwordValidators],
  });

  onSubmit(): void {
    if (this.form.invalid) return;
    this.isLoading.set(true);
    this.errorMessage.set(null);

    this.auth.changePassword(this.form.getRawValue()).subscribe({
      next: (response) => {
        this.router.navigate(['/dashboard']);
      },
      error: () => {
        this.isLoading.set(false);
        this.errorMessage.set(
          `Mot de passe actuel incorrect, ou nouveau mot de passe invalide (${this.passwordHint}).`,
        );
      },
    });
  }
}
