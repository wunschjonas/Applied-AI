import { Component } from '@angular/core';
import { SidebarComponent } from '../../components/sidebar/sidebar.component';

@Component({
  selector: 'app-text-agent',
  standalone: true,
  imports: [SidebarComponent],
  templateUrl: './text-agent.component.html',
  styleUrls: ['./text-agent.component.scss'],
})
export class TextAgentComponent {}
