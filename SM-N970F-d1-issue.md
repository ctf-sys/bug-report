## Title

[Android 16][d1] Amazon Kindle triggers StorageManagerService/vold watchdog and causes system reboot after login

## Device

- Device: Samsung Galaxy Note10
- Model: SM-N970F
- Codename: d1
- ROM: Evolution X
- ROM version: EvolutionX-16.0-20260713-d1-11.9-Official
- Android version: 16
- SDK: 36
- Build ID: BP4A.251205.006
- Security patch: 2026-07-01
- Build type: Official

## Affected application

- Package: `com.amazon.kindle`
- Version: `8.156.0.100 (2.0.100996.0)`
- Version code: `1286503411`
- targetSdk: 36

## Description

Opening Amazon Kindle itself does not immediately cause a problem.

However, after signing in to an Amazon account, Kindle starts its initial synchronization/storage initialization. Shortly afterwards, the whole Android system becomes unresponsive and the device reboots.

This is not a normal application crash or ANR. The Android `system_server` watchdog detects that `StorageManagerService` is blocked while communicating with `vold`, and eventually triggers a system restart.

The issue is reproducible after Kindle login.

## Steps to reproduce

1. Boot the device normally.
2. Install Amazon Kindle from Google Play.
3. Open Kindle.
4. Sign in to an Amazon account.
5. Wait for Kindle to start synchronization / library initialization.
6. The UI becomes unresponsive.
7. After approximately one minute, the device shows the boot animation and restarts.

## Expected behavior

Kindle should complete account synchronization and initialize its application storage without affecting Android system services.

## Actual behavior

`StorageManagerService` becomes blocked.

A pre-watchdog event is generated after approximately 15 seconds:

```text
Subject: Blocked in monitor com.android.server.StorageManagerService
on monitor thread (watchdog.monitor) for 15s

Watchdog-Type: pre_watchdog
