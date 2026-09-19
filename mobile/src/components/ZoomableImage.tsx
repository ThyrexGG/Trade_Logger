import { Image, type ImageSource } from 'expo-image'
import { useMemo, useRef, useState } from 'react'
import { Animated, PanResponder, StyleSheet, View, type LayoutChangeEvent } from 'react-native'
import { clamp, clampTranslate, distance, doubleTapTarget, MAX_SCALE, MIN_SCALE, pinchScale } from '../lib/zoomMath'

const DOUBLE_TAP_MS = 280

/**
 * Pinch-to-zoom, drag-to-pan and double-tap-to-zoom for a full-screen image.
 * Built on React Native's own gesture responder (no native module) so it works
 * on Android, where the ScrollView zoom used on iPhone does nothing.
 */
export function ZoomableImage({ source }: { source: ImageSource }) {
  const scale = useRef(new Animated.Value(1)).current
  const tx = useRef(new Animated.Value(0)).current
  const ty = useRef(new Animated.Value(0)).current
  const size = useRef({ w: 0, h: 0 })
  const [, setReady] = useState(false)

  // Plain-number mirror of the animated values, plus the gesture's starting point.
  const g = useRef({
    scale: 1,
    x: 0,
    y: 0,
    startScale: 1,
    startDist: 0,
    startX: 0,
    startY: 0,
    panBaseDx: 0,
    panBaseDy: 0,
    pinching: false,
    lastTap: 0,
  }).current

  function apply(nextScale: number, nextX: number, nextY: number) {
    g.scale = clamp(nextScale, MIN_SCALE, MAX_SCALE)
    g.x = clampTranslate(nextX, g.scale, size.current.w)
    g.y = clampTranslate(nextY, g.scale, size.current.h)
    scale.setValue(g.scale)
    tx.setValue(g.x)
    ty.setValue(g.y)
  }

  const pan = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => true,
        onMoveShouldSetPanResponder: () => true,
        onPanResponderTerminationRequest: () => false,

        onPanResponderGrant: (e) => {
          const touches = e.nativeEvent.touches
          g.startScale = g.scale
          g.startX = g.x
          g.startY = g.y
          g.panBaseDx = 0
          g.panBaseDy = 0
          g.pinching = false
          g.startDist = 0
          if (touches.length === 1) {
            const now = Date.now()
            if (now - g.lastTap < DOUBLE_TAP_MS) {
              const target = doubleTapTarget(g.scale)
              apply(target, target === MIN_SCALE ? 0 : g.x, target === MIN_SCALE ? 0 : g.y)
              g.lastTap = 0
            } else {
              g.lastTap = now
            }
          }
        },

        onPanResponderMove: (e, gesture) => {
          const touches = e.nativeEvent.touches
          if (touches.length >= 2) {
            if (!g.pinching) {
              g.pinching = true
              g.startDist = distance(touches[0], touches[1])
              g.startScale = g.scale
            }
            apply(pinchScale(g.startScale, g.startDist, distance(touches[0], touches[1])), g.x, g.y)
            return
          }
          if (g.pinching) {
            // One finger lifted mid-pinch: continue panning from where the image is now.
            g.pinching = false
            g.startX = g.x
            g.startY = g.y
            g.panBaseDx = gesture.dx
            g.panBaseDy = gesture.dy
          }
          if (g.scale > 1) {
            apply(g.scale, g.startX + (gesture.dx - g.panBaseDx), g.startY + (gesture.dy - g.panBaseDy))
          }
        },

        onPanResponderRelease: () => {
          g.pinching = false
          if (g.scale < 1.02) apply(1, 0, 0)
        },
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  )

  function onLayout(e: LayoutChangeEvent) {
    size.current = { w: e.nativeEvent.layout.width, h: e.nativeEvent.layout.height }
    setReady(true)
  }

  return (
    <View style={styles.fill} onLayout={onLayout} {...pan.panHandlers}>
      <Animated.View style={[styles.fill, { transform: [{ translateX: tx }, { translateY: ty }, { scale }] }]}>
        <Image source={source} style={styles.fill} contentFit="contain" cachePolicy="disk" />
      </Animated.View>
    </View>
  )
}

const styles = StyleSheet.create({
  fill: { flex: 1, width: '100%', height: '100%', overflow: 'hidden' },
})
