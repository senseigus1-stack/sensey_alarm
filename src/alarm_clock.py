import sys
import time
import threading
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk, messagebox
import pygame.mixer
import sounddevice as sd
import os
import json
import logging
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('alarm_clock.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class AlarmClock:
    def __init__(self, root):
        self.root = root
        self.root.title("Alarm Sensey")
        self.root.geometry("450x400")
        self.root.resizable(False, False)
        
        # Конфигурационный файл
        self.config_file = Path("config.json")
        self.load_config()

        # Инициализация аудио
        try:
            pygame.mixer.init()
        except Exception as e:
            logging.error(f"Ошибка инициализации pygame: {e}")
            messagebox.showerror("Ошибка", "Не удалось инициализировать аудиосистему")

        self.is_alarm_set = False
        self.alarm_time = None
        self.sound_file = self.config.get("sound_file", "Свиридов Время Вперед.wav")
        self.snooze_interval = 5  # минут по умолчанию
        self.volume = self.config.get("volume", 0.5)

        # Инициализация кнопки остановки как None
        self.stop_btn = None  # <-- Добавьте эту строку

        self.create_widgets()
        self.update_clock()

        # Обработка закрытия окна
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def load_config(self):
        """Загрузка настроек из файла"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            else:
                self.config = {
                    "last_time": None,
                    "device": None,
                    "sound_file": "C:/Users/arsenii/Desktop/sensey_alarm/Свиридов Время Вперед.wav",
                    "volume": 0.5
                }
        except Exception as e:
            logging.error(f"Ошибка загрузки конфигурации: {e}")
            self.config = {
                "last_time": None,
                "device": None,
                "sound_file": "alarm.wav",
                "volume": 0.5
            }

    def save_config(self):
        """Сохранение настроек в файл"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Ошибка сохранения конфигурации: {e}")

    def create_widgets(self):
        # Текущее время
        self.time_label = ttk.Label(self.root, font=("Helvetica", 24))
        self.time_label.pack(pady=10)

        # Выбор времени будильника
        ttk.Label(self.root, text="Установите время будильника:").pack()

        self.hour_var = tk.StringVar(value=self.config["last_time"]["hour"] if self.config["last_time"] else "00")
        self.minute_var = tk.StringVar(value=self.config["last_time"]["minute"] if self.config["last_time"] else "00")

        hour_combo = ttk.Combobox(self.root, textvariable=self.hour_var, values=[f"{i:02d}" for i in range(24)], width=5)
        hour_combo.pack(side=tk.LEFT, padx=5)

        ttk.Label(self.root, text=":").pack(side=tk.LEFT)

        minute_combo = ttk.Combobox(self.root, textvariable=self.minute_var, values=[f"{i:02d}" for i in range(60)], width=5)
        minute_combo.pack(side=tk.LEFT, padx=5)

        # Выбор устройства вывода
        ttk.Label(self.root, text="Устройство вывода:").pack(pady=5)
        self.device_var = tk.StringVar(value=self.config["device"] or "")

        devices = self.get_audio_devices()
        if devices:
            device_combo = ttk.Combobox(self.root, textvariable=self.device_var, values=devices, width=30)
            if self.config["device"]:
                try:
                    device_combo.set(self.config["device"])
                except:
                    device_combo.current(0)
            else:
                device_combo.current(0)
            device_combo.pack(pady=2)
        else:
            ttk.Label(self.root, text="Устройства не найдены", foreground="red").pack()

        # Регулятор громкости
        ttk.Label(self.root, text="Громкость:").pack(pady=2)
        self.volume_var = tk.DoubleVar(value=self.volume)
        volume_scale = ttk.Scale(
            self.root,
            variable=self.volume_var,
            from_=0,
            to=1,
            orient=tk.HORIZONTAL,
            command=self.set_volume
        )
        volume_scale.pack(fill=tk.X, padx=20, pady=2)

        # Кнопки управления
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(pady=10)

        self.set_btn = ttk.Button(btn_frame, text="Установить будильник", command=self.set_alarm)
        self.set_btn.pack(side=tk.LEFT, padx=5)

        self.clear_btn = ttk.Button(btn_frame, text="Отменить будильник", command=self.clear_alarm, state=tk.DISABLED)
        self.clear_btn.pack(side=tk.LEFT, padx=5)

        self.snooze_btn = ttk.Button(btn_frame, text="Snooze (5 мин)", command=self.snooze, state=tk.DISABLED)
        self.snooze_btn.pack(side=tk.LEFT, padx=5)

        # Статус
        self.status_label = ttk.Label(self.root, text="Будильник не установлен")
        self.status_packed = False

    def get_audio_devices(self):
        """Получить список доступных аудиоустройств"""
        try:
            devices = sd.query_devices()
            return [f"{i}: {d['name']}" for i, d in enumerate(devices) if d['max_output_channels'] > 0]
        except Exception as e:
            logging.error(f"Ошибка получения аудиоустройств: {e}")
            return []

    def update_clock(self):
        """Обновлять отображение текущего времени"""
        current_time = datetime.now().strftime("%H:%M:%S")
        self.time_label.config(text=current_time)
        self.check_alarm()
        self.root.after(1000, self.update_clock)  # Каждые 1 сек

    def set_alarm(self):
        """Установить будильник"""
        try:
            hour = int(self.hour_var.get())
            minute = int(self.minute_var.get())
            self.alarm_time = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)

            # Если время уже прошло сегодня, установить на завтра
            if self.alarm_time < datetime.now():
                self.alarm_time += timedelta(days=1)

            self.is_alarm_set = True
            
            # Блокировка комбобоксов
            for widget in [self.hour_var, self.minute_var, self.device_var]:
                widget.set(widget.get())
                # В tkinter нельзя напрямую заблокировать Combobox, поэтому просто снимаем фокус
                # и будем проверять состояние в других методах
            self.set_btn.config(state=tk.DISABLED)
            self.clear_btn.config(state=tk.NORMAL)
            self.snooze_btn.config(state=tk.NORMAL)


            # Сохранение в конфигурацию
            self.config["last_time"] = {"hour": self.hour_var.get(), "minute": self.minute_var.get()}
            self.save_config()

            formatted_time = self.alarm_time.strftime("%H:%M")
            self.status_label.config(text=f"Будильник установлен на {formatted_time}")
            logging.info(f"Будильник установлен на {formatted_time}")
        except ValueError:
            messagebox.showerror("Ошибка", "Некорректное время")
            logging.warning("Попытка установки будильника с некорректным временем")

    def clear_alarm(self):
        """Отменить будильник"""
        self.is_alarm_set = False
        self.alarm_time = None
        
        # Разблокировка комбобоксов (косвенно через снятие состояния)
        self.set_btn.config(state=tk.NORMAL)
        self.clear_btn.config(state=tk.DISABLED)
        self.snooze_btn.config(state=tk.DISABLED)

        self.status_label.config(text="Будильник не установлен")
        logging.info("Будильник отменён")

    def snooze(self):
        """Функция Snooze — отложить будильник"""
        if self.is_alarm_set:
            snooze_delta = timedelta(minutes=self.snooze_interval)
            self.alarm_time += snooze_delta
            
            new_time = self.alarm_time.strftime("%H:%M")
            self.status_label.config(text=f"Snooze: будильник перенесён на {new_time}")
            logging.info(f"Snooze активирован. Новый время будильника: {new_time}")

    def check_alarm(self):
        """Проверять, пора ли срабатывать будильнику"""
        if self.is_alarm_set and datetime.now() >= self.alarm_time:
            self.trigger_alarm()

    def trigger_alarm(self):
        """Сработать будильнику"""
        self.is_alarm_set = False
        self.status_label.config(text="БУДИЛЬНИК!")
        logging.info("Будильник сработал!")

        # Проверка существования звукового файла
        if not os.path.exists(self.sound_file):
            logging.error(f"Звуковой файл не найден: {self.sound_file}")
            messagebox.showerror("Ошибка", f"Звуковой файл не найден: {self.sound_file}")
            return

        # Установка выбранного устройства вывода
        try:
            device_id = int(self.device_var.get().split(":")[0])
            device_name = sd.query_devices()[device_id]['name']
            
            pygame.mixer.quit()
            pygame.mixer.init(devicename=device_name)
            logging.info(f"Аудиоустройство установлено: {device_name}")
        except (ValueError, IndexError, Exception) as e:
            logging.error(f"Ошибка при выборе аудиоустройства: {e}")
            messagebox.showerror("Ошибка", "Не удалось установить аудиоустройство")
            return

        # Воспроизведение звука
        try:
            pygame.mixer.music.load(self.sound_file)
            pygame.mixer.music.set_volume(self.volume)
            pygame.mixer.music.play(-1)  # Повторять бесконечно
            logging.info(f"Воспроизведение звука: {self.sound_file} (громкость: {self.volume})")
        except pygame.error as e:
            logging.error(f"Ошибка воспроизведения звука: {e}")
            messagebox.showerror("Ошибка", f"Не удалось воспроизвести звук: {e}")
            return

        # Кнопка остановки
        if not self.stop_btn:
            self.stop_btn = ttk.Button(self.root, text="Остановить", command=self.stop_alarm)
            self.stop_btn.pack(pady=10)
        else:
            self.stop_btn.pack(pady=10)

    def stop_alarm(self):
        """Остановить звук будильника"""
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
            pygame.mixer.quit()
            logging.info("Звук будильника остановлен")
        
        if self.stop_btn and self.stop_btn.winfo_exists():
            self.stop_btn.pack_forget()
        
        self.status_label.config(text="Будильник остановлен")
        logging.info("Будильник остановлен")

    def set_volume(self, value):
        """Установить громкость"""
        self.volume = float(value)
        if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
            pygame.mixer.music.set_volume(self.volume)
        self.config["volume"] = self.volume
        self.save_config()
        logging.info(f"Громкость установлена на {self.volume:.2f}")

    def on_closing(self):
        """Обработка закрытия окна"""
        self.stop_alarm()  # Остановить звук при закрытии
        self.root.destroy()
        logging.info("Приложение закрыто")

def main():
    root = tk.Tk()
    app = AlarmClock(root)
    root.mainloop()

if __name__ == "__main__":
    main()