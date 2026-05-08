import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// Backend returns naive UTC timestamps without 'Z' — append it so JS parses correctly
export function parseUTC(s: string): Date {
  return new Date(s.endsWith('Z') || s.includes('+') ? s : s + 'Z')
}
