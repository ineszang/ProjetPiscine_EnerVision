import { Component, computed, inject, signal, viewChild } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { catchError, map, of } from 'rxjs';
import { SitesService } from '../../core/services/sites.service';
import { RecommendationsService } from '../../core/services/recommendations.service';
import { AuthService } from '../../core/services/auth.service';
import { Site } from '../../shared/models/site.model';
import { RecommendationGenerationReport } from '../../shared/models/recommendation.model';
import { RecommendationList } from '../../shared/components/recommendation-list/recommendation-list';
import { Alert as EvAlert } from '../../shared/components/ui/alert/alert';
import { Brand } from '../../shared/components/ui/brand/brand';
import { Button } from '../../shared/components/ui/button/button';

const GENERATION_FAILED_MESSAGE =
  'La génération des recommandations a échoué, réessayez plus tard.';

export function parseAlertId(raw: string | null): number | null {
  return raw !== null && /^[1-9]\d*$/.test(raw) ? Number(raw) : null;
}

function pluriel(nombre: number, singulier: string, plurielForme: string): string {
  return `${nombre} ${nombre > 1 ? plurielForme : singulier}`;
}

@Component({
  selector: 'app-recommendations',
  standalone: true,
  imports: [RouterLink, RecommendationList, EvAlert, Brand, Button],
  templateUrl: './recommendations.html',
  styleUrl: './recommendations.scss',
})
export class RecommendationsView {
  private route = inject(ActivatedRoute);
  private sitesService = inject(SitesService);
  private recommendationsService = inject(RecommendationsService);
  private auth = inject(AuthService);

  alertId = toSignal(
    this.route.queryParamMap.pipe(map((params) => parseAlertId(params.get('alert')))),
    { initialValue: null },
  );
  siteFilter = signal<string | null>(this.route.snapshot.queryParamMap.get('site'));
  sites = toSignal(this.sitesService.getSites().pipe(catchError(() => of([] as Site[]))), {
    initialValue: [] as Site[],
  });

  list = viewChild.required(RecommendationList);

  isAdmin = computed(() => this.auth.principal()?.role === 'admin');
  generating = signal(false);
  generationReport = signal<RecommendationGenerationReport | null>(null);
  generationError = signal<string | null>(null);

  onSiteChange(event: Event): void {
    this.siteFilter.set((event.target as HTMLSelectElement).value || null);
  }

  onGenerate(): void {
    if (this.generating()) {
      return;
    }
    this.generating.set(true);
    this.generationError.set(null);
    this.recommendationsService.generate(this.siteFilter() ?? undefined).subscribe({
      next: (report) => {
        this.generating.set(false);
        this.generationReport.set(report);
        this.list().reload();
      },
      error: () => {
        this.generating.set(false);
        this.generationError.set(GENERATION_FAILED_MESSAGE);
      },
    });
  }

  bilan(report: RecommendationGenerationReport): string {
    return [
      pluriel(report.recommendations_created, 'recommandation créée', 'recommandations créées'),
      pluriel(report.already_present, 'déjà présente', 'déjà présentes'),
      pluriel(report.alerts_examined, 'alerte examinée', 'alertes examinées'),
    ].join(', ');
  }
}
