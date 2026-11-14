import { Ionicons } from '@expo/vector-icons'
import { Children, Fragment, isValidElement, type ReactElement, type ReactNode } from 'react'
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  View,
  type KeyboardTypeOptions,
  type StyleProp,
  type TextStyle,
  type ViewStyle,
} from 'react-native'
import { isBuy } from '../format'
import { colors, pnlColor, radius, spacing, type } from '../theme'
import { Text, TextInput } from './Text'

/**
 * The phone's component kit — the same pieces as the web's kit.css (docs/DESIGN_SYSTEM.md §6).
 * Every screen is built from these, so a change here changes the whole app. Rules they encode:
 *   - depth is a lightness step plus a hairline, never a shadow or a glow
 *   - figures sit together in ONE divided panel (Figures), not a grid of little boxes
 *   - lists are rows divided by hairlines inside one card (Rows), not a stack of separate cards
 *   - one primary button per screen; everything else is secondary (neutral) or ghost
 *   - cyan means "you can act here / this is now"; green and red are for money only
 */

export type IconName = keyof typeof Ionicons.glyphMap

// --------------------------------------------------------------------------- screen header

/** Title block of a tab screen: small mono eyebrow, title, one plain line, actions on the right. */
export function ScreenHeader({ eyebrow, title, sub, right }: { eyebrow?: string; title: string; sub?: string; right?: ReactNode }) {
  return (
    <View style={styles.header}>
      <View style={styles.headerText}>
        {eyebrow ? <Text style={styles.eyebrow}>{eyebrow}</Text> : null}
        <Text style={styles.title} numberOfLines={1}>
          {title}
        </Text>
        {sub ? (
          <Text style={styles.headerSub} numberOfLines={2}>
            {sub}
          </Text>
        ) : null}
      </View>
      {right ? <View style={styles.headerRight}>{right}</View> : null}
    </View>
  )
}

// --------------------------------------------------------------------------- cards

/**
 * The standard panel. `feature` marks the ONE card on a screen that matters most (a cyan edge).
 * `flush` removes the body padding, for cards whose children are full-width rows.
 */
export function Card({
  title,
  right,
  action,
  feature,
  flush,
  children,
  style,
}: {
  title?: string
  right?: string
  action?: ReactNode
  feature?: boolean
  flush?: boolean
  children?: ReactNode
  style?: StyleProp<ViewStyle>
}) {
  return (
    <View style={[styles.card, feature && styles.cardFeature, style]}>
      {title ? (
        <View style={[styles.cardHead, flush && styles.cardHeadFlush]}>
          <Text style={styles.cardTitle} numberOfLines={1}>
            {title}
          </Text>
          {right ? (
            <Text style={styles.cardRight} numberOfLines={1}>
              {right}
            </Text>
          ) : null}
          {action}
        </View>
      ) : null}
      {flush ? children : <View style={[styles.cardBody, title ? styles.cardBodyUnderHead : null]}>{children}</View>}
    </View>
  )
}

/** A small mono heading between cards, with a fine rule filling the row. */
export function SectionLabel({ children, right, style }: { children: ReactNode; right?: string; style?: StyleProp<ViewStyle> }) {
  return (
    <View style={[styles.section, style]}>
      <Text style={styles.label}>{children}</Text>
      <View style={styles.rule} />
      {right ? <Text style={styles.label}>{right}</Text> : null}
    </View>
  )
}

export function Label({ children, style }: { children: ReactNode; style?: StyleProp<TextStyle> }) {
  return <Text style={[styles.label, style]}>{children}</Text>
}

// --------------------------------------------------------------------------- figures

/**
 * A row (or grid) of statistics as one divided panel. Put it inside a `flush` Card, or use `boxed` to give
 * it its own panel. Children are <Stat>s; they are laid out `columns` per line with hairlines between.
 */
