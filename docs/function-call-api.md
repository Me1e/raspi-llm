# Gemini Live API Documentation

## Overview

The Gemini Live API is an advanced real-time interface that extends the capabilities of the standard Gemini API with enhanced functionality for interactive, conversational applications. The Live API supports sophisticated features like compositional function calling and multi-tool use that are not available in the standard API.

## Key Features

### 1. **Compositional Function Calling**

The Live API supports compositional function calling, allowing the model to chain multiple function calls together in sequence. This enables complex workflows where the output of one function becomes the input for another.

**Example Use Case**: To answer "Get the temperature in my current location", the model can:

1. First call `get_current_location()`
2. Then call `get_weather(location)` using the result from step 1

### 2. **Multi-tool Use**

The Live API can simultaneously combine multiple tools including:

- **Native Tools**: Google Search, Code Execution
- **Custom Function Declarations**: User-defined functions
- **Real-time Processing**: Audio and other modalities

### 3. **Enhanced Modality Support**

- Audio processing capabilities
- Real-time streaming
- WebSocket-based communication

## Implementation Examples

### Compositional Function Calling

#### Python Implementation

```python
# Light control schemas
turn_on_the_lights_schema = {'name': 'turn_on_the_lights'}
turn_off_the_lights_schema = {'name': 'turn_off_the_lights'}

prompt = """
Hey, can you write run some python code to turn on the lights, wait 10s and then turn off the lights?
"""

tools = [
    {'code_execution': {}},
    {'function_declarations': [turn_on_the_lights_schema, turn_off_the_lights_schema]}
]

await run(prompt, tools=tools, modality="AUDIO")
```

#### JavaScript Implementation

```javascript
// Light control schemas
const turnOnTheLightsSchema = { name: 'turn_on_the_lights' };
const turnOffTheLightsSchema = { name: 'turn_off_the_lights' };

const prompt = `
Hey, can you write run some python code to turn on the lights, wait 10s and then turn off the lights?
`;

const tools = [
  { codeExecution: {} },
  { functionDeclarations: [turnOnTheLightsSchema, turnOffTheLightsSchema] },
];

await run(prompt, (tools = tools), (modality = 'AUDIO'));
```

### Multi-tool Use Example

#### Python Implementation

```python
# Multiple tasks example - combining lights, code execution, and search
prompt = """
Hey, I need you to do three things for me.
1. Turn on the lights.
2. Then compute the largest prime palindrome under 100000.
3. Then use Google Search to look up information about the largest earthquake in California the week of Dec 5 2024.
Thanks!
"""

tools = [
    {'google_search': {}},
    {'code_execution': {}},
    {'function_declarations': [turn_on_the_lights_schema, turn_off_the_lights_schema]}
]

# Execute the prompt with specified tools in audio modality
await run(prompt, tools=tools, modality="AUDIO")
```

#### JavaScript Implementation

```javascript
// Multiple tasks example - combining lights, code execution, and search
const prompt = `
Hey, I need you to do three things for me.
1. Turn on the lights.
2. Then compute the largest prime palindrome under 100000.
3. Then use Google Search to look up information about the largest earthquake in California the week of Dec 5 2024.
Thanks!
`;

const tools = [
  { googleSearch: {} },
  { codeExecution: {} },
  { functionDeclarations: [turnOnTheLightsSchema, turnOffTheLightsSchema] },
];

// Execute the prompt with specified tools in audio modality
await run(prompt, { tools: tools, modality: 'AUDIO' });
```

## WebSocket Setup

**Note**: The `run()` function declaration handles the asynchronous WebSocket setup. While the specific implementation is omitted for brevity in the examples above, it manages:

- WebSocket connection establishment
- Real-time message streaming
- Tool execution coordination
- Response handling

## Available Tools in Live API

### Native Tools

1. **Google Search**: `{'google_search': {}}`

   - Enables real-time web search capabilities
   - Returns current information from Google Search

2. **Code Execution**: `{'code_execution': {}}`
   - Allows the model to execute Python code
   - Useful for calculations, data processing, and computational tasks

### Custom Function Declarations

- User-defined functions with OpenAPI schema
- Support for complex parameter types
- Real-time execution and response handling

## Model Support

| Model                 | Live API Support | Compositional Function Calling | Multi-tool Use |
| --------------------- | ---------------- | ------------------------------ | -------------- |
| Gemini 2.0 Flash      | ✔️               | ✔️                             | ✔️             |
| Gemini 1.5 Flash      | ✔️               | ✔️                             | ✔️             |
| Gemini 1.5 Pro        | ✔️               | ✔️                             | ✔️             |
| Gemini 2.0 Flash-Lite | ❌               | ❌                             | ❌             |

## Key Limitations

1. **Exclusive Features**: Compositional function calling and multi-tool use are **Live API only** features
2. **WebSocket Requirement**: Real-time features require WebSocket connections
3. **Model Restrictions**: Not all Gemini models support Live API features
4. **Implementation Complexity**: Requires asynchronous programming patterns

## Best Practices for Live API

### 1. **Tool Selection**

- Limit active tools to 10-20 for optimal performance
- Use dynamic tool selection based on conversation context
- Combine complementary tools (e.g., search + code execution)

### 2. **Error Handling**

```python
try:
    await run(prompt, tools=tools, modality="AUDIO")
except WebSocketException as e:
    # Handle connection issues
    pass
except ToolExecutionError as e:
    # Handle tool execution failures
    pass
```

### 3. **Resource Management**

- Properly close WebSocket connections
- Monitor tool execution timeouts
- Implement retry mechanisms for failed operations

### 4. **Security Considerations**

- Validate all tool inputs
- Implement proper authentication for external APIs
- Monitor and log tool executions
- Use appropriate rate limiting

## Advanced Usage Patterns

### Sequential Tool Execution

The Live API automatically handles dependencies between tool calls:

```
User Request → Location Tool → Weather Tool → Response
```

### Parallel Tool Execution

Multiple independent tools can run simultaneously:

```
User Request → [Light Control + Music Control + Search] → Combined Response
```

### Conditional Tool Chains

Tools can be chained based on conditional logic:

```
User Request → Condition Check → Tool A or Tool B → Follow-up Tool → Response
```

## Integration Examples

### Chat Applications

- Real-time conversation with tool assistance
- Audio input/output processing
- Dynamic tool selection based on context

### Smart Home Control

- Voice-activated device control
- Sensor data integration
- Automated task sequences

### Development Assistants

- Code execution and testing
- Real-time documentation lookup
- Multi-step problem solving

## Troubleshooting

### Common Issues

1. **WebSocket Connection Failures**

   - Check network connectivity
   - Verify API credentials
   - Monitor connection timeouts

2. **Tool Execution Errors**

   - Validate tool schemas
   - Check parameter types
   - Monitor external API responses

3. **Performance Issues**
   - Reduce number of concurrent tools
   - Optimize tool response times
   - Implement proper caching
