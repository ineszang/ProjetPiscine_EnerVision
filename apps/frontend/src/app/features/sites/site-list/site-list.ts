import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { catchError, EMPTY, Observable } from 'rxjs';
import { SitesService } from '../../../core/services/sites.service';
import { Site } from '../../../shared/models/site.model';
import { Card } from '../../../shared/components/ui/card/card';
import { Alert } from '../../../shared/components/ui/alert/alert';
import { Badge, BadgeTone } from '../../../shared/components/ui/badge/badge';
import { Brand } from '../../../shared/components/ui/brand/brand';

const UNAVAILABLE_MESSAGE = 'Liste des sites indisponible, réessayez plus tard.';

const TON_PAR_STATUT: Record<string, BadgeTone> = {
  actif: 'success',
  maintenance: 'warning',
  hors_service: 'danger',
};

@Component({
  selector: 'app-site-list',
  standalone: true,
  imports: [RouterLink, Card, Alert, Badge, Brand],
  templateUrl: './site-list.html',
  styleUrl: './site-list.scss',
})
export class SiteList implements OnInit {
  private sitesService = inject(SitesService);

  sites = signal<Site[]>([]);
  error = signal<string | null>(null);

  ngOnInit(): void {
    this.sitesService
      .getSites()
      .pipe(catchError(() => this.reportUnavailable()))
      .subscribe((sites) => this.sites.set(sites));
  }

  badgeToneForStatus(status: string | null): BadgeTone {
    return status ? (TON_PAR_STATUT[status] ?? 'neutral') : 'neutral';
  }

  private reportUnavailable(): Observable<never> {
    this.error.set(UNAVAILABLE_MESSAGE);
    return EMPTY;
  }
}
