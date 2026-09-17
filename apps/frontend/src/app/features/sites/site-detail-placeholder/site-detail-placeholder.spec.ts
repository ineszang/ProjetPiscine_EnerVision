import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap } from '@angular/router';
import { SiteDetailPlaceholder } from './site-detail-placeholder';

describe('SiteDetailPlaceholder', () => {
  it("affiche l'identifiant du site depuis la route", () => {
    TestBed.configureTestingModule({
      imports: [SiteDetailPlaceholder],
      providers: [
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { paramMap: convertToParamMap({ siteId: 'SITE001' }) } },
        },
      ],
    });

    const fixture = TestBed.createComponent(SiteDetailPlaceholder);
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('SITE001');
  });
});
