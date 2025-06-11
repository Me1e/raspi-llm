#!/usr/bin/env python3

import asyncio
import websockets
import logging
import json
import base64
from websockets.connection import State
from picamera2 import Picamera2
import io
import time
import RPi.GPIO as GPIO

import board
import busio
import digitalio
from PIL import Image, ImageDraw, ImageFont
import adafruit_ssd1306

logging.basicConfig(level=logging.INFO)
logging.info(f"Using websockets library version: {websockets.__version__}")

# GPIO pin assignments
GREEN_LED_PIN = 17 
YELLOW_LED_PIN = 27
RED_LED_PIN = 22
WHITE_LED_PIN = 10
SERVO_PIN = 18
TRIG_PIN = 23
ECHO_PIN = 24
BUZZER_PIN = 9

# OLED configuration
OLED_WIDTH = 128
OLED_HEIGHT = 64
OLED_RESET_PIN_BCM = 4

led_pins = {
    "green": GREEN_LED_PIN,
    "yellow": YELLOW_LED_PIN,
    "red": RED_LED_PIN,
    "white": WHITE_LED_PIN
}

servo_motor = None
current_servo_angle = 90
oled_display = None
display_draw_obj = None
display_image_obj = None
loaded_font = None

user_audio_session_active = False

def setup_gpio():
    global servo_motor, current_servo_angle
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    for pin in led_pins.values():
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)
    
    GPIO.setup(SERVO_PIN, GPIO.OUT)
    servo_motor = GPIO.PWM(SERVO_PIN, 50)
    servo_motor.start(0)
    current_servo_angle = 90
    set_servo_angle_absolute(current_servo_angle)

    GPIO.setup(TRIG_PIN, GPIO.OUT)
    GPIO.setup(ECHO_PIN, GPIO.IN)
    GPIO.output(TRIG_PIN, False)

    GPIO.setup(BUZZER_PIN, GPIO.OUT)
    GPIO.output(BUZZER_PIN, GPIO.LOW)

    logging.info("GPIO setup complete for LEDs, Servo, and Ultrasonic sensor.")
    logging.info("Waiting for ultrasonic sensor to settle...")
    time.sleep(2)
    logging.info("Ultrasonic sensor settled.")

def setup_oled():
    global oled_display, display_draw_obj, display_image_obj, loaded_font
    try:
        logging.info("Initializing OLED display...")
        i2c = board.I2C()
        reset_pin_obj = None
        if OLED_RESET_PIN_BCM is not None:
            try:
                reset_pin_obj = digitalio.DigitalInOut(getattr(board, f"D{OLED_RESET_PIN_BCM}")) 
            except AttributeError:
                logging.warning(f"Board pin D{OLED_RESET_PIN_BCM} not found, attempting direct GPIO for OLED reset. This might not work on all platforms without Blinka explicit setup.")
                reset_pin_obj = None 
                logging.info(f"OLED Reset Pin D{OLED_RESET_PIN_BCM} not used or not found.")

        oled_display = adafruit_ssd1306.SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c, addr=0x3C, reset=reset_pin_obj)
        oled_display.fill(0)
        oled_display.show()
        
        display_image_obj = Image.new("1", (oled_display.width, oled_display.height))
        display_draw_obj = ImageDraw.Draw(display_image_obj)
        
        try:
            loaded_font = ImageFont.truetype("NanumGothicCoding.ttf", 12)
        except IOError:
            logging.warning("NanumGothicCoding.ttf not found. Using default font.")
            loaded_font = ImageFont.load_default()
        
        logging.info("OLED display initialized successfully.")
        display_text_on_oled_impl("AI Ready!", max_lines=1, line_height=14)
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
    try:
        GPIO.output(BUZZER_PIN, GPIO.LOW)
        logging.info("Buzzer pin set to LOW.")
    except RuntimeError as e:
        logging.warning(f"Could not set buzzer pin to LOW during cleanup (possibly already cleaned up or not set up): {e}")
    logging.info("GPIO cleanup finished.")

