# Rpi LCD Weather

Stacja pogodowa na Raspberry Pi wyświetlająca dane z API na wyświetlaczu **LCD 2×16** (I2C), z własnymi ikonami, obracającą się strzałką kierunku wiatru i płynnym ściemnianiem podświetlenia zależnym od pory dnia.

## Funkcje

- **Karuzela ekranów** — temperatura, ciśnienie (względne i bezwzględne), wilgotność, opady, wiatr, produkcja energii, dane z czujników domowych.
- **Własne ikony CGRAM** — termometr, kropla, chmura z deszczem, barometr, błyskawica, zegar, domek, słońce/śnieg zależnie od warunków.
- **Strzałka kierunku wiatru** — 8 wariantów (N/NE/E/SE/S/SW/W/NW), dobierana automatycznie na podstawie stopni z API i pokazująca kierunek, w który wiatr faktycznie wieje.
- **Trend ciśnienia** — strzałka ↑ / ↓ / → porównująca aktualny odczyt z poprzednim cyklem odświeżania.
- **Przewijany tekst** — nazwa stacji, pełna data pomiaru i kierunek wiatru przewijają się, jeśli nie mieszczą się w 16 znakach.
- **Alert pogodowy** — migający ekran ostrzegawczy przy mrozie lub opadach, pokazywany częściej niż pozostałe ekrany.
- **Automatyczna jasność** — pełna jasność podświetlenia między wschodem a zachodem słońca (wyliczane dla lokalizacji przez `astral`), przyciemnienie w nocy.
- **Płynne przejścia** — zapis do CGRAM tylko dla ikon, które faktycznie się zmieniły względem poprzedniego ekranu, więc przełączanie ekranów nie miga.

## Wymagany sprzęt

- Raspberry Pi (dowolny model z GPIO i I2C)
- Wyświetlacz LCD 2×16 ze sterownikiem HD44780 podłączony przez konwerter I2C (PCF8574, domyślny adres `0x27`)
- Podświetlenie LCD sterowane sprzętowym PWM na **GPIO12**

## Zależności

- Python 3
- [`the-raspberry-pi-guy/lcd`](https://github.com/the-raspberry-pi-guy/lcd) — sklonowany do `/home/pi/lcd`
- `pigpio` (i uruchomiony demon `pigpiod`)
- `requests`
- `pytz`
- `astral`

```bash
sudo apt install pigpio python3-pigpio
sudo pigpiod
pip install requests pytz astral

git clone https://github.com/the-raspberry-pi-guy/lcd.git /home/pi/lcd
```

## Konfiguracja

W pliku [`weather.py`](weather.py):

- `API_URL` — adres API zwracającego dane pogodowe w formacie zgodnym z `get_weather_data()`.
- `BACKLIGHT_PIN` / `FREQ` — pin i częstotliwość PWM podświetlenia.
- Lokalizacja w `get_max_brightness()` (domyślnie Kraków) — steruje wschodem/zachodem słońca do automatycznej jasności.

## Uruchomienie

```bash
python3 weather.py
```

Skrypt działa w nieskończonej pętli: pobiera dane z API, po czym cyklicznie wyświetla je na LCD, odświeżając dane po każdym pełnym przejściu przez karuzelę ekranów.
