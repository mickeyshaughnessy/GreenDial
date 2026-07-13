# GreenDial Android (Capacitor)

Native Android shell that loads the live site at **https://greendial.org**. Web deploys update the app content without a new store submission.

| | |
|---|---|
| **Application ID** | `org.greendial.app` |
| **Display name** | GreenDial |
| **Privacy policy** | https://greendial.org/privacy |

## Prerequisites

```bash
# JDK 21 required (Capacitor Android compiles with source 21)
brew install openjdk@21
export JAVA_HOME="/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home"

# Android SDK (example: user-local install)
export ANDROID_HOME="$HOME/Android/sdk"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH"

# One-time SDK packages (API 35/36 + build-tools)
sdkmanager "platform-tools" "platforms;android-36" "build-tools;35.0.0"
yes | sdkmanager --licenses
```

Create `android/local.properties` (gitignored) if missing:

```
sdk.dir=/Users/YOU/Android/sdk
```

## Signing (Play upload key)

`android/keystore.properties` and `android/keystore/*.jks` are **gitignored**. A local upload keystore is created once:

```bash
mkdir -p android/keystore
keytool -genkeypair -v \
  -keystore android/keystore/greendial-upload.jks \
  -alias greendial \
  -keyalg RSA -keysize 2048 -validity 10000 \
  -storepass 'YOUR_STORE_PASSWORD' \
  -keypass 'YOUR_KEY_PASSWORD' \
  -dname "CN=GreenDial, OU=Mobile, O=GreenDial, L=Colorado, ST=CO, C=US"
```

`android/keystore.properties`:

```
storeFile=keystore/greendial-upload.jks
storePassword=YOUR_STORE_PASSWORD
keyAlias=greendial
keyPassword=YOUR_KEY_PASSWORD
```

**Back up the keystore and passwords offline.** Losing them blocks updates for this Play app listing.

> If you use the default local password from the first scaffold (`greendial-upload-change-me`), change it before production and re-sign only if you have not yet uploaded that key to Play.

## Build release AAB

```bash
cd mobile
npm install
npx cap sync android
npm run bundle
# Output:
# android/app/build/outputs/bundle/release/app-release.aab
```

Debug APK (USB install, not for Play):

```bash
cd android && ./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

## Play Console (Internal testing → phone)

1. Open [Google Play Console](https://play.google.com/console) (one-time ~$25 developer fee).
2. Create app **GreenDial**, category **Health & Fitness**.
3. Set privacy policy URL: `https://greendial.org/privacy`.
4. Complete Data safety, content rating, and store listing (short/full description, icon 512, feature graphic, screenshots).
5. **Testing → Internal testing → Create release** → upload `app-release.aab`.
6. Add your Google account as a tester → copy the opt-in URL → open on phone → Install.

Production track can wait until Internal testing looks good.

### Suggested store copy

**Short description (≤80 chars):**  
Free AI health companion — chat with Doc about sleep, diet, exercise & stress.

**Full description (draft):**  
GreenDial is a free AI health companion. Chat with Doc for personalized guidance on sleep, diet, exercise, stress, and everyday well-being. Your profile builds as you talk — no forms, no appointments.

GreenDial is not a medical provider and is not HIPAA-compliant. It does not diagnose, prescribe, or replace professional care. For emergencies, seek qualified help (e.g. call local emergency services or 988 in the US for mental health crisis support).

Privacy: https://greendial.org/privacy  
Web: https://greendial.org

## Project layout

```
mobile/
  capacitor.config.json   # appId + server.url → greendial.org
  www/                    # bootstrap HTML (fallback; live site is loaded)
  resources/              # source icon for capacitor-assets
  android/                # generated Capacitor Android project
```

## Regenerating launcher icons

```bash
cp ../icons/icon-512.png resources/icon.png
cp ../icons/icon-512.png resources/splash.png
npm run assets
npx cap sync android
```
