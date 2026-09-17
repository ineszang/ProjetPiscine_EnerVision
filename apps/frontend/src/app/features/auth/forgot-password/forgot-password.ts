import { Component, inject, signal } from '@angular/core';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { AuthService } from '../../../core/services/auth.service';

@Component({
  selector: 'app-forgot-password',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './forgot-password.html',
  styleUrl: './forgot-password.scss',
})
export class ForgotPassword {
  private fb = inject(FormBuilder);
  private auth = inject(AuthService);

  errorMessage = signal<string | null>(null);
  retryAfterSeconds = signal<number | null>(null);
  submitted = signal(false);
  isLoading = signal(false);

  form = this.fb.nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
  });

  onSubmit(): void {
    if (this.form.invalid) return;

    this.isLoading.set(true);
    this.errorMessage.set(null);
    this.retryAfterSeconds.set(null);

    this.auth.forgotPassword(this.form.getRawValue()).subscribe({
      // Le message affiché ne dépend jamais du fait que le compte existe ou non : la réponse
      // du serveur est déjà générique, l'écran doit l'être aussi.
      next: () => {
        this.isLoading.set(false);
        this.submitted.set(true);
      },
      error: (error: HttpErrorResponse) => {
        this.isLoading.set(false);
        if (error.status === 429) {
          const retryAfter = error.headers.get('Retry-After');
          this.retryAfterSeconds.set(retryAfter ? Number(retryAfter) : null);
          this.errorMessage.set('Trop de demandes, réessayez plus tard.');
          return;
        }
        this.submitted.set(true);
      },
    });
  }
}
