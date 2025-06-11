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

    - [ ] Use Web Audio API (`navigator.mediaDevices.getUserMedia`, `AudioContext`, `ScriptProcessorNode` or `AudioWorkletNode`) in the browser JavaScript to capture microphone input.
    - [ ] Process audio into PCM format (16-bit, 16kHz sample rate preferred by Gemini).
        - *Consider if resampling is needed on the client or if RPi can handle it.*
    - [ ] Stream audio chunks (e.g., as ArrayBuffer or Blob) via WebSocket to the RPi WebSocket server.
    - *Reference: Web Audio API documentation. For client-side audio capture & processing concepts, see `gemini-web-dev/src/lib/audio-recorder.ts` and `gemini-web-dev/src/lib/worklets/audio-processing.ts`. For sending logic see `gemini-web-dev/src/components/control-tray/ControlTray.tsx`.*

### 3.2 RPi: Audio Forwarding (Web Client -> Gemini) (`main.py`)

    - [ ] In `main.py` WebSocket handler, receive audio chunks from the web client.
    - [ ] Convert received audio chunks to base64-encoded strings.
    - [ ] Forward these audio chunks to the Gemini Live API using `BidiGenerateContentRealtimeInput` message, specifically the `audio` field within it (e.g., `{"audio": {"data": "base64string", "mimeType": "audio/pcm;rate=16000"}}`).
    - *Reference: `docs/gemini-live-api.md` (Sending Audio), `docs/google-websocket-api.md` (BidiGenerateContentRealtimeInput, Blob structure). Note: `gemini-live-api.md` uses `audio=types.Blob(...)` in Python SDK, adapt for raw WebSocket JSON.*

### 3.3 RPi: Audio Reception and Forwarding (Gemini -> Web Client) (`main.py`)

    - [ ] In `main.py`, handle `BidiGenerateContentServerContent` messages from Gemini.
    - [ ] Check `modelTurn.parts` for parts with `inlineData.mimeType` starting with `audio/pcm`.
    - [ ] Extract the base64 audio data from `inlineData.data`.
    - [ ] Send this base64 audio data (or raw bytes if preferred by client) back to the connected web client via the RPi WebSocket server.
    - *Reference: `docs/gemini-live-api.md` (Receiving Audio). For handling incoming audio events, see concepts in `gemini-web-dev/src/hooks/use-live-api.ts` (onAudio handler).*

### 3.4 Web Client: Audio Playback

    - [ ] Receive audio chunks (base64 or raw bytes) from the RPi WebSocket server.
    - [ ] Decode base64 if necessary.
    - [ ] Use Web Audio API (`AudioContext`, `AudioBufferSourceNode`) to play back the received audio chunks in the browser.
    - *Reference: Web Audio API documentation. For playback concepts, see `gemini-web-dev/src/lib/audio-streamer.ts`.*

### 3.5 Audio Transcription (Optional, for Debugging/Display)

    - [ ] If `responseModalities` is `["AUDIO"]`, configure `outputAudioTranscription: {}` in `BidiGenerateContentSetup`.
    - [ ] If sending audio from client to Gemini, configure `inputAudioTranscription: {}`.
    - [ ] Handle `inputTranscription` and `outputTranscription` fields in `BidiGenerateContentServerContent` messages from Gemini and display them on the web client.
    - *Reference: `docs/gemini-live-api.md` (Audio Transcriptions), `docs/google-websocket-api.md` (AudioTranscriptionConfig, BidiGenerateContentServerContent).*

## Phase 4: Real-time Video Streaming (RPi Camera -> Gemini)

### 4.1 RPi: Camera Setup and Frame Capture (`main.py`)

    - [ ] Initialize and configure the PiCamera2 using the `picamera2` library (similar to `video-record.py`).
    - [ ] Create a video configuration (e.g., resolution, format).
    - [ ] Implement a loop to continuously capture video frames (e.g., to a BytesIO stream or directly as JPEG).
    - *Reference: `raspberry-pi-project/video-record.py`, `picamera2` documentation.*

