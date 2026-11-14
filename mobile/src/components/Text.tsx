import { createContext, forwardRef, useContext, type ComponentRef } from 'react'
import { Text as RNText, TextInput as RNTextInput, StyleSheet, type TextInputProps, type TextProps, type TextStyle } from 'react-native'
import { fonts } from '../theme'

/**
 * The app's Text and TextInput: the same components as React Native's, in Geist.
 *
 * A bundled font has no weights on Android (asking for bold only smears the regular file), so each weight is
 * its own family. Rather than naming a family in every style, screens keep writing `fontWeight` and this
 * picks the file: 400 -> regular, 500 -> medium, 600 and up -> semibold (nothing renders heavier than 600,
 * as on the web). A style with `fontVariant: ['tabular-nums']` gets Geist Mono, so figures line up.
 * Nested text inherits its parent's weight and mono-ness unless it sets its own.
 *
 * Always import Text / TextInput from here, never from 'react-native' (tests/test_mobile_design_guard.py enforces it).
 */
type Face = { mono: boolean; weight: 400 | 500 | 600 }
const ROOT: Face = { mono: false, weight: 400 }
const FaceContext = createContext<Face>(ROOT)

function weightOf(w: TextStyle['fontWeight'], inherited: Face['weight']): Face['weight'] {
  if (w == null) return inherited
  if (w === 'normal') return 400
  if (w === 'bold') return 600
  const n = typeof w === 'number' ? w : Number(w)
  if (!Number.isFinite(n)) return inherited
  return n >= 600 ? 600 : n >= 500 ? 500 : 400
}

function familyOf(face: Face): string {
  if (face.mono) return face.weight === 600 ? fonts.monoSemi : face.weight === 500 ? fonts.monoMedium : fonts.mono
  return face.weight === 600 ? fonts.sansSemi : face.weight === 500 ? fonts.sansMedium : fonts.sans
}

function resolve(style: TextProps['style'], parent: Face): { face: Face; font: TextStyle } {
  const flat = (StyleSheet.flatten(style) ?? {}) as TextStyle
  const mono = flat.fontVariant ? flat.fontVariant.includes('tabular-nums') : parent.mono
  const face: Face = { mono, weight: weightOf(flat.fontWeight, parent.weight) }
  // fontWeight is reset so Android never fakes a bold on top of the weight-specific file
  return { face, font: { fontFamily: familyOf(face), fontWeight: 'normal' } }
}

export const Text = forwardRef<ComponentRef<typeof RNText>, TextProps>(function Text({ style, ...rest }, ref) {
  const parent = useContext(FaceContext)
  const { face, font } = resolve(style, parent)
  const same = face.mono === parent.mono && face.weight === parent.weight
  const el = <RNText ref={ref} {...rest} style={[style, font]} />
  return same ? el : <FaceContext.Provider value={face}>{el}</FaceContext.Provider>
})

export const TextInput = forwardRef<RNTextInput, TextInputProps>(function TextInput({ style, ...rest }, ref) {
  const { font } = resolve(style, ROOT)
  return <RNTextInput ref={ref} {...rest} style={[style, font]} />
})
// so `useRef<TextInput>(null)` keeps working
export type TextInput = RNTextInput
