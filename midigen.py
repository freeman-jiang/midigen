import argparse

import tokenizer


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
        tokens = tokenizer.read_tokens_from_file(args.input_file)
    else:
        # Convert MIDI to tokens
        tokens = tokenizer.midi_to_tokens(args.input_file)
    
    if args.print_tokens:
        print("Token sequence:")
        print(tokens)
        print(f"Total tokens: {len(tokens)}")
    
    if args.print_readable:
        print("Human-readable token sequence:")
        for token in tokens:
            print(tokenizer.token_to_readable(token))
    
    # Convert tokens back to MIDI if output file is specified
    if args.output:
        tokenizer.tokens_to_midi(tokens, args.output, velocity=args.velocity)
        print(f"Converted tokens back to MIDI: {args.output}")

if __name__ == "__main__":
    main()