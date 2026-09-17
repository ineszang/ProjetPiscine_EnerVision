import { Component, inject, signal } from '@angular/core';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { AuthService } from '../../../core/services/auth.service';
import { Button } from '../../../shared/components/ui/button/button';
import { Card } from '../../../shared/components/ui/card/card';
import { Alert } from '../../../shared/components/ui/alert/alert';
import { Brand } from '../../../shared/components/ui/brand/brand';
import { MESSAGE_LIEN_RESET_INVALIDE, MOTIF_LIEN_RESET_INVALIDE } from '../../../shared/models/auth-redirect-reason';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink, Button, Card, Alert, Brand],
  templateUrl: './login.html',
  styleUrl: './login.scss',
})
export class Login {
  private fb = inject(FormBuilder);
  private auth = inject(AuthService);
  private router = inject(Router);
  private route = inject(ActivatedRoute);

  errorMessage = signal<string | null>(
    this.route.snapshot.queryParamMap.get('motif') === MOTIF_LIEN_RESET_INVALIDE
      ? MESSAGE_LIEN_RESET_INVALIDE
      : null,
  );
  retryAfterSeconds = signal<number | null>(null);
  isLoading = signal(false);

  form = this.fb.nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', Validators.required],
  });

  onSubmit(): void {
    if (this.form.invalid) return;

    this.isLoading.set(true);
    this.errorMessage.set(null);
    this.retryAfterSeconds.set(null);

    this.auth.login(this.form.getRawValue()).subscribe({
      next: (response) => {
        if (response.principal.must_change_password) {
          this.router.navigate(['/change-password']);
          return;
        }
        this.router.navigate(['/dashboard']);
      },
      error: (error: HttpErrorResponse) => {
        this.isLoading.set(false);
        if (error.status === 429) {
          const retryAfter = error.headers.get('Retry-After');
          this.retryAfterSeconds.set(retryAfter ? Number(retryAfter) : null);
          this.errorMessage.set('Trop de tentatives, réessayez plus tard.');
          return;
        }
        this.errorMessage.set('Email ou mot de passe incorrect.');
      },
    });
  }
}
