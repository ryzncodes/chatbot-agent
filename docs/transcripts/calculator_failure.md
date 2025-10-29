# Calculator Tool – Error Handling Transcript

| Speaker | Message | Planner Notes |
| --- | --- | --- |
| User | “calc 2 + two” | `intent=calculate`, slot update `operation=calc 2 + two`, action=`call_calculator` |
| Assistant | “I couldn't compute that expression. Please check the syntax.” | Calculator sanitization rejected invalid token; `tool_success=False` |
| User | “Oops, try 2 + 2.” | Slot update `operation=Oops, try 2 + 2` (raw text), but planner re-evaluates to valid expression |
| Assistant | “4” | Successful calculator call, `tool_success=True` |

**Tool data excerpt (error case)**

```json
{
  "error": "Unsupported character: t"
}
```
