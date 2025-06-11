# Gemini Live API - Comprehensive WebSocket API Reference

## Overview

The Gemini Live API is a stateful API that uses WebSockets for real-time, bidirectional communication with Gemini models. This API is currently in preview and enables interactive conversations with support for text, audio, and video inputs.

## Sessions

A WebSocket connection establishes a session between the client and the Gemini server. After a client initiates a new connection, the session can exchange messages with the server to:

- Send text, audio, or video to the Gemini server
- Receive audio, text, or function call requests from the Gemini server

### WebSocket Connection

To start a session, connect to this WebSocket endpoint:

```
wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent
```

**Note:** The URL is for version `v1beta`.

### Session Configuration

The initial message after connection sets the session configuration, which includes the model, generation parameters, system instructions, and tools. You can change the configuration parameters except the model during the session.

Example configuration structure:

```json
{
  "model": "string",
  "generationConfig": {
    "candidateCount": "integer",
    "maxOutputTokens": "integer",
    "temperature": "number",
    "topP": "number",
    "topK": "integer",
    "presencePenalty": "number",
    "frequencyPenalty": "number",
    "responseModalities": ["string"],
    "speechConfig": "object",
    "mediaResolution": "object"
  },
  "systemInstruction": "string",
  "tools": ["object"]
}
```

## Sending Messages

To exchange messages over the WebSocket connection, the client must send a JSON object over an open WebSocket connection. The JSON object must have **exactly one** of the following fields:

```json
{
  "setup": "BidiGenerateContentSetup",
  "clientContent": "BidiGenerateContentClientContent",
  "realtimeInput": "BidiGenerateContentRealtimeInput",
  "toolResponse": "BidiGenerateContentToolResponse"
}
```

### Supported Client Messages

| Message                            | Description                                                                      |
| ---------------------------------- | -------------------------------------------------------------------------------- |
| `BidiGenerateContentSetup`         | Session configuration to be sent in the first message                            |
| `BidiGenerateContentClientContent` | Incremental content update of the current conversation delivered from the client |
| `BidiGenerateContentRealtimeInput` | Real time audio, video, or text input                                            |
| `BidiGenerateContentToolResponse`  | Response to a `ToolCallMessage` received from the server                         |

## Receiving Messages

To receive messages from Gemini, listen for the WebSocket 'message' event and parse the result according to the definition of the supported server messages.

Example (Python):

```python
async with client.aio.live.connect(model='...', config=config) as session:
    await session.send(input='Hello world!', end_of_turn=True)
    async for message in session.receive():
        print(message)
```

Server messages may have a `usageMetadata` field but will otherwise include **exactly one** of the other fields from the `BidiGenerateContentServerMessage` message.

## Messages and Events

### ActivityEnd

**Type:** Empty object  
**Description:** Marks the end of user activity.

### ActivityHandling

**Description:** The different ways of handling user activity.

**Enums:**

- `ACTIVITY_HANDLING_UNSPECIFIED`: Default behavior is `START_OF_ACTIVITY_INTERRUPTS`
- `START_OF_ACTIVITY_INTERRUPTS`: Start of activity will interrupt the model's response (barge in). This is the default behavior.
- `NO_INTERRUPTION`: The model's response will not be interrupted.

### ActivityStart

**Type:** Empty object  
**Description:** Marks the start of user activity.

### AudioTranscriptionConfig

**Type:** Empty object  
**Description:** The audio transcription configuration.

### AutomaticActivityDetection

**Description:** Configures automatic detection of activity.

**Fields:**

- `disabled` (bool): Optional. If enabled (the default), detected voice and text input count as activity. If disabled, the client must send activity signals.
- `startOfSpeechSensitivity` (StartSensitivity): Optional. Determines how likely speech is to be detected.
- `prefixPaddingMs` (int32): Optional. The required duration of detected speech before start-of-speech is committed.
- `endOfSpeechSensitivity` (EndSensitivity): Optional. Determines how likely detected speech is ended.
- `silenceDurationMs` (int32): Optional. The required duration of detected non-speech before end-of-speech is committed.

