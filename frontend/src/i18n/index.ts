// UI language: English, Hindi, Marathi. Navigation, page titles and common labels are
// translated; data (role, skill, course names) stays as stored.
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import en from '@/i18n/locales/en.json'
import hi from '@/i18n/locales/hi.json'
import mr from '@/i18n/locales/mr.json'

export const LANGUAGES = [
  { code: 'en', label: 'English' },
  { code: 'hi', label: 'हिन्दी' },
  { code: 'mr', label: 'मराठी' },
] as const

const KEY = 'kaushalsetu.language'

function saved(): string {
  try {
    return localStorage.getItem(KEY) ?? 'en'
  } catch {
    return 'en'
  }
}

void i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, hi: { translation: hi }, mr: { translation: mr } },
  lng: saved(),
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
})

i18n.on('languageChanged', (language) => {
  document.documentElement.lang = language
  try {
    localStorage.setItem(KEY, language)
  } catch {
    // Not remembered; fine.
  }
})

export default i18n
