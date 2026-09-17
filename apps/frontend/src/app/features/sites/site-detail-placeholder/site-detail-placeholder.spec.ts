import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { BehaviorSubject } from 'rxjs';
import { SiteDetailPlaceholder } from './site-detail-placeholder';

describe('SiteDetailPlaceholder', () => {
  it("affiche l'identifiant du site depuis la route", () => {
    const paramMap = new BehaviorSubject(convertToParamMap({ siteId: 'SITE001' }));
    TestBed.configureTestingModule({
      imports: [SiteDetailPlaceholder],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: { paramMap } },
      ],
    });

    const fixture = TestBed.createComponent(SiteDetailPlaceholder);
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('SITE001');
  });

  it('met à jour l\'affichage quand le paramètre change sans recréer le composant', () => {
    const paramMap = new BehaviorSubject(convertToParamMap({ siteId: 'SITE001' }));
    TestBed.configureTestingModule({
      imports: [SiteDetailPlaceholder],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: { paramMap } },
      ],
    });

    const fixture = TestBed.createComponent(SiteDetailPlaceholder);
    fixture.detectChanges();

    paramMap.next(convertToParamMap({ siteId: 'SITE002' }));
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('SITE002');
    expect(fixture.nativeElement.textContent).not.toContain('SITE001');
  });
});
