import time
import requests
import pigpio
import sys
sys.path.append("/home/pi/lcd")
from lcd import drivers
sys.path.append("/home/pi/lcd/drivers")
import drivers
import pytz
from astral import LocationInfo
from astral.sun import sun
from datetime import datetime

# Ustawienia pinu PWM
BACKLIGHT_PIN = 12  # GPIO12 obsługuje sprzętowy PWM na Raspberry Pi
FREQ = 1000  # Częstotliwość PWM w Hz

# Inicjalizacja pigpio
pi = pigpio.pi()
if not pi.connected:
    print("Nie można połączyć z demonem pigpio. Upewnij się, że jest uruchomiony.")
    exit()

pi.set_mode(BACKLIGHT_PIN, pigpio.OUTPUT)
pi.set_PWM_frequency(BACKLIGHT_PIN, FREQ)
pi.set_PWM_range(BACKLIGHT_PIN, 100)  # Ustawiamy zakres 0-100 dla Duty Cycle

def fade_backlight(start, end, step=1, delay=0.01):
    if start < end:
        step = abs(step)
    else:
        step = -abs(step)

    for duty in range(start, end + step, step):
        pi.set_PWM_dutycycle(BACKLIGHT_PIN, duty)
        time.sleep(delay)
    pi.set_PWM_dutycycle(BACKLIGHT_PIN, end)

# Adres API
API_URL = "https://countall.com.pl/php/api.php"

# Inicjalizacja wyświetlacza
lcd = drivers.Lcd()

# --- Własne ikony (CGRAM, 5x8 pikseli). LCD ma tylko 8 slotów naraz, więc
# ładujemy dynamicznie tylko te ikony, które są potrzebne na danym ekranie. ---
ICON_THERM = ["00100",
              "01010",
              "01010",
              "01010",
              "01010",
              "10001",
              "10001",
              "01110"]

ICON_DROP = ["00100",
             "00100",
             "01110",
             "11111",
             "11111",
             "11111",
             "01110",
             "00000"]

ICON_RAIN = ["00000",
             "01110",
             "11111",
             "11111",
             "01110",
             "00000",
             "01010",
             "10101"]

ICON_GAUGE = ["01110",
              "10001",
              "10101",
              "10101",
              "10001",
              "01110",
              "00100",
              "00100"]

ICON_BOLT = ["00011",
             "00110",
             "01100",
             "11111",
             "00110",
             "01100",
             "11000",
             "10000"]

ICON_CLOCK = ["01110",
              "10001",
              "10101",
              "10111",
              "10001",
              "10001",
              "01110",
              "00000"]

ICON_HOME = ["00100",
             "01110",
             "11111",
             "11111",
             "01010",
             "01010",
             "01010",
             "00000"]

ICON_SUN = ["00100",
            "10101",
            "01110",
            "11111",
            "01110",
            "10101",
            "00100",
            "00000"]

ICON_SNOW = ["10101",
             "01110",
             "00100",
             "11111",
             "00100",
             "01110",
             "10101",
             "00000"]

ICON_WARN = ["00100",
             "01110",
             "01110",
             "01110",
             "01110",
             "00000",
             "00100",
             "00000"]

ICON_ARROW_UP = ["00100",
                  "01110",
                  "11111",
                  "00100",
                  "00100",
                  "00100",
                  "00100",
                  "00000"]

ICON_ARROW_DOWN = ["00000",
                    "00100",
                    "00100",
                    "00100",
                    "00100",
                    "11111",
                    "01110",
                    "00100"]

ICON_ARROW_FLAT = ["00000",
                    "00100",
                    "00010",
                    "11111",
                    "00010",
                    "00100",
                    "00000",
                    "00000"]

