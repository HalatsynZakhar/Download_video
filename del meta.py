import os
from pathlib import Path
from datetime import datetime
import platform
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing
import ctypes
from ctypes import wintypes
import pywintypes
import win32file
import win32con


def wipe_file_metadata_windows(file_path):
    """
    Затирает метаданные файла на Windows используя Win32 API.
    """
    try:
        # Самая ранняя дата для Windows (1 января 1980)
        earliest_time = pywintypes.Time(datetime(1980, 1, 1, 0, 0, 0))

        # Открываем файл с правами на запись атрибутов
        handle = win32file.CreateFile(
            str(file_path),
            win32con.GENERIC_WRITE,
            win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE,
            None,
            win32con.OPEN_EXISTING,
            win32con.FILE_ATTRIBUTE_NORMAL,
            None
        )

        try:
            # Устанавливаем все три времени: создание, доступ, модификация
            win32file.SetFileTime(handle, earliest_time, earliest_time, earliest_time)
        finally:
            handle.Close()

        return True

    except Exception as e:
        # Fallback на os.utime если Win32 API не сработал
        try:
            earliest_timestamp = datetime(1980, 1, 1, 0, 0, 0).timestamp()
            os.utime(file_path, (earliest_timestamp, earliest_timestamp))
            return True
        except:
            return False


def wipe_file_metadata_unix(file_path):
    """
    Затирает метаданные файла на Unix/Linux/Mac.
    """
    try:
        # Unix epoch - 1 января 1970
        earliest_timestamp = 0
        os.utime(file_path, (earliest_timestamp, earliest_timestamp))
        return True
    except Exception:
        return False


def wipe_file_metadata(file_path):
    """
    Кроссплатформенная функция затирания метаданных.
    """
    if platform.system() == 'Windows':
        return wipe_file_metadata_windows(file_path)
    else:
        return wipe_file_metadata_unix(file_path)


def wipe_batch(files_batch):
    """
    Обрабатывает батч файлов.
    """
    success = 0
    for file_path in files_batch:
        if wipe_file_metadata(file_path):
            success += 1
    return success


