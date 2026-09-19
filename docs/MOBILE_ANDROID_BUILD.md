# Build the installable Android app (with trade alerts)

Everything below is one-time setup, about 30 minutes. The result is an **APK** you
install on your phone: its own icon, no Expo Go, no PC needed, and push
notifications when a trade opens or closes.

You need: a free Expo account, a free Google (Firebase) account, and Node on this PC
(already installed).

Run every command from the `mobile` folder:

```
cd C:\Users\Asus\Desktop\Trade_Logger\mobile
```

## 1. Expo account + project

1. Create a free account at https://expo.dev/signup
2. Log in from the terminal (it asks for your email + password):
   ```
   npx eas-cli login
   ```
3. Create the project. Answer **yes** when it asks to create one:
   ```
   npx eas-cli init
   ```
   This adds a `projectId` to `app.json`. Tell Claude when it's done so it gets committed.

## 2. Firebase (Google's part of Android push)

Android delivers push through Google, so a free Firebase project is required.

1. Go to https://console.firebase.google.com → **Add project** → name it `TradeLogger`
   (turn Google Analytics **off**).
2. In the project, click the **Android** icon to add an app:
   - Android package name: `site.tradelogger.mobile` (exactly this)
   - App nickname: anything
   - Click **Register app**, then **Download google-services.json**.
3. Move that file into the `mobile` folder (next to `app.json`). Tell Claude — it
   gets committed so the cloud build can see it. (It contains no passwords.)

## 3. Let Expo send through your Firebase project

1. Firebase console → ⚙ **Project settings** → **Service accounts** tab →
   **Generate new private key** → download the JSON file. **Keep this file private —
   do not commit it or paste it anywhere.**
2. Upload it to Expo:
   ```
   npx eas-cli credentials
   ```
   Choose: **Android** → **production** (or the profile it lists) →
   **Google Service Account** → **Manage your Google Service Account Key for Push
   Notifications (FCM V1)** → **Set up a Google Service Account Key** → point it at
   the downloaded JSON file.

## 4. Build the APK

```
npx eas-cli build -p android --profile preview
```

The first build takes ~15 minutes in Expo's cloud (free tier may queue). When it
finishes it prints a link and a QR code — open it **on your phone**, download the
APK and install it (Android asks to allow installs from your browser — allow it).

## 5. Turn on alerts and test

1. Open TradeLogger on the phone, sign in.
2. **More → Account & alerts** → switch **Auto-sync trades** on (the server only notices a new trade when it syncs;
   this is off by default) → then switch **Trade alerts** on → allow notifications.
3. Tap **Send a test notification**. It should arrive within a few seconds.

If the test says something like `InvalidCredentials` or `Could not get a push
token`, step 2 or 3 above is incomplete — the message tells you which.

Before building, `npm run preflight` (in `mobile/`) checks steps 1–2 for you.

## Updating the app later

JavaScript-only changes need a new build too (this is a standalone APK, not Expo Go):
`npx eas-cli build -p android --profile preview`, then install the new APK over the old one.
