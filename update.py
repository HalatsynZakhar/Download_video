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


class FileOrganizer:
    """
    Многопоточный организатор файлов с удалением метаданных.
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

    def remove_metadata(self, file_path):
        """Удаляет метаданные из файлов различных форматов."""
        try:
            suffix = file_path.suffix.lower()

            # Обработка изображений
            if suffix in ['.jpg', '.jpeg', '.png', '.tiff', '.bmp', '.webp']:
                img = Image.open(file_path)
                data = list(img.getdata())
                image_without_exif = Image.new(img.mode, img.size)
                image_without_exif.putdata(data)
                image_without_exif.save(file_path)
                return True

            # Обработка PDF файлов
            elif suffix == '.pdf':
                temp_path = file_path.with_suffix('.tmp')
                with open(file_path, 'rb') as input_file:
                    reader = PyPDF2.PdfReader(input_file)
                    writer = PyPDF2.PdfWriter()
                    for page in reader.pages:
                        writer.add_page(page)
                    with open(temp_path, 'wb') as output_file:
                        writer.write(output_file)
                shutil.move(temp_path, file_path)
                return True

            return False

        except Exception as e:
            print(f"⚠️  Ошибка удаления метаданных из {file_path.name}: {e}")
            return False

    def get_next_folder(self):
        """Получает следующую папку для размещения файлов (потокобезопасно)."""
        with self.lock:
            # Проверяем текущую папку
            if self.current_folder is None or len(list(self.current_folder.iterdir())) >= self.max_files_per_folder:
                self.folder_counter += 1
                self.current_folder = self.result / f"{self.folder_counter:04d}"
                if not self.current_folder.exists():
                    self.current_folder.mkdir(parents=True)
                    print(f"✓ Создана папка: {self.current_folder}")
            return self.current_folder

    def get_next_file_number(self):
        """Получает следующий номер файла (потокобезопасно)."""
        with self.lock:
            self.file_counter += 1
            return self.file_counter

    def process_file(self, file_path):
        """Обрабатывает один файл: перемещение, переименование, удаление метаданных."""
        try:
            # Получаем номер файла
            file_number = self.get_next_file_number()

            # Получаем целевую папку
            target_folder = self.get_next_folder()

            # Формируем новое имя
            new_name = f"{file_number:06d}{file_path.suffix}"
            new_path = target_folder / new_name

            # Проверяем дубликаты
            conflict_counter = 0
            while new_path.exists():
                conflict_counter += 1
                new_name = f"{file_number:06d}_{conflict_counter}{file_path.suffix}"
                new_path = target_folder / new_name

            # Перемещаем файл
            shutil.move(str(file_path), str(new_path))

            # Удаляем метаданные
            meta_removed = False
            if self.remove_meta:
                meta_removed = self.remove_metadata(new_path)
                if meta_removed:
                    with self.lock:
                        self.metadata_removed_count += 1

            # Затираем временные метки
            timestamp_wiped = False
            if self.wipe_timestamps:
                timestamp_wiped = self.wipe_file_timestamps(new_path)
                if timestamp_wiped:
                    with self.lock:
                        self.timestamp_wiped_count += 1

            # Обновляем счетчик обработанных
            with self.lock:
                self.processed_count += 1

            return True, file_number

        except Exception as e:
            print(f"❌ Ошибка обработки {file_path.name}: {e}")
            with self.lock:
                self.error_count += 1
            return False, None

    def organize_files(self):
        """Главная функция организации файлов с многопоточностью."""
        try:
            # Проверяем папки
            if not self.source.exists() or not self.source.is_dir():
                print(f"❌ Ошибка: Папка '{self.source}' не существует.")
                return

            if not self.result.exists():
                self.result.mkdir(parents=True)
                print(f"✓ Создана результирующая папка: {self.result}")

            # Получаем список файлов
            print("📂 Сканирование файлов...")
            files = [f for f in self.source.iterdir() if f.is_file()]

            if not files:
                print("⚠️  Нет файлов для обработки.")
                return

            # Сортируем файлы
            files.sort(key=lambda f: (f.stat().st_mtime, f.name.lower()))
            total_files = len(files)
            print(f"✓ Найдено файлов: {total_files}")

            # Определяем начальный номер
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

            # Инициализируем первую папку
            existing_folders = sorted(self.result.glob("*/"), key=lambda f: f.name)
            if existing_folders:
                last_folder = existing_folders[-1]
                self.folder_counter = int(last_folder.name) - 1
            else:
                self.folder_counter = 0

            # Получаем начальную папку
            self.get_next_folder()

            # Параметры обработки
            print(f"\n{'=' * 80}")
            print(f"ПАРАМЕТРЫ ОБРАБОТКИ:")
            print(f"Источник: {self.source}")
            print(f"Назначение: {self.result}")
            print(f"Файлов на папку: {self.max_files_per_folder}")
            print(f"Потоков: {self.max_workers}")
            print(f"Удаление метаданных: {'Да' if self.remove_meta else 'Нет'}")
            print(f"Затирание временных меток: {'Да' if self.wipe_timestamps else 'Нет'}")
            print(f"Платформа: {platform.system()}")
            print(f"{'=' * 80}\n")

            # Многопоточная обработка
            print("🚀 Запуск обработки...")
            print(f"{'-' * 80}")

            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Запускаем обработку файлов
                futures = {executor.submit(self.process_file, file): file for file in files}

                # Собираем результаты
                for future in as_completed(futures):
                    # Выводим прогресс каждые 100 файлов
                    if self.processed_count % 100 == 0 or self.processed_count == total_files:
                        percent = (self.processed_count / total_files) * 100
                        print(f"Прогресс: {self.processed_count}/{total_files} ({percent:.1f}%) | "
                              f"Метаданные: {self.metadata_removed_count} | "
                              f"Метки времени: {self.timestamp_wiped_count} | "
                              f"Ошибки: {self.error_count}")

            # Финальная статистика
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
            print(f"{'=' * 80}")

        except Exception as e:
            print(f"💥 Критическая ошибка: {e}")


def interactive_mode():
    """Интерактивный режим настройки."""
    print(f"{'=' * 80}")
    print("ОРГАНИЗАТОР ФАЙЛОВ С МНОГОПОТОЧНОСТЬЮ")
    print(f"{'=' * 80}\n")

    source = input("Путь к папке-источнику: ").strip()
    result = input("Путь к результирующей папке: ").strip()

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


# ВАЖНО: Для работы на Windows установите:
# pip install pywin32 pillow PyPDF2

if __name__ == "__main__":
    # ============================================================================
    # БЫСТРЫЕ НАСТРОЙКИ - Раскомментируйте нужный вариант
    # ============================================================================

    # Вариант 1: Интерактивный режим (по умолчанию)
    #interactive_mode()

    #Вариант 2: Прямой запуск с вашими настройками
    source_directory = "F:\\Загрузки"
    result_directory = "F:\\м"
    max_files_per_folder = 5000
    start_number = None  # Автоматически определить стартовый номер
    organizer = FileOrganizer(
        source_directory=source_directory,
        result_directory=result_directory,
        max_files_per_folder=max_files_per_folder,
        start_number=start_number,
        remove_meta=True,        # Удалять метаданные из файлов
        wipe_timestamps=True,    # Затирать временные метки
        max_workers=None         # Автоопределение потоков (или укажите число, например 8)
    )
    organizer.organize_files()

    # Вариант 3: Только переименование без обработки метаданных (быстрый режим)
    # organizer = FileOrganizer(
    #     source_directory="F:\\Загрузки",
    #     result_directory="F:\\м",
    #     max_files_per_folder=5000,
    #     start_number=None,
    #     remove_meta=False,       # Не удалять метаданные
    #     wipe_timestamps=False,   # Не затирать временные метки
    #     max_workers=16           # Больше потоков для быстрой работы
    # )
    # organizer.organize_files()