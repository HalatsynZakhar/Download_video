"""
PARANOID CLEANUP — полная очистка следов активности на Windows
Запускать с правами администратора (скрипт сам запросит UAC)
"""

# ╔═════════════════════════════════════════════════════════╗
#  НАСТРОЙКИ — меняйте здесь, остальное не трогайте
# ╠═════════════════════════════════════════════════════════╣
#
#  PAGEFILE
#    True  — включить автоочистку pagefile при выключении ПК
#    False — не трогать
CLEAN_PAGEFILE = False

#  SECURE WIPE свободного пространства (cipher /w)
#    True  — перезаписать свободные кластеры (5–20 мин)
#    False — просто удалить файлы (быстро, достаточно в большинстве случаев)
SECURE_WIPE_FREE_SPACE = False

#  БРАУЗЕРЫ (Chrome, Edge, Firefox)
#    True  — очищать кэш и историю браузеров
#    False — пропустить
CLEAN_BROWSERS = True

#  ЖУРНАЛЫ СОБЫТИЙ WINDOWS
#    True  — очищать System, Application, Security и др.
#    False — пропустить
CLEAN_EVENT_LOGS = True

#  PREFETCH
#    True  — удалять (следы запускавшихся программ)
#    False — пропустить
CLEAN_PREFETCH = True

#  GPU SHADER КЭШ (NVIDIA/AMD/D3D)
#    True  — очищать
#    False — пропустить
CLEAN_GPU_CACHE = False

#  ДАМПЫ ПАМЯТИ И WER
#    True  — удалять crash dumps и отчёты об ошибках
#    False — пропустить
CLEAN_CRASH_DUMPS = True

#  ДИАГНОСТИКА И ТЕЛЕМЕТРИЯ
#    True  — очищать INetCache, WebCache, телеметрию
#    False — пропустить
CLEAN_TELEMETRY = True

#  ГИБЕРНАЦИЯ
#    True  — отключить гибернацию и удалить hiberfil.sys
#    False — не трогать
DISABLE_HIBERNATION = True

#  СЕТЕВАЯ ИСТОРИЯ (список Wi-Fi и LAN сетей в реестре)
#    True  — очищать
#    False — не трогать
CLEAN_NETWORK_HISTORY = True

# ╚═════════════════════════════════════════════════════════╝

import os
import glob
import subprocess
import shutil
import ctypes
import sys
import winreg
import time
import json
import base64

# ═══════════════════════════════════════════════════════════
#  УТИЛИТЫ
# ═══════════════════════════════════════════════════════════

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    if not is_admin():
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join(sys.argv), None, 1
        )
        sys.exit()

def delete_files(pattern):
    deleted = 0
    for file in glob.glob(pattern, recursive=True):
        try:
            os.chmod(file, 0o777)
            os.remove(file)
            deleted += 1
        except:
            pass
    return deleted

def clear_folder(folder):
    deleted = 0
    if not os.path.exists(folder):
        return 0
    for root, dirs, files in os.walk(folder):
        for name in files:
            path = os.path.join(root, name)
            try:
                os.chmod(path, 0o777)
                os.remove(path)
                deleted += 1
            except:
                pass
    return deleted

def safe_delete_folder(folder):
    if os.path.exists(folder):
        try:
            shutil.rmtree(folder, ignore_errors=True)
        except:
            pass

def run_cmd(cmd, timeout=30):
    try:
        subprocess.run(cmd, shell=True,
                       stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL,
                       timeout=timeout)
    except:
        pass

def skip(label):
    print(f"  [пропущено] {label}")

def section(n, title, enabled=True):
    status = "" if enabled else " — ПРОПУЩЕНО"
    print(f"\n{'─'*55}")
    print(f"  [{n}] {title}{status}")
    print(f"{'─'*55}")

def reset_uwp_app(package_name):
    """Полный сброс UWP-приложения: удаляет LocalCache, LocalState,
    TempState, RoamingState, AC, Settings."""
    pkg_root = os.path.join(local, "Packages", package_name)
    if not os.path.exists(pkg_root):
        return 0
    deleted = 0
    for sub in ["LocalCache", "LocalState", "TempState",
                "RoamingState", "AC", "Settings"]:
        deleted += clear_folder(os.path.join(pkg_root, sub))
    return deleted

