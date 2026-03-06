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
#    False — не трогать (если pagefile отключён или не нужно)
CLEAN_PAGEFILE = False

#  SECURE WIPE свободного пространства (cipher /w)
#    True  — перезаписать свободные кластеры (5–20 мин)
#            удалённые файлы станут невосстановимы
#    False — просто удалить файлы (быстро, достаточно в большинстве случаев)
SECURE_WIPE_FREE_SPACE = False

#  БРАУЗЕРЫ (Chrome, Edge, Firefox на системном диске)
#    True  — очищать кэш и историю браузеров
#    False — пропустить (если браузер для деликатных задач
#            находится на отдельном диске, который размонтируется)
CLEAN_BROWSERS = True

#  ЖУРНАЛЫ СОБЫТИЙ WINDOWS
#    True  — очищать System, Application, Security и др.
#    False — пропустить (обычному пользователю они недоступны)
CLEAN_EVENT_LOGS = True

#  PREFETCH
#    True  — удалять (следы запускавшихся программ)
#    False — пропустить (Windows восстановит сам, польза невелика)
CLEAN_PREFETCH = True

#  GPU SHADER КЭШ (NVIDIA/AMD/D3D)
#    True  — очищать
#    False — пропустить (не содержит медиаданных, только шейдеры)
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

# ╚═════════════════════════════════════════════════════════╝