export function Figures({ children, columns = 2, boxed, style }: { children: ReactNode; columns?: number; boxed?: boolean; style?: StyleProp<ViewStyle> }) {
  const cells = Children.toArray(children).filter(isValidElement) as ReactElement[]
  const lines: ReactElement[][] = []
  for (let i = 0; i < cells.length; i += columns) lines.push(cells.slice(i, i + columns))
  return (
    <View style={[boxed && styles.card, style]}>
      {lines.map((line, li) => (
        <View key={li} style={[styles.figLine, li > 0 && styles.figLineTop]}>
          {line.map((cell, ci) => (
            <View key={ci} style={[styles.figCell, ci > 0 && styles.figCellLeft, { flex: (cell.props as { flex?: number }).flex ?? 1 }]}>
              {cell}
            </View>
          ))}
          {/* keep a short last line aligned to the grid */}
          {line.length < columns ? Array.from({ length: columns - line.length }, (_, k) => <View key={`pad-${k}`} style={[styles.figCell, styles.figCellLeft]} />) : null}
        </View>
      ))}
    </View>
  )
}

/** `tight` narrows the side padding for four-across rows; `flex` (read by Figures) makes one cell wider than its neighbours. */
export function Stat({ label, value, sub, color, small, tight }: { label: string; value: string; sub?: string; color?: string; small?: boolean; tight?: boolean; flex?: number }) {
  return (
    <View style={[styles.stat, tight && styles.statTight]}>
      <Text style={styles.label} numberOfLines={1}>
        {label}
      </Text>
      <Text style={[small ? styles.statValueSmall : styles.statValue, color ? { color } : null]} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.7}>
        {value}
      </Text>
      {sub ? (
        <Text style={styles.statSub} numberOfLines={2}>
          {sub}
        </Text>
      ) : null}
    </View>
  )
}

// --------------------------------------------------------------------------- rows

/** Children separated by hairlines — the body of a list card. Use inside a `flush` Card. */
export function Rows({ children, inset = spacing.lg }: { children: ReactNode; inset?: number }) {
  const items = Children.toArray(children).filter(Boolean)
  return (
    <View>
      {items.map((child, i) => (
        <Fragment key={i}>
          {i > 0 ? <View style={[styles.divider, { marginLeft: inset }]} /> : null}
          {child}
        </Fragment>
      ))}
    </View>
  )
}

export function Divider({ inset = 0 }: { inset?: number }) {
  return <View style={[styles.divider, { marginLeft: inset }]} />
}

/** A tappable list row: optional icon, title + one line under it, something on the right, a chevron when it navigates. */
export function Row({
  icon,
  title,
  sub,
  right,
  chevron,
  onPress,
  children,
}: {
  icon?: IconName
  title?: string
  sub?: string
  right?: ReactNode
  chevron?: boolean
  onPress?: () => void
  children?: ReactNode
}) {
  const body = (
    <>
      {icon ? (
        <View style={styles.rowIcon}>
          <Ionicons name={icon} size={18} color={colors.textSecondary} />
        </View>
      ) : null}
      <View style={styles.rowText}>
        {title ? <Text style={styles.rowTitle}>{title}</Text> : null}
        {sub ? <Text style={styles.rowSub}>{sub}</Text> : null}
        {children}
      </View>
      {right}
      {chevron ? <Ionicons name="chevron-forward" size={16} color={colors.textMuted} /> : null}
    </>
  )
  if (!onPress) return <View style={styles.row}>{body}</View>
  return (
    <Pressable onPress={onPress} accessibilityRole="button" style={({ pressed }) => [styles.row, pressed && styles.pressed]}>
      {body}
    </Pressable>
  )
}

/** "Label ........ value" line. Stack them inside <Rows inset={0}> for a facts table. */
export function Fact({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <View style={styles.fact}>
      <Text style={styles.factLabel}>{label}</Text>
      <Text style={[styles.factValue, color ? { color } : null]} numberOfLines={1}>
        {value}
      </Text>
    </View>
  )
}

/**
 * Expert detail behind a toggle (the web's MoreDetails): the plain summary stays on screen, the rest opens on tap.
 * Works inside a `flush` Card (it draws its own top hairline) or on its own.
 */
