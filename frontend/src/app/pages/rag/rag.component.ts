import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { SidebarComponent } from '../../components/sidebar/sidebar.component';
import { MemoryListEntry, MemoryService } from '../../services/memory.service';
import { httpErrorDetail } from '../../core/http-error';

@Component({
  selector: 'app-rag',
  standalone: true,
  imports: [SidebarComponent, FormsModule],
  templateUrl: './rag.component.html',
  styleUrls: ['./rag.component.scss'],
})
export class RagComponent implements OnInit {
  private readonly memoryService = inject(MemoryService);

  // Store
  public storeContent = signal('');
  public storeTags = signal('');
  public isStoring = signal(false);
  public storeSuccess = signal(false);
  public storeError = signal('');

  // Upload
  public isUploading = signal(false);
  public isDragOver = signal(false);
  public uploadMessage = signal('');
  public uploadError = signal('');

  // List
  public allEntries = signal<MemoryListEntry[]>([]);
  public isLoadingList = signal(false);
  public deletingHash = signal<string | null>(null);
  public deleteError = signal('');

  public ngOnInit(): void {
    this.loadAll();
  }

  public store(): void {
    const content = this.storeContent().trim();
    if (!content) return;

    const tags = this.storeTags()
      .split(',')
      .map((t) => t.trim())
      .filter((t) => t.length > 0);

    this.isStoring.set(true);
    this.storeSuccess.set(false);
    this.storeError.set('');
    this.memoryService.store(content, tags).subscribe({
      next: () => {
        this.storeContent.set('');
        this.storeTags.set('');
        this.storeSuccess.set(true);
        this.loadAll();
        setTimeout(() => this.storeSuccess.set(false), 3000);
      },
      error: (err) => {
        this.storeError.set(httpErrorDetail(err, 'Speichern fehlgeschlagen.'));
      },
      complete: () => this.isStoring.set(false),
    });
  }

  public onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.isDragOver.set(true);
  }

  public onDragLeave(event: DragEvent): void {
    event.preventDefault();
    this.isDragOver.set(false);
  }

  public onDrop(event: DragEvent): void {
    event.preventDefault();
    this.isDragOver.set(false);
    const file = event.dataTransfer?.files?.[0];
    if (file) {
      this.uploadFile(file);
    }
  }

  public onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (file) {
      this.uploadFile(file);
    }
    input.value = '';
  }

  public uploadFile(file: File): void {
    this.isUploading.set(true);
    this.uploadMessage.set('');
    this.uploadError.set('');
    this.memoryService.upload(file).subscribe({
      next: (res) => {
        this.uploadMessage.set(
          `${res.filename}: ${res.stored_chunks} Chunk(s) als ${res.kind} gespeichert.`
        );
        this.loadAll();
      },
      error: (err) => {
        this.uploadError.set(httpErrorDetail(err, 'Upload fehlgeschlagen.'));
        this.isUploading.set(false);
      },
      complete: () => this.isUploading.set(false),
    });
  }

  public loadAll(): void {
    this.isLoadingList.set(true);
    this.deleteError.set('');
    this.memoryService.list().subscribe({
      next: (res) => this.allEntries.set(res.entries),
      error: (err) => console.error('[Memory] List error:', err),
      complete: () => this.isLoadingList.set(false),
    });
  }

  public deleteEntry(entry: MemoryListEntry): void {
    if (!entry.content_hash || this.deletingHash()) {
      return;
    }
    const confirmed = window.confirm('Diesen Gedächtnis-Eintrag wirklich löschen?');
    if (!confirmed) {
      return;
    }

    this.deletingHash.set(entry.content_hash);
    this.deleteError.set('');
    this.memoryService.delete(entry.content_hash).subscribe({
      next: () => {
        this.allEntries.update((entries) =>
          entries.filter((item) => item.content_hash !== entry.content_hash)
        );
      },
      error: (err) => {
        this.deleteError.set(httpErrorDetail(err, 'Löschen fehlgeschlagen.'));
        this.deletingHash.set(null);
      },
      complete: () => this.deletingHash.set(null),
    });
  }
}
