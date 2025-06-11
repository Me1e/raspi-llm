Based on the provided HTML content, I need to clarify that this documentation is about **Gemini API's Grounding with Google Search** feature, not specifically a "Gemini Live API." Here's a comprehensive English documentation based on the content:

# Gemini API: Grounding with Google Search - Complete Guide

## Overview

The Grounding with Google Search feature in the Gemini API and AI Studio enhances the accuracy and recency of model responses by integrating real-time web search capabilities. When enabled, this feature provides:

- **More factual responses** grounded in current information
- **Grounding sources** with in-line supporting links
- **Google Search Suggestions** pointing to relevant search results
- **Enhanced factuality and recency** for time-sensitive queries

## Prerequisites

Before implementing Grounding with Google Search:

1. Install your preferred SDK from the available options
2. Configure and prepare your Gemini API key
3. Ensure proper API authentication setup

## Implementation Methods

### Method 1: Search as a Tool (Gemini 2.0 Flash)

Starting with Gemini 2.0, Google Search is available as a tool that the model can decide when to use autonomously.

#### Basic Configuration

```python
from google import genai
from google.genai.types import Tool, GenerateContentConfig, GoogleSearch

client = genai.Client()
model_id = "gemini-2.0-flash"

google_search_tool = Tool(
    google_search = GoogleSearch()
)

response = client.models.generate_content(
    model=model_id,
    contents="When is the next total solar eclipse in the United States?",
    config=GenerateContentConfig(
        tools=[google_search_tool],
        response_modalities=["TEXT"],
    )
)

# Access response content
for each in response.candidates[0].content.parts:
    print(each.text)

# Access grounding metadata
print(response.candidates[0].grounding_metadata.search_entry_point.rendered_content)
```

#### Key Features of Search as a Tool:

- **Multi-turn searches** capability
- **Complex prompts and workflows** requiring planning and reasoning
- **Various use cases**:
  - Enhancing factuality and recency
  - Retrieving web artifacts for analysis
  - Finding relevant multimedia content
  - Technical troubleshooting and coding assistance
  - Region-specific information gathering
  - Content translation assistance
  - Website discovery for further browsing

#### Limitations:

- Function calling combination not yet supported
- Available in all supported languages for text prompts

### Method 2: Google Search Retrieval (Gemini 1.5 Models Only)

**Important Note**: Google Search retrieval is only compatible with Gemini 1.5 models. For Gemini 2.0 models, the SDK automatically converts to Search Grounding and ignores dynamic threshold settings.

#### Basic Implementation

```python
from google import genai
from google.genai import types

client = genai.Client(api_key="GEMINI_API_KEY")

response = client.models.generate_content(
    model='gemini-1.5-flash',
    contents="Who won the US open this year?",
    config=types.GenerateContentConfig(
        tools=[types.Tool(
            google_search_retrieval=types.GoogleSearchRetrieval()
        )]
    )
)
print(response)
```

#### Dynamic Threshold Configuration

Control retrieval behavior with dynamic threshold settings:

```python
from google import genai
from google.genai import types

client = genai.Client(api_key="GEMINI_API_KEY")

response = client.models.generate_content(
    model='gemini-1.5-flash',
    contents="Who won Roland Garros this year?",
    config=types.GenerateContentConfig(
        tools=[types.Tool(
            google_search_retrieval=types.GoogleSearchRetrieval(
                dynamic_retrieval_config=types.DynamicRetrievalConfig(
                    mode=types.DynamicRetrievalConfigMode.MODE_DYNAMIC,
                    dynamic_threshold=0.6))
        )]
    )
)
print(response)
```

## Dynamic Retrieval System

### Understanding Prediction Scores

The system assigns prediction scores (0-1 range) to prompts based on their need for grounding:

| Prompt                                                            | Prediction Score | Reasoning                          |
| ----------------------------------------------------------------- | ---------------- | ---------------------------------- |
| "Write a poem about peonies"                                      | 0.13             | Model knowledge sufficient         |
| "Suggest a toy for a 2yo child"                                   | 0.36             | Model knowledge sufficient         |
| "Can you give a recipe for an asian-inspired guacamole?"          | 0.55             | Grounding helpful but not required |
| "What's Agent Builder? How is grounding billed in Agent Builder?" | 0.72             | Requires grounded information      |
| "Who won the latest F1 grand prix?"                               | 0.97             | Requires current web information   |

### Threshold Configuration

- **Range**: 0.0 to 1.0 (default: 0.3)
- **Threshold = 0**: Always uses Google Search
- **Threshold > 0**: Uses search only when prediction score ≥ threshold
- **Lower threshold**: More prompts trigger search grounding
- **Higher threshold**: Fewer prompts trigger search grounding

