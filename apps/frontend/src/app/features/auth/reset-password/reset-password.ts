import { Component, OnInit, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ReactiveFormsModule, FormBuilder } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { AuthService } from '../../../core/services/auth.service';
import { passwordValidators, PASSWORD_HINT } from '../../../shared/validators/password.validator';
import { PasswordRequirementsChecklist } from '../../../shared/components/password-requirements/password-requirements';
import { MOTIF_LIEN_RESET_INVALIDE } from '../../../shared/models/auth-redirect-reason';

@Component({
  selector: 'app-reset-password',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink, PasswordRequirementsChecklist],
  templateUrl: './reset-password.html',
  styleUrl: './reset-password.scss',
})
export class ResetPassword implements OnInit {
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

  password = toSignal(this.form.controls.new_password.valueChanges, { initialValue: '' });
  isCheckingToken = signal(this.hasToken);

  ngOnInit(): void {
    if (!this.hasToken) {
      this.redirigeVersLoginLienInvalide();
      return;
    }

    this.auth.validateResetToken(this.token).subscribe({
      next: ({ valid }) => {
        this.isCheckingToken.set(false);
        if (!valid) {
          this.redirigeVersLoginLienInvalide();
        }
      },
      error: () => this.isCheckingToken.set(false),
    });
  }

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
          this.redirigeVersLoginLienInvalide();
          return;
        }
        this.errorMessage.set(`Nouveau mot de passe invalide (${this.passwordHint}).`);
      },
    });
  }

  private redirigeVersLoginLienInvalide(): void {
    this.router.navigate(['/login'], { queryParams: { motif: MOTIF_LIEN_RESET_INVALIDE } });
  }
}
