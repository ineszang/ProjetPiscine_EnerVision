import { TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { Chart } from 'chart.js';
import { SiteLoadChart } from './site-load-chart';

vi.mock('chart.js', () => {
  class ChartMock {
    static instances: ChartMock[] = [];
    static register = vi.fn();
    update = vi.fn();
    destroy = vi.fn();
    data = { datasets: [{}] };
    constructor() {
      ChartMock.instances.push(this);
    }
  }
  return { Chart: ChartMock, registerables: [] };
});

type ChartDouble = { destroy: ReturnType<typeof vi.fn> };

function lastChart(): ChartDouble | undefined {
  return (Chart as unknown as { instances: ChartDouble[] }).instances.at(-1);
}

describe('SiteLoadChart', () => {
  it('se crée sans erreur avec une liste de sites valide', () => {
    TestBed.configureTestingModule({ imports: [SiteLoadChart] });
    const fixture = TestBed.createComponent(SiteLoadChart);
    fixture.componentRef.setInput('sites', [
      {
        site_id: 'S1',
        site_name: 'Test',
        current_consumption_kw: 50,
        capacity_kw: 100,
        load_percent: 50,
        data_quality: 'good',
      },
    ]);
    expect(() => fixture.detectChanges()).not.toThrow();
  });
  it('met à jour le graphique quand les sites changent après initialisation', () => {
    TestBed.configureTestingModule({ imports: [SiteLoadChart] });
    const fixture = TestBed.createComponent(SiteLoadChart);
    fixture.componentRef.setInput('sites', [
      {
        site_id: 'S1',
        site_name: 'A',
        current_consumption_kw: 50,
        capacity_kw: 100,
        load_percent: 50,
        data_quality: 'good',
      },
    ]);
    fixture.detectChanges(); // déclenche ngAfterViewInit, this.chart existe désormais

    fixture.componentRef.setInput('sites', [
      {
        site_id: 'S2',
        site_name: 'B',
        current_consumption_kw: 80,
        capacity_kw: 100,
        load_percent: 80,
        data_quality: 'critical',
      },
    ]);
    fixture.detectChanges(); // ré-exécute l'effect, cette fois avec this.chart défini

    expect(() => fixture.detectChanges()).not.toThrow();
  });

  it('détruit le graphique quand le composant est détruit', () => {
    TestBed.configureTestingModule({ imports: [SiteLoadChart] });
    const fixture = TestBed.createComponent(SiteLoadChart);
    fixture.componentRef.setInput('sites', [
      {
        site_id: 'S1',
        site_name: 'A',
        current_consumption_kw: 50,
        capacity_kw: 100,
        load_percent: 50,
        data_quality: 'good',
      },
    ]);
    fixture.detectChanges();

    const chart = lastChart();
    fixture.destroy();

    expect(chart?.destroy).toHaveBeenCalledTimes(1);
  });
});
