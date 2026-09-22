import { TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { vi } from 'vitest';
import { BehaviorSubject, of, throwError } from 'rxjs';
import { RecommendationsView, parseAlertId } from './recommendations';
import { RecommendationList } from '../../shared/components/recommendation-list/recommendation-list';
import { SitesService } from '../../core/services/sites.service';
import { AlertsService } from '../../core/services/alerts.service';
import { RecommendationsService } from '../../core/services/recommendations.service';
import { AuthService } from '../../core/services/auth.service';

const SITES = [
  {
    site_id: 'SITE001',
    site_name: 'Usine Nantes',
    site_type: 'industriel',
    location: 'Nantes',
    capacity_kw: 500,
    status: 'actif',
  },
];

const BILAN = { alerts_examined: 2, recommendations_created: 3, already_present: 1 };

function setup(options: { query?: Record<string, string>; role?: string } = {}) {
  const query = options.query ?? {};
  const queryParamMap = new BehaviorSubject(convertToParamMap(query));
  const generate = vi.fn().mockReturnValue(of(BILAN));
  const getRecommendations = vi.fn().mockReturnValue(of([]));
  const getAlerts = vi.fn().mockReturnValue(of([]));
  TestBed.configureTestingModule({
    imports: [RecommendationsView],
    providers: [
      provideRouter([]),
      {
        provide: ActivatedRoute,
        useValue: { queryParamMap, snapshot: { queryParamMap: convertToParamMap(query) } },
      },
      { provide: SitesService, useValue: { getSites: vi.fn().mockReturnValue(of(SITES)) } },
      { provide: AlertsService, useValue: { getAlerts } },
      { provide: RecommendationsService, useValue: { getRecommendations, generate } },
      {
        provide: AuthService,
        useValue: { principal: vi.fn().mockReturnValue({ role: options.role ?? 'lecteur' }) },
      },
    ],
  });
  const fixture = TestBed.createComponent(RecommendationsView);
  fixture.detectChanges();
  fixture.detectChanges();
  return { fixture, queryParamMap, generate, getRecommendations, getAlerts };
}

function listeEnfant(fixture: ReturnType<typeof setup>['fixture']): RecommendationList {
  return fixture.debugElement.query(By.directive(RecommendationList)).componentInstance;
}

describe('parseAlertId', () => {
  it("n'accepte qu'un entier strictement positif", () => {
    expect(parseAlertId('12')).toBe(12);
    expect(parseAlertId('0')).toBeNull();
    expect(parseAlertId('-3')).toBeNull();
    expect(parseAlertId('abc')).toBeNull();
    expect(parseAlertId('12abc')).toBeNull();
    expect(parseAlertId(null)).toBeNull();
  });
});

describe('RecommendationsView', () => {
  it("cible l'alerte donnée par ?alert= et la transmet à la liste", () => {
    const { fixture } = setup({ query: { alert: '12' } });

    expect(fixture.componentInstance.alertId()).toBe(12);
    expect(listeEnfant(fixture).alertId()).toBe(12);
    expect(fixture.nativeElement.textContent).toContain('Alerte n° 12');
    expect(fixture.nativeElement.querySelector('a[href="/recommendations"]')).not.toBeNull();
  });

  it('ignore un paramètre alert invalide', () => {
    const { fixture } = setup({ query: { alert: 'abc' } });

    expect(fixture.componentInstance.alertId()).toBeNull();
    expect(fixture.nativeElement.textContent).not.toContain('Alerte n°');
  });

  it('applique le site donné par ?site= au filtre et à la liste', () => {
    const { fixture, getAlerts } = setup({ query: { site: 'SITE001' } });

    expect(getAlerts).toHaveBeenCalledWith({ site_id: 'SITE001' });
    const option = fixture.nativeElement.querySelector(
      'option[value="SITE001"]',
    ) as HTMLOptionElement;
    expect(option.selected).toBe(true);
  });

  it('relance la liste sur le site choisi dans le filtre', () => {
    const { fixture, getAlerts } = setup();
    const select = fixture.nativeElement.querySelector(
      '[data-testid="site-filter"]',
    ) as HTMLSelectElement;

    select.value = 'SITE001';
    select.dispatchEvent(new Event('change'));
    fixture.detectChanges();
    fixture.detectChanges();

    expect(getAlerts).toHaveBeenLastCalledWith({ site_id: 'SITE001' });
    expect(listeEnfant(fixture).siteId()).toBe('SITE001');
  });

  it('cache le bouton de génération aux lecteurs', () => {
    const { fixture } = setup({ role: 'lecteur' });

    expect(fixture.nativeElement.querySelector('[data-testid="generate"]')).toBeNull();
  });

  it('permet à un admin de générer pour le site filtré, affiche le bilan et recharge la liste', () => {
    const { fixture, generate, getRecommendations } = setup({
      role: 'admin',
      query: { site: 'SITE001' },
    });

    fixture.nativeElement.querySelector('[data-testid="generate"]').click();
    fixture.detectChanges();
    fixture.detectChanges();

    expect(generate).toHaveBeenCalledWith('SITE001');
    expect(fixture.nativeElement.textContent).toContain(
      '3 recommandations créées, 1 déjà présente, 2 alertes examinées.',
    );
    expect(getRecommendations).toHaveBeenCalledTimes(2);
    expect(fixture.componentInstance.generating()).toBe(false);
  });

  it('génère pour tout le parc quand aucun site n’est filtré', () => {
    const { fixture, generate } = setup({ role: 'admin' });

    fixture.componentInstance.onGenerate();

    expect(generate).toHaveBeenCalledWith(undefined);
  });

  it("signale l'échec de la génération sans casser la page", () => {
    const { fixture, generate } = setup({ role: 'admin' });
    generate.mockReturnValue(throwError(() => new Error('403')));

    fixture.componentInstance.onGenerate();
    fixture.detectChanges();

    expect(fixture.componentInstance.generationError()).not.toBeNull();
    expect(fixture.nativeElement.textContent).toContain(
      'La génération des recommandations a échoué',
    );
    expect(fixture.componentInstance.generating()).toBe(false);
  });

  it('accorde le bilan au singulier', () => {
    const { fixture } = setup();

    expect(
      fixture.componentInstance.bilan({
        alerts_examined: 1,
        recommendations_created: 1,
        already_present: 0,
      }),
    ).toBe('1 recommandation créée, 0 déjà présente, 1 alerte examinée');
  });
});