export function MoreDetails({ label = 'More details', hint, open, onToggle, children }: { label?: string; hint?: string; open: boolean; onToggle: () => void; children: ReactNode }) {
  return (
    <View style={styles.more}>
      <Pressable onPress={onToggle} accessibilityRole="button" accessibilityState={{ expanded: open }} style={({ pressed }) => [styles.moreHead, pressed && styles.pressed]}>
        <Text style={styles.moreLabel}>{label}</Text>
        {hint && !open ? (
          <Text style={styles.moreHint} numberOfLines={1}>
            {hint}
          </Text>
        ) : (
          <View style={{ flex: 1 }} />
        )}
        <Ionicons name={open ? 'chevron-up' : 'chevron-down'} size={15} color={colors.textMuted} />
      </Pressable>
      {open ? children : null}
    </View>
  )
}

// --------------------------------------------------------------------------- small marks

/** Outlined tag in a given colour (account names, exits, status). */
export function Pill({ text, color }: { text: string; color: string }) {
  return (
    <View style={[styles.pill, { borderColor: color === colors.textSecondary ? colors.border : color }]}>
      <Text style={[styles.pillText, { color }]} numberOfLines={1}>
        {text}
      </Text>
    </View>
  )
}

/** Quiet filled tag (setup tags, note tags). */
export function Tag({ text }: { text: string }) {
  return (
    <View style={styles.tag}>
      <Text style={styles.tagText} numberOfLines={1}>
        {text}
      </Text>
    </View>
  )
}

/** Trade direction: an arrow plus the word, so colour is not the only signal. */
export function DirTag({ direction }: { direction: string }) {
  const buy = isBuy(direction)
  const color = buy ? colors.positive : colors.negative
  return (
    <View style={styles.dir}>
      <Ionicons name={buy ? 'arrow-up' : 'arrow-down'} size={11} color={color} />
      <Text style={[styles.dirText, { color }]}>{direction.toUpperCase()}</Text>
    </View>
  )
}

/** The cyan "this is live now" dot. */
export function LiveDot({ size = 7 }: { size?: number }) {
  return <View style={{ width: size, height: size, borderRadius: size, backgroundColor: colors.accent }} />
}

/** Signed money in green / red / neutral. */
export function Money({ value, text, style }: { value: number; text: string; style?: StyleProp<TextStyle> }) {
  return <Text style={[styles.money, style, { color: pnlColor(value) }]}>{text}</Text>
}

/** A budget bar: green while comfortable, amber from 80% of the limit, red once it is reached. */
export function Bar({ ratio, warnAt = 0.8 }: { ratio: number | null | undefined; warnAt?: number }) {
  const r = Math.max(0, Math.min(1, ratio ?? 0))
  const color = r >= 1 ? colors.negative : r >= warnAt ? colors.warning : colors.positive
  return (
    <View style={styles.barTrack} accessibilityRole="progressbar" accessibilityValue={{ min: 0, max: 100, now: Math.round(r * 100) }}>
      <View style={[styles.barFill, { width: `${r * 100}%`, backgroundColor: color }]} />
    </View>
  )
}

// --------------------------------------------------------------------------- controls

/**
 * primary: the one main action of a screen (cyan fill). secondary: neutral. ghost: text only.
 * danger: destructive. `size="sm"` is the compact one for headers and inline actions.
 */
export function Button({
  label,
  onPress,
  busy,
  disabled,
  kind = 'primary',
  size = 'md',
  icon,
  style,
}: {
  label: string
  onPress: () => void
  busy?: boolean
  disabled?: boolean
  kind?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'md' | 'sm'
  icon?: IconName
  style?: StyleProp<ViewStyle>
}) {
  const off = busy || disabled
  const ink = kind === 'primary' ? colors.accentInk : kind === 'danger' ? colors.negative : kind === 'ghost' ? colors.accent : colors.textPrimary
  return (
    <Pressable
      onPress={onPress}
      disabled={off}
      accessibilityRole="button"
      accessibilityState={{ disabled: !!off, busy: !!busy }}
      style={({ pressed }) => [
        styles.btn,
        size === 'sm' && styles.btnSm,
        kind === 'primary' ? styles.btnPrimary : kind === 'danger' ? styles.btnDanger : kind === 'ghost' ? styles.btnGhost : styles.btnSecondary,
        off && styles.off,
        pressed && styles.btnPressed,
        style,
      ]}
    >
      {busy ? (
        <ActivityIndicator size="small" color={ink} />
      ) : (
        <>
          {icon ? <Ionicons name={icon} size={size === 'sm' ? 14 : 16} color={ink} /> : null}
          <Text style={[size === 'sm' ? styles.btnTextSm : styles.btnText, { color: ink }]} numberOfLines={1}>
            {label}
          </Text>
        </>
      )}
    </Pressable>
  )
}

