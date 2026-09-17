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

function pointColors(readings: Reading[]): string[] {
  return readings.map((r) => (r.data_quality ? QUALITY_COLORS[r.data_quality] : UNKNOWN_QUALITY_COLOR));
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
      const readings = this.readings();
      if (this.chart) {
        this.chart.data.labels = readings.map((r) => r.timestamp);
        this.chart.data.datasets[0].data = readings.map((r) => r.consumption_kw ?? 0);
        this.chart.data.datasets[0].pointBackgroundColor = pointColors(readings);
        this.chart.update('none');
      }
    });
  }

  ngAfterViewInit(): void {
    const readings = this.readings();
    this.chart = new Chart(this.canvasRef.nativeElement, {
      type: 'line',
      data: {
        labels: readings.map((r) => r.timestamp),
        datasets: [
          {
            data: readings.map((r) => r.consumption_kw ?? 0),
            borderColor: '#3b82f6',
            pointBackgroundColor: pointColors(readings),
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
