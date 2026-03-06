import os
import glob
import shutil
import subprocess

def delete_files(pattern):
    files = glob.glob(pattern)
    deleted = 0
    for f in files:
        try:
            os.remove(f)
            deleted += 1
        except:
            pass
    return deleted

def clear_folder(folder):
    deleted = 0
    if os.path.exists(folder):
        for root, dirs, files in os.walk(folder):
            for name in files:
                try:
                    os.remove(os.path.join(root, name))
                    deleted += 1
                except:
                    pass
    return deleted

print("Закрываем Explorer...")
subprocess.run("taskkill /f /im explorer.exe", shell=True)

local = os.path.expandvars(r"%LocalAppData%")
appdata = os.path.expandvars(r"%AppData%")
temp = os.path.expandvars(r"%TEMP%")

deleted_total = 0

# 1. Thumbnail cache
deleted_total += delete_files(local + r"\Microsoft\Windows\Explorer\thumbcache*.db")

# 2. Icon cache
deleted_total += delete_files(local + r"\Microsoft\Windows\Explorer\iconcache*.db")

# 3. Explorer cache
deleted_total += delete_files(local + r"\Microsoft\Windows\Explorer\*.db")

# 4. Recent files
deleted_total += clear_folder(appdata + r"\Microsoft\Windows\Recent")

# 5. Jump Lists
deleted_total += clear_folder(appdata + r"\Microsoft\Windows\Recent\AutomaticDestinations")
deleted_total += clear_folder(appdata + r"\Microsoft\Windows\Recent\CustomDestinations")

# 6. Temp user
deleted_total += clear_folder(temp)

# 7. Windows temp
deleted_total += clear_folder(r"C:\Windows\Temp")

# 8. Edge/Chrome image cache
deleted_total += clear_folder(local + r"\Microsoft\Edge\User Data\Default\Cache")
deleted_total += clear_folder(local + r"\Google\Chrome\User Data\Default\Cache")

print(f"Удалено файлов: {deleted_total}")

print("Запускаем Explorer...")
subprocess.Popen("explorer.exe")

input("Очистка завершена. Нажмите Enter для выхода.")