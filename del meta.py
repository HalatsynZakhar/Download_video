import os
from pathlib import Path
from PIL import Image
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

        # Для других типов файлов возвращаем False
        else:
            return False

    except Exception as e:
        print(f"Ошибка удаления метаданных из {file_path.name}: {e}")
        return False


def remove_metadata_from_directory(target_directory, recursive=True, file_extensions=None):
    """
    Удаляет метаданные из всех файлов в указанной директории.

    :param target_directory: Путь к директории для обработки.
    :param recursive: Обрабатывать ли вложенные папки (по умолчанию True).
    :param file_extensions: Список расширений для обработки (например, ['.jpg', '.png', '.pdf']).
                           Если None, обрабатываются все поддерживаемые форматы.
    """
    try:
        # Конвертируем путь в Path-объект
        target = Path(target_directory)

        # Проверяем существование директории
        if not target.exists() or not target.is_dir():
            print(f"Ошибка: Директория '{target_directory}' не существует или не является папкой.")
            return

        # Поддерживаемые расширения
        supported_extensions = {'.jpg', '.jpeg', '.png', '.tiff', '.bmp', '.webp', '.pdf'}

        # Определяем, какие расширения обрабатывать
        if file_extensions:
            extensions_to_process = {ext.lower() for ext in file_extensions if ext.lower() in supported_extensions}
        else:
            extensions_to_process = supported_extensions

        # Счетчики
        total_files = 0
        processed_files = 0
        skipped_files = 0
        error_files = 0

        # Функция для обработки файлов в директории
        def process_directory(directory):
            nonlocal total_files, processed_files, skipped_files, error_files

            try:
                # Получаем все элементы в директории
                items = list(directory.iterdir())

                for item in items:
                    # Если это директория и включен рекурсивный режим
                    if item.is_dir() and recursive:
                        print(f"Обработка поддиректории: {item}")
                        process_directory(item)

                    # Если это файл
                    elif item.is_file():
                        total_files += 1

                        # Проверяем расширение файла
                        if item.suffix.lower() in extensions_to_process:
                            print(f"Обработка файла: {item.name}")

                            # Пытаемся удалить метаданные
                            if remove_metadata(item):
                                processed_files += 1
                            else:
                                error_files += 1
                        else:
                            skipped_files += 1

            except PermissionError as e:
                print(f"Ошибка доступа к директории {directory}: {e}")
            except Exception as e:
                print(f"Ошибка при обработке директории {directory}: {e}")

        # Начинаем обработку
        print(f"Начало обработки директории: {target}")
        print(f"Рекурсивный режим: {'Да' if recursive else 'Нет'}")
        print(f"Обрабатываемые расширения: {', '.join(extensions_to_process)}")
        print("-" * 80)

        process_directory(target)

        # Выводим статистику
        print("-" * 80)
        print(f"Обработка завершена!")
        print(f"Всего файлов найдено: {total_files}")
        print(f"Метаданные успешно удалены: {processed_files}")
        print(f"Файлов пропущено (неподдерживаемый формат): {skipped_files}")
        print(f"Ошибок при обработке: {error_files}")

    except Exception as e:
        print(f"Критическая ошибка: {e}")


def interactive_mode():
    """
    Интерактивный режим для удобного использования скрипта.
    """
    print("=" * 80)
    print("УДАЛЕНИЕ МЕТАДАННЫХ ИЗ ФАЙЛОВ")
    print("=" * 80)

    # Запрашиваем путь к директории
    directory = input("\nВведите путь к директории: ").strip()

    # Запрашиваем режим обработки
    recursive_input = input("Обрабатывать вложенные папки? (да/нет, по умолчанию: да): ").strip().lower()
    recursive = recursive_input != 'нет'

    # Запрашиваем расширения файлов
    extensions_input = input(
        "Введите расширения файлов через запятую (например: .jpg,.png,.pdf)\nили нажмите Enter для обработки всех поддерживаемых форматов: ").strip()

    if extensions_input:
        file_extensions = [ext.strip() for ext in extensions_input.split(',')]
    else:
        file_extensions = None

    # Подтверждение
    print("\n" + "=" * 80)
    print("ПАРАМЕТРЫ ОБРАБОТКИ:")
    print(f"Директория: {directory}")
    print(f"Рекурсивный режим: {'Да' if recursive else 'Нет'}")
    print(f"Расширения: {file_extensions if file_extensions else 'Все поддерживаемые'}")
    print("=" * 80)

    confirm = input("\nНачать обработку? (да/нет): ").strip().lower()

    if confirm == 'да':
        print("\n")
        remove_metadata_from_directory(directory, recursive, file_extensions)
    else:
        print("Обработка отменена.")


# Варианты использования:

# Вариант 1: Интерактивный режим
interactive_mode()

# Вариант 2: Прямой вызов с параметрами (раскомментируйте для использования)
# target_directory = "F:\\м"
# remove_metadata_from_directory(target_directory, recursive=True)

# Вариант 3: Обработка только определенных типов файлов (раскомментируйте для использования)
# target_directory = "F:\\м"
# remove_metadata_from_directory(target_directory, recursive=True, file_extensions=['.jpg', '.png'])

# Вариант 4: Обработка без рекурсии (только текущая папка) (раскомментируйте для использования)
# target_directory = "F:\\м"
# remove_metadata_from_directory(target_directory, recursive=False)