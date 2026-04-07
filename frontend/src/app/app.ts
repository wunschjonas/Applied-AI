import { Component, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';

@Component({
  selector: 'app-root',
  imports: [],
  templateUrl: './app.html',
  styleUrl: './app.css'
})
export class App {
  message = signal('Welcome to Angular!');
  data = signal('');

  constructor(private http: HttpClient) {}

  loadData() {
    this.http.get('http://localhost:8080/api/data').subscribe({
      next: (response: any) => this.data.set(response.data),
      error: (error) => this.data.set('Error loading data')
    });
  }
}
