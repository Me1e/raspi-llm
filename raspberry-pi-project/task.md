# Raspberry Pi Real-time AI Voice Assistant: Task Breakdown

This document outlines the tasks required to build the Raspberry Pi based Real-time AI Voice Assistant as described in `plan.md`.

## Phase 1: Project Setup and Core Infrastructure

### 1.1 Raspberry Pi Environment Setup

    - [X] Install Python 3.x and pip.
    - [X] Install necessary Python libraries:
        - `websockets` (for WebSocket server/client)
        - `google-generativeai` (for Gemini API interaction)
        - `picamera2` (for camera control)
        - `RPi.GPIO` (for hardware control - ensure compatibility with your RPi model and OS for alternatives if needed)
        - `sounddevice` or `pyaudio` (if direct audio capture/playback on RPi is considered beyond browser)
        - Libraries for OLED display (e.g., `adafruit-circuitpython-ssd1306`, `luma.oled`)
        - Libraries for sensors (specific to chosen sensors, e.g., `adafruit-circuitpython-hcsr04` for ultrasonic).
    - [X] Configure Raspberry Pi:
        - Enable camera interface (raspi-config).
        - Enable I2C for OLED display (raspi-config).
        - Ensure correct user permissions for GPIO, camera, audio.
    - [X] Set up project directory structure on Raspberry Pi for `main.py` and other potential modules.
    - [X] Familiarize with Gemini API documentation in `docs/` folder, especially `gemini-live-api.md` and `google-websocket-api.md`.

### 1.2 Basic WebSocket Server on Raspberry Pi (`main.py`)

    - [X] Implement a basic Python WebSocket server using the `websockets` library.
    - [X] Server should be able to accept connections and echo messages for initial testing.
    - *Reference: `websockets` library documentation.*

### 1.3 Basic Web Client (HTML/JavaScript)

    - [X] Create a simple HTML page with JavaScript.
    - [X] Implement JavaScript to connect to the RPi WebSocket server.
    - [X] Add basic UI elements for sending test messages and displaying responses.
    - [X] Test sending messages to RPi and receiving echoes.
    - *Reference: Browser WebSocket API documentation. For UI/interaction patterns, review `gemini-web-dev/src/components/side-panel/SidePanel.tsx` (text input) and `gemini-web-dev/src/App.tsx` (basic layout).*

## Phase 2: Gemini Live API Core Integration on Raspberry Pi (`main.py`)

### 2.1 Gemini API Key Setup

    - [X] Securely store the Gemini API key on the Raspberry Pi (e.g., environment variable, config file not committed to git).
    - [X] Implement a way for `main.py` to load the API key.

### 2.2 Establish Gemini Live API WebSocket Connection

    - [X] In `main.py`, implement Python code to connect to the Gemini Live API WebSocket endpoint: `wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent`.
    - [X] Handle the initial `BidiGenerateContentSetup` message:
        - Specify the model (e.g., "gemini-2.0-flash-live-001" or a newer compatible experimental model).
        - Configure `responseModalities` (initially `["TEXT"]` for easier debugging, later `["AUDIO"]`).
        - Set up `systemInstruction` as per `plan.md` ("You are a helpful assistant...").
        - Prepare for `tools` configuration (Function Calling, Google Search).
    - [X] Handle `BidiGenerateContentSetupComplete` response from Gemini to confirm setup.
    - *Reference: `docs/gemini-live-api.md` (Establishing a Connection), `docs/google-websocket-api.md` (BidiGenerateContentSetup, BidiGenerateContentSetupComplete).*

### 2.3 Basic Text Interaction with Gemini

    - [X] Implement logic in `main.py` to forward text messages received from the web client (via RPi WebSocket) to the Gemini Live API using `BidiGenerateContentClientContent`.
    - [X] Set `turnComplete=True` for initial simple queries.
    - [X] Implement logic in `main.py` to receive text responses (`BidiGenerateContentServerContent.modelTurn.parts` where a part has a `text` field) from Gemini.
    - [X] Forward these Gemini text responses back to the web client via the RPi WebSocket.
    - *Reference: `docs/gemini-live-api.md` (Sending and Receiving Text), `docs/google-websocket-api.md` (BidiGenerateContentClientContent, BidiGenerateContentServerContent).*

