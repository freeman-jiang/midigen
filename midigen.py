import argparse
import ast
from collections import defaultdict

import mido

# Define token ranges as specified in the document
# Note events (0-255)
NOTE_ON_MIN, NOTE_ON_MAX = 0, 127  # NOTE_ON tokens
NOTE_OFF_MIN, NOTE_OFF_MAX = 128, 255  # NOTE_OFF tokens

# Time-shift events (256-287) - 32 tokens
TIME_SHIFT_BASE = 256
TIME_SHIFTS = [
    10, 20, 30, 40, 60, 80, 120, 160, 240, 320, 480, 640, 960, 1920
]

# Add additional time shifts for tokens 270-287
additional_shifts = [
    2400, 2880, 3360, 3840, 4320, 4800, 5280, 5760, 
    6240, 6720, 7200, 7680, 8160, 8640, 9120, 9600, 
    10080, 10560
]
TIME_SHIFTS.extend(additional_shifts)
assert len(TIME_SHIFTS) == 32, f"Expected 32 time shifts, got {len(TIME_SHIFTS)}"

# Create mappings for time shifts
TIME_SHIFT_MAP = {shift: TIME_SHIFT_BASE + i for i, shift in enumerate(TIME_SHIFTS)}
REVERSE_TIME_SHIFT_MAP = {TIME_SHIFT_BASE + i: shift for i, shift in enumerate(TIME_SHIFTS)}

# Special tokens
START_SEQUENCE = 288
END_SEQUENCE = 289

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

def main():
    parser = argparse.ArgumentParser(description='Convert MIDI files to tokens and back')
    parser.add_argument('input_file', help='Input MIDI file or token file (.txt)')
    parser.add_argument('--output', '-o', help='Output file (for conversion back to MIDI)')
    parser.add_argument('--print-tokens', '-p', action='store_true', help='Print the tokens')
    parser.add_argument('--print-readable', '-r', action='store_true', help='Print human-readable token descriptions')
    parser.add_argument('--velocity', '-v', type=int, default=64, help='Velocity for note-on events (default: 64)')
    
    args = parser.parse_args()
    
    # Check if input is a token file
    if args.input_file.endswith('.txt'):
        tokens = read_tokens_from_file(args.input_file)
    else:
        # Convert MIDI to tokens
        tokens = midi_to_tokens(args.input_file)
    
    if args.print_tokens:
        print("Token sequence:")
        print(tokens)
        print(f"Total tokens: {len(tokens)}")
    
    if args.print_readable:
        print("Human-readable token sequence:")
        for token in tokens:
            print(token_to_readable(token))
    
    # Convert tokens back to MIDI if output file is specified
    if args.output:
        tokens_to_midi(tokens, args.output, velocity=args.velocity)
        print(f"Converted tokens back to MIDI: {args.output}")

if __name__ == "__main__":
    main()