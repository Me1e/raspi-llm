#!/usr/bin/env python3

import asyncio
import websockets
import logging
import json
import base64 # 오디오 데이터 Base64 인코딩용
from websockets.connection import State # State 임포트 추가
from picamera2 import Picamera2 # picamera2 임포트
import io # 이미지 스트림 처리를 위해
import time # 프레임 간격 제어를 위해
import RPi.GPIO as GPIO # RPi.GPIO 임포트

# OLED 라이브러리 임포트
import board
import busio
import digitalio
from PIL import Image, ImageDraw, ImageFont
import adafruit_ssd1306

# 기본 로깅 설정
logging.basicConfig(level=logging.INFO)
logging.info(f"Using websockets library version: {websockets.__version__}")

# --- GPIO 설정 ---
# 실제 연결된 GPIO 핀 번호로 수정해야 합니다.
GREEN_LED_PIN = 17 
YELLOW_LED_PIN = 27
RED_LED_PIN = 22
WHITE_LED_PIN = 10 # 흰색 LED 핀 추가
SERVO_PIN = 18 # 서보모터 GPIO 핀
TRIG_PIN = 23 # 초음파 센서 Trig 핀
ECHO_PIN = 24 # 초음파 센서 Echo 핀
BUZZER_PIN = 9 # Example GPIO pin for the buzzer

# OLED 설정
OLED_WIDTH = 128
OLED_HEIGHT = 64
OLED_RESET_PIN_BCM = 4 # GPIO4, 물리적 핀 7. 실제 연결된 핀으로 수정하거나 None으로 설정 가능

led_pins = {
    "green": GREEN_LED_PIN,
    "yellow": YELLOW_LED_PIN,
    "red": RED_LED_PIN,
    "white": WHITE_LED_PIN # 흰색 LED 딕셔너리에 추가
}

servo_motor = None # PWM 객체 저장용
current_servo_angle = 90 # 서보 모터의 현재 각도 추정 (0-180, 초기값은 중앙으로)
oled_display = None
display_draw_obj = None
display_image_obj = None
loaded_font = None

def setup_gpio():
    global servo_motor, current_servo_angle
    GPIO.setmode(GPIO.BCM) # BCM 핀 번호 사용
    GPIO.setwarnings(False) # 경고 메시지 비활성화
    for pin in led_pins.values():
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW) # 초기 상태는 꺼짐
    
    GPIO.setup(SERVO_PIN, GPIO.OUT)
    servo_motor = GPIO.PWM(SERVO_PIN, 50)  # 50Hz (20ms 주기)
    servo_motor.start(0) # 초기 듀티 사이클 0 (펄스 없음)
    # 초기 각도를 90도(중앙)로 설정 시도
    # duty_cycle_for_90_deg = (90.0 / 18.0) + 2.5 
    # servo_motor.ChangeDutyCycle(duty_cycle_for_90_deg)
    # time.sleep(0.5) # 서보가 움직일 시간
    # servo_motor.ChangeDutyCycle(0) # 펄스 중지 (지터 방지)
    current_servo_angle = 90 # 초기 각도 설정
    set_servo_angle_absolute(current_servo_angle) # 실제 모터 이동

    GPIO.setup(TRIG_PIN, GPIO.OUT)
    GPIO.setup(ECHO_PIN, GPIO.IN)
    GPIO.output(TRIG_PIN, False) # 초기 Trig 핀은 LOW 상태

    GPIO.setup(BUZZER_PIN, GPIO.OUT)
    GPIO.output(BUZZER_PIN, GPIO.LOW) # Ensure buzzer is off initially

    logging.info("GPIO setup complete for LEDs, Servo, and Ultrasonic sensor.")
    logging.info("Waiting for ultrasonic sensor to settle...")
    time.sleep(2) # 센서 안정화 시간
    logging.info("Ultrasonic sensor settled.")

