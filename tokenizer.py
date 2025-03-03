import ast
from collections import defaultdict

# Define token ranges as specified in the document
# Note events (0-255)
NOTE_ON_MIN, NOTE_ON_MAX = 0, 127  # NOTE_ON tokens
NOTE_OFF_MIN, NOTE_OFF_MAX = 128, 255  # NOTE_OFF tokens

# Time-shift events (256-287) - 32 tokens
# Quantized time deltas spanning typical musical durations
TIME_SHIFT_BASE = 256
TIME_SHIFTS = [
    10,    # 256: TIME_SHIFT 10 ticks (≈1/64 note at 480 PPQN)
    20,    # 257: TIME_SHIFT 20 ticks
    30,    # 258: TIME_SHIFT 30 ticks (≈1/32 note triplet)
    40,    # 259: TIME_SHIFT 40 ticks (≈1/32 note)
    60,    # 260: TIME_SHIFT 60 ticks (≈1/16 note triplet)
    80,    # 261: TIME_SHIFT 80 ticks (≈1/16 dotted note)
    120,   # 262: TIME_SHIFT 120 ticks (16th note)
    160,   # 263: TIME_SHIFT 160 ticks (≈dotted 16th note)
    240,   # 264: TIME_SHIFT 240 ticks (8th note)
    320,   # 265: TIME_SHIFT 320 ticks (≈dotted 8th note)
    480,   # 266: TIME_SHIFT 480 ticks (quarter note)
    640,   # 267: TIME_SHIFT 640 ticks (≈dotted quarter note)
    960,   # 268: TIME_SHIFT 960 ticks (half note)
    1920,  # 269: TIME_SHIFT 1920 ticks (whole note)
]

# Add additional time shifts for tokens 270-287
# Additional powers of 2 and common values (up to ~2 bars)
additional_shifts = [
    2400,  # 270: TIME_SHIFT 2400 ticks (1.25 whole notes)
    2880,  # 271: TIME_SHIFT 2880 ticks (1.5 whole notes)
    3360,  # 272: TIME_SHIFT 3360 ticks (1.75 whole notes)
    3840,  # 273: TIME_SHIFT 3840 ticks (2 whole notes)
    4320,  # 274: TIME_SHIFT 4320 ticks (2.25 whole notes)
    4800,  # 275: TIME_SHIFT 4800 ticks (2.5 whole notes)
    5280,  # 276: TIME_SHIFT 5280 ticks (2.75 whole notes)
    5760,  # 277: TIME_SHIFT 5760 ticks (3 whole notes)
    6240,  # 278: TIME_SHIFT 6240 ticks (3.25 whole notes)
    6720,  # 279: TIME_SHIFT 6720 ticks (3.5 whole notes)
    7200,  # 280: TIME_SHIFT 7200 ticks (3.75 whole notes)
    7680,  # 281: TIME_SHIFT 7680 ticks (4 whole notes)
    8160,  # 282: TIME_SHIFT 8160 ticks (4.25 whole notes)
    8640,  # 283: TIME_SHIFT 8640 ticks (4.5 whole notes)
    9120,  # 284: TIME_SHIFT 9120 ticks (4.75 whole notes)
    9600,  # 285: TIME_SHIFT 9600 ticks (5 whole notes)
    10080, # 286: TIME_SHIFT 10080 ticks (5.25 whole notes)
    10560  # 287: TIME_SHIFT 10560 ticks (5.5 whole notes)
]
TIME_SHIFTS.extend(additional_shifts)
assert len(TIME_SHIFTS) == 32, f"Expected 32 time shifts, got {len(TIME_SHIFTS)}"

# Create mappings for time shifts
TIME_SHIFT_MAP = {shift: TIME_SHIFT_BASE + i for i, shift in enumerate(TIME_SHIFTS)}
REVERSE_TIME_SHIFT_MAP = {TIME_SHIFT_BASE + i: shift for i, shift in enumerate(TIME_SHIFTS)}

# Special tokens
START_SEQUENCE = 288  # Token to mark the beginning of a sequence
END_SEQUENCE = 289    # Token to mark the end of a sequence

def find_closest_time_shift(delta_time):
    """Find the closest time-shift token for a given delta time."""
    if delta_time == 0:
        return None  # No time shift needed
    
    # Find the closest time-shift value
    closest_shift = min(TIME_SHIFTS, key=lambda x: abs(x - delta_time))
    
    # Get the corresponding token
    return TIME_SHIFT_MAP[closest_shift]

