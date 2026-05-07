import { useState, useEffect } from 'react'

type Theme = 'light' | 'dark'

const COOKIE_KEY = 'mailsort-theme'
const COOKIE_MAX_AGE = 365 * 24 * 60 * 60

function readCookie(): Theme | null {
  const match = document.cookie.match(new RegExp('(?:^|;\\s*)' + COOKIE_KEY + '=([^;]*)'))
  const val = match?.[1]
  return val === 'dark' || val === 'light' ? val : null
}

function writeCookie(theme: Theme) {
  document.cookie = `${COOKIE_KEY}=${theme};max-age=${COOKIE_MAX_AGE};path=/;SameSite=Lax`
}

function getInitialTheme(): Theme {
  const saved = readCookie()
  if (saved) return saved
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(getInitialTheme)

  useEffect(() => {
    const root = document.documentElement
    root.classList.remove('light', 'dark')
    root.classList.add(theme)
    writeCookie(theme)
  }, [theme])

  const toggle = () => setTheme(t => (t === 'dark' ? 'light' : 'dark'))

  return { theme, toggle }
}