### BidiGenerateContentClientContent

**Description:** Incremental update of the current conversation delivered from the client. All content here is unconditionally appended to the conversation history. A message here will interrupt any current model generation.

**Fields:**

- `turns[]` (Content): Optional. The content appended to the current conversation with the model.
- `turnComplete` (bool): Optional. If true, indicates that the server content generation should start with the currently accumulated prompt.

### BidiGenerateContentRealtimeInput

**Description:** User input that is sent in real time. The different modalities (audio, video and text) are handled as concurrent streams.

**Key Differences from BidiGenerateContentClientContent:**

- Can be sent continuously without interruption to model generation
- End of turn is derived from user activity rather than explicitly specified
- Data is processed incrementally to optimize for fast response start

**Fields:**

- `mediaChunks[]` (Blob): Optional. Inlined bytes data for media input. DEPRECATED: Use `audio`, `video`, or `text` instead.
- `audio` (Blob): Optional. These form the realtime audio input stream.
- `video` (Blob): Optional. These form the realtime video input stream.
- `activityStart` (ActivityStart): Optional. Marks the start of user activity. Can only be sent if automatic activity detection is disabled.
- `activityEnd` (ActivityEnd): Optional. Marks the end of user activity. Can only be sent if automatic activity detection is disabled.
- `audioStreamEnd` (bool): Optional. Indicates that the audio stream has ended.
- `text` (string): Optional. These form the realtime text input stream.

### BidiGenerateContentServerContent

**Description:** Incremental server update generated by the model in response to client messages. Content is generated as quickly as possible, not in real time.

**Fields:**

- `generationComplete` (bool): Output only. If true, indicates that the model is done generating.
- `turnComplete` (bool): Output only. If true, indicates that the model has completed its turn.
- `interrupted` (bool): Output only. If true, indicates that a client message has interrupted current model generation.
- `groundingMetadata` (GroundingMetadata): Output only. Grounding metadata for the generated content.
- `inputTranscription` (BidiGenerateContentTranscription): Output only. Input audio transcription.
- `outputTranscription` (BidiGenerateContentTranscription): Output only. Output audio transcription.
- `urlContextMetadata` (UrlContextMetadata): URL context metadata.
- `modelTurn` (Content): Output only. The content that the model has generated.

### BidiGenerateContentServerMessage

**Description:** Response message for the BidiGenerateContent call.

**Fields:**

- `usageMetadata` (UsageMetadata): Output only. Usage metadata about the response(s).

**Union field `messageType` (exactly one of the following):**

- `setupComplete` (BidiGenerateContentSetupComplete): Sent in response to a setup message
- `serverContent` (BidiGenerateContentServerContent): Content generated by the model
- `toolCall` (BidiGenerateContentToolCall): Request for the client to execute function calls
- `toolCallCancellation` (BidiGenerateContentToolCallCancellation): Notification to cancel previously issued tool calls
- `goAway` (GoAway): Notice that the server will soon disconnect
- `sessionResumptionUpdate` (SessionResumptionUpdate): Update of the session resumption state

### BidiGenerateContentSetup

**Description:** Message to be sent in the first (and only in the first) `BidiGenerateContentClientMessage`. Contains configuration that will apply for the duration of the streaming RPC.

**Fields:**

- `model` (string): Required. The model's resource name. Format: `models/{model}`
- `generationConfig` (GenerationConfig): Optional. Generation config. (Note: Several fields are not supported in Live API)
- `systemInstruction` (Content): Optional. The user provided system instructions for the model.
- `tools[]` (Tool): Optional. A list of Tools the model may use to generate the next response.
- `realtimeInputConfig` (RealtimeInputConfig): Optional. Configures the handling of realtime input.
- `sessionResumption` (SessionResumptionConfig): Optional. Configures session resumption mechanism.
- `contextWindowCompression` (ContextWindowCompressionConfig): Optional. Configures a context window compression mechanism.
- `inputAudioTranscription` (AudioTranscriptionConfig): Optional. If set, enables transcription of voice input.
- `outputAudioTranscription` (AudioTranscriptionConfig): Optional. If set, enables transcription of the model's audio output.
- `proactivity` (ProactivityConfig): Optional. Configures the proactivity of the model.

