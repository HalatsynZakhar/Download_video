import os
from pathlib import Path
from datetime import datetime

def organize_files(source_directory, result_directory, max_files_per_folder=5000, start_number=None):
    """
    Организует файлы из "свалки" в упорядоченные папки с указанным лимитом файлов на папку.

    :param source_directory: Путь к "свалке" файлов.
    :param result_directory: Путь к папке с результатом.
    :param max_files_per_folder: Максимальное количество файлов на одну папку.
    :param start_number: Начальное число для нумерации файлов. Если None, определяется автоматически.
    """
    try:
        # Конвертируем пути в Path-объекты
        source = Path(source_directory)
        result = Path(result_directory)

        # Проверяем существование папок
        if not source.exists() or not source.is_dir():
            print(f"Ошибка: Папка источника '{source_directory}' не существует или не является директорией.")
            return
        if not result.exists():
            result.mkdir(parents=True)
            print(f"Создана результирующая папка: {result_directory}")

        # Получаем список файлов из "свалки"
        files = [f for f in source.iterdir() if f.is_file()]
        if not files:
            print("Нет файлов для обработки.")
            return

        # Сортируем файлы по дате последнего изменения (от старого к новому), затем по имени (в порядке возрастания)
        files.sort(key=lambda f: (f.stat().st_mtime, f.name.lower()))

        # Определяем начальный номер
        if start_number is None:
            # Сканируем существующую структуру для определения последнего номера
            existing_folders = sorted(result.glob("*/"), key=lambda f: f.name)
            if existing_folders:
                last_folder = existing_folders[-1]
                last_file = max(
                    (int(f.stem) for f in last_folder.iterdir() if f.is_file() and f.stem.isdigit()),
                    default=0
                )
                start_number = last_file + 1
            else:
                start_number = 1

        # Счетчики
        file_counter = start_number
        rename_counter = 0

        # Работа с последней папкой
        existing_folders = sorted(result.glob("*/"), key=lambda f: f.name)
        if existing_folders:
            current_folder = existing_folders[-1]
            folder_counter = int(current_folder.name)  # Установим номер последней папки
        else:
            folder_counter = 1
            current_folder = result / f"{folder_counter:04d}"
            current_folder.mkdir()
            print(f"Создана первая папка: {current_folder}")

        # Проверяем заполняемость последней папки
        while len(list(current_folder.iterdir())) >= max_files_per_folder:
            folder_counter += 1
            current_folder = result / f"{folder_counter:04d}"
            if not current_folder.exists():
                current_folder.mkdir()
                print(f"Создана новая папка: {current_folder}")

        # Обработка файлов
        for file in files:
            # Формируем новое имя файла
            new_name = f"{file_counter:06d}{file.suffix}"
            new_path = current_folder / new_name

            # Проверяем дубликаты
            conflict_counter = 0
            while new_path.exists():
                conflict_counter += 1
                new_name = f"{file_counter:06d}_{conflict_counter}{file.suffix}"
                new_path = current_folder / new_name

            # Перемещаем файл
            try:
                file.rename(new_path)
            except Exception as e:
                print(f"Ошибка перемещения файла {file}: {e}")
                continue  # Продолжаем работу даже при ошибке

            # Увеличиваем счетчик файлов
            file_counter += 1
            rename_counter += 1

            # Проверяем, если текущая папка заполнена, создаем новую
            if len(list(current_folder.iterdir())) >= max_files_per_folder:
                folder_counter += 1
                current_folder = result / f"{folder_counter:04d}"
                current_folder.mkdir()
                print(f"Создана новая папка: {current_folder}")

            # Проверяем каждые 100 переименований
            if rename_counter == 100:
                print("Проверка: обработано 100 файлов. Результат корректен?")
                user_input = input("Введите 'да' для продолжения без остановки, 'нет' для остановки: ").strip().lower()
                if user_input == 'да':
                    print("Продолжаем обработку без остановок.")
                elif user_input == 'нет':
                    print("Обработка прервана пользователем.")
                    break
                else:
                    print("Некорректный ввод. Обработка прервана.")
                    break

        print(f"Обработка завершена. Всего обработано файлов: {file_counter - start_number}")
        print(f"Создано папок: {folder_counter}")

    except Exception as e:
        print(f"Критическая ошибка: {e}")


# Пример использования
source_directory = "F:\\Загрузки"
result_directory = "F:\\м"
max_files_per_folder = 5000
start_number = None  # Автоматически определить стартовый номер

organize_files(source_directory, result_directory, max_files_per_folder, start_number)