/** A setting with a switch: what it is, one plain line about it, the switch on the right. Use inside a `flush` Card. */
export function ToggleRow({ title, sub, value, onChange, disabled, busy }: { title: string; sub?: string; value: boolean; onChange: (v: boolean) => void; disabled?: boolean; busy?: boolean }) {
  return (
    <View style={styles.toggle}>
      <View style={styles.rowText}>
        <Text style={styles.rowTitle}>{title}</Text>
        {sub ? <Text style={styles.rowSub}>{sub}</Text> : null}
      </View>
      {busy ? (
        <ActivityIndicator color={colors.accent} style={styles.toggleSpinner} />
      ) : (
        <Switch
          value={value}
          onValueChange={onChange}
          disabled={disabled}
          accessibilityLabel={title}
          trackColor={{ true: colors.accent, false: colors.surfaceElevated }}
          thumbColor={colors.textPrimary}
          ios_backgroundColor={colors.surfaceElevated}
        />
      )}
    </View>
  )
}

/** Filter chip. */
export function Chip({ label, on, onPress }: { label: string; on: boolean; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} accessibilityRole="button" accessibilityState={{ selected: on }} style={[styles.chip, on && styles.chipOn]}>
      <Text style={[styles.chipText, on && styles.chipTextOn]} numberOfLines={1}>
        {label}
      </Text>
    </Pressable>
  )
}

/** One line of chips that scrolls sideways (edge to edge; `inset` is the screen gutter). */
export function ChipRow({ children, inset = spacing.lg, wrap }: { children: ReactNode; inset?: number; wrap?: boolean }) {
  if (wrap) return <View style={styles.chipWrap}>{children}</View>
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginHorizontal: -inset, flexGrow: 0 }} contentContainerStyle={[styles.chipRow, { paddingHorizontal: inset }]}>
      {children}
    </ScrollView>
  )
}

/** Segmented control: a few exclusive choices in one track. */
export function Seg<T extends string>({ options, value, onChange }: { options: readonly { key: T; label: string }[]; value: T; onChange: (key: T) => void }) {
  return (
    <View style={styles.seg} accessibilityRole="tablist">
      {options.map((o) => {
        const on = o.key === value
        return (
          <Pressable key={o.key} onPress={() => onChange(o.key)} accessibilityRole="tab" accessibilityState={{ selected: on }} style={[styles.segItem, on && styles.segItemOn]}>
            <Text style={[styles.segText, on && styles.segTextOn]} numberOfLines={1}>
              {o.label}
            </Text>
          </Pressable>
        )
      })}
    </View>
  )
}

export function Field({
  label,
  value,
  onChangeText,
  placeholder,
  keyboardType,
  secure,
  half,
  autoCapitalize = 'none',
  hint,
  error,
  multiline,
  maxLength,
}: {
  label: string
  value: string
  onChangeText: (t: string) => void
  placeholder?: string
  keyboardType?: KeyboardTypeOptions
  secure?: boolean
  half?: boolean
  autoCapitalize?: 'none' | 'characters' | 'sentences'
  hint?: string
  /** shown under the field in red, with a red edge on the input */
  error?: string
  multiline?: boolean
  maxLength?: number
}) {
  return (
    <View style={[styles.field, half && { flex: 1 }]}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <TextInput
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={colors.textMuted}
        keyboardType={keyboardType}
        secureTextEntry={secure}
        autoCapitalize={autoCapitalize}
        autoCorrect={false}
        autoComplete="off"
        multiline={multiline}
        maxLength={maxLength}
        textAlignVertical={multiline ? 'top' : undefined}
        scrollEnabled={multiline ? false : undefined}
        style={[styles.input, multiline && styles.inputMultiline, error ? styles.inputError : null]}
      />
      {error ? <Text style={styles.fieldError}>{error}</Text> : hint ? <Text style={styles.hint}>{hint}</Text> : null}
    </View>
  )
}