### BidiGenerateContentSetupComplete

**Type:** Empty object  
**Description:** Sent in response to a `BidiGenerateContentSetup` message from the client.

### BidiGenerateContentToolCall

**Description:** Request for the client to execute the `functionCalls` and return the responses with matching `id`s.

**Fields:**

- `functionCalls[]` (FunctionCall): Output only. The function call to be executed.

### BidiGenerateContentToolCallCancellation

**Description:** Notification for the client that a previously issued `ToolCallMessage` with the specified `id`s should not have been executed and should be cancelled.

**Fields:**

- `ids[]` (string): Output only. The ids of the tool calls to be cancelled.

### BidiGenerateContentToolResponse

**Description:** Client generated response to a `ToolCall` received from the server. Individual `FunctionResponse` objects are matched to the respective `FunctionCall` objects by the `id` field.

**Fields:**

- `functionResponses[]` (FunctionResponse): Optional. The response to the function calls.

### BidiGenerateContentTranscription

**Description:** Transcription of audio (input or output).

**Fields:**

- `text` (string): Transcription text.

### ContextWindowCompressionConfig

**Description:** Enables context window compression — a mechanism for managing the model's context window so that it does not exceed a given length.

**Fields:**

- `triggerTokens` (int64): The number of tokens required to trigger a context window compression.

**Union field `compressionMechanism` (one of the following):**

- `slidingWindow` (SlidingWindow): A sliding-window mechanism.

### EndSensitivity

**Description:** Determines how end of speech is detected.

**Enums:**

- `END_SENSITIVITY_UNSPECIFIED`: The default is END_SENSITIVITY_HIGH
- `END_SENSITIVITY_HIGH`: Automatic detection ends speech more often
- `END_SENSITIVITY_LOW`: Automatic detection ends speech less often

### GoAway

**Description:** A notice that the server will soon disconnect.

**Fields:**

- `timeLeft` (Duration): The remaining time before the connection will be terminated as ABORTED.

### ProactivityConfig

**Description:** Config for proactivity features.

**Fields:**

- `proactiveAudio` (bool): Optional. If enabled, the model can reject responding to the last prompt.

### RealtimeInputConfig

**Description:** Configures the realtime input behavior in `BidiGenerateContent`.

**Fields:**

- `automaticActivityDetection` (AutomaticActivityDetection): Optional. If not set, automatic activity detection is enabled by default.
- `activityHandling` (ActivityHandling): Optional. Defines what effect activity has.
- `turnCoverage` (TurnCoverage): Optional. Defines which input is included in the user's turn.

### SessionResumptionConfig

**Description:** Session resumption configuration.

**Fields:**

- `handle` (string): The handle of a previous session. If not present then a new session is created.

### SessionResumptionUpdate

**Description:** Update of the session resumption state.

**Fields:**

- `newHandle` (string): New handle that represents a state that can be resumed.
- `resumable` (bool): True if the current session can be resumed at this point.

### SlidingWindow

**Description:** The SlidingWindow method operates by discarding content at the beginning of the context window.

**Fields:**

- `targetTokens` (int64): The target number of tokens to keep. The default value is trigger_tokens/2.

### StartSensitivity

**Description:** Determines how start of speech is detected.

**Enums:**

- `START_SENSITIVITY_UNSPECIFIED`: The default is START_SENSITIVITY_HIGH
- `START_SENSITIVITY_HIGH`: Automatic detection will detect the start of speech more often
- `START_SENSITIVITY_LOW`: Automatic detection will detect the start of speech less often

