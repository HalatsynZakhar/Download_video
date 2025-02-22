import yt_dlp
import shutil
import sys
import os

def check_ffmpeg():
    if not shutil.which("ffmpeg"):
        print("FFmpeg не найден. Пожалуйста, установите FFmpeg и добавьте его в PATH.")
        sys.exit(1)

def download_content(url, output_format, is_playlist=False, batch_mode=False):
    # Настройки для скачивания
    ydl_opts = {
        'format': f'bestvideo+bestaudio/{output_format}' if output_format != "mp3" else 'bestaudio/best',
        'outtmpl': '%(playlist_title)s/%(title)s.%(ext)s' if is_playlist else '%(title)s.%(ext)s',
        'noplaylist': not is_playlist,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio' if output_format == "mp3" else 'FFmpegVideoConvertor',
            'preferredcodec': output_format if output_format != "mp4" else None,
            'preferredquality': '192' if output_format == "mp3" else None,
        }] if output_format != "mp4" else [],
    }

    try:
        with yt_dlp.YoutubeDL({'extract_flat': True}) as ydl:
            # Получаем информацию о контенте без скачивания
            info_dict = ydl.extract_info(url, download=False)
            title = info_dict.get('title')
            playlist_title = info_dict.get('playlist_title', '') if is_playlist else ''

            if is_playlist and 'entries' in info_dict:
                total_videos = len(info_dict['entries'])
                print(f"Обнаружен плейлист: {playlist_title}")
                print(f"Доступное количество видео: {total_videos}")

                if not batch_mode:
                    # Запрашиваем диапазон видео только если не в пакетном режиме
                    while True:
                        try:
                            start = int(input(f"Введите начальный номер видео (1-{total_videos}): "))
                            end = int(input(f"Введите конечный номер видео (1-{total_videos}): "))
                            if 1 <= start <= total_videos and 1 <= end <= total_videos and start <= end:
                                break
                            else:
                                print(f"Неверный диапазон. Убедитесь, что числа находятся в пределах 1-{total_videos} и start <= end.")
                        except ValueError:
                            print("Пожалуйста, введите корректные числа.")

                    print(f"Скачивание видео с {start} по {end}...")
                    ydl_opts.update({
                        'playliststart': start,
                        'playlistend': end,
                    })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Начинаем загрузку
            print(f"Начинаем загрузку в формате {output_format}...")
            try:
                info_after_download = ydl.extract_info(url, download=True)

                # Проверяем формат скачанного файла после завершения постобработки
                if is_playlist and 'entries' in info_after_download:
                    for entry in info_after_download['entries']:
                        check_downloaded_file(entry, output_format, is_playlist, playlist_title, batch_mode)
                else:
                    check_downloaded_file(info_after_download, output_format, is_playlist, playlist_title, batch_mode)
            except yt_dlp.utils.DownloadError as e:
                print(f"Произошла ошибка при скачивании: {e}")
                return

    except Exception as e:
        print(f"Произошла ошибка: {e}")

def check_downloaded_file(info, output_format, is_playlist, playlist_title, batch_mode):
    # Извлекаем название и расширение файла
    title = info.get('title')
    ext = info.get('ext')

    if is_playlist:
        downloaded_file = f"{playlist_title}/{title}.{ext}"
    else:
        downloaded_file = f"{title}.{ext}"

    # Проверяем, соответствует ли формат заявленному
    if ext.lower() != output_format:
        print(f"Файл '{downloaded_file}' скачался в формате {ext}, а не {output_format}.")
        if not batch_mode:
            convert = input("Хотите выполнить конвертацию? (да/нет): ").lower()
            if convert == "да":
                check_ffmpeg()  # Убедимся, что FFmpeg установлен
                if output_format == "mp3":
                    convert_audio(title, is_playlist, playlist_title)
                else:
                    convert_video(title, output_format, is_playlist, playlist_title)
            else:
                print("Конвертация отменена.")
        else:
            print("Конвертация отключена в пакетном режиме.")
    else:
        print(f"Файл успешно скачан в формате {output_format}: {downloaded_file}")

