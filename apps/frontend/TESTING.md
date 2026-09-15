# Conventions de tests unitaires — Frontend

## Outil
Vitest (intégré nativement à Angular CLI, pas d'installation à faire).

## Où écrire les tests
Un fichier `*.spec.ts` à côté de chaque fichier testé (convention Angular CLI
par défaut, respectée automatiquement par `ng generate`).

## Structure attendue (Arrange / Act / Assert)
```typescript
it('devrait faire X quand Y', () => {
  // Arrange : préparer les données et les mocks
  const input = { valeur: 42 };

  // Act : exécuter le code testé
  const result = service.doSomething(input);

  // Assert : vérifier le résultat
  expect(result).toBe(true);
});
```

## Ce qui doit être testé en priorité
- Services (`core/services/`) : logique métier, gestion des erreurs
- Guards et interceptors (`core/guards/`, `core/interceptors/`) : chaque branche de décision
- Composants avec logique (formulaires, conditions d'affichage) — pas nécessaire pour
  un composant 100% template, sans logique

## Gabarit — tester un service avec appel HTTP
```typescript
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { MonService } from './mon.service';

describe('MonService', () => {
  let service: MonService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [MonService, provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(MonService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('devrait récupérer les données', () => {
    service.getData().subscribe();
    const req = httpMock.expectOne('/api/v1/...');
    expect(req.request.method).toBe('GET');
    req.flush({ /* réponse simulée */ });
  });
});
```

## Gabarit — tester un composant standalone
```typescript
import { TestBed } from '@angular/core/testing';
import { MonComposant } from './mon-composant';

describe('MonComposant', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MonComposant],
    }).compileComponents();
  });

  it('devrait se créer', () => {
    const fixture = TestBed.createComponent(MonComposant);
    expect(fixture.componentInstance).toBeTruthy();
  });
});
```

## Lancer les tests
- Développement (mode watch) : `npm test`
- Rapport de couverture (CI) : `npm run test:ci -- --coverage`, puis ouvrir `coverage/index.html`
