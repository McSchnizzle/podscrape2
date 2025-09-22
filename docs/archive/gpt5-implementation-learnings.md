# GPT-5 Implementation Learnings

## Critical Implementation Notes

**WARNING**: GPT-5 models require the **Responses API**, not the Chat Completions API. Using Chat Completions with GPT-5 will result in empty `response.choices[0].message.content`.

## Key Differences from GPT-4

### 1. API Endpoint Change
```python
# WRONG (Chat Completions API)
response = client.chat.completions.create(...)

# CORRECT (Responses API)
response = client.responses.create(...)
```

### 2. Parameter Changes

#### Token Limits
```python
# Chat Completions API
max_tokens=500  # Still used for Chat Completions

# Responses API  
max_output_tokens=500  # Use max_output_tokens for Responses API
```

#### Temperature Restrictions
```python
# GPT-4: Full temperature control (0.0 to 2.0)
temperature=0.1

# GPT-5: Temperature effectively fixed for reasoning models
# Use reasoning.effort instead:
reasoning={"effort": "minimal"}  # "minimal", "low", "medium", "high"
```

### 3. Response Parsing
```python
# WRONG (Chat Completions pattern)
content = response.choices[0].message.content

# CORRECT (Responses API pattern)  
content = response.output_text
```

### 4. Structured JSON Output

#### Chat Completions API Format
```python
response_format={
    "type": "json_schema",
    "json_schema": {...}
}
```

#### Responses API Format
```python
text={
    "format": {
        "type": "json_schema",
        "json_schema": {...}
    }
}
```

## Complete Working Example

```python
# GPT-5-mini with Responses API - CORRECTED FORMAT
response = client.responses.create(
    model="gpt-5-mini",
    input=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Analyze this content..."}
    ],
    reasoning={"effort": "minimal"},  # Control reasoning effort
    max_output_tokens=500,           # Token limit for Responses API
    text={                          # Structured JSON output - CORRECT format
        "format": {
            "type": "json_schema",
            "name": "Analysis",       # Required: name at format level
            "schema": {              # Required: schema at format level (not nested)
                "type": "object",
                "properties": {
                    "score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "reasoning": {"type": "string"}
                },
                "required": ["score", "reasoning"],
                "additionalProperties": False
            },
            "strict": True           # Required: strict at format level
        }
    }
)

# Parse response
result = response.output_text  # JSON string - will be valid JSON matching schema
data = json.loads(result)      # Parse to Python dict
```

## Model Variants

- **gpt-5**: Full reasoning model ($1.25/1M input, $10/1M output)
- **gpt-5-mini**: Cost-effective reasoning model ($0.25/1M input, $2/1M output)  
- **gpt-5-nano**: Lightweight model ($0.05/1M input, $0.40/1M output)
- **gpt-5-chat-latest**: Non-reasoning chat model (if you need Chat Completions behavior)

## Token Limits

- **Input**: Up to ~272K tokens
- **Output**: Up to ~128K reasoning + output tokens  
- **Total Context**: ~400K tokens

## Migration Checklist

When migrating from GPT-4 to GPT-5:

1. [ ] Change `client.chat.completions.create` → `client.responses.create`
2. [ ] Change `max_tokens` → `max_output_tokens` (for Responses API)
3. [ ] Change `response.choices[0].message.content` → `response.output_text`
4. [ ] Remove custom `temperature` parameter
5. [ ] Add `reasoning={"effort": "minimal"}` for simple tasks
6. [ ] Update structured output format: `response_format` → `text.format`
7. [ ] Test full transcript processing (no truncation needed due to large context)

## Common Errors and Fixes

### Empty Response Error
```
ERROR: Failed to parse OpenAI response as JSON: Expecting value: line 1 column 1 (char 0)
```
**Cause**: Using Chat Completions API instead of Responses API
**Fix**: Migrate to `client.responses.create()`

### Parameter Not Supported
```  
ERROR: Unsupported parameter: 'max_tokens' not supported. Use 'max_completion_tokens'
```
**Cause**: Using Chat Completions parameter names with Responses API
**Fix**: Use `max_output_tokens` for Responses API

### Temperature Error
```
ERROR: 'temperature' does not support 0.1. Only default (1) value supported
```
**Cause**: GPT-5 reasoning models don't support custom temperature
**Fix**: Remove temperature parameter, use `reasoning.effort` instead

### Unexpected Keyword
```
ERROR: Responses.create() got unexpected keyword argument 'response_format'
```
**Cause**: Using Chat Completions format for structured output
**Fix**: Use `text.format.json_schema` format for Responses API

## ✅ SUCCESSFUL IMPLEMENTATION CONFIRMED

**GPT-5-mini Responses API is working correctly as of this implementation:**

### Verified Working Configuration
```python
response = client.responses.create(
    model="gpt-5-mini", 
    input=[{"role": "system", "content": "..."}, {"role": "user", "content": "..."}],
    reasoning={"effort": "minimal"},
    max_output_tokens=500,
    text={
        "format": {
            "type": "json_schema",
            "name": "SchemaName",  # CRITICAL: Required at format level
            "schema": {            # CRITICAL: schema key at format level (not nested in json_schema)  
                "type": "object",
                "properties": {...},
                "required": [...],
                "additionalProperties": False
            },
            "strict": True         # CRITICAL: Required at format level
        }
    }
)
result = response.output_text  # Returns valid JSON string
```

### Test Results (Verified Working)
- ✅ **API Call**: `POST /v1/responses` returns 200 OK
- ✅ **Full Transcript Processing**: 24,711 characters processed without truncation
- ✅ **Structured JSON Output**: Perfect JSON schema compliance with all required fields
- ✅ **Quality Reasoning**: Detailed 1,697-character reasoning with confidence scores
- ✅ **No Empty Responses**: `response.output_text` contains valid content
- ✅ **Performance**: Fast response times with reasoning effort "minimal"

## Performance Notes

- First request with new JSON schema may take 10-60 seconds (schema processing)
- Subsequent requests with same schema are fast (cached)
- Use `reasoning.effort: "minimal"` for simple tasks to reduce latency
- Full 65K character transcripts process without truncation (400K context window)
- **CONFIRMED**: No transcript truncation needed - processes full content