def convert_video(video_title, output_format, is_playlist, playlist_title):
    # Конвертируем видео в выбранный формат
    input_file = f"{playlist_title}/{video_title}.mp4" if is_playlist else f"{video_title}.mp4"
    output_file = f"{playlist_title}/{video_title}.{output_format}" if is_playlist else f"{video_title}.{output_format}"

    ffmpeg_command = [
        'ffmpeg',
        '-i', input_file,
        '-c:v', 'copy',
        '-c:a', 'copy',
        output_file
    ]

    try:
        import subprocess
        print(f"Выполняем конвертацию в формат {output_format}...")
        subprocess.run(ffmpeg_command, check=True)
        print(f"Конвертация завершена: {output_file}")
    except Exception as e:
        print(f"Ошибка при конвертации: {e}")

def convert_audio(audio_title, is_playlist, playlist_title):
    # Конвертируем аудио в MP3
    input_file = f"{playlist_title}/{audio_title}.webm" if is_playlist else f"{audio_title}.webm"
    output_file = f"{playlist_title}/{audio_title}.mp3" if is_playlist else f"{audio_title}.mp3"

    ffmpeg_command = [
        'ffmpeg',
        '-i', input_file,
        '-vn',                         # Игнорируем видео
        '-acodec', 'libmp3lame',       # Кодек MP3
        '-q:a', '2',                   # Качество (0 - лучшее, 9 - худшее)
        output_file
    ]

    try:
        import subprocess
        print("Выполняем конвертацию аудио в MP3...")
        subprocess.run(ffmpeg_command, check=True)
        print(f"Конвертация завершена: {output_file}")
    except Exception as e:
        print(f"Ошибка при конвертации: {e}")

def process_links_from_file(file_path, output_format, is_playlist=False):
    # Читаем ссылки из текстового файла
    while True:
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                links = file.read().splitlines()
                # Убираем всё после "?" и пустые строки
                links = [link.split('?')[0].strip() for link in links if link.strip()]
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

    # Определяем, сколько ссылок в файле
    if len(links) == 1:
        print("Обнаружена одна ссылка. Запускаем стандартный режим.")
        download_content(links[0], output_format, is_playlist=is_playlist, batch_mode=False)
    else:
        print(f"Обнаружено {len(links)} ссылок. Запускаем пакетный режим.")
        for i, link in enumerate(links, start=1):
            print(f"\nОбработка ссылки {i}/{len(links)}: {link}")
            download_content(link, output_format, is_playlist=is_playlist, batch_mode=True)


if __name__ == "__main__":
    # Диалог для выбора режима
    print("Что вы хотите скачать?")
    print("1. Одиночное видео или аудио")
    print("2. Весь плейлист или часть плейлиста")
    choice = input("Введите номер (1 или 2): ")

    # Запрашиваем источник ссылок
    print("Откуда взять ссылки?")
    print("1. Ввести вручную")
    print("2. Считать из текстового файла (main.txt)")
    source_choice = input("Введите номер (1 или 2): ")

    # Запрашиваем формат
    print("Выберите формат (mp3, mkv, avi, hevc, mp4): ")
    output_format = input().lower()

    if source_choice == "1":
        url = input("Введите URL видео или плейлиста: ").split('?')[0].strip()  # Убираем всё после "?" и пустые строки
        urls = [url]  # Одна ссылка
    elif source_choice == "2":
        file_path = "main.txt"  # Фиксированный путь к файлу
        process_links_from_file(file_path, output_format=output_format, is_playlist=(choice == "2"))
        sys.exit(0)  # Завершаем выполнение после обработки файла
    else:
        print("Неверный выбор. Пожалуйста, введите 1 или 2.")
        sys.exit(1)

    # Выбор режима
    if choice == "1":
        print("Скачивание одиночного видео или аудио...")
        download_content(urls[0], output_format, is_playlist=False)
    elif choice == "2":
        print("Скачивание плейлиста или части плейлиста...")
        download_content(urls[0], output_format, is_playlist=True)
    else:
        print("Неверный выбор. Пожалуйста, введите 1 или 2.")