# Gemini API configuration
GEMINI_API_KEY = "YOUR_API_KEY_HERE"
GEMINI_MODEL_NAME = "gemini-2.0-flash-live-001"
GEMINI_WS_URL_BASE = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"

# Message queues
web_text_to_gemini_queue = asyncio.Queue()
gemini_to_web_queue = asyncio.Queue()

connected_web_clients = set()
gemini_websocket_connection = None

# Camera configuration
picam2 = None
VIDEO_FPS = 1

# Hardware control implementations
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
    """Convert 0-180 degree angle to SG90 servo duty cycle (2.5 ~ 12.5)."""
    if not (0 <= angle <= 180):
        angle = max(0, min(180, angle))
    return (angle / 18.0) + 2.5

def set_servo_angle_absolute(target_angle: int):
    global current_servo_angle, servo_motor
    target_angle = int(max(0, min(180, target_angle)))
    
    if not servo_motor:
        logging.error("Servo motor not initialized.")
        return {"success": False, "message": "Servo motor not initialized."}
    try:
        duty_cycle = angle_to_duty_cycle(target_angle)
        servo_motor.ChangeDutyCycle(duty_cycle)
        logging.info(f"Servo moving to {target_angle} degrees (duty cycle: {duty_cycle:.2f})")
        time.sleep(0.3 + abs(target_angle - current_servo_angle) * 0.003)
        servo_motor.ChangeDutyCycle(0)
        current_servo_angle = target_angle
        msg = f"Servo motor set to {target_angle} degrees."
        logging.info(msg)
        return {"success": True, "message": msg}
    except Exception as e:
        error_msg = f"Error setting servo angle: {e}"
        logging.error(error_msg)
        return {"success": False, "message": error_msg}

def rotate_servo_impl(degrees: int, direction: str = None):
    """Rotate servo motor by specified degrees relative or set absolute angle."""
    global current_servo_angle
    degrees = int(degrees)

    if direction:
        direction = direction.lower()
        if direction == "clockwise":
            target_angle = current_servo_angle - degrees
        elif direction == "counter_clockwise" or direction == "anticlockwise":
            target_angle = current_servo_angle + degrees
        else:
            return {"success": False, "message": f"Unknown direction: {direction}. Use 'clockwise' or 'counter_clockwise'."}
    else:
        target_angle = degrees
        
    return set_servo_angle_absolute(target_angle)

def get_distance_from_obstacle_impl():
    """Measure distance using ultrasonic sensor and return in cm."""
    try:
        GPIO.output(TRIG_PIN, False)
        time.sleep(0.005)

        GPIO.output(TRIG_PIN, True); time.sleep(0.00001); GPIO.output(TRIG_PIN, False)
        start_t, end_t = time.time(), time.time()
        timeout_s = time.time()
        while GPIO.input(ECHO_PIN) == 0:
            start_t = time.time()
            if start_t - timeout_s > 0.1:
                logging.warning("Ultrasonic timeout (echo HIGH not detected).")
                return {"success": False, "message": "Echo timeout HIGH", "distance_cm": -1}
        timeout_e = time.time()
        while GPIO.input(ECHO_PIN) == 1:
            end_t = time.time()
            if end_t - timeout_e > 0.1:
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
        display_draw_obj.rectangle((0, 0, oled_display.width, oled_display.height), outline=0, fill=0)
        
        if not text.strip():
            oled_display.image(display_image_obj)
            oled_display.show()
            logging.info("OLED cleared.")
            return {"success": True, "message": "OLED cleared."}

        words = text.split(' ')
        calculated_lines = [] 
        current_line_for_calc = ""

        for i, word in enumerate(words):
            test_word = word + (" " if i < len(words) -1 else "")
            potential_line = current_line_for_calc + (" " if current_line_for_calc and word else "") + word

            if hasattr(display_draw_obj, 'textbbox'):
                bbox = display_draw_obj.textbbox((0,0), potential_line, font=loaded_font)
                line_width = bbox[2] - bbox[0]
            else: 
                line_width = display_draw_obj.textlength(potential_line, font=loaded_font)

            if line_width <= oled_display.width:
                current_line_for_calc = potential_line
            else:
                if current_line_for_calc:
                    calculated_lines.append(current_line_for_calc)
                current_line_for_calc = word
        
        if current_line_for_calc:
            calculated_lines.append(current_line_for_calc)

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
    if picam2 is not None:
        try:
            picam2.capture_metadata()
            return True
        except Exception:
            logging.warning("Camera was initialized but seems unresponsive. Re-initializing.")
            try:
                picam2.close()
            except Exception:
                pass
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
        if picam2:
            try:
                picam2.close()
            except Exception as ce_close:
                logging.error(f"Error closing camera during setup failure: {ce_close}")
        picam2 = None
        return False

