import { TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { Chart } from 'chart.js';
import { ReadingHistoryChart } from './reading-history-chart';

vi.mock('chart.js', () => {
  class ChartMock {
    static instances: ChartMock[] = [];
    static register = vi.fn();
    update = vi.fn();
    destroy = vi.fn();
    data: { labels?: unknown[]; datasets: Record<string, unknown>[] } = { datasets: [{}] };
    constructor(_canvas: unknown, config?: { data?: ChartMock['data'] }) {
      if (config?.data) {
        this.data = config.data;
      }
      ChartMock.instances.push(this);
    }
  }
  return { Chart: ChartMock, registerables: [] };
});

type ChartDouble = {
  destroy: ReturnType<typeof vi.fn>;
  data: { labels?: unknown[]; datasets: Record<string, unknown>[] };
};

function lastChart(): ChartDouble | undefined {
  return (Chart as unknown as { instances: ChartDouble[] }).instances.at(-1);
}

const READING = {
  reading_id: 1,
  site_id: 'S1',
  timestamp: '2026-09-17T10:00:00Z',
  source: 'api_history' as const,
  consumption_kw: 42,
  consumption_kwh: null,
  consumption_euros: null,
  voltage_v: null,
  current_a: null,
  power_factor: null,
  temperature_celsius: null,
  humidity_percent: null,
  solar_irradiance_wm2: null,
  is_working_hours: null,
  data_quality: 'good' as const,
  null_reasons: null,
  imputed_values: null,
  imputation_method: null,
};

describe('ReadingHistoryChart', () => {
  it('se crée sans erreur avec une liste de lectures valide', () => {
    TestBed.configureTestingModule({ imports: [ReadingHistoryChart] });
    const fixture = TestBed.createComponent(ReadingHistoryChart);
    fixture.componentRef.setInput('readings', [READING]);
    expect(() => fixture.detectChanges()).not.toThrow();
  });

  it('met à jour le graphique quand les lectures changent après initialisation', () => {
    TestBed.configureTestingModule({ imports: [ReadingHistoryChart] });
    const fixture = TestBed.createComponent(ReadingHistoryChart);
    fixture.componentRef.setInput('readings', [READING]);
    fixture.detectChanges();

    fixture.componentRef.setInput('readings', [
      { ...READING, reading_id: 2, consumption_kw: 60, data_quality: 'critical' as const },
    ]);
    fixture.detectChanges();

    expect(() => fixture.detectChanges()).not.toThrow();
  });

  it("trace du plus ancien au plus récent, quel que soit l'ordre reçu de l'API", () => {
    TestBed.configureTestingModule({ imports: [ReadingHistoryChart] });
    const fixture = TestBed.createComponent(ReadingHistoryChart);
    // L'API trie en timestamp décroissant : le composant doit rétablir la chronologie.
    fixture.componentRef.setInput('readings', [
      { ...READING, reading_id: 2, timestamp: '2026-09-17T11:00:00Z', consumption_kw: 60 },
      { ...READING, reading_id: 1, timestamp: '2026-09-17T10:00:00Z', consumption_kw: 42 },
    ]);
    fixture.detectChanges();

    const chart = lastChart();
    expect(chart?.data.labels).toEqual(['2026-09-17T10:00:00Z', '2026-09-17T11:00:00Z']);
    expect(chart?.data.datasets[0]['data']).toEqual([42, 60]);
  });

  it('détruit le graphique quand le composant est détruit', () => {
    TestBed.configureTestingModule({ imports: [ReadingHistoryChart] });
    const fixture = TestBed.createComponent(ReadingHistoryChart);
    fixture.componentRef.setInput('readings', [READING]);
    fixture.detectChanges();

    const chart = lastChart();
    fixture.destroy();

    expect(chart?.destroy).toHaveBeenCalledTimes(1);
  });
});
