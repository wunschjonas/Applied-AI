import { DatePipe } from '@angular/common';
import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { PostFacade } from '../../facades/post.facade';

@Component({
  selector: 'app-post-context',
  standalone: true,
  imports: [RouterLink, DatePipe],
  templateUrl: './post-context.component.html',
  styleUrls: ['./post-context.component.scss'],
})
export class PostContextComponent {
  public postFacade = inject(PostFacade);
}
