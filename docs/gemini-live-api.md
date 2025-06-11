# Gemini Live API - Comprehensive Documentation

## Overview

The Live API enables low-latency bidirectional voice and video interactions with Gemini, allowing you to talk to Gemini live while also streaming video input or sharing your screen. Using the Live API, you can provide end users with the experience of natural, human-like voice conversations.

**Preview Notice**: The Live API is currently in preview.

You can try the Live API in Google AI Studio by selecting "Stream".

## How the Live API Works

### Streaming Architecture

The Live API uses a streaming model over a WebSocket connection. When you interact with the API, a persistent connection is created. Your input (audio, video, or text) is streamed continuously to the model, and the model's response (text or audio) is streamed back in real-time over the same connection.

This bidirectional streaming ensures low latency and supports features such as:

- Voice activity detection
- Tool usage
- Speech generation

**Security Warning**: It is unsafe to insert your API key into client-side JavaScript or TypeScript code. Use server-side deployments for accessing the Live API in production.

### Output Generation Methods

The Live API processes multimodal input (text, audio, video) to generate text or audio in real-time. It comes with a built-in mechanism to generate audio using one of two methods:

1. **Half Cascade**: The model receives native audio input and uses a specialized model cascade of distinct models to process the input and to generate audio output.

2. **Native**: Gemini 2.5 introduces native audio generation, which directly generates audio output, providing:
   - More natural sounding audio
   - More expressive voices
   - More awareness of additional context (e.g., tone)
   - More proactive responses

## Building with Live API

### Establishing a Connection

**Python Example:**

```python
import asyncio
from google import genai

client = genai.Client(api_key="GEMINI_API_KEY")
model = "gemini-2.0-flash-live-001"
config = {"response_modalities": ["TEXT"]}

async def main():
    async with client.aio.live.connect(model=model, config=config) as session:
        print("Session started")

if __name__ == "__main__":
    asyncio.run(main())
```

**JavaScript Example:**

```javascript
import { GoogleGenAI, Modality } from '@google/genai';

const ai = new GoogleGenAI({ apiKey: 'GOOGLE_API_KEY' });
const model = 'gemini-2.0-flash-live-001';
const config = { responseModalities: [Modality.TEXT] };

async function main() {
  const session = await ai.live.connect({
    model: model,
    callbacks: {
      onopen: function () {
        console.debug('Opened');
      },
      onmessage: function (message) {
        console.debug(message);
      },
      onerror: function (e) {
        console.debug('Error:', e.message);
      },
      onclose: function (e) {
        console.debug('Close:', e.reason);
      },
    },
    config: config,
  });
  // Send content...
  session.close();
}
main();
```

**Important Note**: You can only set one modality in the `response_modalities` field. This means you can configure the model to respond with either text or audio, but not both in the same session.

### Sending and Receiving Text

**Python Example:**

```python
import asyncio
from google import genai

client = genai.Client(api_key="GEMINI_API_KEY")
model = "gemini-2.0-flash-live-001"
config = {"response_modalities": ["TEXT"]}

async def main():
    async with client.aio.live.connect(model=model, config=config) as session:
        message = "Hello, how are you?"
        await session.send_client_content(
            turns={"role": "user", "parts": [{"text": message}]},
            turn_complete=True
        )

        async for response in session.receive():
            if response.text is not None:
                print(response.text, end="")

if __name__ == "__main__":
    asyncio.run(main())
```

**JavaScript Example:**

```javascript
// Complete implementation with message handling
const inputTurns = 'Hello how are you?';
session.sendClientContent({ turns: inputTurns });

const turns = await handleTurn();
for (const turn of turns) {
  if (turn.text) {
    console.debug('Received text: %s\n', turn.text);
  }
}
```

### Audio Handling

#### Audio Formats

Audio data in the Live API is always:

- Raw, little-endian, 16-bit PCM
- Output sample rate: 24kHz
- Input sample rate: natively 16kHz (but API will resample if needed)
- MIME type format: `audio/pcm;rate=16000`

#### Sending Audio

**Python Example:**

```python
# Install helpers: pip install librosa soundfile
import asyncio
import io
from pathlib import Path
from google import genai
from google.genai import types
import soundfile as sf
import librosa

client = genai.Client(api_key="GEMINI_API_KEY")
model = "gemini-2.0-flash-live-001"
config = {"response_modalities": ["TEXT"]}

async def main():
    async with client.aio.live.connect(model=model, config=config) as session:
        buffer = io.BytesIO()
        y, sr = librosa.load("sample.wav", sr=16000)
        sf.write(buffer, y, sr, format='RAW', subtype='PCM_16')
        buffer.seek(0)
        audio_bytes = buffer.read()

        # If already in correct format:
        # audio_bytes = Path("sample.pcm").read_bytes()

        await session.send_realtime_input(
            audio=types.Blob(data=audio_bytes, mime_type="audio/pcm;rate=16000")
        )

        async for response in session.receive():
            if response.text is not None:
                print(response.text)

if __name__ == "__main__":
    asyncio.run(main())
```

