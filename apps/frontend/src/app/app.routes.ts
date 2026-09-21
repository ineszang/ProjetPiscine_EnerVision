import { Routes } from '@angular/router';
import {authGuard} from './core/guards/auth-guard';

export const routes: Routes = [
  { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
  { path: 'login', loadComponent: () => import('./features/auth/login/login').then(m => m.Login) },
  { path: 'change-password', loadComponent: () => import('./features/auth/change-password/change-password').then(m => m.ChangePassword) },
  { path: 'forgot-password', loadComponent: () => import('./features/auth/forgot-password/forgot-password').then(m => m.ForgotPassword) },
  { path: 'reset-password', loadComponent: () => import('./features/auth/reset-password/reset-password').then(m => m.ResetPassword) },
  {
    path: 'dashboard',
    canActivate: [authGuard],
    loadComponent: () => import('./features/dashboard/dashboard').then(m => m.Dashboard),
  },
  {
    path: 'sites',
    canActivate: [authGuard],
    loadComponent: () => import('./features/sites/site-list/site-list').then(m => m.SiteList),
  },
  {
    path: 'sites/:siteId',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/sites/site-detail/site-detail').then((m) => m.SiteDetail),
  },
];
