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
        - Configure `generationConfig` with `responseModalities: ["AUDIO"]` and `outputAudioConfig` (including `audioEncoding: "LINEAR16"` and `synthesizeSpeechConfig` for "Leda" voice).
        - Set up `systemInstruction` as per `plan.md` ("You are a helpful assistant...").
        - Prepare for `tools` configuration (Function Calling, Google Search).
    - [X] Handle `BidiGenerateContentSetupComplete` response from Gemini to confirm setup.
    - *Reference: `docs/gemini-live-api.md` (Establishing a Connection), `docs/google-websocket-api.md` (BidiGenerateContentSetup, BidiGenerateContentSetupComplete, GenerationConfig, OutputAudioConfig, SynthesizeSpeechConfig).*

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
    - [X] Convert 16-bit PCM (check `outputAudioConfig.sampleRateHertz` from Gemini, typically 24kHz) to Float32Array and use Web Audio API to play back the received audio chunks in the browser.
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

    - [X] **LED Control:**
        - `set_led_state(color: string, state: boolean)`
    - [X] **Servo Motor Control:**
        - `rotate_servo(degrees: int, direction: string | null)`
    - [X] **OLED Display Control:** (Implemented in main.py)
        - `display_on_oled(text: string)`
    - [X] **Ultrasonic Sensor Reading:**
        - `get_distance_from_obstacle()`
    - [ ] **Buzzer Melody Playback:**
        - `play_melody(notes: list_of_objects)`: Plays a sequence of musical notes. Each note object should contain `frequency` (Hz) and `duration` (ms).

### 5.2 Implement Hardware Control Functions in Python

    - [X] **GPIO Pin Setup:** (LED, Servo, Ultrasonic, OLED I2C setup in `main.py`)
        - Define and initialize GPIO pins for all connected hardware including Buzzer (e.g., `BUZZER_PIN`).
    - [X] **LED Control Functions:** (`set_led_state_impl`)
    - [X] **Servo Motor Control Functions:** (`rotate_servo_impl`)
    - [X] **OLED Display Functions:** (`display_on_oled_impl`)
    - [X] **Ultrasonic Sensor Functions:** (`get_distance_from_obstacle_impl`)
    - [ ] **Buzzer Melody Playback Function:**
        - Implement `play_melody_impl(notes)` in `main.py` using PWM to control the buzzer for specified frequencies and durations.
    - [X] **Ensure proper `GPIO.cleanup()` on program exit.** (Includes buzzer pin consideration)

### 5.3 Configure Function Calling in Gemini Session Setup

    - [X] Create `Tool` objects containing `functionDeclarations` for LED, Servo, Ultrasonic, and OLED control schemas.
    - [ ] Add `play_melody` function schema to the `Tool` objects in `main.py`'s `gemini_processor` setup message.
    - *Reference: `docs/function-call-api.md`, `docs/gemini-live-api.md` (Function Calling example).*

### 5.4 Handle Tool Calls from Gemini

    - [X] In `main.py`'s `receive_from_gemini` (or tool call handler):
        - Listen for `BidiGenerateContentToolCall` messages.
        - Parse `functionCalls` for existing hardware.
    - [ ] Add logic to parse and handle `functionCall` for `play_melody`:
        - Identify the function `name` as `play_melody`.
        - Extract `notes` argument.
        - Asynchronously execute `play_melody_impl(notes)`.
    - *Reference: `docs/google-websocket-api.md` (BidiGenerateContentToolCall, FunctionCall structure).*

### 5.5 Send Tool Responses to Gemini

    - [X] After existing hardware control functions execute, prepare and send `FunctionResponse` objects.
    - [ ] After `play_melody_impl` executes:
        - Prepare a `FunctionResponse` object (using `id` from original call, `name` as `play_melody`).
        - Populate `response.output` with success/failure status.
    - [ ] Send this `FunctionResponse` back to Gemini.
    - *Reference: `docs/google-websocket-api.md` (BidiGenerateContentToolResponse, FunctionResponse structure).*

## Phase 6: Sensor Integration and OLED Display (Refined based on new requirements)

