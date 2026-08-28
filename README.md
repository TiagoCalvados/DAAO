# DIY Astronomical Attic Observatory

DIY Astronomical Attic Observatory (DAAO) combines images from a phone camera
with the phone's orientation sensors. Version **0.3.4** consists of:

- a Python 3.14 desktop receiver and Qt 6.11.1 GUI;
- a private, native Android camera-and-orientation sender;
- one synchronized HTTP update per second over the local network;
- a perspective-correct magnetic compass tape over the camera image;
- a camera attitude HUD with a horizon line, pitch ladder, and roll indicator;
- a labeled overlay for 27 bright stars, the Sun, and the other seven planets;
- labeled edge arrows for chasing above-horizon objects outside the camera view.

The Android app uses CameraX and Android's rotation-vector sensor. It calculates
the azimuth, elevation, and visual roll of the rear camera's viewing direction.
It also sends the raw device pitch and roll, full orientation quaternion, sensor
accuracy, GPS position, magnetic declination, and timestamps. The desktop uses
the camera-relative values to keep the attitude HUD and astronomical labels
aligned with the image.

No paid application, cloud service, account, or Google Play publication is
required. The signed APK can be downloaded from GitHub and installed directly
on the phone.

## Desktop requirements

- Python 3.14
- [uv](https://docs.astral.sh/uv/)
- Windows, Linux, or macOS with the phone on the same local network

On Windows, install uv with:

```powershell
winget install --id=astral-sh.uv -e
```

Create the locked Python environment:

```powershell
uv sync --locked
```

## Run the desktop application

```powershell
uv run --locked daao
```

DAAO listens on TCP port 8000. Its status bar displays the address to enter in
the Android app, normally:

```text
http://192.168.1.100:8000/data
```

The computer and phone must be on the same network. Allow Python to receive
private-network traffic if the operating-system firewall asks.

## Install the Android application from GitHub

On the phone:

1. Open the [latest DAAO release](https://github.com/stablum/DAAO/releases/latest).
2. Under **Assets**, download `DAAO-Camera-0.3.4-debug.apk`.
3. Open the download. If Android asks, allow the browser or file manager to
   **Install unknown apps** / **Allow from this source**.
4. Confirm **Install**, then open **DAAO Camera**.

This is a free direct installation; Google Play and a developer account are not
involved. Future APKs signed with the same DAAO release key can be installed as
updates. If an older debug-signed DAAO Camera build is already installed,
uninstall it once before installing the release APK because Android will not
replace an app signed by a different key.

## Build the Android application

The repository includes the Gradle wrapper, so Android Studio is not needed for
routine command-line builds once the Android SDK and JDK 17 are installed.

From the repository root:

```powershell
.\android\gradlew.bat -p .\android :app:assembleDebug
```

The resulting APK is:

```text
android\app\build\outputs\apk\debug\app-debug.apk
```

The debug APK is automatically signed with the computer's Android debug key.
For an official signed release, set `DAAO_SIGNING_PROPERTIES` to a local
properties file containing `storeFile`, `storePassword`, `keyAlias`, and
`keyPassword`, then build:

```powershell
$env:DAAO_SIGNING_PROPERTIES = "$env:LOCALAPPDATA\DAAO\android-signing\keystore.properties"
.\android\gradlew.bat -p .\android :app:assembleRelease
```

The signed output is:

```text
android\app\build\outputs\apk\release\app-release.apk
```

The official release key and password are deliberately outside this repository.
The maintainer must back up both separately and never commit or upload either
private file. Losing them would make it impossible to publish installable
updates for the same Android application.

## Install with ADB

On the Android phone (including the Samsung Galaxy A36):

1. Open **Settings → About phone → Software information**.
2. Tap **Build number** seven times to enable Developer options.
3. Open **Settings → Developer options** and enable **USB debugging**.
4. Connect the phone by USB and approve the computer when Android asks.

Then install or update DAAO:

```powershell
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $adb devices
& $adb install -r .\android\app\build\outputs\apk\release\app-release.apk
```

ADB installation does not require Google Play publication, Android developer
registration, or a fee. The cable can be disconnected and USB debugging can be
disabled after installation.

## Use DAAO Camera

1. Start the Python desktop application.
2. Open **DAAO Camera** on the phone and grant camera and location permissions.
3. Enter the complete URL shown in the desktop status bar.
4. Confirm that the rear-camera preview and an orientation reading appear.
5. Tap **Start streaming**.

The phone screen stays awake while the app is open. The status panel reports the
HTTP response, frame number, and JPEG size. A successful connection normally
shows `HTTP 200`. The URL is remembered for the next run.

The app currently runs in the foreground. Android may stop access to the camera
when another app takes ownership of it or DAAO Camera is sent to the background.
For the first run, use the phone outdoors or near a window until Android obtains
a GPS fix. Camera and attitude streaming still work without location, but the
astronomical overlay waits until a position is available.

## Compass calibration

The center marker represents the magnetic azimuth of the rear camera's optical
axis. Compass and pitch-ladder positions use pinhole-camera projection rather
than a linear degrees-per-pixel approximation. The gold horizon line marks zero
elevation, while the green ladder marks five-degree elevation intervals and the
roll scale shows camera rotation.

The default horizontal field of view is 74 degrees, a practical starting value
for the Galaxy S23+ Wide / 1x camera. Use the desktop **Horizontal FOV** control
to calibrate the actual camera crop. **Bearing offset** compensates for a
measured magnetic or mounting offset.

The compass tape remains relative to magnetic north. The astronomical overlay
uses Android's geomagnetic model to correct the camera bearing to true north,
then combines GPS latitude/longitude with the frame's UTC timestamp. It projects
the [IAU named-star catalog](https://iauarchive.eso.org/public/themes/naming_stars/)
and offline [JPL approximate planetary elements](https://ssd.jpl.nasa.gov/planets/approx_pos.html)
through the same pinhole-camera model as the HUD. No network ephemeris service is
used. Sensor calibration and horizontal-FOV calibration will usually dominate
the remaining label-position error.

An object inside the camera view is marked at its calculated image position. An
above-horizon object outside the view gets a labeled arrow near the appropriate
screen edge. The arrow accounts for camera roll and continues to indicate the
shortest screen-relative chase direction when the object is behind the phone.
Labels are spread along each edge to remain readable. Objects below the horizon
are omitted because reorienting the phone cannot make them observable. The
desktop status bar reports how many objects are in view, how many have chase
indicators, or which sensor input the sky overlay is waiting for.

Magnetic heading and camera roll are mathematically undefined when the camera
points exactly vertically; the transmitted quaternion remains valid in that
orientation. The Sun label is positional information only—never look at the Sun
through binoculars or a telescope without a purpose-built solar filter.

## DAAO mobile protocol

The phone sends `multipart/form-data` to `POST /data`. Each request contains:

- a `data` part with JSON sensor and timing information;
- an `image` part with the corresponding JPEG frame.

The JSON uses the protocol identifier `daao-mobile-v1` and includes compatible
`compass`, `orientation`, `camera`, and `location` readings:

```json
{
  "protocol": "daao-mobile-v1",
  "messageId": 1,
  "sessionId": "recording-id",
  "deviceId": "samsung SM-S916B",
  "imageTimestampNs": 1785000000000000000,
  "payload": [
    {
      "name": "compass",
      "time": 1785000000000000000,
      "values": {
        "magneticBearing": 135.0,
        "trueBearing": 137.5,
        "magneticDeclination": 2.5,
        "headingAccuracy": 3.0
      }
    },
    {
      "name": "orientation",
      "time": 1785000000000000000,
      "values": {
        "cameraElevation": 25.0,
        "cameraRoll": 5.0,
        "pitch": -65.0,
        "roll": 5.0,
        "quaternionW": 1.0,
        "quaternionX": 0.0,
        "quaternionY": 0.0,
        "quaternionZ": 0.0
      }
    },
    {
      "name": "camera",
      "time": 1785000000000000000,
      "values": {"horizontalFov": 74.0}
    },
    {
      "name": "location",
      "time": 1785000000000000000,
      "values": {
        "latitude": 52.3676,
        "longitude": 4.9041,
        "altitudeMeters": 12.5,
        "horizontalAccuracy": 4.0,
        "magneticDeclination": 2.5,
        "locationTimestampEpochMs": 1785000000000
      }
    }
  ]
}
```

Requests are limited to 32 MiB. `GET /health` returns a small health response.

## Sensor Logger compatibility

The desktop receiver remains compatible with Sensor Logger JSON batches, raw
`image/*` bodies, base64/data-URI camera fields, and multipart image requests.
Orientation readings with generic `pitch` and `roll` fields are accepted as a
fallback when camera-relative fields are unavailable.
Sensor Logger 1.62 was observed to save camera images locally while omitting
them from HTTP Push, which is why DAAO now has its own Android sender.

## Diagnostic log

DAAO keeps a rotating diagnostic log without saving request bodies or camera
images. On Windows it is written to:

```text
%LOCALAPPDATA%\DAAO\logs\daao.log
```

Each request records its source, content type, size, response outcome, sensor
reading count, and whether a compass heading or image was recognized. Set
`DAAO_LOG_DIR` before starting DAAO to use another directory.

## Tests

Run the Python tests:

```powershell
uv run --locked python -m unittest discover -s tests -v
```

Run Android unit tests:

```powershell
.\android\gradlew.bat -p .\android :app:testDebugUnitTest
```

Build the Python source and wheel distributions with:

```powershell
uv build
```