### TurnCoverage

**Description:** Options about which input is included in the user's turn.

**Enums:**

- `TURN_COVERAGE_UNSPECIFIED`: Default behavior is `TURN_INCLUDES_ONLY_ACTIVITY`
- `TURN_INCLUDES_ONLY_ACTIVITY`: The user's turn only includes activity since the last turn, excluding inactivity
- `TURN_INCLUDES_ALL_INPUT`: The user's turn includes all realtime input since the last turn, including inactivity

### UrlContextMetadata

**Description:** Metadata related to url context retrieval tool.

**Fields:**

- `urlMetadata[]` (UrlMetadata): List of url context.

### UsageMetadata

**Description:** Usage metadata about response(s).

**Fields:**

- `promptTokenCount` (int32): Output only. Number of tokens in the prompt.
- `cachedContentTokenCount` (int32): Number of tokens in the cached part of the prompt.
- `responseTokenCount` (int32): Output only. Total number of tokens across all the generated response candidates.
- `toolUsePromptTokenCount` (int32): Output only. Number of tokens present in tool-use prompt(s).
- `thoughtsTokenCount` (int32): Output only. Number of tokens of thoughts for thinking models.
- `totalTokenCount` (int32): Output only. Total token count for the generation request.
- `promptTokensDetails[]` (ModalityTokenCount): Output only. List of modalities that were processed in the request input.
- `cacheTokensDetails[]` (ModalityTokenCount): Output only. List of modalities of the cached content in the request input.
- `responseTokensDetails[]` (ModalityTokenCount): Output only. List of modalities that were returned in the response.
- `toolUsePromptTokensDetails[]` (ModalityTokenCount): Output only. List of modalities that were processed for tool-use request inputs.

## Ephemeral Authentication Tokens

Ephemeral authentication tokens can be obtained by calling `AuthTokenService.CreateToken` and then used with `GenerativeService.BidiGenerateContentConstrained`, either by passing the token in an `access_token` query parameter, or in an HTTP `Authorization` header with "Token" prefixed to it.

### CreateAuthTokenRequest

**Description:** Create an ephemeral authentication token.

**Fields:**

- `authToken` (AuthToken): Required. The token to create.

### AuthToken

**Description:** A request to create an ephemeral authentication token.

**Fields:**

- `name` (string): Output only. Identifier. The token itself.
- `expireTime` (Timestamp): Optional. Input only. Immutable. An optional time after which messages in BidiGenerateContent sessions will be rejected.
- `newSessionExpireTime` (Timestamp): Optional. Input only. Immutable. The time after which new Live API sessions using the token will be rejected.
- `fieldMask` (FieldMask): Optional. Input only. Immutable. Controls which fields from `bidiGenerateContentSetup` will overwrite the fields from the setup message in the Live API connection.
- `uses` (int32): Optional. Input only. Immutable. The number of times the token can be used.

**Union field `config` (one of the following):**

- `bidiGenerateContentSetup` (BidiGenerateContentSetup): Optional. Input only. Immutable. Configuration specific to `BidiGenerateContent`.

## Common Types

For more information on the commonly-used API resource types `Blob`, `Content`, `FunctionCall`, `FunctionResponse`, `GenerationConfig`, `GroundingMetadata`, `ModalityTokenCount`, and `Tool`, see the Generating content documentation.

## Important Notes

1. **Preview Status**: The Live API is currently in preview
2. **Version**: Use `v1beta` for the WebSocket endpoint
3. **Message Order**: The ordering across different modalities (audio, video, text) is not guaranteed
4. **Session Setup**: Clients should wait for a `BidiGenerateContentSetupComplete` message before sending additional messages
5. **Interruption**: Client messages will interrupt current model generation
6. **Real-time Processing**: Content is generated as quickly as possible, not necessarily in real time
7. **Activity Detection**: Automatic activity detection is enabled by default but can be configured or disabled