### 4.2 RPi: Video Frame Streaming to Gemini (`main.py`)

    - [ ] Convert captured frames to JPEG format.
    - [ ] Base64 encode the JPEG video frames.
    - [ ] Send video frames as part of `BidiGenerateContentRealtimeInput` message, specifically the `video` field (e.g., `{"video": {"data": "base64string", "mimeType": "image/jpeg"}}`).
    - [ ] Manage frame rate to balance performance and Gemini API recommendations/limits.
    - *Reference: `docs/google-websocket-api.md` (BidiGenerateContentRealtimeInput, Blob structure). For concept of sending image data, refer to `gemini-web-dev/src/components/control-tray/ControlTray.tsx` where it prepares canvas image for sending.*

## Phase 5: Hardware Control via Function Calling (`main.py`)

### 5.1 Define Function Schemas for Hardware

    - [ ] Define JSON schemas (OpenAPI format) for functions to control:
        - LEDs (e.g., `turn_on_led`, `set_led_color` with parameters like `color`, `pin_number`)
        - Servo motor (e.g., `rotate_servo` with parameter `angle`)
        - Buzzer (e.g., `sound_buzzer` with parameters `duration`, `frequency`)
        - OLED display (e.g., `display_text_on_oled` with parameter `text_to_display`)
    - *Reference: `docs/function-call-api.md` (Schema examples), `docs/gemini-live-api.md` (Function Calling example). Also review `gemini-web-dev/src/components/altair/Altair.tsx` for tool declaration structure.*

### 5.2 Implement Hardware Control Functions in Python

    - [ ] Write Python functions that use `RPi.GPIO` (or chosen alternative) to control the connected hardware components based on the arguments received from Gemini.
    - [ ] Map function names/parameters from schemas to these Python functions.
    - [ ] Ensure proper GPIO setup (`GPIO.setmode()`, `GPIO.setup()`) and cleanup (`GPIO.cleanup()`).

### 5.3 Configure Function Calling in Gemini Session Setup

    - [ ] Create `Tool` objects containing your `functionDeclarations` (the schemas from 5.1).
    - [ ] Add these `Tool` objects to the `tools` array in the `BidiGenerateContentSetup` message sent to Gemini.
    - *Reference: `docs/gemini-live-api.md` (Function Calling example), `docs/google-websocket-api.md` (Tool structure).*

### 5.4 Handle Tool Calls from Gemini

    - [ ] In `main.py`, listen for `BidiGenerateContentToolCall` messages from Gemini.
    - [ ] Parse the `functionCalls` array from the message.
    - [ ] For each function call, identify the function name and arguments.
    - [ ] Execute the corresponding Python hardware control function (from 5.2) with the provided arguments.
    - *Reference: `docs/google-websocket-api.md` (BidiGenerateContentToolCall, FunctionCall structure).*

### 5.5 Send Tool Responses to Gemini

    - [ ] After executing a hardware function, prepare a `FunctionResponse` object.
        - Include the original `id` from the `FunctionCall`.
        - Set the `name` to the original function name.
        - Populate the `response` field with the result (e.g., `{"output": {"success": True, "message": "LED turned on"}}`).
    - [ ] Send an array of these `FunctionResponse` objects back to Gemini using the `BidiGenerateContentToolResponse` message.
    - *Reference: `docs/google-websocket-api.md` (BidiGenerateContentToolResponse, FunctionResponse structure). `gemini-web-dev/src/components/altair/Altair.tsx` has an example of sending tool responses.*

## Phase 6: Sensor Integration and OLED Display (`main.py`)

### 6.1 Sensor Reading

    - [ ] Implement Python functions to read data from:
        - Ultrasonic sensor (distance).
        - Light sensor (ambient light level).
    - [ ] Handle sensor calibration and data processing/filtering if needed.

### 6.2 Providing Sensor Data to Gemini

    - [ ] **Strategy 1: Via Prompt Augmentation:** Periodically read sensor data, format it as text (e.g., "Current distance: 20cm, Light level: 300 lux"), and include this text in the `BidiGenerateContentClientContent` message along with user's voice/text input.
    - [ ] **Strategy 2: Via Function Calling:** Define a function (e.g., `get_environment_status`) that Gemini can call. This function would read all relevant sensors and return their states in the `FunctionResponse`.
    - [ ] Implement the chosen strategy.

### 6.3 OLED Display Integration (if not fully covered by Function Calling in 5.1)

    - [ ] Implement Python functions to control the OLED display (initialize, clear, write text, draw basic shapes if needed).
    - [ ] Gemini can instruct the OLED via a function call (see 5.1), or `main.py` can directly update it with status information (e.g., "Listening...", "Processing...", sensor values).

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
