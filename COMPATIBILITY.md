# App compatibility

<!-- GENERATED - do not edit. Sources: taktik/core/compat/data/app_builds.json and
     taktik/core/compat/data/overrides/<app>.yaml. Regenerate: python scripts/audit_compatibility_file.py --write -->

The Instagram and TikTok versions TAKTIK supports. Install the **original, unmodified** APK
of a listed version; the download column opens a search for that exact version on
[APKMirror](https://www.apkmirror.com), a public mirror of the original packages.

Status:

- **Reference**: the build the selectors are written against. The safest choice.
- **Supported**: the bot carries selector adjustments for this version
  (`taktik/core/compat/data/overrides/<app>.yaml`). A version written `447.x` covers every
  build of that family.
- **Under validation**: being tested end to end; expect gaps.

Overrides applied: the adjustment sets the bot loads on that version (every key at or below
it). "Desktop app" tells what the TAKTIK desktop app installs itself.

## Architectures

Every version below is supported on `arm64-v8a`, `armeabi-v7a`, `x86_64`, `x86` (`x86_64` and `x86` cover desktop emulators).
The bot reads the screen and does not depend on the CPU architecture, but the APK does:
on the mirror, pick the variant matching `adb shell getprop ro.product.cpu.abi`.
A mirror may not publish every architecture for every build.

## Instagram (`com.instagram.android`)

Reference build: `410.0.0.53.71`.

| Version | Status | Overrides applied | Desktop app | Architectures | Download |
|---|---|---|---|---|---|
| `447.x` | Supported | `417.0.0.0`, `442.0.0.0`, `447.0.0.0` | - | `arm64-v8a`, `armeabi-v7a`, `x86_64`, `x86` | [Search on APKMirror](https://www.apkmirror.com/?post_type=app_release&searchtype=apk&s=Instagram+447.0.0) |
| `444.0.0.46.85` | Under validation | `417.0.0.0`, `442.0.0.0` | Installable, under validation | `arm64-v8a`, `armeabi-v7a`, `x86_64`, `x86` | [Search on APKMirror](https://www.apkmirror.com/?post_type=app_release&searchtype=apk&s=Instagram+444.0.0.46.85) |
| `442.x` | Supported | `417.0.0.0`, `442.0.0.0` | - | `arm64-v8a`, `armeabi-v7a`, `x86_64`, `x86` | [Search on APKMirror](https://www.apkmirror.com/?post_type=app_release&searchtype=apk&s=Instagram+442.0.0) |
| `417.x` | Supported | `417.0.0.0` | - | `arm64-v8a`, `armeabi-v7a`, `x86_64`, `x86` | [Search on APKMirror](https://www.apkmirror.com/?post_type=app_release&searchtype=apk&s=Instagram+417.0.0) |
| `410.0.0.53.71` | Reference | none | Installed by default | `arm64-v8a`, `armeabi-v7a`, `x86_64`, `x86` | [Search on APKMirror](https://www.apkmirror.com/?post_type=app_release&searchtype=apk&s=Instagram+410.0.0.53.71) |

## TikTok (`com.zhiliaoapp.musically`)

Reference build: `43.1.4`.

| Version | Status | Overrides applied | Desktop app | Architectures | Download |
|---|---|---|---|---|---|
| `47.0.3` | Supported | `46.6.3`, `46.9.3`, `47.0.3` | - | `arm64-v8a`, `armeabi-v7a`, `x86_64`, `x86` | [Search on APKMirror](https://www.apkmirror.com/?post_type=app_release&searchtype=apk&s=TikTok+47.0.3) |
| `46.9.3` | Supported | `46.6.3`, `46.9.3` | - | `arm64-v8a`, `armeabi-v7a`, `x86_64`, `x86` | [Search on APKMirror](https://www.apkmirror.com/?post_type=app_release&searchtype=apk&s=TikTok+46.9.3) |
| `46.6.3` | Supported | `46.6.3` | Installable, under validation | `arm64-v8a`, `armeabi-v7a`, `x86_64`, `x86` | [Search on APKMirror](https://www.apkmirror.com/?post_type=app_release&searchtype=apk&s=TikTok+46.6.3) |
| `43.1.4` | Reference | none | Installed by default | `arm64-v8a`, `armeabi-v7a`, `x86_64`, `x86` | [Search on APKMirror](https://www.apkmirror.com/?post_type=app_release&searchtype=apk&s=TikTok+43.1.4) |