def setup_oled():
    global oled_display, display_draw_obj, display_image_obj, loaded_font
    try:
        logging.info("Initializing OLED display...")
        i2c = board.I2C()  # uses board.SCL and board.SDA
        reset_pin_obj = None
        if OLED_RESET_PIN_BCM is not None:
            # board 라이브러리는 물리적 핀 이름 (예: D4)을 사용하거나 BCM 번호를 직접 사용할 수 있게 digitalio.DigitalInOut로 매핑 필요
            # digitalio.DigitalInOut는 board.D<GPIO_NUMBER> 형태를 기대함. board.D4는 GPIO4(BCM).
            # 실제 board.D4가 BCM 4와 매핑되는지 확인 필요. 여기서는 BCM 번호를 직접 사용 가능한 방식으로 시도.
            try:
                 # board.D4가 GPIO4(BCM)를 가리킨다고 가정.
                reset_pin_obj = digitalio.DigitalInOut(getattr(board, f"D{OLED_RESET_PIN_BCM}")) 
            except AttributeError:
                logging.warning(f"Board pin D{OLED_RESET_PIN_BCM} not found, attempting direct GPIO for OLED reset. This might not work on all platforms without Blinka explicit setup.")
                # Blinka/board가 BCM 번호를 직접 지원하지 않을 수 있으므로 이 부분은 주의.
                # 일단은 adafruit_blinka.microcontroller.bcm283x.pin.Pin(OLED_RESET_PIN_BCM) 같은 방식이 필요할 수 있으나 복잡함.
                # 가장 간단한 것은 reset_pin_obj를 None으로 두는 것. 많은 모듈이 리셋핀 없이도 잘 동작함.
                reset_pin_obj = None 
                logging.info(f"OLED Reset Pin D{OLED_RESET_PIN_BCM} not used or not found.")

        oled_display = adafruit_ssd1306.SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c, addr=0x3C, reset=reset_pin_obj)
        oled_display.fill(0)
        oled_display.show()
        
        display_image_obj = Image.new("1", (oled_display.width, oled_display.height))
        display_draw_obj = ImageDraw.Draw(display_image_obj)
        
        try:
            loaded_font = ImageFont.truetype("NanumGothicCoding.ttf", 12) # 폰트 크기 12로 수정
        except IOError:
            logging.warning("NanumGothicCoding.ttf not found. Using default font.")
            loaded_font = ImageFont.load_default()
        
        logging.info("OLED display initialized successfully.")
        display_text_on_oled_impl("AI Ready!", max_lines=1, line_height=14) # line_height도 조정
        return True
    except ValueError as e:
        logging.error(f"OLED I2C setup error (ValueError): {e}. Is I2C enabled and address 0x3C correct?")
    except Exception as e:
        logging.error(f"Failed to initialize OLED display: {e}")
    return False

def cleanup_gpio():
    if servo_motor:
        servo_motor.stop()
    GPIO.cleanup()
    # Ensure buzzer PWM is stopped and pin is cleaned up if it was used
    # This might be tricky if PWM object is local to play_melody_impl
    # For simplicity, just ensure the pin is output low.
    # Proper PWM cleanup might need a global PWM object or more careful handling.
    try:
        GPIO.output(BUZZER_PIN, GPIO.LOW) # Ensure buzzer is off
        logging.info("Buzzer pin set to LOW.")
    except RuntimeError as e:
        logging.warning(f"Could not set buzzer pin to LOW during cleanup (possibly already cleaned up or not set up): {e}")
    logging.info("GPIO cleanup finished.")

# --- Gemini API 설정 ---
GEMINI_API_KEY = "YOUR_API_KEY_HERE" # 실제 API 키로 교체!
GEMINI_MODEL_NAME = "gemini-2.0-flash-live-001"
GEMINI_WS_URL_BASE = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"
# -------------------------

# 웹 클라이언트와 Gemini 간 메시지 전달을 위한 큐
web_text_to_gemini_queue = asyncio.Queue() # 텍스트 메시지용
gemini_to_web_queue = asyncio.Queue() # 웹 클라이언트로 보낼 메시지 (텍스트 또는 오디오 정보)

connected_web_clients = set()
gemini_websocket_connection = None

# --- 카메라 설정 ---
picam2 = None
VIDEO_FPS = 1 # 초당 전송할 프레임 수 (조절 가능)
# ------------------

# --- 하드웨어 제어 함수 (구현부) ---
def set_led_state_impl(color: str, state: bool):
    color = color.lower()
    if color not in led_pins:
        logging.warning(f"Unknown LED color: {color}")
        return {"success": False, "message": f"Unknown LED color: {color}"}
    
    pin_to_control = led_pins[color]
    try:
        if state:
            GPIO.output(pin_to_control, GPIO.HIGH)
            msg = f"{color.capitalize()} LED turned on."
        else:
            GPIO.output(pin_to_control, GPIO.LOW)
            msg = f"{color.capitalize()} LED turned off."
        logging.info(msg)
        return {"success": True, "message": msg}
    except Exception as e:
        error_msg = f"Error controlling {color} LED: {e}"
        logging.error(error_msg)
        return {"success": False, "message": error_msg}

def angle_to_duty_cycle(angle):
    """0-180도 각도를 SG90 서보의 듀티 사이클(2.5 ~ 12.5)로 변환합니다."""
    if not (0 <= angle <= 180):
        # logging.warning(f"Servo angle {angle} out of range (0-180). Clamping.")
        angle = max(0, min(180, angle))
    return (angle / 18.0) + 2.5

def set_servo_angle_absolute(target_angle: int):
    global current_servo_angle, servo_motor
    target_angle = int(max(0, min(180, target_angle))) # 0-180도 범위 보장
    
    if not servo_motor:
        logging.error("Servo motor not initialized.")
        return {"success": False, "message": "Servo motor not initialized."}
    try:
        duty_cycle = angle_to_duty_cycle(target_angle)
        servo_motor.ChangeDutyCycle(duty_cycle)
        logging.info(f"Servo moving to {target_angle} degrees (duty cycle: {duty_cycle:.2f})")
        time.sleep(0.3 + abs(target_angle - current_servo_angle) * 0.003) # 각도 변화량에 따라 충분한 시간 부여
        servo_motor.ChangeDutyCycle(0) # 펄스 중지 (지터 방지 및 모터 보호)
        current_servo_angle = target_angle
        msg = f"Servo motor set to {target_angle} degrees."
        logging.info(msg)
        return {"success": True, "message": msg}
    except Exception as e:
        error_msg = f"Error setting servo angle: {e}"
        logging.error(error_msg)
        return {"success": False, "message": error_msg}

