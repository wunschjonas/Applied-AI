import { Component } from '@angular/core';
import { SidebarComponent } from '../../components/sidebar/sidebar.component';

@Component({
  selector: 'app-image-agent',
  standalone: true,
  imports: [SidebarComponent],
  templateUrl: './image-agent.component.html',
  styleUrls: ['./image-agent.component.scss'],
})
export class ImageAgentComponent {}