**JavaScript Example:**

```javascript
// Install helpers: npm install wavefile
import { GoogleGenAI, Modality } from '@google/genai';
import * as fs from 'node:fs';
import pkg from 'wavefile';
const { WaveFile } = pkg;

// Send Audio Chunk
const fileBuffer = fs.readFileSync('sample.wav');
// Ensure audio conforms to API requirements (16-bit PCM, 16kHz, mono)
const wav = new WaveFile();
wav.fromBuffer(fileBuffer);
wav.toSampleRate(16000);
wav.toBitDepth('16');
const base64Audio = wav.toBase64();

session.sendRealtimeInput({
  audio: {
    data: base64Audio,
    mimeType: 'audio/pcm;rate=16000',
  },
});
```

#### Receiving Audio

**Python Example:**

```python
import asyncio
import wave
from google import genai

client = genai.Client(api_key="GEMINI_API_KEY")
model = "gemini-2.0-flash-live-001"
config = {"response_modalities": ["AUDIO"]}

async def main():
    async with client.aio.live.connect(model=model, config=config) as session:
        wf = wave.open("audio.wav", "wb")
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)

        message = "Hello how are you?"
        await session.send_client_content(
            turns={"role": "user", "parts": [{"text": message}]},
            turn_complete=True
        )

        async for response in session.receive():
            if response.data is not None:
                wf.writeframes(response.data)

        wf.close()

if __name__ == "__main__":
    asyncio.run(main())
```

#### Audio Transcriptions

**Output Audio Transcription:**

```python
config = {
    "response_modalities": ["AUDIO"],
    "output_audio_transcription": {}
}

# In the response loop:
if response.server_content.output_transcription:
    print("Transcript:", response.server_content.output_transcription.text)
```

**Input Audio Transcription:**

```python
config = {
    "response_modalities": ["TEXT"],
    "input_audio_transcription": {},
}

# In the response loop:
if msg.server_content.input_transcription:
    print('Transcript:', msg.server_content.input_transcription.text)
```

### System Instructions

System instructions let you steer the behavior of a model based on your specific needs and use cases. They remain in effect for the entire session.

**Python:**

```python
config = {
    "system_instruction": "You are a helpful assistant and answer in a friendly tone.",
    "response_modalities": ["TEXT"],
}
```

**JavaScript:**

```javascript
const config = {
  responseModalities: [Modality.TEXT],
  systemInstruction:
    'You are a helpful assistant and answer in a friendly tone.',
};
```

### Incremental Content Updates

Use incremental updates to send text input, establish session context, or restore session context.

**For short contexts (turn-by-turn):**

```python
turns = [
    {"role": "user", "parts": [{"text": "What is the capital of France?"}]},
    {"role": "model", "parts": [{"text": "Paris"}]},
]
await session.send_client_content(turns=turns, turn_complete=False)

turns = [{"role": "user", "parts": [{"text": "What is the capital of Germany?"}]}]
await session.send_client_content(turns=turns, turn_complete=True)
```

**For longer contexts**: Provide a single message summary to free up the context window for subsequent interactions.

### Voice and Language Configuration

#### Supported Voices

- Puck
- Charon
- Kore
- Fenrir
- Aoede
- Leda
- Orus
- Zephyr

**Voice Configuration:**

```python
config = {
    "response_modalities": ["AUDIO"],
    "speech_config": {
        "voice_config": {"prebuilt_voice_config": {"voice_name": "Kore"}}
    },
}
```

**Language Configuration:**

```python
config = {
    "response_modalities": ["AUDIO"],
    "speech_config": {
        "language_code": "de-DE"
    }
}
```

**Note**: Native audio output models automatically choose the appropriate language and don't support explicitly setting the language code.

## Native Audio Output

Native audio output models provide higher quality audio outputs with better pacing, voice naturalness, verbosity, and mood.

### Supported Models

- `gemini-2.5-flash-preview-native-audio-dialog`
- `gemini-2.5-flash-exp-native-audio-thinking-dialog`

**Usage:**

```python
model = "gemini-2.5-flash-preview-native-audio-dialog"
config = types.LiveConnectConfig(response_modalities=["AUDIO"])
async with client.aio.live.connect(model=model, config=config) as session:
    # Send audio input and receive audio
```

### Affective Dialog

Enables Gemini to adapt its response style to the input expression and tone.

**Requirements**: API version `v1alpha`

