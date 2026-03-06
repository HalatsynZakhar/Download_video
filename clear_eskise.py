import os
import glob
import subprocess
import shutil

def delete_files(pattern):
    deleted = 0
    for file in glob.glob(pattern):
        try:
            os.remove(file)
            deleted += 1
        except:
            pass
    return deleted

def clear_folder(folder):
    deleted = 0
    if os.path.exists(folder):
        for root, dirs, files in os.walk(folder):
            for name in files:
                path = os.path.join(root, name)
                try:
                    os.remove(path)
                    deleted += 1
                except:
                    pass
    return deleted

print("Закрываем Explorer...")
subprocess.run("taskkill /f /im explorer.exe", shell=True)

local = os.path.expandvars(r"%LocalAppData%")
appdata = os.path.expandvars(r"%AppData%")
programdata = os.path.expandvars(r"%ProgramData%")
temp = os.path.expandvars(r"%TEMP%")

deleted_total = 0

print("Очистка thumbnail cache...")
deleted_total += delete_files(local + r"\Microsoft\Windows\Explorer\thumbcache*.db")

print("Очистка icon cache...")
deleted_total += delete_files(local + r"\Microsoft\Windows\Explorer\iconcache*.db")

print("Очистка Explorer cache...")
deleted_total += delete_files(local + r"\Microsoft\Windows\Explorer\*.db")

print("Очистка Recent files...")
deleted_total += clear_folder(appdata + r"\Microsoft\Windows\Recent")

print("Очистка Jump Lists...")
deleted_total += clear_folder(appdata + r"\Microsoft\Windows\Recent\AutomaticDestinations")
deleted_total += clear_folder(appdata + r"\Microsoft\Windows\Recent\CustomDestinations")

print("Очистка Windows Search index...")
deleted_total += clear_folder(programdata + r"\Microsoft\Search\Data")

print("Очистка TEMP пользователя...")
deleted_total += clear_folder(temp)

print("Очистка Windows TEMP...")
deleted_total += clear_folder(r"C:\Windows\Temp")

print("Очистка Prefetch...")
deleted_total += clear_folder(r"C:\Windows\Prefetch")

print("Очистка Edge cache...")
deleted_total += clear_folder(local + r"\Microsoft\Edge\User Data\Default\Cache")

print("Очистка Chrome cache...")
deleted_total += clear_folder(local + r"\Google\Chrome\User Data\Default\Cache")

print("Очистка DirectX shader cache...")
deleted_total += clear_folder(local + r"\D3DSCache")

print("Отключаем гибернацию (удаляет hiberfil.sys)...")
subprocess.run("powercfg -h off", shell=True)

print(f"Удалено файлов: {deleted_total}")

print("Запускаем Explorer...")
subprocess.Popen("explorer.exe")

input("Очистка завершена. Нажмите Enter для выхода.")