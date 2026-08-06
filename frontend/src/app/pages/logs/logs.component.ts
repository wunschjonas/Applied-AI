import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { CommonModule, DatePipe, SlicePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { forkJoin } from 'rxjs';
import { SidebarComponent } from '../../components/sidebar/sidebar.component';
import { LogService } from '../../services/log.service';
import { PostService } from '../../services/post.service';
import { PostFacade } from '../../facades/post.facade';
import { LogEntry, LogsResponse } from '../../models/log.model';
import { Post } from '../../models/post.model';
import { httpErrorDetail } from '../../core/http-error';

export type LogFilter = 'all' | 'manager' | 'text' | 'image';

@Component({
  selector: 'app-logs',
  standalone: true,
  imports: [SidebarComponent, CommonModule, DatePipe, SlicePipe, FormsModule],
  templateUrl: './logs.component.html',
  styleUrls: ['./logs.component.scss'],
})
export class LogsComponent implements OnInit {
  private readonly logService = inject(LogService);
  private readonly postService = inject(PostService);
  private readonly postFacade = inject(PostFacade);

  private readonly allLogs = signal<LogEntry[]>([]);
  readonly posts = signal<Post[]>([]);
  readonly isLoading = signal(false);
  readonly isDeleting = signal(false);
  readonly loadError = signal('');
  readonly activeFilter = signal<LogFilter>('all');
  readonly selectedPostId = signal<string>('');
  readonly deleteMessage = signal('');

  readonly postTitleById = computed(() => {
    const map = new Map<string, string>();
    for (const post of this.posts()) {
      map.set(post.id, post.title);
    }
    return map;
  });

  readonly logs = computed(() => {
    const postId = this.selectedPostId();
    const rows = this.allLogs();
    if (!postId) return rows;
    return rows.filter((log) => log.post_id === postId);
  });

  /** Post filter selection, else currently selected Manager post. */
  readonly deleteTargetPostId = computed(
    () => this.selectedPostId() || this.postFacade.currentPostId() || '',
  );

  ngOnInit() {
    const currentId = this.postFacade.currentPostId();
    if (currentId) {
      this.selectedPostId.set(currentId);
    }
    this.postService.getAllPosts().subscribe({
      next: (posts) => this.posts.set(posts),
      error: (err) => {
        this.loadError.set(httpErrorDetail(err, 'Posts konnten nicht geladen werden.'));
      },
    });
    this.reloadActiveFilter();
  }

  loadAll() {
    this.activeFilter.set('all');
    this.fetchAllAgents();
  }

  loadManagerLogs() {
    this.activeFilter.set('manager');
    this.isLoading.set(true);
    this.loadError.set('');
    this.logService.getManagerLogs().subscribe({
      next: (response: LogsResponse) => {
        this.allLogs.set(this.sortNewestFirst(response.logs));
        this.isLoading.set(false);
      },
      error: (err) => {
        this.loadError.set(httpErrorDetail(err, 'Manager-Logs konnten nicht geladen werden.'));
        this.isLoading.set(false);
      },
    });
  }

  loadTextLogs() {
    this.activeFilter.set('text');
    this.isLoading.set(true);
    this.loadError.set('');
    this.logService.getTextLogs().subscribe({
      next: (response: LogsResponse) => {
        this.allLogs.set(this.sortNewestFirst(response.logs));
        this.isLoading.set(false);
      },
      error: (err) => {
        this.loadError.set(httpErrorDetail(err, 'Text-Logs konnten nicht geladen werden.'));
        this.isLoading.set(false);
      },
    });
  }

  loadImageLogs() {
    this.activeFilter.set('image');
    this.isLoading.set(true);
    this.loadError.set('');
    this.logService.getImageLogs().subscribe({
      next: (response: LogsResponse) => {
        this.allLogs.set(this.sortNewestFirst(response.logs));
        this.isLoading.set(false);
      },
      error: (err) => {
        this.loadError.set(httpErrorDetail(err, 'Bild-Logs konnten nicht geladen werden.'));
        this.isLoading.set(false);
      },
    });
  }

  onPostFilterChange(postId: string) {
    this.selectedPostId.set(postId);
  }

  postLabel(log: LogEntry): string {
    if (!log.post_id) return '—';
    return this.postTitleById().get(log.post_id) || log.post_id.slice(0, 8);
  }

  deleteTargetPostLabel(): string {
    const id = this.deleteTargetPostId();
    if (!id) return '';
    return this.postTitleById().get(id) || id.slice(0, 8);
  }

  deleteSelectedPostLogs(): void {
    const postId = this.deleteTargetPostId();
    if (!postId || this.isDeleting()) return;
    const title = this.deleteTargetPostLabel();
    if (!confirm(`Alle Logs für Post „${title}“ löschen?`)) return;

    this.isDeleting.set(true);
    this.deleteMessage.set('');
    this.logService.deleteLogsForPost(postId).subscribe({
      next: (res) => {
        this.deleteMessage.set(`${res.deleted} Log(s) für diesen Post gelöscht.`);
        this.reloadActiveFilter();
      },
      error: () => {
        this.deleteMessage.set('Löschen der Post-Logs fehlgeschlagen.');
        this.isDeleting.set(false);
      },
      complete: () => this.isDeleting.set(false),
    });
  }

  deleteAllLogs(): void {
    if (this.isDeleting()) return;
    if (!confirm('Wirklich ALLE Agent-Logs löschen?')) return;

    this.isDeleting.set(true);
    this.deleteMessage.set('');
    this.logService.deleteAllLogs().subscribe({
      next: (res) => {
        this.deleteMessage.set(`${res.deleted} Log(s) gelöscht.`);
        this.reloadActiveFilter();
      },
      error: () => {
        this.deleteMessage.set('Löschen aller Logs fehlgeschlagen.');
        this.isDeleting.set(false);
      },
      complete: () => this.isDeleting.set(false),
    });
  }

  private reloadActiveFilter(): void {
    const filter = this.activeFilter();
    if (filter === 'manager') this.loadManagerLogs();
    else if (filter === 'text') this.loadTextLogs();
    else if (filter === 'image') this.loadImageLogs();
    else this.fetchAllAgents();
  }

  private fetchAllAgents(): void {
    this.isLoading.set(true);
    this.loadError.set('');
    forkJoin([
      this.logService.getManagerLogs(),
      this.logService.getTextLogs(),
      this.logService.getImageLogs(),
    ]).subscribe({
      next: ([manager, text, image]: LogsResponse[]) => {
        this.allLogs.set(
          this.sortNewestFirst([...manager.logs, ...text.logs, ...image.logs]),
        );
        this.isLoading.set(false);
      },
      error: (err) => {
        this.loadError.set(httpErrorDetail(err, 'Logs konnten nicht geladen werden.'));
        this.isLoading.set(false);
      },
    });
  }

  private sortNewestFirst(logs: LogEntry[]): LogEntry[] {
    return [...logs].sort(
      (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
    );
  }
}
