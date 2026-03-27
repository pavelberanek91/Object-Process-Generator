#!/usr/bin/env bash
set -euo pipefail

APP_NAME="OpenOPM"
APP_BUNDLE="${APP_NAME}.app"
DIST_DIR="dist"
BUILD_DIR="build"
SPEC_FILE="OpenOPM.spec"
DMG_NAME="${APP_NAME}-macOS.dmg"
DMG_VOL_NAME="${APP_NAME} Installer"
STAGING_DIR="${BUILD_DIR}/dmg"

echo "==> Kontrola nástrojů"
command -v python3 >/dev/null
command -v hdiutil >/dev/null

echo "==> Instalace build závislostí"
python3 -m pip install --upgrade pip pyinstaller

echo "==> Čištění starých artefaktů"
rm -rf "${DIST_DIR}/${APP_BUNDLE}" "${STAGING_DIR}" "${DIST_DIR}/${DMG_NAME}"

echo "==> Build aplikace přes PyInstaller"
python3 -m PyInstaller --clean --noconfirm "${SPEC_FILE}"

if [[ ! -d "${DIST_DIR}/${APP_BUNDLE}" ]]; then
  echo "Chyba: ${DIST_DIR}/${APP_BUNDLE} nebyl vytvořen."
  exit 1
fi

if [[ -n "${CODESIGN_IDENTITY:-}" ]]; then
  echo "==> Podepisování aplikace (${CODESIGN_IDENTITY})"
  codesign --force --deep --sign "${CODESIGN_IDENTITY}" "${DIST_DIR}/${APP_BUNDLE}"
fi

echo "==> Příprava obsahu DMG"
mkdir -p "${STAGING_DIR}"
cp -R "${DIST_DIR}/${APP_BUNDLE}" "${STAGING_DIR}/"
ln -s /Applications "${STAGING_DIR}/Applications"

echo "==> Vytvářím DMG instalátor"
hdiutil create \
  -volname "${DMG_VOL_NAME}" \
  -srcfolder "${STAGING_DIR}" \
  -ov \
  -format UDZO \
  "${DIST_DIR}/${DMG_NAME}"

echo "Hotovo: ${DIST_DIR}/${DMG_NAME}"
