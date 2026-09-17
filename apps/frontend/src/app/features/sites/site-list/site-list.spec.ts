import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { vi } from 'vitest';
import { of, throwError } from 'rxjs';
import { SiteList } from './site-list';
import { SitesService } from '../../../core/services/sites.service';

describe('SiteList', () => {
  it('charge et affiche les sites au démarrage', () => {
    const sitesMock = {
      getSites: vi.fn().mockReturnValue(
        of([
          {
            site_id: 'SITE001',
            site_name: 'Site 1',
            site_type: 'industriel',
            location: 'Nantes',
            capacity_kw: 500,
            status: 'actif',
          },
        ]),
      ),
    };

    TestBed.configureTestingModule({
      imports: [SiteList],
      providers: [{ provide: SitesService, useValue: sitesMock }, provideRouter([])],
    });

    const fixture = TestBed.createComponent(SiteList);
    fixture.detectChanges();

    expect(sitesMock.getSites).toHaveBeenCalled();
    expect(fixture.componentInstance.sites().length).toBe(1);
    expect(fixture.componentInstance.error()).toBeNull();
  });

  it("signale l'indisponibilité quand le chargement échoue", () => {
    const sitesMock = { getSites: vi.fn().mockReturnValue(throwError(() => new Error('nope'))) };

    TestBed.configureTestingModule({
      imports: [SiteList],
      providers: [{ provide: SitesService, useValue: sitesMock }, provideRouter([])],
    });

    const fixture = TestBed.createComponent(SiteList);
    fixture.detectChanges();

    expect(fixture.componentInstance.error()).not.toBeNull();
    expect(fixture.componentInstance.sites().length).toBe(0);
  });

  it('affiche un tiret pour les champs nullables', () => {
    const sitesMock = {
      getSites: vi.fn().mockReturnValue(
        of([
          {
            site_id: 'SITE002',
            site_name: 'Site 2',
            site_type: 'bureau',
            location: null,
            capacity_kw: null,
            status: null,
          },
        ]),
      ),
    };

    TestBed.configureTestingModule({
      imports: [SiteList],
      providers: [{ provide: SitesService, useValue: sitesMock }, provideRouter([])],
    });

    const fixture = TestBed.createComponent(SiteList);
    fixture.detectChanges();

    const cells = fixture.nativeElement.querySelectorAll('td');
    expect(cells[2].textContent.trim()).toBe('-');
    expect(cells[3].textContent.trim()).toBe('-');
  });
});
