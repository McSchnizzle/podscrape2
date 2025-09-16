# FFmpeg Chunking Debug Investigation

## Problem Summary
FFmpeg chunking fails **only** when run via Web UI → Orchestrator → Audio Script, but works perfectly in all other contexts.

## What Works ✅
1. **Direct AudioProcessor test** (3-min chunks): ✅ All 24 chunks complete
2. **Direct AudioProcessor test** (5-min chunks): ✅ All 15 chunks complete
3. **Subprocess execution test**: ✅ All 15 chunks complete via subprocess.Popen
4. **My FFmpeg fix implementation**: ✅ Removed threading, simplified subprocess.run with timeout

## What Fails ❌
- **Web UI → Orchestrator execution**: ❌ Hangs at chunk 5 (1200s mark) after exactly 300 seconds
- **Logs**: `pipeline_run_20250915_190302.log`, `pipeline_run_20250915_190950.log`

## Technical Details

### FFmpeg Fix Applied
- **Removed**: Complex `_run_ffmpeg_with_timeout()` with threading
- **Added**: Simple `subprocess.run(cmd, capture_output=True, text=True, timeout=300)`
- **File**: `src/podcast/audio_processor.py:224-243`

### Web UI Configuration
- **Chunk Duration**: 5 minutes (set in web_settings database)
- **Expected Chunks**: 15 chunks for 69-minute audio file
- **Failure Point**: Always chunk 5 at 1200s (20-minute mark)

### Execution Chain
```
Web UI (app.py:1009)
  → subprocess.Popen(run_full_pipeline_orchestrator.py)
    → scripts/run_audio.py
      → AudioProcessor.chunk_audio()
        → subprocess.run(ffmpeg) ← HANGS HERE
```

### Key Differences
1. **Direct test**: AudioProcessor() with default 3-min chunks → Works
2. **Orchestrator**: AudioProcessor(chunk_duration_minutes=5) via web config → Fails
3. **Subprocess test**: Same 5-min chunks via subprocess.Popen → Works!

## Critical Discovery
The subprocess execution itself is NOT the problem. My test that mimics Web UI subprocess behavior works perfectly:
```python
subprocess.Popen([python, '-c', 'AudioProcessor.chunk_audio()'], stdout=file, stderr=file)
# ✅ All 15 chunks complete successfully
```

## Root Cause Hypothesis
The issue is **specific to the orchestrator/audio script implementation**, not subprocess execution or FFmpeg itself.

Possible causes:
1. **Environment difference** in orchestrator vs direct execution
2. **Signal handling** in the orchestrator chain
3. **Resource management** in the audio script
4. **Import/initialization difference** between scripts
5. **Database connection** or **web config** interaction causing deadlock

## Files to Investigate
- `run_full_pipeline_orchestrator.py` - Main orchestrator
- `scripts/run_audio.py` - Audio phase script (line 237: chunk_audio call)
- `web_ui/app.py:1009` - Web UI subprocess execution
- Database interaction in audio script vs direct execution

## Next Steps
1. Compare exact environment/imports between working subprocess test and failing orchestrator
2. Check if database connections or web config cause blocking
3. Investigate signal handling in orchestrator vs direct execution
4. Check if there are differences in how AudioProcessor is instantiated

## Test Commands
```bash
# Works ✅
python3 test_ffmpeg_5min.py

# Works ✅
python3 test_subprocess_ffmpeg.py

# Fails ❌
# Via Web UI: Run pipeline button
```

## Status
- **FFmpeg fix**: ✅ Completed and verified in isolation
- **Root cause**: ✅ Identified - Database connection accumulation in orchestrator execution chain
- **Solution**: ✅ Implemented database connection management fixes in audio script

## Solution Implementation

### Root Cause Identified
The FFmpeg hang at chunk 5 was NOT an FFmpeg issue, but a **database connection pool exhaustion** problem in the orchestrator execution chain:

1. **Connection Accumulation**: The audio script was creating multiple database connections that weren't properly cleaned up
2. **Resource Competition**: Web UI → Orchestrator → Audio Script created competing database connections
3. **File Descriptor Limit**: After processing 4-5 chunks, the system hit resource limits causing FFmpeg to hang

### Fix Applied
Modified `scripts/run_audio.py` with:

1. **Explicit Connection Management**: Added connection tracking and cleanup in `AudioProcessor_Runner.__init__()`
2. **Web Config Optimization**: Minimized database usage by immediately closing web config connections
3. **Context Manager Pattern**: Added `__enter__`/`__exit__` methods for proper resource cleanup
4. **Garbage Collection**: Added explicit cleanup after each episode processing
5. **Resource Cleanup**: Ensured all database connections are properly closed

### Test Results
- **Before Fix**: Audio script hangs at chunk 5 after exactly 300 seconds
- **After Fix**: Audio script completes successfully in 3.1 seconds
- **Subprocess Test**: Still works perfectly (confirms FFmpeg itself was never the issue)

### Files Modified
- `scripts/run_audio.py`: Lines 43-67, 106-123, 401-427 - Database connection management fixes

## Verification
```bash
# Test the fix
python3 test_orchestrator_fix.py
# ✅ Audio script test passed - database connection fix appears to work
```

**UPDATE**: The issue is NOT yet resolved. Despite implementing database connection fixes, the problem persists.

## Attempted Solutions (All Failed to Resolve)

### 1. FFmpeg Threading Fix ✅ (But didn't solve the orchestrator issue)
- **Changed**: Removed complex `_run_ffmpeg_with_timeout()` with threading
- **To**: Simple `subprocess.run(cmd, capture_output=True, text=True, timeout=300)`
- **Result**: Fixed direct FFmpeg execution but orchestrator still hangs

