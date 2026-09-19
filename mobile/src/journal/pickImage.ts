import { ImageManipulator, SaveFormat } from 'expo-image-manipulator'
import * as ImagePicker from 'expo-image-picker'
import { whileLockSuspended } from '../lock/suspend'

/** Long edge cap. Chart screenshots stay legible at this size and land far below the API's 4 MB limit. */
const MAX_WIDTH = 1600

export type PickSource = 'camera' | 'library'

export class PickError extends Error {}

/**
 * Lets the user take a photo or choose one, then downsizes it to a JPEG the
 * API will accept. Returns the local file URI, or null if they cancelled.
 */
export async function pickScreenshot(source: PickSource): Promise<string | null> {
  const options: ImagePicker.ImagePickerOptions = { mediaTypes: ['images'], quality: 1, exif: false }

  let result: ImagePicker.ImagePickerResult
  if (source === 'camera') {
    const perm = await whileLockSuspended(() => ImagePicker.requestCameraPermissionsAsync())
    if (!perm.granted) throw new PickError('Camera access is off. Enable it for TradeLogger in your phone settings.')
    result = await whileLockSuspended(() => ImagePicker.launchCameraAsync(options))
  } else {
    result = await whileLockSuspended(() => ImagePicker.launchImageLibraryAsync(options))
  }
  if (result.canceled || result.assets.length === 0) return null

  const asset = result.assets[0]
  const ctx = ImageManipulator.manipulate(asset.uri)
  if (asset.width > MAX_WIDTH) ctx.resize({ width: MAX_WIDTH })
  const image = await ctx.renderAsync()
  const saved = await image.saveAsync({ format: SaveFormat.JPEG, compress: 0.85 })
  return saved.uri
}
