import { TestBed } from '@angular/core/testing';
import { Icon, IconName } from './icon';

const NOMS: IconName[] = ['spike', 'threshold', 'anomaly', 'outage', 'sensor'];

function rendre(name: IconName, label: string | null = null) {
  const fixture = TestBed.createComponent(Icon);
  fixture.componentRef.setInput('name', name);
  fixture.componentRef.setInput('label', label);
  fixture.detectChanges();
  return fixture.nativeElement as HTMLElement;
}

describe('Icon', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [Icon] });
  });

  it('dessine un tracé distinct pour chacun des cinq types', () => {
    const traces = NOMS.map((name) => rendre(name).querySelector('svg')?.innerHTML.trim());

    for (const trace of traces) {
      expect(trace).toBeTruthy();
    }
    expect(new Set(traces).size).toBe(NOMS.length);
  });

  it('reste décoratif sans libellé', () => {
    const svg = rendre('spike').querySelector('svg');

    expect(svg?.getAttribute('aria-hidden')).toBe('true');
    expect(svg?.hasAttribute('role')).toBe(false);
  });

  it('expose un rôle image et un libellé accessible quand on lui en donne un', () => {
    const svg = rendre('outage', 'Coupure').querySelector('svg');

    expect(svg?.getAttribute('role')).toBe('img');
    expect(svg?.getAttribute('aria-label')).toBe('Coupure');
    expect(svg?.hasAttribute('aria-hidden')).toBe(false);
  });

  it('hérite de la couleur du parent via currentColor', () => {
    const svg = rendre('sensor').querySelector('svg');

    expect(svg?.getAttribute('stroke')).toBe('currentColor');
    expect(svg?.getAttribute('fill')).toBe('none');
  });
});
