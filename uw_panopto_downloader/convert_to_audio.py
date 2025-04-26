import argparse
import os
import subprocess
import glob
import sys
import time
import multiprocessing

def find_mp4_files(directory):
    """Find all MP4 files in a directory and its subdirectories."""
    return glob.glob(os.path.join(directory, "**", "*.mp4"), recursive=True)

def convert_file(mp4_path, output_path, bitrate="192k", threads=0):
    """Convert a single MP4 file to MP3 using FFmpeg."""
    # Skip if output file already exists
    if os.path.exists(output_path):
        print(f"Skipping existing file: {output_path}")
        return True

    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Set thread count
    if threads <= 0:
        threads = multiprocessing.cpu_count()

    # Run FFmpeg command
    cmd = [
        "ffmpeg",
        "-i", mp4_path,
        "-threads", str(threads),
        "-vn",                     # No video
        "-b:a", bitrate,           # Audio bitrate
        "-c:a", "libmp3lame",      # MP3 codec
        "-map_metadata", "0",      # Copy metadata
        "-stats",                  # Show progress
        "-y",                      # Overwrite output
        output_path
    ]

    print(f"Converting: {os.path.basename(mp4_path)} -> {os.path.basename(output_path)}")

    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error converting {mp4_path}: {e}")
        return False

def convert_directory(input_dir, output_dir=None, bitrate="192k", threads=0):
    """Process all MP4 files in a directory and convert to MP3."""
    # Find all MP4 files
    mp4_files = find_mp4_files(input_dir)
    if not mp4_files:
        print(f"No MP4 files found in {input_dir}")
        return

    print(f"Found {len(mp4_files)} MP4 files to convert")

    # Process each file
    successful = 0
    failed = 0
    start_time = time.time()

    for i, mp4_path in enumerate(mp4_files, 1):
        try:
            # Determine output path
            if output_dir:
                rel_path = os.path.relpath(mp4_path, input_dir)
                output_path = os.path.join(output_dir, os.path.splitext(rel_path)[0] + ".mp3")
            else:
                output_path = os.path.splitext(mp4_path)[0] + ".mp3"

            # Convert the file
            print(f"\n[{i}/{len(mp4_files)}] ", end="")
            if convert_file(mp4_path, output_path, bitrate, threads):
                successful += 1
            else:
                failed += 1

        except Exception as e:
            print(f"Unexpected error processing {mp4_path}: {e}")
            failed += 1

    elapsed_time = time.time() - start_time
    print(f"\nConversion completed: {successful} successful, {failed} failed")
    print(f"Total time elapsed: {elapsed_time:.2f} seconds")

def main():
    parser = argparse.ArgumentParser(description="Convert MP4 files to MP3 format.")
    parser.add_argument("input", help="Input MP4 file or directory containing MP4 files")
    parser.add_argument("-o", "--output", help="Output MP3 file or directory")
    parser.add_argument("-b", "--bitrate", default="192k", help="Audio bitrate (default: 192k)")
    parser.add_argument("-t", "--threads", type=int, default=0,
                        help="Number of threads for FFmpeg to use (0=auto, default: 0)")

    args = parser.parse_args()

    if os.path.isdir(args.input):
        convert_directory(args.input, args.output, args.bitrate, args.threads)
    elif os.path.isfile(args.input) and args.input.endswith('.mp4'):
        output_path = args.output
        if output_path is None:
            output_path = os.path.splitext(args.input)[0] + ".mp3"
        elif os.path.isdir(output_path):
            output_path = os.path.join(output_path, os.path.splitext(os.path.basename(args.input))[0] + ".mp3")

        start_time = time.time()
        success = convert_file(args.input, output_path, args.bitrate, args.threads)
        elapsed_time = time.time() - start_time

        if success:
            print(f"Conversion completed successfully in {elapsed_time:.2f} seconds")
        else:
            print(f"Conversion failed after {elapsed_time:.2f} seconds")
    else:
        print("Input must be an MP4 file or a directory containing MP4 files")
        sys.exit(1)

if __name__ == "__main__":
    main()