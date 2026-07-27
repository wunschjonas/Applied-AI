import { Component, inject, OnInit } from '@angular/core';
import { CommonModule, DatePipe, SlicePipe } from '@angular/common';
import { forkJoin } from 'rxjs';
import { SidebarComponent } from '../../components/sidebar/sidebar.component';
import { LogService } from '../../services/log.service';
import { LogEntry, LogsResponse } from '../../models/log.model';

export type LogFilter = 'all' | 'manager' | 'text' | 'image';

@Component({
  selector: 'app-logs',
  standalone: true,
  imports: [SidebarComponent, CommonModule, DatePipe, SlicePipe],
  templateUrl: './logs.component.html',
  styleUrls: ['./logs.component.scss'],
})
export class LogsComponent implements OnInit {
  private readonly logService = inject(LogService);

  logs: LogEntry[] = [];
  isLoading = false;
  activeFilter: LogFilter = 'all';

  ngOnInit() {
    this.loadAll();
  }

  loadAll() {
    this.activeFilter = 'all';
    this.isLoading = true;
    forkJoin([
      this.logService.getManagerLogs(),
      this.logService.getTextLogs(),
      this.logService.getImageLogs(),
    ]).subscribe(([manager, text, image]: LogsResponse[]) => {
      this.logs = [...manager.logs, ...text.logs, ...image.logs]
        .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
      console.log('[All Logs]', this.logs);
      this.isLoading = false;
    });
  }

  loadManagerLogs() {
    this.activeFilter = 'manager';
    this.isLoading = true;
    this.logService.getManagerLogs().subscribe((response: LogsResponse) => {
      this.logs = response.logs;
      console.log('[Manager Logs]', response);
      this.isLoading = false;
    });
  }

  loadTextLogs() {
    this.activeFilter = 'text';
    this.isLoading = true;
    this.logService.getTextLogs().subscribe((response: LogsResponse) => {
      this.logs = response.logs;
      console.log('[Text Logs]', response);
      this.isLoading = false;
    });
  }

  loadImageLogs() {
    this.activeFilter = 'image';
    this.isLoading = true;
    this.logService.getImageLogs().subscribe((response: LogsResponse) => {
      this.logs = response.logs;
      console.log('[Image Logs]', response);
      this.isLoading = false;
    });
  }
}
