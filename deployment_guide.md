# Trading Journal Deployment & APK Splicing Guide

This document describes how to deploy your custom Trading Analytics Dashboard to the cloud for free, configure secure credentials, hook the Android app to your live site, and compile the final APK to use on your phone.

---

## Phase 1: Uploading the Code to GitHub

To deploy your dashboard to the cloud, the project needs to live in a GitHub repository:

1. Create a new **Private** or **Public** repository on GitHub named `trade-logger`.
2. Connect your local repository and push the code:
   ```powershell
   git remote add origin https://github.com/<YOUR_GITHUB_USERNAME>/trade-logger.git
   git branch -M main
   git push -u origin main
   ```

*Note: Your `.env` and `trades.db` files are ignored automatically by `.gitignore` so your login passwords and local databases are never exposed publicly.*

---

## Phase 2: Choosing a Hosting Platform (Vercel vs. Streamlit Cloud vs. Render)

> [!WARNING]
> **Streamlit cannot run on Vercel.** 
> Vercel is a **Serverless** hosting platform. Streamlit runs a persistent Python server in the background and uses open **WebSocket** connections to sync state with the dashboard in real-time. Because Vercel's serverless functions shut down after a few seconds of inactivity and do not support persistent WebSockets, Streamlit will not load or function there.

To deploy your dashboard for free, you should use a platform that supports persistent Python Web Services:

### Option A: Streamlit Community Cloud (Recommended & 100% Free)
This is the easiest, official hosting method for Streamlit apps:
1. Sign in to [share.streamlit.io](https://share.streamlit.io) using your GitHub account.
2. Click **New App** (or **Create app**).
3. Select your repository `ThyrexGG/Trade_Logger`, branch `main`, and main file `app.py`.
4. Click **Advanced Settings** before deploying.
5. In the **Secrets** box, paste the exact contents of your local `.env` file:
   ```toml
   CAPITAL_EMAIL = "your-email"
   CAPITAL_PASSWORD = "your-password"
   CAPITAL_API_KEY = "your-key"
   CAPITAL_ACCOUNT_ID = "your-account-id"
   MT5_LOGIN = 123456
   MT5_PASSWORD = "your-mt5-password"
   MT5_SERVER = "your-mt5-server"
   ```
6. Click **Deploy**. Copy your live URL (e.g., `https://trade-logger-xxx.streamlit.app`).

### Option B: Render.com (Free Tier Web Service)
Render provides free hosting inside persistent Linux containers (Web Services):
1. Create a free account on [Render.com](https://render.com).
2. Click **New** -> **Web Service** and connect your GitHub repository.
3. Configure the settings:
   * **Runtime:** `Python`
   * **Build Command:** `pip install -r requirements.txt`
   * **Start Command:** `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`
4. Expand the **Environment** section, click **Add Environment Variable**, and insert the variables from your `.env` file one by one.
5. Click **Create Web Service**. Copy the generated live URL (e.g., `https://trade-logger.onrender.com`).

---

## Phase 3: Splicing the Deployed URL into the Flutter App

Once the web application is running live in the cloud:

1. Open the Flutter main source file: [`main.dart`](file:///c:/Users/Asus/Desktop/Trade_Logger/flutter_app/lib/main.dart)
2. Locate line 9:
   ```dart
   const String dashboardUrl = "http://10.0.2.2:8502";
   ```
3. Swap it with your deployed Streamlit Cloud URL:
   ```dart
   const String dashboardUrl = "https://your-app-name.streamlit.app";
   ```
4. Save the file.

---

## Phase 4: Compiling the APK with Flutter

To compile the Flutter project into an installable Android APK:

1. Open your terminal in the `flutter_app` folder:
   ```powershell
   cd C:\Users\Asus\Desktop\Trade_Logger\flutter_app
   ```
2. Run the Flutter build command:
   ```powershell
   flutter build apk --debug
   ```
   *(For final publication, you can run `flutter build apk --release` to build an optimized, smaller production bundle).*
3. Once the build finishes, your compiled installer file will be located at:
   * `flutter_app/build/app/outputs/flutter-apk/app-debug.apk`

---

## Phase 5: Installing on Your Phone

1. Transfer the `app-debug.apk` file to your Android phone (via Google Drive, USB cable, email, or messaging app).
2. Open the APK file on your phone.
3. Tap **Install**. (If prompted, enable "Install from Unknown Sources" or "Allow from this source" in your phone's browser or file manager settings).
4. Launch the **TradeLogger** app. It will open your trading journal in a full-screen, high-performance Flutter app!
