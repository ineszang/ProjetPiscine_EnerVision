import { Component, inject, signal } from '@angular/core';
import { ReactiveFormsModule, FormBuilder } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { AuthService } from '../../../core/services/auth.service';
import { passwordValidators, PASSWORD_HINT } from '../../../shared/validators/password.validator';

@Component({
  selector: 'app-reset-password',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './reset-password.html',
  styleUrl: './reset-password.scss',
})
export class ResetPassword {
  private fb = inject(FormBuilder);
  private auth = inject(AuthService);
  private router = inject(Router);
  private route = inject(ActivatedRoute);

  private token = this.route.snapshot.queryParamMap.get('token') ?? '';

  errorMessage = signal<string | null>(null);
  isLoading = signal(false);
  passwordHint = PASSWORD_HINT;
  hasToken = this.token.length > 0;

  form = this.fb.nonNullable.group({
    new_password: ['', passwordValidators],
  });

  onSubmit(): void {
    if (this.form.invalid || !this.hasToken) return;

    this.isLoading.set(true);
    this.errorMessage.set(null);

    this.auth.resetPassword({ token: this.token, new_password: this.form.getRawValue().new_password }).subscribe({
      next: () => {
        this.router.navigate(['/dashboard']);
      },
      error: (error: HttpErrorResponse) => {
        this.isLoading.set(false);
        if (error.status === 400) {
          this.errorMessage.set('Ce lien est invalide, déjà utilisé, ou a expiré. Redemandez-en un.');
          return;
        }
        this.errorMessage.set(`Nouveau mot de passe invalide (${this.passwordHint}).`);
      },
    });
  }
}
