# Basic

```
Device: Samsung Galaxy Note10
Model: SM-N970F
Codename: d1
Android: 16
Evolution X: 11.9
Build: EvolutionX-16.0-20260713-d1-11.9-Official
App: Amazon Kindle
Package: com.amazon.kindle
Kindle version: 8.156.0.100
```

# Collecting command

```
adb shell dumpsys dropbox --print > dropbox.txt
grep -iE \
"system_server_pre_watchdog|system_server_watchdog|StorageManagerService|IVold|fixupAppDir|com.amazon.kindle|Last boot reason|Restarting system" \
dropbox.txt > evox-kindle-watchdog.txt
adb bugreport kindle-android16.zip
```

## Report

* 2026-09-12 [Android 16][d1] Amazon Kindle triggers StorageManagerService/vold watchdog and causes system reboot after login
 [Samsung Galaxy Note10](2026-09-12-SM-N970F-d1.md) 
