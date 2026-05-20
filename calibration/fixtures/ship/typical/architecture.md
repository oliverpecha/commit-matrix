# Architecture
React Native app (Expo SDK 51). Supports iOS 15+ and Android 10+.
Camera and media picker features use expo-camera and expo-image-picker.
Feature flags managed via remote config (Firebase Remote Config).

Commit message:
    fix(ios): guard PHPhotosLibrary limited access UI behind iOS 16 check

    iOS 14 introduced PHAuthorizationStatusLimited (user grants access to
    selected photos only). iOS 16 added PHPhotoLibraryChangeObserver for
    observing when the user modifies their limited selection in-app without
    leaving the app. Without the version guard, calling
    PHPhotoLibrary.shared().register(self) on iOS 14/15 raises an
    unrecognized selector crash at runtime — the method does not exist on
    those versions. Fallback on iOS 14/15: user must leave the app to the
    system picker to modify their photo selection. Known edge case: users
    on iOS 15.4+ with StoreKit 2 may see a double prompt — tracked in #1847.

