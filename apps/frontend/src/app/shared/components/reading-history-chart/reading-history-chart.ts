import {
  Component,
  ElementRef,
  ViewChild,
  input,
  effect,
  AfterViewInit,
  OnDestroy,
} from '@angular/core';
import { Chart, registerables } from 'chart.js';
import { Reading, ReadingDataQuality } from '../../models/reading.model';

Chart.register(...registerables);

const QUALITY_COLORS: Record<ReadingDataQuality, string> = {
  good: '#3b82f6',
  partial: '#f9a825',
  degraded: '#ef6c00',
  critical: '#c62828',
};
const UNKNOWN_QUALITY_COLOR = '#9ca3af';

interface ChartSeries {
  labels: string[];
  values: number[];
  colors: string[];
}

// Piège : l'API renvoie les lectures du plus récent au plus ancien (ReadingRepository.list_history
// trie en timestamp desc) ; sans ce tri l'axe des abscisses se lirait à rebours.
function toSeries(readings: Reading[]): ChartSeries {
  const ordered = [...readings].sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp));
  return {
    labels: ordered.map((r) => r.timestamp),
    values: ordered.map((r) => r.consumption_kw ?? 0),
    colors: ordered.map((r) =>
      r.data_quality ? QUALITY_COLORS[r.data_quality] : UNKNOWN_QUALITY_COLOR,
    ),
  };
}

@Component({
  selector: 'app-reading-history-chart',
  standalone: true,
  templateUrl: './reading-history-chart.html',
  styleUrl: './reading-history-chart.scss',
})
export class ReadingHistoryChart implements AfterViewInit, OnDestroy {
  readings = input.required<Reading[]>();

  @ViewChild('canvas') private canvasRef!: ElementRef<HTMLCanvasElement>;
  private chart?: Chart<'line'>;

  constructor() {
    effect(() => {
      const series = toSeries(this.readings());
      if (this.chart) {
        this.chart.data.labels = series.labels;
        this.chart.data.datasets[0].data = series.values;
        this.chart.data.datasets[0].pointBackgroundColor = series.colors;
        this.chart.update('none');
      }
    });
  }

  ngAfterViewInit(): void {
    const series = toSeries(this.readings());
    this.chart = new Chart(this.canvasRef.nativeElement, {
      type: 'line',
      data: {
        labels: series.labels,
        datasets: [
          {
            data: series.values,
            borderColor: '#3b82f6',
            pointBackgroundColor: series.colors,
            tension: 0.25,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: { beginAtZero: true, title: { display: true, text: 'Consommation (kW)' } },
        },
      },
    });
  }

  ngOnDestroy(): void {
    this.chart?.destroy();
  }
}
