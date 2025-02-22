import shutil
from pathlib import Path

def move_files_back(source_directory, target_directory):
    """
    Перемещает все файлы из указанной папки обратно в другую папку.

    :param source_directory: Папка, из которой перемещаются файлы.
    :param target_directory: Папка, куда перемещаются файлы.
    """
    try:
        source = Path(source_directory)
        target = Path(target_directory)

        if not source.exists() or not source.is_dir():
            print(f"Ошибка: Папка источника '{source_directory}' не существует или не является директорией.")
            return

        if not target.exists():
            target.mkdir(parents=True)
            print(f"Создана целевая папка: {target_directory}")

        files = [f for f in source.rglob("*") if f.is_file()]
        if not files:
            print("Нет файлов для перемещения.")
            return

        for file in files:
            try:
                target_file = target / file.name

                # Проверяем на конфликты и создаем уникальное имя при необходимости
                conflict_counter = 0
                while target_file.exists():
                    conflict_counter += 1
                    target_file = target / f"{file.stem}_{conflict_counter}{file.suffix}"

                shutil.move(str(file), str(target_file))
                print(f"Файл {file.name} перемещен в {target_directory}.")

            except Exception as e:
                print(f"Ошибка при перемещении файла {file}: {e}")

        print("Перемещение завершено.")

    except Exception as e:
        print(f"Критическая ошибка: {e}")

# Пример использования
source_directory = r"F:\м\0028"  # Укажите текущую папку
target_directory = "F:\\Загрузки"  # Укажите папку для возврата
move_files_back(source_directory, target_directory)