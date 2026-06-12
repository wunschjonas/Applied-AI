import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { SidebarComponent } from '../../components/sidebar/sidebar.component';
import { MemoryService } from '../../services/memory.service';

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

  // Search
  public searchQuery = signal('');
  public searchResults = signal<string[]>([]);
  public isSearching = signal(false);
  public hasSearched = signal(false);

  // List
  public allEntries = signal<string[]>([]);
  public isLoadingList = signal(false);

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
    this.memoryService.store(content, tags).subscribe({
      next: () => {
        this.storeContent.set('');
        this.storeTags.set('');
        this.storeSuccess.set(true);
        this.loadAll();
        setTimeout(() => this.storeSuccess.set(false), 3000);
      },
      error: (err) => console.error('[Memory] Store error:', err),
      complete: () => this.isStoring.set(false),
    });
  }

  public search(): void {
    const q = this.searchQuery().trim();
    if (!q) return;

    this.isSearching.set(true);
    this.hasSearched.set(false);
    this.memoryService.search(q).subscribe({
      next: (res) => {
        this.searchResults.set(res.results);
        this.hasSearched.set(true);
      },
      error: (err) => console.error('[Memory] Search error:', err),
      complete: () => this.isSearching.set(false),
    });
  }

  public loadAll(): void {
    this.isLoadingList.set(true);
    this.memoryService.list().subscribe({
      next: (res) => this.allEntries.set(res.entries),
      error: (err) => console.error('[Memory] List error:', err),
      complete: () => this.isLoadingList.set(false),
    });
  }
}