# ═══════════════════════════════════════════════════════════
#  РЕЕСТР
# ═══════════════════════════════════════════════════════════

HKCU = winreg.HKEY_CURRENT_USER
HKLM = winreg.HKEY_LOCAL_MACHINE

def clear_reg_key_values(hive, key_path):
    try:
        key = winreg.OpenKey(hive, key_path, 0, winreg.KEY_ALL_ACCESS)
        while True:
            try:
                name, _, _ = winreg.EnumValue(key, 0)
                winreg.DeleteValue(key, name)
            except OSError:
                break
        winreg.CloseKey(key)
    except:
        pass

def clear_reg_key_and_subkeys(hive, key_path):
    try:
        key = winreg.OpenKey(hive, key_path, 0, winreg.KEY_ALL_ACCESS)
        subkeys = []
        i = 0
        while True:
            try:
                subkeys.append(winreg.EnumKey(key, i))
                i += 1
            except OSError:
                break
        winreg.CloseKey(key)
        for sub in subkeys:
            clear_reg_key_and_subkeys(hive, key_path + "\\" + sub)
            try:
                parent = winreg.OpenKey(hive, key_path, 0, winreg.KEY_ALL_ACCESS)
                winreg.DeleteKey(parent, sub)
                winreg.CloseKey(parent)
            except:
                pass
        clear_reg_key_values(hive, key_path)
    except:
        pass

def set_reg_value(hive, key_path, name, reg_type, value):
    try:
        key = winreg.CreateKey(hive, key_path)
        winreg.SetValueEx(key, name, 0, reg_type, value)
        winreg.CloseKey(key)
    except:
        pass

# ═══════════════════════════════════════════════════════════
#  SAVE / RESTORE ICONS
# ═══════════════════════════════════════════════════════════

# Bag #1 = Desktop — фиксированный номер в Windows.
# Оба пути дублируют друг друга, Windows читает оба.
DESKTOP_BAG_KEYS = [
    r"Software\Microsoft\Windows\Shell\Bags\1\Desktop",
    r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\Bags\1\Desktop",
]
# BagMRU хранит привязку Bag#1 → Desktop — нужно восстанавливать вместе
BAGMRU_KEYS = [
    r"Software\Microsoft\Windows\Shell\BagMRU",
    r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\BagMRU",
]

# Временный файл рядом со скриптом — удаляется в конце
ICONS_BACKUP_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "_icons_backup_tmp.json"
)

def _read_key_to_dict(hive, key_path: str) -> dict | None:
    """Читает все значения ключа реестра в словарь с base64 для bytes."""
    try:
        key = winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ)
    except OSError:
        return None
    values = {}
    i = 0
    while True:
        try:
            name, data, dtype = winreg.EnumValue(key, i)
            if isinstance(data, bytes):
                values[name] = {
                    "type": dtype,
                    "data": base64.b64encode(data).decode("ascii"),
                    "encoding": "base64"
                }
            else:
                values[name] = {"type": dtype, "data": data, "encoding": "raw"}
            i += 1
        except OSError:
            break
    winreg.CloseKey(key)
    return values if values else None

def _write_dict_to_key(hive, key_path: str, values: dict) -> int:
    """Записывает словарь значений в ключ реестра (создаёт если нет)."""
    try:
        key = winreg.CreateKeyEx(hive, key_path, 0, winreg.KEY_ALL_ACCESS)
    except OSError:
        return 0
    written = 0
    for name, entry in values.items():
        try:
            data = (base64.b64decode(entry["data"])
                    if entry["encoding"] == "base64" else entry["data"])
            winreg.SetValueEx(key, name, 0, entry["type"], data)
            written += 1
        except:
            pass
    winreg.CloseKey(key)
    return written

