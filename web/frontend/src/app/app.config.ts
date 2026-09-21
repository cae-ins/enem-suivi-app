import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { HttpInterceptorFn, provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideRouter } from '@angular/router';
import { routes } from './app.routes';

const authInterceptor: HttpInterceptorFn = (request, next) => {
  const token = sessionStorage.getItem('enem_access');
  const isApi = request.url.startsWith('/api/');
  return next(token && isApi ? request.clone({ setHeaders: { Authorization: `Bearer ${token}` } }) : request);
};

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    provideHttpClient(withInterceptors([authInterceptor])),
  ],
};
