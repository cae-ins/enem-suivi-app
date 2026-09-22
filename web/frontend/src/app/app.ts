import { CommonModule } from '@angular/common';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Component, OnDestroy, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { interval, Subscription, switchMap } from 'rxjs';

interface ModuleSummary {
  id: string;
  name: string;
  short_name: string;
  description: string;
  team: string;
  frequency: string;
  order: number;
  parameters: ParameterDefinition[];
}

interface ParameterColumn { key: string; label: string; type: string; width: number; }
interface ParameterDefinition {
  key: string;
  label: string;
  type: string;
  default: unknown;
  required: boolean;
  help: string;
  note: string;
  group: string;
  mini?: number;
  maxi?: number;
  options?: unknown[];
  columns?: ParameterColumn[];
}

interface StoredFile {
  id: string;
  original_name: string;
  bucket: string;
  content_type: string;
  size_bytes: number | null;
  status: string;
  created_at: string;
}

interface Execution {
  id: string;
  module_id: string;
  quarter: string;
  parameters: Record<string, unknown>;
  status: string;
  progress: number;
  progress_message: string;
  summary: string;
  created_at: string;
  files: StoredFile[];
}

interface TokenResponse { access: string; refresh: string; }
interface UploadTicket { id: string; upload_url: string; }