def midi_to_tokens(midi_file):
    """Convert a MIDI file to a sequence of tokens according to the specified tokenization scheme."""
    import mido

    # Load the MIDI file
    mid = mido.MidiFile(midi_file)
    
    # Extract all note events with absolute time
    events = []
    
    for track in mid.tracks:
        absolute_time = 0
        
        for msg in track:
            absolute_time += msg.time
            
            if msg.type == 'note_on' and msg.velocity > 0:
                # Note on event
                events.append((absolute_time, 'note_on', msg.note))
            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                # Note off event (note_on with velocity 0 is equivalent to note_off)
                events.append((absolute_time, 'note_off', msg.note))
    
    # Sort events by time
    events.sort()
    
    # Convert events to tokens
    tokens = [START_SEQUENCE]
    
    for i, event in enumerate(events):
        time, event_type, note = event
        
        # Add the note event token
        if event_type == 'note_on':
            tokens.append(note)  # NOTE_ON token is the pitch value (0-127)
        else:  # 'note_off'
            tokens.append(note + 128)  # NOTE_OFF token is pitch value + 128 (128-255)
        
        # Add time shift token if there is a next event
        if i < len(events) - 1:
            next_time = events[i+1][0]
            delta_time = next_time - time
            if delta_time > 0:
                time_shift_token = find_closest_time_shift(delta_time)
                if time_shift_token is not None:
                    tokens.append(time_shift_token)
    
    # Add the end sequence token
    tokens.append(END_SEQUENCE)
    
    return tokens

def tokens_to_midi(tokens, output_file, ticks_per_beat=480, velocity=64):
    """Convert a sequence of tokens back to a MIDI file."""
    import mido
    
    mid = mido.MidiFile(ticks_per_beat=ticks_per_beat)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    
    # Skip START_SEQUENCE token if present
    start_idx = 0
    if tokens and tokens[0] == START_SEQUENCE:
        start_idx = 1
    
    # Remove END_SEQUENCE token if present
    end_idx = len(tokens)
    if tokens and tokens[-1] == END_SEQUENCE:
        end_idx = len(tokens) - 1
    
    tokens = tokens[start_idx:end_idx]
    
    current_time = 0
    pending_events = []  # Events to be written with their absolute time
    
    i = 0
    while i < len(tokens):
        token = tokens[i]
        
        if NOTE_ON_MIN <= token <= NOTE_ON_MAX:
            # NOTE_ON token
            note = token
            pending_events.append((current_time, mido.Message('note_on', note=note, velocity=velocity, time=0)))
            
        elif NOTE_OFF_MIN <= token <= NOTE_OFF_MAX:
            # NOTE_OFF token
            note = token - 128
            pending_events.append((current_time, mido.Message('note_off', note=note, velocity=0, time=0)))
            
        elif token in REVERSE_TIME_SHIFT_MAP:
            # TIME_SHIFT token
            time_shift = REVERSE_TIME_SHIFT_MAP[token]
            current_time += time_shift
        
        i += 1
    
    # Sort pending events by time
    pending_events.sort(key=lambda x: x[0])
    
    # Convert absolute times to delta times
    last_time = 0
    for abs_time, msg in pending_events:
        delta_time = abs_time - last_time
        msg.time = int(delta_time)  # Convert to integer to ensure MIDI compatibility
        track.append(msg)
        last_time = abs_time
    
    mid.save(output_file)

def token_to_readable(token):
    """Convert a token to a human-readable string."""
    if token == START_SEQUENCE:
        return "START_SEQUENCE"
    elif token == END_SEQUENCE:
        return "END_SEQUENCE"
    elif NOTE_ON_MIN <= token <= NOTE_ON_MAX:
        return f"NOTE_ON {token}"
    elif NOTE_OFF_MIN <= token <= NOTE_OFF_MAX:
        return f"NOTE_OFF {token - 128}"
    elif token in REVERSE_TIME_SHIFT_MAP:
        return f"TIME_SHIFT {REVERSE_TIME_SHIFT_MAP[token]}"
    else:
        return f"UNKNOWN {token}"

def read_tokens_from_file(file_path):
    """Read tokens from a text file."""
    with open(file_path, 'r') as f:
        content = f.read()
        try:
            # Try to parse as a Python list
            return ast.literal_eval(content)
        except:
            # If not a Python list, assume one token per line
            return [int(line.strip()) for line in content.split('\n') if line.strip()] 