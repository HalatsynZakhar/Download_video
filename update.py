import os
from pathlib import Path
from datetime import datetime
from PIL import Image
from PIL.ExifTags import TAGS
import PyPDF2
import shutil


def remove_metadata(file_path):
    """
    Удаляет метаданные из файлов различных форматов.

    :param file_path: Path объект файла
    :return: True если метаданные успешно удалены, False в противном случае
    """
    try:
        suffix = file_path.suffix.lower()

        # Обработка изображений (JPEG, PNG, TIFF, BMP, WEBP)
        if suffix in ['.jpg', '.jpeg', '.png', '.tiff', '.bmp', '.webp']:
            img = Image.open(file_path)

            # Создаем новое изображение без метаданных
            data = list(img.getdata())
            image_without_exif = Image.new(img.mode, img.size)
            image_without_exif.putdata(data)

            # Сохраняем без метаданных
            image_without_exif.save(file_path)
            return True

        # Обработка PDF файлов
        elif suffix == '.pdf':
            # Создаем временный файл
            temp_path = file_path.with_suffix('.tmp')

            with open(file_path, 'rb') as input_file:
                reader = PyPDF2.PdfReader(input_file)
                writer = PyPDF2.PdfWriter()

                # Копируем страницы без метаданных
                for page in reader.pages:
                    writer.add_page(page)

                # Сохраняем в временный файл
                with open(temp_path, 'wb') as output_file:
                    writer.write(output_file)

            # Заменяем оригинальный файл
            shutil.move(temp_path, file_path)
            return True

        # Для других типов файлов можно добавить обработку
        else:
            return False

    except Exception as e:
        print(f"Ошибка удаления метаданных из {file_path.name}: {e}")
        return False


def organize_files(source_directory, result_directory, max_files_per_folder=5000,
                   start_number=None, remove_meta=True):
    """
    Организует файлы из "свалки" в упорядоченные папки с указанным лимитом файлов на папку.
    Опционально удаляет метаданные из файлов.

    :param source_directory: Путь к "свалке" файлов.
    :param result_directory: Путь к папке с результатом.
    :param max_files_per_folder: Максимальное количество файлов на одну папку.
    :param start_number: Начальное число для нумерации файлов. Если None, определяется автоматически.
    :param remove_meta: Удалять ли метаданные из файлов (по умолчанию True).
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
                    (int(f.stem.split('_')[0]) for f in last_folder.iterdir()
                     if f.is_file() and f.stem.split('_')[0].isdigit()),
                    default=0
                )
                start_number = last_file + 1
            else:
                start_number = 1

        # Счетчики
        file_counter = start_number
        rename_counter = 0
        metadata_removed_count = 0

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

            # Удаляем метаданные, если требуется
            if remove_meta:
                if remove_metadata(new_path):
                    metadata_removed_count += 1

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
        if remove_meta:
            print(f"Метаданные удалены из {metadata_removed_count} файлов")

    except Exception as e:
        print(f"Критическая ошибка: {e}")


# Пример использования
source_directory = "F:\\Загрузки"
result_directory = "F:\\м"
max_files_per_folder = 5000
start_number = None  # Автоматически определить стартовый номер

# remove_meta=True для удаления метаданных, False для отключения этой функции
organize_files(source_directory, result_directory, max_files_per_folder, start_number, remove_meta=True)