async def stream_video_to_gemini():
    global gemini_websocket_connection, picam2
    
    if not await setup_camera():
        logging.error("Initial camera setup failed. Video streaming will not start immediately.")

    while True:
        await asyncio.sleep(1.0 / VIDEO_FPS) 
        
        if picam2 is None or not picam2.started:
            logging.warning("Camera not running. Attempting to set up camera for video stream...")
            if not await setup_camera():
                logging.warning("Retrying camera setup in 5 seconds for video stream...")
                await asyncio.sleep(5) 
                continue
        
        if gemini_websocket_connection and gemini_websocket_connection.state == State.OPEN and picam2 and picam2.started:
            try:
                buffer = io.BytesIO()
                picam2.capture_file(buffer, format='jpeg')
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
                    picam2 = None
                    await asyncio.sleep(1)
                else:
                    await asyncio.sleep(2)
        else:
            logging.debug("Gemini not connected or camera not ready. Skipping video frame.")
            await asyncio.sleep(1)

# Predefined melody library
PREDEFINED_MELODIES = {
    "twinkle_star": {
        "name": "Twinkle Twinkle Little Star",
        "notes": [
            {"frequency": 523, "duration": 400},
            {"frequency": 523, "duration": 400},
            {"frequency": 784, "duration": 400},
            {"frequency": 784, "duration": 400},
            {"frequency": 880, "duration": 400},
            {"frequency": 880, "duration": 400},
            {"frequency": 784, "duration": 800},
            {"frequency": 698, "duration": 400},
            {"frequency": 698, "duration": 400},
            {"frequency": 659, "duration": 400},
            {"frequency": 659, "duration": 400},
            {"frequency": 587, "duration": 400},
            {"frequency": 587, "duration": 400},
            {"frequency": 523, "duration": 800},
        ]
    },
    "happy_birthday": {
        "name": "Happy Birthday",
        "notes": [
            {"frequency": 523, "duration": 300},
            {"frequency": 523, "duration": 300},
            {"frequency": 587, "duration": 600},
            {"frequency": 523, "duration": 600},
            {"frequency": 698, "duration": 600},
            {"frequency": 659, "duration": 1200},
            {"frequency": 523, "duration": 300},
            {"frequency": 523, "duration": 300},
            {"frequency": 587, "duration": 600},
            {"frequency": 523, "duration": 600},
            {"frequency": 784, "duration": 600},
            {"frequency": 698, "duration": 1200},
        ]
    },
    "mary_lamb": {
        "name": "Mary Had a Little Lamb",
        "notes": [
            {"frequency": 659, "duration": 400},
            {"frequency": 587, "duration": 400},
            {"frequency": 523, "duration": 400},
            {"frequency": 587, "duration": 400},
            {"frequency": 659, "duration": 400},
            {"frequency": 659, "duration": 400},
            {"frequency": 659, "duration": 800},
            {"frequency": 587, "duration": 400},
            {"frequency": 587, "duration": 400},
            {"frequency": 587, "duration": 800},
            {"frequency": 659, "duration": 400},
            {"frequency": 784, "duration": 400},
            {"frequency": 784, "duration": 800},
        ]
    },
    "ode_to_joy": {
        "name": "Ode to Joy (Beethoven)",
        "notes": [
            {"frequency": 659, "duration": 400},
            {"frequency": 659, "duration": 400},
            {"frequency": 698, "duration": 400},
            {"frequency": 784, "duration": 400},
            {"frequency": 784, "duration": 400},
            {"frequency": 698, "duration": 400},
            {"frequency": 659, "duration": 400},
            {"frequency": 587, "duration": 400},
            {"frequency": 523, "duration": 400},
            {"frequency": 523, "duration": 400},
            {"frequency": 587, "duration": 400},
            {"frequency": 659, "duration": 400},
            {"frequency": 659, "duration": 600},
            {"frequency": 587, "duration": 200},
            {"frequency": 587, "duration": 800},
        ]
    },
    "fur_elise": {
        "name": "Für Elise (Beethoven)",
        "notes": [
            {"frequency": 659, "duration": 300},
            {"frequency": 622, "duration": 300},
            {"frequency": 659, "duration": 300},
            {"frequency": 622, "duration": 300},
            {"frequency": 659, "duration": 300},
            {"frequency": 494, "duration": 300},
            {"frequency": 587, "duration": 300},
            {"frequency": 523, "duration": 300},
            {"frequency": 440, "duration": 600},
            {"frequency": 262, "duration": 300},
            {"frequency": 330, "duration": 300},
            {"frequency": 440, "duration": 300},
            {"frequency": 494, "duration": 600},
        ]
    },
    "canon": {
        "name": "Canon in D (Pachelbel)",
        "notes": [
            {"frequency": 587, "duration": 800},
            {"frequency": 440, "duration": 800},
            {"frequency": 494, "duration": 800},
            {"frequency": 370, "duration": 800},
            {"frequency": 392, "duration": 800},
            {"frequency": 587, "duration": 800},
            {"frequency": 392, "duration": 800},
            {"frequency": 440, "duration": 800},
            {"frequency": 587, "duration": 400},
            {"frequency": 523, "duration": 400},
            {"frequency": 587, "duration": 400},
            {"frequency": 440, "duration": 400},
            {"frequency": 494, "duration": 400},
            {"frequency": 370, "duration": 400},
            {"frequency": 392, "duration": 400},
            {"frequency": 440, "duration": 400},
        ]
    }
}