## Phase 3: Real-time Audio Streaming (Web Client <-> RPi <-> Gemini)

### 3.1 Web Client: Audio Capture and Streaming to RPi

    - [X] Use Web Audio API (`navigator.mediaDevices.getUserMedia`, `AudioContext`, `ScriptProcessorNode` or `AudioWorkletNode`) in the browser JavaScript to capture microphone input.
    - [X] Process audio into PCM format (16-bit, 16kHz sample rate preferred by Gemini).
        - *Consider if resampling is needed on the client or if RPi can handle it.*
    - [X] Stream audio chunks (e.g., as ArrayBuffer or Blob) via WebSocket to the RPi WebSocket server.
    - *Reference: Web Audio API documentation. For client-side audio capture & processing concepts, see `gemini-web-dev/src/lib/audio-recorder.ts` and `gemini-web-dev/src/lib/worklets/audio-processing.ts`. For sending logic see `gemini-web-dev/src/components/control-tray/ControlTray.tsx`.*

### 3.2 RPi: Audio Forwarding (Web Client -> Gemini) (`main.py`)

    - [X] In `main.py` WebSocket handler, receive audio chunks from the web client.
    - [X] Convert received audio chunks to base64-encoded strings.
    - [X] Forward these audio chunks to the Gemini Live API using `BidiGenerateContentRealtimeInput` message, specifically the `audio` field within it (e.g., `{"audio": {"data": "base64string", "mimeType": "audio/pcm;rate=16000"}}`).
    - *Reference: `docs/gemini-live-api.md` (Sending Audio), `docs/google-websocket-api.md` (BidiGenerateContentRealtimeInput, Blob structure). Note: `gemini-live-api.md` uses `audio=types.Blob(...)` in Python SDK, adapt for raw WebSocket JSON.*

### 3.3 RPi: Audio Reception and Forwarding (Gemini -> Web Client) (`main.py`)

    - [X] In `main.py`, handle `BidiGenerateContentServerContent` messages from Gemini that contain audio data (`modelTurn.parts` with `inlineData.mimeType` starting with `audio/pcm`).
    - [X] Decode Base64 audio data from Gemini if needed.
    - [X] Stream these audio chunks (wrapped in JSON like `{"type": "audio_data", "payload": "..."}`) back to the connected web client via the RPi WebSocket server.
    - *Reference: `docs/gemini-live-api.md` (Receiving Audio). For handling incoming audio events, see concepts in `gemini-web-dev/src/hooks/use-live-api.ts` (onAudio handler).*

### 3.4 Web Client: Audio Playback

    - [X] Receive audio chunks (JSON wrapped with `type: "audio_data"`) from the RPi WebSocket server.
    - [X] Decode base64 audio data from the payload.
    - [X] Convert 16-bit PCM (24kHz) to Float32Array and use Web Audio API to play back the received audio chunks in the browser.
    - *Reference: Web Audio API documentation. For playback concepts, see `gemini-web-dev/src/lib/audio-streamer.ts`.*

### 3.5 Audio Transcription (Optional, for Debugging/Display)

    - [X] Configure `outputAudioTranscription` and/or `inputAudioTranscription` in `BidiGenerateContentSetup`.
    - [X] Handle transcription messages from Gemini and display them on the web client (e.g., as `{"type": "status", "message": "[Transcript]: ..."}`).
    - *Reference: `docs/gemini-live-api.md` (Audio Transcriptions), `docs/google-websocket-api.md` (AudioTranscriptionConfig, BidiGenerateContentServerContent).*

## Phase 4: Real-time Video Streaming (RPi Camera -> Gemini)

