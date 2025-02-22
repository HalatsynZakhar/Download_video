import yt_dlp
import shutil
import sys
import os
from concurrent.futures import ThreadPoolExecutor

# Константы
MAX_WORKERS_PER_SITE = 4  # Максимальное количество потоков для одного сайта (0 = полное распараллеливание)
DEFAULT_DOWNLOAD_PATH = "F:/G/Download"  # Путь по умолчанию

def check_ffmpeg():
    if not shutil.which("ffmpeg"):
        print("FFmpeg не найден. Конвертация файлов будет отключена.")
        return False
    return True

def clean_youtube_playlist_url(url):
    """Очищает URL плейлиста YouTube от лишних параметров."""
    if "youtube.com/playlist" in url or "youtu.be" in url:
        # Оставляем только основную часть URL плейлиста
        base_url = url.split('&')[0]
        return base_url
    return url

def analyze_url(url):
    try:
        with yt_dlp.YoutubeDL({'extract_flat': True, 'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            if 'entries' in info:
                return "playlist"
            elif 'title' in info:
                return "single_video"
    except yt_dlp.utils.DownloadError as e:
        print(f"URL не поддерживается: {url}. Пропускаем...")
        return None
    except Exception:
        pass
    return None

def get_playlist_range(total_videos):
    while True:
        range_input = input("Введите диапазон видео для скачивания (например, 1-3 или 0 для скачивания всех): ")
        if range_input == "0":
            return 1, total_videos  # Скачивать все видео
        try:
            start, end = map(int, range_input.split('-'))
            if 1 <= start <= total_videos and 1 <= end <= total_videos and start <= end:
                return start, end
            else:
                print(f"Неверный диапазон. Убедитесь, что числа находятся в пределах 1-{total_videos} и start <= end.")
        except ValueError:
            print("Пожалуйста, введите корректный диапазон (например, 1-3 или 0).")

def download_content(url, content_type, is_playlist=False, playlist_range=None):
    print(f"Начинаем загрузку {'аудио' if content_type == 'audio' else 'видео'}: {url}")

    if content_type == "audio":
        ydl_opts = {
            'format': 'bestaudio/best',  # Лучший аудиоформат
            'outtmpl': f'{DEFAULT_DOWNLOAD_PATH}/%(playlist_title)s/%(title)s.%(ext)s' if is_playlist else f'{DEFAULT_DOWNLOAD_PATH}/%(title)s.%(ext)s',
            'noplaylist': not is_playlist,
            'postprocessors': [],  # Отключаем автоматическую конвертацию
        }
    elif content_type == "video":
        ydl_opts = {
            'format': 'bestvideo+bestaudio/best',  # Лучшее видео с аудио
            'outtmpl': f'{DEFAULT_DOWNLOAD_PATH}/%(playlist_title)s/%(title)s.%(ext)s' if is_playlist else f'{DEFAULT_DOWNLOAD_PATH}/%(title)s.%(ext)s',
            'noplaylist': not is_playlist,
            'postprocessors': [],  # Отключаем автоматическую конвертацию
        }

    if is_playlist and playlist_range:
        ydl_opts.update({
            'playliststart': playlist_range[0],
            'playlistend': playlist_range[1],
        })

    try:
        os.makedirs(DEFAULT_DOWNLOAD_PATH, exist_ok=True)  # Создаем папку для загрузок
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        print(f"Загрузка завершена: {url}")
    except yt_dlp.utils.DownloadError as e:
        print(f"Ошибка при скачивании: {e}")
    except Exception as e:
        print(f"Произошла непредвиденная ошибка: {e}")

def process_link(url, content_type, playlist_ranges):
    print("-" * 50)  # Разделитель
    content_type_detected = analyze_url(url)
    if content_type_detected == "playlist":
        print(f"Ссылка '{url}' распознана как плейлист.")
        playlist_range = playlist_ranges.get(url)  # Получаем диапазон из словаря
        if playlist_range is None:
            print(f"Диапазон для плейлиста '{url}' не найден. Скачиваем все видео.")
            playlist_range = (1, float('inf'))  # По умолчанию скачивать все видео
        download_content(url, content_type, is_playlist=True, playlist_range=playlist_range)
    elif content_type_detected == "single_video":
        print(f"Ссылка '{url}' распознана как одиночное видео.")
        download_content(url, content_type, is_playlist=False)
    else:
        print(f"Не удалось определить тип контента для ссылки: {url}")
    print("-" * 50)  # Разделитель

def process_links_parallel(links, content_type, max_workers_per_site, playlist_ranges):
    sites = {}
    for link in links:
        domain = link.split('/')[2]  # Извлекаем домен (например, youtube.com)
        if domain not in sites:
            sites[domain] = []
        sites[domain].append(link)

    with ThreadPoolExecutor(max_workers=max_workers_per_site) as executor:
        for domain, domain_links in sites.items():
            print(f"Обрабатываем {len(domain_links)} ссылок для сайта: {domain}")
            for link in domain_links:
                executor.submit(process_link, link, content_type, playlist_ranges)

def analyze_downloaded_files():
    download_folder = DEFAULT_DOWNLOAD_PATH
    if not os.path.exists(download_folder):
        print(f"Папка {download_folder} не найдена. Нет файлов для анализа.")
        return

    files = []
    for root, _, filenames in os.walk(download_folder):
        for filename in filenames:
            files.append(os.path.join(root, filename))

    if not files:
        print(f"В папке {download_folder} нет файлов для анализа.")
        return

    print("Обнаруженные файлы:")
    for file in files:
        ext = os.path.splitext(file)[1][1:].lower()  # Получаем расширение файла
        print(f"- {file} ({ext})")

    convert = input("Хотите выполнить конвертацию? (да/нет): ").lower()
    if convert == "да":
        supported_formats = ["mp3", "mp4", "m4a", "wav", "flac", "avi", "mkv"]
        print("Доступные форматы для конвертации:")
        for i, fmt in enumerate(supported_formats, 1):
            print(f"{i}. {fmt}")
        try:
            choice = int(input("Введите номер формата для конвертации: "))
            target_format = supported_formats[choice - 1]
        except (ValueError, IndexError):
            print("Неверный выбор. Конвертация отменена.")
            return

        if not check_ffmpeg():
            print("FFmpeg не найден. Конвертация невозможна.")
            return

        for file in files:
            convert_file(file, target_format)
            os.remove(file)  # Удаляем оригинальный файл после конвертации
    else:
        print("Конвертация отменена.")

def convert_file(file, output_format):
    try:
        import subprocess
        output_file = os.path.splitext(file)[0] + f".{output_format}"
        ffmpeg_command = [
            'ffmpeg',
            '-i', file,
            '-c:v', 'copy' if output_format not in ["mp3", "wav", "flac"] else 'libmp3lame',
            '-c:a', 'copy' if output_format not in ["mp3", "wav", "flac"] else 'libmp3lame',
            output_file
        ]
        print(f"Выполняем конвертацию файла: {file}")
        subprocess.run(ffmpeg_command, check=True)
        print(f"Конвертация завершена: {output_file}")
    except Exception as e:
        print(f"Ошибка при конвертации файла {file}: {e}")

def process_links_from_file(file_path, content_type):
    while True:
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                links = file.read().splitlines()
                links = [clean_youtube_playlist_url(link.strip()) for link in links if link.strip()]
            if not links:
                print("Файл пустой. Попробуйте еще раз.")
                continue
            break
        except FileNotFoundError:
            print(f"Файл '{file_path}' не найден. Попробуйте еще раз.")
            file_path = input("Введите путь к текстовому файлу с ссылками: ")
        except Exception as e:
            print(f"Ошибка при чтении файла: {e}")
            file_path = input("Введите путь к текстовому файлу с ссылками: ")

    print(f"Обнаружено {len(links)} ссылок.")
    playlist_ranges = {}
    for link in links:
        if analyze_url(link) == "playlist":
            print(f"В файле обнаружен плейлист: {link}")
            with yt_dlp.YoutubeDL({'extract_flat': True, 'quiet': True}) as ydl:
                info = ydl.extract_info(link, download=False)
                total_videos = len(info['entries'])
                print(f"Обнаружен плейлист с {total_videos} видео.")
                playlist_ranges[link] = get_playlist_range(total_videos)

    process_links_parallel(links, content_type, MAX_WORKERS_PER_SITE, playlist_ranges)
    analyze_downloaded_files()

if __name__ == "__main__":
    print("Что вы хотите скачать?")
    print("1. Аудио")
    print("2. Видео")
    content_choice = input("Введите номер (1 или 2): ")

    if content_choice == "1":
        content_type = "audio"
    elif content_choice == "2":
        content_type = "video"
    else:
        print("Неверный выбор. Пожалуйста, введите 1 или 2.")
        sys.exit()

    print("Откуда взять ссылки?")
    print("1. Ввести вручную")
    print("2. Считать из текстового файла (main.txt)")
    source_choice = input("Введите номер (1 или 2): ")

    if source_choice == "1":
        url = input("Введите URL видео или плейлиста: ").strip()
        playlist_ranges = {}
        if analyze_url(url) == "playlist":
            with yt_dlp.YoutubeDL({'extract_flat': True, 'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                total_videos = len(info['entries'])
                print(f"Обнаружен плейлист с {total_videos} видео.")
                playlist_ranges[url] = get_playlist_range(total_videos)
        process_link(clean_youtube_playlist_url(url), content_type, playlist_ranges)
        analyze_downloaded_files()
    elif source_choice == "2":
        file_path = "main.txt"
        process_links_from_file(file_path, content_type)
    else:
        print("Неверный выбор. Пожалуйста, введите 1 или 2.")