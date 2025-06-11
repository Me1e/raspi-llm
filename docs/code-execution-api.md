# Gemini API Code Execution and Live API Comprehensive Guide

## Overview

The Gemini API provides advanced code execution capabilities that enable AI models to generate and run Python code iteratively. This tool is particularly powerful for code-based reasoning, mathematical calculations, data processing, and creating visualizations. The API also supports the Multimodal Live API for bidirectional communication.

## Core Features

### Code Execution Tool

- **Language Support**: Python only (other languages can be generated but not executed)
- **Iterative Learning**: Model learns from execution results and refines code until reaching final output
- **Multi-Part Responses**: Returns text, executable code, and execution results
- **Real-time Processing**: Code runs in a sandboxed environment with immediate feedback

### Multimodal Live API

- **Bidirectional Communication**: Supports real-time, two-way interaction
- **Multi-tool Use**: Can combine code execution with other tools simultaneously
- **Enhanced Interactivity**: Designed for conversational AI applications

## Model Support

### Single Turn Operations

- **Supported Models**: All Gemini 2.0 models
- **Primary Model**: `gemini-2.0-flash` (recommended)

### Bidirectional (Multimodal Live API)

- **Supported Models**: Only Flash experimental models
- **Multi-tool Use**: Supported (unlike single turn)

## Implementation Guide

### Basic Setup

#### Python Implementation

```python
from google import genai
from google.genai import types

client = genai.Client()
response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents="Your calculation request here",
    config=types.GenerateContentConfig(
        tools=[types.Tool(code_execution=types.ToolCodeExecution)]
    ),
)
```

#### JavaScript Implementation

```javascript
import { GoogleGenAI } from '@google/genai';

const ai = new GoogleGenAI({ apiKey: 'GOOGLE_API_KEY' });
let response = await ai.models.generateContent({
  model: 'gemini-2.0-flash',
  contents: ['Your request here'],
  config: {
    tools: [{ codeExecution: {} }],
  },
});
```

#### Go Implementation

```go
package main

import (
    "context"
    "os"
    "google.golang.org/genai"
)

func main() {
    ctx := context.Background()
    client, _ := genai.NewClient(ctx, &genai.ClientConfig{
        APIKey: os.Getenv("GOOGLE_API_KEY"),
        Backend: genai.BackendGeminiAPI,
    })

    config := &genai.GenerateContentConfig{
        Tools: []*genai.Tool{
            {CodeExecution: &genai.ToolCodeExecution{}},
        },
    }

    result, _ := client.Models.GenerateContent(
        ctx,
        "gemini-2.0-flash",
        genai.Text("Your request here"),
        config,
    )
}
```

#### REST API Implementation

```bash
curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=$GOOGLE_API_KEY" \
-H 'Content-Type: application/json' \
-d '{
    "tools": [{"code_execution": {}}],
    "contents": {
        "parts": {
            "text": "Your request here"
        }
    }
}'
```

### Chat Integration

#### Python Chat Setup

```python
chat = client.chats.create(
    model="gemini-2.0-flash",
    config=types.GenerateContentConfig(
        tools=[types.Tool(code_execution=types.ToolCodeExecution)]
    ),
)

response = chat.send_message("Your message here")
```

#### JavaScript Chat Setup

```javascript
const chat = ai.chats.create({
  model: 'gemini-2.0-flash',
  config: {
    tools: [{ codeExecution: {} }],
  },
});

const response = await chat.sendMessage({
  message: 'Your message here',
});
```

## Response Structure

### Content Parts

Each response contains multiple parts with specific naming conventions:

#### Python Naming

- `text`: Model-generated explanatory text
- `executable_code`: Python code ready for execution
- `code_execution_result`: Output from code execution

#### JavaScript Naming

- `text`: Model-generated explanatory text
- `executableCode`: Python code ready for execution
- `codeExecutionResult`: Output from code execution

### Response Processing

```python
for part in response.candidates[0].content.parts:
    if part.text is not None:
        print(part.text)
    if part.executable_code is not None:
        print(part.executable_code.code)
    if part.code_execution_result is not None:
        print(part.code_execution_result.output)
```

## Input/Output Capabilities

### File Input Support

Starting with Gemini 2.0 Flash, the API supports file input for enhanced data processing:

#### Supported Input File Types

- **Images**: `.png`, `.jpeg`
- **Data**: `.csv`, `.xml`
- **Code**: `.cpp`, `.java`, `.py`, `.js`, `.ts`

#### File Input Methods

- `part.inlineData`: Direct data embedding
- `part.fileData`: Files uploaded via Files API

