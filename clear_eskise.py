import os
import glob
import subprocess

# путь к кэшу эскизов
thumbcache_path = os.path.expandvars(r"%LocalAppData%\Microsoft\Windows\Explorer")

print("Закрываем проводник...")
subprocess.run("taskkill /f /im explorer.exe", shell=True)

files = glob.glob(os.path.join(thumbcache_path, "thumbcache*.db"))

deleted = 0
for file in files:
    try:
        os.remove(file)
        deleted += 1
    except Exception as e:
        print(f"Не удалось удалить {file}: {e}")

print(f"Удалено файлов: {deleted}")

print("Запускаем проводник...")
subprocess.Popen("explorer.exe")

input("Готово. Нажмите Enter для выхода.")