### Optimization Strategy

1. Create representative query sets
2. Analyze prediction scores in responses
3. Sort queries by prediction scores
4. Select optimal threshold for your use case
5. Balance latency, quality, and cost considerations

## Response Structure Analysis

### Successful Grounded Response

When grounding succeeds, responses include `groundingMetadata`:

```json
{
  "candidates": [
    {
      "content": {
        "parts": [
          {
            "text": "Carlos Alcaraz won the Gentlemen's Singles title at the 2024 Wimbledon Championships. He defeated Novak Djokovic in the final, winning his second consecutive Wimbledon title and fourth Grand Slam title overall."
          }
        ],
        "role": "model"
      },
      "groundingMetadata": {
        "searchEntryPoint": {
          "renderedContent": "[HTML content for Google Search Suggestions]"
        },
        "groundingChunks": [
          {
            "web": {
              "uri": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/...",
              "title": "wikipedia.org"
            }
          }
        ],
        "groundingSupports": [
          {
            "segment": {
              "endIndex": 85,
              "text": "Carlos Alcaraz won the Gentlemen's Singles title at the 2024 Wimbledon Championships."
            },
            "groundingChunkIndices": [0, 1, 2, 3],
            "confidenceScores": [0.97380733, 0.97380733, 0.97380733, 0.97380733]
          }
        ],
        "webSearchQueries": ["who won wimbledon 2024"]
      }
    }
  ]
}
```

### Key Response Components

1. **searchEntryPoint**: Contains `renderedContent` for Google Search Suggestions
2. **groundingChunks**: Source websites with redirect URIs and titles
3. **groundingSupports**: Text segments with confidence scores and source indices
4. **webSearchQueries**: Actual search queries used

### URI Access Rules

- **Domain**: `vertexaisearch.cloud.google.com/grounding-api-redirect/...`
- **Accessibility**: 30 days after generation
- **Usage Restriction**: Direct end-user access only, no programmatic querying
- **Violation Consequence**: Service may stop providing redirection URIs

## Google Search Suggestions Requirement

**Mandatory Implementation**: When using Grounding with Google Search, you must display Google Search Suggestions included in the response metadata. The `renderedContent` field provides the necessary HTML/CSS code for implementation.

## URL Context Tool Integration

The URL context tool complements Grounding with Google Search by:

- **Augmenting prompts** with specific URL contexts
- **Combining broad discovery** with in-depth analysis
- **Enabling complex workflows** that require both search and detailed URL content analysis

## Pricing and Limitations

### Free Tier Allowances

- **1,500 queries per day** on paid tier (free)
- **Additional queries**: $35 per 1,000 queries

### Language Support

- Available in all Gemini API supported languages for text prompts

### Model Compatibility

- **Gemini 2.0**: Use Search as a Tool
- **Gemini 1.5**: Use Google Search Retrieval with dynamic threshold options

## Troubleshooting

### No Grounding Metadata

If responses lack `groundingMetadata`, possible causes:

- Low source relevance
- Incomplete model response information
- Threshold settings preventing grounding activation
- Query doesn't benefit from web grounding

### Best Practices

1. **Test threshold values** with representative queries
2. **Monitor prediction scores** to optimize settings
3. **Implement proper error handling** for non-grounded responses
4. **Display Search Suggestions** as required
5. **Respect URI access restrictions** to maintain service availability

## Complete Implementation Example

```python
from google import genai
from google.genai.types import Tool, GenerateContentConfig, GoogleSearch

def setup_grounded_search(api_key, model_version="gemini-2.0-flash"):
    client = genai.Client(api_key=api_key)

    if model_version.startswith("gemini-2.0"):
        # Use Search as a Tool for Gemini 2.0
        google_search_tool = Tool(google_search=GoogleSearch())

        def query_with_grounding(prompt):
            response = client.models.generate_content(
                model=model_version,
                contents=prompt,
                config=GenerateContentConfig(
                    tools=[google_search_tool],
                    response_modalities=["TEXT"],
                )
            )
            return response

    else:
        # Use Search Retrieval for Gemini 1.5
        from google.genai import types

        def query_with_grounding(prompt, threshold=0.3):
            response = client.models.generate_content(
                model=model_version,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(
                        google_search_retrieval=types.GoogleSearchRetrieval(
                            dynamic_retrieval_config=types.DynamicRetrievalConfig(
                                mode=types.DynamicRetrievalConfigMode.MODE_DYNAMIC,
                                dynamic_threshold=threshold
                            )
                        )
                    )]
                )
            )
            return response

    return query_with_grounding

# Usage
query_function = setup_grounded_search("your-api-key")
result = query_function("What are the latest developments in AI technology?")
```
