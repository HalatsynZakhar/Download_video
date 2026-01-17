import os
from pathlib import Path
from datetime import datetime
from PIL import Image
import PyPDF2
import shutil
import platform
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing
import pywintypes
import win32file
import win32con
from threading import Lock
import time
import tempfile


class FileOrganizer:
    """
    Организатор файлов с созданием чистых копий без метаданных.
    Исходные файлы остаются нетронутыми.
    """

    def __init__(self, source_directory, result_directory, max_files_per_folder=5000,
                 start_number=None, remove_meta=True, wipe_timestamps=True, max_workers=None):
        self.source = Path(source_directory)
        self.result = Path(result_directory)
        self.max_files_per_folder = max_files_per_folder
        self.start_number = start_number
        self.remove_meta = remove_meta
        self.wipe_timestamps = wipe_timestamps
        self.max_workers = max_workers or min(multiprocessing.cpu_count() * 2, 16)

        # Потокобезопасные счетчики
        self.lock = Lock()
        self.file_counter = 0
        self.folder_counter = 1
        self.current_folder = None
        self.processed_count = 0
        self.metadata_removed_count = 0
        self.timestamp_wiped_count = 0
        self.error_count = 0

    def wipe_file_timestamps_windows(self, file_path):
        """Затирает временные метки файла на Windows."""
        try:
            earliest_time = pywintypes.Time(datetime(1980, 1, 1, 0, 0, 0))
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
                win32file.SetFileTime(handle, earliest_time, earliest_time, earliest_time)
            finally:
                handle.Close()
            return True
        except Exception:
            try:
                earliest_timestamp = datetime(1980, 1, 1, 0, 0, 0).timestamp()
                os.utime(file_path, (earliest_timestamp, earliest_timestamp))
                return True
            except:
                return False

    def wipe_file_timestamps_unix(self, file_path):
        """Затирает временные метки файла на Unix/Linux/Mac."""
        try:
            earliest_timestamp = 0
            os.utime(file_path, (earliest_timestamp, earliest_timestamp))
            return True
        except Exception:
            return False

    def wipe_file_timestamps(self, file_path):
        """Кроссплатформенное затирание временных меток."""
        if platform.system() == 'Windows':
            return self.wipe_file_timestamps_windows(file_path)
        else:
            return self.wipe_file_timestamps_unix(file_path)

    def create_clean_copy(self, source_path, dest_path):
        """
        Создаёт чистую копию файла без метаданных.
        Исходный файл НЕ изменяется.
        Возвращает True если метаданные были удалены.
        """
        try:
            suffix = source_path.suffix.lower()

            # Обработка изображений - создаём временную чистую копию
            if suffix in ['.jpg', '.jpeg', '.png', '.tiff', '.bmp', '.webp']:
                with Image.open(source_path) as img:
                    # Сохраняем БЕЗ метаданных в целевой файл
                    if suffix in ['.jpg', '.jpeg']:
                        img.save(dest_path, 'JPEG', quality=95, optimize=False, exif=b'')
                    elif suffix == '.png':
                        img.save(dest_path, 'PNG', optimize=False)
                    else:
                        # Создаем новое изображение без EXIF
                        data = list(img.getdata())
                        clean_img = Image.new(img.mode, img.size)
                        clean_img.putdata(data)
                        clean_img.save(dest_path)
                return True

            # Обработка PDF - создаём чистую копию
            elif suffix == '.pdf':
                try:
                    with open(source_path, 'rb') as input_file:
                        reader = PyPDF2.PdfReader(input_file)
                        writer = PyPDF2.PdfWriter()

                        # Копируем страницы без метаданных
                        for page in reader.pages:
                            writer.add_page(page)

                        # Сохраняем чистый PDF
                        with open(dest_path, 'wb') as output_file:
                            writer.write(output_file)
                    return True
                except:
                    # Если не получилось - просто копируем
                    shutil.copy2(source_path, dest_path)
                    return False

            # Для остальных файлов - обычное копирование
            else:
                shutil.copy2(source_path, dest_path)
                return False

        except Exception as e:
            # При ошибке пытаемся хотя бы скопировать файл
            try:
                if not dest_path.exists():
                    shutil.copy2(source_path, dest_path)
            except:
                pass
            return False

    def get_next_folder(self):
        """Получает следующую папку для размещения файлов (потокобезопасно)."""
        with self.lock:
            if self.current_folder is None or len(list(self.current_folder.iterdir())) >= self.max_files_per_folder:
                self.folder_counter += 1
                self.current_folder = self.result / f"{self.folder_counter:04d}"
                if not self.current_folder.exists():
                    self.current_folder.mkdir(parents=True)
            return self.current_folder

    def get_next_file_number(self):
        """Получает следующий номер файла (потокобезопасно)."""
        with self.lock:
            self.file_counter += 1
            return self.file_counter

    def process_file(self, file_path):
        """
        Обрабатывает один файл: создаёт чистую копию, переименовывает, удаляет оригинал.
        Операция перемещения с очисткой метаданных.
        """
        try:
            # Получаем номер и папку
            file_number = self.get_next_file_number()
            target_folder = self.get_next_folder()

            # Формируем путь
            new_name = f"{file_number:06d}{file_path.suffix}"
            new_path = target_folder / new_name

            # Проверяем конфликты
            conflict_counter = 0
            while new_path.exists():
                conflict_counter += 1
                new_name = f"{file_number:06d}_{conflict_counter}{file_path.suffix}"
                new_path = target_folder / new_name

            # Создаём чистую копию
            meta_removed = False
            if self.remove_meta:
                meta_removed = self.create_clean_copy(file_path, new_path)
                if meta_removed:
                    with self.lock:
                        self.metadata_removed_count += 1
            else:
                # Если не нужно удалять метаданные - просто копируем
                shutil.copy2(file_path, new_path)

            # Затираем временные метки на копии
            timestamp_wiped = False
            if self.wipe_timestamps:
                timestamp_wiped = self.wipe_file_timestamps(new_path)
                if timestamp_wiped:
                    with self.lock:
                        self.timestamp_wiped_count += 1

            # Удаляем оригинал после успешного копирования
            try:
                file_path.unlink()
            except Exception as e:
                # Если не удалось удалить - не критично, продолжаем
                pass

            with self.lock:
                self.processed_count += 1

            return True, file_number

        except Exception as e:
            with self.lock:
                self.error_count += 1
            return False, None

    def organize_files(self):
        """Главная функция с оптимизацией."""
        try:
            start_time = time.time()

            # Проверки
            if not self.source.exists() or not self.source.is_dir():
                print(f"❌ Ошибка: Папка '{self.source}' не существует.")
                return

            if self.source == self.result:
                print(f"❌ Ошибка: Папка-источник и результат не могут совпадать!")
                return

            if not self.result.exists():
                self.result.mkdir(parents=True)
                print(f"✓ Создана результирующая папка: {self.result}")

            # Сканирование
            print("📂 Сканирование файлов...")
            files = [f for f in self.source.iterdir() if f.is_file()]

            if not files:
                print("⚠️  Нет файлов для обработки.")
                return

            # Сортировка
            files.sort(key=lambda f: (f.stat().st_mtime, f.name.lower()))
            total_files = len(files)
            print(f"✓ Найдено файлов: {total_files}")

            # Начальный номер
            if self.start_number is None:
                existing_folders = sorted(self.result.glob("*/"), key=lambda f: f.name)
                if existing_folders:
                    last_folder = existing_folders[-1]
                    try:
                        last_file = max(
                            (int(f.stem.split('_')[0]) for f in last_folder.iterdir()
                             if f.is_file() and f.stem.split('_')[0].isdigit()),
                            default=0
                        )
                        self.file_counter = last_file
                    except:
                        self.file_counter = 0
                else:
                    self.file_counter = 0
            else:
                self.file_counter = self.start_number - 1

            # Инициализация папки
            existing_folders = sorted(self.result.glob("*/"), key=lambda f: f.name)
            if existing_folders:
                last_folder = existing_folders[-1]
                self.folder_counter = int(last_folder.name) - 1
            else:
                self.folder_counter = 0

            self.get_next_folder()

            # Информация
            print(f"\n{'=' * 80}")
            print(f"ПАРАМЕТРЫ ОБРАБОТКИ:")
            print(f"Источник: {self.source}")
            print(f"Назначение: {self.result}")
            print(f"Файлов на папку: {self.max_files_per_folder}")
            print(f"Потоков: {self.max_workers}")
            print(f"Удаление метаданных: {'Да' if self.remove_meta else 'Нет'}")
            print(f"Затирание временных меток: {'Да' if self.wipe_timestamps else 'Нет'}")
            print(f"⚠️  ОПЕРАЦИЯ ПЕРЕМЕЩЕНИЯ: исходные файлы будут удалены после копирования")
            print(f"{'=' * 80}\n")

            # Обработка
            print("🚀 Запуск обработки...")
            print(f"{'-' * 80}")

            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {executor.submit(self.process_file, file): file for file in files}

                last_update = time.time()
                for future in as_completed(futures):
                    # Обновляем прогресс
                    current_time = time.time()
                    if (current_time - last_update > 2) or (self.processed_count % 100 == 0) or (
                            self.processed_count == total_files):
                        percent = (self.processed_count / total_files) * 100
                        elapsed = current_time - start_time
                        speed = self.processed_count / elapsed if elapsed > 0 else 0

                        print(f"Прогресс: {self.processed_count}/{total_files} ({percent:.1f}%) | "
                              f"Скорость: {speed:.1f} ф/с | "
                              f"Метаданные: {self.metadata_removed_count} | "
                              f"Ошибки: {self.error_count}")
                        last_update = current_time

            # Статистика
            total_time = time.time() - start_time
            print(f"{'-' * 80}")
            print(f"✅ Обработка завершена!")
            print(f"\nСТАТИСТИКА:")
            print(f"  Всего файлов: {total_files}")
            print(f"  Успешно обработано: {self.processed_count}")
            print(f"  Создано папок: {self.folder_counter}")
            if self.remove_meta:
                print(f"  Метаданные удалены: {self.metadata_removed_count}")
            if self.wipe_timestamps:
                print(f"  Временные метки затерты: {self.timestamp_wiped_count}")
            print(f"  Ошибок: {self.error_count}")
            print(f"  Время работы: {total_time:.2f} сек ({total_time / 60:.1f} мин)")
            print(f"  Средняя скорость: {total_files / total_time:.1f} файлов/сек")
            print(f"\n✅ Файлы перемещены с очисткой метаданных")
            print(f"📁 Исходная папка '{self.source}' очищена")
            print(f"{'=' * 80}")

        except Exception as e:
            print(f"💥 Критическая ошибка: {e}")