def rotate_servo_impl(degrees: int, direction: str = None):
    """서보 모터를 지정된 각도만큼 상대적으로 회전시키거나 절대 각도로 설정합니다."""
    global current_servo_angle
    degrees = int(degrees)

    if direction:
        direction = direction.lower()
        if direction == "clockwise":
            target_angle = current_servo_angle + degrees
        elif direction == "counter_clockwise" or direction == "anticlockwise":
            target_angle = current_servo_angle - degrees
        else:
            return {"success": False, "message": f"Unknown direction: {direction}. Use 'clockwise' or 'counter_clockwise'."}
    else: # direction이 없으면 degrees를 절대 각도로 간주
        target_angle = degrees
        
    return set_servo_angle_absolute(target_angle)

def get_distance_from_obstacle_impl():
    """초음파 센서를 사용하여 거리를 측정하고 cm 단위로 반환합니다."""
    try:
        # Ensure Trig is low for a short period before sending a pulse
        GPIO.output(TRIG_PIN, False)
        time.sleep(0.005) # Settle time before measurement

        GPIO.output(TRIG_PIN, True); time.sleep(0.00001); GPIO.output(TRIG_PIN, False)
        start_t, end_t = time.time(), time.time()
        timeout_s = time.time()
        while GPIO.input(ECHO_PIN) == 0:
            start_t = time.time()
            if start_t - timeout_s > 0.1: # Reduced timeout for faster failure detection
                logging.warning("Ultrasonic timeout (echo HIGH not detected).")
                return {"success": False, "message": "Echo timeout HIGH", "distance_cm": -1}
        timeout_e = time.time()
        while GPIO.input(ECHO_PIN) == 1:
            end_t = time.time()
            if end_t - timeout_e > 0.1: # Reduced timeout
                logging.warning("Ultrasonic timeout (echo LOW not detected).")
                return {"success": False, "message": "Echo timeout LOW", "distance_cm": -1}
        dist = round((end_t - start_t) * 34300 / 2, 2)
        logging.info(f"Distance: {dist} cm.")
        status = "in_range"
        if dist > 400 or dist < 2: status = "out_of_range"
        return {"success": True, "message": f"Obstacle at {dist} cm.", "distance_cm": dist, "unit": "cm", "status": status}
    except Exception as e: return {"success": False, "message": f"Dist err: {e}", "distance_cm": -1}

def display_text_on_oled_impl(text: str, max_lines: int = 4, line_height: int = 14):
    global display_draw_obj, display_image_obj, oled_display, loaded_font
    if not oled_display or not display_draw_obj or not display_image_obj or not loaded_font:
        logging.error("OLED not initialized, cannot display text.")
        return {"success": False, "message": "OLED not initialized."}
    try:
        display_draw_obj.rectangle((0, 0, oled_display.width, oled_display.height), outline=0, fill=0) # Clear
        
        if not text.strip(): # 빈 텍스트면 지워진 화면으로 표시하고 종료
            oled_display.image(display_image_obj)
            oled_display.show()
            logging.info("OLED cleared.")
            return {"success": True, "message": "OLED cleared."}

        words = text.split(' ')
        calculated_lines = [] 
        current_line_for_calc = ""

        for i, word in enumerate(words):
            test_word = word + (" " if i < len(words) -1 else "") # 다음 단어와의 공백 고려
            # 현재 줄에 단어를 추가했을 때 너비를 계산
            potential_line = current_line_for_calc + (" " if current_line_for_calc and word else "") + word

            if hasattr(display_draw_obj, 'textbbox'):
                bbox = display_draw_obj.textbbox((0,0), potential_line, font=loaded_font)
                line_width = bbox[2] - bbox[0]
            else: 
                line_width = display_draw_obj.textlength(potential_line, font=loaded_font)

            if line_width <= oled_display.width:
                current_line_for_calc = potential_line
            else:
                if current_line_for_calc: # 이전까지 완성된 줄 추가
                    calculated_lines.append(current_line_for_calc)
                current_line_for_calc = word # 새 줄은 현재 단어로 시작 (공백 없이)
        
        if current_line_for_calc: # 마지막 줄 추가
            calculated_lines.append(current_line_for_calc)

        # 화면에 표시할 최종 줄 선택 (마지막 max_lines 만큼)
        lines_to_display = calculated_lines[-max_lines:]

        y_text = 0
        for line_content in lines_to_display:
            display_draw_obj.text((0, y_text), line_content.strip(), font=loaded_font, fill=255)
            y_text += line_height 
            if y_text >= oled_display.height: 
                break
        
        oled_display.image(display_image_obj)
        oled_display.show()
        return {"success": True, "message": "Text updated on OLED."}
    except Exception as e: 
        error_msg = f"Error displaying on OLED: {e}"
        logging.error(error_msg)
        return {"success": False, "message": error_msg}