### Graph Output Support

- **Library**: Matplotlib only
- **Format**: Inline images in response
- **Capability**: Automatic graph generation and rendering

### Technical Specifications

#### Runtime Limitations

- **Maximum Runtime**: 30 seconds per execution
- **Error Handling**: Up to 5 automatic regeneration attempts
- **File Size Limit**: 1 million tokens (~2MB for text files)

#### Processing Details

- **Best Performance**: Text and CSV files
- **Output Format**: Always returned as `part.inlineData`
- **Real-time Execution**: Immediate feedback and results

## Feature Comparison Table

| Feature            | Single Turn                                         | Bidirectional (Multimodal Live API)                 |
| ------------------ | --------------------------------------------------- | --------------------------------------------------- |
| Models supported   | All Gemini 2.0 models                               | Only Flash experimental models                      |
| File input types   | .png, .jpeg, .csv, .xml, .cpp, .java, .py, .js, .ts | .png, .jpeg, .csv, .xml, .cpp, .java, .py, .js, .ts |
| Plotting libraries | Matplotlib                                          | Matplotlib                                          |
| Multi-tool use     | No                                                  | Yes                                                 |

## Billing Structure

### Token-Based Pricing

- **No Additional Charges**: Standard model rates apply
- **Single Billing**: Once for input, once for final output

### Input Tokens Include

- User prompt
- Intermediate processing tokens (labeled separately)

### Output Tokens Include

- Generated code
- Code execution results
- Model-generated summaries
- Multimodal output (images, graphs)

### Billing Flow

1. **Initial Input**: User prompt (billed as input tokens)
2. **Intermediate Processing**: Generated code + execution results (billed as input tokens)
3. **Final Output**: Summary + formatted results (billed as output tokens)

### Token Transparency

- API response includes intermediate token count
- Clear breakdown of billing components
- Separate labeling of intermediate tokens

## Supported Libraries

The code execution environment includes comprehensive Python libraries:

### Data Processing

- `numpy` - Numerical computing
- `pandas` - Data manipulation and analysis
- `scipy` - Scientific computing
- `scikit-learn` - Machine learning

### Visualization

- `matplotlib` - Plotting and graphing (only supported for rendering)
- `seaborn` - Statistical data visualization

### File Handling

- `openpyxl` - Excel file processing
- `PyPDF2` - PDF manipulation
- `python-docx` - Word document processing
- `python-pptx` - PowerPoint processing
- `lxml` - XML processing

### Image Processing

- `opencv-python` - Computer vision
- `pillow` - Image manipulation
- `imageio` - Image I/O

### Mathematical Libraries

- `sympy` - Symbolic mathematics
- `mpmath` - Arbitrary precision arithmetic

### Specialized Libraries

- `tensorflow` - Machine learning framework
- `geopandas` - Geographic data processing
- `chess` - Chess game logic
- `fpdf` - PDF generation
- `reportlab` - PDF toolkit

### Utility Libraries

- `attrs` - Python classes
- `joblib` - Lightweight pipelining
- `jsonschema` - JSON schema validation
- `tabulate` - Table formatting

**Important**: Custom library installation is not supported.

## Limitations and Constraints

### Functional Limitations

- **Code Only**: Cannot return media files or other artifacts
- **Python Exclusive**: Only Python code execution supported
- **No Custom Libraries**: Pre-installed libraries only

### Performance Considerations

- **Model Variation**: Different models have varying code execution success rates
- **Potential Regressions**: May impact non-code outputs (e.g., creative writing)
- **Runtime Constraints**: 30-second maximum execution time

### API Constraints

- **Single-turn Multi-tool**: Not supported for single-turn operations
- **File Size**: Limited by model token window
- **Error Recovery**: Maximum 5 automatic retry attempts

## Best Practices

### Effective Usage

1. **Clear Instructions**: Provide specific, detailed prompts
2. **Iterative Approach**: Allow model to refine code through multiple attempts
3. **File Optimization**: Use supported file types for best results
4. **Error Handling**: Account for potential execution failures

### Optimization Tips

1. **Model Selection**: Use `gemini-2.0-flash` for optimal performance
2. **Input Format**: Structure data clearly for better processing
3. **Output Verification**: Always verify code execution results
4. **Resource Management**: Be mindful of 30-second runtime limit

## Integration Patterns

### Mathematical Calculations

- Prime number computations
- Statistical analysis
- Complex equation solving

### Data Analysis

- CSV file processing
- Data visualization
- Pattern recognition

### Code Generation and Testing

- Algorithm implementation
- Code verification
- Performance analysis
