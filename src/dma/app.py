#!/usr/bin/env python

"""
Main entry point for the DMA application.

Uses argparse subparsers to route to different modules (web, cli, build-memory).
If no module is specified, it defaults to 'web'.

Usage:
    python -m dma [mode] [options]

Examples:
    python -m dma
        (Defaults to web mode)
        -> Starting web server on 0.0.0.0:8000 (debug=False)

    python -m dma --port 8080 --debug
        (Defaults to web mode and passes args)
        -> Starting web server on 0.0.0.0:8080 (debug=True)

    python -m dma cli --config my_config.yaml
        -> Starting CLI with config: my_config.yaml

    python -m dma build-memory --type wikipedia --category "Artificial intelligence"
        -> Building memory of type: wikipedia
        -> Using root category: Artificial intelligence
"""

import argparse
import sys

import logging

# --- Module Functions ---
# Each function now accepts the parsed 'args' object as its only parameter.
# They no longer do any argument parsing themselves.

def launch_web(args):
    """Launches the web server with given arguments."""
    print(f"Starting web server on {args.host}:{args.port} (debug={args.debug})")
    from dma.webui import launch_webui
    
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
        
    launch_webui(host=args.host, port=args.port)
    

def launch_cli(args):
    """Launches the CLI with given arguments."""
    # print(f"Starting CLI with config: {args.config}")
    from .cli import main as launch_cli_main
    launch_cli_main()

def launch_build_memory(args):
    """Launches the memory builder with given arguments."""
    print(f"Building memory of type: {args.type}")
    
    # only wikipedia type is implemented for now
    if args.type != "wikipedia":
        print(f"Memory type '{args.type}' is not yet implemented.")
        return
    
    from dma.extraction import build_memory_of_type
    build_memory_of_type(memory_type=args.type, category=args.category, remove_existing=args.remove_existing)

def create_parser():
    """Creates the main argument parser with subparsers for each mode."""
    
    # 1. Create the main parser
    parser = argparse.ArgumentParser(
        description="DMA Application Launcher.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        # Add the usage examples to the help message
        epilog=__doc__.split("Usage:")[1] 
    )
    
    # 2. Add subparsers container
    # 'dest='mode'' stores the name of the subcommand used (e.g., 'web', 'cli')
    subparsers = parser.add_subparsers(dest='mode', help='Available modes')

    # --- Web Subparser ('web') ---
    web_parser = subparsers.add_parser(
        'web', 
        help='Launch the web server (default if no mode is specified)',
        description="Launch the DMA Web Server."
    )
    web_parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind the web server to (default: 0.0.0.0)")
    web_parser.add_argument("--port", type=int, default=8000, help="Port for the web server (default: 8000)")
    web_parser.add_argument("--debug", action="store_true", help="Enable debug mode (e.g., for auto-reload)")
    # Link this subparser to its function
    web_parser.set_defaults(func=launch_web)

    # --- CLI Subparser ('cli') ---
    cli_parser = subparsers.add_parser(
        'cli', 
        help='Launch the CLI interface',
        description="Launch the DMA Command Line Interface."
    )
    cli_parser.add_argument("--config", type=str, default="config.yaml", help="Path to configuration file (default: config.yaml)")
    cli_parser.set_defaults(func=launch_cli)

    # --- Build-Memory Subparser ('build-memory') ---
    build_parser = subparsers.add_parser(
        'build-memory', 
        help='Launch the memory builder',
        description="Launch the DMA Memory Builder."
    )
    build_parser.add_argument(
        "--type",
        type=str,
        choices=["wikipedia", "mediawiki", "directory"],
        required=True,
        help="Type of memory to build"
    )
    build_parser.add_argument("--category", type=str, help="Root category for Wikipedia/MediaWiki crawl (required for this type). Separate multiple categories with commas.")
    build_parser.add_argument("--path", type=str, help="Path for directory memory (required for this type)")
    build_parser.add_argument("-rm", "--remove-existing", action="store_true", help="Remove existing memory before building new one")
    build_parser.set_defaults(func=launch_build_memory)
    
    return parser

def launch():
    """
    Main entry point.
    Parses arguments, handles the default 'web' mode, and calls the appropriate function.
    """
    parser = create_parser()
    
    # --- Default Subcommand Logic ---
    # Get all args after the script name (sys.argv[0])
    args_list = sys.argv[1:]
    
    # Get the names of all defined sub-commands
    known_modes = parser._subparsers._actions[1].choices.keys()

    # If no args are given, or the first arg is not a known mode (and not a help flag),
    # we inject 'web' as the default command.
    if not args_list or (args_list[0] not in known_modes and args_list[0] not in ['-h', '--help', '--version']):
        # Insert 'web' at the beginning of the argument list (after the script name)
        sys.argv.insert(1, 'web')
    
    # --- Parse and Execute ---
    args = parser.parse_args()
    
    if hasattr(args, 'func'):
        # Call the function that was linked using set_defaults()
        args.func(args)
    else:
        # This handles cases like 'python app.py -h' or just 'python app.py'
        # if the default logic was not applied (e.g., if 'web' wasn't a subcommand)
        print("No mode specified. Use -h for help.")
        parser.print_help()

if __name__ == "__main__":
    launch()