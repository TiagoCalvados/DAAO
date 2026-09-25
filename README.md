# DAAO

DAAO 0.4.2 is a phone-first astronomy assistant. Open the Android app, point the
camera at the sky, and ask a question aloud. The phone uses its location, compass,
time, and a small built-in sky catalog to answer. The desktop receiver is optional
and no longer required by the Android app.

On launch, the app shows **“Welcome Tiago, what would you like to know?”** without
speaking. It listens for a question and speaks only in response. There are no
**Voice**, **Describe sky**, or **Start streaming** controls. A small text field is
available if speech recognition is unavailable. The answer panel occupies a narrow
strip at the bottom of the camera preview.

Try:

- “What is that bright star in front of me?”
- “Please describe what you see now.”
- “Where can I find Mars?”
- “Where is the Moon?”

The answers are based on calculated sky positions, **not image recognition**. A
camera image alone does not establish the identity of a bright point. Point the
camera center directly at an object for the best match. The built-in catalog
contains the Moon, Mars, and a selection of bright named stars. It reports when a
requested object is below the horizon or when no catalog match is close enough.
Compass calibration, magnetic interference, GPS accuracy, camera field of view,
and the approximate Moon calculation can affect the answer. The app never invents
objects elsewhere in the sky to fill a description.

Voice questions use Android's on-device recognizer on Android 12 and later.
Availability depends on the phone and its installed language pack. Typing still
works when offline recognition is unavailable. The ordinary debug build speaks
with the phone's text-to-speech voice. A private `tiago` build speaks with Tiago's
confirmed voice reference using Pocket TTS entirely on the phone.

## Build and install the Android app

Requirements: JDK 17 and Android SDK 36. From the repository root:

```powershell
.\android\gradlew.bat -p .\android :app:assembleDebug
```

The APK is `android\app\build\outputs\apk\debug\app-debug.apk`. Install it on an
Android phone with `adb install -r` or transfer it to the phone and open it.
Grant camera, location, and microphone permissions. No desktop URL or streaming
setup is needed.

### Private Tiago voice build

The user's recording, model weights, and native voice runtime are deliberately
excluded from Git. To build the private APK, place the seven Pocket TTS model
files in `.private/android-assets/pocket/`, a mono 24 kHz PCM16 reference WAV in
`.private/android-assets/voice/tiago-reference.wav`, and the sherpa-onnx 1.13.8
Android AAR in `.private/runtime/sherpa-onnx-1.13.8.aar`. Then run:

```powershell
.\android\gradlew.bat -p .\android :app:assembleTiago
```

The result is `android\app\build\outputs\apk\tiago\app-tiago.apk`. It installs
as **DAAO Tiago** with its own app ID, beside any older DAAO installation. This build
includes the private reference and approximately 198 MB of model weights. It
never sends voice recordings or generated speech to the desktop or a speech
service. On first use it copies the model to app-private storage, which needs
additional free space. Do not distribute this APK without Tiago's consent.

For a release build, set `DAAO_SIGNING_PROPERTIES` to a private properties file
with `storeFile`, `storePassword`, `keyAlias`, and `keyPassword`, then run
`:app:assembleRelease`. Keep the key and password outside the repository.

## Optional desktop receiver

The Python desktop viewer and its HTTP receiver remain available for existing
Sensor Logger and `daao-mobile-v1` clients. It receives images and sensor data at
`POST /data` and reports status at `GET /health`. The new Android app does not send
data to it.

Requirements: Python 3.14 and [uv](https://docs.astral.sh/uv/).

```powershell
uv sync --locked
uv run --locked daao
```

## Tests

```powershell
uv run --locked python -m unittest discover -s tests -v
.\android\gradlew.bat -p .\android :app:testDebugUnitTest
```