### 4.1 RPi: Camera Setup and Frame Capture (`main.py`)

    - [X] Initialize and configure the PiCamera2 using the `picamera2` library (similar to `video-record.py`).
    - [X] Create a video configuration (e.g., resolution, format).
    - [X] Implement a loop to continuously capture video frames (e.g., to a BytesIO stream or directly as JPEG).
    - *Reference: `raspberry-pi-project/video-record.py`, `picamera2` documentation.*

### 4.2 RPi: Video Frame Streaming to Gemini (`main.py`)

    - [X] Convert captured frames to JPEG format.
    - [X] Base64 encode the JPEG video frames.
    - [X] Send video frames as part of `BidiGenerateContentRealtimeInput` message, specifically the `video` field (e.g., `{"video": {"data": "base64string", "mimeType": "image/jpeg"}}`).
    - [X] Manage frame rate to balance performance and Gemini API recommendations/limits.
    - *Reference: `docs/google-websocket-api.md` (BidiGenerateContentRealtimeInput, Blob structure). For concept of sending image data, refer to `gemini-web-dev/src/components/control-tray/ControlTray.tsx` where it prepares canvas image for sending.*

## Phase 5: Hardware Control via Function Calling (`main.py`)

_This phase focuses on enabling Gemini to control connected hardware components through voice commands by defining and implementing function calls._

### 5.1 Define Function Schemas for Hardware

    - [ ] **LED Control:**
        - `set_led_state(color: string, state: boolean)`: 특정 색상 LED(예: "green", "yellow", "red")를 켜거나(true) 끕니다(false).
    - [ ] **Servo Motor Control:**
        - `rotate_servo(degrees: int, direction: string | null)`: 서보 모터를 지정된 각도만큼 특정 방향("clockwise", "counter_clockwise")으로 상대 회전시키거나, 방향 없이 절대 각도로 설정합니다. (예: `degrees: 60, direction: "clockwise"` 또는 `degrees: 90, direction: null` (90도로 설정)).
        - *Consider a function like `set_servo_angle(angle: int)` for absolute positioning if more suitable.*
    - [ ] **OLED Display Control:**
        - `display_on_oled(text: string, line_number: int | null)`: OLED에 주어진 텍스트를 표시합니다. 여러 줄 표시를 위해 줄 번호(선택적)를 받을 수 있습니다. 긴 텍스트는 자동 줄 바꿈 또는 스크롤 처리 필요.
    - [ ] **Ultrasonic Sensor Reading:**
        - `get_distance_from_obstacle()`: 초음파 센서를 사용하여 전방 장애물까지의 거리를 cm 단위로 반환합니다. (Gemini가 이 함수를 호출하여 정보를 얻음)

### 5.2 Implement Hardware Control Functions in Python

    - [ ] **GPIO Pin Setup:**
        - Define GPIO pin numbers for Green, Yellow, Red LEDs.
        - Define GPIO pin number for Servo Motor PWM.
        - Define GPIO pin numbers for Ultrasonic Sensor (Trig, Echo).
        - Define I2C pins/address for OLED (referencing `board.I2C()` and `addr=0x3C`).
        - Initialize `RPi.GPIO` in BCM mode and set up pins as OUT or IN.
    - [ ] **LED Control Functions:**
        - Implement Python function `set_led_state_impl(color_name, on_off)` that maps color name to GPIO pin and controls `GPIO.output()`.
    - [ ] **Servo Motor Control Functions:**
        - Implement Python function `rotate_servo_impl(degrees, direction)`:
            - Convert `degrees` and `direction` to appropriate PWM duty cycle changes.
            - Handle relative vs. absolute rotation logic.
            - Initialize `GPIO.PWM(SERVO_PIN, 50)` and use `servo.ChangeDutyCycle()`.
    - [ ] **OLED Display Functions:**
        - Implement Python class/functions for OLED control based on the reference:
            - Initialization (`adafruit_ssd1306.SSD1306_I2C`).
            - Clearing display (`oled.fill(0); oled.show()`).
            - Drawing text with PIL (`Image`, `ImageDraw`, `ImageFont`).
            - Handling multi-line text (splitting, positioning).
            - Buffering incoming text from Gemini (since it arrives word by word) and displaying coherently.
        - Implement `display_on_oled_impl(text_to_display, line_num)` to use these utilities.
    - [ ] **Ultrasonic Sensor Functions:**
        - Implement Python function `get_distance_from_obstacle_impl()` based on the reference code:
            - Trigger pulse, measure echo duration.
            - Calculate distance and return it.
    - [ ] **Ensure proper `GPIO.cleanup()` on program exit.**