async def setup_camera():
    global picam2
    if picam2 is not None: # 이미 초기화 및 실행 중이면 반환
        try: # 간단한 상태 확인 시도
            picam2.capture_metadata()
            return True
        except Exception:
            logging.warning("Camera was initialized but seems unresponsive. Re-initializing.")
            try:
                picam2.close()
            except Exception:
                pass # 이미 닫혔거나 문제 있는 상태일 수 있음
            picam2 = None

    try:
        logging.info("Initializing camera...")
        picam2 = Picamera2()
        capture_config = picam2.create_still_configuration(main={"size": (640, 480)}) 
        picam2.configure(capture_config)
        picam2.start()
        logging.info("Camera setup successful and started.")
        return True
    except Exception as e:
        logging.error(f"Failed to setup or start camera: {e}")
        if picam2: # 부분적으로라도 초기화 되었다면 close 시도
            try:
                picam2.close()
            except Exception as ce_close:
                logging.error(f"Error closing camera during setup failure: {ce_close}")
        picam2 = None
        return False

async def stream_video_to_gemini():
    global gemini_websocket_connection, picam2
    
    # 앱 시작 시 카메라 설정 시도
    if not await setup_camera():
        logging.error("Initial camera setup failed. Video streaming will not start immediately.")

    while True:
        await asyncio.sleep(1.0 / VIDEO_FPS) 
        
        if picam2 is None or not picam2.started: # 카메라가 없거나 시작되지 않았다면 설정 시도
            logging.warning("Camera not running. Attempting to set up camera for video stream...")
            if not await setup_camera():
                logging.warning("Retrying camera setup in 5 seconds for video stream...")
                await asyncio.sleep(5) 
                continue # 다음 루프에서 다시 시도
        
        if gemini_websocket_connection and gemini_websocket_connection.state == State.OPEN and picam2 and picam2.started:
            try:
                buffer = io.BytesIO()
                picam2.capture_file(buffer, format='jpeg') # 기본 품질 사용
                buffer.seek(0)
                image_bytes = buffer.read()
                
                if not image_bytes:
                    logging.warning("Captured empty image, skipping frame.")
                    continue

                image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                
                gemini_video_input = {
                    "realtimeInput": {
                        "video": {"data": image_base64, "mimeType": "image/jpeg"}
                    }
                }
                await gemini_websocket_connection.send(json.dumps(gemini_video_input))
                logging.debug(f"Sent video frame to Gemini ({len(image_bytes)} bytes).")

            except Exception as e:
                logging.error(f"Error capturing or sending video frame: {e}")
                if isinstance(e, RuntimeError) and ("Camera not running" in str(e) or "No data available" in str(e)):
                    logging.info("Camera seems to have stopped. Attempting to re-initialize camera...")
                    if picam2:
                        try: picam2.close()
                        except Exception: pass
                    picam2 = None # 재설정 강제
                    await asyncio.sleep(1) # 짧은 지연 후 재시도
                else:
                    await asyncio.sleep(2) # 다른 일반적인 오류의 경우 잠시 대기 후 재시도
        else:
            logging.debug("Gemini not connected or camera not ready. Skipping video frame.")
            await asyncio.sleep(1) # 대기

# --- Function Call 스키마 정의 --- (Task 5.1의 결과물, Task 5.3에서 사용됨)
led_tool_schema = {
    "name": "set_led_state",
    "description": "Turns a specific colored LED on or off.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "color": {
                "type": "STRING",
                "description": "The color of the LED to control. Accepted values: 'green', 'yellow', 'red', 'white'." # 흰색 추가
            },
            "state": {
                "type": "BOOLEAN",
                "description": "The desired state of the LED: true for on, false for off."
            }
        },
        "required": ["color", "state"]
    }
}

servo_tool_schema = {
    "name": "rotate_servo",
    "description": "Rotates the servo motor by a specified number of degrees relative to current position or sets it to an absolute angle. Default is absolute if direction is not provided.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "degrees": {
                "type": "INTEGER",
                "description": "The angle in degrees (0-180 for absolute, or relative change)."
            },
            "direction": {
                "type": "STRING",
                "description": "Optional. Direction for relative rotation: 'clockwise' or 'counter_clockwise'. If omitted, 'degrees' is treated as an absolute angle.",
                "nullable": True # 선택적 파라미터 명시 (OpenAPI v3 style)
            }
        },
        "required": ["degrees"]
    }
}

ultrasonic_tool_schema = {
    "name": "get_distance_from_obstacle",
    "description": "Measures the distance to the nearest obstacle in front of the sensor and returns the distance in centimeters.",
    "parameters": { # 파라미터 없음
        "type": "OBJECT",
        "properties": {}
    }
}

oled_tool_schema = {
    "name": "display_on_oled",
    "description": "Displays a given text string on the OLED screen.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "text": {
                "type": "STRING",
                "description": "The text to display on the OLED screen."
            }
            # line_number는 Gemini가 직접 관리하기 어려우므로, 여기서는 text만 받도록 단순화
            # Python 함수 내부에서 자동 줄바꿈 처리
        },
        "required": ["text"]
    }
}

