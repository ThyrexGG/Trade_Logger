let suspended = 0

/**
 * Wrap anything that legitimately sends the app to the background for a while
 * (the camera, the photo picker). Without this, returning from a slow photo
 * would re-lock the app as if the user had walked away.
 */
export async function whileLockSuspended<T>(fn: () => Promise<T>): Promise<T> {
  suspended++
  try {
    return await fn()
  } finally {
    suspended--
  }
}

export function isLockSuspended(): boolean {
  return suspended > 0
}
