# Secrets to recreate after OS reinstall

The repository deliberately does not contain operational secrets. After reinstall, recreate/store these separately:

1. Linux password for user `admini`.
2. Wi-Fi hotspot SSID/PSK.
3. GitHub authentication for cloning private repositories when needed.
4. Short-lived GitHub Actions runner registration tokens for `jojos-hub`, `jojos-kso`, and `jojos-kitchen`.
5. Android release signing key/passwords when production-signed APKs are introduced.
6. Future central API credentials/device tokens.

Do not put these values into tracked files, shell history, README files or application source.

Recommended operational rule: create new credentials after reinstall rather than trying to reconstruct forgotten passwords. Keep them in a password manager or secret store and rotate them when a device/hub is replaced.
