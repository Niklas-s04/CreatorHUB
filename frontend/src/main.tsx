import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router'
import App from './App'
import { queryClient } from './shared/api/queryClient'
import { ToastProvider } from './shared/ui/toast/ToastProvider'
import { initializeTheme } from './shared/theme/ThemeContext'
import { ThemeProvider } from './shared/theme/ThemeProvider'
import './styles.css'

initializeTheme()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </ToastProvider>
      </QueryClientProvider>
    </ThemeProvider>
  </React.StrictMode>
)