```python
client = genai.Client(api_key="GOOGLE_API_KEY", http_options={"api_version": "v1alpha"})
config = types.LiveConnectConfig(
    response_modalities=["AUDIO"],
    enable_affective_dialog=True
)
```

### Proactive Audio

Allows Gemini to proactively decide not to respond if the content is not relevant.

**Requirements**: API version `v1alpha`

```python
client = genai.Client(api_key="GOOGLE_API_KEY", http_options={"api_version": "v1alpha"})
config = types.LiveConnectConfig(
    response_modalities=["AUDIO"],
    proactivity={'proactive_audio': True}
)
```

### Native Audio with Thinking

Use the thinking-capable model for enhanced reasoning:

```python
model = "gemini-2.5-flash-exp-native-audio-thinking-dialog"
config = types.LiveConnectConfig(response_modalities=["AUDIO"])
```

## Tool Use with Live API

### Supported Tools Overview

| Tool                 | Cascaded models (`gemini-2.0-flash-live-001`) | `gemini-2.5-flash-preview-native-audio-dialog` | `gemini-2.5-flash-exp-native-audio-thinking-dialog` |
| -------------------- | --------------------------------------------- | ---------------------------------------------- | --------------------------------------------------- |
| **Search**           | Yes                                           | Yes                                            | Yes                                                 |
| **Function calling** | Yes                                           | Yes                                            | No                                                  |
| **Code execution**   | Yes                                           | No                                             | No                                                  |
| **URL context**      | Yes                                           | No                                             | No                                                  |

### Function Calling

Define function declarations as part of the session configuration. After receiving tool calls, respond with `FunctionResponse` objects using `session.send_tool_response`.

**Example:**

```python
# Define tools in config
tools = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="get_weather",
                description="Get current weather",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "location": types.Schema(type=types.Type.STRING)
                    }
                )
            )
        ]
    )
]

config = {
    "response_modalities": ["TEXT"],
    "tools": tools
}
```

### Asynchronous Function Calling

The Live API supports asynchronous function calling, allowing the model to continue processing while waiting for function results.

### Code Execution

Enable code execution in the session:

```python
config = {
    "response_modalities": ["TEXT"],
    "tools": [types.Tool(code_execution={})]
}
```

### Google Search Grounding

Enable Google Search for grounding:

```python
config = {
    "response_modalities": ["TEXT"],
    "tools": [types.Tool(google_search={})]
}
```

### Combining Multiple Tools

You can combine multiple tools in a single session:

```python
config = {
    "response_modalities": ["TEXT"],
    "tools": [
        types.Tool(code_execution={}),
        types.Tool(google_search={}),
        types.Tool(function_declarations=[...])
    ]
}
```

## Handling Interruptions

### Voice Activity Detection (VAD)

The Live API includes built-in voice activity detection to handle natural conversation flow and interruptions.

## Session Management

### Token Count

Monitor token usage during the session to manage costs and context limits.

### Extending Session Duration

#### Context Window Compression

For longer sessions, use context compression to maintain conversation history while staying within limits.

#### Session Resumption

Sessions can be resumed to continue conversations across disconnections.

#### GoAway Messages

Handle graceful session termination by listening for GoAway messages before disconnection.

#### Generation Complete Messages

Receive notifications when the model completes a generation turn.

## Media Resolution

Configure appropriate media resolution for video inputs to balance quality and performance.

## Limitations

### Response Modalities

- Only one response modality can be set per session (TEXT or AUDIO, not both)
- Modality cannot be changed during an active session

### Client Authentication

- API keys must be kept secure and used server-side only
- Client-side JavaScript implementations are unsafe for production

### Maximum Session Duration

Sessions have time limits that depend on usage and model type.

### Context Window

Each model has specific context window limitations that affect conversation length.

## Supported Languages

The Live API supports multiple languages with automatic language detection for audio inputs. Explicitly supported languages include:

- English (en-US)
- German (de-DE)
- Spanish (es-ES)
- French (fr-FR)
- Italian (it-IT)
- Portuguese (pt-BR)
- And many others

## Third-Party Integrations

The Live API can be integrated with various third-party services and frameworks for enhanced functionality.

## Best Practices

1. **Connection Management**: Always properly close sessions and handle connection errors
2. **Audio Quality**: Use recommended audio formats for best results
3. **Token Management**: Monitor token usage to avoid unexpected costs
4. **Error Handling**: Implement robust error handling for network issues
5. **Security**: Never expose API keys in client-side code
6. **Performance**: Use appropriate audio sample rates and compression
7. **User Experience**: Implement proper loading states and feedback for users

## Error Handling

Implement comprehensive error handling for:

- Network connectivity issues
- API rate limits
- Invalid audio formats
- Session timeouts
- Tool execution failures

## Rate Limits and Quotas

Be aware of API rate limits and implement appropriate backoff strategies when limits are exceeded.
