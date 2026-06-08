import { Component, inject } from '@angular/core';
import { SidebarComponent } from '../../components/sidebar/sidebar.component';
import { LogService } from '../../services/log.service';

@Component({
  selector: 'app-logs',
  standalone: true,
  imports: [SidebarComponent],
  templateUrl: './logs.component.html',
  styleUrls: ['./logs.component.scss'],
})
export class LogsComponent {
  private readonly logService = inject(LogService);

  fetchManagerLogs() {
    this.logService.getManagerLogs().subscribe(console.log);
  }

  fetchTextLogs() {
    this.logService.getTextLogs().subscribe(console.log);
  }

  fetchImageLogs() {
    this.logService.getImageLogs().subscribe(console.log);
  }
}