// --------------------------------------------------------------------------- states

const TONE = {
  error: { bg: colors.negativeSoft, line: colors.negativeLine, ink: colors.negative, icon: 'alert-circle-outline' },
  warn: { bg: colors.warningSoft, line: colors.warningLine, ink: colors.warning, icon: 'warning-outline' },
  info: { bg: colors.infoSoft, line: colors.infoLine, ink: colors.info, icon: 'information-circle-outline' },
  ok: { bg: colors.positiveSoft, line: colors.positiveLine, ink: colors.positive, icon: 'checkmark-circle-outline' },
} as const

/** An inline message: something failed, needs attention, or worked. Tappable when `onPress` is given. */
export function Notice({ tone = 'error', children, onPress, style }: { tone?: keyof typeof TONE; children: ReactNode; onPress?: () => void; style?: StyleProp<ViewStyle> }) {
  const t = TONE[tone]
  const body = (
    <>
      <Ionicons name={t.icon} size={16} color={t.ink} style={styles.noticeIcon} />
      <Text style={[styles.noticeText, { color: t.ink }]}>{children}</Text>
    </>
  )
  const box = [styles.notice, { backgroundColor: t.bg, borderColor: t.line }, style]
  if (!onPress) {
    return (
      <View style={box} accessibilityRole={tone === 'error' ? 'alert' : undefined}>
        {body}
      </View>
    )
  }
  return (
    <Pressable onPress={onPress} accessibilityRole="button" style={box}>
      {body}
    </Pressable>
  )
}

/** Nothing to show yet: says what happened and what to do next. */
export function Empty({ icon = 'file-tray-outline', title, text, children }: { icon?: IconName; title: string; text?: string; children?: ReactNode }) {
  return (
    <View style={styles.empty}>
      <View style={styles.emptyIcon}>
        <Ionicons name={icon} size={20} color={colors.textMuted} />
      </View>
      <Text style={styles.emptyTitle}>{title}</Text>
      {text ? <Text style={styles.emptyText}>{text}</Text> : null}
      {children}
    </View>
  )
}

export function Loading({ fill }: { fill?: boolean }) {
  return (
    <View style={fill ? styles.loadingFill : styles.loading}>
      <ActivityIndicator color={colors.accent} />
    </View>
  )
}

/** Small centred grey line at the bottom of a screen (disclaimers, "read-only"). */
export function Footnote({ children }: { children: ReactNode }) {
  return <Text style={styles.footnote}>{children}</Text>
}

/** "12.5" -> 12.5, "" -> null, junk -> NaN (so the caller can tell "empty" from "invalid"). */
export function parseNum(s: string): number | null {
  const t = s.trim().replace(/,/g, '')
  if (!t) return null
  const n = Number(t)
  return Number.isFinite(n) ? n : NaN
}