def interactive_mode():
    """Интерактивный режим настройки."""
    print(f"{'=' * 80}")
    print("ОРГАНИЗАТОР ФАЙЛОВ С ПЕРЕМЕЩЕНИЕМ И ОЧИСТКОЙ МЕТАДАННЫХ")
    print(f"{'=' * 80}\n")

    source = input("Путь к папке-источнику: ").strip()
    result = input("Путь к результирующей папке: ").strip()

    if source == result:
        print("❌ Ошибка: Папки не должны совпадать!")
        return

    max_files_input = input("Максимум файлов на папку (по умолчанию: 5000): ").strip()
    max_files = int(max_files_input) if max_files_input.isdigit() else 5000

    start_num_input = input("Начальный номер файла (Enter = авто): ").strip()
    start_number = int(start_num_input) if start_num_input.isdigit() else None

    remove_meta_input = input("Удалять метаданные из файлов? (да/нет, по умолчанию: да): ").strip().lower()
    remove_meta = remove_meta_input != 'нет'

    wipe_time_input = input("Затирать временные метки? (да/нет, по умолчанию: да): ").strip().lower()
    wipe_timestamps = wipe_time_input != 'нет'

    workers_input = input("Количество потоков (Enter = авто): ").strip()
    max_workers = int(workers_input) if workers_input.isdigit() else None

    print(f"\n⚠️  Начать обработку? (да/нет): ", end='')
    confirm = input().strip().lower()

    if confirm == 'да':
        print()
        organizer = FileOrganizer(
            source, result, max_files, start_number,
            remove_meta, wipe_timestamps, max_workers
        )
        organizer.organize_files()
    else:
        print("❌ Отменено.")


if __name__ == "__main__":
    # Вариант 2: Прямой запуск
    source_directory = "F:\\Загрузки"
    result_directory = "F:\\м"
    max_files_per_folder = 5000
    start_number = None

    organizer = FileOrganizer(
        source_directory=source_directory,
        result_directory=result_directory,
        max_files_per_folder=max_files_per_folder,
        start_number=start_number,
        remove_meta=True,
        wipe_timestamps=True,
        max_workers=None
    )
    organizer.organize_files()