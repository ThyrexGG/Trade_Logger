import AsyncStorage from '@react-native-async-storage/async-storage'
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ActivityIndicator,
  Alert,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { getAIStatus, postAIChat } from '../api/ai'
import { SimpleMarkdown } from '../components/SimpleMarkdown'
import { colors, radius, spacing } from '../theme'
import type { AIUsage } from '../types/ai'

interface Turn {
  id: string
  role: 'user' | 'assistant'
  content: string
  error?: boolean
}

const STORE_KEY = 'tl.assistant.history.v1'
const STORE_CAP = 60
const MAX_HISTORY = 18

const SUGGESTIONS = [
  'How did I perform today?',
  "Why is today's P&L negative?",
  'What are my strongest and weakest symbols?',
  'Summarize my current market context.',
]

let counter = 0
const nextId = () => `t${Date.now()}-${counter++}`

/** Read-only analytical chat over your TradeLogger data. It can explain and analyse — it can never place a trade. */
export function AssistantScreen() {
  const [turns, setTurns] = useState<Turn[]>([])
  const [loaded, setLoaded] = useState(false)
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const [configured, setConfigured] = useState<boolean | null>(null)
  const [usage, setUsage] = useState<AIUsage | null>(null)
  const list = useRef<FlatList<Turn>>(null)
  const abort = useRef<AbortController | null>(null)

  useEffect(() => {
    AsyncStorage.getItem(STORE_KEY)
      .then((raw) => {
        if (!raw) return
        const parsed = JSON.parse(raw) as Turn[]
        if (Array.isArray(parsed)) setTurns(parsed.filter((t) => t && typeof t.content === 'string').slice(-STORE_CAP))
      })
      .catch(() => {})
      .finally(() => setLoaded(true))
    getAIStatus()
      .then((s) => {
        setConfigured(s.configured)
        if (s.usage) setUsage(s.usage)
      })
      .catch(() => setConfigured(null))
    return () => abort.current?.abort()
  }, [])

  useEffect(() => {
    if (!loaded) return
    AsyncStorage.setItem(STORE_KEY, JSON.stringify(turns.slice(-STORE_CAP))).catch(() => {})
  }, [turns, loaded])

  useEffect(() => {
    const t = setTimeout(() => list.current?.scrollToEnd({ animated: true }), 60)
    return () => clearTimeout(t)
  }, [turns.length, sending])

  const ask = useCallback(async (text: string, base: Turn[]) => {
    abort.current?.abort()
    const controller = new AbortController()
    abort.current = controller
    setSending(true)
    const history = [...base, { id: 'x', role: 'user' as const, content: text }]
      .slice(-MAX_HISTORY)
      .map((t) => ({ role: t.role, content: t.content }))
    try {
      const res = await postAIChat(history, controller.signal)
      if (controller.signal.aborted) return
      if (res.usage) setUsage(res.usage)
      setTurns((prev) => [
        ...prev,
        res.ok && res.reply
          ? { id: nextId(), role: 'assistant', content: res.reply }
          : { id: nextId(), role: 'assistant', content: res.error ?? 'The assistant could not respond.', error: true },
      ])
    } catch (err) {
      if (controller.signal.aborted) return
      setTurns((prev) => [
        ...prev,
        {
          id: nextId(),
          role: 'assistant',
          content: err instanceof Error ? err.message : 'Could not reach the assistant.',
          error: true,
        },
      ])
    } finally {
      if (!controller.signal.aborted) setSending(false)
    }
  }, [])

  function send(text: string) {
    const t = text.trim()
    if (!t || sending) return
    setDraft('')
    const base = turns
    setTurns([...base, { id: nextId(), role: 'user', content: t }])
    void ask(t, base)
  }

  function retry() {
    if (sending) return
    const trimmed = turns[turns.length - 1]?.error ? turns.slice(0, -1) : turns
    const last = trimmed[trimmed.length - 1]
    if (!last || last.role !== 'user') return
    const base = trimmed.slice(0, -1)
    setTurns(trimmed)
    void ask(last.content, base)
  }

  function clear() {
    Alert.alert('Clear this conversation?', 'This only removes it from this phone.', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Clear',
        style: 'destructive',
        onPress: () => {
          abort.current?.abort()
          setSending(false)
          setTurns([])
        },
      },
    ])
  }

  const lastIsError = turns[turns.length - 1]?.error === true

  return (
    <SafeAreaView style={styles.screen} edges={['bottom']}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined} keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}>
        <View style={styles.topBar}>
          <Text style={styles.topText} numberOfLines={1}>
            {configured === false
              ? 'Assistant is not set up on the server'
              : usage
                ? `${usage.day_requests}/${usage.day_budget} messages used today`
                : 'Read-only — it can analyse, never trade'}
          </Text>
          {turns.length > 0 ? (
            <Pressable onPress={clear} hitSlop={10} accessibilityRole="button">
              <Text style={styles.clear}>Clear</Text>
            </Pressable>
          ) : null}
        </View>

        <FlatList
          ref={list}
          data={turns}
          keyExtractor={(t) => t.id}
          contentContainerStyle={styles.list}
          keyboardShouldPersistTaps="handled"
          ListEmptyComponent={
            loaded ? (
              <View style={styles.empty}>
                <Text style={styles.emptyTitle}>Ask about your trading</Text>
                <Text style={styles.emptySub}>Answers use your journal, positions and analytics. Try one:</Text>
                {SUGGESTIONS.map((s) => (
                  <Pressable key={s} onPress={() => send(s)} style={styles.suggest} accessibilityRole="button">
                    <Text style={styles.suggestText}>{s}</Text>
                  </Pressable>
                ))}
              </View>
            ) : null
          }
          renderItem={({ item }) =>
            item.role === 'user' ? (
              <View style={styles.userBubble}>
                <Text style={styles.userText}>{item.content}</Text>
              </View>
            ) : (
              <View style={[styles.botBubble, item.error && styles.botError]}>
                <SimpleMarkdown text={item.content} color={item.error ? colors.negative : colors.textPrimary} />
              </View>
            )
          }
          ListFooterComponent={
            sending ? (
              <View style={styles.thinking}>
                <ActivityIndicator color={colors.accent} size="small" />
                <Text style={styles.thinkingText}>Thinking…</Text>
              </View>
            ) : lastIsError ? (
              <Pressable onPress={retry} style={styles.retry} accessibilityRole="button">
                <Text style={styles.retryText}>Try again</Text>
              </Pressable>
            ) : null
          }
        />

        <View style={styles.composer}>
          <TextInput
            value={draft}
            onChangeText={setDraft}
            placeholder="Ask about your trades…"
            placeholderTextColor={colors.textMuted}
            multiline
            maxLength={2000}
            style={styles.input}
          />
          <Pressable
            onPress={() => send(draft)}
            disabled={sending || !draft.trim()}
            style={[styles.send, (sending || !draft.trim()) && { opacity: 0.4 }]}
            accessibilityRole="button"
            accessibilityLabel="Send"
          >
            <Text style={styles.sendText}>Send</Text>
          </Pressable>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  topBar: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: spacing.lg, paddingVertical: spacing.sm },
  topText: { color: colors.textMuted, fontSize: 12, flexShrink: 1 },
  clear: { color: colors.accent, fontSize: 13, fontWeight: '600' },
  list: { padding: spacing.lg, gap: spacing.md, flexGrow: 1 },
  empty: { gap: spacing.sm, paddingTop: spacing.lg },
  emptyTitle: { color: colors.textPrimary, fontSize: 20, fontWeight: '700' },
  emptySub: { color: colors.textMuted, fontSize: 13, marginBottom: spacing.sm },
  suggest: { borderColor: colors.border, borderWidth: 1, backgroundColor: colors.surface, borderRadius: radius.lg, padding: spacing.md },
  suggestText: { color: colors.textSecondary, fontSize: 14 },
  userBubble: { alignSelf: 'flex-end', maxWidth: '85%', backgroundColor: 'rgba(240,185,11,0.16)', borderRadius: radius.lg, padding: spacing.md },
  userText: { color: colors.textPrimary, fontSize: 15, lineHeight: 21 },
  botBubble: { alignSelf: 'flex-start', maxWidth: '95%', backgroundColor: colors.surface, borderColor: colors.border, borderWidth: 1, borderRadius: radius.lg, padding: spacing.md },
  botError: { borderColor: 'rgba(239,68,68,0.4)', backgroundColor: 'rgba(239,68,68,0.08)' },
  thinking: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingVertical: spacing.sm },
  thinkingText: { color: colors.textMuted, fontSize: 13 },
  retry: { alignSelf: 'flex-start', borderColor: colors.border, borderWidth: 1, borderRadius: radius.md, paddingHorizontal: spacing.lg, paddingVertical: spacing.sm },
  retryText: { color: colors.accent, fontWeight: '600' },
  composer: { flexDirection: 'row', alignItems: 'flex-end', gap: spacing.sm, padding: spacing.md, borderTopColor: colors.borderSubtle, borderTopWidth: 1 },
  input: {
    flex: 1,
    maxHeight: 120,
    color: colors.textPrimary,
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.lg,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    fontSize: 15,
  },
  send: { backgroundColor: colors.accent, borderRadius: radius.lg, paddingHorizontal: spacing.lg, paddingVertical: spacing.md },
  sendText: { color: '#000', fontWeight: '700' },
})