/** Shared layout + input styles for screens that lay out their own content. */
export const ui = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  flex: { flex: 1, minWidth: 0 },
  /** scroll content of a screen */
  content: { paddingHorizontal: spacing.lg, paddingTop: spacing.sm, paddingBottom: spacing.xxl, gap: spacing.md },
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  rowBetween: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.md },
  rowWrap: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: spacing.sm },
  cols: { flexDirection: 'row', gap: spacing.md },
  input: {
    backgroundColor: colors.surfaceElevated,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: 11,
    color: colors.textPrimary,
    fontSize: 15,
  },
  inputMultiline: { minHeight: 88, lineHeight: 21 },
  fieldLabel: { ...type.small, color: colors.textSecondary },
  body: { ...type.body },
  sub: { ...type.sub },
  muted: { ...type.small },
  heading: { ...type.heading },
  num: { ...type.num },
  hero: { ...type.hero },
})

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'space-between', gap: spacing.md, paddingHorizontal: spacing.lg, paddingTop: spacing.md, paddingBottom: spacing.md },
  headerText: { flexShrink: 1, gap: 2 },
  headerRight: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingBottom: 2 },
  eyebrow: { ...type.label, color: colors.accent },
  title: { ...type.title },
  headerSub: { ...type.small },

  card: { backgroundColor: colors.surface, borderColor: colors.border, borderWidth: 1, borderRadius: radius.lg, overflow: 'hidden' },
  cardFeature: { borderColor: colors.accentLine },
  cardHead: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, paddingHorizontal: spacing.lg, paddingTop: spacing.md + 2 },
  cardHeadFlush: { paddingBottom: spacing.md, borderBottomWidth: 1, borderBottomColor: colors.borderSubtle },
  cardTitle: { ...type.heading, fontSize: 14, flex: 1 },
  cardRight: { ...type.label, textTransform: 'none', letterSpacing: 0.2, flexShrink: 1 },
  cardBody: { padding: spacing.lg, gap: spacing.sm },
  cardBodyUnderHead: { paddingTop: spacing.md },

  section: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, marginTop: spacing.sm },
  rule: { flex: 1, height: 1, backgroundColor: colors.borderSubtle },
  label: { ...type.label },

  figLine: { flexDirection: 'row' },
  figLineTop: { borderTopWidth: 1, borderTopColor: colors.borderSubtle },
  figCell: { flex: 1, minWidth: 0 },
  figCellLeft: { borderLeftWidth: 1, borderLeftColor: colors.borderSubtle },
  stat: { paddingHorizontal: spacing.lg, paddingVertical: spacing.md, gap: 3 },
  statTight: { paddingHorizontal: spacing.md },
  statValue: { ...type.figure },
  statValueSmall: { ...type.figure, fontSize: 15, lineHeight: 20 },
  statSub: { ...type.small, fontSize: 11, lineHeight: 15 },

  divider: { height: 1, backgroundColor: colors.borderSubtle },
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, paddingHorizontal: spacing.lg, paddingVertical: 13, minHeight: 52 },
  pressed: { backgroundColor: colors.surfaceHover },
  rowIcon: { width: 32, height: 32, borderRadius: radius.md, backgroundColor: colors.surfaceElevated, alignItems: 'center', justifyContent: 'center' },
  rowText: { flex: 1, gap: 2, minWidth: 0 },
  rowTitle: { ...type.heading, fontWeight: '500' },
  rowSub: { ...type.small },
  more: { borderTopWidth: 1, borderTopColor: colors.borderSubtle },
  moreHead: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, paddingHorizontal: spacing.lg, minHeight: 44 },
  moreLabel: { ...type.sub, fontWeight: '500', color: colors.textSecondary },
  moreHint: { ...type.small, flex: 1, textAlign: 'right' },
  toggle: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, paddingHorizontal: spacing.lg, paddingVertical: spacing.md },
  toggleSpinner: { width: 51 },
  fact: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: spacing.lg, paddingVertical: 11, paddingHorizontal: spacing.lg },
  factLabel: { ...type.sub, color: colors.textMuted },
  factValue: { ...type.num, flexShrink: 1 },

  pill: { borderWidth: 1, borderRadius: radius.sm, paddingHorizontal: 6, paddingVertical: 1, maxWidth: '100%' },
  pillText: { fontSize: 11, lineHeight: 16, fontWeight: '500' },
  tag: { backgroundColor: colors.surfaceElevated, borderRadius: radius.sm, paddingHorizontal: 7, paddingVertical: 2, maxWidth: '100%' },
  tagText: { fontSize: 11, lineHeight: 16, color: colors.textSecondary },
  dir: { flexDirection: 'row', alignItems: 'center', gap: 2 },
  dirText: { fontSize: 11, lineHeight: 16, fontWeight: '500', letterSpacing: 0.4, fontVariant: ['tabular-nums'] },
  money: { ...type.num, fontWeight: '600' },
  barTrack: { height: 6, borderRadius: radius.pill, backgroundColor: colors.surfaceElevated, overflow: 'hidden' },
  barFill: { height: 6, borderRadius: radius.pill },

  btn: { flexDirection: 'row', gap: spacing.sm, borderRadius: radius.md, alignItems: 'center', justifyContent: 'center', minHeight: 46, paddingHorizontal: spacing.lg, borderWidth: 1 },
  btnSm: { minHeight: 36, paddingHorizontal: spacing.md, gap: 6 },
  btnPrimary: { backgroundColor: colors.accent, borderColor: colors.accent },
  btnSecondary: { backgroundColor: colors.surfaceElevated, borderColor: colors.border },
  btnGhost: { backgroundColor: 'transparent', borderColor: 'transparent' },
  btnDanger: { backgroundColor: colors.negativeSoft, borderColor: colors.negativeLine },
  btnPressed: { opacity: 0.8 },
  off: { opacity: 0.45 },
  btnText: { fontSize: 15, fontWeight: '600' },
  btnTextSm: { fontSize: 13, fontWeight: '600' },

  chip: { borderColor: colors.border, borderWidth: 1, borderRadius: radius.pill, paddingHorizontal: 13, minHeight: 34, justifyContent: 'center', backgroundColor: colors.surface },
  chipOn: { backgroundColor: colors.accentSoft, borderColor: colors.accentLine },
  chipText: { color: colors.textSecondary, fontSize: 13, fontWeight: '500' },
  chipTextOn: { color: colors.accent },
  chipRow: { gap: spacing.sm },
  chipWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },

  seg: { flexDirection: 'row', backgroundColor: colors.surface, borderColor: colors.border, borderWidth: 1, borderRadius: radius.md, padding: 3, gap: 3 },
  segItem: { flex: 1, minHeight: 34, alignItems: 'center', justifyContent: 'center', borderRadius: radius.sm, paddingHorizontal: spacing.sm },
  segItemOn: { backgroundColor: colors.surfaceElevated },
  segText: { color: colors.textMuted, fontSize: 13, fontWeight: '500' },
  segTextOn: { color: colors.textPrimary },

  field: { gap: 6 },
  fieldLabel: { ...type.small, color: colors.textSecondary },
  input: { backgroundColor: colors.surfaceElevated, borderColor: colors.border, borderWidth: 1, borderRadius: radius.md, paddingHorizontal: spacing.md, paddingVertical: 11, color: colors.textPrimary, fontSize: 15 },
  inputMultiline: { minHeight: 88, lineHeight: 21 },
  inputError: { borderColor: colors.negativeLine },
  fieldError: { fontSize: 11, lineHeight: 15, color: colors.negative },
  hint: { ...type.small, fontSize: 11, lineHeight: 15 },

  notice: { flexDirection: 'row', gap: spacing.sm, borderWidth: 1, borderRadius: radius.md, paddingHorizontal: spacing.md, paddingVertical: 10 },
  noticeIcon: { marginTop: 1 },
  noticeText: { flex: 1, fontSize: 13, lineHeight: 18 },

  empty: { alignItems: 'center', paddingVertical: 44, paddingHorizontal: spacing.xl, gap: spacing.sm },
  emptyIcon: { width: 44, height: 44, borderRadius: radius.lg, backgroundColor: colors.surface, borderColor: colors.border, borderWidth: 1, alignItems: 'center', justifyContent: 'center', marginBottom: spacing.xs },
  emptyTitle: { ...type.heading, textAlign: 'center' },
  emptyText: { ...type.small, fontSize: 13, lineHeight: 19, textAlign: 'center', maxWidth: 300 },
  loading: { paddingVertical: spacing.xxl, alignItems: 'center' },
  loadingFill: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  footnote: { ...type.small, fontSize: 11, lineHeight: 16, textAlign: 'center', paddingHorizontal: spacing.md },
})
