// Extends app.json. The Firebase file is only wired in once it exists, so the app
// still builds and runs (without push) before the Firebase setup in
// docs/MOBILE_ANDROID_BUILD.md has been done.
const fs = require('fs')
const path = require('path')

module.exports = ({ config }) => {
  const hasGoogleServices = fs.existsSync(path.join(__dirname, 'google-services.json'))
  return {
    ...config,
    android: {
      ...config.android,
      ...(hasGoogleServices ? { googleServicesFile: './google-services.json' } : {}),
    },
  }
}
