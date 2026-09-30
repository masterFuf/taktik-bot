# App compatibility

<!-- GENERATED - do not edit. Sources: taktik/core/compat/data/app_builds.json and
     taktik/core/compat/data/overrides/<app>.yaml. Regenerate: python scripts/audits/audit_compatibility_file.py --write -->

The Instagram and TikTok versions TAKTIK supports. Install the **original, unmodified** APK
of a listed version; the download column opens a search for that exact version on
[APKMirror](https://www.apkmirror.com), a public mirror of the original packages.

Status:

- **Reference**: the build the selectors are written against. The safest choice.
- **Validated**: a build proven by runs of the bot's test bench on one of our phones; the runs
  and the known limits are listed under each table.
- **Supported**: the bot carries selector adjustments for this version
  (`taktik/core/compat/data/overrides/<app>.yaml`) and a validated build of it runs on one of our
  phones. A version written `447.x` covers every build of that family.
- **Under validation**: being tested end to end; expect gaps.
- **Adjusted, not validated**: the bot carries selector adjustments for this version, but none of
  our phones runs it and no validation is planned; expect gaps.

Overrides applied: the adjustment sets the bot loads on that version (every key at or below
it). "Desktop app" tells what the TAKTIK desktop app installs itself.

## Architectures

Every version below is listed for `arm64-v8a`, `armeabi-v7a`: the architectures a validated run played.
The bot reads the screen and does not depend on the CPU architecture, but the APK does:
on the mirror, pick the variant matching `adb shell getprop ro.product.cpu.abi`.
A mirror may not publish every architecture for every build.

Tested on real arm64 phones only: the phones, Android versions, app versions and languages
are in the README, section "Tested on". Emulators (`x86_64`, `x86`) are not tested.

## Instagram (`com.instagram.android`)

Reference build: `410.0.0.53.71`.

| Version | Status | Overrides applied | Desktop app | Architectures | Download |
|---|---|---|---|---|---|
| `447.0.0.55.81` | Validated | `417.0.0.0`, `442.0.0.0`, `447.0.0.0` | Installable | `arm64-v8a`, `armeabi-v7a` | [Search on APKMirror](https://www.apkmirror.com/?post_type=app_release&searchtype=apk&s=Instagram+447.0.0.55.81) |
| `447.x` | Supported | `417.0.0.0`, `442.0.0.0`, `447.0.0.0` | - | `arm64-v8a`, `armeabi-v7a` | [Search on APKMirror](https://www.apkmirror.com/?post_type=app_release&searchtype=apk&s=Instagram+447.0.0) |
| `442.x` | Adjusted, not validated | `417.0.0.0`, `442.0.0.0` | - | `arm64-v8a`, `armeabi-v7a` | [Search on APKMirror](https://www.apkmirror.com/?post_type=app_release&searchtype=apk&s=Instagram+442.0.0) |
| `417.x` | Adjusted, not validated | `417.0.0.0` | - | `arm64-v8a`, `armeabi-v7a` | [Search on APKMirror](https://www.apkmirror.com/?post_type=app_release&searchtype=apk&s=Instagram+417.0.0) |
| `410.0.0.53.71` | Reference | none | Installed by default | `arm64-v8a`, `armeabi-v7a` | [Search on APKMirror](https://www.apkmirror.com/?post_type=app_release&searchtype=apk&s=Instagram+410.0.0.53.71) |

Validated builds, with the runs that prove them and their known limits (notes):

- `447.0.0.55.81`, validated on 2026-09-30: 1 Lab run on Pixel 6a (arm64-v8a, versionCode 385311922, fr, 23 actions left out). Notes: One Lab run of 2026-09-30 on the Pixel 6a, Instagram in French, which holds a client's account: played without the 23 actions of its exception (no message thread opened, no typing, no story viewed, no search left behind, Discover people never opened). Four known failures of 447: reading the comments and their authors, the state and the opening of a row of a followers list. No run is green in the strict sense of lab:exit (made on the validated commit): the maintainer's decision validates, with this evidence and these limits. versionCode and ABI: those of the APK pulled from this phone on 2026-09-26; the report did not record them yet.
- `410.0.0.53.71`, validated on 2026-09-30: 2 Lab runs on Pixel 3a (armeabi-v7a, versionCode 381606582, en). Notes: Selector reference. Two Lab runs of 2026-09-30 on the Pixel 3a, Instagram in English, armeabi-v7a variant (the only one run): the first without a failure, the second with one (back to the grid, which depends on the random draws of the Lab's session memory). No run is green in the strict sense of lab:exit (made on the validated commit): the maintainer's decision validates, with this evidence and these limits. versionCode and ABI: those of the APK pulled from this phone on 2026-09-26; the report did not record them yet.

## TikTok (`com.zhiliaoapp.musically`)

Reference build: `43.1.4`.

| Version | Status | Overrides applied | Desktop app | Architectures | Download |
|---|---|---|---|---|---|
| `47.0.3` | Validated | `46.6.3`, `46.9.3`, `47.0.3` | Installable | `arm64-v8a`, `armeabi-v7a` | [Search on APKMirror](https://www.apkmirror.com/?post_type=app_release&searchtype=apk&s=TikTok+47.0.3) |
| `46.9.3` | Adjusted, not validated | `46.6.3`, `46.9.3` | - | `arm64-v8a`, `armeabi-v7a` | [Search on APKMirror](https://www.apkmirror.com/?post_type=app_release&searchtype=apk&s=TikTok+46.9.3) |
| `46.6.3` | Adjusted, not validated | `46.6.3` | - | `arm64-v8a`, `armeabi-v7a` | [Search on APKMirror](https://www.apkmirror.com/?post_type=app_release&searchtype=apk&s=TikTok+46.6.3) |
| `43.1.4` | Reference | none | Installed by default | `arm64-v8a`, `armeabi-v7a` | [Search on APKMirror](https://www.apkmirror.com/?post_type=app_release&searchtype=apk&s=TikTok+43.1.4) |

Validated builds, with the runs that prove them and their known limits (notes):

- `47.0.3`, validated on 2026-09-30: 1 Lab run on Pixel 6a (arm64-v8a, versionCode 2024700030, fr). Notes: One Lab run of 2026-09-29 on the Pixel 6a, TikTok in French. Except the new followers: the Activity page of 47.0.3 opens but is not recognised (one failure, six tests blocked), to be taken up after 1.9.9. No run is green in the strict sense of lab:exit (made on the validated commit): the maintainer's decision validates, with this evidence and these limits. versionCode and ABI: those of the APK pulled from this phone on 2026-09-26; the report did not record them yet.
- `43.1.4`, validated on 2026-09-30: 2 Lab runs on Pixel 3a (arm64-v8a, versionCode 2024301040, fr). Notes: Selector reference. Two Lab runs of 2026-09-30 on the Pixel 3a, TikTok in French: the first without a failure, the second with four failures, three due to the content served (a LIVE without a share button, a video without comments, a suggestion expected under a fixed name) and one to the sound harvest. In both, the sound harvest followed an account by mistake (a tap on the avatar landing on Follow), fixed since in the core. No run is green in the strict sense of lab:exit (made on the validated commit): the maintainer's decision validates, with this evidence and these limits. versionCode and ABI: those of the APK pulled from this phone on 2026-09-26; the report did not record them yet.