_This phase is largely integrated into Phase 5 through Function Calling for the Ultrasonic sensor and OLED display. Specific tasks here focus on how Gemini utilizes this data and presents it._

### 6.1 Sensor Data Usage (via Function Calling)

    - [ ] Test voice commands like "현재 정면의 장애물로부터 몇미터 떨어져있어?" or "What's the distance to the object in front?".
    - [ ] Ensure Gemini calls the `get_distance_from_obstacle` function.
    - [ ] Ensure Gemini uses the returned distance in its verbal (audio) response to the user.

### 6.2 OLED Display for Gemini's Responses

    - [X] When Gemini generates an audio response, its transcription (if `outputAudioTranscription` is enabled) or a summary should be targeted for OLED display. (Implemented in `main.py` for `outputTranscription`)
    - [ ] **Strategy for displaying full responses:**
        - In `main.py`'s `receive_from_gemini`:
            - Accumulate text parts from `outputTranscription` (or `modelTurn.parts.text` if AUDIO modality is off for some reason).
            - Once a "turn" is considered complete by Gemini, call the `display_on_oled` function.
            - The `display_on_oled_impl` function will need to handle text wrapping and potentially scrolling for longer messages. (Basic wrapping exists, scrolling needs review).
    - [ ] Test voice commands that elicit longer responses from Gemini to see how they are displayed on the OLED.

## Phase 7: Web Client Enhancements and User Interface

### 7.1 Improved UI/UX

    - [ ] Design a more polished and user-friendly interface on the web client (HTML, CSS, JavaScript).
    - [ ] Visual indicators for: WebSocket connection status, microphone state, Gemini processing state.
    - [ ] Clear display area for Gemini's text responses and transcriptions.
    - [ ] Controls for session start/stop, mute/unmute.
    - *Reference: `gemini-web-dev` for UI component ideas.*

### 7.2 Displaying Multimodal Information

    - [ ] If RPi sends status updates about hardware changes or sensor readings, display this on the web client.

## Phase 8: System Testing, Refinement, and Documentation

### 8.1 End-to-End Testing

    - [ ] Test all core features thoroughly:
        - Bidirectional audio streaming (with "Leda" voice) and natural conversation flow.
        - Video streaming and Gemini's ability to "see".
        - Function calling for all defined hardware (LEDs, servo, OLED, **Buzzer/Melody**).
        - Sensor data integration and Gemini's reaction to it.
        - Google Search integration.
    - [ ] Test under various network conditions.
    - [ ] Test various voice commands and edge cases (including for melody playback, e.g., "Play a C major scale").

### 8.2 Latency Optimization

    - [ ] Profile audio/video processing pipelines.
    - [ ] Optimize data chunk sizes and streaming frequencies.
    - [ ] Investigate Gemini API settings affecting latency.

### 8.3 Error Handling and Robustness

    - [ ] Implement comprehensive error handling in `main.py` (RPi WebSocket, Gemini API, hardware control).
    - [ ] Implement retry mechanisms or graceful degradation.
    - [ ] Add error handling to the web client.

### 8.4 Logging

    - [ ] Implement robust logging in `main.py` (key events, errors, messages).
    - [ ] Utilize browser console logging on the web client.

### 8.5 Code Documentation and Project README

    - [ ] Add comments and docstrings to Python and JavaScript code.
    - [ ] Update `README.md` for the `raspberry-pi-project` (overview, setup, usage, API key config).

### 8.6 Google Search Grounding Integration

    - [X] Integrate Google Search as a tool (`main.py` updated).
    - [ ] Handle/display `groundingMetadata` from Gemini responses if applicable.
    - *Reference: `docs/google-search-api.md` (Method 1: Search as a Tool).*

### 8.7 (Optional) Advanced Gemini Live API Features

    - [ ] Explore: `automaticActivityDetection`, `sessionResumption`, `contextWindowCompression`.
    - *Reference: `docs/google-websocket-api.md`.*

This task list provides a structured approach. You can adjust the order and granularity based on your priorities and development flow. Good luck!