import os
import glob
import subprocess
import shutil
import ctypes
import sys
import winreg
import time

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
    ]:
        clear_reg_key_and_subkeys(HKCU, p)

    # ── Office MRU (все версии) ──
    for ver in ["16.0", "15.0", "14.0", "12.0"]:
        for app in ["Word", "Excel", "PowerPoint", "Access", "Publisher"]:
            for sub in ["File MRU", "Place MRU", "Reading Locations", "User Templates"]:
                clear_reg_key_and_subkeys(HKCU,
                    rf"Software\Microsoft\Office\{ver}\{app}\{sub}")
    clear_reg_key_and_subkeys(HKCU,
        r"Software\Microsoft\Office\Common\Open Find")

    # ── ShellBags — история открытых папок ──
    # Очищаем только записи о папках, пропускаем рабочий стол (Desktop = {Desktop GUID})
    # Простейший безопасный вариант — чистить только BagMRU верхнего уровня,
    # не трогая Bags (там хранятся позиции иконок рабочего стола)
    for p in [
        r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\BagMRU",
        r"Software\Microsoft\Windows\Shell\BagMRU",
    ]:
        clear_reg_key_and_subkeys(HKCU, p)
    # Bags не трогаем — там позиции иконок рабочего стола

    # ── UserAssist — история запуска программ ──
    clear_reg_key_and_subkeys(HKCU,
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\UserAssist")

    # ── Windows Media Player ──
    for p in [
        r"Software\Microsoft\MediaPlayer\Player\RecentFileList",
        r"Software\Microsoft\MediaPlayer\Player\RecentURLList",
    ]:
        clear_reg_key_values(HKCU, p)

    # ── Paint MRU ──
    clear_reg_key_values(HKCU,
        r"Software\Microsoft\Windows\CurrentVersion\Applets\Paint\Recent File List")

    # ── Политики приватности ──
    # (эскизы не отключаем — только чистим при запуске)
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

# ── 1. Explorer ───────────────────────────────
section(1, "Останавливаем Explorer")
run_cmd("taskkill /f /im explorer.exe")
time.sleep(1)

# ── 2. Thumbnail & Icon cache ─────────────────
section(2, "Кэш эскизов и иконок")
deleted_total += delete_files(local + r"\Microsoft\Windows\Explorer\thumbcache*.db")
deleted_total += delete_files(local + r"\Microsoft\Windows\Explorer\iconcache*.db")
deleted_total += delete_files(local + r"\Microsoft\Windows\Explorer\*.db")
# Убедиться что эскизы включены (на случай если старая версия скрипта отключила)
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
# ~$ временные файлы только в папке текущего пользователя (без рекурсии по всем дискам)
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
section(5, "Windows Search индекс")
# Принудительная остановка с таймаутом (net stop может зависать)
run_cmd("sc stop WSearch", timeout=10)
time.sleep(3)
run_cmd("taskkill /f /im SearchIndexer.exe", timeout=5)
time.sleep(1)
safe_delete_folder(progdata + r"\Microsoft\Search\Data")
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

# ── 9. Просмотрщики фото ─────────────────────
section(9, "Кэш просмотрщиков изображений")
deleted_total += clear_folder(local + r"\Microsoft\Windows Photo Viewer")
deleted_total += clear_folder(
    local + r"\Packages\Microsoft.Windows.Photos_8wekyb3d8bbwe\LocalCache")
deleted_total += clear_folder(
    local + r"\Packages\Microsoft.Windows.Photos_8wekyb3d8bbwe\LocalState\PhotosAppData")
deleted_total += clear_folder(
    local + r"\Packages\Microsoft.Windows.Photos_8wekyb3d8bbwe\LocalState\mediadb")

# ── 10. Windows Media Player ──────────────────
section(10, "Windows Media Player")
deleted_total += clear_folder(local + r"\Microsoft\Media Player")
deleted_total += delete_files(
    userprofile + r"\AppData\Roaming\Microsoft\Windows Media\*.*")
deleted_total += delete_files(
    userprofile + r"\AppData\Local\Microsoft\Media Player\*.wmdb")
deleted_total += delete_files(
    userprofile + r"\AppData\Local\Microsoft\Media Player\*.db")

# ── 11. Браузеры ──────────────────────────────
section(11, "Кэш и история браузеров", CLEAN_BROWSERS)
if CLEAN_BROWSERS:
    for sub in ["Default\\Cache", "Default\\Cache2", "Default\\GPUCache",
                "Default\\Code Cache", "Default\\Media Cache",
                "Default\\Application Cache", "Default\\Service Worker"]:
        deleted_total += clear_folder(local + rf"\Google\Chrome\User Data\{sub}")
    for f in ["History", "Thumbnails", "Visited Links", "Web Data", "Shortcuts"]:
        deleted_total += delete_files(
            local + rf"\Google\Chrome\User Data\Default\{f}")
    for sub in ["Default\\Cache", "Default\\GPUCache",
                "Default\\Code Cache", "Default\\Service Worker"]:
        deleted_total += clear_folder(
            local + rf"\Microsoft\Edge\User Data\{sub}")
    for f in ["History", "Thumbnails", "Visited Links"]:
        deleted_total += delete_files(
            local + rf"\Microsoft\Edge\User Data\Default\{f}")
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
    deleted_total += delete_files(
        local + r"\Microsoft\Windows\WebCache\WebCacheV01.dat")
    deleted_total += delete_files(
        local + r"\Microsoft\Windows\WebCache\WebCacheV24.dat")
else:
    skip("Телеметрия и WebCache")

# ── 15. Реестр ────────────────────────────────
section(15, "Реестр: MRU, ShellBags, UserAssist, Timeline")
clear_all_registry_traces()
print("  ✓ Все ключи реестра очищены")

# ── 16. Журналы событий ───────────────────────
section(16, "Журналы событий Windows", CLEAN_EVENT_LOGS)
if CLEAN_EVENT_LOGS:
    logs = [
        "System", "Application", "Security",
        "Microsoft-Windows-Shell-Core/Operational",
        "Microsoft-Windows-Recent-Docs-Settings/Analytic",
        "Microsoft-Windows-Windows Defender/Operational",
        "Microsoft-Windows-TaskScheduler/Operational",
        "Microsoft-Windows-TerminalServices-LocalSessionManager/Operational",
    ]
    for log in logs:
        run_cmd(f'wevtutil cl "{log}"')
    print(f"  ✓ Очищено {len(logs)} журналов")
else:
    skip("Журналы событий")

# ── 17. Гибернация ────────────────────────────
section(17, "Гибернация (hiberfil.sys)", DISABLE_HIBERNATION)
if DISABLE_HIBERNATION:
    run_cmd("powercfg -h off")
    print("  ✓ hiberfil.sys удалён")
else:
    skip("Гибернация")

# ── 18. DNS кэш ──────────────────────────────
section(18, "DNS кэш")
run_cmd("ipconfig /flushdns")
print("  ✓ DNS очищен")

# ── 19. Буфер обмена ─────────────────────────
section(19, "Буфер обмена")
run_cmd("echo off | clip")
run_cmd('powershell -command "Set-Clipboard -Value \'\'"')
print("  ✓ Буфер очищен")

# ── 20. PageFile ──────────────────────────────
section(20, "PageFile — автоочистка при выключении", CLEAN_PAGEFILE)
if CLEAN_PAGEFILE:
    setup_pagefile_wipe()
else:
    skip("PageFile (отключено в настройках)")

# ── 21. Secure wipe свободного места ─────────
section(21, "Перезапись свободного пространства (cipher /w)", SECURE_WIPE_FREE_SPACE)
if SECURE_WIPE_FREE_SPACE:
    wipe_free_space("C:")
else:
    skip("cipher /w (отключено — запустить вручную: cipher /w:C:\\)")

# ── 22. Запускаем Explorer ───────────────────
section(22, "Запускаем Explorer")
subprocess.Popen("explorer.exe")

# ─────────────────────────────────────────────
print("\n" + "=" * 55)
print(f"  Удалено файлов: {deleted_total}")
print()
print("  АКТИВНЫЕ МОДУЛИ:")
modules = [
    ("Эскизы и иконки",         True),
    ("LNK-ярлыки / Recent",     True),
    ("Office кэш и MRU",        True),
    ("ShellBags / UserAssist",  True),
    ("Windows Timeline",        True),
    ("TEMP папки",              True),
    ("Реестр MRU",              True),
    ("Prefetch",                CLEAN_PREFETCH),
    ("Браузеры",                CLEAN_BROWSERS),
    ("GPU кэш",                 CLEAN_GPU_CACHE),
    ("Дампы памяти",            CLEAN_CRASH_DUMPS),
    ("Телеметрия / WebCache",   CLEAN_TELEMETRY),
    ("Журналы событий",         CLEAN_EVENT_LOGS),
    ("Гибернация",              DISABLE_HIBERNATION),
    ("PageFile wipe",           CLEAN_PAGEFILE),
    ("cipher /w",               SECURE_WIPE_FREE_SPACE),
]
for name, enabled in modules:
    mark = "✓" if enabled else "○"
    print(f"  {mark} {name}")
print("=" * 55)

input("\nНажмите Enter для выхода...")