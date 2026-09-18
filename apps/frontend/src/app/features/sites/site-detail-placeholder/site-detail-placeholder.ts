import { Component, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { map } from 'rxjs';
import { Card } from '../../../shared/components/ui/card/card';
import { Brand } from '../../../shared/components/ui/brand/brand';

@Component({
  selector: 'app-site-detail-placeholder',
  standalone: true,
  imports: [RouterLink, Card, Brand],
  templateUrl: './site-detail-placeholder.html',
  styleUrl: './site-detail-placeholder.scss',
})
export class SiteDetailPlaceholder {
  private route = inject(ActivatedRoute);

  siteId = toSignal(this.route.paramMap.pipe(map((params) => params.get('siteId'))));
}
