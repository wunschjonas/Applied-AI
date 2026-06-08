import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';

@Injectable({
  providedIn: 'root',
})
export class LogService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = 'http://localhost:8080';


}
