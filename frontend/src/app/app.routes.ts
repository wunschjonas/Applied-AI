import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    pathMatch: 'full',
    redirectTo: 'home',
  },
  {
    path: 'home',
    loadComponent: () =>
      import('./pages/home/home.component').then(
        (module) => module.HomeComponent,
      ),
  },
  {
    path: 'image_agent',
    loadComponent: () =>
      import('./pages/image-agent/image-agent.component').then(
        (module) => module.ImageAgentComponent,
      ),
  },
  {
    path: 'text_agent',
    loadComponent: () =>
      import('./pages/text-agent/text-agent.component').then(
        (module) => module.TextAgentComponent,
      ),
  },
  {
    path: 'logs',
    loadComponent: () =>
      import('./pages/logs/logs.component').then(
        (module) => module.LogsComponent,
      ),
  },
  {
    path: 'rag',
    loadComponent: () =>
      import('./pages/rag/rag.component').then((module) => module.RagComponent),
  },
  {
    path: 'preview',
    loadComponent: () =>
      import('./pages/preview/preview.component').then(
        (module) => module.PreviewComponent,
      ),
  },
  {
    path: 'contact',
    loadComponent: () =>
      import('./pages/contact/contact.component').then(
        (module) => module.ContactComponent,
      ),
  },
  {
    path: '**',
    redirectTo: 'home',
  },
];
