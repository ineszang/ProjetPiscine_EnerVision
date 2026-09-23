export function rapport(nom, data) {
  const horodatage = new Date().toISOString().replace(/[:.]/g, '-');
  const markdown = enMarkdown(nom, data);
  const sorties = {
    stdout: `${markdown}\n`,
    [`/results/${nom}-${horodatage}.json`]: JSON.stringify(data, null, 2),
    [`/results/${nom}-${horodatage}.md`]: markdown,
  };
  if (__ENV.K6_RESUME) {
    sorties[__ENV.K6_RESUME] = markdown;
  }
  return sorties;
}

function valeur(metrique, statistique, unite) {
  const brut = metrique?.values?.[statistique];
  if (brut === undefined) {
    return '-';
  }
  return unite === '%' ? `${(brut * 100).toFixed(2)} %` : `${brut.toFixed(1)} ${unite}`;
}

function enMarkdown(nom, data) {
  const m = data.metrics;
  const lignes = [
    `### Tir k6 « ${nom} »`,
    '',
    '| Mesure | Valeur |',
    '|---|---|',
    `| Requêtes | ${m.http_reqs?.values?.count ?? 0} (${valeur(m.http_reqs, 'rate', 'req/s')}) |`,
    `| Échecs HTTP | ${valeur(m.http_req_failed, 'rate', '%')} |`,
    `| Vérifications réussies | ${valeur(m.checks, 'rate', '%')} |`,
    `| Durée médiane | ${valeur(m.http_req_duration, 'med', 'ms')} |`,
    `| Durée p95 | ${valeur(m.http_req_duration, 'p(95)', 'ms')} |`,
    `| Durée p99 | ${valeur(m.http_req_duration, 'p(99)', 'ms')} |`,
    `| VUs au plus haut | ${m.vus_max?.values?.max ?? '-'} |`,
    '',
    '| Seuil | Résultat |',
    '|---|---|',
  ];
  for (const [metrique, detail] of Object.entries(m)) {
    for (const [expression, resultat] of Object.entries(detail.thresholds || {})) {
      lignes.push(`| \`${metrique}\` ${expression} | ${resultat.ok ? 'tenu' : '**franchi**'} |`);
    }
  }
  return lignes.join('\n');
}