### 5.3 Configure Function Calling in Gemini Session Setup

    - [ ] Create `Tool` objects containing `functionDeclarations` for all defined schemas (LEDs, Servo, OLED, Ultrasonic) from 5.1.
    - [ ] In `main.py`'s `gemini_processor`, add these `Tool` objects to the `tools` array within the `setup` message sent to Gemini.
    - *Reference: `docs/function-call-api.md`, `docs/gemini-live-api.md` (Function Calling example), `gemini-web-dev/src/components/altair/Altair.tsx` for tool declaration structure.*

### 5.4 Handle Tool Calls from Gemini

    - [ ] In `main.py`'s `receive_from_gemini` (or a dedicated tool call handler):
        - Listen for `BidiGenerateContentToolCall` messages (`message_data['toolCall']`).
        - Parse the `functionCalls` array.
        - For each `functionCall`:
            - Identify the function `name` (e.g., "set_led_state", "rotate_servo").
            - Extract arguments from `args`.
            - Asynchronously execute the corresponding Python implementation function (e.g., `set_led_state_impl`).
    - *Reference: `docs/google-websocket-api.md` (BidiGenerateContentToolCall, FunctionCall structure).*

### 5.5 Send Tool Responses to Gemini

    - [ ] After a Python hardware/sensor function (e.g., `set_led_state_impl`) executes:
        - Prepare a `FunctionResponse` object.
            - Use the `id` from the original `FunctionCall`.
            - Set `name` to the original function name.
            - Populate `response.output` with a JSON object indicating success/failure and any relevant data (e.g., `{"success": True, "message": "Green LED turned on"}` or `{"distance_cm": 25.5}`).
    - [ ] Send an array of these `FunctionResponse` objects back to Gemini using the `BidiGenerateContentToolResponse` message.
    - *Reference: `docs/google-websocket-api.md` (BidiGenerateContentToolResponse, FunctionResponse structure). `gemini-web-dev/src/components/altair/Altair.tsx` has an example of sending tool responses.*

## Phase 6: Sensor Integration and OLED Display (Refined based on new requirements)

_This phase is largely integrated into Phase 5 through Function Calling for the Ultrasonic sensor and OLED display. Specific tasks here focus on how Gemini utilizes this data and presents it._

### 6.1 Sensor Data Usage (via Function Calling)

    - [ ] Test voice commands like "현재 정면의 장애물로부터 몇미터 떨어져있어?" or "What's the distance to the object in front?".
    - [ ] Ensure Gemini calls the `get_distance_from_obstacle` function.
    - [ ] Ensure Gemini uses the returned distance in its verbal (audio) response to the user.

### 6.2 OLED Display for Gemini's Responses

    - [ ] When Gemini generates an audio response, its transcription (if `outputAudioTranscription` is enabled) or a summary should be targeted for OLED display.
    - [ ] **Strategy for displaying full responses:**
        - In `main.py`'s `receive_from_gemini`:
            - Accumulate text parts from `outputTranscription` (or `modelTurn.parts.text` if AUDIO modality is off for some reason).
            - Once a "turn" is considered complete by Gemini (e.g., after a series of audio chunks or a `turnComplete` message for text), or after a short delay of no new text, call the `display_on_oled` function (which Gemini would invoke via function calling, or `main.py` could call it directly with the accumulated text).
            - The `display_on_oled_impl` function will need to handle text wrapping and potentially scrolling for longer messages on the small OLED screen.
    - [ ] Test voice commands that elicit longer responses from Gemini to see how they are displayed on the OLED.

