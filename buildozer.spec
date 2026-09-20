[app]
title = östTube
package.name = osttube
package.domain = org.omerfaruk
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,json
version = 1.0

# Fixed requirements - removed ffpyplayer and adjusted versions
requirements = python3,kivy,requests,yt-dlp

orientation = portrait
fullscreen = 0

# Android permissions
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE
android.features = android.hardware.touchscreen

# Android API settings
android.api = 34
android.minapi = 24
android.archs = arm64-v8a

# Build performance
p4a.bootstrap = sdl2
p4a.release_artifact = apk

# Java/Gradle settings
android.accept_sdk_license = True
android.gradle_dependencies = 

# Logcat configuration
android.logcat_filters = *:S python:D

# Build configuration
android.add_src =

[buildozer]
log_level = 2
warn_on_root = 1