# Strzałki kierunku wiatru wg oktantu: N, NE, E, SE, S, SW, W, NW
WIND_ARROWS = [
    ["00100", "01110", "10101", "00100", "00100", "00100", "00100", "00000"],  # N
    ["00000", "00111", "00011", "00101", "01000", "10000", "00000", "00000"],  # NE
    ["00000", "00100", "00010", "11111", "00010", "00100", "00000", "00000"],  # E
    ["00000", "10000", "01000", "00101", "00011", "00111", "00000", "00000"],  # SE
    ["00000", "00100", "00100", "00100", "00100", "10101", "01110", "00100"],  # S
    ["00000", "00001", "00010", "10100", "11000", "11100", "00000", "00000"],  # SW
    ["00000", "00100", "01000", "11111", "01000", "00100", "00000", "00000"],  # W
    ["00000", "11100", "11000", "10100", "00010", "00001", "00000", "00000"],  # NW
]

_PLACEHOLDERS = ["{0x00}", "{0x01}", "{0x02}", "{0x03}", "{0x04}", "{0x05}", "{0x06}", "{0x07}"]
_CGRAM_ADDR = [0x40, 0x48, 0x50, 0x58, 0x60, 0x68, 0x70, 0x78]
_RS = 0b00000001  # bit Register Select sterownika lcd - wybiera zapis danych, nie komendy
_loaded_icons = [None] * 8  # co aktualnie siedzi w każdym slocie CGRAM

def set_icons(*bitmaps):
    """Ładuje podane bitmapy (max 8) do CGRAM i zwraca listę placeholderów
    {0x00}.. w tej samej kolejności, do użycia w lcd_display_extended_string.
    Nadpisuje po I2C tylko te sloty, których zawartość faktycznie się zmieniła
    względem poprzedniego ekranu - dzięki temu przejścia między ekranami
    dzielącymi wspólną ikonę (np. ten sam domek) są równie płynne jak między
    "Prod. teraz" i "Prod. dzis", które zawsze używały jednej, wspólnej ikonki."""
    for slot, bmp in enumerate(bitmaps):
        if _loaded_icons[slot] == bmp:
            continue
        _loaded_icons[slot] = bmp
        lcd.lcd_write(_CGRAM_ADDR[slot])
        for row in bmp:
            lcd.lcd_write(int("0b000" + row, 2), _RS)
    return _PLACEHOLDERS[:len(bitmaps)]

