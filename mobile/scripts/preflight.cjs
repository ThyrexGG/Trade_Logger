// Run before building the Android APK:  npm run preflight
// Checks the one-time setup from docs/MOBILE_ANDROID_BUILD.md so a 15-minute
// cloud build doesn't fail (or silently ship without push) over a missing file.
const fs = require('fs')
const path = require('path')

const root = path.join(__dirname, '..')
const PACKAGE = 'site.tradelogger.mobile'
let failures = 0
const ok = (msg) => console.log(`  ✓ ${msg}`)
const bad = (msg, fix) => {
  failures++
  console.log(`  ✗ ${msg}\n      -> ${fix}`)
}

console.log('TradeLogger Android build pre-flight\n')

// 1. Expo project id (written by `npx eas-cli init`)
let projectId = null
try {
  const app = JSON.parse(fs.readFileSync(path.join(root, 'app.json'), 'utf8'))
  projectId = app.expo?.extra?.eas?.projectId ?? null
  if (app.expo?.android?.package === PACKAGE) ok(`Android package is ${PACKAGE}`)
  else bad(`Android package is "${app.expo?.android?.package}"`, `it must be ${PACKAGE} (it is what Firebase is registered against)`)
} catch (e) {
  bad('app.json could not be read', String(e))
}
if (projectId) ok(`Expo project id present (${projectId})`)
else bad('No Expo project id in app.json', 'run: npx eas-cli login   then   npx eas-cli init')

// 2. Firebase file for Android push
const gsPath = path.join(root, 'google-services.json')
if (!fs.existsSync(gsPath)) {
  bad('google-services.json is missing', 'Firebase console -> Add Android app (package ' + PACKAGE + ') -> download it into the mobile/ folder')
} else {
  try {
    const gs = JSON.parse(fs.readFileSync(gsPath, 'utf8'))
    const pkgs = (gs.client || []).map((c) => c?.client_info?.android_client_info?.package_name)
    if (pkgs.includes(PACKAGE)) ok('google-services.json matches the app package')
    else bad(`google-services.json is for ${pkgs.join(', ') || 'no Android app'}`, `re-register the Android app in Firebase with package name exactly ${PACKAGE}, then download it again`)
    if (gs.project_info?.project_id) ok(`Firebase project: ${gs.project_info.project_id}`)
  } catch (e) {
    bad('google-services.json is not valid JSON', 'download it again from the Firebase console (do not edit it)')
  }
}

// 3. Assets the build needs
for (const f of ['assets/icon.png', 'assets/splash-icon.png', 'assets/android-icon-foreground.png', 'assets/notification-icon.png']) {
  if (fs.existsSync(path.join(root, f))) ok(f)
  else bad(`${f} is missing`, 'restore it from git')
}

console.log(
  failures
    ? `\n${failures} problem${failures > 1 ? 's' : ''} to fix before building. (The FCM key upload in step 3 of the guide cannot be checked from here.)`
    : '\nAll local checks pass. Build with:  npx eas-cli build -p android --profile preview\n(Reminder: the FCM V1 key must also be uploaded with `npx eas-cli credentials` — see the guide, step 3.)',
)
process.exit(failures ? 1 : 0)