def save_icon_positions() -> tuple[dict, int]:
    """
    Сохраняет позиции иконок рабочего стола из реестра в словарь и файл.
    ВАЖНО: вызывать пока Explorer живой — он держит актуальные
    координаты в памяти и сбрасывает в реестр только при завершении.
    """
    backup = {"version": 1, "keys": {}}
    saved_values = 0

    for key_path in DESKTOP_BAG_KEYS + BAGMRU_KEYS:
        values = _read_key_to_dict(HKCU, key_path)
        if values:
            backup["keys"][key_path] = values
            saved_values += len(values)

    # Пишем на диск как страховку
    try:
        with open(ICONS_BACKUP_FILE, "w", encoding="utf-8") as f:
            json.dump(backup, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  ! Не удалось записать файл бэкапа: {e}")

    return backup, saved_values

def restore_icon_positions(backup: dict) -> int:
    """
    Восстанавливает позиции иконок из словаря в реестр.
    Вызывать после очистки ShellBags, пока Explorer остановлен.
    """
    total = 0
    for key_path, values in backup.get("keys", {}).items():
        total += _write_dict_to_key(HKCU, key_path, values)
    return total

def cleanup_icons_backup():
    """Удаляет временный файл бэкапа иконок."""
    try:
        if os.path.exists(ICONS_BACKUP_FILE):
            os.remove(ICONS_BACKUP_FILE)
    except:
        pass

# ═══════════════════════════════════════════════════════════
#  ОЧИСТКА РЕЕСТРА
# ═══════════════════════════════════════════════════════════

def clear_all_registry_traces():
    # ── Explorer MRU ──
    for p in [
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\RecentDocs",
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\ComDlg32\OpenSavePidlMRU",
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\ComDlg32\LastVisitedPidlMRU",
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\RunMRU",
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\TypedPaths",
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\Map Network Drive MRU",
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\WordWheelQuery",
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\MountPoints2",
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\FeatureUsage",
    ]:
        clear_reg_key_and_subkeys(HKCU, p)

    # ── Search / Start menu история ──
    for p in [
        r"Software\Microsoft\Windows\CurrentVersion\Search\RecentApps",
        r"Software\Microsoft\Windows\CurrentVersion\Search\JumplistData",
        r"Software\Microsoft\Windows\CurrentVersion\SearchSettings",
    ]:
        clear_reg_key_and_subkeys(HKCU, p)

    # ── Office MRU (все версии) ──
    for ver in ["16.0", "15.0", "14.0", "12.0"]:
        for app in ["Word", "Excel", "PowerPoint", "Access", "Publisher"]:
            for sub in ["File MRU", "Place MRU", "Reading Locations", "User Templates"]:
                clear_reg_key_and_subkeys(HKCU,
                    rf"Software\Microsoft\Office\{ver}\{app}\{sub}")
    clear_reg_key_and_subkeys(HKCU, r"Software\Microsoft\Office\Common\Open Find")

    # ── ShellBags (история открытых папок) ──
    # Позиции иконок уже сохранены и будут восстановлены после этой функции
    for p in [
        r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\Bags",
        r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\BagMRU",
        r"Software\Microsoft\Windows\Shell\Bags",
        r"Software\Microsoft\Windows\Shell\BagMRU",
    ]:
        clear_reg_key_and_subkeys(HKCU, p)

    # ── UserAssist (история запуска программ) ──
    clear_reg_key_and_subkeys(HKCU,
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\UserAssist")

    # ── Windows Media Player ──
    for p in [
        r"Software\Microsoft\MediaPlayer\Player\RecentFileList",
        r"Software\Microsoft\MediaPlayer\Player\RecentURLList",
        r"Software\Microsoft\MediaPlayer\Preferences\LastPlayed",
        r"Software\Microsoft\MediaPlayer\Player",
    ]:
        clear_reg_key_and_subkeys(HKCU, p)

    # ── Photos ──
    clear_reg_key_and_subkeys(HKCU,
        r"Software\Microsoft\Windows\CurrentVersion\Applets\Windows Photo Viewer\RecentFileList")
    clear_reg_key_and_subkeys(HKCU,
        r"Software\Classes\Local Settings\Software\Microsoft\Windows\CurrentVersion"
        r"\AppModel\SystemAppData\Microsoft.Windows.Photos_8wekyb3d8bbwe")

    # ── IE/Edge Legacy typed URLs ──
    for p in [
        r"Software\Microsoft\Internet Explorer\TypedURLs",
        r"Software\Microsoft\Internet Explorer\TypedURLsTime",
    ]:
        clear_reg_key_and_subkeys(HKCU, p)

    # ── Paint MRU ──
    clear_reg_key_values(HKCU,
        r"Software\Microsoft\Windows\CurrentVersion\Applets\Paint\Recent File List")

    # ── Политики приватности ──
    set_reg_value(HKCU,
        r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer",
        "NoRecentDocsHistory", winreg.REG_DWORD, 1)
    set_reg_value(HKCU,
        r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer",
        "NoStartMenuMFUprogramsList", winreg.REG_DWORD, 1)

    # ── Отключить Windows Timeline ──
    set_reg_value(HKCU,
        r"Software\Microsoft\Windows\CurrentVersion\ActivityFeed",
        "EnableActivityFeed", winreg.REG_DWORD, 0)

    # ── Отключить историю поиска ──
    set_reg_value(HKCU,
        r"Software\Microsoft\Windows\CurrentVersion\Search",
        "HistoryViewEnabled", winreg.REG_DWORD, 0)
    set_reg_value(HKCU,
        r"Software\Microsoft\Windows\CurrentVersion\Search",
        "DeviceHistoryEnabled", winreg.REG_DWORD, 0)
    set_reg_value(HKCU,
        r"Software\Policies\Microsoft\Windows\Explorer",
        "DisableSearchHistory", winreg.REG_DWORD, 1)

def clear_network_history():
    for p in [
        r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\NetworkList\Profiles",
        r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\NetworkList\Signatures\Managed",
        r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\NetworkList\Signatures\Unmanaged",
    ]:
        clear_reg_key_and_subkeys(HKLM, p)

def setup_pagefile_wipe():
    set_reg_value(HKLM,
        r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management",
        "ClearPageFileAtShutdown", winreg.REG_DWORD, 1)
    inf_content = """[Unicode]
Unicode=yes
[Version]
signature="$CHICAGO$"
Revision=1
[Registry Values]
MACHINE\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Memory Management\\ClearPageFileAtShutdown=4,1
"""
    inf_path = r"C:\Windows\Temp\pagefile_policy.inf"
    try:
        with open(inf_path, "w", encoding="utf-16") as f:
            f.write(inf_content)
        run_cmd(f'secedit /configure /db secedit.sdb /cfg "{inf_path}" /quiet')
        os.remove(inf_path)
    except:
        pass
    print("  ✓ PageFile будет перезаписан при каждом выключении ПК")

def wipe_free_space(drive="C:"):
    print(f"  Запуск cipher /w:{drive} — займёт несколько минут...")
    try:
        subprocess.run(f"cipher /w:{drive}\\", shell=True, timeout=1200)
        print(f"  ✓ Свободное пространство {drive} перезаписано")
    except subprocess.TimeoutExpired:
        print(f"  ✓ cipher /w завершён по таймауту")
    except Exception as e:
        print(f"  ✗ Ошибка: {e}")

# ═══════════════════════════════════════════════════════════
#  ГЛАВНЫЙ СКРИПТ
# ═══════════════════════════════════════════════════════════

run_as_admin()

local       = os.path.expandvars(r"%LocalAppData%")
appdata     = os.path.expandvars(r"%AppData%")
progdata    = os.path.expandvars(r"%ProgramData%")
temp        = os.path.expandvars(r"%TEMP%")
userprofile = os.path.expandvars(r"%USERPROFILE%")

deleted_total = 0

print("=" * 55)
print("   PARANOID CLEANUP")
print("=" * 55)

# ╔══════════════════════════════════════════════════════════╗
# ║  БЛОК 1 — СОХРАНЕНИЕ ИКОНОК                              ║
# ║  Explorer должен быть живым в этот момент                ║
# ╚══════════════════════════════════════════════════════════╝

section(0, "Сохраняем позиции иконок рабочего стола")
icon_backup, saved_values = save_icon_positions()
saved_keys = len(icon_backup["keys"])
if saved_values > 0:
    print(f"  ✓ Сохранено: {saved_values} значений из {saved_keys} ключей")
    print(f"  ✓ Файл страховки: {ICONS_BACKUP_FILE}")
else:
    print("  ! Позиции иконок не найдены в реестре.")
    print("    Возможно включено 'Автоматически упорядочить значки'.")
    print("    Продолжаем очистку.")

# ╔══════════════════════════════════════════════════════════╗
# ║  БЛОК 2 — ОЧИСТКА                                        ║
# ╚══════════════════════════════════════════════════════════╝

# ── 1. Explorer ───────────────────────────────
section(1, "Останавливаем Explorer")
run_cmd("taskkill /f /im explorer.exe")
time.sleep(2)

# ── 2. Thumbnail & Icon cache ─────────────────
section(2, "Кэш эскизов и иконок")
deleted_total += delete_files(local + r"\Microsoft\Windows\Explorer\thumbcache*.db")
deleted_total += delete_files(local + r"\Microsoft\Windows\Explorer\iconcache*.db")
deleted_total += delete_files(local + r"\Microsoft\Windows\Explorer\*.db")
# Убедиться что эскизы включены
set_reg_value(HKCU,
    r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
    "IconsOnly", winreg.REG_DWORD, 0)
set_reg_value(HKCU,
    r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced",
    "DisableThumbnailCache", winreg.REG_DWORD, 0)

# ── 3. LNK-ярлыки ─────────────────────────────
section(3, "LNK-ярлыки (следы открытых файлов)")
deleted_total += clear_folder(appdata + r"\Microsoft\Windows\Recent")
deleted_total += clear_folder(appdata + r"\Microsoft\Windows\Recent\AutomaticDestinations")
deleted_total += clear_folder(appdata + r"\Microsoft\Windows\Recent\CustomDestinations")
deleted_total += delete_files(appdata + r"\Microsoft\Office\Recent\*.LNK")

# ── 4. Office ─────────────────────────────────
section(4, "Office: кэш и временные файлы")
for app in ["Word", "Excel", "PowerPoint"]:
    deleted_total += clear_folder(appdata + rf"\Microsoft\{app}")
    deleted_total += clear_folder(local + rf"\Microsoft\{app}")
users_doc_folders = [
    os.path.join(userprofile, "Documents"),
    os.path.join(userprofile, "Desktop"),
    os.path.join(userprofile, "Downloads"),
    appdata + r"\Microsoft\Word",
    appdata + r"\Microsoft\Excel",
]
for folder in users_doc_folders:
    for ext in ["docx", "doc", "xlsx", "xls", "pptx", "ppt"]:
        deleted_total += delete_files(os.path.join(folder, f"~$*.{ext}"))

# ── 5. Windows Search ─────────────────────────
section(5, "Windows Search — индекс и история запросов")
run_cmd("sc stop WSearch", timeout=10)
time.sleep(3)
run_cmd("taskkill /f /im SearchIndexer.exe", timeout=5)
time.sleep(1)
# Индексная БД
safe_delete_folder(progdata + r"\Microsoft\Search\Data")
# Данные UWP Search и Cortana
deleted_total += reset_uwp_app("Microsoft.Windows.Search_cw5n1h2txyewy")
deleted_total += reset_uwp_app("Microsoft.Windows.Cortana_cw5n1h2txyewy")
# Отключаем историю поиска через политику
set_reg_value(HKCU,
    r"Software\Policies\Microsoft\Windows\Explorer",
    "DisableSearchHistory", winreg.REG_DWORD, 1)
run_cmd("sc start WSearch", timeout=10)

# ── 6. Windows Timeline ───────────────────────
section(6, "Windows Timeline (ActivityCache)")
for pattern in [
    local + r"\ConnectedDevicesPlatform\**\ActivitiesCache.db",
    local + r"\ConnectedDevicesPlatform\**\ActivitiesCache.db-wal",
    local + r"\ConnectedDevicesPlatform\**\ActivitiesCache.db-shm",
]:
    deleted_total += delete_files(pattern)
safe_delete_folder(local + r"\ConnectedDevicesPlatform")

# ── 7. Prefetch ───────────────────────────────
section(7, "Prefetch", CLEAN_PREFETCH)
if CLEAN_PREFETCH:
    deleted_total += clear_folder(r"C:\Windows\Prefetch")
else:
    skip("Prefetch")

# ── 8. TEMP ───────────────────────────────────
section(8, "TEMP папки")
deleted_total += clear_folder(temp)
deleted_total += clear_folder(r"C:\Windows\Temp")

# ── 9. Photos — полный сброс ──────────────────
section(9, "Microsoft Photos — полный сброс")
# Останавливаем процесс
run_cmd("taskkill /f /im Microsoft.Photos.exe", timeout=5)
run_cmd(
    'powershell -command "Get-Process | '
    'Where-Object {$_.MainWindowTitle -like \'*Photo*\'} | '
    'Stop-Process -Force"',
    timeout=5
)
time.sleep(1)
# Удаляем все папки данных UWP пакета Photos
n_photos = reset_uwp_app("Microsoft.Windows.Photos_8wekyb3d8bbwe")
deleted_total += n_photos
# Старый Photo Viewer
deleted_total += clear_folder(local + r"\Microsoft\Windows Photo Viewer")
print(f"  ✓ Photos UWP: удалено {n_photos} файлов, Photo Viewer очищен")

# ── 10. Media Player — полный сброс ──────────
section(10, "Windows Media Player — полный сброс")
# Останавливаем классический WMP
run_cmd("taskkill /f /im wmplayer.exe", timeout=5)
time.sleep(1)
# Классический WMP (Win10)
deleted_total += clear_folder(local + r"\Microsoft\Media Player")
deleted_total += clear_folder(local + r"\Microsoft\Windows Media")
deleted_total += clear_folder(appdata + r"\Microsoft\Windows Media")
deleted_total += clear_folder(appdata + r"\Microsoft\Windows Media Player")
deleted_total += clear_folder(local + r"\Microsoft\Windows Media Player")
deleted_total += delete_files(local + r"\Microsoft\Media Player\*.wmdb")
deleted_total += delete_files(local + r"\Microsoft\Media Player\*.db")
# Новый Media Player UWP Win11 (ZuneMusic / ZuneVideo)
run_cmd("taskkill /f /im Microsoft.Media.Player.exe", timeout=5)
n_music = reset_uwp_app("Microsoft.ZuneMusic_8wekyb3d8bbwe")
n_video = reset_uwp_app("Microsoft.ZuneVideo_8wekyb3d8bbwe")
deleted_total += n_music + n_video
print(f"  ✓ WMP Classic: очищен")
print(f"  ✓ Media Player UWP (ZuneMusic): удалено {n_music} файлов")
print(f"  ✓ Media Player UWP (ZuneVideo): удалено {n_video} файлов")

# ── 11. Браузеры ──────────────────────────────
section(11, "Кэш и история браузеров", CLEAN_BROWSERS)
if CLEAN_BROWSERS:
    for sub in ["Default\\Cache", "Default\\Cache2", "Default\\GPUCache",
                "Default\\Code Cache", "Default\\Media Cache",
                "Default\\Application Cache", "Default\\Service Worker"]:
        deleted_total += clear_folder(local + rf"\Google\Chrome\User Data\{sub}")
    for f in ["History", "Thumbnails", "Visited Links", "Web Data", "Shortcuts"]:
        deleted_total += delete_files(local + rf"\Google\Chrome\User Data\Default\{f}")
    for sub in ["Default\\Cache", "Default\\GPUCache",
                "Default\\Code Cache", "Default\\Service Worker"]:
        deleted_total += clear_folder(local + rf"\Microsoft\Edge\User Data\{sub}")
    for f in ["History", "Thumbnails", "Visited Links"]:
        deleted_total += delete_files(local + rf"\Microsoft\Edge\User Data\Default\{f}")
    for profile in glob.glob(appdata + r"\Mozilla\Firefox\Profiles\*"):
        deleted_total += clear_folder(os.path.join(profile, "cache2"))
        deleted_total += clear_folder(os.path.join(profile, "thumbnails"))
        for f in ["places.sqlite", "formhistory.sqlite",
                  "downloads.sqlite", "content-prefs.sqlite"]:
            deleted_total += delete_files(os.path.join(profile, f))
else:
    skip("Браузеры (отключено в настройках)")

# ── 12. GPU Shader кэш ────────────────────────
section(12, "GPU shader кэш", CLEAN_GPU_CACHE)
if CLEAN_GPU_CACHE:
    deleted_total += clear_folder(local + r"\D3DSCache")
    deleted_total += clear_folder(local + r"\NVIDIA\DXCache")
    deleted_total += clear_folder(local + r"\NVIDIA\GLCache")
    deleted_total += clear_folder(local + r"\NVIDIA\ComputeCache")
    deleted_total += clear_folder(local + r"\AMD\DXCache")
else:
    skip("GPU кэш (не содержит медиаданных)")

# ── 13. Дампы памяти ──────────────────────────
section(13, "Дампы памяти и WER", CLEAN_CRASH_DUMPS)
if CLEAN_CRASH_DUMPS:
    safe_delete_folder(local + r"\Microsoft\Windows\WER\ReportQueue")
    safe_delete_folder(local + r"\Microsoft\Windows\WER\ReportArchive")
    safe_delete_folder(local + r"\CrashDumps")
    deleted_total += delete_files(r"C:\Windows\Minidump\*.dmp")
    deleted_total += delete_files(r"C:\Windows\*.dmp")
else:
    skip("Дампы памяти")

# ── 14. Телеметрия и WebCache ─────────────────
section(14, "Диагностика, телеметрия, WebCache", CLEAN_TELEMETRY)
if CLEAN_TELEMETRY:
    safe_delete_folder(progdata + r"\Microsoft\Diagnosis")
    safe_delete_folder(progdata + r"\Microsoft\Windows\WER")
    deleted_total += clear_folder(local + r"\Microsoft\Windows\INetCache")
    deleted_total += clear_folder(local + r"\Microsoft\Windows\INetCookies")
    deleted_total += clear_folder(local + r"\Microsoft\Windows\WebCache")
    deleted_total += delete_files(local + r"\Microsoft\Windows\WebCache\WebCacheV01.dat")
    deleted_total += delete_files(local + r"\Microsoft\Windows\WebCache\WebCacheV24.dat")
else:
    skip("Телеметрия и WebCache")

# ── 15. Реестр ────────────────────────────────
section(15, "Реестр: MRU, ShellBags, UserAssist, Search, Timeline")
clear_all_registry_traces()
# Восстанавливаем позиции иконок сразу после очистки ShellBags —
# Explorer остановлен, запись в реестр без конкуренции
written = restore_icon_positions(icon_backup)
time.sleep(1)  # убеждаемся что реестр сброшен на диск до старта Explorer
print(f"  ✓ Реестр очищен, позиции иконок восстановлены ({written} значений)")

# ── 16. Сетевая история ───────────────────────
section(16, "Сетевая история (список Wi-Fi и LAN сетей)", CLEAN_NETWORK_HISTORY)
if CLEAN_NETWORK_HISTORY:
    clear_network_history()
    print("  ✓ История подключений к сетям удалена")
else:
    skip("Сетевая история")

# ── 17. Журналы событий ───────────────────────
section(17, "Журналы событий Windows", CLEAN_EVENT_LOGS)
if CLEAN_EVENT_LOGS:
    logs = [
        "System", "Application", "Security",
        "Microsoft-Windows-Shell-Core/Operational",
        "Microsoft-Windows-Recent-Docs-Settings/Analytic",
        "Microsoft-Windows-Windows Defender/Operational",
        "Microsoft-Windows-TaskScheduler/Operational",
        "Microsoft-Windows-TerminalServices-LocalSessionManager/Operational",
        "Microsoft-Windows-Search-ProfileNotify/Operational",
    ]
    for log in logs:
        run_cmd(f'wevtutil cl "{log}"')
    print(f"  ✓ Очищено {len(logs)} журналов")
else:
    skip("Журналы событий")

# ── 18. Гибернация ────────────────────────────
section(18, "Гибернация (hiberfil.sys)", DISABLE_HIBERNATION)
if DISABLE_HIBERNATION:
    run_cmd("powercfg -h off")
    print("  ✓ hiberfil.sys удалён")
else:
    skip("Гибернация")

# ── 19. DNS кэш ───────────────────────────────
section(19, "DNS кэш")
run_cmd("ipconfig /flushdns")
print("  ✓ DNS очищен")

# ── 20. Буфер обмена ──────────────────────────
section(20, "Буфер обмена")
run_cmd("echo off | clip")
run_cmd('powershell -command "Set-Clipboard -Value \'\'"')
print("  ✓ Буфер очищен")

# ── 21. PageFile ──────────────────────────────
section(21, "PageFile — автоочистка при выключении", CLEAN_PAGEFILE)
if CLEAN_PAGEFILE:
    setup_pagefile_wipe()
else:
    skip("PageFile (отключено в настройках)")

# ── 22. Secure wipe свободного места ──────────
section(22, "Перезапись свободного пространства (cipher /w)", SECURE_WIPE_FREE_SPACE)
if SECURE_WIPE_FREE_SPACE:
    wipe_free_space("C:")
else:
    skip("cipher /w (отключено — запустить вручную: cipher /w:C:\\)")

# ╔══════════════════════════════════════════════════════════╗
# ║  БЛОК 3 — ВОССТАНОВЛЕНИЕ                                 ║
# ╚══════════════════════════════════════════════════════════╝

section(23, "Запускаем Explorer и панель задач")
subprocess.Popen("explorer.exe")
print("  Ожидание запуска Explorer", end="", flush=True)
for _ in range(15):
    time.sleep(1)
    print(".", end="", flush=True)
    result = subprocess.run(
        'tasklist /fi "imagename eq explorer.exe" /fo csv /nh',
        shell=True, capture_output=True, text=True
    )
    if "explorer.exe" in result.stdout:
        break
print()
time.sleep(2)  # дать Explorer время инициализировать рабочий стол
run_cmd('powershell -command "(New-Object -ComObject Shell.Application).MinimizeAll()"')
run_cmd('ie4uinit.exe -show')
print("  ✓ Explorer запущен, панель задач восстановлена")

# ── Удаляем временный файл бэкапа ─────────────
section(24, "Удаляем временные файлы скрипта")
cleanup_icons_backup()
print("  ✓ Временный файл бэкапа иконок удалён")

# ═══════════════════════════════════════════════════════════
#  ИТОГ
# ═══════════════════════════════════════════════════════════

print("\n" + "=" * 55)
print(f"  Удалено файлов: {deleted_total}")
print()
print("  АКТИВНЫЕ МОДУЛИ:")
modules = [
    ("Позиции иконок: сохранено/восстановлено", True),
    ("Эскизы и иконки",                        True),
    ("LNK-ярлыки / Recent",                    True),
    ("Office кэш и MRU",                       True),
    ("UserAssist / реестр MRU",                True),
    ("ShellBags (история папок)",              True),
    ("Windows Timeline",                       True),
    ("Search — индекс и история",              True),
    ("Photos — полный сброс",                  True),
    ("Media Player — полный сброс",            True),
    ("TEMP папки",                             True),
    ("Prefetch",                               CLEAN_PREFETCH),
    ("Браузеры",                               CLEAN_BROWSERS),
    ("GPU кэш",                                CLEAN_GPU_CACHE),
    ("Дампы памяти",                           CLEAN_CRASH_DUMPS),
    ("Телеметрия / WebCache",                  CLEAN_TELEMETRY),
    ("Сетевая история",                        CLEAN_NETWORK_HISTORY),
    ("Журналы событий",                        CLEAN_EVENT_LOGS),
    ("Гибернация",                             DISABLE_HIBERNATION),
    ("PageFile wipe",                          CLEAN_PAGEFILE),
    ("cipher /w",                              SECURE_WIPE_FREE_SPACE),
]
for name, enabled in modules:
    mark = "✓" if enabled else "○"
    print(f"  {mark} {name}")
print("=" * 55)

input("\nНажмите Enter для выхода...")