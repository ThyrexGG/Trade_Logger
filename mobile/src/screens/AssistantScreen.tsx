import { Ionicons } from '@expo/vector-icons'
import AsyncStorage from '@react-native-async-storage/async-storage'
import { useCallback, useEffect, useRef, useState } from 'react'
import { ActivityIndicator, Alert, FlatList, KeyboardAvoidingView, Platform, Pressable, StyleSheet, View } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'
import { getAIStatus, postAIChat } from '../api/ai'
import { SimpleMarkdown } from '../components/SimpleMarkdown'
import { Text, TextInput } from '../components/Text'
import { Button, Card, Row, Rows, ui } from '../components/ui'
import { colors, radius, spacing, type } from '../theme'
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
  const canSend = !sending && draft.trim().length > 0

  return (
    <SafeAreaView style={ui.screen} edges={['bottom']}>
      <KeyboardAvoidingView style={ui.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined} keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}>
        <View style={styles.topBar}>
          <Text style={styles.topText} numberOfLines={1}>
            {configured === false ? 'Ask AI is not set up on the server' : usage ? `${usage.day_requests} of ${usage.day_budget} messages used today` : 'Read-only: it can explain, never trade'}
          </Text>
          {turns.length > 0 ? <Button label="Clear" kind="ghost" size="sm" onPress={clear} /> : null}
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
                <Text style={ui.sub}>Answers use your own journal, open trades and numbers. Try one:</Text>
                <Card flush style={styles.suggestCard}>
                  <Rows>
                    {SUGGESTIONS.map((s) => (
                      <Row key={s} title={s} chevron onPress={() => send(s)} />
                    ))}
                  </Rows>
                </Card>
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
                <ActivityIndicator color={colors.textMuted} size="small" />
                <Text style={ui.muted}>Thinking…</Text>
              </View>
            ) : lastIsError ? (
              <Button label="Try again" kind="secondary" size="sm" icon="refresh-outline" onPress={retry} style={styles.retry} />
            ) : null
          }
        />

        <View style={styles.composer}>
          <TextInput value={draft} onChangeText={setDraft} placeholder="Ask about your trades…" placeholderTextColor={colors.textMuted} multiline maxLength={2000} style={styles.input} />
          <Pressable onPress={() => send(draft)} disabled={!canSend} style={[styles.send, !canSend && styles.sendOff]} accessibilityRole="button" accessibilityLabel="Send">
            <Ionicons name="arrow-up" size={20} color={canSend ? colors.accentInk : colors.textMuted} />
          </Pressable>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  topBar: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: spacing.lg, minHeight: 36 },
  topText: { ...type.small, flexShrink: 1 },
  list: { padding: spacing.lg, gap: spacing.md, flexGrow: 1 },
  empty: { gap: spacing.sm, paddingTop: spacing.md },
  emptyTitle: { ...type.title, fontSize: 20, lineHeight: 26 },
  suggestCard: { marginTop: spacing.sm },
  userBubble: { alignSelf: 'flex-end', maxWidth: '85%', backgroundColor: colors.surfaceElevated, borderColor: colors.border, borderWidth: 1, borderRadius: radius.lg, paddingHorizontal: spacing.md, paddingVertical: 10 },
  userText: { ...type.body, fontSize: 15, lineHeight: 21 },
  botBubble: { alignSelf: 'flex-start', maxWidth: '96%' },
  botError: { borderColor: colors.negativeLine, backgroundColor: colors.negativeSoft, borderWidth: 1, borderRadius: radius.lg, padding: spacing.md },
  thinking: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingVertical: spacing.sm },
  retry: { alignSelf: 'flex-start' },
  composer: { flexDirection: 'row', alignItems: 'flex-end', gap: spacing.sm, paddingHorizontal: spacing.lg, paddingVertical: spacing.md, borderTopColor: colors.borderSubtle, borderTopWidth: 1 },
  input: {
    flex: 1,
    maxHeight: 120,
    minHeight: 44,
    color: colors.textPrimary,
    backgroundColor: colors.surfaceElevated,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.lg,
    paddingHorizontal: spacing.md,
    paddingVertical: 11,
    fontSize: 15,
  },
  send: { width: 44, height: 44, borderRadius: radius.lg, backgroundColor: colors.accent, alignItems: 'center', justifyContent: 'center' },
  sendOff: { backgroundColor: colors.surfaceElevated },
})