buzzer_tool_schema = {
    "name": "play_melody",
    "description": "Plays a sequence of musical notes on the buzzer. Each note has a frequency and duration.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "notes": {
                "type": "ARRAY",
                "description": "A list of notes to play. Each note is an object with 'frequency' (in Hz) and 'duration' (in milliseconds).",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "frequency": {"type": "INTEGER", "description": "Frequency of the note in Hz (e.g., 262 for Middle C, 440 for A4)."},
                        "duration": {"type": "INTEGER", "description": "Duration of the note in milliseconds."}
                    },
                    "required": ["frequency", "duration"]
                }
            }
        },
        "required": ["notes"]
    }
}

async def gemini_processor():
    global gemini_websocket_connection, accumulated_transcription_for_oled
    if GEMINI_API_KEY == "YOUR_API_KEY_HERE":
        logging.error("Gemini API Key is not set. Please update GEMINI_API_KEY in main.py.")
        await gemini_to_web_queue.put(json.dumps({"type": "status", "message": "Error: Gemini API Key not configured on the server."}))
        return

    uri_with_key = f"{GEMINI_WS_URL_BASE}?key={GEMINI_API_KEY}"
    
    while True: 
        try:
            async with websockets.connect(uri_with_key) as gemini_ws:
                gemini_websocket_connection = gemini_ws 
                logging.info("Successfully connected to Gemini Live API.")

                # Task 5.3: Function Calling 설정 추가
                tools_config = [
                    {"functionDeclarations": [led_tool_schema, servo_tool_schema, ultrasonic_tool_schema, oled_tool_schema, buzzer_tool_schema]},
                    {"googleSearch": {}}
                ]

                setup_message = {
                    "setup": {
                        "model": f"models/{GEMINI_MODEL_NAME}",
                        "generationConfig": {
                            "responseModalities": ["AUDIO"],
                            "speechConfig": {
                                "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Leda"}}
                            }
                        },
                        "outputAudioTranscription": {},
                        "systemInstruction": {
                            "parts": [{"text": "You are a friendly and helpful Raspberry Pi assistant. Answer as succinctly and quickly as possible by only answering what is needed."}]
                        },
                        "tools": tools_config
                    }
                }
                await gemini_ws.send(json.dumps(setup_message))
                logging.info(f"Sent Gemini setup message: {json.dumps(setup_message)}")

                response_raw = await gemini_ws.recv()
                response_data = json.loads(response_raw)
                logging.info(f"Received initial response from Gemini: {response_data}")

                if "setupComplete" not in response_data:
                    error_msg = f"Gemini setup failed: {response_data}"
                    logging.error(error_msg)
                    await gemini_to_web_queue.put(json.dumps({"type": "status", "message": f"Error: {error_msg}"}))
                    gemini_websocket_connection = None 
                    await asyncio.sleep(5) 
                    continue 

                logging.info("Gemini session setup complete.")
                await gemini_to_web_queue.put(json.dumps({"type": "status", "message": "[Gemini session ready]"}))

                accumulated_transcription_for_oled = "" # 새 세션 시작 시 트랜스크립션 초기화

                async def forward_text_to_gemini():
                    while True:
                        if not gemini_websocket_connection: break
                        try:
                            message_from_web = await web_text_to_gemini_queue.get()
                            if gemini_websocket_connection and gemini_websocket_connection.state == State.OPEN:
                                logging.info(f"Relaying TEXT from web client to Gemini: {message_from_web}")
                                gemini_client_content = {
                                    "clientContent": {
                                        "turns": [{"role": "user", "parts": [{"text": str(message_from_web)}]}],
                                        "turnComplete": True
                                    }
                                }
                                await gemini_websocket_connection.send(json.dumps(gemini_client_content))
                            else:
                                logging.warning("Gemini connection closed. Cannot send text.")
                                web_text_to_gemini_queue.put_nowait(message_from_web) 
                                break
                        except websockets.exceptions.ConnectionClosed:
                            logging.warning("Connection to Gemini closed (forward_text_to_gemini).")
                            if 'message_from_web' in locals(): web_text_to_gemini_queue.put_nowait(message_from_web) 
                            break
                        except Exception as e_fwd:
                            logging.error(f"Error in forward_text_to_gemini: {e_fwd}")
                        finally:
                             if 'message_from_web' in locals() and web_text_to_gemini_queue.empty() is False : 
                                web_text_to_gemini_queue.task_done()


                async def receive_from_gemini():
                    global accumulated_transcription_for_oled
                    while True:
                        if not gemini_websocket_connection: break
                        try:
                            message_from_gemini_raw = await gemini_websocket_connection.recv()
                            logging.debug(f"Raw from Gemini: {message_from_gemini_raw[:200]}") # Debugging
                            message_data = json.loads(message_from_gemini_raw)
                            
                            message_for_web = None

                            if "serverContent" in message_data:
                                server_content = message_data["serverContent"]
                                
                                # 오디오 데이터 처리
                                if "modelTurn" in server_content and server_content["modelTurn"].get("parts"):
                                    for part in server_content["modelTurn"]["parts"]:
                                        if "inlineData" in part and part["inlineData"].get("mimeType", "").startswith("audio/pcm"):
                                            audio_base64 = part["inlineData"]["data"]
                                            logging.info(f"Received AUDIO data from Gemini (approx {len(audio_base64)*3/4} bytes of PCM).")
                                            message_for_web = {"type": "audio_data", "payload": audio_base64}
                                    # 오디오와 함께 트랜스크립션이 올 수도 있으므로, 계속 다른 part도 확인
                                
                                # 텍스트 트랜스크립션 처리 (outputAudioTranscription)
                                if "outputTranscription" in server_content and server_content["outputTranscription"].get("text"):
                                    transcript_part = server_content["outputTranscription"]["text"]
                                    
                                    # turnComplete이 있거나 새로운 응답이 시작될 때 이전 텍스트 초기화
                                    if server_content.get("turnComplete") or (transcript_part.strip() and len(accumulated_transcription_for_oled) > 200):
                                        accumulated_transcription_for_oled = ""
                                    
                                    accumulated_transcription_for_oled += transcript_part
                                    logging.info(f"Received Output Transcription: {transcript_part}")
                                    # 실시간 트랜스크립션 청크를 OLED에 바로 표시
                                    display_text_on_oled_impl(accumulated_transcription_for_oled, line_height=14)
                                    
                                    # 웹 클라이언트에게도 트랜스크립션 조각 전송 (선택적)
                                    if message_for_web is None: # 오디오 데이터가 없는 경우 (예: 텍스트 응답만)
                                         message_for_web = {"type": "status", "message": f"[T]: {transcript_part}"}
                                    else: # 오디오 데이터가 이미 있다면, 트랜스크립션은 별도 메시지로.
                                        await gemini_to_web_queue.put(json.dumps({"type": "status", "message": f"[T]: {transcript_part}"}))


                                # 텍스트 응답 (예: responseModalities가 TEXT일 때 또는 오류 메시지)
                                # modelTurn.parts에 text가 있는 경우도 고려 (audio와 함께 올 수 있음)
                                if "modelTurn" in server_content and server_content["modelTurn"].get("parts"):
                                    text_response_part = ""
                                    for part in server_content["modelTurn"]["parts"]:
                                        if "text" in part: # 오디오 외의 텍스트 파트 (거의 없을 것으로 예상되나 방어 코드)
                                            text_response_part += part["text"] + " "
                                    if text_response_part.strip() and message_for_web is None: # 오디오 데이터가 없고 텍스트만 있다면
                                        logging.info(f"Received TEXT response from Gemini: {text_response_part.strip()}")
                                        message_for_web = {"type": "status", "message": text_response_part.strip()}
                                    elif text_response_part.strip(): # 오디오도 있고 텍스트도 있다면 (거의 없을 상황)
                                        await gemini_to_web_queue.put(json.dumps({"type": "status", "message": text_response_part.strip()}))


                                if "interrupted" in server_content and server_content["interrupted"]:
                                    logging.info("Gemini: Interrupted by new input")
                                    if message_for_web is None: message_for_web = {"type": "status", "message": "[Gemini: Interrupted]"}
                                
                                if "turnComplete" in server_content and server_content["turnComplete"]:
                                    logging.info("Gemini: Turn complete.")
                                    # 턴 완료 메시지는 별도로 보내거나, 마지막 데이터에 포함시킬 수 있음
                                    # 여기서는 별도 상태 메시지로 전송하지 않음 (오디오 스트림의 끝으로 간주)

                            elif "toolCall" in message_data:
                                tool_call_data = message_data["toolCall"]
                                logging.info(f"Received Tool Call from Gemini: {tool_call_data}")
                                
                                function_responses = [] # 여러 함수 호출에 대한 응답 리스트
                                
                                if "functionCalls" in tool_call_data:
                                    for fc in tool_call_data["functionCalls"]:
                                        fc_name = fc.get("name")
                                        fc_args = fc.get("args")
                                        fc_id = fc.get("id") # 중요: 응답 시 이 ID 사용
                                        
                                        tool_call_result = None
                                        if fc_name == "set_led_state":
                                            color = fc_args.get("color")
                                            state = fc_args.get("state")
                                            if color is not None and state is not None:
                                                logging.info(f"Executing tool call: set_led_state(color='{color}', state={state})")
                                                tool_call_result = set_led_state_impl(color, state)
                                            else:
                                                tool_call_result = {"success": False, "message": "Missing color or state argument for set_led_state."}
                                        elif fc_name == "rotate_servo": # 서보 모터 함수 호출 처리
                                            degrees = fc_args.get("degrees")
                                            direction = fc_args.get("direction") # 선택적
                                            if degrees is not None:
                                                logging.info(f"Executing tool call: rotate_servo(degrees={degrees}, direction='{direction}')")
                                                tool_call_result = rotate_servo_impl(degrees, direction)
                                            else:
                                                tool_call_result = {"success": False, "message": "Missing degrees argument for rotate_servo."}
                                        elif fc_name == "get_distance_from_obstacle": # 초음파 센서 함수 호출
                                            logging.info("Executing tool call: get_distance_from_obstacle()")
                                            tool_call_result = get_distance_from_obstacle_impl()
                                        elif fc_name == "display_on_oled": # OLED 함수 호출 처리
                                            text_to_display = fc_args.get("text")
                                            if text_to_display is not None:
                                                logging.info(f"Executing tool: display_on_oled(text='{text_to_display[:20]}...')")
                                                tool_call_result = display_text_on_oled_impl(text_to_display, line_height=14)
                                            else:
                                                tool_call_result = {"success": False, "message": "Missing text for OLED."}
                                        elif fc_name == "play_melody":
                                            notes_to_play = fc_args.get("notes", [])
                                            tool_call_result = play_melody_impl(notes_to_play)
                                        else:
                                            logging.warning(f"Unknown function call name: {fc_name}")
                                            tool_call_result = {"success": False, "message": f"Unknown function: {fc_name}"}
                                        
                                        if tool_call_result and fc_id:
                                            function_responses.append({
                                                "id": fc_id,
                                                "name": fc_name,
                                                "response": {"output": tool_call_result} # Gemini는 'output' 필드 안에 결과를 기대
                                            })
                                
                                # Task 5.5: Send Tool Responses
                                if function_responses:
                                    tool_response_message = {
                                        "toolResponse": {
                                            "functionResponses": function_responses
                                        }
                                    }
                                    if gemini_websocket_connection and gemini_websocket_connection.state == State.OPEN:
                                        await gemini_websocket_connection.send(json.dumps(tool_response_message))
                                        logging.info(f"Sent tool responses to Gemini: {json.dumps(tool_response_message)}")
                                    else:
                                        logging.warning("Gemini connection closed. Cannot send tool responses.")
                                # Tool call에 대한 직접적인 사용자 응답은 보통 없음 (Gemini가 결과를 바탕으로 다시 말함)
                                # message_for_web = {"type": "status", "message": f"[Executed tool call(s)]"}

                            elif "goAway" in message_data:
                                logging.warning(f"Gemini server sent GoAway: {message_data['goAway']}")
                                message_for_web = {"type": "status", "message": "[Gemini session ending]"}
                                break 
                            else: # 기타 Gemini 메시지
                                logging.info(f"Received unhandled message structure from Gemini: {message_from_gemini_raw[:200]}...")
                                # message_for_web = {"type": "status", "message": "[Gemini: Unhandled message structure]"}


                            if message_for_web:
                                await gemini_to_web_queue.put(json.dumps(message_for_web))

                        except websockets.exceptions.ConnectionClosed:
                            logging.warning("Connection to Gemini closed (receive_from_gemini).")
                            break 
                        except json.JSONDecodeError:
                            logging.error(f"Failed to decode JSON from Gemini: {message_from_gemini_raw[:500]}")
                        except Exception as e_recv:
                            logging.error(f"Error in receive_from_gemini: {e_recv}")
                
                await asyncio.gather(
                    forward_text_to_gemini(),
                    receive_from_gemini()
                )

        except (websockets.exceptions.WebSocketException, ConnectionRefusedError, OSError) as e:
            logging.error(f"Gemini connection/setup error: {e}. Retrying in 5 seconds...")
        except Exception as e_outer:
            logging.error(f"Unexpected error in gemini_processor outer loop: {e_outer}. Retrying in 5 seconds...")
        finally:
            gemini_websocket_connection = None 
            logging.info("Gemini processor attempting to reconnect or has finished a cycle.")
            await gemini_to_web_queue.put(json.dumps({"type": "status", "message": "[Error: Disconnected from Gemini. Attempting to reconnect...]"}),)
            await asyncio.sleep(5) 