### 6.3 Light Sensor (If still planned - Not explicitly in new requirements, but was in `plan.md`)

    - [ ] If light sensor integration is still desired:
        - Define a function schema: `get_ambient_light_level()`.
        - Implement the Python function to read the light sensor.
        - Add to Gemini's tools.
        - Test by asking "What's the current light level?".

## Phase 7: Web Client Enhancements and User Interface

### 7.1 Improved UI/UX

    - [ ] Design a more polished and user-friendly interface on the web client (HTML, CSS, JavaScript).
    - [ ] Visual indicators for:
        - WebSocket connection status (RPi, Gemini).
        - Microphone recording state (e.g., idle, listening, sending).
        - Gemini processing state (e.g., "Thinking...").
    - [ ] Clear display area for Gemini's text responses and audio/input transcriptions.
    - [ ] Controls for starting/stopping the session, muting/unmuting microphone.
    - *Reference: `gemini-web-dev` for UI component ideas (e.g., `ControlTray`, `SidePanel`, `AudioPulse`).*

### 7.2 Displaying Multimodal Information

    - [ ] If RPi sends status updates about hardware changes (e.g., "LED is now ON") or summarized sensor readings, display this information appropriately on the web client.

## Phase 8: System Testing, Refinement, and Documentation

### 8.1 End-to-End Testing

    - [ ] Test all core features thoroughly:
        - Bidirectional audio streaming and natural conversation flow.
        - Video streaming and Gemini's ability to "see".
        - Function calling for all defined hardware (LEDs, servo, buzzer, OLED).
        - Sensor data integration and Gemini's reaction to it.
    - [ ] Test under various network conditions (if possible simulate latency/packet loss).
    - [ ] Test various voice commands and edge cases.

### 8.2 Latency Optimization

    - [ ] Profile audio/video processing pipelines on RPi and client.
    - [ ] Optimize data chunk sizes and streaming frequencies for minimal perceived latency.
    - [ ] Investigate Gemini API settings that might affect latency (e.g., model choice, specific configurations).

### 8.3 Error Handling and Robustness

    - [ ] Implement comprehensive error handling in `main.py` for:
        - RPi WebSocket server errors (connection drops, etc.).
        - Gemini Live API WebSocket errors (connection drops, API errors, message parsing).
        - Hardware control errors (GPIO issues, sensor read failures).
    - [ ] Implement retry mechanisms or graceful degradation where appropriate.
    - [ ] Add error handling to the web client (WebSocket connection, media device access).

### 8.4 Logging

    - [ ] Implement robust logging in `main.py` for diagnostics, saving to a file. Log key events, errors, messages sent/received.
    - [ ] Utilize browser console logging on the web client for debugging.
    - *Reference: `gemini-web-dev/src/lib/store-logger.ts` for advanced client-side logging patterns, adapt for simple console logs or server-side needs.*

### 8.5 Code Documentation and Project README

    - [ ] Add clear comments and docstrings to Python code in `main.py` and any helper modules.
    - [ ] Document JavaScript code on the web client.
    - [ ] Create/Update a `README.md` for the `raspberry-pi-project` detailing:
        - Project overview and features.
        - Hardware setup instructions.
        - Software installation steps.
        - How to run the system.
        - API key configuration.

### 8.6 (Optional) Google Search Grounding Integration

    - [ ] If real-time web information is required, integrate Google Search as a tool.
    - [ ] Add `{'google_search': {}}` to the `tools` array in `BidiGenerateContentSetup`.
    - [ ] Potentially handle/display `groundingMetadata` from Gemini responses.
    - *Reference: `docs/google-search-api.md` (Method 1: Search as a Tool).*

### 8.7 (Optional) Advanced Gemini Live API Features

    - [ ] Explore and implement if useful:
        - `automaticActivityDetection` configuration.
        - `sessionResumption` for reconnecting.
        - `contextWindowCompression` for long conversations.
    - *Reference: `docs/google-websocket-api.md` for these configurations.*

This task list provides a structured approach. You can adjust the order and granularity based on your priorities and development flow. Good luck!