@Component({
  selector: 'app-root',
  imports: [CommonModule, FormsModule],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App implements OnDestroy {
  private readonly http = inject(HttpClient);
  private poll?: Subscription;

  readonly authenticated = signal(Boolean(sessionStorage.getItem('enem_access')));
  readonly loading = signal(false);
  readonly modules = signal<ModuleSummary[]>([]);
  readonly files = signal<StoredFile[]>([]);
  readonly executions = signal<Execution[]>([]);
  readonly error = signal('');
  readonly notice = signal('');
  readonly executionOpen = signal(false);

  username = sessionStorage.getItem('enem_user') ?? '';
  password = '';
  selectedModule = '';
  quarter = 'T3_2026';
  parameterValues: Record<string, any> = {};
  uploadQuarter = 'T3_2026';

  constructor() {
    if (this.authenticated()) this.startSession();
  }

  ngOnDestroy(): void { this.poll?.unsubscribe(); }

  login(): void {
    this.loading.set(true);
    this.error.set('');
    this.http.post<TokenResponse>('/api/v1/auth/token/', {
      username: this.username,
      password: this.password,
    }).subscribe({
      next: tokens => {
        sessionStorage.setItem('enem_access', tokens.access);
        sessionStorage.setItem('enem_refresh', tokens.refresh);
        sessionStorage.setItem('enem_user', this.username);
        this.authenticated.set(true);
        this.password = '';
        this.loading.set(false);
        this.startSession();
      },
      error: () => {
        this.loading.set(false);
        this.error.set('Identifiant ou mot de passe incorrect.');
      },
    });
  }

  logout(): void {
    sessionStorage.clear();
    this.poll?.unsubscribe();
    this.authenticated.set(false);
    this.modules.set([]);
    this.files.set([]);
    this.executions.set([]);
  }

  openExecution(module?: ModuleSummary): void {
    this.selectedModule = module?.id ?? this.modules()[0]?.id ?? '';
    this.resetParameters();
    this.error.set('');
    this.executionOpen.set(true);
  }

  createExecution(): void {
    if (!this.selectedModule) {
      this.error.set('Sélectionne un module.');
      return;
    }
    const parameters = this.buildParameters();
    const missing = this.currentParameters().filter(parameter =>
      parameter.required && this.isEmpty(parameters[parameter.key])
    );
    if (missing.length) {
      this.error.set(`Champs obligatoires : ${missing.map(item => item.label).join(', ')}`);
      return;
    }
    this.loading.set(true);
    this.http.post<Execution>('/api/v1/executions/', {
      module_id: this.selectedModule,
      quarter: this.quarter,
      parameters,
      global_parameters: {},
    }).subscribe({
      next: execution => {
        this.loading.set(false);
        this.executionOpen.set(false);
        this.notice.set(`Traitement ${execution.id.slice(0, 8)} placé dans la file.`);
        this.refreshExecutions();
      },
      error: error => this.handleError(error, 'Impossible de lancer le traitement.'),
    });
  }

  currentParameters(): ParameterDefinition[] {
    return this.modules().find(module => module.id === this.selectedModule)?.parameters ?? [];
  }

  parameterGroups(): string[] {
    return [...new Set(this.currentParameters().map(parameter => parameter.group))];
  }

  parametersForGroup(group: string): ParameterDefinition[] {
    return this.currentParameters().filter(parameter => parameter.group === group);
  }

  moduleChanged(): void {
    this.resetParameters();
  }

  addVersion(key: string): void {
    (this.parameterValues[key] as string[]).push('');
  }

  removeVersion(key: string, index: number): void {
    (this.parameterValues[key] as string[]).splice(index, 1);
  }

  addTableRow(parameter: ParameterDefinition): void {
    const row: Record<string, unknown> = {};
    for (const column of parameter.columns ?? []) row[column.key] = '';
    (this.parameterValues[parameter.key] as Record<string, unknown>[]).push(row);
  }

  removeTableRow(key: string, index: number): void {
    (this.parameterValues[key] as Record<string, unknown>[]).splice(index, 1);
  }

  upload(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    this.loading.set(true);
    this.error.set('');
    this.http.post<UploadTicket>('/api/v1/files/upload-ticket/', {
      filename: file.name,
      content_type: file.type || 'application/octet-stream',
      category: 'entrees',
      quarter: this.uploadQuarter,
    }).subscribe({
      next: ticket => this.http.put(ticket.upload_url, file, {
        headers: { 'Content-Type': file.type || 'application/octet-stream' },
        responseType: 'text',
      }).subscribe({
        next: () => this.http.post<StoredFile>(`/api/v1/files/${ticket.id}/complete/`, {}).subscribe({
          next: stored => {
            this.loading.set(false);
            this.notice.set(`${stored.original_name} est disponible dans MinIO.`);
            input.value = '';
            this.refreshFiles();
          },
          error: error => this.handleError(error, 'Le dépôt n’a pas pu être confirmé.'),
        }),
        error: error => this.handleError(error, 'MinIO a refusé le fichier.'),
      }),
      error: error => this.handleError(error, 'Impossible de préparer le dépôt.'),
    });
  }

  download(file: StoredFile): void {
    this.http.get<{ download_url: string }>(`/api/v1/files/${file.id}/download/`).subscribe({
      next: response => window.open(response.download_url, '_blank', 'noopener'),
      error: error => this.handleError(error, 'Impossible de préparer le téléchargement.'),
    });
  }

  moduleName(id: string): string {
    return this.modules().find(module => module.id === id)?.short_name ?? id;
  }

  statusLabel(status: string): string {
    return ({ queued: 'En attente', running: 'En cours', succeeded: 'Terminé', failed: 'Erreur', cancelled: 'Annulé' } as Record<string, string>)[status] ?? status;
  }

  size(bytes: number | null): string {
    if (bytes === null) return '—';
    if (bytes < 1024) return `${bytes} o`;
    if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} Ko`;
    return `${(bytes / 1024 ** 2).toFixed(1)} Mo`;
  }

  private startSession(): void {
    this.refreshAll();
    this.poll?.unsubscribe();
    this.poll = interval(3000).pipe(switchMap(() => this.http.get<Execution[]>('/api/v1/executions/')))
      .subscribe({ next: data => this.executions.set(data), error: error => this.handleUnauthorized(error) });
  }

  private refreshAll(): void {
    this.loading.set(true);
    this.http.get<ModuleSummary[]>('/api/v1/modules/').subscribe({
      next: data => {
        this.modules.set(data);
        this.selectedModule ||= data[0]?.id ?? '';
        this.resetParameters();
        this.loading.set(false);
      },
      error: error => this.handleError(error, 'Le catalogue métier est indisponible.'),
    });
    this.refreshFiles();
    this.refreshExecutions();
  }

  private refreshFiles(): void {
    this.http.get<StoredFile[]>('/api/v1/files/').subscribe({
      next: data => this.files.set(data),
      error: error => this.handleUnauthorized(error),
    });
  }

  private refreshExecutions(): void {
    this.http.get<Execution[]>('/api/v1/executions/').subscribe({
      next: data => this.executions.set(data),
      error: error => this.handleUnauthorized(error),
    });
  }

  private handleError(error: HttpErrorResponse, fallback: string): void {
    this.loading.set(false);
    if (this.handleUnauthorized(error)) return;
    const detail = this.apiError(error.error) || fallback;
    this.error.set(detail);
  }

  private resetParameters(): void {
    const values: Record<string, any> = {};
    for (const parameter of this.currentParameters()) {
      const value = parameter.default;
      if (parameter.type === 'versions') {
        values[parameter.key] = Array.isArray(value) ? [...value] : [''];
      } else if (parameter.type === 'tableau') {
        values[parameter.key] = Array.isArray(value) ? value.map(row => ({ ...(row as object) })) : [];
      } else {
        values[parameter.key] = value ?? '';
      }
    }
    this.parameterValues = values;
  }

  private buildParameters(): Record<string, unknown> {
    const result: Record<string, unknown> = {};
    for (const parameter of this.currentParameters()) {
      let value = this.parameterValues[parameter.key];
      if (parameter.type === 'versions') value = (value as string[]).filter(item => item.trim());
      if (parameter.type === 'tableau') {
        value = (value as Record<string, unknown>[]).filter(row => Object.values(row).some(item => String(item ?? '').trim()));
      }
      result[parameter.key] = value;
    }
    const trimestre = result['trimestre'];
    if (typeof trimestre === 'string' && trimestre) this.quarter = trimestre.replace('-', '_');
    return result;
  }

  private isEmpty(value: unknown): boolean {
    return value === null || value === undefined || value === '' || (Array.isArray(value) && value.length === 0);
  }

  private apiError(payload: unknown): string {
    if (!payload || typeof payload !== 'object') return '';
    const object = payload as Record<string, unknown>;
    if (typeof object['detail'] === 'string') return object['detail'];
    const messages = Object.values(object).flatMap(value => Array.isArray(value) ? value : [value]);
    return messages.filter(value => typeof value === 'string').join(' ');
  }

  private handleUnauthorized(error: HttpErrorResponse): boolean {
    if (error.status !== 401) return false;
    this.logout();
    this.error.set('La session a expiré. Reconnecte-toi.');
    return true;
  }
}