def get_wind_octant(degree_raw):
    try:
        degree = float(degree_raw) % 360
    except (TypeError, ValueError):
        return 0
    # wind_degree z API to kierunek, SKĄD wieje wiatr - obracamy o 180 st.,
    # żeby strzałka pokazywała, DOKĄD wiatr płynie
    degree = (degree + 180) % 360
    return int((degree + 22.5) // 45) % 8

def get_condition_icon(temp, suma_opadu):
    if suma_opadu > 0:
        return ICON_RAIN
    if temp < 0:
        return ICON_SNOW
    return ICON_SUN

def get_pressure_trend_icon(current, previous, threshold=0.5):
    if previous is None or abs(current - previous) < threshold:
        return ICON_ARROW_FLAT
    return ICON_ARROW_UP if current > previous else ICON_ARROW_DOWN

def get_weather_data():
    while True:
        try:
            response = requests.get(API_URL, timeout=15)
            response.raise_for_status()
            data = response.json()

            # Pobranie wartości jako liczby
            temp = float(data["weather_data"]["current"].get("temp_c", 0))
            humidity = float(data["weather_data"]["current"].get("humidity", 0))
            suma_opadu = float(data["weather_data"]["current"].get("precip_mm", 0))
            pressure = float(data["weather_data"]["current"].get("pressure_mb", 0))
            data_pomiaru = data["weather_data"]["current"].get("last_updated", "Brak danych")
            predkosc_wiatru = float(data["weather_data"]["current"].get("wind_kph", 0))
            kierunek_wiatru = data["weather_data"]["current"].get("wind_dir", "Brak danych")
            kierunek_wiatru_degree = data["weather_data"]["current"].get("wind_degree", "Brak danych")
            prod_now = str(int(data.get("aktualna_produkcja", 0)))
            today_prod = float(data.get("today_prod", 0))
            home_temp = float(data.get("home_temp", 0))
            home_humidity = float(data.get("home_humidity", 0))
            home_presure = float(data.get("home_presure", 0))
            stacja = data["weather_data"]["location"].get("name", "Cracow")

            return temp, humidity, pressure, prod_now, today_prod, suma_opadu, data_pomiaru, stacja, kierunek_wiatru, predkosc_wiatru, kierunek_wiatru_degree, home_temp, home_humidity, home_presure
        except requests.exceptions.RequestException as e:
            print(f"Blad pobierania danych: {e}")
            lcd.lcd_clear()
            lcd.lcd_display_string("Blad pobierania", 1)
            lcd.lcd_display_string("Czekam na dane", 2)
            fade_backlight(0, 50, step=1, delay=0.02)  # Rozjaśnienie do 50%
            time.sleep(5)  # Odczekanie przed kolejną próbą
            fade_backlight(0, 50, step=1, delay=0.02)  # Rozjaśnienie do 50%


def get_max_brightness():
    try:
        city = LocationInfo("Cracow", "Poland")  # Ustawiamy Kraków
        s = sun(city.observer, date=datetime.today())

        # Uzyskujemy czas systemowy w strefie czasowej Bangkoku
        cracow_tz = pytz.timezone("Europe/Warsaw")
        now = datetime.now(cracow_tz).replace(microsecond=0).time()  # Usuwamy mikrosekundy

        # Sprawdzamy dane o wschodzie i zachodzie słońca
        sunrise_time = s["sunrise"].time()
        sunset_time = s["sunset"].time()

        # Porównanie godzin i minut (bez mikrosekund)
        if sunrise_time <= now <= sunset_time:
            return 100  # Między wschodem a zachodem słońca
        else:
            return 50  # Po zachodzie, lub przed wschodem

    except Exception as e:
        return 50  # Bezpieczna wartość domyślna

def display_data_on_lcd(top_line, bottom_line, hold_time=2.0):
    lcd.lcd_clear()
    lcd.lcd_display_extended_string(top_line, 1)
    lcd.lcd_display_extended_string(bottom_line, 2)
    max_brightness = get_max_brightness()
    step = 0.02 if max_brightness == 50 else 0.01
    fade_backlight(0, max_brightness, step=1, delay=step)  # Rozjaśnienie
    time.sleep(hold_time)
    fade_backlight(max_brightness, 0, step=1, delay=step)  # Ściemnienie

def display_scrolling(top_line, bottom_text, hold_time=2.0, scroll_speed=0.35):
    """Górna linia (może zawierać placeholder ikony) jest statyczna. Dolna linia
    to zwykły tekst - jeśli ma więcej niż 16 znaków, przewija się w lewo."""
    lcd.lcd_clear()
    lcd.lcd_display_extended_string(top_line, 1)

    scroll = len(bottom_text) > 16
    if scroll:
        padded = bottom_text + "   "
        loop_text = padded + padded
    lcd.lcd_display_string(loop_text[0:16] if scroll else bottom_text, 2)

    max_brightness = get_max_brightness()
    step = 0.02 if max_brightness == 50 else 0.01
    fade_backlight(0, max_brightness, step=1, delay=step)

    if scroll:
        for i in range(1, len(padded)):
            lcd.lcd_display_string(loop_text[i:i + 16], 2)
            time.sleep(scroll_speed)
    else:
        time.sleep(hold_time)

    fade_backlight(max_brightness, 0, step=1, delay=step)

def display_alert(temp, suma_opadu):
    """Migający ekran ostrzegawczy - mróz lub opady - pokazywany częściej niż zwykłe ekrany."""
    if temp < 0:
        message = f"Mroz! {temp}\xDFC"
    else:
        message = f"Deszcz! {suma_opadu}mm"

    ic_warn, = set_icons(ICON_WARN)
    lcd.lcd_clear()
    lcd.lcd_display_extended_string(f"{ic_warn} UWAGA POGODA", 1)
    lcd.lcd_display_string(message[:16], 2)

    max_brightness = get_max_brightness()
    step = 0.02 if max_brightness == 50 else 0.01
    for _ in range(3):
        fade_backlight(0, max_brightness, step=2, delay=step)
        fade_backlight(max_brightness, 15, step=2, delay=step)
    fade_backlight(15, max_brightness, step=1, delay=step)
    time.sleep(1)
    fade_backlight(max_brightness, 0, step=1, delay=step)

prev_pressure = None

while True:
    try:
        # Pobranie danych z API
        temp, humidity, pressure, prod_now, today_prod, suma_opadu, data_pomiaru, stacja, kierunek_wiatru, predkosc_wiatru, kierunek_wiatru_degree, home_temp, home_humidity, home_presure = get_weather_data()

        if None not in [temp, humidity, pressure, prod_now, today_prod, suma_opadu, data_pomiaru, stacja, kierunek_wiatru, predkosc_wiatru, kierunek_wiatru_degree, home_temp, home_humidity, home_presure]:
            wind_octant = get_wind_octant(kierunek_wiatru_degree)
            condition_icon = get_condition_icon(temp, suma_opadu)
            trend_icon = get_pressure_trend_icon(pressure, prev_pressure)
            alert = temp < 0 or suma_opadu > 0

            ic_clock, ic_cond = set_icons(ICON_CLOCK, condition_icon)
            display_scrolling(f"{ic_clock}{ic_cond} Data pomiaru", data_pomiaru)

            ic_home, = set_icons(ICON_HOME)
            display_scrolling(f"{ic_home} Stacja pogody", stacja)

            for i in range(4):
                ic_therm, = set_icons(ICON_THERM)
                display_data_on_lcd(f"{ic_therm} Temp. zewn.", f"{temp}\xDFC")

                ic_gauge, ic_trend = set_icons(ICON_GAUGE, trend_icon)
                display_data_on_lcd(f"{ic_gauge}{ic_trend} Cisn. wzgl.", f"{pressure}hPa")

                if alert:
                    display_alert(temp, suma_opadu)

                ic_gauge, ic_home = set_icons(ICON_GAUGE, ICON_HOME)
                display_data_on_lcd(f"{ic_gauge}{ic_home} Cisn.bezwz.", f"{home_presure}hPa")

                ic_drop, ic_rain = set_icons(ICON_DROP, ICON_RAIN)
                display_data_on_lcd(f"{ic_drop} Wilg: {humidity}%", f"{ic_rain} Opad: {suma_opadu}mm")

                ic_wind, = set_icons(WIND_ARROWS[wind_octant])
                display_scrolling(f"{ic_wind} Wiatr {predkosc_wiatru}km/h", f"Kier: {kierunek_wiatru_degree}\xDF {kierunek_wiatru}")

                if alert:
                    display_alert(temp, suma_opadu)

                ic_home, ic_therm = set_icons(ICON_HOME, ICON_THERM)
                display_data_on_lcd(f"{ic_home}{ic_therm} Temp. dom", f"{home_temp}\xDFC")

                ic_home, ic_drop = set_icons(ICON_HOME, ICON_DROP)
                display_data_on_lcd(f"{ic_home}{ic_drop} Wilg. dom", f"{home_humidity}%")

                ic_bolt, = set_icons(ICON_BOLT)
                display_data_on_lcd(f"{ic_bolt} Prod. teraz", f"{prod_now}W")
                display_data_on_lcd(f"{ic_bolt} Prod. dzis", f"{today_prod}kWh")

            prev_pressure = pressure

    except Exception as e:
        display_data_on_lcd("Wystapil blad", str(e)[:16])
        time.sleep(5)
        continue