### 2. Database Connection Management ❌ (Seemed promising but failed)
- **Added**: Explicit connection tracking and cleanup in `AudioProcessor_Runner.__init__()`
- **Added**: Context manager pattern with `__enter__`/`__exit__` methods
- **Added**: Immediate web config connection cleanup
- **Added**: Garbage collection after each episode
- **Result**: Works in dry-run mode but still hangs in actual execution

### 3. Resource Cleanup Improvements ❌
- **Added**: Force cleanup of database connections between chunks
- **Added**: Explicit memory management and garbage collection
- **Result**: No change in hang behavior

## Why It Still Fails

Despite all attempted fixes, the issue persists with these consistent patterns:
- **Always hangs at chunk 5** (1200s/20-minute mark)
- **Exactly 300 seconds timeout** before hanging
- **Only fails in orchestrator chain**: Web UI → Orchestrator → Audio Script
- **Works perfectly in isolation** and simple subprocess tests

## Top 5 Remaining Problem Hypotheses

### 1. **Nested Subprocess Timeout Conflict** 🔥 (Most Likely)
The orchestrator has multiple timeout layers:
- Web UI subprocess.Popen (no explicit timeout)
- Orchestrator process timeout (7200 seconds)
- Audio script subprocess timeout (300 seconds per chunk)
- FFmpeg subprocess timeout (300 seconds)

**Theory**: At chunk 5 (20 minutes total), multiple 300-second timeouts may be stacking or conflicting, causing a deadlock where the parent process times out waiting for FFmpeg while FFmpeg is waiting for parent process signals.

### 2. **File Handle/Descriptor Exhaustion** 🔥
Despite database connection fixes, the deep process chain may be accumulating file descriptors:
- Web UI keeps log file handles open
- Orchestrator streams stdout/stderr in real-time
- Audio script creates temporary chunk files
- FFmpeg opens input/output file handles

**Theory**: By chunk 5, the system hits file descriptor limits causing subprocess.run() to hang waiting for available file handles.

### 3. **Python GIL/Output Streaming Deadlock** 🔥
The orchestrator uses real-time output streaming with line buffering:
```python
process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1)
```

**Theory**: The real-time output reading loop may create a deadlock where:
- Parent process waits for FFmpeg output
- FFmpeg waits for parent to read its output buffer
- Buffer fills up causing mutual blocking

### 4. **Memory/Buffer Overflow in Process Chain**
Audio chunks accumulate in memory through the process chain:
- 69-minute audio file = ~60MB
- 5 chunks × 2MB each = 10MB in chunk files
- Multiple processes holding references to the same data

**Theory**: Memory pressure or buffer overflow causes subprocess creation to fail silently, appearing as a hang.

### 5. **Signal Handling Interference in Deep Process Tree**
The process hierarchy is 4+ levels deep:
```
Web UI → Orchestrator → Audio Script → FFmpeg subprocess
```

**Theory**: Signal masking or handling in the deep process tree prevents proper subprocess communication. When FFmpeg tries to send completion signals, they get lost or mishandled in the chain.

## Critical Observations for Next Debugger

### What Works (Baseline for comparison)
- ✅ `python3 test_ffmpeg_5min.py` - Direct AudioProcessor, 15 chunks, 5-min each
- ✅ `python3 test_subprocess_ffmpeg.py` - Simple subprocess call, same configuration
- ✅ `python3 test_orchestrator_fix.py` - Audio script in dry-run mode

### What Fails (The mystery)
- ❌ Web UI → Orchestrator → Audio Script (full chain)
- ❌ Always at chunk 5, always after 300 seconds
- ❌ Even with all database and resource management fixes

### The 300-Second Mystery
The timing is suspiciously exact:
- Chunk 1-4: Complete in 0.5-3.3 seconds each
- Chunk 5: Hangs for exactly 300 seconds then fails
- 300 seconds = FFmpeg subprocess timeout value

This suggests the hang occurs **during** the subprocess.run() call, not before or after.

## Recommended Next Steps

### 1. Deep Process Monitoring
- Monitor file descriptors: `lsof -p <pid>` during execution
- Monitor memory usage: `ps aux` tracking RSS/VSZ
- Monitor subprocess tree: `pstree -p <pid>`

### 2. Timeout Isolation Testing
- Test with different timeout values (60s, 120s, 600s)
- Remove timeout entirely from subprocess.run()
- Add explicit process group isolation with `os.setsid()`

### 3. Output Buffer Investigation
- Test with unbuffered output: `PYTHONUNBUFFERED=1`
- Remove real-time streaming from orchestrator
- Use simple subprocess.run() without Popen streaming

### 4. Add Extensive Logging
Around `subprocess.run()` in audio_processor.py:
```python
logger.info(f"About to start FFmpeg for chunk {chunk_num+1}")
logger.info(f"Command: {' '.join(cmd)}")
logger.info(f"File descriptors before: {len(os.listdir('/proc/self/fd'))}")
# subprocess.run() call here
logger.info(f"FFmpeg completed for chunk {chunk_num+1}")
```

### 5. Process Isolation Test
Try running audio script with complete process isolation:
- Use `subprocess.Popen()` with new process group
- Test with `nohup` and background execution
- Consider containerization to isolate resource limits

## Files Modified (For Reference)
- `src/podcast/audio_processor.py`: Lines 224-243 (FFmpeg subprocess fix)
- `scripts/run_audio.py`: Lines 43-67, 106-123, 401-427 (Database connection management)

The issue remains **UNRESOLVED** and requires deeper investigation into process management and resource isolation.