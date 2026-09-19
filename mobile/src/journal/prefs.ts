import AsyncStorage from '@react-native-async-storage/async-storage'
import type { DateFilter } from './filters'

const DATE_KEY = 'tl.journal.dateFilter'
const ACCOUNT_KEY = 'tl.journal.account'

export interface JournalPrefs {
  dateFilter: DateFilter
  account: string
}

const DEFAULTS: JournalPrefs = { dateFilter: 'week', account: 'ALL' }

/** The remembered filter choices (same defaults as the web: This week, all accounts). */
export async function loadPrefs(): Promise<JournalPrefs> {
  try {
    const [d, a] = await Promise.all([AsyncStorage.getItem(DATE_KEY), AsyncStorage.getItem(ACCOUNT_KEY)])
    return {
      dateFilter: d === 'today' || d === 'month' || d === 'all' || d === 'week' ? d : DEFAULTS.dateFilter,
      account: a || DEFAULTS.account,
    }
  } catch {
    return DEFAULTS
  }
}

export function savePref(key: 'dateFilter' | 'account', value: string): void {
  AsyncStorage.setItem(key === 'dateFilter' ? DATE_KEY : ACCOUNT_KEY, value).catch(() => {
    /* the choice just won't stick */
  })
}