async def rpi_websocket_handler(websocket, path=None):
    global gemini_websocket_connection
    logging.info(f"Web client connected: {websocket.remote_address}")
    connected_web_clients.add(websocket)
    try:
        async for message_from_web in websocket:
            if isinstance(message_from_web, str): 
                try:
                    data = json.loads(message_from_web)
                    if data.get("type") == "audio_stream_end":
                        logging.info(f"Received audio_stream_end signal from {websocket.remote_address}")
                        if gemini_websocket_connection and gemini_websocket_connection.state == State.OPEN:
                            end_signal_message = {"realtimeInput": {"audioStreamEnd": True}}
                            await gemini_websocket_connection.send(json.dumps(end_signal_message))
                            logging.info("Sent audioStreamEnd:true to Gemini.")
                        # continue # audio_stream_end는 턴을 종료시키므로, 추가 텍스트 입력이 없으면 여기서 끝.
                    else: # 기타 JSON (향후 확장용) 또는 알 수 없는 JSON
                        logging.info(f"Received JSON from web client {websocket.remote_address}: {message_from_web}")
                        # 일반 텍스트처럼 Gemini로 보낼지 여부 결정. 지금은 로깅만.
                except json.JSONDecodeError:
                    # JSON 파싱 실패 시 일반 텍스트 메시지로 간주
                    logging.info(f"Received TEXT from web client {websocket.remote_address}: {message_from_web}")
                    await web_text_to_gemini_queue.put(message_from_web)
                
            elif isinstance(message_from_web, bytes): 
                logging.info(f"Received AUDIO ({len(message_from_web)} bytes) from web client {websocket.remote_address}")
                if gemini_websocket_connection and gemini_websocket_connection.state == State.OPEN:
                    try:
                        audio_base64 = base64.b64encode(message_from_web).decode('utf-8')
                        gemini_realtime_input = {
                            "realtimeInput": {
                                "audio": {"data": audio_base64, "mimeType": "audio/pcm;rate=16000"}
                            }
                        }
                        await gemini_websocket_connection.send(json.dumps(gemini_realtime_input))
                        # logging.info("Sent audio chunk to Gemini.") # 너무 자주 로깅되므로 DEBUG 레벨로 변경 또는 주석 처리
                        logging.debug("Sent audio chunk to Gemini.")
                    except websockets.exceptions.ConnectionClosed:
                        logging.warning("Gemini connection closed. Cannot send audio.")
                    except Exception as e_audio_send:
                        logging.error(f"Error sending audio to Gemini: {e_audio_send}")
                else:
                    logging.warning("Gemini not connected. Cannot send audio.")
            else:
                logging.warning(f"Received unknown message type from {websocket.remote_address}")

    except websockets.exceptions.ConnectionClosedOK:
        logging.info(f"Web client {websocket.remote_address} disconnected normally.")
    except websockets.exceptions.ConnectionClosedError as e:
        logging.error(f"Web client {websocket.remote_address} connection closed with error: {e}")
    except Exception as e:
        logging.error(f"An error with web client {websocket.remote_address}: {e}")
    finally:
        logging.info(f"Web client connection handler for {websocket.remote_address} finished.")
        connected_web_clients.remove(websocket)