def wipe_metadata_from_directory(target_directory, recursive=True, file_extensions=None, max_workers=None):
    """
    Быстро затирает метаданные используя многопоточность.

    :param target_directory: Путь к директории для обработки.
    :param recursive: Обрабатывать ли вложенные папки.
    :param file_extensions: Список расширений для обработки.
    :param max_workers: Количество потоков (по умолчанию CPU*4).
    """
    try:
        target = Path(target_directory)

        if not target.exists() or not target.is_dir():
            print(f"Ошибка: Директория '{target_directory}' не существует.")
            return

        # Проверяем платформу
        if platform.system() == 'Windows':
            print("Платформа: Windows (используется Win32 API)")
        else:
            print(f"Платформа: {platform.system()}")

        # Нормализуем расширения
        if file_extensions:
            extensions_to_process = {ext.lower() if ext.startswith('.') else f'.{ext.lower()}'
                                     for ext in file_extensions}
        else:
            extensions_to_process = None

        print("Сканирование файлов...")

        # Быстро собираем все файлы
        if recursive:
            all_files = list(target.rglob('*'))
        else:
            all_files = list(target.iterdir())

        # Фильтруем файлы и собираем директории
        files = []
        directories = []
        for f in all_files:
            if f.is_file():
                if extensions_to_process is None or f.suffix.lower() in extensions_to_process:
                    files.append(f)
            elif f.is_dir():
                directories.append(f)

        total_files = len(files)
        total_dirs = len(directories)
        print(f"Найдено файлов для обработки: {total_files}")
        print(f"Найдено директорий для обработки: {total_dirs}")

        if total_files == 0 and total_dirs == 0:
            print("Нет файлов и директорий для обработки.")
            return

        total_items = total_files + total_dirs

        # Определяем количество потоков
        if max_workers is None:
            max_workers = min(multiprocessing.cpu_count() * 4, 32)

        print(f"Запуск обработки с {max_workers} потоками...")
        print("-" * 80)

        processed = 0

        # Сначала обрабатываем файлы
        print("Обработка файлов...")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Разбиваем на батчи для лучшей производительности
            batch_size = 100
            batches = [files[i:i + batch_size] for i in range(0, len(files), batch_size)]

            # Запускаем батчи
            futures = {executor.submit(wipe_batch, batch): len(batch) for batch in batches}

            # Собираем результаты
            for future in as_completed(futures):
                try:
                    success = future.result()
                    processed += success

                    # Выводим прогресс
                    if processed % 1000 == 0 or processed == total_files:
                        percent = (processed / total_items) * 100
                        print(f"Прогресс: {processed}/{total_items} ({percent:.1f}%)")

                except Exception as e:
                    print(f"Ошибка в батче файлов: {e}")

        # Затем обрабатываем директории (от самых глубоких к корневым)
        if directories:
            print("\nОбработка директорий...")
            # Сортируем по глубине (самые вложенные первыми)
            directories.sort(key=lambda d: len(d.parts), reverse=True)

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                batch_size = 100
                dir_batches = [directories[i:i + batch_size] for i in range(0, len(directories), batch_size)]

                futures = {executor.submit(wipe_batch, batch): len(batch) for batch in dir_batches}

                for future in as_completed(futures):
                    try:
                        success = future.result()
                        processed += success

                        if processed % 1000 == 0 or processed == total_items:
                            percent = (processed / total_items) * 100
                            print(f"Прогресс: {processed}/{total_items} ({percent:.1f}%)")

                    except Exception as e:
                        print(f"Ошибка в батче директорий: {e}")

        # Финальная статистика
        print("-" * 80)
        print(f"✓ Обработка завершена!")
        print(f"Всего файлов: {total_files}")
        print(f"Всего директорий: {total_dirs}")
        print(f"Успешно обработано: {processed}")
        print(f"Ошибок: {total_items - processed}")

    except Exception as e:
        print(f"Критическая ошибка: {e}")


def interactive_mode():
    """
    Интерактивный режим.
    """
    print("=" * 80)
    print("ЗАТИРАНИЕ МЕТАДАННЫХ (МНОГОПОТОЧНЫЙ РЕЖИМ)")
    print("=" * 80)

    directory = input("\nПуть к директории: ").strip()

    recursive_input = input("Обрабатывать вложенные папки? (да/нет, по умолчанию: да): ").strip().lower()
    recursive = recursive_input != 'нет'

    extensions_input = input("Расширения файлов через запятую (Enter = все файлы): ").strip()
    file_extensions = [ext.strip() for ext in extensions_input.split(',')] if extensions_input else None

    threads_input = input(f"Количество потоков (Enter = авто): ").strip()
    max_workers = int(threads_input) if threads_input.isdigit() else None

    print("\n" + "=" * 80)
    print("ПАРАМЕТРЫ:")
    print(f"Директория: {directory}")
    print(f"Рекурсия: {'Да' if recursive else 'Нет'}")
    print(f"Расширения: {file_extensions if file_extensions else 'ВСЕ'}")
    print(f"Потоки: {max_workers if max_workers else 'Авто'}")
    print("=" * 80)

    confirm = input("\n⚠️  Начать обработку? (да/нет): ").strip().lower()

    if confirm == 'да':
        print("\n")
        wipe_metadata_from_directory(directory, recursive, file_extensions, max_workers)
    else:
        print("Отменено.")


# ВАЖНО: Для работы на Windows установите:
# pip install pywin32

# Варианты использования:

# Вариант 1: Интерактивный режим
interactive_mode()

# Вариант 2: Максимальная скорость - все файлы, много потоков
# wipe_metadata_from_directory("F:\\м", recursive=True, max_workers=32)

# Вариант 3: Только изображения
# wipe_metadata_from_directory("F:\\м", recursive=True, file_extensions=['jpg', 'png', 'jpeg'])

# Вариант 4: Контроль потоков вручную
# wipe_metadata_from_directory("F:\\м", recursive=True, max_workers=16)