def get_predefined_melody(melody_name: str):
    """Get predefined melody."""
    melody_name = melody_name.lower().replace(" ", "_").replace("-", "_")
    return PREDEFINED_MELODIES.get(melody_name)

def list_available_melodies():
    """Return list of available melodies."""
    return {key: value["name"] for key, value in PREDEFINED_MELODIES.items()}

# Function call schema definitions
led_tool_schema = {
    "name": "set_led_state",
    "description": "Turns a specific colored LED on or off.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "color": {
                "type": "STRING",
                "description": "The color of the LED to control. Accepted values: 'green', 'yellow', 'red', 'white'."
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
                "nullable": True
            }
        },
        "required": ["degrees"]
    }
}

ultrasonic_tool_schema = {
    "name": "get_distance_from_obstacle",
    "description": "Measures the distance to the nearest obstacle in front of the sensor and returns the distance in centimeters.",
    "parameters": {
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

# Predefined melody playback schema
predefined_melody_tool_schema = {
    "name": "play_predefined_melody",
    "description": "Plays a well-known, beautiful melody from a predefined collection. Use this for requests like 'play beautiful music', 'play a famous song', or when user wants high-quality melodies.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "melody_name": {
                "type": "STRING",
                "description": "Name of the predefined melody to play. Available options: 'twinkle_star' (Twinkle Twinkle Little Star), 'happy_birthday' (Happy Birthday), 'mary_lamb' (Mary Had a Little Lamb), 'ode_to_joy' (Ode to Joy by Beethoven), 'fur_elise' (Für Elise by Beethoven), 'canon' (Canon in D by Pachelbel)"
            }
        },
        "required": ["melody_name"]
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

                # Function calling configuration
                tools_config = [
                    {"functionDeclarations": [led_tool_schema, servo_tool_schema, ultrasonic_tool_schema, oled_tool_schema, buzzer_tool_schema, predefined_melody_tool_schema]},
                    {"googleSearch": {}}
                ]

                setup_message = {
                    "setup": {
                        "model": f"models/{GEMINI_MODEL_NAME}",
                        "generationConfig": {
                            "responseModalities": ["AUDIO"],
                        },
                        "outputAudioTranscription": {},
                        "systemInstruction": {
                            "parts": [{"text": "당신은 라즈베리파이 어시스턴트입니다. 무조건 한국어로만 답변하세요. 최대한 짧고 간결하게 답변하세요. 숫자, 거리, 각도 등은 모두 한글로 읽으세요. 예: '46cm'는 '사십육 센티미터', '90도'는 '구십도', '3.5초'는 '삼점오 초'로 말하세요."}]
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

                accumulated_transcription_for_oled = ""

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
                            logging.debug(f"Raw from Gemini: {message_from_gemini_raw[:200]}")
                            message_data = json.loads(message_from_gemini_raw)
                            
                            message_for_web = None

                            if "serverContent" in message_data:
                                server_content = message_data["serverContent"]
                                
                                # Audio data processing
                                if "modelTurn" in server_content and server_content["modelTurn"].get("parts"):
                                    for part in server_content["modelTurn"]["parts"]:
                                        if "inlineData" in part and part["inlineData"].get("mimeType", "").startswith("audio/pcm"):
                                            audio_base64 = part["inlineData"]["data"]
                                            logging.info(f"[{time.time():.3f}] AUDIO CHUNK: Received from Gemini (approx {len(audio_base64)*3/4} bytes of PCM). Sending to web immediately.")
                                            message_for_web = {"type": "audio_data", "payload": audio_base64}
                                
                                # Text transcription processing
                                transcription_message = None
                                if "outputTranscription" in server_content and server_content["outputTranscription"].get("text"):
                                    transcript_part = server_content["outputTranscription"]["text"]
                                    
                                    if server_content.get("turnComplete") or len(accumulated_transcription_for_oled) > 200:
                                        accumulated_transcription_for_oled = ""
                                    
                                    accumulated_transcription_for_oled += transcript_part
                                    logging.info(f"[{time.time():.3f}] TRANSCRIPTION: {transcript_part}")
                                    
                                    if message_for_web is None:
                                         message_for_web = {"type": "status", "message": f"[T]: {transcript_part}"}
                                    else:
                                        transcription_message = {"type": "status", "message": f"[T]: {transcript_part}"}

                                    asyncio.create_task(asyncio.to_thread(display_text_on_oled_impl, accumulated_transcription_for_oled, 4, 14))

                                # Text response processing
                                if "modelTurn" in server_content and server_content["modelTurn"].get("parts"):
                                    text_response_part = ""
                                    for part in server_content["modelTurn"]["parts"]:
                                        if "text" in part:
                                            text_response_part += part["text"] + " "
                                    if text_response_part.strip() and message_for_web is None:
                                        logging.info(f"Received TEXT response from Gemini: {text_response_part.strip()}")
                                        message_for_web = {"type": "status", "message": text_response_part.strip()}
                                    elif text_response_part.strip():
                                        await gemini_to_web_queue.put(json.dumps({"type": "status", "message": text_response_part.strip()}))

                                if "interrupted" in server_content and server_content["interrupted"]:
                                    logging.info("Gemini: Interrupted by new input")
                                    interrupt_message = {"type": "clear_audio_buffer", "message": "[Gemini: Interrupted]"}
                                    await gemini_to_web_queue.put(json.dumps(interrupt_message))
                                    if message_for_web is None: message_for_web = {"type": "status", "message": "[Gemini: Interrupted]"}
                                
                                if "turnComplete" in server_content and server_content["turnComplete"]:
                                    global user_audio_session_active
                                    logging.info("Gemini: Turn complete.")
                                    user_audio_session_active = False

                            elif "toolCall" in message_data:
                                tool_call_data = message_data["toolCall"]
                                logging.info(f"Received Tool Call from Gemini: {tool_call_data}")
                                
                                function_responses = []
                                
                                if "functionCalls" in tool_call_data:
                                    for fc in tool_call_data["functionCalls"]:
                                        fc_name = fc.get("name")
                                        fc_args = fc.get("args")
                                        fc_id = fc.get("id")
                                        
                                        tool_call_result = None
                                        if fc_name == "set_led_state":
                                            color = fc_args.get("color")
                                            state = fc_args.get("state")
                                            if color is not None and state is not None:
                                                logging.info(f"Executing tool call: set_led_state(color='{color}', state={state})")
                                                tool_call_result = set_led_state_impl(color, state)
                                            else:
                                                tool_call_result = {"success": False, "message": "Missing color or state argument for set_led_state."}
                                        elif fc_name == "rotate_servo":
                                            degrees = fc_args.get("degrees")
                                            direction = fc_args.get("direction")
                                            if degrees is not None:
                                                logging.info(f"Executing tool call: rotate_servo(degrees={degrees}, direction='{direction}')")
                                                tool_call_result = rotate_servo_impl(degrees, direction)
                                            else:
                                                tool_call_result = {"success": False, "message": "Missing degrees argument for rotate_servo."}
                                        elif fc_name == "get_distance_from_obstacle":
                                            logging.info("Executing tool call: get_distance_from_obstacle()")
                                            tool_call_result = get_distance_from_obstacle_impl()
                                        elif fc_name == "display_on_oled":
                                            text_to_display = fc_args.get("text")
                                            if text_to_display is not None:
                                                logging.info(f"Executing tool: display_on_oled(text='{text_to_display[:20]}...')")
                                                tool_call_result = display_text_on_oled_impl(text_to_display, line_height=14)
                                            else:
                                                tool_call_result = {"success": False, "message": "Missing text for OLED."}
                                        elif fc_name == "play_melody":
                                            notes_to_play = fc_args.get("notes", [])
                                            tool_call_result = play_melody_impl(notes_to_play)
                                        elif fc_name == "play_predefined_melody":
                                            melody_name = fc_args.get("melody_name")
                                            if melody_name:
                                                melody = get_predefined_melody(melody_name)
                                                if melody:
                                                    logging.info(f"Playing predefined melody: {melody['name']}")
                                                    tool_call_result = play_melody_impl(melody["notes"])
                                                else:
                                                    available = list_available_melodies()
                                                    tool_call_result = {"success": False, "message": f"Unknown melody '{melody_name}'. Available: {list(available.keys())}"}
                                            else:
                                                tool_call_result = {"success": False, "message": "Missing melody_name for predefined melody."}
                                        else:
                                            logging.warning(f"Unknown function call name: {fc_name}")
                                            tool_call_result = {"success": False, "message": f"Unknown function: {fc_name}"}
                                        
                                        if tool_call_result and fc_id:
                                            function_responses.append({
                                                "id": fc_id,
                                                "name": fc_name,
                                                "response": {"output": tool_call_result}
                                            })
                                
                                # Send tool responses
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

                            elif "goAway" in message_data:
                                logging.warning(f"Gemini server sent GoAway: {message_data['goAway']}")
                                message_for_web = {"type": "status", "message": "[Gemini session ending]"}
                                break 
                            else:
                                logging.info(f"Received unhandled message structure from Gemini: {message_from_gemini_raw[:200]}...")


                            if message_for_web:
                                await gemini_to_web_queue.put(json.dumps(message_for_web))
                            

                            if transcription_message:
                                await gemini_to_web_queue.put(json.dumps(transcription_message))

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
    global gemini_websocket_connection, user_audio_session_active, accumulated_transcription_for_oled
    logging.info(f"Web client connected: {websocket.remote_address}")
    connected_web_clients.add(websocket)
    try:
        async for message_from_web in websocket:
            if isinstance(message_from_web, str): 
                try:
                    data = json.loads(message_from_web)
                    if data.get("type") == "audio_stream_end":
                        logging.info(f"Received audio_stream_end signal from {websocket.remote_address}")
                        user_audio_session_active = False
                        if gemini_websocket_connection and gemini_websocket_connection.state == State.OPEN:
                            end_signal_message = {"realtimeInput": {"audioStreamEnd": True}}
                            await gemini_websocket_connection.send(json.dumps(end_signal_message))
                            logging.info("Sent audioStreamEnd:true to Gemini.")
                    else:
                        logging.info(f"Received JSON from web client {websocket.remote_address}: {message_from_web}")
                except json.JSONDecodeError:
                    logging.info(f"Received TEXT from web client {websocket.remote_address}: {message_from_web}")
                    await web_text_to_gemini_queue.put(message_from_web)
                
            elif isinstance(message_from_web, bytes): 
                logging.info(f"Received AUDIO ({len(message_from_web)} bytes) from web client {websocket.remote_address}")
                
                # OLED initialization when user starts new audio session
                if not user_audio_session_active:
                    user_audio_session_active = True
                    accumulated_transcription_for_oled = ""
                    asyncio.create_task(asyncio.to_thread(display_text_on_oled_impl, "", 4, 14))
                    logging.info("User started speaking - OLED cleared for new session")
                
                if gemini_websocket_connection and gemini_websocket_connection.state == State.OPEN:
                    try:
                        audio_base64 = base64.b64encode(message_from_web).decode('utf-8')
                        gemini_realtime_input = {
                            "realtimeInput": {
                                "audio": {"data": audio_base64, "mimeType": "audio/pcm;rate=16000"}
                            }
                        }
                        await gemini_websocket_connection.send(json.dumps(gemini_realtime_input))
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
                *[client_ws.send(message_to_broadcast_json) for client_ws in active_clients],
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

    setup_gpio()
    if not setup_oled():
        logging.warning("OLED setup failed. Text display on OLED will not be available.")

    asyncio.create_task(gemini_processor())
    asyncio.create_task(broadcast_gemini_responses())
    asyncio.create_task(stream_video_to_gemini())

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
        pwm_buzzer = GPIO.PWM(BUZZER_PIN, 100)
        pwm_buzzer.start(10)
        
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
                frequency = 20

            try:
                pwm_buzzer.ChangeFrequency(frequency)
                time.sleep(duration_ms / 1000.0)
                time.sleep(0.05)
            except Exception as e:
                logging.error(f"Error playing note {frequency}Hz for {duration_ms}ms: {e}")
        
        pwm_buzzer.stop()
        logging.info("Melody playback finished.")
        return {"status": "success", "message": "Melody played."}
    except Exception as e:
        logging.error(f"Error in play_melody_impl: {e}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    try:
 
        asyncio.run(start_main_server())
    except KeyboardInterrupt:
        logging.info("Main server shutting down.")
    except Exception as e:
        logging.error(f"Failed to start main server: {e}")
    finally:
        if oled_display:
            try:
                display_draw_obj.rectangle((0,0,OLED_WIDTH,OLED_HEIGHT), outline=0, fill=0)
                oled_display.show()
            except Exception as e_oled_clean:
                logging.error(f"Error clearing OLED on exit: {e_oled_clean}")
        cleanup_gpio()
        logging.info("GPIO cleanup finished. Exiting.")