async def broadcast_gemini_responses():
    while True:
        message_to_broadcast_json = await gemini_to_web_queue.get()
        active_clients = list(connected_web_clients) 
        if active_clients:
            results = await asyncio.gather(
                *[client_ws.send(message_to_broadcast_json) for client_ws in active_clients], # JSON 문자열 그대로 전송
                return_exceptions=True
            )
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logging.error(f"Error sending to client {active_clients[i].remote_address}: {result}")
        gemini_to_web_queue.task_done()


async def start_main_server():
    server_host = "0.0.0.0"
    server_port = 8765
    logging.info(f"Starting RPi WebSocket server on ws://{server_host}:{server_port}")

    setup_gpio() # GPIO 초기화 호출
    if not setup_oled(): # OLED 설정 시도
        logging.warning("OLED setup failed. Text display on OLED will not be available.")
        # OLED 실패 시에도 프로그램은 계속 실행되도록 처리

    asyncio.create_task(gemini_processor())
    asyncio.create_task(broadcast_gemini_responses())
    asyncio.create_task(stream_video_to_gemini()) # 비디오 스트리밍 태스크 추가

    async with websockets.serve(rpi_websocket_handler, server_host, server_port):
        await asyncio.Future()  

def play_melody_impl(notes):
    """
    Plays a sequence of notes on the buzzer.
    Each note in the 'notes' list should be a dictionary: {'frequency': hz, 'duration': ms}
    """
    try:
        logging.info(f"Playing melody: {notes}")
        
        # Create PWM object once and reuse it
        pwm_buzzer = GPIO.PWM(BUZZER_PIN, 100)  # Start with 100Hz, will change frequency for each note
        pwm_buzzer.start(10)  # Start with 10% duty cycle (like the example)
        
        for note in notes:
            frequency = note.get("frequency")
            duration_ms = note.get("duration")
            if frequency is None or duration_ms is None or frequency <= 0 or duration_ms <= 0:
                logging.warning(f"Skipping invalid note: {note}")
                continue

            # Min duration to prevent issues, min frequency for typical buzzers
            if duration_ms < 10: 
                duration_ms = 10
            if frequency < 20: 
                frequency = 20  # Avoid very low frequencies

            try:
                # Change frequency for this note (like the example code)
                pwm_buzzer.ChangeFrequency(frequency)
                time.sleep(duration_ms / 1000.0)
                time.sleep(0.05)  # Short pause between notes
            except Exception as e:
                logging.error(f"Error playing note {frequency}Hz for {duration_ms}ms: {e}")
        
        pwm_buzzer.stop()  # Stop PWM after all notes
        logging.info("Melody playback finished.")
        return {"status": "success", "message": "Melody played."}
    except Exception as e:
        logging.error(f"Error in play_melody_impl: {e}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    try:
        # 로깅 레벨을 DEBUG로 설정하여 더 자세한 정보 확인 (필요시)
        # logging.getLogger().setLevel(logging.DEBUG) 
        asyncio.run(start_main_server())
    except KeyboardInterrupt:
        logging.info("Main server shutting down.")
    except Exception as e:
        logging.error(f"Failed to start main server: {e}")
    finally:
        if oled_display: # OLED 화면 정리
            try:
                display_draw_obj.rectangle((0,0,OLED_WIDTH,OLED_HEIGHT), outline=0, fill=0)
                oled_display.show()
            except Exception as e_oled_clean:
                logging.error(f"Error clearing OLED on exit: {e_oled_clean}")
        cleanup_gpio() # 프로그램 종료 시 GPIO 정리
        logging.info("GPIO cleanup finished. Exiting.")